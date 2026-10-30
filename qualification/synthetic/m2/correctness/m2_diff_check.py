"""Second implementation for the differential stream: recomputes rank, median ratio and episodes from the raw case inputs
with different algorithms (loops, partial selection, run extraction) and compares with the stream expectations and the
committed manifest hash. Usage: python m2_diff_check.py [manifest.json] [--n 20000]"""
import hashlib
import heapq
import json
import sys
from fractions import Fraction

import gen_m2_diff as G


def shown(x):
    x = Fraction(x)
    return int(x) if x.denominator == 1 else str(x.numerator) + "/" + str(x.denominator)


def rank_b(c):
    h, x = c["h"], c["x"]
    n = len(h)
    le = ge = 0
    for v in h:
        if v <= x:
            le += 1
        if x <= v:
            ge += 1
    return {"n": n, "rank_le": shown(Fraction(le, n)), "upper_share": shown(Fraction(ge, n))}


def median_b(c):
    h, x = c["h"], c["x"]
    n = len(h)
    k = n // 2 + 1
    low = heapq.nsmallest(k, h)           # partial selection instead of a full sort
    med = Fraction(low[-1]) if n % 2 else Fraction(low[-1] + low[-2], 2)
    mean = Fraction(sum(h), n)
    return {"median": shown(med), "mean": shown(mean),
            "median_ratio": None if med == 0 else shown(Fraction(x) / med),
            "mean_ratio": None if mean == 0 else shown(Fraction(x) / mean)}


def episodes_b(c):
    pts, gap, N = c["pts"], c["gap"], c["N"]
    ratio = []
    for p in pts:
        ratio.append(None if (p is None or p[1] == 0) else Fraction(15 * p[0], p[1]))
    fired = [k for k, r in enumerate(ratio) if r is not None and r >= N]
    starts = []
    prev = None
    for k in fired:
        if prev is None or (k - prev - 1) >= gap:
            starts.append(k)
        prev = k
    best = None
    for k, r in enumerate(ratio):
        if r is not None and (best is None or r > best[0]):
            best = (r, k)
    return {"episodes": len(starts), "first": starts[0] if starts else None, "last": starts[-1] if starts else None,
            "peak": None if best is None else shown(best[0]), "peak_idx": None if best is None else best[1]}


IMPL = {"rank": rank_b, "median_ratio": median_b, "episodes": episodes_b}


def main():
    man_path = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else None
    n = 20000
    if "--n" in sys.argv:
        n = int(sys.argv[sys.argv.index("--n") + 1])
    seed = 20261029
    man = None
    if man_path:
        man = json.load(open(man_path))
        seed = man["seed"]
    hs = {k: hashlib.sha256() for k in IMPL}
    counts = {k: 0 for k in IMPL}
    diffs = 0
    for kind, i, inp, exp in G.cases(seed, n):
        counts[kind] += 1
        hs[kind].update(G.line(kind, i, inp, exp).encode("ascii"))
        got = IMPL[kind](inp)
        if got != exp:
            diffs += 1
            if diffs <= 5:
                print("DIFF", kind, i, inp, exp, got)
    ok = diffs == 0 and all(v >= 20000 for v in counts.values())
    if man is not None:
        ok = ok and man["sha256_of_case_stream"] == {k: h.hexdigest() for k, h in hs.items()}
    print("cases", counts, "differences", diffs, "DIFFCHECK", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
