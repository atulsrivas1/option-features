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
from enum import IntEnum
from array import array

import m3a_harness as H
from option_features import m3a_history as MH
from option_features.flowgrid import Calendar, GridRecord
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
            self.assertEqual(ring.views, {})          # no view, sorted copy or per-call memo (R-193)

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


class Layout(unittest.TestCase):
    """The M3a store layout (flowstore._Cols): all-or-nothing appends, eviction at k, add_series, int64 bounds,
    detach on eviction, and an injected-failure fuzz against a twin store that never saw the failed append."""

    def _read_all(self, st, cal, series="A/stock/iv30", metric="iv30"):
        out = []
        for a in cal.ids:
            for m in (0, 1, 5, 11):
                r = MH.same_minute_column(st, series, metric, a, m, min_sessions=1)
                out.append((r.status, r.code, r.value and (r.value["n"], r.value["sessions"], r.value["values"])))
        return out

    def test_F1_failed_append_changes_nothing(self):
        cal = _cal(10, 6)
        st = HistoryStore(cal)
        st.add_series("A/stock/iv30", 3)
        st.append("A/stock/iv30", "iv30", 0, cal.ids[0], [1, 2, 3, 4, 5, 6])
        for bad in (1.5, Decimal("2"), Fraction(1, 2)):
            before = (st.dump(), self._read_all(st, cal))
            with self.assertRaises(TypeError):
                st.append("A/stock/iv30", "iv30", 0, cal.ids[1], [bad, 2, 3, 4, 5, 6])
            self.assertEqual((st.dump(), self._read_all(st, cal)), before, bad)
        for i in (1, 2, 3):
            st.append("A/stock/iv30", "iv30", 0, cal.ids[i], [i] * 6)
        r = MH.same_minute_column(st, "A/stock/iv30", "iv30", cal.ids[5], 2, min_sessions=1)
        self.assertEqual(r.value["sessions"], tuple(cal.ids[1:4]))
        self.assertEqual(list(st.retained().values())[0], cal.ids[1:4])
        st.dump()

    BAD_ELEMENTS = (1.5, Decimal("2"), Fraction(1, 3), None, True, False, "7", float("nan"), float("inf"), b"1", 2 + 0j)
    BAD_TOTALS = (1.5, Decimal("2"), Fraction(7, 1), True, False, float("nan"), float("inf"), "7", b"7", 2 + 0j)

    def _unchanged(self, st, cal, call, exc=(TypeError, ValueError), msg=None):
        before = (st.dump(), self._read_all(st, cal), st.stats()["records"], dict(st.retained()))
        with self.assertRaises(exc, msg=msg):
            call()
        self.assertEqual((st.dump(), self._read_all(st, cal), st.stats()["records"], dict(st.retained())), before, msg)

    def test_F2_mixed_huge_int_and_bad_grids_rejected(self):
        cal = _cal(10, 3)
        st = HistoryStore(cal)
        st.add_series("A/stock/iv30", 3)
        st.append("A/stock/iv30", "iv30", 0, cal.ids[0], [1, 2, 3])
        grids = ([1, 10 ** 30, Fraction(1, 3)], [10 ** 30, 1.5, 2], [10 ** 30, 10 ** 30, Fraction(5, 1)],
                 [2 ** 63, 2 ** 64, Decimal("1")], [10 ** 30, None, 2], [10 ** 30, True, 2], [0, 10 ** 30, 1.5],
                 [0, 0, Fraction(1, 3)], [1, 2, "7"])
        for g in grids:
            self._unchanged(st, cal, lambda g=g: st.append("A/stock/iv30", "iv30", 0, cal.ids[1], g), msg=g)
        st.append("A/stock/iv30", "iv30", 0, cal.ids[1], [10 ** 30, 2, 3])        # a real huge int is still fine
        st.dump()

    def test_F2_bad_element_every_form(self):
        cal = _cal(10, 4)
        st = HistoryStore(cal)
        st.add_series("A/stock/iv30", 3)
        for bad in self.BAD_ELEMENTS:
            for pos in (0, 3):
                for rest in (5, 0, 10 ** 30):
                    g = [rest] * 4
                    g[pos] = bad
                    self._unchanged(st, cal, lambda g=g: st.append("A/stock/iv30", "iv30", 0, cal.ids[0], g), msg=g)
            self._unchanged(st, cal, lambda b=bad: st.append("A/stock/iv30", "iv30", 0, cal.ids[0], [b, 4],
                                                             grid_idx=[0, 2]), msg=("sparse", bad))
        self.assertEqual(len(st), 0)

    def test_F2_bad_total_rejected(self):
        cal = _cal(10, 3)
        st = HistoryStore(cal)
        st.add_series("A/stock/iv30", 3)
        st.add_series("A/stock/skew25", 3)
        st.append("A/stock/iv30", "iv30", 0, cal.ids[0], [1, 2, 3])
        st.append("A/stock/skew25", "skew25", 0, cal.ids[0], [], total=5)
        for bad in self.BAD_TOTALS:
            self._unchanged(st, cal, lambda b=bad: st.append("A/stock/skew25", "skew25", 0, cal.ids[1], [], total=b),
                            msg=bad)
            self._unchanged(st, cal, lambda b=bad: st.append("A/stock/iv30", "iv30", 0, cal.ids[1], [1, 2, 3], total=b),
                            msg=bad)
        st.append("A/stock/skew25", "skew25", 0, cal.ids[1], [], total=-10 ** 30)    # any exact int is fine
        st.append("A/stock/skew25", "skew25", 0, cal.ids[2], [], total=0)
        st.dump()

    def test_F2_m2_unchanged_by_the_checks(self):
        cal = _cal(10, 3)
        st = HistoryStore(cal)
        st.append("P/stock/premium", "premium", 60, cal.ids[0], [1, 2, 3], total=6)
        st.append("P/stock/premium", "premium", 60, cal.ids[1], [1, 10 ** 30, 3])
        st.append("P/stock/premium", "premium", 60, cal.ids[2], [True, 2, 3])        # M2 narrow accepts bool: untouched
        self.assertEqual(st.stats()["records"], 3)

    def test_m2_series_same_error_as_before(self):
        cal = _cal(10, 6)
        st = HistoryStore(cal)
        with self.assertRaises(TypeError):
            st.append("P/stock/premium", "premium", 60, cal.ids[0], [1.5, 2, 3])
        self.assertEqual(len(st), 0)

    def test_m15_eviction_exactly_at_k(self):
        cal = _cal(10, 6)
        st = HistoryStore(cal)
        st.add_series("A/stock/iv30", 3)
        for i in range(3):
            st.append("A/stock/iv30", "iv30", 0, cal.ids[i], [i + 1] * 6)
        r = MH.same_minute_column(st, "A/stock/iv30", "iv30", cal.ids[9], 1, min_sessions=1)
        self.assertEqual((r.value["sessions"], r.value["values"]), (tuple(cal.ids[0:3]), (1, 2, 3)))
        st.append("A/stock/iv30", "iv30", 0, cal.ids[3], [4] * 6)
        r = MH.same_minute_column(st, "A/stock/iv30", "iv30", cal.ids[9], 1, min_sessions=1)
        self.assertEqual((r.value["sessions"], r.value["values"]), (tuple(cal.ids[1:4]), (2, 3, 4)))

    def test_m09_add_series_after_reads(self):
        cal = _cal(30, 6)
        st = HistoryStore(cal)
        st.add_series("A/stock/iv30", 20)
        for i in range(20):
            st.append("A/stock/iv30", "iv30", 0, cal.ids[i], [i + 1] * 6)
        self.assertEqual(MH.same_minute_column(st, "A/stock/iv30", "iv30", cal.ids[25], 1, min_sessions=1).value["n"], 20)
        st.add_series("A/stock/iv30", 5)
        r = MH.same_minute_column(st, "A/stock/iv30", "iv30", cal.ids[25], 1, min_sessions=1)
        self.assertEqual(r.value["values"], (16, 17, 18, 19, 20))
        st.add_series("A/stock/iv30", 252)
        st.append("A/stock/iv30", "iv30", 0, cal.ids[20], [99] * 6)
        r = MH.same_minute_column(st, "A/stock/iv30", "iv30", cal.ids[25], 1, min_sessions=1)
        self.assertEqual(r.value["values"], (16, 17, 18, 19, 20, 99))

    def test_m10_int64_bounds(self):
        cal = _cal(10, 3)
        st = HistoryStore(cal)
        st.add_series("A/stock/iv30", 252)
        vals = [2 ** 63 - 1, -2 ** 63, 2 ** 63, -2 ** 63 - 1]
        for i, v in enumerate(vals):
            st.append("A/stock/iv30", "iv30", 0, cal.ids[i], [v, v, v])
        r = MH.same_minute_column(st, "A/stock/iv30", "iv30", cal.ids[9], 2, min_sessions=1)
        self.assertEqual(r.value["values"], tuple(vals))
        back = HistoryStore.load(st.dump(), cal, series_k={"A/stock/iv30": 252})
        self.assertEqual(MH.same_minute_column(back, "A/stock/iv30", "iv30", cal.ids[9], 2, min_sessions=1).value,
                         r.value)
        self.assertEqual(back.dump(), st.dump())

    def test_m07_detach_on_eviction(self):
        cal = _cal(10, 4)
        st = HistoryStore(cal)
        st.add_series("A/stock/iv30", 2)
        st.append("A/stock/iv30", "iv30", 0, cal.ids[0], [7, 7, 7, 7])
        st.append("A/stock/iv30", "iv30", 0, cal.ids[1], [8, 8, 8, 8])
        view = st.baseline("A/stock/iv30", "iv30", 0, cal.ids[2], k=2)
        held = st._rings[("A/stock/iv30", "iv30", 0)].recs[cal.ids[0]]
        for i in (2, 3):
            st.append("A/stock/iv30", "iv30", 0, cal.ids[i], [9 + i] * 4)
        self.assertEqual(list(held.vals), [7, 7, 7, 7])
        self.assertEqual(view.mean(), Fraction(15, 2))

    def test_injected_failure_fuzz(self):
        for seed in range(400):
            rng = random.Random(seed)
            cal = _cal(40, rng.choice([4, 6]))
            k = rng.choice([2, 3, 5, 252])
            a, b = HistoryStore(cal), HistoryStore(cal)
            for st in (a, b):
                st.add_series("A/stock/iv30", k)
            steps = []
            for i in range(rng.randint(3, 30)):
                m = cal.minutes[i]
                grid = [rng.choice([0, rng.randint(1, 9), 2 ** 63, rng.randint(1, 10 ** 8)]) for _ in range(m)]
                steps.append((cal.ids[i], grid, rng.random() < 0.8))
            fail_at = rng.randrange(len(steps))
            for j, (sid, grid, comp) in enumerate(steps):
                if j == fail_at:
                    bad = list(grid)
                    if rng.random() < 0.3:
                        with self.assertRaises(TypeError, msg=seed):
                            a.append("A/stock/iv30", "iv30", 0, sid, grid, complete=comp,
                                     total=rng.choice(self.BAD_TOTALS))
                        continue
                    for _ in range(rng.randint(1, 3)):
                        bad[rng.randrange(len(bad))] = rng.choice(self.BAD_ELEMENTS[:3] + (None, "7", True))
                    if rng.random() < 0.5:                       # mixed huge-int and bad-type grid
                        bad[rng.randrange(len(bad))] = rng.choice([10 ** 30, -10 ** 30, 2 ** 64])
                        bad[rng.randrange(len(bad))] = rng.choice([Fraction(1, 3), 1.5, Decimal("3")])
                    if all(type(v) is int for v in bad):
                        bad[0] = Fraction(1, 3)
                    with self.assertRaises(TypeError, msg=seed):
                        a.append("A/stock/iv30", "iv30", 0, sid, bad, complete=comp)
                    continue
                for st in (a, b):
                    st.append("A/stock/iv30", "iv30", 0, sid, grid, complete=comp)
                if rng.random() < 0.2:
                    for st in (a, b):
                        st.seal("A/stock/iv30", "iv30", 0, sid)
            self.assertEqual(a.dump(), b.dump(), seed)
            self.assertEqual(self._read_all(a, cal), self._read_all(b, cal), seed)



