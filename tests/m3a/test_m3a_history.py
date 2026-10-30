"""S02 history store: per-series k up to 252 (`HistoryStore.add_series`), the record `delta_convention`, and the two
M3a read forms `scalar_baseline` and `same_minute_column` (option_features.m3a_history).

First owner of author2 m3a_cases_history.json, all 73 M3A-H rows (one test method per row id), and of the perf rows
W09 (M3A-B7 round trip), W10 (M3A-B8 peak RSS and store bytes), R03 (store bytes at retention 252), R04 (retention
past K), D10 (canonical append order). The B6 append rate and the B5 read share are measured on the same workload.

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12
"""
import ctypes
import gc
import json
import os
import random
import statistics
import sys
import tempfile
import time
import unittest
from decimal import Decimal
from fractions import Fraction

import m3a_harness as H
from option_features import m3a_history as MH
from option_features.flowgrid import Calendar
from option_features.flowresult import M2StructuralError
from option_features.flowstore import MAX_K, HistoryStore, HistoryView

SET, FILE = "author2", "m3a_cases_history.json"
ROWS = H.rows(SET, FILE)
_HEADER = json.loads((H.set_dir(SET) / FILE).read_text(encoding="utf-8").split("\n", 1)[0])
CALENDARS = _HEADER["calendars"]
LABEL = "synthetic workload, relative engineering budget"


# ---- row adapter (fixture inputs -> store API) -------------------------------------------------------------------

def _grid(spec):
    g = [spec["base"]] * spec["len"]
    for i, v in spec["over"]:
        g[i] = v
    return g


def _key(series_id, metric, window_s=0):
    return "%s|%s|%d" % (series_id, metric, window_s)


def _out(status, reason=None, code=None, value=None):
    return {"status": status, "reason": reason, "code": code, "value": value}


def _read(res):
    v = res.value
    if isinstance(v, dict):
        v = {k: (list(x) if isinstance(x, tuple) else x) for k, x in v.items()}
    return _out(res.status, res.reason, res.code, v)


def run_row(row):
    inp = row["inputs"]
    kind = inp.get("kind")
    if kind == "grid_bytes":
        return _out("available", value=MH.grid_store_bytes(inp["names"], inp["k"], inp["grid"], inp["copies"]))
    if kind == "scalar_bytes":
        return _out("available", value=MH.scalar_store_bytes(inp["names"], inp["series"], inp["k"]))
    cal = Calendar(CALENDARS[inp["calendar_ref"]])
    cfg = inp["store_config"]
    kd, kbk = cfg["k_default"], cfg["k_by_key"]
    store = HistoryStore(cal, k=kd if kd <= MAX_K else 20)
    declared = set()
    try:
        for op in inp["ops"]:
            if op[0] == "seal":
                store.seal(op[1], op[2], 0, cal.ids[op[3]])
                continue
            series, metric, i, val, complete, lane = op[1:7]
            if series not in declared:
                declared.add(series)
                k = kbk.get(_key(series, metric), kd)
                if k != store.k:
                    store.add_series(series, k)
            conv = op[7] if len(op) > 7 else None
            sid = cal.ids[i] if type(i) is int else i     # a session id outside the calendar is given as text
            if op[0] == "s":
                store.append(series, metric, 0, sid, [], total=val, complete=bool(complete), lane=lane,
                             delta_convention=conv)
            else:
                store.append(series, metric, 0, sid, _grid(val), complete=bool(complete), lane=lane,
                             delta_convention=conv)
    except M2StructuralError as e:
        return _out("invalid_input", code=e.code)
    q = inp["query"]
    form = q["q"]
    if form == "retained":
        return _out("available", value={"retained": store.retained()})
    if form == "hashes":
        return _out("available", value={"content_sha256_digest": store.content_hash(),
                                        "dump_sha256": store.dump_sha256(),
                                        "n_lines": store.dump(False).count(b"\n")})
    kw = {k: q[k] for k in ("min_sessions", "max_sessions", "lane", "delta_convention", "x") if k in q}
    if form == "scalar_baseline":
        return _read(MH.scalar_baseline(store, q["series_id"], q["metric"], q["as_of"], **kw))
    if form == "same_minute_column":
        return _read(MH.same_minute_column(store, q["series_id"], q["metric"], q["as_of"], q["minute"], **kw))
    raise AssertionError("unknown query form %r" % form)


