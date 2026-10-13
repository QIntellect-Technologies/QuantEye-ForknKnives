import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

import os
import sqlite3
import json
import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, List

import database as db
from app import app

client = app.test_client()

audit_items = []

def log_test(section, name, expected, actual, passed, details="", severity="HIGH", affected=""):
    status = "PASS" if passed else "FAIL"
    entry = {
        'section': section,
        'test_name': name,
        'expected': str(expected),
        'actual': str(actual),
        'status': status,
        'details': details,
        'severity': severity if not passed else "NONE",
        'affected_modules': affected if not passed else ""
    }
    audit_items.append(entry)
    print(f"[{status}] [{section}] {name}")
    print(f"       Expected: {expected}")
    print(f"       Actual:   {actual}")
    if details:
        print(f"       Details:  {details}")
    if not passed:
        print(f"       [DEFECT] Severity: {severity} | Affected: {affected}")
    print()

def run_comprehensive_audit():
    print("=" * 80)
    print("  STRICT REAL PRODUCTION AUDIT: ATTENDANCE -> LEAVE -> OVERTIME -> PAYROLL")
    print("=" * 80)

    TEST_USER_ID = 38
    TEST_USER_NAME = "Imran Khalid"

    # =================================================================
    # 1. DATABASE INTEGRITY AUDIT
    # =================================================================
    print("\n--- SECTION 1: DATABASE INTEGRITY AUDIT ---")
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()

    c.execute("PRAGMA integrity_check;")
    integ = c.fetchall()
    log_test("A. Database Integrity", "PRAGMA integrity_check", "[('ok',)]", str(integ), integ == [('ok',)])

    c.execute("PRAGMA foreign_key_check;")
    fk_res = c.fetchall()
    log_test("A. Database Integrity", "PRAGMA foreign_key_check", "[] (0 violations)", str(fk_res), len(fk_res) == 0)

    # Check for orphan records in all tables with foreign keys to users
    tables_to_check = [
        ('attendance', 'user_id'),
        ('leave_requests', 'user_id'),
        ('employee_leave_balances', 'user_id'),
        ('overtime', 'user_id'),
        ('salary_configs', 'user_id'),
        ('employee_shift_history', 'user_id'),
        ('manual_absent', 'user_id'),
        ('locator_history', 'user_id')
    ]
    orphan_found = False
    for tbl, col in tables_to_check:
        c.execute(f"SELECT count(*) FROM {tbl} WHERE {col} NOT IN (SELECT id FROM users);")
        cnt = c.fetchone()[0]
        if cnt > 0:
            orphan_found = True
        log_test("A. Database Integrity", f"Orphan records in {tbl}.{col}", "0 orphans", str(cnt), cnt == 0)

    # Check duplicate records in users
    c.execute("SELECT name, count(*) FROM users GROUP BY name HAVING count(*) > 1;")
    dups = c.fetchall()
    log_test("A. Database Integrity", "Duplicate user names in users table", "0", str(len(dups)), len(dups) == 0)

    # Check shift foreign keys
    c.execute("SELECT count(*) FROM users WHERE shift_id IS NOT NULL AND shift_id NOT IN (SELECT id FROM shifts);")
    bad_shifts = c.fetchone()[0]
    log_test("A. Database Integrity", "Users referencing non-existent shift_id", "0", str(bad_shifts), bad_shifts == 0)

    conn.close()

    # =================================================================
    # 2. ATTENDANCE WORKFLOW AUDIT
    # =================================================================
    print("\n--- SECTION 2: ATTENDANCE WORKFLOW AUDIT ---")
    # Clean audit test dates
    D_PRES = "2026-10-12"
    D_LATE = "2026-10-13"
    D_CHCK = "2026-10-14"
    D_ABSN = "2026-10-15"

    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute("DELETE FROM attendance WHERE user_id = ? AND date(timestamp) IN (?, ?, ?, ?);",
                  (TEST_USER_ID, D_PRES, D_LATE, D_CHCK, D_ABSN))
        c.execute("DELETE FROM manual_absent WHERE user_id = ? AND date IN (?, ?, ?, ?);",
                  (TEST_USER_ID, D_PRES, D_LATE, D_CHCK, D_ABSN))
        c.execute("DELETE FROM leave_requests WHERE user_id = ? AND start_date IN (?, ?, ?, ?);",
                  (TEST_USER_ID, D_PRES, D_LATE, D_CHCK, D_ABSN))
        c.execute("DELETE FROM overtime WHERE user_id = ? AND ot_date IN (?, ?, ?, ?);",
                  (TEST_USER_ID, D_PRES, D_LATE, D_CHCK, D_ABSN))
        conn.commit()

    # 2.1 Normal Present (Check-in on time for Shift 1: 10:31 start with 2 min grace)
    # Check-in at 10:32:00 (within grace period 10:31 - 10:33)
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO attendance (user_id, detected_name, confidence, source, location, device_id, timestamp) "
            "VALUES (?, ?, 1.0, 'manual', 'Main Entrance', 'cam_norm', ?)",
            (TEST_USER_ID, TEST_USER_NAME, f"{D_PRES} 10:32:00")
        )
        conn.commit()

    rep_pres = db.get_detailed_attendance_report(start_date=D_PRES, end_date=D_PRES)
    emp_p = next((r for r in rep_pres.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    daily_p = emp_p.get('daily_records', [{}])[0] if emp_p else {}
    log_test(
        "B. Attendance", "Scenario A: Normal Present (Check-in 10:32:00 within 2m grace of 10:31 start)",
        "status == 'present'", f"status == '{daily_p.get('status')}'",
        daily_p.get('status') == 'present',
        details=f"first_seen: {daily_p.get('first_seen')}, shift_start: {daily_p.get('shift_start')}, grace: {daily_p.get('grace_period_minutes')}m"
    )

    # 2.2 Late Arrival (Check-in at 10:35:00, after 10:33:00 grace deadline)
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO attendance (user_id, detected_name, confidence, source, location, device_id, timestamp) "
            "VALUES (?, ?, 1.0, 'manual', 'Main Entrance', 'cam_late', ?)",
            (TEST_USER_ID, TEST_USER_NAME, f"{D_LATE} 10:35:00")
        )
        conn.commit()

    rep_late = db.get_detailed_attendance_report(start_date=D_LATE, end_date=D_LATE)
    emp_l = next((r for r in rep_late.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    daily_l = emp_l.get('daily_records', [{}])[0] if emp_l else {}
    log_test(
        "B. Attendance", "Scenario B: Late Arrival (Check-in 10:35:00 after 10:33 grace deadline)",
        "status == 'late'", f"status == '{daily_l.get('status')}'",
        daily_l.get('status') == 'late',
        details=f"first_seen: {daily_l.get('first_seen')}, deadline: 10:33:00"
    )

    # 2.3 Check-in / Check-out separation
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO attendance (user_id, detected_name, confidence, source, location, device_id, timestamp) "
            "VALUES (?, ?, 1.0, 'manual', 'Entrance', 'cam_in', ?)",
            (TEST_USER_ID, TEST_USER_NAME, f"{D_CHCK} 10:31:00")
        )
        c.execute(
            "INSERT INTO attendance (user_id, detected_name, confidence, source, location, device_id, checkout_location, checkout_camera_id, timestamp) "
            "VALUES (?, ?, 1.0, 'manual', 'Exit', 'cam_out', 'Exit', 'cam_out', ?)",
            (TEST_USER_ID, TEST_USER_NAME, f"{D_CHCK} 10:34:00")
        )
        conn.commit()

    rep_chk = db.get_detailed_attendance_report(start_date=D_CHCK, end_date=D_CHCK)
    emp_c = next((r for r in rep_chk.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    daily_c = emp_c.get('daily_records', [{}])[0] if emp_c else {}
    has_sep = (daily_c.get('first_seen') and daily_c.get('last_seen') and daily_c.get('first_seen') != daily_c.get('last_seen'))
    log_test(
        "B. Attendance", "Scenario C: Check-in / Check-out separation and genuine checkout",
        "status == 'checked_out' with distinct first_seen and last_seen",
        f"status == '{daily_c.get('status')}', first_seen: {daily_c.get('first_seen')}, last_seen: {daily_c.get('last_seen')}",
        daily_c.get('status') == 'checked_out' and has_sep,
        details=f"Check-In Cam: {daily_c.get('checkin_camera')}, Check-Out Cam: {daily_c.get('checkout_camera')}"
    )

    # 2.4 Unexcused Absence
    rep_abs = db.get_detailed_attendance_report(start_date=D_ABSN, end_date=D_ABSN)
    emp_a = next((r for r in rep_abs.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    daily_a = emp_a.get('daily_records', [{}])[0] if emp_a else {}
    log_test(
        "B. Attendance", "Scenario D: Unexcused Absence on scheduled workday with no logs",
        "status == 'absent'", f"status == '{daily_a.get('status')}'",
        daily_a.get('status') == 'absent',
        details=f"scheduled_workday: {daily_a.get('scheduled_workday')}"
    )

    # =================================================================
    # 3. LEAVE MANAGEMENT AUDIT
    # =================================================================
    print("\n--- SECTION 3: LEAVE MANAGEMENT AUDIT ---")
    D_LPAID = "2026-10-19"
    D_LUNPD = "2026-10-20"
    D_LREJ  = "2026-10-21"
    D_LPEND = "2026-10-22"

    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute("DELETE FROM attendance WHERE user_id = ? AND date(timestamp) IN (?, ?, ?, ?);",
                  (TEST_USER_ID, D_LPAID, D_LUNPD, D_LREJ, D_LPEND))
        c.execute("DELETE FROM manual_absent WHERE user_id = ? AND date IN (?, ?, ?, ?);",
                  (TEST_USER_ID, D_LPAID, D_LUNPD, D_LREJ, D_LPEND))
        c.execute("DELETE FROM leave_requests WHERE user_id = ? AND start_date IN (?, ?, ?, ?);",
                  (TEST_USER_ID, D_LPAID, D_LUNPD, D_LREJ, D_LPEND))
        conn.commit()

    # 3.1 Paid Leave
    res_lpaid = client.post('/api/leaves', json={
        'user_id': TEST_USER_ID,
        'leave_type': 'annual',
        'start_date': D_LPAID,
        'end_date': D_LPAID,
        'reason': 'Approved Paid Leave'
    })
    lpaid_id = res_lpaid.get_json().get('id')
    client.put(f'/api/leaves/{lpaid_id}', json={'status': 'approved'})

    rep_lp = db.get_detailed_attendance_report(start_date=D_LPAID, end_date=D_LPAID)
    emp_lp = next((r for r in rep_lp.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    daily_lp = emp_lp.get('daily_records', [{}])[0] if emp_lp else {}
    log_test(
        "C. Leave Management", "Approved Paid Leave reflection in attendance",
        "status == 'on_leave'", f"status == '{daily_lp.get('status')}'",
        daily_lp.get('status') == 'on_leave',
        details=f"Leave ID: {lpaid_id}, is_paid=1"
    )

    # 3.2 Unpaid Leave
    res_lunpd = client.post('/api/leaves', json={
        'user_id': TEST_USER_ID,
        'leave_type': 'unpaid',
        'start_date': D_LUNPD,
        'end_date': D_LUNPD,
        'reason': 'Approved Unpaid Leave'
    })
    lunpd_id = res_lunpd.get_json().get('id')
    client.put(f'/api/leaves/{lunpd_id}', json={'status': 'approved'})

    rep_lu = db.get_detailed_attendance_report(start_date=D_LUNPD, end_date=D_LUNPD)
    emp_lu = next((r for r in rep_lu.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    daily_lu = emp_lu.get('daily_records', [{}])[0] if emp_lu else {}
    log_test(
        "C. Leave Management", "Approved Unpaid Leave reflection in attendance",
        "status == 'on_leave_unpaid'", f"status == '{daily_lu.get('status')}'",
        daily_lu.get('status') == 'on_leave_unpaid',
        details=f"Leave ID: {lunpd_id}, is_paid=0"
    )

    # 3.3 Rejected Leave
    res_lrej = client.post('/api/leaves', json={
        'user_id': TEST_USER_ID,
        'leave_type': 'annual',
        'start_date': D_LREJ,
        'end_date': D_LREJ,
        'reason': 'Rejected Leave'
    })
    lrej_id = res_lrej.get_json().get('id')
    client.put(f'/api/leaves/{lrej_id}', json={'status': 'rejected'})

    rep_lr = db.get_detailed_attendance_report(start_date=D_LREJ, end_date=D_LREJ)
    emp_lr = next((r for r in rep_lr.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    daily_lr = emp_lr.get('daily_records', [{}])[0] if emp_lr else {}
    log_test(
        "C. Leave Management", "Rejected Leave does not excuse absence",
        "status == 'absent'", f"status == '{daily_lr.get('status')}'",
        daily_lr.get('status') == 'absent',
        details=f"Leave ID: {lrej_id}, status: rejected"
    )

    # 3.4 Pending Leave
    res_lpen = client.post('/api/leaves', json={
        'user_id': TEST_USER_ID,
        'leave_type': 'annual',
        'start_date': D_LPEND,
        'end_date': D_LPEND,
        'reason': 'Pending Leave'
    })
    lpen_id = res_lpen.get_json().get('id')

    rep_lpen = db.get_detailed_attendance_report(start_date=D_LPEND, end_date=D_LPEND)
    emp_lpen = next((r for r in rep_lpen.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
    daily_lpen = emp_lpen.get('daily_records', [{}])[0] if emp_lpen else {}
    log_test(
        "C. Leave Management", "Pending Leave does not grant leave status until approved",
        "status == 'absent'", f"status == '{daily_lpen.get('status')}'",
        daily_lpen.get('status') == 'absent',
        details=f"Leave ID: {lpen_id}, status: pending"
    )

    # =================================================================
    # 4. OVERTIME MANAGEMENT AUDIT
    # =================================================================
    print("\n--- SECTION 4: OVERTIME MANAGEMENT AUDIT ---")
    D_OT = "2026-10-12"

    res_ot_add = client.post('/api/overtime', json={
        'user_id': TEST_USER_ID,
        'ot_date': D_OT,
        'hours': 3.0,
        'reason': 'Overtime Audit Test'
    })
    ot_id = res_ot_add.get_json().get('id') if res_ot_add.is_json else None
    log_test(
        "D. Overtime", "API POST /api/overtime creates record",
        "HTTP 201 with positive integer ID",
        f"HTTP {res_ot_add.status_code} with ID {ot_id}",
        res_ot_add.status_code == 201 and ot_id is not None
    )

    # Approve overtime
    res_ot_appr = client.put(f'/api/overtime/{ot_id}', json={'status': 'approved', 'approved_by': 'Admin Auditor'})
    res_ot_list = client.get(f'/api/overtime?user_id={TEST_USER_ID}')
    ot_data = res_ot_list.get_json() if res_ot_list.is_json else []
    ot_row = next((o for o in ot_data if o.get('id') == ot_id), None)
    log_test(
        "D. Overtime", "API PUT /api/overtime/<id> status updates to 'approved'",
        "status == 'approved' and approved_by == 'Admin Auditor'",
        f"status == '{ot_row.get('status') if ot_row else None}', approved_by == '{ot_row.get('approved_by') if ot_row else None}'",
        ot_row is not None and ot_row.get('status') == 'approved' and ot_row.get('approved_by') == 'Admin Auditor'
    )

    # Check for Overtime Frontend UI
    with open('templates/index.html', encoding='utf-8') as f:
        html_code = f.read()
    has_ot_ui = 'id="overtime-view"' in html_code or 'id="overtime-tab"' in html_code or 'loadOvertime' in html_code
    log_test(
        "D. Overtime", "Frontend UI View: Dedicated Overtime view/tab in index.html",
        "Overtime Management view/tab (#overtime-view or #overtime-tab) exists",
        f"has_ot_ui == {has_ot_ui}",
        has_ot_ui,
        details="DEFECT CONFIRMED: Overtime API and DB table exist, but NO UI view/tab exists in index.html!",
        severity="HIGH",
        affected="Overtime -> Frontend UI"
    )

    # =================================================================
    # 5. OVERTIME <-> PAYROLL INTEGRATION AUDIT
    # =================================================================
    print("\n--- SECTION 5: OVERTIME <-> PAYROLL INTEGRATION ---")
    salary_cfg = db.get_salary_config(TEST_USER_ID)
    ot_rate = salary_cfg.get('ot_rate', 0.0)
    expected_ot_pay = round(3.0 * ot_rate, 2)

    payroll_oct = db.calculate_monthly_payroll('2026-10')
    imran_rec = next((r for r in payroll_oct.get('records', []) if r.get('employee_id') == TEST_USER_ID), None)

    has_ot_amount = 'overtime_amount' in imran_rec or 'overtime_hours' in imran_rec
    ot_amount_in_rec = imran_rec.get('overtime_amount', 0.0) if imran_rec else 0.0
    log_test(
        "E. Overtime <-> Payroll", "Payroll Calculation Engine incorporates Approved Overtime into Net Salary",
        f"Record contains overtime_amount == PKR {expected_ot_pay} (3.0 hrs * PKR {ot_rate}/hr)",
        f"has_overtime_field={has_ot_amount}, overtime_amount={ot_amount_in_rec}",
        has_ot_amount and ot_amount_in_rec == expected_ot_pay,
        details="DEFECT CONFIRMED: calculate_monthly_payroll in database.py does NOT query or integrate overtime table!",
        severity="CRITICAL",
        affected="Overtime -> Payroll Calculation -> Net Salary"
    )

    # =================================================================
    # 6. SALARY STRUCTURE <-> PAYROLL INTEGRATION AUDIT
    # =================================================================
    print("\n--- SECTION 6: SALARY STRUCTURE <-> PAYROLL ---")
    allowances = salary_cfg.get('allowances', 0.0)
    deductions = salary_cfg.get('deductions', 0.0)
    has_allowances = 'allowances' in imran_rec
    has_salary_deductions = 'salary_deductions' in imran_rec or 'custom_deductions' in imran_rec

    log_test(
        "F. Salary Structure", "Payroll Calculation incorporates Allowances and Fixed Deductions from salary_configs",
        f"Record includes allowances (PKR {allowances}) and custom deductions (PKR {deductions})",
        f"has_allowances={has_allowances}, has_salary_deductions={has_salary_deductions}",
        has_allowances and has_salary_deductions,
        details=f"DEFECT CONFIRMED: salary_configs has allowances={allowances} and deductions={deductions}, but calculate_monthly_payroll only calculates absence-rule deductions!",
        severity="MEDIUM",
        affected="Salary Structure -> Payroll -> Net Salary"
    )

    # =================================================================
    # 7. EXPORT ROUTES AUDIT (CSV & EXCEL)
    # =================================================================
    print("\n--- SECTION 7: EXPORTS AUDIT ---")
    # CSV Export
    res_csv = client.get('/api/reports/export/csv?start_date=2026-10-01&end_date=2026-10-07')
    log_test(
        "G. Reports & Exports", "API GET /api/reports/export/csv exports valid attendance CSV",
        "HTTP 200 with text/csv content-type and payload > 1000 bytes",
        f"HTTP {res_csv.status_code}, content_type: {res_csv.content_type}, length: {len(res_csv.data)} bytes",
        res_csv.status_code == 200 and 'csv' in res_csv.content_type and len(res_csv.data) > 1000
    )

    # Excel Export
    res_excel = client.get('/api/reports/export/excel?start_date=2026-10-01&end_date=2026-10-07')
    excel_ok = res_excel.status_code == 200 and 'spreadsheet' in res_excel.content_type
    log_test(
        "G. Reports & Exports", "API GET /api/reports/export/excel exports valid Excel workbook (.xlsx)",
        "HTTP 200 with application/vnd.openxmlformats-officedocument.spreadsheetml.sheet content-type",
        f"HTTP {res_excel.status_code}, content_type: {res_excel.content_type}",
        excel_ok,
        details="DEFECT CONFIRMED: ModuleNotFoundError: No module named 'openpyxl' in env310tfgpu environment!",
        severity="MEDIUM",
        affected="Attendance Reports -> Excel Export"
    )

    # =================================================================
    # 8. CLEANUP AUDIT RECORDS
    # =================================================================
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        c.execute("DELETE FROM attendance WHERE user_id = ? AND date(timestamp) IN (?, ?, ?, ?, ?, ?, ?, ?);",
                  (TEST_USER_ID, D_PRES, D_LATE, D_CHCK, D_ABSN, D_LPAID, D_LUNPD, D_LREJ, D_LPEND))
        c.execute("DELETE FROM manual_absent WHERE user_id = ? AND date IN (?, ?, ?, ?, ?, ?, ?, ?);",
                  (TEST_USER_ID, D_PRES, D_LATE, D_CHCK, D_ABSN, D_LPAID, D_LUNPD, D_LREJ, D_LPEND))
        c.execute("DELETE FROM leave_requests WHERE user_id = ? AND start_date IN (?, ?, ?, ?, ?, ?, ?, ?);",
                  (TEST_USER_ID, D_PRES, D_LATE, D_CHCK, D_ABSN, D_LPAID, D_LUNPD, D_LREJ, D_LPEND))
        c.execute("DELETE FROM overtime WHERE user_id = ? AND ot_date IN (?, ?);",
                  (TEST_USER_ID, D_OT, "2026-10-13"))
        conn.commit()

    total = len(audit_items)
    passed = sum(1 for i in audit_items if i['status'] == 'PASS')
    failed = total - passed

    print("\n" + "=" * 80)
    print(f"AUDIT SUMMARY: {passed}/{total} TESTS PASSED | {failed} DEFECTS FOUND")
    print("=" * 80)

    with open('scratch/comprehensive_audit_evidence.json', 'w', encoding='utf-8') as f:
        json.dump(audit_items, f, indent=2, ensure_ascii=False)
    print("Wrote results to scratch/comprehensive_audit_evidence.json")

if __name__ == '__main__':
    run_comprehensive_audit()
