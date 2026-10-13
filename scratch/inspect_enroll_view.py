with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('id="enroll-view"')
if idx != -1:
    print("Found enroll-view at", idx)
    print(html[idx:idx+2500])
