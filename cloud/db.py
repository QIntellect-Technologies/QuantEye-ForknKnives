"""
Cloud Database Layer for QIntellect Attendance System (Phase 1)
Strictly isolated from local database.py and local attendance.db.
Implements WAL mode, busy timeouts, multi-tenant schemas, atomic batch transactions,
and robust duplicate prevention.
"""

import sqlite3
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from cloud.config import CLOUD_DB_PATH, SQLITE_TIMEOUT_SECONDS, SQLITE_WAL_MODE

import logging

logger = logging.getLogger("cloud.db")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s] [CLOUD-DB] [%(levelname)s] %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

SELECTED_DEPLOYMENT_EMPLOYEES = [
    {"local_user_id": 95, "name": "Sikander FnK", "department": "FnK Operations", "position": "Floor Supervisor"},
    {"local_user_id": 96, "name": "Shahid Assistant Chef FnK", "department": "FnK Operations", "position": "Assistant Chef"},
    {"local_user_id": 97, "name": "Salman FnK", "department": "FnK Operations", "position": "Kitchen Specialist"},
    {"local_user_id": 98, "name": "Shoaib FnK", "department": "FnK Operations", "position": "Inventory Controller"},
    {"local_user_id": 99, "name": "Siddique FnK", "department": "FnK Operations", "position": "Procurement Officer"},
]


def get_selected_deployment_employee_ids() -> List[int]:
    return [item["local_user_id"] for item in SELECTED_DEPLOYMENT_EMPLOYEES]


