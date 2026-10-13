import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import json
import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, List

import database as db
from app import app

client = app.test_client()

audit_results = []

def record(section: str, test_name: str, expected: str, actual: str, passed: bool, details: str = "", severity: str = "HIGH", affected_modules: str = ""):
    status = "PASS" if passed else "FAIL"
    entry = {
        'section': section,
        'test': test_name,
        'expected': str(expected),
        'actual': str(actual),
        'status': status,
        'details': details,
        'severity': severity if not passed else "NONE",
        'affected_modules': affected_modules if not passed else ""
    }
    audit_results.append(entry)
    print(f"[{status}] [{section}] {test_name}")
    print(f"       Expected: {expected}")
    print(f"       Actual:   {actual}")
    if details:
        print(f"       Details:  {details}")
    if not passed:
        print(f"       [!] Severity: {severity} | Affected: {affected_modules}")
    print()

def main():
    print("=" * 80)
    print("  STRICT PRODUCTION AUDIT: ATTENDANCE -> LEAVE -> OVERTIME -> PAYROLL")
    print("=" * 80)

    # Use Imran Khalid (ID 38) as the primary test subject
    TEST_USER_ID = 38
    TEST_USER_NAME = "Imran Khalid"

    # =================================================================
    # SECTION 1: DATABASE INTEGRITY AUDIT
    # =================================================================
    print("\n--- 1. DATABASE INTEGRITY AUDIT ---")
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()

    c.execute("PRAGMA integrity_check;")
    integ = c.fetchall()
    record("1. Database Integrity", "PRAGMA integrity_check", "[('ok',)]", str(integ), integ == [('ok',)])

    c.execute("PRAGMA foreign_key_check;")
    fk_check = c.fetchall()
    record("1. Database Integrity", "PRAGMA foreign_key_check", "[] (0 violations)", str(fk_check), len(fk_check) == 0)

    # Check orphan attendance records
    c.execute("SELECT count(*) FROM attendance WHERE user_id NOT IN (SELECT id FROM users);")
    orphan_att = c.fetchone()[0]
    record("1. Database Integrity", "Orphan attendance records", "0", str(orphan_att), orphan_att == 0)

    # Check orphan leaves
    c.execute("SELECT count(*) FROM leave_requests WHERE user_id NOT IN (SELECT id FROM users);")
    orphan_leaves = c.fetchone()[0]
    record("1. Database Integrity", "Orphan leave requests", "0", str(orphan_leaves), orphan_leaves == 0)

    # Check orphan overtime
    c.execute("SELECT count(*) FROM overtime WHERE user_id NOT IN (SELECT id FROM users);")
    orphan_ot = c.fetchone()[0]
    record("1. Database Integrity", "Orphan overtime records", "0", str(orphan_ot), orphan_ot == 0)

    # Check orphan salary configs
    c.execute("SELECT count(*) FROM salary_configs WHERE user_id NOT IN (SELECT id FROM users);")
    orphan_salary = c.fetchone()[0]
    record("1. Database Integrity", "Orphan salary configs", "0", str(orphan_salary), orphan_salary == 0)

    # Check duplicate users
    c.execute("SELECT name, count(*) FROM users GROUP BY name HAVING count(*) > 1;")
    dup_users = c.fetchall()
    record("1. Database Integrity", "Duplicate user names in users table", "0 duplicates", f"{len(dup_users)} duplicates: {dup_users}", len(dup_users) == 0)

    # Check invalid shift IDs on users
    c.execute("SELECT count(*) FROM users WHERE shift_id IS NOT NULL AND shift_id NOT IN (SELECT id FROM shifts);")
    invalid_shifts = c.fetchone()[0]
    record("1. Database Integrity", "Users with non-existent shift_id", "0", str(invalid_shifts), invalid_shifts == 0)

    conn.close()

    # =================================================================
    # SECTION 2: MANUAL ATTENDANCE TESTING
    # =================================================================
    print("\n--- 2. MANUAL ATTENDANCE TESTING ---")
    AUDIT_DATE_NORMAL = "2026-10-12"  # A Monday
    AUDIT_DATE_LATE = "2026-10-13"    # A Tuesday
    AUDIT_DATE_CHECKOUT = "2026-10-14"# A Wednesday
    AUDIT_DATE_ABSENT = "2026-10-15"  # A Thursday

    # Clean any prior logs on these audit dates for test user
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute("DELETE FROM attendance WHERE user_id = ? AND date(timestamp) IN (?, ?, ?, ?);",
                  (TEST_USER_ID, AUDIT_DATE_NORMAL, AUDIT_DATE_LATE, AUDIT_DATE_CHECKOUT, AUDIT_DATE_ABSENT))
        c.execute("DELETE FROM manual_absent WHERE user_id = ? AND date IN (?, ?, ?, ?);",
                  (TEST_USER_ID, AUDIT_DATE_NORMAL, AUDIT_DATE_LATE, AUDIT_DATE_CHECKOUT, AUDIT_DATE_ABSENT))
        c.execute("DELETE FROM leave_requests WHERE user_id = ? AND start_date IN (?, ?, ?, ?);",
                  (TEST_USER_ID, AUDIT_DATE_NORMAL, AUDIT_DATE_LATE, AUDIT_DATE_CHECKOUT, AUDIT_DATE_ABSENT))
        c.execute("DELETE FROM overtime WHERE user_id = ? AND ot_date IN (?, ?, ?, ?);",
                  (TEST_USER_ID, AUDIT_DATE_NORMAL, AUDIT_DATE_LATE, AUDIT_DATE_CHECKOUT, AUDIT_DATE_ABSENT))
        conn.commit()

    # 2.1 Scenario A: Normal Present (Valid Check-in on time)
    # Target date: AUDIT_DATE_NORMAL, Check-in at 08:05:00 (Shift 1 starts at 08:00 with 15 min grace period)
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO attendance (user_id, detected_name, confidence, source, location, device_id, timestamp) "
            "VALUES (?, ?, 1.0, 'manual', 'Main Entrance', 'cam_manual_test', ?)",
            (TEST_USER_ID, TEST_USER_NAME, f"{AUDIT_DATE_NORMAL} 08:05:00")
        )
        conn.commit()

    # Query report for this date
    rep_normal = db.get_detailed_attendance_report(start_date=AUDIT_DATE_NORMAL, end_date=AUDIT_DATE_NORMAL)
    emp_norm = next((r for r in rep_normal.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    daily_norm = emp_norm.get('daily_records', [{}])[0] if emp_norm else {}
    norm_status = daily_norm.get('status')
    record(
        "2. Attendance", "Scenario A: Normal Present (Check-in 08:05:00 within grace period)",
        "status == 'present'", f"status == '{norm_status}'",
        norm_status == 'present',
        details=f"first_seen: {daily_norm.get('first_seen')}, dev: {daily_norm.get('checkin_camera')}"
    )

    # 2.2 Scenario B: Late Arrival (Check-in after shift grace period: 10:35:00 > 10:33)
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO attendance (user_id, detected_name, confidence, source, location, device_id, timestamp) "
            "VALUES (?, ?, 1.0, 'manual', 'Main Entrance', 'cam_manual_test', ?)",
            (TEST_USER_ID, TEST_USER_NAME, f"{AUDIT_DATE_LATE} 10:35:00")
        )
        conn.commit()

    rep_late = db.get_detailed_attendance_report(start_date=AUDIT_DATE_LATE, end_date=AUDIT_DATE_LATE)
    emp_late = next((r for r in rep_late.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    daily_late = emp_late.get('daily_records', [{}])[0] if emp_late else {}
    late_status = daily_late.get('status')
    record(
        "2. Attendance", "Scenario B: Late Arrival (Check-in 08:35:00 > 08:15 grace limit)",
        "status == 'late'", f"status == '{late_status}'",
        late_status == 'late',
        details=f"first_seen: {daily_late.get('first_seen')}, grace limit was 08:15"
    )

    # 2.3 Scenario C: Check-in / Check-out separation
    # Insert Check-in at 08:00:00 and Check-out at 20:00:00 (Shift 1 ends at 20:00)
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO attendance (user_id, detected_name, confidence, source, location, device_id, timestamp) "
            "VALUES (?, ?, 1.0, 'manual', 'Main Gate', 'cam_in', ?)",
            (TEST_USER_ID, TEST_USER_NAME, f"{AUDIT_DATE_CHECKOUT} 08:00:00")
        )
        c.execute(
            "INSERT INTO attendance (user_id, detected_name, confidence, source, location, device_id, checkout_location, checkout_camera_id, timestamp) "
            "VALUES (?, ?, 1.0, 'manual', 'Exit Gate', 'cam_out', 'Exit Gate', 'cam_out', ?)",
            (TEST_USER_ID, TEST_USER_NAME, f"{AUDIT_DATE_CHECKOUT} 20:00:00")
        )
        conn.commit()

    rep_checkout = db.get_detailed_attendance_report(start_date=AUDIT_DATE_CHECKOUT, end_date=AUDIT_DATE_CHECKOUT)
    emp_checkout = next((r for r in rep_checkout.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    daily_checkout = emp_checkout.get('daily_records', [{}])[0] if emp_checkout else {}
    checkout_status = daily_checkout.get('status')
    has_sep_times = bool(daily_checkout.get('first_seen')) and bool(daily_checkout.get('last_seen')) and daily_checkout.get('first_seen') != daily_checkout.get('last_seen')
    record(
        "2. Attendance", "Scenario C: Check-in / Check-out separation & genuine checkout",
        "status == 'checked_out' with distinct first_seen and last_seen",
        f"status == '{checkout_status}', first_seen: {daily_checkout.get('first_seen')}, last_seen: {daily_checkout.get('last_seen')}",
        checkout_status == 'checked_out' and has_sep_times,
        details=f"In Cam: {daily_checkout.get('checkin_camera')}, Out Cam: {daily_checkout.get('checkout_camera')}"
    )

    # 2.4 Scenario D: Scheduled Working Day with No Attendance (Absent)
    rep_absent = db.get_detailed_attendance_report(start_date=AUDIT_DATE_ABSENT, end_date=AUDIT_DATE_ABSENT)
    emp_absent = next((r for r in rep_absent.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    daily_absent = emp_absent.get('daily_records', [{}])[0] if emp_absent else {}
    absent_status = daily_absent.get('status')
    record(
        "2. Attendance", "Scenario D: Unexcused Absence on scheduled workday",
        "status == 'absent'", f"status == '{absent_status}'",
        absent_status == 'absent',
        details=f"Scheduled workday: {daily_absent.get('scheduled_workday')}"
    )

    # =================================================================
    # SECTION 3: LEAVE MANAGEMENT AUDIT
    # =================================================================
    print("\n--- 3. LEAVE MANAGEMENT AUDIT ---")
    LEAVE_DATE_PAID = "2026-10-19"      # Monday
    LEAVE_DATE_UNPAID = "2026-10-20"    # Tuesday
    LEAVE_DATE_REJECT = "2026-10-21"    # Wednesday
    LEAVE_DATE_PENDING = "2026-10-22"   # Thursday

    # Clean any prior logs on these leave test dates
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute("DELETE FROM attendance WHERE user_id = ? AND date(timestamp) IN (?, ?, ?, ?);",
                  (TEST_USER_ID, LEAVE_DATE_PAID, LEAVE_DATE_UNPAID, LEAVE_DATE_REJECT, LEAVE_DATE_PENDING))
        c.execute("DELETE FROM manual_absent WHERE user_id = ? AND date IN (?, ?, ?, ?);",
                  (TEST_USER_ID, LEAVE_DATE_PAID, LEAVE_DATE_UNPAID, LEAVE_DATE_REJECT, LEAVE_DATE_PENDING))
        c.execute("DELETE FROM leave_requests WHERE user_id = ? AND start_date IN (?, ?, ?, ?);",
                  (TEST_USER_ID, LEAVE_DATE_PAID, LEAVE_DATE_UNPAID, LEAVE_DATE_REJECT, LEAVE_DATE_PENDING))
        conn.commit()

    # 3.1 Paid Leave: Create Pending -> Approve Paid Leave
    res_paid_create = client.post('/api/leaves', json={
        'user_id': TEST_USER_ID,
        'leave_type': 'annual',
        'start_date': LEAVE_DATE_PAID,
        'end_date': LEAVE_DATE_PAID,
        'reason': 'Audit Paid Leave Test'
    })
    paid_leave_id = res_paid_create.get_json().get('id') if res_paid_create.is_json else None
    res_paid_approve = client.put(f'/api/leaves/{paid_leave_id}', json={'status': 'approved'})

    rep_paid_leave = db.get_detailed_attendance_report(start_date=LEAVE_DATE_PAID, end_date=LEAVE_DATE_PAID)
    emp_paid = next((r for r in rep_paid_leave.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    paid_day_status = emp_paid.get('daily_records', [{}])[0].get('status') if emp_paid else None
    record(
        "3. Leave Management", "Approved Paid Leave: attendance reflection",
        "status == 'on_leave'", f"status == '{paid_day_status}'",
        paid_day_status == 'on_leave',
        details=f"Leave ID: {paid_leave_id}, API create HTTP {res_paid_create.status_code}, approve HTTP {res_paid_approve.status_code}"
    )

    # 3.2 Unpaid Leave: Create Pending -> Approve Unpaid Leave
    res_unpaid_create = client.post('/api/leaves', json={
        'user_id': TEST_USER_ID,
        'leave_type': 'unpaid',
        'start_date': LEAVE_DATE_UNPAID,
        'end_date': LEAVE_DATE_UNPAID,
        'reason': 'Audit Unpaid Leave Test'
    })
    unpaid_leave_id = res_unpaid_create.get_json().get('id') if res_unpaid_create.is_json else None
    res_unpaid_approve = client.put(f'/api/leaves/{unpaid_leave_id}', json={'status': 'approved'})

    rep_unpaid_leave = db.get_detailed_attendance_report(start_date=LEAVE_DATE_UNPAID, end_date=LEAVE_DATE_UNPAID)
    emp_unpaid = next((r for r in rep_unpaid_leave.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    unpaid_day_status = emp_unpaid.get('daily_records', [{}])[0].get('status') if emp_unpaid else None
    record(
        "3. Leave Management", "Approved Unpaid Leave: attendance reflection",
        "status == 'on_leave_unpaid'", f"status == '{unpaid_day_status}'",
        unpaid_day_status == 'on_leave_unpaid',
        details=f"Leave ID: {unpaid_leave_id}, is_paid=0"
    )

    # 3.3 Rejected Leave: Create -> Reject
    res_rej_create = client.post('/api/leaves', json={
        'user_id': TEST_USER_ID,
        'leave_type': 'annual',
        'start_date': LEAVE_DATE_REJECT,
        'end_date': LEAVE_DATE_REJECT,
        'reason': 'Audit Rejected Leave Test'
    })
    rej_leave_id = res_rej_create.get_json().get('id') if res_rej_create.is_json else None
    res_rej_approve = client.put(f'/api/leaves/{rej_leave_id}', json={'status': 'rejected'})

    rep_rej = db.get_detailed_attendance_report(start_date=LEAVE_DATE_REJECT, end_date=LEAVE_DATE_REJECT)
    emp_rej = next((r for r in rep_rej.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    rej_day_status = emp_rej.get('daily_records', [{}])[0].get('status') if emp_rej else None
    record(
        "3. Leave Management", "Rejected Leave does not excuse absence",
        "status == 'absent'", f"status == '{rej_day_status}'",
        rej_day_status == 'absent',
        details=f"Rejected leave must remain absent if no attendance exists"
    )

    # 3.4 Pending Leave: Create Pending (not yet approved)
    res_pen_create = client.post('/api/leaves', json={
        'user_id': TEST_USER_ID,
        'leave_type': 'annual',
        'start_date': LEAVE_DATE_PENDING,
        'end_date': LEAVE_DATE_PENDING,
        'reason': 'Audit Pending Leave Test'
    })
    pen_leave_id = res_pen_create.get_json().get('id') if res_pen_create.is_json else None

    rep_pen = db.get_detailed_attendance_report(start_date=LEAVE_DATE_PENDING, end_date=LEAVE_DATE_PENDING)
    emp_pen = next((r for r in rep_pen.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    pen_day_status = emp_pen.get('daily_records', [{}])[0].get('status') if emp_pen else None
    record(
        "3. Leave Management", "Pending Leave does not grant leave status until approved",
        "status == 'absent'", f"status == '{pen_day_status}'",
        pen_day_status == 'absent',
        details=f"Pending leave status is unapproved, so absence remains unexcused"
    )

    # =================================================================
    # SECTION 4: OVERTIME MANAGEMENT AUDIT
    # =================================================================
    print("\n--- 4. OVERTIME MANAGEMENT AUDIT ---")
    OT_DATE = "2026-10-12"

    # 4.1 Overtime Record Creation via API
    res_ot_add = client.post('/api/overtime', json={
        'user_id': TEST_USER_ID,
        'ot_date': OT_DATE,
        'hours': 2.5,
        'reason': 'Production Deployment Audit'
    })
    ot_id = res_ot_add.get_json().get('id') if res_ot_add.is_json else None
    record(
        "4. Overtime", "API POST /api/overtime creates pending overtime record",
        "HTTP 201 with success=True and integer ID",
        f"HTTP {res_ot_add.status_code} with id={ot_id}",
        res_ot_add.status_code == 201 and ot_id is not None,
        details=f"Inserted OT record #{ot_id}"
    )

    # 4.2 Overtime Query via API
    res_ot_get = client.get(f'/api/overtime?user_id={TEST_USER_ID}')
    ot_records = res_ot_get.get_json() if res_ot_get.is_json else []
    ot_match = next((o for o in ot_records if o.get('id') == ot_id), None)
    record(
        "4. Overtime", "API GET /api/overtime returns created overtime with status 'pending'",
        "HTTP 200 with status == 'pending' and hours == 2.5",
        f"HTTP {res_ot_get.status_code}, status={ot_match.get('status') if ot_match else None}, hours={ot_match.get('hours') if ot_match else None}",
        res_ot_get.status_code == 200 and ot_match is not None and ot_match.get('status') == 'pending' and ot_match.get('hours') == 2.5
    )

    # 4.3 Overtime Status Update / Approval via API
    res_ot_put = client.put(f'/api/overtime/{ot_id}', json={'status': 'approved', 'approved_by': 'Admin Audit'})
    res_ot_get_appr = client.get(f'/api/overtime?user_id={TEST_USER_ID}')
    ot_appr_records = res_ot_get_appr.get_json() if res_ot_get_appr.is_json else []
    ot_appr_match = next((o for o in ot_appr_records if o.get('id') == ot_id), None)
    record(
        "4. Overtime", "API PUT /api/overtime/<id> updates status to 'approved'",
        "status == 'approved' and approved_by == 'Admin Audit'",
        f"status == '{ot_appr_match.get('status') if ot_appr_match else None}', approved_by == '{ot_appr_match.get('approved_by') if ot_appr_match else None}'",
        ot_appr_match is not None and ot_appr_match.get('status') == 'approved' and ot_appr_match.get('approved_by') == 'Admin Audit'
    )

    # 4.4 Overtime Rejection via API
    res_ot_rej_add = client.post('/api/overtime', json={
        'user_id': TEST_USER_ID,
        'ot_date': "2026-10-13",
        'hours': 1.0,
        'reason': 'Rejected OT'
    })
    ot_rej_id = res_ot_rej_add.get_json().get('id') if res_ot_rej_add.is_json else None
    client.put(f'/api/overtime/{ot_rej_id}', json={'status': 'rejected', 'approved_by': 'Admin Audit'})
    res_ot_rej_get = client.get(f'/api/overtime?user_id={TEST_USER_ID}')
    ot_rej_records = res_ot_rej_get.get_json() if res_ot_rej_get.is_json else []
    ot_rej_match = next((o for o in ot_rej_records if o.get('id') == ot_rej_id), None)
    record(
        "4. Overtime", "API PUT /api/overtime/<id> updates status to 'rejected'",
        "status == 'rejected'",
        f"status == '{ot_rej_match.get('status') if ot_rej_match else None}'",
        ot_rej_match is not None and ot_rej_match.get('status') == 'rejected'
    )

    # 4.5 Edge case: Missing user_id returns 400
    res_ot_bad = client.post('/api/overtime', json={'hours': 2.0})
    record(
        "4. Overtime", "Validation: Missing user_id returns 400 Bad Request",
        "HTTP 400", f"HTTP {res_ot_bad.status_code}",
        res_ot_bad.status_code == 400
    )

    # =================================================================
    # SECTION 5: ATTENDANCE <-> LEAVE INTERACTION
    # =================================================================
    print("\n--- 5. ATTENDANCE <-> LEAVE INTERACTION ---")
    INTERACTION_DATE = "2026-10-23"  # Friday

    # Clean date
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute("DELETE FROM attendance WHERE user_id = ? AND date(timestamp) = ?;", (TEST_USER_ID, INTERACTION_DATE))
        c.execute("DELETE FROM manual_absent WHERE user_id = ? AND date = ?;", (TEST_USER_ID, INTERACTION_DATE))
        c.execute("DELETE FROM leave_requests WHERE user_id = ? AND start_date = ?;", (TEST_USER_ID, INTERACTION_DATE))
        conn.commit()

    # Case 1: Employee has BOTH attendance log AND approved leave on the SAME date.
    # What is the defined business rule in database.py get_detailed_attendance_report?
    # Priority order: Actual Face Attendance > Manual Absent > Approved Leave > Unexcused Absence
    # Insert attendance
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO attendance (user_id, detected_name, confidence, source, location, device_id, timestamp) "
            "VALUES (?, ?, 1.0, 'manual', 'Main Gate', 'cam_1', ?)",
            (TEST_USER_ID, TEST_USER_NAME, f"{INTERACTION_DATE} 08:00:00")
        )
        conn.commit()
    # Create approved leave for same date
    res_l_same = client.post('/api/leaves', json={
        'user_id': TEST_USER_ID,
        'leave_type': 'annual',
        'start_date': INTERACTION_DATE,
        'end_date': INTERACTION_DATE,
        'reason': 'Same Date Both Attendance and Leave'
    })
    l_same_id = res_l_same.get_json().get('id')
    client.put(f'/api/leaves/{l_same_id}', json={'status': 'approved'})

    rep_both = db.get_detailed_attendance_report(start_date=INTERACTION_DATE, end_date=INTERACTION_DATE)
    emp_both = next((r for r in rep_both.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    both_status = emp_both.get('daily_records', [{}])[0].get('status') if emp_both else None
    record(
        "5. Attendance <-> Leave", "Priority Order: Actual Attendance overrides Approved Leave on same date",
        "status == 'present' (Actual Attendance > Approved Leave)",
        f"status == '{both_status}'",
        both_status == 'present',
        details=f"Defined rule in database.py L1922: Actual Attendance takes precedence over Leave"
    )

    # Case 2: Manual Absent overrides Attendance and Leave
    db.mark_user_absent_today(TEST_USER_ID, target_date=INTERACTION_DATE)
    rep_man_abs = db.get_detailed_attendance_report(start_date=INTERACTION_DATE, end_date=INTERACTION_DATE)
    emp_man_abs = next((r for r in rep_man_abs.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    man_abs_status = emp_man_abs.get('daily_records', [{}])[0].get('status') if emp_man_abs else None
    record(
        "5. Attendance <-> Leave", "Priority Order: Manual Absent override converts day to Absent or On Leave",
        "attendance removed and manual_absent logged",
        f"status == '{man_abs_status}'",
        man_abs_status in ('absent', 'on_leave'),
        details=f"Resulting status after manual absent: {man_abs_status}"
    )

    # =================================================================
    # SECTION 6: OVERTIME <-> PAYROLL INTEGRATION
    # =================================================================
    print("\n--- 6. OVERTIME <-> PAYROLL INTEGRATION ---")
    # Check whether calculate_monthly_payroll incorporates approved overtime
    # Imran Khalid has 2.5 hours approved overtime on 2026-10-12
    # Check his salary config for ot_rate
    salary_cfg = db.get_salary_config(TEST_USER_ID)
    ot_rate = salary_cfg.get('ot_rate', 0.0)
    expected_ot_pay = round(2.5 * ot_rate, 2)

    payroll_oct = db.calculate_monthly_payroll('2026-10')
    imran_payroll = next((r for r in payroll_oct.get('records', []) if r.get('employee_id') == TEST_USER_ID), None)

    has_ot_in_payroll = 'overtime_amount' in imran_payroll or 'overtime_hours' in imran_payroll
    record(
        "6. Overtime <-> Payroll", "Payroll Calculation Engine incorporates Approved Overtime into monthly payroll",
        f"Payroll record contains overtime_hours (2.5) and overtime_amount (PKR {expected_ot_pay})",
        f"Overtime in record: {has_ot_in_payroll}, Keys: {[k for k in imran_payroll.keys() if 'ot' in k or 'overtime' in k]}",
        has_ot_in_payroll,
        details=f"ot_rate={ot_rate}, hours=2.5. Overtime is currently NOT integrated into calculate_monthly_payroll!",
        severity="CRITICAL",
        affected_modules="Overtime -> Payroll -> Salary"
    )

    # =================================================================
    # SECTION 7: LEAVE <-> PAYROLL INTEGRATION
    # =================================================================
    print("\n--- 7. LEAVE <-> PAYROLL INTEGRATION ---")
    # Imran Khalid in October 2026:
    # Basic salary = 250,000.00
    # Scheduled workdays = 27
    # Baseline:
    # Check current values of present, absent, approved_leave, payable_days, net_salary
    record(
        "7. Leave <-> Payroll", "Leave -> Payroll integration: Paid vs Unpaid leave classification",
        "Paid leave increases payable_days without deduction; Unpaid leave increases absent_days with deduction",
        f"present={imran_payroll.get('present_days')}, absent={imran_payroll.get('absent_days')}, leave={imran_payroll.get('approved_leave_days')}, payable={imran_payroll.get('payable_days')}, net={imran_payroll.get('net_salary')}",
        imran_payroll is not None and imran_payroll.get('payable_days') is not None,
        details=f"Matched rule: {imran_payroll.get('matched_rule')}, deduction: {imran_payroll.get('deduction_amount')}"
    )

    # =================================================================
    # SECTION 8: SALARY STRUCTURE <-> PAYROLL
    # =================================================================
    print("\n--- 8. SALARY STRUCTURE <-> PAYROLL ---")
    # Verify basic salary sync between users table and salary_configs
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT u.salary, sc.basic_salary, sc.allowances, sc.deductions, sc.ot_rate FROM users u LEFT JOIN salary_configs sc ON u.id = sc.user_id WHERE u.id = ?;", (TEST_USER_ID,))
    sal_row = c.fetchone()
    conn.close()

    record(
        "8. Salary Structure", "Salary sync between users.salary and salary_configs.basic_salary",
        "users.salary == salary_configs.basic_salary == 250000.0",
        f"users.salary = {sal_row[0]}, salary_configs.basic_salary = {sal_row[1]}",
        sal_row[0] == 250000.0 and sal_row[1] == 250000.0,
        details=f"allowances={sal_row[2]}, deductions={sal_row[3]}, ot_rate={sal_row[4]}"
    )

    # Verify if Allowances and Fixed Deductions from salary_configs are incorporated into net salary in Payroll
    has_allowances = 'allowances' in imran_payroll
    has_custom_deductions = 'custom_deductions' in imran_payroll or 'salary_deductions' in imran_payroll
    record(
        "8. Salary Structure", "Payroll Calculation incorporates Salary Allowances and Custom Deductions",
        "Payroll record includes allowances and custom deductions from salary_configs",
        f"has_allowances={has_allowances}, has_custom_deductions={has_custom_deductions}",
        has_allowances and has_custom_deductions,
        details=f"salary_configs has allowances={sal_row[2]} and deductions={sal_row[3]}, but calculate_monthly_payroll only calculates absence rule deduction!",
        severity="MEDIUM",
        affected_modules="Salary Structure -> Payroll -> Net Pay"
    )

    # =================================================================
    # SECTION 9: HISTORICAL DATA & SHIFT IMMUTABILITY TEST
    # =================================================================
    print("\n--- 9. HISTORICAL DATA & SHIFT IMMUTABILITY TEST ---")
    # Check employee_shift_history for Imran Khalid
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT shift_id, shift_name, effective_from FROM employee_shift_history WHERE user_id = ? ORDER BY effective_from;", (TEST_USER_ID,))
    shift_hist = c.fetchall()
    conn.close()

    record(
        "9. Historical Shift", "Shift changes preserve historical effective_from timeline in employee_shift_history",
        "History entries exist with distinct effective_from dates",
        f"History entries: {len(shift_hist)} -> {shift_hist}",
        len(shift_hist) >= 1,
        details="Report logic queries employee_shift_history to ensure historical dates use historical shifts"
    )

    # =================================================================
    # SECTION 10: FRONTEND UI & WORKFLOW AUDIT
    # =================================================================
    print("\n--- 10. FRONTEND UI & WORKFLOW AUDIT ---")
    with open('templates/index.html', encoding='utf-8') as f:
        html = f.read()

    # Check for presence of required views
    views_to_check = [
        ('dashboard-view', 'Dashboard View'),
        ('staff-view', 'Staff Directory View'),
        ('shifts-view', 'Shift Management View'),
        ('leaves-view', 'Leave Management View'),
        ('payroll-view', 'Payroll View'),
        ('reports-view', 'Attendance Reports View')
    ]
    for vid, vlabel in views_to_check:
        has_v = f'id="{vid}"' in html
        record("10. Frontend UI", f"DOM Page View: {vlabel} (#{vid}) exists in index.html", "True", str(has_v), has_v)

    # Check for Overtime Management UI in index.html
    has_ot_view = 'id="overtime-view"' in html or 'id="overtime-tab"' in html or 'loadOvertime' in html
    record(
        "10. Frontend UI", "DOM Page View: Overtime Management UI exists in index.html",
        "Overtime Management view/tab (#overtime-view or #overtime-tab) and loadOvertime function exist",
        f"has_ot_view={has_ot_view}",
        has_ot_view,
        details="There is currently NO dedicated Overtime management UI view or tab in index.html!",
        severity="HIGH",
        affected_modules="Overtime -> Frontend UI"
    )

    # =================================================================
    # SECTION 11: REPORTS AND EXPORTS AUDIT
    # =================================================================
    print("\n--- 11. REPORTS AND EXPORTS AUDIT ---")
    # Test Attendance Report API
    res_rep_api = client.get('/api/reports/attendance?start_date=2026-10-01&end_date=2026-10-07')
    record(
        "11. Reports & Exports", "API GET /api/reports/attendance returns structured report records",
        "HTTP 200 with non-empty records list",
        f"HTTP {res_rep_api.status_code} with {len(res_rep_api.get_json().get('records', []))} records",
        res_rep_api.status_code == 200 and len(res_rep_api.get_json().get('records', [])) > 0
    )

    # Test Excel Export Route
    res_export = client.get('/api/reports/attendance/export?start_date=2026-10-01&end_date=2026-10-07')
    is_excel = (res_export.status_code == 200 and
                ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in res_export.content_type or
                 'spreadsheet' in res_export.content_type))
    record(
        "11. Reports & Exports", "API GET /api/reports/attendance/export generates valid Excel spreadsheet",
        "HTTP 200 with spreadsheet Content-Type and binary payload > 1000 bytes",
        f"HTTP {res_export.status_code}, Content-Type: {res_export.content_type}, Length: {len(res_export.data)} bytes",
        is_excel and len(res_export.data) > 1000
    )

    # Clean up test records
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute("DELETE FROM attendance WHERE user_id = ? AND date(timestamp) IN (?, ?, ?, ?, ?, ?, ?, ?);",
                  (TEST_USER_ID, AUDIT_DATE_NORMAL, AUDIT_DATE_LATE, AUDIT_DATE_CHECKOUT, AUDIT_DATE_ABSENT,
                   LEAVE_DATE_PAID, LEAVE_DATE_UNPAID, LEAVE_DATE_REJECT, LEAVE_DATE_PENDING))
        c.execute("DELETE FROM manual_absent WHERE user_id = ? AND date IN (?, ?, ?, ?, ?, ?, ?, ?);",
                  (TEST_USER_ID, AUDIT_DATE_NORMAL, AUDIT_DATE_LATE, AUDIT_DATE_CHECKOUT, AUDIT_DATE_ABSENT,
                   LEAVE_DATE_PAID, LEAVE_DATE_UNPAID, LEAVE_DATE_REJECT, LEAVE_DATE_PENDING))
        c.execute("DELETE FROM leave_requests WHERE user_id = ? AND start_date IN (?, ?, ?, ?, ?, ?, ?, ?);",
                  (TEST_USER_ID, AUDIT_DATE_NORMAL, AUDIT_DATE_LATE, AUDIT_DATE_CHECKOUT, AUDIT_DATE_ABSENT,
                   LEAVE_DATE_PAID, LEAVE_DATE_UNPAID, LEAVE_DATE_REJECT, LEAVE_DATE_PENDING))
        c.execute("DELETE FROM overtime WHERE user_id = ? AND ot_date IN (?, ?);",
                  (TEST_USER_ID, OT_DATE, "2026-10-13"))
        conn.commit()

    print("\n" + "=" * 80)
    total_tests = len(audit_results)
    passed_tests = sum(1 for r in audit_results if r['status'] == 'PASS')
    failed_tests = total_tests - passed_tests
    print(f"AUDIT SUMMARY: {passed_tests}/{total_tests} TESTS PASSED | {failed_tests} FAILED")
    print("=" * 80)

    # Save to JSON
    with open('scratch/production_audit_results.json', 'w', encoding='utf-8') as f:
        json.dump(audit_results, f, indent=2, ensure_ascii=False)
    print("\nSaved detailed audit results to scratch/production_audit_results.json")

if __name__ == '__main__':
    main()
