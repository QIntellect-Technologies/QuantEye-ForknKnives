import sqlite3

conn = sqlite3.connect('attendance.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = [r[0] for r in c.fetchall()]
print(f"Total tables: {len(tables)}")
for t in tables:
    c.execute(f"PRAGMA table_info('{t}');")
    cols = [f"{col[1]} ({col[2]})" for col in c.fetchall()]
    print(f"\nTABLE: {t}")
    print("  Columns:", ", ".join(cols))
    c.execute(f"PRAGMA foreign_key_list('{t}');")
    fks = c.fetchall()
    if fks:
        print("  Foreign Keys:")
        for fk in fks:
            print(f"    -> from {fk[3]} to {fk[2]}({fk[4]}) ON DELETE {fk[6]}")

c.execute("PRAGMA integrity_check;")
print("\nPRAGMA integrity_check:", c.fetchall())

c.execute("PRAGMA foreign_key_check;")
print("PRAGMA foreign_key_check:", c.fetchall())

conn.close()
