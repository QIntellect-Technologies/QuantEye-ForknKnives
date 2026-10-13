import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import database as db

db.init_db()

conn = sqlite3.connect('attendance.db')
c = conn.cursor()

c.execute("SELECT date('now'), date('now', 'localtime'), datetime('now'), datetime('now', 'localtime')")
print("Dates:", c.fetchone())

# Check recent attendance entries
c.execute("SELECT id, user_id, detected_name, confidence, source, timestamp FROM attendance ORDER BY id DESC LIMIT 5")
print("\nRecent attendance:")
for r in c.fetchall():
    print(r)

# Check manual_absent
c.execute("SELECT user_id, date, created_at FROM manual_absent")
print("\nManual absent:")
for r in c.fetchall():
    print(r)
