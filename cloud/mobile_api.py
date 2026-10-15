"""Authenticated employee and admin endpoints for the FNK mobile pilot."""

import json
import logging
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from cloud.config import CLOUD_SECRET_KEY
from cloud.db import get_db_connection, get_selected_deployment_employee_ids

logger = logging.getLogger("cloud.mobile")
mobile_bp = Blueprint("mobile_api", __name__)
MOBILE_TOKEN_MAX_AGE_SECONDS = 14 * 24 * 60 * 60
MOBILE_SHIFT_TICKET_MAX_AGE_SECONDS = 60


def _serializer() -> URLSafeTimedSerializer:
    secret = os.environ.get("MOBILE_AUTH_SECRET") or CLOUD_SECRET_KEY
    return URLSafeTimedSerializer(secret, salt="qintellect-mobile-session-v1")


def _shift_ticket_serializer() -> URLSafeTimedSerializer:
    secret = os.environ.get("MOBILE_AUTH_SECRET") or CLOUD_SECRET_KEY
    return URLSafeTimedSerializer(secret, salt="qintellect-mobile-shift-socket-v1")


def load_mobile_shift_socket_account(ticket: str):
    try:
        payload = _shift_ticket_serializer().loads(
            ticket, max_age=MOBILE_SHIFT_TICKET_MAX_AGE_SECONDS
        )
    except (BadSignature, SignatureExpired):
        return None
    account_id = payload.get("account_id") if isinstance(payload, dict) else None
    if not account_id:
        return None
    with get_db_connection() as conn:
        account = conn.execute(
            """SELECT id, username, role, staff_id, branch_id FROM mobile_accounts
               WHERE id = ? AND active = 1 AND role = 'employee'""",
            (account_id,),
        ).fetchone()
    return dict(account) if account else None


def _business_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(os.environ.get("MOBILE_TIMEZONE", "Asia/Karachi"))
    except ZoneInfoNotFoundError:
        logger.warning("Unknown MOBILE_TIMEZONE; using UTC")
        return ZoneInfo("UTC")


