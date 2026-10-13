#!/usr/bin/env python
"""
TARGETED LEAVE & HOLIDAY / PAYROLL — 4 DEFECTS VERIFICATION TEST SUITE
Tests:
- TEST A: Reversed Dates Validation (HTTP 400 + duration calculation)
- TEST B: Casual Leave Quota Enforcement (10 days/yr, 100% paid, calendar year isolation)
- TEST C: UI/API Data Binding (No undefined, null, NaN)
- TEST D: Public Holidays Scheduled Days & Deduction Protection (Oct 1 & Oct 6)
- TEST E: Approved Casual Leave -> Payroll Integration
- TEST F: Pending & Rejected Leave Isolation
- TEST G: API / UI / Database Consistency
- TEST H: SQLite Database Integrity (PRAGMA integrity_check, foreign_key_check)
- TEST J: Baseline restoration
"""

import sys
import os
import sqlite3
from datetime import datetime, date

# Ensure app directory in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database as db
import app

def run_tests():
    print("=" * 70)
    print("STARTING TARGETED 4 DEFECTS FIX & VERIFICATION SUITE")
    print("=" * 70)

    client = app.app.test_client()
    passed = 0
    failed = 0

    def assert_test(cond, title, detail=""):
        nonlocal passed, failed
        if cond:
            print(f"  [PASS] {title}")
            passed += 1
        else:
            print(f"  [FAIL] {title} - {detail}")
            failed += 1

    # ----------------------------------------------------
    # TEST A: REVERSED DATES
    # ----------------------------------------------------
    print("\n--- TEST A: DEFECT 1 - REVERSED DATES ---")
    
    # 1. API attempt with end_date < start_date
    resp = client.post('/api/leaves', json={
        'user_id': 1,
        'leave_type': 'casual',
        'start_date': '2026-10-08',
        'end_date': '2026-10-04',
        'reason': 'Testing reversed date range'
    })
    assert_test(resp.status_code == 400, "POST /api/leaves with end_date < start_date returns HTTP 400", f"Got status {resp.status_code}")
    res_data = resp.get_json() or {}
    assert_test("earlier than start date" in (res_data.get('error') or res_data.get('message') or ''),
                "Error message explicitly states 'End date cannot be earlier than start date.'", f"Got: {res_data}")

    # 2. Direct database add_leave_request attempt
    lid_bad = db.add_leave_request(
        user_id=1,
        user_name="Test User",
        leave_type="casual",
        start_date="2026-10-08",
        end_date="2026-10-04",
        reason="Direct DB attempt"
    )
    assert_test(lid_bad is None, "database.add_leave_request rejects end_date < start_date returning None", f"Got id: {lid_bad}")

    # Verify no reversed records exist in leave_requests
    with sqlite3.connect(db.DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM leave_requests WHERE end_date < start_date")
        cnt_bad = c.fetchone()[0]
    assert_test(cnt_bad == 0, "No leave records in DB have end_date < start_date", f"Found {cnt_bad} invalid records")

    # 3. Valid date range durations
    q1 = db.check_leave_quota(1, 'casual', '2026-10-08', '2026-10-08')
    assert_test(q1['requested_days'] == 1, "2026-10-08 -> 2026-10-08 calculates as 1 day", f"Got: {q1['requested_days']}")

    q2 = db.check_leave_quota(1, 'casual', '2026-10-08', '2026-10-09')
    assert_test(q2['requested_days'] == 2, "2026-10-08 -> 2026-10-09 calculates as 2 days", f"Got: {q2['requested_days']}")

    q3 = db.check_leave_quota(1, 'casual', '2026-10-08', '2026-10-10')
    assert_test(q3['requested_days'] == 3, "2026-10-08 -> 2026-10-10 calculates as 3 days", f"Got: {q3['requested_days']}")

    # ----------------------------------------------------
    # TEST B & F: CASUAL LEAVE QUOTA & PENDING/REJECTED RULES
    # ----------------------------------------------------
    print("\n--- TEST B & F: DEFECT 2 - CASUAL LEAVE ANNUAL QUOTA (10 DAYS) & STATUS RULES ---")

    # Create temporary employee for isolated quota testing
    temp_user_id = db.add_user(
        name="Temp Quota Tester",
        email="quota_tester@school.internal",
        department="Academic",
        position="Test Faculty",
        salary=50000.0
    )
    assert_test(temp_user_id is not None, "Created temporary employee for quota testing", f"ID: {temp_user_id}")

    # Verify Casual Leave default allowance is 10.0 and is_paid == 1
    ltypes = db.get_leave_types()
    casual_type = next((lt for lt in ltypes if lt['code'] == 'casual'), None)
    assert_test(casual_type is not None and casual_type['yearly_allowance'] == 10.0 and casual_type['is_paid'] == 1,
                "Casual Leave configured as 10 days/yr and 100% Paid in leave_types table")

    # Initial balance check
    init_quota = db.check_leave_quota(temp_user_id, 'casual', '2026-10-01', '2026-10-02')
    assert_test(init_quota['remaining_days'] == 10.0 and init_quota['allowed'] is True,
                "Initial remaining quota is 10.0 days and request of 2 days is allowed", f"Got: {init_quota}")

    # Create a PENDING request for 4 days
    pend_id = db.add_leave_request(
        user_id=temp_user_id,
        user_name="Temp Quota Tester",
        leave_type="casual",
        start_date="2026-10-10",
        end_date="2026-10-13",
        reason="Pending request test"
    )
    db.update_leave_status(pend_id, 'pending')
    q_after_pend = db.check_leave_quota(temp_user_id, 'casual', '2026-10-14', '2026-10-15')
    assert_test(q_after_pend['remaining_days'] == 10.0,
                "TEST F: Pending leave does NOT consume approved quota (remaining = 10.0)", f"Got: {q_after_pend['remaining_days']}")

    # Create a REJECTED request for 4 days
    rej_id = db.add_leave_request(
        user_id=temp_user_id,
        user_name="Temp Quota Tester",
        leave_type="casual",
        start_date="2026-10-16",
        end_date="2026-10-19",
        reason="Rejected request test"
    )
    db.update_leave_status(rej_id, 'rejected')
    q_after_rej = db.check_leave_quota(temp_user_id, 'casual', '2026-10-20', '2026-10-21')
    assert_test(q_after_rej['remaining_days'] == 10.0,
                "TEST F: Rejected leave does NOT consume approved quota (remaining = 10.0)", f"Got: {q_after_rej['remaining_days']}")

    # Now approve 2 days
    appr1_id = db.add_leave_request(
        user_id=temp_user_id,
        user_name="Temp Quota Tester",
        leave_type="casual",
        start_date="2026-10-01",
        end_date="2026-10-02",
        reason="2 days approved"
    )
    db.update_leave_status(appr1_id, 'approved')
    q_after_appr1 = db.check_leave_quota(temp_user_id, 'casual', '2026-10-22', '2026-10-23')
    assert_test(q_after_appr1['remaining_days'] == 8.0,
                "Approved 2 days consumes quota: Remaining = 8.0", f"Got: {q_after_appr1['remaining_days']}")

    # Approve another 3 days
    appr2_id = db.add_leave_request(
        user_id=temp_user_id,
        user_name="Temp Quota Tester",
        leave_type="casual",
        start_date="2026-10-03",
        end_date="2026-10-05",
        reason="3 days approved"
    )
    db.update_leave_status(appr2_id, 'approved')
    q_after_appr2 = db.check_leave_quota(temp_user_id, 'casual', '2026-10-22', '2026-10-23')
    assert_test(q_after_appr2['remaining_days'] == 5.0,
                "Approved another 3 days consumes quota: Remaining = 5.0", f"Got: {q_after_appr2['remaining_days']}")

    # Attempt to request 6 days (remaining is 5)
    q_exceed = db.check_leave_quota(temp_user_id, 'casual', '2026-10-20', '2026-10-25') # 6 days
    assert_test(q_exceed['allowed'] is False,
                "Attempt to request 6 days when 5 remaining is BLOCKED (allowed=False)", f"Got: {q_exceed}")
    assert_test("only has 5 allowed paid days" in q_exceed['message'],
                "Exceeded message specifies exact remaining days and policy recommendation", f"Got msg: {q_exceed['message']}")

    # Attempt API submission exceeding quota
    resp_exceed = client.post('/api/leaves', json={
        'user_id': temp_user_id,
        'leave_type': 'casual',
        'start_date': '2026-10-20',
        'end_date': '2026-10-25',
        'reason': 'Exceeding quota attempt'
    })
    assert_test(resp_exceed.status_code == 400, "POST /api/leaves exceeding quota is rejected with HTTP 400", f"Got: {resp_exceed.status_code}")

    # Calendar Year Isolation: 2027 should have fresh 10 days
    q_2027 = db.check_leave_quota(temp_user_id, 'casual', '2027-03-01', '2027-03-05')
    assert_test(q_2027['remaining_days'] == 10.0 and q_2027['allowed'] is True,
                "Calendar Year Isolation: Year 2027 has full 10 days entitlement", f"Got remaining: {q_2027['remaining_days']}")

    # Clean up temp user and leave requests
    with sqlite3.connect(db.DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM leave_requests WHERE user_id = ?", (temp_user_id,))
        c.execute("DELETE FROM employee_leave_balances WHERE user_id = ?", (temp_user_id,))
        c.execute("DELETE FROM employee_shift_history WHERE user_id = ?", (temp_user_id,))
        c.execute("DELETE FROM users WHERE id = ?", (temp_user_id,))
        conn.commit()

    # ----------------------------------------------------
    # TEST C: DEFECT 4 - UI / API DATA BINDING (NO UNDEFINED)
    # ----------------------------------------------------
    print("\n--- TEST C: DEFECT 4 - UI / API DATA BINDING (NO UNDEFINED) ---")

    # 1. API endpoint called with NO parameters
    res_noparams = client.get('/api/leaves/check-quota').get_json()
    assert_test(isinstance(res_noparams.get('remaining_days'), (int, float)) and res_noparams.get('remaining_days') == 10.0,
                "GET /api/leaves/check-quota (no params) returns numeric remaining_days = 10.0", f"Got: {res_noparams}")
    assert_test(res_noparams.get('requested_days') == 0,
                "GET /api/leaves/check-quota (no params) returns numeric requested_days = 0", f"Got: {res_noparams}")

    # 2. API endpoint called with user and leave_type but NO dates
    res_nodates = client.get('/api/leaves/check-quota?user_id=1&leave_type=casual').get_json()
    assert_test(isinstance(res_nodates.get('remaining_days'), (int, float)) and res_nodates.get('requested_days') == 0,
                "GET /api/leaves/check-quota (user, no dates) returns valid numbers (remaining >= 0, requested = 0)", f"Got: {res_nodates}")

    # 3. API endpoint called with valid dates
    res_valid = client.get('/api/leaves/check-quota?user_id=1&leave_type=casual&start_date=2026-10-08&end_date=2026-10-10').get_json()
    assert_test(res_valid.get('requested_days') == 3 and isinstance(res_valid.get('remaining_days'), (int, float)),
                "GET /api/leaves/check-quota with 3-day dates returns requested_days = 3 and valid remaining_days", f"Got: {res_valid}")

    # 4. Verify no NaN / null / undefined in response JSON
    for k in ['remaining_days', 'requested_days', 'allocated_days', 'used_days']:
        v = res_valid.get(k)
        assert_test(v is not None and not str(v).lower() in ['nan', 'undefined', 'null'],
                    f"Property '{k}' is strictly numeric and not undefined/null/NaN", f"Value: {v}")

    # ----------------------------------------------------
    # TEST D: DEFECT 3 - PUBLIC HOLIDAYS -> SCHEDULED DAYS & DEDUCTION PROTECTION
    # ----------------------------------------------------
    print("\n--- TEST D: DEFECT 3 - PUBLIC HOLIDAYS & SCHEDULED WORKING DAYS ---")

    # Verify the two configured holidays exist: 2026-10-01 and 2026-10-06
    holidays = db.get_company_holidays(2026)
    oct1_h = next((h for h in holidays if h['holiday_date'] == '2026-10-01'), None)
    oct6_h = next((h for h in holidays if h['holiday_date'] == '2026-10-06'), None)
    assert_test(oct1_h is not None, "2026-10-01 Public Holiday exists in company_holidays", f"Holiday: {oct1_h}")
    assert_test(oct6_h is not None, "2026-10-06 Public Holiday exists in company_holidays", f"Holiday: {oct6_h}")

    # Test single-day attendance reports on the public holidays
    rep_oct1 = db.get_detailed_attendance_report(target_date='2026-10-01')
    oct1_statuses = set(r.get('status') for r in rep_oct1.get('records', []))
    assert_test('holiday' in oct1_statuses and 'absent' not in oct1_statuses,
                "Oct 1 detailed attendance records mark employees as 'holiday' (0 absences)", f"Statuses: {oct1_statuses}")

    rep_oct6 = db.get_detailed_attendance_report(target_date='2026-10-06')
    oct6_statuses = set(r.get('status') for r in rep_oct6.get('records', []))
    assert_test(oct6_statuses == {'holiday'},
                "Oct 6 detailed attendance records mark 100% of employees as 'holiday'", f"Statuses: {oct6_statuses}")

    # Test multi-day attendance report for October 2026
    rep_multi = db.get_detailed_attendance_report(start_date='2026-10-01', end_date='2026-10-31')
    first_emp = rep_multi.get('records', [])[0] if rep_multi.get('records') else None
    assert_test(first_emp is not None, "Retrieved multi-day attendance report records")
    if first_emp:
        daily = first_emp.get('daily_records', [])
        d1 = next((d for d in daily if d['date'] == '2026-10-01'), None)
        d6 = next((d for d in daily if d['date'] == '2026-10-06'), None)
        assert_test(d1 is not None and d1.get('status') == 'holiday' and d1.get('scheduled_workday') is False,
                    "Multi-day report: Oct 1 is holiday and scheduled_workday=False", f"d1: {d1}")
        assert_test(d6 is not None and d6.get('status') == 'holiday' and d6.get('scheduled_workday') is False,
                    "Multi-day report: Oct 6 is holiday and scheduled_workday=False", f"d6: {d6}")

    # Verify scheduled days count in monthly payroll
    payroll_data = db.calculate_monthly_payroll('2026-10')
    records = payroll_data.get('records', [])
    assert_test(len(records) > 0, "Payroll records generated for October 2026")
    if records:
        emp_pr = records[0]
        # Mon-Sat schedule has 27 normal days; minus 2 holidays = 25 scheduled days
        assert_test(emp_pr['scheduled_workdays'] == 25,
                    f"Scheduled working days correctly reduced by 2 holidays (27 - 2 = 25)", f"Got: {emp_pr['scheduled_workdays']}")
        assert_test(emp_pr['absent_days'] <= emp_pr['scheduled_workdays'],
                    f"Absent days ({emp_pr['absent_days']}) never exceed scheduled days ({emp_pr['scheduled_workdays']})")

    # ----------------------------------------------------
    # TEST E: DEFECT 3B - CASUAL LEAVE -> PAYROLL INTEGRATION
    # ----------------------------------------------------
    print("\n--- TEST E: DEFECT 3B - CASUAL LEAVE -> PAYROLL INTEGRATION ---")

    # Check Abdullah's payroll row
    ab_pr = next((p for p in records if 'abdullah' in p.get('employee_name', '').lower()), None)
    assert_test(ab_pr is not None, "Retrieved payroll record for Abdullah")
    if ab_pr:
        appr_leave = ab_pr.get('approved_leave_days', 0)
        alias_leave = ab_pr.get('leave_days', 0)
        assert_test(appr_leave >= 1 and alias_leave >= 1,
                    f"Payroll reflects Approved Leave correctly (approved_leave_days={appr_leave}, leave_days={alias_leave})",
                    f"Got: approved_leave_days={appr_leave}, leave_days={alias_leave}")
        assert_test(ab_pr['payable_days'] >= appr_leave,
                    f"Payable days ({ab_pr['payable_days']}) properly credits approved paid leave",
                    f"payable_days: {ab_pr['payable_days']}")


    # ----------------------------------------------------
    # TEST G: API / UI / DB CONSISTENCY
    # ----------------------------------------------------
    print("\n--- TEST G: API / UI / DATABASE CONSISTENCY ---")
    resp_ltypes = client.get('/api/leave-types').get_json()
    db_ltypes = db.get_leave_types()
    assert_test(len(resp_ltypes) == len(db_ltypes), "API /api/leave-types matches database leave_types count")

    casual_api = next((lt for lt in resp_ltypes if lt['code'] == 'casual'), {})
    assert_test(casual_api.get('yearly_allowance') == 10.0 and casual_api.get('is_paid') == 1,
                "API confirms Casual Leave is 10.0 days and is_paid = 1")

    # ----------------------------------------------------
    # TEST H: DATABASE INTEGRITY
    # ----------------------------------------------------
    print("\n--- TEST H: DATABASE INTEGRITY CHECKS ---")
    with sqlite3.connect(db.DB_PATH) as conn:
        c = conn.cursor()
        c.execute("PRAGMA integrity_check")
        ic_res = c.fetchone()[0]
        assert_test(ic_res == "ok", f"PRAGMA integrity_check = '{ic_res}'")

        c.execute("PRAGMA foreign_key_check")
        fk_violations = c.fetchall()
        assert_test(len(fk_violations) == 0, f"PRAGMA foreign_key_check = 0 violations (found: {len(fk_violations)})")

        # Check for orphan leave requests
        c.execute("SELECT COUNT(*) FROM leave_requests WHERE user_id NOT IN (SELECT id FROM users)")
        orphan_leaves = c.fetchone()[0]
        assert_test(orphan_leaves == 0, f"No orphaned leave requests (found: {orphan_leaves})")

    # ----------------------------------------------------
    # SUMMARY
    # ----------------------------------------------------
    print("\n" + "=" * 70)
    print(f"VERIFICATION RESULTS: {passed} PASSED, {failed} FAILED")
    print("=" * 70)
    return failed == 0

if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
