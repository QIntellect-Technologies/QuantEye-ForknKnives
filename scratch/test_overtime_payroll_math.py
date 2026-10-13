import os, sys
sys.path.insert(0, os.path.abspath('.'))
import sqlite3
import database as db

# Test Employee ID 38 (Imran Khalid)
TEST_USER_ID = 38

print("=== TESTING OVERTIME & SALARY PAYROLL INTEGRATION ===")

# Save current salary config for Imran Khalid to restore later
orig_cfg = db.get_salary_config(TEST_USER_ID)
print(f"Original salary config: {orig_cfg}")

try:
    # Set salary config according to prompt baseline example:
    # Basic Salary = PKR 250,000
    # Allowances = PKR 35,000
    # Fixed Deductions = PKR 10,000
    # OT Rate = PKR 1,201.92
    db.set_salary_config(
        user_id=TEST_USER_ID,
        basic_salary=250000.0,
        allowances=35000.0,
        deductions=10000.0,
        ot_rate=1201.92
    )
    
    # Clean any prior test overtime for Imran Khalid
    with sqlite3.connect('attendance.db') as conn:
        conn.execute("DELETE FROM overtime WHERE user_id = ? AND ot_date IN ('2026-10-15', '2026-10-16', '2026-10-17')", (TEST_USER_ID,))
        conn.commit()

    # 1. Add 3.0 hours approved overtime
    ot_appr_id = db.add_overtime(
        user_id=TEST_USER_ID,
        user_name='Imran Khalid',
        ot_date='2026-10-15',
        hours=3.0,
        reason='Production deployment'
    )
    db.update_overtime_status(ot_appr_id, status='approved', approved_by='Admin')

    # 2. Add 2.0 hours pending overtime (MUST BE EXCLUDED)
    ot_pend_id = db.add_overtime(
        user_id=TEST_USER_ID,
        user_name='Imran Khalid',
        ot_date='2026-10-16',
        hours=2.0,
        reason='Pending task'
    )
    # status is 'pending' by default

    # 3. Add 4.0 hours rejected overtime (MUST BE EXCLUDED)
    ot_rej_id = db.add_overtime(
        user_id=TEST_USER_ID,
        user_name='Imran Khalid',
        ot_date='2026-10-17',
        hours=4.0,
        reason='Rejected task'
    )
    db.update_overtime_status(ot_rej_id, status='rejected', approved_by='Admin')

    # Now calculate payroll for 2026-10
    payroll = db.calculate_monthly_payroll('2026-10')
    imran_rec = next((r for r in payroll.get('records', []) if r.get('employee_id') == TEST_USER_ID), None)

    assert imran_rec is not None, "Imran Khalid record missing from payroll!"
    print(f"\nPayroll record for Imran Khalid:")
    print(f"  Basic Salary: PKR {imran_rec.get('basic_salary')}")
    print(f"  Allowances: PKR {imran_rec.get('allowances')}")
    print(f"  Overtime Hours: {imran_rec.get('overtime_hours')}")
    print(f"  Overtime Rate: PKR {imran_rec.get('overtime_rate')}")
    print(f"  Overtime Amount: PKR {imran_rec.get('overtime_amount')}")
    print(f"  Gross Salary: PKR {imran_rec.get('gross_salary')}")
    print(f"  Custom Deductions: PKR {imran_rec.get('custom_deductions')}")
    print(f"  Absence Deduction: PKR {imran_rec.get('deduction_amount')}")
    print(f"  Net Salary: PKR {imran_rec.get('net_salary')}")

    # Assertions
    assert imran_rec['basic_salary'] == 250000.0, f"Expected 250000.0, got {imran_rec['basic_salary']}"
    assert imran_rec['allowances'] == 35000.0, f"Expected 35000.0, got {imran_rec['allowances']}"
    assert imran_rec['overtime_hours'] == 3.0, f"Expected exactly 3.0 hours (pending/rejected excluded!), got {imran_rec['overtime_hours']}"
    assert imran_rec['overtime_rate'] == 1201.92, f"Expected 1201.92, got {imran_rec['overtime_rate']}"
    expected_ot_amt = round(3.0 * 1201.92, 2) # 3605.76
    assert imran_rec['overtime_amount'] == expected_ot_amt, f"Expected {expected_ot_amt}, got {imran_rec['overtime_amount']}"
    expected_gross = round(250000.0 + 35000.0 + 3605.76, 2) # 288605.76
    assert imran_rec['gross_salary'] == expected_gross, f"Expected {expected_gross}, got {imran_rec['gross_salary']}"
    assert imran_rec['custom_deductions'] == 10000.0, f"Expected 10000.0, got {imran_rec['custom_deductions']}"
    expected_net = round(expected_gross - 10000.0 - imran_rec['deduction_amount'], 2)
    assert imran_rec['net_salary'] == expected_net, f"Expected {expected_net}, got {imran_rec['net_salary']}"

    print(f"\nALL MATHEMATICAL & BUSINESS ASSERTIONS PASSED!")
    print(f"Expected OT Amount = {expected_ot_amt} -> ACTUAL = {imran_rec['overtime_amount']}")
    print(f"Expected Net = {expected_net} -> ACTUAL = {imran_rec['net_salary']}")

finally:
    # Cleanup test overtime
    with sqlite3.connect('attendance.db') as conn:
        conn.execute("DELETE FROM overtime WHERE user_id = ? AND ot_date IN ('2026-10-15', '2026-10-16', '2026-10-17')", (TEST_USER_ID,))
        conn.commit()
    # Restore original config
    if orig_cfg:
        db.set_salary_config(
            user_id=TEST_USER_ID,
            basic_salary=float(orig_cfg.get('basic_salary') or 0.0),
            allowances=float(orig_cfg.get('allowances') or 0.0),
            deductions=float(orig_cfg.get('deductions') or 0.0),
            ot_rate=float(orig_cfg.get('ot_rate') or 0.0)
        )
    print("\nCleaned up test overtime and restored original salary config.")
