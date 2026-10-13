with open(r'd:\QIntellect-AI-Attendence-11-9-2026\Final-AI-Attendence-System\Final-AI-Attendence-System\Flask-Attedence\templates\index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'payrollReviewTableBody' in line or 'table-responsive' in line and 'id="payrollReview' in line or 'payrollReviewTable' in line:
        print(f"{i+1}: {line.strip()}")
