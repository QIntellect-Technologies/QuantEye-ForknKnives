import sys
sys.path.insert(0, ".")
import app
print('Keys in EMBEDDING_CACHE:', len(app.EMBEDDING_CACHE), list(app.EMBEDDING_CACHE.keys())[:10])
print('38 in EMBEDDING_CACHE:', 38 in app.EMBEDDING_CACHE)
if 38 in app.EMBEDDING_CACHE:
    print('38 data:', app.EMBEDDING_CACHE[38].keys())
else:
    print('Calling refresh_embedding_cache...')
    app.refresh_embedding_cache()
    print('After refresh: len:', len(app.EMBEDDING_CACHE), '38 in cache:', 38 in app.EMBEDDING_CACHE)

res = app.app.test_client().post('/api/locate/scan-now', json={'user_id': 38})
print('Scan status with user_id=38:', res.status_code, res.get_json())
