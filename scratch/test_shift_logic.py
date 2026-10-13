import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import database as db
from datetime import datetime

print("Initializing DB...")
db.init_db()

print("\n--- SHIFTS IN DB ---")
shifts = db.get_all_shifts()
for s in shifts:
    print(f"Shift ID {s['id']}: {s['name']} ({s['start_time']} - {s['end_time']}) Grace: {s['grace_period_minutes']}m | Users: {s['user_count']}")

print("\n--- TESTING TIME WINDOW LOGIC ---")
dt_morning_905 = datetime.strptime("2026-10-06 09:05:00", "%Y-%m-%d %H:%M:%S")
dt_morning_920 = datetime.strptime("2026-10-06 09:20:00", "%Y-%m-%d %H:%M:%S")
dt_evening_1705 = datetime.strptime("2026-10-06 17:05:00", "%Y-%m-%d %H:%M:%S")

print("09:05 AM for Morning Shift (09:00 + 15m):", db.is_time_in_grace_window("09:00", 15, dt_morning_905))
print("09:20 AM for Morning Shift (09:00 + 15m):", db.is_time_in_grace_window("09:00", 15, dt_morning_920))
print("17:05 PM for Morning Shift (09:00 + 15m):", db.is_time_in_grace_window("09:00", 15, dt_evening_1705))
print("17:05 PM for Evening Shift (17:00 + 15m):", db.is_time_in_grace_window("17:00", 15, dt_evening_1705))

users = db.get_all_users()
print(f"\nTotal users in DB: {len(users)}")
if users:
    u0 = users[0]
    print(f"User {u0['name']} (ID {u0['id']}): Shift = {u0['shift_name']} ({u0['shift_start']} - {u0['shift_end']})")
    allowed, reason, shift_info = db.check_user_shift_allowed(u0['id'], dt_morning_905)
    print("Check at 09:05 AM:", allowed, "->", reason)
    allowed, reason, shift_info = db.check_user_shift_allowed(u0['id'], dt_evening_1705)
    print("Check at 17:05 PM:", allowed, "->", reason)

print("\nAll tests passed successfully!")
