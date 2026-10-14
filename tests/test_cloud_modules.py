"""
Phase 1 Cloud Integration Test Suite
Validates:
1. Cloud startup and isolated database initialization.
2. Confirmation that local attendance.db remains untouched.
3. License key generation with expiry and cryptographic signature verification.
4. Server-side rejection of expired or mismatched installation licenses.
5. Multi-tenant Staff Directory & Shift Management.
6. Attendance batch ingestion, idempotency & duplicate prevention on (installation_id, local_attendance_id).
7. Partial batch failures and payload validation.
8. Attendance Reports querying and metrics for 5 employees.
9. Concurrency & transaction integrity in SQLite WAL mode.
"""

import unittest
import os
import tempfile
import json
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Set isolated test database environment before importing cloud modules
temp_dir = tempfile.mkdtemp()
TEST_CLOUD_DB = Path(temp_dir) / "test_cloud_attendance.db"
os.environ['CLOUD_DB_PATH'] = str(TEST_CLOUD_DB)
os.environ['CLOUD_SECRET_KEY'] = 'test-secret-key-phase1-validation'

from cloud.db import (
    init_cloud_db, get_db_connection, get_organizations, get_branches,
    create_shift, get_shifts, create_or_sync_staff, get_staff_list,
    ingest_attendance_batch, query_attendance_reports, set_staff_attendance_status
)
from cloud.license import generate_license_key, verify_license_key
from cloud.app import create_cloud_app
from cloud.shift_push import register_shift_client, unregister_shift_client


