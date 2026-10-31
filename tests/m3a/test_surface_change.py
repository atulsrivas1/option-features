"""S07 change outputs V4 (M3A-3), V7 (M3A-6), V10 (M3A-9): prior readings.

First owner of author3 m3a_cases_v4.json (80 rows incl. V4-S-01..09 and V4-Cx1), m3a_cases_v7.json (44) and
m3a_cases_v10.json (64) = 188 rows, one test method per row id; uses author3 m3a_g5_priors.json. Plus: hand-built frame
unit tests, hostile-input guards, a Developer differential (>= 20,000 random cases against a pure-Python reference with
exact Fraction rounding) and a Developer perf SMOKE check (M3A-B4 share; not gate evidence, GATE_BUDGETS section 8
rule 7).

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12
"""
import json
import math
import random
import time
import unittest
from fractions import Fraction

import adapt_surface_change as A
import m3a_harness as H
from option_features import m3a_common as C
from option_features import surface_change as SC
from option_features.flowgrid import Calendar
from option_features.flowstore import HistoryStore

FILES = (("V4", "m3a_cases_v4.json"), ("V7", "m3a_cases_v7.json"), ("V10", "m3a_cases_v10.json"))
OIDS = {"V4": "M3A-3", "V7": "M3A-6", "V10": "M3A-9"}
LABEL = "synthetic workload, relative engineering budget"
UNITS = 10 ** 8


def owned_rows():
    out = []
    for fam, fn in FILES:
        for r in H.rows("author3", fn):
            assert H.owners_of("author3", fn, r["id"]) == ["S07"], r["id"]
            out.append(r)
    return out


ROWS = owned_rows()


# ---- fixture rows -----------------------------------------------------------------------------------------------

def _close(test, got, want, tol, where):
    test.assertIsNotNone(got, where)
    test.assertLessEqual(abs(Fraction(got) - Fraction(want)), Fraction(tol), (where, got, want))


def check_row(test, row, res, back):
    exp, rid, fam = row["expected"], row["id"], row["family"]
    test.assertEqual(res.output_id, OIDS[fam], rid)
    test.assertEqual((res.status, res.reason, res.code), (exp["status"], exp["reason"], exp["code"]), rid)
    if exp["status"] != "available":
        test.assertIsNone(res.value, rid)
        test.assertIsNone(res.fired, rid)
        test.assertEqual(res.labels, [], rid)                     # R-105
        if exp["status"] == "invalid_input":
            test.assertIsNone(res.coverage, rid)
        elif exp["coverage"] is not None:
            test.assertEqual(res.coverage["contract_reasons"], exp["coverage"]["contract_reasons"], rid)
        C.canonical_line(res)
        return
    want, got, tol = exp["value"], res.value, exp["tol"]
    for key in exp["assert"]:
        where = (rid, key)
        if key == "now":
            _close(test, got["now"], want["now"], tol["iv"] if fam == "V4" else tol["diff_annual"], where)
        elif key == "prior":
            test.assertEqual(Fraction(got["prior"]), Fraction(want["prior"]), where)
        elif key in ("change_points", "gap_change_points"):
            _close(test, got[key], want[key], tol["points"], where)
        elif key == "change_ratio":
            _close(test, got[key], want[key], tol["change_ratio"], where)
        elif key == "priors.session_id":
            test.assertEqual([back.get(p["session_id"], p["session_id"]) for p in got["priors"]],
                             [p["session_id"] for p in want["priors"]], where)
        else:
            test.assertEqual(got[key], want[key], where)
    for p, w in zip(got.get("priors", []), want.get("priors", [])):         # stored gaps are exact (8 decimals)
        test.assertEqual(Fraction(p["gap"]), Fraction(w["gap"]), (rid, "gap"))
    if exp["fire_assert"]:
        test.assertEqual(res.fired, exp["fired"], (rid, "fired"))
    else:
        test.assertIn(res.fired, (True, False), rid)
    if exp["labels_assert"]:
        test.assertEqual(res.labels, exp["labels"], (rid, "labels"))
    if exp["coverage"] is not None:
        test.assertEqual(res.coverage["contract_reasons"], exp["coverage"]["contract_reasons"], (rid, "coverage"))
    json.dumps(res.value)                                                    # wire-ready: plain JSON values only
    C.canonical_line(res)


class Rows(unittest.TestCase):
    def test_owned_row_count(self):
        self.assertEqual(len(ROWS), 188)
        self.assertEqual({f: sum(1 for r in ROWS if r["family"] == f) for f, _ in FILES},
                         {"V4": 80, "V7": 44, "V10": 64})
        ids = {r["id"] for r in ROWS}
        self.assertTrue({"V4-S-%02d" % i for i in range(1, 10)} <= ids)
        self.assertIn("V4-Cx1", ids)


def _make(row):
    def test(self):
        res, back = A.run_row(row)
        check_row(self, row, res, back)
    return test


for _r in ROWS:
    setattr(Rows, "test_" + _r["id"].replace("-", "_"), _make(_r))


class G5Priors(unittest.TestCase):
    """author3 m3a_g5_priors.json: the prior-reading classes (validity, none, zero prior, sign pairs, ratio pairs),
    through the public functions (hand-built frames, defined below)."""
    G5 = json.loads((H.set_dir("author3") / "m3a_g5_priors.json").read_text(encoding="utf-8"))

    def test_g5_manifest_clean(self):
        self.assertEqual(H.manifest_mismatches("author3"), [])

    def test_g5_reading_validity_none_and_zero(self):
        cutoff = self.G5["cutoff_ns"]
        fr, fl = mk_frame([{"d": 10, "atm": 0.2, "label": "exact-model"}], cutoff=cutoff)
        seen = 0
        for r in self.G5["rows"]:
            if "reading" not in r:
                continue
            seen += 1
            res = SC.iv_change(fr, fl, cutoff, {"prior": r["reading"]})
            if r["code"] is not None:
                self.assertEqual((res.status, res.code), ("invalid_input", r["code"]), r["id"])
            elif r["reading"] is None:
                self.assertEqual((res.status, res.reason), ("unavailable", "no_prior_reading"), r["id"])
            elif Fraction(r["reading"]["value"]) == 0:
                self.assertEqual((res.status, res.reason), ("unavailable", "zero_denominator"), r["id"])
            else:
                self.assertEqual(res.status, "available", r["id"])
        self.assertEqual(seen, 8)

    def test_g5_sign_pairs(self):
        seen = 0
        for r in self.G5["rows"]:
            if "now_skew" not in r:
                continue
            seen += 1
            now = Fraction(r["now_skew"])
            fr, fl = mk_frame([{"d": 30, "atm": 0.2, "put": 0.2 + float(now), "call": 0.2, "label": "exact-model"}],
                              {30: 0.2})
            res = SC.skew_change(fr, fl, 1000, {"condition": "sign_change",
                                                "prior": {"kind": "frame", "value": r["prior_skew"], "time_ns": 5}},
                                 None, "XYZ/stock/skew25", None)
            self.assertEqual((res.value["sign_changed"], res.fired), (r["sign_changed"],) * 2, r["id"])
        self.assertEqual(seen, 8)

    def test_g5_ratio_pairs(self):
        seen = 0
        fr, fl = mk_frame([{"d": 10, "atm": 0.22, "label": "exact-model"}])
        for r in self.G5["rows"]:
            if "pct" not in r:
                continue
            seen += 1
            res = SC.iv_change(fr, fl, 1000, {"prior": {"kind": "frame", "value": r["prior"], "time_ns": 5}})
            pct = Fraction(res.value["change_ratio"]) * 100
            self.assertLessEqual(abs(pct - Fraction(r["pct"])), Fraction(1, 10 ** 5), r["id"])
            self.assertEqual(res.fired, pct >= 10, r["id"])                  # inclusive, on the rounded decimal
        self.assertEqual(seen, 4)


