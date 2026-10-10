import os
import sys
import sqlite3
import json
from datetime import datetime

sys.path.insert(0, r'd:\QIntellect-AI-Attendence-11-9-2026\Final-AI-Attendence-System\Final-AI-Attendence-System\Flask-Attedence')

def mock_module(name):
    import types
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m
mock_module('cv2')
mock_module('deepface')
mock_module('deepface.DeepFace')
mock_module('face_recognition')
insightface = mock_module('insightface')
insightface.app = mock_module('insightface.app')
insightface.app.FaceAnalysis = lambda *a, **k: None
ultralytics = mock_module('ultralytics')
ultralytics.YOLO = lambda *a, **k: None

import app as flask_app
import database as db

client = flask_app.app.test_client()

print("1. Testing Manual Attendance Target Date...")
uid_manual = None
try:
    with db.sqlite3.connect(db.DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO users (name, department, active, shift_id) VALUES ('Manual Test User', 'Testing', 1, 1)")
        uid_manual = c.lastrowid
        conn.commit()
    db.assign_user_shift(uid_manual, 1, '2026-01-01')

    # Test with target_date = 2026-09-15
    with flask_app.app.test_request_context():
        import flask
        flask.session['admin_unlocked'] = True
        res = client.post(f'/api/users/{uid_manual}/mark-present', json={
            "date": "2026-09-15",
            "check_in_time": "09:00",
            "check_out_time": "18:00",
            "notes": "Testing Target Date"
        })
        print(f"Manual Mark Present API Response: {res.status_code}")
        
        # Verify in DB
        with db.sqlite3.connect(db.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM attendance WHERE user_id = ? AND date(timestamp) = '2026-09-15'", (uid_manual,))
            logs = c.fetchall()
            print(f"Logs found for 2026-09-15: {len(logs)}")
            if logs:
                print(f"Log 1 Timestamp: {logs[0]['timestamp']}, Source: {logs[0]['source']}")
                if len(logs) > 1:
                    print(f"Log 2 Timestamp: {logs[1]['timestamp']}, Source: {logs[1]['source']}")
finally:
    if uid_manual:
        with db.sqlite3.connect(db.DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM attendance WHERE user_id = ?", (uid_manual,))
            c.execute("DELETE FROM employee_shift_history WHERE user_id = ?", (uid_manual,))
            c.execute("DELETE FROM users WHERE id = ?", (uid_manual,))
            conn.commit()

print("\n2. Testing Pro-rata Payroll (Mid-month Joiner & Exit)...")
uid_joiner = None
uid_exiter = None
try:
    with db.sqlite3.connect(db.DB_PATH) as conn:
        c = conn.cursor()
        # Joiner: 15th Oct
        c.execute("INSERT INTO users (name, department, active, join_date, salary, shift_id) VALUES ('Mid Joiner', 'Testing', 1, '2026-10-15', 50000, 1)")
        uid_joiner = c.lastrowid
        # Exiter: 20th Oct
        c.execute("INSERT INTO users (name, department, active, join_date, exit_date, salary, shift_id) VALUES ('Mid Exiter', 'Testing', 1, '2026-01-01', '2026-10-20', 50000, 1)")
        uid_exiter = c.lastrowid
        conn.commit()
    db.assign_user_shift(uid_joiner, 1, '2026-10-15')
    db.assign_user_shift(uid_exiter, 1, '2026-01-01')

    def mark_attendance(uid, dates):
        for d in dates:
            db.mark_user_present_today(uid, target_date=d, check_in_time="09:00", check_out_time="18:00")
            
    mark_attendance(uid_joiner, ["2026-10-15", "2026-10-16", "2026-10-19"])
    mark_attendance(uid_exiter, ["2026-10-19", "2026-10-20"])

    with db.sqlite3.connect(db.DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM payroll_runs WHERE payroll_month = '2026-10'")
        conn.commit()

    payroll_all = db.calculate_monthly_payroll("2026-10")
    
    print("Payroll dict keys:", payroll_all.keys())
    print("Employees list length:", len(payroll_all.get('employees', [])))
    print("All payroll UIDs:", [r['employee_id'] for r in payroll_all.get('records', [])])
    
    payroll_joiner = next((r for r in payroll_all.get('records', []) if r['employee_id'] == uid_joiner), {})
    payroll_exiter = next((r for r in payroll_all.get('records', []) if r['employee_id'] == uid_exiter), {})

    print("Joiner Payroll:", payroll_joiner)
    print("Exiter Payroll:", payroll_exiter)

finally:
    for uid in (uid_joiner, uid_exiter):
        if uid:
            with db.sqlite3.connect(db.DB_PATH) as conn:
                c = conn.cursor()
                c.execute("DELETE FROM attendance WHERE user_id = ?", (uid,))
                c.execute("DELETE FROM employee_shift_history WHERE user_id = ?", (uid,))
                c.execute("DELETE FROM users WHERE id = ?", (uid,))
                conn.commit()

print("\n3. DB Integrity Checks...")
with db.sqlite3.connect(db.DB_PATH) as conn:
    c = conn.cursor()
    c.execute("PRAGMA integrity_check;")
    integrity = c.fetchone()[0]
    print(f"Integrity Check: {integrity}")
    c.execute("PRAGMA foreign_key_check;")
    fks = c.fetchall()
    print(f"Foreign Key Check Violations: {len(fks)}")
