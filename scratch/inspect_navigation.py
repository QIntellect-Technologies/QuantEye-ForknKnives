import re

with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

print("--- SIDEBAR & TOP-LEVEL NAVIGATION ---")
for line_idx, line in enumerate(html.splitlines()):
    if any(k in line.lower() for k in ['nav-link', 'nav-item', 'switchview', 'showview', 'data-view', 'showtab']):
        if len(line.strip()) < 150:
            print(f"L{line_idx+1}: {line.strip()}")

print("\n--- VIEW CONTAINERS (-view or id='...-view') ---")
views = re.findall(r'id=["\']([a-zA-Z0-9_\-]+view)["\']', html)
print("Views found:", set(views))

print("\n--- SETTINGS SUB-TABS ---")
settings_tabs = re.findall(r'switchSettingsTab\(["\']([a-zA-Z0-9_\-]+)["\']', html)
print("Settings sub-tabs found:", set(settings_tabs))
