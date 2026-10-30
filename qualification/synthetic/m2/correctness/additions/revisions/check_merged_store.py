import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import m2_load, m2add_store_a as SA, m2common as C
head, rows = m2_load.load_dataset(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'm2_cases_store.json'))
bad = []
for r in rows:
    res, _ = SA.store(r['inputs'], r['params'], C.invalid, lambda **kw: C.res(**kw))
    e = r['expected']
    same = res['status'] == e['status'] and res['code'] == e['code'] and res['value'] == e['value']
    if not same:
        bad.append((r['id'], res['status'], res['code'], e['code']))
print('merged store rows', len(rows), 'differences under the new canonical rules', len(bad), bad[:10])
