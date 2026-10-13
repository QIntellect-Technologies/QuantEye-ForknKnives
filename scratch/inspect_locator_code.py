with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

pos = 363652
print(html[pos-100:pos+1500])
