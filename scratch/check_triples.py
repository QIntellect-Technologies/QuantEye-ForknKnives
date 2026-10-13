with open('d:/QIntellect-AI-Attendence-11-9-2026/Final-AI-Attendence-System/Final-AI-Attendence-System/Flask-Attedence/database.py', 'r', encoding='utf-8') as f:
    text = f.read()

count = 0
for i, line in enumerate(text.split('\n')):
    c = line.count("'''")
    if c > 0:
        count += c
        print(f"{i+1} (total: {count}): {line}")
