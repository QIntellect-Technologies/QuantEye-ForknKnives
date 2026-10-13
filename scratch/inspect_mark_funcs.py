import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('database.py', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if any(fn in l for fn in ['def mark_user_present_today', 'def mark_user_absent_today', 'def log_attendance']):
        print(f"Line {i+1}:")
        print(''.join(lines[i:i+40]))
        print('-'*50)
