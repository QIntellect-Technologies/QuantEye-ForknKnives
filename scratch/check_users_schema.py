import sqlite3
conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute("SELECT id, name, email FROM users WHERE id > 100")
print("Users with id > 100:", c.fetchall())
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
print("Users schema:", c.fetchone()[0])
