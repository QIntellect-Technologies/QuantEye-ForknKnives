with open('templates/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

import re
# Find navigation links/items
print("=== Nav/Sidebar links ===")
for match in re.finditer(r'<a\s+[^>]*class="[^"]*(?:nav-link|sidebar|menu)[^"]*"[^>]*>(.*?)</a>', text, re.IGNORECASE | re.DOTALL):
    clean = re.sub(r'<[^>]+>', ' ', match.group(0))
    print(' '.join(clean.split()))

print("\n=== All tab buttons / onclicks ===")
for match in re.finditer(r'<button\s+[^>]*onclick="([^"]*)"[^>]*>(.*?)</button>', text, re.IGNORECASE | re.DOTALL):
    clean = re.sub(r'<[^>]+>', ' ', match.group(2))
    fn = match.group(1)
    if any(k in fn.lower() for k in ['tab', 'section', 'nav', 'page', 'show']):
        print(f"fn: {fn} -> {' '.join(clean.split())}")

print("\n=== Main Section / Content IDs ===")
for match in re.finditer(r'<div\s+[^>]*id="([a-zA-Z0-9_\-]+Section|[a-zA-Z0-9_\-]+Tab|[a-zA-Z0-9_\-]+Content|[a-zA-Z0-9_\-]+Pane)"[^>]*>', text, re.IGNORECASE):
    print(match.group(0))
