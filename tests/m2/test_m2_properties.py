"""Property tests (story A) against an independent Fraction reference: grid builder, window totals, history store,
percentile and baseline kernels, batched/fused/cached paths, canonical text, the Tester's differential stream.

The reference here is deliberately naive (per-point, per-print loops with Fractions and sorted lists) and shares no
code with the library. Developer evidence only; the independent Tester must re-run. Synthetic data only.
"""
import hashlib
import json
import os
import random
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import m2_adapter  # noqa: F401  (puts the fixtures directory on sys.path through its loader)

NS = 10 ** 9
G = 60 * NS
OPEN0 = 1790000000 * NS


def lib():
    from option_features import flowgrid, flowrank, flowresult, flowstore
    return flowgrid, flowstore, flowrank, flowresult


# ------------------------------------------------------------------ reference model (Fractions, naive loops)
def ref_eligible(prints, contracts, lane):
    out = []
    for p in prints:
        c = contracts[p[0]]
        if c.lane != lane or p[5] or p[4] != 100:
            continue
        out.append((p[1], p[2] * p[3] * p[4], p[3], c.right, p[0]))
    return out


def ref_grid(prints, contracts, lane, open_ns, minutes, W, cid=None, right=None):
    pts = ref_eligible(prints, contracts, lane)
    res = {"premium": [], "contracts": [], "prints": [], "put_volume": [], "call_volume": []}
    for i in range(minutes):
        t_i = open_ns + G * i
        sel = [q for q in pts if t_i - W * NS <= q[0] <= t_i and (cid is None or q[4] == cid)]
        res["premium"].append(sum(q[1] for q in sel))
        res["contracts"].append(sum(q[2] for q in sel))
        res["prints"].append(len(sel))
        res["put_volume"].append(sum(q[2] for q in sel if q[3] == "P"))
        res["call_volume"].append(sum(q[2] for q in sel if q[3] == "C"))
    return res


def rand_world(rng, ncontracts=6):
    flowgrid = lib()[0]
    contracts = {}
    for i in range(ncontracts):
        contracts["K%d" % i] = flowgrid.Contract(rng.choice("CP"), 1000000 + 10000 * i, "2026-12-18",
                                                 rng.choice(["stock", "stock", "stock", "etf_index"]), "SYN1")
    return contracts


def rand_prints(rng, contracts, open_ns, minutes, n, edge=True):
    """Random sorted prints inside [open, close], many exactly on grid or window boundaries."""
    ps = []
    for _ in range(n):
        r = rng.random()
        if edge and r < 0.35:
            t = open_ns + G * rng.randrange(0, minutes + 1) - rng.choice([0, 0, 0, 1, 60 * NS, 300 * NS, 301 * NS, 299 * NS + 1])
        else:
            t = open_ns + rng.randrange(0, minutes * G + 1)
        t = max(open_ns, min(t, open_ns + minutes * G))
        mult = rng.choice([100, 100, 100, 100, 10, 1])
        ps.append([rng.choice(list(contracts)), t, rng.randrange(0, 40) * 100 if rng.random() < 0.9 else rng.randrange(1, 9) * 10000,
                   rng.randrange(0, 30), mult, 1 if rng.random() < 0.1 else 0])
    ps.sort(key=lambda p: p[1])
    return [tuple(p) + (i,) for i, p in enumerate(ps)]


def dense(rec):
    g = [0] * rec.minutes
    for i, v in zip(rec.idx, rec.vals):
        g[i] = v
    return g


