#!/usr/bin/env python3
"""SYNTHETIC performance workload generator for Option Features P1/M1.

Provenance: SYNTHETIC. Tester-authored from THROUGHPUT_BUDGET.md section 1 only.
Stdlib only. Seeded, deterministic (own splitmix64 PRNG, independent of the
Python random module version). LF output, no absolute paths.

The generator parameters + seed define the full workloads. Only a manifest and
small sample files are written. Any consumer regenerates the full stream with
the functions below (import this module) or via the runner contract.

Usage: python gen_perf_workloads.py --out DIR [--seed N] [--no-digest]
"""
import argparse
import hashlib
import json
import math
import os

PROVENANCE = "SYNTHETIC"
QUAL = "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12"
DEFAULT_SEED = 20261029
M64 = (1 << 64) - 1
TICK = 10000  # prices are integer ticks of 0.0001, rendered with 4 places
NS = 1_000_000_000

# ---- workload shape (THROUGHPUT_BUDGET section 1) ----
UNDERLYINGS = ["SYN1", "SYN2", "SYN3", "SYN4", "SYN5"]
SESSIONS = 5
CUTOFFS_PER_SESSION = 78               # one per 5 minutes over 6.5 h
CUTOFF_STEP_NS = 300 * NS
# chain sizes: contracts = expiries x strikes x 2 rights
CHAIN_SIZES = {
    "S": {"expiries_days": [7, 28, 35, 63, 91], "strikes": 50},                                   # 500
    "M": {"expiries_days": [7, 14, 21, 28, 35, 63, 91, 182], "strikes": 125},                     # 2000
    "L": {"expiries_days": [7, 14, 21, 28, 35, 42, 56, 63, 91, 126, 182, 273], "strikes": 250},   # 6000
}
STRIKE_STEP_TICKS = TICK // 2          # 0.50
SPOT_TICKS = 100 * TICK
# quote updates per contract per session: Pareto tail, median 50, p99 5000
Q_MEDIAN, Q_P99, Q_CAP = 50, 5000, 20000
_INV_ALPHA = math.log(Q_P99 / Q_MEDIAN) / math.log(50.0)   # p99/median = 50^(1/alpha)
_XM = Q_MEDIAN / (2.0 ** _INV_ALPHA)
STREAM_SIZES = [100_000, 1_000_000]
STREAM_QUOTE_SHARE_PCT = 80            # 80 percent quotes, 20 percent trades
STREAM_CLASSES = ["normal", "locked", "crossed", "bid_zero", "touch_ask", "touch_bid",
                  "inside", "stale_boundary", "window_end"]
STREAM_CLASS_WEIGHTS = [70, 3, 3, 3, 8, 8, 3, 1, 1]  # percent
OC_WINDOWS = [1, 50, 5000]             # OC6 update-window sizes (OC5 uses a single quote state)
WINDOW_NS = 300 * NS
SAMPLE_N = 40


class SM64:
    def __init__(self, seed):
        self.s = seed & M64

    def next(self):
        self.s = (self.s + 0x9E3779B97F4A7C15) & M64
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
        return z ^ (z >> 31)

    def uni(self):
        return (self.next() >> 11) / float(1 << 53)

    def below(self, n):
        return self.next() % n


def sub(seed, *keys):
    """Derive an independent stream seed from (seed, keys); stable across runs."""
    h = hashlib.sha256((str(seed) + "|" + "|".join(str(k) for k in keys)).encode()).digest()
    return int.from_bytes(h[:8], "big")


