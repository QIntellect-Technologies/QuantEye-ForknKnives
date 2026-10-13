"""
Cloud Routes: Settings & License Key Management
Phase 1 Scope:
- Organization profile (view & update)
- Branch profile (view & update)
- License key generator with installation-specific expiry dates
- Active licenses listing and verification
Preservation:
- Excluded tabs (Payroll Rules, Payroll Calendar, Salary Structure, Local Camera Config) are strictly absent from this cloud interface.
"""

from flask import Blueprint, request, jsonify
from datetime import datetime, timezone, timedelta
from cloud.db import (
    get_organizations, get_organization_by_id, update_organization,
    get_branches, get_branch_by_id, update_branch,
    save_license, get_license_by_key, get_licenses_for_branch
)
from cloud.license import generate_license_key, verify_license_key
from cloud.auth import require_cloud_admin

settings_bp = Blueprint('cloud_settings', __name__)


# -------------------------------------------------------------
# Organization & Branch Endpoints
# -------------------------------------------------------------

@settings_bp.route('/organizations', methods=['GET'])
@require_cloud_admin
def api_get_organizations():
    orgs = get_organizations()
    return jsonify({"success": True, "organizations": orgs}), 200


@settings_bp.route('/organizations/<org_id>', methods=['GET'])
@require_cloud_admin
def api_get_organization(org_id):
    org = get_organization_by_id(org_id)
    if not org:
        return jsonify({"success": False, "error": "Organization not found"}), 404
    return jsonify({"success": True, "organization": org}), 200


@settings_bp.route('/organizations/<org_id>', methods=['PUT', 'POST'])
@require_cloud_admin
def api_update_organization(org_id):
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    code = data.get('code')
    if not name or not code:
        return jsonify({"success": False, "error": "Name and code are required"}), 400
        
    ok = update_organization(
        org_id=org_id,
        name=name.strip(),
        code=code.strip(),
        email=data.get('email', ''),
        phone=data.get('phone', '')
    )
    if not ok:
        return jsonify({"success": False, "error": "Failed to update organization"}), 400
    return jsonify({"success": True, "message": "Organization updated successfully"}), 200


@settings_bp.route('/branches', methods=['GET'])
@require_cloud_admin
def api_get_branches():
    org_id = request.args.get('org_id')
    branches = get_branches(org_id=org_id)
    return jsonify({"success": True, "branches": branches}), 200


@settings_bp.route('/branches/<branch_id>', methods=['GET'])
@require_cloud_admin
def api_get_branch(branch_id):
    branch = get_branch_by_id(branch_id)
    if not branch:
        return jsonify({"success": False, "error": "Branch not found"}), 404
    return jsonify({"success": True, "branch": branch}), 200


@settings_bp.route('/branches/<branch_id>', methods=['PUT', 'POST'])
@require_cloud_admin
def api_update_branch(branch_id):
    data = request.get_json(silent=True) or {}
    branch_name = data.get('branch_name')
    branch_code = data.get('branch_code')
    city = data.get('city')
    if not branch_name or not branch_code or not city:
        return jsonify({"success": False, "error": "Branch name, code, and city are required"}), 400
        
    ok = update_branch(
        branch_id=branch_id,
        branch_name=branch_name.strip(),
        branch_code=branch_code.strip(),
        city=city.strip(),
        address=data.get('address', ''),
        email=data.get('contact_email', ''),
        phone=data.get('contact_phone', '')
    )
    if not ok:
        return jsonify({"success": False, "error": "Failed to update branch"}), 400
    return jsonify({"success": True, "message": "Branch updated successfully"}), 200


# -------------------------------------------------------------
# License Generator & Management
# -------------------------------------------------------------

@settings_bp.route('/licenses/generate', methods=['POST'])
@require_cloud_admin
def api_generate_license():
    """
    Generate an installation-specific license key with configurable expiry date.
    """
    data = request.get_json(silent=True) or {}
    org_id = data.get('org_id')
    branch_id = data.get('branch_id')
    installation_id = data.get('installation_id')
    days_valid = data.get('days_valid')
    expires_at_str = data.get('expires_at')
    max_employees = int(data.get('max_employees', 50) or 50)
    max_cameras = int(data.get('max_cameras', 10) or 10)
    
    if not org_id or not branch_id or not installation_id:
        return jsonify({
            "success": False,
            "error": "org_id, branch_id, and installation_id are required"
        }), 400
        
    # Calculate expiry
    if expires_at_str:
        try:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        except Exception:
            return jsonify({"success": False, "error": "Invalid expires_at format. Use ISO-8601"}), 400
    else:
        days = int(days_valid or 30)
        expires_at = datetime.now(timezone.utc) + timedelta(days=days)
        
    expires_at_iso = expires_at.isoformat()
    issued_at_iso = datetime.now(timezone.utc).isoformat()
    
    # Generate cryptographic license key
    license_key = generate_license_key(
        org_id=org_id,
        branch_id=branch_id,
        installation_id=installation_id,
        expires_at_iso=expires_at_iso,
        max_employees=max_employees,
        max_cameras=max_cameras
    )
    
    # Record license in DB
    lic_id = save_license(
        license_key=license_key,
        org_id=org_id,
        branch_id=branch_id,
        installation_id=installation_id,
        issued_at=issued_at_iso,
        expires_at=expires_at_iso,
        max_employees=max_employees,
        max_cameras=max_cameras
    )
    
    return jsonify({
        "success": True,
        "license_id": lic_id,
        "license_key": license_key,
        "installation_id": installation_id,
        "issued_at": issued_at_iso,
        "expires_at": expires_at_iso,
        "max_employees": max_employees,
        "max_cameras": max_cameras
    }), 201


@settings_bp.route('/licenses/verify', methods=['POST'])
def api_verify_license():
    """
    Public or client-callable license verification endpoint.
    """
    data = request.get_json(silent=True) or {}
    license_key = data.get('license_key') or request.headers.get('X-License-Key')
    installation_id = data.get('installation_id') or request.headers.get('X-Installation-Id')
    
    if not license_key:
        return jsonify({"success": False, "error": "license_key is required"}), 400
        
    is_valid, payload, msg = verify_license_key(license_key, expected_installation_id=installation_id)
    return jsonify({
        "success": is_valid,
        "valid": is_valid,
        "message": msg,
        "payload": payload
    }), (200 if is_valid else 400)


@settings_bp.route('/licenses', methods=['GET'])
@require_cloud_admin
def api_list_licenses():
    branch_id = request.args.get('branch_id', 'branch-main')
    licenses = get_licenses_for_branch(branch_id)
    return jsonify({"success": True, "licenses": licenses}), 200
