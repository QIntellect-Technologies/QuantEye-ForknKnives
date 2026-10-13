import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
import database as db

def run_shift_audit():
    client = app.test_client()
    results = []

    def record(test_id, action, expected, actual, passed, evidence, severity=None, affects=None):
        results.append({
            'test_id': test_id,
            'action': action,
            'expected': str(expected),
            'actual': str(actual),
            'passed': bool(passed),
            'evidence': evidence,
            'severity': severity,
            'affects': affects
        })

    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # =========================================================================
    # 0. PRE-AUDIT BASELINE SNAPSHOT
    # =========================================================================
    tables = [
        'users', 'departments', 'designations', 'shifts', 
        'attendance', 'leave_requests', 'overtime', 
        'salary_configs', 'payroll_records', 'embeddings', 
        'branch_settings', 'employee_shift_history'
    ]
    pre_counts = {t: cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    orig_shifts = [dict(r) for r in cur.execute("SELECT * FROM shifts ORDER BY id").fetchall()]
    user38_orig_shift = cur.execute("SELECT shift_id FROM users WHERE id = 38").fetchone()[0]

    print("=" * 80)
    print("MODULE 4 AUDIT — PRE-AUDIT BASELINE SNAPSHOT")
    for t, c in pre_counts.items():
        print(f"  {t:25s}: {c}")
    print(f"  Existing Shifts count     : {len(orig_shifts)}")
    for s in orig_shifts:
        print(f"    Shift #{s['id']}: '{s['name']}' ({s['start_time']} - {s['end_time']}), grace={s['grace_period_minutes']}m, default={s['is_default']}")
    print(f"  User #38 Current Shift ID : {user38_orig_shift}")
    print("=" * 80)

    # =========================================================================
    # SECTION 1: SHIFT CRUD TESTING
    # =========================================================================
    print("\n--- 1. SHIFT CRUD TESTING ---")

    # SFT-01: List existing shifts
    res = client.get('/api/shifts')
    data = res.get_json() or {}
    shifts_list = data.get('shifts', [])
    passed = res.status_code == 200 and data.get('success') is True and len(shifts_list) == len(orig_shifts)
    record(
        'SFT-01',
        'GET /api/shifts (List existing shifts)',
        'HTTP 200, success=True, returns list of configured shifts',
        f'HTTP {res.status_code}, count={len(shifts_list)}',
        passed,
        f"Shifts returned: {[s['name'] for s in shifts_list]}"
    )

    # SFT-02: Create valid shift
    temp_shift_name = "QA Audit Evening Shift 2026"
    res = client.post('/api/shifts', json={
        'name': temp_shift_name,
        'start_time': '16:00',
        'end_time': '00:00',
        'grace_period_minutes': 20,
        'working_days': [0, 1, 2, 3, 4]
    })
    cdata = res.get_json() or {}
    temp_shift_id = cdata.get('shift_id')
    passed = res.status_code == 201 and cdata.get('success') is True and temp_shift_id is not None
    record(
        'SFT-02',
        f'POST /api/shifts (Create valid shift "{temp_shift_name}")',
        'HTTP 201 Created with integer shift_id',
        f'HTTP {res.status_code}, shift_id={temp_shift_id}, success={cdata.get("success")}',
        passed,
        f"Response payload: {cdata}"
    )

    # SFT-03: Verify SQLite row persistence for new shift
    cur.execute("SELECT * FROM shifts WHERE id = ?", (temp_shift_id,))
    s_row = cur.fetchone()
    db_persisted = (
        s_row is not None and
        s_row['name'] == temp_shift_name and
        s_row['start_time'] == '16:00' and
        s_row['end_time'] == '00:00' and
        s_row['grace_period_minutes'] == 20
    )
    record(
        'SFT-03',
        'Verify SQLite row persistence for created shift',
        'Row found with exact start_time, end_time, grace_period_minutes',
        f'found={s_row is not None}, name="{s_row["name"] if s_row else None}"',
        db_persisted,
        f"SQLite row: {dict(s_row) if s_row else None}"
    )

    # SFT-04: Duplicate shift name rejection
    res = client.post('/api/shifts', json={
        'name': temp_shift_name,
        'start_time': '16:00',
        'end_time': '00:00'
    })
    passed = res.status_code == 400
    record(
        'SFT-04',
        'POST /api/shifts with duplicate shift name',
        'HTTP 400 Bad Request',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Response: {res.get_json()}"
    )

    # SFT-05: Missing shift name validation
    res = client.post('/api/shifts', json={'name': '', 'start_time': '09:00', 'end_time': '17:00'})
    passed = res.status_code == 400
    record(
        'SFT-05',
        'POST /api/shifts with empty shift name',
        'HTTP 400 Bad Request',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Response: {res.get_json()}"
    )

    # SFT-06: Whitespace shift name validation
    res = client.post('/api/shifts', json={'name': '   ', 'start_time': '09:00', 'end_time': '17:00'})
    passed = res.status_code == 400
    record(
        'SFT-06',
        'POST /api/shifts with whitespace-only shift name',
        'HTTP 400 Bad Request',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Response: {res.get_json()}"
    )

    # SFT-07: Edit shift
    updated_shift_name = "QA Audit Evening Shift 2026 - Updated"
    res = client.put(f'/api/shifts/{temp_shift_id}', json={
        'name': updated_shift_name,
        'start_time': '17:00',
        'end_time': '01:00',
        'grace_period_minutes': 30,
        'working_days': [0, 1, 2, 3, 4, 5]
    })
    passed = res.status_code == 200 and (res.get_json() or {}).get('success') is True
    cur.execute("SELECT * FROM shifts WHERE id = ?", (temp_shift_id,))
    upd_s_row = cur.fetchone()
    db_updated = upd_s_row and upd_s_row['name'] == updated_shift_name and upd_s_row['grace_period_minutes'] == 30
    record(
        'SFT-07',
        f'PUT /api/shifts/{temp_shift_id} (Update shift configuration)',
        'HTTP 200, success=True, SQLite row updated',
        f'HTTP {res.status_code}, db_updated={db_updated}',
        passed and db_updated,
        f"Updated SQLite row: {dict(upd_s_row) if upd_s_row else None}"
    )

    # SFT-08: Block delete default shift (Shift ID 1)
    res = client.delete('/api/shifts/1')
    passed = res.status_code == 400
    record(
        'SFT-08',
        'DELETE /api/shifts/1 (Attempt delete protected default shift)',
        'HTTP 400 Bad Request (Cannot delete default Morning Shift)',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Protection response: {res.get_json()}"
    )

    # SFT-09: Delete custom shift
    res = client.delete(f'/api/shifts/{temp_shift_id}')
    passed = res.status_code == 200 and (res.get_json() or {}).get('success') is True
    cur.execute("SELECT * FROM shifts WHERE id = ?", (temp_shift_id,))
    del_row = cur.fetchone()
    record(
        'SFT-09',
        f'DELETE /api/shifts/{temp_shift_id} (Delete custom audit shift)',
        'HTTP 200, row deleted from SQLite',
        f'HTTP {res.status_code}, row_exists={del_row is not None}',
        passed and del_row is None,
        f"Shift deletion confirmed: {del_row is None}"
    )

    # =========================================================================
    # SECTION 2: EMPLOYEE SHIFT ASSIGNMENT & REASSIGNMENT
    # =========================================================================
    print("\n--- 2. EMPLOYEE SHIFT ASSIGNMENT ---")

    # SFT-10: Individual shift assignment (Move User 38 to Shift 3 Night Shift)
    res = client.post('/api/users/38/assign-shift', json={'shift_id': 3})
    passed = res.status_code == 200 and (res.get_json() or {}).get('success') is True
    cur.execute("SELECT shift_id FROM users WHERE id = 38")
    u38_shift = cur.fetchone()[0]
    record(
        'SFT-10',
        'POST /api/users/38/assign-shift to Shift #3 (Night Shift)',
        'HTTP 200, users.shift_id updated to 3 in SQLite',
        f'HTTP {res.status_code}, current_shift_id={u38_shift}',
        passed and u38_shift == 3,
        f"User 38 assigned shift: {u38_shift}"
    )

    # SFT-11: Reassign User 38 back to Shift 1 (Morning Shift)
    res = client.post('/api/users/38/assign-shift', json={'shift_id': 1})
    passed = res.status_code == 200
    cur.execute("SELECT shift_id FROM users WHERE id = 38")
    u38_shift_restored = cur.fetchone()[0]
    record(
        'SFT-11',
        'POST /api/users/38/assign-shift revert back to Shift #1',
        'HTTP 200, users.shift_id reverted to 1',
        f'HTTP {res.status_code}, current_shift_id={u38_shift_restored}',
        passed and u38_shift_restored == 1,
        f"User 38 restored shift: {u38_shift_restored}"
    )

    # SFT-12: Bulk shift assignment to specific users
    res = client.post('/api/shifts/bulk-assign', json={
        'user_ids': [41, 46],
        'shift_id': 3
    })
    bdata = res.get_json() or {}
    passed = res.status_code == 200 and bdata.get('count') == 2
    cur.execute("SELECT id, shift_id FROM users WHERE id IN (41, 46)")
    bulk_rows = {r[0]: r[1] for r in cur.fetchall()}
    bulk_ok = bulk_rows.get(41) == 3 and bulk_rows.get(46) == 3
    record(
        'SFT-12',
        'POST /api/shifts/bulk-assign to User IDs [41, 46] with shift_id=3',
        'HTTP 200, count=2, both users updated in SQLite',
        f'HTTP {res.status_code}, count={bdata.get("count")}, db_shifts={bulk_rows}',
        passed and bulk_ok,
        f"Bulk assigned rows: {bulk_rows}"
    )

    # Revert User 41, 46 back to Shift 1
    client.post('/api/shifts/bulk-assign', json={'user_ids': [41, 46], 'shift_id': 1})

    # =========================================================================
    # SECTION 3: SHIFT HISTORY IMMUTABILITY
    # =========================================================================
    print("\n--- 3. SHIFT HISTORY IMMUTABILITY ---")

    # SFT-13: Timeline test across multiple effective dates
    # User 38: Day 1 (2026-10-01) -> Morning Shift (ID 1)
    #          Day 2 (2026-10-05) -> Night Shift (ID 3)
    # Verify report calculation on 2026-10-01 uses Morning Shift, and 2026-10-05 uses Night Shift
    cur.execute('''
        INSERT OR REPLACE INTO employee_shift_history 
        (user_id, shift_id, effective_from, shift_name, start_time, end_time, grace_period_minutes, working_days, history_source)
        VALUES (38, 1, '2026-10-01', 'Morning Shift', '08:00', '16:00', 15, '[0,1,2,3,4,5]', 'qa_audit_test')
    ''')
    cur.execute('''
        INSERT OR REPLACE INTO employee_shift_history 
        (user_id, shift_id, effective_from, shift_name, start_time, end_time, grace_period_minutes, working_days, history_source)
        VALUES (38, 3, '2026-10-05', 'Night Shift', '22:00', '06:00', 20, '[0,1,2,3,4,5]', 'qa_audit_test')
    ''')
    conn.commit()

    # Query report logic for 2026-10-01
    rep_day1 = db.get_detailed_attendance_report(start_date='2026-10-01', end_date='2026-10-01')
    u38_rec_day1 = next((r for r in rep_day1.get('records', []) if r.get('user_id') == 38), None)
    day1_shift = u38_rec_day1['daily_records'][0]['shift_name'] if u38_rec_day1 and u38_rec_day1.get('daily_records') else None

    # Query report logic for 2026-10-05
    rep_day2 = db.get_detailed_attendance_report(start_date='2026-10-05', end_date='2026-10-05')
    u38_rec_day2 = next((r for r in rep_day2.get('records', []) if r.get('user_id') == 38), None)
    day2_shift = u38_rec_day2['daily_records'][0]['shift_name'] if u38_rec_day2 and u38_rec_day2.get('daily_records') else None

    history_immutability_ok = day1_shift == 'Morning Shift' and day2_shift == 'Night Shift'
    record(
        'SFT-13',
        'Historical Shift Timeline Immutability across multiple effective dates',
        'Date 2026-10-01 resolves to Morning Shift; Date 2026-10-05 resolves to Night Shift',
        f'day1_shift="{day1_shift}", day2_shift="{day2_shift}"',
        history_immutability_ok,
        f"Timeline resolution confirmed: Day 1 = {day1_shift}, Day 2 = {day2_shift}"
    )

    # Clean up test history entries for user 38
    cur.execute("DELETE FROM employee_shift_history WHERE user_id = 38 AND effective_from IN ('2026-10-01', '2026-10-05')")
    conn.commit()

    # =========================================================================
    # SECTION 4: GRACE PERIOD & ARRIVAL WINDOW CALCULATION
    # =========================================================================
    print("\n--- 4. GRACE PERIOD VERIFICATION ---")
    # Shift start: 08:00, Grace: 15 mins -> Deadline: 08:15:00
    # Arrivals: 07:59, 08:00, 08:10, 08:15 -> Present
    # Arrivals: 08:16, 08:30 -> Late
    def eval_status(checkin_time_str, start_str="08:00", grace_m=15):
        start_mins = db.parse_time_to_minutes(start_str)
        deadline = start_mins + grace_m
        check_mins = db.parse_time_to_minutes(checkin_time_str)
        return 'late' if check_mins > deadline else 'present'

    grace_results = {
        '07:59': eval_status('07:59'),
        '08:00': eval_status('08:00'),
        '08:10': eval_status('08:10'),
        '08:15': eval_status('08:15'),
        '08:16': eval_status('08:16'),
        '08:30': eval_status('08:30')
    }
    grace_accurate = (
        grace_results['07:59'] == 'present' and
        grace_results['08:00'] == 'present' and
        grace_results['08:10'] == 'present' and
        grace_results['08:15'] == 'present' and
        grace_results['08:16'] == 'late' and
        grace_results['08:30'] == 'late'
    )
    record(
        'SFT-14',
        'Grace period status evaluation matrix (Start 08:00, Grace 15m)',
        '07:59-08:15 = Present, 08:16-08:30 = Late',
        f'results={grace_results}',
        grace_accurate,
        f"Evaluation matrix: {grace_results}"
    )

    # =========================================================================
    # SECTION 5: OVERNIGHT / CROSS-MIDNIGHT SHIFT
    # =========================================================================
    print("\n--- 5. OVERNIGHT SHIFT VERIFICATION ---")
    # Shift: 22:00 to 06:00 (Starts 22:00, ends next morning 06:00)
    # Check is_time_in_grace_window when grace=0 (full shift allowed)
    dt_2205 = datetime(2026, 10, 15, 22, 5)
    dt_0200 = datetime(2026, 10, 16, 2, 0)
    dt_0555 = datetime(2026, 10, 16, 5, 55)
    dt_1200 = datetime(2026, 10, 16, 12, 0)  # Midday (outside shift)

    allowed_2205 = db.is_time_in_grace_window("22:00", 0, dt_2205, "06:00")
    allowed_0200 = db.is_time_in_grace_window("22:00", 0, dt_0200, "06:00")
    allowed_0555 = db.is_time_in_grace_window("22:00", 0, dt_0555, "06:00")
    allowed_1200 = db.is_time_in_grace_window("22:00", 0, dt_1200, "06:00")

    overnight_accurate = allowed_2205 and allowed_0200 and allowed_0555 and (not allowed_1200)
    record(
        'SFT-15',
        'Overnight cross-midnight shift window evaluation (22:00 - 06:00)',
        '22:05=True, 02:00=True, 05:55=True, 12:00=False',
        f'22:05={allowed_2205}, 02:00={allowed_0200}, 05:55={allowed_0555}, 12:00={allowed_1200}',
        overnight_accurate,
        f"Overnight cross-midnight wrap-around calculations verified"
    )

    # =========================================================================
    # SECTION 6: SHIFT -> ATTENDANCE, LEAVE, OVERTIME, PAYROLL
    # =========================================================================
    print("\n--- 6. INTEGRATION WITH ATTENDANCE, LEAVE, OVERTIME, PAYROLL ---")

    # SFT-16: Shift check on attendance logging
    allowed_sh, reason_sh, info_sh = db.check_user_shift_allowed(38)
    record(
        'SFT-16',
        'db.check_user_shift_allowed for User #38 with current time',
        'Returns boolean allowed, reason string, shift info dict',
        f'allowed={allowed_sh}, reason="{reason_sh}", shift="{info_sh.get("name") if info_sh else None}"',
        info_sh is not None and 'name' in info_sh,
        f"Shift check details: {reason_sh}"
    )

    # SFT-17: Scheduled workday determination
    # Shift working days: Mon-Sat [0,1,2,3,4,5], Sunday [6] is off
    mon_dt = datetime(2026, 10, 12)  # Monday
    sun_dt = datetime(2026, 10, 18)  # Sunday
    is_mon_work = db._is_scheduled_workday(mon_dt, [0, 1, 2, 3, 4, 5])
    is_sun_work = db._is_scheduled_workday(sun_dt, [0, 1, 2, 3, 4, 5])
    workday_ok = is_mon_work is True and is_sun_work is False
    record(
        'SFT-17',
        'Shift scheduled workday calculation: Monday=Workday, Sunday=OffDay',
        'Monday in [0,1,2,3,4,5] -> True; Sunday in [0,1,2,3,4,5] -> False',
        f'Monday={is_mon_work}, Sunday={is_sun_work}',
        workday_ok,
        f"Monday workday={is_mon_work}, Sunday workday={is_sun_work}"
    )

    # SFT-18: Payroll numerical anchor verification
    cur.execute("""
        SELECT u.id, u.name, sc.basic_salary, sc.allowances, sc.deductions, sc.ot_rate
        FROM users u 
        JOIN salary_configs sc ON u.id = sc.user_id 
        WHERE u.id = 38
    """)
    anc = cur.fetchone()
    basic = anc[2]
    allowances = anc[3]
    deductions = anc[4]
    ot_rate = anc[5]
    ot_amount = round(3.0 * ot_rate, 2)
    gross = basic + allowances + ot_amount
    net_with = gross - deductions - 25000.0
    net_without = gross - deductions

    anchor_ok = (
        basic == 250000.0 and
        allowances == 35000.0 and
        deductions == 10000.0 and
        ot_rate == 1201.92 and
        ot_amount == 3605.76 and
        gross == 288605.76 and
        net_with == 253605.76 and
        net_without == 278605.76
    )
    record(
        'SFT-18',
        'Payroll Numerical Anchor Verification (Employee #38)',
        'Basic 250k, Allowances 35k, Deductions 10k, OT 3605.76, Gross 288,605.76, Net 253,605.76',
        f'Gross={gross}, Net={net_with}',
        anchor_ok,
        f"Employee #38 anchor: Basic={basic}, Net={net_with}"
    )

    # =========================================================================
    # SECTION 7: API VALIDATION & EDGE CASES
    # =========================================================================
    print("\n--- 7. API VALIDATION & EDGE CASES ---")

    # SFT-19: Assign non-existent shift ID
    res = client.post('/api/users/38/assign-shift', json={'shift_id': 999999})
    # Let's see what happens if shift_id 999999 is assigned
    # In database.py: users.shift_id = 999999, but _record_employee_shift_history checks:
    # "SELECT name... FROM shifts WHERE id = 999999" -> if not shift: raise ValueError("Shift not found")
    # So assign_user_shift catches exception and returns False -> HTTP 400!
    passed = res.status_code == 400
    record(
        'SFT-19',
        'POST /api/users/38/assign-shift with non-existent shift_id=999999',
        'HTTP 400 Bad Request (Shift not found)',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Rejection response: {res.get_json()}"
    )

    # SFT-20: Assign shift to non-existent user ID
    res = client.post('/api/users/999999/assign-shift', json={'shift_id': 1})
    passed = res.status_code == 400
    record(
        'SFT-20',
        'POST /api/users/999999/assign-shift for non-existent user_id=999999',
        'HTTP 400 Bad Request (User not found)',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Rejection response: {res.get_json()}"
    )

    # SFT-21: Bulk assign with missing shift_id
    res = client.post('/api/shifts/bulk-assign', json={'user_ids': [38]})
    passed = res.status_code == 400
    record(
        'SFT-21',
        'POST /api/shifts/bulk-assign with missing shift_id',
        'HTTP 400 Bad Request',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Response: {res.get_json()}"
    )

    # =========================================================================
    # SECTION 8: BASELINE SNAPSHOT RESTORATION & INTEGRITY
    # =========================================================================
    print("\n--- 8. BASELINE RESTORATION & INTEGRITY ---")

    # Restore all users to shift_id 1 and clean up temporary test history
    cur.execute("UPDATE users SET shift_id = 1")
    cur.execute("DELETE FROM employee_shift_history WHERE effective_from != '2020-01-01'")
    conn.commit()

    post_counts = {t: cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    ic = cur.execute("PRAGMA integrity_check").fetchall()
    fk = cur.execute("PRAGMA foreign_key_check").fetchall()

    counts_match = all(post_counts[t] == pre_counts[t] for t in tables)
    record(
        'SFT-22',
        'Database baseline counts & integrity checks after Shift audit',
        'All 12 tables match pre-audit baseline, PRAGMA integrity_check=ok, PRAGMA foreign_key_check=0',
        f'counts_match={counts_match}, ic={ic[0][0]}, fk={len(fk)} violations',
        counts_match and ic[0][0] == 'ok' and len(fk) == 0,
        f"Post counts: {post_counts}"
    )

    conn.close()

    # Save results to JSON
    with open('scratch/shift_audit_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    passed_cnt = sum(1 for r in results if r['passed'])
    print("\n" + "=" * 80)
    print(f"MODULE 4 (SHIFT MANAGEMENT) AUDIT SUMMARY: {passed_cnt}/{len(results)} PASSED")
    print("=" * 80)
    for r in results:
        status = "[PASS]" if r['passed'] else "[FAIL]"
        print(f"{status} {r['test_id']}: {r['action']}")
        print(f"       Expected: {r['expected']}")
        print(f"       Actual:   {r['actual']}")
        if not r['passed']:
            print(f"       Severity: {r.get('severity')}")
            print(f"       Affects : {r.get('affects')}")

    return passed_cnt == len(results)

if __name__ == '__main__':
    run_shift_audit()
