"""S02b: zero points in a minute series are holes (R-195). A stored 0 in a minute series means "no value at that
minute": the grid may hold zeros in the contiguous int64 block, and `same_minute_column` (and any read of a minute
series) skips them; n counts only the non-zero points. Scalar series are unaffected (a scalar 0 is a real value).

Tests: semantics, layout (zero grids live in the block), text / binary round trip, a differential against an
independent pure-Python reference over >= 20,000 random grids, and a perf SMOKE check (H.best_of; not gate evidence).

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12
"""
import gc
import random
import statistics
import time
import unittest

import m3a_harness as H
from option_features import m3a_history as MH
from option_features.flowgrid import Calendar
from option_features.flowstore import HistoryStore

SID = "A/stock/iv30"


def _cal(n=40, minutes=12):
    return Calendar([("S%04d" % i, minutes) for i in range(n)])


def _read(st, cal, as_of, minute, **kw):
    return MH.same_minute_column(st, SID, "iv30", cal.ids[as_of], minute, **kw)


class Semantics(unittest.TestCase):
    def setUp(self):
        self.cal = _cal()
        self.st = HistoryStore(self.cal)
        self.st.add_series(SID, 252)

    def put(self, i, grid, **kw):
        self.st.append(SID, "iv30", 0, self.cal.ids[i], grid, **kw)

    def test_zero_is_skipped_and_n_counts_nonzero(self):
        for i in range(10):
            self.put(i, [0 if i in (2, 5, 9) else 100 + i] * 12)
        r = _read(self.st, self.cal, 10, 3, min_sessions=1)
        self.assertEqual(r.status, "available")
        self.assertEqual(list(r.value["sessions"]), [self.cal.ids[i] for i in (0, 1, 3, 4, 6, 7, 8)])
        self.assertEqual(list(r.value["values"]), [100, 101, 103, 104, 106, 107, 108])
        self.assertEqual(r.value["n"], 7)

    def test_min_sessions_counts_nonzero_only(self):
        for i in range(10):
            self.put(i, [0 if i < 4 else 7] * 12)
        self.assertEqual(_read(self.st, self.cal, 10, 0, min_sessions=6).status, "available")
        r = _read(self.st, self.cal, 10, 0, min_sessions=7)
        self.assertEqual((r.status, r.reason, r.value["n"]), ("unavailable", "insufficient_history", 6))

    def test_window_is_the_last_nonzero_sessions(self):
        for i in range(12):
            self.put(i, [0 if i in (10, 11) else i + 1] * 12)
        r = _read(self.st, self.cal, 12, 4, min_sessions=1, max_sessions=3)
        self.assertEqual(list(r.value["values"]), [8, 9, 10])        # sessions 7, 8, 9: the zeros do not use window slots
        self.assertEqual(list(r.value["sessions"]), [self.cal.ids[i] for i in (7, 8, 9)])

    def test_window_reaches_back_over_interleaved_zeros(self):
        for i in range(20):
            self.put(i, [0 if i % 2 else i + 1] * 12)
        r = _read(self.st, self.cal, 20, 0, min_sessions=1, max_sessions=4)
        self.assertEqual(list(r.value["values"]), [13, 15, 17, 19])
        self.assertEqual(list(r.value["sessions"]), [self.cal.ids[i] for i in (12, 14, 16, 18)])

    def test_all_zero_column_is_unavailable(self):
        for i in range(25):
            self.put(i, [0] * 12)
        r = _read(self.st, self.cal, 25, 5)
        self.assertEqual((r.status, r.reason, r.code, r.value), ("unavailable", "insufficient_history", None,
                                                                  {"values": None, "sessions": None, "n": 0}))
        r = _read(self.st, self.cal, 25, 5, min_sessions=1)
        self.assertEqual((r.status, r.reason, r.value["n"]), ("unavailable", "insufficient_history", 0))

    def test_single_nonzero(self):
        for i in range(25):
            self.put(i, [0] * 12 if i != 13 else [0] * 6 + [9] + [0] * 5)
        r = _read(self.st, self.cal, 25, 6, min_sessions=1)
        self.assertEqual((r.status, list(r.value["values"]), r.value["n"]), ("available", [9], 1))
        self.assertEqual(_read(self.st, self.cal, 25, 6).status, "unavailable")      # default min_sessions 20
        self.assertEqual(_read(self.st, self.cal, 25, 5, min_sessions=1).status, "unavailable")

    def test_zero_at_the_edges_of_the_grid(self):
        for i in range(21):
            self.put(i, [0] + [5] * 10 + [0])
        self.assertEqual(_read(self.st, self.cal, 21, 0).status, "unavailable")
        self.assertEqual(_read(self.st, self.cal, 21, 11).status, "unavailable")
        r = _read(self.st, self.cal, 21, 1)
        self.assertEqual((r.status, r.value["n"]), ("available", 21))
        r = _read(self.st, self.cal, 21, 10)
        self.assertEqual((r.status, r.value["n"]), ("available", 21))

    def test_incomplete_short_and_zero_together(self):
        for i in range(12):
            g = [3] * 6 if i == 4 else ([0] * 12 if i == 8 else [3 + i] * 12)
            self.put(i, g, complete=(i != 6))
        r = _read(self.st, self.cal, 12, 9, min_sessions=1)       # 4 is short, 6 incomplete, 8 zero at the minute
        self.assertEqual(list(r.value["sessions"]), [self.cal.ids[i] for i in (0, 1, 2, 3, 5, 7, 9, 10, 11)])
        self.assertEqual(list(r.value["values"]), [3 + i for i in (0, 1, 2, 3, 5, 7, 9, 10, 11)])

    def test_sparse_record_missing_and_explicit_zero_are_holes(self):
        for i in range(25):
            if i % 3 == 0:
                self.put(i, [7, 0, 7], grid_idx=[1, 4, 9])        # index 4 stored as 0, others missing (0)
            else:
                self.put(i, [4] * 12)
        r = _read(self.st, self.cal, 25, 4, min_sessions=1)
        self.assertEqual(r.value["n"], 16)
        r = _read(self.st, self.cal, 25, 1, min_sessions=1)
        self.assertEqual(r.value["n"], 25)

    def test_scalar_zero_is_a_value(self):
        st, cal = self.st, self.cal
        st.add_series("A/stock/iv30_close", 252)
        for i in range(25):
            st.append("A/stock/iv30_close", "iv30_close", 0, cal.ids[i], [], total=0 if i % 2 else i)
        r = MH.scalar_baseline(st, "A/stock/iv30_close", "iv30_close", cal.ids[25])
        self.assertEqual((r.status, r.value["n"]), ("available", 25))
        self.assertEqual(list(r.value["values"]), [0 if i % 2 else i for i in range(25)])

    def test_no_zero_is_unchanged(self):
        for i in range(25):
            self.put(i, [i + 1] * 12)
        r = _read(self.st, self.cal, 25, 3)
        self.assertEqual(list(r.value["values"]), [i + 1 for i in range(25)])


