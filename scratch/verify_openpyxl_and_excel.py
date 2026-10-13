import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")

import openpyxl
print(f"openpyxl version: {openpyxl.__version__}")

from app import app
import io

client = app.test_client()

print("\nCalling GET /api/reports/export/excel?start_date=2026-10-01&end_date=2026-10-07...")
res = client.get('/api/reports/export/excel?start_date=2026-10-01&end_date=2026-10-07')

print(f"HTTP Status: {res.status_code}")
print(f"Content-Type: {res.content_type}")
print(f"Data Length: {len(res.data)} bytes")

if res.status_code == 200:
    excel_file = io.BytesIO(res.data)
    wb = openpyxl.load_workbook(excel_file)
    print(f"Workbook sheet names: {wb.sheetnames}")
    sheet = wb.active
    print(f"Active Sheet title: {sheet.title}")
    print(f"Dimensions: {sheet.dimensions} (Max row: {sheet.max_row}, Max column: {sheet.max_column})")
    
    print("\nFirst 10 rows preview:")
    for r in range(1, min(12, sheet.max_row + 1)):
        row_vals = [sheet.cell(r, c).value for c in range(1, min(10, sheet.max_column + 1))]
        print(f"  Row {r}: {row_vals}")

    print("\nEXCEL EXPORT VERIFICATION: SUCCESS!")
else:
    print(f"FAILED with response: {res.data}")
