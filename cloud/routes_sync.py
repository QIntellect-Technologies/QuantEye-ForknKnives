"""
Cloud Routes: Attendance Synchronization Gateway
Phase 1 Scope:
- Ingestion endpoint: POST /api/v1/sync/attendance
- Authentication via X-License-Key and X-Installation-Id
- Rejection of invalid, mismatched, or expired licenses
- Transactional batch ingestion with idempotency:
  (installation_id, local_attendance_id)
- Return granular acceptance, duplicate, and rejection status
"""

from flask import Blueprint, request, jsonify
from cloud.auth import validate_sync_credentials
from cloud.db import ingest_attendance_batch
from cloud.shift_push import build_shift_snapshot

sync_bp = Blueprint('cloud_sync', __name__)


@sync_bp.route('/shifts', methods=['GET'])
def api_sync_shifts():
    """Return branch shift configuration to a licensed local installation."""
    is_valid, license_payload, err_msg = validate_sync_credentials(request)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": "License validation rejected shift synchronization",
            "details": err_msg
        }), 403

    branch_id = license_payload.get('branch_id')
    snapshot = build_shift_snapshot(branch_id)
    snapshot['installation_id'] = license_payload.get('installation_id')
    return jsonify(snapshot), 200


@sync_bp.route('/attendance', methods=['POST'])
def api_sync_attendance():
    """
    Synchronize attendance events from local installation.
    Payload:
    {
       "events": [
           {
               "local_attendance_id": 101,
               "detected_name": "Ahmad Ali",
               "timestamp": "2026-10-12 09:05:22",
               "confidence": 0.88,
               "source": "rtsp://camera1",
               "camera_id": "cam_entrance",
               "event_type": "checkin",
               "status": "present"
           }, ...
       ]
    }
    """
    # 1. Validate License & Installation Identity
    is_valid, license_payload, err_msg = validate_sync_credentials(request)
    if not is_valid:
        return jsonify({
            "success": False,
            "error": "License validation rejected synchronization",
            "details": err_msg
        }), 403
        
    org_id = license_payload.get('org_id')
    branch_id = license_payload.get('branch_id')
    installation_id = license_payload.get('installation_id')
    
    # 2. Parse Payload
    data = request.get_json(silent=True) or {}
    events = data.get('events')
    
    if events is None:
        # Check if single record or flat list sent
        if isinstance(data, list):
            events = data
        elif 'attendance' in data:
            events = data['attendance']
        else:
            return jsonify({
                "success": False,
                "error": "Missing 'events' list in payload"
            }), 400
            
    if not isinstance(events, list):
        return jsonify({
            "success": False,
            "error": "'events' must be an array of attendance records"
        }), 400
        
    # 3. Process Transactional Batch Ingestion with Idempotency
    try:
        summary = ingest_attendance_batch(
            org_id=org_id,
            branch_id=branch_id,
            installation_id=installation_id,
            events=events
        )
        
        status_code = 200
        # If all records were rejected due to invalid payloads
        if summary['total'] > 0 and summary['accepted'] == 0 and summary['duplicates'] == 0:
            status_code = 400
            
        return jsonify({
            "success": summary['rejected'] == 0 or (summary['accepted'] > 0 or summary['duplicates'] > 0),
            "installation_id": installation_id,
            "branch_id": branch_id,
            "batch_summary": summary
        }), status_code
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Database error during batch ingestion transaction",
            "details": str(e)
        }), 500
