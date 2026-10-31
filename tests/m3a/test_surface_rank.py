"""S08 history rank outputs: M3A-1 (V1), M3A-2 (V3, both iv_form forms), M3A-8 (V9, both delta conventions), module
option_features.surface_rank.

First owner of author2 m3a_cases_V1.json (52 rows), m3a_cases_V3.json (80) and m3a_cases_V9.json (69) = 201 rows, one
test method per row id, and of the perf rows W06 (M3A-B5) and W07 (M3A-B5n) of author4 m3a_perf_resource_rows.json.
Expectations come only from the row files, the G4 fingerprint file and the rulings; the author reference modules are
never imported.

Developer unit tests below: structural order, S02b (zero holes) and R-192 (read status) rules, S09 parity, the S02 read
forms as the only history path, an independent pure-Python differential (more than 20,000 random cases), and the perf
smoke checks (best_of, GATE_BUDGETS section 8 rule 7: smoke checks, never gate evidence).

Bench (Developer evidence, not a gate): `python tests/m3a/test_surface_rank.py --bench-build PATH` writes the 103-name
W06/W07 store (the Tester generator's values, re-implemented here and checked against the manifest) as a binary
snapshot; `--bench-run PATH` attaches it in a fresh process and prints one JSON line (warm-up, 30 timed repeats).

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12
"""
import hashlib
import json
import os
import random
import re
import sys
import tempfile
import time
import unittest
from decimal import Decimal
from fractions import Fraction

import m3a_harness as H
from option_features import m3a_history as MH
from option_features import m3a_validate as V
from option_features import surface_rank as SR
from option_features.flowgrid import Calendar
from option_features.flowrank import SessionInfo
from option_features.flowstore import HistoryStore
from option_features.m3a_common import SURFACE_REASONS, canonical_bytes, canonical_line

SET = "author2"
FAMILIES = (("V1", "m3a_cases_V1.json", 52), ("V3", "m3a_cases_V3.json", 80), ("V9", "m3a_cases_V9.json", 69))
CALENDARS = {}
for _fam, _fn, _n in FAMILIES:
    _h = json.loads((H.set_dir(SET) / _fn).read_text(encoding="utf-8").split("\n", 1)[0])
    CALENDARS.update(_h["calendars"])
LABEL = "synthetic workload, relative engineering budget"
NATURAL_CONV = {"skew25": "spot", "skew25_fwd": "forward"}
FN = {"V1": SR.rank_v1, "V3": SR.rank_v3, "V9": SR.rank_v9}
OID = {"V1": "M3A-1", "V3": "M3A-2", "V9": "M3A-8"}


# ---- row adapter (fixture inputs -> store and API) ----------------------------------------------------------------

def _grid(spec):
    g = [spec["base"]] * spec["len"]
    for i, v in spec["over"]:
        g[i] = v
    return g


def build_store(inp):
    """HistoryStore holding the row's records (append order = row order) in the row's series, ring lane and k."""
    cal = Calendar(CALENDARS[inp["calendar_ref"]])
    st = HistoryStore(cal, k=20)
    ser = inp["series"]
    series_id, metric = ser["series_id"], ser["metric"]
    st.add_series(series_id, inp["store_k"])
    conv = inp.get("records_convention") or NATURAL_CONV.get(metric)
    lane = inp["ring_lane"]
    for idx, v, comp in inp["records"]:
        sid = cal.ids[idx]
        if isinstance(v, dict):
            st.append(series_id, metric, 0, sid, _grid(v), complete=bool(comp), lane=lane, delta_convention=conv)
        else:
            st.append(series_id, metric, 0, sid, [], total=v, complete=bool(comp), lane=lane, delta_convention=conv)
    return st


def call_row(row, fam):
    inp = row["inputs"]
    st = build_store(inp)
    s = inp["session"]
    sess = SessionInfo(s["session_id"], None, None, None, s["complete"], s["feed_delay_tag"])
    now = inp["now"]
    underlying = inp["series"]["series_id"].split("/")[0]
    kw = dict(params=row["params"], upstream_reason=now.get("unavailable"), labels=(inp["model_label"],),
              cutoff_ns=inp["cutoff_ns"])
    if fam == "V9":
        return SR.rank_v9(st, underlying, sess, inp["evaluation_ns"], now.get("put25_iv"), now.get("call25_iv"), **kw)
    return FN[fam](st, underlying, sess, inp["evaluation_ns"], now.get("float"), **kw)


def check_row(tc, row, got):
    e = row["expected"]
    for k in ("output_id", "series_id", "session_id", "evaluation_ns", "lane", "status", "reason", "code", "value",
              "fired"):
        if k in e:
            tc.assertEqual(getattr(got, k), e[k], (row["id"], k))
    if "params" in e:
        tc.assertEqual(got.params, e["params"], (row["id"], "params"))
    if "labels" in e:
        tc.assertEqual(got.labels, e["labels"], (row["id"], "labels"))
    tc.assertIsNone(got.coverage, row["id"])               # no chain is read: nothing to cover
    if e["status"] != "available":                         # R-105: an unavailable or invalid result has no labels
        tc.assertEqual(got.labels, [], row["id"])
        tc.assertIsNone(got.value, row["id"])
        tc.assertIsNone(got.fired, row["id"])


class Rows(unittest.TestCase):
    def test_row_counts(self):
        for fam, fn, n in FAMILIES:
            self.assertEqual(len(H.rows(SET, fn)), n)
        self.assertEqual(sum(n for _, _, n in FAMILIES), 201)
        self.assertEqual(H.EXPECTED_FIXTURE_COUNTS["S08"], 201)


def _make(row, fam):
    def test(self):
        check_row(self, row, call_row(row, fam))
    return test


for _fam, _fn, _n in FAMILIES:
    for _r in H.rows(SET, _fn):
        assert H.owners_of(SET, _fn, _r["id"]) == ["S08"]
        setattr(Rows, "test_" + _r["id"].replace("-", "_"), _make(_r, _fam))


# ---- G4 fingerprints (m3a_g4_histories.json) --------------------------------------------------------------------------
# The planted histories are regenerated here from the ruled seed and catalogue (the generator's plant(), re-implemented),
# the fingerprint is checked, and the planted counts are read back through the rank outputs.

G4 = {r["id"]: r["value"] for r in H.rows(SET, "m3a_g4_histories.json")}
SEED = 20261030


def _canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def _plant(rng, n, ge, le, lo=2_000_000, hi=95_000_000, xlo=30_000_000, xhi=60_000_000):
    t = ge + le - n
    up, dn = ge - t, le - t
    x = rng.randrange(xlo, xhi)
    below = rng.sample(range(lo, x), dn) if dn else []
    above = rng.sample(range(x + 1, hi), up) if up else []
    vals = below + [x] * t + above
    rng.shuffle(vals)
    return x, vals


CATALOGUE = (("n20_top1", 20, 1, 20), ("n21_top1", 21, 1, 21), ("n252_top12", 252, 12, 241),
             ("n252_ties3", 252, 3, 252), ("n100_mid", 100, 50, 51), ("n252_bottom12", 252, 241, 12))


def _scalar_store(vals, session_idx=None, ring_lane="stock", metric="iv30_close", conv=None, cal=None):
    n = len(vals)
    cal = cal or Calendar([("S%04d" % i, 390) for i in range(max(n + 5, 30))])
    st = HistoryStore(cal, k=20)
    series = "SYN1/stock/" + metric
    st.add_series(series, 252)
    for i, v in enumerate(vals):
        st.append(series, metric, 0, cal.ids[i], [], total=v, lane=ring_lane, delta_convention=conv)
    return st, cal


class G4Fingerprints(unittest.TestCase):
    def test_calendar_fingerprints(self):
        self.assertEqual(_sha(_canon(CALENDARS["cal-b979373e"])), G4["calendar_scalar_sha256"])
        self.assertEqual(_sha(_canon(CALENDARS["cal-d6deacf4"])), G4["calendar_minute_sha256"])

    def test_planted_histories_rank_back(self):
        rng = random.Random("%d:%s" % (SEED, "g4-catalogue"))
        made = {}
        for name, n, ge, le in CATALOGUE:
            x, vals = _plant(rng, n, ge, le)
            made[name] = (n, ge, le, x, vals)
            fp = G4[name]
            self.assertEqual((fp["n"], fp["x"], fp["sha256"]), (n, x, _sha(_canon([x, vals]))), name)
        v = rng.randrange(10_000_000, 80_000_000)
        self.assertEqual(G4["const30"]["sha256"], _sha(_canon([v, [v] * 30])))
        for name, (n, ge, le, x, vals) in made.items():
            st, cal = _scalar_store(vals)
            sess = SessionInfo(cal.ids[n], None, None, None, True, "live")
            r = SR.rank_v1(st, "SYN1", sess, 1, x / 1e8, {"x": 5})
            self.assertEqual(r.status, "available", name)
            self.assertEqual((r.value["n"], r.value["rank_le"]), (n, le), name)
            self.assertEqual(r.value["upper_share"], _share(ge, n), name)
            self.assertEqual(r.value["lower_share"], _share(le, n), name)
            self.assertEqual(r.fired, ge * 100 <= 5 * n, name)
        # bottom 5 percent reads lower_share
        n, ge, le, x, vals = made["n252_bottom12"]
        st, cal = _scalar_store(vals)
        sess = SessionInfo(cal.ids[n], None, None, None, True, "live")
        r = SR.rank_v1(st, "SYN1", sess, 1, x / 1e8, {"x": 5, "tail": "bottom"})
        self.assertEqual(r.fired, le * 100 <= 5 * n)
        self.assertTrue(r.fired)

    def test_constant_history_is_zero_range(self):
        st, cal = _scalar_store([33_000_000] * 30)
        sess = SessionInfo(cal.ids[30], None, None, None, True, "live")
        for now in (0.33, 0.5, 0.01):
            r = SR.rank_v1(st, "SYN1", sess, 1, now, {})
            self.assertEqual((r.status, r.reason), ("unavailable", "zero_range_history"))