class GridBuilder(unittest.TestCase):
    def test_builder_equals_bruteforce(self):
        flowgrid = lib()[0]
        rng = random.Random(1)
        for trial in range(60):
            contracts = rand_world(rng)
            minutes = rng.choice([1, 2, 7, 20, 41])
            open_ns = OPEN0 + rng.randrange(0, 5) * NS // 2
            ps = rand_prints(rng, contracts, open_ns, minutes, rng.choice([0, 1, 5, 40, 120]))
            windows = rng.choice([(60,), (300,), (60, 300, 900)])
            lane = rng.choice(["stock", "etf_index"])
            close = open_ns + minutes * G
            b = flowgrid.build_session_records(ps, contracts, "2026-01-05", open_ns, close, minutes, windows, lane, "N1", True, "full")
            by = {(r.series_id, r.metric, r.window_s): r for r in b.records}
            for W in windows:
                for sid, cid in [("N1", None)] + [(c, c) for c in contracts if contracts[c].lane == lane]:
                    ref = ref_grid(ps, contracts, lane, open_ns, minutes, W, cid)
                    metrics = ("premium", "contracts", "prints", "put_volume", "call_volume") if cid is None else ("premium", "contracts", "prints")
                    elig = [q for q in ref_eligible(ps, contracts, lane) if (cid is None or q[4] == cid) and open_ns <= q[0] <= close]
                    tot = {"premium": sum(q[1] for q in elig), "contracts": sum(q[2] for q in elig), "prints": len(elig),
                           "put_volume": sum(q[2] for q in elig if q[3] == "P"), "call_volume": sum(q[2] for q in elig if q[3] == "C")}
                    if cid is not None and not elig:
                        self.assertNotIn((sid, "premium", W), by, "contract without eligible prints must have no series")
                        continue
                    for m in metrics:
                        rec = by[(sid, m, W)]
                        self.assertEqual(dense(rec), ref[m], (trial, sid, m, W))
                        self.assertEqual(rec.total, tot[m], (trial, sid, m, W))
                        self.assertTrue(all(v > 0 for v in rec.vals) and list(rec.idx) == sorted(set(rec.idx)))
            cond = sum(1 for p in ps if open_ns <= p[1] <= close and contracts[p[0]].lane == lane and p[5])
            non = sum(1 for p in ps if open_ns <= p[1] <= close and contracts[p[0]].lane == lane and not p[5] and p[4] != 100)
            self.assertEqual((b.excluded_condition_count, b.nonstandard_count), (cond, non))
            self.assertEqual(b.eligible_count, len([1 for q in ref_eligible(ps, contracts, lane) if open_ns <= q[0] <= close]))

    def test_window_totals_equal_bruteforce(self):
        flowgrid = lib()[0]
        rng = random.Random(2)
        for trial in range(200):
            contracts = rand_world(rng)
            open_ns = OPEN0
            ps = rand_prints(rng, contracts, open_ns, 30, rng.choice([0, 3, 30, 90]))
            T = open_ns + rng.randrange(0, 31) * G + rng.choice([0, 0, 1, -1])
            W = rng.choice([60, 300, 900])
            lane = rng.choice(["stock", "etf_index"])
            flt = rng.choice(["all", "calls", "puts"])
            tot = flowgrid.window_totals(ps, contracts, T, W, lane, flt, "full")
            sc = flowgrid.window_totals(ps, contracts, T, W, lane, flt, "scanned")
            self.assertEqual(tot, sc)
            want = {"all": "CP", "calls": "C", "puts": "P"}[flt]
            win = [p for p in ps if T - W * NS <= p[1] <= T and contracts[p[0]].lane == lane and contracts[p[0]].right in want]
            el = [p for p in win if not p[5] and p[4] == 100]
            self.assertEqual(tot.premium, sum(p[2] * p[3] * 100 for p in el))
            self.assertEqual(tot.volume, sum(p[3] for p in el))
            self.assertEqual(tot.count, len(el))
            self.assertEqual(tot.put_volume, sum(p[3] for p in el if contracts[p[0]].right == "P"))
            self.assertEqual(tot.excluded_condition_count, sum(1 for p in win if p[5]))
            self.assertEqual(tot.nonstandard_count, sum(1 for p in win if not p[5] and p[4] != 100))

    def test_check_prints_precedence(self):
        flowgrid = lib()[0]
        ok = ("K0", 5, "1.0000", 1, 100, 0, 0)
        self.assertIsNone(flowgrid.check_prints([ok]))
        self.assertEqual(flowgrid.check_prints([("K0", 6, "1.0000", 1, 100, 0, 0), ("K0", 5, "-1.0000", 1, 0, 0, 1)]), "unordered_prints")
        self.assertEqual(flowgrid.check_prints([("K0", 5, "-1.0000", 1, 0, 0, 0)]), "negative_size_or_price")
        self.assertEqual(flowgrid.check_prints([("K0", 5, "1.0000", -1, 0, 0, 0)]), "negative_size_or_price")
        self.assertEqual(flowgrid.check_prints([("K0", 5, "1.0000", 1, 0, 0, 0)]), "bad_multiplier")
        self.assertEqual(flowgrid.check_prints([("K0", 5, 100, 1, -3, 0, 0)]), "bad_multiplier")
        self.assertEqual(flowgrid.check_prints([("K0", 5, "-0.0000", 1, 100, 0, 0)]), None)
        self.assertEqual(flowgrid.price_ticks("12.3"), 123000)
        self.assertRaises(ValueError, flowgrid.price_ticks, "1.00001")


