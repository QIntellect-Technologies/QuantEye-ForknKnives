import json
with open('scratch/audit_results.json') as f:
    res = json.load(f)
passed = sum(1 for r in res if r['status'] == 'PASS')
failed = sum(1 for r in res if r['status'] != 'PASS')
print(f"TOTAL: {len(res)} | PASSED: {passed} | FAILED: {failed}")
for r in res:
    if r['status'] != 'PASS':
        print("FAILED:", r)
