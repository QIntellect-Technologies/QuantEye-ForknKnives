import sqlite3
conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name LIKE '%locat%'")
rows = c.fetchall()
for r in rows:
    print(r[0])
conn.close()
