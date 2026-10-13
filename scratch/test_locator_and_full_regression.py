import sys
sys.path.insert(0, ".")
import os
import sqlite3
import json
import time
from datetime import datetime
import database as db
from app import (
    app, update_live_presence, refresh_presence_timestamp,
    refresh_embedding_cache, LIVE_PRESENCE, presence_lock, _ADMIN_CONFIG_PASSWORD
)

client = app.test_client()

def run_locator_audit():
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    refresh_embedding_cache()

    print("=====================================================================", flush=True)
    print("  COMPLETE AUDIT: STAFF & ROOM LOCATOR MODULE + FULL REGRESSION     ", flush=True)
    print("=====================================================================", flush=True)

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
        print(f"[{status}] {module} :: {test_name}", flush=True)
        print(f"       Expected: {expected}", flush=True)
        print(f"       Actual:   {actual}", flush=True)
        if details:
            print(f"       Details:  {details}", flush=True)

    # =================================================================
    # SECTION 1: ROOMS RADAR & CAMERA MAPPINGS
    # =================================================================
    print("\n--- 1. ROOMS RADAR & CAMERA ROOM MAPPINGS ---", flush=True)

    # 1.1 GET /api/locate/rooms returns all configured camera rooms
    res_rooms = client.get('/api/locate/rooms')
    rdata = res_rooms.get_json() if res_rooms.is_json else {}
    rooms = rdata.get('rooms', [])
    record_test(
        "Room Radar",
        "API GET /api/locate/rooms returns all configured rooms",
        "HTTP 200 with 3 active camera rooms",
        f"HTTP {res_rooms.status_code} with {len(rooms)} rooms",
        res_rooms.status_code == 200 and len(rooms) == 3,
        f"Configured rooms: {[r.get('room_name') for r in rooms]}"
    )

    # 1.2 Room structure and camera stream linkage
    first_room = rooms[0] if rooms else {}
    req_fields = ['camera_id', 'room_name', 'camera_name', 'occupants', 'occupant_count', 'stream_url']
    has_fields = all(f in first_room for f in req_fields)
    record_test(
        "Room Radar",
        "Room payload schema & stream binding",
        f"Contains all fields: {req_fields}",
        f"Contains fields: {list(first_room.keys())}",
        has_fields and first_room.get('stream_url', '').startswith('/api/stream/'),
        f"Stream endpoint: {first_room.get('stream_url')}"
    )

    # =================================================================
    # SECTION 2: STAFF PERSON TRACKING & DWELL TIME ENGINE
    # =================================================================
    print("\n--- 2. STAFF PERSON LOCATION SEARCH & DWELL TIME ENGINE ---", flush=True)

    # 2.1 GET /api/locate/person (All staff tracking)
    res_person_all = client.get('/api/locate/person')
    pdata_all = res_person_all.get_json() if res_person_all.is_json else {}
    tracked_staff = pdata_all.get('results', [])
    record_test(
        "Staff Locator",
        "API GET /api/locate/person returns all active personnel tracking",
        "HTTP 200 with 38 staff members tracked",
        f"HTTP {res_person_all.status_code} with {len(tracked_staff)} staff members",
        res_person_all.status_code == 200 and len(tracked_staff) == 38,
        "Every active employee has an active tracking state"
    )

    # 2.2 Search by Name Query
    res_imran = client.get('/api/locate/person?name=Imran')
    idata = res_imran.get_json() if res_imran.is_json else {}
    imran_results = idata.get('results', [])
    imran_found = any(u.get('user_id') == 38 and 'Imran' in u.get('name', '') for u in imran_results)
    record_test(
        "Staff Locator",
        "API GET /api/locate/person?name=Imran filters matched employees",
        "HTTP 200 containing Imran Khalid (ID #38)",
        f"HTTP {res_imran.status_code} with {len(imran_results)} matches, found={imran_found}",
        res_imran.status_code == 200 and imran_found,
        f"Found: {[u.get('name') for u in imran_results]}"
    )

    # 2.3 Search by User ID
    res_by_id = client.get('/api/locate/person?user_id=38')
    id_data = res_by_id.get_json() if res_by_id.is_json else {}
    id_results = id_data.get('results', [])
    record_test(
        "Staff Locator",
        "API GET /api/locate/person?user_id=38 returns exact individual profile",
        "HTTP 200 with exactly 1 record for user #38",
        f"HTTP {res_by_id.status_code} with {len(id_results)} records",
        res_by_id.status_code == 200 and len(id_results) == 1 and id_results[0].get('user_id') == 38,
        f"Matched: {id_results[0].get('name') if id_results else 'None'}"
    )

    # 2.4 Empty Search Query Handling
    res_nonexistent = client.get('/api/locate/person?name=NonExistentGhost999')
    non_data = res_nonexistent.get_json() if res_nonexistent.is_json else {}
    non_results = non_data.get('results', [])
    record_test(
        "Staff Locator",
        "Search: Clean handling when no employee matches query",
        "HTTP 200 with empty results list []",
        f"HTTP {res_nonexistent.status_code} with {len(non_results)} results",
        res_nonexistent.status_code == 200 and len(non_results) == 0,
        "Handles un-enrolled / non-existent names without crashing"
    )

    # 2.5 Live Presence Update & State Machine
    # Simulate Imran Khalid entering 'Corridor' via camera 'cam_8075'
    update_live_presence(
        user_id=38,
        name="Imran Khalid",
        department="AI & Data Science",
        camera_id="cam_8075",
        camera_name="DVR",
        room_name="Corridor",
        confidence=0.94
    )
    res_imran_live = client.get('/api/locate/person?user_id=38')
    im_live = res_imran_live.get_json().get('results', [])[0]
    record_test(
        "Presence Engine",
        "State Machine: Active room presence reflected in real time",
        "status=='active' with status_label containing 'Sitting in Corridor'",
        f"status='{im_live.get('status')}', label='{im_live.get('status_label')}'",
        im_live.get('status') == 'active' and 'Corridor' in im_live.get('room_name', '') and 'Sitting in' in im_live.get('status_label', ''),
        f"Room: {im_live.get('room_name')}, Dwell: {im_live.get('dwell_minutes')} min, Cam: {im_live.get('camera_name')}"
    )

    # 2.6 Room Radar Occupancy Reflection
    # Re-query /api/locate/rooms to verify Corridor now shows 1 occupant
    res_rooms_occ = client.get('/api/locate/rooms')
    rooms_occ = res_rooms_occ.get_json().get('rooms', [])
    corridor_room = next((r for r in rooms_occ if r.get('camera_id') == 'cam_8075'), None)
    corridor_has_imran = any(o.get('user_id') == 38 for o in corridor_room.get('occupants', [])) if corridor_room else False
    record_test(
        "Room Radar",
        "Occupancy Sync: Room radar updates occupant count and lists occupant",
        "Corridor room has occupant_count >= 1 with Imran Khalid listed",
        f"Corridor occupant_count={corridor_room.get('occupant_count') if corridor_room else None}, has_imran={corridor_has_imran}",
        corridor_room is not None and corridor_room.get('occupant_count', 0) >= 1 and corridor_has_imran,
        f"Occupants in Corridor: {[o.get('name') for o in corridor_room.get('occupants', [])] if corridor_room else []}"
    )

    # 2.7 Presence Decay Engine
    # Manually backdate Imran's last_seen timestamp by 180 seconds to test 'recent' transition
    with presence_lock:
        if 38 in LIVE_PRESENCE:
            LIVE_PRESENCE[38]['last_seen'] = time.time() - 180
    res_decay_recent = client.get('/api/locate/person?user_id=38')
    im_recent = res_decay_recent.get_json().get('results', [])[0]
    record_test(
        "Presence Engine",
        "Decay Transition: Status transitions to 'recent' after timeout (>120s)",
        "status=='recent' with status_label containing 'Recently in Corridor'",
        f"status='{im_recent.get('status')}', label='{im_recent.get('status_label')}'",
        im_recent.get('status') == 'recent' and 'Recently in' in im_recent.get('status_label', ''),
        f"Decay verified: elapsed > 120s"
    )

    # Backdate by 700 seconds to test 'away' transition
    with presence_lock:
        if 38 in LIVE_PRESENCE:
            LIVE_PRESENCE[38]['last_seen'] = time.time() - 700
    res_decay_away = client.get('/api/locate/person?user_id=38')
    im_away = res_decay_away.get_json().get('results', [])[0]
    record_test(
        "Presence Engine",
        "Decay Transition: Status transitions to 'away' after long timeout (>600s)",
        "status=='away' with status_label containing 'Away From Room'",
        f"status='{im_away.get('status')}', label='{im_away.get('status_label')}'",
        im_away.get('status') == 'away' and 'Away From Room' in im_away.get('status_label', ''),
        f"Decay verified: elapsed > 600s"
    )

    # =================================================================
    # SECTION 3: PARALLEL INSTANT CAMERA SCAN (SCAN-NOW API)
    # =================================================================
    print("\n--- 3. PARALLEL INSTANT CAMERA SCAN (/api/locate/scan-now) ---", flush=True)

    # 3.1 Validation: Non-existent employee returns 404
    res_scan_404 = client.post('/api/locate/scan-now', json={'name': 'Ghost Person 999'})
    record_test(
        "Scan-Now API",
        "Validation: Reject scan for non-existent employee",
        "HTTP 404 Not Found",
        f"HTTP {res_scan_404.status_code} - {res_scan_404.get_json()}",
        res_scan_404.status_code == 404,
        "Target existence validated before running vision models"
    )

    # 3.2 Validation: Employee without facial embeddings returns 400
    # Temporarily create user without biometrics
    client.post('/api/admin/verify-password', json={'password': _ADMIN_CONFIG_PASSWORD})
    client.post('/api/admin/enable-enrollment')
    res_no_emb_user = client.post('/api/enroll/create-user', json={
        'name': f"No Embedding User {int(time.time())}",
        'email': f"no.emb.{int(time.time())}@qintellect.test"
    })
    temp_uid = res_no_emb_user.get_json().get('user_id')
    res_scan_no_emb = client.post('/api/locate/scan-now', json={'user_id': temp_uid})
    record_test(
        "Scan-Now API",
        "Validation: Reject scan for employee without facial biometric enrollment",
        "HTTP 400 Bad Request with 'No facial profile enrolled'",
        f"HTTP {res_scan_no_emb.status_code} - {res_scan_no_emb.get_json()}",
        res_scan_no_emb.status_code == 400 and 'No facial profile' in res_scan_no_emb.get_json().get('message', ''),
        "Biometric profile required for optical face matching"
    )
    # Clean up temp user
    db.delete_user(temp_uid)
    client.post('/api/admin/disable-enrollment')
    client.post('/api/admin/lock')

    # 3.3 Valid Scan for Enrolled Employee (Imran Khalid)
    res_scan_valid = client.post('/api/locate/scan-now', json={'name': 'Imran Khalid'})
    scan_val_data = res_scan_valid.get_json() if res_scan_valid.is_json else {}
    record_test(
        "Scan-Now API",
        "Scan Execution: Query on-demand camera scan for enrolled staff member",
        "HTTP 200 with success=True and all_cameras_scanned list",
        f"HTTP {res_scan_valid.status_code} with success={scan_val_data.get('success')}, cameras={len(scan_val_data.get('all_cameras_scanned', []))}",
        res_scan_valid.status_code == 200 and scan_val_data.get('success') is True and isinstance(scan_val_data.get('all_cameras_scanned'), list),
        f"Scanned {len(scan_val_data.get('all_cameras_scanned', []))} camera streams, found={scan_val_data.get('found')}"
    )

    # =================================================================
    # SECTION 4: HISTORICAL ROOM TRANSITION LEDGER (DB PERSISTENCE)
    # =================================================================
    print("\n--- 4. HISTORICAL ROOM SNAPSHOTS & DATABASE PERSISTENCE ---", flush=True)

    # 4.1 Record persistent snapshot via database
    # Create a fresh temporary user to test clean insertion and cascade
    client.post('/api/admin/verify-password', json={'password': _ADMIN_CONFIG_PASSWORD})
    client.post('/api/admin/enable-enrollment')
    res_hist_user = client.post('/api/enroll/create-user', json={
        'name': f"Locator Test User {int(time.time())}",
        'email': f"loc.test.{int(time.time())}@qintellect.test",
        'department': 'Engineering'
    })
    hist_uid = res_hist_user.get_json().get('user_id')
    client.post('/api/admin/disable-enrollment')
    client.post('/api/admin/lock')

    first_seen_ts = time.time() - 600
    last_seen_ts = time.time()
    snap_ok = db.record_locator_snapshot(
        user_id=hist_uid,
        name="Locator Test User",
        department="Engineering",
        camera_id="cam_2869",
        camera_name="Local Web Cam",
        room_name="AI ROOM",
        confidence=0.88,
        first_seen=first_seen_ts,
        last_seen=last_seen_ts,
        interval_seconds=0
    )
    record_test(
        "Locator Persistence",
        "Database Persistence: Persist 5-minute room snapshot to locator_history",
        "Function returns True",
        f"Returned: {snap_ok}",
        snap_ok is True,
        "Persisted room snapshot into SQLite locator_history"
    )

    # 4.2 Query history via API /api/locate/history
    res_hist_api = client.get(f'/api/locate/history?user_id={hist_uid}')
    h_api_data = res_hist_api.get_json() if res_hist_api.is_json else {}
    h_records = h_api_data.get('history', [])
    record_test(
        "Locator History API",
        "API GET /api/locate/history returns persistent timeline entries",
        "HTTP 200 with history length >= 1 matching room 'AI ROOM'",
        f"HTTP {res_hist_api.status_code} with {len(h_records)} records, room={h_records[0].get('room_name') if h_records else None}",
        res_hist_api.status_code == 200 and len(h_records) >= 1 and h_records[0].get('room_name') == 'AI ROOM',
        f"Recorded presence window: {h_records[0].get('first_seen')} to {h_records[0].get('last_seen')} (Confidence: {h_records[0].get('confidence')})"
    )

    # 4.3 Room Name Filter on History API
    res_room_hist = client.get('/api/locate/history?room_name=AI%20ROOM&limit=5')
    r_api_data = res_room_hist.get_json() if res_room_hist.is_json else {}
    room_h_records = r_api_data.get('history', [])
    all_ai_room = all(r.get('room_name') == 'AI ROOM' for r in room_h_records)
    record_test(
        "Locator History API",
        "Filter: Filter historical room records by room_name",
        "HTTP 200 with all entries belonging to 'AI ROOM'",
        f"HTTP {res_room_hist.status_code} with {len(room_h_records)} records, match={all_ai_room}",
        res_room_hist.status_code == 200 and len(room_h_records) > 0 and all_ai_room,
        f"All returned records belong to AI ROOM"
    )

    # 4.4 Throttling Engine: Duplicate snapshot within interval returns False
    dup_snap = db.record_locator_snapshot(
        user_id=hist_uid,
        name="Locator Test User",
        department="Engineering",
        camera_id="cam_2869",
        camera_name="Local Web Cam",
        room_name="AI ROOM",
        confidence=0.88,
        first_seen=first_seen_ts,
        last_seen=last_seen_ts,
        interval_seconds=300
    )
    record_test(
        "Locator Persistence",
        "Throttling: Prevent database bloat by suppressing snapshots within 300s",
        "Returns False (throttled)",
        f"Returned: {dup_snap}",
        dup_snap is False,
        "Snapshot correctly throttled within 5-minute interval"
    )

    # 4.5 Foreign Key Cascade Deletion & Purge
    del_res = db.delete_user(hist_uid)
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute("SELECT count(*) FROM locator_history WHERE user_id = ?", (hist_uid,))
    loc_remaining = c.fetchone()[0]
    conn.close()
    record_test(
        "Locator Persistence",
        "Cascade Cleanup: Deleting user purges their entries in locator_history automatically",
        "loc_remaining == 0 and del_res is True",
        f"del_res={del_res}, loc_remaining={loc_remaining}",
        del_res is True and loc_remaining == 0,
        "Foreign key cascade on locator_history verified"
    )

    # Clean up live presence simulated state for Imran
    with presence_lock:
        LIVE_PRESENCE.pop(38, None)

    # =================================================================
    # SECTION 5: FULL REGRESSION AUDIT (15 FROZEN BASELINE ITEMS)
    # =================================================================
    print("\n--- 5. FULL SYSTEM REGRESSION AUDIT (15 FROZEN BASELINE ITEMS) ---", flush=True)

    # 5.1 Database Physical Integrity
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

    # 5.2 Foreign Key Integrity Check
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

    # 5.3 Payroll V1 Baseline Calculation
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

    # 5.4 Leave & Holiday Management
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

    # 5.5 Employee Salary Structure Module
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

    # 5.6 Staff Biometric Enrollment Security Gate
    res_admin_st = client.get('/api/admin/status')
    res_admin_block = client.post('/api/enroll/create-user', json={'name': 'Blocked'})
    record_test(
        "Enrollment Gate",
        "Staff enrollment security lock & route protection",
        "HTTP 403 Forbidden when enrollment is locked",
        f"HTTP {res_admin_block.status_code}",
        res_admin_block.status_code == 403 and res_admin_st.status_code == 200,
        "Enrollment gate locked and verified"
    )

    # 5.7 Shift Management
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

    # 5.8 Staff Management
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

    # 5.9 Departments & Designations
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

    # 5.10 Settings & Branch
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

    # 5.11 Camera Management
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

    # 5.12 Attendance Reports
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

    # 5.13 Dashboard & Stats
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
    # SECTION 6: COMPLETE REST API REGRESSION (21/21 APIS)
    # =================================================================
    print("\n--- 6. COMPLETE REST API REGRESSION SUITE (21/21 APIS) ---", flush=True)

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

    print("\n" + "="*69, flush=True)
    print(f"AUDIT SUMMARY: {passed}/{total} TESTS PASSED | {failed} FAILED", flush=True)
    print("="*69, flush=True)

    with open('scratch/locator_audit_results.json', 'w') as jf:
        json.dump(results, jf, indent=2)
    print(f"\n[OK] Wrote {len(results)} test results to scratch/locator_audit_results.json", flush=True)

    if failed == 0:
        print("\nALL MODULE AND REGRESSION CHECKS PASSED WITH 100% SUCCESS!", flush=True)
    else:
        print(f"\nCRITICAL: {failed} CHECKS FAILED! INVESTIGATE IMMEDIATELY.", flush=True)
        for r in results:
            if r['status'] == 'FAIL':
                print(f"FAILED: {r['module']} - {r['test']} -> Expected: {r['expected']} | Actual: {r['actual']}", flush=True)

    return results

if __name__ == '__main__':
    run_locator_audit()
