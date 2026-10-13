with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('/locate/history')
if idx != -1:
    print(html[idx-100:idx+1500])
else:
    print("/locate/history not found in index.html")
