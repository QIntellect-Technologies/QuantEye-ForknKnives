import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import database as db

db.init_db()

conn = sqlite3.connect('attendance.db')
c = conn.cursor()

# Test what date(timestamp, 'localtime') returns for f"{target_date} 09:00:00"
target_date = "2026-10-05"
c.execute("SELECT date(?, 'localtime'), datetime(?, 'localtime')", (f"{target_date} 09:00:00", f"{target_date} 09:00:00"))
row = c.fetchone()
print(f"For '{target_date} 09:00:00': date={row[0]}, datetime={row[1]}")

# Test what happens when mark_user_present_today(46, '2026-10-05') is called:
res = db.mark_user_present_today(46, '2026-10-05')
print("mark_user_present_today(46, '2026-10-05') returned:", res)

# Check if user 46 is now found in attendance for 2026-10-05
c.execute("SELECT id, user_id, timestamp, date(timestamp, 'localtime') FROM attendance WHERE user_id = 46")
rows = c.fetchall()
print("Attendance rows for 46:", rows)

# Check report for 2026-10-05
rep = db.get_detailed_attendance_report(target_date='2026-10-05')
rec = [r for r in rep['records'] if r['user_id'] == 46][0]
print("Report record for 46 on 2026-10-05:", rec['status'], rec['first_seen'], rec['date'])
