import sys
sys.path.insert(0, r'd:\QIntellect-AI-Attendence-11-9-2026\Final-AI-Attendence-System\Final-AI-Attendence-System\Flask-Attedence')
import database as db
import sqlite3

with sqlite3.connect('attendance.db') as conn:
    c = conn.cursor()
    c.execute("INSERT INTO users (name, department, active, join_date) VALUES ('ZTest', 'Test', 1, '2026-10-01')")
    uid = c.lastrowid
    c.execute("INSERT INTO attendance (user_id, source, timestamp) VALUES (?, 'manual', '2026-10-12 08:05:00')", (uid,))
    conn.commit()

report = db.get_detailed_attendance_report('2026-10-12', '2026-10-12')
for r in report['records']:
    if r['user_id'] == uid:
        print(r['daily_records'][0]['status_display'])
        print(r['daily_records'][0])

with sqlite3.connect('attendance.db') as conn:
    c = conn.cursor()
    c.execute("DELETE FROM attendance WHERE user_id = ?", (uid,))
    c.execute("DELETE FROM employee_shift_history WHERE user_id = ?", (uid,))
    c.execute("DELETE FROM employee_leave_balances WHERE user_id = ?", (uid,))
    c.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.commit()
