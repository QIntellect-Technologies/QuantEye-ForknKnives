"""
Cloud Routes: Attendance Reports
Phase 1 Scope:
- Query attendance records with combinable filters:
  - date range (start_date, end_date)
  - department
  - shift
  - employee_name / search
  - status (present, late, absent, etc.)
  - camera_id
- Summary metrics (total present, checkins, checkouts)
- Export to JSON / CSV compatible format
"""

import csv
import io
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, Response
from cloud.db import get_staff_list, query_attendance_reports
from cloud.auth import require_cloud_admin

reports_bp = Blueprint('cloud_reports', __name__)


@reports_bp.route('', methods=['GET'])
@reports_bp.route('/', methods=['GET'])
@require_cloud_admin
def api_get_attendance_reports(force_format=None):
    org_id = request.args.get('org_id', 'org-default')
    branch_id = request.args.get('branch_id', 'branch-main')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    date_filter = request.args.get('date')
    today = datetime.now(timezone.utc).date()
    relative_ranges = {
        'today': (today, today),
        'yesterday': (today - timedelta(days=1), today - timedelta(days=1)),
        'last7': (today - timedelta(days=6), today),
        'this_week': (today - timedelta(days=today.weekday()), today),
        'this_month': (today.replace(day=1), today),
        'last30': (today - timedelta(days=29), today),
    }
    if start_date or end_date:
        start_date = start_date or end_date
        end_date = end_date or start_date
    elif date_filter in relative_ranges:
        start, end = relative_ranges[date_filter]
        start_date, end_date = start.isoformat(), end.isoformat()
    elif date_filter:
        start_date = end_date = date_filter
    department = request.args.get('department')
    shift_id = request.args.get('shift_id') or request.args.get('shift')
    employee_name = request.args.get('employee_name') or request.args.get('search')
    event_type = request.args.get('event_type')
    status = request.args.get('status')
    camera_id = request.args.get('camera_id') or request.args.get('camera')
    export_format = (force_format or request.args.get('format', '')).lower()
    
    events = query_attendance_reports(
        org_id=org_id,
        branch_id=branch_id,
        start_date=start_date,
        end_date=end_date,
        department=department,
        shift_id=shift_id,
        employee_name=employee_name,
        event_type=event_type,
        status=status,
        camera_id=camera_id
    )
    
    if export_format == 'csv':
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "ID", "Installation ID", "Local Record ID", "Employee Name", "Department",
            "Position", "Shift", "Timestamp", "Event Type", "Status", "Confidence", "Camera ID", "Location"
        ])
        def _safe_cell(val):
            s = str(val or '')
            if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
                return f"'{s}"
            return s

        for e in events:
            writer.writerow([
                _safe_cell(e.get('id')),
                _safe_cell(e.get('installation_id')),
                _safe_cell(e.get('local_attendance_id')),
                _safe_cell(e.get('employee_name')),
                _safe_cell(e.get('department')),
                _safe_cell(e.get('position')),
                _safe_cell(e.get('shift_name')),
                _safe_cell(e.get('timestamp')),
                _safe_cell(e.get('event_type')),
                _safe_cell(e.get('status')),
                e.get('confidence', 1.0),
                _safe_cell(e.get('camera_id')),
                _safe_cell(e.get('location'))
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=cloud_attendance_report.csv"}
        )
        
    # Metrics calculation
    total_events = len(events)
    employee_key = lambda event: event.get('user_id') or event.get('staff_id') or event.get('employee_name')
    unique_employees = len({employee_key(e) for e in events if employee_key(e)})
    checkins = sum(1 for e in events if str(e.get('event_type', '')).lower() == 'checkin')
    checkouts = sum(1 for e in events if str(e.get('event_type', '')).lower() == 'checkout')
    present_keys = {
        employee_key(e) for e in events
        if employee_key(e) and str(e.get('status', '')).lower() in ('present', 'late', 'checked_out')
    }
    late_keys = {
        employee_key(e) for e in events
        if employee_key(e) and str(e.get('status', '')).lower() == 'late'
    }
    staff = get_staff_list(branch_id=branch_id, active_only=True)
    total_staff = len(staff)
    absent_count = max(0, total_staff - len(present_keys))
    attendance_rate = round((len(present_keys) / total_staff) * 100, 1) if total_staff else 0
    department_stats = {}
    for person in staff:
        department_name = person.get('department') or 'Unassigned'
        department = department_stats.setdefault(department_name, {'department': department_name, 'total': 0, 'present': 0})
        department['total'] += 1
        person_key = person.get('local_user_id') or person.get('id')
        if person_key in present_keys:
            department['present'] += 1
    departments = []
    for department in department_stats.values():
        department['absent'] = department['total'] - department['present']
        department['attendance_rate'] = round((department['present'] / department['total']) * 100, 1) if department['total'] else 0
        departments.append(department)
    date_label = start_date if start_date == end_date else f"{start_date} to {end_date}" if start_date and end_date else 'All dates'
    
    return jsonify({
        "success": True,
        "count": total_events,
        "summary": {
            "total_records": total_events,
            "unique_employees": unique_employees,
            "checkin_count": checkins,
            "checkout_count": checkouts,
            "total_enrolled": total_staff,
            "total_matching": total_staff,
            "total_registered": total_staff,
            "total_present_days": len(present_keys),
            "present": len(present_keys),
            "total_absent_days": absent_count,
            "absent": absent_count,
            "total_late_days": len(late_keys),
            "late": len(late_keys),
            "attendance_rate": attendance_rate
        },
        "departments": departments,
        "date_label": date_label,
        "filters": {
            "org_id": org_id,
            "branch_id": branch_id,
            "start_date": start_date,
            "end_date": end_date,
            "department": department,
            "shift_id": shift_id
        },
        "records": events
    }), 200
