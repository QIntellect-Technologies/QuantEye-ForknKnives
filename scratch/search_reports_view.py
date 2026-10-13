with open('templates/index.html', 'r', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('id="reports-view"')
if idx != -1:
    print(html[idx:idx+2500])
else:
    print("Not found")
