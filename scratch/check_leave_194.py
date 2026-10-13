import sqlite3

with sqlite3.connect("attendance.db") as conn:
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("PRAGMA table_info(leave_requests)")
    cols = [col["name"] for col in c.fetchall()]
    print("leave_requests columns:", cols)

    c.execute("SELECT * FROM leave_requests WHERE id = 194")
    row = c.fetchone()
    if row:
        print("Leave request 194:", dict(row))
    else:
        print("Leave request 194 not found!")

    c.execute("SELECT * FROM leave_requests ORDER BY id DESC LIMIT 5")
    rows = c.fetchall()
    print("Latest 5 leave requests:")
    for r in rows:
        print(dict(r))

    c.execute("SELECT id, name FROM users WHERE name LIKE '%Qaisar%' OR name LIKE '%Shaheen%' OR name LIKE '%Shahen%'")
    users = c.fetchall()
    print("Matching users:")
    for u in users:
        print(dict(u))

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%leave%'")
    tables = c.fetchall()
    print("Leave tables:", [dict(t) for t in tables])