# ---- hand-built frames (no chain): exact arithmetic, precedence, hostile input ---------------------------------

def mk_frame(expiries, tenors=None, eligible=1, delta_convention=None, cutoff=1000, lane="stock"):
    """(frame Result, floats) in the S05 shape. expiries: list of dicts {d, atm, put, call, label, reason, put_reason,
    call_reason}; reason set = the expiry is unavailable with it. tenors: {tenor: float | reason string}."""
    fe, fl = {}, {}
    for e in expiries:
        d = str(e["d"])
        ok = e.get("reason") is None
        atm, put, call = e.get("atm"), e.get("put"), e.get("call")
        sides = {}
        for k, v, rs in (("put25_iv", put, e.get("put_reason")), ("call25_iv", call, e.get("call_reason"))):
            if not ok:
                sides[k] = {"status": "unavailable", "reason": e["reason"], "value": None}
            elif v is None:
                sides[k] = {"status": "unavailable", "reason": rs or "no_delta_bracket", "value": None}
            else:
                sides[k] = {"status": "available", "reason": None, "value": C.round_text(v)}
        fe[d] = {"status": "available" if ok else "unavailable", "reason": e.get("reason"), "forward": "100.00000000",
                 "atm_iv": C.round_text(atm) if ok and atm is not None else None, **sides}
        item = {"atm_iv": atm if ok else None, "put25_iv": put if ok else None, "call25_iv": call if ok else None}
        if "label" in e:
            item["label"] = e["label"]
        fl[d] = item
    ft, flt = {}, {}
    for t, v in (tenors or {}).items():
        if isinstance(v, str):
            ft[str(t)] = {"status": "unavailable", "reason": v, "iv": None, "method": None, "expiries_used": None}
            flt[str(t)] = None
        else:
            used = [x["d"] for x in expiries if x["d"] == t] or [x["d"] for x in expiries][:2] or [t]
            ft[str(t)] = {"status": "available", "reason": None, "iv": C.round_text(v), "method": "as_is",
                          "expiries_used": used}
            flt[str(t)] = v
    cov = {"listed_strikes": 10, "eligible_strikes": eligible, "per_expiry": {},
           "contract_reasons": {"stale_quote": 2}}
    params = {"delta_convention": delta_convention} if delta_convention else {}
    frame = C.Result.available("M3A-0", None, None, cutoff, None, params=params, coverage=cov, lane=lane,
                               labels=["exact-model"], frame={"expiries": fe, "tenors": ft})
    return frame, {"expiries": fl, "tenors": flt, "available": True}


def v4(frame, floats, params, cutoff=1000):
    return SC.iv_change(frame, floats, cutoff, params)


def store_with(values, series="XYZ/stock/term_30_91", conv=None, lane="stock"):
    """(store, as_of): scalar closes (10^-8 ints, oldest first) on consecutive sessions, then the current session."""
    n = len(values)
    ids = ["2026-01-%02d" % (i + 1) for i in range(n)] + ["2026-02-01"]
    st = HistoryStore(Calendar([(d, 390) for d in ids]), k=20)
    for d, v in zip(ids, values):
        st.append(series, series.rsplit("/", 1)[1], 0, d, [], total=v, lane=lane, delta_convention=conv)
    return st, "2026-02-01"


