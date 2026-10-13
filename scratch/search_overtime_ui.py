import re

with open('templates/index.html', encoding='utf-8') as f:
    c = f.read()

print('Matches for overtime in index.html:', len(re.findall(r'overtime', c, re.IGNORECASE)))
for m in re.finditer(r'(?:id|class|data-[a-z]+)=["\'][^"\']*overtime[^"\']*["\']', c, re.IGNORECASE):
    print('  UI match:', m.group(0))

for m in re.finditer(r'function\s+([a-zA-Z0-9_]*overtime[a-zA-Z0-9_]*)\s*\(', c, re.IGNORECASE):
    print('  JS func:', m.group(1))

for m in re.finditer(r'([a-zA-Z0-9_]*overtime[a-zA-Z0-9_]*)\s*[:=]\s*function', c, re.IGNORECASE):
    print('  JS func var:', m.group(1))

# Check occurrences of /api/overtime in index.html
print('\nOccurrences of /api/overtime in index.html:', len(re.findall(r'/api/overtime', c)))
for m in re.finditer(r'.{0,50}/api/overtime.{0,50}', c):
    print('  Context:', m.group(0).strip())

# Also check for ot_rate in index.html
print('\nOccurrences of ot_rate in index.html:', len(re.findall(r'ot_rate', c, re.IGNORECASE)))
for m in re.finditer(r'.{0,40}ot_rate.{0,40}', c, re.IGNORECASE):
    print('  ot_rate context:', m.group(0).strip())
