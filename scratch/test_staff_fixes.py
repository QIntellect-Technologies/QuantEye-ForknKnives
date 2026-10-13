"""
Targeted Verification Script for Staff Directory Fixes STF-01, STF-02, and STF-03.
Verifies:
1. STF-01: Whitespace name -> HTTP 400 {"error": "Name is required"}
2. STF-02: Non-existent shift_id -> HTTP 400 {"error": "Invalid shift ID"}
3. STF-03: Non-existent user_id -> HTTP 404 {"error": "Staff member not found"}
4. Normal update workflow -> HTTP 200 on valid update, fields persisted
5. Restoration of exact production baseline across all 12 tables
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
from app import app, db

client = app.test_client()

results = []

def record(test_id, action, expected, actual, passed):
    status = "PASS" if passed else "FAIL"
    results.append({
        'test_id': test_id,
        'action': action,
        'expected': expected,
        'actual': actual,
        'status': status
    })
    print(f"[{status}] {test_id}: {action}")
    print(f"       Expected: {expected}")
    print(f"       Actual:   {actual}")

print("\n" + "="*80)
print("RUNNING TARGETED VERIFICATION: STF-01, STF-02, STF-03")
print("="*80)

# 1. STF-01: Whitespace-only name
r_stf01 = client.post('/api/users/38/update', json={'name': '   '})
stf01_body = r_stf01.get_json() or {}
stf01_ok = (r_stf01.status_code == 400 and stf01_body.get('error') == 'Name is required')
record(
    "STF-01",
    "POST /api/users/38/update with whitespace-only name ('   ')",
    "HTTP 400, {'error': 'Name is required'}",
    f"HTTP {r_stf01.status_code}, {stf01_body}",
    stf01_ok
)

# 2. STF-02: Non-existent shift_id
r_stf02 = client.post('/api/users/38/update', json={'name': 'Imran Khalid', 'shift_id': 99999})
stf02_body = r_stf02.get_json() or {}
stf02_ok = (r_stf02.status_code == 400 and stf02_body.get('error') == 'Invalid shift ID')
record(
    "STF-02",
    "POST /api/users/38/update with non-existent shift_id (99999)",
    "HTTP 400, {'error': 'Invalid shift ID'}",
    f"HTTP {r_stf02.status_code}, {stf02_body}",
    stf02_ok
)

# 3. STF-03: Non-existent user_id
r_stf03 = client.post('/api/users/999999/update', json={'name': 'Ghost Employee'})
stf03_body = r_stf03.get_json() or {}
stf03_ok = (r_stf03.status_code == 404 and stf03_body.get('error') == 'Staff member not found')
record(
    "STF-03",
    "POST /api/users/999999/update with non-existent user_id (999999)",
    "HTTP 404, {'error': 'Staff member not found'}",
    f"HTTP {r_stf03.status_code}, {stf03_body}",
    stf03_ok
)

# 4. Normal update workflow with valid data
temp_user_id = db.add_user(
    name="Targeted Verification Temp",
    email="tempverify@example.com",
    phone="0300-1111111",
    department="Software Development",
    position="Software Engineer",
    cnic="35201-1111111-1",
    salary=80000.0,
    join_date="2026-03-01",
    shift_id=1,
    checkin_cameras="all",
    checkout_cameras="all"
)

valid_upd_payload = {
    'name': 'Targeted Verification Temp Updated',
    'email': 'tempupdated@example.com',
    'phone': '0300-2222222',
    'department': 'Software Engineering',
    'position': 'Senior Software Engineer',
    'cnic': '35201-2222222-2',
    'salary': 95000.0,
    'shift_id': 3,
    'checkin_cameras': 'nvr_office',
    'checkout_cameras': 'nvr_office'
}

r_valid = client.post(f'/api/users/{temp_user_id}/update', json=valid_upd_payload)
valid_body = r_valid.get_json() or {}
r_get = client.get(f'/api/users/{temp_user_id}')
get_body = r_get.get_json() or {}

valid_ok = (
    r_valid.status_code == 200 and
    valid_body.get('success') is True and
    get_body.get('name') == 'Targeted Verification Temp Updated' and
    get_body.get('department') == 'Software Engineering' and
    get_body.get('shift_id') == 3 and
    get_body.get('salary') == 95000.0 and
    get_body.get('checkin_cameras') == 'nvr_office'
)

record(
    "STF-VALID-UPDATE",
    f"Normal update workflow on employee #{temp_user_id}",
    "HTTP 200, success=True, all fields updated in SQLite",
    f"HTTP {r_valid.status_code}, success={valid_body.get('success')}, name={get_body.get('name')}, shift={get_body.get('shift_id')}",
    valid_ok
)

# Clean up temp user
db.delete_user(temp_user_id)
with sqlite3.connect('attendance.db') as conn:
    cursor = conn.cursor()
    cursor.execute("DELETE FROM employee_shift_history WHERE user_id = ?", (temp_user_id,))
    conn.commit()

# Verify baseline restoration
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

with sqlite3.connect('attendance.db') as conn:
    cursor = conn.cursor()
    baseline_match = True
    for t, expected in baseline_tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cursor.fetchone()[0]
        if cnt != expected:
            baseline_match = False
            print(f"[FAIL] Baseline mismatch on '{t}': expected {expected}, found {cnt}")
    
    cursor.execute("PRAGMA integrity_check;")
    ic = cursor.fetchone()[0]
    cursor.execute("PRAGMA foreign_key_check;")
    fks = len(cursor.fetchall())

record(
    "STF-BASELINE",
    "Restoration of exact production baseline (12 tables) & PRAGMAs",
    "All 12 tables match exact baseline, integrity=ok, fks=0",
    f"Baseline match: {baseline_match}, integrity: {ic}, fks: {fks}",
    baseline_match and ic == 'ok' and fks == 0
)

passed_count = sum(1 for r in results if r['status'] == 'PASS')
print("\n" + "="*80)
print(f"TARGETED VERIFICATION RESULT: {passed_count}/{len(results)} PASSED")
print("="*80)
