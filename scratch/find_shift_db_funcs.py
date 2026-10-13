import re

with open('database.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("SHIFT FUNCTIONS IN database.py:")
for i, l in enumerate(lines):
    if re.search(r'def\s+.*shift', l, re.IGNORECASE):
        print(f"  Line {i+1:4d}: {l.strip()}")
