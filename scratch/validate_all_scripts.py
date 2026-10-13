import re
import subprocess
import os

with open('templates/index.html', encoding='utf-8', errors='ignore') as f:
    html = f.read()

# extract all <script> blocks that are javascript
scripts = re.findall(r'<script(?:\s+[^>]*)?>(.*?)</script>', html, re.DOTALL)
print(f"Found {len(scripts)} script blocks.")

for i, s in enumerate(scripts):
    s_clean = s.strip()
    if not s_clean:
        continue
    # write to temp js file
    temp_js = f"scratch/temp_test_script_{i}.js"
    with open(temp_js, 'w', encoding='utf-8') as tf:
        tf.write(s_clean)
    
    res = subprocess.run(['node', '--check', temp_js], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FAILED on script #{i}:")
        print(res.stderr[:500])
    else:
        print(f"Script #{i} syntax valid ({len(s_clean)} bytes)")
    
    if os.path.exists(temp_js):
        os.remove(temp_js)
