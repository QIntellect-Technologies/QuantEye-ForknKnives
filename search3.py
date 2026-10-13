with open(r'd:\QIntellect-AI-Attendence-11-9-2026\Final-AI-Attendence-System\Final-AI-Attendence-System\Flask-Attedence\templates\index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'mainReportThead' in line or 'mainMultiDayTable' in line:
        print(f"{i+1}: {line.strip()}")
