"""
Cloud Application Entrypoint & Blueprint Registration
Run as standalone cloud service: python -m cloud.app
or imported into test suites.
"""

import sys
import secrets
import logging
import os
import json
from pathlib import Path
from flask import Flask, jsonify, request, session, render_template, make_response
from flask_cors import CORS
from flask_sock import Sock

# Ensure root directory is in sys.path when running directly inside the cloud directory
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from cloud.config import CLOUD_API_PREFIX, CLOUD_DB_PATH, ADMIN_CONFIG_PASSWORD, CLOUD_SECRET_KEY
from cloud.db import (
    init_cloud_db,
    purge_cloud_attendance_events_once,
    get_staff_list,
    get_staff_by_id,
    set_staff_attendance_status,
    query_attendance_reports,
    get_shifts,
    get_branches,
    update_branch,
    update_staff_profile,
    delete_staff,
    set_default_shift
)
from cloud.routes_settings import settings_bp
from cloud.routes_shifts import shifts_bp
from cloud.routes_staff import staff_bp
from cloud.routes_reports import reports_bp, api_get_attendance_reports
from cloud.routes_sync import sync_bp
from cloud.mobile_api import bootstrap_mobile_accounts_from_env, load_mobile_shift_socket_account, mobile_bp
from cloud.auth import validate_sync_credentials
from cloud.shift_push import build_shift_snapshot, register_shift_client, unregister_shift_client

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [CLOUD] [%(levelname)s] %(message)s')
logger = logging.getLogger("cloud.app")


def _assign_staff_shift(staff_id: str, shift_id: str) -> bool:
    staff = get_staff_by_id(str(staff_id))
    if not staff:
        return False
    return update_staff_profile(
        staff_id=str(staff_id),
        name=staff.get('name') or '',
        email=staff.get('email'),
        phone=staff.get('phone'),
        cnic=staff.get('cnic'),
        department=staff.get('department'),
        position=staff.get('position'),
        shift_id=str(shift_id),
        notes=staff.get('notes'),
        active=int(staff.get('active', 1))
    )


