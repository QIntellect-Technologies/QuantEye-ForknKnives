import sqlite3
conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()
cursor.execute("SELECT id, timestamp, typeof(timestamp), date(timestamp) FROM attendance WHERE user_id = 38 ORDER BY id DESC LIMIT 10")
for r in cursor.fetchall():
    print(r)
