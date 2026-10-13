import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines, 1):
    if 'id="' in line and '-view' in line:
        print(f"Line {idx}: {line.strip()}")
