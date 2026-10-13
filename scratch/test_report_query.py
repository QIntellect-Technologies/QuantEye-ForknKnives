import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import database as db

rep = db.get_detailed_attendance_report(target_date='today')
print("Report Summary:", rep['summary'])
imran_rec = [r for r in rep['records'] if r['user_id'] == 38]
print("Imran record:", imran_rec)

conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute("SELECT * FROM attendance WHERE user_id = 38 AND date(timestamp, 'localtime') = date('now', 'localtime')")
print("Attendance logs today for 38:", c.fetchall())

c.execute("SELECT * FROM manual_absent WHERE user_id = 38 AND date = date('now', 'localtime')")
print("Manual absent for 38 today:", c.fetchall())
