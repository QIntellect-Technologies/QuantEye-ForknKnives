import sys
import os
import json
import sqlite3

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
import database as db

def run_audit():
    client = app.test_client()
    results = []

    def record_test(test_id, action, expected, actual, passed, evidence, severity=None, affects=None):
        results.append({
            'test_id': test_id,
            'action': action,
            'expected': str(expected),
            'actual': str(actual),
            'passed': bool(passed),
            'evidence': evidence,
            'severity': severity,
            'affects': affects
        })

    # =========================================================================
    # 0. BASELINE CAPTURE
    # =========================================================================
    conn = sqlite3.connect('attendance.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    baseline_counts = {
        'users': cur.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'departments': cur.execute("SELECT COUNT(*) FROM departments").fetchone()[0],
        'designations': cur.execute("SELECT COUNT(*) FROM designations").fetchone()[0],
        'shifts': cur.execute("SELECT COUNT(*) FROM shifts").fetchone()[0],
        'attendance': cur.execute("SELECT COUNT(*) FROM attendance").fetchone()[0],
        'leave_requests': cur.execute("SELECT COUNT(*) FROM leave_requests").fetchone()[0],
        'overtime': cur.execute("SELECT COUNT(*) FROM overtime").fetchone()[0],
        'salary_configs': cur.execute("SELECT COUNT(*) FROM salary_configs").fetchone()[0],
        'payroll_records': cur.execute("SELECT COUNT(*) FROM payroll_records").fetchone()[0],
        'embeddings': cur.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0],
    }

    cur.execute("PRAGMA integrity_check;")
    baseline_ic = cur.fetchall()
    cur.execute("PRAGMA foreign_key_check;")
    baseline_fk = cur.fetchall()

    print("=" * 80)
    print("INITIAL DATABASE BASELINE:")
    for k, v in baseline_counts.items():
        print(f"  {k:20s}: {v}")
    print(f"  integrity_check     : {baseline_ic[0][0]}")
    print(f"  foreign_key_check   : {len(baseline_fk)} violations")
    print("=" * 80)

    # =========================================================================
    # MODULE 1 — DEPARTMENTS AUDIT
    # =========================================================================
    print("\n--- AUDITING MODULE 1: DEPARTMENTS ---")

    # DEP-01: List existing departments
    res = client.get('/api/departments')
    passed = res.status_code == 200 and isinstance(res.get_json(), list) and len(res.get_json()) > 0
    depts = res.get_json() if passed else []
    record_test(
        'DEP-01',
        'GET /api/departments (List all)',
        'HTTP 200 with non-empty JSON list',
        f'HTTP {res.status_code}, count={len(depts)}',
        passed,
        f"Fetched {len(depts)} departments. First: {depts[0].get('name') if depts else 'N/A'}"
    )

    # DEP-02: Active filter
    res = client.get('/api/departments?active_only=true')
    active_depts = res.get_json() if res.status_code == 200 else []
    all_active = all(d.get('active') == 1 for d in active_depts)
    record_test(
        'DEP-02',
        'GET /api/departments?active_only=true',
        'HTTP 200, all returned items active==1',
        f'HTTP {res.status_code}, count={len(active_depts)}, all_active={all_active}',
        res.status_code == 200 and all_active,
        f"Total active departments: {len(active_depts)}"
    )

    # DEP-03: Create audit department
    audit_dept_name = "QA Audit Automated Dept 2026"
    audit_dept_code = "QAA"
    audit_dept_desc = "Temporary department created for production audit"
    res = client.post('/api/departments', json={
        'name': audit_dept_name,
        'code': audit_dept_code,
        'description': audit_dept_desc
    })
    created_data = res.get_json() or {}
    created_dept_id = created_data.get('id')
    passed = res.status_code == 201 and created_data.get('success') is True and created_dept_id is not None
    record_test(
        'DEP-03',
        f'POST /api/departments (Create "{audit_dept_name}")',
        'HTTP 201 with success=True and integer ID',
        f"HTTP {res.status_code}, id={created_dept_id}, success={created_data.get('success')}",
        passed,
        f"Response payload: {created_data}"
    )

    # DEP-04: Database persistence verification
    cur.execute("SELECT * FROM departments WHERE id = ?", (created_dept_id,))
    dept_row = cur.fetchone()
    db_persisted = (
        dept_row is not None and
        dept_row['name'] == audit_dept_name and
        dept_row['code'] == audit_dept_code and
        dept_row['description'] == audit_dept_desc and
        dept_row['active'] == 1
    )
    record_test(
        'DEP-04',
        'Verify SQLite row persistence for newly created department',
        f'Row exists with name="{audit_dept_name}", code="{audit_dept_code}", active=1',
        f'Row found={dept_row is not None}, name="{dept_row["name"] if dept_row else None}", active={dept_row["active"] if dept_row else None}',
        db_persisted,
        f"SQLite row values: {dict(dept_row) if dept_row else None}"
    )

    # DEP-05: Required field validation (empty name)
    res = client.post('/api/departments', json={'name': '', 'code': 'EMPTY'})
    passed = res.status_code == 400
    record_test(
        'DEP-05',
        'POST /api/departments with empty name',
        'HTTP 400 Bad Request',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Response: {res.get_json()}"
    )

    # DEP-06: Duplicate name validation
    res = client.post('/api/departments', json={
        'name': audit_dept_name,
        'code': 'DUP',
        'description': 'Duplicate attempt'
    })
    passed = res.status_code == 409
    record_test(
        'DEP-06',
        'POST /api/departments with duplicate name',
        'HTTP 409 Conflict',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Duplicate rejection response: {res.get_json()}"
    )

    # DEP-07: Edit existing department
    updated_name = "QA Audit Automated Dept 2026 - Updated"
    updated_code = "QAA-UPD"
    updated_desc = "Updated description during audit"
    res = client.put(f'/api/departments/{created_dept_id}', json={
        'name': updated_name,
        'code': updated_code,
        'description': updated_desc,
        'active': 1
    })
    passed = res.status_code == 200 and (res.get_json() or {}).get('success') is True
    cur.execute("SELECT * FROM departments WHERE id = ?", (created_dept_id,))
    upd_row = cur.fetchone()
    db_updated = upd_row and upd_row['name'] == updated_name and upd_row['code'] == updated_code
    record_test(
        'DEP-07',
        f'PUT /api/departments/{created_dept_id} (Update details)',
        'HTTP 200, success=True, SQLite row updated',
        f'HTTP {res.status_code}, DB updated={db_updated}',
        passed and db_updated,
        f"Updated SQLite row: {dict(upd_row) if upd_row else None}"
    )

    # DEP-08: Edit validation (empty name)
    res = client.put(f'/api/departments/{created_dept_id}', json={'name': ''})
    passed = res.status_code == 400
    record_test(
        'DEP-08',
        f'PUT /api/departments/{created_dept_id} with empty name',
        'HTTP 400 Bad Request',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Response: {res.get_json()}"
    )

    # DEP-09: Delete / soft-delete behavior
    res = client.delete(f'/api/departments/{created_dept_id}')
    del_data = res.get_json() or {}
    passed = res.status_code == 200 and del_data.get('success') is True
    cur.execute("SELECT * FROM departments WHERE id = ?", (created_dept_id,))
    del_row = cur.fetchone()
    is_soft_delete = del_row is not None and del_row['active'] == 0
    record_test(
        'DEP-09',
        f'DELETE /api/departments/{created_dept_id}',
        'HTTP 200, success=True, SQLite active set to 0 (soft-delete)',
        f'HTTP {res.status_code}, row exists={del_row is not None}, active={del_row["active"] if del_row else None}',
        passed and is_soft_delete,
        f"Soft-delete confirmed: active={del_row['active'] if del_row else 'None'}"
    )

    # DEP-10: Inactive excluded from active_only=true
    res = client.get('/api/departments?active_only=true')
    active_ids = [d['id'] for d in (res.get_json() or [])]
    passed = created_dept_id not in active_ids
    record_test(
        'DEP-10',
        'GET /api/departments?active_only=true (Verify soft-deleted exclusion)',
        'Soft-deleted department excluded from active list',
        f'Found in active_ids: {created_dept_id in active_ids}',
        passed,
        f"Inactive ID {created_dept_id} excluded from active list"
    )

    # DEP-11: Inactive included in active_only=false
    res = client.get('/api/departments?active_only=false')
    all_ids = [d['id'] for d in (res.get_json() or [])]
    passed = created_dept_id in all_ids
    record_test(
        'DEP-11',
        'GET /api/departments?active_only=false (Verify soft-deleted inclusion in full list)',
        'Soft-deleted department included in full list',
        f'Found in all_ids: {created_dept_id in all_ids}',
        passed,
        f"ID {created_dept_id} present in full list"
    )

    # DEP-12: Staff count computation
    # Check that staff_count in GET /api/departments accurately reflects users table
    cur.execute("SELECT department, COUNT(*) as cnt FROM users WHERE active=1 AND department IS NOT NULL GROUP BY department")
    actual_counts = {r['department']: r['cnt'] for r in cur.fetchall()}
    dept_api_list = client.get('/api/departments').get_json() or []
    counts_match = True
    for d in dept_api_list:
        expected_cnt = actual_counts.get(d['name'], 0)
        if d.get('staff_count') != expected_cnt:
            counts_match = False
            break
    record_test(
        'DEP-12',
        'Department staff_count calculation accuracy',
        'staff_count matches COUNT(*) in users table for each department',
        f'Counts match: {counts_match}',
        counts_match,
        f"Compared {len(dept_api_list)} departments against users table"
    )

    # DEP-13: Designation count computation
    cur.execute("SELECT department_id, COUNT(*) as cnt FROM designations WHERE active=1 GROUP BY department_id")
    actual_desig_counts = {r['department_id']: r['cnt'] for r in cur.fetchall()}
    desig_counts_match = True
    for d in dept_api_list:
        expected_desig_cnt = actual_desig_counts.get(d['id'], 0)
        if d.get('designation_count') != expected_desig_cnt:
            desig_counts_match = False
            break
    record_test(
        'DEP-13',
        'Department designation_count calculation accuracy',
        'designation_count matches COUNT(*) in designations table',
        f'Counts match: {desig_counts_match}',
        desig_counts_match,
        f"Compared {len(dept_api_list)} departments against designations table"
    )

    # DEP-14: Availability to Staff Enrollment
    # Staff enrollment dropdown is populated via /api/departments?active_only=true
    res = client.get('/api/departments?active_only=true')
    enroll_options = [d['name'] for d in (res.get_json() or [])]
    has_baseline_depts = 'AI & Data Science' in enroll_options and 'Software Development' in enroll_options
    record_test(
        'DEP-14',
        'Department availability for Staff Enrollment dropdown',
        'Active departments available for enrollment options',
        f'Count={len(enroll_options)}, contains core depts={has_baseline_depts}',
        has_baseline_depts,
        f"Available departments for enrollment: {enroll_options[:5]}..."
    )

    # =========================================================================
    # MODULE 2 — DESIGNATIONS AUDIT
    # =========================================================================
    print("\n--- AUDITING MODULE 2: DESIGNATIONS ---")

    # DES-01: List existing designations
    res = client.get('/api/designations')
    passed = res.status_code == 200 and isinstance(res.get_json(), list) and len(res.get_json()) > 0
    desigs = res.get_json() if passed else []
    record_test(
        'DES-01',
        'GET /api/designations (List all)',
        'HTTP 200 with non-empty JSON list',
        f'HTTP {res.status_code}, count={len(desigs)}',
        passed,
        f"Fetched {len(desigs)} designations. First: {desigs[0].get('title') if desigs else 'N/A'}"
    )

    # DES-02: Filter by department_id
    dept_1_desigs = client.get('/api/designations?department_id=1').get_json() or []
    all_dept_1 = all(d.get('department_id') == 1 for d in dept_1_desigs)
    record_test(
        'DES-02',
        'GET /api/designations?department_id=1',
        'HTTP 200, all records have department_id == 1',
        f'count={len(dept_1_desigs)}, all_match={all_dept_1}',
        len(dept_1_desigs) > 0 and all_dept_1,
        f"Titles: {[d.get('title') for d in dept_1_desigs]}"
    )

    # DES-03: Filter by department_name
    dept_name_desigs = client.get('/api/designations?department_name=AI%20%26%20Data%20Science').get_json() or []
    all_dept_name = all(d.get('department_name') == 'AI & Data Science' for d in dept_name_desigs)
    record_test(
        'DES-03',
        'GET /api/designations?department_name=AI & Data Science',
        'HTTP 200, all records belong to specified department name',
        f'count={len(dept_name_desigs)}, all_match={all_dept_name}',
        len(dept_name_desigs) > 0 and all_dept_name,
        f"Titles: {[d.get('title') for d in dept_name_desigs]}"
    )

    # DES-04: Create designation under valid department
    audit_desig_title = "QA Automation Lead Engineer 2026"
    audit_desig_desc = "Temporary designation for production audit"
    res = client.post('/api/designations', json={
        'department_id': 1,
        'title': audit_desig_title,
        'description': audit_desig_desc
    })
    created_desig_data = res.get_json() or {}
    created_desig_id = created_desig_data.get('id')
    passed = res.status_code == 201 and created_desig_data.get('success') is True and created_desig_id is not None
    record_test(
        'DES-04',
        f'POST /api/designations (Create "{audit_desig_title}" under dept_id=1)',
        'HTTP 201 with success=True and integer ID',
        f"HTTP {res.status_code}, id={created_desig_id}, success={created_desig_data.get('success')}",
        passed,
        f"Response payload: {created_desig_data}"
    )

    # DES-05: Database persistence verification
    cur.execute("SELECT * FROM designations WHERE id = ?", (created_desig_id,))
    desig_row = cur.fetchone()
    db_desig_persisted = (
        desig_row is not None and
        desig_row['department_id'] == 1 and
        desig_row['title'] == audit_desig_title and
        desig_row['description'] == audit_desig_desc and
        desig_row['active'] == 1
    )
    record_test(
        'DES-05',
        'Verify SQLite row persistence for newly created designation',
        f'Row exists with department_id=1, title="{audit_desig_title}", active=1',
        f'Row found={desig_row is not None}, title="{desig_row["title"] if desig_row else None}", active={desig_row["active"] if desig_row else None}',
        db_desig_persisted,
        f"SQLite row values: {dict(desig_row) if desig_row else None}"
    )

    # DES-06: Required field validation (missing title)
    res = client.post('/api/designations', json={'department_id': 1, 'title': ''})
    passed = res.status_code == 400
    record_test(
        'DES-06',
        'POST /api/designations with empty title',
        'HTTP 400 Bad Request',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Response: {res.get_json()}"
    )

    # DES-07: Missing department_id validation
    res = client.post('/api/designations', json={'title': 'Test Title'})
    passed = res.status_code == 400
    record_test(
        'DES-07',
        'POST /api/designations with missing department_id',
        'HTTP 400 Bad Request',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Response: {res.get_json()}"
    )

    # DES-08: Nonexistent department_id handling
    # Let's see what happens if department_id does not exist
    res = client.post('/api/designations', json={'department_id': 999999, 'title': 'Ghost Desig'})
    res_code = res.status_code
    res_json = res.get_json()
    # In sqlite, does it reject or insert? Let's check:
    cur.execute("SELECT id FROM designations WHERE title = 'Ghost Desig'")
    ghost_row = cur.fetchone()
    if ghost_row:
        # Clean ghost row immediately
        cur.execute("DELETE FROM designations WHERE id = ?", (ghost_row['id'],))
        conn.commit()
    record_test(
        'DES-08',
        'POST /api/designations with non-existent department_id=999999',
        'Should reject or return error if FK enforced',
        f'HTTP {res_code}: {res_json}',
        res_code in [400, 404, 500] or (ghost_row is None),
        f"Server response: {res_json}, ghost row inserted: {ghost_row is not None}",
        severity='LOW' if ghost_row is not None else None,
        affects='Foreign key validation on designation creation' if ghost_row is not None else None
    )

    # DES-09: Edit existing designation
    upd_desig_title = "QA Automation Lead Engineer 2026 - Updated"
    upd_desig_desc = "Updated description during audit"
    res = client.put(f'/api/designations/{created_desig_id}', json={
        'title': upd_desig_title,
        'description': upd_desig_desc,
        'active': 1
    })
    passed = res.status_code == 200 and (res.get_json() or {}).get('success') is True
    cur.execute("SELECT * FROM designations WHERE id = ?", (created_desig_id,))
    upd_d_row = cur.fetchone()
    db_upd_ok = upd_d_row and upd_d_row['title'] == upd_desig_title and upd_d_row['description'] == upd_desig_desc
    record_test(
        'DES-09',
        f'PUT /api/designations/{created_desig_id} (Update title & description)',
        'HTTP 200, success=True, SQLite row updated',
        f'HTTP {res.status_code}, DB updated={db_upd_ok}',
        passed and db_upd_ok,
        f"Updated SQLite row: {dict(upd_d_row) if upd_d_row else None}"
    )

    # DES-10: Edit validation (empty title)
    res = client.put(f'/api/designations/{created_desig_id}', json={'title': ''})
    passed = res.status_code == 400
    record_test(
        'DES-10',
        f'PUT /api/designations/{created_desig_id} with empty title',
        'HTTP 400 Bad Request',
        f'HTTP {res.status_code}: {res.get_json()}',
        passed,
        f"Response: {res.get_json()}"
    )

    # DES-11: Delete / soft-delete behavior
    res = client.delete(f'/api/designations/{created_desig_id}')
    del_d_data = res.get_json() or {}
    passed = res.status_code == 200 and del_d_data.get('success') is True
    cur.execute("SELECT * FROM designations WHERE id = ?", (created_desig_id,))
    del_d_row = cur.fetchone()
    is_d_soft_delete = del_d_row is not None and del_d_row['active'] == 0
    record_test(
        'DES-11',
        f'DELETE /api/designations/{created_desig_id}',
        'HTTP 200, success=True, SQLite active set to 0 (soft-delete)',
        f'HTTP {res.status_code}, row exists={del_d_row is not None}, active={del_d_row["active"] if del_d_row else None}',
        passed and is_d_soft_delete,
        f"Soft-delete confirmed: active={del_d_row['active'] if del_d_row else 'None'}"
    )

    # DES-12: Inactive excluded from active_only=true
    res = client.get('/api/designations?active_only=true')
    active_d_ids = [d['id'] for d in (res.get_json() or [])]
    passed = created_desig_id not in active_d_ids
    record_test(
        'DES-12',
        'GET /api/designations?active_only=true (Verify soft-deleted exclusion)',
        'Soft-deleted designation excluded from active list',
        f'Found in active_d_ids: {created_desig_id in active_d_ids}',
        passed,
        f"Inactive ID {created_desig_id} excluded from active list"
    )

    # DES-13: Staff Enrollment cascading dependency
    # When user selects department in enrollment, UI calls /api/designations?department_name=<name>&active_only=true
    res = client.get('/api/designations?department_name=Software%20Development&active_only=true')
    dev_desigs = res.get_json() or []
    has_dev_roles = len(dev_desigs) > 0 and any('Developer' in d.get('title', '') for d in dev_desigs)
    record_test(
        'DES-13',
        'Designations cascading to Staff Enrollment by department_name',
        'Returns active designations for selected department',
        f'Count={len(dev_desigs)}, has_dev_roles={has_dev_roles}',
        has_dev_roles,
        f"Cascaded designations: {[d.get('title') for d in dev_desigs]}"
    )

    # DES-14: Orphan check across all designations
    cur.execute("""
        SELECT d.id, d.title, d.department_id 
        FROM designations d 
        LEFT JOIN departments dept ON d.department_id = dept.id 
        WHERE dept.id IS NULL
    """)
    orphan_desigs = cur.fetchall()
    record_test(
        'DES-14',
        'Designation orphan check in SQLite database',
        '0 orphan designations (all reference existing departments)',
        f'Orphan count={len(orphan_desigs)}',
        len(orphan_desigs) == 0,
        f"Orphan records: {[dict(r) for r in orphan_desigs]}"
    )

    # =========================================================================
    # CLEAN UP AUDIT RECORDS
    # =========================================================================
    print("\n--- CLEANING UP TEMPORARY AUDIT RECORDS ---")
    if created_desig_id:
        cur.execute("DELETE FROM designations WHERE id = ?", (created_desig_id,))
        conn.commit()
        print(f"  [CLEAN] Removed audit designation ID {created_desig_id}")
    if created_dept_id:
        cur.execute("DELETE FROM departments WHERE id = ?", (created_dept_id,))
        conn.commit()
        print(f"  [CLEAN] Removed audit department ID {created_dept_id}")

    # =========================================================================
    # POST-AUDIT BASELINE RECONCILIATION
    # =========================================================================
    print("\n--- RECONCILING BASELINE AFTER AUDIT ---")
    post_counts = {
        'users': cur.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        'departments': cur.execute("SELECT COUNT(*) FROM departments").fetchone()[0],
        'designations': cur.execute("SELECT COUNT(*) FROM designations").fetchone()[0],
        'shifts': cur.execute("SELECT COUNT(*) FROM shifts").fetchone()[0],
        'attendance': cur.execute("SELECT COUNT(*) FROM attendance").fetchone()[0],
        'leave_requests': cur.execute("SELECT COUNT(*) FROM leave_requests").fetchone()[0],
        'overtime': cur.execute("SELECT COUNT(*) FROM overtime").fetchone()[0],
        'salary_configs': cur.execute("SELECT COUNT(*) FROM salary_configs").fetchone()[0],
        'payroll_records': cur.execute("SELECT COUNT(*) FROM payroll_records").fetchone()[0],
        'embeddings': cur.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0],
    }

    cur.execute("PRAGMA integrity_check;")
    post_ic = cur.fetchall()
    cur.execute("PRAGMA foreign_key_check;")
    post_fk = cur.fetchall()

    baseline_identical = True
    for k in baseline_counts:
        diff = post_counts[k] - baseline_counts[k]
        if diff != 0:
            baseline_identical = False
            print(f"  [FAIL] Count mismatch in {k}: before={baseline_counts[k]}, after={post_counts[k]}")
        else:
            print(f"  [OK] {k:20s}: {post_counts[k]} (Unchanged)")

    record_test(
        'BASE-01',
        'Database baseline counts identical before and after audit',
        'All 10 table counts match baseline exactly (0 lingering audit records)',
        f'identical={baseline_identical}',
        baseline_identical,
        f"Post counts: {post_counts}"
    )

    record_test(
        'BASE-02',
        'PRAGMA integrity_check after audit',
        'ok',
        f"{post_ic[0][0]}",
        post_ic == [('ok',)],
        f"Integrity check result: {post_ic}"
    )

    record_test(
        'BASE-03',
        'PRAGMA foreign_key_check after audit',
        '0 violations',
        f"{len(post_fk)} violations",
        len(post_fk) == 0,
        f"FK check result: {post_fk}"
    )

    conn.close()

    # Save results to json
    with open('scratch/audit_modules_1_2_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    passed_count = sum(1 for r in results if r['passed'])
    failed_count = sum(1 for r in results if not r['passed'])

    print("\n" + "=" * 80)
    print(f"AUDIT MODULES 1 & 2 SUMMARY: {passed_count}/{len(results)} PASSED | {failed_count} FAILED")
    print("=" * 80)

    for r in results:
        status_symbol = "[PASS]" if r['passed'] else "[FAIL]"
        print(f"{status_symbol} {r['test_id']}: {r['action']}")
        print(f"       Expected: {r['expected']}")
        print(f"       Actual:   {r['actual']}")
        if not r['passed']:
            print(f"       Severity: {r.get('severity')}")
            print(f"       Affects : {r.get('affects')}")

if __name__ == '__main__':
    run_audit()
