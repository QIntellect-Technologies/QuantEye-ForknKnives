with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

import re
matches = [m.start() for m in re.finditer(r'API_BASE', html)]
for m in matches[:5]:
    print(html[m-20:m+60])
