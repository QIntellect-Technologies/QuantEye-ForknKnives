with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = 72737 + 2400
print(html[idx:idx+2500])
