with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

import re
matches = [m.start() for m in re.finditer(r'enable-enrollment', html)]
print("References to enable-enrollment:", matches)
for m in matches:
    print(html[m-50:m+250])

matches2 = [m.start() for m in re.finditer(r'verify-password', html)]
print("References to verify-password:", matches2)
for m in matches2:
    print(html[m-50:m+250])
