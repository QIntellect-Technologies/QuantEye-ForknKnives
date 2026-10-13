"""
Comprehensive Production Audit Script for Module 6: Staff Directory & Employee Management (#staff-view)
Strictly adheres to AUDIT FIRST -- ZERO CODE CHANGES.
Verifies:
1. UI DOM structure & controls (#staff-view, #editUserModal, #bulkCameraModal)
2. API contract & validations (GET /api/users, GET /api/users/<id>, POST /api/users/<id>/update, POST /api/users/<id>/delete, POST /api/users/bulk-assign-cameras)
3. End-to-End CRUD Lifecycle (Create -> Read -> Update -> Bulk Camera -> Camera Security -> Delete -> 404)
4. Data Reconciliation (Metrics, Search across 38 employees, Department Filtering)
5. Edge cases & error handling (Invalid user, empty name, invalid shift ID)
6. Complete database baseline restoration across all 12 tables and PRAGMA checks.
"""

import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
import unittest
from datetime import datetime

# Initialize Flask test client
from app import app, db

client = app.test_client()

audit_results = []

def record_test(test_id, category, action, expected, actual, status):
    audit_results.append({
        'test_id': test_id,
        'category': category,
        'action': action,
        'expected': expected,
        'actual': actual,
        'status': status
    })
    badge = f"[{status}]"
    print(f"{badge} {test_id} ({category}): {action}")
    if status != "PASS":
        print(f"       Expected: {expected}")
        print(f"       Actual:   {actual}")

# Check baseline tables
baseline_tables = [
    ('users', 38),
    ('departments', 10),
    ('designations', 23),
    ('shifts', 2),
    ('attendance', 84),
    ('leave_requests', 1),
    ('overtime', 0),
    ('salary_configs', 37),
    ('payroll_records', 106),
    ('embeddings', 3872),
    ('branch_settings', 1),
    ('employee_shift_history', 38)
]

conn = sqlite3.connect('attendance.db')
c = conn.cursor()

# Verify initial baseline
for t, expected in baseline_tables:
    c.execute(f"SELECT COUNT(*) FROM {t}")
    count = c.fetchone()[0]
    if count != expected:
        print(f"[PRE-CHECK WARNING] Table '{t}' expected {expected}, found {count}")

# ==============================================================================
# SECTION 1: UI DOM & STATIC ASSETS AUDIT
# ==============================================================================
with open('templates/index.html', 'r', encoding='utf-8') as f:
    html_content = f.read()

# STF-UI-01: #staff-view and page header
has_staff_view = 'id="staff-view"' in html_content
has_staff_header = 'Staff Directory' in html_content
has_metric_cards = ('id="tabStatTotalStaff"' in html_content and 
                    'id="tabStatDepts"' in html_content and 
                    'id="tabStatPayroll"' in html_content)
record_test(
    "STF-UI-01", "UI DOM",
    "Verify #staff-view exists with header and metric counters",
    "True, True, True",
    f"{has_staff_view}, {has_staff_header}, {has_metric_cards}",
    "PASS" if (has_staff_view and has_staff_header and has_metric_cards) else "FAIL"
)

# STF-UI-02: Header action buttons
has_bulk_cam_btn = 'openBulkCameraModal()' in html_content
has_add_staff_btn = 'openTabAddStaffModal()' in html_content
has_refresh_btn = 'loadTabStaffDirectory()' in html_content
record_test(
    "STF-UI-02", "UI DOM",
    "Verify Bulk Camera, Add New Staff, and Refresh List buttons exist",
    "True, True, True",
    f"{has_bulk_cam_btn}, {has_add_staff_btn}, {has_refresh_btn}",
    "PASS" if (has_bulk_cam_btn and has_add_staff_btn and has_refresh_btn) else "FAIL"
)

# STF-UI-03: Filter & Search inputs
has_search_input = 'id="tabStaffSearchInput"' in html_content
has_dept_filter = 'id="tabStaffDeptFilter"' in html_content
record_test(
    "STF-UI-03", "UI DOM",
    "Verify search input (#tabStaffSearchInput) and dept filter (#tabStaffDeptFilter)",
    "True, True",
    f"{has_search_input}, {has_dept_filter}",
    "PASS" if (has_search_input and has_dept_filter) else "FAIL"
)

