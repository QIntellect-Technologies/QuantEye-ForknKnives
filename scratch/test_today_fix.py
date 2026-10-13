import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
import database as db

# Test report with target_date='today'
print("--- TEST WITH target_date='today' ---")
rep = db.get_detailed_attendance_report(target_date='today')
print("Summary:", rep['summary'])
imran_rec = [r for r in rep['records'] if r['user_id'] == 38]
print("Imran record:", imran_rec)

# Test query directly if target_date is '2026-10-06'
print("\n--- TEST WITH target_date='2026-10-06' ---")
rep2 = db.get_detailed_attendance_report(target_date='2026-10-06')
print("Summary:", rep2['summary'])
imran_rec2 = [r for r in rep2['records'] if r['user_id'] == 38]
print("Imran record:", imran_rec2)
