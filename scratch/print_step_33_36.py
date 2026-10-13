import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

path = r'C:\Users\Fafcom Technology\.gemini\antigravity-ide\brain\ef92d91d-6c61-4da8-9c2e-03929feb0a46\.system_generated\logs\transcript.jsonl'
with open(path, 'r', encoding='utf-8') as f:
    for line in f:
        d = json.loads(line)
        if d.get('step_index') in [33, 36]:
            print(f"=== STEP {d.get('step_index')} ===")
            print(d.get('content', '')[:2500])