class _E(IntEnum):
    ONE = 1


class _I(int):
    pass


class _NpInt64(int):
    """Stand-in for numpy.int64 (an int-like that is not an exact int)."""


class _Shifty(list):
    """A list subclass whose iteration changes shape between calls (check passes, use differs)."""
    calls = 0

    def __iter__(self):
        _Shifty.calls += 1
        return iter([1] * len(self) if _Shifty.calls % 2 else [Fraction(1, 3)] * len(self))


def _bad_scalars():
    return [True, False, 1.5, Decimal("2"), Fraction(1, 3), "7", b"7", None, 2 + 0j, float("nan"), float("inf"),
            _E.ONE, _I(3), _NpInt64(3)]


S = "A/stock/atm_iv"


class Hardening3(unittest.TestCase):
    """Round 3 (D1 to D5): every M3a append form is all-or-nothing against a twin store that never saw the call; M2
    structural codes come before type errors; the dense-grid text writer is byte-identical for every accepted value."""

    def _pair(self, k=3, minutes=16, n=12):
        cal = Calendar([("S%03d" % i, minutes) for i in range(n)])
        a, b = HistoryStore(cal), HistoryStore(cal)
        for st in (a, b):
            st.add_series(S, k)
            st.add_series("A/stock/skew25", k)
            st.append(S, "atm_iv", 0, "S000", list(range(1, minutes + 1)))
            st.append("A/stock/skew25", "skew25", 0, "S000", [], total=5)
        return cal, a, b

    def _state(self, st, cal):
        reads = [Layout._read_all(None, st, cal, S, "atm_iv"),
                 [(r.status, r.code, r.value) for r in (MH.scalar_baseline(st, "A/stock/skew25", "skew25", s, min_sessions=1)
                                                  for s in cal.ids)]]
        return (st.dump(), st.content_hash(), st.binary_snapshot(), st.stats()["records"], st.retained(), reads)

    def _same_after_failure(self, a, b, cal, call, exc=(TypeError, ValueError), msg=None):
        with self.assertRaises(exc, msg=msg):
            call()
        self.assertEqual(self._state(a, cal), self._state(b, cal), msg)
        for st in (a, b):                                    # later appends behave the same
            st.append(S, "atm_iv", 0, "S001", list(range(2, 18)))
            st.append("A/stock/skew25", "skew25", 0, "S001", [], total=6)
        self.assertEqual(self._state(a, cal), self._state(b, cal), msg)

    def test_D1_D3_non_list_grids_rejected(self):
        for bad in (bytes(range(1, 17)), bytes(range(1, 9)), bytearray(range(1, 9)), memoryview(bytes(range(1, 9))),
                    array("q", range(1, 17)), array("B", range(1, 17)), (x for x in range(1, 17)), range(1, 17),
                    {1: 1}, "1234", _Shifty([1] * 16)):
            cal, a, b = self._pair()
            self._same_after_failure(a, b, cal, lambda bad=bad: a.append(S, "atm_iv", 0, "S001", bad),
                                     msg=repr(bad)[:40])

    def test_D3_copy_once_list_and_tuple_still_work(self):
        cal, a, b = self._pair()
        g = list(range(1, 17))
        a.append(S, "atm_iv", 0, "S001", tuple(g))
        b.append(S, "atm_iv", 0, "S001", g)
        g[0] = 99                                            # caller mutation after the call changes nothing
        self.assertEqual(a.dump(), b.dump())

    def test_D3_total_snapshot_from_the_copy(self):
        cal, a, b = self._pair()
        self._same_after_failure(a, b, cal, lambda: a.append(S, "atm_iv", 0, "S001", _Shifty([1] * 16)))

    def test_D2_append_record_bad_inputs(self):
        for bad_vals in ((Fraction(1, 3), 10 ** 30), (True, 2), (1.5, 2), (Decimal("1"), 2), ("1", 2), (None, 2),
                         (2 + 0j, 2), (_E.ONE, 2), (_I(3), 2), (_NpInt64(3), 2), [Fraction(1, 3), 2],
                         array("d", [1.0, 2.0]), array("f", [1.0, 2.0]), memoryview(array("d", [1.0, 2.0])),
                         b"\x01\x02", bytearray(b"\x01\x02"), (x for x in (1, 2))):
            cal, a, b = self._pair()
            rec = GridRecord(S, "atm_iv", 0, "S001", 16, array("H", [1, 3]), bad_vals, 5)
            self._same_after_failure(a, b, cal, lambda rec=rec: a.append_record(rec), msg=repr(bad_vals)[:40])

    def test_D2_append_record_bad_totals(self):
        for bad in _bad_scalars():
            cal, a, b = self._pair()
            rec = GridRecord(S, "atm_iv", 0, "S001", 16, array("H", [1, 3]), (4, 5), bad)
            self._same_after_failure(a, b, cal, lambda rec=rec: a.append_record(rec), msg=repr(bad))

    def test_D2_append_record_good_still_works(self):
        cal, a, b = self._pair()
        a.append_record(GridRecord(S, "atm_iv", 0, "S001", 16, array("H", [1, 3]), array("q", [4, 5]), 9))
        b.append_record(GridRecord(S, "atm_iv", 0, "S001", 16, array("H", [1, 3]), (4, 10 ** 30), 9))
        self.assertEqual(a.stats()["records"], b.stats()["records"])
        b.dump()

    def test_D2_append_many_all_or_nothing(self):
        def good(sid):
            return GridRecord(S, "atm_iv", 0, sid, 16, array("H", [1, 3]), (4, 5), 9)
        bads = [GridRecord(S, "atm_iv", 0, "S004", 16, array("H", [1, 3]), (Fraction(1, 3), 5), 9),
                GridRecord(S, "atm_iv", 0, "S004", 16, array("H", [1, 3]), (4, 5), float("nan")),
                GridRecord(S, "atm_iv", 0, "S002", 16, array("H", [1, 3]), (4, 5), 9)]       # duplicate / order
        for bad in bads:
            cal, a, b = self._pair(k=2)
            batch = [good("S001"), good("S002"), good("S003"), bad]
            self._same_after_failure(a, b, cal, lambda batch=batch: a.append_many(batch))
        cal, a, b = self._pair(k=2)                         # a new ring created inside the failed batch disappears
        batch = [GridRecord("B/stock/iv30", "iv30", 0, "S001", 16, array("H", [1]), (4,), 4),
                 GridRecord("B/stock/iv30", "iv30", 0, "S002", 16, array("H", [1]), (Fraction(1, 2),), 4)]
        self._same_after_failure(a, b, cal, lambda: a.append_many(batch))

    def test_D4_structural_before_type(self):
        cal = Calendar([("S%03d" % i, 16) for i in range(6)])
        for bad_grid, bad_total in (([Fraction(1, 3)] * 16, None), ([1] * 16, 1.5), (b"\x01" * 16, None),
                                    ([True] * 16, None)):
            def fresh():
                st = HistoryStore(cal)
                st.add_series(S, 3)
                st.append(S, "atm_iv", 0, "S002", [1] * 16)
                return st
            cases = (("duplicate_session", "S002", 16), ("out_of_order_append", "S001", 16),
                     ("session_not_in_calendar", "NOPE", 16), ("record_length_mismatch", "S003", 17))
            for code, sid, ln in cases:
                grid = bad_grid if ln == 16 else list(bad_grid) + [bad_grid[0]]
                st = fresh()
                with self.assertRaises(M2StructuralError, msg=code) as cm:
                    st.append(S, "atm_iv", 0, sid, grid, total=bad_total)
                self.assertEqual(cm.exception.code, code)
        st = fresh()                                        # and with append_record
        rec = GridRecord(S, "atm_iv", 0, "S002", 16, array("H", [1]), (Fraction(1, 3),), 5)
        with self.assertRaises(M2StructuralError) as cm:
            st.append_record(rec)
        self.assertEqual(cm.exception.code, "duplicate_session")

    def test_D5_dense_text_identical_to_old_writer(self):
        def old_text(idx, vals, minutes):                   # the previous per-point writer
            tokens = ["0"] * minutes
            for i, v in zip(idx, vals):
                tokens[i] = str(v)
            return ",".join(tokens)
        cal = Calendar([("S%03d" % i, 5) for i in range(6)])
        cases = ([Fraction(1, 3), 10 ** 30, 2, 3, 4], [Decimal("1.50"), 10 ** 30, 2, 3, 4], [_E.ONE, 10 ** 30, 2, 3, 4],
                 [10 ** 30, -10 ** 30, 2 ** 64, 7, 8], [True, 10 ** 30, 2, 3, 4], [1, 2, 3, 4, 5])
        for sid, vals in zip(cal.ids, cases):
            st = HistoryStore(cal)
            st.append("P/stock/premium", "premium", 60, sid, vals)
            line = st.dump().decode().split("\n")[0]
            self.assertIn('"grid":[%s],' % old_text(range(5), vals, 5), line, vals)

    def test_D5_beyond_64_bit_tuple_forms_round_trip(self):
        for n in (1, 2, 3):
            cal = Calendar([("S%03d" % i, n) for i in range(3)])
            for series, metric, w in (("P/stock/premium", "premium", 60), (S, "atm_iv", 0)):
                st = HistoryStore(cal)
                if series == S:
                    st.add_series(S, 5)
                st.append(series, metric, w, "S000", [10 ** 30] * n)
                line = st.dump().decode().split(chr(10))[0]
                self.assertIn('"grid":[%s],' % ",".join(["1" + "0" * 30] * n), line)
                back = HistoryStore.load(st.dump(), cal, series_k={S: 5} if series == S else None)
                self.assertEqual(back.dump(), st.dump())

    def test_round3_injection_fuzz(self):
        for seed in range(300):
            rng = random.Random(seed)
            cal, a, b = self._pair(k=rng.choice([2, 3, 252]), n=20)
            for i in range(1, 12):
                sid = "S%03d" % i
                good = [rng.randint(1, 9) for _ in range(16)]
                if rng.random() < 0.4:
                    kind = rng.randrange(6)
                    bad_scalar = rng.choice(_bad_scalars())
                    if kind == 0:
                        grid = rng.choice([bytes(good), bytearray(good), memoryview(bytes(good)), array("q", good)])
                        call = lambda g=grid: a.append(S, "atm_iv", 0, sid, g)
                    elif kind == 1:
                        call = lambda: a.append(S, "atm_iv", 0, sid, _Shifty([1] * 16))
                    elif kind == 2:
                        g = list(good)
                        g[0] = bad_scalar if bad_scalar is not None else 1.5
                        g[rng.randrange(1, 16)] = 10 ** 30
                        call = lambda g=g: a.append(S, "atm_iv", 0, sid, g)
                    elif kind == 3:
                        if bad_scalar is None:
                            continue
                        call = lambda t=bad_scalar: a.append("A/stock/skew25", "skew25", 0, sid, [], total=t)
                    elif kind == 4:
                        rec = GridRecord(S, "atm_iv", 0, sid, 16, array("H", [1, 3]),
                                         (rng.choice(_bad_scalars()[:9]), 5), 5)
                        call = lambda r=rec: a.append_record(r)
                    else:
                        ok = GridRecord(S, "atm_iv", 0, sid, 16, array("H", [1, 3]), (4, 5), 9)
                        rec = GridRecord(S, "atm_iv", 0, "S%03d" % (i + 1), 16, array("H", [1]), (Fraction(1, 3),), 5)
                        call = lambda r=(ok, rec): a.append_many(r)
                    with self.assertRaises((TypeError, ValueError), msg=(seed, kind)):
                        call()
                    self.assertEqual(self._state(a, cal), self._state(b, cal), (seed, kind))
                for st in (a, b):
                    st.append(S, "atm_iv", 0, sid, good)
                self.assertEqual(a.dump(), b.dump(), seed)


