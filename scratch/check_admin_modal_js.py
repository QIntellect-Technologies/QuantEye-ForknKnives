with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

import re

# find adminPasswordModal
idx1 = html.find('id="adminPasswordModal"')
if idx1 != -1:
    print("=== ADMIN PASSWORD MODAL ===")
    print(html[idx1:idx1+1000])

# find functions related to admin password
for fn in ['checkAdminPassword', 'openAdminPasswordModal', 'toggleEnrollmentAccess', 'checkEnrollmentEnabled']:
    matches = [m.start() for m in re.finditer(rf'function\s+{fn}', html)]
    for m in matches:
        print(f"\n=== FUNCTION {fn} ===")
        print(html[m:m+500])
