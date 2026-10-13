import sys
sys.path.insert(0, r'd:\QIntellect-AI-Attendence-11-9-2026\Final-AI-Attendence-System\Final-AI-Attendence-System\Flask-Attedence')
import database as db
report = db.get_detailed_attendance_report(start_date='2026-10-01', end_date='2026-10-10')
for r in report['records']:
    if r['user_id'] == 38:
        for d in r['daily_records']:
            print(f"{d['date']}: {d['status']} (override: {d.get('calendar_override')})")