def _share(a, n):
    f = Fraction(a, n)
    return f.numerator if f.denominator == 1 else "%d/%d" % (f.numerator, f.denominator)


# ---- Developer unit tests -----------------------------------------------------------------------------------------------

def _mstore(vals_by_session, minutes=12, n_sessions=60, metric="atm_iv", lane="stock", complete=None, k=252):
    """Minute-series store: `vals_by_session` {calendar index: grid list}."""
    cal = Calendar([("S%04d" % i, minutes) for i in range(n_sessions)])
    st = HistoryStore(cal, k=20)
    series = "U/stock/" + metric
    st.add_series(series, k)
    for i in sorted(vals_by_session):
        st.append(series, metric, 0, cal.ids[i], vals_by_session[i], lane=lane,
                  complete=True if complete is None else complete.get(i, True))
    return st, cal


def _sess(cal, i, complete=True, tag="live"):
    return SessionInfo(cal.ids[i], None, None, None, complete, tag)


class V3Holes(unittest.TestCase):
    """S02b / R-195 (decision 2026-10-31-m3a-s02b item 7): a stored 0 at the minute is a hole and is never ranked; a
    current value of 0 at the minute is unavailable and is never ranked."""

    def test_zero_in_history_is_not_a_point(self):
        grids = {i: [100 + i] * 12 for i in range(30)}
        for i in (5, 6, 7, 20):
            grids[i] = [0] + grids[i][1:]
        st, cal = _mstore(grids)
        r = SR.rank_v3(st, "U", _sess(cal, 40), 1, 1.0e-6 * 120, {"minute": 0, "x": 50, "min_sessions": 5})
        self.assertEqual(r.status, "available")
        self.assertEqual(r.value["n"], 26)                      # 30 sessions minus 4 holes
        self.assertEqual(r.value["rank_le"], 26)                # 120 is above every kept value (100..129 except holes)
        # the holes do not move the rank: count only the non-zero points at or below 120
        kept = [100 + i for i in range(30) if i not in (5, 6, 7, 20)]
        self.assertEqual(r.value["rank_le"], sum(1 for v in kept if v <= 12000))

    def test_current_zero_is_unavailable_never_ranked(self):
        st, cal = _mstore({i: [50 + i] * 12 for i in range(30)})
        for form, reason in (("30d", "no_bracketing_expiry"), ("atm", "no_atm_strike")):
            metric = "iv30" if form == "30d" else "atm_iv"
            st, cal = _mstore({i: [50 + i] * 12 for i in range(30)}, metric=metric)
            for now in (0.0, 4e-9, -0.0):                        # rounds to 0 at 10^-8
                r = SR.rank_v3(st, "U", _sess(cal, 40), 1, now, {"minute": 3, "iv_form": form})
                self.assertEqual((r.status, r.reason, r.value, r.fired), ("unavailable", reason, None, None), (form, now))
            r = SR.rank_v3(st, "U", _sess(cal, 40), 1, 6e-9, {"minute": 3, "iv_form": form})
            self.assertEqual(r.status, "available")             # 1 unit is a value

    def test_all_zero_column_is_insufficient(self):
        st, cal = _mstore({i: [0] * 12 for i in range(30)})
        r = SR.rank_v3(st, "U", _sess(cal, 40), 1, 0.01, {"minute": 4})
        self.assertEqual((r.status, r.reason), ("unavailable", "insufficient_history"))

    def test_window_reaches_back_past_holes(self):
        grids = {i: [1000 + i] * 12 for i in range(12)}
        grids[10] = [0] * 12
        grids[11] = [0] * 12
        st, cal = _mstore(grids)
        r = SR.rank_v3(st, "U", _sess(cal, 20), 1, 1008 / 1e8, {"minute": 2, "min_sessions": 1, "max_sessions": 3, "x": 100})
        self.assertEqual(r.value["n"], 3)                       # sessions 7, 8, 9 (10 and 11 are holes)
        self.assertEqual(r.value["rank_le"], 2)                 # 1007 and 1008 are <= 1008; 1009 is not
        self.assertEqual(r.value["upper_share"], "2/3")

    def test_scalar_zero_is_a_value(self):
        st, cal = _scalar_store([0] + [5, 7, 9] * 10, metric="skew25", conv="spot")
        sess = SessionInfo(cal.ids[31], None, None, None, True, "live")
        r = SR.rank_v9(st, "SYN1", sess, 1, 0.1, 0.1, {"x": 100, "min_sessions": 5})
        self.assertEqual(r.status, "available")
        self.assertEqual((r.value["n"], r.value["x"]), (31, "0.00000000"))
        self.assertEqual(r.value["rank_le"], 1 + 0)             # the history 0 counts, x = 0 equals it


class ReadPath(unittest.TestCase):
    """The history is read only through scalar_baseline and same_minute_column (S02b item 7, R-192)."""

    def test_no_history_view_or_baseline(self):
        st, cal = _mstore({i: [100 + i] * 12 for i in range(30)})
        st2, cal2 = _scalar_store(list(range(1000, 1030)))

        def boom(*a, **k):
            raise AssertionError("HistoryView path used")
        st.baseline = boom
        st2.baseline = boom
        r = SR.rank_v3(st, "U", _sess(cal, 40), 1, 1.0e-6 * 110, {"minute": 4})
        self.assertEqual(r.status, "available")
        r = SR.rank_v1(st2, "SYN1", SessionInfo(cal2.ids[31], None, None, None, True, "live"), 1, 1.0e-5 * 100, {})
        self.assertEqual(r.status, "available")

    def test_reads_go_through_the_s02_functions(self):
        calls = []
        real_s, real_m = SR.scalar_baseline, SR.same_minute_column
        SR.scalar_baseline = lambda *a, **k: (calls.append("s"), real_s(*a, **k))[1]
        SR.same_minute_column = lambda *a, **k: (calls.append("m"), real_m(*a, **k))[1]
        try:
            st, cal = _mstore({i: [100 + i] * 12 for i in range(30)})
            SR.rank_v3(st, "U", _sess(cal, 40), 1, 0.001, {"minute": 4})
            st2, cal2 = _scalar_store(list(range(1000, 1030)))
            SR.rank_v1(st2, "SYN1", SessionInfo(cal2.ids[31], None, None, None, True, "live"), 1, 0.001, {})
            SR.rank_v9(st2, "SYN1", SessionInfo(cal2.ids[31], None, None, None, True, "live"), 1, 0.2, 0.1, {})
        finally:
            SR.scalar_baseline, SR.same_minute_column = real_s, real_m
        self.assertEqual(calls, ["m", "s", "s"])

    def test_unavailable_read_values_are_never_touched(self):
        """R-192: an unavailable read has values None; the rank must not use them (it would raise on None)."""
        real = SR.same_minute_column
        seen = []

        def fake(*a, **k):
            r = real(*a, **k)
            seen.append(r.status)
            return r
        SR.same_minute_column = fake
        try:
            st, cal = _mstore({i: [100 + i] * 12 for i in range(5)})
            r = SR.rank_v3(st, "U", _sess(cal, 40), 1, 0.001, {"minute": 4})
        finally:
            SR.same_minute_column = real
        self.assertEqual(seen, ["unavailable"])
        self.assertEqual((r.status, r.reason), ("unavailable", "insufficient_history"))

    def test_invalid_read_status_is_reported_as_the_code(self):
        st, cal = _scalar_store([5, 6, 7] * 10, metric="skew25_fwd", conv="spot")      # forward series, spot records
        sess = SessionInfo(cal.ids[31], None, None, None, True, "live")
        r = SR.rank_v9(st, "SYN1", sess, 1, 0.2, 0.1, {"delta_convention": "forward", "x": 5})
        self.assertEqual((r.status, r.code), ("invalid_input", "convention_mismatch"))


_NO = object()