class Rows(unittest.TestCase):
    def test_row_count(self):
        self.assertEqual(len(ROWS), 73)


def _make(row):
    def test(self):
        got = run_row(row)
        exp = row["expected"]
        for k in ("status", "reason", "code", "value"):
            self.assertEqual(got[k], exp[k], (row["id"], k))
    return test


for _r in ROWS:
    setattr(Rows, "test_" + _r["id"].replace("-", "_"), _make(_r))


# ---- unit tests ----------------------------------------------------------------------------------------------------

def _cal(n=300, minutes=30):
    return Calendar([("S%04d" % i, minutes) for i in range(n)])


class AddSeries(unittest.TestCase):
    def test_k_bounds(self):
        st = HistoryStore(_cal())
        for bad in (0, 253, -1, True, 2.0, "5", None):
            with self.assertRaises((ValueError, TypeError), msg=repr(bad)):
                st.add_series("SYN1/stock/iv30_close", bad)
        st.add_series("SYN1/stock/iv30_close", 252)
        self.assertEqual(st.k_of("SYN1/stock/iv30_close"), 252)
        self.assertEqual(st.k_of("PRM/stock/premium"), 20)

    def test_m2_series_keep_cap_60(self):
        st = HistoryStore(_cal())
        st.add_series("PRM/stock/premium", 60)
        with self.assertRaises(ValueError):
            st.add_series("PRM/stock/premium", 61)
        with self.assertRaises(ValueError):
            HistoryStore(_cal(), k=61)
        self.assertEqual(MAX_K, 60)

    def test_every_m3a_metric_takes_252(self):
        st = HistoryStore(_cal())
        for m in ("atm_iv", "atm_iv_close", "iv30", "iv30_close", "skew25", "skew25_fwd", "term_30_91"):
            st.add_series("SYN1/etf_index/" + m, 252)

    def test_lowering_k_trims_oldest(self):
        cal = _cal()
        st = HistoryStore(cal)
        st.add_series("A/stock/iv30_close", 252)
        for i in range(100):
            st.append("A/stock/iv30_close", "iv30_close", 0, cal.ids[i], [], total=i)
        st.add_series("A/stock/iv30_close", 30)
        self.assertEqual(list(st.retained().values())[0], cal.ids[70:100])


class Convention(unittest.TestCase):
    def _store(self):
        cal = _cal()
        st = HistoryStore(cal)
        st.add_series("A/stock/skew25_fwd", 252)
        for i in range(25):
            st.append("A/stock/skew25_fwd", "skew25_fwd", 0, cal.ids[i], [], total=1000 + i, delta_convention="forward")
        return cal, st

    def test_bad_convention_value_at_append(self):
        cal = _cal()
        st = HistoryStore(cal)
        with self.assertRaises(ValueError):
            st.append("A/stock/skew25", "skew25", 0, cal.ids[0], [], total=1, delta_convention="fwd")

    def test_text_round_trip_keeps_convention(self):
        cal, st = self._store()
        back = HistoryStore.load(st.dump(), cal, series_k={"A/stock/skew25_fwd": 252})
        self.assertEqual(back.content_hash(), st.content_hash())
        self.assertEqual(back.dump(), st.dump())
        r = MH.scalar_baseline(back, "A/stock/skew25_fwd", "skew25_fwd", cal.ids[25], delta_convention="forward")
        self.assertEqual((r.status, r.value["n"]), ("available", 25))
        snap = HistoryStore.from_snapshot(st.snapshot(), cal, series_k={"A/stock/skew25_fwd": 252})
        self.assertEqual(snap.dump(), st.dump())

    def test_binary_round_trip_keeps_convention_and_k(self):
        cal, st = self._store()
        back = HistoryStore.from_binary_snapshot(st.binary_snapshot(), cal)
        self.assertEqual(back.k_of("A/stock/skew25_fwd"), 252)
        self.assertEqual(back.recompute_content_hash(), st.content_hash())
        self.assertEqual(back.dump(), st.dump())

    def test_spot_records_keep_m2_line(self):
        cal = _cal()
        st = HistoryStore(cal)
        st.append("A/stock/iv30_close", "iv30_close", 0, cal.ids[0], [], total=5)
        line = next(st.lines())
        self.assertNotIn("delta_convention", line)
        self.assertEqual(line[:line.rindex(',"content_sha256"')], '{"series_id":"A/stock/iv30_close","metric":"iv30_close","session_id":"S0000",'
                                     '"window_s":0,"grid":[],"total":5,"complete":true')


