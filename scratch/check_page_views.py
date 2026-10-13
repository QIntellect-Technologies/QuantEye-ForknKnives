with open('templates/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

depth = 0
views = []

for idx, line in enumerate(lines, 1):
    open_count = line.count('<div')
    close_count = line.count('</div>')
    
    if 'id="' in line and '-view' in line and '<div' in line:
        match = line.strip()
        views.append((idx, depth + open_count, match))
        
    depth += open_count - close_count

print(f"Final Depth at end of file: {depth}")
for idx, d, name in views:
    print(f"Line {idx} (Depth {d}): {name}")
