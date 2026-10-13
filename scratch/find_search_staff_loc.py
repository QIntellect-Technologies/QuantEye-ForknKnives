with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('function searchStaffLocation')
if idx != -1:
    print(html[idx:idx+2500])
else:
    print("function searchStaffLocation NOT FOUND!")
    import re
    matches = [m.start() for m in re.finditer(r'searchStaffLocation', html)]
    for m in matches:
        print(html[m-50:m+200])
