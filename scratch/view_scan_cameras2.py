with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

pos = 363652 + 1400
print(html[pos:pos+1500])