class Layout(unittest.TestCase):
    def test_zero_bearing_grids_live_in_the_block(self):
        cal = _cal()
        st = HistoryStore(cal)
        st.add_series(SID, 30)
        for i in range(10):
            st.append(SID, "iv30", 0, cal.ids[i], [0, 5, 0, 6, 7, 0, 8, 9, 0, 1, 2, 3])
        c = st.m3a_cols(SID, "iv30", 0)
        self.assertEqual(c.inb, [True] * 10)
        rec = st._rings[(SID, "iv30", 0)].recs[cal.ids[0]]
        self.assertEqual(len(rec.idx), 12)                         # dense, shared full index
        self.assertEqual(list(rec.vals), [0, 5, 0, 6, 7, 0, 8, 9, 0, 1, 2, 3])
        self.assertEqual(rec.total, 41)

    def test_all_zero_grid_is_legal_and_dense(self):
        cal = _cal()
        st = HistoryStore(cal)
        st.append(SID, "iv30", 0, cal.ids[0], [0] * 12)
        c = st.m3a_cols(SID, "iv30", 0)
        self.assertEqual((c.inb, c.tot), ([True], [0]))

    def test_round_trips_keep_holes_and_hash(self):
        cal = _cal(30)
        st = HistoryStore(cal)
        st.add_series(SID, 252)
        rnd = random.Random(5)
        for i in range(25):
            st.append(SID, "iv30", 0, cal.ids[i], [rnd.choice((0, 0, rnd.randrange(1, 10 ** 8))) for _ in range(12)])
        want = [_read(st, cal, 25, m, min_sessions=1) for m in range(12)]
        text = HistoryStore.load(st.dump(), cal, series_k={SID: 252})
        snap = HistoryStore.from_binary_snapshot(st.binary_snapshot(), cal)
        for other in (text, snap):
            self.assertEqual(other.content_hash(), st.content_hash())
            self.assertNotIn(False, other.m3a_cols(SID, "iv30", 0).inb)      # zero-bearing grids are in the block
            for m in range(12):
                got = _read(other, cal, 25, m, min_sessions=1)
                self.assertEqual((got.status, got.value), (want[m].status, want[m].value), m)

    def test_eviction_with_holes(self):
        cal = _cal(30)
        st = HistoryStore(cal)
        st.add_series(SID, 5)
        for i in range(17):
            st.append(SID, "iv30", 0, cal.ids[i], [0 if (i + m) % 3 == 0 else 10 * i + m for m in range(12)])
        for m in range(12):
            r = _read(st, cal, 17, m, min_sessions=1)
            exp = [(i, 10 * i + m) for i in range(12, 17) if (i + m) % 3 != 0]
            self.assertEqual(list(r.value["values"]) if r.value["values"] else [], [v for _, v in exp], m)


