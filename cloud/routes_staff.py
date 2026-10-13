"""
Cloud Routes: Staff Directory
Phase 1 Scope:
- Staff listing with shift and department associations
- Staff creation and profile updates
- Preserves local application contracts (_safe_user dictionary output)
- Does not modify local recognition models or local SQLite embeddings
"""

from flask import Blueprint, request, jsonify
from cloud.db import (
    get_staff_list, get_staff_by_id, create_or_sync_staff, update_staff_profile
)
from cloud.auth import require_cloud_admin

staff_bp = Blueprint('cloud_staff', __name__)


@staff_bp.route('', methods=['GET'])
@staff_bp.route('/', methods=['GET'])
@require_cloud_admin
def api_get_staff():
    branch_id = request.args.get('branch_id', 'branch-main')
    active_only = request.args.get('active_only', 'false').lower() == 'true'
    staff = get_staff_list(branch_id=branch_id, active_only=active_only)
    return jsonify({"success": True, "staff": staff}), 200


@staff_bp.route('/<staff_id>', methods=['GET'])
@require_cloud_admin
def api_get_single_staff(staff_id):
    person = get_staff_by_id(staff_id)
    if not person:
        return jsonify({"success": False, "error": "Staff member not found"}), 404
    return jsonify({"success": True, "staff": person}), 200


@staff_bp.route('', methods=['POST'])
@staff_bp.route('/', methods=['POST'])
@require_cloud_admin
def api_create_staff():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    org_id = data.get('org_id', 'org-default')
    branch_id = data.get('branch_id', 'branch-main')
    
    if not name or not str(name).strip():
        return jsonify({"success": False, "error": "Name is required"}), 400
        
    try:
        staff_id = create_or_sync_staff(
            org_id=org_id,
            branch_id=branch_id,
            name=name.strip(),
            local_user_id=data.get('local_user_id'),
            email=data.get('email'),
            phone=data.get('phone'),
            cnic=data.get('cnic'),
            department=data.get('department'),
            position=data.get('position'),
            shift_id=data.get('shift_id'),
            notes=data.get('notes'),
            active=int(data.get('active', 1) or 1)
        )
        created = get_staff_by_id(staff_id)
        return jsonify({
            "success": True,
            "staff_id": staff_id,
            "staff": created,
            "message": f"Staff member '{name.strip()}' created/updated successfully"
        }), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@staff_bp.route('/<staff_id>', methods=['PUT'])
@require_cloud_admin
def api_update_staff(staff_id):
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    if not name or not str(name).strip():
        return jsonify({"success": False, "error": "Name is required"}), 400
        
    try:
        ok = update_staff_profile(
            staff_id=staff_id,
            name=name.strip(),
            email=data.get('email'),
            phone=data.get('phone'),
            cnic=data.get('cnic'),
            department=data.get('department'),
            position=data.get('position'),
            shift_id=data.get('shift_id'),
            notes=data.get('notes'),
            active=int(data.get('active', 1) or 1)
        )
        if not ok:
            return jsonify({"success": False, "error": "Staff not found or update failed"}), 404
        updated = get_staff_by_id(staff_id)
        return jsonify({
            "success": True,
            "staff": updated,
            "message": f"Staff profile for '{name.strip()}' updated successfully"
        }), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@staff_bp.route('/<staff_id>', methods=['DELETE'])
@require_cloud_admin
def api_delete_staff(staff_id):
    from cloud.db import delete_staff
    try:
        ok = delete_staff(staff_id)
        if not ok:
            return jsonify({"success": False, "error": "Staff not found or deletion failed"}), 404
        return jsonify({"success": True, "message": "Staff member deleted successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

