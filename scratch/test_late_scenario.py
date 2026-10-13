import sys
sys.path.insert(0, ".")
import sqlite3
import database as db

TEST_USER_ID = 38
TEST_USER_NAME = "Imran Khalid"
TEST_DATE = "2026-10-13"

# Insert check-in at 10:35:00 (after 10:31 + 2 min grace period = 10:33)
with sqlite3.connect('attendance.db') as conn:
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE user_id = ? AND date(timestamp) = ?;", (TEST_USER_ID, TEST_DATE))
    c.execute(
        "INSERT INTO attendance (user_id, detected_name, confidence, source, location, device_id, timestamp) "
        "VALUES (?, ?, 1.0, 'manual', 'Main Entrance', 'cam_manual_test', ?)",
        (TEST_USER_ID, TEST_USER_NAME, f"{TEST_DATE} 10:35:00")
    )
    conn.commit()

rep = db.get_detailed_attendance_report(start_date=TEST_DATE, end_date=TEST_DATE)
emp = next((r for r in rep.get('records', []) if r.get('user_id') == TEST_USER_ID), None)
daily = emp.get('daily_records', [{}])[0] if emp else {}
print("Check-in 10:35:00 Status:", daily.get('status'))
print("First seen:", daily.get('first_seen'))

# Clean up
with sqlite3.connect('attendance.db') as conn:
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE user_id = ? AND date(timestamp) = ?;", (TEST_USER_ID, TEST_DATE))
    conn.commit()
