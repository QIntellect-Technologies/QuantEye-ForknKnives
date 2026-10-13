import sys
sys.path.insert(0, ".")
import sqlite3
import database as db
from app import app

client = app.test_client()

print("=== 1. TEST GET /api/salary ===")
res = client.get('/api/salary')
print("Status code:", res.status_code)
data = res.get_json()
print("Total records returned:", len(data))
print("Sample record 0:", data[0] if data else None)
assert res.status_code == 200
assert len(data) == 38, f"Expected 38 active users, got {len(data)}"

print("\n=== 2. TEST GET /api/salary/summary ===")
res_sum = client.get('/api/salary/summary')
print("Status code:", res_sum.status_code)
summary = res_sum.get_json()
print("Summary:", summary)
assert res_sum.status_code == 200
assert summary['total_employees'] == 38
assert summary['total_basic'] > 0

print("\n=== 3. TEST GET /api/salary/38 (Imran Khalid) ===")
res_user = client.get('/api/salary/38')
print("Status code:", res_user.status_code)
user_cfg = res_user.get_json()
print("User 38 config:", user_cfg)
assert res_user.status_code == 200
assert user_cfg['user_name'] == 'Imran Khalid'
assert user_cfg['basic_salary'] == 250000.0

print("\n=== 4. TEST POST /api/salary (Validation) ===")
res_invalid = client.post('/api/salary', json={'user_id': 38, 'basic_salary': -500})
print("Negative salary response:", res_invalid.status_code, res_invalid.get_json())
assert res_invalid.status_code == 400

res_invalid_user = client.post('/api/salary', json={'user_id': 999999, 'basic_salary': 50000})
print("Invalid user response:", res_invalid_user.status_code, res_invalid_user.get_json())
assert res_invalid_user.status_code == 404

print("\n=== 5. TEST POST /api/salary (Valid update) ===")
res_update = client.post('/api/salary', json={
    'user_id': 38,
    'basic_salary': 250000,
    'allowances': 25000,
    'deductions': 5000,
    'ot_rate': 1200
})
print("Update response:", res_update.status_code, res_update.get_json())
assert res_update.status_code == 200
updated = res_update.get_json()['config']
assert updated['allowances'] == 25000.0
assert updated['deductions'] == 5000.0
assert updated['ot_rate'] == 1200.0
assert updated['net_estimated'] == 270000.0  # 250000 + 25000 - 5000

print("\n=== 6. TEST DB PERSISTENCE & PRAGMAS ===")
conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute("PRAGMA integrity_check;")
assert c.fetchall() == [('ok',)]
c.execute("PRAGMA foreign_key_check;")
assert c.fetchall() == []
c.execute("SELECT * FROM salary_configs WHERE user_id = 38;")
print("DB row in salary_configs:", c.fetchone())
conn.close()

print("\nALL BACKEND & API TESTS PASSED SUCCESSFULLY!")
