import sys
import os
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
import database as db

def run_dashboard_audit():
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

    print("=" * 80)
    print("MODULE 5 AUDIT — PRE-AUDIT BASELINE SNAPSHOT")
    for t, c in pre_counts.items():
        print(f"  {t:25s}: {c}")
    print("=" * 80)

    # =========================================================================
    # SECTION 1: ARCHITECTURE & DOM INSPECTION
    # =========================================================================
    print("\n--- 1. ARCHITECTURE & DOM INSPECTION ---")
    with open('templates/index.html', 'r', encoding='utf-8') as f:
        html_content = f.read()

    # DSH-01: Verify Dashboard container & KPI elements in DOM
    has_dashboard_view = 'id="dashboard-view"' in html_content
    has_val_enrolled = 'id="valEnrolled"' in html_content
    has_val_attendance = 'id="valAttendance"' in html_content
    has_val_records = 'id="valRecords"' in html_content
    has_logs_container = 'id="logsContainer"' in html_content
    has_sync_status = 'id="logSyncStatus"' in html_content

    dom_kpi_ok = (has_dashboard_view and has_val_enrolled and has_val_attendance and 
                  has_val_records and has_logs_container and has_sync_status)
    record(
        'DSH-01',
        'Verify #dashboard-view structure and KPI card IDs in index.html',
        'All elements (dashboard-view, valEnrolled, valAttendance, valRecords, logsContainer, logSyncStatus) exist',
        f'dashboard_view={has_dashboard_view}, enrolled={has_val_enrolled}, att={has_val_attendance}, rec={has_val_records}, logs={has_logs_container}, sync={has_sync_status}',
        dom_kpi_ok,
        "DOM elements for dashboard metrics verified"
    )

    # DSH-02: Check for missing ticker elements referenced in loadStats (DEFECT DETECTION)
    # DSH-02: Check safe null-guards for ticker elements in loadStats()
    has_ticker_guards = (
        'if (tickerTotalStudents)' in html_content and
        'if (tickerTotalPresent)' in html_content and
        'if (tickerTotalAbsent)' in html_content
    )
    record(
        'DSH-02',
        'Verify safe null-checks for tickerTotal* elements in loadStats()',
        'Safe null-guards exist for tickerTotalStudents, tickerTotalPresent, tickerTotalAbsent',
        f'guards_present={has_ticker_guards}',
        has_ticker_guards,
        'Safe null-checks in loadStats() eliminate TypeError when elements are absent from DOM'
    )

    # DSH-03: Verify Live Reports & Analytics View (#reports-view)
    has_reports_view = 'id="reports-view"' in html_content
    has_report_stats = ('id="mainStatTotal"' in html_content and 
                        'id="mainStatPresent"' in html_content and 
                        'id="mainStatAbsent"' in html_content and 
                        'id="mainStatLate"' in html_content)
    has_dept_grid = 'id="mainDeptGrid"' in html_content
    has_date_presets = ('id="mBtnToday"' in html_content and 
                        'id="mBtnYesterday"' in html_content and 
                        'id="mBtnLast7"' in html_content and 
                        'id="mBtnThisWeek"' in html_content and 
                        'id="mBtnThisMonth"' in html_content)
    reports_dom_ok = has_reports_view and has_report_stats and has_dept_grid and has_date_presets
    record(
        'DSH-03',
        'Verify #reports-view analytics container, KPI cards, dept grid, date presets',
        'All elements exist in DOM',
        f'reports_view={has_reports_view}, stats={has_report_stats}, grid={has_dept_grid}, presets={has_date_presets}',
        reports_dom_ok,
        "Live attendance reports and analytics DOM elements verified"
    )

    # =========================================================================
    # SECTION 2: DATABASE -> DASHBOARD RECONCILIATION (/api/stats)
    # =========================================================================
    print("\n--- 2. DATABASE -> DASHBOARD RECONCILIATION (/api/stats) ---")

    # Independent SQLite queries
    sql_total_users = cur.execute("SELECT COUNT(*) FROM users WHERE active = 1").fetchone()[0]
    sql_total_logs = cur.execute("SELECT COUNT(*) FROM attendance").fetchone()[0]
    sql_today_logs = cur.execute("SELECT COUNT(*) FROM attendance WHERE date(timestamp) = date('now', 'localtime')").fetchone()[0]
    sql_unique_today = cur.execute("""
        SELECT COUNT(DISTINCT user_id) FROM attendance 
        WHERE date(timestamp) = date('now', 'localtime')
        AND user_id NOT IN (SELECT user_id FROM manual_absent WHERE date = date('now', 'localtime'))
    """).fetchone()[0]
    sql_absent_today = max(sql_total_users - sql_unique_today, 0)
    sql_avg_conf = cur.execute("SELECT AVG(confidence) FROM attendance").fetchone()[0] or 0.0

    # API call
    res_stats = client.get('/api/stats')
    data_stats = res_stats.get_json() or {}

    stats_match = (
        res_stats.status_code == 200 and
        data_stats.get('total_users') == sql_total_users and
        data_stats.get('total_logs') == sql_total_logs and
        data_stats.get('today_attendance') == sql_today_logs and
        data_stats.get('present_users') == sql_unique_today and
        data_stats.get('absent_users') == sql_absent_today and
        abs(float(data_stats.get('avg_confidence', 0)) - float(sql_avg_conf)) < 0.0001
    )
    record(
        'DSH-04',
        'Reconcile GET /api/stats KPI metrics directly against SQLite',
        f'total_users={sql_total_users}, total_logs={sql_total_logs}, today_att={sql_today_logs}, present={sql_unique_today}, absent={sql_absent_today}',
        f'HTTP {res_stats.status_code}: total_users={data_stats.get("total_users")}, total_logs={data_stats.get("total_logs")}, today_att={data_stats.get("today_attendance")}, present={data_stats.get("present_users")}, absent={data_stats.get("absent_users")}',
        stats_match,
        f"API stats response: {data_stats}"
    )

    # =========================================================================
    # SECTION 3: RECENT ATTENDANCE LOGS RECONCILIATION (/api/attendance/logs)
    # =========================================================================
    print("\n--- 3. RECENT ATTENDANCE LOGS RECONCILIATION ---")

    # Query SQLite for top 15 logs
    cur.execute("""
        SELECT a.id, u.name, a.confidence, a.timestamp, a.source, a.location, a.device_id
        FROM attendance a
        JOIN users u ON a.user_id = u.id
        ORDER BY a.timestamp DESC LIMIT 15
    """)
    sql_logs = [dict(r) for r in cur.fetchall()]

    res_logs = client.get('/api/attendance/logs?limit=15')
    data_logs = res_logs.get_json() or {}
    api_logs = data_logs.get('logs', [])

    logs_reconciled = (
        res_stats.status_code == 200 and
        len(api_logs) == len(sql_logs) and
        all(api_logs[i]['id'] == sql_logs[i]['id'] and 
            api_logs[i]['name'] == sql_logs[i]['name'] 
            for i in range(len(sql_logs)))
    )
    record(
        'DSH-05',
        'Reconcile GET /api/attendance/logs (Top 15 Recent Activity) against SQLite',
        f'count={len(sql_logs)}, latest_id={sql_logs[0]["id"] if sql_logs else None}',
        f'count={len(api_logs)}, latest_id={api_logs[0]["id"] if api_logs else None}',
        logs_reconciled,
        f"Recent logs verified: first 3 IDs = {[l['id'] for l in api_logs[:3]]}"
    )

    # DSH-06: Verify chronological sort order (strict timestamp DESC)
    is_sorted_desc = True
    for i in range(len(api_logs) - 1):
        if api_logs[i]['timestamp'] < api_logs[i+1]['timestamp']:
            is_sorted_desc = False
            break
    record(
        'DSH-06',
        'Verify recent attendance logs chronological sort order (DESC)',
        'Each log timestamp >= subsequent log timestamp',
        f'is_sorted_desc={is_sorted_desc}',
        is_sorted_desc,
        "Log ordering verified strictly descending by timestamp"
    )

    # =========================================================================
    # SECTION 4: DATE & PERIOD FILTERING RECONCILIATION
    # =========================================================================
    print("\n--- 4. DATE & PERIOD FILTERING RECONCILIATION ---")

    # DSH-07: Filter 'today'
    res_today = client.get('/api/reports/attendance?date=today')
    d_today = res_today.get_json() or {}
    s_today = d_today.get('summary', {})
    today_ok = (res_today.status_code == 200 and 
                s_today.get('total_enrolled') == sql_total_users and 
                s_today.get('total_present_days') == sql_unique_today)
    record(
        'DSH-07',
        'GET /api/reports/attendance?date=today',
        f'total_enrolled={sql_total_users}, present={sql_unique_today}, absent={sql_absent_today}',
        f'enrolled={s_today.get("total_enrolled")}, present={s_today.get("total_present_days")}, absent={s_today.get("total_absent_days")}',
        today_ok,
        f"Today summary: {s_today}"
    )

    # DSH-08: Filter 'yesterday' (2026-10-07)
    # In SQLite, on 2026-10-07: 4 logs, 2 unique users (Imran Khalid, Malaika Irshad)
    cur.execute("""
        SELECT COUNT(DISTINCT user_id) FROM attendance 
        WHERE date(timestamp) = date('now', 'localtime', '-1 day')
        AND user_id NOT IN (SELECT user_id FROM manual_absent WHERE date = date('now', 'localtime', '-1 day'))
    """)
    sql_yest_unique = cur.fetchone()[0]

    res_yest = client.get('/api/reports/attendance?date=yesterday')
    d_yest = res_yest.get_json() or {}
    s_yest = d_yest.get('summary', {})
    yest_ok = (res_yest.status_code == 200 and 
               s_yest.get('total_enrolled') == sql_total_users and 
               s_yest.get('total_present_days') == sql_yest_unique)
    record(
        'DSH-08',
        'GET /api/reports/attendance?date=yesterday',
        f'total_enrolled={sql_total_users}, present={sql_yest_unique}, absent={sql_total_users - sql_yest_unique}',
        f'enrolled={s_yest.get("total_enrolled")}, present={s_yest.get("total_present_days")}, absent={s_yest.get("total_absent_days")}',
        yest_ok,
        f"Yesterday summary: {s_yest}"
    )

    # DSH-09: Filter 'last7'
    res_last7 = client.get('/api/reports/attendance?date=last7')
    d_last7 = res_last7.get_json() or {}
    s_last7 = d_last7.get('summary', {})
    last7_ok = res_last7.status_code == 200 and d_last7.get('is_multi_day') is True
    record(
        'DSH-09',
        'GET /api/reports/attendance?date=last7',
        'HTTP 200, is_multi_day=True, multi-day summary metrics present',
        f'HTTP {res_last7.status_code}, is_multi_day={d_last7.get("is_multi_day")}, attended_count={s_last7.get("attended_count")}',
        last7_ok,
        f"Last7 summary: {s_last7}"
    )

    # DSH-10: Filter 'this_week'
    res_week = client.get('/api/reports/attendance?date=this_week')
    d_week = res_week.get_json() or {}
    week_ok = res_week.status_code == 200 and 'summary' in d_week
    record(
        'DSH-10',
        'GET /api/reports/attendance?date=this_week',
        'HTTP 200 with summary metrics',
        f'HTTP {res_week.status_code}, summary={bool(d_week.get("summary"))}',
        week_ok,
        f"This week summary: {d_week.get('summary')}"
    )

    # DSH-11: Filter 'this_month' (October 2026)
    res_month = client.get('/api/reports/attendance?date=this_month')
    d_month = res_month.get_json() or {}
    s_month = d_month.get('summary', {})
    month_ok = res_month.status_code == 200 and s_month.get('total_enrolled') == sql_total_users
    record(
        'DSH-11',
        'GET /api/reports/attendance?date=this_month',
        f'HTTP 200, total_enrolled={sql_total_users}',
        f'HTTP {res_month.status_code}, enrolled={s_month.get("total_enrolled")}, rate={s_month.get("attendance_rate")}%',
        month_ok,
        f"This month summary: {s_month}"
    )

    # DSH-12: Filter Custom Date Range (2026-10-01 to 2026-10-07)
    res_custom = client.get('/api/reports/attendance?start_date=2026-10-01&end_date=2026-10-07')
    d_custom = res_custom.get_json() or {}
    s_custom = d_custom.get('summary', {})
    custom_ok = res_custom.status_code == 200 and d_custom.get('total_days') == 7
    record(
        'DSH-12',
        'GET /api/reports/attendance with custom date range (2026-10-01 to 2026-10-07)',
        'HTTP 200, total_days=7, is_multi_day=True',
        f'HTTP {res_custom.status_code}, total_days={d_custom.get("total_days")}, attended={s_custom.get("attended_count")}',
        custom_ok,
        f"Custom range summary: {s_custom}"
    )

    # =========================================================================
    # SECTION 5: DEPARTMENT FILTERING & BREAKDOWN
    # =========================================================================
    print("\n--- 5. DEPARTMENT FILTERING & BREAKDOWN ---")

    # DSH-13: Reconcile Department Breakdown against SQLite
    cur.execute("""
        SELECT COALESCE(department, 'General / Unassigned') as dept, COUNT(*) as cnt
        FROM users WHERE active = 1
        GROUP BY dept ORDER BY dept
    """)
    sql_depts = {r['dept']: r['cnt'] for r in cur.fetchall()}

    api_depts = {d['department']: d['total_staff'] for d in d_today.get('departments', [])}
    depts_reconciled = (len(sql_depts) == len(api_depts) and 
                        all(api_depts.get(k) == v for k, v in sql_depts.items()))
    record(
        'DSH-13',
        'Reconcile Department Breakdown headcount grid against SQLite',
        f'Exact department counts match: {sql_depts}',
        f'API breakdown counts: {api_depts}',
        depts_reconciled,
        f"Department breakdown matches SQLite: {depts_reconciled}"
    )

    # DSH-14: Filter by specific existing department
    import urllib.parse
    test_dept = list(sql_depts.keys())[0]
    encoded_dept = urllib.parse.quote(test_dept)
    res_dept_filter = client.get(f'/api/reports/attendance?date=today&department={encoded_dept}')
    d_df = res_dept_filter.get_json() or {}
    records_df = d_df.get('records', [])
    dept_filter_ok = (res_dept_filter.status_code == 200 and 
                      len(records_df) == sql_depts[test_dept] and 
                      all(r['department'] == test_dept for r in records_df))
    record(
        'DSH-14',
        f'GET /api/reports/attendance?department={test_dept}',
        f'Returns exactly {sql_depts[test_dept]} records belonging to "{test_dept}"',
        f'HTTP {res_dept_filter.status_code}, count={len(records_df)}',
        dept_filter_ok,
        f"Filtered department records: count={len(records_df)}"
    )

    # DSH-15: Filter by non-existent department
    res_nonexistent = client.get('/api/reports/attendance?date=today&department=NonexistentQA99')
    d_ne = res_nonexistent.get_json() or {}
    ne_ok = res_nonexistent.status_code == 200 and len(d_ne.get('records', [])) == 0
    record(
        'DSH-15',
        'GET /api/reports/attendance?department=NonexistentQA99',
        'HTTP 200 with empty records list (records=[])',
        f'HTTP {res_nonexistent.status_code}, records_count={len(d_ne.get("records", []))}',
        ne_ok,
        f"Empty state returned cleanly: {d_ne.get('summary')}"
    )

    # =========================================================================
    # SECTION 6: CONTROLLED REAL-TIME REFRESH & ATTENDANCE LOGGING
    # =========================================================================
    print("\n--- 6. CONTROLLED ATTENDANCE REFRESH & DOWNSTREAM UPDATE ---")

    # DSH-16: Controlled attendance logging updates Dashboard metrics immediately
    # Insert temporary attendance log for User 38 on current timestamp
    cur.execute("""
        INSERT INTO attendance (user_id, detected_name, confidence, source, location, device_id, timestamp)
        VALUES (38, 'Imran Khalid', 0.95, 'qa_audit_stream', 'Main Gate', 'cam_audit_01', datetime('now', 'localtime'))
    """)
    conn.commit()

    # Re-query /api/stats
    res_stats_after = client.get('/api/stats')
    data_stats_after = res_stats_after.get_json() or {}

    # Verify present_users increased by 1 and today_attendance increased by 1
    stats_updated = (
        data_stats_after.get('today_attendance') == sql_today_logs + 1 and
        data_stats_after.get('present_users') == sql_unique_today + 1 and
        data_stats_after.get('total_logs') == sql_total_logs + 1
    )
    record(
        'DSH-16',
        'Verify immediate update of /api/stats KPI metrics upon new attendance detection',
        f'today_attendance={sql_today_logs + 1}, present_users={sql_unique_today + 1}, total_logs={sql_total_logs + 1}',
        f'today_attendance={data_stats_after.get("today_attendance")}, present={data_stats_after.get("present_users")}, logs={data_stats_after.get("total_logs")}',
        stats_updated,
        f"Updated stats: {data_stats_after}"
    )

    # DSH-17: Verify new attendance log appears at top of /api/attendance/logs
    res_logs_after = client.get('/api/attendance/logs?limit=5')
    data_logs_after = res_logs_after.get_json() or {}
    first_log = data_logs_after.get('logs', [{}])[0]
    log_top_ok = (first_log.get('name') == 'Imran Khalid' and 
                  first_log.get('source') == 'qa_audit_stream')
    record(
        'DSH-17',
        'Verify latest attendance log appears immediately at top of /api/attendance/logs',
        'Latest log: name="Imran Khalid", source="qa_audit_stream"',
        f'Top log: name="{first_log.get("name")}", source="{first_log.get("source")}"',
        log_top_ok,
        f"Top log payload: {first_log}"
    )

    # Clean up temporary attendance log
    cur.execute("DELETE FROM attendance WHERE source = 'qa_audit_stream'")
    conn.commit()

    # =========================================================================
    # SECTION 7: API ROBUSTNESS & EDGE CASES
    # =========================================================================
    print("\n--- 7. API ROBUSTNESS & EDGE CASES ---")

    # DSH-18: /api/stats HEAD method
    res_head = client.head('/api/stats')
    record(
        'DSH-18',
        'HEAD /api/stats',
        'HTTP 200 OK',
        f'HTTP {res_head.status_code}',
        res_head.status_code == 200,
        "HTTP HEAD supported"
    )

    # DSH-19: /api/attendance/logs with string or negative limit
    res_bad_lim = client.get('/api/attendance/logs?limit=-5')
    # Should handle gracefully without 500
    record(
        'DSH-19',
        'GET /api/attendance/logs?limit=-5',
        'HTTP 200 with logs list or empty list, no 500 crash',
        f'HTTP {res_bad_lim.status_code}',
        res_bad_lim.status_code == 200,
        f"Response keys: {list((res_bad_lim.get_json() or {}).keys())}"
    )

    # DSH-20: /api/reports/attendance with inverted dates (start_date > end_date)
    res_inv = client.get('/api/reports/attendance?start_date=2026-10-07&end_date=2026-10-01')
    d_inv = res_inv.get_json() or {}
    # backend automatically swaps: start <= end
    inv_ok = res_inv.status_code == 200 and 'summary' in d_inv
    record(
        'DSH-20',
        'GET /api/reports/attendance with inverted dates (start > end)',
        'HTTP 200, handles inverted range gracefully without 500 error',
        f'HTTP {res_inv.status_code}',
        inv_ok,
        f"Response summary: {d_inv.get('summary')}"
    )

    # =========================================================================
    # SECTION 8: CROSS-MODULE RECONCILIATION
    # =========================================================================
    print("\n--- 8. CROSS-MODULE RECONCILIATION ---")

    # DSH-21: Branch & Organization Settings Identity Consistency
    cur.execute("SELECT branch_name, company_name FROM branch_settings LIMIT 1")
    br_row = cur.fetchone()
    br_name = br_row['branch_name'] if br_row else "Main Branch"
    org_name = br_row['company_name'] if br_row else "QIntellect Technologies"

    has_branch_in_html = br_name in html_content
    has_org_in_html = org_name in html_content
    record(
        'DSH-21',
        'Cross-Module: Verify Branch & Organization Settings identity on Dashboard',
        f'Branch: "{br_name}", Organization: "{org_name}" reflected in UI',
        f'branch_found={has_branch_in_html}, org_found={has_org_in_html}',
        has_branch_in_html and has_org_in_html,
        f"Identity: {br_name} | {org_name}"
    )

    # DSH-22: Salary & Payroll Anchor Verification (Employee #38)
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

    anchor_ok = (
        basic == 250000.0 and
        allowances == 35000.0 and
        deductions == 10000.0 and
        ot_rate == 1201.92 and
        ot_amount == 3605.76 and
        gross == 288605.76 and
        net_with == 253605.76
    )
    record(
        'DSH-22',
        'Cross-Module: Payroll & Salary Anchor Verification (Employee #38)',
        'Basic 250k, Allowances 35k, Deductions 10k, OT 3605.76, Gross 288,605.76, Net 253,605.76',
        f'Gross={gross}, Net={net_with}',
        anchor_ok,
        f"Employee #38 anchor: Basic={basic}, Net={net_with}"
    )

    # =========================================================================
    # SECTION 9: BASELINE RESTORATION & DATABASE INTEGRITY
    # =========================================================================
    print("\n--- 9. BASELINE RESTORATION & DATABASE INTEGRITY ---")

    post_counts = {t: cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
    ic = cur.execute("PRAGMA integrity_check").fetchall()
    fk = cur.execute("PRAGMA foreign_key_check").fetchall()

    counts_match = all(post_counts[t] == pre_counts[t] for t in tables)
    record(
        'DSH-23',
        'Database baseline row counts & integrity check after Dashboard audit',
        'All 12 tables match pre-audit baseline, PRAGMA integrity_check=ok, PRAGMA foreign_key_check=0',
        f'counts_match={counts_match}, ic={ic[0][0]}, fk={len(fk)} violations',
        counts_match and ic[0][0] == 'ok' and len(fk) == 0,
        f"Post counts: {post_counts}"
    )

    conn.close()

    # Save results to JSON
    with open('scratch/dashboard_audit_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    passed_cnt = sum(1 for r in results if r['passed'])
    print("\n" + "=" * 80)
    print(f"MODULE 5 (DASHBOARD & LIVE ANALYTICS) AUDIT SUMMARY: {passed_cnt}/{len(results)} PASSED")
    print("=" * 80)
    for r in results:
        status = "[PASS]" if r['passed'] else "[FAIL]"
        print(f"{status} {r['test_id']}: {r['action']}")
        print(f"       Expected: {r['expected']}")
        print(f"       Actual:   {r['actual']}")
        if not r['passed']:
            print(f"       Severity: {r.get('severity')}")
            print(f"       Affects : {r.get('affects')}")

    return passed_cnt, len(results)

if __name__ == '__main__':
    run_dashboard_audit()