class V4Units(unittest.TestCase):
    def setUp(self):
        self.ex = [{"d": 10, "atm": 0.2, "label": "exact-model"}, {"d": 30, "atm": 0.28, "label": "exact-model"}]
        self.fr, self.fl = mk_frame(self.ex, {30: 0.28})
        self.base = {"prior": {"kind": "frame", "value": "0.2", "time_ns": 999}}

    def test_atm_form_nearest_eligible_default(self):
        r = v4(self.fr, self.fl, self.base)
        self.assertEqual((r.status, r.value["iv_form"], r.value["now"], r.value["prior_kind"]),
                         ("available", "atm", "0.20000000", "frame"))
        self.assertEqual((r.value["change_points"], r.value["change_ratio"], r.fired), ("0.00000000", "0.00000000", False))

    def test_30d_form(self):
        r = v4(self.fr, self.fl, {**self.base, "iv_form": "30d"})
        self.assertEqual((r.value["iv_form"], r.value["now"], r.value["change_points"], r.value["change_ratio"]),
                         ("30d", "0.28000000", "8.00000000", "0.40000000"))
        self.assertTrue(r.fired)                                   # +40 percent, default up, default 10

    def test_rounding_ties_half_even_and_exact_boundary(self):
        # now 0.5 exactly representable; prior 0.45454545 -> ratio (0.5-0.45454545)/0.45454545 = 0.10000000...
        fr, fl = mk_frame([{"d": 10, "atm": 0.22, "label": "exact-model"}])
        r = v4(fr, fl, {"prior": {"kind": "frame", "value": "0.2", "time_ns": 5}})
        self.assertEqual((r.value["change_ratio"], r.fired), ("0.10000000", True))      # inclusive at exactly 10 percent
        r = v4(fr, fl, {"prior": {"kind": "frame", "value": "0.2", "time_ns": 5}, "direction": "down", "at_most": "10"})
        self.assertFalse(r.fired)                                                       # down fires at <= -10

    def test_zero_prior_and_no_prior(self):
        self.assertEqual(v4(self.fr, self.fl, {"prior": {"kind": "frame", "value": "0", "time_ns": 5}}).reason,
                         "zero_denominator")
        self.assertEqual(v4(self.fr, self.fl, {}).reason, "no_prior_reading")
        self.assertEqual(v4(self.fr, self.fl, {"prior": None}).reason, "no_prior_reading")

    def test_upstream_before_prior_reasons(self):
        fr, fl = mk_frame([{"d": 10, "reason": "no_atm_strike"}])
        self.assertEqual(v4(fr, fl, {}).reason, "no_atm_strike")                 # no prior too: upstream first
        fr, fl = mk_frame([{"d": 10, "atm": 0.2, "label": "exact-model"}], {30: "no_bracketing_expiry"})
        self.assertEqual(v4(fr, fl, {"iv_form": "30d"}).reason, "no_bracketing_expiry")

    def test_atm_skips_low_coverage_only(self):
        ex = [{"d": 7, "reason": "low_surface_coverage"}, {"d": 14, "reason": "low_surface_coverage"},
              {"d": 30, "atm": 0.3, "label": "exact-model"}]
        fr, fl = mk_frame(ex)
        self.assertEqual(v4(fr, fl, {"prior": {"kind": "frame", "value": "0.3", "time_ns": 5}}).value["now"],
                         "0.30000000")
        ex[0] = {"d": 7, "reason": "no_atm_strike"}                              # no fallback past a no_atm_strike
        fr, fl = mk_frame(ex)
        self.assertEqual(v4(fr, fl, {}).reason, "no_atm_strike")
        fr, fl = mk_frame([{"d": 7, "reason": "low_surface_coverage"}])
        self.assertEqual(v4(fr, fl, {}).reason, "low_surface_coverage")

    def test_no_eligible_contract_wins(self):
        fr, fl = mk_frame([{"d": 30, "reason": "no_atm_strike"}], {30: "no_bracketing_expiry"}, eligible=0)
        self.assertEqual(v4(fr, fl, {"iv_form": "30d"}).reason, "no_eligible_contract")

    def test_labels_of_used_expiry_only(self):
        ex = [{"d": 10, "atm": 0.2, "label": "approximate: European model on an American-style contract"},
              {"d": 30, "atm": 0.28, "label": "exact-model"}]
        fr, fl = mk_frame(ex, {30: 0.28})
        self.assertEqual(v4(fr, fl, {}).labels, ["approximate: European model on an American-style contract"])
        self.assertEqual(v4(fr, fl, {"iv_form": "30d"}).labels, ["approximate: European model on an American-style contract", "exact-model"])
        self.assertEqual(v4(fr, fl, {"feed_delay_tag": "delayed", "mode": "close"}).labels,
                         ["approximate: European model on an American-style contract", "delayed"])

    def test_labels_fall_back_to_frame_labels_without_expiry_labels(self):
        fr, fl = mk_frame([{"d": 10, "atm": 0.2}])
        self.assertEqual(v4(fr, fl, {}).labels, ["exact-model"])

    def test_structural_codes_and_order(self):
        p = {"prior": {"kind": "frame", "value": "0.2", "time_ns": 1000}}
        self.assertEqual(v4(self.fr, self.fl, p).code, "prior_not_before_cutoff")
        self.assertEqual(v4(self.fr, self.fl, {**p, "iv_form": "60d"}).code, "iv_form_not_allowed")   # 13 before 17
        self.assertEqual(v4(self.fr, self.fl, {"feed_delay_tag": "delayed"}).code, "delayed_feed_tag")
        self.assertEqual(v4(self.fr, self.fl, {"direction": "sideways"}).code, "invalid_direction")
        self.assertEqual(v4(self.fr, self.fl, {"direction": None}).code, "malformed_type")
        self.assertEqual(v4(self.fr, self.fl, {"at_least": 1.5}).code, "malformed_type")
        self.assertEqual(v4(self.fr, self.fl, {"x": 1.5, "direction": "either"}).code, "malformed_type")
        self.assertEqual(v4(self.fr, self.fl, {"prior_sessions": 0}).code, "malformed_type")
        self.assertEqual(v4(self.fr, self.fl, {"prior": {"kind": "year", "value": "0.2", "time_ns": 5}}).code,
                         "malformed_type")
        self.assertEqual(v4(self.fr, self.fl, {"prior": {"kind": "frame", "value": True, "time_ns": 5}}).code,
                         "malformed_type")
        self.assertEqual(v4(self.fr, self.fl, {"prior": {"kind": "frame", "value": "abc", "time_ns": 5}}).code,
                         "malformed_type")

    def test_frame_invalid_code_wins_by_position(self):
        bad = C.Result.invalid("M3A-0", "bad_spot", evaluation_ns=1000)
        self.assertEqual(v4(bad, None, {"iv_form": "60d"}).code, "bad_spot")             # position 2 before 13
        bad = C.Result.invalid("M3A-0", "delta_not_allowed", evaluation_ns=1000)
        self.assertEqual(v4(bad, None, {"iv_form": "60d"}).code, "delta_not_allowed")    # same slot: the frame's
        bad = C.Result.invalid("M3A-0", "tenor_not_allowed", evaluation_ns=1000)
        self.assertEqual(v4(bad, None, {"iv_form": "60d"}).code, "tenor_not_allowed")    # 12 before 13
        bad = C.Result.invalid("M3A-0", "delta_not_allowed", evaluation_ns=1000)
        self.assertEqual(v4(bad, None, {"delayed_feed_tag": 1, "feed_delay_tag": "delayed"}).code, "delta_not_allowed")

    def test_result_fields_and_echo(self):
        r = v4(self.fr, self.fl, {**self.base, "direction": "either", "x": "5"})
        self.assertEqual(r.params["direction"], "either")
        self.assertEqual(r.params["x"], "5")
        self.assertEqual((r.params["iv_form"], r.params["mode"], r.params["feed_delay_tag"], r.params["lane"]),
                         ("atm", "intraday", "live", "stock"))
        self.assertEqual(v4(self.fr, self.fl, self.base).params["at_least"], "10")      # default threshold echoed
        self.assertEqual(r.coverage["contract_reasons"], {"stale_quote": 2})
        self.assertEqual(r.evaluation_ns, 1000)

    def test_reading_value_forms(self):
        for val, want in (("0.2", "0.20000000"), (Fraction(1, 5), "0.20000000"), (0, None), (0.25, "0.25000000")):
            r = v4(self.fr, self.fl, {"prior": {"kind": "session", "value": val, "time_ns": 5}})
            if want is None:
                self.assertEqual(r.reason, "zero_denominator")
            else:
                self.assertEqual((r.value["prior"], r.value["prior_kind"]), (want, "session"))
        r = v4(self.fr, self.fl, {"prior": {"kind": "frame", "value": "0.200000004", "time_ns": 5}})
        self.assertEqual(r.value["prior"], "0.20000000")                       # half-even to 8 decimals
        r = v4(self.fr, self.fl, {"prior": {"kind": "frame", "value": "0.200000005", "time_ns": 5}})
        self.assertEqual(r.value["prior"], "0.20000000")                       # tie to even
        r = v4(self.fr, self.fl, {"prior": {"kind": "frame", "value": "0.200000015", "time_ns": 5}})
        self.assertEqual(r.value["prior"], "0.20000002")


