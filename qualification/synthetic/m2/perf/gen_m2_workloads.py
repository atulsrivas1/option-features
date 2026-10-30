#!/usr/bin/env python3
"""SYNTHETIC performance workload generator for Option Features M2 (rev 2, against the ruled docs).

Provenance: SYNTHETIC. Tester-authored from docs/m2/M2_GATE_BUDGETS.md section 2, M2_IO_CONTRACT.md
and M2_FIXTURE_REQUIREMENTS.md (G1, G7, G8, G9). Stdlib only. Seeded, deterministic (own splitmix64
PRNG). LF output, no absolute paths. The library under test is never imported.

Only a compact manifest (sha256 digests, frozen facts, tiny samples) is written. Full workloads
regenerate at run time from (seed, parameters) by importing this module.

Usage: python gen_m2_workloads.py --out DIR [--seed N] [--quick]
"""
import argparse
import hashlib
import json
import os
from bisect import bisect_left, bisect_right
from fractions import Fraction

PROVENANCE = "SYNTHETIC"
QUAL = "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12"
LABEL = "synthetic workload, relative engineering budget"
DEFAULT_SEED = 20261029
M64 = (1 << 64) - 1
TICK = 10000                           # prices are integer ticks (price x 10^4)
NS = 1_000_000_000
SESSION_S = 23_400                     # 6.5 h
SESSION_NS = SESSION_S * NS
MINUTES = 390                          # 60 s grid values per session
B_NS = 300 * NS                        # F17/F4 trailing window and cutoff step
CUTOFFS = 78                           # per session
# budgets doc section 2
UNIT_PRINTS = 40_000                   # frozen print total of one size-M unit (2,000 x median 20)
M_CONTRACTS = 2000                     # 8 expiries x 125 strikes x 2 rights
N_EXP, N_STRIKE = 8, 125
UNDERLYINGS = ["SYN1", "SYN2", "SYN3", "SYN4", "SYN5"]
SESSIONS_GENERATED = 25                # 20 history + 5 evaluated (21..25)
EVAL_SESSIONS = (21, 22, 23, 24, 25)
K_HISTORY = 20
SERIES_COUNTS = (500, 2000, 6000)
STREAM_SIZES = (100_000, 1_000_000)
METRICS = ("premium", "contracts", "prints", "put_volume", "call_volume")
LARGE_PREM = 100_000 * TICK            # $100,000 in price-tick units (price_ticks x size x multiplier)
STD_MULT = 100
CONC_CASES = 200
HALF_DAYS = {7: 210, 14: 210}          # PO ruling A4: two half-day sessions in the 25-session history (minutes)
DENSE_EVERY = 5                        # PO ruling A2: series s with s % 5 == 0 (20 percent) are dense
DENSE_MIN_PRINTS = 300                 # >= 300 prints per session so the 20-session median can be non-zero (see defect)
EPISODE_POINTS_STREAM = 1_000_000
SAMPLE_N = 10


class SM64:
    def __init__(self, seed):
        self.s = seed & M64

    def next(self):
        self.s = (self.s + 0x9E3779B97F4A7C15) & M64
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
        return z ^ (z >> 31)

    def below(self, n):
        return self.next() % n


def sub(seed, *keys):
    h = hashlib.sha256((str(seed) + "|" + "|".join(str(k) for k in keys)).encode()).digest()
    return int.from_bytes(h[:8], "big")


def lane(underlying):
    return "etf_index" if underlying == "SYN5" else "stock"


