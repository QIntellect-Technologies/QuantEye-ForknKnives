import sys
import os
import json
import sqlite3
import datetime
import calendar

sys.path.insert(0, os.path.abspath('.'))

from app import app
import database as db

client = app.test_client()

results = []

def record_test(test_id, category, description, expected, actual, passed, details=None):
    status = "PASS" if passed else "FAIL"
    results.append({
        "test_id": test_id,
        "category": category,
        "description": description,
        "expected": expected,
        "actual": actual,
        "status": status,
        "details": details or ""
    })
    print(f"[{status}] {test_id} ({category}): {description}")
    if not passed:
        print(f"       Expected: {expected}")
        print(f"       Actual:   {actual}")
        if details:
            print(f"       Details:  {details}")

print("=" * 80)
print("COMPREHENSIVE VERIFICATION: SIX ATTENDANCE, LEAVE & OVERTIME TICKETS")
print("=" * 80)

# Establish database baseline
conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute("SELECT count(*) FROM shifts")
baseline_shifts = c.fetchone()[0]
c.execute("SELECT count(*) FROM attendance")
baseline_attendance = c.fetchone()[0]
c.execute("SELECT count(*) FROM overtime")
baseline_overtime = c.fetchone()[0]
c.execute("SELECT count(*) FROM leave_requests")
baseline_leaves = c.fetchone()[0]
c.execute("SELECT count(*) FROM manual_absent")
baseline_manual_absent = c.fetchone()[0]
c.execute("PRAGMA foreign_key_check")
baseline_fk_violations = len(c.fetchall())
conn.close()

print(f"Baseline rows: shifts={baseline_shifts}, attendance={baseline_attendance}, overtime={baseline_overtime}, leaves={baseline_leaves}, manual_absent={baseline_manual_absent}")
print(f"Baseline FK violations: {baseline_fk_violations}\n")

# Tracker for test artifacts to clean up
created_shift_ids = []
created_attendance_ids = []
created_overtime_ids = []
created_leave_ids = []
created_manual_absents = []