class V7Units(unittest.TestCase):
    def setUp(self):
        ex = [{"d": 30, "atm": 0.22, "label": "exact-model"}, {"d": 91, "atm": 0.24, "label": "exact-model"}]
        self.fr, self.fl = mk_frame(ex, {30: 0.22, 91: 0.24})

    def run7(self, vals, params=None, **kw):
        st, asof = store_with(vals) if vals is not None else (None, "2026-02-01")
        return SC.gap_change(self.fr, self.fl, 1000, params or {}, st, "XYZ/stock/term_30_91", asof, **kw)

    def test_n_th_prior_and_priors_list(self):
        r = self.run7([10 ** 6 * 5, -10 ** 6, 3 * 10 ** 6, 2 * 10 ** 6], {"prior_sessions": 3})
        self.assertEqual([p["gap"] for p in r.value["priors"]], ["0.02000000", "0.03000000", "-0.01000000"])  # recent first
        self.assertEqual(r.value["now"], "0.02000000")
        self.assertEqual(r.value["gap_change_points"], "3.00000000")       # now 0.02 vs the 3rd prior (-0.01)
        self.assertNotIn("slope_change_points", r.value)
        self.assertEqual(set(r.value), {"now", "priors", "gap_change_points"})

    def test_empty_vs_short_store(self):
        self.assertEqual(self.run7(None).reason, "no_prior_reading")           # no store at all
        self.assertEqual(self.run7([]).reason, "no_prior_reading")
        self.assertEqual(self.run7([1, 2], {"prior_sessions": 3}).reason, "insufficient_history")
        self.assertEqual(self.run7([1], {"prior_sessions": 2}).reason, "insufficient_history")

    def test_scalar_zero_is_a_value(self):
        r = self.run7([0])
        self.assertEqual((r.status, r.value["priors"][0]["gap"], r.value["gap_change_points"]),
                         ("available", "0.00000000", "2.00000000"))
        self.assertTrue(r.fired)                                               # exactly 2 points, either, default 2

    def test_directions_and_thresholds(self):
        base = [-10 ** 6]                                                      # change +3 points
        self.assertTrue(self.run7(base, {"direction": "up", "at_least": "3"}).fired)
        self.assertFalse(self.run7(base, {"direction": "up", "at_least": "3.00000001"}).fired)
        self.assertFalse(self.run7(base, {"direction": "down", "at_most": "3"}).fired)
        self.assertTrue(self.run7([5 * 10 ** 6], {"direction": "down", "at_most": "3"}).fired)    # -3 <= -3
        self.assertTrue(self.run7([5 * 10 ** 6], {"direction": "either", "x": 3}).fired)
        self.assertFalse(self.run7(base, {"direction": "either", "x": "3.5"}).fired)

    def test_upstream_order(self):
        fr, fl = mk_frame([{"d": 30, "atm": 0.22}], {30: 0.22, 91: "no_bracketing_expiry"})
        r = SC.gap_change(fr, fl, 1000, {}, None, "XYZ/stock/term_30_91", "2026-02-01")
        self.assertEqual(r.reason, "no_bracketing_expiry")                     # before no_prior_reading
        fr, fl = mk_frame([{"d": 30, "atm": 0.22}], {30: "low_surface_coverage", 91: "no_bracketing_expiry"})
        self.assertEqual(SC.gap_change(fr, fl, 1000, {}, None, "x/stock/term_30_91", "2026-02-01").reason,
                         "low_surface_coverage")                              # tenors ascending: 30 first
        fr, fl = mk_frame([{"d": 30, "atm": 0.22}], {30: 0.22, 91: 0.24}, eligible=0)
        self.assertEqual(SC.gap_change(fr, fl, 1000, {}, None, "x/stock/term_30_91", "2026-02-01").reason,
                         "no_eligible_contract")

    def test_read_codes(self):
        st, _ = store_with([1])
        r = SC.gap_change(self.fr, self.fl, 1000, {}, st, "XYZ/stock/term_30_91", "2099-01-01")
        self.assertEqual((r.status, r.code), ("invalid_input", "session_not_in_calendar"))
        r = SC.gap_change(self.fr, self.fl, 1000, {}, st, "XYZ/stock/term_30_91", None)
        self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"))
        r = SC.gap_change(self.fr, self.fl, 1000, {}, st, None, "2026-02-01")
        self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"))

    def test_lane_mismatch_read_is_no_history(self):
        st, asof = store_with([10 ** 6], lane="etf_index")
        r = SC.gap_change(self.fr, self.fl, 1000, {}, st, "XYZ/stock/term_30_91", asof)
        self.assertEqual(r.reason, "no_prior_reading")                         # R-112 read n 0: an empty store

    def test_tenor_missing_from_frame_is_malformed(self):
        fr, fl = mk_frame([{"d": 30, "atm": 0.22}], {30: 0.22})
        r = SC.gap_change(fr, fl, 1000, {}, None, "x/stock/term_30_91", "2026-02-01")
        self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"))

    def test_convention_is_ignored(self):
        for bad in ("forward", 5, None, "Spot"):
            r = self.run7([-10 ** 6], {"delta_convention": bad})
            self.assertEqual((r.status, r.value["gap_change_points"]), ("available", "3.00000000"), bad)
            self.assertNotIn("delta_convention", r.params)


class V10Units(unittest.TestCase):
    def setUp(self):
        self.ex = [{"d": 20, "atm": 0.18, "put": 0.22, "call": 0.15, "label": "exact-model"},
                   {"d": 45, "atm": 0.25, "put": 0.29, "call": 0.22, "label": "approximate: European model on an American-style contract"}]
        self.fr, self.fl = mk_frame(self.ex, {30: 0.22})
        self.prior = {"kind": "frame", "value": "0.04", "time_ns": 5}

    def run10(self, params=None, frame=None, floats=None, vals=None, series="XYZ/stock/skew25", conv=None):
        st = asof = None
        if vals is not None:
            st, asof = store_with(vals, series, conv)
        return SC.skew_change(frame or self.fr, floats or self.fl, 1000, params or {}, st, series, asof)

    def test_per_side_interpolation_then_one_rounding(self):
        r = self.run10({"prior": self.prior})
        w = lambda iv, d: iv * iv * d
        def cm(a20, a45):
            return math.sqrt((w(a20, 20) + (w(a45, 45) - w(a20, 20)) * (30 - 20) / 25) / 30)
        want = Fraction(cm(0.22, 0.29)) - Fraction(cm(0.15, 0.22))
        n, d = want.numerator * UNITS, want.denominator
        q, rem = divmod(n, d)
        q += (2 * rem > d) or (2 * rem == d and q & 1)
        self.assertEqual(r.value["now"], C.units_text(q))
        self.assertEqual(r.value["delta_convention"], "spot")
        self.assertEqual(r.labels, ["approximate: European model on an American-style contract", "exact-model"])

    def test_exact_expiry_as_is(self):
        fr, fl = mk_frame([{"d": 30, "atm": 0.2, "put": 0.23, "call": 0.17, "label": "exact-model"}], {30: 0.2})
        r = self.run10({"prior": self.prior}, fr, fl)
        self.assertEqual((r.value["now"], r.value["change_points"]), ("0.06000000", "2.00000000"))
        self.assertTrue(r.fired)                                               # default either, 2 points, inclusive

    def test_side_failures_put_then_call_and_bracket_reasons(self):
        ex = [{"d": 30, "atm": 0.2, "put": None, "call": None, "label": "exact-model"}]
        fr, fl = mk_frame(ex, {30: 0.2})
        self.assertEqual(self.run10({}, fr, fl).reason, "no_delta_bracket")
        ex = [{"d": 30, "atm": 0.2, "put": 0.2, "call": None, "call_reason": "no_delta_bracket", "label": "exact-model"}]
        fr, fl = mk_frame(ex, {30: 0.2})
        self.assertEqual(self.run10({}, fr, fl).reason, "no_delta_bracket")
        ex = [{"d": 30, "reason": "low_surface_coverage"}]
        fr, fl = mk_frame(ex, {30: "low_surface_coverage"})
        self.assertEqual(self.run10({}, fr, fl).reason, "low_surface_coverage")        # R-178: exact expiry
        ex = [{"d": 20, "reason": "low_surface_coverage"}, {"d": 45, "atm": 0.2, "put": 0.2, "call": 0.1, "label": "exact-model"}]
        fr, fl = mk_frame(ex, {30: "no_bracketing_expiry"})
        self.assertEqual(self.run10({}, fr, fl).reason, "no_bracketing_expiry")        # R-139
        ex = [{"d": 20, "atm": 0.2, "put": None, "call": 0.1, "label": "exact-model"},
              {"d": 45, "atm": 0.2, "put": 0.2, "call": 0.1, "label": "exact-model"}]
        fr, fl = mk_frame(ex, {30: 0.2})
        self.assertEqual(self.run10({}, fr, fl).reason, "no_delta_bracket")            # bracketing side missing
        ex = [{"d": 45, "atm": 0.2, "put": 0.2, "call": 0.1, "label": "exact-model"}]
        fr, fl = mk_frame(ex, {30: 0.2})
        self.assertEqual(self.run10({}, fr, fl).reason, "no_bracketing_expiry")

    def test_sign_rules(self):
        fr, fl = mk_frame([{"d": 30, "atm": 0.2, "put": 0.23, "call": 0.20, "label": "exact-model"}], {30: 0.2})
        for prior, changed, sp in (("-0.02", True, -1), ("0.02", False, 1), ("0", False, 0), ("0.000000004", False, 0)):
            r = self.run10({"condition": "sign_change", "prior": {"kind": "frame", "value": prior, "time_ns": 5}}, fr, fl)
            self.assertEqual((r.value["sign_now"], r.value["sign_prior"], r.value["sign_changed"], r.fired),
                             (1, sp, changed, changed), prior)
        fr, fl = mk_frame([{"d": 30, "atm": 0.2, "put": 0.20, "call": 0.20, "label": "exact-model"}], {30: 0.2})
        r = self.run10({"condition": "sign_change", "prior": {"kind": "frame", "value": "-0.02", "time_ns": 5}}, fr, fl)
        self.assertEqual((r.value["sign_now"], r.value["sign_changed"], r.fired), (0, False, False))   # 0 never flips
        r = self.run10({"condition": "change", "prior": {"kind": "frame", "value": "-0.02", "time_ns": 5}}, fr, fl)
        self.assertEqual((r.value["change_points"], r.fired), ("2.00000000", True))

    def test_session_kind_reads_store_and_ignores_decoy(self):
        r = self.run10({"prior_kind": "session", "prior_sessions": 2, "prior": self.prior}, vals=[10 ** 6, 5 * 10 ** 6, 2 * 10 ** 6])
        self.assertEqual([p["gap"] for p in r.value["priors"]], ["0.02000000", "0.05000000"])
        self.assertEqual(r.status, "available")
        self.assertEqual(r.params["prior_kind"], "session")
        r = self.run10({"prior_kind": "session", "prior": self.prior}, vals=[])
        self.assertEqual(r.reason, "no_prior_reading")
        r = self.run10({"prior_kind": "session", "prior_sessions": 3}, vals=[1, 2])
        self.assertEqual(r.reason, "insufficient_history")
        r = self.run10({"prior_kind": "frame"}, vals=[1, 2, 3])
        self.assertEqual(r.reason, "no_prior_reading")                         # decoy store ignored
        self.assertEqual(self.run10({"prior_kind": "session"}).reason, "no_prior_reading")   # no store

    def test_convention_codes(self):
        fwd = {"delta_convention": "forward"}
        self.assertEqual(self.run10({**fwd, "prior": self.prior}).code, "convention_mismatch")      # prior has none = spot
        self.assertEqual(self.run10({"delta_convention": "Spot"}).code, "convention_not_allowed")
        self.assertEqual(self.run10({"delta_convention": 2}).code, "malformed_type")
        r = self.run10({**fwd, "prior_kind": "session", "prior": {**self.prior, "delta_convention": "forward"}},
                       vals=[10 ** 6], series="XYZ/stock/skew25_fwd", conv="forward")
        self.assertEqual((r.status, r.value["delta_convention"]), ("available", "forward"))
        r = self.run10({"prior_kind": "session"}, vals=[10 ** 6], conv="forward")                  # stored forward, spot asked
        self.assertEqual(r.code, "convention_mismatch")
        r = self.run10({**fwd, "prior_kind": "session"}, vals=[10 ** 6], series="XYZ/stock/skew25")  # spot series, forward asked
        self.assertEqual(r.code, "convention_mismatch")
        fr, fl = mk_frame(self.ex, {30: 0.22}, delta_convention="forward")
        self.assertEqual(self.run10({"prior": self.prior}, fr, fl).code, "convention_mismatch")   # frame of the other convention

    def test_unavailable_frame_with_failed_side_still_reads_other_items(self):
        # the frame itself may be unavailable (another expiry's 25-delta side); V10 reads only what it needs
        ex = [{"d": 30, "atm": 0.2, "put": 0.23, "call": 0.2, "label": "exact-model"},
              {"d": 60, "atm": 0.2, "put": None, "call": 0.2, "label": "exact-model"}]
        fr, fl = mk_frame(ex, {30: 0.2})
        r = self.run10({"prior": self.prior}, fr, fl)
        self.assertEqual((r.status, r.value["now"]), ("available", "0.03000000"))