class _Lie(str):
    rsplit = lambda self, *a, **k: ["x", "premium"]


class _Eq(str):
    __eq__ = lambda self, o: False
    __hash__ = lambda self: 1


class _Str(str):
    __str__ = lambda self: "x/premium"
    __hash__ = lambda self: hash("x/premium")


class StrSubclassIds(unittest.TestCase):
    """Last round: a str subclass series id cannot masquerade as an M2 id; TypeError before any mutation."""

    def test_every_entry_point_rejects(self):
        cal = Calendar([("d%02d" % i, 4) for i in range(5)])
        for cls in (_Lie, _Eq, _Str):
            sid = cls("U/stock/iv30_close")
            rec = GridRecord(sid, "iv30_close", 0, "d00", 0, array("H"), array("B"), Fraction(1, 3))
            calls = (lambda: HistoryStore(cal).append(sid, "iv30_close", 0, "d00", [], total=Fraction(1, 3)),
                     lambda: HistoryStore(cal).append(sid, "iv30_close", 0, "d00", [Fraction(1, 3)] * 4),
                     lambda: HistoryStore(cal).append_record(rec),
                     lambda: HistoryStore(cal).append_many([rec]),
                     lambda: HistoryStore(cal).add_series(sid, 100))
            for call in calls:
                with self.assertRaises(TypeError, msg=cls.__name__):
                    call()
            st = HistoryStore(cal)
            with self.assertRaises(TypeError):
                st.append_many([GridRecord("U/stock/iv30", "iv30", 0, "d00", 0, array("H"), array("B"), 3), rec])
            self.assertEqual((len(st), st.stats()["records"]), (0, 0))
            self.assertEqual(st.dump(), HistoryStore(cal).dump())



