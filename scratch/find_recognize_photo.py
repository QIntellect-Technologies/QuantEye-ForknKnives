with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('function recognizePhoto')
if idx != -1:
    print(html[idx:idx+1200])
else:
    print("function recognizePhoto NOT found!")
    # search where recognizePhoto is mentioned
    import re
    matches = [m.start() for m in re.finditer(r'recognizePhoto', html)]
    for m in matches:
        print(html[m-50:m+200])
