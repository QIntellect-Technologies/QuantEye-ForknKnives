with open('templates/index.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

import re
matches = [m.start() for m in re.finditer(r'id=["\'][^"\']*leave[^"\']*modal[^"\']*["\']', html, re.I)]
if not matches:
    matches = [m.start() for m in re.finditer(r'submitLeaveRequest|addLeaveRequest|saveLeaveRequest', html, re.I)]

for idx in matches:
    print('--- MATCH ---')
    print(html[idx-100:idx+1200])
