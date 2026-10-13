import sqlite3
from app import db

# Dry run / inspection of request 194
with sqlite3.connect("attendance.db") as conn:
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM leave_requests WHERE id = 194")
    req = dict(c.fetchone())
    print("Current Leave Request 194:", req)

    c.execute("SELECT * FROM leave_types WHERE code = ?", (req['leave_type'],))
    lt = dict(c.fetchone())
    print("Leave Type:", lt)

# Let's temporarily approve in transaction or check what get_detailed_attendance_report does
with sqlite3.connect("attendance.db") as conn:
    c = conn.cursor()
    c.execute("UPDATE leave_requests SET status = 'approved', approved_by = 'Admin' WHERE id = 194")
    conn.commit()

rep = db.get_detailed_attendance_report(start_date='2026-10-08', end_date='2026-10-17')
emp41 = next((r for r in rep.get('records', []) if r.get('user_id') == 41), None)

print("\n--- ATTENDANCE REPORT FOR USER 41 (2026-10-08 to 2026-10-17) ---")
if emp41:
    print(f"Total days: {emp41.get('total_days')}, Present: {emp41.get('present_days')}, Leave: {emp41.get('leave_days')}, Absent: {emp41.get('absent_days')}")
    for d in emp41.get('daily_records', []):
        print(f"  {d.get('date')} ({d.get('day')}): status={d.get('status')}, scheduled={d.get('scheduled_workday')}")
else:
    print("User 41 not found in report!")

pay = db.calculate_monthly_payroll('2026-10')
emp41_pay = next((r for r in pay.get('records', []) if r.get('employee_id') == 41), None)
print("\n--- PAYROLL PREVIEW FOR USER 41 (OCTOBER 2026) ---")
if emp41_pay:
    print(f"Basic: {emp41_pay.get('basic_salary')}, Scheduled workdays: {emp41_pay.get('scheduled_workdays')}")
    print(f"Present: {emp41_pay.get('present_days')}, Approved Leave: {emp41_pay.get('approved_leave_days')}, Absent: {emp41_pay.get('absent_days')}, Payable: {emp41_pay.get('payable_days')}")
    print(f"Deduction Amount: {emp41_pay.get('deduction_amount')}, Net: {emp41_pay.get('net_salary')}")
