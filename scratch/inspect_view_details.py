with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

def show_section(title, start_str, length=1500):
    idx = html.find(start_str)
    if idx != -1:
        print(f"\n==================== {title} ====================")
        print(html[idx:idx+length])
    else:
        print(f"\nNOT FOUND: {title}")

show_section("LOCATOR VIEW", 'id="locator-view"', 1000)
show_section("VERIFY VIEW", 'id="verify-view"', 1000)
show_section("CAMERA DETECT VIEW", 'id="camera-detect-view"', 1000)
show_section("MULTI VIEW", 'id="multi-view"', 1000)