def create_cloud_app(init_db_on_start: bool = True) -> Flask:
    root_templates = Path(__file__).resolve().parent.parent / "templates"
    root_static = Path(__file__).resolve().parent.parent / "static"
    app = Flask(__name__, template_folder=str(root_templates), static_folder=str(root_static))
    app.secret_key = os.environ.get('FLASK_SECRET_KEY') or secrets.token_urlsafe(32)
    CORS(app)
    
    # Register blueprints under cloud API prefix
    app.register_blueprint(settings_bp, url_prefix=f"{CLOUD_API_PREFIX}/settings")
    app.register_blueprint(shifts_bp, url_prefix=f"{CLOUD_API_PREFIX}/shifts")
    app.register_blueprint(staff_bp, url_prefix=f"{CLOUD_API_PREFIX}/staff")
    app.register_blueprint(reports_bp, url_prefix=f"{CLOUD_API_PREFIX}/reports")
    app.register_blueprint(sync_bp, url_prefix=f"{CLOUD_API_PREFIX}/sync")
    app.register_blueprint(mobile_bp, url_prefix=f"{CLOUD_API_PREFIX}/mobile")

    sock = Sock(app)

    @sock.route(f"{CLOUD_API_PREFIX}/sync/shift-events")
    def api_sync_shift_events(ws):
        is_valid, license_payload, error_message = validate_sync_credentials(request)
        if not is_valid:
            ws.send(json.dumps({'type': 'error', 'success': False, 'error': error_message}))
            ws.close()
            return

        branch_id = license_payload.get('branch_id')
        register_shift_client(branch_id, ws)
        try:
            ws.send(json.dumps(build_shift_snapshot(branch_id)))
            while ws.receive() is not None:
                pass
        except Exception as error:
            logger.info("Shift push connection closed for branch %s: %s", branch_id, error)
        finally:
            unregister_shift_client(branch_id, ws)

    @sock.route(f"{CLOUD_API_PREFIX}/mobile/shift-events")
    def api_mobile_shift_events(ws):
        account = load_mobile_shift_socket_account(request.args.get("ticket", ""))
        if not account:
            ws.send(json.dumps({"type": "error", "success": False, "error": "Mobile shift ticket is invalid or expired."}))
            ws.close()
            return

        branch_id = account["branch_id"]
        register_shift_client(branch_id, ws)
        try:
            ws.send(json.dumps(build_shift_snapshot(branch_id)))
            while ws.receive() is not None:
                pass
        except Exception as error:
            logger.info("Mobile shift push connection closed for branch %s: %s", branch_id, error)
        finally:
            unregister_shift_client(branch_id, ws)
    
    # Backwards-compatible aliases for index.html frontend calls under /api/*
    app.register_blueprint(settings_bp, url_prefix="/api/settings", name="legacy_settings")
    app.register_blueprint(shifts_bp, url_prefix="/api/shifts", name="legacy_shifts")
    app.register_blueprint(staff_bp, url_prefix="/api/staff", name="legacy_staff")
    app.register_blueprint(reports_bp, url_prefix="/api/reports", name="legacy_reports")

    @app.route("/api/init", methods=['POST'])
    def api_init_shim():
        return jsonify({"success": True, "message": "Cloud system initialized and ready"}), 200

    @app.route("/api/stats", methods=['GET'])
    def api_stats_shim():
        staff = get_staff_list(branch_id='branch-main', active_only=True)
        reports = query_attendance_reports(org_id='org-default', branch_id='branch-main')
        present_count = len({r.get('employee_name') for r in reports if str(r.get('status', '')).lower() in ('present', 'late')})
        total_staff = len(staff)
        absent_count = max(0, total_staff - present_count)
        return jsonify({
            "total_users": total_staff,
            "today_attendance": len(reports),
            "total_logs": len(reports),
            "present_users": present_count,
            "absent_users": absent_count,
            "unique_users_today": present_count
        }), 200

    @app.route("/api/users", methods=['GET'])
    def api_users_shim():
        staff = get_staff_list(branch_id='branch-main', active_only=False)
        mapped_users = []
        for s in staff:
            mapped_users.append({
                "id": s.get("id"),
                "user_id": s.get("local_user_id") or s.get("id"),
                "name": s.get("name"),
                "department": s.get("department") or "General",
                "position": s.get("position") or "Staff",
                "shift_id": s.get("shift_id") or "shift-morning",
                "shift_name": s.get("shift_name") or "Standard Morning Shift",
                "email": s.get("email") or "",
                "phone": s.get("phone") or "",
                "cnic": s.get("cnic") or "",
                "active": s.get("active", 1)
            })
        return jsonify({"success": True, "users": mapped_users}), 200

    @app.route("/api/reports/departments", methods=['GET'])
    def api_report_departments_shim():
        staff = get_staff_list(branch_id='branch-main', active_only=False)
        depts = sorted(list({s.get('department') for s in staff if s.get('department')}))
        if not depts:
            depts = ["Engineering", "Administration", "Operations", "Sales"]
        return jsonify({"success": True, "departments": depts}), 200

    @app.route("/api/reports/shifts", methods=['GET'])
    def api_report_shifts_shim():
        shifts = get_shifts(branch_id='branch-main', active_only=True)
        return jsonify({"success": True, "shifts": shifts}), 200

    @app.route("/api/reports/attendance", methods=['GET'])
    def api_reports_attendance_legacy():
        return api_get_attendance_reports()

    @app.route("/api/reports/export/csv", methods=['GET'])
    def api_reports_export_csv_legacy():
        return api_get_attendance_reports(force_format='csv')

    @app.route("/api/cameras", methods=['GET'])
    def api_cameras_shim():
        return jsonify([]), 200

    @app.route("/api/users/bulk-assign-cameras", methods=['POST'])
    def api_bulk_assign_cameras_shim():
        return jsonify({"success": True, "message": "Camera assignments updated"}), 200

    @app.route("/api/settings/branch", methods=['GET', 'PUT'])
    def api_settings_branch_legacy():
        if request.method == 'GET':
            branches = get_branches(org_id='org-default')
            b = branches[0] if branches else {}
            return jsonify({
                "branch_name": b.get("branch_name", "Main Branch"),
                "company_name": b.get("branch_name", "Main Branch"),
                "city": b.get("city", "Lahore"),
                "admin_name": "Mr. Abid",
                "phone": b.get("contact_phone", ""),
                "email": b.get("contact_email", "")
            }), 200
        else:
            data = request.get_json(silent=True) or {}
            branch_name = data.get("branch_name") or data.get("company_name", "Main Branch")
            city = data.get("city", "Lahore")
            phone = data.get("phone", "")
            email = data.get("email", "")
            update_branch("branch-main", branch_name, "BR-MAIN", city, address="", email=email, phone=phone)
            return jsonify({"success": True, "message": "Branch & Organization settings updated successfully"}), 200

    @app.route("/api/admin/verify-password", methods=['POST'])
    def api_admin_verify_password():
        data = request.get_json(silent=True) or {}
        password = str(data.get('password', ''))
        if not ADMIN_CONFIG_PASSWORD:
            return jsonify({'success': False, 'message': 'Admin configuration password is not configured on this server.'}), 503
        if secrets.compare_digest(password, ADMIN_CONFIG_PASSWORD) or secrets.compare_digest(password, CLOUD_SECRET_KEY):
            session['admin_unlocked'] = True
            resp = jsonify({'success': True, 'message': 'Access granted'})
            resp.set_cookie("cloud_admin_token", CLOUD_SECRET_KEY, httponly=True, samesite="Lax")
            return resp, 200
        return jsonify({'success': False, 'message': 'Incorrect password'}), 401

    @app.route("/api/admin/status", methods=['GET'])
    def api_admin_status():
        return jsonify({
            'admin_unlocked': bool(session.get('admin_unlocked', True)),
            'enrollment_enabled': False
        }), 200

    @app.route("/api/admin/lock", methods=['POST'])
    def api_admin_lock():
        session.pop('admin_unlocked', None)
        return jsonify({'success': True, 'message': 'Admin locked'}), 200

    @app.route("/api/users/<user_id>/update", methods=['POST'])
    def api_user_update_shim(user_id):
        data = request.get_json(silent=True) or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"success": False, "error": "Name is required"}), 400
        update_staff_profile(
            staff_id=str(user_id),
            name=name,
            email=data.get("email"),
            phone=data.get("phone"),
            cnic=data.get("cnic"),
            department=data.get("department"),
            position=data.get("position"),
            shift_id=data.get("shift_id"),
            notes=data.get("notes")
        )
        return jsonify({"success": True, "message": "Staff profile updated successfully"}), 200

    @app.route("/api/users/<user_id>/delete", methods=['POST'])
    def api_user_delete_shim(user_id):
        delete_staff(str(user_id))
        return jsonify({"success": True, "message": "Staff member deleted successfully"}), 200

    @app.route("/api/users/<user_id>/assign-shift", methods=['POST', 'PUT'])
    def api_user_assign_shift_shim(user_id):
        data = request.get_json(silent=True) or {}
        shift_id = data.get("shift_id")
        if not shift_id:
            return jsonify({"success": False, "error": "shift_id is required"}), 400
        if not _assign_staff_shift(str(user_id), str(shift_id)):
            return jsonify({"success": False, "error": "Staff member or shift assignment not found"}), 404
        return jsonify({"success": True, "message": "Shift assigned successfully"}), 200

    @app.route("/api/users/<user_id>/mark-present", methods=['POST'])
    def api_user_mark_present_shim(user_id):
        data = request.get_json(silent=True) or {}
        try:
            result = set_staff_attendance_status(
                user_id=str(user_id),
                target_date=data.get('date'),
                status='present',
                check_in_time=data.get('check_in_time'),
                check_out_time=data.get('check_out_time'),
                notes=str(data.get('notes') or '')
            )
        except ValueError as error:
            return jsonify({"success": False, "error": str(error)}), 400
        if not result:
            return jsonify({"success": False, "error": "Staff member not found"}), 404
        return jsonify({"success": True, "message": "Attendance marked present", "attendance": result}), 200

    @app.route("/api/users/<user_id>/mark-absent", methods=['POST'])
    def api_user_mark_absent_shim(user_id):
        data = request.get_json(silent=True) or {}
        try:
            result = set_staff_attendance_status(
                user_id=str(user_id),
                target_date=data.get('date'),
                status='absent',
                notes=str(data.get('notes') or '')
            )
        except ValueError as error:
            return jsonify({"success": False, "error": str(error)}), 400
        if not result:
            return jsonify({"success": False, "error": "Staff member not found"}), 404
        return jsonify({"success": True, "message": "Attendance marked absent", "attendance": result}), 200

    @app.route("/api/users/bulk-assign-shifts", methods=['POST'])
    def api_user_bulk_assign_shifts_shim():
        data = request.get_json(silent=True) or {}
        user_ids = data.get("user_ids", [])
        shift_id = data.get("shift_id")
        if not shift_id:
            return jsonify({"success": False, "error": "shift_id is required"}), 400
        if user_ids == 'all':
            user_ids = [staff['id'] for staff in get_staff_list(branch_id='branch-main', active_only=True)]
        if not isinstance(user_ids, list):
            return jsonify({"success": False, "error": "user_ids must be a list or 'all'"}), 400
        failed_ids = [str(uid) for uid in user_ids if not _assign_staff_shift(str(uid), str(shift_id))]
        if failed_ids:
            return jsonify({
                "success": False,
                "error": "Some staff members could not be assigned",
                "failed_user_ids": failed_ids
            }), 404
        return jsonify({"success": True, "updated": len(user_ids), "message": "Shifts assigned to selected staff"}), 200

    @app.route("/api/shifts/<shift_id>/set-default", methods=['POST'])
    def api_shift_set_default_shim(shift_id):
        ok = set_default_shift(str(shift_id))
        if not ok:
            return jsonify({"success": False, "error": "Shift not found"}), 404
        return jsonify({"success": True, "message": "Default shift set successfully"}), 200

    @app.route("/api/live-detections", methods=['GET'])
    def api_live_detections_shim():
        return jsonify({"detections": []}), 200

    @app.route("/api/clear-live-detections", methods=['POST', 'GET'])
    def api_clear_live_detections_shim():
        return jsonify({"success": True, "message": "Live detections cleared"}), 200

    @app.route("/health", methods=['GET'])
    @app.route("/api/health", methods=['GET'])
    @app.route(f"{CLOUD_API_PREFIX}/health", methods=['GET'])
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "QIntellect-Cloud-Attendance",
            "version": "1.0.0-phase1",
            "db_path": str(CLOUD_DB_PATH)
        }), 200

    @app.route("/", methods=['GET'])
    def root_dashboard():
        session['admin_unlocked'] = True
        resp = make_response(render_template("index.html", is_cloud=True))
        resp.set_cookie("cloud_admin_token", CLOUD_SECRET_KEY, httponly=True, samesite="Lax")
        return resp

    if init_db_on_start:
        init_cloud_db()
        purge_confirmation = os.environ.get("PURGE_CLOUD_ATTENDANCE_CONFIRM", "")
        purge_operation_id = os.environ.get("PURGE_CLOUD_ATTENDANCE_OPERATION_ID", "")
        if purge_confirmation == "DELETE_ALL_TEST_ATTENDANCE" and purge_operation_id.strip():
            try:
                purge_cloud_attendance_events_once(purge_operation_id)
            except Exception:
                logger.exception("One-time attendance cleanup failed; cloud service will continue without purging.")
        elif purge_confirmation or purge_operation_id:
            logger.warning("Attendance cleanup was requested without the required confirmation and operation ID; no rows were deleted.")
        try:
            bootstrap_mobile_accounts_from_env()
        except Exception:
            logger.exception("Mobile account bootstrap failed; cloud service will continue without provisioning.")
        
    return app


app = create_cloud_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '5050'))
    logger.info("Starting QIntellect Cloud Attendance Service on port %s...", port)
    app.run(host='0.0.0.0', port=port, debug=False)
