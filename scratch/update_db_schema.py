import sqlite3
import os

DB_PATH = 'attendance.db'

def update_schema():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('ALTER TABLE attendance ADD COLUMN notes TEXT DEFAULT ""')
    except Exception as e:
        print(e)
    
    try:
        c.execute('ALTER TABLE attendance ADD COLUMN marked_by TEXT DEFAULT "System"')
    except Exception as e:
        print(e)
    
    # Check what columns exist in attendance
    c.execute("PRAGMA table_info(attendance)")
    print(c.fetchall())
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    update_schema()
