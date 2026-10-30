#!/usr/bin/env python3
"""SYNTHETIC performance workload generator for Option Features M3a (G7 history-store workloads, G8 performance
workloads), Tester-authored from docs/m3a/M3A_GATE_BUDGETS.md sections 3 and 5 and M3A_FIXTURE_REQUIREMENTS.md sections
3 and 7. Stdlib only. Seeded, deterministic (own splitmix64). LF, ASCII, no absolute paths. The library under test is
never imported; no vendor, recorded data, network or download is involved.

Only a compact manifest (frozen facts, sha256 digests, truth samples) and tiny samples are written. Full workloads
regenerate at run time from (seed, parameters) by importing this module:
    chain(size, underlying, session, cutoff_index, seed)      -> one all-valid-quote smile chain (G1/G8)
    chain_truth(chain)                                         -> forward, ATM IV, 25-delta IV, tenor IV (floats)
    history_close(name, series, session) / history_grid(...)   -> history values in 1e-8 integer units (G7)
    units()                                                    -> the 5 x 5 x 78 unit keys
Usage: python gen_m3a_workloads.py --out DIR [--seed N] [--quick] | --recheck FACTS.json MANIFEST.json
"""
import argparse
import hashlib
import json
import math
import os
import sys
from array import array
from fractions import Fraction

from m3a_common import DEFAULT_SEED, M64, PERF_LABEL, PROVENANCE, QUAL, SplitMix, cj, sha

NS = 1_000_000_000
SESSION_S, MINUTES, CUTOFFS = 23_400, 390, 78
UNDERLYINGS = ["SYN1", "SYN2", "SYN3", "SYN4", "SYN5"]
SESSIONS_EVAL = 5                       # evaluated sessions, ordinal 1..5 (history sessions 1..252 before the first)
HISTORY_SESSIONS = 252
NAMES = 103
SERIES = ("iv30_close", "skew25", "skew25_fwd", "term_30_91", "atm_iv_close", "iv30_min", "atm_iv_min")   # 7 series per name (owner decisions 2 and 3)
UNIT = 100_000_000                      # 1e-8 integer units; 1 point = 0.01 = 1,000,000 units
POINT = 1_000_000
SIZES = {"S": (5, 50), "M": (8, 125), "L": (8, 375)}             # (expiries, strikes per expiry); x 2 rights
EXPIRIES = {"S": [7, 21, 35, 63, 98], "M": [5, 12, 19, 26, 33, 61, 89, 119], "L": [5, 12, 19, 26, 33, 61, 89, 119]}
STEP_CENTS = {"S": 100, "M": 40, "L": 13}
RATE, YIELD = 0.05, 0.01
TARGET_DELTA = 0.25
FROZEN_TOL = 0.10                       # facts rechecked within +/- 10 percent before each run (requirements section 7)


def mix(seed, *ints):
    h = SplitMix(seed ^ 0xA5A5A5A5)
    v = 0
    for i in ints:
        h.s = (h.s + (i & M64) * 0x9E3779B97F4A7C15) & M64
        v = h.next()
    return v


# ------------------------------------------------------------------ BSM (floats; stdlib math)
def ncdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def bsm(S, K, T, r, q, sig, right):
    sq = sig * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sig * sig) * T) / sq
    d2 = d1 - sq
    if right == "call":
        return S * math.exp(-q * T) * ncdf(d1) - K * math.exp(-r * T) * ncdf(d2)
    return K * math.exp(-r * T) * ncdf(-d2) - S * math.exp(-q * T) * ncdf(-d1)


def delta_abs(S, K, T, r, q, sig, right):
    d1 = (math.log(S / K) + (r - q + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))
    return math.exp(-q * T) * (ncdf(d1) if right == "call" else ncdf(-d1))


def vega(S, K, T, r, q, sig):
    d1 = (math.log(S / K) + (r - q + 0.5 * sig * sig) * T) / (sig * math.sqrt(T))
    return S * math.exp(-q * T) * math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi) * math.sqrt(T)


def smile(T_days, k, u):
    """G1 true volatility sigma(k, T) = a(T) + b(T) k + c(T) k^2; u = underlying index."""
    T = T_days / 365.0
    a = 0.16 + 0.02 * u + 0.06 * (1.0 - math.exp(-T / 0.20))
    b = -0.10 - 0.05 * math.exp(-T * 5.0)
    c = 0.80
    return a + b * k + c * k * k


