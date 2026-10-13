import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

print('=== VIEW CONTAINERS in index.html ===')
for m in re.finditer(r'<div[^>]*id="([^"]*-view)"[^>]*>', text):
    print(m.group(0))

print('\n=== switchTab function ===')
idx = text.find('function switchTab(')
if idx != -1:
    print(text[idx:idx+800])