class Structural(unittest.TestCase):
    """Order of the codes: IO contract section 4 request list (4, 5, 10, 13, 15, 16, 17, 18) with the view-read
    session check after position 5 and invalid_session_window after the position-10 types (decision file item 3)."""

    def setUp(self):
        self.st, self.cal = _scalar_store([10 + (i * 7) % 13 for i in range(40)])
        self.sess = SessionInfo(self.cal.ids[41], None, None, None, True, "live")

    def code(self, params=None, sess=_NO, **kw):
        r = SR.rank_v1(self.st, "SYN1", self.sess if sess is _NO else sess, kw.pop("ev", 1), kw.pop("now", 0.15), params, **kw)
        self.assertEqual(r.status, "invalid_input", r)
        return r.code

    def test_order(self):
        s = self.sess
        bad_s = SessionInfo("2099-01-01", None, None, None, True, "delayed")
        self.assertEqual(self.code({"mode": 5, "lane": "x"}), "malformed_type")
        self.assertEqual(self.code({"mode": "weekly", "lane": "x"}), "invalid_mode")
        self.assertEqual(self.code({"lane": "x", "min_sessions": 0}, bad_s), "invalid_lane")
        self.assertEqual(self.code({"min_sessions": 0, "x": 101}, bad_s), "session_not_in_calendar")
        self.assertEqual(self.code({"min_sessions": 0, "x": 101}), "malformed_type")
        self.assertEqual(self.code({"min_sessions": 30, "max_sessions": 20, "x": 101}), "invalid_session_window")
        self.assertEqual(self.code({"x": 101}, SessionInfo(s.session_id, None, None, None, True, "delayed")),
                         "threshold_out_of_range")
        self.assertEqual(self.code({"x": 5}, SessionInfo(s.session_id, None, None, None, True, "delayed")),
                         "delayed_feed_tag")
        self.assertEqual(self.code({"tail": "middle", "x": 101}), "malformed_type")
        self.assertEqual(self.code({"x": 5.0}), "malformed_type")
        self.assertEqual(self.code({"x": True}), "malformed_type")
        self.assertEqual(self.code({"x": Decimal(5)}), "malformed_type")
        self.assertEqual(self.code({"x": "1/0"}), "malformed_type")
        self.assertEqual(self.code({"x": -1}), "threshold_out_of_range")

    def test_cutoff_codes(self):
        self.assertEqual(self.code({}, cutoff_ns=-1), "bad_cutoff")
        self.assertEqual(self.code({}, cutoff_ns=1.5), "malformed_type")
        self.assertEqual(self.code({}, ev=5, cutoff_ns=6), "cutoff_mismatch")
        self.assertEqual(self.code({}, ev="5"), "malformed_type")
        self.assertEqual(self.code({}, ev=True), "malformed_type")
        self.assertEqual(self.code({"min_sessions": 0}, ev=5, cutoff_ns=6), "malformed_type")

    def test_never_raises_on_hostile_arguments(self):
        class Boom:
            def __getattr__(self, n):
                raise RuntimeError(n)
        for sess in (None, 5, "S0001", Boom(), SessionInfo(5, None, None, None, True, "live"),
                     SessionInfo(Boom(), None, None, None, True, "live")):
            self.assertEqual(self.code({}, sess), "malformed_type", sess)
        for params in ("x", [1], 5, Boom(), {5: 6, "x": Boom()}):
            r = SR.rank_v1(self.st, "SYN1", self.sess, 1, 0.15, params)
            self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"), params)
        for und in (None, 5, b"SYN1", "", "SY/N1"):
            r = SR.rank_v1(self.st, und, self.sess, 1, 0.15, {})
            self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"), und)
        for now in (None, "0.1", True, float("nan"), float("inf"), [1], Boom()):
            r = SR.rank_v1(self.st, "SYN1", self.sess, 1, now, {})
            self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"), now)
        for up in ("bogus", 5, ["no_atm_strike"], "no_quote"):
            r = SR.rank_v1(self.st, "SYN1", self.sess, 1, 0.15, {}, upstream_reason=up)
            self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"), up)
        for lab in (None, 5, [5], ["a", 7]):
            r = SR.rank_v1(self.st, "SYN1", self.sess, 1, 0.15, {}, labels=lab)
            self.assertEqual(r.status, "available" if lab is None else "invalid_input")

    def test_v3_rules(self):
        st, cal = _mstore({i: [100 + i] * 12 for i in range(30)})
        s = _sess(cal, 40)

        def code(params, sess=s):
            r = SR.rank_v3(st, "U", sess, 1, 0.001, params)
            self.assertEqual(r.status, "invalid_input", r)
            return r.code
        self.assertEqual(code({"minute": 12}), "minute_out_of_range")
        self.assertEqual(code({"minute": -1}), "minute_out_of_range")
        for bad in (None, True, 5.0, "5"):
            self.assertEqual(code({"minute": bad}), "malformed_type", bad)
        self.assertEqual(code({}), "malformed_type")
        self.assertEqual(code({"minute": 3, "mode": "close"}), "invalid_mode")      # V3 is intraday only (R-175)
        self.assertEqual(code({"minute": 3, "iv_form": "90d", "x": 101}), "iv_form_not_allowed")
        self.assertEqual(code({"minute": 3, "iv_form": None}), "malformed_type")
        self.assertEqual(code({"minute": 99, "x": 101}), "threshold_out_of_range")
        self.assertEqual(code({"minute": 99}, _sess(cal, 40, tag="delayed")), "minute_out_of_range")
        self.assertEqual(code({"minute": 3}, _sess(cal, 40, tag="delayed")), "delayed_feed_tag")
        # a half-day current session bounds the minute by its own grid
        cal2 = Calendar([("S%04d" % i, 12 if i != 40 else 5) for i in range(60)])
        st = HistoryStore(cal2, k=20)
        self.assertEqual(code({"minute": 5}, SessionInfo("S0040", None, None, None, True, "live")),
                         "minute_out_of_range")

    def test_v9_rules(self):
        st, cal = _scalar_store([10 + (i * 5) % 7 for i in range(40)], metric="skew25_fwd", conv="spot")
        s = SessionInfo(cal.ids[41], None, None, None, True, "live")

        def code(params, **kw):
            r = SR.rank_v9(st, "SYN1", s, 1, 0.2, 0.1, params, **kw)
            self.assertEqual(r.status, "invalid_input", r)
            return r.code
        self.assertEqual(code({"delta_convention": "Forward"}), "convention_not_allowed")
        self.assertEqual(code({"delta_convention": None}), "malformed_type")
        self.assertEqual(code({"delta_convention": 7}), "malformed_type")
        r = SR.rank_v9(st, "SYN1", s, 1, 0.2, 0.1, {"delta_convention": "forward"})
        self.assertEqual((r.status, r.code, r.series_id), ("invalid_input", "convention_mismatch", "SYN1/stock/skew25_fwd"))
        for bad in (None, "a", True):
            r = SR.rank_v9(st, "SYN1", s, 1, bad, 0.1, {})
            self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"))
            r = SR.rank_v9(st, "SYN1", s, 1, 0.2, bad, {})
            self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"))

    def test_params_not_mutated(self):
        p = {"x": 5, "tail": "top"}
        before = dict(p)
        SR.rank_v1(self.st, "SYN1", self.sess, 1, 0.15, p)
        self.assertEqual(p, before)


