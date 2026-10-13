with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('id="locator-view"')
if idx != -1:
    print("=== LOCATOR VIEW HTML (2000 chars) ===")
    print(html[idx:idx+2000])

import re
print("\n=== LOCATOR JS FUNCTIONS ===")
for fn in ['locateStaffMember', 'loadRoomsOccupancy', 'scanAllCamerasLiveNow', 'loadLocationHistory', 'renderRoomsGrid', 'renderLocatorResults']:
    matches = [m.start() for m in re.finditer(rf'function\s+{fn}', html)]
    if matches:
        print(f"Function {fn} found at {matches[0]}")
        print(html[matches[0]:matches[0]+350])
    else:
        print(f"Function {fn} NOT FOUND")
