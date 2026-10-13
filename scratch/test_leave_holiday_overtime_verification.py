import sys
import os
sys.path.insert(0, os.path.abspath('.'))
import json
import sqlite3
from app import app
import database as db

client = app.test_client()

print("=" * 70)
print("LEAVE & HOLIDAY MANAGEMENT + OVERTIME END-TO-END VERIFICATION")
print("=" * 70)

# 1. HTML Verification: Verify buttons and modals in index.html
with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

checks = [
    ('File Leave Request button exists', 'openFileLeaveModal()' in html),
    ('Add Holiday button exists', 'openAddHolidayModal()' in html),
    ('Add Leave Type button exists', 'openAddLeaveTypeModal()' in html),
    ('+ Log Overtime button exists', 'openAddOvertimeModal()' in html),
    ('Subtab leave-requests exists', 'id="subtab-leave-requests"' in html),
    ('Subtab leave-balances exists', 'id="subtab-leave-balances"' in html),
    ('Subtab leave-types exists', 'id="subtab-leave-types"' in html),
    ('Subtab company-holidays exists', 'id="subtab-company-holidays"' in html),
    ('fileLeaveModal exists', 'id="fileLeaveModal"' in html),
    ('companyHolidayModal exists', 'id="companyHolidayModal"' in html),
    ('leaveTypeModal exists', 'id="leaveTypeModal"' in html),
    ('addOvertimeModal exists', 'id="addOvertimeModal"' in html),
    ('modalHolidayRecurring field exists', 'id="modalHolidayRecurring"' in html),
    ('window.openFileLeaveModal exposed', 'window.openFileLeaveModal =' in html),
    ('window.openAddHolidayModal exposed', 'window.openAddHolidayModal =' in html),
    ('window.openAddLeaveTypeModal exposed', 'window.openAddLeaveTypeModal =' in html),
    ('window.openAddOvertimeModal exposed', 'window.openAddOvertimeModal =' in html),
]

all_html_ok = True
for name, ok in checks:
    status = "PASS" if ok else "FAIL"
    if not ok: all_html_ok = False
    print(f"[{status}] HTML: {name}")

print("\n--- 2. REAL-TIME DATA STORE: LEAVE REQUEST CYCLE ---")
# Check GET /api/leaves
res = client.get('/api/leaves')
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
initial_leaves = res.get_json()
print(f"Initial leave requests count: {len(initial_leaves)}")

# Test POST /api/leaves
post_data = {
    'user_id': 38,
    'leave_type': 'casual',
    'start_date': '2026-10-20',
    'end_date': '2026-10-21',
    'reason': 'Test Leave Application'
}
res = client.post('/api/leaves', data=json.dumps(post_data), content_type='application/json')
assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.data}"
leave_id = res.get_json().get('id')
print(f"[PASS] Created test leave request #{leave_id}")

# Check leave appears in GET /api/leaves
res = client.get('/api/leaves')
leaves = res.get_json()
found = [l for l in leaves if l['id'] == leave_id]
assert len(found) == 1, "Created leave not found in GET /api/leaves"
print(f"[PASS] Leave #{leave_id} retrieved in real time: status={found[0]['status']}")

# Test PUT /api/leaves/<id> approve
res = client.put(f'/api/leaves/{leave_id}', data=json.dumps({'status': 'approved', 'approved_by': 'Admin Test'}), content_type='application/json')
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
res = client.get('/api/leaves')
leaves = res.get_json()
found = [l for l in leaves if l['id'] == leave_id]
assert found[0]['status'] == 'approved', f"Expected approved, got {found[0]['status']}"
print(f"[PASS] Leave #{leave_id} approved: status={found[0]['status']}")

# Clean up test leave
res = client.delete(f'/api/leaves/{leave_id}')
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print(f"[PASS] Cleaned up test leave #{leave_id}")

print("\n--- 3. REAL-TIME DATA STORE: LEAVE TYPES POLICY CYCLE ---")
res = client.get('/api/leave-types')
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
initial_ltypes = res.get_json()
print(f"Initial leave types count: {len(initial_ltypes)}")

# Test POST /api/leave-types
type_data = {
    'name': 'Paternity Leave Test',
    'code': 'paternity_test',
    'yearly_allowance': 5.0,
    'is_paid': 1,
    'description': 'Temporary verification policy'
}
res = client.post('/api/leave-types', data=json.dumps(type_data), content_type='application/json')
assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.data}"
type_id = res.get_json().get('id')
print(f"[PASS] Created test leave type #{type_id}")

res = client.get('/api/leave-types')
types = res.get_json()
found_t = [t for t in types if t['id'] == type_id]
assert len(found_t) == 1, "Created leave type not found"
print(f"[PASS] Leave type #{type_id} retrieved: name={found_t[0]['name']}, days={found_t[0]['yearly_allowance']}")

