"""
Cloud Configuration for QIntellect Attendance System (Phase 1)
Isolated from local attendance system configuration.
"""

import os
import sys
from pathlib import Path

# Base directory for the Flask-Attendence root
BASE_DIR = Path(__file__).resolve().parent.parent

# Cloud DB Path - strictly isolated, defaults to cloud_attendance.db in BASE_DIR or custom path
CLOUD_DB_NAME = os.environ.get('CLOUD_DB_NAME', 'cloud_attendance.db')
CLOUD_DB_PATH = Path(os.environ.get('CLOUD_DB_PATH', str(BASE_DIR / CLOUD_DB_NAME)))

# License Secret Key for HMAC signature generation and validation
CLOUD_SECRET_KEY = os.environ.get('CLOUD_SECRET_KEY', 'qintellect-cloud-secret-key-2026-secure-token')

# SQLite connection settings
SQLITE_TIMEOUT_SECONDS = float(os.environ.get('CLOUD_SQLITE_TIMEOUT', '30.0'))
SQLITE_WAL_MODE = os.environ.get('CLOUD_SQLITE_WAL', 'true').lower() in ('true', '1', 'yes')

# Cloud API Settings
CLOUD_API_PREFIX = '/api/v1'

# Admin configuration password (defaults to .env or system admin password)
ADMIN_CONFIG_PASSWORD = os.environ.get('ADMIN_CONFIG_PASSWORD', '')
if not ADMIN_CONFIG_PASSWORD:
    env_file = BASE_DIR / '.env'
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('ADMIN_CONFIG_PASSWORD='):
                        ADMIN_CONFIG_PASSWORD = line.split('=', 1)[1].strip()
                        break
        except Exception:
            pass
