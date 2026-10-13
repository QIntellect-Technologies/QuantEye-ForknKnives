with open('app.py', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if 'export' in l.lower() and '@app.route' in l.lower():
        print(f"Line {i+1}: {l.strip()}")
        print(''.join(lines[i:i+20]))
        print('-'*50)