class Guards(unittest.TestCase):
    """Never raises on caller data; no hidden state; inputs untouched."""

    def setUp(self):
        self.fr, self.fl = mk_frame([{"d": 10, "atm": 0.2, "put": 0.22, "call": 0.18, "label": "exact-model"},
                                     {"d": 30, "atm": 0.21, "put": 0.23, "call": 0.19, "label": "exact-model"}],
                                    {30: 0.21, 91: 0.24})

    def test_hostile_inputs_never_raise(self):
        class Boom:
            def __getattr__(self, name):
                raise RuntimeError(name)
            __getitem__ = get = __iter__ = __eq__ = __hash__ = None
        junk = (None, 0, "x", [], {}, (), Boom(), 1.5, object())
        for fn in (SC.iv_change, SC.gap_change, SC.skew_change):
            for frame in junk + (self.fr,):
                for floats in junk + (self.fl,):
                    for params in junk + ({"prior": Boom()}, {"prior": {"kind": "frame", "value": Boom(), "time_ns": 1}},
                                          {"priors": Boom()}, {"iv_form": Boom()}):
                        for cutoff in (1000, None, "x"):
                            r = fn(frame, floats, cutoff, params)
                            self.assertIn(r.status, C.STATUSES)
                            if r.status == "invalid_input":
                                self.assertIn(r.code, C.CODES)

    def test_hostile_store_and_series(self):
        for store in (None, 0, "x", object(), {}):
            for series in (None, 1, "x", "a/b/c", ""):
                for fn in (SC.gap_change, SC.skew_change):
                    r = fn(self.fr, self.fl, 1000, {}, store, series, "2026-02-01")
                    self.assertIn(r.status, C.STATUSES)

    def test_non_finite_and_missing_floats_are_malformed_not_raised(self):
        for bad in (float("nan"), float("inf"), None, "0.2", True):
            fr, fl = mk_frame([{"d": 10, "atm": 0.2, "label": "exact-model"}])
            fl["expiries"]["10"]["atm_iv"] = bad
            r = v4(fr, fl, {"prior": {"kind": "frame", "value": "0.2", "time_ns": 5}})
            self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"), bad)
        fr, fl = mk_frame([{"d": 10, "atm": 0.2}])
        self.assertEqual(v4(fr, {}, {}).code, "malformed_type")

    def test_no_hidden_state_and_inputs_not_mutated(self):
        st, asof = store_with([10 ** 6, 2 * 10 ** 6])
        p = {"prior_sessions": 2, "x": "3", "direction": "either", "priors": [{"time_ns": 5, "session_id": "a"}]}
        snap = (json.dumps(p, sort_keys=True), json.dumps(self.fl, sort_keys=True), C.canonical_line(self.fr),
                st.content_hash() if hasattr(st, "content_hash") else None)
        first = SC.gap_change(self.fr, self.fl, 1000, p, st, "XYZ/stock/term_30_91", asof)
        again = SC.gap_change(self.fr, self.fl, 1000, p, st, "XYZ/stock/term_30_91", asof)
        self.assertEqual(C.canonical_line(first), C.canonical_line(again))
        self.assertEqual(snap, (json.dumps(p, sort_keys=True), json.dumps(self.fl, sort_keys=True),
                                C.canonical_line(self.fr), st.content_hash() if hasattr(st, "content_hash") else None))
        # a second, different request in between changes nothing about the first
        SC.gap_change(self.fr, self.fl, 1000, {"prior_sessions": 1}, st, "XYZ/stock/term_30_91", asof)
        self.assertEqual(C.canonical_line(first), C.canonical_line(SC.gap_change(
            self.fr, self.fl, 1000, p, st, "XYZ/stock/term_30_91", asof)))

    def test_fired_is_a_bool_and_values_are_plain_text(self):
        r = v4(self.fr, self.fl, {"prior": {"kind": "frame", "value": "0.2", "time_ns": 5}})
        self.assertIs(type(r.fired), bool)
        for k in ("now", "prior", "change_points", "change_ratio"):
            self.assertIs(type(r.value[k]), str)


