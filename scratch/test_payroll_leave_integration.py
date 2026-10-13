"""
FINAL LEAVE -> PAYROLL REGRESSION TEST (v3)
Uses a temporary copy of the production DB to bypass finalized payroll immutability.
Steps:
1. Copy attendance.db to a temp file
2. In the temp DB: delete the finalized payroll_runs record (no trigger blocks DELETE on non-Finalized? 
   Wait — triggers block DELETE when status='Finalized'. So we must drop/recreate the trigger
   or use a different DB path in db module.
3. Actually we just override db.DB_PATH in the module to point to temp DB,
   manipulate the temp copy freely, run calculation, then discard.
"""
import sys
import os
import shutil
import sqlite3
import tempfile
from datetime import date, timedelta

sys.path.insert(0, r"d:\QIntellect-AI-Attendence-11-9-2026\Final-AI-Attendence-System\Final-AI-Attendence-System\Flask-Attedence")

PROD_DB = r"d:\QIntellect-AI-Attendence-11-9-2026\Final-AI-Attendence-System\Final-AI-Attendence-System\Flask-Attedence\attendance.db"
UID = 38
UNAME = "Imran Khalid"
TEST_MONTH = "2026-10"


def setup_test_db(temp_db_path, leave_dates_paid=None, leave_dates_unpaid=None):
    """Copy prod DB to temp, remove finalized payroll run, insert test leaves."""
    shutil.copy2(PROD_DB, temp_db_path)
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.cursor()

    # Drop immutability triggers in the temp DB
    cursor.execute("DROP TRIGGER IF EXISTS prevent_finalized_payroll_run_update")
    cursor.execute("DROP TRIGGER IF EXISTS prevent_finalized_payroll_run_delete")
    # Remove finalized payroll run for the test month
    cursor.execute("DELETE FROM payroll_runs WHERE payroll_month = ?", (TEST_MONTH,))

    # Clean any existing test leaves
    cursor.execute("DELETE FROM leave_requests WHERE reason LIKE 'REGTEST_%'")

    # Insert requested test leaves
    if leave_dates_paid:
        for d in leave_dates_paid:
            cursor.execute("""
                INSERT INTO leave_requests (user_id, user_name, leave_type, start_date, end_date, reason, status, approved_by)
                VALUES (?, ?, 'casual', ?, ?, 'REGTEST_paid', 'approved', 'AuditSystem')
            """, (UID, UNAME, d, d))

    if leave_dates_unpaid:
        for d in leave_dates_unpaid:
            cursor.execute("""
                INSERT INTO leave_requests (user_id, user_name, leave_type, start_date, end_date, reason, status, approved_by)
                VALUES (?, ?, 'unpaid', ?, ?, 'REGTEST_unpaid', 'approved', 'AuditSystem')
            """, (UID, UNAME, d, d))

    conn.commit()
    conn.close()


