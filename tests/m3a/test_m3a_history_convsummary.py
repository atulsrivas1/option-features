"""S02d: O(1) per-ring convention summary behind the `scalar_baseline` convention check (R-193, B5 share).

`_Cols.cc` (convention -> record count) is kept in step with push, eviction and the lazy rebuild (load, attach,
snapshot, seal, add_series, a failed append). A skew read scans no records when every convention of the ring conforms
to the request; otherwise the old per-record scan of the selected window decides. Results are unchanged.

Tests: the summary equals the ring's records after every operation (incl. eviction, rollback, loads); a failing-first
check that a conforming ring returns no per-record conventions; a differential of >= 30,000 random reads against an
independent pure-Python reference over random stores (ring wrap, evictions, mixed and None conventions, k changes,
incomplete records, text / binary / snapshot / attach round trips).

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12
"""
import os
import random
import tempfile
import unittest
from collections import Counter
from unittest import mock

from option_features import flowstore as FS
from option_features import m3a_history as MH
from option_features.flowgrid import Calendar
from option_features.flowstore import HistoryStore

N = 70
CONVS = (None, "spot", "forward")
TRIALS = 1100


def _cal():
    return Calendar([("S%04d" % i, 3) for i in range(N)])


def _check_summary(tc, st):
    for key, ring in st._rings.items():
        c = ring.m3a
        if c is None:
            continue
        tc.assertEqual(c.cc, dict(Counter(r.conv for r in ring.recs.values())), key)
        tc.assertEqual(c.cc, dict(Counter(c.conv)), key)
        tc.assertTrue(all(v > 0 for v in c.cc.values()))


def _ref(st, series_id, metric, as_of, mn, mx, lane, conv):
    """Independent reference: the rule written from the ring's records, no layout."""
    metric_conv = "forward" if metric.endswith("_fwd") else "spot"
    if conv != metric_conv:
        return ("invalid", "convention_mismatch")
    ring = st._rings.get((series_id, metric, 0))
    if ring is None or ring.lane != lane:
        sel = []
    else:
        sel = [r for r in ring.recs.values() if r.session_id < as_of and r.complete][-mx:]
    ok = {None, "spot"} if conv == "spot" else {conv}
    if any(r.conv not in ok for r in sel):
        return ("invalid", "convention_mismatch")
    if len(sel) < mn:
        return ("unavailable", len(sel))
    return ("available", tuple(r.total for r in sel), tuple(r.session_id for r in sel))


def _got(r):
    if r.status == "invalid_input":
        return ("invalid", r.code)
    if r.status == "unavailable":
        return ("unavailable", r.value["n"])
    return ("available", r.value["values"], r.value["sessions"])


