import sqlite3

conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute("SELECT * FROM shifts WHERE id = 1;")
print("Shift 1:", c.fetchone())
c.execute("SELECT shift_id, start_time, end_time, grace_period_minutes, working_days FROM employee_shift_history WHERE user_id = 38;")
print("Imran shift history:", c.fetchall())
conn.close()