# ---- Developer differential: random cases against a pure-Python reference (exact Fraction rounding) ----------------

def _hr(fr):
    """Half-even rounding of a Fraction to an int (reference)."""
    q, rem = divmod(fr.numerator, fr.denominator)
    two = 2 * rem
    if two > fr.denominator or (two == fr.denominator and q & 1):
        q += 1
    return q


def ref_units(x):
    return _hr(Fraction(x) * UNITS)


def ref_text(u):
    return ("-" if u < 0 else "") + "%d.%08d" % divmod(abs(u), UNITS)


def ref_fire(direction, x, thr):
    if direction == "up":
        return x >= thr
    if direction == "down":
        return x <= -thr
    return abs(x) >= thr


def _rand_float(rng):
    k = rng.randrange(6)
    if k == 0:
        return rng.uniform(0.01, 1.2)
    if k == 1:
        return rng.randrange(1, 10 ** 8) / 1e8
    if k == 2:
        return rng.randrange(1, 2 ** 22) / 2.0 ** 22          # dyadic: many exact decimal-tie neighbours
    if k == 3:
        return (rng.randrange(1, 10 ** 7) + 0.5) / 1e8 * rng.choice((1, 2, 4))
    if k == 4:
        return rng.randrange(1, 2 ** 20) / 2.0 ** 20 + 2.0 ** -40
    return rng.uniform(1e-9, 1e-6)


def _rand_thr(rng, default):
    """(request value or None, exact Fraction)"""
    k = rng.randrange(5)
    if k == 0:
        return None, Fraction(default)
    if k == 1:
        v = rng.randrange(0, 12)
        return v, Fraction(v)
    if k == 2:
        t = "%d.%d" % (rng.randrange(0, 9), rng.randrange(0, 100))
        return t, Fraction(t)
    if k == 3:
        f = Fraction(rng.randrange(0, 60), rng.choice((2, 4, 8)))
        return f, f
    t = str(rng.randrange(0, 6))
    return t, Fraction(t)


_NAME = {"up": "at_least", "down": "at_most", "either": "x"}


def _rand_prior_value(rng, now_u):
    """(request value, exact prior units): near the now value, zero, negative, long decimals."""
    k = rng.randrange(6)
    if k == 0:
        u = 0
    elif k == 1:
        u = now_u + rng.randrange(-30, 31)
    elif k == 2:
        u = rng.randrange(-5 * 10 ** 7, 5 * 10 ** 7)
    elif k == 3:
        u = now_u * rng.choice((1, 2, 3)) // rng.choice((1, 2, 3, 4, 5))
    elif k == 4:
        u = round(now_u / 1.1)                                  # about +10 percent: boundary neighbourhood
    else:
        u = round(now_u * 1.1)
    form = rng.randrange(4)
    if form == 0:
        return ref_text(u), u
    if form == 1:
        return Fraction(u, UNITS), u
    if form == 2:                                               # 9 decimals: exact half-even rounding of the text
        extra = rng.randrange(10)
        t = ref_text(u)
        t = t + str(extra) if u >= 0 else t + str(extra)
        fr = Fraction(t)
        return t, _hr(fr * UNITS)
    return ref_text(u).rstrip("0").rstrip(".") if "." in ref_text(u) else ref_text(u), u


def _same(test, got, want, tag):
    test.assertEqual(
        (got.status, got.reason, got.code, got.value, got.fired, got.labels, got.params), want, tag)


def _expect_invalid(code):
    return ("invalid_input", None, code, None, None, [], None)


def _expect_unavailable(reason, params):
    return ("unavailable", reason, None, None, None, [], params)


