import sys
sys.path.append('.')
import database
report = database.get_detailed_attendance_report(start_date='2026-10-01', end_date='2026-10-31')
records = report.get('records', [])
abdul = next((r for r in records if r['user_id'] == 46), None)
if abdul:
    for day in abdul.get('daily_records', []):
        if '2026-10-08' <= day['date'] <= '2026-10-12':
            print(f"{day['date']} - status: {day['status']}, scheduled_workday: {day['scheduled_workday']}")
