import re

with open('database.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("REFERENCES TO employee_shift_history IN database.py:")
for i, l in enumerate(lines):
    if 'employee_shift_history' in l:
        print(f"  Line {i+1:4d}: {l.strip()}")
