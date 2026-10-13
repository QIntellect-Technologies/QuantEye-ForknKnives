import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    content = f.read()

ids_to_check = [
    'reports-view', 'staff-view', 'shifts-view', 'enroll-view', 'live-view', 'multi-view', 'locator-view',
    'tabStaffTableBody', 'tabStatTotalStaff', 'tabStatDepts', 'tabStatPayroll', 'tabStaffDeptFilter',
    'mainReportTbody', 'mainStatRegistered', 'mainStatPresent', 'mainStatAbsent', 'mainDeptGrid',
    'shiftsCardsGrid', 'shiftsTableBody', 'shiftsCountBadge'
]

for elem_id in ids_to_check:
    found = f'id="{elem_id}"' in content or f"id='{elem_id}'" in content
    print(f"{elem_id}: {'[OK] Found' if found else '[MISSING] NOT FOUND'}")
