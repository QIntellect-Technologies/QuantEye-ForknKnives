import sys
sys.path.insert(0, '.')
import app

print("TOTAL ROUTES IN APP.PY:", len(list(app.app.url_map.iter_rules())))
for r in sorted([rule.rule for rule in app.app.url_map.iter_rules()]):
    print(r)