def d4(x):
    return "%.4f" % x


# ------------------------------------------------------------------ G8 chains
def spot_cents(underlying, session, cutoff_index, seed):
    u = UNDERLYINGS.index(underlying)
    return 10000 + 37 * u + 11 * session + (mix(seed, u, session, cutoff_index) % 401) - 200


def cutoff_ns(session, cutoff_index):
    """Session-relative cutoff: open + 300 s x (index + 1); session ordinal stretches the day clock (synthetic)."""
    return (session * 86_400 + 34_200 + 300 * (cutoff_index + 1)) * NS


def chain(size, underlying="SYN1", session=3, cutoff_index=45, seed=DEFAULT_SEED):
    """One all-valid-quote smile chain of the M1 ChainContract shape. Returns dict with the request-level fields."""
    nexp, nstr = SIZES[size]
    u = UNDERLYINGS.index(underlying)
    sc = spot_cents(underlying, session, cutoff_index, seed)
    S = sc / 100.0
    cut = cutoff_ns(session, cutoff_index)
    step = STEP_CENTS[size]
    contracts, floored = [], 0
    for ei, days in enumerate(EXPIRIES[size]):
        T = days / 365.0
        F = S * math.exp((RATE - YIELD) * T)
        for si in range(nstr):
            kc = 10000 + (si - nstr // 2) * step
            K = kc / 100.0
            sig = smile(days, math.log(K / F), u)
            for right in ("call", "put"):
                mid = bsm(S, K, T, RATE, YIELD, sig, right)
                if mid < 0.03:
                    mid, floored = 0.03, floored + 1
                half = max(0.01, round(0.01 * mid, 4))
                bid, ask = round(mid - half, 4), round(mid + half, 4)
                ev = cut - NS * (1 + mix(seed, u, session, cutoff_index, ei, si, right == "put") % 9)
                contracts.append({"contract_id": "%s-E%d-%s%03d" % (underlying, ei, "C" if right == "call" else "P", si),
                                  "expiry_days": days, "right": right, "strike": "%d.%02d" % divmod(kc, 100),
                                  "bid": d4(bid), "ask": d4(ask), "event_ns": ev, "known_at_ns": None,
                                  "style": "european", "condition": "regular"})
    return {"size": size, "underlying": underlying, "session": session, "cutoff_index": cutoff_index, "cutoff_ns": cut,
            "spot": "%d.%02d" % divmod(sc, 100), "rate": "0.0500", "dividend_yield": "0.0100", "floored": floored,
            "contracts": contracts}


def chain_bytes(ch):
    return ("\n".join(cj(c) for c in ch["contracts"]) + "\n").encode("ascii")


def chain_truth(ch):
    """Known values from the true smile (floats, tolerance IV 1e-4 / forward 1e-6, R-94; quantised quotes: vega >= 4)."""
    S, u, size = float(ch["spot"]), UNDERLYINGS.index(ch["underlying"]), ch["size"]
    nexp, nstr = SIZES[size]
    step = STEP_CENTS[size]
    exps, wtot = [], {}
    for days in EXPIRIES[size]:
        T = days / 365.0
        F = S * math.exp((RATE - YIELD) * T)
        ks = [(10000 + (si - nstr // 2) * step) / 100.0 for si in range(nstr)]
        ia = min(range(nstr), key=lambda i: (abs(ks[i] - F), i))        # tie goes to the lower strike (R-10)
        atm = smile(days, math.log(ks[ia] / F), u)
        side = {}
        for right, direction in (("put", -1), ("call", 1)):
            prev = (ia, delta_abs(S, ks[ia], T, RATE, YIELD, atm, right), atm)
            side[right] = None
            i = ia + direction
            while 0 <= i < nstr:
                sg = smile(days, math.log(ks[i] / F), u)
                d = delta_abs(S, ks[i], T, RATE, YIELD, sg, right)
                if (prev[1] - TARGET_DELTA) * (d - TARGET_DELTA) <= 0 and prev[1] != d:
                    d0, s0, d1, s1 = prev[1], prev[2], d, sg
                    iv = s0 + (TARGET_DELTA - d0) / (d1 - d0) * (s1 - s0)      # linear in delta (R-09)
                    side[right] = {"iv": "%.8f" % iv, "bracket_index": [prev[0], i],
                                   "strike_distance_from_atm": abs(i - ia)}
                    break
                prev = (i, d, sg)
                i += direction
        exps.append({"expiry_days": days, "forward": "%.8f" % F, "atm_strike": "%.2f" % ks[ia], "atm_index": ia,
                     "atm_iv": "%.8f" % atm, "put25": side["put"], "call25": side["call"],
                     "atm_vega": "%.4f" % vega(S, ks[ia], T, RATE, YIELD, atm)})
        wtot[days] = atm * atm * T
    tenors = {}
    ds = sorted(wtot)
    for tau in (9, 30, 91):
        lo = [d for d in ds if d <= tau]
        hi = [d for d in ds if d >= tau]
        if not lo or not hi:
            tenors[str(tau)] = None
            continue
        a, b = lo[-1], hi[0]
        w = wtot[a] if a == b else wtot[a] + (tau - a) / (b - a) * (wtot[b] - wtot[a])   # linear total variance (R-15)
        tenors[str(tau)] = {"iv": "%.8f" % math.sqrt(w / (tau / 365.0)), "expiries_used": [a, b]}
    return {"expiries": exps, "tenors": tenors}


def chain_facts(ch, truth):
    cs = ch["contracts"]
    nexp, nstr = SIZES[ch["size"]]
    return {"contracts": len(cs), "expiries": len({c["expiry_days"] for c in cs}), "strikes_per_expiry": nstr,
            "calls": sum(1 for c in cs if c["right"] == "call"), "puts": sum(1 for c in cs if c["right"] == "put"),
            "quote_count": 2 * len(cs), "all_valid_quotes": all(float(c["bid"]) > 0 and float(c["ask"]) > float(c["bid"]) for c in cs),
            "floored_wing_quotes": ch["floored"], "naive_delta_evaluations": len(cs),
            "max_delta_evaluations_budget": 200, "chain_sha256": sha(chain_bytes(ch))}


# ------------------------------------------------------------------ units (5 x 5 x 78)
def units():
    return ["%s/%02d/%03d" % (u, s, c) for u in UNDERLYINGS for s in range(1, SESSIONS_EVAL + 1) for c in range(CUTOFFS)]


# ------------------------------------------------------------------ G7 history values (integer 1e-8 units)
def name_base(n, seed):
    return 15_000_000 + mix(seed, 1, n) % 45_000_000          # iv30 level 0.15 .. 0.60 annual


def history_close(n, series, s, seed):
    """Session-close scalar of name n, series, session s (1-based); integer in 1e-8 units. Name 101 is constant
    (zero-range history); every other name varies."""
    if series == "iv30_close":
        b = name_base(n, seed)
        return b if n == 101 else b + (mix(seed, 2, n, s) % 6_000_001) - 3_000_000
    if series == "atm_iv_close":
        b = name_base(n, seed) - 400_000
        return b if n == 101 else b + (mix(seed, 14, n, s) % 6_000_001) - 3_000_000
    if series == "skew25_fwd":
        return 0 if n == 101 else ((mix(seed, 16, n) % 8_000_001) - 4_000_000) + (mix(seed, 17, n, s) % 1_000_001) - 500_000
    if series == "skew25":
        return 0 if n == 101 else ((mix(seed, 3, n) % 8_000_001) - 4_000_000) + (mix(seed, 4, n, s) % 1_000_001) - 500_000
    if series == "term_30_91":
        return 0 if n == 101 else ((mix(seed, 5, n) % 6_000_001) - 3_000_000) + (mix(seed, 6, n, s) % 1_000_001) - 500_000
    raise KeyError(series)


def history_grid(n, s, seed, kind="iv30"):
    """iv30 minute grid (390 integers) of name n, session s: close value plus a bounded integer walk."""
    base = history_close(n, "iv30_close" if kind == "iv30" else "atm_iv_close", s, seed)
    x = mix(seed, 7 if kind == "iv30" else 15, n, s)
    out = []
    for _ in range(MINUTES):
        x = (x * 6364136223846793005 + 1442695040888963407) & M64
        out.append(base + ((x >> 40) % 400_001) - 200_000)
    return out


PLAN = ["top_unique", "top_tie", "top5pct", "median", "bottom_tie", "bottom_unique", "second_from_top", "bottom5pct"]


def today_value(n, series, seed, hist):
    """Planted rank of today's value x against the 252-session history `hist` (sorted ascending list)."""
    if n == 101:
        return hist[0]                                        # constant history: x equals the constant
    p = PLAN[n % 8]
    h = sorted(hist)
    if p == "top_unique":
        return h[-1] + 1
    if p == "top_tie":
        return h[-1]
    if p == "top5pct":
        return h[len(h) - 13]
    if p == "median":
        return h[len(h) // 2]
    if p == "bottom_tie":
        return h[0]
    if p == "bottom_unique":
        return h[0] - 1
    if p == "second_from_top":
        return h[-2]
    return h[12]


def rank_truth(x, hist):
    n = len(hist)
    le = sum(1 for v in hist if v <= x)
    ge = sum(1 for v in hist if v >= x)
    zero = max(hist) == min(hist)
    if n < 20:
        return {"status": "unavailable", "reason": "insufficient_history", "n": n}
    if zero:
        return {"status": "unavailable", "reason": "zero_range_history", "n": n}
    return {"status": "available", "reason": None, "n": n, "rank_le": le, "upper_share": str(Fraction(ge, n)),
            "lower_share": str(Fraction(le, n))}


def rank_truth_lines(seed, quick):
    names = 8 if quick else NAMES
    lines = []
    for n in range(names):
        for series in ("iv30_close", "skew25", "skew25_fwd", "atm_iv_close"):
            hist = [history_close(n, series, s, seed) for s in range(1, HISTORY_SESSIONS + 1)]
            x = today_value(n, series, seed, hist)
            lines.append(cj({"name": n, "series": series, "x": x, **rank_truth(x, hist)}))
        for kind, nm in (("iv30", "iv30_min@195"), ("atm", "atm_iv_min@195")):
            grid = [history_grid(n, s, seed, kind)[195] for s in range(1, HISTORY_SESSIONS + 1)]
            x = today_value(n, nm, seed, grid)
            lines.append(cj({"name": n, "series": nm, "x": x, **rank_truth(x, grid)}))
    return lines


def point_inputs(n, seed):
    """M3A-B4 point-output inputs of name n (integers in 1e-8 units): now and prior readings."""
    iv_now = name_base(n, seed) + mix(seed, 8, n) % 4_000_001 - 2_000_000
    iv_prior = iv_now - (mix(seed, 9, n) % 3_000_001) + 1_000_000
    sk_now = ((mix(seed, 10, n) % 8_000_001) - 4_000_000)
    sk_prior = ((mix(seed, 11, n) % 8_000_001) - 4_000_000)
    t930 = iv_now - (mix(seed, 12, n) % 2_000_001) + 500_000
    t3091 = iv_now + (mix(seed, 13, n) % 2_000_001) - 500_000
    return {"iv30_now": iv_now, "iv30_prior": iv_prior, "skew_now": sk_now, "skew_prior": sk_prior,
            "iv9": t930, "iv30": iv_now, "iv91": t3091}


def point_truth(n, seed):
    p = point_inputs(n, seed)
    sg = lambda v: (v > 0) - (v < 0)
    d = p["skew_now"] - p["skew_prior"]
    return {"name": n, "v4_change_points": str(Fraction(p["iv30_now"] - p["iv30_prior"], POINT)),
            "v4_change_ratio": str(Fraction(p["iv30_now"] - p["iv30_prior"], p["iv30_prior"])),
            "v5_9_30": str(Fraction(p["iv30"] - p["iv9"], POINT)), "v5_30_91": str(Fraction(p["iv91"] - p["iv30"], POINT)),
            "v10_change_points": str(Fraction(d, POINT)), "v10_sign_now": sg(p["skew_now"]),
            "v10_sign_prior": sg(p["skew_prior"]),
            "v10_sign_changed": sg(p["skew_now"]) * sg(p["skew_prior"]) == -1}


# ------------------------------------------------------------------ store workload facts
def store_facts():
    recs = NAMES * HISTORY_SESSIONS * len(SERIES)
    grid_raw = NAMES * HISTORY_SESSIONS * MINUTES * 8 * 2          # two minute grids (iv30, atm_iv)
    return {"names": NAMES, "series_per_name": len(SERIES), "series_total": NAMES * len(SERIES),
            "sessions": HISTORY_SESSIONS, "retention_k": HISTORY_SESSIONS, "records": recs,
            "scalar_records": NAMES * HISTORY_SESSIONS * 5, "grid_records": NAMES * HISTORY_SESSIONS * 2,
            "minute_grid_raw_bytes": grid_raw, "minute_grid_m2_layout_bytes": 3 * grid_raw,
            "scalar_bytes_raw": NAMES * HISTORY_SESSIONS * 5 * 8, "m2_layout_share_of_768MiB": round(3 * grid_raw / (768 * 2 ** 20), 4),
            "flag": "matches the budgets doc of PR 104 (7 series, about 181,700 records, store 768 MiB); the older doc text (4 series, 104,000 records, 512 MB) is superseded; 7 series per name = 181,692 records, 721 series; 486 MB M2 layout is 60 percent of the 768 MiB budget (RULED)",
            "budget_store_bytes": 768 * 2 ** 20, "hard_store_bytes_per_worker": 1 << 30,
            "formula": "names x sessions x 390 x 8 B x 2 grids (raw), x 3 for the M2 layout (raw, sorted copy, merged array)"}


def store_digest(seed, quick):
    """sha256 over the whole store workload (every record of every name and series), streamed."""
    h = hashlib.sha256()
    names = 4 if quick else NAMES
    little = sys.byteorder == "little"
    for n in range(names):
        for s in range(1, HISTORY_SESSIONS + 1):
            for series in ("iv30_close", "skew25", "skew25_fwd", "term_30_91", "atm_iv_close"):
                h.update(history_close(n, series, s, seed).to_bytes(8, "little", signed=True))
            for kind in ("iv30", "atm"):
                a = array("q", history_grid(n, s, seed, kind))
                if not little:
                    a.byteswap()
                h.update(a.tobytes())
    return h.hexdigest()


# ------------------------------------------------------------------ manifest
def build_manifest(seed, quick):
    m = {"provenance": PROVENANCE, "label": QUAL, "perf_label": PERF_LABEL, "seed": seed, "quick": quick,
         "generator": "gen_m3a_workloads.py", "chains": {}, "units": {}, "store": store_facts(), "truth_samples": {}}
    for size in ("S", "M", "L"):
        ch = chain(size, seed=seed)
        tr = chain_truth(ch)
        m["chains"][size] = {"unit": "SYN1/03/045", "spot": ch["spot"], "cutoff_ns": ch["cutoff_ns"],
                             "expiry_days": EXPIRIES[size], "facts": chain_facts(ch, tr),
                             "truth_sha256": sha(cj(tr).encode("ascii"))}
        if size == "M":
            m["truth_samples"]["M_expiries_head"] = tr["expiries"][:2]
            m["truth_samples"]["M_tenors"] = tr["tenors"]
    # B11 cutoff sweep: 78 cutoffs of SYN1/03, spot changes at every cutoff, size M chains regenerate per cutoff
    spots = [spot_cents("SYN1", 3, c, seed) for c in range(CUTOFFS)]
    m["sweep_B11"] = {"unit_prefix": "SYN1/03/", "cutoffs": CUTOFFS, "spot_cents_sha256": sha(cj(spots).encode()),
                      "distinct_spots": len(set(spots)), "all_cutoffs_new_spot_vs_previous": all(
                          spots[i] != spots[i - 1] for i in range(1, CUTOFFS)),
                      "repeated_spot_cutoff_indexes": [i for i in range(CUTOFFS) if spots[i] in spots[:i]],
                      "note": "71 distinct spots across 78 cutoffs: a cache keyed on spot alone would hit on the repeated cutoffs and could pass B11 by accident; the cutoff must be in the key"}
    us = units()
    m["units"] = {"grid": "5 underlyings x 5 evaluated sessions x 78 cutoffs", "count": len(us),
                  "key_format": "UNDERLYING/SESSION_ORDINAL(2)/CUTOFF_INDEX(3), e.g. SYN1/03/045",
                  "session_ordinal_to_calendar": "calendar session = 252 + ordinal; history sessions 1..256 generated, "
                                                 "each evaluated session has 252 prior sessions",
                  "units_sha256": sha(("\n".join(us) + "\n").encode()), "first": us[:3], "last": us[-3:],
                  "b10_units_size_M": len(us)}
    rl = rank_truth_lines(seed, quick)
    m["rank_truth"] = {"names": 8 if quick else NAMES, "lines": len(rl), "sha256": sha(("\n".join(rl) + "\n").encode()),
                       "plan": PLAN, "zero_range_name": 101, "samples": [json.loads(x) for x in rl[:6]]}
    pt = [cj(point_truth(n, seed)) for n in range(NAMES)]
    m["point_truth"] = {"names": NAMES, "sha256": sha(("\n".join(pt) + "\n").encode()), "samples": [json.loads(pt[0]), json.loads(pt[101])]}
    m["store_content_sha256"] = {"names_covered": 4 if quick else NAMES, "value": store_digest(seed, quick)}
    return m


def samples(out, seed):
    ch = chain("M", seed=seed)
    with open(os.path.join(out, "sample_chain_M_head.jsonl"), "w", encoding="ascii", newline="\n") as f:
        f.write(cj({"provenance": PROVENANCE, "label": QUAL, "sample": "first 16 contracts of the size-M chain SYN1/03/045",
                    "cutoff_ns": ch["cutoff_ns"], "spot": ch["spot"], "rate": ch["rate"],
                    "dividend_yield": ch["dividend_yield"]}) + "\n")
        for c in ch["contracts"][:16]:
            f.write(cj(c) + "\n")
    with open(os.path.join(out, "sample_store_name0.jsonl"), "w", encoding="ascii", newline="\n") as f:
        f.write(cj({"provenance": PROVENANCE, "label": QUAL, "sample": "name 0, sessions 1-3: scalar series and the first 8 minutes of the iv30 grid"}) + "\n")
        for s in (1, 2, 3):
            f.write(cj({"name": 0, "session": s, "iv30_close": history_close(0, "iv30_close", s, seed),
                        "skew25": history_close(0, "skew25", s, seed), "term_30_91": history_close(0, "term_30_91", s, seed),
                        "iv30_min_head": history_grid(0, s, seed)[:8]}) + "\n")
    with open(os.path.join(out, "sample_units.jsonl"), "w", encoding="ascii", newline="\n") as f:
        f.write(cj({"provenance": PROVENANCE, "label": QUAL, "sample": "first 20 unit keys"}) + "\n")
        for k in units()[:20]:
            f.write(cj({"unit_key": k}) + "\n")


def recheck(facts, manifest, tol=FROZEN_TOL):
    """Frozen-fact recheck before each run: every measured count within +/- tol of the manifest value."""
    bad = []
    for size, f in facts.get("chains", {}).items():
        ref = manifest["chains"][size]["facts"]
        for k in ("contracts", "expiries", "strikes_per_expiry", "quote_count"):
            if k in f and abs(f[k] - ref[k]) > tol * ref[k]:
                bad.append("%s.%s measured %s frozen %s" % (size, k, f[k], ref[k]))
    for k in ("names", "sessions", "records"):
        if k in facts.get("store", {}) and abs(facts["store"][k] - manifest["store"][k]) > tol * manifest["store"][k]:
            bad.append("store.%s" % k)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--quick", action="store_true", help="digest only the first 4 names and rank-truth 8 names")
    ap.add_argument("--recheck", nargs=2, metavar=("FACTS", "MANIFEST"))
    a = ap.parse_args()
    if a.recheck:
        bad = recheck(json.load(open(a.recheck[0])), json.load(open(a.recheck[1])))
        print("recheck", "OK" if not bad else "FAIL " + "; ".join(bad))
        return 1 if bad else 0
    os.makedirs(a.out, exist_ok=True)
    m = build_manifest(a.seed, a.quick)
    with open(os.path.join(a.out, "m3a_workload_manifest.json"), "w", encoding="ascii", newline="\n") as f:
        f.write(json.dumps(m, sort_keys=True, indent=1, ensure_ascii=True) + "\n")
    samples(a.out, a.seed)
    print("manifest written; chains", {k: v["facts"]["contracts"] for k, v in m["chains"].items()},
          "store records", m["store"]["records"], "units", m["units"]["count"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