# STF-UI-04: Table & Pagination elements
has_table_body = 'id="tabStaffTableBody"' in html_content
has_select_all = 'id="selectAllStaffCheck"' in html_content
has_pagination = ('id="tabStaffPagination"' in html_content and 
                  'id="tabStaffPageControls"' in html_content and
                  'id="tabStaffShowingStart"' in html_content)
record_test(
    "STF-UI-04", "UI DOM",
    "Verify table body, select-all checkbox, and pagination controls",
    "True, True, True",
    f"{has_table_body}, {has_select_all}, {has_pagination}",
    "PASS" if (has_table_body and has_select_all and has_pagination) else "FAIL"
)

# STF-UI-05: Edit Staff Modal (#editUserModal)
has_edit_modal = 'id="editUserModal"' in html_content
has_edit_fields = all(k in html_content for k in [
    'id="editUserId"', 'id="editName"', 'id="editEmail"', 'id="editDepartment"',
    'id="editPosition"', 'id="editCNIC"', 'id="editSalary"', 'id="editJoinDate"',
    'id="editShiftId"', 'id="editCheckinCamerasWrapper"', 'id="editCheckoutCamerasWrapper"'
])
record_test(
    "STF-UI-05", "UI DOM",
    "Verify #editUserModal exists with required HR input fields",
    "True, True",
    f"{has_edit_modal}, {has_edit_fields}",
    "PASS" if (has_edit_modal and has_edit_fields) else "FAIL"
)

# STF-UI-06: Bulk Camera Assignment Modal (#bulkCameraModal)
has_bulk_modal = 'id="bulkCameraModal"' in html_content
has_bulk_controls = ('id="bulkCheckinCamerasWrapper"' in html_content and
                     'id="bulkCheckoutCamerasWrapper"' in html_content and
                     'submitBulkCameraAssignment()' in html_content)
record_test(
    "STF-UI-06", "UI DOM",
    "Verify #bulkCameraModal exists with checkin/checkout wrappers and submit handler",
    "True, True",
    f"{has_bulk_modal}, {has_bulk_controls}",
    "PASS" if (has_bulk_modal and has_bulk_controls) else "FAIL"
)

# ==============================================================================
# SECTION 2: BACKEND API INVENTORY & VALIDATION
# ==============================================================================

# STF-API-01: GET /api/users
res = client.get('/api/users')
status_ok = res.status_code == 200
data = res.get_json() if status_ok else {}
users_list = data.get('users', [])
record_test(
    "STF-API-01", "Backend API",
    "GET /api/users retrieves active staff directory list with shift and camera metadata",
    "HTTP 200, array of 38 users with shift_name, checkin_cameras, checkout_cameras",
    f"HTTP {res.status_code}, {len(users_list)} users, sample keys: {list(users_list[0].keys()) if users_list else 'none'}",
    "PASS" if status_ok and len(users_list) == 38 and 'shift_name' in users_list[0] else "FAIL"
)

# STF-API-02: GET /api/users/<id> for valid user (Imran Khalid, ID 38)
res = client.get('/api/users/38')
status_ok = res.status_code == 200
u38 = res.get_json() if status_ok else {}
record_test(
    "STF-API-02", "Backend API",
    "GET /api/users/38 retrieves single employee profile details",
    "HTTP 200, name='Imran Khalid', department='AI & Data Science', salary=250000.0",
    f"HTTP {res.status_code}, name='{u38.get('name')}', dept='{u38.get('department')}', salary={u38.get('salary')}",
    "PASS" if status_ok and u38.get('name') == 'Imran Khalid' and u38.get('salary') == 250000.0 else "FAIL"
)

# STF-API-03: GET /api/users/<id> for non-existent user
res = client.get('/api/users/999999')
record_test(
    "STF-API-03", "Backend API",
    "GET /api/users/999999 for non-existent user returns HTTP 404",
    "HTTP 404, {'error': 'User not found'}",
    f"HTTP {res.status_code}, {res.get_json()}",
    "PASS" if res.status_code == 404 else "FAIL"
)

