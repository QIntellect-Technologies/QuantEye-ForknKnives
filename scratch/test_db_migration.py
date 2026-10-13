import sqlite3

conn = sqlite3.connect('attendance.db')
cursor = conn.cursor()

payroll_record_columns = {row[1] for row in cursor.execute("PRAGMA table_info(payroll_records)")}
new_cols = [
    ("allowances", "REAL NOT NULL DEFAULT 0.0"),
    ("custom_deductions", "REAL NOT NULL DEFAULT 0.0"),
    ("overtime_hours", "REAL NOT NULL DEFAULT 0.0"),
    ("overtime_rate", "REAL NOT NULL DEFAULT 0.0"),
    ("overtime_amount", "REAL NOT NULL DEFAULT 0.0"),
    ("gross_salary", "REAL NOT NULL DEFAULT 0.0"),
]
for col, ctype in new_cols:
    if col not in payroll_record_columns:
        print(f"Adding column {col} to payroll_records...")
        cursor.execute(f"ALTER TABLE payroll_records ADD COLUMN {col} {ctype}")

payroll_run_columns = {row[1] for row in cursor.execute("PRAGMA table_info(payroll_runs)")}
run_cols = [
    ("total_allowances", "REAL NOT NULL DEFAULT 0.0"),
    ("total_overtime", "REAL NOT NULL DEFAULT 0.0")
]
for col, ctype in run_cols:
    if col not in payroll_run_columns:
        print(f"Adding column {col} to payroll_runs...")
        cursor.execute(f"ALTER TABLE payroll_runs ADD COLUMN {col} {ctype}")

conn.commit()

cursor.execute("PRAGMA integrity_check;")
print("integrity_check:", cursor.fetchall())
cursor.execute("PRAGMA foreign_key_check;")
print("foreign_key_check:", cursor.fetchall())

conn.close()
print("Migration completed successfully!")
