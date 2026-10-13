import re

for fname in ['database.py', 'app.py']:
    print(f"=== {fname} matches for 'overtime' ===")
    with open(fname, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f):
            if 'overtime' in line.lower():
                print(f"{idx+1}: {line.strip()[:100]}")