class Reads(unittest.TestCase):
    def setUp(self):
        self.cal = cal = Calendar([("S%04d" % i, 12 if i % 10 == 9 else 30) for i in range(300)])
        self.st = st = HistoryStore(cal)
        st.add_series("A/stock/iv30", 252)
        st.add_series("A/stock/iv30_close", 252)
        for i in range(260):
            st.append("A/stock/iv30", "iv30", 0, cal.ids[i], [i * 100 + m for m in range(cal.minutes[i])])
            st.append("A/stock/iv30_close", "iv30_close", 0, cal.ids[i], [], total=i, complete=(i % 7 != 3))

    def test_scalar_skips_incomplete_and_caps(self):
        r = MH.scalar_baseline(self.st, "A/stock/iv30_close", "iv30_close", self.cal.ids[270], min_sessions=5,
                               max_sessions=5)
        self.assertEqual(list(r.value["values"]), [254, 256, 257, 258, 259])
        self.assertEqual(r.value["n"], 5)

    def test_minute_zero_is_a_value(self):
        cal, st = self.cal, self.st
        st.add_series("Z/stock/iv30", 252)
        for i in range(21):
            st.append("Z/stock/iv30", "iv30", 0, cal.ids[i], [0] * 5 + [7] * 3)
        r = MH.same_minute_column(st, "Z/stock/iv30", "iv30", cal.ids[21], 2)
        self.assertEqual((r.status, list(r.value["values"])), ("available", [0] * 21))
        r = MH.same_minute_column(st, "Z/stock/iv30", "iv30", cal.ids[21], 9)   # every grid is 8 long: skipped
        self.assertEqual((r.status, r.reason, r.value["n"]), ("unavailable", "insufficient_history", 0))

    def test_minute_half_day_skipped(self):
        r = MH.same_minute_column(self.st, "A/stock/iv30", "iv30", self.cal.ids[260], 20, max_sessions=30)
        self.assertEqual(r.value["n"], 30)
        self.assertNotIn(self.cal.ids[259], r.value["sessions"])
        self.assertEqual(r.value["values"][-1], 258 * 100 + 20)

    def test_view_read_order(self):
        st, c = self.st, self.cal.ids[260]
        f = MH.same_minute_column
        self.assertEqual(f(st, "A/stock/iv30", "iv30", "nope", 99, min_sessions=0).code, "session_not_in_calendar")
        self.assertEqual(f(st, "A/stock/iv30", "iv30", c, 99, min_sessions=0).code, "minute_out_of_range")
        self.assertEqual(f(st, "A/stock/iv30", "iv30", c, "1", min_sessions=0).code, "malformed_type")
        self.assertEqual(f(st, "A/stock/iv30", "iv30", c, 1, min_sessions=0, x=101).code, "malformed_type")
        self.assertEqual(f(st, "A/stock/iv30", "iv30", c, 1, min_sessions=True).code, "malformed_type")
        self.assertEqual(f(st, "A/stock/iv30", "iv30", c, 1, max_sessions=5, x=101).code, "invalid_session_window")
        self.assertEqual(f(st, "A/stock/iv30", "iv30", c, 1, x=101).code, "threshold_out_of_range")
        self.assertIsNone(f(st, "A/stock/iv30", "iv30", c, 1, x="5").code)       # integer text accepted (R-190)
        self.assertEqual(f(st, "A/stock/iv30", "iv30", c, 1, x=float("nan")).code, "malformed_type")   # R-190
        self.assertEqual(f(st, "A/stock/iv30", "iv30", c, 1, x=100).status, "available")

    def test_r190_convention_and_x_types(self):
        cal, st = self.cal, self.st
        st.add_series("A/stock/skew25", 252)
        for i in range(25):
            st.append("A/stock/skew25", "skew25", 0, cal.ids[i], [], total=i)
        f, c = MH.scalar_baseline, cal.ids[30]
        for bad in ("fwd", 1, None):          # wrong string, non-string, supplied None: malformed_type (R-190)
            self.assertEqual(f(st, "A/stock/skew25", "skew25", c, delta_convention=bad).code, "malformed_type", bad)
        self.assertEqual(f(st, "A/stock/skew25", "skew25", c).status, "available")       # not supplied = spot
        g = MH.same_minute_column
        for bad in (50.0, Decimal("50"), True, "abc"):
            self.assertEqual(g(st, "A/stock/iv30", "iv30", cal.ids[260], 1, x=bad).code, "malformed_type", bad)
        self.assertEqual(g(st, "A/stock/iv30", "iv30", cal.ids[260], 1, x="50").status, "available")
        self.assertEqual(g(st, "A/stock/iv30", "iv30", cal.ids[260], 1, x="201/2").code, "threshold_out_of_range")
        self.assertEqual(g(st, "A/stock/iv30", "iv30", cal.ids[260], 1, x=Fraction(1, 2)).status, "available")

    def test_totality_unhashable_and_odd_x(self):
        st, c = self.st, self.cal.ids[260]
        for sid, met, w in ((["A"], "iv30", 0), ("A/stock/iv30", {"m": 1}, 0), ("A/stock/iv30", "iv30", [0])):
            self.assertEqual(MH.scalar_baseline(st, sid, met, c, window_s=w).code, "malformed_type")
            self.assertEqual(MH.same_minute_column(st, sid, met, c, 1, window_s=w).code, "malformed_type")
        g = MH.same_minute_column
        for bad in (Decimal("sNaN"), Decimal("NaN"), float("nan"), float("inf"), Decimal("Infinity")):
            self.assertEqual(g(st, "A/stock/iv30", "iv30", c, 1, x=bad).code, "malformed_type", bad)
        self.assertEqual(g(st, "A/stock/iv30", "iv30", c, 1, x=10 ** 400).code, "threshold_out_of_range")
        self.assertEqual(g(st, "A/stock/iv30", "iv30", c, 1, x=0).status, "available")
        self.assertEqual(g(st, "A/stock/iv30", "iv30", c, 1, x=-1).code, "threshold_out_of_range")

    def test_none_sessions_mean_defaults(self):
        st, c = self.st, self.cal.ids[260]
        for kw in ({"min_sessions": None}, {"max_sessions": None}, {"min_sessions": None, "max_sessions": None}):
            a = MH.scalar_baseline(st, "A/stock/iv30_close", "iv30_close", c, **kw)
            b = MH.scalar_baseline(st, "A/stock/iv30_close", "iv30_close", c)
            self.assertEqual((a.status, a.value), (b.status, b.value), kw)
            a = MH.same_minute_column(st, "A/stock/iv30", "iv30", c, 3, **kw)
            b = MH.same_minute_column(st, "A/stock/iv30", "iv30", c, 3)
            self.assertEqual((a.status, a.value), (b.status, b.value), kw)

    def test_subclass_keys_are_malformed(self):
        class S(str):
            def __hash__(self):
                raise RuntimeError("caller code")

        class I(int):
            def __hash__(self):
                raise RuntimeError("caller code")

        st, c = self.st, self.cal.ids[260]
        for sid, met, w, lane in ((S("A/stock/iv30"), "iv30", 0, "stock"), ("A/stock/iv30", S("iv30"), 0, "stock"),
                                  ("A/stock/iv30", "iv30", I(0), "stock"), ("A/stock/iv30", "iv30", 0, S("stock")),
                                  ("A/stock/iv30", "iv30", True, "stock")):
            self.assertEqual(MH.scalar_baseline(st, sid, met, c, window_s=w, lane=lane).code, "malformed_type")
            self.assertEqual(MH.same_minute_column(st, sid, met, c, 1, window_s=w, lane=lane).code, "malformed_type")

    def test_as_of_excluded_and_cache_per_as_of(self):
        cal, st = self.cal, self.st
        last = cal.ids[259]                          # the last stored session
        r = MH.scalar_baseline(st, "A/stock/iv30_close", "iv30_close", last)
        self.assertNotIn(last, r.value["sessions"])
        self.assertEqual(r.value["sessions"][-1], cal.ids[258])
        r2 = MH.scalar_baseline(st, "A/stock/iv30_close", "iv30_close", cal.ids[201])
        self.assertEqual(r2.value["sessions"][-1], cal.ids[200])
        m1 = MH.same_minute_column(st, "A/stock/iv30", "iv30", last, 3)
        m2 = MH.same_minute_column(st, "A/stock/iv30", "iv30", cal.ids[201], 3)
        self.assertEqual((m1.value["values"][-1], m2.value["values"][-1]), (25803, 20003))

    def test_lane_and_metric_convention(self):
        cal, st = self.cal, self.st
        r = MH.scalar_baseline(st, "A/stock/iv30_close", "iv30_close", cal.ids[260], lane="etf_index")
        self.assertEqual((r.reason, r.value["n"]), ("insufficient_history", 0))
        st.add_series("F/stock/skew25_fwd", 252)
        st.add_series("F/stock/skew25", 252)
        for i in range(25):
            st.append("F/stock/skew25_fwd", "skew25_fwd", 0, cal.ids[i], [], total=i, delta_convention="forward")
            st.append("F/stock/skew25", "skew25", 0, cal.ids[i], [], total=i, delta_convention="forward")
        f = MH.scalar_baseline
        self.assertEqual(f(st, "F/stock/skew25_fwd", "skew25_fwd", cal.ids[30], delta_convention="spot").code,
                         "convention_mismatch")
        self.assertEqual(f(st, "F/stock/skew25", "skew25", cal.ids[30], delta_convention="forward").code,
                         "convention_mismatch")
        self.assertEqual(f(st, "F/stock/skew25_fwd", "skew25_fwd", cal.ids[30], delta_convention="forward").status,
                         "available")

    def test_load_rejects_bad_convention_field(self):
        cal = _cal()
        st = HistoryStore(cal)
        st.append("A/stock/skew25_fwd", "skew25_fwd", 0, cal.ids[0], [], total=1, delta_convention="forward")
        text = st.dump().replace(b'"forward"', b'"fwd"')
        with self.assertRaises(ValueError):
            HistoryStore.load(text, cal, verify=False)

    def test_no_sorted_copy_built(self):
        MH.scalar_baseline(self.st, "A/stock/iv30_close", "iv30_close", self.cal.ids[260])
        MH.same_minute_column(self.st, "A/stock/iv30", "iv30", self.cal.ids[260], 3)
        for ring in self.st._rings.values():
            for v in ring.views.values():
                self.assertNotIsInstance(v, HistoryView)
                self.assertIsInstance(v, MH._Base)

    def test_cache_dropped_by_append_and_seal(self):
        cal, st = self.cal, self.st
        a = MH.scalar_baseline(st, "A/stock/iv30_close", "iv30_close", cal.ids[262])
        st.append("A/stock/iv30_close", "iv30_close", 0, cal.ids[260], [], total=-5, complete=False)
        b = MH.scalar_baseline(st, "A/stock/iv30_close", "iv30_close", cal.ids[262])
        self.assertEqual(b.value["values"], a.value["values"][1:])     # the append evicted the oldest (k 252)
        st.seal("A/stock/iv30_close", "iv30_close", 0, cal.ids[260])
        c = MH.scalar_baseline(st, "A/stock/iv30_close", "iv30_close", cal.ids[262])
        self.assertEqual(c.value["values"], b.value["values"] + (-5,))
        st.drop_caches()
        self.assertEqual(MH.scalar_baseline(st, "A/stock/iv30_close", "iv30_close", cal.ids[262]).value, c.value)

    def test_reads_do_not_change_store(self):
        before = self.st.dump()
        MH.same_minute_column(self.st, "A/stock/iv30", "iv30", self.cal.ids[260], 3)
        self.assertEqual(self.st.dump(), before)