class Semantics(unittest.TestCase):
    def test_v1_forms_labels_and_delay(self):
        st, cal = _scalar_store([10, 20, 30, 40, 50] * 6)
        d = _sess(cal, 31, tag="delayed")
        r = SR.rank_v1(st, "SYN1", d, 1, 3e-7 * 10, {"mode": "close", "x": 50}, labels=("exact-model",))
        self.assertEqual((r.status, r.labels, r.value["form"]), ("available", ["delayed", "exact-model"], "end_of_day"))
        r = SR.rank_v1(st, "SYN1", d, 1, 3e-7 * 10, {"mode": "intraday"})
        self.assertEqual((r.status, r.code), ("invalid_input", "delayed_feed_tag"))
        r = SR.rank_v1(st, "SYN1", _sess(cal, 31), 1, 3e-7 * 10, {}, labels=["b", "a", "b"])
        self.assertEqual((r.status, r.labels, r.value["form"]), ("available", ["a", "b"], "intraday"))
        r = SR.rank_v1(st, "SYN1", _sess(cal, 31, complete=False), 1, 3e-7 * 10, {"mode": "close"})
        self.assertEqual((r.status, r.reason), ("unavailable", "session_not_complete"))
        r = SR.rank_v1(st, "SYN1", _sess(cal, 31, complete=False), 1, 3e-7 * 10, {"mode": "intraday"})
        self.assertEqual(r.status, "available")          # intraday does not need a sealed session

    def test_reason_order(self):
        st, cal = _scalar_store([7] * 10)
        s = _sess(cal, 11, complete=False)
        r = SR.rank_v1(st, "SYN1", s, 1, 0.1, {"mode": "close"}, upstream_reason="no_bracketing_expiry")
        self.assertEqual(r.reason, "no_bracketing_expiry")
        r = SR.rank_v1(st, "SYN1", s, 1, 0.1, {"mode": "close"})
        self.assertEqual(r.reason, "insufficient_history")
        st, cal = _scalar_store([7] * 30)
        s = _sess(cal, 31, complete=False)
        r = SR.rank_v1(st, "SYN1", s, 1, 0.1, {"mode": "close"})
        self.assertEqual(r.reason, "session_not_complete")
        r = SR.rank_v1(st, "SYN1", _sess(cal, 31), 1, 0.1, {"mode": "close"})
        self.assertEqual(r.reason, "zero_range_history")
        for reason in SURFACE_REASONS:
            r = SR.rank_v1(st, "SYN1", _sess(cal, 31), 1, 0.1, {}, upstream_reason=reason)
            self.assertEqual((r.status, r.reason, r.labels), ("unavailable", reason, []))

    def test_x_and_tail(self):
        vals = list(range(100, 120)) * 2                # 40 values, each twice
        st, cal = _scalar_store([v * 1000 for v in vals])
        s = _sess(cal, 41)
        now = 110 * 1000 / 1e8
        r = SR.rank_v1(st, "SYN1", s, 1, now, {"x": 0})
        self.assertEqual((r.value["rank_le"], r.value["upper_share"], r.fired), (22, "1/2", False))
        top = SR.rank_v1(st, "SYN1", s, 1, now, {"x": 50})
        self.assertTrue(top.fired)                      # upper_share 20/40 <= 50/100, exact boundary
        self.assertFalse(SR.rank_v1(st, "SYN1", s, 1, now, {"x": Fraction(199, 4)}).fired)
        bot = SR.rank_v1(st, "SYN1", s, 1, now, {"x": 55, "tail": "bottom"})
        self.assertTrue(bot.fired)                      # lower_share 22/40 = 0.55, exact boundary
        self.assertFalse(SR.rank_v1(st, "SYN1", s, 1, now, {"x": "219/4", "tail": "bottom"}).fired)
        self.assertEqual(SR.rank_v1(st, "SYN1", s, 1, now, {"x": "5/2"}).params["x"], "5/2")
        self.assertTrue(SR.rank_v1(st, "SYN1", s, 1, 1.0, {"x": 0}).fired)             # above everything: upper_share 0
        self.assertTrue(SR.rank_v1(st, "SYN1", s, 1, now, {"x": 100}).fired)
        # x = 100 on a tie
        self.assertEqual(SR.rank_v1(st, "SYN1", s, 1, now, {}).params["x"], 5)

    def test_v9_skew_is_the_exact_difference_rounded_once(self):
        st, cal = _scalar_store([4_000_000] * 15 + [4_000_001] * 15, metric="skew25", conv="spot")
        s = SessionInfo(cal.ids[31], None, None, None, True, "live")
        rng = random.Random(7)
        for _ in range(3000):
            put = rng.random() * 0.8
            call = rng.random() * 0.8
            want = _round_half_even(Fraction(put) - Fraction(call))
            r = SR.rank_v9(st, "SYN1", s, 1, put, call, {})
            self.assertEqual(r.value["x"], _units_text(want), (put, call))

    def test_skew_differs_from_float_subtraction_on_planted_ties(self):
        """put - call in float arithmetic is rounded; the stored skew25 is the EXACT difference rounded once. Planted
        so that the exact difference sits within 4e-18 of a 10^-8 tie: the two rules give different units."""
        st, cal = _scalar_store([4_000_000] * 15 + [4_000_001] * 15, metric="skew25", conv="spot")
        s = SessionInfo(cal.ids[31], None, None, None, True, "live")
        rng = random.Random(11)
        differing = 0
        for _ in range(4000):
            put = 0.25 + rng.random() * 0.25
            k = rng.randrange(100_000, 30_000_000)
            tie = Fraction(2 * k + 1, 2 * 10 ** 8)
            call = float(Fraction(put) - tie)
            want = _round_half_even(Fraction(put) - Fraction(call))
            if round(Fraction(put - call) * 10 ** 8) != want:
                differing += 1
            r = SR.rank_v9(st, "SYN1", s, 1, put, call, {})
            self.assertEqual(r.value["x"], _units_text(want), (put, call))
        self.assertGreater(differing, 300)               # the planted cases do separate the two rules

    def test_x_zero_forms(self):
        st, cal = _scalar_store([10, 20, 30, 40] * 8)
        s = _sess(cal, 33)
        for x in (0, "0", Fraction(0), "0/7", Fraction(0, 3)):
            r = SR.rank_v1(st, "SYN1", s, 1, 1e-6, {"x": x, "min_sessions": 5})
            self.assertEqual(r.status, "available", x)
            self.assertEqual((r.params["x"], r.fired), (0, True), x)         # above every value: upper_share 0
            r = SR.rank_v1(st, "SYN1", s, 1, 3e-7, {"x": x, "min_sessions": 5})
            self.assertFalse(r.fired, x)
        for x in (100, "100", Fraction(100), "200/2", Fraction(1000, 10)):
            r = SR.rank_v1(st, "SYN1", s, 1, 3e-7, {"x": x, "min_sessions": 5})
            self.assertEqual((r.status, r.params["x"], r.fired), ("available", 100, True), x)
        for x in ("101", Fraction(1001, 10), "-1/2", Fraction(-1, 3), "1001/10"):
            r = SR.rank_v1(st, "SYN1", s, 1, 3e-7, {"x": x})
            self.assertEqual((r.status, r.code), ("invalid_input", "threshold_out_of_range"), x)

    def test_canonical_bytes_are_stable(self):
        st, cal = _scalar_store([10 + (i * 7) % 13 for i in range(40)])
        s = _sess(cal, 41)
        a = SR.rank_v1(st, "SYN1", s, 7, 0.15, {"x": 10})
        b = SR.rank_v1(st, "SYN1", s, 7, 0.15, {"x": 10})
        self.assertEqual(canonical_line(a), canonical_line(b))
        self.assertTrue(canonical_bytes([a, b]).endswith(b"\n"))
        for r in (a, SR.rank_v1(st, "SYN1", s, 7, 0.15, {"x": 200}), SR.rank_v1(st, "SYN1", s, 7, 0.15, {}, upstream_reason="no_atm_strike")):
            json.loads(canonical_line(r))


def _round_half_even(q):
    return round(q * 10 ** 8)


def _units_text(u):
    return ("-" if u < 0 else "") + "%d.%08d" % divmod(abs(u), 10 ** 8)


# ---- independent pure-Python reference and the differential --------------------------------------------------------------
# The reference models the ruled behaviour on plain lists (no store, no S02 code): retention by append count, last N
# available sessions, holes, short grids, ring lane, record conventions, the position order of the contract, the reason
# order of R-131 item 7, Fraction arithmetic for x and the shares.

ABSENT = object()
MT = "malformed_type"
LANES = ("stock", "etf_index")
FORMS = {"atm": "atm_iv", "30d": "iv30"}
UPSTREAM_ZERO = {"atm": "no_atm_strike", "30d": "no_bracketing_expiry"}


def _ref_x(x):
    t = type(x)
    if t is int or t is Fraction:
        return Fraction(x)
    if t is str and re.fullmatch(r"-?[0-9]+(/[0-9]+)?", x):
        try:
            return Fraction(x)
        except ZeroDivisionError:
            return None
    return None


def _ref_units(f):
    return round(Fraction(f) * 10 ** 8)


def _ref_share(a, n):
    f = Fraction(a, n)
    return f.numerator if f.denominator == 1 else "%d/%d" % (f.numerator, f.denominator)


def _finite_number(v):
    t = type(v)
    if t is float:
        return v - v == 0.0
    return t is int