# Clean up test leave type
res = client.delete(f'/api/leave-types/{type_id}')
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print(f"[PASS] Cleaned up test leave type #{type_id}")

print("\n--- 4. REAL-TIME DATA STORE: PUBLIC HOLIDAYS CYCLE ---")
res = client.get('/api/holidays')
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
initial_holidays = res.get_json()
print(f"Initial holidays count: {len(initial_holidays)}")

# Test POST /api/holidays
holiday_data = {
    'name': 'Test Iqbal Day',
    'holiday_date': '2026-11-09',
    'description': 'National public holiday',
    'is_recurring': 1
}
res = client.post('/api/holidays', data=json.dumps(holiday_data), content_type='application/json')
assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.data}"
holiday_id = res.get_json().get('id')
print(f"[PASS] Created test holiday #{holiday_id}")

res = client.get('/api/holidays')
holidays = res.get_json()
found_h = [h for h in holidays if h['id'] == holiday_id]
assert len(found_h) == 1, "Created holiday not found"
print(f"[PASS] Holiday #{holiday_id} retrieved: name={found_h[0]['name']}, date={found_h[0]['holiday_date']}")

# Clean up test holiday
res = client.delete(f'/api/holidays/{holiday_id}')
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print(f"[PASS] Cleaned up test holiday #{holiday_id}")

print("\n--- 5. REAL-TIME DATA STORE: OVERTIME CYCLE ---")
res = client.get('/api/overtime')
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
initial_ot = res.get_json()
print(f"Initial overtime records count: {len(initial_ot)}")

# Test POST /api/overtime
ot_data = {
    'user_id': 38,
    'ot_date': '2026-10-15',
    'hours': 2.0,
    'reason': 'Server Migration Support'
}
res = client.post('/api/overtime', data=json.dumps(ot_data), content_type='application/json')
assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.data}"
ot_id = res.get_json().get('id')
print(f"[PASS] Created test overtime log #{ot_id}")

res = client.get('/api/overtime')
records = res.get_json()
found_ot = [o for o in records if o['id'] == ot_id]
assert len(found_ot) == 1, "Created overtime record not found"
print(f"[PASS] Overtime #{ot_id} retrieved: hours={found_ot[0]['hours']}, status={found_ot[0]['status']}")

# Test PUT /api/overtime/<id>
res = client.put(f'/api/overtime/{ot_id}', data=json.dumps({'status': 'approved', 'approved_by': 'Admin Test'}), content_type='application/json')
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
res = client.get('/api/overtime')
found_ot = [o for o in res.get_json() if o['id'] == ot_id]
assert found_ot[0]['status'] == 'approved', "Status not updated"
print(f"[PASS] Overtime #{ot_id} updated: status={found_ot[0]['status']}")

# Clean up test overtime
res = client.delete(f'/api/overtime/{ot_id}')
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
print(f"[PASS] Cleaned up test overtime #{ot_id}")

print("\n--- 6. LEAVE BALANCES REAL-TIME RETRIEVAL ---")
res = client.get('/api/leaves/balances?year=2026')
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
balances = res.get_json()
print(f"[PASS] Retrieved {len(balances)} employee leave quotas for 2026")
user38_bal = [b for b in balances if b['user_id'] == 38][0]
print(f"[PASS] Imran Khalid (#38) quota: Annual={user38_bal['balances']['annual']['used']}/{user38_bal['balances']['annual']['allocated']} days")

print("\n--- 7. DATABASE INTEGRITY & PRODUCTION COUNTS VERIFICATION ---")
conn = sqlite3.connect('attendance.db')
c = conn.cursor()

tables = [
    ('users', 38), ('departments', 10), ('designations', 23),
    ('shifts', 2), ('attendance', 84), ('leave_requests', 1),
    ('overtime', 0), ('salary_configs', 37), ('payroll_records', 106),
    ('embeddings', 3872), ('branch_settings', 1), ('employee_shift_history', 38)
]

db_ok = True
for t, expected in tables:
    c.execute(f'SELECT COUNT(*) FROM {t}')
    actual = c.fetchone()[0]
    matched = (actual == expected)
    if not matched: db_ok = False
    print(f"[{'PASS' if matched else 'FAIL'}] Table {t:22}: actual={actual} expected={expected}")

c.execute('PRAGMA integrity_check')
ic = c.fetchone()[0]
c.execute('PRAGMA foreign_key_check')
fk = len(c.fetchall())
print(f"[{'PASS' if ic == 'ok' else 'FAIL'}] PRAGMA integrity_check: {ic}")
print(f"[{'PASS' if fk == 0 else 'FAIL'}] PRAGMA foreign_key_check: {fk} violations")

if all_html_ok and db_ok and ic == 'ok' and fk == 0:
    print("\n" + "=" * 70)
    print("ALL VERIFICATION CHECKS PASSED SUCCESSFULLY (100%)")
    print("=" * 70)
else:
    print("\nFAILURES DETECTED!")
    sys.exit(1)
