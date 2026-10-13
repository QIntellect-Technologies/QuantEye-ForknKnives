with open('app.py', encoding='utf-8', errors='ignore') as f:
    text = f.read()

import re
matches = [m.start() for m in re.finditer(r'/api/enroll', text)]
for m in matches:
    print("--------------------------------------------------")
    print(text[m-20:m+500])