def ref_eval(c):
    """(status, reason, code, value, fired, series_id, params, labels) of case dict `c`."""
    kind, p = c["kind"], c["params"]
    oid = OID[kind]
    lane = p.get("lane", "stock")
    lane_s = lane if type(lane) is str and lane in LANES else "stock"
    conv = "spot"
    form = "atm"
    series_tail = {"V1": "iv30_close", "V3": "atm_iv", "V9": "skew25"}[kind]
    sel = p.get("iv_form") if kind == "V3" else p.get("delta_convention") if kind == "V9" else None
    if type(sel) is str:                       # the series of a valid requested form, also on an invalid result
        series_tail = (FORMS if kind == "V3" else {"spot": "skew25", "forward": "skew25_fwd"}).get(sel, series_tail)

    def out(status, reason=None, code=None, value=None, fired=None, params=None, labels=()):
        return dict(status=status, reason=reason, code=code, value=value, fired=fired,
                    series_id="%s/%s/%s" % (c["underlying"], lane_s, series_tail), params=params, labels=sorted(set(labels)),
                    output_id=oid, lane=lane_s)

    def bad(code):
        return out("invalid_input", code=code)
    mode = p.get("mode", "intraday")
    if type(mode) is not str:
        return bad(MT)
    if mode not in ("intraday", "close") or (kind == "V3" and mode != "intraday"):
        return bad("invalid_mode")
    if type(lane) is not str:
        return bad(MT)
    if lane not in LANES:
        return bad("invalid_lane")
    sid = c["session_id"]
    ids = [i for i, _ in c["cal"]]
    if sid not in ids:
        return bad("session_not_in_calendar")
    pos = ids.index(sid)
    tag = p["feed_delay_tag"] if "feed_delay_tag" in p else c["tag"]
    if type(tag) is not str or tag not in ("live", "delayed"):
        return bad(MT)
    tail = p.get("tail")
    if tail is not None and (type(tail) is not str or tail not in ("top", "bottom")):
        return bad(MT)
    mn = p.get("min_sessions")
    mn = 20 if mn is None else mn
    if type(mn) is not int or mn < 1:
        return bad(MT)
    mx = p.get("max_sessions")
    mx = 252 if mx is None else mx
    if type(mx) is not int or mx < 1:
        return bad(MT)
    up = c["upstream"]
    if up is not None and (type(up) is not str or up not in SURFACE_REASONS):
        return bad(MT)
    if up is None:
        vals = (c["put"], c["call"]) if kind == "V9" else (c["now"],)
        if not all(_finite_number(v) for v in vals):
            return bad(MT)
    if mx < mn:
        return bad("invalid_session_window")
    if kind == "V3":
        form = p.get("iv_form", "atm")
        if type(form) is not str:
            return bad(MT)
        if form not in FORMS:
            return bad("iv_form_not_allowed")
        series_tail = FORMS[form]
    if kind == "V9":
        conv = p.get("delta_convention", "spot")
        if type(conv) is not str:
            return bad(MT)
        if conv not in ("spot", "forward"):
            return bad("convention_not_allowed")
        series_tail = "skew25" if conv == "spot" else "skew25_fwd"
    x = p.get("x")
    xv = Fraction(5) if x is None else _ref_x(x)
    if xv is None:
        return bad(MT)
    if xv < 0 or xv > 100:
        return bad("threshold_out_of_range")
    minute = None
    if kind == "V3":
        minute = p.get("minute")
        if type(minute) is not int:
            return bad(MT)
        if minute < 0 or minute >= c["cal"][pos][1]:
            return bad("minute_out_of_range")
    # history: the retained records (last k appended), same lane, complete, before the session
    recs = c["records"][-c["k"]:] if c["records"] else []
    selected = []
    if c["ring_lane"] == lane:
        for (idx, payload, comp, rconv) in recs:
            if idx >= pos or not comp:
                continue
            if kind == "V3":
                if len(payload) <= minute or payload[minute] == 0:
                    continue
                selected.append((idx, payload[minute], rconv))
            else:
                selected.append((idx, payload, rconv))
        selected = selected[-mx:]
    if kind == "V9" and any((rc or "spot") != conv for _, _, rc in selected):
        return bad("convention_mismatch")
    if tag == "delayed" and (kind == "V3" or mode == "intraday"):
        return bad("delayed_feed_tag")
    params = {"max_sessions": mx, "min_sessions": mn, "mode": mode,
              "x": 5 if x is None else (x if type(x) is int else _ref_share(xv.numerator, xv.denominator))}
    if kind != "V3":
        params["tail"] = tail or "top"
    if kind == "V3":
        params["iv_form"] = form
        params["minute"] = minute
    if kind == "V9":
        params["delta_convention"] = conv
    labels = list(c["labels"]) + (["delayed"] if tag == "delayed" else [])

    def na(reason):
        return out("unavailable", reason=reason, params=params)
    if up is not None:
        return na(up)
    if kind == "V9":
        now_u = _ref_units(Fraction(c["put"]) - Fraction(c["call"]))
    else:
        now_u = _ref_units(Fraction(c["now"]))
    if kind == "V3" and now_u == 0:
        return na(UPSTREAM_ZERO[form])
    values = [v for _, v, _ in selected]
    n = len(values)
    if n < mn:
        return na("insufficient_history")
    if mode == "close" and not c["complete"]:
        return na("session_not_complete")
    if min(values) == max(values):
        return na("zero_range_history")
    le = sum(1 for v in values if v <= now_u)
    ge = sum(1 for v in values if v >= now_u)
    value = {"x": _units_text(now_u), "n": n}
    if kind == "V3":
        value.update(minute=minute, rank_le=le, upper_share=_ref_share(ge, n))
    else:
        value.update(rank_le=le, upper_share=_ref_share(ge, n), lower_share=_ref_share(le, n),
                     form="intraday" if mode == "intraday" else "end_of_day")
    share = Fraction(le, n) if (tail == "bottom" and kind != "V3") else Fraction(ge, n)
    fired = share <= xv / 100
    return out("available", value=value, fired=fired, params=params, labels=labels)


_POOLS = {
    "mode": ["intraday"] * 12 + ["close"] * 5 + ["weekly", 5, None],
    "lane": ["stock"] * 14 + ["etf_index", "ETF", 3, None],
    "feed_delay_tag": ["live", "delayed", "x", None, 5],
    "min_sessions": [None, 1, 2, 3, 5, 10, 20, 20, 0, -1, True, "3", 2.5],
    "max_sessions": [None, 252, 30, 12, 5, 3, 1, 0, True, 2.5],
    "tail": [None, "top", "bottom", "middle", 5],
    "x": [None, 5, 0, 100, 101, -1, 1, 50, 10, 25, "5/2", "7", Fraction(5, 2), Fraction(33, 4), 5.0, True,
          Decimal(5), "abc", "1/0", "-3", 3.3, "0", Fraction(0), "0/3", "200/2", Fraction(100), "1001/10", Fraction(-1, 4)],
    "iv_form": ["atm", "30d", "90d", "ATM", "", 5, None],
    "delta_convention": ["spot", "forward", "Forward", "", 7, None, True],
}
_PROB = {"mode": .25, "lane": .15, "feed_delay_tag": .1, "min_sessions": .5, "max_sessions": .3, "tail": .4, "x": .85,
         "iv_form": .5, "delta_convention": .55}


def _pick(rng, name, hostile):
    pool = _POOLS[name]
    if not hostile:
        if name == "max_sessions":
            return rng.choice((None, 252, 252, 30, 25))
        if name == "min_sessions":
            return rng.choice((None, 1, 2, 3, 5, 10, 10, 20))
        good = [v for v in pool if v is not None and type(v) in (str, int, Fraction) and v is not True
                and not (name == "x" and (v in (101, -1, "abc", "1/0", "-3", "1001/10", Fraction(-1, 4)) or type(v) is bool))
                and not (name in ("min_sessions", "max_sessions") and (v == 0 or v == -1 or v == "3"))
                and not (name == "mode" and v in ("weekly", 5)) and not (name == "lane" and v in ("ETF", 3))
                and not (name in ("iv_form", "delta_convention") and v in ("90d", "ATM", "", 5, "Forward", 7, True))
                and not (name == "tail" and v in ("middle", 5)) and not (name == "feed_delay_tag" and v in ("x", 5))]
        return rng.choice(good) if good else rng.choice(pool)
    return rng.choice(pool)