class _StrSub(str):
    pass


class _EqTrue:
    def __eq__(self, o):
        return True

    def __hash__(self):
        return 1


class _StrLie(str):
    def __str__(self):
        return 'spot","content_sha256":"x'


class _Flip:
    """A record whose series_id changes on every read."""
    def __init__(self, names):
        self._names, self._n = names, 0

    @property
    def series_id(self):
        self._n += 1
        return self._names[0] if self._n == 1 else self._names[1]

    metric, window_s, session_id, minutes = "iv30_close", 0, "S001", 16
    idx = array("H", [1])
    vals = (Fraction(1, 3),)
    total = 5


class _LyingIdx(list):
    def __len__(self):
        return 3


class _BoomHash(str):
    def __hash__(self):
        raise RuntimeError("boom")


class Round5(unittest.TestCase):
    """Review round 5: M2 batch/append semantics identical to main, delta_convention type, atomic _store / seal /
    add_series, attributes read once, no empty rings, grid_idx copy, reads never raise, skew-type _fwd only, gc and
    pickling rules."""

    def _m2(self):
        cal = Calendar([("D%03d" % i, 6) for i in range(10)])
        return cal, HistoryStore(cal)

    def _rec(self, ses, sid="B/stock/other"):
        return GridRecord(sid, "m", 0, ses, 6, array("H", [0, 1]), (1, 2), 3)

    # CODE 1
    def test_C1_m2_batches_keep_main_semantics(self):
        def gen():
            yield self._rec("D000")
            yield self._rec("D001")
            raise RuntimeError("mid")
        for label, make in (("gen", lambda: gen()),
                            ("object", lambda: [self._rec("D000"), self._rec("D001"), object(), self._rec("D003")]),
                            ("none", lambda: [self._rec("D000"), self._rec("D001"), None])):
            cal, st = self._m2()
            with self.assertRaises((RuntimeError, AttributeError), msg=label) as cm:
                st.append_many(make())
            self.assertEqual(st.stats()["records"], 2, label)
            if label == "object":
                self.assertIn("idx", str(cm.exception))
            if label == "gen":
                self.assertIsInstance(cm.exception, RuntimeError)

    def test_C1_m3a_batches_stay_all_or_nothing_for_generators_too(self):
        cal, a, b = Hardening3()._pair(k=3)

        def gen():
            yield GridRecord(S, "atm_iv", 0, "S001", 16, array("H", [1]), (4,), 4)
            yield GridRecord(S, "atm_iv", 0, "S002", 16, array("H", [1]), (Fraction(1, 3),), 4)
        with self.assertRaises(TypeError):
            a.append_many(gen())
        self.assertEqual(a.dump(), b.dump())

    # CODE 2
    def test_C2_m2_dense_truthiness_path(self):
        for bad in (None, ""):
            cal, st = self._m2()
            st.append("B/stock/other", "m", 0, "D000", [bad, 1, 2, 3, 4, 5], total=15)
            self.assertEqual(st.stats()["records"], 1)

    # CODE 3
    def test_C3_delta_convention_exact_str(self):
        cal = Calendar([("D%03d" % i, 3) for i in range(4)])
        for series, metric in (("U/stock/skew25_fwd", "skew25_fwd"), ("P/stock/premium", "premium")):
            for bad in (_StrSub("spot"), _EqTrue(), _StrLie("spot"), b"spot", ["spot"]):
                st = HistoryStore(cal)
                if series.startswith("U"):
                    st.add_series(series, 100)
                with self.assertRaises((TypeError, ValueError), msg=(series, bad)):
                    st.append(series, metric, 0, "D000", [1, 2, 3], delta_convention=bad)
                self.assertEqual(st.stats()["records"], 0)

    # CODE 4
    def test_C4_push_failure_leaves_nothing(self):
        from option_features import flowstore as FS
        cal, a, b = Hardening3()._pair(k=3)
        MH.same_minute_column(a, S, "atm_iv", "S005", 1, min_sessions=1)             # layout built
        real = FS._Cols.push

        def boom(self, rec):
            raise MemoryError("block")
        FS._Cols.push = boom
        try:
            with self.assertRaises(MemoryError):
                a.append(S, "atm_iv", 0, "S001", [3] * 16)
            ring = a._rings[(S, "atm_iv", 0)]
            self.assertIsNone(ring.m3a)                                              # M25
            with self.assertRaises(MemoryError):                                     # a brand-new ring leaves no trace
                a.append("B/stock/iv30", "iv30", 0, "S001", [3] * 16)
            self.assertNotIn(("B/stock/iv30", "iv30", 0), a._rings)
        finally:
            FS._Cols.push = real
        self.assertEqual(a.dump(), b.dump())
        self.assertEqual(MH.same_minute_column(a, S, "atm_iv", "S005", 1, min_sessions=1).value,
                         MH.same_minute_column(b, S, "atm_iv", "S005", 1, min_sessions=1).value)

    def test_C4_eviction_then_push_failure_restores_the_evicted_record(self):
        from option_features import flowstore as FS
        cal, a, b = Hardening3()._pair(k=2)
        a.append(S, "atm_iv", 0, "S001", [2] * 16)
        b.append(S, "atm_iv", 0, "S001", [2] * 16)
        MH.same_minute_column(a, S, "atm_iv", "S005", 1, min_sessions=1)
        real = FS._Cols.push
        FS._Cols.push = lambda self, rec: (_ for _ in ()).throw(MemoryError("x"))
        try:
            with self.assertRaises(MemoryError):
                a.append(S, "atm_iv", 0, "S002", [9] * 16)
        finally:
            FS._Cols.push = real
        self.assertEqual(a.dump(), b.dump())
        self.assertEqual(list(a.retained().values())[0], list(b.retained().values())[0])

    def test_C4_seal_failure(self):
        from option_features import flowstore as FS
        cal, a, b = Hardening3()._pair(k=3)
        for st in (a, b):
            st.append(S, "atm_iv", 0, "S001", [2] * 16, complete=False)
        MH.same_minute_column(a, S, "atm_iv", "S005", 1, min_sessions=1)
        real = FS._Cols.seal
        FS._Cols.seal = lambda self, sid: (_ for _ in ()).throw(MemoryError("x"))
        try:
            with self.assertRaises(MemoryError):
                a.seal(S, "atm_iv", 0, "S001")
        finally:
            FS._Cols.seal = real
        self.assertIsNone(a._rings[(S, "atm_iv", 0)].m3a)
        self.assertEqual(a.dump(), b.dump())
        self.assertEqual(a.seal(S, "atm_iv", 0, "S001"), True)

    # CODE 5
    def test_C5_attributes_read_once(self):
        for names in (("x/stock/premium", "U/stock/iv30_close"), ("U/stock/iv30_close", "x/stock/premium")):
            cal, st = self._m2()
            st = HistoryStore(Calendar([("S%03d" % i, 16) for i in range(4)]))
            try:
                st.append_record(_Flip(names))
            except (TypeError, ValueError):
                pass
            for key, ring in st._rings.items():
                if key[0] == "U/stock/iv30_close":
                    for r in ring.recs.values():
                        self.assertTrue(all(type(v) is int for v in r.vals), names)

    # CODE 6
    def test_C6_no_empty_ring_on_failure(self):
        cal = Calendar([("D%03d" % i, 3) for i in range(4)])
        for strict in (True, False):
            st = HistoryStore(cal, strict_calendar=strict)
            with self.assertRaises(Exception):
                st.append("P/stock/premium", "premium", 0, _BoomHash("D000"), [1, 2, 3])
            self.assertEqual(len(st._rings), 0)

    # CODE 7
    def test_C7_grid_idx_copied_once(self):
        cal = Calendar([("D%03d" % i, 16) for i in range(4)])
        st = HistoryStore(cal)
        st.add_series(S, 5)
        try:
            st.append(S, "atm_iv", 0, "D000", [1, 2], grid_idx=_LyingIdx([1, 3]))
        except (TypeError, ValueError):
            pass
        for ring in st._rings.values():
            for r in ring.recs.values():
                self.assertEqual(len(r.idx), len(r.vals))

    # CODE 8
    def test_C8_reads_never_raise_on_unhashable_convention(self):
        cal, st = self._m2()
        st.append("B/stock/premium", "premium", 0, "D000", [1, 2, 3, 4, 5, 6])
        for bad in ([], {}, set()):
            r = MH.scalar_baseline(st, "B/stock/premium", "premium", "D005", min_sessions=1, delta_convention=bad)
            self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"))

    # CODE 9 / M02
    def test_C9_only_skew_type_fwd_is_m3a(self):
        cal = Calendar([("D%03d" % i, 3) for i in range(4)])
        st = HistoryStore(cal)
        with self.assertRaises(ValueError):
            st.add_series("X/stock/foo_fwd", 100)
        st.add_series("X/stock/skew30_fwd", 100)
        with self.assertRaises(TypeError):
            st.append("X/stock/skew30_fwd", "skew30_fwd", 0, "D000", [Fraction(1, 3)] * 3)

    # M64
    def test_M64_lowering_k_clears_cached_views(self):
        cal = Calendar([("D%03d" % i, 3) for i in range(30)])
        st = HistoryStore(cal)
        for i in range(8):
            st.append("P/stock/premium", "premium", 0, cal.ids[i], [i + 1] * 3)
        v1 = st.baseline("P/stock/premium", "premium", 0, cal.ids[8], k=5)
        self.assertEqual(v1.sessions, tuple(cal.ids[3:8]))
        st.add_series("P/stock/premium", 3)
        v2 = st.baseline("P/stock/premium", "premium", 0, cal.ids[8], k=5)
        self.assertIsNone(v2)                                    # only 3 stored sessions remain

    # M53
    def test_M53_minute_none_is_malformed(self):
        cal, a, b = Hardening3()._pair()
        r = MH.same_minute_column(a, S, "atm_iv", "S005", None, min_sessions=1)
        self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"))

    # M05 / M06
    def test_M05_M06_gc_state_restored(self):
        import gc as _gc
        cal, a, b = Hardening3()._pair()
        data = a.dump()
        snap = a.snapshot()
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.bin")
            a.binary_snapshot_to(p)
            ops = (lambda: a.dump(), lambda: HistoryStore.load(data, cal, series_k={S: 3, "A/stock/skew25": 3}),
                   lambda: HistoryStore.from_snapshot(snap, cal),
                   lambda: HistoryStore.attach_binary(p, cal).close_mapping(),
                   lambda: HistoryStore.load(b"junk\n#END records=1 content_sha256=" + b"0" * 64 + b"\n", cal))
            for enabled in (True, False):
                try:
                    for op in ops:
                        (_gc.enable if enabled else _gc.disable)()
                        try:
                            op()
                        except (ValueError, M2StructuralError):
                            pass
                        self.assertEqual(_gc.isenabled(), enabled)
                finally:
                    _gc.enable()

    # ARCH 4
    def test_A4_pickle_refused_with_a_clear_message(self):
        import pickle
        cal, a, b = Hardening3()._pair()
        loaded = HistoryStore.load(a.dump(), cal, series_k={S: 3, "A/stock/skew25": 3})   # no read yet, no layout
        for st in (a, loaded):
            with self.assertRaises(TypeError) as cm:
                pickle.dumps(st)
            self.assertIn("binary_snapshot", str(cm.exception))
        c2, m2 = self._m2()
        m2.append("B/stock/other", "m", 0, "D000", [1, 2, 3, 4, 5, 6])
        self.assertEqual(pickle.loads(pickle.dumps(m2)).dump(), m2.dump())



