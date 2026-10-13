import sqlite3

conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [r[0] for r in cursor.fetchall()]
print(f"Total tables: {len(tables)}")
for t in tables:
    cursor.execute(f"SELECT count(*) FROM [{t}]")
    count = cursor.fetchone()[0]
    print(f"  - {t}: {count} rows")
conn.close()
