import json
import sqlite3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime
import database as db
from app import app

def run_tests():
    client = app.test_client()
    print("=== STARTING LEAVE QUOTA & CATEGORY PERIOD ENHANCEMENTS TEST ===")
    
    # Clean any previous test data
    with sqlite3.connect(db.DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM leave_requests WHERE reason LIKE 'TEST_QUOTA_%'")
        c.execute("DELETE FROM leave_types WHERE code IN ('test_6m_policy', 'test_1m_policy')")
        conn.commit()

    # 1. Test check_leave_quota directly
    print("\n[Test 1] Direct check_leave_quota function:")
    # User 41, casual leave (10 allowed), request 13 days (2026-11-01 to 2026-11-13)
    res_exceeded = db.check_leave_quota(41, 'casual', '2026-11-01', '2026-11-13')
    print("13-day Casual Leave check:", res_exceeded)
    assert res_exceeded['allowed'] is False, "Should block 13 days"
    expected_msg = "Casual Leave only has 10 allowed paid days for this employee. You cannot request 13 days. Please adjust the dates or file the excess days under Unpaid Leave (LWP)."
    assert res_exceeded['message'] == expected_msg, f"Message mismatch:\nGot:      {res_exceeded['message']}\nExpected: {expected_msg}"
    print("PASS: Exact error message matches!")

    # 2. Test GET /api/leaves/check-quota endpoint
    print("\n[Test 2] GET /api/leaves/check-quota endpoint:")
    resp = client.get('/api/leaves/check-quota?user_id=41&leave_type=casual&start_date=2026-11-01&end_date=2026-11-13')
    assert resp.status_code == 200
    quota_json = resp.get_json()
    assert quota_json['allowed'] is False
    assert quota_json['message'] == expected_msg
    print("PASS: API endpoint returned quota rejection with exact message!")

    # 3. Test POST /api/leaves blocking when quota exceeded
    print("\n[Test 3] POST /api/leaves blocked when exceeding quota:")
    resp_post_fail = client.post('/api/leaves', json={
        'user_id': 41,
        'leave_type': 'casual',
        'start_date': '2026-11-01',
        'end_date': '2026-11-13',
        'reason': 'TEST_QUOTA_EXCEED'
    })
    assert resp_post_fail.status_code == 400, f"Expected HTTP 400, got {resp_post_fail.status_code}"
    post_json = resp_post_fail.get_json()
    assert post_json['success'] is False
    assert post_json['message'] == expected_msg
    print("PASS: POST /api/leaves returned HTTP 400 with expected error!")

    # 4. Test POST /api/leaves allowing valid days within quota
    print("\n[Test 4] POST /api/leaves allowed within quota (5 days):")
    resp_post_ok = client.post('/api/leaves', json={
        'user_id': 41,
        'leave_type': 'casual',
        'start_date': '2026-11-01',
        'end_date': '2026-11-05',
        'reason': 'TEST_QUOTA_VALID'
    })
    assert resp_post_ok.status_code == 201, f"Expected HTTP 201, got {resp_post_ok.status_code}"
    req_id_valid = resp_post_ok.get_json().get('id')
    print(f"PASS: Leave request #{req_id_valid} filed successfully within quota!")

    # 5. Test Unpaid Leave (LWP) with no upper limit
    print("\n[Test 5] POST /api/leaves allowed for Unpaid Leave (15 days):")
    resp_unpaid_ok = client.post('/api/leaves', json={
        'user_id': 41,
        'leave_type': 'unpaid',
        'start_date': '2026-11-01',
        'end_date': '2026-11-15',
        'reason': 'TEST_QUOTA_UNPAID'
    })
    assert resp_unpaid_ok.status_code == 201, f"Expected HTTP 201, got {resp_unpaid_ok.status_code}"
    unpaid_req_id = resp_unpaid_ok.get_json().get('id')
    print(f"PASS: Unpaid leave #{unpaid_req_id} filed successfully!")

    # 6. Test Policy Allowance Period: 6-Month and Monthly
    print("\n[Test 6] Adding Leave Types with 6-Month and Monthly options:")
    resp_lt_6m = client.post('/api/leave-types', json={
        'name': 'Test 6M Policy',
        'code': 'test_6m_policy',
        'yearly_allowance': 6.0,
        'allowance_period': 'half_yearly',
        'is_paid': 1,
        'description': '6-month test policy'
    })
    assert resp_lt_6m.status_code == 201
    tid_6m = resp_lt_6m.get_json().get('id')

    resp_lt_1m = client.post('/api/leave-types', json={
        'name': 'Test 1M Policy',
        'code': 'test_1m_policy',
        'yearly_allowance': 2.0,
        'allowance_period': 'monthly',
        'is_paid': 1,
        'description': 'Monthly test policy'
    })
    assert resp_lt_1m.status_code == 201
    tid_1m = resp_lt_1m.get_json().get('id')

    # Verify period persisted in db
    with sqlite3.connect(db.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT allowance_period FROM leave_types WHERE id = ?", (tid_6m,))
        row_6m = c.fetchone()
        assert row_6m['allowance_period'] == 'half_yearly'
        c.execute("SELECT allowance_period FROM leave_types WHERE id = ?", (tid_1m,))
        row_1m = c.fetchone()
        assert row_1m['allowance_period'] == 'monthly'
    print("PASS: 6-Month and Monthly leave policy types saved and verified!")

    # 7. Multi-day attendance report column verification
    print("\n[Test 7] Attendance report records contain 'leave_days':")
    rep = db.get_detailed_attendance_report(start_date='2026-10-08', end_date='2026-10-17')
    records = rep.get('records', [])
    assert len(records) > 0
    first_r = records[0]
    assert 'leave_days' in first_r, "leave_days must be present in report record"
    print(f"PASS: Report record has leave_days = {first_r.get('leave_days')}, present_days = {first_r.get('present_days')}, absent_days = {first_r.get('absent_days')}")

    # Cleanup test artifacts
    with sqlite3.connect(db.DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM leave_requests WHERE reason LIKE 'TEST_QUOTA_%'")
        c.execute("DELETE FROM leave_types WHERE code IN ('test_6m_policy', 'test_1m_policy')")
        conn.commit()
    print("PASS: Cleaned up test records!")
    print("\n=== ALL LEAVE ENHANCEMENT TESTS PASSED PERFECTLY (7/7) ===")

if __name__ == '__main__':
    run_tests()