def create_mobile_account(
    username: str,
    password: str,
    role: str,
    local_user_id: Optional[int] = None,
    branch_id: str = "branch-main",
    display_name: Optional[str] = None,
    department: Optional[str] = None,
    position: Optional[str] = None,
    db_path=None,
) -> str:
    """Provision an account from a trusted script; there is intentionally no signup API."""
    normalized_username = str(username or "").strip()
    normalized_role = str(role or "").strip().lower()
    if len(normalized_username) < 3:
        raise ValueError("Username must contain at least 3 characters")
    if len(password or "") < 10:
        raise ValueError("Password must contain at least 10 characters")
    if normalized_role not in {"employee", "admin"}:
        raise ValueError("Role must be employee or admin")

    staff_id = None
    with get_db_connection(db_path) as conn:
        if normalized_role == "employee":
            if local_user_id is None or int(local_user_id) not in get_selected_deployment_employee_ids():
                raise ValueError("Employee account must map to a selected FNK employee ID")
            staff = conn.execute(
                "SELECT id FROM cloud_staff WHERE branch_id = ? AND local_user_id = ? AND active = 1",
                (branch_id, int(local_user_id)),
            ).fetchone()
            if not staff:
                raise ValueError("Active cloud staff record was not found for that employee ID")
            staff_id = staff["id"]
        account_id = f"mobile-{uuid.uuid4().hex[:16]}"
        conn.execute(
                """INSERT INTO mobile_accounts (
                         id, username, password_hash, role, staff_id, branch_id, display_name, department, position
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (account_id, normalized_username, generate_password_hash(password), normalized_role, staff_id,
                 branch_id, str(display_name or normalized_username).strip(),
                 str(department or '').strip(), str(position or '').strip()),
        )
        conn.commit()
    return account_id


def bootstrap_mobile_accounts_from_env(db_path=None) -> Dict[str, int]:
    """Provision configured mobile accounts without exposing passwords in logs."""
    raw_config = os.environ.get("MOBILE_BOOTSTRAP_ACCOUNTS")
    result = {"created": 0, "unchanged": 0, "mismatched": 0}
    if not raw_config:
        return result

    try:
        configured_accounts = json.loads(raw_config)
    except json.JSONDecodeError as error:
        raise ValueError("MOBILE_BOOTSTRAP_ACCOUNTS must contain valid JSON") from error
    if not isinstance(configured_accounts, list):
        raise ValueError("MOBILE_BOOTSTRAP_ACCOUNTS must be a JSON array")

    accounts = []
    seen_usernames = set()
    selected_employee_ids = set(get_selected_deployment_employee_ids())
    for index, entry in enumerate(configured_accounts):
        if not isinstance(entry, dict):
            raise ValueError(f"Mobile bootstrap entry {index + 1} must be an object")

        username = str(entry.get("username") or "").strip()
        password = entry.get("password")
        role = str(entry.get("role") or "employee").strip().lower()
        branch_id = str(entry.get("branch_id") or "branch-main").strip()
        employee_id = entry.get("employee_id")
        if len(username) < 3:
            raise ValueError(f"Mobile bootstrap entry {index + 1} has an invalid username")
        if not isinstance(password, str) or len(password) < 10:
            raise ValueError(f"Mobile bootstrap password for '{username}' must contain at least 10 characters")
        if role not in {"employee", "admin"}:
            raise ValueError(f"Mobile bootstrap role for '{username}' must be employee or admin")
        if not branch_id:
            raise ValueError(f"Mobile bootstrap branch for '{username}' cannot be empty")

        if role == "employee":
            if isinstance(employee_id, bool):
                raise ValueError(f"Mobile employee '{username}' requires a valid employee_id")
            try:
                employee_id = int(employee_id)
            except (TypeError, ValueError) as error:
                raise ValueError(f"Mobile employee '{username}' requires a valid employee_id") from error
            if employee_id not in selected_employee_ids:
                raise ValueError(f"Mobile employee '{username}' must map to a selected FNK employee ID")
        elif employee_id is not None:
            raise ValueError(f"Mobile admin '{username}' must not have an employee_id")

        normalized_key = username.casefold()
        if normalized_key in seen_usernames:
            raise ValueError(f"Duplicate mobile bootstrap username '{username}'")
        seen_usernames.add(normalized_key)
        accounts.append({
            "username": username,
            "password": password,
            "role": role,
            "branch_id": branch_id,
            "employee_id": employee_id,
            "display_name": entry.get("display_name"),
            "department": entry.get("department"),
            "position": entry.get("position"),
        })

    for account in accounts:
        with get_db_connection(db_path) as conn:
            existing = conn.execute(
                """SELECT a.id, a.role, a.branch_id, a.staff_id, s.id AS resolved_staff_id,
                          s.local_user_id, s.branch_id AS staff_branch_id
                   FROM mobile_accounts a
                   LEFT JOIN cloud_staff s ON s.id = a.staff_id
                   WHERE a.username = ?""",
                (account["username"],),
            ).fetchone()

        if existing:
            expected_employee_id = account["employee_id"]
            mapping_matches = (
                existing["local_user_id"] == expected_employee_id
                and (expected_employee_id is None or existing["resolved_staff_id"] is not None)
                and (expected_employee_id is None or existing["staff_branch_id"] == account["branch_id"])
                and (expected_employee_id is not None or existing["staff_id"] is None)
            )
            if (
                existing["role"] == account["role"]
                and existing["branch_id"] == account["branch_id"]
                and mapping_matches
            ):
                result["unchanged"] += 1
                logger.info("Mobile bootstrap account '%s' already matches its configured role and mapping.", account["username"])
            else:
                result["mismatched"] += 1
                logger.warning("Mobile bootstrap account '%s' has a role, branch, or employee mapping mismatch; leaving it unchanged.", account["username"])
            continue

        create_mobile_account(
            username=account["username"],
            password=account["password"],
            role=account["role"],
            local_user_id=account["employee_id"],
            branch_id=account["branch_id"],
            display_name=account["display_name"],
            department=account["department"],
            position=account["position"],
            db_path=db_path,
        )
        result["created"] += 1
        logger.info("Provisioned mobile bootstrap account '%s' with role '%s'.", account["username"], account["role"])

    logger.info(
        "Mobile account bootstrap finished: %d created, %d unchanged, %d mismatched.",
        result["created"], result["unchanged"], result["mismatched"],
    )
    return result


def _load_account_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        payload = _serializer().loads(
            auth_header[7:].strip(), max_age=MOBILE_TOKEN_MAX_AGE_SECONDS
        )
    except SignatureExpired:
        return None
    except BadSignature:
        return None
    account_id = payload.get("account_id") if isinstance(payload, dict) else None
    if not account_id:
        return None
    with get_db_connection() as conn:
        account = conn.execute(
            "SELECT id, username, role, staff_id, branch_id, display_name, department, position FROM mobile_accounts WHERE id = ? AND active = 1",
            (account_id,),
        ).fetchone()
    return dict(account) if account else None


def require_mobile_role(*roles):
    def decorate(handler):
        @wraps(handler)
        def wrapped(*args, **kwargs):
            account = _load_account_token()
            if not account:
                return jsonify({"success": False, "error": "Sign in again to continue."}), 401
            if roles and account["role"] not in roles:
                return jsonify({"success": False, "error": "This account cannot access that page."}), 403
            g.mobile_account = account
            return handler(*args, **kwargs)
        return wrapped
    return decorate


def _get_employee_context(account: Dict[str, Any], db_path=None):
    if not account.get("staff_id"):
        return None
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            """SELECT s.id AS staff_id, s.local_user_id, s.name, s.department, s.position, s.branch_id,
                      s.shift_id, sh.name AS shift_name, sh.start_time, sh.end_time,
                      sh.grace_period_minutes, sh.working_days, sh.active AS shift_active
               FROM cloud_staff s LEFT JOIN cloud_shifts sh ON sh.id = s.shift_id
               WHERE s.id = ? AND s.active = 1 AND s.branch_id = ?""",
            (account["staff_id"], account["branch_id"]),
        ).fetchone()
    return dict(row) if row else None


def _shift_check(shift: Dict[str, Any], current: datetime) -> Dict[str, Any]:
    if not shift.get("shift_id") or not shift.get("shift_active"):
        return {"allowed": False, "reason": "No active shift is assigned."}
    start = str(shift.get("start_time") or "09:00")
    end = str(shift.get("end_time") or "17:00")
    start_minutes = int(start[:2]) * 60 + int(start[3:5])
    end_minutes = int(end[:2]) * 60 + int(end[3:5])
    current_minutes = current.hour * 60 + current.minute
    try:
        working_days = {int(day) for day in json.loads(shift.get("working_days") or "[0,1,2,3,4,5]")}
    except (TypeError, ValueError, json.JSONDecodeError):
        working_days = {0, 1, 2, 3, 4, 5}

    scheduled_date = current.date()
    if start_minutes > end_minutes and current_minutes <= end_minutes:
        from datetime import timedelta
        scheduled_date -= timedelta(days=1)
    if scheduled_date.weekday() not in working_days:
        return {"allowed": False, "reason": f"{scheduled_date.strftime('%A')} is not a scheduled workday."}

    grace = max(0, int(shift.get("grace_period_minutes") or 0))
    if grace:
        grace_end = start_minutes + grace
        if grace_end < 1440:
            allowed = start_minutes <= current_minutes <= grace_end
        else:
            allowed = current_minutes >= start_minutes or current_minutes <= grace_end % 1440
    elif start_minutes <= end_minutes:
        allowed = start_minutes <= current_minutes <= end_minutes
    else:
        allowed = current_minutes >= start_minutes or current_minutes <= end_minutes

    if not allowed:
        return {"allowed": False, "reason": f"Check-in is outside {shift['shift_name']} hours."}
    return {"allowed": True, "reason": "Within the assigned shift."}


def _attendance_for_day(staff_id: str, target_date: str, db_path=None):
    with get_db_connection(db_path) as conn:
        row = conn.execute(
            """SELECT timestamp, source, camera_id, event_type, status
               FROM cloud_attendance_events
               WHERE staff_id = ? AND DATE(timestamp) = ?
                 AND LOWER(event_type) IN ('checkin', 'check-in')
                 AND LOWER(status) IN ('present', 'late', 'checked_out')
               ORDER BY timestamp ASC LIMIT 1""",
            (staff_id, target_date),
        ).fetchone()
    return dict(row) if row else None


def _expo_push(messages):
    if not messages:
        return
    request_body = json.dumps(messages).encode("utf-8")
    push_request = urllib.request.Request(
        "https://exp.host/--/api/v2/push/send",
        data=request_body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(push_request, timeout=5) as response:
            if response.status >= 300:
                logger.warning("Expo push service returned HTTP %s", response.status)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        logger.warning("Could not deliver mobile push notification: %s", error)


def notify_attendance_event(staff_id: str, source: str, timestamp: str, camera_id: str = "", db_path=None) -> None:
    """Notify admins for every new mark and the employee when a camera made the mark."""
    with get_db_connection(db_path) as conn:
        staff = conn.execute("SELECT name, branch_id FROM cloud_staff WHERE id = ?", (staff_id,)).fetchone()
        if not staff:
            return
        tokens = conn.execute(
            """SELECT DISTINCT t.token, a.role, a.staff_id
               FROM mobile_device_tokens t JOIN mobile_accounts a ON a.id = t.account_id
               WHERE a.active = 1 AND a.branch_id = ?""",
            (staff["branch_id"],),
        ).fetchall()

    messages = []
    for token in tokens:
        is_employee_camera_notice = source != "mobile" and token["role"] == "employee" and token["staff_id"] == staff_id
        is_admin_notice = token["role"] == "admin"
        if not (is_employee_camera_notice or is_admin_notice):
            continue
        title = "Attendance recorded" if is_employee_camera_notice else f"{staff['name']} checked in"
        body = f"{timestamp} · {source.title()}"
        if camera_id and source != "mobile":
            body += f" · {camera_id}"
        messages.append({
            "to": token["token"],
            "title": title,
            "body": body,
            "sound": "default",
            "channelId": "attendance",
            "data": {"type": "attendance", "staff_id": staff_id, "source": source, "timestamp": timestamp},
        })
    _expo_push(messages)


def notify_shift_schedule_changed(branch_id: str, db_path=None) -> None:
    """Push a refresh hint to mobile accounts when a cloud shift changes."""
    with get_db_connection(db_path) as conn:
        tokens = conn.execute(
            """SELECT DISTINCT t.token FROM mobile_device_tokens t
               JOIN mobile_accounts a ON a.id = t.account_id
               WHERE a.active = 1 AND a.branch_id = ?""",
            (branch_id,),
        ).fetchall()
    _expo_push([{
        "to": row["token"],
        "title": "Shift schedule updated",
        "body": "Open FNK Attendance to load your latest shift times.",
        "sound": "default",
        "channelId": "attendance",
        "data": {"type": "shift_schedule_updated", "branch_id": branch_id},
    } for row in tokens])


@mobile_bp.post("/login")
def mobile_login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username") or "").strip()
    password = str(data.get("password") or "")
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role, staff_id, branch_id, display_name, department, position FROM mobile_accounts WHERE username = ? AND active = 1",
            (username,),
        ).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"success": False, "error": "Username or password is incorrect."}), 401
    account = dict(row)
    token = _serializer().dumps({"account_id": account["id"]})
    staff = _get_employee_context(account) if account["role"] == "employee" else None
    return jsonify({
        "success": True,
        "token": token,
        "account": {
            "username": account["username"],
            "role": account["role"],
            "name": staff["name"] if staff else account.get("display_name") or "FNK Admin",
            "employee_id": staff["local_user_id"] if staff else None,
            "department": staff.get("department") if staff else account.get("department"),
            "position": staff.get("position") if staff else account.get("position"),
        },
    }), 200


@mobile_bp.get("/me")
@require_mobile_role("employee", "admin")
def mobile_me():
    account = g.mobile_account
    staff = _get_employee_context(account) if account["role"] == "employee" else None
    if account["role"] == "employee" and not staff:
        return jsonify({"success": False, "error": "Employee account is no longer active."}), 403
    return jsonify({"success": True, "account": {
        "username": account["username"], "role": account["role"],
        "name": staff["name"] if staff else account.get("display_name") or "FNK Admin",
        "employee_id": staff["local_user_id"] if staff else None,
        "department": staff.get("department") if staff else account.get("department"),
        "position": staff.get("position") if staff else account.get("position"),
    }}), 200


@mobile_bp.post("/push-token")
@require_mobile_role("employee", "admin")
def register_push_token():
    data = request.get_json(silent=True) or {}
    token = str(data.get("token") or "").strip()
    platform = str(data.get("platform") or "").strip().lower()
    if not token.startswith(("ExponentPushToken[", "ExpoPushToken[")) or not token.endswith("]"):
        return jsonify({"success": False, "error": "A valid Expo push token is required."}), 400
    with get_db_connection() as conn:
        conn.execute(
            """INSERT INTO mobile_device_tokens (token, account_id, platform)
               VALUES (?, ?, ?)
               ON CONFLICT(token) DO UPDATE SET account_id = excluded.account_id, platform = excluded.platform""",
            (token, g.mobile_account["id"], platform),
        )
        conn.commit()
    return jsonify({"success": True}), 200


@mobile_bp.post("/employee/shift-socket-ticket")
@require_mobile_role("employee")
def issue_employee_shift_socket_ticket():
    ticket = _shift_ticket_serializer().dumps({"account_id": g.mobile_account["id"]})
    return jsonify({"success": True, "ticket": ticket, "expires_in": MOBILE_SHIFT_TICKET_MAX_AGE_SECONDS}), 200


@mobile_bp.get("/employee/schedule")
@require_mobile_role("employee")
def employee_schedule():
    account = g.mobile_account
    staff = _get_employee_context(account)
    if not staff:
        return jsonify({"success": False, "error": "No active cloud shift is assigned."}), 404
    now = datetime.now(_business_timezone())
    shift_result = _shift_check(staff, now)
    attendance = _attendance_for_day(staff["staff_id"], now.date().isoformat())
    schedule = {
        "shift_name": staff["shift_name"], "start_time": staff["start_time"],
        "end_time": staff["end_time"], "grace_period_minutes": staff["grace_period_minutes"],
        "working_days": json.loads(staff["working_days"] or "[0,1,2,3,4,5]"),
        "local_date": now.date().isoformat(), "allowed": shift_result["allowed"],
        "reason": shift_result["reason"], "attendance": attendance,
    }
    return jsonify({"success": True, "schedule": schedule}), 200


@mobile_bp.post("/employee/check-in")
@require_mobile_role("employee")
def employee_check_in():
    account = g.mobile_account
    staff = _get_employee_context(account)
    if not staff:
        return jsonify({"success": False, "error": "No active cloud shift is assigned."}), 404
    now = datetime.now(_business_timezone())
    shift_result = _shift_check(staff, now)
    if not shift_result["allowed"]:
        return jsonify({"success": False, "error": shift_result["reason"], "schedule": shift_result}), 409

    timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
    date_key = int(now.strftime("%Y%m%d"))
    with get_db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            """SELECT id, timestamp, source, camera_id FROM cloud_attendance_events
               WHERE staff_id = ? AND DATE(timestamp) = ?
                 AND LOWER(event_type) IN ('checkin', 'check-in')
                 AND LOWER(status) IN ('present', 'late', 'checked_out')
               ORDER BY timestamp ASC LIMIT 1""",
            (staff["staff_id"], now.date().isoformat()),
        ).fetchone()
        if existing:
            conn.commit()
            return jsonify({
                "success": True, "already_marked": True,
                "attendance": {"timestamp": existing["timestamp"], "source": existing["source"], "camera_id": existing["camera_id"]},
                "message": "Attendance was already marked for this shift.",
            }), 200

        absent = conn.execute(
            """SELECT id FROM cloud_attendance_events WHERE staff_id = ? AND DATE(timestamp) = ?
               AND LOWER(event_type) IN ('checkin', 'check-in') AND LOWER(status) = 'absent'
               ORDER BY timestamp ASC LIMIT 1""",
            (staff["staff_id"], now.date().isoformat()),
        ).fetchone()
        if absent:
            conn.execute(
                """UPDATE cloud_attendance_events SET timestamp = ?, status = 'present', source = 'mobile',
                   marked_by = ?, notes = 'Employee mobile check-in' WHERE id = ?""",
                (timestamp, account["username"], absent["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO cloud_attendance_events (
                       id, org_id, branch_id, installation_id, local_attendance_id,
                       staff_id, employee_name, timestamp, event_type, status,
                       confidence, location, source, marked_by, notes
                   ) VALUES (?, 'org-default', ?, ?, ?, ?, ?, ?, 'checkin', 'present', 1.0, '', 'mobile', ?, 'Employee mobile check-in')
                   ON CONFLICT(installation_id, local_attendance_id) DO NOTHING""",
                (f"att-{uuid.uuid4().hex[:12]}", staff["branch_id"], f"mobile:{account['id']}",
                 date_key * 2, staff["staff_id"], staff["name"], timestamp, account["username"]),
            )
        conn.commit()

    notify_attendance_event(staff["staff_id"], "mobile", timestamp)
    return jsonify({"success": True, "already_marked": False, "attendance": {"timestamp": timestamp, "source": "mobile"}}), 201


