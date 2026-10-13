import sys
import sqlite3

sys.path.insert(0, r"d:\QIntellect-AI-Attendence-11-9-2026\Final-AI-Attendence-System\Final-AI-Attendence-System\Flask-Attedence")

DB_PATH = r"d:\QIntellect-AI-Attendence-11-9-2026\Final-AI-Attendence-System\Final-AI-Attendence-System\Flask-Attedence\attendance.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("=== 1. Saved payroll runs for 2026-10 ===")
cursor.execute("SELECT id, payroll_month, status, is_finalized FROM payroll_runs WHERE payroll_month = '2026-10'")
rows = cursor.fetchall()
print("  Rows:", rows)

print("\n=== 2. Imran (ID=38) Oct 1-8 attendance ===")
cursor.execute("SELECT date(timestamp), COUNT(*) FROM attendance WHERE user_id=38 AND date(timestamp) BETWEEN '2026-10-01' AND '2026-10-08' GROUP BY date(timestamp)")
print("  Attendance records:", cursor.fetchall())

print("\n=== 3. Imran shift working_days ===")
cursor.execute("SELECT id, name, working_days, start_time FROM shifts WHERE id = (SELECT shift_id FROM users WHERE id=38)")
print("  Shift:", cursor.fetchall())

print("\n=== 4. Imran leaves in Oct 2026 ===")
cursor.execute("SELECT id, leave_type, start_date, end_date, status FROM leave_requests WHERE user_id=38 AND start_date >= '2026-10-01'")
print("  Leaves:", cursor.fetchall())

print("\n=== 5. What day of week is 2026-10-02 and 2026-10-03? ===")
cursor.execute("SELECT strftime('%w', '2026-10-02'), strftime('%A', '2026-10-02')")
print("  Oct 2:", cursor.fetchone())
cursor.execute("SELECT strftime('%w', '2026-10-03'), strftime('%A', '2026-10-03')")
print("  Oct 3:", cursor.fetchone())
# 0=Sunday, 1=Monday ... 6=Saturday

print("\n=== 6. Payroll table schema ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%payroll%'")
print("  Tables:", cursor.fetchall())

conn.close()
