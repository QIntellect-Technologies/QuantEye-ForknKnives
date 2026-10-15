import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

temp_dir = tempfile.mkdtemp()
TEST_MOBILE_DB = Path(temp_dir) / "mobile_test.db"
os.environ["CLOUD_DB_PATH"] = str(TEST_MOBILE_DB)
os.environ["CLOUD_SECRET_KEY"] = "mobile-api-test-secret"

from cloud.app import create_cloud_app
from cloud.db import get_db_connection, ingest_attendance_batch, init_cloud_db
from cloud.mobile_api import (
    _business_timezone,
    bootstrap_mobile_accounts_from_env,
    create_mobile_account,
    load_mobile_shift_socket_account,
    notify_attendance_event,
    notify_shift_schedule_changed,
)
from unittest.mock import patch


class TestMobileApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._database_path_patch = patch("cloud.db.CLOUD_DB_PATH", TEST_MOBILE_DB)
        cls._database_path_patch.start()
        init_cloud_db(TEST_MOBILE_DB)
        cls.app = create_cloud_app(init_db_on_start=False)
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()
        cls.employee_account_id = create_mobile_account(
            "employee.test", "correct horse battery", "employee", local_user_id=95
        )
        cls.admin_account_id = create_mobile_account(
            "admin.test", "another long password", "admin",
            display_name="ABID", department="FNK", position="Manager",
        )
        current = datetime.now(_business_timezone())
        start = (current - timedelta(minutes=2)).strftime("%H:%M")
        end = (current + timedelta(minutes=60)).strftime("%H:%M")
        with get_db_connection(TEST_MOBILE_DB) as conn:
            shift_id = conn.execute(
                "SELECT id FROM cloud_shifts WHERE id = 'shift-morning-default'"
            ).fetchone()[0]
            conn.execute(
                "UPDATE cloud_shifts SET start_time = ?, end_time = ?, grace_period_minutes = 15, working_days = '[0,1,2,3,4,5,6]' WHERE id = 'shift-morning-default'",
                (start, end),
            )
            conn.execute("UPDATE cloud_staff SET shift_id = ? WHERE local_user_id = 95", (shift_id,))
            conn.commit()
        cls.employee_token = cls.login("employee.test", "correct horse battery")
        cls.admin_token = cls.login("admin.test", "another long password")

    @classmethod
    def tearDownClass(cls):
        cls._database_path_patch.stop()

    @classmethod
    def login(cls, username, password):
        response = cls.client.post(
            "/api/v1/mobile/login", json={"username": username, "password": password}
        )
        if response.status_code != 200:
            raise AssertionError(response.get_json())
        return response.get_json()["token"]

    def test_login_has_no_signup_and_provides_role(self):
        response = self.client.post(
            "/api/v1/mobile/login", json={"username": "employee.test", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.post("/api/v1/mobile/signup").status_code, 404)
        me = self.client.get(
            "/api/v1/mobile/me", headers={"Authorization": f"Bearer {self.employee_token}"}
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.get_json()["account"]["role"], "employee")
        self.assertEqual(me.get_json()["account"]["employee_id"], 95)
        self.assertTrue(me.get_json()["account"]["position"])
        self.assertTrue(me.get_json()["account"]["department"])

        admin_login = self.client.post(
            "/api/v1/mobile/login",
            json={"username": "admin.test", "password": "another long password"},
        )
        self.assertEqual(admin_login.status_code, 200)
        self.assertEqual(admin_login.get_json()["account"]["name"], "ABID")
        self.assertEqual(admin_login.get_json()["account"]["department"], "FNK")
        self.assertEqual(admin_login.get_json()["account"]["position"], "Manager")

        admin_me = self.client.get(
            "/api/v1/mobile/me", headers={"Authorization": f"Bearer {self.admin_token}"}
        )
        self.assertEqual(admin_me.status_code, 200)
        self.assertEqual(admin_me.get_json()["account"]["name"], "ABID")
        self.assertEqual(admin_me.get_json()["account"]["department"], "FNK")
        self.assertEqual(admin_me.get_json()["account"]["position"], "Manager")

    def test_environment_bootstrap_is_idempotent_and_preserves_mismatched_accounts(self):
        import json

        accounts = [
            {"username": "bootstrap.employee", "password": "employee bootstrap password", "role": "employee", "branch_id": "branch-main", "employee_id": 95},
            {"username": "bootstrap.admin", "password": "administrator bootstrap password", "role": "admin", "branch_id": "branch-main", "employee_id": None},
        ]
        with patch.dict(os.environ, {"MOBILE_BOOTSTRAP_ACCOUNTS": json.dumps(accounts)}):
            first = bootstrap_mobile_accounts_from_env(TEST_MOBILE_DB)
            second = bootstrap_mobile_accounts_from_env(TEST_MOBILE_DB)

        self.assertEqual(first, {"created": 2, "unchanged": 0, "mismatched": 0})
        self.assertEqual(second, {"created": 0, "unchanged": 2, "mismatched": 0})

        accounts[0]["employee_id"] = 96
        accounts[0]["password"] = "replacement bootstrap password"
        with patch.dict(os.environ, {"MOBILE_BOOTSTRAP_ACCOUNTS": json.dumps(accounts)}):
            mismatch = bootstrap_mobile_accounts_from_env(TEST_MOBILE_DB)

        self.assertEqual(mismatch, {"created": 0, "unchanged": 1, "mismatched": 1})
        valid_login = self.client.post(
            "/api/v1/mobile/login",
            json={"username": "bootstrap.employee", "password": "employee bootstrap password"},
        )
        invalid_login = self.client.post(
            "/api/v1/mobile/login",
            json={"username": "bootstrap.employee", "password": "replacement bootstrap password"},
        )
        self.assertEqual(valid_login.status_code, 200)
        self.assertEqual(invalid_login.status_code, 401)
        with get_db_connection(TEST_MOBILE_DB) as conn:
            mapping = conn.execute(
                "SELECT s.local_user_id FROM mobile_accounts a JOIN cloud_staff s ON s.id = a.staff_id WHERE a.username = ?",
                ("bootstrap.employee",),
            ).fetchone()[0]
            account_count = conn.execute(
                "SELECT COUNT(*) FROM mobile_accounts WHERE username LIKE 'bootstrap.%'"
            ).fetchone()[0]
        self.assertEqual(mapping, 95)
        self.assertEqual(account_count, 2)

    def test_environment_bootstrap_rejects_short_password_without_logging_it(self):
        import json

        config = [{"username": "too.short", "password": "1234567", "role": "admin"}]
        with patch.dict(os.environ, {"MOBILE_BOOTSTRAP_ACCOUNTS": json.dumps(config)}):
            with self.assertRaisesRegex(ValueError, "at least 10 characters"):
                bootstrap_mobile_accounts_from_env(TEST_MOBILE_DB)

    def test_bad_bootstrap_config_does_not_prevent_cloud_app_startup(self):
        import json

        config = [{"username": "too.short", "password": "1234567", "role": "admin"}]
        with patch.dict(os.environ, {"MOBILE_BOOTSTRAP_ACCOUNTS": json.dumps(config)}):
            with self.assertLogs("cloud.app", level="ERROR") as captured:
                app = create_cloud_app(init_db_on_start=True)
        self.assertNotIn("1234567", "\n".join(captured.output))
        self.assertIsNotNone(app)

    def test_employee_checkin_uses_shift_and_camera_cannot_duplicate_it(self):
        headers = {"Authorization": f"Bearer {self.employee_token}"}
        schedule = self.client.get("/api/v1/mobile/employee/schedule", headers=headers)
        self.assertEqual(schedule.status_code, 200, schedule.get_json())
        self.assertTrue(schedule.get_json()["schedule"]["allowed"])

        checkin = self.client.post("/api/v1/mobile/employee/check-in", headers=headers, json={})
        self.assertEqual(checkin.status_code, 201, checkin.get_json())
        self.assertEqual(checkin.get_json()["attendance"]["source"], "mobile")
        self.assertEqual(checkin.get_json()["attendance"]["status"], "present")

        timestamp = checkin.get_json()["attendance"]["timestamp"]
        result = ingest_attendance_batch(
            "org-default", "branch-main", "test-camera-installation", [{
                "local_attendance_id": 34567,
                "user_id": 95,
                "employee_name": "Sikander FnK",
                "timestamp": timestamp,
                "event_type": "checkin",
                "status": "present",
                "source": "camera",
                "camera_id": "front-door",
            }],
            db_path=TEST_MOBILE_DB,
        )
        self.assertEqual(result["accepted"], 0)
        self.assertEqual(result["duplicates"], 1)

        repeated = self.client.post("/api/v1/mobile/employee/check-in", headers=headers, json={})
        self.assertEqual(repeated.status_code, 200)
        self.assertTrue(repeated.get_json()["already_marked"])

        with get_db_connection(TEST_MOBILE_DB) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM cloud_attendance_events WHERE staff_id = (SELECT staff_id FROM mobile_accounts WHERE id = ?) AND DATE(timestamp) = DATE(?) AND event_type = 'checkin'",
                (self.employee_account_id, timestamp),
            ).fetchone()[0]
        self.assertEqual(count, 1)

    def test_mobile_late_checkin_and_checkout_flow(self):
        account_id = create_mobile_account(
            "late.employee", "late employee test password", "employee", local_user_id=96
        )
        token = self.login("late.employee", "late employee test password")
        headers = {"Authorization": f"Bearer {token}"}
        now = datetime.now(_business_timezone())
        start = (now - timedelta(minutes=30)).strftime("%H:%M")
        end = (now + timedelta(minutes=90)).strftime("%H:%M")
        with get_db_connection(TEST_MOBILE_DB) as conn:
            shift_id = conn.execute(
                "SELECT id FROM cloud_shifts WHERE id = 'shift-morning-default'"
            ).fetchone()[0]
            original_staff_shift = conn.execute(
                "SELECT shift_id FROM cloud_staff WHERE local_user_id = 96"
            ).fetchone()[0]
            original_shift = conn.execute(
                "SELECT start_time, end_time, grace_period_minutes, working_days FROM cloud_shifts WHERE id = 'shift-morning-default'"
            ).fetchone()
            conn.execute(
                "UPDATE cloud_shifts SET start_time = ?, end_time = ?, grace_period_minutes = 5, working_days = '[0,1,2,3,4,5,6]' WHERE id = 'shift-morning-default'",
                (start, end),
            )
            conn.execute("UPDATE cloud_staff SET shift_id = ? WHERE local_user_id = 96", (shift_id,))
            conn.commit()

        try:
            schedule = self.client.get("/api/v1/mobile/employee/schedule", headers=headers)
            self.assertEqual(schedule.status_code, 200, schedule.get_json())
            self.assertTrue(schedule.get_json()["schedule"]["allowed"])
            self.assertEqual(schedule.get_json()["schedule"]["checkin_status"], "late")

            checkin = self.client.post("/api/v1/mobile/employee/check-in", headers=headers, json={})
            self.assertEqual(checkin.status_code, 201, checkin.get_json())
            self.assertEqual(checkin.get_json()["attendance"]["status"], "late")

            schedule_after_checkin = self.client.get("/api/v1/mobile/employee/schedule", headers=headers)
            self.assertEqual(schedule_after_checkin.get_json()["schedule"]["attendance"]["status"], "late")
            self.assertIsNone(schedule_after_checkin.get_json()["schedule"]["checkout"])

            checkout = self.client.post("/api/v1/mobile/employee/check-out", headers=headers, json={})
            self.assertEqual(checkout.status_code, 201, checkout.get_json())
            self.assertEqual(checkout.get_json()["attendance"]["status"], "checked_out")

            repeated_checkout = self.client.post("/api/v1/mobile/employee/check-out", headers=headers, json={})
            self.assertEqual(repeated_checkout.status_code, 200, repeated_checkout.get_json())
            self.assertTrue(repeated_checkout.get_json()["already_marked"])

            schedule_after_checkout = self.client.get("/api/v1/mobile/employee/schedule", headers=headers)
            self.assertEqual(schedule_after_checkout.get_json()["schedule"]["checkout"]["status"], "checked_out")

            with get_db_connection(TEST_MOBILE_DB) as conn:
                events = conn.execute(
                    "SELECT event_type, status FROM cloud_attendance_events WHERE staff_id = (SELECT staff_id FROM mobile_accounts WHERE id = ?) ORDER BY event_type",
                    (account_id,),
                ).fetchall()
            self.assertEqual([(row["event_type"], row["status"]) for row in events], [
                ("checkin", "late"), ("checkout", "checked_out")
            ])
        finally:
            with get_db_connection(TEST_MOBILE_DB) as conn:
                conn.execute(
                    "UPDATE cloud_shifts SET start_time = ?, end_time = ?, grace_period_minutes = ?, working_days = ? WHERE id = 'shift-morning-default'",
                    tuple(original_shift),
                )
                conn.execute("UPDATE cloud_staff SET shift_id = ? WHERE local_user_id = 96", (original_staff_shift,))
                conn.commit()

    def test_mobile_checkout_requires_checkin(self):
        create_mobile_account(
            "checkout.employee", "checkout employee test password", "employee", local_user_id=97
        )
        token = self.login("checkout.employee", "checkout employee test password")
        response = self.client.post(
            "/api/v1/mobile/employee/check-out",
            headers={"Authorization": f"Bearer {token}"},
            json={},
        )
        self.assertEqual(response.status_code, 409)

    def test_admin_can_view_attendance_but_employee_cannot(self):
        admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        response = self.client.get("/api/v1/mobile/admin/attendance", headers=admin_headers)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertIsInstance(response.get_json()["records"], list)
        self.assertEqual(response.get_json()["summary"]["total"], 5)
        self.assertEqual(len(response.get_json()["employees"]), 5)
        staff = next(row for row in response.get_json()["employees"] if row["local_user_id"] == 95)
        self.assertTrue(staff["position"])
        self.assertTrue(staff["department"])

        employee_response = self.client.get(
            "/api/v1/mobile/admin/attendance",
            headers={"Authorization": f"Bearer {self.employee_token}"},
        )
        self.assertEqual(employee_response.status_code, 403)

    def test_camera_mark_pings_employee_and_admin_but_mobile_only_pings_admin(self):
        for token, auth in (
            ("ExponentPushToken[employee-test]", self.employee_token),
            ("ExponentPushToken[admin-test]", self.admin_token),
        ):
            response = self.client.post(
                "/api/v1/mobile/push-token",
                headers={"Authorization": f"Bearer {auth}"},
                json={"token": token, "platform": "ios"},
            )
            self.assertEqual(response.status_code, 200)

        staff_id = None
        with get_db_connection(TEST_MOBILE_DB) as conn:
            staff_id = conn.execute(
                "SELECT staff_id FROM mobile_accounts WHERE id = ?", (self.employee_account_id,)
            ).fetchone()[0]

        with patch("cloud.mobile_api._expo_push") as send_push:
            notify_attendance_event(staff_id, "camera-front-door", "2026-10-14 09:15:00", "front-door", TEST_MOBILE_DB)
            camera_recipients = {message["to"] for message in send_push.call_args.args[0]}
            self.assertEqual(camera_recipients, {
                "ExponentPushToken[employee-test]", "ExponentPushToken[admin-test]"
            })
            self.assertTrue(all(message["channelId"] == "attendance" for message in send_push.call_args.args[0]))

            send_push.reset_mock()
            notify_attendance_event(staff_id, "mobile", "2026-10-14 09:16:00", db_path=TEST_MOBILE_DB)
            mobile_recipients = {message["to"] for message in send_push.call_args.args[0]}
            self.assertEqual(mobile_recipients, {"ExponentPushToken[admin-test]"})

    def test_cloud_shift_change_notifies_registered_mobile_accounts(self):
        for token, auth in (
            ("ExponentPushToken[employee-shift-test]", self.employee_token),
            ("ExponentPushToken[admin-shift-test]", self.admin_token),
        ):
            response = self.client.post(
                "/api/v1/mobile/push-token",
                headers={"Authorization": f"Bearer {auth}"},
                json={"token": token, "platform": "android"},
            )
            self.assertEqual(response.status_code, 200)

        with patch("cloud.mobile_api._expo_push") as send_push:
            notify_shift_schedule_changed("branch-main", TEST_MOBILE_DB)

        messages = send_push.call_args.args[0]
        recipients = {message["to"] for message in messages}
        self.assertTrue({
            "ExponentPushToken[employee-shift-test]", "ExponentPushToken[admin-shift-test]"
        }.issubset(recipients))
        self.assertTrue(all(message["data"]["type"] == "shift_schedule_updated" for message in messages))
        self.assertTrue(all(message["channelId"] == "attendance" for message in messages))

    def test_employee_shift_socket_ticket_is_short_lived_and_role_scoped(self):
        response = self.client.post(
            "/api/v1/mobile/employee/shift-socket-ticket",
            headers={"Authorization": f"Bearer {self.employee_token}"},
            json={},
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        account = load_mobile_shift_socket_account(response.get_json()["ticket"])
        self.assertEqual(account["id"], self.employee_account_id)

        admin_response = self.client.post(
            "/api/v1/mobile/employee/shift-socket-ticket",
            headers={"Authorization": f"Bearer {self.admin_token}"},
            json={},
        )
        self.assertEqual(admin_response.status_code, 403)
        self.assertIsNone(load_mobile_shift_socket_account("tampered-ticket"))


if __name__ == "__main__":
    unittest.main()