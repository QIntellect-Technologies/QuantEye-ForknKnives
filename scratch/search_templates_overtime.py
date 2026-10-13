import os
import re

for root, dirs, files in os.walk('templates'):
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            with open(filepath, encoding='utf-8', errors='ignore') as f:
                c = f.read()
            matches = re.findall(r'overtime', c, re.IGNORECASE)
            api_matches = re.findall(r'/api/overtime', c)
            if matches:
                print(f"{filepath}: {len(matches)} overtime matches, {len(api_matches)} /api/overtime matches")
