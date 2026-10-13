import sys
sys.path.insert(0, '.')
import database as db

for c in db.get_all_cameras():
    print(f"ID={c['id']}, camera_id='{c['camera_id']}', name='{c['name']}', room_name='{c['room_name']}'")
