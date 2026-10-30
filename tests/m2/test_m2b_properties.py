"""Property tests for the M2 story B print-window families against an independent Fraction reference.

The reference below is written from the matrix text with plain loops and `fractions.Fraction`; it shares no code
with the library (only the module under test is imported). Random streams include ties on one timestamp,
zero sizes, zero prices, nonstandard multipliers, excluded conditions, two lanes, both rights, text and tick
prices and an optional side element. Cutoffs sit on and around window boundaries.

Label: synthetic workload, relative engineering budget (no claim about recorded data). Synthetic fixtures only.
"""
import os
import random
import unittest
from fractions import Fraction

from option_features import episodes as E, m2prints as M, printtape as PT

NS = 1_000_000_000
OPEN = 1_790_000_000 * NS
LANES = ("stock", "etf_index")


def make_contracts(rng):
    cons = {}
    n = 0
    for lane in LANES:
        for right in "CP":
            for strike in (1_000_000, 1_050_000, 1_100_000):
                for expiry in ("2026-11-20", "2026-12-18", "2027-01-15"):
                    if rng.random() < 0.55:
                        cons["K%d" % n] = (right, strike, expiry, lane)
                        n += 1
    return cons


def make_prints(rng, cons, n, span_s, text_prices=True, ties=True):
    ids = sorted(cons)
    t = OPEN + rng.randrange(0, 5) * NS
    rows = []
    seq = 0
    for _ in range(n):
        if not (ties and rng.random() < 0.12):
            t += rng.choice((0, 1, 7, NS // 3, NS, 3 * NS, 29 * NS, 61 * NS)) * rng.choice((1, 1, 1, 4))
        t = min(t, OPEN + span_s * NS)
        price = rng.choice((0, 1, 55, 100, 12_345, 250_000, 999_999, 1_000_000, 5_000_000))
        size = rng.choice((0, 1, 1, 2, 5, 10, 50, 1000))
        mult = 100 if rng.random() < 0.9 else rng.choice((10, 50, 1000))
        excl = rng.random() < 0.06
        pr = price
        if text_prices and rng.random() < 0.5:
            pr = "%d.%04d" % (price // 10000, price % 10000)
        row = (rng.choice(ids), t, pr, size, mult, excl, seq)
        if rng.random() < 0.3:
            row += (rng.choice(("ask", "bid", "unknown")),)
        rows.append(row)
        seq += 1
    return rows


def tick(p):
    if isinstance(p, int):
        return p
    w, f = p.split(".")
    return int(w) * 10000 + int(f)


# ------------------------------------------------------------------------------------------ reference
def ref_collect(prints, cons, lane, flt, start, end, only=None):
    rows, nonstd, excl_n = [], 0, 0
    for p in prints:
        cid, t, price, size, mult, excl = p[:6]
        if not (start <= t <= end):
            continue
        right, strike, expiry, ln = cons[cid]
        if ln != lane or (flt == "calls" and right != "C") or (flt == "puts" and right != "P"):
            continue
        if only is not None and cid != only:
            continue
        if excl:
            excl_n += 1
            continue
        if mult != 100:
            nonstd += 1
            continue
        rows.append({"cid": cid, "prem": Fraction(tick(price)) * size * mult, "size": size, "right": right,
                     "strike": strike, "expiry": expiry})
    return rows, nonstd, excl_n


def ref_cov(n, nonstd, excl_n):
    return {"eligible_count": n, "nonstandard_count": nonstd, "excluded_condition_count": excl_n,
            "unavailable_points": 0}


def ref_f1_numbers(prints, cons, lane, flt, T):
    r60, _, _ = ref_collect(prints, cons, lane, flt, T - 60 * NS, T)
    r900, nn, nx = ref_collect(prints, cons, lane, flt, T - 900 * NS, T)
    return sum(r["prem"] for r in r60), sum(r["prem"] for r in r900), ref_cov(len(r900), nn, nx)


def ref_f1(prints, cons, lane, flt, T, N):
    if T - OPEN < 900 * NS:
        return ("unavailable", "insufficient_window", None, None, None)
    p60, p900, cv = ref_f1_numbers(prints, cons, lane, flt, T)
    if p900 == 0:
        return ("unavailable", "zero_denominator", None, None, cv)
    ratio = Fraction(15) * p60 / p900
    return ("available", None, (int(p60), int(p900), ratio), ratio >= Fraction(N), cv)


def got_f1(r):
    if r["status"] != "available":
        return (r["status"], r["reason"], None, None, r["coverage"])
    v = r["value"]
    return ("available", None, (v["p60"], v["p900"], v["ratio"]), r["fired"], r["coverage"])


def ref_f4(prints, cons, lane, T, W, thr, N):
    rows, nn, nx = ref_collect(prints, cons, lane, "all", T - W * NS, T)
    big = [r for r in rows if r["prem"] >= thr]
    return ({"large_count": len(big), "large_premium": int(sum(r["prem"] for r in big))}, len(big) >= N,
            ref_cov(len(rows), nn, nx))


def ref_f17(prints, cons, lane, T, cid, thr):
    rows, nn, nx = ref_collect(prints, cons, lane, "all", T - 300 * NS, T, only=cid)
    s = sum(r["prem"] for r in rows)
    return {"window_premium": int(s)}, s >= thr, ref_cov(len(rows), nn, nx)


def ref_f7(prints, cons, lane, T, W, th):
    rows, nn, nx = ref_collect(prints, cons, lane, "all", T - W * NS, T)
    total = sum(r["prem"] for r in rows)
    cv = ref_cov(len(rows), nn, nx)
    if total == 0:
        return None, None, cv
    st, ex = {}, {}
    for r in rows:
        st[r["strike"]] = st.get(r["strike"], 0) + r["prem"]
        ex[r["expiry"]] = ex.get(r["expiry"], 0) + r["prem"]
    ts = sorted(st, key=lambda k: (-st[k], k))[0]
    te = sorted(ex, key=lambda k: (-ex[k], k))[0]
    ss, es = st[ts] / total, ex[te] / total
    return ({"top_strike": ts, "strike_share": ss, "top_expiry": te, "expiry_share": es,
             "total_premium": int(total)}, ss >= th or es >= th, cv)


def ref_f18(prints, cons, lane, T, W, al, am):
    rows, nn, nx = ref_collect(prints, cons, lane, "all", T - W * NS, T)
    put = sum(r["size"] for r in rows if r["right"] == "P")
    call = sum(r["size"] for r in rows if r["right"] == "C")
    cv = ref_cov(len(rows), nn, nx)
    if put + call == 0:
        return None, None, cv
    share = Fraction(put, put + call)
    fired = (al is not None and share >= al) or (am is not None and share <= am)
    return ({"put_volume": put, "call_volume": call, "put_share": share,
             "put_call_ratio": None if call == 0 else Fraction(put, call)}, fired, cv)


def ref_f12(prints, cons, lane, flt, T, N, n_episodes, gap):
    """Plain loop state machine written from the rule text, F1 recomputed by brute force at every grid point."""
    if T - OPEN < 900 * NS:
        return None
    last = (T - OPEN) // (60 * NS)
    fired_seq, ratios = [], []
    for k in range(last + 1):
        if k < 15:
            fired_seq.append(None)
            ratios.append(None)
            continue
        Tk = OPEN + k * 60 * NS
        p60, p900, _ = ref_f1_numbers(prints, cons, lane, flt, Tk)
        if p900 == 0:
            fired_seq.append(None)
            ratios.append(None)
        else:
            r = Fraction(15) * p60 / p900
            ratios.append(r)
            fired_seq.append(r >= N)
    episodes = []
    run_quiet = None            # None = not inside an episode
    for k, f in enumerate(fired_seq):
        if f:
            if run_quiet is None:
                episodes.append(k)
            run_quiet = 0
        elif run_quiet is not None:
            run_quiet += 1
            if run_quiet >= gap:
                run_quiet = None
    avail = [(r, k) for k, r in enumerate(ratios) if r is not None]
    peak = None
    for r, k in avail:
        if peak is None or r > peak[0]:
            peak = (r, k)
    return {"episode_count": len(episodes),
            "first_ns": None if not episodes else OPEN + episodes[0] * 60 * NS,
            "last_ns": None if not episodes else OPEN + episodes[-1] * 60 * NS,
            "peak_ratio": None if peak is None else peak[0],
            "peak_ns": None if peak is None else OPEN + peak[1] * 60 * NS,
            "unavailable_points": last + 1 - len(avail), "quiet_gap": gap}, len(episodes) >= n_episodes


def cutoffs_for(rng, prints, count):
    ts = sorted({p[1] for p in prints})
    out = [OPEN + 899 * NS, OPEN + 900 * NS, OPEN + 901 * NS, OPEN + 30 * NS]
    for _ in range(count):
        base = rng.choice(ts)
        out.append(base + rng.choice((0, 0, 1, -1, 60 * NS, -60 * NS, 300 * NS, 900 * NS, -900 * NS, 3600 * NS)))
    out.append(ts[-1] + 3 * NS)
    return [t for t in out if t > OPEN - 10 * NS]


class Scenario:
    def __init__(self, seed, n=260, span_s=5400):
        rng = random.Random(seed)
        self.rng = rng
        self.cons = make_contracts(rng)
        self.prints = make_prints(rng, self.cons, n, span_s)
        self.tape = PT.build_tape(self.prints, self.cons)
        self.cuts = cutoffs_for(rng, self.prints, 14)


SEEDS = range(1, 1 + int(os.environ.get("M2B_SEEDS", "24")))


class FamiliesAgainstReference(unittest.TestCase):
    def test_f1(self):
        for seed in SEEDS:
            sc = Scenario(seed)
            for lane in LANES:
                for flt in ("all", "calls", "puts"):
                    for N in (1, 2, 3, "7/2"):
                        sweep = M.f1_sweep(sc.tape, sc.cuts, OPEN, n=N, flt=flt, lane=lane)
                        for T, sw in zip(sc.cuts, sweep):
                            want = ref_f1(sc.prints, sc.cons, lane, flt, T, Fraction(N))
                            one = M.f1_premium_surge(sc.tape, T, OPEN, n=N, flt=flt, lane=lane)
                            self.assertEqual(got_f1(one), want, (seed, lane, flt, N, T))
                            self.assertEqual(M.canonical_line(sw), M.canonical_line(one))

    def test_f4(self):
        for seed in SEEDS:
            sc = Scenario(seed)
            for W in (60, 300, 900, 3600):
                for thr in (1, 100_000, 1_000_000_000, 5_000_000_000):
                    for N in (1, 2):
                        sweep = M.f4_sweep(sc.tape, sc.cuts, window_s=W, threshold_ticks=thr, n=N, lane="stock")
                        for T, sw in zip(sc.cuts, sweep):
                            want = ref_f4(sc.prints, sc.cons, "stock", T, W, thr, N)
                            one = M.f4_large_prints(sc.tape, T, window_s=W, threshold_ticks=thr, n=N, lane="stock")
                            self.assertEqual((one["value"], one["fired"], one["coverage"]), want, (seed, W, thr, T))
                            self.assertEqual(M.canonical_line(sw), M.canonical_line(one))

    def test_f17(self):
        for seed in SEEDS:
            sc = Scenario(seed)
            for lane in LANES:
                for thr in (1, 5_000_000, 1_000_000_000):
                    ids = sorted(sc.cons)
                    sweep = M.f17_sweep(sc.tape, sc.cuts, ids, threshold_ticks=thr, lane=lane)
                    cols = M.f17_sweep_columns(sc.tape, sc.cuts, ids, lane=lane)
                    for T, sw, col in zip(sc.cuts, sweep, cols):
                        self.assertEqual(col, [r["value"]["window_premium"] for r in sw])
                        self.assertEqual(M.f17_columns(sc.tape, T, ids, lane=lane), col)
                        many = M.f17_many(sc.tape, T, ids, threshold_ticks=thr, lane=lane)
                        self.assertEqual([M.canonical_line(r) for r in sw], [M.canonical_line(r) for r in many])
                        for cid, r in zip(ids, many):
                            want = ref_f17(sc.prints, sc.cons, lane, T, cid, thr)
                            self.assertEqual((r["value"], r["fired"], r["coverage"]), want, (seed, cid, T))
                            one = M.f17_window_premium(sc.tape, T, cid, threshold_ticks=thr, lane=lane)
                            self.assertEqual(M.canonical_line(one), M.canonical_line(r))

    def test_f7(self):
        for seed in SEEDS:
            sc = Scenario(seed)
            for W in (60, 300, 3600):
                for th in ("3/5", "1/10", "1"):
                    sweep = M.f7_sweep(sc.tape, sc.cuts, window_s=W, share_threshold=th, lane="stock")
                    for T, sw in zip(sc.cuts, sweep):
                        want = ref_f7(sc.prints, sc.cons, "stock", T, W, Fraction(th))
                        one = M.f7_concentration(sc.tape, T, window_s=W, share_threshold=th, lane="stock")
                        if want[0] is None:
                            self.assertEqual((one["status"], one["reason"], one["coverage"]),
                                             ("unavailable", "zero_denominator", want[2]))
                        else:
                            self.assertEqual((one["value"], one["fired"], one["coverage"]), want, (seed, W, T))
                        self.assertEqual(M.canonical_line(sw), M.canonical_line(one))

    def test_f18(self):
        for seed in SEEDS:
            sc = Scenario(seed)
            for W in (60, 300, 3600):
                for al, am in (("1/2", None), (None, "1/3"), ("3/5", "1/5"), ("1", "0")):
                    sweep = M.f18_sweep(sc.tape, sc.cuts, window_s=W, at_least=al, at_most=am, lane="etf_index")
                    for T, sw in zip(sc.cuts, sweep):
                        want = ref_f18(sc.prints, sc.cons, "etf_index", T, W, None if al is None else Fraction(al),
                                       None if am is None else Fraction(am))
                        one = M.f18_put_share(sc.tape, T, window_s=W, at_least=al, at_most=am, lane="etf_index")
                        if want[0] is None:
                            self.assertEqual((one["status"], one["reason"], one["coverage"]),
                                             ("unavailable", "zero_denominator", want[2]))
                        else:
                            self.assertEqual((one["value"], one["fired"], one["coverage"]), want, (seed, W, T))
                        self.assertEqual(M.canonical_line(sw), M.canonical_line(one))

    def test_f12(self):
        for seed in range(1, 1 + min(8, len(SEEDS))):
            sc = Scenario(seed, n=500, span_s=4200)
            ends = [OPEN + s * NS for s in (899, 900, 1500, 2399, 2400, 4200)]
            for lane in LANES:
                for gap in (1, 2, 5):
                    for N, ne in ((1, 1), (2, 2), (3, 1)):
                        for T in ends:
                            got = E.f12_from_tape(sc.tape, T, OPEN, n=N, n_episodes=ne, quiet_gap=gap, lane=lane)
                            want = ref_f12(sc.prints, sc.cons, lane, "all", T, Fraction(N), ne, gap)
                            if want is None:
                                self.assertEqual((got["status"], got["reason"]), ("unavailable", "insufficient_window"))
                                continue
                            self.assertEqual((got["value"], got["fired"]), want, (seed, lane, gap, N, T))
                            p60, p900 = E.f1_grid_columns(sc.tape, OPEN, (T - OPEN) // (60 * NS), "all", lane)
                            from_pts = E.f12_episodes(p60, p900, T, OPEN, n=N, n_episodes=ne, quiet_gap=gap, lane=lane)
                            self.assertEqual(from_pts["value"], got["value"])
                            self.assertEqual(from_pts["fired"], got["fired"])


class Determinism(unittest.TestCase):
    def test_tie_order_and_arrival_do_not_change_results(self):
        for seed in range(1, 9):
            sc = Scenario(seed, n=300, span_s=3000)
            rng = random.Random(seed * 77)
            prints = list(sc.prints)
            i, out = 0, []
            while i < len(prints):          # shuffle runs of equal timestamps, reassign seq in the new order
                j = i
                while j < len(prints) and prints[j][1] == prints[i][1]:
                    j += 1
                run = prints[i:j]
                rng.shuffle(run)
                out.extend(run)
                i = j
            out = [p[:6] + (k,) + p[7:] for k, p in enumerate(out)]
            tape2 = PT.build_tape(out, sc.cons)
            self.assertIsNone(tape2.error)
            for T in sc.cuts:
                for fn in (lambda t, T: M.canonical_line(M.f1_premium_surge(t, T, OPEN)),
                           lambda t, T: M.canonical_line(M.f4_large_prints(t, T, threshold_ticks=5_000_000)),
                           lambda t, T: M.canonical_line(M.f7_concentration(t, T)),
                           lambda t, T: M.canonical_line(M.f18_put_share(t, T, at_least="1/2")),
                           lambda t, T: [M.canonical_line(r) for r in M.f17_many(t, T)]):
                    a, b = fn(sc.tape, T), fn(tape2, T)
                    if isinstance(a, list):
                        a, b = sorted(a), sorted(b)
                    self.assertEqual(a, b)

    def test_sweep_order_and_duplicates_do_not_matter(self):
        sc = Scenario(3)
        base = M.f7_sweep(sc.tape, sc.cuts)
        rev = M.f7_sweep(sc.tape, sc.cuts[::-1])[::-1]
        dup = M.f7_sweep(sc.tape, sc.cuts + sc.cuts[:5])[:len(sc.cuts)]
        self.assertEqual([M.canonical_line(r) for r in base], [M.canonical_line(r) for r in rev])
        self.assertEqual([M.canonical_line(r) for r in base], [M.canonical_line(r) for r in dup])
        a = M.f17_sweep(sc.tape, sc.cuts)
        b = M.f17_sweep(sc.tape, sc.cuts[::-1])[::-1]
        self.assertEqual([[M.canonical_line(r) for r in x] for x in a], [[M.canonical_line(r) for r in x] for x in b])

    def test_lane_isolation(self):
        sc = Scenario(5)
        keep = {c: v for c, v in sc.cons.items() if v[3] == "stock"}
        only = [p for p in sc.prints if p[0] in keep]
        tape_only = PT.build_tape(only, keep)
        for T in sc.cuts:
            self.assertEqual(M.canonical_line(M.f7_concentration(tape_only, T)),
                             M.canonical_line(M.f7_concentration(sc.tape, T)))
            self.assertEqual(M.canonical_line(M.f18_put_share(tape_only, T, at_most="1")),
                             M.canonical_line(M.f18_put_share(sc.tape, T, at_most="1")))


class Units(unittest.TestCase):
    def test_ticks4(self):
        self.assertEqual(PT.ticks4("80.0000"), 800000)
        self.assertEqual(PT.ticks4("80"), 800000)
        self.assertEqual(PT.ticks4("0.0001"), 1)
        self.assertEqual(PT.ticks4("-0.5"), -5000)
        self.assertEqual(PT.ticks4("1.50000"), 15000)
        self.assertEqual(PT.ticks4(123), 123)
        self.assertEqual(PT.ticks4(Fraction(3, 2)), 15000)
        with self.assertRaises(ValueError):
            PT.ticks4("1.00001")

    def test_structural_precedence_and_validate_off(self):
        cons = {"A": ("C", 1, "2026-11-20", "stock")}
        both = [("A", 20, "1.0000", 5, 100, 0, 0), ("A", 10, "-1.0000", 5, 0, 0, 1)]
        self.assertEqual(PT.build_tape(both, cons).error, "unordered_prints")
        neg_mult = [("A", 10, "-1.0000", 5, 0, 0, 0)]
        self.assertEqual(PT.build_tape(neg_mult, cons).error, "negative_size_or_price")
        self.assertIsNone(PT.build_tape(both, cons, validate="off").error)
        self.assertEqual(PT.build_tape([("Z", 1, 1, 1, 100, 0, 0)], cons).error, "unknown_contract")
        self.assertEqual(PT.build_tape([("A", 1, "1.00001", 1, 100, 0, 0)], cons).error, "malformed_type")
        self.assertEqual(PT.build_tape([("Z", 1, "x", 1, 100, 0, 0)], cons).error, "unknown_contract")
        self.assertEqual(PT.build_tape([("A", 1, "1.0", 1, 0, 0, 0), ("Z", 2, 1, 1, 100, 0, 1)], cons).error, "bad_multiplier")
        r = M.f4_large_prints(PT.build_tape([("Z", 1, 1, 1, 100, 0, 0)], cons), 5)
        self.assertEqual((r["status"], r["code"], r["version"]), ("invalid_input", "unknown_contract", "0.2.0a1"))
        r = M.f18_put_share(PT.build_tape([("A", 1, "1.00001", 1, 100, 0, 0)], cons), 5, at_least="1/2")
        self.assertEqual((r["status"], r["code"]), ("invalid_input", "malformed_type"))
        with self.assertRaises(ValueError):
            PT.build_tape([], cons).select("stock", "bogus")

    def test_f12_parameter_validation(self):
        for kw in ({"quiet_gap": 0}, {"n_episodes": 0}, {"grid_s": 30}):
            with self.assertRaises(ValueError):
                E.f12_episodes([], [], OPEN + 1000 * NS, OPEN, **kw)

    def test_f12_early_points_are_never_available_and_missing_points_count(self):
        T = OPEN + 1200 * NS                      # grid points 0..20
        r = E.f12_episodes([3000] * 21, [15000] * 21, T, OPEN, n=3)
        self.assertEqual(r["value"]["unavailable_points"], 15)       # points 0..14 are before open + 900 s
        self.assertEqual(r["value"]["first_ns"], OPEN + 15 * 60 * NS)
        self.assertEqual(r["value"]["episode_count"], 1)
        short = E.f12_episodes([None] * 15 + [3000, 1000], [None] * 15 + [15000, 15000], T, OPEN, n=3)
        self.assertEqual(short["value"]["unavailable_points"], 19)   # 15 early + 4 missing of 21
        self.assertEqual(short["value"]["peak_ns"], OPEN + 15 * 60 * NS)
        zero = E.f12_episodes([5] * 21, [0] * 21, T, OPEN, n=3)      # P900 = 0 is unavailable at every point
        self.assertEqual((zero["value"]["episode_count"], zero["value"]["unavailable_points"],
                          zero["value"]["peak_ratio"], zero["value"]["peak_ns"], zero["fired"]), (0, 21, None, None, False))

    def test_canonical_line_shape(self):
        sc = Scenario(2)
        line = M.canonical_line(M.f1_premium_surge(sc.tape, OPEN + 2000 * NS, OPEN))
        self.assertTrue(line.endswith("\n") and " " not in line.strip())
        self.assertTrue(line.startswith('{"output_id":"M2-1","series_id":null'))

    def test_empty_tape(self):
        tape = PT.build_tape([], {})
        r = M.f4_large_prints(tape, OPEN + 1000 * NS)
        self.assertEqual((r["status"], r["value"]["large_count"]), ("available", 0))
        self.assertEqual(M.f1_premium_surge(tape, OPEN + 1000 * NS, OPEN)["reason"], "zero_denominator")
        self.assertEqual(M.f17_many(tape, OPEN + 1000 * NS, ["X"])[0]["value"]["window_premium"], 0)


if __name__ == "__main__":
    unittest.main()
