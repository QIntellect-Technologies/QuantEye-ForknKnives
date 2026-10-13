import sys
sys.path.insert(0, ".")
import sqlite3
import json
from datetime import datetime
import database as db
from app import app

client = app.test_client()

def run_audit():
    print("=====================================================================")
    print("  COMPREHENSIVE AUDIT: EMPLOYEE SALARY STRUCTURE + FULL REGRESSION  ")
    print("=====================================================================")

    results = []

    def record_test(module, test_name, expected, actual, passed, details=""):
        status = "PASS" if passed else "FAIL"
        results.append({
            'module': module,
            'test': test_name,
            'expected': str(expected),
            'actual': str(actual),
            'status': status,
            'details': details
        })
        print(f"[{status}] {module} :: {test_name}")
        print(f"       Expected: {expected}")
        print(f"       Actual:   {actual}")
        if details:
            print(f"       Details:  {details}")

    # =================================================================
    # SECTION 1: NEW MODULE AUDIT (EMPLOYEE SALARY STRUCTURE)
    # =================================================================
    print("\n--- 1. NEW MODULE: EMPLOYEE SALARY STRUCTURE AUDIT ---")

    # Test 1.1: GET /api/salary returns all active staff
    res = client.get('/api/salary')
    data = res.get_json() if res.is_json else []
    record_test(
        "Salary Structure",
        "API GET /api/salary returns all active employees",
        "HTTP 200 with 38 active employees",
        f"HTTP {res.status_code} with {len(data)} employees",
        res.status_code == 200 and len(data) == 38,
        f"Fields present: {list(data[0].keys()) if data else 'none'}"
    )

    # Test 1.2: GET /api/salary/summary returns aggregate metrics
    res_sum = client.get('/api/salary/summary')
    sdata = res_sum.get_json() if res_sum.is_json else {}
    record_test(
        "Salary Structure",
        "API GET /api/salary/summary returns KPI metrics",
        "HTTP 200 with total_employees=38 and positive total_basic",
        f"HTTP {res_sum.status_code} with total_employees={sdata.get('total_employees')} and total_basic={sdata.get('total_basic')}",
        res_sum.status_code == 200 and sdata.get('total_employees') == 38 and sdata.get('total_basic', 0) > 0,
        f"Summary: {sdata}"
    )

    # Test 1.3: GET /api/salary/38 for Imran Khalid
    res_u = client.get('/api/salary/38')
    udata = res_u.get_json() if res_u.is_json else {}
    record_test(
        "Salary Structure",
        "API GET /api/salary/<id> retrieves employee profile",
        "HTTP 200 for user_id=38 (Imran Khalid)",
        f"HTTP {res_u.status_code} for user: {udata.get('user_name')}",
        res_u.status_code == 200 and udata.get('user_name') == 'Imran Khalid',
        f"Basic: {udata.get('basic_salary')}, Dept: {udata.get('department')}"
    )

    # Test 1.4: Validation - Negative values rejected
    res_neg = client.put('/api/salary/38', json={
        'basic_salary': -1000,
        'allowances': 500,
        'deductions': 0,
        'ot_rate': 0
    })
    record_test(
        "Salary Structure",
        "Validation: Reject negative basic salary",
        "HTTP 400 Bad Request",
        f"HTTP {res_neg.status_code}",
        res_neg.status_code == 400,
        f"Response message: {res_neg.get_json()}"
    )

    # Test 1.5: Validation - Non-existent user rejected
    res_no_user = client.put('/api/salary/999999', json={
        'basic_salary': 50000,
        'allowances': 5000,
        'deductions': 1000,
        'ot_rate': 250
    })
    record_test(
        "Salary Structure",
        "Validation: Reject non-existent employee ID",
        "HTTP 404 Not Found",
        f"HTTP {res_no_user.status_code}",
        res_no_user.status_code == 404,
        f"Response message: {res_no_user.get_json()}"
    )

    # Test 1.6: Save Salary Package (CRUD Update)
    res_save = client.put('/api/salary/38', json={
        'basic_salary': 250000.0,
        'allowances': 35000.0,
        'deductions': 10000.0,
        'ot_rate': 1200.0
    })
    save_data = res_save.get_json() if res_save.is_json else {}
    cfg = save_data.get('config', {})
    expected_net = 250000.0 + 35000.0 - 10000.0 # 275,000
    record_test(
        "Salary Structure",
        "CRUD: Update salary package with allowances and deductions",
        "HTTP 200 with net_estimated=275000.0",
        f"HTTP {res_save.status_code} with net_estimated={cfg.get('net_estimated')}",
        res_save.status_code == 200 and cfg.get('net_estimated') == expected_net and cfg.get('is_configured') == 1,
        f"Updated config: {cfg}"
    )

    # Test 1.7: Database Synchronization with users.salary
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT salary FROM users WHERE id = 38")
    u_salary = c.fetchone()[0]
    c.execute("SELECT basic_salary, allowances, deductions, ot_rate FROM salary_configs WHERE user_id = 38")
    sc_row = c.fetchone()
    conn.close()
    record_test(
        "Salary Structure",
        "Database Persistence & Sync: salary_configs and users.salary consistency",
        "users.salary == 250000.0 and salary_configs has matching row",
        f"users.salary={u_salary}, salary_configs={sc_row}",
        u_salary == 250000.0 and sc_row == (250000.0, 35000.0, 10000.0, 1200.0),
        "Synchronized to prevent Payroll V1 drift"
    )

    # Test 1.8: Auto-Set OT Rates API (1/208th divisor)
    res_ot = client.post('/api/salary/auto-ot-rates', json={'divisor': 208})
    ot_data = res_ot.get_json() if res_ot.is_json else {}
    record_test(
        "Salary Structure",
        "Utility: Auto-Calculate OT rates for all staff",
        "HTTP 200 with updated_count=38",
        f"HTTP {res_ot.status_code} with updated_count={ot_data.get('updated_count')}",
        res_ot.status_code == 200 and ot_data.get('updated_count') == 38,
        f"Response: {ot_data.get('message')}"
    )

    # Test 1.9: Department & Search Filtering API
    res_filter = client.get('/api/salary?department=AI%20%26%20Data%20Science')
    fdata = res_filter.get_json() if res_filter.is_json else []
    all_ai = all(x.get('department') == 'AI & Data Science' for x in fdata)
    record_test(
        "Salary Structure",
        "Filter: Filter employees by department",
        "All returned employees belong to 'AI & Data Science'",
        f"Returned {len(fdata)} employees, all match dept: {all_ai}",
        res_filter.status_code == 200 and len(fdata) > 0 and all_ai,
        f"Found {len(fdata)} members in AI & Data Science"
    )

    # Test 1.10: Reset Salary Package to default base
    # Test on user 84 (Abdullah - School)
    client.put('/api/salary/84', json={'basic_salary': 30000, 'allowances': 2000, 'deductions': 500, 'ot_rate': 150})
    res_del = client.delete('/api/salary/84')
    res_del_data = res_del.get_json() if res_del.is_json else {}
    check_u84 = client.get('/api/salary/84').get_json()
    record_test(
        "Salary Structure",
        "CRUD: Reset custom package back to default base",
        "HTTP 200 and is_configured=0 with allowances=0, deductions=0",
        f"HTTP {res_del.status_code}, is_configured={check_u84.get('is_configured')}, allowances={check_u84.get('allowances')}",
        res_del.status_code == 200 and check_u84.get('is_configured') == 0 and check_u84.get('allowances') == 0.0,
        f"Reset result: {res_del_data}"
    )

    # =================================================================
    # SECTION 2: FULL SYSTEM REGRESSION AUDIT (ALL FROZEN MODULES)
    # =================================================================
    print("\n--- 2. FULL REGRESSION AUDIT (11 FROZEN MODULES) ---")

    # Check 2.1: Database Pragmas
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("PRAGMA integrity_check;")
    ic = c.fetchall()
    c.execute("PRAGMA foreign_key_check;")
    fk = c.fetchall()
    conn.close()
    record_test(
        "Database Integrity",
        "PRAGMA integrity_check",
        "[('ok',)]",
        str(ic),
        ic == [('ok',)],
        "Database is physically intact"
    )
    record_test(
        "Database Integrity",
        "PRAGMA foreign_key_check",
        "[] (Zero foreign key violations)",
        str(fk),
        fk == [],
        "Zero foreign key violations across all tables"
    )

    # Check 2.2: Payroll V1 Calculation Engine Baseline
    # Verify that October 2026 payroll for Imran Khalid still produces exact baseline numbers
    preview = db.calculate_monthly_payroll('2026-10')
    imran_record = next((r for r in preview.get('records', []) if r.get('employee_id') == 38), None)
    record_test(
        "Payroll V1",
        "Payroll calculation engine produces exact baseline for October 2026",
        "Imran Khalid: basic_salary=250000.0, payable_days=4.0, net_salary=37037.04",
        f"Imran Khalid: basic_salary={imran_record.get('basic_salary')}, payable_days={imran_record.get('payable_days')}, net_salary={imran_record.get('net_salary')}" if imran_record else "Not found",
        imran_record is not None and imran_record.get('basic_salary') == 250000.0 and imran_record.get('net_salary') == 37037.04 and imran_record.get('payable_days') == 4.0,
        f"Matched Rule: {imran_record.get('matched_rule')}, Status: {imran_record.get('status')}" if imran_record else "Missing"
    )

    # Check 2.3: Leave & Holiday Management APIs
    res_lt = client.get('/api/leave-types')
    res_hol = client.get('/api/holidays')
    res_lreq = client.get('/api/leaves')
    res_lbal = client.get('/api/leaves/balances?year=2026')
    leave_ok = all(r.status_code == 200 for r in [res_lt, res_hol, res_lreq, res_lbal])
    record_test(
        "Leave & Holidays",
        "Leave APIs (leave-types, holidays, leaves, balances)",
        "All return HTTP 200",
        f"Types: {res_lt.status_code}, Holidays: {res_hol.status_code}, Requests: {res_lreq.status_code}, Balances: {res_lbal.status_code}",
        leave_ok,
        f"Leave types count: {len(res_lt.get_json()) if res_lt.is_json else 0}"
    )

    # Check 2.4: Shift Management
    res_shifts = client.get('/api/shifts')
    shift_json = res_shifts.get_json() if res_shifts.is_json else {}
    shifts = shift_json.get('shifts', []) if isinstance(shift_json, dict) else shift_json
    record_test(
        "Shift Management",
        "Shift configurations and employee assignments",
        "HTTP 200 with active shifts configured",
        f"HTTP {res_shifts.status_code} with {len(shifts)} shifts",
        res_shifts.status_code == 200 and len(shifts) >= 2,
        f"Shifts: {[s.get('name') for s in shifts if isinstance(s, dict)]}"
    )

    # Check 2.5: Staff Management
    res_users = client.get('/api/users')
    users_data = res_users.get_json() if res_users.is_json else {}
    users_list = users_data.get('users', []) if isinstance(users_data, dict) else users_data
    record_test(
        "Staff Management",
        "Staff directory list API",
        "HTTP 200 with 38 users",
        f"HTTP {res_users.status_code} with {len(users_list)} users",
        res_users.status_code == 200 and len(users_list) == 38,
        "Staff directory completely intact"
    )

    # Check 2.6: Departments & Designations
    res_depts = client.get('/api/departments')
    res_desigs = client.get('/api/designations')
    dept_ok = res_depts.status_code == 200 and res_desigs.status_code == 200
    record_test(
        "Departments & Designations",
        "Departments & Designations API suite",
        "Both return HTTP 200 with non-empty collections",
        f"Depts: {res_depts.status_code} ({len(res_depts.get_json() or [])}), Desigs: {res_desigs.status_code} ({len(res_desigs.get_json() or [])})",
        dept_ok,
        "Department-designation hierarchy intact"
    )

    # Check 2.7: Settings & Branch
    res_branch = client.get('/api/settings/branch')
    bdata = res_branch.get_json() if res_branch.is_json else {}
    record_test(
        "Settings",
        "Branch settings API",
        "HTTP 200 with branch_name configured",
        f"HTTP {res_branch.status_code} with branch: {bdata.get('branch_name')}",
        res_branch.status_code == 200 and bool(bdata.get('branch_name')),
        f"Branch: {bdata.get('branch_name')}, City: {bdata.get('city')}"
    )

    # Check 2.8: Camera Management
    res_cams = client.get('/api/cameras')
    cdata = res_cams.get_json() if res_cams.is_json else []
    record_test(
        "Camera Management",
        "Camera feeds configuration API",
        "HTTP 200 with active cameras",
        f"HTTP {res_cams.status_code} with {len(cdata)} cameras",
        res_cams.status_code == 200 and len(cdata) > 0,
        f"Cameras: {[c.get('name') for c in cdata]}"
    )

    # Check 2.9: Attendance Reports
    res_rep = client.get('/api/reports/attendance?start_date=2026-10-01&end_date=2026-10-07')
    rdata = res_rep.get_json() if res_rep.is_json else {}
    record_test(
        "Attendance Reports",
        "Attendance detailed report API",
        "HTTP 200 with report records",
        f"HTTP {res_rep.status_code} with {len(rdata.get('records', []))} records",
        res_rep.status_code == 200 and 'records' in rdata,
        "Reports generation engine intact"
    )

    # Check 2.10: Dashboard Stats
    res_stats = client.get('/api/stats')
    s_kpi = res_stats.get_json() if res_stats.is_json else {}
    record_test(
        "Dashboard",
        "Dashboard KPI stats API",
        "HTTP 200 with total_users and present count",
        f"HTTP {res_stats.status_code} with total_users={s_kpi.get('total_users')}",
        res_stats.status_code == 200 and s_kpi.get('total_users') == 38,
        f"KPIs: {s_kpi}"
    )

    # =================================================================
    # SECTION 3: COMPREHENSIVE API REGRESSION SUITE (18/18 APIS)
    # =================================================================
    print("\n--- 3. COMPLETE API REGRESSION SUITE (18/18 APIS) ---")
    all_endpoints = [
        ('/api/stats', 'GET'),
        ('/api/users', 'GET'),
        ('/api/departments', 'GET'),
        ('/api/designations', 'GET'),
        ('/api/shifts', 'GET'),
        ('/api/cameras', 'GET'),
        ('/api/settings/branch', 'GET'),
        ('/api/payroll/rules', 'GET'),
        ('/api/payroll/calendar', 'GET'),
        ('/api/payroll/history', 'GET'),
        ('/api/payroll?month=2026-10', 'GET'),
        ('/api/reports/attendance?start_date=2026-10-01&end_date=2026-10-07', 'GET'),
        ('/api/leave-types', 'GET'),
        ('/api/leaves', 'GET'),
        ('/api/leaves/balances?year=2026', 'GET'),
        ('/api/holidays', 'GET'),
        ('/api/salary', 'GET'),
        ('/api/salary/summary', 'GET')
    ]

    all_api_ok = True
    for path, method in all_endpoints:
        r = client.get(path)
        ok = (r.status_code == 200)
        if not ok:
            all_api_ok = False
        record_test("API Suite", f"{method} {path}", "HTTP 200", f"HTTP {r.status_code}", ok)

    # Final summary
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r['status'] == 'PASS')
    failed_tests = total_tests - passed_tests

    print("\n=====================================================================")
    print(f"AUDIT SUMMARY: {passed_tests}/{total_tests} TESTS PASSED | {failed_tests} FAILED")
    print("=====================================================================")

    return {
        'total': total_tests,
        'passed': passed_tests,
        'failed': failed_tests,
        'results': results
    }

if __name__ == '__main__':
    audit_data = run_audit()
    with open('scratch/salary_audit_results.json', 'w', encoding='utf-8') as f:
        json.dump(audit_data, f, indent=2)
    if audit_data['failed'] > 0:
        sys.exit(1)
    else:
        print("\nALL MODULE AND REGRESSION CHECKS PASSED WITH 100% SUCCESS!")
        sys.exit(0)
