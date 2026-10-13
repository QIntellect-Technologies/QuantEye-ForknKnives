with open('app.py', encoding='utf-8') as f:
    app_text = f.read()

import re
print("Attendance routes in app.py:")
for m in re.finditer(r'@app\.route\([\'"]([^\'"]*attendance[^\'"]*)[\'"].*?\)\s+def\s+([a-zA-Z0-9_]+)', app_text):
    print(f"  {m.group(1)} -> {m.group(2)}")

with open('database.py', encoding='utf-8') as f:
    db_text = f.read()

print("\nAttendance functions in database.py:")
for m in re.finditer(r'def\s+([a-zA-Z0-9_]*attendance[a-zA-Z0-9_]*)\s*\(', db_text):
    print(f"  {m.group(1)}")