def ensure_selected_cloud_staff(org_id: str = 'org-default', branch_id: str = 'branch-main', db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Create or update the five selected deployment staff records without deleting existing cloud users."""
    with get_db_connection(db_path) as conn:
        current_rows = conn.execute(
            "SELECT id, local_user_id, name FROM cloud_staff WHERE branch_id = ?",
            (branch_id,)
        ).fetchall()
        current_by_local = {int(row['local_user_id']) if row['local_user_id'] is not None else None: row for row in current_rows}
        created = []
        for item in SELECTED_DEPLOYMENT_EMPLOYEES:
            local_id = item['local_user_id']
            row = current_by_local.get(local_id)
            if row:
                conn.execute(
                    "UPDATE cloud_staff SET name = ?, department = ?, position = ?, active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (item['name'], item['department'], item['position'], row['id'])
                )
                created.append(dict(row))
                continue

            name_match = conn.execute(
                "SELECT id FROM cloud_staff WHERE branch_id = ? AND LOWER(name) = LOWER(?)",
                (branch_id, item['name'])
            ).fetchone()
            if name_match:
                conn.execute(
                    "UPDATE cloud_staff SET local_user_id = ?, department = ?, position = ?, active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (local_id, item['department'], item['position'], name_match['id'])
                )
                created.append({"id": name_match['id'], "local_user_id": local_id, "name": item['name']})
                continue

            staff_id = f"staff-{uuid.uuid4().hex[:12]}"
            conn.execute(
                "INSERT INTO cloud_staff (id, org_id, branch_id, local_user_id, name, department, position, active) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                (staff_id, org_id, branch_id, local_id, item['name'], item['department'], item['position'])
            )
            created.append({"id": staff_id, "local_user_id": local_id, "name": item['name']})
        conn.commit()
    return created


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Establish an isolated SQLite connection with safe timeout, row factory,
    foreign key enforcement, and WAL pragma.
    """
    target_path = Path(db_path) if db_path else CLOUD_DB_PATH
    
    # Ensure directory exists
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(target_path), timeout=SQLITE_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    
    # Enforce SQLite pragmas for safety and concurrency
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        if SQLITE_WAL_MODE:
            conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except Exception as e:
        logger.warning(f"Could not apply some SQLite pragmas: {e}")
        
    return conn


def init_cloud_db(db_path: Optional[Path] = None):
    """
    Initialize schema for cloud modules:
    - Organizations & Branches
    - Licenses
    - Shifts & Shift Assignments
    - Staff Directory
    - Synced Attendance Events with strictly enforced UNIQUE(installation_id, local_attendance_id)
    """
    target_path = Path(db_path) if db_path else CLOUD_DB_PATH
    logger.info(f"Initializing Cloud Database at: {target_path}")
    
    with get_db_connection(target_path) as conn:
        cursor = conn.cursor()
        
        # 1. Cloud Organizations
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cloud_organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT NOT NULL UNIQUE,
                contact_email TEXT,
                contact_phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. Cloud Branches
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cloud_branches (
                id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                branch_name TEXT NOT NULL,
                branch_code TEXT NOT NULL,
                city TEXT NOT NULL,
                address TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES cloud_organizations(id) ON DELETE CASCADE,
                UNIQUE(org_id, branch_code)
            )
        ''')
        
        # 3. Cloud Licenses (Installation specific)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cloud_licenses (
                id TEXT PRIMARY KEY,
                license_key TEXT NOT NULL UNIQUE,
                org_id TEXT NOT NULL,
                branch_id TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                issued_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                max_employees INTEGER DEFAULT 50,
                max_cameras INTEGER DEFAULT 10,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES cloud_organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (branch_id) REFERENCES cloud_branches(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_licenses_inst ON cloud_licenses(installation_id);')
        
        # 4. Cloud Shifts
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cloud_shifts (
                id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                branch_id TEXT NOT NULL,
                name TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                grace_period_minutes INTEGER DEFAULT 15,
                checkout_grace_period_minutes INTEGER DEFAULT 0,
                working_days TEXT NOT NULL DEFAULT '[0,1,2,3,4,5]',
                is_default INTEGER DEFAULT 0,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES cloud_organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (branch_id) REFERENCES cloud_branches(id) ON DELETE CASCADE,
                UNIQUE(branch_id, name)
            )
        ''')
        
        # 5. Cloud Staff Directory
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cloud_staff (
                id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                branch_id TEXT NOT NULL,
                local_user_id INTEGER,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                cnic TEXT,
                department TEXT,
                position TEXT,
                shift_id TEXT,
                active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES cloud_organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (branch_id) REFERENCES cloud_branches(id) ON DELETE CASCADE,
                FOREIGN KEY (shift_id) REFERENCES cloud_shifts(id) ON DELETE SET NULL,
                UNIQUE(branch_id, name)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_staff_local ON cloud_staff(branch_id, local_user_id);')
        
        # 6. Cloud Attendance Events
        # Idempotency requirement: installation_id + local_attendance_id is UNIQUE
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cloud_attendance_events (
                id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                branch_id TEXT NOT NULL,
                installation_id TEXT NOT NULL,
                local_attendance_id INTEGER NOT NULL,
                staff_id TEXT,
                employee_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT DEFAULT 'checkin',
                status TEXT DEFAULT 'present',
                confidence REAL DEFAULT 1.0,
                camera_id TEXT,
                location TEXT,
                source TEXT,
                marked_by TEXT DEFAULT 'System',
                notes TEXT,
                raw_payload TEXT,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (org_id) REFERENCES cloud_organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (branch_id) REFERENCES cloud_branches(id) ON DELETE CASCADE,
                FOREIGN KEY (staff_id) REFERENCES cloud_staff(id) ON DELETE SET NULL,
                UNIQUE(installation_id, local_attendance_id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_att_lookup ON cloud_attendance_events(org_id, branch_id, timestamp);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_att_staff ON cloud_attendance_events(staff_id, timestamp);')
        
        # Seed default organization & branch if database is fresh
        cursor.execute('SELECT COUNT(*) FROM cloud_organizations')
        if cursor.fetchone()[0] == 0:
            org_id = 'org-default'
            branch_id = 'branch-main'
            cursor.execute('''
                INSERT INTO cloud_organizations (id, name, code, contact_email, contact_phone)
                VALUES (?, ?, ?, ?, ?)
            ''', (org_id, 'QIntellect Technologies', 'QINTELLECT', 'admin@qintellect.ai', '+92 300 0000000'))
            
            cursor.execute('''
                INSERT INTO cloud_branches (id, org_id, branch_name, branch_code, city, address, contact_email, contact_phone)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (branch_id, org_id, 'Main Branch', 'MAIN', 'Lahore', 'Head Office Campus', 'branch@qintellect.ai', '+92 300 0000000'))
            
            # Seed default shift
            shift_id = 'shift-morning-default'
            cursor.execute('''
                INSERT INTO cloud_shifts (id, org_id, branch_id, name, start_time, end_time, grace_period_minutes, checkout_grace_period_minutes, working_days, is_default, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (shift_id, org_id, branch_id, 'Morning Shift', '09:00', '17:00', 15, 0, '[0,1,2,3,4,5]', 1, 1))

        conn.commit()
        ensure_selected_cloud_staff(org_id='org-default', branch_id='branch-main', db_path=target_path)
    logger.info("Cloud Database initialized successfully.")


# -------------------------------------------------------------
# Organization & Branch Operations
# -------------------------------------------------------------

def get_organizations(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM cloud_organizations ORDER BY name ASC").fetchall()
        return [dict(r) for r in rows]


def get_organization_by_id(org_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM cloud_organizations WHERE id = ?", (org_id,)).fetchone()
        return dict(row) if row else None


def update_organization(org_id: str, name: str, code: str, email: str = '', phone: str = '', db_path: Optional[Path] = None) -> bool:
    with get_db_connection(db_path) as conn:
        cur = conn.execute('''
            UPDATE cloud_organizations
            SET name = ?, code = ?, contact_email = ?, contact_phone = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (name, code, email, phone, org_id))
        conn.commit()
        return cur.rowcount > 0


def get_branches(org_id: Optional[str] = None, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        if org_id:
            rows = conn.execute("SELECT * FROM cloud_branches WHERE org_id = ? ORDER BY branch_name ASC", (org_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM cloud_branches ORDER BY branch_name ASC").fetchall()
        return [dict(r) for r in rows]


def get_branch_by_id(branch_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM cloud_branches WHERE id = ?", (branch_id,)).fetchone()
        return dict(row) if row else None


def update_branch(branch_id: str, branch_name: str, branch_code: str, city: str, address: str = '', email: str = '', phone: str = '', db_path: Optional[Path] = None) -> bool:
    with get_db_connection(db_path) as conn:
        cur = conn.execute('''
            UPDATE cloud_branches
            SET branch_name = ?, branch_code = ?, city = ?, address = ?, contact_email = ?, contact_phone = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (branch_name, branch_code, city, address, email, phone, branch_id))
        conn.commit()
        return cur.rowcount > 0


# -------------------------------------------------------------
# License Storage & Verification
# -------------------------------------------------------------

def save_license(
    license_key: str,
    org_id: str,
    branch_id: str,
    installation_id: str,
    issued_at: str,
    expires_at: str,
    max_employees: int = 50,
    max_cameras: int = 10,
    db_path: Optional[Path] = None
) -> str:
    lic_id = f"lic-{uuid.uuid4().hex[:12]}"
    with get_db_connection(db_path) as conn:
        conn.execute('''
            INSERT INTO cloud_licenses (id, license_key, org_id, branch_id, installation_id, issued_at, expires_at, max_employees, max_cameras, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (lic_id, license_key, org_id, branch_id, installation_id, issued_at, expires_at, max_employees, max_cameras))
        conn.commit()
    return lic_id


def get_license_by_key(license_key: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM cloud_licenses WHERE license_key = ?", (license_key,)).fetchone()
        return dict(row) if row else None


def get_licenses_for_branch(branch_id: str, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM cloud_licenses WHERE branch_id = ? ORDER BY created_at DESC", (branch_id,)).fetchall()
        return [dict(r) for r in rows]


# -------------------------------------------------------------
# Shift Management
# -------------------------------------------------------------

def get_shifts(branch_id: str, active_only: bool = True, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        query = "SELECT * FROM cloud_shifts WHERE branch_id = ?"
        params: List[Any] = [branch_id]
        if active_only:
            query += " AND active = 1"
        query += " ORDER BY is_default DESC, name ASC"
        rows = conn.execute(query, params).fetchall()
        shifts = []
        for r in rows:
            d = dict(r)
            try:
                d['working_days'] = json.loads(d.get('working_days', '[]'))
            except Exception:
                d['working_days'] = [0, 1, 2, 3, 4, 5]
            shifts.append(d)
        return shifts


def get_shift_by_id(shift_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM cloud_shifts WHERE id = ?", (shift_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d['working_days'] = json.loads(d.get('working_days', '[]'))
        except Exception:
            d['working_days'] = [0, 1, 2, 3, 4, 5]
        return d


def create_shift(
    org_id: str,
    branch_id: str,
    name: str,
    start_time: str,
    end_time: str,
    grace_period_minutes: int = 15,
    checkout_grace_period_minutes: int = 0,
    working_days: Optional[List[int]] = None,
    is_default: bool = False,
    db_path: Optional[Path] = None
) -> str:
    shift_id = f"shift-{uuid.uuid4().hex[:12]}"
    wd_json = json.dumps(working_days if working_days is not None else [0, 1, 2, 3, 4, 5])
    with get_db_connection(db_path) as conn:
        if is_default:
            conn.execute("UPDATE cloud_shifts SET is_default = 0 WHERE branch_id = ?", (branch_id,))
        conn.execute('''
            INSERT INTO cloud_shifts (id, org_id, branch_id, name, start_time, end_time, grace_period_minutes, checkout_grace_period_minutes, working_days, is_default, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (shift_id, org_id, branch_id, name, start_time, end_time, grace_period_minutes, checkout_grace_period_minutes, wd_json, 1 if is_default else 0))
        conn.commit()
    return shift_id


def update_shift(
    shift_id: str,
    name: str,
    start_time: str,
    end_time: str,
    grace_period_minutes: int = 15,
    checkout_grace_period_minutes: int = 0,
    working_days: Optional[List[int]] = None,
    is_default: Optional[bool] = None,
    db_path: Optional[Path] = None
) -> bool:
    with get_db_connection(db_path) as conn:
        cur_shift = conn.execute("SELECT branch_id FROM cloud_shifts WHERE id = ?", (shift_id,)).fetchone()
        if not cur_shift:
            return False
        branch_id = cur_shift['branch_id']
        
        if is_default:
            conn.execute("UPDATE cloud_shifts SET is_default = 0 WHERE branch_id = ?", (branch_id,))
            
        wd_json = json.dumps(working_days) if working_days is not None else None
        
        updates = ["name = ?", "start_time = ?", "end_time = ?", "grace_period_minutes = ?", "checkout_grace_period_minutes = ?", "updated_at = CURRENT_TIMESTAMP"]
        params: List[Any] = [name, start_time, end_time, grace_period_minutes, checkout_grace_period_minutes]
        
        if wd_json is not None:
            updates.append("working_days = ?")
            params.append(wd_json)
        if is_default is not None:
            updates.append("is_default = ?")
            params.append(1 if is_default else 0)
            
        params.append(shift_id)
        cur = conn.execute(f"UPDATE cloud_shifts SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()
        return cur.rowcount > 0


def set_default_shift(shift_id: str, db_path: Optional[Path] = None) -> bool:
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT branch_id FROM cloud_shifts WHERE id = ?", (shift_id,)).fetchone()
        if not row:
            return False
        branch_id = row['branch_id']
        conn.execute("UPDATE cloud_shifts SET is_default = 0 WHERE branch_id = ?", (branch_id,))
        cur = conn.execute("UPDATE cloud_shifts SET is_default = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (shift_id,))
        conn.commit()
        return cur.rowcount > 0


def delete_shift(shift_id: str, db_path: Optional[Path] = None) -> bool:
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT is_default FROM cloud_shifts WHERE id = ?", (shift_id,)).fetchone()
        if not row:
            return False
        if row['is_default'] == 1:
            raise ValueError("Cannot delete the default shift")
        assigned = conn.execute("SELECT COUNT(*) FROM cloud_staff WHERE shift_id = ?", (shift_id,)).fetchone()[0]
        if assigned > 0:
            raise ValueError(f"Cannot delete shift: it is currently assigned to {assigned} staff member(s)")
        cur = conn.execute("DELETE FROM cloud_shifts WHERE id = ?", (shift_id,))
        conn.commit()
        return cur.rowcount > 0


# -------------------------------------------------------------
# Staff Directory Operations
# -------------------------------------------------------------

def get_staff_list(branch_id: str, active_only: bool = True, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        query = '''
            SELECT s.*, sh.name as shift_name, sh.start_time as shift_start, sh.end_time as shift_end
            FROM cloud_staff s
            LEFT JOIN cloud_shifts sh ON s.shift_id = sh.id
            WHERE s.branch_id = ?
        '''
        params: List[Any] = [branch_id]
        if active_only:
            query += " AND s.active = 1"
        rows = conn.execute(query, params).fetchall()
        staff = [dict(r) for r in rows]
        selected_ids = set(get_selected_deployment_employee_ids())
        selected_names = {item['name'].lower() for item in SELECTED_DEPLOYMENT_EMPLOYEES}
        if selected_ids or selected_names:
            staff = [
                row for row in staff
                if (row.get('local_user_id') is not None and int(row['local_user_id']) in selected_ids)
                or (row.get('name') and row['name'].lower() in selected_names)
            ]
        staff.sort(key=lambda row: row.get('name', ''))
        return staff


def get_staff_by_id(staff_id: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        query = '''
            SELECT s.*, sh.name as shift_name, sh.start_time as shift_start, sh.end_time as shift_end
            FROM cloud_staff s
            LEFT JOIN cloud_shifts sh ON s.shift_id = sh.id
            WHERE s.id = ?
        '''
        row = conn.execute(query, (staff_id,)).fetchone()
        return dict(row) if row else None


def get_staff_by_name(branch_id: str, name: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    with get_db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM cloud_staff WHERE branch_id = ? AND LOWER(name) = LOWER(?)", (branch_id, name.strip())).fetchone()
        return dict(row) if row else None


def create_or_sync_staff(
    org_id: str,
    branch_id: str,
    name: str,
    local_user_id: Optional[int] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    cnic: Optional[str] = None,
    department: Optional[str] = None,
    position: Optional[str] = None,
    shift_id: Optional[str] = None,
    notes: Optional[str] = None,
    active: int = 1,
    db_path: Optional[Path] = None
) -> str:
    with get_db_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM cloud_staff WHERE branch_id = ? AND (LOWER(name) = LOWER(?) OR (local_user_id IS NOT NULL AND local_user_id = ?))",
            (branch_id, name.strip(), local_user_id)
        ).fetchone()
        
        if existing:
            staff_id = existing['id']
            conn.execute('''
                UPDATE cloud_staff
                SET name = ?, local_user_id = COALESCE(?, local_user_id), email = COALESCE(?, email),
                    phone = COALESCE(?, phone), cnic = COALESCE(?, cnic), department = COALESCE(?, department),
                    position = COALESCE(?, position), shift_id = COALESCE(?, shift_id), notes = COALESCE(?, notes),
                    active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (name.strip(), local_user_id, email, phone, cnic, department, position, shift_id, notes, active, staff_id))
            conn.commit()
            return staff_id
        else:
            staff_id = f"staff-{uuid.uuid4().hex[:12]}"
            conn.execute('''
                INSERT INTO cloud_staff (id, org_id, branch_id, local_user_id, name, email, phone, cnic, department, position, shift_id, notes, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (staff_id, org_id, branch_id, local_user_id, name.strip(), email, phone, cnic, department, position, shift_id, notes, active))
            conn.commit()
            return staff_id


def update_staff_profile(
    staff_id: str,
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    cnic: Optional[str] = None,
    department: Optional[str] = None,
    position: Optional[str] = None,
    shift_id: Optional[str] = None,
    notes: Optional[str] = None,
    active: int = 1,
    db_path: Optional[Path] = None
) -> bool:
    with get_db_connection(db_path) as conn:
        cur = conn.execute('''
            UPDATE cloud_staff
            SET name = ?, email = ?, phone = ?, cnic = ?, department = ?, position = ?,
                shift_id = ?, notes = ?, active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (name.strip(), email, phone, cnic, department, position, shift_id, notes, active, staff_id))
        conn.commit()
        return cur.rowcount > 0


def delete_staff(staff_id: str, db_path: Optional[Path] = None) -> bool:
    with get_db_connection(db_path) as conn:
        cur = conn.execute("DELETE FROM cloud_staff WHERE id = ?", (staff_id,))
        conn.commit()
        return cur.rowcount > 0


def set_staff_attendance_status(
    user_id: str,
    target_date: Optional[str],
    status: str,
    check_in_time: Optional[str] = None,
    check_out_time: Optional[str] = None,
    notes: str = '',
    db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """Apply a manual attendance correction for one selected deployment employee and date."""
    normalized_status = str(status or '').strip().lower()
    if normalized_status not in {'present', 'absent'}:
        raise ValueError('Attendance status must be present or absent')

    if not target_date or str(target_date).lower() == 'today':
        target_date = datetime.now(timezone.utc).date().isoformat()
    target = datetime.strptime(str(target_date), '%Y-%m-%d').date()
    date_key = int(target.strftime('%Y%m%d'))

    def make_timestamp(time_value: Optional[str], fallback: str) -> str:
        value = str(time_value or fallback).strip()
        parsed = datetime.strptime(f'{target.isoformat()} {value}', '%Y-%m-%d %H:%M')
        return parsed.strftime('%Y-%m-%d %H:%M:%S')

    check_in_timestamp = make_timestamp(check_in_time, '09:00') if normalized_status == 'present' else None
    check_out_timestamp = make_timestamp(check_out_time, '17:00') if normalized_status == 'present' and check_out_time else None

    with get_db_connection(db_path) as conn:
        staff = conn.execute(
            'SELECT * FROM cloud_staff WHERE branch_id = ? AND (CAST(local_user_id AS TEXT) = ? OR id = ?)',
            ('branch-main', str(user_id), str(user_id))
        ).fetchone()
        if not staff:
            return None

        staff = dict(staff)
        existing = conn.execute(
            'SELECT id, event_type FROM cloud_attendance_events WHERE staff_id = ? AND DATE(timestamp) = ?',
            (staff['id'], target.isoformat())
        ).fetchall()
        if existing:
            conn.execute(
                '''UPDATE cloud_attendance_events
                   SET status = ?, marked_by = 'Admin', source = 'manual',
                       notes = CASE WHEN ? != '' THEN ? ELSE notes END
                   WHERE staff_id = ? AND DATE(timestamp) = ?''',
                (normalized_status, notes, notes, staff['id'], target.isoformat())
            )
            if check_in_timestamp:
                checkin_row = next((row for row in existing if str(row['event_type']).lower() in {'checkin', 'check-in'}), None)
                if checkin_row:
                    conn.execute('UPDATE cloud_attendance_events SET timestamp = ? WHERE id = ?', (check_in_timestamp, checkin_row['id']))
            if check_out_timestamp:
                checkout_row = next((row for row in existing if str(row['event_type']).lower() in {'checkout', 'check-out'}), None)
                if checkout_row:
                    conn.execute('UPDATE cloud_attendance_events SET timestamp = ? WHERE id = ?', (check_out_timestamp, checkout_row['id']))
                else:
                    conn.execute(
                        '''INSERT INTO cloud_attendance_events (
                               id, org_id, branch_id, installation_id, local_attendance_id,
                               staff_id, employee_name, timestamp, event_type, status,
                               confidence, location, source, marked_by, notes
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'checkout', ?, 1.0, '', 'manual', 'Admin', ?)
                           ON CONFLICT(installation_id, local_attendance_id) DO UPDATE SET
                               staff_id = excluded.staff_id,
                               employee_name = excluded.employee_name,
                               timestamp = excluded.timestamp,
                               event_type = excluded.event_type,
                               status = excluded.status,
                               source = excluded.source,
                               marked_by = excluded.marked_by,
                               notes = excluded.notes''',
                        (f"att-{uuid.uuid4().hex[:12]}", staff['org_id'], staff['branch_id'],
                         f"cloud-admin:{staff['id']}", date_key * 2 + 1, staff['id'],
                         staff['name'], check_out_timestamp, normalized_status, notes)
                    )
            conn.commit()
            return {'staff_id': staff['id'], 'user_id': staff['local_user_id'], 'date': target.isoformat(), 'status': normalized_status}

        installation_id = f"cloud-admin:{staff['id']}"
        base_local_id = date_key * 2
        manual_events = [
            (base_local_id, 'checkin', check_in_timestamp or f'{target.isoformat()} 00:00:00')
        ]
        if check_out_timestamp:
            manual_events.append((base_local_id + 1, 'checkout', check_out_timestamp))
        for local_id, event_type, timestamp in manual_events:
            conn.execute(
                '''INSERT INTO cloud_attendance_events (
                       id, org_id, branch_id, installation_id, local_attendance_id,
                       staff_id, employee_name, timestamp, event_type, status,
                       confidence, location, source, marked_by, notes
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, '', 'manual', 'Admin', ?)
                   ON CONFLICT(installation_id, local_attendance_id) DO UPDATE SET
                       staff_id = excluded.staff_id,
                       employee_name = excluded.employee_name,
                       timestamp = excluded.timestamp,
                       event_type = excluded.event_type,
                       status = excluded.status,
                       source = excluded.source,
                       marked_by = excluded.marked_by,
                       notes = excluded.notes''',
                (f"att-{uuid.uuid4().hex[:12]}", staff['org_id'], staff['branch_id'], installation_id,
                 local_id, staff['id'], staff['name'], timestamp, event_type, normalized_status, notes)
            )
        conn.commit()
        return {'staff_id': staff['id'], 'user_id': staff['local_user_id'], 'date': target.isoformat(), 'status': normalized_status}



# -------------------------------------------------------------
# Transactional Batch Attendance Ingestion with Duplicate Prevention
# -------------------------------------------------------------

def ingest_attendance_batch(
    org_id: str,
    branch_id: str,
    installation_id: str,
    events: List[Dict[str, Any]],
    db_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Ingest attendance records atomically within an explicit transaction.
    Guarantees duplicate prevention via UNIQUE(installation_id, local_attendance_id).
    
    Returns breakdown:
    {
      "accepted": count,
      "duplicates": count,
      "rejected": count,
      "errors": list_of_errors,
      "accepted_local_ids": list,
      "duplicate_local_ids": list
    }
    """
    results: Dict[str, Any] = {
        "total": len(events),
        "accepted": 0,
        "duplicates": 0,
        "rejected": 0,
        "errors": [],
        "accepted_local_ids": [],
        "duplicate_local_ids": []
    }
    
    if not events:
        return results
        
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        # Explicit transaction start
        cursor.execute("BEGIN IMMEDIATE;")
        
        for idx, item in enumerate(events):
            local_id = item.get('local_attendance_id') or item.get('id')
            emp_name = str(item.get('detected_name') or item.get('employee_name') or '').strip()
            ts = item.get('timestamp')
            selected_names = {item['name'].lower() for item in SELECTED_DEPLOYMENT_EMPLOYEES}
            selected_ids = set(get_selected_deployment_employee_ids())
            user_id = item.get('user_id')
            user_id_int = None
            try:
                if user_id is not None:
                    user_id_int = int(user_id)
            except (TypeError, ValueError):
                user_id_int = None

            allowed_employee = user_id_int in selected_ids or emp_name.lower() in selected_names
            if not allowed_employee:
                results["rejected"] += 1
                results["errors"].append({
                    "index": idx,
                    "local_attendance_id": local_id,
                    "error": f"Employee not in deployment allowlist: {emp_name or 'unknown'}"
                })
                continue

            # Validation
            if local_id is None or not emp_name or not ts:
                results["rejected"] += 1
                results["errors"].append({
                    "index": idx,
                    "local_attendance_id": local_id,
                    "error": "Missing required fields (local_attendance_id, detected_name/employee_name, timestamp)"
                })
                continue
                
            try:
                local_id_int = int(local_id)
            except (ValueError, TypeError):
                results["rejected"] += 1
                results["errors"].append({
                    "index": idx,
                    "local_attendance_id": local_id,
                    "error": "local_attendance_id must be integer"
                })
                continue
                
            # Check duplicate idempotency identity
            cursor.execute('''
                SELECT id FROM cloud_attendance_events
                WHERE installation_id = ? AND local_attendance_id = ?
            ''', (installation_id, local_id_int))
            existing_row = cursor.fetchone()
            
            if existing_row:
                results["duplicates"] += 1
                results["duplicate_local_ids"].append(local_id_int)
                continue
                
            # Lookup or link staff record
            staff_query = "SELECT id FROM cloud_staff WHERE branch_id = ? AND (LOWER(name) = LOWER(?) OR local_user_id = ?)"
            staff_params = (branch_id, emp_name, user_id_int)
            cursor.execute(staff_query, staff_params)
            staff_row = cursor.fetchone()
            staff_id = staff_row['id'] if staff_row else None
            
            if not staff_id and item.get('auto_link_staff', True):
                # Auto register staff in directory if new
                staff_id = f"staff-{uuid.uuid4().hex[:12]}"
                cursor.execute('''
                    INSERT INTO cloud_staff (id, org_id, branch_id, local_user_id, name, department)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (staff_id, org_id, branch_id, user_id_int, emp_name, item.get('department') or 'General'))
                
            event_uuid = f"att-{uuid.uuid4().hex[:12]}"
            event_type = item.get('event_type') or ('checkout' if 'checkout' in str(item.get('source', '')).lower() else 'checkin')
            status = item.get('status') or 'present'
            if (
                staff_id
                and str(event_type).strip().lower() in {'checkin', 'check-in'}
                and str(status).strip().lower() in {'present', 'late', 'checked_out'}
            ):
                admin_installation_id = f"cloud-admin:{staff_id}"
                cursor.execute('''
                    DELETE FROM cloud_attendance_events
                    WHERE staff_id = ? AND installation_id = ?
                      AND DATE(timestamp) = DATE(?) AND LOWER(status) = 'absent'
                ''', (staff_id, admin_installation_id, ts))
                cursor.execute('''
                    UPDATE cloud_attendance_events
                    SET status = ?
                    WHERE staff_id = ? AND DATE(timestamp) = DATE(?)
                      AND LOWER(status) = 'absent'
                ''', (str(status).strip().lower(), staff_id, ts))
            confidence = float(item.get('confidence', 1.0) or 1.0)
            camera_id = str(item.get('camera_id') or item.get('checkout_camera_id') or item.get('device_id') or '')
            location = str(item.get('location') or item.get('checkout_location') or '')
            source = str(item.get('source') or '')
            marked_by = str(item.get('marked_by') or 'System')
            notes = str(item.get('notes') or '')
            raw_payload = json.dumps(item)
            
            cursor.execute('''
                INSERT INTO cloud_attendance_events (
                    id, org_id, branch_id, installation_id, local_attendance_id, staff_id,
                    employee_name, timestamp, event_type, status, confidence, camera_id,
                    location, source, marked_by, notes, raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                event_uuid, org_id, branch_id, installation_id, local_id_int, staff_id,
                emp_name, ts, event_type, status, confidence, camera_id,
                location, source, marked_by, notes, raw_payload
            ))
            results["accepted"] += 1
            results["accepted_local_ids"].append(local_id_int)
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Transaction failed during attendance batch ingestion: {e}")
        raise e
    finally:
        conn.close()
        
    return results


# -------------------------------------------------------------
# Cloud Attendance Reports Querying
# -------------------------------------------------------------

def query_attendance_reports(
    org_id: str,
    branch_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    department: Optional[str] = None,
    shift_id: Optional[str] = None,
    employee_name: Optional[str] = None,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    camera_id: Optional[str] = None,
    db_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """
    Query attendance records with combinable filters for reporting.
    """
    with get_db_connection(db_path) as conn:
        query = '''
            SELECT a.*,
                   s.local_user_id AS user_id,
                   COALESCE(s.name, a.employee_name) AS name,
                   DATE(a.timestamp) AS date,
                   CASE
                       WHEN LOWER(a.event_type) IN ('checkin', 'check-in')
                            AND LOWER(a.status) IN ('present', 'late', 'checked_out')
                       THEN a.timestamp
                       ELSE NULL
                   END AS first_seen,
                   CASE
                       WHEN LOWER(a.event_type) IN ('checkout', 'check-out')
                       THEN a.timestamp
                       ELSE NULL
                   END AS last_seen,
                   a.camera_id AS checkin_camera,
                   a.location AS checkin_location,
                   s.department, s.position, sh.name as shift_name
            FROM cloud_attendance_events a
            LEFT JOIN cloud_staff s ON a.staff_id = s.id
            LEFT JOIN cloud_shifts sh ON s.shift_id = sh.id
            WHERE a.org_id = ? AND a.branch_id = ?
        '''
        params: List[Any] = [org_id, branch_id]

        selected_ids = get_selected_deployment_employee_ids()
        selected_names = [item['name'].lower() for item in SELECTED_DEPLOYMENT_EMPLOYEES]
        if selected_ids:
            placeholders = ', '.join(['?'] * len(selected_ids))
            query += f" AND (s.local_user_id IN ({placeholders}) OR LOWER(a.employee_name) IN ({', '.join('?' for _ in selected_names)}))"
            params.extend(selected_ids)
            params.extend(selected_names)
        elif selected_names:
            placeholders = ', '.join(['?'] * len(selected_names))
            query += f" AND LOWER(a.employee_name) IN ({placeholders})"
            params.extend(selected_names)

        if start_date:
            query += " AND DATE(a.timestamp) >= DATE(?)"
            params.append(start_date)
        if end_date:
            query += " AND DATE(a.timestamp) <= DATE(?)"
            params.append(end_date)
        if department:
            query += " AND LOWER(s.department) = LOWER(?)"
            params.append(department.strip())
        if shift_id:
            query += " AND s.shift_id = ?"
            params.append(shift_id)
        if employee_name:
            query += " AND LOWER(a.employee_name) LIKE ?"
            params.append(f"%{employee_name.lower().strip()}%")
        if event_type:
            query += " AND LOWER(a.event_type) = LOWER(?)"
            params.append(event_type.strip())
        if status:
            query += " AND LOWER(a.status) = LOWER(?)"
            params.append(status.strip())
        if camera_id:
            query += " AND a.camera_id = ?"
            params.append(camera_id)

        query += " ORDER BY a.timestamp DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