def gen_case(rng, big=False):
    kind = rng.choice(("V1", "V3", "V9"))
    hostile = rng.random() < 0.3
    ncal = rng.choice((70, 100, 270)) if big else rng.choice((24, 40, 70))
    mins = rng.choice((6, 12, 12, 30))
    half = {i: rng.randrange(1, mins) for i in range(rng.randrange(0, ncal, 9), ncal, 11)} if rng.random() < .6 else {}
    cal = [("S%04d" % i, half.get(i, mins)) for i in range(ncal)]
    cur = (ncal - 1 - rng.randrange(0, 6) if rng.random() > .3 else rng.randrange(5, ncal)) if rng.random() > .04 else None
    session_id = "S%04d" % cur if cur is not None else "S9999"
    cur_pos = cur if cur is not None else ncal // 2
    p = {}
    for name, prob in _PROB.items():
        if name == "iv_form" and kind != "V3" or name == "delta_convention" and kind != "V9":
            if rng.random() < .15:
                p[name] = _pick(rng, name, True)              # ignored by that output
            continue
        if rng.random() < prob:
            p[name] = _pick(rng, name, hostile)
    if kind == "V3":
        r = rng.random()
        p["minute"] = (rng.randrange(0, mins) if r < .8 else
                       rng.choice((mins, mins + 3, -1, None, True, 2.0, "1")) if hostile else rng.randrange(0, mins))
    tie_heavy = rng.random() < .5
    lo, hi = (1, rng.choice((3, 8, 30))) if tie_heavy else (1, 10 ** 8)
    hole_p = rng.choice((0, 0, .05, .3, 1.0)) if kind == "V3" else 0
    n_rec = rng.choice((0, 3, 12, 25, 30, 30, 45, 60, 60)) if not big else rng.choice((200, 253, 270))
    n_rec = min(n_rec, ncal)
    idxs = sorted(rng.sample(range(ncal), n_rec))
    if cur is not None and rng.random() < .5 and cur not in idxs and idxs:
        idxs = sorted(idxs + [cur])
    nat = {"V9": "spot"}.get(kind)
    ring_lane = "stock" if rng.random() < .9 else "etf_index"
    lane_ok = p.get("lane", "stock") == ring_lane
    records = []
    for idx in idxs:
        comp = rng.random() < .9
        if kind == "V3":
            glen = cal[idx][1] if rng.random() < .93 else rng.randrange(1, cal[idx][1] + 1)
            grid = [0 if rng.random() < hole_p else rng.randint(lo, hi) for _ in range(glen)]
            payload = grid
        else:
            payload = rng.randint(lo, hi) if kind == "V1" else rng.randint(-hi, hi)
            if kind == "V9" and rng.random() < .03:
                payload = 0
        records.append((idx, payload, comp, None))
    conv_req = p.get("delta_convention", "spot")
    metric_conv = "forward" if conv_req == "forward" else "spot"
    if kind == "V9":
        flip = rng.random() < .04
        records = [(i, pl, cp, (("forward" if metric_conv == "spot" else "spot") if flip and rng.random() < .3 else
                                (metric_conv if rng.random() < .8 else None if metric_conv == "spot" else metric_conv)))
                   for i, pl, cp in [(a, b, c_) for a, b, c_, _ in records]]
    k = rng.choice((252, 252, 60, 30, 20, 5))
    # now: around the history values so that ties, extremes and holes are hit
    pool_vals = [pl[rng.randrange(len(pl))] if kind == "V3" and pl else pl for _, pl, _, _ in records] if records else [5]
    base = rng.choice(pool_vals) if pool_vals else 5
    if rng.random() < .5:
        base += rng.choice((-2, -1, 0, 0, 0, 1, 2))
    now_u = base if kind != "V9" else base + rng.choice((0, 0, 1, -3))
    c = dict(kind=kind, cal=cal, k=k, ring_lane=ring_lane, records=records, underlying="U%d" % rng.randrange(3),
             session_id=session_id, tag=rng.choice(("live",) * 6 + ("delayed",)),
             complete=rng.random() < .7, params=p, labels=rng.choice((("exact-model",), ("exact-model", "approximate"), ())),
             upstream=None, now=None, put=None, call=None)
    if rng.random() < .07:
        c["upstream"] = rng.choice(list(SURFACE_REASONS) + ["bogus", 5])
    if kind == "V9":
        callv = rng.random() * .6
        c["call"] = callv
        c["put"] = callv + (now_u / 1e8)
        if rng.random() < .1:
            c["put"] = c["call"]
    else:
        c["now"] = now_u / 1e8
        if rng.random() < .04:
            c["now"] = rng.choice((None, "1", float("nan"), True, -0.0, 0.0, 4e-9))
    if kind == "V9" and rng.random() < .03:
        c["put"] = rng.choice((None, float("inf"), True))
    c["_metric"] = None
    return c


def build_case_store(c):
    cal = Calendar(c["cal"])
    st = HistoryStore(cal, k=20)
    kind = c["kind"]
    if kind == "V3":
        series_tail = FORMS.get(c["params"].get("iv_form", "atm"), "atm_iv") if type(c["params"].get("iv_form", "atm")) is str else "atm_iv"
        metric = series_tail
    elif kind == "V1":
        metric = "iv30_close"
    else:
        cv = c["params"].get("delta_convention", "spot")
        metric = "skew25_fwd" if cv == "forward" else "skew25"
    lane_s = c["params"].get("lane", "stock")
    lane_s = lane_s if type(lane_s) is str else "stock"
    series = "%s/%s/%s" % (c["underlying"], lane_s, metric)
    if c["records"]:
        st.add_series(series, c["k"])
    for idx, payload, comp, rconv in c["records"]:
        if kind == "V3":
            st.append(series, metric, 0, cal.ids[idx], list(payload), complete=comp, lane=c["ring_lane"])
        else:
            st.append(series, metric, 0, cal.ids[idx], [], total=payload, complete=comp, lane=c["ring_lane"],
                      delta_convention=rconv)
    return st


def run_case(c, st):
    sess = SessionInfo(c["session_id"], None, None, None, c["complete"], c["tag"])
    kw = dict(params=dict(c["params"]), upstream_reason=c["upstream"], labels=c["labels"])
    if c["kind"] == "V9":
        return SR.rank_v9(st, c["underlying"], sess, 5, c["put"], c["call"], **kw)
    return FN[c["kind"]](st, c["underlying"], sess, 5, c["now"], **kw)


def same(got, ref):
    return (got.status, got.reason, got.code, got.value, got.fired, got.series_id, got.params, got.labels,
            got.output_id, got.lane) == (ref["status"], ref["reason"], ref["code"], ref["value"], ref["fired"],
                                         ref["series_id"], ref["params"], ref["labels"], ref["output_id"], ref["lane"])


class Differential(unittest.TestCase):
    N = 20400

    def test_against_the_pure_python_reference(self):
        rng = random.Random(20261031)
        stats = {}
        diffs = []
        for i in range(self.N):
            c = gen_case(rng, big=(i % 400 == 0))
            st = build_case_store(c)
            got = run_case(c, st)
            ref = ref_eval(c)
            key = (c["kind"], ref["status"], ref["reason"] or ref["code"])
            stats[key] = stats.get(key, 0) + 1
            if not same(got, ref):
                diffs.append((i, c["kind"], got, ref))
                if len(diffs) > 5:
                    break
        self.assertEqual(diffs, [], diffs[:2])
        avail = sum(v for k, v in stats.items() if k[1] == "available")
        self.assertGreater(avail, 3000, stats)
        for kind in ("V1", "V3", "V9"):
            self.assertGreater(sum(v for k, v in stats.items() if k[0] == kind and k[1] == "available"), 700, kind)
        for code in ("convention_mismatch", "delayed_feed_tag", "minute_out_of_range", "threshold_out_of_range",
                     "iv_form_not_allowed", "convention_not_allowed", "invalid_session_window", "session_not_in_calendar",
                     "invalid_mode", "invalid_lane", MT):
            self.assertGreater(sum(v for k, v in stats.items() if k[2] == code), 20, code)
        for reason in ("insufficient_history", "zero_range_history", "session_not_complete", "no_atm_strike"):
            self.assertGreater(sum(v for k, v in stats.items() if k[2] == reason), 20, reason)


class S09Parity(unittest.TestCase):
    """The codes of the shared S09 list (validate_request) equal this module's on the same parameters (empty chain, valid
    spot and rates): the positions 4, 5, 10, 13, 15, 16 and 18 cannot drift apart."""
    N = 6000

    def test_codes_equal_validate_request(self):
        rng = random.Random(5)
        cal = Calendar([("S%04d" % i, 12) for i in range(50)])
        st = HistoryStore(cal, k=20)
        n = 0
        for _ in range(self.N):
            kind = rng.choice(("V1", "V3", "V9"))
            hostile = True
            p = {}
            for name, prob in _PROB.items():
                if name == "iv_form" and kind != "V3" or name == "delta_convention" and kind != "V9":
                    continue
                if rng.random() < prob:
                    p[name] = _pick(rng, name, hostile)
            if kind == "V3":
                p["minute"] = rng.choice((0, 5, 11, 12, -1, True, 2.0, 7))
            if p.get("min_sessions") is not None and p.get("max_sessions") is not None:
                # the S09 request list has no window code; keep the pair ordered when both are plain ints
                pass
            tag = rng.choice(("live", "delayed"))
            sess = SessionInfo("S0030", None, None, None, True, tag)
            s09 = dict(p)
            s09["evaluation_ns"] = 5
            s09.setdefault("feed_delay_tag", tag)
            s09["session_minutes"] = 12
            oid = OID[kind]
            want = V.validate_request(oid, [], "100", "0.05", "0.01", 5, s09, validate="full")
            kw = dict(params=dict(p))
            if kind == "V9":
                got = SR.rank_v9(st, "U", sess, 5, 0.2, 0.1, cutoff_ns=5, **kw)
            else:
                got = FN[kind](st, "U", sess, 5, 0.2, cutoff_ns=5, **kw)
            mn, mx = p.get("min_sessions"), p.get("max_sessions")
            ints = type(mn) in (int, type(None)) and type(mx) in (int, type(None)) and (mn is None or mn >= 1) \
                and (mx is None or mx >= 1)
            if ints and (20 if mn is None else mn) > (252 if mx is None else mx):
                continue                                  # invalid_session_window has no S09 request-list position
            self.assertEqual(got.code if got.status == "invalid_input" else None, want, (kind, p, tag))
            n += 1
        self.assertGreater(n, self.N * .9)


# ---- perf smoke (W06 / W07) -------------------------------------------------------------------------------------------
# Dense synthetic fixture: every session of the 252-session ring holds all 390 grid minutes, no zero point, so the
# minute reads take the contiguous-block path of the S02 store. Smoke checks only (GATE_BUDGETS section 8 rule 7).

PERF_NAMES = 12
SESSIONS = 252
MINUTES = 390
MINUTE = 195
B5 = {"V1": 50e-6, "V9": 50e-6, "V3": 150e-6}
B5N = {"V1": 20e-3, "V9": 20e-3, "V3": 50e-3}