class Memory(unittest.TestCase):
    def test_formula(self):
        self.assertEqual(MH.grid_store_bytes(2 * 103, 252, 390, 3),
                         {"raw_bytes": 161965440, "total_bytes": 485896320, "within_768MiB": True})
        self.assertEqual(MH.STORE_BUDGET_BYTES, 805306368)
        self.assertEqual(MH.STORE_HARD_BYTES, 1073741824)


# ---- perf rows ---------------------------------------------------------------------------------------------------

def _private_bytes():
    """(private bytes, peak working set) of this process (Windows); (None, None) elsewhere."""
    if sys.platform != "win32":
        return None, None
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t)]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    psapi = ctypes.WinDLL("psapi")
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return pmc.PrivateUsage, pmc.PeakWorkingSetSize


NAMES, SESSIONS, GRID = 103, 252, 390
MINUTE_METRICS = ("atm_iv", "iv30")
SCALAR_METRICS = ("atm_iv_close", "iv30_close", "skew25", "skew25_fwd", "term_30_91")
_PATTERN = [(m * 7919) % 50000 for m in range(GRID)]


def _b6_calendar():
    return Calendar([("2024-%03d" % i, GRID) for i in range(SESSIONS + 1)])


def _append_b6(store, cal, sessions=None, names=None):
    """The M3A-B6 set (103 names x 7 series x 252 sessions = 181,692 records), canonical session order; returns the
    seconds spent inside the append calls only (grids are generated outside the timed calls)."""
    spent = 0.0
    clock = time.perf_counter
    for s in (sessions if sessions is not None else range(SESSIONS)):
        sid = cal.ids[s]
        for n in (names if names is not None else range(NAMES)):
            for j, m in enumerate(MINUTE_METRICS):
                base = 10000000 + ((n * 1009 + s * 9176 + j * 31) * 2654435761) % 80000000
                grid = [base + p for p in _PATTERN]
                t0 = clock()
                store.append("N%03d/stock/%s" % (n, m), m, 0, sid, grid)
                spent += clock() - t0
            for j, m in enumerate(SCALAR_METRICS):
                v = 1000000 + ((n * 2003 + s * 7121 + j * 97) * 2246822519) % 90000000
                conv = "forward" if m == "skew25_fwd" else None
                t0 = clock()
                store.append("N%03d/stock/%s" % (n, m), m, 0, sid, [], total=v, delta_convention=conv)
                spent += clock() - t0
    return spent


