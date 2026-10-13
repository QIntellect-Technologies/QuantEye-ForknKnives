import sqlite3
import os
import requests
import json
from datetime import datetime, timedelta

DB_PATH = 'attendance.db'
BASE_URL = 'http://localhost:5000'

def test_ticket_02_06_payroll():
    print("Testing TICKET-02 and TICKET-06: Leave + OT -> Payroll")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # We need a test employee
        c.execute("SELECT id FROM users WHERE active=1 LIMIT 1")
        user_id = c.fetchone()['id']
        
        # Get payroll preview
        res = requests.get(f"{BASE_URL}/api/payroll/preview?month=2026-10")
        assert res.status_code == 200
        preview_before = next((r for r in res.json().get('records', []) if r['employee_id'] == user_id), None)
        
        # Insert backdated paid leave and unpaid leave
        c.execute("""
            INSERT INTO leave_requests (user_id, user_name, leave_type, start_date, end_date, status)
            VALUES (?, 'Test User', 'sick', '2026-10-01', '2026-10-01', 'approved')
        """, (user_id,))
        c.execute("""
            INSERT INTO leave_requests (user_id, user_name, leave_type, start_date, end_date, status)
            VALUES (?, 'Test User', 'unpaid', '2026-10-02', '2026-10-02', 'approved')
        """, (user_id,))
        
        # Insert OT
        c.execute("""
            INSERT INTO overtime (user_id, ot_date, hours, status, ot_rate)
            VALUES (?, '2026-10-03', 2, 'approved', 100)
        """, (user_id,))
        conn.commit()
        
        # Get payroll preview again
        res2 = requests.get(f"{BASE_URL}/api/payroll/preview?month=2026-10")
        preview_after = next((r for r in res2.json().get('records', []) if r['employee_id'] == user_id), None)
        
        if preview_before and preview_after:
            print(f"Before: Payable={preview_before['payable_days']} OT={preview_before['overtime_amount']}")
            print(f"After: Payable={preview_after['payable_days']} OT={preview_after['overtime_amount']}")

def test_ticket_04_monthly_quota():
    print("Testing TICKET-04: Monthly Quota")
    # Add a monthly leave type
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT OR IGNORE INTO leave_types (code, name, yearly_allowance, is_paid, description, allowance_period)
            VALUES ('monthly_leave', 'Monthly Leave', 2, 1, 'Monthly', 'monthly')
        """)
        conn.commit()
        
    res = requests.get(f"{BASE_URL}/api/leaves/balances?year=2026")
    print(res.status_code)
    # etc...

if __name__ == '__main__':
    try:
        # Run tests or just use standard requests
        print("Starting comprehensive test...")
    except Exception as e:
        print(f"Error: {e}")
