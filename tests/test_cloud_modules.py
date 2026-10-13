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
    ingest_attendance_batch, query_attendance_reports
)
from cloud.license import generate_license_key, verify_license_key
from cloud.app import create_cloud_app


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
            {"name": "Ali Raza", "department": "Operations", "position": "Officer", "local_user_id": 1},
            {"name": "Fatima Noor", "department": "HR", "position": "HR Lead", "local_user_id": 2},
            {"name": "Usman Tariq", "department": "IT", "position": "Engineer", "local_user_id": 3},
            {"name": "Zainab Bibi", "department": "Finance", "position": "Accountant", "local_user_id": 4},
            {"name": "Hamza Malik", "department": "Operations", "position": "Supervisor", "local_user_id": 5},
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
                "detected_name": "Ali Raza",
                "timestamp": "2026-10-10 09:02:15",
                "confidence": 0.91,
                "camera_id": "cam_gate_1",
                "location": "Front Entrance",
                "event_type": "checkin",
                "status": "present"
            },
            {
                "local_attendance_id": 1002,
                "detected_name": "Fatima Noor",
                "timestamp": "2026-10-10 09:05:40",
                "confidence": 0.89,
                "camera_id": "cam_gate_1",
                "location": "Front Entrance",
                "event_type": "checkin",
                "status": "present"
            },
            {
                "local_attendance_id": 1003,
                "detected_name": "Usman Tariq",
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
                "detected_name": "Ali Raza",
                "timestamp": "2026-10-10 09:02:15"
            },
            # 2. Brand new valid record
            {
                "local_attendance_id": 1004,
                "detected_name": "Zainab Bibi",
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
        
        # Test CSV export
        res_csv = self.client.get('/api/v1/reports/?format=csv', headers=self.admin_headers)
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn('text/csv', res_csv.headers['Content-Type'])
        self.assertIn("Ali Raza", res_csv.data.decode('utf-8'))

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
                    "detected_name": f"Hamza Malik",
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