class Summary(unittest.TestCase):
    def setUp(self):
        self.cal = _cal()
        self.sid = "A/stock/skew25"
        self.st = HistoryStore(self.cal)
        self.st.add_series(self.sid, 5)

    def put(self, i, conv=None, **kw):
        self.st.append(self.sid, "skew25", 0, self.cal.ids[i], [], total=i, delta_convention=conv, **kw)

    def cols(self):
        return self.st.m3a_cols(self.sid, "skew25", 0)

    def test_counts_follow_append_and_eviction(self):
        for i, cv in enumerate(["spot", None, "forward", "spot", "spot"]):
            self.put(i, cv)
        self.assertEqual(self.cols().cc, {"spot": 3, None: 1, "forward": 1})
        self.put(5, None)                                   # evicts the "spot" of session 0
        self.assertEqual(self.cols().cc, {"spot": 2, None: 2, "forward": 1})
        self.put(6, "spot")                                 # evicts None
        self.put(7, "spot")                                 # evicts "forward": the key must disappear
        self.assertEqual(self.cols().cc, {"spot": 4, None: 1})
        _check_summary(self, self.st)

    def test_conforming_ring_returns_no_record_conventions(self):
        for i in range(12):
            self.put(i, "spot" if i % 2 else None)
        convs, sessions, values = MH._select(self.st, self.sid, "skew25", 0, "stock", self.cal.ids[12], 252,
                                             MH._SCALAR, {None, "spot"})
        self.assertEqual(len(values), 5)                    # k = 5 retained
        self.assertEqual(len(convs), 0)

    def test_nonconforming_ring_still_scans_the_window(self):
        for i in range(8):
            self.put(i, "forward" if i == 6 else "spot")

        def f(a):
            return MH.scalar_baseline(self.st, self.sid, "skew25", self.cal.ids[a], min_sessions=1)
        self.assertEqual(f(8).code, "convention_mismatch")
        # the forward record (session 6) is outside a window ending at session 5: the window decides, not the ring
        self.assertEqual(f(6).status, "available")

    def test_ring_with_old_mismatch_evicted_becomes_clean(self):
        self.put(0, "forward")
        for i in range(1, 5):
            self.put(i, "spot")

        def f(a):
            return MH.scalar_baseline(self.st, self.sid, "skew25", self.cal.ids[a], min_sessions=1)
        self.assertEqual(f(5).code, "convention_mismatch")
        self.put(5, "spot")                                  # evicts the forward record
        self.assertEqual(f(6).status, "available")
        self.assertEqual(self.cols().cc, {"spot": 5})

    def test_incomplete_then_seal(self):
        self.put(0, "forward", complete=False)
        for i in range(1, 4):
            self.put(i, "spot")

        def f():
            return MH.scalar_baseline(self.st, self.sid, "skew25", self.cal.ids[4], min_sessions=1)
        self.assertEqual(f().status, "available")            # incomplete forward record is not selected
        self.st.seal(self.sid, "skew25", 0, self.cal.ids[0])
        self.assertEqual(f().code, "convention_mismatch")
        _check_summary(self, self.st)

    def test_failed_append_leaves_a_correct_summary(self):
        for i in range(5):
            self.put(i, "spot")
        real = FS._Cols.push

        def boom(c, rec):
            real(c, rec)
            raise RuntimeError("after push")
        with mock.patch.object(FS._Cols, "push", boom):
            with self.assertRaises(RuntimeError):
                self.put(5, "forward")
        # ring unchanged (session 5 absent, session 0 not evicted); the summary is rebuilt on the next read
        r = MH.scalar_baseline(self.st, self.sid, "skew25", self.cal.ids[6], min_sessions=1)
        self.assertEqual((r.status, r.value["n"]), ("available", 5))
        self.assertEqual(self.cols().cc, {"spot": 5})
        _check_summary(self, self.st)

    def test_add_series_k_change_rebuilds(self):
        for i in range(5):
            self.put(i, "spot" if i else "forward")
        self.st.add_series(self.sid, 3)
        MH.scalar_baseline(self.st, self.sid, "skew25", self.cal.ids[6], min_sessions=1)
        _check_summary(self, self.st)
        self.assertEqual(self.cols().cc, {"spot": 3})

    def test_loaded_stores_build_the_summary(self):
        for i in range(9):
            self.put(i, [None, "spot", "forward"][i % 3])
        sk = {self.sid: 5}
        p = os.path.join(tempfile.mkdtemp(), "s.bin")
        self.st.binary_snapshot_to(p)
        stores = [HistoryStore.load(self.st.dump(), self.cal, series_k=sk),
                  HistoryStore.from_snapshot(self.st.snapshot(), self.cal, series_k=sk),
                  HistoryStore.from_binary_snapshot(self.st.binary_snapshot(), self.cal),
                  HistoryStore.attach_binary(p, self.cal)]
        try:
            for s in stores:
                ring = s._rings[(self.sid, "skew25", 0)]
                self.assertIsNone(ring.m3a)
                c = s.m3a_cols(self.sid, "skew25", 0)
                self.assertEqual(c.cc, dict(Counter(r.conv for r in ring.recs.values())))
                _check_summary(self, s)
            ring = c = s = None                              # views of the mapping must be gone before it closes
        finally:
            stores[-1].close_mapping()


