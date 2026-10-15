"""Authenticated local-client push channel for cloud shift changes."""

import json
import os
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cloud.db import get_db_connection, get_selected_deployment_employee_ids, get_shifts, get_staff_list

_CLIENTS_LOCK = threading.Lock()
_CLIENTS_BY_BRANCH: Dict[str, List[Any]] = {}


def build_shift_snapshot(branch_id: str, db_path=None) -> Dict[str, Any]:
    shifts = get_shifts(branch_id=branch_id, active_only=False, db_path=db_path)
    assignments = [
        {
            'local_user_id': staff.get('local_user_id'),
            'shift_id': staff.get('shift_id'),
            'effective_from': str(staff.get('updated_at') or '')[:10] or None,
        }
        for staff in get_staff_list(branch_id=branch_id, active_only=True, db_path=db_path)
        if staff.get('local_user_id') is not None and staff.get('shift_id')
    ]
    try:
        business_timezone = ZoneInfo(os.environ.get('MOBILE_TIMEZONE', 'Asia/Karachi'))
    except ZoneInfoNotFoundError:
        business_timezone = ZoneInfo('UTC')
    today = datetime.now(business_timezone).date().isoformat()
    employee_ids = get_selected_deployment_employee_ids()
    mobile_attendance = []
    if employee_ids:
        placeholders = ', '.join('?' for _ in employee_ids)
        with get_db_connection(db_path) as conn:
            rows = conn.execute(
                f'''SELECT s.local_user_id, a.employee_name, a.timestamp, a.event_type,
                           a.status, a.source, a.camera_id, a.location,
                           sh.id AS shift_id, sh.name AS shift_name,
                           sh.start_time AS shift_start_time, sh.end_time AS shift_end_time,
                           sh.grace_period_minutes AS shift_grace_period_minutes,
                           sh.checkout_grace_period_minutes AS shift_checkout_grace_period_minutes
                    FROM cloud_attendance_events a
                    JOIN cloud_staff s ON s.id = a.staff_id
                    LEFT JOIN cloud_shifts sh ON sh.id = s.shift_id
                    WHERE a.branch_id = ? AND DATE(a.timestamp) = ?
                      AND LOWER(a.source) = 'mobile'
                      AND LOWER(a.event_type) IN ('checkin', 'check-in', 'checkout', 'check-out')
                      AND s.local_user_id IN ({placeholders})
                    ORDER BY a.timestamp ASC''',
                (branch_id, today, *employee_ids),
            ).fetchall()
            mobile_attendance = [dict(row) for row in rows]
    return {
        'type': 'shift_snapshot',
        'success': True,
        'branch_id': branch_id,
        'shifts': shifts,
        'staff_assignments': assignments,
        'mobile_attendance': mobile_attendance,
    }


def register_shift_client(branch_id: str, client: Any) -> None:
    with _CLIENTS_LOCK:
        _CLIENTS_BY_BRANCH.setdefault(branch_id, []).append(client)


def unregister_shift_client(branch_id: str, client: Any) -> None:
    with _CLIENTS_LOCK:
        clients = _CLIENTS_BY_BRANCH.get(branch_id, [])
        if client in clients:
            clients.remove(client)
        if not clients:
            _CLIENTS_BY_BRANCH.pop(branch_id, None)


def publish_shift_snapshot(branch_id: str, db_path=None) -> int:
    message = json.dumps(build_shift_snapshot(branch_id, db_path=db_path))
    with _CLIENTS_LOCK:
        clients = list(_CLIENTS_BY_BRANCH.get(branch_id, []))

    delivered = 0
    for client in clients:
        try:
            client.send(message)
            delivered += 1
        except Exception:
            unregister_shift_client(branch_id, client)
    return delivered