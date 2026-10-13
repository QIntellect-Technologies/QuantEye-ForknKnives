import sqlite3
DB_PATH = 'attendance.db'

def update_schema():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('ALTER TABLE users ADD COLUMN exit_date TEXT')
    except Exception as e:
        print(e)
    conn.commit()
    conn.close()
    print("Schema updated for users table")

if __name__ == '__main__':
    update_schema()