def dense_store(names=PERF_NAMES, sessions=SESSIONS):
    cal = Calendar([("S%04d" % i, MINUTES) for i in range(sessions + 5)])
    st = HistoryStore(cal, k=20)
    tmpl = [((j * 2654435761) % 400001) - 200000 for j in range(MINUTES)]
    for n in range(names):
        base = 15_000_000 + (n * 7919) % 40_000_000
        for metric, conv in (("iv30_close", None), ("skew25", "spot"), ("iv30", None), ("atm_iv", None)):
            st.add_series("N%d/stock/%s" % (n, metric), 252)
        for s in range(sessions):
            sid = cal.ids[s]
            close = base + (s * 104729 + n * 31) % 6_000_001 - 3_000_000
            st.append("N%d/stock/iv30_close" % n, "iv30_close", 0, sid, [], total=close)
            st.append("N%d/stock/skew25" % n, "skew25", 0, sid, [], total=(s * 7727 + n * 13) % 8_000_001 - 4_000_000,
                      delta_convention="spot")
            st.append("N%d/stock/iv30" % n, "iv30", 0, sid, [close + t for t in tmpl])
            st.append("N%d/stock/atm_iv" % n, "atm_iv", 0, sid, [close - 400_000 + t for t in tmpl])
    return st, cal


def _perf_sweep(st, cal, names, calls_per_series=1, record=None):
    """One pass over `names` name slots x the families; returns {family: total seconds} and, when `record` is a dict,
    appends per-call times."""
    sess = SessionInfo(cal.ids[SESSIONS], None, None, None, True, "live")
    clock = time.perf_counter
    tot = {"V1": 0.0, "V9": 0.0, "V3a": 0.0, "V3d": 0.0}
    for slot in range(names):
        u = "N%d" % (slot % PERF_NAMES)
        for fam, call in (("V1", lambda: SR.rank_v1(st, u, sess, 1, 0.30, None)),
                          ("V9", lambda: SR.rank_v9(st, u, sess, 1, 0.31, 0.30, None)),
                          ("V3a", lambda: SR.rank_v3(st, u, sess, 1, 0.30, {"minute": MINUTE, "iv_form": "atm"})),
                          ("V3d", lambda: SR.rank_v3(st, u, sess, 1, 0.30, {"minute": MINUTE, "iv_form": "30d"}))):
            t0 = clock()
            r = call()
            dt = clock() - t0
            if r.status == "invalid_input":
                raise AssertionError(r)
            tot[fam] += dt
            if record is not None:
                record[fam].append(dt)
    return tot


