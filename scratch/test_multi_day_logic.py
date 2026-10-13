import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

DB_PATH = 'attendance.db'

def parse_time_to_minutes(t_str: str) -> int:
    try:
        parts = t_str.strip().split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 480

def test_get_detailed_attendance_report(
    target_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    department: Optional[str] = None,
    shift_id: Optional[Any] = None,
    status_filter: Optional[str] = None,
    search_query: Optional[str] = None
) -> Dict[str, Any]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Resolve date targets
        if target_date == 'today' or (not target_date and not start_date):
            cursor.execute("SELECT date('now', 'localtime')")
            target_date = cursor.fetchone()[0]
            start_date = target_date
            end_date = target_date
            is_multi_day = False
        elif target_date == 'yesterday':
            cursor.execute("SELECT date('now', 'localtime', '-1 day')")
            target_date = cursor.fetchone()[0]
            start_date = target_date
            end_date = target_date
            is_multi_day = False
        elif target_date == 'this_week':
            cursor.execute("SELECT date('now', 'localtime', 'weekday 0', '-6 days'), date('now', 'localtime')")
            start_date, end_date = cursor.fetchone()
            is_multi_day = (start_date != end_date)
        elif target_date == 'this_month':
            cursor.execute("SELECT date('now', 'localtime', 'start of month'), date('now', 'localtime')")
            start_date, end_date = cursor.fetchone()
            is_multi_day = (start_date != end_date)
        elif target_date == 'last7':
            cursor.execute("SELECT date('now', 'localtime', '-6 days'), date('now', 'localtime')")
            start_date, end_date = cursor.fetchone()
            is_multi_day = True
        elif target_date == 'last30':
            cursor.execute("SELECT date('now', 'localtime', '-29 days'), date('now', 'localtime')")
            start_date, end_date = cursor.fetchone()
            is_multi_day = True
        elif target_date and not start_date:
            start_date = target_date
            end_date = target_date
            is_multi_day = False
        else:
            is_multi_day = (start_date != end_date)

        # Generate list of dates in the range
        dt_start = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(end_date, "%Y-%m-%d")
        total_days = (dt_end - dt_start).days + 1
        date_list = [(dt_start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(total_days)]

        # Fetch active users matching department and shift filters
        user_query = '''
            SELECT u.id, u.name, u.email, u.phone, u.department, u.photo_path, u.cnic, u.position, u.salary, u.join_date,
                   COALESCE(u.shift_id, 1) as shift_id,
                   COALESCE(s.name, 'General Morning Shift') as shift_name,
                   COALESCE(s.start_time, '08:00') as start_time,
                   COALESCE(s.end_time, '20:00') as end_time,
                   COALESCE(s.grace_period_minutes, 15) as grace_period_minutes
            FROM users u
            LEFT JOIN shifts s ON COALESCE(u.shift_id, 1) = s.id
            WHERE u.active = 1
        '''
        user_params = []
        if department and department.strip() and department.lower() != 'all':
            user_query += " AND LOWER(TRIM(u.department)) = LOWER(TRIM(?))"
            user_params.append(department.strip())
        if shift_id and str(shift_id).strip() and str(shift_id).lower() != 'all':
            user_query += " AND (u.shift_id = ? OR LOWER(TRIM(s.name)) = LOWER(TRIM(?)))"
            user_params.extend([str(shift_id).strip(), str(shift_id).strip()])

        user_query += " ORDER BY u.department ASC, u.name ASC"
        cursor.execute(user_query, user_params)
        users = [dict(r) for r in cursor.fetchall()]

        if not users:
            return {
                'is_multi_day': is_multi_day,
                'date_label': start_date if not is_multi_day else f"{start_date} to {end_date}",
                'start_date': start_date,
                'end_date': end_date,
                'total_days': total_days,
                'summary': {
                    'total_enrolled': 0,
                    'attended_count': 0,
                    'zero_attendance_count': 0,
                    'total_present_days': 0,
                    'total_late_days': 0,
                    'total_absent_days': 0,
                    'attendance_rate': 0.0
                },
                'records': [],
                'departments': []
            }

        user_ids = [u['id'] for u in users]
        placeholders = ','.join('?' for _ in user_ids)

        # Retrieve distinct attendance logs grouped by user_id and log_date
        att_query = f'''
            SELECT user_id, 
                   date(timestamp) as log_date,
                   MIN(timestamp) as first_seen,
                   MAX(timestamp) as last_seen,
                   COUNT(*) as log_count,
                   location,
                   device_id,
                   source
            FROM attendance
            WHERE user_id IN ({placeholders})
              AND date(timestamp) >= ?
              AND date(timestamp) <= ?
            GROUP BY user_id, log_date
        '''
        cursor.execute(att_query, (*user_ids, start_date, end_date))
        att_map = {(r['user_id'], r['log_date']): dict(r) for r in cursor.fetchall()}

        # Retrieve manual absences
        cursor.execute(
            f"SELECT user_id, date FROM manual_absent WHERE user_id IN ({placeholders}) AND date >= ? AND date <= ?",
            (*user_ids, start_date, end_date)
        )
        absent_set = set((r[0], r[1]) for r in cursor.fetchall())

        # Retrieve approved leaves
        cursor.execute(
            f"SELECT user_id, start_date, end_date FROM leave_requests WHERE user_id IN ({placeholders}) AND status = 'approved' AND end_date >= ? AND start_date <= ?",
            (*user_ids, start_date, end_date)
        )
        leave_rows = cursor.fetchall()
        leave_set = set()
        for lr in leave_rows:
            l_uid, l_start, l_end = lr[0], lr[1], lr[2]
            try:
                cur_l = datetime.strptime(l_start, "%Y-%m-%d")
                end_l = datetime.strptime(l_end, "%Y-%m-%d")
                while cur_l <= end_l:
                    leave_set.add((l_uid, cur_l.strftime("%Y-%m-%d")))
                    cur_l += timedelta(days=1)
            except Exception:
                pass

        dept_stats = {}
        for u in users:
            d = u['department'] or 'General / Unassigned'
            if d not in dept_stats:
                dept_stats[d] = {'total_staff': 0, 'attended_staff': 0, 'present_days': 0, 'absent_days': 0, 'late_days': 0}
            dept_stats[d]['total_staff'] += 1

        records = []
        total_present_days_all = 0
        total_late_days_all = 0
        total_absent_days_all = 0
        attended_users_count = 0

        for u in users:
            uid = u['id']
            dept = u['department'] or 'General / Unassigned'
            shift_start = u.get('start_time') or '08:00'
            grace_mins = int(u.get('grace_period_minutes') or 15)
            start_mins = parse_time_to_minutes(shift_start)
            grace_deadline_mins = start_mins + grace_mins

            emp_daily_records = []
            emp_present_days = 0
            emp_late_days = 0
            emp_absent_days = 0
            emp_working_days = 0
            emp_leave_days = 0

            for cur_date in date_list:
                dt_obj = datetime.strptime(cur_date, "%Y-%m-%d")
                day_name = dt_obj.strftime("%a")
                is_sunday = (dt_obj.weekday() == 6)

                att = att_map.get((uid, cur_date))
                is_manual_absent = (uid, cur_date) in absent_set
                is_leave = (uid, cur_date) in leave_set

                if is_leave:
                    status = 'on_leave'
                    first_seen = None
                    last_seen = None
                    loc = '-'
                    dev = '-'
                    emp_leave_days += 1
                    emp_working_days += 1
                elif att and not is_manual_absent:
                    first_seen = att['first_seen']
                    raw_last_seen = att['last_seen']
                    last_seen = None
                    if first_seen and raw_last_seen and str(first_seen) != str(raw_last_seen):
                        try:
                            fmt = "%Y-%m-%d %H:%M:%S"
                            t1 = datetime.strptime(str(first_seen).split('.')[0], fmt)
                            t2 = datetime.strptime(str(raw_last_seen).split('.')[0], fmt)
                            if (t2 - t1).total_seconds() >= 60:
                                last_seen = raw_last_seen
                        except Exception:
                            if str(first_seen) != str(raw_last_seen):
                                last_seen = raw_last_seen

                    loc = att['location'] or 'Main Gate / Entrance'
                    dev = att['device_id'] or 'Camera #1'

                    # Determine late vs present vs checked_out
                    try:
                        time_part = str(first_seen).split(' ')[-1] if ' ' in str(first_seen) else str(first_seen).split('T')[-1]
                        checkin_mins = parse_time_to_minutes(time_part)
                        if checkin_mins > grace_deadline_mins:
                            status = 'late'
                            emp_late_days += 1
                        elif last_seen:
                            status = 'checked_out'
                        else:
                            status = 'present'
                    except Exception:
                        status = 'present'

                    emp_present_days += 1
                    emp_working_days += 1
                else:
                    # No attendance record
                    if is_sunday:
                        status = 'weekend'
                        first_seen = None
                        last_seen = None
                        loc = '-'
                        dev = '-'
                    else:
                        status = 'absent'
                        first_seen = None
                        last_seen = None
                        loc = '-'
                        dev = '-'
                        emp_absent_days += 1
                        emp_working_days += 1

                emp_daily_records.append({
                    'date': cur_date,
                    'date_formatted': dt_obj.strftime("%d %b %Y"),
                    'day': day_name,
                    'status': status,
                    'status_display': status.upper().replace('_', ' '),
                    'first_seen': first_seen,
                    'last_seen': last_seen,
                    'location': loc,
                    'device_id': dev,
                    'shift_name': u['shift_name']
                })

            if emp_present_days > 0:
                attended_users_count += 1
                dept_stats[dept]['attended_staff'] += 1

            dept_stats[dept]['present_days'] += emp_present_days
            dept_stats[dept]['absent_days'] += emp_absent_days
            dept_stats[dept]['late_days'] += emp_late_days

            total_present_days_all += emp_present_days
            total_late_days_all += emp_late_days
            total_absent_days_all += emp_absent_days

            effective_working_days = max(emp_working_days, 1) if emp_working_days > 0 else total_days
            emp_rate = round((emp_present_days / effective_working_days * 100), 1) if effective_working_days > 0 else 0.0

            # Filter matching logic
            if search_query and search_query.strip():
                sq = search_query.strip().lower()
                if not (sq in u['name'].lower() or sq in dept.lower() or sq in (u['position'] or '').lower() or sq in str(uid)):
                    continue

            if status_filter and status_filter.lower() != 'all':
                sf = status_filter.lower()
                if sf == 'present' and emp_present_days == 0:
                    continue
                elif sf == 'absent' and emp_present_days > 0:
                    continue
                elif sf == 'late' and emp_late_days == 0:
                    continue

            if is_multi_day:
                # ONE ROW PER EMPLOYEE
                records.append({
                    'user_id': uid,
                    'name': u['name'],
                    'email': u['email'] or '',
                    'phone': u['phone'] or '',
                    'department': dept,
                    'position': u['position'] or 'Staff Member',
                    'cnic': u['cnic'] or '',
                    'salary': float(u['salary'] or 0),
                    'join_date': u['join_date'] or '',
                    'shift_name': u['shift_name'],
                    'shift_start': u['start_time'],
                    'shift_end': u['end_time'],
                    'photo_path': u['photo_path'],
                    'total_days': total_days,
                    'working_days': emp_working_days,
                    'present_days': emp_present_days,
                    'absent_days': emp_absent_days,
                    'late_days': emp_late_days,
                    'leave_days': emp_leave_days,
                    'attendance_rate': emp_rate,
                    'present_display': f"{emp_present_days} / {emp_working_days}",
                    'absent_display': f"{emp_absent_days} / {emp_working_days}",
                    'daily_records': emp_daily_records
                })
            else:
                # Single day view: 1 row for that day
                day_entry = emp_daily_records[0] if emp_daily_records else {}
                records.append({
                    'user_id': uid,
                    'name': u['name'],
                    'email': u['email'] or '',
                    'phone': u['phone'] or '',
                    'department': dept,
                    'position': u['position'] or 'Staff Member',
                    'cnic': u['cnic'] or '',
                    'salary': float(u['salary'] or 0),
                    'join_date': u['join_date'] or '',
                    'shift_name': u['shift_name'],
                    'shift_start': u['start_time'],
                    'shift_end': u['end_time'],
                    'photo_path': u['photo_path'],
                    'status': day_entry.get('status', 'absent'),
                    'first_seen': day_entry.get('first_seen'),
                    'last_seen': day_entry.get('last_seen'),
                    'location': day_entry.get('location', 'Main Gate / Entrance'),
                    'device_id': day_entry.get('device_id', 'Camera #1'),
                    'date': start_date,
                    'daily_records': emp_daily_records
                })

        # Calculate overall attendance percentage
        total_possible_workdays = len(users) * total_days
        overall_rate = round((total_present_days_all / total_possible_workdays * 100), 1) if total_possible_workdays > 0 else 0.0

        dept_summary = []
        for dname, ddata in dept_stats.items():
            tot_st = ddata['total_staff']
            pres_d = ddata['present_days']
            max_d = tot_st * total_days
            d_rate = round((pres_d / max_d * 100), 1) if max_d > 0 else 0.0
            dept_summary.append({
                'department': dname,
                'total_staff': tot_st,
                'attended_staff': ddata['attended_staff'],
                'present_days': pres_d,
                'absent_days': ddata['absent_days'],
                'late_days': ddata['late_days'],
                'attendance_rate': d_rate
            })

        date_label = start_date if not is_multi_day else f"{start_date} to {end_date}"

        return {
            'is_multi_day': is_multi_day,
            'date_label': date_label,
            'start_date': start_date,
            'end_date': end_date,
            'total_days': total_days,
            'summary': {
                'total_enrolled': len(users),
                'total_matching': len(records),
                'attended_count': attended_users_count,
                'zero_attendance_count': len(users) - attended_users_count,
                'total_present_days': total_present_days_all,
                'total_late_days': total_late_days_all,
                'total_absent_days': total_absent_days_all,
                'attendance_rate': overall_rate
            },
            'records': records,
            'departments': dept_summary
        }

if __name__ == '__main__':
    # Test multi-day (2026-10-01 to 2026-10-07)
    res_multi = test_get_detailed_attendance_report(start_date='2026-10-01', end_date='2026-10-07')
    print('=== MULTI-DAY TEST ===')
    print('is_multi_day:', res_multi['is_multi_day'])
    print('total_days:', res_multi['total_days'])
    print('summary:', res_multi['summary'])
    print('Total summarized employee rows:', len(res_multi['records']))
    for r in res_multi['records'][:4]:
        print(f"EMP #{r['user_id']} {r['name']} | Dept: {r['department']} | Present: {r['present_display']} | Absent: {r['absent_display']} | Late: {r['late_days']} | Rate: {r['attendance_rate']}% | Days recorded: {len(r['daily_records'])}")
    
    # Test single-day (today)
    res_single = test_get_detailed_attendance_report(target_date='today')
    print('\n=== SINGLE-DAY TEST ===')
    print('is_multi_day:', res_single['is_multi_day'])
    print('records count:', len(res_single['records']))
    print('Sample single rec:', res_single['records'][0]['name'], res_single['records'][0]['status'])