def run_scenario(label, leave_dates_paid=None, leave_dates_unpaid=None):
    """Run payroll calculation against a fresh temp DB copy with controlled leave data."""
    import database as db

    tmpdir = tempfile.mkdtemp()
    temp_db = os.path.join(tmpdir, "test_payroll.db")
    try:
        setup_test_db(temp_db, leave_dates_paid=leave_dates_paid, leave_dates_unpaid=leave_dates_unpaid)

        # Point db module to temp DB for this call
        original_db_path = db.DB_PATH
        db.DB_PATH = temp_db

        try:
            result = db.calculate_monthly_payroll(TEST_MONTH)
        finally:
            db.DB_PATH = original_db_path

        emp = next(
            (r for r in result.get('records', []) if r.get('employee_id') == UID or r.get('employee_name') == UNAME),
            None
        )

        print(f"\n{'='*65}")
        print(f"  SCENARIO: {label}")
        print(f"{'='*65}")
        if emp:
            print(f"  Employee            : {emp.get('employee_name')} (ID={UID})")
            print(f"  Payroll Month       : {TEST_MONTH}")
            print(f"  Basic Salary        : PKR {emp.get('basic_salary', 0):,.2f}")
            print(f"  Scheduled Work Days : {emp.get('scheduled_workdays')}")
            print(f"  Present Days        : {emp.get('present_days')}")
            print(f"  Late Days           : {emp.get('late_days')}")
            print(f"  Absent Days         : {emp.get('absent_days')}")
            print(f"  Approved Leave Days : {emp.get('approved_leave_days')}")
            print(f"  Payable Days        : {emp.get('payable_days')}")
            print(f"  Matched Rule        : {emp.get('matched_rule')}")
            print(f"  Deduction Type      : {emp.get('deduction_type')}")
            print(f"  Deduction Amount    : PKR {emp.get('deduction_amount', 0):,.2f}")
            print(f"  Net Salary          : PKR {emp.get('net_salary', 0):,.2f}")
            print(f"  Status              : {emp.get('status')}")
            return emp
        else:
            print(f"  [ERROR] Employee record not found!")
            return None
    except Exception as e:
        import traceback
        print(f"\n  [EXCEPTION in {label}]: {e}")
        traceback.print_exc()
        return None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    print("=" * 65)
    print("  PRE-FLIGHT: AVAILABLE TEST LEAVE DATES")
    print("=" * 65)

    conn = sqlite3.connect(PROD_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date(timestamp) FROM attendance WHERE user_id=?
        AND date(timestamp) BETWEEN '2026-10-01' AND '2026-10-08'
        GROUP BY date(timestamp)
    """, (UID,))
    attended = set(r[0] for r in cursor.fetchall())
    cursor.execute("SELECT working_days FROM shifts WHERE id=(SELECT shift_id FROM users WHERE id=?)", (UID,))
    row = cursor.fetchone()
    working_codes = set(row[0].split(',')) if row else set()
    conn.close()

    print(f"  Attended dates      : {sorted(attended)}")
    print(f"  Working day codes   : {working_codes} (0=Sun,1=Mon,2=Tue,3=Wed,4=Thu,5=Fri,6=Sat)")

    # Find working days with no attendance
    # SQLite weekday: strftime('%w') returns 0=Sun,1=Mon,...6=Sat
    # Python weekday(): 0=Mon,...6=Sun → convert: (weekday+1)%7 for SQLite-style
    free_days = []
    for i in range(31):
        d = date(2026, 10, 1) + timedelta(days=i)
        if d > date.today():
            break
        python_dow = str(d.weekday())  # 0=Mon, ... 5=Sat, 6=Sun
        # We need a working day that is not a company holiday and not attended
        if python_dow in working_codes and d.isoformat() not in attended:
            if d.isoformat() not in ['2026-10-01', '2026-10-06']: # Hardcode skip holidays for test
                free_days.append(d.isoformat())

    print(f"  Free working days   : {free_days}")

    if len(free_days) < 2:
        print("\n  [ABORT] Not enough free working days without attendance to test leave integration.")
        print("  This means there are attendance records on all working days tested so far.")
        return

    leave_day_1 = free_days[0]
    leave_day_2 = free_days[1]
    print(f"  Test leave dates    : {leave_day_1} and {leave_day_2}")

    # Run the 3 scenarios
    r1 = run_scenario("1. NO LEAVE (Baseline)")
    r2 = run_scenario("2. APPROVED PAID LEAVE (2 Days)", leave_dates_paid=[leave_day_1, leave_day_2])
    r3 = run_scenario("3. APPROVED UNPAID LEAVE (2 Days)", leave_dates_unpaid=[leave_day_1, leave_day_2])

    # Print verdict
    print(f"\n{'='*65}")
    print("  INTEGRATION VERDICT")
    print(f"{'='*65}")

    if r1 and r2 and r3:
        paid_leave_detected = (r2.get('approved_leave_days', 0) > r1.get('approved_leave_days', 0))
        unpaid_leave_as_absent = (r3.get('absent_days', 0) > r1.get('absent_days', 0))
        paid_no_extra_deduction = (r2.get('deduction_amount', 0) == r1.get('deduction_amount', 0))
        unpaid_affects_payroll = (r3.get('net_salary', 0) != r1.get('net_salary', 0) or r3.get('absent_days', 0) > 0)

        print(f"  Paid leave detected in payroll     : {'PASS' if paid_leave_detected else 'FAIL'}")
        print(f"  Paid leave causes no extra deduction: {'PASS' if paid_no_extra_deduction else 'FAIL'}")
        print(f"  Unpaid leave counted as absent     : {'PASS' if unpaid_leave_as_absent else 'FAIL'}")
        print(f"  Unpaid leave affects payroll       : {'PASS' if unpaid_affects_payroll else 'FAIL'}")
        overall = paid_leave_detected and paid_no_extra_deduction and unpaid_leave_as_absent and unpaid_affects_payroll
        print(f"\n  OVERALL LEAVE->PAYROLL INTEGRATION: {'*** PASS ***' if overall else '*** FAIL ***'}")
    else:
        print("  Could not run all scenarios. Check errors above.")

    print()


if __name__ == '__main__':
    main()
