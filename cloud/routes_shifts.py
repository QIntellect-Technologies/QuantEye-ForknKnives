"""
Cloud Routes: Shift Management
Phase 1 Scope:
- Multi-shift listing, creation, modification, deletion
- Working days & grace period configuration
- Default shift marking
- Shift assignment endpoints matching local application contract
"""

from flask import Blueprint, request, jsonify
from cloud.db import (
    get_shifts, get_shift_by_id, create_shift, update_shift, delete_shift,
    set_default_shift
)
from cloud.auth import require_cloud_admin

shifts_bp = Blueprint('cloud_shifts', __name__)


@shifts_bp.route('', methods=['GET'])
@shifts_bp.route('/', methods=['GET'])
@require_cloud_admin
def api_get_shifts():
    branch_id = request.args.get('branch_id', 'branch-main')
    active_only = request.args.get('active_only', 'false').lower() == 'true'
    shifts = get_shifts(branch_id=branch_id, active_only=active_only)
    return jsonify({"success": True, "shifts": shifts}), 200


@shifts_bp.route('/<shift_id>', methods=['GET'])
@require_cloud_admin
def api_get_shift(shift_id):
    shift = get_shift_by_id(shift_id)
    if not shift:
        return jsonify({"success": False, "error": "Shift not found"}), 404
    return jsonify({"success": True, "shift": shift}), 200


@shifts_bp.route('', methods=['POST'])
@shifts_bp.route('/', methods=['POST'])
@require_cloud_admin
def api_create_shift():
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    start_time = data.get('start_time', '09:00')
    end_time = data.get('end_time', '17:00')
    org_id = data.get('org_id', 'org-default')
    branch_id = data.get('branch_id', 'branch-main')
    grace_period = int(data.get('grace_period_minutes', 15) or 15)
    checkout_grace = int(data.get('checkout_grace_period_minutes', 0) or 0)
    working_days = data.get('working_days', [0, 1, 2, 3, 4, 5])
    is_default = bool(data.get('is_default', False))
    
    if not name or not str(name).strip():
        return jsonify({"success": False, "error": "Shift name is required"}), 400
        
    try:
        shift_id = create_shift(
            org_id=org_id,
            branch_id=branch_id,
            name=name.strip(),
            start_time=start_time,
            end_time=end_time,
            grace_period_minutes=grace_period,
            checkout_grace_period_minutes=checkout_grace,
            working_days=working_days,
            is_default=is_default
        )
        return jsonify({
            "success": True,
            "shift_id": shift_id,
            "message": f"Shift '{name.strip()}' created successfully"
        }), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@shifts_bp.route('/<shift_id>', methods=['PUT'])
@require_cloud_admin
def api_update_shift(shift_id):
    data = request.get_json(silent=True) or {}
    name = data.get('name')
    start_time = data.get('start_time', '09:00')
    end_time = data.get('end_time', '17:00')
    grace_period = int(data.get('grace_period_minutes', 15) or 15)
    checkout_grace = int(data.get('checkout_grace_period_minutes', 0) or 0)
    working_days = data.get('working_days')
    is_default = data.get('is_default')
    
    if not name or not str(name).strip():
        return jsonify({"success": False, "error": "Shift name is required"}), 400
        
    try:
        ok = update_shift(
            shift_id=shift_id,
            name=name.strip(),
            start_time=start_time,
            end_time=end_time,
            grace_period_minutes=grace_period,
            checkout_grace_period_minutes=checkout_grace,
            working_days=working_days,
            is_default=is_default
        )
        if not ok:
            return jsonify({"success": False, "error": "Shift not found or update failed"}), 404
        return jsonify({"success": True, "message": f"Shift '{name.strip()}' updated successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@shifts_bp.route('/<shift_id>/set-default', methods=['POST'])
def api_set_default_shift(shift_id):
    try:
        ok = set_default_shift(shift_id)
        if not ok:
            return jsonify({"success": False, "error": "Shift not found"}), 404
        return jsonify({"success": True, "message": "Default shift set successfully"}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@shifts_bp.route('/<shift_id>', methods=['DELETE'])
@require_cloud_admin
def api_delete_shift(shift_id):
    try:
        ok = delete_shift(shift_id)
        if not ok:
            return jsonify({"success": False, "error": "Shift not found or deletion failed"}), 404
        return jsonify({"success": True, "message": "Shift deleted successfully"}), 200
    except ValueError as ve:
        return jsonify({"success": False, "error": str(ve)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