class Differential(unittest.TestCase):
    """>= 20,000 random cases in total; every difference fails. Seeded (reproducible)."""
    N_V4, N_V7, N_V10 = 8000, 6000, 6000

    def test_v4_random_cases(self):
        rng = random.Random(20261031)
        reasons = ("no_atm_strike", "low_surface_coverage", "style_unknown", "no_bracketing_expiry", "price_out_of_bounds")
        for case in range(self.N_V4):
            form = rng.choice(("atm", "30d", None))
            n_exp = rng.randrange(1, 5)
            days = sorted(rng.sample(range(2, 120), n_exp))
            ex, fexp = [], []
            for d in days:
                if rng.random() < 0.3:
                    ex.append({"d": d, "reason": rng.choice(reasons[:3])})
                else:
                    ex.append({"d": d, "atm": _rand_float(rng), "label": rng.choice(("exact-model", "approximate: European model on an American-style contract"))})
            tens = {30: (rng.choice(reasons) if rng.random() < 0.25 else _rand_float(rng))}
            eligible = 0 if rng.random() < 0.05 else 3
            fr, fl = mk_frame(ex, tens, eligible)
            # expected now
            if (form or "atm") == "atm":
                now, why, lab = None, None, None
                low = None
                for e in ex:
                    if e.get("reason") is None:
                        now, lab = e["atm"], [e["label"]]
                        break
                    if e["reason"] == "low_surface_coverage":
                        low = low or "low_surface_coverage"
                        continue
                    why = e["reason"]
                    break
                if now is None and why is None:
                    why = low
            else:
                t = tens[30]
                if isinstance(t, str):
                    now, why, lab = None, t, None
                else:
                    now, why = t, None
                    lab = fr.frame["tenors"]["30"]["expiries_used"]
                    lab = [next(e for e in ex if e["d"] == d).get("label", "exact-model") if next(e for e in ex if e["d"] == d).get("reason") is None else None for d in lab]
                    if None in lab:
                        lab = None                                       # tenor pointing at an unavailable fake expiry
                        now = None
                        continue
            direction = rng.choice((None, "up", "down", "either"))
            dname = direction or "up"
            rv, thr = _rand_thr(rng, 10)
            mode = rng.choice(("intraday", "close"))
            delayed = rng.random() < 0.15
            params = {"mode": mode}
            if form:
                params["iv_form"] = form
            if direction:
                params["direction"] = direction
            if rv is not None:
                params[_NAME[dname]] = rv
            if delayed:
                params["feed_delay_tag"] = "delayed"
            have_prior = rng.random() > 0.15
            pv = pu = None
            if have_prior:
                now_u = ref_units(now) if now is not None else 20_000_000
                pv, pu = _rand_prior_value(rng, now_u)
                params["prior"] = {"kind": rng.choice(("frame", "session")), "value": pv, "time_ns": rng.choice((5, 999, 999))}
                if rng.random() < 0.07:
                    params["prior"]["time_ns"] = rng.choice((1000, 1001))
            iv_bad = rng.random() < 0.05
            if iv_bad:
                params["iv_form"] = rng.choice(("ATM", "60d", 30, None, ["atm"]))
            res = v4(fr, fl, params)
            echo = {"direction": dname, "feed_delay_tag": "delayed" if delayed else "live", "iv_form": form or "atm",
                    "lane": "stock", "mode": mode, _NAME[dname]: rv if rv is not None else "10"}
            if isinstance(echo[_NAME[dname]], Fraction):
                echo[_NAME[dname]] = str(echo[_NAME[dname]])
            echo = {k: echo[k] for k in sorted(echo)}
            if iv_bad:
                code = "iv_form_not_allowed" if isinstance(params["iv_form"], str) else "malformed_type"
                want = _expect_invalid(code)
            elif have_prior and params["prior"]["time_ns"] >= 1000:
                want = _expect_invalid("prior_not_before_cutoff")
            elif delayed and mode == "intraday":
                want = _expect_invalid("delayed_feed_tag")
            elif eligible == 0:
                want = _expect_unavailable("no_eligible_contract", echo)
            elif now is None and why is not None:
                want = _expect_unavailable(why, echo)
            elif not have_prior:
                want = _expect_unavailable("no_prior_reading", echo)
            elif pu == 0:
                want = _expect_unavailable("zero_denominator", echo)
            else:
                now_u = ref_units(now)
                change = now_u - pu
                ratio = _hr(Fraction(change * UNITS, pu))
                fired = ref_fire(dname, Fraction(ratio, 10 ** 6), thr)
                value = {"iv_form": form or "atm", "now": ref_text(now_u), "prior": ref_text(pu),
                         "change_points": ref_text(change * 100), "change_ratio": ref_text(ratio),
                         "prior_kind": params["prior"]["kind"]}
                labels = sorted(set(lab) | ({"delayed"} if delayed else set()))
                want = ("available", None, None, value, fired, labels, echo)
            _same(self, res, want, (case, params))

    def test_v7_random_cases(self):
        rng = random.Random(20261032)
        for case in range(self.N_V7):
            t30, t91 = _rand_float(rng), _rand_float(rng)
            reasons = ("no_bracketing_expiry", "low_surface_coverage", "no_atm_strike")
            ten = {30: t30 if rng.random() > 0.15 else rng.choice(reasons),
                   91: t91 if rng.random() > 0.15 else rng.choice(reasons)}
            ex = [{"d": 30, "atm": t30, "label": "exact-model"}, {"d": 91, "atm": t91, "label": "approximate: European model on an American-style contract"}]
            eligible = 0 if rng.random() < 0.04 else 2
            fr, fl = mk_frame(ex, ten, eligible)
            n = rng.choice((1, 1, 2, 3, 5))
            have = rng.choice((0, 1, 2, 3, 4, 6, 8)) if rng.random() > 0.2 else n
            stored = [rng.choice((0, rng.randrange(-10 ** 7, 10 ** 7), rng.randrange(-3 * 10 ** 7, 3 * 10 ** 7))) for _ in range(have)]
            direction = rng.choice((None, "up", "down", "either"))
            dname = direction or "either"
            rv, thr = _rand_thr(rng, 2)
            params = {"prior_sessions": n}
            if direction:
                params["direction"] = direction
            if rv is not None:
                params[_NAME[dname]] = rv
            delayed = rng.random() < 0.2
            if delayed:
                params["feed_delay_tag"] = "delayed"
                params["mode"] = "close"
            bad_time = rng.random() < 0.05
            if bad_time:
                params["priors"] = [{"time_ns": rng.choice((1000, 5, 2000)), "session_id": "s"}, {"time_ns": 1000}]
            st = None if rng.random() < 0.05 else store_with(stored)[0]
            res = SC.gap_change(fr, fl, 1000, params, st, "XYZ/stock/term_30_91", "2026-02-01")
            echo = {"direction": dname, "feed_delay_tag": "delayed" if delayed else "live", "lane": "stock",
                    "mode": "close" if delayed else "intraday", "prior_sessions": n,
                    _NAME[dname]: (str(rv) if isinstance(rv, Fraction) else rv) if rv is not None else "2"}
            echo = {k: echo[k] for k in sorted(echo)}
            if bad_time and any(p["time_ns"] >= 1000 for p in params["priors"]):
                want = _expect_invalid("prior_not_before_cutoff")
            elif eligible == 0:
                want = _expect_unavailable("no_eligible_contract", echo)
            elif isinstance(ten[30], str):
                want = _expect_unavailable(ten[30], echo)
            elif isinstance(ten[91], str):
                want = _expect_unavailable(ten[91], echo)
            else:
                avail = stored if st is not None else []
                if not avail:
                    want = _expect_unavailable("no_prior_reading", echo)
                elif len(avail) < n:
                    want = _expect_unavailable("insufficient_history", echo)
                else:
                    last = avail[-n:]
                    now_u = _hr((Fraction(t91) - Fraction(t30)) * UNITS)
                    change = (now_u - last[0]) * 100
                    pri = [{"session_id": "2026-01-%02d" % (len(avail) - i), "gap": ref_text(last[len(last) - 1 - i])} for i in range(n)]
                    value = {"now": ref_text(now_u), "priors": pri, "gap_change_points": ref_text(change)}
                    labels = sorted({"exact-model", "approximate: European model on an American-style contract"} | ({"delayed"} if delayed else set()))
                    want = ("available", None, None, value, ref_fire(dname, Fraction(change, UNITS), thr), labels, echo)
            _same(self, res, want, (case, params, stored))

    def test_v10_random_cases(self):
        rng = random.Random(20261033)
        reasons = ("no_atm_strike", "low_surface_coverage", "style_unknown")
        for case in range(self.N_V10):
            n_exp = rng.randrange(1, 5)
            days = sorted(rng.sample([5, 9, 14, 20, 30, 30, 45, 60, 91, 120], n_exp))
            days = sorted(set(days))
            ex = []
            for d in days:
                e = {"d": d}
                if rng.random() < 0.15:
                    e["reason"] = rng.choice(reasons)
                else:
                    e["atm"] = _rand_float(rng)
                    e["label"] = rng.choice(("exact-model", "approximate: European model on an American-style contract"))
                    e["put"] = _rand_float(rng) if rng.random() > 0.15 else None
                    e["call"] = _rand_float(rng) if rng.random() > 0.15 else None
                    e["put_reason"] = rng.choice(("no_delta_bracket", "price_out_of_bounds"))
                    e["call_reason"] = rng.choice(("no_delta_bracket", "price_out_of_bounds"))
                ex.append(e)
            conv = rng.choice((None, "spot", "forward"))
            eligible = 0 if rng.random() < 0.04 else 4
            fr, fl = mk_frame(ex, {30: 0.2}, eligible, delta_convention=conv)
            cm = ref_side_tenor(ex, 30)
            kind = rng.choice(("frame", "session", None))
            cond = rng.choice((None, "change", "sign_change"))
            direction = rng.choice((None, "up", "down", "either"))
            dname = direction or "either"
            rv, thr = _rand_thr(rng, 2)
            n = rng.choice((1, 1, 2, 3))
            have = rng.choice((0, 1, 2, 3, 5))
            stored = [rng.choice((0, rng.randrange(-10 ** 7, 10 ** 7), rng.randrange(-3 * 10 ** 7, 3 * 10 ** 7))) for _ in range(have)]
            req_conv = conv
            params = {"prior_sessions": n}
            if kind:
                params["prior_kind"] = kind
            if cond:
                params["condition"] = cond
            if direction:
                params["direction"] = direction
            if rv is not None:
                params[_NAME[dname]] = rv
            if req_conv:
                params["delta_convention"] = req_conv
            now_u = None
            if not isinstance(cm[0], str) and not isinstance(cm[1], str):
                now_u = _hr((Fraction(cm[0]) - Fraction(cm[1])) * UNITS)
            pv = pu = None
            if (kind or "frame") == "frame" and rng.random() > 0.15:
                pv, pu = _rand_prior_value(rng, now_u if now_u is not None else 3_000_000)
                params["prior"] = {"kind": "frame", "value": pv, "time_ns": 5}
                if rng.random() < 0.3:
                    params["prior"]["delta_convention"] = rng.choice(("spot", "forward"))
            mism = "prior" in params and params["prior"].get("delta_convention", "spot") != (req_conv or "spot")
            frame_mism = (conv or "spot") != (req_conv or "spot") if conv else False
            sconv = rng.choice((None, "spot", "forward")) if (kind == "session") else None
            series = "XYZ/stock/skew25_fwd" if (req_conv == "forward") else "XYZ/stock/skew25"
            st = None
            if kind == "session" and rng.random() > 0.05:
                st = store_with(stored, series, sconv)[0]
            res = SC.skew_change(fr, fl, 1000, params, st, series, "2026-02-01")
            dc = req_conv or "spot"
            echo = {"condition": cond or "change", "delta_convention": dc, "direction": dname,
                    "feed_delay_tag": "live", "lane": "stock", "mode": "intraday", "prior_kind": kind or "frame",
                    "prior_sessions": n, _NAME[dname]: (str(rv) if isinstance(rv, Fraction) else rv) if rv is not None else "2"}
            echo = {k: echo[k] for k in sorted(echo)}
            labels_of = lambda d_: next(e for e in ex if e["d"] == d_)["label"]
            if mism:
                want = _expect_invalid("convention_mismatch")
            elif kind == "session" and st is not None and any(
                    (sconv or "spot") != dc for _ in [0]) and stored and len(stored) >= 0 and _store_conv_visible(stored, sconv, dc):
                want = _expect_invalid("convention_mismatch")
            elif frame_mism:
                want = _expect_invalid("convention_mismatch")
            elif eligible == 0:
                want = _expect_unavailable("no_eligible_contract", echo)
            elif isinstance(cm[0], str):
                want = _expect_unavailable(cm[0], echo)
            elif isinstance(cm[1], str):
                want = _expect_unavailable(cm[1], echo)
            else:
                if (kind or "frame") == "frame":
                    if pu is None:
                        want = _expect_unavailable("no_prior_reading", echo)
                        priors = None
                    else:
                        priors, ref_u = [], pu
                else:
                    avail = stored if st is not None else []
                    if not avail:
                        want = _expect_unavailable("no_prior_reading", echo)
                        priors = None
                    elif len(avail) < n:
                        want = _expect_unavailable("insufficient_history", echo)
                        priors = None
                    else:
                        last = avail[-n:]
                        ref_u = last[0]
                        priors = [{"session_id": "2026-01-%02d" % (len(avail) - i), "gap": ref_text(last[len(last) - 1 - i])} for i in range(n)]
                if priors is not None or (kind or "frame") == "frame" and pu is not None:
                    if priors is None:
                        priors = []
                    change = (now_u - ref_u) * 100
                    sg = lambda u: (u > 0) - (u < 0)
                    changed = sg(now_u) * sg(ref_u) < 0
                    value = {"now": ref_text(now_u), "priors": priors, "change_points": ref_text(change),
                             "sign_now": sg(now_u), "sign_prior": sg(ref_u), "sign_changed": changed,
                             "delta_convention": dc}
                    fired = changed if (cond == "sign_change") else ref_fire(dname, Fraction(change, UNITS), thr)
                    labs = set()
                    for dd in cm[2]:
                        labs.add(labels_of(dd))
                    want = ("available", None, None, value, fired, sorted(labs), echo)
            _same(self, res, want, (case, params, stored))


