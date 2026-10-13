import sqlite3
conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name IN ('embeddings', 'salary_configs', 'employee_shift_history')")
for name, sql in c.fetchall():
    print(f"=== {name} ===")
    print(sql)
