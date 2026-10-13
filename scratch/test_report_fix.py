import sqlite3
import datetime
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db
from config import DB_PATH

def test_new_report(
    target_date=None,
    start_date=None,
    end_date=None,
    department=None,
    shift_id=None,
    status_filter=None,
    search_query=None
):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Resolve date filter
        if target_date == 'today' or (not target_date and not start_date):
            cursor.execute("SELECT date('now', 'localtime')")
            target_date = cursor.fetchone()[0]
        elif target_date == 'yesterday':
            cursor.execute("SELECT date('now', 'localtime', '-1 day')")
            target_date = cursor.fetchone()[0]
        elif target_date == 'this_week':
            # Monday to Today
            cursor.execute("SELECT date('now', 'localtime', 'weekday 0', '-6 days'), date('now', 'localtime')")
            start_date, end_date = cursor.fetchone()
            target_date = None
        elif target_date == 'this_month':
            # 1st of month to Today
            cursor.execute("SELECT date('now', 'localtime', 'start of month'), date('now', 'localtime')")
            start_date, end_date = cursor.fetchone()
            target_date = None

        is_range = bool(start_date and end_date)

        # Base user query
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
        if shift_id and str(shift_id).lower() != 'all':
            user_query += " AND u.shift_id = ?"
            user_params.append(int(shift_id))

        user_query += " ORDER BY u.department ASC, u.name ASC"
        cursor.execute(user_query, user_params)
        users = [dict(r) for r in cursor.fetchall()]

        if not users:
            return {
                'summary': {'total_registered': 0, 'present': 0, 'absent': 0, 'late': 0, 'attendance_rate': 0.0},
                'departments': [],
                'shifts': [],
                'records': [],
                'date_label': target_date if not is_range else f"{start_date} to {end_date}"
            }

        user_ids = [u['id'] for u in users]
        placeholders = ','.join('?' for _ in user_ids)
        users_by_id = {u['id']: u for u in users}

        records = []
        dept_stats = {}
        for u in users:
            d = u['department'] or 'General'
            if d not in dept_stats:
                dept_stats[d] = {'total': 0, 'present': 0, 'absent': 0, 'late': 0}
            dept_stats[d]['total'] += 1

        if not is_range:
            # Single date logic
            att_query = f'''
                SELECT user_id,
                       date(timestamp) as log_date,
                       MIN(timestamp) as first_seen,
                       MAX(timestamp) as last_seen,
                       AVG(confidence) as avg_confidence,
                       COUNT(*) as log_count,
                       location,
                       device_id,
                       source
                FROM attendance
                WHERE user_id IN ({placeholders})
                  AND date(timestamp) = ?
                GROUP BY user_id
            '''
            cursor.execute(att_query, (*user_ids, target_date))
            att_map = {r['user_id']: dict(r) for r in cursor.fetchall()}

            cursor.execute(
                f"SELECT user_id FROM manual_absent WHERE user_id IN ({placeholders}) AND date = ?",
                (*user_ids, target_date)
            )
            absent_set = set(r[0] for r in cursor.fetchall())

            for u in users:
                uid = u['id']
                dept = u['department'] or 'General'
                att = att_map.get(uid)
                is_manually_absent = uid in absent_set

                if is_manually_absent or not att:
                    status = 'absent'
                    first_seen = None
                    last_seen = None
                    avg_conf = 0.0
                    log_count = 0
                    loc = 'N/A'
                    dev = 'Camera #1'
                    src = 'manual'
                else:
                    first_seen = att['first_seen']
                    raw_last_seen = att['last_seen']
                    last_seen = None
                    if first_seen and raw_last_seen and str(first_seen) != str(raw_last_seen):
                        try:
                            fmt = "%Y-%m-%d %H:%M:%S"
                            t1 = datetime.datetime.strptime(str(first_seen).split('.')[0], fmt)
                            t2 = datetime.datetime.strptime(str(raw_last_seen).split('.')[0], fmt)
                            if (t2 - t1).total_seconds() >= 60:
                                last_seen = raw_last_seen
                        except Exception:
                            if str(first_seen) != str(raw_last_seen):
                                last_seen = raw_last_seen

                    avg_conf = float(att['avg_confidence'] or 1.0)
                    log_count = att['log_count']
                    loc = att['location'] or 'Main Gate'
                    dev = att['device_id'] or 'Camera #1'
                    src = att['source'] or 'ai_camera'

                    shift_start = u.get('start_time') or '08:00'
                    grace_mins = int(u.get('grace_period_minutes') or 15)
                    try:
                        sh_parts = shift_start.split(':')
                        sh_mins = int(sh_parts[0]) * 60 + int(sh_parts[1])
                        grace_limit = sh_mins + grace_mins

                        time_str = str(first_seen).split(' ')[-1] if ' ' in str(first_seen) else str(first_seen).split('T')[-1]
                        ci_parts = time_str.split(':')
                        ci_mins = int(ci_parts[0]) * 60 + int(ci_parts[1])

                        if ci_mins > grace_limit:
                            status = 'late'
                        else:
                            status = 'present'
                    except Exception:
                        status = 'present'

                if status in ('present', 'late', 'checked_out'):
                    dept_stats[dept]['present'] += 1
                    if status == 'late':
                        dept_stats[dept]['late'] += 1
                else:
                    dept_stats[dept]['absent'] += 1

                rec = {
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
                    'status': status,
                    'first_seen': first_seen,
                    'last_seen': last_seen,
                    'confidence': round(avg_conf, 3),
                    'log_count': log_count,
                    'location': loc,
                    'device_id': dev,
                    'source': src,
                    'date': target_date
                }

                # Apply text search filter
                if search_query:
                    sq = search_query.lower()
                    if not (sq in u['name'].lower() or sq in dept.lower() or sq in (u['position'] or '').lower() or sq in str(uid)):
                        continue

                # Apply status filter
                if not status_filter or status_filter.lower() == 'all' or status.lower() == status_filter.lower():
                    records.append(rec)

        else:
            # Multi-day range query
            att_query = f'''
                SELECT user_id,
                       date(timestamp) as log_date,
                       MIN(timestamp) as first_seen,
                       MAX(timestamp) as last_seen,
                       AVG(confidence) as avg_confidence,
                       COUNT(*) as log_count,
                       location,
                       device_id,
                       source
                FROM attendance
                WHERE user_id IN ({placeholders})
                  AND date(timestamp) >= ?
                  AND date(timestamp) <= ?
                GROUP BY user_id, log_date
                ORDER BY log_date DESC, user_id ASC
            '''
            cursor.execute(att_query, (*user_ids, start_date, end_date))
            att_rows = cursor.fetchall()

            cursor.execute(
                f"SELECT user_id, date FROM manual_absent WHERE user_id IN ({placeholders}) AND date >= ? AND date <= ?",
                (*user_ids, start_date, end_date)
            )
            absent_set = set((r[0], r[1]) for r in cursor.fetchall())

            for r in att_rows:
                uid = r['user_id']
                log_date = r['log_date']
                u = users_by_id.get(uid)
                if not u:
                    continue

                dept = u['department'] or 'General'
                is_manually_absent = (uid, log_date) in absent_set
                if is_manually_absent:
                    status = 'absent'
                    first_seen = None
                    last_seen = None
                    avg_conf = 0.0
                    log_count = 0
                    loc = 'N/A'
                    dev = 'Camera #1'
                    src = 'manual'
                else:
                    first_seen = r['first_seen']
                    raw_last_seen = r['last_seen']
                    last_seen = None
                    if first_seen and raw_last_seen and str(first_seen) != str(raw_last_seen):
                        try:
                            fmt = "%Y-%m-%d %H:%M:%S"
                            t1 = datetime.datetime.strptime(str(first_seen).split('.')[0], fmt)
                            t2 = datetime.datetime.strptime(str(raw_last_seen).split('.')[0], fmt)
                            if (t2 - t1).total_seconds() >= 60:
                                last_seen = raw_last_seen
                        except Exception:
                            if str(first_seen) != str(raw_last_seen):
                                last_seen = raw_last_seen

                    avg_conf = float(r['avg_confidence'] or 1.0)
                    log_count = r['log_count']
                    loc = r['location'] or 'Main Gate'
                    dev = r['device_id'] or 'Camera #1'
                    src = r['source'] or 'ai_camera'

                    shift_start = u.get('start_time') or '08:00'
                    grace_mins = int(u.get('grace_period_minutes') or 15)
                    try:
                        sh_parts = shift_start.split(':')
                        sh_mins = int(sh_parts[0]) * 60 + int(sh_parts[1])
                        grace_limit = sh_mins + grace_mins

                        time_str = str(first_seen).split(' ')[-1] if ' ' in str(first_seen) else str(first_seen).split('T')[-1]
                        ci_parts = time_str.split(':')
                        ci_mins = int(ci_parts[0]) * 60 + int(ci_parts[1])

                        if ci_mins > grace_limit:
                            status = 'late'
                        else:
                            status = 'present'
                    except Exception:
                        status = 'present'

                if status in ('present', 'late', 'checked_out'):
                    dept_stats[dept]['present'] += 1
                    if status == 'late':
                        dept_stats[dept]['late'] += 1
                else:
                    dept_stats[dept]['absent'] += 1

                rec = {
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
                    'status': status,
                    'first_seen': first_seen,
                    'last_seen': last_seen,
                    'confidence': round(avg_conf, 3),
                    'log_count': log_count,
                    'location': loc,
                    'device_id': dev,
                    'source': src,
                    'date': log_date
                }

                if search_query:
                    sq = search_query.lower()
                    if not (sq in u['name'].lower() or sq in dept.lower() or sq in (u['position'] or '').lower() or sq in str(uid)):
                        continue

                if not status_filter or status_filter.lower() == 'all' or status.lower() == status_filter.lower():
                    records.append(rec)

        # Department breakdown summary
        dept_summary = []
        for dname, ddata in dept_stats.items():
            t = ddata['total']
            p = ddata['present']
            rate = round((p / t * 100), 1) if t > 0 else 0.0
            dept_summary.append({
                'department': dname,
                'total': t,
                'present': p,
                'absent': ddata['absent'],
                'late': ddata['late'],
                'attendance_rate': rate
            })

        # Calculate totals from filtered records
        tot_recs = len(records)
        pres_recs = sum(1 for r in records if r['status'] in ('present', 'late', 'checked_out'))
        late_recs = sum(1 for r in records if r['status'] == 'late')
        abs_recs = sum(1 for r in records if r['status'] == 'absent')
        rate = round((pres_recs / tot_recs * 100), 1) if tot_recs > 0 else 0.0

        return {
            'summary': {
                'total_registered': len(users) if not is_range else tot_recs,
                'total_matching': tot_recs,
                'present': pres_recs,
                'absent': abs_recs,
                'late': late_recs,
                'attendance_rate': rate
            },
            'departments': dept_summary,
            'records': records,
            'date_label': target_date if not is_range else f"{start_date} to {end_date}"
        }

print("Testing Today:")
res = test_new_report(target_date='today')
print("Today Summary:", res['summary'], "Count:", len(res['records']))

print("\nTesting Yesterday:")
res_yest = test_new_report(target_date='yesterday')
print("Yesterday Summary:", res_yest['summary'], "Count:", len(res_yest['records']))

print("\nTesting Date Range (2026-10-01 to 2026-10-07):")
res_rng = test_new_report(start_date='2026-10-01', end_date='2026-10-07')
print("Range Summary:", res_rng['summary'], "Count:", len(res_rng['records']))
print("Sample Range Records:", [(r['name'], r['date'], r['status'], r['first_seen']) for r in res_rng['records'][:5]])
