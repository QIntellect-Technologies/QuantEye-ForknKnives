import sys
sys.path.insert(0, ".")
import database as db
import sqlite3

conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute("PRAGMA foreign_keys = ON")
c.execute("DELETE FROM users WHERE id IN (127, 129)")
conn.commit()
c.execute("SELECT count(*) FROM users WHERE active = 1")
count = c.fetchone()[0]
conn.close()
print("Active users in attendance.db:", count)
