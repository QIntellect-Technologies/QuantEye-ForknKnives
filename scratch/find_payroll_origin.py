import json

for cid in ['c4b0e78a-6024-4335-b8c2-5bab75616d90', 'ef92d91d-6c61-4da8-9c2e-03929feb0a46']:
    path = rf'C:\Users\Fafcom Technology\.gemini\antigravity-ide\brain\{cid}\.system_generated\logs\transcript.jsonl'
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            d = json.loads(line)
            if d.get('type') == 'USER_INPUT' and 'payroll' in d.get('content', '').lower():
                s = d.get('content', '').replace('\n', ' ')
                print(f"[{cid} Step {d.get('step_index')}] {s[:160]}...")
