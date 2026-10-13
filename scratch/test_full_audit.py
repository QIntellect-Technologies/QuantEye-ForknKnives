import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import database as db

def audit_database():
    print("=== DATABASE AUDIT ===")
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in c.fetchall()]
    print(f"Total tables: {len(tables)}")
    for t in tables:
        c.execute(f"SELECT count(*) FROM {t}")
        cnt = c.fetchone()[0]
        print(f"  Table: {t} ({cnt} rows)")
        
    print("\n=== ACTIVE USERS / EMPLOYEES ===")
    users = db.get_all_users()
    print(f"Total users retrieved: {len(users)}")
    for u in users[:5]:
        print(f"  User #{u['id']}: {u['name']} | Dept: {u['department']} | Role: {u['position']} | Shift: {u.get('shift_name')}")
        
    print("\n=== SHIFTS ===")
    shifts = db.get_all_shifts()
    print(f"Total shifts: {len(shifts)}")
    for s in shifts:
        print(f"  Shift #{s['id']}: {s['name']} ({s['start_time']} - {s['end_time']}) | Grace: {s['grace_period_minutes']}m")
        
    print("\n=== DEPARTMENTS ===")
    depts = db.get_all_departments_list(active_only=False)
    print(f"Total configured departments: {len(depts)}")
    for d in depts:
        print(f"  Dept #{d['id']}: {d['name']} | Staff: {d.get('staff_count', 0)} | Roles: {d.get('designation_count', 0)} | Active: {d.get('active')}")
        
    print("\n=== DESIGNATIONS ===")
    desigs = db.get_designations(active_only=False)
    print(f"Total configured designations: {len(desigs)}")
    for ds in desigs[:5]:
        print(f"  Desig #{ds['id']}: {ds['title']} (Dept: {ds.get('department_name')}) | Active: {ds.get('active')}")
        
    print("\n=== CAMERAS ===")
    cams = db.get_all_cameras(active_only=False)
    print(f"Total configured cameras: {len(cams)}")
    for cam in cams:
        print(f"  Camera #{cam['id']}: {cam['name']} ({cam['camera_type']}) | Loc: {cam.get('room_name', cam.get('location'))} | Active: {cam['active']}")

    print("\n=== SETTINGS ===")
    branch = db.get_branch_settings()
    print(f"Branch Settings: {branch}")
    
    print("\n=== ATTENDANCE REPORT LOGICAL INTEGRITY TESTS ===")
    r_today = db.get_detailed_attendance_report(target_date='today')
    r_yest = db.get_detailed_attendance_report(target_date='yesterday')
    r_last7 = db.get_detailed_attendance_report(target_date='last7')
    r_last30 = db.get_detailed_attendance_report(target_date='last30')
    r_this_month = db.get_detailed_attendance_report(target_date='this_month')
    
    print(f"Today report records: {len(r_today['records'])} (is_multi_day: {r_today['is_multi_day']})")
    print(f"Yesterday report records: {len(r_yest['records'])} (is_multi_day: {r_yest['is_multi_day']})")
    print(f"Last 7 Days records: {len(r_last7['records'])} (is_multi_day: {r_last7['is_multi_day']})")
    print(f"Last 30 Days records: {len(r_last30['records'])} (is_multi_day: {r_last30['is_multi_day']})")
    print(f"This Month records: {len(r_this_month['records'])} (is_multi_day: {r_this_month['is_multi_day']})")
    
    # Check if yesterday attended records are accounted for in multi-day
    yest_attended = [r for r in r_yest['records'] if r.get('status') in ('present', 'late', 'checked_out')]
    print(f"Yesterday attended count: {len(yest_attended)}")
    if yest_attended:
        for ya in yest_attended:
            m7 = next((x for x in r_last7['records'] if x['user_id'] == ya['user_id']), None)
            assert m7 is not None, f"User {ya['user_id']} missing in Last 7 Days!"
            assert m7['present_days'] >= 1, f"User {ya['user_id']} attended yesterday but present_days in Last 7 is {m7['present_days']}"
            print(f"  [PASS] User #{ya['user_id']} ({ya['name']}) attended yesterday -> present in Last 7 Days ({m7['present_days']} present days)")
            
    # Test Complete View daily records for Imran Khalid
    imran = next((x for x in r_last30['records'] if 'imran' in x['name'].lower()), None)
    if imran:
        print(f"\n=== COMPLETE VIEW AUDIT FOR {imran['name']} (Last 30 Days) ===")
        print(f"  Total Days: {imran['total_days']}, Present: {imran['present_days']}, Absent: {imran['absent_days']}, Late: {imran['late_days']}")
        print(f"  Daily Records Attached: {len(imran['daily_records'])}")
        assert len(imran['daily_records']) == imran['total_days'], "Daily records count mismatch!"
        sample_days = [d for d in imran['daily_records'] if d['status'] != 'absent']
        for sd in sample_days:
            print(f"   - {sd['date']} ({sd['day']}): Status={sd['status']}, FirstSeen={sd['first_seen']}, LastSeen={sd['last_seen']}")

    print("\nALL AUDIT CHECKS COMPLETED SUCCESSFULLY.")

if __name__ == "__main__":
    audit_database()
