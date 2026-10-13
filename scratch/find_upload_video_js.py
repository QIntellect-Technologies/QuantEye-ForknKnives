with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('function uploadEnrollmentVideo')
if idx != -1:
    print("=== FUNCTION uploadEnrollmentVideo ===")
    print(html[idx:idx+1500])
else:
    print("function uploadEnrollmentVideo NOT FOUND!")
    # search where uploadEnrollmentVideo is called
    import re
    matches = [m.start() for m in re.finditer(r'uploadEnrollmentVideo', html)]
    for m in matches:
        print(html[m-50:m+200])