class _BoomDict(dict):
    """A views dict whose clear() raises KeyboardInterrupt (an injected failure after the commit point)."""
    def clear(self):
        raise KeyboardInterrupt("injected")


class _BoomSid:
    idx = array("H", [1])
    metric, window_s, session_id, minutes, vals, total = "m", 0, "D001", 6, (1,), 1

    @property
    def series_id(self):
        raise RuntimeError("series_id property")


class _ShiftAttr:
    """A record whose named attribute returns its first value once and the second value afterwards."""
    def __init__(self, attr, first, second):
        self._attr, self._first, self._second, self._n = attr, first, second, 0
        self.series_id, self.metric, self.window_s = "A/stock/iv30", "iv30", 0
        self.session_id, self.minutes, self.idx, self.vals, self.total = "S001", 16, array("H", [1]), (7,), 5
        object.__setattr__(self, "_ready", True)

    def __getattribute__(self, name):
        if name == object.__getattribute__(self, "_attr") and object.__getattribute__(self, "__dict__").get("_ready"):
            n = object.__getattribute__(self, "_n") + 1
            object.__setattr__(self, "_n", n)
            return object.__getattribute__(self, "_first" if n == 1 else "_second")
        return object.__getattribute__(self, name)


class _ShiftIdx(list):
    calls = 0

    def __iter__(self):
        _ShiftIdx.calls += 1
        return iter([1, 3] if _ShiftIdx.calls % 2 else [2, 4])