def _declare(store):
    for n in range(NAMES):
        for m in MINUTE_METRICS + SCALAR_METRICS:
            store.add_series("N%03d/stock/%s" % (n, m), 252)


def _series_k():
    return {"N%03d/stock/%s" % (n, m): 252 for n in range(NAMES) for m in MINUTE_METRICS + SCALAR_METRICS}


class PerfStore(unittest.TestCase):
    """W09 (B7), W10 (B8), R03 (B8 store bytes) and the B6 append rate and B5 read share on one B6 store."""

    @classmethod
    def setUpClass(cls):
        gc.collect()
        cls.priv0, _ = _private_bytes()
        cls.cal = _b6_calendar()
        cls.store = HistoryStore(cls.cal)
        _declare(cls.store)
        cls.append_s = _append_b6(cls.store, cls.cal)
        gc.collect()
        cls.priv1, cls.peak1 = _private_bytes()
        cls.records = NAMES * 7 * SESSIONS

    @classmethod
    def tearDownClass(cls):
        cls.store = None
        gc.collect()

    def test_B6_append_rate(self):
        rate = self.records / self.append_s
        print("\nB6 append %d records (103 names x 7 series x 252 sessions): %.3f s, %.0f records/s "
              "(budget >= 25,000 records/s, hard 5,000; %s)" % (self.records, self.append_s, rate, LABEL))
        self.assertEqual(self.store.stats()["records"], self.records)
        self.assertGreaterEqual(rate, 25000)

    def test_R03_store_bytes(self):
        est = self.store.stats()["est_bytes"]
        print("\nR03 store at retention 252, 103 names x 7 series: est %d B (%.1f MiB)%s; per series %.0f B "
              "(budget <= 768 MiB = 805,306,368 B, hard 1 GiB; %s)"
              % (est, est / 2 ** 20, "" if self.priv0 is None else ", private bytes delta %d B (%.1f MiB)"
                 % (self.priv1 - self.priv0, (self.priv1 - self.priv0) / 2 ** 20), est / (NAMES * 7), LABEL))
        self.assertLessEqual(est, MH.STORE_BUDGET_BYTES)
        if self.priv0 is not None:
            self.assertLessEqual(self.priv1 - self.priv0, MH.STORE_BUDGET_BYTES)

    def test_W10_peak_rss_and_store(self):
        if self.peak1 is None:
            self.skipTest("Windows process counters only")
        _, peak = _private_bytes()          # after the B6 build and (by name order) the W09 round trip
        print("\nW10 peak working set of the test process %.1f MiB (budget <= 2 GB, hard 4 GB); store private bytes "
              "%.1f MiB (budget <= 768 MiB, hard 1 GiB; %s)" % (peak / 2 ** 20, (self.priv1 - self.priv0) / 2 ** 20,
                                                                LABEL))
        self.assertLessEqual(peak, 2 * 10 ** 9)
        self.assertLessEqual(self.priv1 - self.priv0, MH.STORE_BUDGET_BYTES)

    def test_W09_round_trip(self):
        st, cal, n = self.store, self.cal, self.records
        h0 = st.content_hash()
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "b6.txt")
            t0 = time.perf_counter()
            st.dump_to(p)
            w_txt = time.perf_counter() - t0
            t0 = time.perf_counter()
            with open(p, "rb") as fh:
                back = HistoryStore.load(fh.read(), cal, series_k=_series_k())
            r_txt = time.perf_counter() - t0
            self.assertEqual(back.content_hash(), h0)
            r = MH.scalar_baseline(back, "N007/stock/skew25_fwd", "skew25_fwd", cal.ids[SESSIONS],
                                   delta_convention="forward")
            self.assertEqual((r.status, r.value["n"]), ("available", 252))
            back = None
            gc.collect()
            p2 = os.path.join(d, "b6.bin")
            t0 = time.perf_counter()
            st.binary_snapshot_to(p2)
            w_bin = time.perf_counter() - t0
            t0 = time.perf_counter()
            att = HistoryStore.attach_binary(p2, cal, expected_content_hash=h0)
            r_bin = time.perf_counter() - t0
            try:
                self.assertEqual(att.k_of("N000/stock/iv30"), 252)
                a = MH.same_minute_column(att, "N050/stock/iv30", "iv30", cal.ids[SESSIONS], 200)
                b = MH.same_minute_column(st, "N050/stock/iv30", "iv30", cal.ids[SESSIONS], 200)
                self.assertEqual(list(a.value["values"]), list(b.value["values"]))
            finally:
                att.close_mapping()
        print("\nW09 round trip %d records: canonical LF text write %.0f rec/s, read %.0f rec/s; mmap snapshot write "
              "%.0f rec/s, attach %.0f rec/s; content hash identical (budget write >= 25,000, read >= 50,000 "
              "records/s, hard 5,000 / 10,000; %s)" % (n, n / w_txt, n / r_txt, n / w_bin, n / r_bin, LABEL))
        for w, r in ((w_txt, r_txt), (w_bin, r_bin)):
            self.assertGreaterEqual(n / w, 25000)
            self.assertGreaterEqual(n / r, 50000)

    def test_B5_read_share(self):
        """Per series, 252 sessions, 103 names: `cold` = the first read of a session (selection built, cache dropped
        before each pass, outside the timer); `sweep` = a later cutoff of the same session (selection cached, the
        minute moves with the cutoff: what V3 reads at 77 of 78 cutoffs); `warm` = the same read again."""
        st, as_of = self.store, self.cal.ids[SESSIONS]
        out = {}
        forms = (("scalar_baseline", lambda n, m: MH.scalar_baseline(st, "N%03d/stock/iv30_close" % n, "iv30_close",
                                                                        as_of)),
                 ("same_minute_column", lambda n, m: MH.same_minute_column(st, "N%03d/stock/iv30" % n, "iv30", as_of,
                                                                              m)))
        for label, fn in forms:
            fn(0, 0)
            for mode in ("cold", "sweep", "warm"):
                runs = []
                for rep in range(30):
                    if mode == "cold":
                        st.drop_caches()
                    minute = (rep * 13) % GRID if mode == "sweep" else 195
                    t0 = time.perf_counter()
                    for n in range(NAMES):
                        fn(n, minute)
                    runs.append((time.perf_counter() - t0) / NAMES)
                out[label, mode] = (statistics.median(runs), sorted(runs)[int(0.95 * len(runs)) - 1])
        lines = ["  %-18s %-5s p50 %6.1f us p95 %6.1f us" % (k[0], k[1], v[0] * 1e6, v[1] * 1e6) for k, v in out.items()]
        print("\nB5 read share per series (V1/V9 budget <= 50 us, V3 budget <= 150 us per series, whole request; "
              "%s):\n%s" % (LABEL, "\n".join(lines)))
        for mode in ("cold", "sweep", "warm"):
            self.assertLessEqual(out["scalar_baseline", mode][1], 50e-6, mode)
            self.assertLessEqual(out["same_minute_column", mode][1], 150e-6, mode)


