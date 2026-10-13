with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

import re
matches = [m.start() for m in re.finditer(r'/locate/', html)]
print("References to /locate/ in index.html:")
for m in matches:
    print(html[m-50:m+100])
