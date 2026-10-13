import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database as db

# Test bulk mark with specific IDs [38, 46]
users = [38, 46]

for uid in users:
    db.mark_user_present_today(uid)

rep = db.get_detailed_attendance_report(target_date='today')
print("Present after marking [38, 46]:", rep['summary']['present'])
present_ids = [r['user_id'] for r in rep['records'] if r['status'] == 'present']
print("Present user IDs:", present_ids)
