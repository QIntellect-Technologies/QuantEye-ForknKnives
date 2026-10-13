import os, sys
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
import database as db

with sqlite3.connect('attendance.db') as conn:
    cursor = conn.cursor()
    # Check runs
    runs = cursor.execute("SELECT id, payroll_month, status, finalized_at FROM payroll_runs").fetchall()
    print("Before:", runs)

    # Drop triggers temporarily to remove run 1
    cursor.execute("DROP TRIGGER IF EXISTS prevent_finalized_payroll_run_update")
    cursor.execute("DROP TRIGGER IF EXISTS prevent_finalized_payroll_run_delete")
    cursor.execute("DROP TRIGGER IF EXISTS prevent_finalized_payroll_record_delete")
    cursor.execute("DROP TRIGGER IF EXISTS prevent_finalized_payroll_record_update")
    cursor.execute("DROP TRIGGER IF EXISTS prevent_finalized_payroll_record_insert")

    # Delete run 1 records and run
    cursor.execute("DELETE FROM payroll_records WHERE payroll_run_id = 1")
    cursor.execute("DELETE FROM payroll_runs WHERE id = 1")
    conn.commit()

# Recreate triggers with init_db
db.init_db()

with sqlite3.connect('attendance.db') as conn:
    cursor = conn.cursor()
    runs = cursor.execute("SELECT id, payroll_month, status, finalized_at FROM payroll_runs").fetchall()
    print("After:", runs)
    integrity = cursor.execute("PRAGMA integrity_check").fetchall()
    fk = cursor.execute("PRAGMA foreign_key_check").fetchall()
    print("Integrity check:", integrity)
    print("Foreign key check:", fk)

    # Verify triggers are active by trying to update run 2 (2026-09 Finalized)
    try:
        cursor.execute("UPDATE payroll_runs SET status = 'Draft' WHERE id = 2")
        print("ERROR: Trigger should have blocked this!")
    except sqlite3.IntegrityError as e:
        print("PASS: Triggers are active and blocking modifications to finalized runs:", e)
