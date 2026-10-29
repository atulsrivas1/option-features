import json, sys
sys.path.insert(0, ".")
from oracle import check
rows = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "m1_iv_extra_cases.json"))["rows"]
bad = 0
nv = 0
for r in rows:
    b, n = check(r)
    nv += n
    for m in b:
        print(r["id"], m)
    bad += len(b)
print("rows", len(rows), "oracle numeric values", nv, "disagreements", bad)
