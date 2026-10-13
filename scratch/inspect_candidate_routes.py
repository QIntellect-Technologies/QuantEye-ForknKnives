import sys
sys.path.insert(0, ".")
import inspect
import app

print("--- RELEVANT ROUTES IN APP.PY ---")
for rule in app.app.url_map.iter_rules():
    r = rule.rule
    if any(k in r for k in ['enroll', 'verify', 'locator', 'face', 'upload', 'stream', 'multi', 'payslip', 'export']):
        print(f"{list(rule.methods)}: {r}")