# ---- independent pure-Python reference -----------------------------------------------------------------------------

def reference(sessions, k, as_of_pos, minute, min_sessions, max_sessions):
    """sessions: list of (pos, complete, grid-as-dense-list) in append order. Returns (status, sessions, values, n).
    Written from the rule only: the last k appended are retained; take complete sessions before as_of whose grid has
    the minute and a non-zero value there; keep the last max_sessions; unavailable when fewer than min_sessions."""
    kept = sessions[-k:]
    out = []
    for pos, complete, grid in kept:
        if pos >= as_of_pos or not complete:
            continue
        if minute >= len(grid) or grid[minute] == 0:
            continue
        out.append((pos, grid[minute]))
    out = out[-max_sessions:]
    n = len(out)
    if n < min_sessions:
        return "unavailable", None, None, n
    return "available", [p for p, _ in out], [v for _, v in out], n


def _random_grid(rnd, length, kind):
    if kind == "allzero":
        return [0] * length
    if kind == "single":
        g = [0] * length
        g[rnd.randrange(length)] = rnd.randrange(1, 10 ** 8)
        return g
    if kind == "edges":
        g = [rnd.randrange(1, 100) for _ in range(length)]
        g[0] = 0
        g[-1] = 0
        return g
    if kind == "full":
        return [rnd.randrange(1, 10 ** 8) for _ in range(length)]
    p = rnd.choice((0.02, 0.1, 0.5, 0.9))
    return [0 if rnd.random() < p else rnd.randrange(1, 10 ** 8) for _ in range(length)]


KINDS = ("allzero", "single", "edges", "full", "mixed", "mixed", "mixed")


class Differential(unittest.TestCase):
    MIN_GRIDS = 20000

    def test_against_reference(self):
        rnd = random.Random(20261031)
        cal = Calendar([("S%03d" % i, 6 + (i % 3) * 3 if i % 11 == 5 else 9) for i in range(40)])
        grids = reads = zero_hits = 0
        seen = {"allzero": 0, "single": 0, "edges": 0}
        while grids < self.MIN_GRIDS:
            k = rnd.choice((1, 2, 3, 5, 8, 20))
            st = HistoryStore(cal)
            st.add_series(SID, k)
            n_sess = rnd.randrange(1, 15)
            pos = sorted(rnd.sample(range(30), n_sess))
            rows = []
            colkind = rnd.choice(KINDS)
            for p in pos:
                kind = colkind if rnd.random() < 0.7 else rnd.choice(KINDS)
                length = cal.minutes[p] if rnd.random() < 0.9 else rnd.randrange(1, cal.minutes[p] + 1)
                g = _random_grid(rnd, length, kind)
                seen[kind] = seen.get(kind, 0) + 1
                complete = rnd.random() < 0.85
                if rnd.random() < 0.15 and length:                  # sparse form of the same dense grid
                    idx = [m for m in range(length) if g[m]] or []
                    vals = [g[m] for m in idx]
                    if rnd.random() < 0.5 and idx:
                        idx.append(length - 1) if idx[-1] != length - 1 else None
                        vals = [g[m] for m in idx]
                    if idx and cal.minutes[p] >= length:
                        st.append(SID, "iv30", 0, cal.ids[p], vals, grid_idx=idx, complete=complete)
                        dense = [0] * cal.minutes[p]
                        for m, v in zip(idx, vals):
                            dense[m] = v
                        rows.append((p, complete, dense))
                        grids += 1
                        continue
                st.append(SID, "iv30", 0, cal.ids[p], g, complete=complete)
                rows.append((p, complete, g))
                grids += 1
            for _ in range(6):
                as_of = rnd.randrange(0, 30)
                minute = rnd.randrange(0, cal.minutes[as_of])
                mn = rnd.choice((1, 1, 2, 3, 20))
                mx = rnd.choice((mn, mn + 1, mn + 3, 252))
                want = reference(rows, k, as_of, minute, mn, mx)
                got = MH.same_minute_column(st, SID, "iv30", cal.ids[as_of], minute, min_sessions=mn, max_sessions=mx)
                gv = got.value
                have = (got.status, None if gv["sessions"] is None else [cal.position(s) for s in gv["sessions"]],
                        None if gv["values"] is None else list(gv["values"]), gv["n"])
                self.assertEqual(have, want, (rows, k, as_of, minute, mn, mx))
                reads += 1
                zero_hits += any(len(g) > minute and g[minute] == 0 for p, c, g in rows if p < as_of)
        self.assertGreaterEqual(grids, self.MIN_GRIDS)
        self.assertGreater(zero_hits, 1000)
        self.assertTrue(all(v > 100 for v in seen.values()), seen)
        print("\nS02b differential: %d grids, %d reads, %d reads with a zero in range, kinds %s" % (grids, reads,
                                                                                                    zero_hits, seen))


