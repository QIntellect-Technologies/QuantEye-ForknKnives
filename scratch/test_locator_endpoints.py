import sys
sys.path.insert(0, ".")
import time
import json
import sqlite3
from app import app, update_live_presence, LIVE_PRESENCE
import database as db

client = app.test_client()

print("=======================================================")
print("     TESTING STAFF & ROOM LOCATOR ENDPOINTS & LOGIC    ")
print("=======================================================")

# 1. Test GET /api/locate/rooms
res_rooms = client.get('/api/locate/rooms')
print("Rooms API Status:", res_rooms.status_code)
rdata = res_rooms.get_json() if res_rooms.is_json else {}
rooms = rdata.get('rooms', [])
print(f"Total Rooms returned: {len(rooms)}")
for r in rooms:
    print(f" - Room: '{r.get('room_name')}' (Cam: {r.get('camera_name')}), Occupants: {r.get('occupant_count')}")

# 2. Test GET /api/locate/person (all staff)
res_person_all = client.get('/api/locate/person')
print("\nLocate Person All Status:", res_person_all.status_code)
pdata_all = res_person_all.get_json() if res_person_all.is_json else {}
results_all = pdata_all.get('results', [])
print(f"Total staff members tracked: {len(results_all)}")

# 3. Test GET /api/locate/person?name=Imran
res_imran = client.get('/api/locate/person?name=Imran')
print("\nLocate Imran Status:", res_imran.status_code)
idata = res_imran.get_json() if res_imran.is_json else {}
imran_res = idata.get('results', [])
print(f"Matched staff for 'Imran': {len(imran_res)}")
if imran_res:
    im = imran_res[0]
    print(f" - Found: {im.get('name')} (ID #{im.get('user_id')}), Status: {im.get('status_label')}, Room: {im.get('room_name')}")

# 4. Test simulate live presence in room
print("\nSimulating Live Presence for Imran Khalid in 'Main Office' via camera 'dvr'...")
update_live_presence(
    user_id=38,
    name="Imran Khalid",
    department="AI & Data Science",
    camera_id="dvr",
    camera_name="DVR",
    room_name="Main Office",
    confidence=0.92
)

# 5. Re-check /api/locate/person?name=Imran
res_imran_live = client.get('/api/locate/person?name=Imran')
ilive_data = res_imran_live.get_json() if res_imran_live.is_json else {}
im_live = ilive_data.get('results', [])[0]
print("Post-presence Imran status:", im_live.get('status_label'))
print("Room name:", im_live.get('room_name'))
print("Active status:", im_live.get('status'))

# 6. Re-check /api/locate/rooms to verify Main Office has occupant
res_rooms_live = client.get('/api/locate/rooms')
rooms_live = res_rooms_live.get_json().get('rooms', [])
main_office = next((r for r in rooms_live if 'Main Office' in r.get('room_name', '') or r.get('camera_id') == 'dvr'), None)
print("Main Office occupancy:", main_office.get('occupant_count') if main_office else "None", "occupants:", [o.get('name') for o in main_office.get('occupants', [])] if main_office else [])

# 7. Test record_locator_snapshot in database
print("\nTesting record_locator_snapshot in database...")
now_str = time.strftime("%Y-%m-%d %H:%M:%S")
snap_id = db.record_locator_snapshot(
    user_id=38,
    name="Imran Khalid",
    department="AI & Data Science",
    camera_id="dvr",
    camera_name="DVR",
    room_name="Main Office",
    confidence=0.92,
    first_seen=now_str,
    last_seen=now_str,
    interval_seconds=300
)
print("Snapshot recorded with ID:", snap_id)

# 8. Test GET /api/locate/history?user_id=38
res_hist = client.get('/api/locate/history?user_id=38')
print("History API Status:", res_hist.status_code)
hdata = res_hist.get_json() if res_hist.is_json else {}
hist_entries = hdata.get('history', [])
print(f"History entries returned for Imran: {len(hist_entries)}")
if hist_entries:
    print("Latest entry:", hist_entries[0])

# 9. Clean up live presence
with app.app_context():
    from app import presence_lock
    with presence_lock:
        LIVE_PRESENCE.pop(38, None)
print("Cleaned up LIVE_PRESENCE for user 38")
