with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

import re
matches = [m.start() for m in re.finditer(r'adminPasswordModal', html)]
for m in matches:
    print("---------------------------------------")
    print(html[m-50:m+300])