class Round6(unittest.TestCase):
    """Re-check of 3df0594: batch atomicity when the failure comes before the first M3a record, atomic add_series,
    prescan that never raises, rollback on BaseException, and surviving mutants (N03 N04 N13 N18 N19 N21 N27 to N30)."""

    def _m2rec(self, ses, sid="B/stock/other", total=3):
        return GridRecord(sid, "m", 0, ses, 6, array("H", [0, 1]), (1, 2), total)

    def _cal(self):
        return Calendar([("D%03d" % i, 6) for i in range(10)])

    def test_R1_failure_before_first_m3a_record_rolls_back(self):
        cal = self._cal()
        for batch in ([self._m2rec("D003"), self._m2rec("D002"),
                       GridRecord("A/stock/iv30", "iv30", 0, "D004", 6, array("H", [0]), (1,), 1)],
                      (self._m2rec("D001"), self._m2rec("D001"),
                       GridRecord("A/stock/iv30", "iv30", 0, "D004", 6, array("H", [0]), (1,), 1))):
            st, twin = HistoryStore(cal), HistoryStore(cal)
            with self.assertRaises(M2StructuralError):
                st.append_many(batch)
            self.assertEqual((st.stats()["records"], st.dump()), (0, twin.dump()))

    def test_R3_prescan_never_raises(self):
        cal = self._cal()
        st = HistoryStore(cal)
        with self.assertRaises(RuntimeError):
            st.append_many([self._m2rec("D000"), _BoomSid(), self._m2rec("D002")])
        self.assertEqual(st.stats()["records"], 1)                      # as on main: the earlier record stays

    def test_R2_add_series_is_atomic(self):
        cal, a, b = Hardening3()._pair(k=5)
        for sid in ("S001", "S002", "S003"):
            for st in (a, b):
                st.append(S, "atm_iv", 0, sid, [2] * 16)
        MH.same_minute_column(a, S, "atm_iv", "S009", 1, min_sessions=1)
        ring = a._rings[(S, "atm_iv", 0)]
        ring.views = _BoomDict({("x", 1): object()})
        with self.assertRaises(KeyboardInterrupt):
            a.add_series(S, 2)
        ring.views = {}
        self.assertEqual(a.k_of(S), 5)
        self.assertEqual(len(ring.recs), 4)
        self.assertEqual(a.dump(), b.dump())
        self.assertEqual(MH.same_minute_column(a, S, "atm_iv", "S009", 1, min_sessions=1).value,
                         MH.same_minute_column(b, S, "atm_iv", "S009", 1, min_sessions=1).value)

    def test_R4_store_and_seal_roll_back_after_the_commit_point(self):
        cal, a, b = Hardening3()._pair(k=5)
        ring = a._rings[(S, "atm_iv", 0)]
        ring.views = _BoomDict({("x", 1): object()})
        with self.assertRaises(KeyboardInterrupt):
            a.append(S, "atm_iv", 0, "S001", [3] * 16)
        ring.views = {}
        self.assertEqual(a.dump(), b.dump())
        for st in (a, b):
            st.append(S, "atm_iv", 0, "S001", [3] * 16, complete=False)
        ring.views = _BoomDict({("x", 1): object()})
        with self.assertRaises(KeyboardInterrupt):
            a.seal(S, "atm_iv", 0, "S001")
        ring.views = {}
        self.assertFalse(ring.recs["S001"].complete)
        self.assertEqual(a.dump(), b.dump())

    def test_N_base_exception_rolls_back_store_and_seal(self):
        from option_features import flowstore as FS
        cal, a, b = Hardening3()._pair(k=3)
        MH.same_minute_column(a, S, "atm_iv", "S009", 1, min_sessions=1)
        real_push, real_seal = FS._Cols.push, FS._Cols.seal
        FS._Cols.push = lambda self, rec: (_ for _ in ()).throw(KeyboardInterrupt())
        try:
            with self.assertRaises(KeyboardInterrupt):
                a.append(S, "atm_iv", 0, "S001", [3] * 16)
        finally:
            FS._Cols.push = real_push
        self.assertEqual(a.dump(), b.dump())
        for st in (a, b):
            st.append(S, "atm_iv", 0, "S001", [3] * 16, complete=False)
        MH.same_minute_column(a, S, "atm_iv", "S009", 1, min_sessions=1)
        FS._Cols.seal = lambda self, sid: (_ for _ in ()).throw(KeyboardInterrupt())
        try:
            with self.assertRaises(KeyboardInterrupt):
                a.seal(S, "atm_iv", 0, "S001")
        finally:
            FS._Cols.seal = real_seal
        self.assertFalse(a._rings[(S, "atm_iv", 0)].recs["S001"].complete)
        self.assertIsNone(a._rings[(S, "atm_iv", 0)].m3a)

    def test_N19_trim_at_k_plus_one(self):
        cal = Calendar([("D%03d" % i, 3) for i in range(10)])
        for n, k, want in ((4, 3, 3), (3, 3, 3), (2, 3, 2)):
            st = HistoryStore(cal)
            for i in range(n):
                st.append("P/stock/premium", "premium", 0, cal.ids[i], [i + 1] * 3)
            st.add_series("P/stock/premium", k)
            self.assertEqual(list(st.retained().values())[0], cal.ids[max(0, n - k):n])
            self.assertEqual(len(list(st.retained().values())[0]), want)

    def test_N21_per_ring_k_when_loading(self):
        cal = Calendar([("D%03d" % i, 3) for i in range(10)])
        st = HistoryStore(cal, k=10)
        for i in range(6):
            for sid in ("A/stock/p1", "B/stock/p2", "C/stock/p3"):
                st.append(sid, "premium", 0, cal.ids[i], [i + 1] * 3)
        ks = {"A/stock/p1": 2, "B/stock/p2": 4}
        for back in (HistoryStore.load(st.dump(), cal, k=10, series_k=ks),
                     HistoryStore.from_snapshot(st.snapshot(), cal, k=10, series_k=ks)):
            got = {key[0]: len(v) for key, v in ((k_, list(r.recs)) for k_, r in back._rings.items())}
            self.assertEqual(got, {"A/stock/p1": 2, "B/stock/p2": 4, "C/stock/p3": 6})

    def test_N28_N29_N30_attributes_read_once(self):
        cal = Calendar([("S%03d" % i, 16) for i in range(4)])
        for attr, first, second in (("total", 5, Fraction(1, 3)), ("session_id", "S001", "S002"),
                                    ("series_id", "A/stock/iv30", "x/stock/premium")):
            st = HistoryStore(cal)
            st.add_series("A/stock/iv30", 5)
            st.append_record(_ShiftAttr(attr, first, second))
            self.assertEqual(len(st._rings), 1, attr)
            (key, ring), = st._rings.items()
            (sid, rec), = ring.recs.items()
            self.assertEqual((key[0], sid, rec.session_id, type(rec.total)), ("A/stock/iv30", "S001", "S001", int), attr)

    def test_N27_grid_idx_copied_once(self):
        cal = Calendar([("D%03d" % i, 16) for i in range(4)])
        st = HistoryStore(cal)
        st.add_series(S, 5)
        _ShiftIdx.calls = 0
        st.append(S, "atm_iv", 0, "D000", [5, 6], grid_idx=_ShiftIdx([1, 3]))
        rec = st._rings[(S, "atm_iv", 0)].recs["D000"]
        self.assertEqual((list(rec.idx), list(rec.vals)), ([1, 3], [5, 6]))


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

    def test_B5_read_share_per_call(self):
        """R-193 binding form: warm process, store built before the timer, derived per-series read state dropped
        before EVERY call (outside the timer); 30 repeats of 103 calls after one warm-up; per-call p5/p50/p95/max.
        S02 read share: same_minute_column <= 75 us p95 per call per form (atm_iv, iv30); scalar_baseline <= 25 us."""
        st, as_of = self.store, self.cal.ids[SESSIONS]
        clock = time.perf_counter
        res = {}
        forms = [("scalar_baseline iv30_close", lambda n: MH.scalar_baseline(
                     st, "N%03d/stock/iv30_close" % n, "iv30_close", as_of), 25e-6)]
        for m in MINUTE_METRICS:
            forms.append(("same_minute_column " + m, (lambda m: lambda n: MH.same_minute_column(
                st, "N%03d/stock/%s" % (n, m), m, as_of, 195))(m), 75e-6))
        for label, fn, budget in forms:
            for n in range(NAMES):                       # warm-up
                fn(n)
            calls = []
            for _ in range(30):
                for n in range(NAMES):
                    st.drop_caches()
                    t0 = clock()
                    fn(n)
                    calls.append(clock() - t0)
            calls.sort()
            q = lambda p: calls[min(len(calls) - 1, int(p * len(calls)))]
            res[label] = (q(0.05), q(0.5), q(0.95), calls[-1], budget)
        print("\nB5 read share per call (R-193: cache dropped every call, 30 x 103 calls after warm-up; "
              "synthetic workload, relative engineering budget):")
        for label, (p5, p50, p95, mx, b) in res.items():
            print("  %-30s p5 %6.1f us p50 %6.1f us p95 %6.1f us max %7.1f us (budget <= %d us p95)"
                  % (label, p5 * 1e6, p50 * 1e6, p95 * 1e6, mx * 1e6, b * 1e6))
        for label, (p5, p50, p95, mx, b) in res.items():
            self.assertLessEqual(p95, b, label)

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