# ------------------------------------------------------------------ store and views vs sorted-list reference
def rand_ring(rng, store, series, metric, W, minutes_list, density):
    cal = store.calendar
    grids = {}
    for sid, m in zip(cal.ids, minutes_list):
        g = [0] * m
        for i in range(m):
            if rng.random() < density:
                g[i] = rng.choice([1, 2, 3, 7, 10 ** 6, 12])
        grids[sid] = g
    return grids


class StoreViews(unittest.TestCase):
    def _cal(self, n, minutes_of=None):
        flowgrid = lib()[0]
        ids = ["2026-01-%02d" % (i + 1) for i in range(n)] if n < 28 else ["2026-%02d-%02d" % (1 + i // 28, 1 + i % 28) for i in range(n)]
        return flowgrid.Calendar([(s, (minutes_of or (lambda i: 30))(i)) for i, s in enumerate(ids)])

    def test_rank_median_mean_equal_reference(self):
        _, flowstore, _, _ = lib()
        rng = random.Random(3)
        for trial in range(150):
            K = rng.choice([1, 3, 20])
            cal = self._cal(K + 2, lambda i: rng.choice([1, 5, 12, 30]) if trial % 2 else 30)
            store = flowstore.HistoryStore(cal, k=max(K, 2) + 1)
            W = rng.choice([0, 60, 300, 900])
            density = rng.choice([0.0, 0.1, 0.5, 1.0])
            grids = rand_ring(rng, store, "S", "premium", W, cal.minutes, density)
            for sid in cal.ids[:-1]:
                store.append("S", "premium", W, sid, grids[sid], total=sum(grids[sid]), complete=True)
            as_of = cal.ids[-2] if rng.random() < 0.3 else cal.ids[-1]
            view = store.baseline("S", "premium", W, as_of, K)
            pos = cal.position(as_of)
            if view is None:
                self.assertTrue(pos < K or any(s not in store._rings[("S", "premium", W)].recs for s in cal.ids[pos - K:pos]))
                continue
            skip = W // 60
            vals = [v for sid in cal.ids[pos - K:pos] for v in grids[sid][skip:]]
            self.assertEqual(view.n, len(vals))
            if not vals:
                continue
            sv = sorted(vals)
            n = len(vals)
            med = Fraction(sv[n // 2]) if n % 2 else Fraction(sv[n // 2 - 1] + sv[n // 2], 2)
            self.assertEqual(view.median(), med)
            self.assertEqual(view.mean(), Fraction(sum(vals), n))
            xs = {-1, 0, 1, 2, 5, 7, 10, 11, 10 ** 6, 10 ** 6 + 1, Fraction(1, 2), Fraction(5, 2), Fraction(9, 1), Fraction(7, 1)}
            for x in xs:
                self.assertEqual(view.rank(x), (n, sum(1 for v in vals if v <= x), sum(1 for v in vals if v >= x)), (trial, x))

    def test_overflow_values_fall_back_to_lists(self):
        flowgrid, flowstore, _, _ = lib()
        cal = self._cal(3, lambda i: 3)
        store = flowstore.HistoryStore(cal, k=3)
        big = 2 ** 70
        store.append("S", "premium", 60, cal.ids[0], [big, 0, 5], total=big + 5)
        store.append("S", "premium", 60, cal.ids[1], [big * 2, 1, 5], total=2 * big + 6)
        v = store.baseline("S", "premium", 60, cal.ids[2], 2)
        # counted points after dropping the first one (W = 60, skip 1): [0, 5] and [1, 5] -> sorted 0, 1, 5, 5
        self.assertEqual(v.n, 4)
        self.assertEqual(v.rank(big), (4, 4, 0))
        self.assertEqual(v.rank(5), (4, 4, 2))
        self.assertEqual(v.median(), Fraction(3))
        self.assertEqual(v.mean(), Fraction(11, 4))
        big_store = flowstore.HistoryStore(cal, k=3)
        big_store.append("S", "premium", 0, cal.ids[0], [big, 0, 5], total=big + 5)
        big_store.append("S", "premium", 0, cal.ids[1], [big * 2, 1, 5], total=2 * big + 6)
        w = big_store.baseline("S", "premium", 0, cal.ids[2], 2)          # window 0: nothing dropped, 64-bit overflow
        self.assertEqual(w.rank(big), (6, 5, 2))
        self.assertEqual(w.median(), Fraction(5))
        self.assertEqual(w.mean(), Fraction(3 * big + 11, 6))
        text = store.dump().decode()
        self.assertIn(str(big), text)
        self.assertEqual(flowstore.HistoryStore.load(text.encode(), cal, 3).dump(), store.dump())

    def test_ring_retention_order_and_errors(self):
        _, flowstore, _, flowresult = lib()
        cal = self._cal(30)
        store = flowstore.HistoryStore(cal, k=5)
        for i in range(8):
            store.append("S", "m", 300, cal.ids[i], [i, 0, 1], complete=(i % 3 != 0))
        self.assertEqual(store.retained()["S|m|300"], list(cal.ids[3:8]))
        for bad, code in [(cal.ids[7], "duplicate_session"), (cal.ids[2], "out_of_order_append")]:
            with self.assertRaises(flowresult.M2StructuralError) as cm:
                store.append("S", "m", 300, bad, [1])
            self.assertEqual(cm.exception.code, code)
        with self.assertRaises(flowresult.M2StructuralError) as cm:
            store.append("S", "m", 300, "2031-01-01", [1])
        self.assertEqual(cm.exception.code, "session_not_in_calendar")
        with self.assertRaises(flowresult.M2StructuralError) as cm:
            store.append("S", "m", 300, cal.ids[9], [1, 2], grid_idx=[1, 1])
        self.assertEqual(cm.exception.code, "non_monotone_grid")
        with self.assertRaises(flowresult.M2StructuralError):
            store.append("S", "m", 300, cal.ids[9], [1, 2], grid_idx=[0, 99])
        # a failed append leaves the store untouched
        self.assertEqual(store.retained()["S|m|300"], list(cal.ids[3:8]))
        self.assertFalse(store.seal("S", "m", 300, "2026-01-30"))
        self.assertEqual(store.complete_sessions_before("S", "m", 300, cal.ids[8], 2), (cal.ids[5], cal.ids[7]))
        self.assertTrue(store.seal("S", "m", 300, cal.ids[3]))
        self.assertIn(cal.ids[3], store.complete_sessions_before("S", "m", 300, cal.ids[8], 5))
        self.assertRaises(ValueError, flowstore.HistoryStore, cal, 61)

    def test_cache_invalidation_and_cold_equals_warm(self):
        _, flowstore, flowrank, flowresult = lib()
        cal = self._cal(25)
        rng = random.Random(4)
        store = flowstore.HistoryStore(cal, k=22)
        for i in range(20):
            store.append("S", "premium", 60, cal.ids[i], [rng.randrange(0, 5) for _ in range(30)])
        as_of = cal.ids[20]
        v1 = store.baseline("S", "premium", 60, as_of, 20)
        self.assertIs(v1, store.baseline("S", "premium", 60, as_of, 20))      # warm: same cached object
        r1 = v1.rank(2), v1.median(), v1.mean()
        v19 = store.baseline("S", "premium", 60, as_of, 19)                  # another K is another cache entry
        self.assertEqual(len(v19.sessions), 19)
        self.assertEqual(len(store.baseline("S", "premium", 60, as_of, 20).sessions), 20)
        store.append("S", "premium", 60, cal.ids[20], [9] * 30)               # ring changes: cache cleared
        v2 = store.baseline("S", "premium", 60, as_of, 20)
        self.assertIsNot(v1, v2)
        self.assertEqual((v2.rank(2), v2.median(), v2.mean()), r1)            # as_of excludes the new session
        self.assertEqual(v1, v2)
        v3 = store.baseline("S", "premium", 60, cal.ids[21], 20)
        self.assertNotEqual(v2, v3)
        self.assertEqual(hash(v2), hash(v1))
        store.append("S", "premium", 60, cal.ids[21], [0] * 30, complete=False)
        self.assertIsNone(store.baseline("S", "premium", 60, cal.ids[22], 20))   # incomplete session: no baseline
        store.seal("S", "premium", 60, cal.ids[21])
        self.assertIsNotNone(store.baseline("S", "premium", 60, cal.ids[22], 20))
        # eviction of the oldest ring record invalidates dependents
        other = flowstore.HistoryStore(cal, k=20)
        for i in range(20):
            other.append("S", "premium", 60, cal.ids[i], [1] * 30)
        va = other.baseline("S", "premium", 60, cal.ids[20], 20)
        other.append("S", "premium", 60, cal.ids[20], [1] * 30)          # evicts ids[0]: the cached view must not survive
        self.assertEqual(len(other.retained()["S|premium|60"]), 20)
        self.assertIsNone(other.baseline("S", "premium", 60, cal.ids[20], 20))
        self.assertEqual(va.sessions, tuple(cal.ids[0:20]))            # the old view stays a valid immutable snapshot
        self.assertIsNotNone(other.baseline("S", "premium", 60, cal.ids[21], 20))

    def test_canonical_text_round_trip_and_independent_serializer(self):
        _, flowstore, _, _ = lib()
        rng = random.Random(5)
        cal = self._cal(12, lambda i: 6)
        store = flowstore.HistoryStore(cal, k=8)
        series = ["B", "A", "C2", "C10"]
        order = [(s, m, i) for i in range(12) for s in series for m in ("premium", "contracts")]
        for s, m, i in order:
            g = [rng.choice([0, 0, 3, 10 ** 12]) for _ in range(6)]
            store.append(s, m, 300, cal.ids[i], g, total=sum(g) + 1, complete=rng.random() < 0.8)
        data = store.dump()
        # independent re-serialisation of the same content with json
        lines = []
        for key in sorted(store._rings):
            for sid in sorted(store._rings[key].recs):
                r = store._rings[key].recs[sid]
                g = [0] * r.minutes
                for i, v in zip(r.idx, r.vals):
                    g[i] = v
                body = {"series_id": key[0], "metric": key[1], "session_id": sid, "window_s": key[2], "grid": g,
                        "total": r.total, "complete": r.complete}
                text = json.dumps(body, separators=(",", ":"))
                h = hashlib.sha256((text + "\n").encode()).hexdigest()
                body["content_sha256"] = h
                lines.append(json.dumps(body, separators=(",", ":")) + "\n")
        self.assertEqual(data, "".join(lines).encode())
        self.assertEqual(store.content_hash(), hashlib.sha256(data).hexdigest())
        loaded = flowstore.HistoryStore.load(data, cal, k=8)
        self.assertEqual(loaded.dump(), data)
        self.assertEqual(loaded.content_hash(), store.content_hash())
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "store.lf")
            store.dump_to(p)
            with open(p, "rb") as fh:
                self.assertEqual(fh.read(), data)
            self.assertEqual(flowstore.HistoryStore.load(p, cal, k=8).dump(), data)
        bad = data.replace(b'"total":1,', b'"total":2,', 1) if b'"total":1,' in data else data[:-3] + b"0}\n"
        with self.assertRaises(ValueError):
            flowstore.HistoryStore.load(bad, cal, k=8)

    def test_hash_independent_of_series_arrival_order(self):
        _, flowstore, _, _ = lib()
        cal = self._cal(6, lambda i: 4)
        rng = random.Random(6)
        recs = [(s, m, i, [rng.randrange(0, 9) for _ in range(4)]) for s in "XYZW" for m in ("premium", "prints") for i in range(6)]
        hashes = set()
        for _ in range(6):
            store = flowstore.HistoryStore(cal, k=20)
            by = {}
            for r in recs:
                by.setdefault((r[0], r[1]), []).append(r)
            keys = list(by)
            rng.shuffle(keys)
            pending = {k: list(v) for k, v in by.items()}
            while pending:                       # interleave series in random order, sessions stay in order per series
                k = rng.choice(list(pending))
                s, m, i, g = pending[k].pop(0)
                store.append(s, m, 300, cal.ids[i], g)
                if not pending[k]:
                    del pending[k]
            hashes.add(store.content_hash())
        self.assertEqual(len(hashes), 1)


# ------------------------------------------------------------------ kernels end to end vs the reference
def ref_rank(vals, x):
    n = len(vals)
    return n, Fraction(sum(1 for v in vals if v <= x), n), Fraction(sum(1 for v in vals if v >= x), n)


class KernelsEndToEnd(unittest.TestCase):
    def _world(self, rng, minutes=36, nsess=22):
        flowgrid, flowstore, flowrank, _ = lib()
        contracts = rand_world(rng, 5)
        for c in contracts:       # put the name in one lane so every print counts for series "SYN1"
            contracts[c] = contracts[c]._replace(lane="stock")
        cal = flowgrid.Calendar([("2026-%02d-%02d" % (1 + i // 28, 1 + i % 28), minutes) for i in range(nsess)])
        store = flowstore.HistoryStore(cal, k=20)
        sess_prints = {}
        for i, sid in enumerate(cal.ids):
            open_ns = OPEN0 + i * 86400 * NS
            ps = rand_prints(rng, contracts, open_ns, minutes, rng.choice([0, 10, 60, 150]))
            sess_prints[sid] = (open_ns, ps)
        return contracts, cal, store, sess_prints

    def _fill(self, store, cal, contracts, sess_prints, upto, windows=(60, 300, 900)):
        flowgrid = lib()[0]
        for sid in cal.ids[:upto]:
            open_ns, ps = sess_prints[sid]
            b = flowgrid.build_session_records(ps, contracts, sid, open_ns, open_ns + cal.minutes_of(sid) * G, cal.minutes_of(sid),
                                               windows, "stock", "SYN1", True, "full")
            store.append_many(b.records, True)

    def test_f2_f10_f20_f19_equal_reference(self):
        flowgrid, flowstore, flowrank, _ = lib()
        rng = random.Random(7)
        for trial in range(12):
            contracts, cal, store, sp = self._world(rng)
            self._fill(store, cal, contracts, sp, 21)
            today = cal.ids[21]
            open_ns, tps = sp[today]
            minutes = cal.minutes_of(today)
            for W in (60, 300, 900):
                cut = open_ns + rng.choice([W * NS - 1, W * NS, W * NS + 1, 20 * G, minutes * G, 25 * G + 7])
                complete = rng.random() < 0.7
                session = flowrank.SessionInfo(today, open_ns, open_ns + minutes * G, minutes, complete, "live",
                                               sum(p[3] for p in tps if not p[5] and p[4] == 100), None)
                tot = flowgrid.window_totals(tps, contracts, cut, W, "stock", "all", "full")
                cov = {"eligible_count": tot.eligible_count, "nonstandard_count": tot.nonstandard_count,
                       "excluded_condition_count": tot.excluded_condition_count, "unavailable_points": 0}
                hist = {m: [] for m in ("premium", "contracts", "prints")}
                for sid in cal.ids[1:21]:
                    o, ps = sp[sid]
                    g = ref_grid(ps, contracts, "stock", o, cal.minutes_of(sid), W)
                    for m in hist:
                        hist[m].extend(g[m][W // 60:])
                xs = {"premium": tot.premium, "contracts": tot.volume, "prints": tot.count}
                elapsed_ok = cut - open_ns >= W * NS
                for m, x in xs.items():
                    got = flowrank.f2_rank(store, "SYN1", m, x, session, cut, W, "intraday", 5, 20, "stock", cov)
                    if not elapsed_ok:
                        self.assertEqual((got.status, got.reason), ("unavailable", "insufficient_window"))
                        continue
                    n, le, ge = ref_rank(hist[m], x)
                    self.assertEqual((got.value["n"], got.value["rank_le"], got.value["upper_share"]), (n, le, ge))
                    self.assertEqual(got.fired, ge <= Fraction(5, 100))
                    self.assertEqual(got.value["x"], Fraction(x, W // 60) if m == "prints" else x)
                # F10 vs reference
                got = flowrank.f10_baseline(store, "SYN1", tot.volume, session, cut, W, 2, 20, "median", "stock", cov)
                if elapsed_ok:
                    sv = sorted(hist["contracts"])
                    n = len(sv)
                    med = Fraction(sv[n // 2]) if n % 2 else Fraction(sv[n // 2 - 1] + sv[n // 2], 2)
                    mean = Fraction(sum(sv), n)
                    self.assertEqual((got.status == "available", got.value["median"] if got.value else None),
                                     (med != 0, med if med != 0 else None))
                    ps_ = got.value["per_statistic"] if got.value else got.per_statistic
                    self.assertEqual(ps_["mean"]["ratio"], None if mean == 0 else Fraction(tot.volume) / mean)
                    self.assertEqual(ps_["median"]["ratio"], None if med == 0 else Fraction(tot.volume) / med)
            # end of day forms
            tot_hist = {"premium": [], "contracts": [], "prints": []}
            put_hist = []
            for sid in cal.ids[1:21]:
                o, ps = sp[sid]
                el = [p for p in ps if not p[5] and p[4] == 100 and o <= p[1] <= o + cal.minutes_of(sid) * G]
                tot_hist["premium"].append(sum(p[2] * p[3] * 100 for p in el))
                tot_hist["contracts"].append(sum(p[3] for p in el))
                tot_hist["prints"].append(len(el))
            el = [p for p in tps if not p[5] and p[4] == 100]
            today_tot = {"premium": sum(p[2] * p[3] * 100 for p in el), "contracts": sum(p[3] for p in el), "prints": len(el)}
            session = flowrank.SessionInfo(today, open_ns, open_ns + minutes * G, minutes, True, "live", None, None)
            for m in ("premium", "contracts", "prints"):
                s2 = session._replace(total=today_tot[m])
                got = flowrank.f2_rank(store, "SYN1", m, today_tot[m], s2, open_ns + minutes * G, 300, "end_of_day", 5, 20, "stock")
                vals = [Fraction(v, minutes) if m == "prints" else Fraction(v) for v in tot_hist[m]]
                x = Fraction(today_tot[m], minutes) if m == "prints" else Fraction(today_tot[m])
                n, le, ge = ref_rank(vals, x)
                self.assertEqual((got.value["n"], got.value["rank_le"], got.value["upper_share"]), (n, le, ge))
                g20 = flowrank.f20_baseline(store, "SYN1", m, s2, open_ns + minutes * G, 300, 2, 20, "mean", "stock")
                sv = sorted(tot_hist[m])
                med = Fraction(sv[10] + sv[9], 2)
                mean = Fraction(sum(sv), 20)
                if g20.status == "available":
                    self.assertEqual((g20.value["median"], g20.value["mean"]), (med, mean))
                    self.assertEqual(g20.fired, Fraction(today_tot[m]) / mean >= 2)
                else:
                    self.assertEqual(g20.reason, "zero_denominator")
                    self.assertEqual(mean, 0)

    def test_f19_equals_reference(self):
        flowgrid, flowstore, flowrank, _ = lib()
        rng = random.Random(8)
        cal = flowgrid.Calendar([("2026-%02d-%02d" % (1 + i // 28, 1 + i % 28), 3) for i in range(22)])
        for trial in range(80):
            store = flowstore.HistoryStore(cal, k=20)
            pcs = [(rng.randrange(0, 6), rng.choice([0, 1, 2, 3, 5])) for _ in range(21)]
            zero_calls = sum(1 for _, c in pcs[1:] if c == 0)
            for i, (p, c) in enumerate(pcs[1:], start=1):
                store.append("S", "put_volume", 300, cal.ids[i], [0, 0, 0], total=p)
                store.append("S", "call_volume", 300, cal.ids[i], [0, 0, 0], total=c)
            put, call = rng.randrange(0, 8), rng.choice([0, 1, 2, 3, 4])
            sess = flowrank.SessionInfo(cal.ids[21], OPEN0, OPEN0 + 180 * NS, 3, rng.random() < 0.8, "live")
            got = flowrank.f19_percentile(store, "S", put, call, sess, OPEN0 + 180 * NS, 300, 5, 20)
            ratios = [Fraction(p, c) for p, c in pcs[1:] if c > 0]
            # prior window is calendar sessions 1..20 (20 sessions before index 21)
            if len(ratios) < 20:
                self.assertEqual((got.status, got.reason), ("unavailable", "insufficient_history"))
            elif not sess.complete:
                self.assertEqual(got.reason, "session_not_complete")
            elif call == 0:
                self.assertEqual(got.reason, "zero_denominator")
            else:
                n, le, ge = ref_rank(ratios, Fraction(put, call))
                self.assertEqual((got.value["n"], got.value["rank_le"], got.value["upper_share"]), (n, le, ge))
                self.assertEqual(got.fired, ge <= Fraction(5, 100))
            self.assertEqual(zero_calls, sum(1 for _, c in pcs[1:] if c == 0))

    def test_batched_fused_cached_equal_single(self):
        flowgrid, flowstore, flowrank, flowresult = lib()
        rng = random.Random(9)
        contracts, cal, store, sp = self._world(rng)
        self._fill(store, cal, contracts, sp, 21)
        today = cal.ids[21]
        open_ns, tps = sp[today]
        minutes = cal.minutes_of(today)
        session = flowrank.SessionInfo(today, open_ns, open_ns + minutes * G, minutes, False, "live")
        cut = open_ns + 30 * G
        W = 300
        items = []
        for sid in ["SYN1"] + sorted(contracts) + ["NOPE"]:
            tot = flowgrid.window_totals([p for p in tps if sid in ("SYN1", p[0])], contracts, cut, W, "stock", "all", "full")
            items.append((sid, tot.premium, tot.volume, tot.count, None))
        many = flowrank.flow_pack_many(store, session, cut, W, items)
        self.assertEqual(len(many), len(items))
        order = list(range(len(items)))
        rng.shuffle(order)
        single = {}
        for i in order:        # shuffled series order, cold views first then warm
            s, p, v, c, cov = items[i]
            single[i] = flowrank.flow_pack(store, s, session, cut, W, p, v, c, coverage=cov)
        for i, res in enumerate(many):
            self.assertEqual(flowresult.canonical_bytes(list(res)), flowresult.canonical_bytes(list(single[i])))
            sep = (flowrank.f2_rank(store, items[i][0], "premium", items[i][1], session, cut, W),
                   flowrank.f2_rank(store, items[i][0], "contracts", items[i][2], session, cut, W),
                   flowrank.f2_rank(store, items[i][0], "prints", items[i][3], session, cut, W),
                   None,
                   flowrank.f10_baseline(store, items[i][0], items[i][2], session, cut, W))
            self.assertEqual(flowresult.canonical_bytes([res[0], res[1], res[2], res[4]]),
                             flowresult.canonical_bytes([sep[0], sep[1], sep[2], sep[4]]))
        # a loaded store gives the same bytes as the built one
        loaded = flowstore.HistoryStore.load(store.dump(), cal, k=20)
        again = flowrank.flow_pack_many(loaded, session, cut, W, items)
        self.assertEqual(flowresult.canonical_bytes([r for t in again for r in t]), flowresult.canonical_bytes([r for t in many for r in t]))

    def test_f2d_average_and_reason_order(self):
        flowgrid, flowstore, flowrank, _ = lib()
        Res = lib()[3].Result
        mk = lambda up, status="available", reason=None: Res(  # noqa: E731
            "M2-2", "S", "d", 1, status, reason, None, {"upper_share": up} if status == "available" else None)
        d = flowrank.f2d_combine(mk(Fraction(1, 20)), mk(Fraction(1, 2)), mk(Fraction(0)))
        self.assertEqual((d.status, d.fired, d.value["average"]), ("available", None, (Fraction(19, 20) + Fraction(1, 2) + 1) / 3))
        d = flowrank.f2d_combine(mk(0), mk(0, "unavailable", "insufficient_window"), mk(0, "unavailable", "insufficient_history"))
        self.assertEqual((d.status, d.reason, d.value), ("unavailable", "insufficient_window", None))


class Differential(unittest.TestCase):
    """The Tester's differential stream (rank and median-ratio kinds, 20,000 cases each) through HistoryView."""

    def test_stream(self):
        _, flowstore, flowrank, _ = lib()
        flowgrid = lib()[0]
        m2_adapter._loader()
        import gen_m2_diff as D
        n = int(os.environ.get("M2A_DIFF_N", "20000"))
        done = {"rank": 0, "median_ratio": 0}
        for kind, i, inp, exp in D.cases(20261029, n):
            if kind not in done:
                continue
            h, x = inp["h"], inp["x"]
            cal = flowgrid.Calendar([("2026-01-01", len(h)), ("2026-01-02", 1)])
            store = flowstore.HistoryStore(cal, k=1)
            store.append("S", "m", 0, "2026-01-01", h, total=sum(h))
            view = store.baseline("S", "m", 0, "2026-01-02", 1)
            if kind == "rank":
                nn, le, ge = view.rank(x)
                self.assertEqual({"n": nn, "rank_le": D.fmt(Fraction(le, nn)), "upper_share": D.fmt(Fraction(ge, nn))}, exp, i)
            else:
                med, mean = view.median(), view.mean()
                per, _ = flowrank._stat_block(x, med, mean, 2, "median")
                got = {"median": D.fmt(med), "mean": D.fmt(mean),
                       "median_ratio": None if per["median"]["ratio"] is None else D.fmt(per["median"]["ratio"]),
                       "mean_ratio": None if per["mean"]["ratio"] is None else D.fmt(per["mean"]["ratio"])}
                self.assertEqual(got, exp, i)
            done[kind] += 1
        self.assertEqual(done, {"rank": n, "median_ratio": n})


class NoFloat(unittest.TestCase):
    def test_no_float_in_m2_modules(self):
        base = Path(__file__).resolve().parents[2] / "packages" / "features" / "src" / "option_features"
        for name in ("flowresult", "flowgrid", "flowstore", "flowrank"):
            text = (base / (name + ".py")).read_text(encoding="utf-8")
            code = "\n".join(line.split("#")[0] for line in text.splitlines())
            for tok in ("float(", "import math", "from math", "1e-", "numpy", "import decimal", "from decimal"):
                self.assertNotIn(tok, code, "%s uses %s" % (name, tok))


if __name__ == "__main__":
    unittest.main()
