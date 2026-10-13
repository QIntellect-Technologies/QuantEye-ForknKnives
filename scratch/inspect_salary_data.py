import sqlite3
conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger' AND (tbl_name='salary_configs' OR sql LIKE '%salary_configs%')")
rows = c.fetchall()
print(f"Triggers: {rows}")

# Check foreign key check
c.execute("PRAGMA foreign_key_check;")
fk = c.fetchall()
print(f"FK check: {fk}")

# Check current users count and salary summary
c.execute("SELECT count(*), count(salary), avg(salary), min(salary), max(salary) FROM users WHERE active=1;")
print(f"Users stats: {c.fetchone()}")

# Check sample users
c.execute("SELECT id, name, department, position, salary FROM users WHERE active=1 LIMIT 5;")
for r in c.fetchall():
    print(f"User: {r}")

conn.close()
