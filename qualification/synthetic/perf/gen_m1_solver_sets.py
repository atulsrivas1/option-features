#!/usr/bin/env python3
"""SYNTHETIC M1 solver contract sets: 10k flat-vol + 10k mixed-surface.

Provenance: SYNTHETIC. Tester-authored from PO_BRAINSTORM_TOP2_RULINGS Part B only.
Stdlib only, seeded, deterministic, LF, no absolute paths.
Inputs only: the reference result is the CURRENT solver output captured by the
Tester at run time (never authored here). Prices are Black-Scholes (European,
float math) rounded to 4 decimal places, so a few contracts are intentionally
unsolvable (price at or below intrinsic) and must give a closed reason.
Residual risk: libm differences could move a rounded price by one tick on
another platform; the manifest digest is recorded for the generating machine.

Usage: python gen_m1_solver_sets.py --out DIR [--seed N]
"""
import argparse
import hashlib
import json
import math
import os

from gen_perf_workloads import SM64, sub, dec, TICK

PROVENANCE = "SYNTHETIC"
QUAL = "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12"
DEFAULT_SEED = 20261029
SET_SIZE = 10_000
SAMPLE_N = 20
EXTREME_FRACTION_PCT = 10   # of mixed-surface contracts get extreme vol
CLASSES = ["deep_itm", "deep_otm", "atm", "short_expiry", "extreme_vol", "long_expiry", "ordinary"]


def _ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs_price(S, K, T, r, q, sig, right):
    if T <= 0 or sig <= 0:
        return max(0.0, (S - K) if right == "C" else (K - S))
    sd = sig * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sig * sig) * T) / sd
    d2 = d1 - sd
    df, dq = math.exp(-r * T), math.exp(-q * T)
    if right == "C":
        return S * dq * _ncdf(d1) - K * df * _ncdf(d2)
    return K * df * _ncdf(-d2) - S * dq * _ncdf(-d1)


def _r4(x):
    return int(round(x * TICK))


def contract(seed, kind, i):
    """Contract i of set 'flat' or 'mixed'. Pure function of (seed, kind, i)."""
    g = SM64(sub(seed, "m1set", kind, i))
    S = 100.0
    right = "CP"[g.below(2)]
    r = (g.below(501)) / 10000.0          # 0 .. 5 percent
    q = (g.below(301)) / 10000.0          # 0 .. 3 percent
    cls = "ordinary"
    if kind == "flat":
        mny = 0.8 + 0.4 * g.uni()
        T = (14 + g.below(351)) / 365.0
        sig = 0.10 + 0.50 * g.uni()
        sig = round(sig, 4)               # stated flat sigma, known by construction
        cls = "atm" if abs(mny - 1.0) < 0.03 else "ordinary"
    else:
        pick = g.below(100)
        if pick < EXTREME_FRACTION_PCT:
            cls = "extreme_vol"
            mny = 0.7 + 0.6 * g.uni()
            T = (7 + g.below(300)) / 365.0
            sig = round((0.01 + 0.04 * g.uni()) if g.below(2) == 0 else (2.0 + 3.0 * g.uni()), 4)
        elif pick < 30:
            cls = "deep_itm" if g.below(2) == 0 else "deep_otm"
            mny = (0.3 + 0.4 * g.uni()) if (cls == "deep_itm") == (right == "P") else (1.4 + 1.6 * g.uni())
            T = (14 + g.below(351)) / 365.0
            sig = round(0.10 + 0.50 * g.uni(), 4)
        elif pick < 55:
            cls = "short_expiry"
            mny = 0.85 + 0.3 * g.uni()
            T = (1 + g.below(7)) / 365.0
            sig = round(0.10 + 0.60 * g.uni(), 4)
        elif pick < 65:
            cls = "long_expiry"
            mny = 0.7 + 0.6 * g.uni()
            T = (400 + g.below(700)) / 365.0
            sig = round(0.10 + 0.50 * g.uni(), 4)
        else:
            mny = 0.75 + 0.5 * g.uni()
            T = (7 + g.below(358)) / 365.0
            sig = round(0.10 + 0.40 * g.uni(), 4)
        # smile and term effect on the stated vol (parameterised surface)
        sig = round(max(0.005, sig * (1.0 + 0.5 * (mny - 1.0) ** 2 * 4 + 0.1 / math.sqrt(T * 365.0 / 30.0))), 4)
    K = round(S / mny, 2)
    t_days = int(round(T * 365.0))
    return {"i": i, "set": kind, "class": cls, "spot": dec(_r4(S)), "strike": dec(_r4(K)),
            "t_days": t_days, "t_years_exact": "%d/365" % t_days, "rate": dec(_r4(r)), "div": dec(_r4(q)),
            "right": right, "style": "european", "price": dec(_r4(bs_price(S, K, t_days / 365.0, r, q, sig, right))),
            "stated_sigma": dec(_r4(sig))}


def canon(rec):
    return json.dumps(rec, sort_keys=True, separators=(",", ":"))


def set_digest(seed, kind, n=SET_SIZE):
    h = hashlib.sha256()
    for i in range(n):
        h.update(canon(contract(seed, kind, i)).encode() + b"\n")
    return h.hexdigest()


def class_counts(seed, kind, n=SET_SIZE):
    c = {}
    for i in range(n):
        k = contract(seed, kind, i)["class"]
        c[k] = c.get(k, 0) + 1
    return dict(sorted(c.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    s = a.seed
    man = {"provenance": PROVENANCE, "qualification_label": QUAL, "label": "synthetic workload, relative engineering budget",
           "generator": "gen_m1_solver_sets.py", "seed": s, "schema_version": 1,
           "set_size": SET_SIZE, "unit_key": "set:i (zero-padded index)",
           "reference_result": "CURRENT solver output captured by the Tester at run time; not authored",
           "pricing": "Black-Scholes European float math, rounded to 4 places; some contracts unsolvable by design",
           "classes": CLASSES, "extreme_fraction_pct": EXTREME_FRACTION_PCT,
           "sets": {k: {"sha256_of_canonical_jsonl": set_digest(s, k), "class_counts": class_counts(s, k)}
                    for k in ("flat", "mixed")},
           "sample_files": ["sample_m1_flat.jsonl", "sample_m1_mixed.jsonl"]}
    with open(os.path.join(a.out, "m1_solver_manifest.json"), "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(man, indent=1, sort_keys=True) + "\n")
    for k in ("flat", "mixed"):
        with open(os.path.join(a.out, "sample_m1_%s.jsonl" % k), "w", encoding="utf-8", newline="\n") as f:
            f.write("".join(canon(contract(s, k, i)) + "\n" for i in range(SAMPLE_N)))


if __name__ == "__main__":
    main()
