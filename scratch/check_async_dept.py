with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

idx = html.find('onEnrollDeptChange(deptName)')
print(html[idx-30:idx+400])