# ---- perf SMOKE (not gate evidence; GATE_BUDGETS section 8 rule 7) ---------------------------------------------------

NAMES, SESSIONS, GRID = 20, 252, 390


def _store(zero_pct, seed=3):
    cal = Calendar([("S%04d" % i, GRID) for i in range(SESSIONS + 1)])
    st = HistoryStore(cal)
    rnd = random.Random(seed)
    for n in range(NAMES):
        sid = "N%03d/stock/iv30" % n
        st.add_series(sid, 252)
        for i in range(SESSIONS):
            g = [rnd.randrange(10 ** 6, 10 ** 8) for _ in range(GRID)]
            if zero_pct:
                for m in range(GRID):
                    if rnd.random() < zero_pct / 100:
                        g[m] = 0
            st.append(sid, "iv30", 0, cal.ids[i], g)
    return st, cal


class PerfSmoke(unittest.TestCase):
    """Developer SMOKE check: best of up to 3 samples, budgets as GATE_BUDGETS section 5 (B5 p95 75 us per call hole-free;
    V3 150 us), ratio <= 1.3 of the hole-free read. The 30-repeat fresh-process figures belong to the Tester."""

    def test_zero_bearing_read_cost(self):
        clean, cal = _store(0)
        holey, _ = _store(3)
        as_of = cal.ids[SESSIONS]

        def per_call(st):
            fn = lambda n: MH.same_minute_column(st, "N%03d/stock/iv30" % n, "iv30", as_of, 195)
            for n in range(NAMES):
                fn(n)
            calls = []
            gc.disable()
            try:
                for _ in range(30):
                    for n in range(NAMES):
                        t0 = time.perf_counter()
                        fn(n)
                        calls.append(time.perf_counter() - t0)
            finally:
                gc.enable()
            calls.sort()
            return calls[len(calls) // 2], calls[int(0.95 * len(calls)) - 1]

        def sample():
            return per_call(clean), per_call(holey)

        def merge(a, b):
            return tuple(min(x, y, key=lambda t: t[1]) for x, y in zip(a, b))

        def ok(r):
            (c50, c95), (h50, h95) = r
            return c95 <= H.B5_MINUTE_CALL_S and h50 <= 150e-6 and h50 / c50 <= 1.3
        ((c50, c95), (h50, h95)), used = H.best_of(sample, merge, ok)
        print("\nS02b read smoke best of %d (used %d), synthetic workload, relative engineering budget: hole-free p50 %.1f us "
              "p95 %.1f us (<= 75 us); 3%% zeros p50 %.1f us p95 %.1f us (<= 150 us); ratio %.2f (<= 1.3)"
              % (H.SMOKE_TRIES, used, c50 * 1e6, c95 * 1e6, h50 * 1e6, h95 * 1e6, h50 / c50))
        self.assertLessEqual(c95, H.B5_MINUTE_CALL_S)
        self.assertLessEqual(h50, 150e-6)
        self.assertLessEqual(h50 / c50, 1.3)


if __name__ == "__main__":
    unittest.main()
