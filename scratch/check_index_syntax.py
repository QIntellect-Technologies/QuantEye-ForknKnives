with open('templates/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Check important IDs exist
required_ids = [
    'salary-config-tab',
    'salaryConfigNavBtn',
    'manageSalaryPackagesButton',
    'editSalaryConfigModal',
    'autoOtRateModal',
    'salaryTotalStaff',
    'salaryTotalBase',
    'salaryTotalAllowances',
    'salaryTotalNet',
    'salarySearchInput',
    'salaryDeptFilter',
    'salaryStatusFilter',
    'salaryConfigTable',
    'salaryConfigTableBody',
    'modalSalaryBasic',
    'modalSalaryAllowances',
    'modalSalaryDeductions',
    'modalSalaryOtRate',
    'modalPreviewNet',
    'saveSalaryBtn'
]

missing = []
for req in required_ids:
    if f'id="{req}"' not in text and f"id='{req}'" not in text:
        missing.append(req)

print("Missing IDs:", missing)

# Check script closing
if text.count('<script>') != text.count('</script>'):
    print(f"Mismatch in script tags: {text.count('<script>')} vs {text.count('</script>')}")
else:
    print("Script tags matched:", text.count('<script>'))

print("Total index.html lines:", len(text.splitlines()))
