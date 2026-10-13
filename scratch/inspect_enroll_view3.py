with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = 72737 + 4800
print(html[idx:idx+2500])