try:
    # -------------------------------------------------------------
    # FEATURE 1: CHECKOUT GRACE PERIOD IN SHIFT MANAGEMENT
    # -------------------------------------------------------------
    print("--- 1. SHIFT MANAGEMENT: CHECKOUT GRACE PERIOD VALIDATION ---")
    
    # Negative test: -1
    res = client.post('/api/shifts', json={
        'name': 'Test Neg Grace', 'start_time': '09:00', 'end_time': '17:00',
        'checkout_grace_period_minutes': -1
    })
    record_test("S1.1", "Shift Grace", "Reject negative checkout grace period (-1)",
                400, res.status_code, res.status_code == 400)

    # Decimal test: 1.5
    res = client.post('/api/shifts', json={
        'name': 'Test Decimal Grace', 'start_time': '09:00', 'end_time': '17:00',
        'checkout_grace_period_minutes': 1.5
    })
    record_test("S1.2", "Shift Grace", "Reject decimal checkout grace period (1.5)",
                400, res.status_code, res.status_code == 400)

    # Exceeding test: 121
    res = client.post('/api/shifts', json={
        'name': 'Test Excess Grace', 'start_time': '09:00', 'end_time': '17:00',
        'checkout_grace_period_minutes': 121
    })
    record_test("S1.3", "Shift Grace", "Reject checkout grace period > 120 (121)",
                400, res.status_code, res.status_code == 400)

    # Non-numeric test: "abc"
    res = client.post('/api/shifts', json={
        'name': 'Test NonNumeric Grace', 'start_time': '09:00', 'end_time': '17:00',
        'checkout_grace_period_minutes': 'abc'
    })
    record_test("S1.4", "Shift Grace", "Reject non-numeric checkout grace period ('abc')",
                400, res.status_code, res.status_code == 400)

    # Valid test: 15
    res = client.post('/api/shifts', json={
        'name': 'Test Valid Grace 15', 'start_time': '09:00', 'end_time': '17:00',
        'checkout_grace_period_minutes': 15
    })
    data = res.get_json() or {}
    test_shift_15_id = data.get('shift_id')
    if test_shift_15_id: created_shift_ids.append(test_shift_15_id)
    record_test("S1.5", "Shift Grace", "Accept valid checkout grace period 15 min",
                201, res.status_code, res.status_code == 201 and test_shift_15_id is not None)

    # Verify reloading / reading from API
    res = client.get('/api/shifts')
    all_shifts = (res.get_json() or {}).get('shifts', [])
    found = next((s for s in all_shifts if s.get('id') == test_shift_15_id), {})
    record_test("S1.6", "Shift Grace", "Reload shift and verify checkout grace period matches (15)",
                15, found.get('checkout_grace_period_minutes'), found.get('checkout_grace_period_minutes') == 15)

    # Valid test: update to 45
    res = client.put(f'/api/shifts/{test_shift_15_id}', json={
        'name': 'Test Valid Grace Updated', 'start_time': '09:00', 'end_time': '17:00',
        'checkout_grace_period_minutes': 45
    })
    record_test("S1.7", "Shift Grace", "Update shift checkout grace period to 45 min",
                200, res.status_code, res.status_code == 200)

    # Verify persistence in DB
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT checkout_grace_period_minutes FROM shifts WHERE id = ?", (test_shift_15_id,))
    row = c.fetchone()
    db_grace = row[0] if row else None
    conn.close()
    record_test("S1.8", "Shift Grace", "Database persisted updated checkout grace period (45)",
                45, db_grace, db_grace == 45)


    # -------------------------------------------------------------
    # FEATURE 2: OVERTIME CALCULATION RULE WITH CHECKOUT GRACE
    # -------------------------------------------------------------
    print("\n--- 2. OVERTIME CALCULATION: max(0, checkout - (shift_end + grace)) ---")

    # Shift 09:00-17:00, grace 15
    # 17:00 checkout -> 0
    ot_1700 = db.calculate_eligible_overtime('09:00', '17:00', '17:00', 15)
    record_test("OT2.1", "OT Rule", "Checkout exactly at shift end (17:00) with 15m grace -> 0 OT",
                0.0, ot_1700, ot_1700 == 0.0)

    # 17:10 checkout -> 0
    ot_1710 = db.calculate_eligible_overtime('09:00', '17:00', '17:10', 15)
    record_test("OT2.2", "OT Rule", "Checkout inside grace window (17:10) with 15m grace -> 0 OT",
                0.0, ot_1710, ot_1710 == 0.0)

    # 17:15 checkout -> 0
    ot_1715 = db.calculate_eligible_overtime('09:00', '17:00', '17:15', 15)
    record_test("OT2.3", "OT Rule", "Checkout exactly at end of grace (17:15) with 15m grace -> 0 OT",
                0.0, ot_1715, ot_1715 == 0.0)

    # 17:30 checkout -> 15 min (0.25h)
    ot_1730 = db.calculate_eligible_overtime('09:00', '17:00', '17:30', 15)
    record_test("OT2.4", "OT Rule", "Checkout after grace (17:30) with 15m grace -> 15 min (0.25h)",
                0.25, ot_1730, ot_1730 == 0.25)

    # 18:00 checkout -> 45 min (0.75h)
    ot_1800 = db.calculate_eligible_overtime('09:00', '17:00', '18:00', 15)
    record_test("OT2.5", "OT Rule", "Checkout at 18:00 with 15m grace -> 45 min (0.75h)",
                0.75, ot_1800, ot_1800 == 0.75)

    # Grace 0 preserves existing behavior: 17:30 checkout -> 30 min (0.5h)
    ot_zero_grace = db.calculate_eligible_overtime('09:00', '17:00', '17:30', 0)
    record_test("OT2.6", "OT Rule", "Grace 0 preserves existing calculation: checkout 17:30 -> 30 min (0.5h)",
                0.5, ot_zero_grace, ot_zero_grace == 0.5)

    # Overnight shift: 22:00 to 06:00 next day with 30 min grace
    # 06:20 checkout -> 0
    ot_on_early = db.calculate_eligible_overtime('22:00', '06:00', '06:20', 30)
    record_test("OT2.7", "OT Rule", "Overnight shift checkout within grace (06:20) with 30m grace -> 0 OT",
                0.0, ot_on_early, ot_on_early == 0.0)

    # 07:00 checkout -> 30 min (0.5h)
    ot_on_late = db.calculate_eligible_overtime('22:00', '06:00', '07:00', 30)
    record_test("OT2.8", "OT Rule", "Overnight shift checkout after grace (07:00) with 30m grace -> 30 min (0.5h)",
                0.5, ot_on_late, ot_on_late == 0.5)


    # -------------------------------------------------------------
    # TICKET 1: PAID LEAVE CLASSIFICATION SPLIT ACROSS COLUMNS
    # -------------------------------------------------------------
    print("\n--- 3. TICKET 1: PAID LEAVE CLASSIFICATION & SUMMARY ---")

    # Pick test employee: 38 (Imran Khalid)
    test_user_id = 38
    today = datetime.date.today()
    current_year = today.year
    current_month = today.month
    last_day = calendar.monthrange(current_year, current_month)[1]
    leave_start = datetime.date(current_year, current_month, 1)
    leave_end = min(datetime.date(current_year, current_month, min(5, last_day)), datetime.date(current_year, current_month, last_day))

    # Create a valid multi-day paid leave in the current month to avoid false negatives from future-month validation.
    c_res = client.post('/api/leaves', json={
        'user_id': test_user_id,
        'leave_type': 'casual',
        'start_date': leave_start.isoformat(),
        'end_date': leave_end.isoformat(),
        'reason': 'Multi-day Verification Casual Leave'
    })
    payload = c_res.get_json() or {}
    leave_id = payload.get('id') or payload.get('leave_id')
    if leave_id:
        created_leave_ids.append(leave_id)
        client.put(f'/api/leaves/{leave_id}', json={'status': 'approved', 'approved_by': 'Admin'})

    # Generate detailed attendance report for the current month
    rep_res = client.get(f'/api/reports/attendance?start_date={leave_start.isoformat()}&end_date={leave_end.isoformat()}&user_id={test_user_id}')
    rep_data = rep_res.get_json() or {}
    emp_summary = (rep_data.get('summary') or {}).get('employees', {}).get(str(test_user_id)) or {}

    paid_leaves = emp_summary.get('paid_leave_days', 0)
    unpaid_leaves = emp_summary.get('unpaid_leave_days', 0)
    payable_days = emp_summary.get('payable_days', 0)

    record_test("T1.1", "Paid Leave", "Multi-day approved paid leave is classified under paid leave days.",
                '>= 1', paid_leaves, paid_leaves >= 1, f"summary={emp_summary}")

    record_test("T1.2", "Paid Leave", "Unpaid leave days is 0 for paid leave.",
                0, unpaid_leaves, unpaid_leaves == 0)

    record_test("T1.3", "Paid Leave", "Payable days includes the generated paid leave days.",
                True, payable_days >= paid_leaves, payable_days >= paid_leaves, f"payable_days={payable_days}, paid_leaves={paid_leaves}")

    # Check monthly payroll calculation for the current valid month.
    payroll = db.calculate_monthly_payroll(current_year, current_month)
    user_pay = next((p for p in payroll if p.get('user_id') == test_user_id), {})
    payroll_paid_days = user_pay.get('paid_leave_days') or user_pay.get('paid_leaves') or 0
    record_test("T1.4", "Paid Leave", "Monthly payroll reflects the paid leave days for the current valid month.",
                '>= 1', payroll_paid_days, payroll_paid_days >= 1, f"user_pay={user_pay}")


    # -------------------------------------------------------------
    # TICKET 2: PAGINATION AND SEARCH FOR LEAVE BALANCES & REQUESTS
    # -------------------------------------------------------------
    print("\n--- 4. TICKET 2: PAGINATION AND SEARCH FOR LEAVES & BALANCES ---")

    with open('templates/index.html', 'r', encoding='utf-8') as f:
        idx_html = f.read()

    # Leave Requests pagination elements
    record_test("T2.1", "Leave Pagination", "Leave search input with oninput handler exists",
                True, 'id="leaveSearch"' in idx_html and 'onLeaveSearchInput()' in idx_html,
                'id="leaveSearch"' in idx_html and 'onLeaveSearchInput()' in idx_html)

    record_test("T2.2", "Leave Pagination", "Leave page size selector (10, 25, 50, 100) exists",
                True, 'id="leavePageSize"' in idx_html and 'changeLeavePageSize(this.value)' in idx_html,
                'id="leavePageSize"' in idx_html and 'changeLeavePageSize(this.value)' in idx_html)

    record_test("T2.3", "Leave Pagination", "Leave pagination bar with info and prev/next buttons exists",
                True, 'id="leavePaginationBar"' in idx_html and 'id="leavePrevBtn"' in idx_html and 'id="leaveNextBtn"' in idx_html,
                'id="leavePaginationBar"' in idx_html and 'id="leavePrevBtn"' in idx_html and 'id="leaveNextBtn"' in idx_html)

    # Leave Balances pagination elements
    record_test("T2.4", "Leave Pagination", "Leave balance search input exists",
                True, 'id="leaveBalanceSearch"' in idx_html and 'onLeaveBalanceSearchInput()' in idx_html,
                'id="leaveBalanceSearch"' in idx_html and 'onLeaveBalanceSearchInput()' in idx_html)

    record_test("T2.5", "Leave Pagination", "Leave balance page size selector exists",
                True, 'id="leaveBalancePageSize"' in idx_html and 'changeLeaveBalancePageSize(this.value)' in idx_html,
                'id="leaveBalancePageSize"' in idx_html and 'changeLeaveBalancePageSize(this.value)' in idx_html)

    record_test("T2.6", "Leave Pagination", "Leave balance pagination bar with info and prev/next buttons exists",
                True, 'id="leaveBalancePaginationBar"' in idx_html and 'id="leaveBalancePrevBtn"' in idx_html and 'id="leaveBalanceNextBtn"' in idx_html,
                'id="leaveBalancePaginationBar"' in idx_html and 'id="leaveBalancePrevBtn"' in idx_html and 'id="leaveBalanceNextBtn"' in idx_html)

    # Check API endpoints for leave requests and balances
    res_l = client.get('/api/leaves')
    record_test("T2.7", "Leave API", "GET /api/leaves returns 200 with list",
                200, res_l.status_code, res_l.status_code == 200 and isinstance(res_l.get_json(), list))

    res_b = client.get('/api/leaves/balances?year=2026')
    record_test("T2.8", "Leave API", "GET /api/leaves/balances returns 200 with list",
                200, res_b.status_code, res_b.status_code == 200 and isinstance(res_b.get_json(), list))


    # -------------------------------------------------------------
    # TICKET 3: MANUAL MARK ATTENDANCE — SHIFT DROPDOWN & HISTORICAL PRESERVATION
    # -------------------------------------------------------------
    print("\n--- 5. TICKET 3: MANUAL MARK ATTENDANCE WITH SHIFT SELECTION ---")

    # Check User 38 original assigned shift
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT shift_id FROM users WHERE id = ?", (test_user_id,))
    orig_user_shift = c.fetchone()[0]
    conn.close()

    # Create distinct shift for manual entry (e.g. 10:00 - 18:00, grace 20)
    res_shift = client.post('/api/shifts', json={
        'name': 'Special Manual Shift', 'start_time': '10:00', 'end_time': '18:00',
        'checkout_grace_period_minutes': 20
    })
    special_shift_id = (res_shift.get_json() or {}).get('shift_id')
    if special_shift_id: created_shift_ids.append(special_shift_id)

    # Mark user present using special shift on test date '2026-11-10'
    test_att_date = '2026-11-10'
    res_manual = client.post(f'/api/users/{test_user_id}/mark-present', json={
        'date': test_att_date,
        'shift_id': special_shift_id,
        'check_in': '10:00',
        'check_out': '19:00',  # 1h after 18:00, grace is 20m -> OT should be 40 mins (0.67h)
        'notes': 'Manual shift test'
    })
    record_test("T3.1", "Manual Mark", "Mark attendance with specific shift_id succeeds",
                200, res_manual.status_code, res_manual.status_code == 200)

    # Check attendance record in DB
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("""SELECT id, shift_id, source, marked_by FROM attendance 
                 WHERE user_id = ? AND date(timestamp) = ? ORDER BY id DESC LIMIT 1""",
              (test_user_id, test_att_date))
    att_row = c.fetchone()
    if att_row:
        att_id, att_shift_id, att_source, att_marked_by = att_row
        created_attendance_ids.append(att_id)
    else:
        att_id, att_shift_id, att_source, att_marked_by = None, None, None, None

    # Check user permanent shift in users table
    c.execute("SELECT shift_id FROM users WHERE id = ?", (test_user_id,))
    current_user_shift = c.fetchone()[0]
    conn.close()

    record_test("T3.2", "Manual Mark", "Attendance record persists chosen shift_id",
                special_shift_id, att_shift_id, att_shift_id == special_shift_id)

    record_test("T3.3", "Manual Mark", "User permanent shift_id remains untouched",
                orig_user_shift, current_user_shift, current_user_shift == orig_user_shift)

    record_test("T3.4", "Manual Mark", "Attendance source is recorded as 'manual'",
                'manual', att_source, att_source == 'manual')

    # Check overtime record created for this manual attendance entry
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT id, hours, status FROM overtime WHERE user_id = ? AND ot_date = ?", (test_user_id, test_att_date))
    ot_row = c.fetchone()
    conn.close()
    if ot_row:
        ot_id, ot_hrs, ot_stat = ot_row
        created_overtime_ids.append(ot_id)
    else:
        ot_id, ot_hrs, ot_stat = None, None, None

    # 18:00 shift end + 20 min grace = 18:20. Checkout at 19:00 -> 40 min = 0.67 hr
    expected_ot = round(40 / 60.0, 2)
    record_test("T3.5", "Manual Mark", "Overtime calculated using chosen shift and checkout grace (40 mins = 0.67h)",
                expected_ot, ot_hrs, ot_hrs == expected_ot, f"ot_row={ot_row}")


    # -------------------------------------------------------------
    # TICKET 4: ATTENDANCE REPORTS QUICK ACTIONS & CHECKOUT VALIDATION
    # -------------------------------------------------------------
    print("\n--- 6. TICKET 4: QUICK ACTIONS & CHECKOUT VALIDATION ---")

    # Validation: empty checkout
    res_val1 = client.post(f'/api/users/{test_user_id}/mark-present', json={
        'date': '2026-11-12', 'check_in': '09:00', 'check_out': ''
    })
    record_test("T4.1", "Checkout Validation", "Reject empty checkout time",
                400, res_val1.status_code, res_val1.status_code == 400)

    # Validation: '0' checkout
    res_val2 = client.post(f'/api/users/{test_user_id}/mark-present', json={
        'date': '2026-11-12', 'check_in': '09:00', 'check_out': '0'
    })
    record_test("T4.2", "Checkout Validation", "Reject '0' checkout time",
                400, res_val2.status_code, res_val2.status_code == 400)

    # Validation: checkout <= checkin on same day
    res_val3 = client.post(f'/api/users/{test_user_id}/mark-present', json={
        'date': '2026-11-12', 'check_in': '09:00', 'check_out': '08:30'
    })
    record_test("T4.3", "Checkout Validation", "Reject checkout <= checkin for daytime shift",
                400, res_val3.status_code, res_val3.status_code == 400)

    # Overnight checkout: checkin 22:00, checkout 06:30 with overnight shift
    res_val4 = client.post(f'/api/users/{test_user_id}/mark-present', json={
        'date': '2026-11-12', 'shift_id': 3, 'check_in': '22:00', 'check_out': '06:30'
    })
    record_test("T4.4", "Checkout Validation", "Accept valid overnight checkout (22:00 to 06:30)",
                200, res_val4.status_code, res_val4.status_code == 200)

    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT id FROM attendance WHERE user_id = ? AND date(timestamp) = '2026-11-12'", (test_user_id,))
    for r in c.fetchall(): created_attendance_ids.append(r[0])
    c.execute("SELECT id FROM overtime WHERE user_id = ? AND ot_date = '2026-11-12'", (test_user_id,))
    for r in c.fetchall(): created_overtime_ids.append(r[0])
    conn.close()

    # Quick Action: Mark Absent on date 2026-11-13
    res_absent = client.post('/api/attendance/mark-absent', json={
        'user_id': test_user_id, 'date': '2026-11-13', 'reason': 'Quick Action Test'
    })
    record_test("T4.5", "Quick Actions", "Mark Absent returns 200 and records absence",
                200, res_absent.status_code, res_absent.status_code == 200)
    created_manual_absents.append((test_user_id, '2026-11-13'))


    # -------------------------------------------------------------
    # TICKET 5: MANUAL ATTENDANCE MUST SHOW "MANUAL BY ADMIN"
    # -------------------------------------------------------------
    print("\n--- 7. TICKET 5: SOURCE ATTRIBUTION (MANUAL BY ADMIN VS AUTO BY SYSTEM) ---")

    # Query attendance report for the test manual attendance record on 2026-11-10
    rep_res_source = client.get(f'/api/reports/attendance?start_date=2026-11-10&end_date=2026-11-10&user_id={test_user_id}')
    rep_rows = (rep_res_source.get_json() or {}).get('rows', [])
    manual_rep_row = next((r for r in rep_rows if r.get('user_id') == test_user_id), {})

    source_val = manual_rep_row.get('source')
    source_label = manual_rep_row.get('source_label')
    marked_by = manual_rep_row.get('marked_by')

    record_test("T5.1", "Source Label", "Manual attendance record has source == 'manual'",
                'manual', source_val, source_val == 'manual')

    record_test("T5.2", "Source Label", "Manual attendance reports 'Manual by Admin'",
                'Manual by Admin', source_label, source_label == 'Manual by Admin')

    record_test("T5.3", "Source Label", "Manual attendance records marked_by admin attribution",
                'Admin', marked_by, marked_by in ['Admin', 'admin'])

    # Verify template code displays 'Manual by Admin' when source === 'manual'
    record_test("T5.4", "Source UI", "templates/index.html renders 'Manual by Admin' for manual source",
                True, 'Manual by Admin' in idx_html and 'Auto by System' in idx_html,
                'Manual by Admin' in idx_html and 'Auto by System' in idx_html)

    with open('templates/attendance_report.html', 'r', encoding='utf-8') as f:
        att_rep_html = f.read()
    record_test("T5.5", "Source UI", "templates/attendance_report.html renders 'Manual by Admin'",
                True, 'Manual by Admin' in att_rep_html and 'Auto by System' in att_rep_html,
                'Manual by Admin' in att_rep_html and 'Auto by System' in att_rep_html)


    # -------------------------------------------------------------
    # FEATURE 5 & 6: OVERTIME APPROVAL WORKFLOW & IMMUTABILITY
    # -------------------------------------------------------------
    print("\n--- 8. FEATURE 5 & 6: OVERTIME APPROVAL WORKFLOW & IMMUTABILITY ---")

    # Create pending OT record
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT name, shift_id FROM users WHERE id = ?", (test_user_id,))
    ot_test_user = c.fetchone()
    for attendance_date in ('2026-11-16', '2026-11-17'):
        c.execute('''
            INSERT INTO attendance (user_id, detected_name, confidence, source, timestamp, notes, marked_by, shift_id)
            VALUES (?, ?, 1.0, 'manual', ?, 'OT finality verification', 'Admin', ?)
        ''', (test_user_id, ot_test_user[0], f'{attendance_date} 09:00:00', ot_test_user[1]))
        created_attendance_ids.append(c.lastrowid)

    c.execute("""INSERT INTO overtime (user_id, user_name, ot_date, hours, reason, status) 
                 VALUES (?, 'Imran Khalid', '2026-11-16', 2.0, 'Immutability test 1', 'pending')""",
              (test_user_id,))
    ot_test_1_id = c.lastrowid
    created_overtime_ids.append(ot_test_1_id)

    c.execute("""INSERT INTO overtime (user_id, user_name, ot_date, hours, reason, status) 
                 VALUES (?, 'Imran Khalid', '2026-11-17', 3.0, 'Immutability test 2', 'pending')""",
              (test_user_id,))
    ot_test_2_id = c.lastrowid
    created_overtime_ids.append(ot_test_2_id)
    conn.commit()
    conn.close()

    # 1. Approve record 1
    res_app = client.put(f'/api/overtime/{ot_test_1_id}', json={'status': 'approved', 'approved_by': 'Admin'})
    record_test("OT6.1", "OT Immutability", "Approve pending overtime record returns 200",
                200, res_app.status_code, res_app.status_code == 200)

    # 2. Attempt to modify already approved record -> must fail with 409 Conflict
    res_imm1 = client.put(f'/api/overtime/{ot_test_1_id}', json={'status': 'rejected', 'approved_by': 'Admin'})
    record_test("OT6.2", "OT Immutability", "Rejecting an already approved overtime record returns 409 Conflict",
                409, res_imm1.status_code, res_imm1.status_code == 409)

    # 3. Reject record 2
    res_rej = client.put(f'/api/overtime/{ot_test_2_id}', json={'status': 'rejected', 'approved_by': 'Admin'})
    record_test("OT6.3", "OT Immutability", "Reject pending overtime record returns 200",
                200, res_rej.status_code, res_rej.status_code == 200)

    # 4. Attempt to modify already rejected record -> must fail with 409 Conflict
    res_imm2 = client.put(f'/api/overtime/{ot_test_2_id}', json={'status': 'approved', 'approved_by': 'Admin'})
    record_test("OT6.4", "OT Immutability", "Approving an already rejected overtime record returns 409 Conflict",
                409, res_imm2.status_code, res_imm2.status_code == 409)

    # 5. Bulk approve skips already finalized records
    res_bulk = client.post('/api/overtime/bulk-approve', json={'ids': [ot_test_1_id, ot_test_2_id]})
    bulk_data = res_bulk.get_json() or {}
    record_test("OT6.5", "OT Immutability", "Bulk approve skips already approved/rejected records (updated_count == 0)",
                0, bulk_data.get('updated_count'), bulk_data.get('updated_count') == 0)

    # 6. Verify UI modal and approval subtab elements
    record_test("OT6.6", "OT UI", "Overtime approval subtab (#subtab-ot-approval) exists in index.html",
                True, 'id="subtab-ot-approval"' in idx_html, 'id="subtab-ot-approval"' in idx_html)

    record_test("OT6.7", "OT UI", "Overtime detail popup modal (#otDetailModal) with month nav exists",
                True, 'id="otDetailModal"' in idx_html and 'otModalPrevMonth' in idx_html,
                'id="otDetailModal"' in idx_html and 'otModalPrevMonth' in idx_html)

    record_test("OT6.8", "OT UI", "Confirmation dialogs with permanence warning exist in script",
                True, 'This decision is permanent and cannot be undone' in idx_html,
                'This decision is permanent and cannot be undone' in idx_html)

