with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('function onEnrollDeptChange')
if idx != -1:
    print("=== FUNCTION onEnrollDeptChange ===")
    print(html[idx:idx+1000])
else:
    print("function onEnrollDeptChange NOT FOUND!")
    import re
    matches = [m.start() for m in re.finditer(r'onEnrollDeptChange', html)]
    for m in matches:
        print(html[m-50:m+200])
