import sys
sys.path.insert(0, ".")
import inspect
import database as db

print("--- LOCATOR FUNCTIONS IN DATABASE.PY ---")
db_funcs = [name for name in dir(db) if any(k in name.lower() for k in ['locat', 'room', 'presence'])]
for f in db_funcs:
    print(f)

with open('app.py', encoding='utf-8', errors='ignore') as fp:
    lines = fp.readlines()

print("\n--- LOCATOR ENDPOINTS IN APP.PY ---")
for i, l in enumerate(lines):
    if '/api/locate' in l:
        print(f"L{i+1}: {l.strip()}")
        # print next 20 lines
        for j in range(i+1, min(i+25, len(lines))):
            print(f"   {lines[j].strip()[:90]}")
        print("="*60)