finally:
    # -------------------------------------------------------------
    # CLEANUP & DATABASE INTEGRITY VERIFICATION
    # -------------------------------------------------------------
    print("\n--- 9. CLEANUP OF TEST RECORDS & INTEGRITY VERIFICATION ---")
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()

    if created_shift_ids:
        c.execute(f"DELETE FROM shifts WHERE id IN ({','.join(map(str, created_shift_ids))})")
    if created_attendance_ids:
        c.execute(f"DELETE FROM attendance WHERE id IN ({','.join(map(str, created_attendance_ids))})")
    if created_overtime_ids:
        c.execute(f"DELETE FROM overtime WHERE id IN ({','.join(map(str, created_overtime_ids))})")
    if created_leave_ids:
        c.execute(f"DELETE FROM leave_requests WHERE id IN ({','.join(map(str, created_leave_ids))})")
    for u_id, dt in created_manual_absents:
        c.execute("DELETE FROM manual_absent WHERE user_id = ? AND date = ?", (u_id, dt))
    conn.commit()

    # Verify counts returned to baseline
    c.execute("SELECT count(*) FROM shifts")
    curr_shifts = c.fetchone()[0]
    c.execute("SELECT count(*) FROM attendance")
    curr_attendance = c.fetchone()[0]
    c.execute("SELECT count(*) FROM overtime")
    curr_overtime = c.fetchone()[0]
    c.execute("SELECT count(*) FROM leave_requests")
    curr_leaves = c.fetchone()[0]
    c.execute("SELECT count(*) FROM manual_absent")
    curr_manual_absent = c.fetchone()[0]

    record_test("CLN.1", "Cleanup", f"Shifts table restored to baseline ({baseline_shifts})",
                baseline_shifts, curr_shifts, curr_shifts == baseline_shifts)

    record_test("CLN.2", "Cleanup", f"Attendance table restored to baseline ({baseline_attendance})",
                baseline_attendance, curr_attendance, curr_attendance == baseline_attendance)

    record_test("CLN.3", "Cleanup", f"Overtime table restored to baseline ({baseline_overtime})",
                baseline_overtime, curr_overtime, curr_overtime == baseline_overtime)

    record_test("CLN.4", "Cleanup", f"Leave requests table restored to baseline ({baseline_leaves})",
                baseline_leaves, curr_leaves, curr_leaves == baseline_leaves)

    record_test("CLN.5", "Cleanup", f"Manual absent table restored to baseline ({baseline_manual_absent})",
                baseline_manual_absent, curr_manual_absent, curr_manual_absent == baseline_manual_absent)

    # PRAGMA integrity_check
    c.execute("PRAGMA integrity_check")
    integrity = c.fetchone()[0]
    record_test("INT.1", "DB Integrity", "PRAGMA integrity_check passes",
                "ok", integrity, integrity == "ok")

    # PRAGMA foreign_key_check: must not introduce new violations beyond baseline
    c.execute("PRAGMA foreign_key_check")
    fk_violations = c.fetchall()
    record_test("INT.2", "DB Integrity", f"PRAGMA foreign_key_check has 0 new violations ({baseline_fk_violations})",
                baseline_fk_violations, len(fk_violations), len(fk_violations) == baseline_fk_violations)

    conn.close()

print("\n" + "=" * 80)
total_tests = len(results)
passed_tests = sum(1 for r in results if r['status'] == 'PASS')
failed_tests = total_tests - passed_tests
print(f"VERIFICATION SUMMARY: TOTAL={total_tests}, PASSED={passed_tests}, FAILED={failed_tests}")
if failed_tests == 0:
    print("ALL SIX TICKETS FIXED AND VERIFIED SUCCESSFULLY!")
else:
    print(f"WARNING: {failed_tests} TESTS FAILED!")
print("=" * 80)
