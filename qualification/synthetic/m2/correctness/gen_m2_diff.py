"""Differential case stream (percentile rank, median ratio, episode detection): at least 20,000 randomized cases each,
generated at run time from a seed; only this generator and the manifest hash are committed. Expected values here are
implementation A (sorted lists, state machine); m2_diff_check.py recomputes them with an independent implementation B.
Usage: python gen_m2_diff.py [--n 20000] [--seed S] [--out DIR] [--cases]   (--cases also writes the case lines)"""
import argparse
import hashlib
import json
import os
import random
from fractions import Fraction as Fr

LABEL = ("mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, "
         "Windows x64, CPython 3.12")


def fmt(x):
    x = Fr(x)
    return int(x) if x.denominator == 1 else "%d/%d" % (x.numerator, x.denominator)


def rank_case(rng):
    n = rng.choice([1, 2, 3, 5, 10, 19, 20, 21, 40])
    hi = rng.choice([1, 3, 9, 100])
    h = [rng.randrange(0, hi + 1) for _ in range(n)]
    x = rng.randrange(-1, hi + 2)
    s = sorted(h)
    le = sum(1 for v in s if v <= x)
    ge = sum(1 for v in s if v >= x)
    return {"h": h, "x": x}, {"n": n, "rank_le": fmt(Fr(le, n)), "upper_share": fmt(Fr(ge, n))}


def median_case(rng):
    n = rng.randrange(1, 31)
    hi = rng.choice([1, 5, 20])
    z = rng.random() < 0.3
    h = [0 if (z and rng.random() < 0.7) else rng.randrange(0, hi + 1) for _ in range(n)]
    x = rng.randrange(0, 31)
    s = sorted(h)
    med = Fr(s[n // 2]) if n % 2 else Fr(s[n // 2 - 1] + s[n // 2], 2)
    mean = Fr(sum(h), n)
    e = {"median": fmt(med), "mean": fmt(mean),
         "median_ratio": None if med == 0 else fmt(Fr(x) / med), "mean_ratio": None if mean == 0 else fmt(Fr(x) / mean)}
    return {"h": h, "x": x}, e


def episode_case(rng):
    n = rng.randrange(0, 60)
    pts = [None] * 15
    for _ in range(n):
        t = rng.random()
        if t < 0.15:
            pts.append(None)
        elif t < 0.2:
            pts.append([0, 0])
        else:
            pts.append([rng.randrange(0, 6) * 1000 + rng.randrange(0, 3), 15000])
    gap = rng.randrange(1, 7)
    N = rng.choice([2, 3, 5])
    eps, inep, quiet = 0, False, 0
    first = last = None
    peak = pk = None
    for k, p in enumerate(pts):
        r = None if (p is None or p[1] == 0) else Fr(15 * p[0], p[1])
        if r is not None and (peak is None or r > peak):
            peak, pk = r, k
        if r is not None and r >= N:
            if not inep:
                eps += 1
                inep = True
                first = k if first is None else first
                last = k
            quiet = 0
        elif inep:
            quiet += 1
            if quiet >= gap:
                inep = False
    return {"pts": pts, "gap": gap, "N": N}, {"episodes": eps, "first": first, "last": last,
                                               "peak": None if peak is None else fmt(peak), "peak_idx": pk}


KINDS = (("rank", rank_case), ("median_ratio", median_case), ("episodes", episode_case))


def cases(seed, n):
    for kind, fn in KINDS:
        rng = random.Random("%s:%s" % (seed, kind))
        for i in range(n):
            inp, exp = fn(rng)
            yield kind, i, inp, exp


def line(kind, i, inp, exp):
    return json.dumps({"kind": kind, "i": i, "in": inp, "exp": exp}, sort_keys=True, separators=(",", ":")) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=20261029)
    ap.add_argument("--out", default=".")
    ap.add_argument("--cases", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    hs = {k: hashlib.sha256() for k, _ in KINDS}
    counts = {k: 0 for k, _ in KINDS}
    f = open(os.path.join(a.out, "m2_diff_cases.jsonl"), "wb") if a.cases else None
    for kind, i, inp, exp in cases(a.seed, a.n):
        b = line(kind, i, inp, exp).encode("ascii")
        hs[kind].update(b)
        counts[kind] += 1
        if f:
            f.write(b)
    man = {"provenance": "SYNTHETIC", "label": LABEL, "seed": a.seed, "cases_per_kind": counts,
           "sha256_of_case_stream": {k: h.hexdigest() for k, h in hs.items()}}
    with open(os.path.join(a.out, "m2_diff_manifest.json"), "wb") as g:
        g.write((json.dumps(man, sort_keys=True, indent=1) + "\n").encode("ascii"))
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