class Differential(unittest.TestCase):
    reads = 0

    def test_random_reads_equal_reference(self):
        cal = _cal()
        rnd = random.Random(20261031)
        tmp = tempfile.mkdtemp()
        series = [("A/stock/skew25", "skew25"), ("A/stock/skew25_fwd", "skew25_fwd"),
                  ("A/stock/term_30_91", "term_30_91")]
        for trial in range(TRIALS):
            kind = rnd.choice(("pure", "mixed", "mixed", "none"))
            k = rnd.choice((3, 5, 8, 20, 40))
            st = HistoryStore(cal)
            for sid, _ in series:
                st.add_series(sid, k)

            def conv_for(metric):
                base = "forward" if metric.endswith("_fwd") else "spot"
                if metric == "term_30_91":
                    return None
                clean = rnd.choice((base, None if base == "spot" else base))
                if kind == "pure":
                    return base
                if kind == "none":
                    return clean
                return rnd.choice(CONVS) if rnd.random() < .12 else clean

            def feed(s, lo, hi):
                for i in range(lo, hi):
                    if rnd.random() < .12:
                        continue
                    for sid, m in series:
                        s.append(sid, m, 0, cal.ids[i], [], total=rnd.randint(-5, 10 ** 6),
                                 complete=rnd.random() > .1, delta_convention=conv_for(m))
                        if rnd.random() < .05:
                            s.seal(sid, m, 0, cal.ids[i])

            def reads_on(s):
                for _ in range(rnd.randint(3, 6)):
                    sid, m = rnd.choice(series[:2])
                    a = rnd.randrange(0, N)
                    mn = rnd.randint(1, 6)
                    mx = rnd.choice((mn, mn + rnd.randint(0, 5), 252))
                    lane = rnd.choice(("stock", "stock", "stock", "index"))
                    conv = rnd.choice(("spot", "forward"))
                    kw = {} if conv == "spot" and rnd.random() < .5 else {"delta_convention": conv}
                    got = _got(MH.scalar_baseline(s, sid, m, cal.ids[a], min_sessions=mn, max_sessions=mx,
                                                  lane=lane, **kw))
                    self.assertEqual(got, _ref(s, sid, m, cal.ids[a], mn, mx, lane, conv),
                                     (trial, sid, a, mn, mx, lane, conv))
                    t = MH.scalar_baseline(s, "A/stock/term_30_91", "term_30_91", cal.ids[a], min_sessions=mn,
                                           max_sessions=mx)
                    self.assertNotEqual(t.code, "convention_mismatch")
                    Differential.reads += 2

            cut = rnd.randint(2, N - 5)
            feed(st, 0, cut)
            reads_on(st)
            _check_summary(self, st)
            if rnd.random() < .3:                               # retention change mid-life
                for sid, _ in series:
                    st.add_series(sid, rnd.choice((3, 8, 40)))
                reads_on(st)
            feed(st, cut, N)
            reads_on(st)
            _check_summary(self, st)
            sk = {sid: st.k_of(sid) for sid, _ in series}
            att = None
            r = rnd.random()
            if r < .25:
                other = HistoryStore.load(st.dump(), cal, series_k=sk)
            elif r < .5:
                other = HistoryStore.from_snapshot(st.snapshot(), cal, series_k=sk)
            elif r < .75:
                other = HistoryStore.from_binary_snapshot(st.binary_snapshot(), cal)
            else:
                p = os.path.join(tmp, "t%d.bin" % trial)
                st.binary_snapshot_to(p)
                other = att = HistoryStore.attach_binary(p, cal)
            try:
                reads_on(other)
                _check_summary(self, other)
                for sid, m in series:                           # one more append on the loaded store (may evict)
                    ring = other._rings.get((sid, m, 0))
                    if ring is None or not ring.recs:
                        continue
                    i = cal.ids.index(max(ring.recs)) + 1
                    if i < N:
                        other.append(sid, m, 0, cal.ids[i], [], total=1, delta_convention=conv_for(m))
                reads_on(other)
                _check_summary(self, other)
            finally:
                ring = None
                if att is not None:
                    att.close_mapping()
        self.assertGreaterEqual(Differential.reads, 30000)


if __name__ == "__main__":
    unittest.main()
