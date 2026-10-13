with open('templates/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re

views = [
    'dashboard-view',
    'enroll-view',
    'live-view',
    'multi-view',
    'camera-detect-view',
    'verify-view',
    'locator-view',
    'reports-view',
    'payroll-view',
    'leaves-view',
    'shifts-view',
    'staff-view',
    'settings-view',
]

for v in views:
    idx = text.find(f'id="{v}"')
    if idx != -1:
        # find closing or preview
        snippet = text[idx:idx+300].replace('\n', ' ')
        print(f"[{v}]: (found at char {idx}) -> {snippet[:120]}")
    else:
        print(f"[{v}]: NOT FOUND")
