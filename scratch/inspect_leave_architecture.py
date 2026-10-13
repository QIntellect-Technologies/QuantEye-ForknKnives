import sqlite3

with sqlite3.connect("attendance.db") as conn:
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("--- LEAVE TYPES ---")
    c.execute("SELECT * FROM leave_types")
    for r in c.fetchall():
        print(dict(r))

    print("\n--- LEAVE BALANCES FOR USER 41 ---")
    c.execute("SELECT * FROM employee_leave_balances WHERE user_id = 41")
    for r in c.fetchall():
        print(dict(r))

    print("\n--- ALL LEAVE BALANCES ---")
    c.execute("SELECT * FROM employee_leave_balances LIMIT 10")
    for r in c.fetchall():
        print(dict(r))
