with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('recognitionMessage')
if idx != -1:
    print("Found recognitionMessage around:")
    print(html[idx-100:idx+600])

import re
matches = [m.start() for m in re.finditer(r'/api/recognize/frame', html)]
print("References to /api/recognize/frame:", matches)
for m in matches:
    print(html[m-50:m+200])
