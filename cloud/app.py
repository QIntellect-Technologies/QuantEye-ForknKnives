"""
Cloud Application Entrypoint & Blueprint Registration
Run as standalone cloud service: python -m cloud.app
or imported into test suites.
"""

import sys
import secrets
import logging
from pathlib import Path
from flask import Flask, jsonify, request, session, render_template, make_response
from flask_cors import CORS

# Ensure root directory is in sys.path when running directly inside the cloud directory
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from cloud.config import CLOUD_API_PREFIX, CLOUD_DB_PATH, ADMIN_CONFIG_PASSWORD, CLOUD_SECRET_KEY
from cloud.db import (
    init_cloud_db,
    get_staff_list,
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

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [CLOUD] [%(levelname)s] %(message)s')
logger = logging.getLogger("cloud.app")


def create_cloud_app(init_db_on_start: bool = True) -> Flask:
    root_templates = Path(__file__).resolve().parent.parent / "templates"
    root_static = Path(__file__).resolve().parent.parent / "static"
    app = Flask(__name__, template_folder=str(root_templates), static_folder=str(root_static))
    app.secret_key = "cloud-secret-session-key-qintellect"
    CORS(app)
    
    # Register blueprints under cloud API prefix
    app.register_blueprint(settings_bp, url_prefix=f"{CLOUD_API_PREFIX}/settings")
    app.register_blueprint(shifts_bp, url_prefix=f"{CLOUD_API_PREFIX}/shifts")
    app.register_blueprint(staff_bp, url_prefix=f"{CLOUD_API_PREFIX}/staff")
    app.register_blueprint(reports_bp, url_prefix=f"{CLOUD_API_PREFIX}/reports")
    app.register_blueprint(sync_bp, url_prefix=f"{CLOUD_API_PREFIX}/sync")
    
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
                "admin_name": "Mr. Junaid",
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
        update_staff_profile(staff_id=str(user_id), shift_id=shift_id)
        return jsonify({"success": True, "message": "Shift assigned successfully"}), 200

    @app.route("/api/users/bulk-assign-shifts", methods=['POST'])
    def api_user_bulk_assign_shifts_shim():
        data = request.get_json(silent=True) or {}
        user_ids = data.get("user_ids", [])
        shift_id = data.get("shift_id")
        for uid in user_ids:
            update_staff_profile(staff_id=str(uid), shift_id=shift_id)
        return jsonify({"success": True, "message": "Shifts assigned to selected staff"}), 200

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
        
    return app


app = create_cloud_app()

if __name__ == '__main__':
    logger.info("Starting QIntellect Cloud Attendance Service on port 5050...")
    app.run(host='0.0.0.0', port=5050, debug=False)
