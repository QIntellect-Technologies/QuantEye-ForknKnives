with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('function uploadEnrollmentVideo')
print(html[idx+1300:idx+2500])