def dec(ticks):
    sign = "-" if ticks < 0 else ""
    t = abs(ticks)
    return "%s%d.%04d" % (sign, t // TICK, t % TICK)


def chain_size(size):
    c = CHAIN_SIZES[size]
    return len(c["expiries_days"]) * c["strikes"] * 2


def chain_contract(size, i):
    """Contract i of a chain (no PRNG). Order: expiry, strike, right (C,P)."""
    c = CHAIN_SIZES[size]
    n = c["strikes"]
    e, rem = divmod(i, n * 2)
    k, r = divmod(rem, 2)
    strike = SPOT_TICKS + (k - n // 2) * STRIKE_STEP_TICKS
    return {"i": i, "expiry_days": c["expiries_days"][e], "strike": dec(strike),
            "right": "CP"[r], "style": ("european" if e % 3 == 2 else "american")}


def quote_count(seed, size, underlying, session, i):
    u = SM64(sub(seed, "qc", size, underlying, session, i)).uni()
    n = int(round(_XM * (1.0 - u) ** (-_INV_ALPHA)))
    return max(1, min(Q_CAP, n))


def quote_stream_for_contract(seed, size, underlying, session, i, n=None):
    """Timed quotes for one contract in one session (ints are ns / ticks)."""
    n = quote_count(seed, size, underlying, session, i) if n is None else n
    g = SM64(sub(seed, "qs", size, underlying, session, i))
    span = CUTOFFS_PER_SESSION * CUTOFF_STEP_NS
    mid = SPOT_TICKS // 20 + g.below(SPOT_TICKS // 20)
    ts = sorted(g.below(span) for _ in range(n))
    for t in ts:
        mid = max(TICK // 50, mid + g.below(41) - 20)
        half = 1 + g.below(10)
        yield {"t_rel_ns": t, "bid": dec(mid - half), "ask": dec(mid + half),
               "bid_size": 1 + g.below(50), "ask_size": 1 + g.below(50)}


def oc_window(seed, nupd, window_ns=WINDOW_NS):
    """One contract, nupd quote updates inside [-window_ns, 0]; evaluation time is 0."""
    g = SM64(sub(seed, "ocw", nupd))
    ts = sorted(-g.below(window_ns) for _ in range(nupd))
    mid = 2 * TICK
    out = []
    for t in ts:
        mid = max(TICK // 10, mid + g.below(21) - 10)
        half = 1 + g.below(5)
        out.append({"t_rel_ns": t, "bid": dec(mid - half), "ask": dec(mid + half),
                    "bid_size": 1 + g.below(30), "ask_size": 1 + g.below(30)})
    return out


def _pick(r):
    acc = 0
    for idx, w in enumerate(STREAM_CLASS_WEIGHTS):
        acc += w
        if r < acc:
            return idx
    return 0


def stream_record(seed, n_total, i):
    """Record i of the mixed quote/trade stream. Pure function of (seed, i); time non-decreasing."""
    g = SM64(sub(seed, "st", i))
    cls = STREAM_CLASSES[_pick(g.below(100))]
    t = i * 1_000_000 + g.below(1_000_000)
    base = 2 * TICK + g.below(20000) * 10
    half = 5 + g.below(20)
    bid, ask = base - half, base + half
    is_quote = g.below(100) < STREAM_QUOTE_SHARE_PCT
    if cls == "locked":
        ask = bid
    elif cls == "crossed":
        bid, ask = ask + 1, bid
    elif cls == "bid_zero":
        bid = 0
    rec = {"i": i, "t_rel_ns": t, "contract": g.below(2000), "class": cls}
    if is_quote:
        rec.update(k="q", bid=dec(bid), ask=dec(ask), bid_size=1 + g.below(50), ask_size=1 + g.below(50))
        return rec
    if cls == "touch_ask":
        px = ask
    elif cls == "touch_bid":
        px = bid
    elif cls == "inside":
        px = (bid + ask) // 2 if ask - bid > 1 else bid
    else:
        px = base + g.below(2 * half + 1) - half
    if cls == "stale_boundary":
        rec["age_hint_ns"] = 3 * NS + g.below(3) - 1
    rec.update(k="t", price=dec(px), size=1 + g.below(100))
    return rec


def canon(rec):
    return json.dumps(rec, sort_keys=True, separators=(",", ":"))


def stream_digest(seed, n):
    h = hashlib.sha256()
    for i in range(n):
        h.update(canon(stream_record(seed, n, i)).encode() + b"\n")
    return h.hexdigest()


def cutoffs():
    return [(k + 1) * CUTOFF_STEP_NS for k in range(CUTOFFS_PER_SESSION)]


def build_manifest(seed, with_digest=True):
    sizes = {k: chain_size(k) for k in CHAIN_SIZES}
    assert sizes == {"S": 500, "M": 2000, "L": 6000}, sizes
    qc = sorted(quote_count(seed, "M", "SYN1", 1, i) for i in range(2000))
    m = {
        "provenance": PROVENANCE,
        "qualification_label": QUAL,
        "label": "synthetic workload, relative engineering budget",
        "generator": "gen_perf_workloads.py", "seed": seed, "schema_version": 1,
        "prng": "splitmix64; stream seeds = first 8 bytes of sha256(seed|keys)",
        "universe": {"underlyings": UNDERLYINGS, "sessions": SESSIONS,
                     "cutoffs_per_session": CUTOFFS_PER_SESSION, "cutoff_step_ns": CUTOFF_STEP_NS,
                     "total_cutoffs_per_size": len(UNDERLYINGS) * SESSIONS * CUTOFFS_PER_SESSION},
        "chains": {k: {"contracts": sizes[k], **CHAIN_SIZES[k],
                       "sample": [chain_contract(k, i) for i in range(6)]} for k in CHAIN_SIZES},
        "quote_updates": {"distribution": "pareto tail, median 50, p99 5000, cap %d, min 1" % Q_CAP,
                          "xm": _XM, "inv_alpha": _INV_ALPHA,
                          "tolerance_pct": 10, "targets": {"median": 50, "p99": 5000},
                          "frozen_fact_size_M_SYN1_s1": {"median": qc[1000], "p99": qc[1979],
                                                   "max": qc[-1], "total": sum(qc)}},
        "oc_windows": {"updates": OC_WINDOWS, "window_ns": WINDOW_NS,
                       "note": "OC5 = single quote state; OC6 = time-weighted window of N updates"},
        "streams": {"sizes": STREAM_SIZES, "quote_share_pct": STREAM_QUOTE_SHARE_PCT,
                    "classes": STREAM_CLASSES, "class_weights_pct": STREAM_CLASS_WEIGHTS,
                    "stale_boundary": "age_hint_ns in {3s-1ns, 3s, 3s+1ns}",
                    "full_workload": "regenerate with stream_record(seed, n, i), i in 0..n-1"},
    }
    if with_digest:
        m["streams"]["sha256_of_canonical_jsonl"] = {str(n): stream_digest(seed, n) for n in STREAM_SIZES}
    return m


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--no-digest", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    man = build_manifest(a.seed, not a.no_digest)
    write(os.path.join(a.out, "perf_manifest.json"), json.dumps(man, indent=1, sort_keys=True) + "\n")
    s = a.seed
    write(os.path.join(a.out, "sample_stream_100k.jsonl"),
          "".join(canon(stream_record(s, 100_000, i)) + "\n" for i in range(SAMPLE_N * 5)))
    write(os.path.join(a.out, "sample_chain_M_quotes.jsonl"),
          "".join(canon({"contract": chain_contract("M", i), "quotes": list(
              quote_stream_for_contract(s, "M", "SYN1", 1, i, min(5, quote_count(s, "M", "SYN1", 1, i))))}) + "\n"
              for i in range(SAMPLE_N)))
    write(os.path.join(a.out, "sample_oc_windows.jsonl"),
          "".join(canon({"updates": n, "head": oc_window(s, n)[:5]}) + "\n" for n in OC_WINDOWS))


if __name__ == "__main__":
    main()
