import sqlite3

conn = sqlite3.connect('attendance.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 80)
print("1. SHIFT TABLES IN SQLITE:")
print("=" * 80)
for r in cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND (name LIKE '%shift%' OR name='users')"):
    print(f"Table: {r['name']}")
    print(r['sql'])
    print("-" * 50)

print("\n2. EXISTING SHIFT ROWS in 'shifts':")
for r in cur.execute("SELECT * FROM shifts"):
    print(dict(r))

print("\n3. EXISTING SHIFT HISTORY ROWS in 'employee_shift_history' (sample 10):")
try:
    for r in cur.execute("SELECT * FROM employee_shift_history LIMIT 10"):
        print(dict(r))
    cnt = cur.execute("SELECT COUNT(*) FROM employee_shift_history").fetchone()[0]
    print(f"Total shift history rows: {cnt}")
except Exception as e:
    print(f"Error querying employee_shift_history: {e}")

print("\n4. USERS SHIFT_ID DISTRIBUTION:")
for r in cur.execute("SELECT shift_id, COUNT(*) as cnt FROM users GROUP BY shift_id"):
    print(dict(r))

conn.close()
