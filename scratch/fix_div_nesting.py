with open('templates/index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

d = 0
for idx in range(2001, 2538): # line 2002 to 2538
    line = lines[idx]
    op = line.count('<div')
    cl = line.count('</div>')
    d += op - cl
    print(f"Line {idx+1} (change +{op - cl}, current {d}): {line.strip()[:60]}")

print(f"\nFinal Depth of enroll-view at line 2538: {d}")
