import json
import glob
import os

keywords = ['payroll v2', 'overtime', 'next module', 'implementation plan', 'project scope', 'module by module']

logs = glob.glob(r'C:\Users\Fafcom Technology\.gemini\antigravity-ide\brain\*\.system_generated\logs\transcript.jsonl')
print(f"Found {len(logs)} transcript files")

for log in logs:
    cid = log.split(os.sep)[-4]
    with open(log, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                content = str(data.get('content', ''))
                for kw in keywords:
                    if kw in content.lower():
                        # print match snippet
                        idx = content.lower().find(kw)
                        snippet = content[max(0, idx-60):min(len(content), idx+100)].replace('\n', ' ')
                        print(f"[{cid} | Step {data.get('step_index')} | {data.get('type')}] ...{snippet}...")
                        break
            except Exception:
                pass
