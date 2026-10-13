import sys
sys.path.insert(0, ".")
from app import app

client = app.test_client()
res = client.get('/api/reports/export/excel?start_date=2026-10-01&end_date=2026-10-07')
print("Status code:", res.status_code)
print("Content-Type:", res.content_type)
print("Payload length:", len(res.data), "bytes")
