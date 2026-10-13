import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

depth = 0
for idx, line in enumerate(lines, 1):
    op = line.count('<div')
    cl = line.count('</div>')
    
    if '<div' in line and 'class=' in line and 'main-panel' in line:
        print(f"MAIN PANEL OPENED at Line {idx} (Depth before: {depth})")
        
    if '<div' in line and 'id=' in line and '-view' in line:
        m = re.search(r'id="([^"]+)"', line) or re.search(r"id='([^']+)'", line)
        v_id = m.group(1) if m else line.strip()
        print(f"VIEW OPENED: {v_id} at Line {idx} (Depth before: {depth}, after: {depth + op - cl})")
        
    depth += op - cl

print(f"Total Depth at end: {depth}")
