with open(r'd:\QIntellect-AI-Attendence-11-9-2026\Final-AI-Attendence-System\Final-AI-Attendence-System\Flask-Attedence\templates\index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'Payable Days' in line or 'Paid Leave' in line or 'Approved' in line or 'Approved Leave' in line:
        print(f"{i+1}: {line.strip()}")
