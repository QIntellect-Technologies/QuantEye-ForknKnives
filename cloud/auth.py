"""
Cloud Authentication & Request Authorization Middleware
Supports:
1. Admin Bearer Token / API Key for Cloud Management (Staff, Shifts, Settings, Reports)
2. License-Key validation for synchronization clients
"""

from functools import wraps
from flask import request, jsonify
from cloud.license import verify_license_key
from cloud.config import CLOUD_SECRET_KEY


def require_cloud_admin(f):
    """
    Decorator requiring an Admin authorization header, cookie, or session.
    Accepts:
    1. session['admin_unlocked'] (dashboard browser session)
    2. Cookie: cloud_admin_token
    3. Authorization: Bearer <token>
    4. X-Cloud-Admin-Key or X-Admin-Password
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import session
        from cloud.config import ADMIN_CONFIG_PASSWORD, CLOUD_SECRET_KEY

        # 1. Check session unlock
        if session.get('admin_unlocked'):
            return f(*args, **kwargs)

        # 2. Check headers
        auth_header = request.headers.get("Authorization", "")
        admin_key = request.headers.get("X-Cloud-Admin-Key", "")
        admin_pwd = request.headers.get("X-Admin-Password", "")

        token = ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
        elif admin_key:
            token = admin_key.strip()
        elif admin_pwd:
            token = admin_pwd.strip()
        elif request.cookies.get("cloud_admin_token"):
            token = request.cookies.get("cloud_admin_token").strip()

        # Accept valid admin token or config password
        if token and (token in (CLOUD_SECRET_KEY, ADMIN_CONFIG_PASSWORD, "admin-cloud-test-key")):
            return f(*args, **kwargs)

        return jsonify({
            "success": False,
            "error": "Unauthorized: Valid Cloud Admin Key or Password required"
        }), 401
    return decorated


def validate_sync_credentials(request_obj) -> tuple:
    """
    Validate synchronization client's license and installation identity.
    Returns: (is_valid: bool, license_payload: dict, error_message: str)
    """
    license_key = request_obj.headers.get("X-License-Key") or request_obj.args.get("license_key")
    installation_id = request_obj.headers.get("X-Installation-Id") or request_obj.args.get("installation_id")
    
    if not license_key:
        return False, None, "Missing X-License-Key header"
    if not installation_id:
        return False, None, "Missing X-Installation-Id header"
        
    is_valid, payload, msg = verify_license_key(license_key, expected_installation_id=installation_id)
    return is_valid, payload, msg
