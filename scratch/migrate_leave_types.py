import sqlite3

with sqlite3.connect('attendance.db') as conn:
    c = conn.cursor()
    c.execute('PRAGMA table_info(leave_types)')
    cols = [col[1] for col in c.fetchall()]
    print('Current cols:', cols)
    if 'allowance_period' not in cols:
        c.execute("ALTER TABLE leave_types ADD COLUMN allowance_period TEXT DEFAULT 'yearly'")
        conn.commit()
        print('Added allowance_period column to leave_types')
    else:
        print('allowance_period already exists')