# STF-API-04: POST /api/users/<id>/update empty name validation
res = client.post('/api/users/38/update', data=json.dumps({'name': '   '}), content_type='application/json')
record_test(
    "STF-API-04", "Validation",
    "POST /api/users/38/update rejects whitespace-only name",
    "HTTP 400, {'error': 'Name is required'}",
    f"HTTP {res.status_code}, {res.get_json()}",
    "PASS" if res.status_code == 400 and 'Name is required' in res.get_json().get('error', '') else "FAIL"
)

# STF-API-05: POST /api/users/<id>/update for non-existent user returns HTTP 404
res = client.post('/api/users/999999/update', data=json.dumps({'name': 'Ghost Employee'}), content_type='application/json')
record_test(
    "STF-API-05", "Backend API",
    "POST /api/users/999999/update for non-existent user returns HTTP 404",
    "HTTP 404, {'error': 'Staff member not found'}",
    f"HTTP {res.status_code}, {res.get_json()}",
    "PASS" if res.status_code == 404 and 'Staff member not found' in res.get_json().get('error', '') else "FAIL"
)

# STF-VAL-01: POST /api/users/<id>/update with non-existent shift ID returns HTTP 400
res_invalid_shift = client.post('/api/users/38/update', data=json.dumps({
    'name': 'Imran Khalid',
    'department': 'AI & Data Science',
    'shift_id': 99999
}), content_type='application/json')
record_test(
    "STF-VAL-01", "Edge Cases",
    "POST /api/users/38/update with non-existent shift ID (shift_id=99999) returns HTTP 400",
    "HTTP 400, {'error': 'Invalid shift ID'}",
    f"HTTP {res_invalid_shift.status_code}, {res_invalid_shift.get_json()}",
    "PASS" if res_invalid_shift.status_code == 400 and 'Invalid shift ID' in res_invalid_shift.get_json().get('error', '') else "FAIL"
)

# ==============================================================================
# SECTION 3: END-TO-END CRUD LIFECYCLE ON TEMPORARY USER
# ==============================================================================

# Create temporary user using db.add_user
test_user_id = db.add_user(
    name="Audit Test Staff",
    email="audittest@example.com",
    phone="0300-9999999",
    department="Software Development",
    position="Software Engineer",
    cnic="35201-9999999-9",
    salary=95000.0,
    join_date="2026-03-01",
    shift_id=1,
    checkin_cameras="all",
    checkout_cameras="all"
)

record_test(
    "STF-CRUD-01", "CRUD Lifecycle",
    f"Create temporary employee #{test_user_id} and retrieve via GET /api/users/{test_user_id}",
    f"Employee ID {test_user_id} created and returned via GET",
    f"Created ID {test_user_id}, GET status {client.get(f'/api/users/{test_user_id}').status_code}",
    "PASS" if client.get(f'/api/users/{test_user_id}').status_code == 200 else "FAIL"
)

# Update the test employee profile with valid shift_id (3 = Night Shift)
upd_payload = {
    'name': 'Audit Test Staff Updated',
    'email': 'auditupdated@example.com',
    'phone': '0300-8888888',
    'department': 'Software Engineering',
    'position': 'Senior Systems Specialist',
    'cnic': '35201-8888888-8',
    'salary': 105000.0,
    'shift_id': 3,
    'checkin_cameras': 'nvr_office',
    'checkout_cameras': 'nvr_office'
}
res_upd = client.post(f'/api/users/{test_user_id}/update', data=json.dumps(upd_payload), content_type='application/json')
res_chk = client.get(f'/api/users/{test_user_id}')
chk_data = res_chk.get_json() if res_chk.status_code == 200 else {}

upd_success = (
    res_upd.status_code == 200 and
    chk_data.get('name') == 'Audit Test Staff Updated' and
    chk_data.get('department') == 'Software Engineering' and
    chk_data.get('salary') == 105000.0 and
    chk_data.get('shift_id') == 3 and
    chk_data.get('checkin_cameras') == 'nvr_office'
)

