with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

pos = 366773
print(html[pos:pos+1600])
