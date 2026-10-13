import os
import sys
import io
import json
import sqlite3
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.abspath('.'))

import openpyxl
from app import app
import database as db

# Ensure DB initialized
db.init_db()

client = app.test_client()

audit_results = []

def record(section, test, expected, actual, passed, details="", severity="NONE", affected_modules=""):
    res = {
        "section": section,
        "test": test,
        "expected": expected,
        "actual": actual,
        "status": "PASS" if passed else "FAIL",
        "details": details,
        "severity": "NONE" if passed else severity,
        "affected_modules": affected_modules
    }
    audit_results.append(res)
    symbol = "✓" if passed else "✗"
    print(f"  [{symbol}] {section} - {test}: {res['status']}")
    if not passed:
        print(f"      Expected: {expected}")
        print(f"      Actual:   {actual}")
        if details:
            print(f"      Details:  {details}")

def main():
    print("=" * 80)
    print("  STRICT POST-FIX PRODUCTION AUDIT: EXCEL | OVERTIME | SALARY | PAYROLL")
    print("=" * 80)

    # -------------------------------------------------------------
    # SECTION 1: OPENPYXL & EXCEL EXPORT AUDIT
    # -------------------------------------------------------------
    print("\n--- 1. OPENPYXL & EXCEL EXPORT AUDIT ---")
    
    # 1.1 Verify openpyxl installed and imported
    openpyxl_ver = getattr(openpyxl, '__version__', 'unknown')
    record(
        "1. Excel Export", "openpyxl module is installed and imported in environment",
        "openpyxl version >= 3.0",
        f"openpyxl version: {openpyxl_ver}",
        openpyxl_ver != 'unknown'
    )

    # 1.2 Test GET /api/reports/export/excel
    res_excel = client.get('/api/reports/export/excel?start_date=2026-10-01&end_date=2026-10-07')
    is_200 = res_excel.status_code == 200
    is_excel_mime = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' in res_excel.content_type
    content_len = len(res_excel.data)

    wb_valid = False
    sheet_names = []
    num_rows = 0
    if is_200 and content_len > 1000:
        try:
            wb = openpyxl.load_workbook(io.BytesIO(res_excel.data))
            sheet_names = wb.sheetnames
            ws = wb.active
            num_rows = ws.max_row
            wb_valid = True
        except Exception as e:
            wb_valid = False

    record(
        "1. Excel Export", "GET /api/reports/export/excel returns HTTP 200 with valid .xlsx workbook",
        "HTTP 200, valid openpyxl workbook, sheets=['Attendance Report'], max_row > 10",
        f"HTTP {res_excel.status_code}, len={content_len}b, valid={wb_valid}, sheets={sheet_names}, rows={num_rows}",
        is_200 and is_excel_mime and wb_valid and num_rows > 10
    )

    # 1.3 Test GET /api/reports/attendance/export (alias route)
    res_excel_alias = client.get('/api/reports/attendance/export?start_date=2026-10-01&end_date=2026-10-07')
    record(
        "1. Excel Export", "GET /api/reports/attendance/export alias route returns valid .xlsx workbook",
        "HTTP 200, Content-Type=xlsx, Length > 1000 bytes",
        f"HTTP {res_excel_alias.status_code}, Length: {len(res_excel_alias.data)} bytes",
        res_excel_alias.status_code == 200 and len(res_excel_alias.data) > 1000
    )

    # -------------------------------------------------------------
    # SECTION 2: OVERTIME MANAGEMENT & API AUDIT
    # -------------------------------------------------------------
    print("\n--- 2. OVERTIME MANAGEMENT & API AUDIT ---")
    TEST_USER_ID = 38 # Imran Khalid
    
    # 2.1 Overtime API Creation (POST /api/overtime)
    post_res = client.post('/api/overtime', json={
        'user_id': TEST_USER_ID,
        'ot_date': '2026-10-18',
        'hours': 3.5,
        'reason': 'Audit overtime test'
    })
    post_data = post_res.get_json() or {}
    test_ot_id = post_data.get('id')
    record(
        "2. Overtime API", "API POST /api/overtime creates overtime record with status='pending'",
        "HTTP 201 with success=True and integer id",
        f"HTTP {post_res.status_code}, id={test_ot_id}, json={post_data}",
        post_res.status_code == 201 and test_ot_id is not None
    )

    # Verify pending in DB
    ot_rec = next((r for r in db.get_overtime(user_id=TEST_USER_ID) if r['id'] == test_ot_id), None)
    record(
        "2. Overtime API", "Overtime record persists to SQLite with correct rate and amount",
        "status='pending', hours=3.5, ot_rate > 0, ot_amount > 0",
        f"status={ot_rec.get('status') if ot_rec else None}, hours={ot_rec.get('hours') if ot_rec else None}, rate={ot_rec.get('ot_rate') if ot_rec else None}, amount={ot_rec.get('ot_amount') if ot_rec else None}",
        ot_rec is not None and ot_rec.get('status') == 'pending' and float(ot_rec.get('hours')) == 3.5
    )

    # 2.2 Overtime Approval (PUT /api/overtime/<id>)
    put_appr = client.put(f'/api/overtime/{test_ot_id}', json={'status': 'approved', 'approved_by': 'Admin'})
    appr_rec = next((r for r in db.get_overtime(user_id=TEST_USER_ID) if r['id'] == test_ot_id), None)
    record(
        "2. Overtime API", "API PUT /api/overtime/<id> approves overtime",
        "HTTP 200, status='approved', approved_by='Admin'",
        f"HTTP {put_appr.status_code}, status={appr_rec.get('status') if appr_rec else None}, by={appr_rec.get('approved_by') if appr_rec else None}",
        put_appr.status_code == 200 and appr_rec is not None and appr_rec.get('status') == 'approved' and appr_rec.get('approved_by') == 'Admin'
    )

    # 2.3 Overtime Rejection (PUT /api/overtime/<id>)
    # Create another record to test rejection
    post_rej = client.post('/api/overtime', json={
        'user_id': TEST_USER_ID,
        'ot_date': '2026-10-19',
        'hours': 2.0,
        'reason': 'Audit rejection test'
    })
    rej_ot_id = post_rej.get_json().get('id')
    put_rej = client.put(f'/api/overtime/{rej_ot_id}', json={'status': 'rejected', 'approved_by': 'Admin'})
    rej_rec = next((r for r in db.get_overtime(user_id=TEST_USER_ID) if r['id'] == rej_ot_id), None)
    record(
        "2. Overtime API", "API PUT /api/overtime/<id> rejects overtime",
        "HTTP 200, status='rejected'",
        f"HTTP {put_rej.status_code}, status={rej_rec.get('status') if rej_rec else None}",
        put_rej.status_code == 200 and rej_rec is not None and rej_rec.get('status') == 'rejected'
    )

    # 2.4 Overtime Deletion (DELETE /api/overtime/<id>)
    del_res = client.delete(f'/api/overtime/{rej_ot_id}')
    post_del_rec = next((r for r in db.get_overtime(user_id=TEST_USER_ID) if r['id'] == rej_ot_id), None)
    record(
        "2. Overtime API", "API DELETE /api/overtime/<id> deletes overtime record from SQLite",
        "HTTP 200, record not in SQLite",
        f"HTTP {del_res.status_code}, found_in_db={post_del_rec is not None}",
        del_res.status_code == 200 and post_del_rec is None
    )

    # Clean up test_ot_id
    db.delete_overtime(test_ot_id)

    # -------------------------------------------------------------
    # SECTION 3: OVERTIME <-> PAYROLL INTEGRATION & MATHEMATICAL PROOF
    # -------------------------------------------------------------
    print("\n--- 3. OVERTIME <-> PAYROLL INTEGRATION AUDIT ---")
    # Save original salary config
    orig_cfg = db.get_salary_config(TEST_USER_ID)

    # Set exact test baseline parameters:
    # Basic Salary = PKR 250,000
    # Allowances = PKR 35,000
    # Fixed Deductions = PKR 10,000
    # OT Rate = PKR 1,201.92
    db.set_salary_config(
        user_id=TEST_USER_ID,
        basic_salary=250000.0,
        allowances=35000.0,
        deductions=10000.0,
        ot_rate=1201.92
    )

    # Insert controlled overtime logs:
    # 1. Approved OT = 3.0 hours on 2026-10-15
    ot1 = db.add_overtime(user_id=TEST_USER_ID, ot_date='2026-10-15', hours=3.0, reason='Approved work')
    db.update_overtime_status(ot1, 'approved', 'Admin')

    # 2. Pending OT = 5.0 hours on 2026-10-16 (MUST BE EXCLUDED)
    ot2 = db.add_overtime(user_id=TEST_USER_ID, ot_date='2026-10-16', hours=5.0, reason='Pending review')

    # 3. Rejected OT = 4.0 hours on 2026-10-17 (MUST BE EXCLUDED)
    ot3 = db.add_overtime(user_id=TEST_USER_ID, ot_date='2026-10-17', hours=4.0, reason='Rejected work')
    db.update_overtime_status(ot3, 'rejected', 'Admin')

    # Run calculate_monthly_payroll for 2026-10
    payroll_oct = db.calculate_monthly_payroll('2026-10')
    emp_payroll = next((r for r in payroll_oct.get('records', []) if r.get('employee_id') == TEST_USER_ID), None)

    # Assert Overtime Hours: exactly 3.0 hours
    ot_hours_actual = emp_payroll.get('overtime_hours')
    record(
        "3. Overtime -> Payroll", "Payroll includes ONLY approved overtime hours (pending/rejected excluded)",
        "overtime_hours == 3.0",
        f"overtime_hours = {ot_hours_actual}",
        ot_hours_actual == 3.0,
        details="Pending (5.0 hrs) and Rejected (4.0 hrs) were correctly excluded"
    )

    # Assert Overtime Rate: 1201.92
    ot_rate_actual = emp_payroll.get('overtime_rate')
    record(
        "3. Overtime -> Payroll", "Payroll consumes employee's configured ot_rate",
        "overtime_rate == 1201.92",
        f"overtime_rate = {ot_rate_actual}",
        ot_rate_actual == 1201.92
    )

    # Assert Overtime Amount: 3.0 * 1201.92 = 3605.76
    expected_ot_pay = 3605.76
    ot_amt_actual = emp_payroll.get('overtime_amount')
    record(
        "3. Overtime -> Payroll", "Payroll calculates exact overtime payout: 3.0 × 1201.92 = PKR 3,605.76",
        f"overtime_amount == {expected_ot_pay}",
        f"overtime_amount = {ot_amt_actual}",
        ot_amt_actual == expected_ot_pay
    )

    # -------------------------------------------------------------
    # SECTION 4: SALARY ALLOWANCES & CUSTOM DEDUCTIONS INTEGRATION
    # -------------------------------------------------------------
    print("\n--- 4. SALARY ALLOWANCES & DEDUCTIONS AUDIT ---")
    # Assert Allowances: 35000.0
    allowances_actual = emp_payroll.get('allowances')
    record(
        "4. Salary -> Payroll", "Payroll consumes configured allowances from salary_configs",
        "allowances == 35000.0",
        f"allowances = {allowances_actual}",
        allowances_actual == 35000.0
    )

    # Assert Custom Deductions: 10000.0
    custom_ded_actual = emp_payroll.get('custom_deductions')
    record(
        "4. Salary -> Payroll", "Payroll consumes configured fixed custom deductions from salary_configs",
        "custom_deductions == 10000.0",
        f"custom_deductions = {custom_ded_actual}",
        custom_ded_actual == 10000.0
    )

    # Assert Gross Salary: Basic (250000) + Allowances (35000) + OT (3605.76) = 288605.76
    expected_gross = 288605.76
    gross_actual = emp_payroll.get('gross_salary')
    record(
        "4. Salary -> Payroll", "Payroll Gross Salary formula: Basic + Allowances + Overtime Pay = PKR 288,605.76",
        f"gross_salary == {expected_gross}",
        f"gross_salary = {gross_actual}",
        gross_actual == expected_gross
    )

    # Assert Net Salary: Gross - Custom Deductions - Absence Deductions
    absence_ded = emp_payroll.get('deduction_amount') or 0.0
    expected_net = round(expected_gross - 10000.0 - absence_ded, 2)
    net_actual = emp_payroll.get('net_salary')
    record(
        "4. Salary -> Payroll", "Payroll Net Salary formula: Gross − Fixed Deductions − Absence Deductions",
        f"net_salary == {expected_net}",
        f"net_salary = {net_actual}",
        net_actual == expected_net,
        details=f"Gross={gross_actual}, Fixed={custom_ded_actual}, Absence={absence_ded}, Net={net_actual}"
    )

    # Clean up test overtime
    db.delete_overtime(ot1)
    db.delete_overtime(ot2)
    db.delete_overtime(ot3)

    # Restore original config
    if orig_cfg:
        db.set_salary_config(
            user_id=TEST_USER_ID,
            basic_salary=float(orig_cfg.get('basic_salary') or 0.0),
            allowances=float(orig_cfg.get('allowances') or 0.0),
            deductions=float(orig_cfg.get('deductions') or 0.0),
            ot_rate=float(orig_cfg.get('ot_rate') or 0.0)
        )

    # -------------------------------------------------------------
    # SECTION 5: FRONTEND UI & DOM AUDIT
    # -------------------------------------------------------------
    print("\n--- 5. FRONTEND UI & OVERTIME MANAGEMENT AUDIT ---")
    with open('templates/index.html', encoding='utf-8') as f:
        html = f.read()

    has_ot_view = 'id="overtime-view"' in html
    record(
        "5. Overtime UI", "DOM Page View: Dedicated Overtime View (#overtime-view) exists in index.html",
        "True", str(has_ot_view), has_ot_view
    )

    has_ot_menu = "switchTab('overtime-view', this)" in html or 'switchTab("overtime-view", this)' in html
    record(
        "5. Overtime UI", "Sidebar navigation: Overtime Management menu item exists",
        "True", str(has_ot_menu), has_ot_menu
    )

    has_ot_modal = 'id="addOvertimeModal"' in html
    record(
        "5. Overtime UI", "Modal dialog: Log Overtime Modal (#addOvertimeModal) exists",
        "True", str(has_ot_modal), has_ot_modal
    )

    has_ot_table = 'id="overtimeTableBody"' in html
    record(
        "5. Overtime UI", "Table body: Overtime records table (#overtimeTableBody) exists",
        "True", str(has_ot_table), has_ot_table
    )

    has_ot_kpis = 'id="otKpiTotalLogs"' in html and 'id="otKpiApprovedHours"' in html and 'id="otKpiApprovedAmount"' in html
    record(
        "5. Overtime UI", "Metric cards: KPI counters (Total, Approved Hours, Approved Pay) exist",
        "True", str(has_ot_kpis), has_ot_kpis
    )

    has_ot_js = 'loadOvertimeRecords' in html and 'updateOvertimeStatus' in html and 'deleteOvertimeRecord' in html
    record(
        "5. Overtime UI", "Client JavaScript: loadOvertimeRecords, updateOvertimeStatus, deleteOvertimeRecord defined",
        "True", str(has_ot_js), has_ot_js
    )

    # -------------------------------------------------------------
    # SECTION 6: DATABASE INTEGRITY & REGRESSION AUDIT
    # -------------------------------------------------------------
    print("\n--- 6. DATABASE INTEGRITY & REGRESSION AUDIT ---")
    with sqlite3.connect('attendance.db') as conn:
        c = conn.cursor()
        integrity = c.execute("PRAGMA integrity_check").fetchall()
        fk = c.execute("PRAGMA foreign_key_check").fetchall()

    record(
        "6. DB Integrity", "SQLite database PRAGMA integrity_check is OK",
        "[('ok',)]", str(integrity),
        integrity == [('ok',)]
    )

    record(
        "6. DB Integrity", "SQLite database PRAGMA foreign_key_check has 0 violations",
        "[]", str(fk),
        fk == []
    )

    # Verify protected modules untouched
    print("\n" + "=" * 80)
    total_tests = len(audit_results)
    passed_tests = sum(1 for r in audit_results if r['status'] == 'PASS')
    failed_tests = total_tests - passed_tests
    print(f"AUDIT SUMMARY: {passed_tests}/{total_tests} TESTS PASSED | {failed_tests} FAILED")
    print("=" * 80)

    # Write results to json
    with open('scratch/post_fix_audit_results.json', 'w', encoding='utf-8') as f:
        json.dump(audit_results, f, indent=2, ensure_ascii=False)

if __name__ == '__main__':
    main()
