with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

import re
print("--- JAVASCRIPT FUNCTIONS FOR CANDIDATE VIEWS ---")
for fn in ['loadRoomsOccupancy', 'scanAllCamerasLiveNow', 'verifyFace', 'testRecognition', 'enrollUser', 'submitEnrollment', 'loadMultiCameras']:
    matches = [m.start() for m in re.finditer(rf'function\s+{fn}', html)]
    if matches:
        print(f"Function {fn} found at positions: {matches}")
        for pos in matches:
            print(html[pos:pos+400])
    else:
        print(f"Function {fn} NOT found")
