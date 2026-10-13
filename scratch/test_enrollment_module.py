import sys
sys.path.insert(0, ".")
import os
import sqlite3
import numpy as np
import cv2
from datetime import datetime
import database as db
from app import app, _ADMIN_CONFIG_PASSWORD

client = app.test_client()

print("=======================================================")
print("  DIAGNOSTIC TEST: STAFF ENROLLMENT & ADMIN SECURITY   ")
print("=======================================================")

# 1. Test Admin Security Gate
res_status1 = client.get('/api/admin/status')
print("Initial Admin Status:", res_status1.get_json())

# 2. Try creating user without enabling enrollment -> Should be 403 Forbidden
res_blocked = client.post('/api/enroll/create-user', json={'name': 'Test Blocked User'})
print(f"Blocked Create User without auth: HTTP {res_blocked.status_code} - {res_blocked.get_json()}")

# 3. Test wrong password
res_wrong_pw = client.post('/api/admin/verify-password', json={'password': 'wrongpassword123'})
print(f"Wrong Admin Password: HTTP {res_wrong_pw.status_code} - {res_wrong_pw.get_json()}")

# 4. Test correct password
res_correct_pw = client.post('/api/admin/verify-password', json={'password': _ADMIN_CONFIG_PASSWORD})
print(f"Correct Admin Password: HTTP {res_correct_pw.status_code} - {res_correct_pw.get_json()}")

# 5. Enable enrollment
res_enable = client.post('/api/admin/enable-enrollment')
print(f"Enable Enrollment: HTTP {res_enable.status_code} - {res_enable.get_json()}")

# 6. Check Admin Status after enable
res_status2 = client.get('/api/admin/status')
print("Admin Status after enable:", res_status2.get_json())

# 7. Create Test User via /api/enroll/create-user
test_name = f"Enroll Test User {int(datetime.now().timestamp())}"
res_create = client.post('/api/enroll/create-user', json={
    'name': test_name,
    'email': f"test_{int(datetime.now().timestamp())}@qintellect.test",
    'phone': '0300-1122334',
    'department': 'AI & Data Science',
    'position': 'Research Fellow',
    'cnic': '35202-9999999-1',
    'salary': 65000,
    'shift_id': 1,
    'checkin_cameras': 'all',
    'checkout_cameras': 'all'
})
print(f"Create User via /api/enroll/create-user: HTTP {res_create.status_code} - {res_create.get_json()}")
cdata = res_create.get_json() if res_create.is_json else {}
new_user_id = cdata.get('user_id')

# 8. Check status before video/embedding upload
if new_user_id:
    res_st1 = client.get(f'/api/enroll/status/{new_user_id}')
    print(f"Status before embeddings: HTTP {res_st1.status_code} - {res_st1.get_json()}")

    # 9. Clean up test user so DB doesn't have junk
    db.delete_user(new_user_id)
    print(f"Cleaned up test user #{new_user_id}")

# 10. Disable enrollment
res_disable = client.post('/api/admin/disable-enrollment')
print(f"Disable Enrollment: HTTP {res_disable.status_code} - {res_disable.get_json()}")

# 11. Lock admin
res_lock = client.post('/api/admin/lock')
print(f"Lock Admin: HTTP {res_lock.status_code} - {res_lock.get_json()}")

# 12. Final Admin Status
res_status3 = client.get('/api/admin/status')
print("Final Admin Status:", res_status3.get_json())