def _store_conv_visible(stored, sconv, dc):
    """True when a stored record's convention (None = spot) differs from the request and the read selects it."""
    return (sconv or "spot") != dc and len(stored) > 0


def ref_side_tenor(ex, target):
    """Reference constant-maturity 25-delta put and call IV at `target` days (written from the rules of R-104, R-139,
    R-178; the same float formula as the M1 iv_30d): (put, call, expiries used) or reasons as strings."""
    out = []
    for side, miss in (("put", "put_reason"), ("call", "call_reason")):
        recs = []
        for e in ex:
            if e.get("reason") is not None:
                recs.append((e["d"], e["reason"], None))
            elif e.get(side) is None:
                recs.append((e["d"], e[miss], None))
            else:
                recs.append((e["d"], None, e[side]))
        exact = [r for r in recs if r[0] == target]
        lo = [r for r in recs if r[0] < target]
        hi = [r for r in recs if r[0] > target]
        if exact:
            r = exact[0]
            out.append(r[1] if r[1] else (r[2], (r[0],)))
            continue
        if not lo or not hi:
            out.append("no_bracketing_expiry")
            continue
        a, b = lo[-1], hi[0]
        bad = None
        for r in (a, b):
            if r[1] is not None:
                bad = "no_bracketing_expiry" if r[1] in ("no_atm_strike", "low_surface_coverage") else r[1]
                break
        if bad:
            out.append(bad)
            continue
        wa, wb = a[2] * a[2] * a[0], b[2] * b[2] * b[0]
        var = wa + (wb - wa) * (target - a[0]) / (b[0] - a[0])
        out.append((math.sqrt(var / target), (a[0], b[0])))
    p, c = out
    if isinstance(p, str):
        return p, c if isinstance(c, str) else c[0], None
    if isinstance(c, str):
        return p[0], c, None
    return p[0], c[0], sorted(set(p[1]) | set(c[1]))


# ---- Developer perf SMOKE check (M3A-B4 share). Not gate evidence: GATE_BUDGETS section 8 rule 7. ---------------------

class PerfSmoke(unittest.TestCase):
    """Per name context (one call of each output) against the M3A-B4 budget 1 ms and the 103-name batch 110 ms.
    best of up to 3 samples (m3a_harness.best_of); budgets unchanged. The Tester's 30-repeat bench is the evidence."""
    B4_NAME_S, B4_BATCH_S = 1e-3, 110e-3

    def test_per_name_and_batch_smoke(self):
        ex = [{"d": 20, "atm": 0.18, "put": 0.22, "call": 0.15, "label": "exact-model"},
              {"d": 45, "atm": 0.25, "put": 0.29, "call": 0.22, "label": "exact-model"},
              {"d": 91, "atm": 0.27, "put": 0.31, "call": 0.24, "label": "exact-model"}]
        fr, fl = mk_frame(ex, {30: 0.22, 91: 0.27})
        st, asof = store_with([10 ** 6 * i for i in range(1, 8)])
        p4 = {"prior": {"kind": "frame", "value": "0.2", "time_ns": 5}, "iv_form": "30d", "direction": "either", "x": "5"}
        p7 = {"prior_sessions": 3, "direction": "either", "x": "2"}
        p10 = {"prior_kind": "session", "prior_sessions": 2, "direction": "either", "x": "2"}

        def one():
            SC.iv_change(fr, fl, 1000, p4)
            SC.gap_change(fr, fl, 1000, p7, st, "XYZ/stock/term_30_91", asof)
            SC.skew_change(fr, fl, 1000, p10, st, "XYZ/stock/skew25", asof)

        def sample():
            one()
            reps = 300
            t0 = time.perf_counter()
            for _ in range(reps):
                one()
            per = (time.perf_counter() - t0) / reps
            t0 = time.perf_counter()
            for _ in range(103):
                one()
            return {"name": per, "batch": time.perf_counter() - t0}

        best, used = H.best_of(sample, lambda a, b: {k: min(a[k], b[k]) for k in a},
                               lambda b: b["name"] <= self.B4_NAME_S and b["batch"] <= self.B4_BATCH_S)
        self.assertLessEqual(best["name"], self.B4_NAME_S, (best, LABEL))
        self.assertLessEqual(best["batch"], self.B4_BATCH_S, (best, LABEL))
        self.assertTrue(one() is None)


if __name__ == "__main__":
    unittest.main()
