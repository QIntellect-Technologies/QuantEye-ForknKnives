import sys
sys.path.append('.')
import database
report = database.get_detailed_attendance_report(start_date='2026-10-01', end_date='2026-10-10')
records = report.get('records', [])
abdul = next((r for r in records if r['user_id'] == 46), None)
if abdul:
    for day in abdul.get('daily_records', []):
        print(f"{day['date']} - {day['day']} - status: {day['status']}, scheduled_workday: {day['scheduled_workday']}, shift_name: {day.get('shift_name')}")
else:
    print("User 46 not found")
