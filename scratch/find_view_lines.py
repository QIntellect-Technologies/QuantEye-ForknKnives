with open('templates/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

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

for idx, line in enumerate(lines):
    for v in views:
        if f'id="{v}"' in line:
            print(f"Line {idx+1}: id='{v}' -> {line.strip()[:80]}")
