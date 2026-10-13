with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('function createEnrollUser')
if idx != -1:
    print(html[idx:idx+1500])
else:
    print("function createEnrollUser NOT found")
