"""Authenticated local-client push channel for cloud shift changes."""

import json
import threading
from typing import Any, Dict, List, Optional

from cloud.db import get_shifts, get_staff_list

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
    return {
        'type': 'shift_snapshot',
        'success': True,
        'branch_id': branch_id,
        'shifts': shifts,
        'staff_assignments': assignments,
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