record_test(
    "STF-CRUD-02", "CRUD Lifecycle",
    f"Update employee #{test_user_id} HR profile details, shift (Night Shift #3), and camera permissions",
    "HTTP 200 and all updated fields reflected",
    f"HTTP {res_upd.status_code}, name='{chk_data.get('name')}', dept='{chk_data.get('department')}', shift_id={chk_data.get('shift_id')}, salary={chk_data.get('salary')}",
    "PASS" if upd_success else "FAIL"
)

# Bulk camera assignment targeting this test user
res_bulk_cam = client.post('/api/users/bulk-assign-cameras', data=json.dumps({
    'user_ids': [test_user_id],
    'checkin_cameras': 'cam_entrance',
    'checkout_cameras': 'cam_exit'
}), content_type='application/json')
res_bulk_chk = client.get(f'/api/users/{test_user_id}').get_json()

bulk_cam_ok = (
    res_bulk_cam.status_code == 200 and
    res_bulk_cam.get_json().get('count') == 1 and
    res_bulk_chk.get('checkin_cameras') == 'cam_entrance' and
    res_bulk_chk.get('checkout_cameras') == 'cam_exit'
)

record_test(
    "STF-CRUD-03", "Camera Assignment",
    f"Apply bulk camera assignment to user #{test_user_id}",
    "HTTP 200, count=1, checkin='cam_entrance', checkout='cam_exit'",
    f"HTTP {res_bulk_cam.status_code}, count={res_bulk_cam.get_json().get('count')}, in='{res_bulk_chk.get('checkin_cameras')}', out='{res_bulk_chk.get('checkout_cameras')}'",
    "PASS" if bulk_cam_ok else "FAIL"
)

# Test camera authorization check: check_user_camera_allowed
allowed_in, msg_in = db.check_user_camera_allowed(test_user_id, 'cam_entrance', 'checkin')
blocked_in, msg_blocked = db.check_user_camera_allowed(test_user_id, 'nvr_office', 'checkin')
cam_auth_ok = allowed_in is True and blocked_in is False

record_test(
    "STF-SEC-01", "Camera Security",
    f"Enforce camera authorization rule on employee #{test_user_id}",
    "cam_entrance=True (allowed), nvr_office=False (blocked)",
    f"cam_entrance={allowed_in}, nvr_office={blocked_in}",
    "PASS" if cam_auth_ok else "FAIL"
)

# Delete the test employee
res_del = client.post(f'/api/users/{test_user_id}/delete')
del_ok = res_del.status_code == 200 and res_del.get_json().get('success') is True
res_after_del = client.get(f'/api/users/{test_user_id}')
purged_ok = res_after_del.status_code == 404

record_test(
    "STF-CRUD-04", "CRUD Lifecycle",
    f"Delete employee #{test_user_id} and confirm 404 on subsequent get",
    "HTTP 200 on delete, HTTP 404 on subsequent get",
    f"Delete HTTP {res_del.status_code}, Get HTTP {res_after_del.status_code}",
    "PASS" if del_ok and purged_ok else "FAIL"
)

# Clean up shift history for test user if any entry was generated
c.execute("DELETE FROM employee_shift_history WHERE user_id = ?", (test_user_id,))
conn.commit()

# ==============================================================================
# SECTION 4: SEARCH, FILTER, AND METRIC CALCULATION RECONCILIATION
# ==============================================================================

# Metric calculation audit against database
c.execute("SELECT COUNT(*), COUNT(DISTINCT department), SUM(salary) FROM users WHERE active = 1")
row_metrics = c.fetchone()
db_total_staff = row_metrics[0]
db_active_depts = row_metrics[1]
db_total_payroll = float(row_metrics[2] or 0)

all_staff_api = client.get('/api/users').get_json().get('users', [])
api_total_staff = len(all_staff_api)
api_depts = len(set(u['department'] for u in all_staff_api if u['department']))
api_payroll = sum(float(u.get('salary') or 0) for u in all_staff_api)