def contract(cid):
    """cid -> (right, strike_ticks, expiry_index). cid = ((e*125+s)*2+r), r 0=C 1=P."""
    r = cid & 1
    es = cid >> 1
    return ("P" if r else "C", 50 * TICK + (es % N_STRIKE) * (TICK // 2), es // N_STRIKE)


def minutes_of(k):
    return HALF_DAYS.get(k, MINUTES)


def unit_n(k):
    """Frozen print total of a unit: 40,000 for a full day, prorated for a half-day."""
    return UNIT_PRINTS * minutes_of(k) // MINUTES


def session_open_ns(k):
    return k * 86_400 * NS + 34_200 * NS


# ---------- G1: per-contract print counts and the print stream ----------
def unit_counts(seed, underlying, k, n=UNIT_PRINTS):
    """Per-contract print counts summing exactly to n. Lower half 0..19, upper half 20 + scaled
    Pareto excess, so the median is about 20 and the tail is scaled to the frozen total."""
    r = SM64(sub(seed, "cnt", underlying, k))
    half = M_CONTRACTS // 2
    base = max(1, 20 * n // UNIT_PRINTS)       # 20 for a full day, scaled for half-days
    low = [r.below(base) for _ in range(half)]
    xs = []
    for _ in range(half):
        v = min(r.below(1_000_000), 999_900) / 1e6
        xs.append((1.0 / (1.0 - v)) ** (1 / 1.1) - 1.0)
    target = n - sum(low) - base * half
    assert target > 0, (n, target)
    sc = target / sum(xs)
    up = [base + int(x * sc) for x in xs]
    d = n - sum(low) - sum(up)
    i = 0
    while d > 0:
        up[i % half] += 1
        d -= 1
        i += 1
    counts = low + up
    ids = list(range(M_CONTRACTS))
    for i in range(M_CONTRACTS - 1, 0, -1):
        j = r.below(i + 1)
        ids[i], ids[j] = ids[j], ids[i]
    out = [0] * M_CONTRACTS
    for cid, c in zip(ids, counts):
        out[cid] = c
    return out


def id_sequence(seed, underlying, k, n=UNIT_PRINTS):
    counts = unit_counts(seed, underlying, k, n)
    seq = []
    for cid, c in enumerate(counts):
        seq.extend([cid] * c)
    r = SM64(sub(seed, "shuf", underlying, k))
    for i in range(len(seq) - 1, 0, -1):
        j = r.below(i + 1)
        seq[i], seq[j] = seq[j], seq[i]
    return seq


def skew_ids(seed, n):
    r = SM64(sub(seed, "skew", n))
    out = []
    for _ in range(n):
        u = r.below(1_000_000) / 1e6
        out.append(int(M_CONTRACTS * u * u * u))
    return out


def prints(seed, key, open_ns, ids, session_ns=SESSION_NS):
    """Yield (contract_id, time_ns, price_ticks, size, multiplier, condition_excluded, seq),
    sorted by (time_ns, seq). Ties on one ns occur; about a quarter of 300 s boundary crossings
    emit prints exactly at B-1 ns and B ns (inclusive-window stress). 2 percent nonstandard
    multiplier, 1 percent excluded condition."""
    n = len(ids)
    r = SM64(sub(seed, "prn", *key))
    mean = max(2, session_ns // n)
    t = 0
    i = 0

    def mk(t_rel, seqno):
        c = ids[seqno]
        price = 5_000 + r.below(200_000)
        size = 1 + (r.below(10) if r.below(100) < 90 else r.below(500))
        mult = STD_MULT if r.below(100) >= 2 else (10, 50, 1000)[r.below(3)]
        return (c, open_ns + t_rel, price, size, mult, r.below(100) == 0, seqno)

    while i < n:
        t2 = min(t + (0 if r.below(100) < 1 else r.below(2 * mean + 1)), session_ns)   # 1 percent same-ns ties
        b = (t2 // B_NS) * B_NS
        if b > t and b > 0 and i + 2 < n and r.below(100) < 25:
            yield mk(b - 1, i)
            yield mk(b, i + 1)
            i += 2
            t = b
        yield mk(t2, i)
        i += 1
        t = t2


def unit_prints(seed, underlying, k, n=None):
    n = unit_n(k) if n is None else n
    return prints(seed, (underlying, k), session_open_ns(k), id_sequence(seed, underlying, k, n),
                  minutes_of(k) * 60 * NS)


def stream_prints(seed, n):
    return prints(seed, ("rate", n), session_open_ns(1), skew_ids(seed, n))


def _digest_prints(it, want_tallies=False):
    h = hashlib.sha256()
    buf = []
    t = {"n": 0, "eligible": 0, "premium_ticks": 0, "large_prints": 0, "put_volume": 0,
         "call_volume": 0, "ties": 0, "boundary_prints": 0}
    last = -1
    first = []
    for p in it:
        buf.append("%d,%d,%d,%d,%d,%d,%d\n" % (p[0], p[1], p[2], p[3], p[4], 1 if p[5] else 0, p[6]))
        if len(buf) >= 8192:
            h.update("".join(buf).encode())
            buf = []
        t["n"] += 1
        if p[1] == last:
            t["ties"] += 1
        last = p[1]
        if p[1] % B_NS in (0, B_NS - 1):
            t["boundary_prints"] += 1
        if p[4] == STD_MULT and not p[5]:
            prem = p[2] * p[3] * p[4]
            t["eligible"] += 1
            t["premium_ticks"] += prem
            if prem >= LARGE_PREM:
                t["large_prints"] += 1
            if p[0] & 1:
                t["put_volume"] += p[3]
            else:
                t["call_volume"] += p[3]
        if len(first) < SAMPLE_N:
            first.append(list(p))
    if buf:
        h.update("".join(buf).encode())
    t["sha256"] = h.hexdigest()
    t["sample"] = first
    return t


def count_stats(counts):
    s = sorted(counts)
    return {"median": (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2, "p99": s[int(len(s) * 0.99)],
            "max": s[-1], "contracts_with_prints": sum(1 for c in counts if c)}


def unit_facts(seed, underlying, k):
    cs = unit_counts(seed, underlying, k, unit_n(k))
    t = _digest_prints(unit_prints(seed, underlying, k))
    t.update({"unit": "%s/%02d" % (underlying, k), "k": k, "expected_n": unit_n(k), "minutes": minutes_of(k), "lane": lane(underlying), "count_stats": count_stats(cs)})
    return t


# ---------- trailing-window truth (F4, F17; Q9 closed trailing [T-300, T]) ----------
def window_truth(seed, underlying, k):
    ps = list(unit_prints(seed, underlying, k))
    op = session_open_ns(k)
    elig = [p for p in ps if p[4] == STD_MULT and not p[5]]
    gt = [p[1] for p in elig]
    large_prefix = [0]
    for p in elig:
        large_prefix.append(large_prefix[-1] + (1 if p[2] * p[3] * p[4] >= LARGE_PREM else 0))
    by_c = {}
    for p in elig:
        by_c.setdefault(p[0], ([], [0]))
        ts, cum = by_c[p[0]]
        ts.append(p[1])
        cum.append(cum[-1] + p[2] * p[3] * p[4])
    rows = []
    h = hashlib.sha256()
    for i in range(1, CUTOFFS + 1):
        T = op + i * B_NS
        lo, hi = bisect_left(gt, T - B_NS), bisect_right(gt, T)
        fire = 0
        tot = 0
        for ts, cum in by_c.values():
            a, b = bisect_left(ts, T - B_NS), bisect_right(ts, T)
            s = cum[b] - cum[a]
            tot += s
            if s >= LARGE_PREM:
                fire += 1
        row = (i, hi - lo, large_prefix[hi] - large_prefix[lo], fire, tot)
        h.update(("%d,%d,%d,%d,%d\n" % row).encode())
        rows.append(row)
    return {"unit": "%s/%02d" % (underlying, k), "cutoffs": CUTOFFS, "window_s": 300,
            "columns": ["cutoff", "eligible_prints", "large_prints_F4", "contracts_sum_ge_100k_F17", "window_premium_ticks"],
            "sha256": h.hexdigest(), "sample": [list(x) for x in rows[:3]]}


# ---------- trade-to-grid reference (M2-B18 truth) ----------
def trade_to_grid(ps, open_ns, mins=MINUTES):
    """Per contract series, per metric: sparse grid {bin: value} (390 bins of 60 s) and totals."""
    g = {}
    for p in ps:
        if p[4] != STD_MULT or p[5]:
            continue
        b = min((p[1] - open_ns) // (60 * NS), mins - 1)
        d = g.setdefault(p[0], {m: {} for m in METRICS})
        vals = {"premium": p[2] * p[3] * p[4], "contracts": p[3], "prints": 1,
                "put_volume": p[3] if p[0] & 1 else 0, "call_volume": 0 if p[0] & 1 else p[3]}
        for m in METRICS:
            d[m][b] = d[m].get(b, 0) + vals[m]
    return g


def grid_truth(seed, underlying, k):
    g = trade_to_grid(unit_prints(seed, underlying, k), session_open_ns(k), minutes_of(k))
    h = hashlib.sha256()
    for cid in sorted(g):
        for m in METRICS:
            h.update(("%d,%s,%s\n" % (cid, m, ",".join("%d:%d" % (b, v) for b, v in sorted(g[cid][m].items())))).encode())
    return {"unit": "%s/%02d" % (underlying, k), "series_with_prints": len(g), "records": 5 * len(g), "sha256": h.hexdigest()}


# ---------- G8: history records (M2-B1 / B17 set), independent of the print streams ----------
def series_session(seed, s, k):
    """Sparse 60 s grids for the 5 metrics of contract series s in session k, plus complete flag.
    Count per series-session: 1 + int(10 x Pareto(1.1)), cap 1,000 (median about 20)."""
    r = SM64(sub(seed, "hist", s, k))
    v = min(r.below(1_000_000), 999_999) / 1e6
    c = min(1000, 1 + int(10 * (1.0 / (1.0 - v)) ** (1 / 1.1)))
    if s % DENSE_EVERY == 0:
        c = min(1000, DENSE_MIN_PRINTS + c)
    right = s & 1
    mins = minutes_of(k)
    d = {m: {} for m in METRICS}
    for _ in range(c):
        b = r.below(mins)
        size = 1 + r.below(10)
        prem = (5_000 + r.below(200_000)) * size * STD_MULT
        for m, val in (("premium", prem), ("contracts", size), ("prints", 1),
                       ("put_volume", size if right else 0), ("call_volume", 0 if right else size)):
            if val:
                d[m][b] = d[m].get(b, 0) + val
    return c, d


def history_line(seed, s, m, k, d):
    nz = sorted(d[m].items())
    mins = minutes_of(k)
    rec = {"complete": True, "grid_nz": [[b, v] for b, v in nz], "grid_zeros": mins - len(nz),
           "metric": m, "minutes": mins, "series_id": "S%04d" % s, "session_id": k,
           "total": sum(v for _, v in nz)}
    line = json.dumps(rec, sort_keys=True, separators=(",", ":"))
    return line, hashlib.sha256(line.encode()).hexdigest()


def history_facts(seed, n_series, sessions=SESSIONS_GENERATED):
    h = hashlib.sha256()
    recs = 0
    nzs = 0
    first = None
    for s in range(n_series):
        per_k = [series_session(seed, s, k)[1] for k in range(1, sessions + 1)]
        for m in METRICS:
            for k in range(1, sessions + 1):
                line, sha = history_line(seed, s, m, k, per_k[k - 1])
                h.update((line + "\n").encode())
                recs += 1
                nzs += len(per_k[k - 1][m])
                if first is None:
                    first = line
    return {"series": n_series, "sessions": sessions, "records": recs, "grid_values_per_record": "390 (full day) or 210 (half-days %s)" % sorted(HALF_DAYS),
            "nonzero_points": nzs, "line_order": "(series_id, metric, session_id) as generated by series then metric order in METRICS then session",
            "sha256": h.hexdigest(), "sample_line": first[:300]}


def rank_truth(seed, n_series):
    """Tester reference (Fraction, sorted list): F2 intraday/end-of-day upper_share and rank_le and
    F10 median/mean ratio for metric 'contracts', today = session 21 grid bin 200 / session total."""
    h = hashlib.sha256()
    zero = {"dense": 0, "sparse": 0}
    cnt = {"dense": 0, "sparse": 0}
    for s in range(n_series):
        cls = "dense" if s % DENSE_EVERY == 0 else "sparse"
        hist = []
        tots = []
        for k in range(1, K_HISTORY + 1):
            d = series_session(seed, s, k)[1]["contracts"]
            vals = [0] * minutes_of(k)
            for b, v in d.items():
                vals[b] = v
            hist.extend(vals)
            tots.append(sum(vals))
        today = series_session(seed, s, 21)[1]["contracts"]
        x = today.get(200, 0)
        xt = sum(today.values())
        hs = sorted(hist)
        n = len(hs)
        le = bisect_right(hs, x)
        ge = n - bisect_left(hs, x)
        med = Fraction(hs[n // 2 - 1] + hs[n // 2], 2)
        mean = Fraction(sum(hs), n)
        ts = sorted(tots)
        tge = len(ts) - bisect_left(ts, xt)
        mr = "zd" if med == 0 else str(Fraction(x) / med)
        zero[cls] += 1 if med == 0 else 0
        cnt[cls] += 1
        h.update(("%d|%d|%d|%d|%d|%d|%s|%s|%s\n" % (s, x, n, le, ge, tge, med, mean, mr)).encode())
    return {"series": n_series, "history_values": sum(minutes_of(k) for k in range(1, K_HISTORY + 1)),
            "sha256": h.hexdigest(), "series_by_class": cnt, "series_with_zero_median_by_class": zero,
            "note": "dense = s %% %d == 0 (20 percent, >= %d prints per session); gates are timed on the mixed set, dense and sparse reported separately" % (DENSE_EVERY, DENSE_MIN_PRINTS)}


# ---------- F12 episode points ----------
def episode_points(seed, key, n, dense=False):
    """n points of (state, ratio_num, ratio_den): 0 quiet, 1 fired (ratio >= 1), 2 unavailable (0,0)."""
    r = SM64(sub(seed, "ep", *key))
    pf = 15 if dense else 4            # fire probability from quiet, percent
    st = 0
    out = []
    for _ in range(n):
        u = r.below(100)
        if st == 0:
            st = 1 if u < pf else (2 if u < pf + 1 else 0)
        elif st == 1:
            st = 1 if u < 70 else (0 if u < 98 else 2)
        else:
            st = 0 if u < 60 else 2
        if st == 1:
            den = 1 + r.below(4)
            out.append((1, den + r.below(5 * den), den))
        elif st == 0:
            den = 2 + r.below(4)
            out.append((0, r.below(den), den))
        else:
            out.append((2, 0, 0))
    return out


def episodes_ref(points, quiet_gap=1):
    """Reference scan. Episode starts at a fired point, ends after quiet_gap consecutive non-fired
    points (unavailable counts as quiet). Returns (count, first_idx, last_idx, peak 'n/d', peak_idx earliest)."""
    count = 0
    first = last = peak_i = None
    peak = None
    quiet = quiet_gap
    for i, (s, a, b) in enumerate(points):
        if s == 1:
            if quiet >= quiet_gap:
                count += 1
            quiet = 0
            if first is None:
                first = i
            last = i
            if peak is None or a * peak[1] > peak[0] * b:
                peak = (a, b)
                peak_i = i
        else:
            quiet += 1
    return count, first, last, (None if peak is None else str(Fraction(*peak))), peak_i


def episode_facts(seed, n_series, session=1, minutes=MINUTES):
    h1 = hashlib.sha256()
    h5 = hashlib.sha256()
    hp = hashlib.sha256()
    t1 = t5 = 0
    first = []
    for s in range(n_series):
        pts = episode_points(seed, (n_series, session, s), minutes, s % DENSE_EVERY == 0)
        hp.update(("".join("%d,%d,%d;" % p for p in pts) + "\n").encode())
        e1, e5 = episodes_ref(pts, 1), episodes_ref(pts, 5)
        t1 += e1[0]
        t5 += e5[0]
        h1.update(("%d:%r\n" % (s, e1)).encode())
        h5.update(("%d:%r\n" % (s, e5)).encode())
        if len(first) < 3:
            first.append({"series": s, "gap1": list(e1), "gap5": list(e5)})
    return {"series": n_series, "points_per_series": minutes, "points_sha256": hp.hexdigest(),
            "truth_gap1_total": t1, "truth_gap5_total": t5, "truth_gap1_sha256": h1.hexdigest(),
            "truth_gap5_sha256": h5.hexdigest(), "sample": first}


def episode_stream_facts(seed, n=EPISODE_POINTS_STREAM):
    """n points in sessions of 390 (the last may be shorter); sessions are separate episodes scans."""
    h = hashlib.sha256()
    tot = 0
    i = 0
    sidx = 0
    while i < n:
        m = min(MINUTES, n - i)
        pts = episode_points(seed, ("stream", sidx), m)
        e = episodes_ref(pts, 1)
        tot += e[0]
        h.update(("%d:%r\n" % (sidx, e)).encode())
        i += m
        sidx += 1
    return {"points": n, "sessions": sidx, "truth_gap1_total": tot, "truth_sha256": h.hexdigest()}


# ---------- G7: concentration (F7) ----------
def concentration_prints(case):
    """One print per (strike, expiry, right) cell, size 1, price = premium/100 ticks. Returns list of
    (cid, premium_ticks)."""
    cells = N_EXP * N_STRIKE * 2
    prem = [0] * cells
    unit = STD_MULT
    by, key, bp, m = case["by"], case["top_key"], case["bp"], case["m"]
    total_u = 10_000 * m
    top_u = m * bp
    if by == "strike":
        top_cells = [((e * N_STRIKE + key) * 2 + rr) for e in range(N_EXP) for rr in (0, 1)]
    else:
        top_cells = [((key * N_STRIKE + s) * 2 + rr) for s in range(N_STRIKE) for rr in (0, 1)]
    ts = set(top_cells)
    for c in top_cells:
        prem[c] = top_u // len(top_cells)
    rest = [c for c in range(cells) if c not in ts]
    rest_u = total_u - top_u
    each = rest_u // len(rest)
    for c in rest:
        prem[c] = each
    prem[rest[0]] += rest_u - each * len(rest)
    return [(c, p * unit) for c, p in enumerate(prem)]


def f7_reference(cp):
    total = sum(p for _, p in cp)
    st, ex = {}, {}
    for cid, p in cp:
        e, s = (cid >> 1) // N_STRIKE, (cid >> 1) % N_STRIKE
        st[s] = st.get(s, 0) + p
        ex[e] = ex.get(e, 0) + p
    ts = min(st, key=lambda s: (-st[s], s))
    te = min(ex, key=lambda e: (-ex[e], e))
    fired = st[ts] * 100 >= 60 * total or ex[te] * 100 >= 60 * total
    return {"top_strike": ts, "strike_share": str(Fraction(st[ts], total)), "top_expiry": te,
            "expiry_share": str(Fraction(ex[te], total)), "total_premium": total, "fired": fired}


def concentration_cases(seed, n=CONC_CASES):
    out = []
    for c in range(n):
        r = SM64(sub(seed, "conc", c))
        by = "strike" if c % 2 else "expiry"
        cells = 16 if by == "strike" else 250
        m = cells * (1 + r.below(20))
        bp = (5999, 6000, 6001, 3000, 9000)[c % 5]
        key = r.below(N_STRIKE if by == "strike" else N_EXP)
        case = {"case": c, "by": by, "top_key": key, "bp": bp, "m": m}
        case["truth"] = f7_reference(concentration_prints(case))
        out.append(case)
    return out


def _dr(rows):
    h = hashlib.sha256()
    for row in rows:
        h.update((json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode())
    return h.hexdigest()


def build_manifest(seed, quick=False):
    units = [("SYN1", k) for k in (EVAL_SESSIONS[:1] if quick else range(1, SESSIONS_GENERATED + 1))]
    if not quick:
        units += [(u, 21) for u in UNDERLYINGS[1:]]
    man = {"provenance": PROVENANCE, "qualification_label": QUAL, "label": LABEL, "seed": seed,
           "generator": "gen_m2_workloads.py", "quick": quick,
           "shape": {"unit_prints_frozen": UNIT_PRINTS, "contracts_M": M_CONTRACTS,
                     "sessions_generated": SESSIONS_GENERATED, "history_k": K_HISTORY,
                     "evaluated_sessions": list(EVAL_SESSIONS), "cutoffs_per_session": CUTOFFS,
                     "series_counts": list(SERIES_COUNTS), "grid_s": 60, "minutes": MINUTES,
                     "stream_sizes": list(STREAM_SIZES), "half_day_sessions_minutes": {str(k): m for k, m in sorted(HALF_DAYS.items())}, "f17_window": "closed trailing [T-300 s, T] (Q9)",
                     "metrics": list(METRICS)}}
    man["unit_streams"] = [unit_facts(seed, u, k) for u, k in units]
    man["rate_streams"] = [dict(_digest_prints(stream_prints(seed, n)), n_requested=n)
                           for n in ((STREAM_SIZES[0],) if quick else STREAM_SIZES)]
    man["window_truth"] = [window_truth(seed, "SYN1", 21)] + ([] if quick else [window_truth(seed, "SYN2", 21)])
    man["trade_to_grid_truth"] = [grid_truth(seed, "SYN1", 21)] + ([] if quick else [grid_truth(seed, "SYN1", 1)])
    man["history_records"] = history_facts(seed, 60 if quick else 2000)
    man["rank_truth"] = rank_truth(seed, 50 if quick else 500)
    man["episodes"] = [episode_facts(seed, n) for n in ((500,) if quick else SERIES_COUNTS)]
    man["episode_stream"] = episode_stream_facts(seed, 100_000 if quick else EPISODE_POINTS_STREAM)
    cc = concentration_cases(seed, 20 if quick else CONC_CASES)
    man["concentration"] = {"cases": len(cc), "fired": sum(1 for x in cc if x["truth"]["fired"]),
                            "sha256": _dr(cc), "sample": cc[:3]}
    man["workload_facts_informational"] = {
        "frozen_fact": "print total per size-M unit <= %d (full day), prorated for half-days; PO ruling A1" % UNIT_PRINTS,
        "per_unit_total_ok": all(u["n"] == u["expected_n"] and u["n"] <= UNIT_PRINTS for u in man["unit_streams"]),
        "measured_count_stats_by_unit": {u["unit"]: u["count_stats"] for u in man["unit_streams"]},
        "note": "median and p99 per contract are measured generator facts, informational, no tolerance check"}
    man["half_day_sessions"] = {str(k): m for k, m in sorted(HALF_DAYS.items())}
    return man


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--quick", action="store_true", help="reduced manifest for smoke tests")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    man = build_manifest(a.seed, quick=a.quick)
    p = os.path.join(a.out, "m2_workload_manifest.json")
    with open(p, "w", newline="\n") as f:
        json.dump(man, f, indent=1, sort_keys=True)
        f.write("\n")
    print(p)


if __name__ == "__main__":
    main()
