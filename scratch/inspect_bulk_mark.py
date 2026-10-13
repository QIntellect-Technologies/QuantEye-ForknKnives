with open('app.py', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'def api_bulk_mark_attendance' in l or 'def api_mark_absent' in l:
        print(f"Line {i+1}:")
        print(''.join(lines[i-1:i+35]))
        print('-'*50)
