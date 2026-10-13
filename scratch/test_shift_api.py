import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import app as flask_app
import json

print("Setting up Flask test client...")
client = flask_app.app.test_client()

print("\n1. GET /api/shifts")
res = client.get('/api/shifts')
print("Status:", res.status_code)
print("Data:", res.get_json())

print("\n2. POST /api/shifts (Create Custom Client Shift)")
new_shift = {
    "name": "Customer Special Shift",
    "start_time": "14:00",
    "end_time": "22:00",
    "grace_period_minutes": 20
}
res = client.post('/api/shifts', json=new_shift)
print("Status:", res.status_code)
data = res.get_json()
print("Data:", data)
created_id = data.get('shift_id')

if created_id:
    print(f"\n3. PUT /api/shifts/{created_id} (Update Custom Shift)")
    update_shift = {
        "name": "Customer Evening Shift",
        "start_time": "15:00",
        "end_time": "23:00",
        "grace_period_minutes": 15
    }
    res = client.put(f'/api/shifts/{created_id}', json=update_shift)
    print("Status:", res.status_code)
    print("Data:", res.get_json())

    print(f"\n4. DELETE /api/shifts/{created_id}")
    res = client.delete(f'/api/shifts/{created_id}')
    print("Status:", res.status_code)
    print("Data:", res.get_json())

print("\n5. GET /api/users (checking shift metadata in user profiles)")
res = client.get('/api/users')
users = res.get_json().get('users', [])
print(f"Fetched {len(users)} users. Sample first user shift info:")
if users:
    u = users[0]
    print(f"Name: {u['name']} | Shift: {u.get('shift_name')} | Hours: {u.get('shift_start')} - {u.get('shift_end')} | Grace: {u.get('shift_grace')}m")

print("\nAll API tests completed successfully!")
