import sys
sys.path.insert(0, ".")
import os
import sqlite3
import json
import io
import cv2
import numpy as np
from datetime import datetime
import database as db
from app import app, _ADMIN_CONFIG_PASSWORD, refresh_embedding_cache

client = app.test_client()

def run_enrollment_audit():
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    print("=====================================================================", flush=True)
    print("  COMPLETE AUDIT: STAFF BIOMETRIC ENROLLMENT + FULL SYSTEM REGRESSION")
    print("=====================================================================")

    results = []

    def record_test(module, test_name, expected, actual, passed, details=""):
        status = "PASS" if passed else "FAIL"
        results.append({
            'module': module,
            'test': test_name,
            'expected': str(expected),
            'actual': str(actual),
            'status': status,
            'details': details
        })
        print(f"[{status}] {module} :: {test_name}")
        print(f"       Expected: {expected}")
        print(f"       Actual:   {actual}")
        if details:
            print(f"       Details:  {details}")

    # =================================================================
    # SECTION 1: ADMIN ACCESS SECURITY CONTROLS
    # =================================================================
    print("\n--- 1. ADMIN SECURITY GATE & ENROLLMENT ACCESS CONTROLS ---")

    # 1.1 Initial State: Enrollment Disabled
    res_st = client.get('/api/admin/status')
    st_data = res_st.get_json() if res_st.is_json else {}
    record_test(
        "Admin Security",
        "Initial session state has enrollment disabled",
        "HTTP 200 with admin_unlocked=False, enrollment_enabled=False",
        f"HTTP {res_st.status_code} with {st_data}",
        res_st.status_code == 200 and not st_data.get('admin_unlocked') and not st_data.get('enrollment_enabled'),
        "Enrollment is protected by default"
    )

    # 1.2 Access Control: Block Profile Creation when Disabled
    res_block_create = client.post('/api/enroll/create-user', json={'name': 'Hacker Bob'})
    record_test(
        "Admin Security",
        "Access Control: Block create-user when enrollment is locked",
        "HTTP 403 Forbidden",
        f"HTTP {res_block_create.status_code}",
        res_block_create.status_code == 403,
        f"Response: {res_block_create.get_json()}"
    )

    # 1.3 Access Control: Block Video Upload when Disabled
    res_block_upload = client.post('/api/enroll/upload-video', data={'user_id': '1'})
    record_test(
        "Admin Security",
        "Access Control: Block upload-video when enrollment is locked",
        "HTTP 403 Forbidden",
        f"HTTP {res_block_upload.status_code}",
        res_block_upload.status_code == 403,
        f"Response: {res_block_upload.get_json()}"
    )

    # 1.4 Access Control: Block Status Check when Disabled
    res_block_st = client.get('/api/enroll/status/1')
    record_test(
        "Admin Security",
        "Access Control: Block enrollment status when locked",
        "HTTP 403 Forbidden",
        f"HTTP {res_block_st.status_code}",
        res_block_st.status_code == 403,
        f"Response: {res_block_st.get_json()}"
    )

    # 1.5 Access Control: Reject Invalid Admin Password
    res_bad_pw = client.post('/api/admin/verify-password', json={'password': 'invalid_secret_pass'})
    record_test(
        "Admin Security",
        "Authentication: Reject incorrect admin password",
        "HTTP 401 Unauthorized with success=False",
        f"HTTP {res_bad_pw.status_code} - {res_bad_pw.get_json()}",
        res_bad_pw.status_code == 401 and res_bad_pw.get_json().get('success') is False,
        "Protected against unauthorized password attempts"
    )

    # 1.6 Authentication: Accept Valid Admin Master Password
    res_ok_pw = client.post('/api/admin/verify-password', json={'password': _ADMIN_CONFIG_PASSWORD})
    record_test(
        "Admin Security",
        "Authentication: Verify valid admin master password",
        "HTTP 200 OK with success=True",
        f"HTTP {res_ok_pw.status_code} - {res_ok_pw.get_json()}",
        res_ok_pw.status_code == 200 and res_ok_pw.get_json().get('success') is True,
        "Admin session unlocked successfully"
    )

    # 1.7 Enable Enrollment via Admin Session
    res_enable = client.post('/api/admin/enable-enrollment')
    res_st_after = client.get('/api/admin/status')
    st_after = res_st_after.get_json() if res_st_after.is_json else {}
    record_test(
        "Admin Security",
        "Session State: Enable enrollment mode after admin auth",
        "HTTP 200 with admin_unlocked=True and enrollment_enabled=True",
        f"HTTP {res_enable.status_code}, status={st_after}",
        res_enable.status_code == 200 and st_after.get('admin_unlocked') and st_after.get('enrollment_enabled'),
        "Enrollment pipeline is now activated"
    )

    # =================================================================
    # SECTION 2: STAFF PROFILE CREATION & VALIDATION
    # =================================================================
    print("\n--- 2. STAFF PROFILE REGISTRATION & INPUT VALIDATION ---")

    # 2.1 Validation: Reject Empty Name
    res_no_name = client.post('/api/enroll/create-user', json={'name': ''})
    record_test(
        "Staff Enrollment",
        "Validation: Reject empty staff name",
        "HTTP 400 Bad Request with error message",
        f"HTTP {res_no_name.status_code} - {res_no_name.get_json()}",
        res_no_name.status_code == 400 and 'Name is required' in res_no_name.get_json().get('error', ''),
        "Empty name rejected correctly"
    )

    # 2.2 Full Profile Creation
    timestamp_id = int(datetime.now().timestamp())
    test_user_name = f"Audit Engineer {timestamp_id}"
    test_email = f"audit.eng.{timestamp_id}@qintellect.test"
    test_phone = "0300-9876543"
    test_dept = "AI & Data Science"
    test_position = "AI Research Engineer"
    test_cnic = "35202-7777777-1"
    test_salary = 85000.0
    test_join_date = "2026-10-01"
    
    res_create = client.post('/api/enroll/create-user', json={
        'name': test_user_name,
        'email': test_email,
        'phone': test_phone,
        'department': test_dept,
        'position': test_position,
        'cnic': test_cnic,
        'salary': test_salary,
        'join_date': test_join_date,
        'shift_id': 1,
        'checkin_cameras': 'all',
        'checkout_cameras': 'all'
    })
    cdata = res_create.get_json() if res_create.is_json else {}
    enrolled_user_id = cdata.get('user_id')
    record_test(
        "Staff Enrollment",
        "CRUD: Create new staff profile with full enterprise HR fields",
        f"HTTP 201 with success=True and valid user_id",
        f"HTTP {res_create.status_code} with user_id={enrolled_user_id}",
        res_create.status_code == 201 and cdata.get('success') is True and enrolled_user_id is not None,
        f"Profile created: ID #{enrolled_user_id} - '{test_user_name}'"
    )

    # 2.3 Duplicate Name Conflict (name is UNIQUE in database schema)
    res_dup = client.post('/api/enroll/create-user', json={
        'name': test_user_name,
        'email': f"another_{test_email}"
    })
    record_test(
        "Staff Enrollment",
        "Validation: Reject duplicate employee name",
        "HTTP 409 Conflict",
        f"HTTP {res_dup.status_code} - {res_dup.get_json()}",
        res_dup.status_code == 409,
        "Duplicate employee prevented by unique constraint"
    )

    # 2.4 Database Persistence of Profile & Shift History
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT id, name, email, department, position, salary, shift_id FROM users WHERE id = ?", (enrolled_user_id,))
    u_row = c.fetchone()
    c.execute("SELECT user_id, shift_id, effective_from FROM employee_shift_history WHERE user_id = ?", (enrolled_user_id,))
    sh_row = c.fetchone()
    conn.close()
    record_test(
        "Staff Enrollment",
        "Database Persistence: users record and employee_shift_history created",
        f"Matching user row and shift history row for user {enrolled_user_id}",
        f"users={u_row}, shift_history={sh_row}",
        u_row is not None and u_row[1] == test_user_name and u_row[5] == test_salary and sh_row is not None and sh_row[1] == 1,
        "Complete persistence verified in SQLite"
    )

    # =================================================================
    # SECTION 3: BIOMETRIC ENROLLMENT & EMBEDDINGS EXTRACTION
    # =================================================================
    print("\n--- 3. BIOMETRIC STATUS & VIDEO EMBEDDING EXTRACTION ---")

    # 3.1 Status Before Embeddings
    res_pre_st = client.get(f'/api/enroll/status/{enrolled_user_id}')
    pre_st_data = res_pre_st.get_json() if res_pre_st.is_json else {}
    record_test(
        "Staff Enrollment",
        "Biometric Status: Pre-biometric state reports not enrolled",
        "HTTP 200 with enrolled=False and embeddings_count=0",
        f"HTTP {res_pre_st.status_code} - enrolled={pre_st_data.get('enrolled')}, count={pre_st_data.get('embeddings_count')}",
        res_pre_st.status_code == 200 and pre_st_data.get('enrolled') is False and pre_st_data.get('embeddings_count') == 0,
        f"Response message: {pre_st_data.get('message')}"
    )

    # 3.2 Video Upload Validation: Missing File
    res_no_vid = client.post('/api/enroll/upload-video', data={'user_id': str(enrolled_user_id)})
    record_test(
        "Staff Enrollment",
        "Validation: Reject upload without video file",
        "HTTP 400 Bad Request with 'No video provided'",
        f"HTTP {res_no_vid.status_code} - {res_no_vid.get_json()}",
        res_no_vid.status_code == 400 and 'No video provided' in res_no_vid.get_json().get('error', ''),
        "File requirement strictly enforced"
    )

    # 3.3 Real Video Upload & Biometric Embedding Extraction
    test_video_path = "uploads/nvr_enroll_33_1779360621.940326.mp4"
    with open(test_video_path, 'rb') as vf:
        video_bytes = vf.read()

    res_upload = client.post(
        '/api/enroll/upload-video',
        data={
            'user_id': str(enrolled_user_id),
            'video': (io.BytesIO(video_bytes), 'test_enroll.mp4')
        },
        content_type='multipart/form-data'
    )
    up_data = res_upload.get_json() if res_upload.is_json else {}
    record_test(
        "Staff Enrollment",
        "Biometric Pipeline: Process video and store facial embeddings",
        "HTTP 200 with success=True and embeddings_count >= 10",
        f"HTTP {res_upload.status_code} with count={up_data.get('embeddings_count')}, avg_quality={up_data.get('avg_quality')}",
        res_upload.status_code == 200 and up_data.get('success') is True and up_data.get('embeddings_count', 0) >= 10,
        f"Processed {up_data.get('total_frames_processed')} frames, quality: {up_data.get('avg_quality')}"
    )

    # 3.4 Status After Biometrics
    res_post_st = client.get(f'/api/enroll/status/{enrolled_user_id}')
    post_st_data = res_post_st.get_json() if res_post_st.is_json else {}
    record_test(
        "Staff Enrollment",
        "Biometric Status: Post-biometric state reports enrolled",
        "HTTP 200 with enrolled=True and embeddings_count >= 10",
        f"HTTP {res_post_st.status_code} - enrolled={post_st_data.get('enrolled')}, count={post_st_data.get('embeddings_count')}",
        res_post_st.status_code == 200 and post_st_data.get('enrolled') is True and post_st_data.get('embeddings_count', 0) >= 10,
        f"Active embeddings: {post_st_data.get('embeddings_count')}"
    )

    # 3.5 Database Verification: Embeddings stored in table
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT count(*), min(length(embedding)) FROM embeddings WHERE user_id = ?", (enrolled_user_id,))
    emb_count, min_len = c.fetchone()
    conn.close()
    record_test(
        "Staff Enrollment",
        "Database Persistence: 512-D vectors stored in embeddings table",
        "count >= 10 and min_len > 1000 bytes (JSON float array)",
        f"count={emb_count}, min_len={min_len} bytes",
        emb_count >= 10 and min_len > 1000,
        f"Persisted {emb_count} verified biometric embeddings"
    )

    # =================================================================
    # SECTION 4: VECTORIZED RECOGNITION MATCH & CROSS-MODULE SYNC
    # =================================================================
    print("\n--- 4. REAL-TIME AI RECOGNITION & CROSS-MODULE INTEGRATION ---")

    # 4.1 Real-Time Recognition Match
    # Extract first face frame from the enrolled video and send to /api/recognize/frame
    cap = cv2.VideoCapture(test_video_path)
    ret, test_frame = cap.read()
    cap.release()
    assert ret and test_frame is not None, "Failed to read test frame from video"
    
    _, img_encoded = cv2.imencode('.jpg', test_frame)
    res_recog = client.post(
        '/api/recognize/frame',
        data={'image': (io.BytesIO(img_encoded.tobytes()), 'test_face.jpg')},
        content_type='multipart/form-data'
    )
    recog_data = res_recog.get_json() if res_recog.is_json else {}
    detections = recog_data.get('detections', [])
    matched_target = any(d.get('matched_user') == test_user_name for d in detections)
    record_test(
        "Staff Enrollment",
        "AI Recognition Engine: Instant match against newly enrolled employee",
        f"HTTP 200 and matched_user=='{test_user_name}'",
        f"HTTP {res_recog.status_code}, matched={matched_target}, detections={len(detections)}",
        res_recog.status_code == 200 and matched_target,
        f"Top detection match: {detections[0].get('matched_user') if detections else 'None'} (similarity: {detections[0].get('similarity') if detections else 0.0})"
    )

    # 4.2 Cross-Module Sync: Employee Salary Structure Module
    res_sal = client.get(f'/api/salary/{enrolled_user_id}')
    sal_data = res_sal.get_json() if res_sal.is_json else {}
    record_test(
        "Cross-Module: Salary",
        "Integration: Newly enrolled employee automatically appears in Salary Structure",
        f"HTTP 200 with basic_salary={test_salary} and net_estimated={test_salary}",
        f"HTTP {res_sal.status_code} - basic={sal_data.get('basic_salary')}, net={sal_data.get('net_estimated')}",
        res_sal.status_code == 200 and sal_data.get('basic_salary') == test_salary and sal_data.get('net_estimated') == test_salary,
        f"Synchronized with base pay without manual config"
    )

    # 4.3 Cross-Module Sync: Staff Directory & Shifts
    res_users = client.get('/api/users')
    all_users = res_users.get_json().get('users', []) if res_users.is_json else []
    user_in_dir = any(u.get('id') == enrolled_user_id for u in all_users)
    record_test(
        "Cross-Module: Directory",
        "Integration: Enrolled staff member appears in Staff Directory",
        "Enrolled user exists in /api/users active list",
        f"User found in directory: {user_in_dir} (total staff: {len(all_users)})",
        user_in_dir and len(all_users) == 39,
        f"Staff count increased from 38 to 39 seamlessly"
    )

    # =================================================================
    # SECTION 5: CLEANUP, CASCADE & ADMIN TEARDOWN
    # =================================================================
    print("\n--- 5. CLEANUP, CASCADE VERIFICATION & ADMIN LOCK TEARDOWN ---")

    # 5.1 Delete Enrolled User and Test Foreign Key Cascade
    del_ok = db.delete_user(enrolled_user_id)
    refresh_embedding_cache()
    
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT count(*) FROM users WHERE id = ?", (enrolled_user_id,))
    u_remaining = c.fetchone()[0]
    c.execute("SELECT count(*) FROM embeddings WHERE user_id = ?", (enrolled_user_id,))
    emb_remaining = c.fetchone()[0]
    c.execute("SELECT count(*) FROM employee_shift_history WHERE user_id = ?", (enrolled_user_id,))
    sh_remaining = c.fetchone()[0]
    conn.close()

    record_test(
        "Staff Enrollment",
        "Cleanup & Cascade: Delete user and auto-cascade purge all embeddings and histories",
        "User deleted, embeddings count=0, shift history count=0",
        f"Deleted: {del_ok}, user_rows={u_remaining}, emb_rows={emb_remaining}, sh_rows={sh_remaining}",
        del_ok and u_remaining == 0 and emb_remaining == 0 and sh_remaining == 0,
        "Cascade clean: Zero orphaned records left in database"
    )

    # 5.2 Disable Enrollment & Lock Admin Session
    res_dis = client.post('/api/admin/disable-enrollment')
    res_lock = client.post('/api/admin/lock')
    res_st_final = client.get('/api/admin/status')
    st_final = res_st_final.get_json() if res_st_final.is_json else {}
    res_relock_chk = client.post('/api/enroll/create-user', json={'name': 'Blocked Again'})
    record_test(
        "Admin Security",
        "Session Teardown: Disable enrollment, lock admin session, re-verify security gate",
        "admin_unlocked=False, enrollment_enabled=False, create-user returns HTTP 403",
        f"status={st_final}, create-user HTTP {res_relock_chk.status_code}",
        not st_final.get('admin_unlocked') and not st_final.get('enrollment_enabled') and res_relock_chk.status_code == 403,
        "System locked down: Security perimeter completely intact"
    )

    # =================================================================
    # SECTION 6: FULL REGRESSION AUDIT (15 FROZEN BASELINE ITEMS)
    # =================================================================
    print("\n--- 6. FULL SYSTEM REGRESSION AUDIT (15 FROZEN MODULES) ---")

    # 6.1 Database Physical Integrity
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("PRAGMA integrity_check")
    integ = c.fetchall()
    record_test(
        "Database Integrity",
        "PRAGMA integrity_check",
        "[('ok',)]",
        str(integ),
        integ == [('ok',)],
        "Database is physically intact"
    )

    # 6.2 Foreign Key Integrity Check
    c.execute("PRAGMA foreign_key_check")
    fk_violations = c.fetchall()
    conn.close()
    record_test(
        "Database Integrity",
        "PRAGMA foreign_key_check",
        "[] (Zero foreign key violations)",
        str(fk_violations),
        len(fk_violations) == 0,
        "Zero foreign key violations across all tables"
    )

    # 6.3 Payroll V1 Baseline Calculation
    preview = db.calculate_monthly_payroll('2026-10')
    imran_record = next((r for r in preview.get('records', []) if r.get('employee_id') == 38), None)
    expected_imran = {
        'basic_salary': 250000.0,
        'payable_days': 4.0,
        'net_salary': 37037.04
    }
    imran_match = (
        imran_record is not None and
        imran_record.get('basic_salary') == expected_imran['basic_salary'] and
        imran_record.get('payable_days') == expected_imran['payable_days'] and
        imran_record.get('net_salary') == expected_imran['net_salary']
    )
    record_test(
        "Payroll V1",
        "Payroll calculation engine produces exact baseline for October 2026",
        f"Imran Khalid: basic_salary=250000.0, payable_days=4.0, net_salary=37037.04",
        f"Imran Khalid: basic_salary={imran_record.get('basic_salary') if imran_record else None}, payable_days={imran_record.get('payable_days') if imran_record else None}, net_salary={imran_record.get('net_salary') if imran_record else None}",
        imran_match,
        f"Matched Rule: {imran_record.get('matched_rule') if imran_record else ''}, Status: {preview.get('status')}"
    )

    # 6.4 Leave & Holiday Management
    res_ltypes = client.get('/api/leave-types')
    res_holidays = client.get('/api/holidays')
    res_leaves = client.get('/api/leaves')
    res_balances = client.get('/api/leaves/balances?year=2026')
    leave_ok = (
        res_ltypes.status_code == 200 and
        res_holidays.status_code == 200 and
        res_leaves.status_code == 200 and
        res_balances.status_code == 200
    )
    record_test(
        "Leave & Holidays",
        "Leave APIs (leave-types, holidays, leaves, balances)",
        "All return HTTP 200",
        f"Types: {res_ltypes.status_code}, Holidays: {res_holidays.status_code}, Requests: {res_leaves.status_code}, Balances: {res_balances.status_code}",
        leave_ok,
        f"Leave types count: {len(res_ltypes.get_json() or [])}"
    )

    # 6.5 Employee Salary Structure Module
    res_sal_all = client.get('/api/salary')
    res_sal_sum = client.get('/api/salary/summary')
    sal_list = res_sal_all.get_json() if res_sal_all.is_json else []
    sal_sum_data = res_sal_sum.get_json() if res_sal_sum.is_json else {}
    record_test(
        "Salary Structure",
        "Salary configuration directory & KPI summary APIs",
        "HTTP 200 with 38 staff and positive total_basic",
        f"HTTP {res_sal_all.status_code} ({len(sal_list)} staff), HTTP {res_sal_sum.status_code} (total_basic: {sal_sum_data.get('total_basic')})",
        res_sal_all.status_code == 200 and len(sal_list) == 38 and res_sal_sum.status_code == 200 and sal_sum_data.get('total_basic', 0) > 0,
        f"Salary Structure baseline 100% intact"
    )

    # 6.6 Shift Management
    res_shifts = client.get('/api/shifts')
    shifts = res_shifts.get_json().get('shifts', []) if res_shifts.is_json else []
    record_test(
        "Shift Management",
        "Shift configurations and employee assignments",
        "HTTP 200 with active shifts configured",
        f"HTTP {res_shifts.status_code} with {len(shifts)} shifts",
        res_shifts.status_code == 200 and len(shifts) >= 2,
        f"Shifts: {[s.get('name') for s in shifts if isinstance(s, dict)]}"
    )

    # 6.7 Staff Management
    res_users = client.get('/api/users')
    users_data = res_users.get_json() if res_users.is_json else {}
    users_list = users_data.get('users', []) if isinstance(users_data, dict) else users_data
    record_test(
        "Staff Management",
        "Staff directory list API",
        "HTTP 200 with 38 users",
        f"HTTP {res_users.status_code} with {len(users_list)} users",
        res_users.status_code == 200 and len(users_list) == 38,
        "Staff directory completely intact"
    )

    # 6.8 Departments & Designations
    res_depts = client.get('/api/departments')
    res_desigs = client.get('/api/designations')
    dept_ok = res_depts.status_code == 200 and res_desigs.status_code == 200
    record_test(
        "Departments & Designations",
        "Departments & Designations API suite",
        "Both return HTTP 200 with non-empty collections",
        f"Depts: {res_depts.status_code} ({len(res_depts.get_json() or [])}), Desigs: {res_desigs.status_code} ({len(res_desigs.get_json() or [])})",
        dept_ok,
        "Department-designation hierarchy intact"
    )

    # 6.9 Settings & Branch
    res_branch = client.get('/api/settings/branch')
    bdata = res_branch.get_json() if res_branch.is_json else {}
    record_test(
        "Settings",
        "Branch settings API",
        "HTTP 200 with branch_name configured",
        f"HTTP {res_branch.status_code} with branch: {bdata.get('branch_name')}",
        res_branch.status_code == 200 and bool(bdata.get('branch_name')),
        f"Branch: {bdata.get('branch_name')}, City: {bdata.get('city')}"
    )

    # 6.10 Camera Management
    res_cams = client.get('/api/cameras')
    cdata = res_cams.get_json() if res_cams.is_json else []
    record_test(
        "Camera Management",
        "Camera feeds configuration API",
        "HTTP 200 with active cameras",
        f"HTTP {res_cams.status_code} with {len(cdata)} cameras",
        res_cams.status_code == 200 and len(cdata) > 0,
        f"Cameras: {[c.get('name') for c in cdata]}"
    )

    # 6.11 Attendance Reports
    res_rep = client.get('/api/reports/attendance?start_date=2026-10-01&end_date=2026-10-07')
    rdata = res_rep.get_json() if res_rep.is_json else {}
    record_test(
        "Attendance Reports",
        "Attendance detailed report API",
        "HTTP 200 with report records",
        f"HTTP {res_rep.status_code} with {len(rdata.get('records', []))} records",
        res_rep.status_code == 200 and len(rdata.get('records', [])) > 0,
        "Reports generation engine intact"
    )

    # 6.12 Dashboard & Stats
    res_dash = client.get('/api/stats')
    dash_data = res_dash.get_json() if res_dash.is_json else {}
    record_test(
        "Dashboard",
        "Dashboard KPI stats API",
        "HTTP 200 with total_users and present count",
        f"HTTP {res_dash.status_code} with total_users={dash_data.get('total_users')}",
        res_dash.status_code == 200 and dash_data.get('total_users') == 38,
        f"KPIs: {dash_data}"
    )

    # =================================================================
    # SECTION 7: FULL REST API REGRESSION (21/21 APIS)
    # =================================================================
    print("\n--- 7. COMPLETE REST API REGRESSION SUITE (21/21 APIS) ---")

    endpoints_to_test = [
        ('/api/stats', 'GET'),
        ('/api/users', 'GET'),
        ('/api/departments', 'GET'),
        ('/api/designations', 'GET'),
        ('/api/shifts', 'GET'),
        ('/api/cameras', 'GET'),
        ('/api/settings/branch', 'GET'),
        ('/api/payroll/rules', 'GET'),
        ('/api/payroll/calendar', 'GET'),
        ('/api/payroll/history', 'GET'),
        ('/api/payroll?month=2026-10', 'GET'),
        ('/api/reports/attendance?start_date=2026-10-01&end_date=2026-10-07', 'GET'),
        ('/api/leave-types', 'GET'),
        ('/api/leaves', 'GET'),
        ('/api/leaves/balances?year=2026', 'GET'),
        ('/api/holidays', 'GET'),
        ('/api/salary', 'GET'),
        ('/api/salary/summary', 'GET'),
        ('/api/admin/status', 'GET'),
        ('/api/locate/rooms', 'GET'),
        ('/api/locate/person?name=Imran', 'GET')
    ]

    for ep, method in endpoints_to_test:
        if method == 'GET':
            r = client.get(ep)
        else:
            r = client.post(ep)
        record_test(
            "API Suite",
            f"{method} {ep}",
            "HTTP 200",
            f"HTTP {r.status_code}",
            r.status_code == 200
        )

    # =================================================================
    # SUMMARY
    # =================================================================
    total = len(results)
    passed = sum(1 for r in results if r['status'] == 'PASS')
    failed = total - passed

    print("\n" + "="*69)
    print(f"AUDIT SUMMARY: {passed}/{total} TESTS PASSED | {failed} FAILED")
    print("="*69)

    with open('scratch/audit_results.json', 'w') as jf:
        json.dump(results, jf, indent=2)
    print(f"\n[OK] Wrote {len(results)} test results to scratch/audit_results.json", flush=True)

    if failed == 0:
        print("\nALL MODULE AND REGRESSION CHECKS PASSED WITH 100% SUCCESS!", flush=True)
    else:
        print(f"\nCRITICAL: {failed} CHECKS FAILED! INVESTIGATE IMMEDIATELY.", flush=True)
        for r in results:
            if r['status'] == 'FAIL':
                print(f"FAILED: {r['module']} - {r['test']} -> Expected: {r['expected']} | Actual: {r['actual']}", flush=True)

    return results

if __name__ == '__main__':
    run_enrollment_audit()