class PerfRetention(unittest.TestCase):
    def test_R04_retention_past_k(self):
        cal = _b6_calendar()
        st = HistoryStore(cal, k=60)
        st.add_series("A/stock/iv30_close", 252)
        for i in range(SESSIONS + 1):
            st.append("A/stock/iv30_close", "iv30_close", 0, cal.ids[i], [], total=i)
            st.append("PRM/stock/premium", "premium", 0, cal.ids[i], [i + 1])
        ret = st.retained()
        self.assertEqual(ret["A/stock/iv30_close|iv30_close|0"], cal.ids[1:SESSIONS + 1])
        self.assertEqual(ret["PRM/stock/premium|premium|0"], cal.ids[SESSIONS + 1 - 60:SESSIONS + 1])
        with self.assertRaises(ValueError):
            st.add_series("A/stock/iv30_close", 253)
        with self.assertRaises(ValueError):
            st.add_series("PRM/stock/premium", 61)
        self.assertEqual(HistoryStore(cal).k, 20)

    def test_D10_canonical_append_order(self):
        cal = _b6_calendar()
        names = list(range(NAMES))
        a, b = HistoryStore(cal), HistoryStore(cal)
        _declare(a)
        _declare(b)
        _append_b6(a, cal, sessions=range(30))
        random.Random(7).shuffle(names)
        for s in range(30):                       # same records, names in another order within each session
            _append_b6(b, cal, sessions=[s], names=names)
        self.assertEqual(a.content_hash(), b.content_hash())
        c = HistoryStore(cal)
        _declare(c)
        _append_b6(c, cal, sessions=range(30))
        self.assertEqual(a.content_hash(), c.content_hash())
        self.assertEqual(a.dump(), c.dump())
        with self.assertRaises(M2StructuralError) as e:   # shuffled sessions: closed code, no silent reorder
            c.append("N000/stock/iv30_close", "iv30_close", 0, cal.ids[10], [], total=1)
        self.assertEqual(e.exception.code, "out_of_order_append")
        with self.assertRaises(M2StructuralError) as e:
            c.append("N000/stock/iv30_close", "iv30_close", 0, cal.ids[29], [], total=1)
        self.assertEqual(e.exception.code, "duplicate_session")


if __name__ == "__main__":
    unittest.main()
