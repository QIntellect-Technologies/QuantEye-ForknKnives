import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('database.py', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'def get_detailed_attendance_report' in l:
        print(''.join(lines[i+240:i+320]))
        break