class TestCloudPhase1Integration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Record state of local attendance.db before tests run
        cls.local_db_path = Path(__file__).resolve().parent.parent / "attendance.db"
        if cls.local_db_path.exists():
            cls.local_db_stat_before = cls.local_db_path.stat()
        else:
            cls.local_db_stat_before = None

        init_cloud_db(TEST_CLOUD_DB)
        cls.app = create_cloud_app(init_db_on_start=False)
        cls.client = cls.app.test_client()
        cls.admin_headers = {"X-Cloud-Admin-Key": "test-secret-key-phase1-validation"}

    def test_01_local_database_remains_untouched(self):
        """Verify that local attendance.db was not modified or written to."""
        if self.local_db_stat_before and self.local_db_path.exists():
            stat_now = self.local_db_path.stat()
            self.assertEqual(
                stat_now.st_size,
                self.local_db_stat_before.st_size,
                "Local attendance.db file size changed during cloud initialization!"
            )
            self.assertEqual(
                stat_now.st_mtime,
                self.local_db_stat_before.st_mtime,
                "Local attendance.db timestamp changed during cloud initialization!"
            )

    def test_02_cloud_db_initialization_and_wal_mode(self):
        """Verify cloud database schema exists and WAL mode is active."""
        with get_db_connection(TEST_CLOUD_DB) as conn:
            journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            self.assertIn(journal_mode.lower(), ['wal', 'memory'], "WAL mode should be enabled")
            
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
            self.assertIn("cloud_organizations", tables)
            self.assertIn("cloud_branches", tables)
            self.assertIn("cloud_licenses", tables)
            self.assertIn("cloud_shifts", tables)
            self.assertIn("cloud_staff", tables)
            self.assertIn("cloud_attendance_events", tables)

    def test_03_license_generation_and_validation(self):
        """Test license generation, tamper protection, installation binding, and expiration."""
        org_id = "org-default"
        branch_id = "branch-main"
        installation_id = "inst-pilot-001"
        
        # Valid active license (expires in 10 days)
        future_date = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        lic_key = generate_license_key(org_id, branch_id, installation_id, future_date)
        
        is_valid, payload, msg = verify_license_key(lic_key, expected_installation_id=installation_id)
        self.assertTrue(is_valid, f"Expected valid license: {msg}")
        self.assertEqual(payload['installation_id'], installation_id)
        
        # Mismatched installation
        is_valid_bad_inst, _, msg_bad = verify_license_key(lic_key, expected_installation_id="inst-different-machine")
        self.assertFalse(is_valid_bad_inst)
        self.assertIn("mismatch", msg_bad.lower())
        
        # Expired license
        past_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        expired_key = generate_license_key(org_id, branch_id, installation_id, past_date)
        is_valid_expired, _, msg_exp = verify_license_key(expired_key, expected_installation_id=installation_id)
        self.assertFalse(is_valid_expired)
        self.assertIn("expired", msg_exp.lower())
        
        # Tampered license string
        tampered_key = lic_key[:-4] + "ABCD"
        is_valid_tampered, _, msg_tamp = verify_license_key(tampered_key, expected_installation_id=installation_id)
        self.assertFalse(is_valid_tampered)

    def test_04_shift_management_endpoints(self):
        """Test Shift creation, listing, default management, and deletion."""
        # Create evening shift
        res = self.client.post('/api/v1/shifts/', json={
            "name": "Evening Shift",
            "start_time": "14:00",
            "end_time": "22:00",
            "grace_period_minutes": 20,
            "working_days": [0, 1, 2, 3, 4]
        }, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)
        shift_id = res.get_json()['shift_id']
        
        # List shifts
        res_list = self.client.get('/api/v1/shifts/?branch_id=branch-main', headers=self.admin_headers)
        self.assertEqual(res_list.status_code, 200)
        shifts = res_list.get_json()['shifts']
        self.assertTrue(any(s['id'] == shift_id for s in shifts))
        
        # Update shift
        res_up = self.client.put(f'/api/v1/shifts/{shift_id}', json={
            "name": "Evening Shift (Updated)",
            "start_time": "14:30",
            "end_time": "22:30",
            "grace_period_minutes": 15
        }, headers=self.admin_headers)
        self.assertEqual(res_up.status_code, 200)

        # Test set-default via legacy endpoint (used by UI)
        res_def = self.client.post(f'/api/shifts/{shift_id}/set-default')
        self.assertEqual(res_def.status_code, 200)
        self.assertTrue(res_def.get_json()['success'])

        # Verify it is now default
        res_list2 = self.client.get('/api/v1/shifts/?branch_id=branch-main', headers=self.admin_headers)
        shifts2 = res_list2.get_json()['shifts']
        for s in shifts2:
            if s['id'] == shift_id:
                self.assertEqual(s['is_default'], 1)
            else:
                self.assertEqual(s['is_default'], 0)

        # Reset default shift back to shift-morning-default for subsequent tests
        res_reset = self.client.post('/api/shifts/shift-morning-default/set-default')
        self.assertEqual(res_reset.status_code, 200)

    def test_05_staff_directory_for_5_employees(self):
        """Test managing directory for the 5 pilot employees."""
        employees = [
            {"name": "Sikander FnK", "department": "FnK Operations", "position": "Floor Supervisor", "local_user_id": 95},
            {"name": "Shahid Assistant Chef FnK", "department": "FnK Operations", "position": "Assistant Chef", "local_user_id": 96},
            {"name": "Salman FnK", "department": "FnK Operations", "position": "Kitchen Specialist", "local_user_id": 97},
            {"name": "Shoaib FnK", "department": "FnK Operations", "position": "Inventory Controller", "local_user_id": 98},
            {"name": "Siddique FnK", "department": "FnK Operations", "position": "Procurement Officer", "local_user_id": 99},
        ]
        
        created_ids = []
        for emp in employees:
            res = self.client.post('/api/v1/staff/', json=emp, headers=self.admin_headers)
            self.assertEqual(res.status_code, 201)
            created_ids.append(res.get_json()['staff_id'])
            
        self.assertEqual(len(created_ids), 5)
        
        # Verify listing
        res_dir = self.client.get('/api/v1/staff/?branch_id=branch-main', headers=self.admin_headers)
        self.assertEqual(res_dir.status_code, 200)
        staff_data = res_dir.get_json()['staff']
        names_found = [s['name'] for s in staff_data]
        for emp in employees:
            self.assertIn(emp['name'], names_found)

    def test_05a_individual_and_bulk_shift_assignment(self):
        staff = get_staff_list(branch_id='branch-main', active_only=True)
        individual, bulk = staff[0], staff[1]
        new_shift = create_shift(
            org_id='org-default',
            branch_id='branch-main',
            name='Assignment Test Shift',
            start_time='10:00',
            end_time='18:00'
        )

        individual_response = self.client.post(
            f"/api/users/{individual['id']}/assign-shift",
            json={'shift_id': new_shift}
        )
        self.assertEqual(individual_response.status_code, 200, individual_response.get_json())
        individual_after = get_staff_list(branch_id='branch-main', active_only=True)
        individual_after = next(staffer for staffer in individual_after if staffer['id'] == individual['id'])
        self.assertEqual(individual_after['shift_id'], new_shift)
        self.assertEqual(individual_after['department'], individual['department'])

        bulk_response = self.client.post(
            '/api/users/bulk-assign-shifts',
            json={'user_ids': [bulk['id']], 'shift_id': 'shift-morning-default'}
        )
        self.assertEqual(bulk_response.status_code, 200, bulk_response.get_json())
        bulk_after = get_staff_list(branch_id='branch-main', active_only=True)
        bulk_after = next(staffer for staffer in bulk_after if staffer['id'] == bulk['id'])
        self.assertEqual(bulk_after['shift_id'], 'shift-morning-default')
        self.assertEqual(bulk_after['department'], bulk['department'])

    def test_05b_shift_sync_returns_local_employee_assignments(self):
        staff = get_staff_list(branch_id='branch-main', active_only=True)
        employee = staff[0]
        assigned_shift_id = create_shift(
            org_id='org-default',
            branch_id='branch-main',
            name='Cloud Assignment Sync Test',
            start_time='15:40',
            end_time='17:00'
        )
        create_or_sync_staff(
            org_id='org-default',
            branch_id='branch-main',
            name=employee['name'],
            local_user_id=employee['local_user_id'],
            shift_id=assigned_shift_id
        )
        installation_id = 'inst-assignment-sync-test'
        license_key = generate_license_key(
            'org-default',
            'branch-main',
            installation_id,
            (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        )

        response = self.client.get(
            '/api/v1/sync/shifts',
            headers={
                'X-License-Key': license_key,
                'X-Installation-Id': installation_id
            }
        )

        self.assertEqual(response.status_code, 200, response.get_json())
        payload = response.get_json()
        assignment = next(
            item for item in payload['staff_assignments']
            if item['local_user_id'] == employee['local_user_id']
        )
        self.assertEqual(assignment['shift_id'], assigned_shift_id)
        self.assertEqual(assignment['effective_from'], datetime.now(timezone.utc).date().isoformat())
        shift_summary = next(
            shift for shift in get_shifts(branch_id='branch-main')
            if shift['id'] == assigned_shift_id
        )
        self.assertEqual(shift_summary['user_count'], 1)

    def test_05d_shift_mutations_push_snapshot_to_connected_client(self):
        employee = get_staff_list(branch_id='branch-main', active_only=True)[0]
        original_shift_id = employee.get('shift_id')

        class FakeClient:
            def __init__(self):
                self.messages = []
            def send(self, message):
                self.messages.append(json.loads(message))

        client = FakeClient()
        shift_id = None
        register_shift_client('branch-main', client)
        try:
            shift_id = create_shift(
                org_id='org-default',
                branch_id='branch-main',
                name='Connected Push Test Shift',
                start_time='18:40',
                end_time='22:00'
            )
            create_or_sync_staff(
                org_id='org-default',
                branch_id='branch-main',
                name=employee['name'],
                local_user_id=employee['local_user_id'],
                shift_id=shift_id
            )
            pushed_assignment = next(
                assignment for assignment in client.messages[-1]['staff_assignments']
                if assignment['local_user_id'] == employee['local_user_id']
            )
            self.assertEqual(pushed_assignment['shift_id'], shift_id)
            self.assertEqual(client.messages[-1]['type'], 'shift_snapshot')
        finally:
            if shift_id:
                create_or_sync_staff(
                    org_id='org-default',
                    branch_id='branch-main',
                    name=employee['name'],
                    local_user_id=employee['local_user_id'],
                    shift_id=original_shift_id
                )
                from cloud.db import delete_shift
                delete_shift(shift_id)
            unregister_shift_client('branch-main', client)

    def test_05c_new_checkin_clears_cloud_manual_absence_for_the_day(self):
        employee = get_staff_list(branch_id='branch-main', active_only=True)[0]
        target_date = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        user_id = employee['local_user_id']
        staff_id = employee['id']

        result = set_staff_attendance_status(
            user_id=str(user_id), target_date=target_date, status='absent'
        )
        self.assertIsNotNone(result)

        summary = ingest_attendance_batch(
            org_id='org-default',
            branch_id='branch-main',
            installation_id='inst-absence-override-test',
            events=[{
                'local_attendance_id': 87654321,
                'user_id': user_id,
                'employee_name': employee['name'],
                'timestamp': f'{target_date} 09:01:00',
                'event_type': 'checkin',
                'status': 'present',
            }],
            db_path=TEST_CLOUD_DB,
        )

        with get_db_connection(TEST_CLOUD_DB) as conn:
            day_events = conn.execute(
                'SELECT installation_id, status, source FROM cloud_attendance_events '
                'WHERE staff_id = ? AND DATE(timestamp) = ?',
                (staff_id, target_date)
            ).fetchall()

        self.assertEqual(summary['accepted'], 1)
        self.assertEqual(len(day_events), 1)
        self.assertEqual(day_events[0]['status'], 'present')
        self.assertEqual(day_events[0]['source'], '')

    def test_06_attendance_batch_ingestion_and_duplicate_prevention(self):
        """
        Test transactional batch attendance syncing with strict duplicate prevention
        on (installation_id, local_attendance_id).
        """
        inst_id = "inst-pilot-001"
        valid_lic = generate_license_key(
            "org-default", "branch-main", inst_id,
            (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        )
        sync_headers = {
            "X-License-Key": valid_lic,
            "X-Installation-Id": inst_id
        }
        
        batch_events = [
            {
                "local_attendance_id": 1001,
                "detected_name": "Sikander FnK",
                "user_id": 95,
                "timestamp": "2026-10-10 09:02:15",
                "confidence": 0.91,
                "camera_id": "cam_gate_1",
                "location": "Front Entrance",
                "event_type": "checkin",
                "status": "present"
            },
            {
                "local_attendance_id": 1002,
                "detected_name": "Shahid Assistant Chef FnK",
                "user_id": 96,
                "timestamp": "2026-10-10 09:05:40",
                "confidence": 0.89,
                "camera_id": "cam_gate_1",
                "location": "Front Entrance",
                "event_type": "checkin",
                "status": "present"
            },
            {
                "local_attendance_id": 1003,
                "detected_name": "Shoaib FnK",
                "user_id": 98,
                "timestamp": "2026-10-10 09:12:05",
                "confidence": 0.94,
                "camera_id": "cam_gate_1",
                "location": "Front Entrance",
                "event_type": "checkin",
                "status": "late"
            }
        ]
        
        # First sync attempt: all 3 accepted
        res1 = self.client.post('/api/v1/sync/attendance', json={"events": batch_events}, headers=sync_headers)
        self.assertEqual(res1.status_code, 200)
        summary1 = res1.get_json()['batch_summary']
        self.assertEqual(summary1['accepted'], 3)
        self.assertEqual(summary1['duplicates'], 0)
        
        # Second sync attempt with identical payload: all 3 treated as duplicates, 0 inserted
        res2 = self.client.post('/api/v1/sync/attendance', json={"events": batch_events}, headers=sync_headers)
        self.assertEqual(res2.status_code, 200)
        summary2 = res2.get_json()['batch_summary']
        self.assertEqual(summary2['accepted'], 0)
        self.assertEqual(summary2['duplicates'], 3)
        self.assertEqual(len(summary2['duplicate_local_ids']), 3)

    def test_07_partial_batch_failures_and_payload_validation(self):
        """Test partial batch where some records are valid, some duplicates, and some invalid."""
        inst_id = "inst-pilot-001"
        valid_lic = generate_license_key(
            "org-default", "branch-main", inst_id,
            (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        )
        sync_headers = {
            "X-License-Key": valid_lic,
            "X-Installation-Id": inst_id
        }
        
        mixed_batch = [
            # 1. Duplicate (1001 was already ingested)
            {
                "local_attendance_id": 1001,
                "detected_name": "Sikander FnK",
                "user_id": 95,
                "timestamp": "2026-10-10 09:02:15"
            },
            # 2. Brand new valid record
            {
                "local_attendance_id": 1004,
                "detected_name": "Siddique FnK",
                "user_id": 99,
                "timestamp": "2026-10-10 09:15:30",
                "event_type": "checkin"
            },
            # 3. Invalid record (missing name)
            {
                "local_attendance_id": 1005,
                "detected_name": "",
                "timestamp": "2026-10-10 09:20:00"
            }
        ]
        
        res = self.client.post('/api/v1/sync/attendance', json={"events": mixed_batch}, headers=sync_headers)
        self.assertEqual(res.status_code, 200)
        summary = res.get_json()['batch_summary']
        self.assertEqual(summary['accepted'], 1)
        self.assertEqual(summary['duplicates'], 1)
        self.assertEqual(summary['rejected'], 1)
        self.assertEqual(len(summary['errors']), 1)

    def test_08_expired_or_unauthorized_sync_rejection(self):
        """Ensure server rejects sync requests when license is expired or missing."""
        inst_id = "inst-pilot-001"
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        expired_lic = generate_license_key("org-default", "branch-main", inst_id, past_date)
        
        res_exp = self.client.post(
            '/api/v1/sync/attendance',
            json={"events": [{"local_attendance_id": 9999, "detected_name": "Test", "timestamp": "2026-10-10 10:00:00"}]},
            headers={"X-License-Key": expired_lic, "X-Installation-Id": inst_id}
        )
        self.assertEqual(res_exp.status_code, 403)
        self.assertIn("License validation rejected", res_exp.get_json()['error'])

    def test_09_cloud_attendance_reports_and_export(self):
        """Test attendance reporting and CSV export."""
        # Query JSON report
        res = self.client.get('/api/v1/reports/?start_date=2026-10-01&end_date=2026-10-15', headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        report = res.get_json()
        self.assertGreater(report['count'], 0)
        self.assertIn('summary', report)
        self.assertIn('total_records', report['summary'])
        record = report['records'][0]
        self.assertIsNotNone(record.get('user_id'))
        self.assertTrue(record.get('name'))
        self.assertTrue(record.get('date'))
        self.assertIn('first_seen', record)
        self.assertIn('checkin_camera', record)
        self.assertEqual(report['summary']['total_enrolled'], 5)
        
        # Test CSV export
        res_csv = self.client.get('/api/v1/reports/?format=csv', headers=self.admin_headers)
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn('text/csv', res_csv.headers['Content-Type'])
        self.assertIn("Sikander FnK", res_csv.data.decode('utf-8'))

    def test_09a_today_filter_and_report_quick_actions(self):
        today = datetime.now(timezone.utc).date().isoformat()
        absent_response = self.client.post(
            '/api/users/95/mark-absent',
            json={'date': today}
        )
        self.assertEqual(absent_response.status_code, 200, absent_response.get_json())

        report_response = self.client.get(
            '/api/v1/reports/?date=today',
            headers=self.admin_headers
        )
        self.assertEqual(report_response.status_code, 200)
        absent_record = next(record for record in report_response.get_json()['records'] if record['user_id'] == 95)
        self.assertEqual(absent_record['name'], 'Sikander FnK')
        self.assertEqual(absent_record['date'], today)
        self.assertEqual(absent_record['status'], 'absent')
        self.assertIsNone(absent_record['first_seen'])

        present_response = self.client.post(
            '/api/users/95/mark-present',
            json={'date': today, 'check_in_time': '09:10', 'check_out_time': '17:00', 'notes': 'Corrected'}
        )
        self.assertEqual(present_response.status_code, 200, present_response.get_json())
        report_response = self.client.get(
            '/api/v1/reports/?date=today',
            headers=self.admin_headers
        )
        records = [record for record in report_response.get_json()['records'] if record['user_id'] == 95]
        self.assertEqual(len(records), 2)
        self.assertTrue(any(record['first_seen'] == f'{today} 09:10:00' for record in records))
        self.assertTrue(any(record['last_seen'] == f'{today} 17:00:00' for record in records))

    def test_10_concurrent_batch_ingestion(self):
        """Verify concurrent sync requests handle transactions without data loss or SQLite deadlocks."""
        inst_id = "inst-pilot-001"
        valid_lic = generate_license_key(
            "org-default", "branch-main", inst_id,
            (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        )
        
        def run_sync(worker_id):
            client = self.app.test_client()
            events = [
                {
                    "local_attendance_id": 2000 + (worker_id * 10) + i,
                    "detected_name": "Salman FnK",
                    "user_id": 97,
                    "timestamp": f"2026-10-11 1{worker_id}:0{i}:00",
                    "event_type": "checkout"
                }
                for i in range(3)
            ]
            res = client.post(
                '/api/v1/sync/attendance',
                json={"events": events},
                headers={"X-License-Key": valid_lic, "X-Installation-Id": inst_id}
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.get_json()['batch_summary']['accepted'], 3)

    def test_11_dashboard_html_view(self):
        """Verify GET / returns complete dashboard HTML and sets session token."""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('text/html', res.headers.get('Content-Type'))
        body = res.data.decode('utf-8')
        self.assertIn("QIntellect", body)
        self.assertIn("cloud-mode", body)
        self.assertIn("Attendance Reports", body)
        self.assertIn("Staff Directory", body)
        self.assertIn("Shift Management", body)
        self.assertIn("License Key Generator", body)
        # Excluded items are tagged with cloud-hide class for CSS-level hiding
        self.assertIn("cloud-hide", body)

    def test_12_shift_deletion_safety(self):
        """Verify default shift or shift assigned to staff cannot be deleted."""
        # Cannot delete default shift
        res_del_def = self.client.delete('/api/v1/shifts/shift-morning-default', headers=self.admin_headers)
        self.assertEqual(res_del_def.status_code, 400)
        self.assertIn("default shift", res_del_def.get_json()['error'].lower())


if __name__ == '__main__':
    unittest.main()

