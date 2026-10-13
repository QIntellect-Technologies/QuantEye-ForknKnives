import re

with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

views = ['live-view', 'multi-view', 'verify-view', 'payroll-view', 'staff-view', 'locator-view', 'settings-view', 'enroll-view', 'camera-detect-view', 'shifts-view', 'reports-view', 'dashboard-view', 'leaves-view']

for v in views:
    idx = html.find(f'id="{v}"')
    if idx == -1:
        idx = html.find(f"id='{v}'")
    if idx != -1:
        snippet = html[idx:idx+400]
        # find closing tag or length
        print(f"\n==================== VIEW: {v} (at pos {idx}) ====================")
        print(snippet[:350])
    else:
        print(f"\nVIEW NOT FOUND: {v}")