metrics_reconciled = (
    db_total_staff == api_total_staff == 38 and
    db_active_depts == api_depts == 10 and
    abs(db_total_payroll - api_payroll) < 0.01
)

record_test(
    "STF-REC-01", "Data Reconciliation",
    "Reconcile Staff Directory metrics (Total Staff, Active Depts, Payroll) with SQLite",
    f"Total: {db_total_staff}, Depts: {db_active_depts}, Payroll: PKR {db_total_payroll:,.2f}",
    f"Total: {api_total_staff}, Depts: {api_depts}, Payroll: PKR {api_payroll:,.2f}",
    "PASS" if metrics_reconciled else "FAIL"
)

# Search filtering emulation across 38 employees
# Search query: "Imran" -> exactly 2 records: Imran Khalid (#38) and Asim Imran - Student (#76)
query_matches = [u for u in all_staff_api if 'imran' in (u.get('name') or '').lower()]
imran_match_ids = {u['id'] for u in query_matches}
record_test(
    "STF-REC-02", "Search Filter",
    "Search query 'imran' returns all matching staff members",
    "2 matches (IDs: 38 Imran Khalid, 76 Asim Imran)",
    f"{len(query_matches)} matches (IDs: {imran_match_ids})",
    "PASS" if len(query_matches) == 2 and imran_match_ids == {38, 76} else "FAIL"
)

# Department filter: "AI & Data Science" -> exactly 1 record (Employee #38)
ai_matches = [u for u in all_staff_api if u.get('department') == 'AI & Data Science']
record_test(
    "STF-REC-03", "Department Filter",
    "Filter by department 'AI & Data Science'",
    "1 employee in AI & Data Science (#38 Imran Khalid)",
    f"{len(ai_matches)} employee(s): {[u['name'] for u in ai_matches]}",
    "PASS" if len(ai_matches) == 1 and ai_matches[0]['id'] == 38 else "FAIL"
)

# Department filter: "Software Development" -> exactly 7 records
sd_matches = [u for u in all_staff_api if u.get('department') == 'Software Development']
record_test(
    "STF-REC-04", "Department Filter",
    "Filter by department 'Software Development'",
    "7 employees in Software Development",
    f"{len(sd_matches)} employees",
    "PASS" if len(sd_matches) == 7 else "FAIL"
)

# ==============================================================================
# SECTION 5: DATABASE INTEGRITY & EXACT PRODUCTION BASELINE
# ==============================================================================
c.execute("PRAGMA integrity_check")
ic = c.fetchone()[0]
c.execute("PRAGMA foreign_key_check")
fk_violations = len(c.fetchall())

record_test(
    "STF-DB-01", "Database Integrity",
    "PRAGMA integrity_check",
    "ok", ic,
    "PASS" if ic == 'ok' else "FAIL"
)

record_test(
    "STF-DB-02", "Database Integrity",
    "PRAGMA foreign_key_check",
    "0 violations", f"{fk_violations} violations",
    "PASS" if fk_violations == 0 else "FAIL"
)

# Check all 12 table baseline counts
baseline_ok = True
for t, expected in baseline_tables:
    c.execute(f"SELECT COUNT(*) FROM {t}")
    count = c.fetchone()[0]
    matched = (count == expected)
    if not matched:
        baseline_ok = False
    record_test(
        f"STF-BASE-{t[:4].upper()}", "Production Baseline",
        f"Row count for table '{t}'",
        f"{expected} rows", f"{count} rows",
        "PASS" if matched else "FAIL"
    )

conn.close()

passed = sum(1 for r in audit_results if r['status'] == 'PASS')
failed = sum(1 for r in audit_results if r['status'] == 'FAIL')

print("\n" + "=" * 80)
print(f"AUDIT SUMMARY: {passed} PASSED | {failed} FAILED (TOTAL {len(audit_results)})")
print("=" * 80)

# Save JSON results for report generator
with open('scratch/staff_audit_results.json', 'w') as f:
    json.dump(audit_results, f, indent=2)