def _p95(xs):
    s = sorted(xs)
    return s[max(0, -(-len(s) * 95 // 100) - 1)]


_DENSE = {}


def _dense():
    if "st" not in _DENSE:
        _DENSE["st"], _DENSE["cal"] = dense_store()
    return _DENSE["st"], _DENSE["cal"]


class PerfSmoke(unittest.TestCase):
    def test_w06_b5_per_series_smoke(self):
        st, cal = _dense()

        def sample():
            rec = {"V1": [], "V9": [], "V3a": [], "V3d": []}
            for _ in range(12):
                _perf_sweep(st, cal, PERF_NAMES, record=rec)
            return {k: _p95(v) for k, v in rec.items()}
        budget = {"V1": B5["V1"], "V9": B5["V9"], "V3a": B5["V3"], "V3d": B5["V3"]}
        best, used = H.best_of(sample, lambda a, b: {k: min(a[k], b[k]) for k in a},
                               lambda d: all(d[k] <= budget[k] for k in d))
        print("\nW06 M3A-B5 smoke (%d names x 252 sessions x 390 minutes, dense; best of %d): %s (budget V1/V9 <= 50 us, "
              "V3 <= 150 us each form; %s)" % (PERF_NAMES, used, {k: "%.1f us p95" % (v * 1e6) for k, v in best.items()},
                                               LABEL))
        for k, v in best.items():
            self.assertLessEqual(v, budget[k], k)

    def test_w07_b5n_103_names_smoke(self):
        st, cal = _dense()

        def sample():
            best = None
            for _ in range(5):
                t = _perf_sweep(st, cal, 103)
                best = t if best is None else {k: min(best[k], t[k]) for k in t}
            return best
        budget = {"V1": B5N["V1"], "V9": B5N["V9"], "V3a": B5N["V3"], "V3d": B5N["V3"]}
        best, used = H.best_of(sample, lambda a, b: {k: min(a[k], b[k]) for k in a},
                               lambda d: all(d[k] <= budget[k] for k in d))
        print("\nW07 M3A-B5n smoke (103 name slots over %d dense names; best of %d): %s (budget V1/V9 <= 20 ms, V3 <= 50 ms "
              "each form; %s)" % (PERF_NAMES, used, {k: "%.2f ms" % (v * 1e3) for k, v in best.items()}, LABEL))
        for k, v in best.items():
            self.assertLessEqual(v, budget[k], k)

    def test_dense_fixture_takes_the_block_path(self):
        """A dense fixture must never fall to the per-record fallback of the S02 read (a failure to investigate)."""
        st, cal = _dense()
        probes = []
        real = MH._probe
        MH._probe = lambda r, m: (probes.append(1), real(r, m))[1]
        try:
            _perf_sweep(st, cal, PERF_NAMES)
        finally:
            MH._probe = real
        self.assertEqual(probes, [])
        for n in range(PERF_NAMES):
            c = st.m3a_cols("N%d/stock/iv30" % n, "iv30", 0)
            self.assertIsNotNone(c.mv)
            self.assertTrue(all(c.inb) and all(c.done))


# ---- bench (Developer evidence, not a gate): fresh process, warm-up, 30 repeats -------------------------------------------
# The 103-name W06/W07 store: the Tester generator's values (qualification/.../author4/gen_m3a_workloads.py) re-implemented
# here; the rank truth is checked against the manifest sha256 before anything is timed.

M64 = (1 << 64) - 1


class _SplitMix:
    def __init__(self, seed):
        self.s = seed & M64

    def next(self):
        self.s = (self.s + 0x9E3779B97F4A7C15) & M64
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
        return z ^ (z >> 31)


def _mix(seed, *ints):
    h = _SplitMix(seed ^ 0xA5A5A5A5)
    v = 0
    for i in ints:
        h.s = (h.s + (i & M64) * 0x9E3779B97F4A7C15) & M64
        v = h.next()
    return v


def _name_base(n, seed):
    return 15_000_000 + _mix(seed, 1, n) % 45_000_000


def _history_close(n, series, s, seed):
    if series == "iv30_close":
        b = _name_base(n, seed)
        return b if n == 101 else b + (_mix(seed, 2, n, s) % 6_000_001) - 3_000_000
    if series == "atm_iv_close":
        b = _name_base(n, seed) - 400_000
        return b if n == 101 else b + (_mix(seed, 14, n, s) % 6_000_001) - 3_000_000
    if series == "skew25_fwd":
        return 0 if n == 101 else ((_mix(seed, 16, n) % 8_000_001) - 4_000_000) + (_mix(seed, 17, n, s) % 1_000_001) - 500_000
    if series == "skew25":
        return 0 if n == 101 else ((_mix(seed, 3, n) % 8_000_001) - 4_000_000) + (_mix(seed, 4, n, s) % 1_000_001) - 500_000
    if series == "term_30_91":
        return 0 if n == 101 else ((_mix(seed, 5, n) % 6_000_001) - 3_000_000) + (_mix(seed, 6, n, s) % 1_000_001) - 500_000
    raise KeyError(series)


def _history_grid(n, s, seed, kind="iv30", upto=MINUTES):
    base = _history_close(n, "iv30_close" if kind == "iv30" else "atm_iv_close", s, seed)
    x = _mix(seed, 7 if kind == "iv30" else 15, n, s)
    out = []
    for _ in range(upto):
        x = (x * 6364136223846793005 + 1442695040888963407) & M64
        out.append(base + ((x >> 40) % 400_001) - 200_000)
    return out


_PLAN = ["top_unique", "top_tie", "top5pct", "median", "bottom_tie", "bottom_unique", "second_from_top", "bottom5pct"]


def _today_value(n, hist):
    if n == 101:
        return hist[0]
    p = _PLAN[n % 8]
    h = sorted(hist)
    return {"top_unique": lambda: h[-1] + 1, "top_tie": lambda: h[-1], "top5pct": lambda: h[len(h) - 13],
            "median": lambda: h[len(h) // 2], "bottom_tie": lambda: h[0], "bottom_unique": lambda: h[0] - 1,
            "second_from_top": lambda: h[-2], "bottom5pct": lambda: h[12]}[p]()


def _rank_truth(x, hist):
    n = len(hist)
    le = sum(1 for v in hist if v <= x)
    ge = sum(1 for v in hist if v >= x)
    if max(hist) == min(hist):
        return {"status": "unavailable", "reason": "zero_range_history", "n": n}
    return {"status": "available", "reason": None, "n": n, "rank_le": le, "upper_share": str(Fraction(ge, n)),
            "lower_share": str(Fraction(le, n))}


def _manifest():
    return json.loads((H.set_dir("author4") / "m3a_workload_manifest.json").read_text(encoding="utf-8"))


def _truth_line(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class BenchGenerator(unittest.TestCase):
    def test_generator_matches_the_manifest_samples(self):
        man = _manifest()
        seed = man["seed"]
        got = []
        for series in ("iv30_close", "skew25", "skew25_fwd", "atm_iv_close"):
            hist = [_history_close(0, series, s, seed) for s in range(1, 253)]
            x = _today_value(0, hist)
            got.append({"name": 0, "series": series, "x": x, **_rank_truth(x, hist)})
        for kind, nm in (("iv30", "iv30_min@195"), ("atm", "atm_iv_min@195")):
            grid = [_history_grid(0, s, seed, kind, MINUTE + 1)[MINUTE] for s in range(1, 253)]
            x = _today_value(0, grid)
            got.append({"name": 0, "series": nm, "x": x, **_rank_truth(x, grid)})
        want = man["rank_truth"]["samples"]
        order = ("iv30_close", "skew25", "skew25_fwd", "atm_iv_close", "iv30_min@195", "atm_iv_min@195")
        by = {g["series"]: g for g in got}
        self.assertEqual([by[s] for s in order], want)


def bench_build(path):
    """Write the 103-name store (7 series per name, 252 sessions, 390-minute dense grids) as a binary snapshot and the
    today-values / truth next to it. Checks the rank truth against the manifest sha256 first."""
    man = _manifest()
    seed = man["seed"]
    names, sessions = man["rank_truth"]["names"], 252
    lines, today = [], {}
    for n in range(names):
        for series in ("iv30_close", "skew25", "skew25_fwd", "atm_iv_close"):
            hist = [_history_close(n, series, s, seed) for s in range(1, sessions + 1)]
            x = _today_value(n, hist)
            today[(n, series)] = x
            lines.append(_truth_line({"name": n, "series": series, "x": x, **_rank_truth(x, hist)}))
        for kind, nm in (("iv30", "iv30_min@195"), ("atm", "atm_iv_min@195")):
            grid = [_history_grid(n, s, seed, kind, MINUTE + 1)[MINUTE] for s in range(1, sessions + 1)]
            x = _today_value(n, grid)
            today[(n, nm)] = x
            lines.append(_truth_line({"name": n, "series": nm, "x": x, **_rank_truth(x, grid)}))
    sha = hashlib.sha256(("\n".join(lines) + "\n").encode("ascii")).hexdigest()
    assert sha == man["rank_truth"]["sha256"], "rank truth differs from the manifest"
    cal = Calendar([("S%04d" % i, MINUTES) for i in range(sessions + 4)])
    st = HistoryStore(cal, k=20)
    t0 = time.perf_counter()
    for n in range(names):
        u = "N%03d" % n
        for metric in ("iv30_close", "skew25", "skew25_fwd", "term_30_91", "atm_iv_close", "iv30", "atm_iv"):
            st.add_series("%s/stock/%s" % (u, metric), 252)
        for s in range(1, sessions + 1):
            sid = cal.ids[s - 1]
            for metric, conv in (("iv30_close", None), ("skew25", "spot"), ("skew25_fwd", "forward"), ("term_30_91", None),
                                 ("atm_iv_close", None)):
                st.append("%s/stock/%s" % (u, metric), metric, 0, sid, [], total=_history_close(n, metric, s, seed),
                          delta_convention=conv)
            st.append("%s/stock/iv30" % u, "iv30", 0, sid, _history_grid(n, s, seed, "iv30"))
            st.append("%s/stock/atm_iv" % u, "atm_iv", 0, sid, _history_grid(n, s, seed, "atm"))
    st.binary_snapshot_to(path)
    meta = {"records": st.stats()["records"], "content_hash": st.content_hash(), "names": names,
            "today": {"%d|%s" % k: v for k, v in today.items()}, "truth_lines": lines, "build_s": time.perf_counter() - t0}
    with open(path + ".meta.json", "w") as f:
        json.dump(meta, f)
    print(json.dumps({"built": path, "records": meta["records"], "rank_truth_sha256_ok": True}))
    if os.environ.get("S08_BENCH_DIRECT") == "1":          # also time the store exactly as appended (no snapshot attach)
        bench_run(path, direct_store=st)


def bench_run(path, repeats=30, direct_store=None):
    """One fresh process: attach, build the layout, correctness pass against the truth lines (untimed), one warm-up pass,
    `repeats` timed passes. Prints one JSON line: per-series per-call p50/p95 (30 x 103 calls per family and form) and
    the 103-name wall p50/p95 (B5n), plus the fixture density facts."""
    meta = json.load(open(path + ".meta.json"))
    cal = Calendar([("S%04d" % i, MINUTES) for i in range(252 + 4)])
    st = direct_store or HistoryStore.attach_binary(path, cal, expected_content_hash=meta["content_hash"])
    st.build_m3a_layout()
    frozen = os.environ.get("S08_BENCH_FREEZE", "1") == "1"
    if frozen:                                  # the runner rule (IO contract section 7): gc.freeze() after the store load
        import gc
        gc.collect()
        gc.freeze()
    names = meta["names"]
    truth = {}
    for ln in meta["truth_lines"]:
        o = json.loads(ln)
        truth[(o["name"], o["series"])] = o
    sess = SessionInfo(cal.ids[252], None, None, None, True, "live")
    today = {tuple([int(k.split("|")[0]), k.split("|")[1]]): v for k, v in meta["today"].items()}

    NAMES = ["N%03d" % n for n in range(names)]
    args = {"V1": [(NAMES[n], today[(n, "iv30_close")] / 1e8) for n in range(names)],
            "V9": [(NAMES[n], today[(n, "skew25")] / 1e8) for n in range(names)],
            "V3a": [(NAMES[n], today[(n, "atm_iv_min@195")] / 1e8) for n in range(names)],
            "V3d": [(NAMES[n], today[(n, "iv30_min@195")] / 1e8) for n in range(names)]}
    p_atm, p_30d = {"minute": MINUTE, "iv_form": "atm"}, {"minute": MINUTE, "iv_form": "30d"}

    def call(fam, n):
        u, v = args[fam][n]
        if fam == "V1":
            return SR.rank_v1(st, u, sess, 1, v, None)
        if fam == "V9":
            return SR.rank_v9(st, u, sess, 1, v, 0.0, None)
        if fam == "V3a":
            return SR.rank_v3(st, u, sess, 1, v, p_atm)
        return SR.rank_v3(st, u, sess, 1, v, p_30d)
    tkey = {"V1": "iv30_close", "V9": "skew25", "V3a": "atm_iv_min@195", "V3d": "iv30_min@195"}
    probes = []
    real = MH._probe
    MH._probe = lambda r, m: (probes.append(1), real(r, m))[1]
    wrong = 0
    try:
        for fam in tkey:
            for n in range(names):
                r = call(fam, n)
                t = truth[(n, tkey[fam])]
                if t["status"] == "unavailable":
                    ok = (r.status, r.reason) == ("unavailable", t["reason"])
                else:
                    ok = (r.status == "available" and r.value["n"] == t["n"] and r.value["rank_le"] == t["rank_le"]
                          and Fraction(str(r.value["upper_share"])) == Fraction(t["upper_share"]))
                    if fam != "V3a" and fam != "V3d":
                        ok = ok and Fraction(str(r.value["lower_share"])) == Fraction(t["lower_share"])
                wrong += 0 if ok else 1
    finally:
        MH._probe = real
    fams = ("V1", "V9", "V3a", "V3d")
    skew_note = "V9 now = today skew25 (put - 0.0)"
    for fam in fams:                       # warm-up pass
        for n in range(names):
            call(fam, n)
    per = {f: [] for f in fams}
    wall = {f: [] for f in fams}
    clock = time.perf_counter_ns
    for _ in range(repeats):
        for fam in fams:
            t_all = clock()
            for n in range(names):
                t0 = clock()
                call(fam, n)
                per[fam].append(clock() - t0)
            wall[fam].append(clock() - t_all)

    def q(xs, p):
        s = sorted(xs)
        return s[max(0, -(-len(s) * p // 100) - 1)]
    out = {"gc_frozen": frozen, "repeats": repeats, "names": names, "wrong_results": wrong, "per_series_calls": len(per["V1"]),
           "probe_fallback_calls": len(probes), "records": st.stats()["records"], "note": skew_note,
           "per_call_us": {f: {"p50": q(per[f], 50) / 1e3, "p95": q(per[f], 95) / 1e3, "max": max(per[f]) / 1e3} for f in fams},
           "sweep_ms": {f: {"p50": q(wall[f], 50) / 1e6, "p95": q(wall[f], 95) / 1e6, "max": max(wall[f]) / 1e6} for f in fams}}
    print(json.dumps(out))
    if direct_store is None:
        st.close_mapping()


if __name__ == "__main__" and len(sys.argv) >= 3 and sys.argv[1] in ("--bench-build", "--bench-run"):
    if sys.argv[1] == "--bench-build":
        bench_build(sys.argv[2])
    else:
        bench_run(sys.argv[2])
elif __name__ == "__main__":
    unittest.main()