@mobile_bp.get("/admin/attendance")
@require_mobile_role("admin")
def admin_attendance():
    target_date = request.args.get("date") or datetime.now(_business_timezone()).date().isoformat()
    selected_ids = get_selected_deployment_employee_ids()
    placeholders = ",".join("?" for _ in selected_ids)
    selected_names = ("sikander fnk", "shahid assistant chef fnk", "salman fnk", "shoaib fnk", "siddique fnk")
    with get_db_connection() as conn:
        rows = conn.execute(
            f"""SELECT a.id, a.employee_name, a.timestamp, a.event_type, a.status,
                       a.source, a.camera_id, a.location, s.local_user_id, s.department, s.position
                FROM cloud_attendance_events a LEFT JOIN cloud_staff s ON s.id = a.staff_id
                WHERE a.branch_id = ? AND DATE(a.timestamp) = ?
                  AND (s.local_user_id IN ({placeholders}) OR LOWER(a.employee_name) IN (?, ?, ?, ?, ?))
                ORDER BY a.timestamp DESC""",
            (g.mobile_account["branch_id"], target_date, *selected_ids,
             *selected_names),
        ).fetchall()
        staff_rows = conn.execute(
            f"""SELECT s.id AS staff_id, s.local_user_id, s.name, s.department, s.position,
                       sh.name AS shift_name, sh.start_time, sh.end_time
                FROM cloud_staff s LEFT JOIN cloud_shifts sh ON sh.id = s.shift_id
                WHERE s.branch_id = ? AND s.active = 1
                  AND (s.local_user_id IN ({placeholders}) OR LOWER(s.name) IN (?, ?, ?, ?, ?))
                ORDER BY s.local_user_id""",
            (g.mobile_account["branch_id"], *selected_ids, *selected_names),
        ).fetchall()
        employees = []
        for staff in staff_rows:
            checkin = conn.execute(
                """SELECT timestamp, source, camera_id, location FROM cloud_attendance_events
                   WHERE staff_id = ? AND DATE(timestamp) = ?
                     AND LOWER(event_type) IN ('checkin', 'check-in')
                     AND LOWER(status) IN ('present', 'late', 'checked_out')
                   ORDER BY timestamp ASC LIMIT 1""",
                (staff["staff_id"], target_date),
            ).fetchone()
            employee = dict(staff)
            employee["attendance"] = dict(checkin) if checkin else None
            employee["status"] = "marked" if checkin else "waiting"
            employees.append(employee)

    marked = sum(1 for employee in employees if employee["attendance"])
    mobile_marked = sum(
        1 for employee in employees
        if employee["attendance"] and str(employee["attendance"].get("source") or "").lower() == "mobile"
    )
    camera_marked = sum(
        1 for employee in employees
        if employee["attendance"] and str(employee["attendance"].get("source") or "").lower() != "mobile"
    )
    return jsonify({
        "success": True,
        "date": target_date,
        "records": [dict(row) for row in rows],
        "employees": employees,
        "summary": {
            "total": len(employees),
            "marked": marked,
            "waiting": len(employees) - marked,
            "mobile": mobile_marked,
            "camera": camera_marked,
        },
    }), 200