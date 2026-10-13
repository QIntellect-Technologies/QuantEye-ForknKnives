with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('function createEnrollUser')
print(html[idx+1200:idx+2500])
