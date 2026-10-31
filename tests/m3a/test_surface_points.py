"""S06 chain point outputs V5, V6, V8, V11, V21 (M3A-4, M3A-5, M3A-7, M3A-10, M3A-11): whole-row checks of the 218 author3
rows S06 first-owns (v5 40, v6 34, v8 66, v11 38, v21 40, structural-tagged rows included), unit and hostile-input tests,
a differential against a pure-Python reference written here, and perf row W05 (gate M3A-B4).

Expectations come from the row files and from an exact Fraction reference in this file, never from the library or an
author's oracle. `gating` false rows (near threshold, R-140) assert every value but the fire decision unless the row
marks its boundary as exact (`expected.boundary.exact`, R-182), where the fire decision is asserted as well.

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12
"""
import json
import math
import random
import statistics
import time
import unittest
from fractions import Fraction

import m3a_harness as H
from option_features import m3a_common as C
from option_features import surface_points as P
from option_features import surfaceframe as SF
from option_features.chainiv import ChainContract

FILES = ("m3a_cases_v5.json", "m3a_cases_v6.json", "m3a_cases_v8.json", "m3a_cases_v11.json", "m3a_cases_v21.json")
REPEATS = 30
B4_NAME_S = 0.001
B4_BATCH_S = 0.110
B4_HARD_NAME_S = 0.005
B4_HARD_BATCH_S = 0.550
LABEL = "synthetic workload, relative engineering budget"


def owned_rows():
    out = []
    for fn in FILES:
        for r in H.rows("author3", fn):
            if H.owners_of("author3", fn, r["id"]) == ["S06"]:
                out.append(r)
    return out


def contracts_of(raw):
    return [ChainContract(c["contract_id"], c["expiry_days"], c["right"], c["strike"], c["bid"], c["ask"],
                          c["event_ns"], c["known_at_ns"], c["style"], c["condition"]) for c in raw]


def run_row(row):
    ch = row["inputs"]["chain"]
    return P.point_output(row["output_id"], contracts_of(ch["contracts"]), ch["spot"], ch["rate"],
                          ch["dividend_yield"], ch["cutoff_ns"], dict(row["inputs"]["request"]))


def _close(test, got, want, tol, where):
    test.assertIsNotNone(got, where)
    test.assertLessEqual(abs(Fraction(got) - Fraction(want)), tol, (where, got, want))


def check_value(test, row, res):
    exp = row["expected"]
    tol = {k: Fraction(v) for k, v in exp["tol"].items()}
    rid = row["id"]
    got, want = res.value, exp["value"]
    for key in exp["assert"]:
        where = (rid, key)
        if key == "delta_convention":                # R-184: echoed in params, never in value keys
            test.assertEqual(res.params["delta_convention"], want[key], where)
            test.assertNotIn(key, got, where)
        elif key == "pairs":
            test.assertEqual(set(got["pairs"]), set(want["pairs"]), where)
            for name, wp in want["pairs"].items():
                gp = got["pairs"][name]
                _close(test, gp["longer"], wp["longer"], tol["iv"], where + (name, "longer"))
                _close(test, gp["shorter"], wp["shorter"], tol["iv"], where + (name, "shorter"))
                _close(test, gp["spread_points"], wp["spread_points"], tol["points"], where + (name, "spread"))
        elif key in ("nearest_days", "second_days", "tenor"):
            test.assertEqual(got[key], want[key], where)
        elif key == "ratio":
            _close(test, got[key], want[key], tol["ratio"], where)
        elif key in ("wings_mid", "atm_iv", "put25_iv", "call25_iv"):
            _close(test, got[key], want[key], tol["iv"], where)
        else:                                        # *_points, put_distance, call_distance
            _close(test, got[key], want[key], tol["points"], where)


def check_row(test, row, res):
    exp = row["expected"]
    rid = row["id"]
    test.assertEqual(res.output_id, row["output_id"], rid)
    test.assertEqual((res.status, res.reason, res.code), (exp["status"], exp["reason"], exp["code"]), rid)
    if exp["status"] != "available":
        test.assertIsNone(res.value, rid)
        test.assertIsNone(res.fired, rid)
        test.assertEqual(res.labels, [], rid)
        C.canonical_line(res)
        return
    check_value(test, row, res)
    boundary = (exp.get("boundary") or {}).get("exact")
    if exp["fire_assert"] or boundary:
        test.assertEqual(res.fired, exp["fired"], (rid, "fired"))
    else:
        test.assertIsInstance(res.fired, bool, rid)
    if exp["coverage"] is not None:
        for k, v in exp["coverage"].items():
            test.assertEqual(res.coverage[k], v, (rid, "coverage", k))
    if exp["labels_assert"]:
        test.assertEqual(res.labels, exp["labels"], (rid, "labels"))
    json.dumps(res.value)
    C.canonical_line(res)


ROWS = owned_rows()


class Rows(unittest.TestCase):
    def test_owned_row_count(self):
        self.assertEqual(len(ROWS), 218)
        by = {}
        for r in ROWS:
            by[r["family"]] = by.get(r["family"], 0) + 1
        self.assertEqual(by, {"V5": 40, "V6": 34, "V8": 66, "V11": 38, "V21": 40})


def _make(row):
    def test(self):
        check_row(self, row, run_row(row))
    return test


for _r in ROWS:
    setattr(Rows, "test_" + _r["id"].replace("-", "_"), _make(_r))


# ================================================================================================ synthetic frames
EXACT = "exact-model"
APPROX = "approximate: European model on an American-style contract"
SOLVER = ("upper_asymptote", "sigma_cap", "price_out_of_bounds", "iteration_budget")
EXPIRY_BAD = ("no_atm_strike", "low_surface_coverage") + SOLVER


def units_str(u):
    """10^-8 units as 8-decimal text, no sign on zero (written here, independent of the library)."""
    sign = "-" if u < 0 else ""
    u = abs(u)
    return "%s%d.%08d" % (sign, u // 10 ** 8, u % 10 ** 8)


def rhe(fr):
    """round half to even of a Fraction to an int."""
    q, r = divmod(fr.numerator, fr.denominator)
    r2 = 2 * r
    if r2 > fr.denominator or (r2 == fr.denominator and q % 2 == 1):
        q += 1
    return q


def units_of(fr):
    return rhe(Fraction(fr) * 10 ** 8)


def synth_frame(rnd, tenor_targets, force_ok=False, eligible=None):
    """A consistent synthetic M3A-0 result: (frame Result, floats, labels, expiry list). No chain, no solver."""
    pool = [1, 3, 5, 7, 9, 14, 20, 21, 28, 30, 31, 45, 60, 75, 91, 120]
    days = sorted(rnd.sample(pool, rnd.randrange(0 if not force_ok else 3, 7)))
    if force_ok and 30 not in days and rnd.random() < 0.5:
        days = sorted(days + [30]) if 30 not in days else days
    exps = []
    for d in days:
        e = {"days": d, "status": "available", "reason": None, "atm": None, "put": None, "call": None,
             "lab": {"atm": None, "put25_iv": [], "call25_iv": []}}
        if force_ok or rnd.random() < 0.8:
            atm = rnd.uniform(0.05, 1.2) if rnd.random() < 0.97 else rnd.choice((0.0, 0.2, 0.5))
            e["atm"] = atm
            e["lab"]["atm"] = rnd.choice((EXACT, EXACT, APPROX))
            for side, key in (("put", "put25_iv"), ("call", "call25_iv")):
                if force_ok or rnd.random() < 0.85:
                    iv = max(0.0, atm + rnd.uniform(-0.08, 0.2))
                    if rnd.random() < 0.05:
                        iv = atm                                        # distance exactly 0
                    e[side] = ("available", None, iv)
                    e["lab"][key] = [rnd.choice((EXACT, EXACT, APPROX)) for _ in range(rnd.choice((1, 2)))]
                else:
                    e[side] = ("unavailable", rnd.choice(("no_delta_bracket", "no_delta_bracket") + SOLVER), None)
        else:
            e["status"], e["reason"] = "unavailable", rnd.choice(EXPIRY_BAD)
            e["put"] = e["call"] = ("unavailable", e["reason"], None)
        exps.append(e)
    from option_features.tenors import ExpiryIV, tenors as kernel
    recs = [ExpiryIV(e["days"], e["status"], e["reason"], e["atm"]) for e in exps]
    ten = kernel(recs, tuple(tenor_targets))
    frame_exp, float_exp, labels = {}, {}, {}
    for e in exps:
        def side(t):
            return {"status": t[0], "reason": t[1], "value": None if t[2] is None else C.round_text(t[2])}
        frame_exp[str(e["days"])] = {"status": e["status"], "reason": e["reason"], "forward": "1.00000000",
                                     "atm_iv": None if e["atm"] is None else C.round_text(e["atm"]),
                                     "put25_iv": side(e["put"]), "call25_iv": side(e["call"])}
        float_exp[str(e["days"])] = {"atm_iv": e["atm"], "put25_iv": e["put"][2], "call25_iv": e["call"][2]}
        labels[str(e["days"])] = e["lab"]
    frame_ten, float_ten = {}, {}
    for t in tenor_targets:
        r = ten[t]
        frame_ten[str(t)] = {"status": r.status, "reason": r.reason, "iv": None if r.iv is None else C.round_text(r.iv),
                             "method": r.method, "expiries_used": None if r.expiries_used is None else list(r.expiries_used)}
        float_ten[str(t)] = r.iv
    elig = eligible if eligible is not None else (0 if rnd.random() < 0.03 else rnd.randrange(1, 40))
    cov = {"listed_strikes": elig + 3, "eligible_strikes": elig, "per_expiry": {}, "contract_reasons": {}}
    res = C.Result.available("M3A-0", None, None, 10, None, params={"delta_convention": "spot", "lane": "stock",
                                                                      "feed_delay_tag": "live"},
                             coverage=cov, labels=[], lane="stock",
                             frame={"expiries": frame_exp, "tenors": frame_ten})
    floats = {"expiries": float_exp, "tenors": float_ten, "available": True}
    return res, floats, labels, exps


# ================================================================================================ the reference
def ref_cm(recs, target, side):
    """Constant-maturity value at `target` days of one quantity from per-expiry records, written from the rules (R-104,
    R-139, R-178): returns (reason, iv, expiries_used). recs: [(days, status, reason, value)] ascending."""
    exact = [r for r in recs if r[0] == target]
    if exact:
        r = exact[0]
        return (None, r[3], (target,)) if r[1] == "available" else (r[2], None, None)
    lo = [r for r in recs if r[0] < target]
    hi = [r for r in recs if r[0] > target]
    if not lo or not hi:
        return "no_bracketing_expiry", None, None
    lo, hi = lo[-1], hi[0]
    for r in (lo, hi):
        if r[1] != "available":
            return ("no_bracketing_expiry" if r[2] in ("no_atm_strike", "low_surface_coverage") else r[2]), None, None
    w_lo = lo[3] * lo[3] * lo[0]
    w_hi = hi[3] * hi[3] * hi[0]
    var = w_lo + (w_hi - w_lo) * (target - lo[0]) / (hi[0] - lo[0])
    return None, math.sqrt(var / target), (lo[0], hi[0])


DEFAULT_THR = {"M3A-4": "3", "M3A-5": "3", "M3A-7": "5", "M3A-10": "3", "M3A-11": None}
KEY = {"up": "at_least", "down": "at_most", "either": "x"}


def ref_point(oid, exps, eligible, labels, params):
    """(status, reason_or_code, value, fired, labels) for one output; written from the rulings, not from the library."""
    direction = params.get("direction", "up")
    thr_text = params.get(KEY[direction], DEFAULT_THR[oid])
    if thr_text is None:
        return "invalid_input", "threshold_required", None, None, []
    thr = Fraction(thr_text)
    if eligible == 0:
        return "unavailable", "no_eligible_contract", None, None, []
    atm = [(e["days"], e["status"], e["reason"], e["atm"]) for e in exps]
    put = [(e["days"], e["put"][0], e["put"][1], e["put"][2]) for e in exps]
    call = [(e["days"], e["call"][0], e["call"][1], e["call"][2]) for e in exps]
    lab = {e["days"]: e["lab"] for e in exps}
    used_labels = []

    def atm_l(days):
        return [lab[d]["atm"] for d in days if lab[d]["atm"] is not None]

    def side_l(used, key):
        return [x for d in used or () for x in lab[d][key]]
    kind = "pts"
    if oid == "M3A-4":
        shown = {}
        fail = {}
        for name, (s, l) in (("9-30", (9, 30)), ("30-91", (30, 91))):
            rs, vs, us = ref_cm(atm, s, "atm")
            rl, vl, ul = ref_cm(atm, l, "atm")
            if rs or rl:
                fail[name] = rs or rl
                continue
            x = rhe((Fraction(vl) - Fraction(vs)) * 100 * 10 ** 8)
            shown[name] = (x, vl, vs, atm_l(us) + atm_l(ul))
        want = params.get("pair", "9-30")
        if want not in shown:
            return "unavailable", fail[want], None, None, []
        label = {"9-30": "9_30", "30-91": "30_91"}
        value = {"pairs": {label[n]: {"longer": C.round_text(v[1]), "shorter": C.round_text(v[2]),
                                      "spread_points": units_str(v[0])} for n, v in shown.items()}}
        x = shown[want][0]
        used_labels = [y for v in shown.values() for y in v[3]]
    elif oid == "M3A-5":
        ok = [e for e in exps if e["status"] == "available"]
        if len(ok) < 2:
            return "unavailable", "fewer_than_two_expiries", None, None, []
        n, s = ok[0], ok[1]
        x = rhe((Fraction(s["atm"]) - Fraction(n["atm"])) * 100 * 10 ** 8)
        value = {"nearest_days": n["days"], "second_days": s["days"], "spread_points": units_str(x)}
        used_labels = atm_l((n["days"], s["days"]))
    else:
        a = ua = None
        if oid in ("M3A-10", "M3A-11"):
            ra, a, ua = ref_cm(atm, 30, "atm")
            if ra:
                return "unavailable", ra, None, None, []
        rp, p, up = ref_cm(put, 30, "put")
        if rp:
            return "unavailable", rp, None, None, []
        rc, c, uc = ref_cm(call, 30, "call")
        if rc:
            return "unavailable", rc, None, None, []
        used_labels = atm_l(ua or ()) + side_l(up, "put25_iv") + side_l(uc, "call25_iv")
        if oid == "M3A-7":
            x = rhe((Fraction(p) - Fraction(c)) * 100 * 10 ** 8)
            value = {"put25_iv": C.round_text(p), "call25_iv": C.round_text(c), "skew_points": units_str(x),
                     "tenor": 30}
            used_labels = side_l(up, "put25_iv") + side_l(uc, "call25_iv")
        elif oid == "M3A-10":
            mid = (Fraction(p) + Fraction(c)) / 2
            x = rhe((mid - Fraction(a)) * 100 * 10 ** 8)
            value = {"wings_mid": units_str(units_of(mid)), "atm_iv": C.round_text(a), "curvature_points": units_str(x)}
        else:
            pd = rhe((Fraction(p) - Fraction(a)) * 100 * 10 ** 8)
            cd = rhe((Fraction(c) - Fraction(a)) * 100 * 10 ** 8)
            if cd == 0:
                return "unavailable", "zero_denominator", None, None, []
            x = rhe((Fraction(p) - Fraction(a)) / (Fraction(c) - Fraction(a)) * 10 ** 8)       # unrounded distances
            value = {"put_distance": units_str(pd), "call_distance": units_str(cd), "ratio": units_str(x)}
            kind = "ratio"
    v = Fraction(x, 10 ** 8)
    if direction == "up":
        fired = v >= thr
    elif direction == "down":
        fired = v <= (thr if kind == "ratio" else -thr)
    else:
        fired = abs(v) >= thr
    if params.get("feed_delay_tag") == "delayed":
        used_labels = used_labels + ["delayed"]
    return "available", None, value, fired, sorted(set(used_labels))


def random_params(rnd, oid):
    p = {"feed_delay_tag": rnd.choice(("live", "live", "delayed"))}
    if oid == "M3A-4":
        p["pair"] = rnd.choice(("9-30", "30-91", "9-30"))
    d = rnd.choice((None, "up", "down", "either"))
    if d is not None:
        p["direction"] = d
    dd = d or "up"
    if rnd.random() < 0.7:
        p[KEY[dd]] = rnd.choice(("0", "1", "2.5", "3", "5", "10", "-2", "0.00000001", "4.25")) if oid == "M3A-11" \
            else rnd.choice(("0", "0.5", "1", "2", "3", "5", "7.25", "12"))
    return p


FRAME_TENORS = {"M3A-4": (9, 30, 91), "M3A-5": (), "M3A-7": (), "M3A-10": (30,), "M3A-11": (30,)}


def run_core(oid, res, floats, labels, params):
    res.params["feed_delay_tag"] = params.get("feed_delay_tag", "live")      # the frame was built with the request tag
    return P.point_from_frame(oid, res, floats, params, labels)


def compare(test, oid, got, want, where):
    status, reason, value, fired, labels = want
    if status == "invalid_input":
        test.assertEqual((got.status, got.code), (status, reason), where)
        return
    test.assertEqual((got.status, got.reason), (status, reason), where)
    test.assertEqual(got.value, value, where)
    test.assertEqual(got.fired, fired, where)
    test.assertEqual(got.labels, labels, where)


class Differential(unittest.TestCase):
    """The library against a pure-Python reference (above) on random synthetic frames: statuses, reasons, every value
    text, the fire decision and the labels must be equal, bit for bit. Frames are built without a chain or a solver, so
    every failure precedence of the rulings is reached many times."""

    CASES = 24000

    def test_random_frames(self):
        rnd = random.Random(20261031)
        seen = {}
        for i in range(self.CASES):
            oid = OUTPUTS[i % 5]
            res, floats, labels, exps = synth_frame(rnd, FRAME_TENORS[oid], force_ok=rnd.random() < 0.4)
            params = random_params(rnd, oid)
            want = ref_point(oid, exps, res.coverage["eligible_strikes"], labels, params)
            got = run_core(oid, res, floats, labels, params)
            compare(self, oid, got, want, (i, oid, params))
            seen[(oid, want[0], want[1])] = seen.get((oid, want[0], want[1]), 0) + 1
        for oid in OUTPUTS:
            self.assertGreater(seen.get((oid, "available", None), 0), 200, oid)
            self.assertGreater(sum(v for k, v in seen.items() if k[0] == oid and k[1] == "unavailable"), 200, oid)
        for reason in ("no_bracketing_expiry", "no_delta_bracket", "low_surface_coverage", "no_atm_strike",
                       "no_eligible_contract", "fewer_than_two_expiries", "zero_denominator"):
            self.assertTrue(any(k[2] == reason for k in seen), reason)
        self.assertTrue(any(k[1] == "invalid_input" for k in seen))


OUTPUTS = ("M3A-4", "M3A-5", "M3A-7", "M3A-10", "M3A-11")


# ================================================================================================ exact frames by hand
def hand_frame(expiries, tenor_targets=(9, 30, 91), eligible=10, delayed=False, labels=None):
    """expiries {days: (atm, put, call)} (None = that item unavailable with no_delta_bracket / no_atm_strike), a frame
    Result built the way S05 builds it (the tenor kernel over the per-expiry ATM IVs)."""
    rnd = random.Random(0)
    res, floats, lab, exps = synth_frame(rnd, tenor_targets, force_ok=True, eligible=eligible)
    from option_features.tenors import ExpiryIV, tenors as kernel
    exps = []
    frame_exp, float_exp, lab = {}, {}, {}
    for d, (atm, put, call) in sorted(expiries.items()):
        e = {"days": d, "status": "available" if atm is not None else "unavailable",
             "reason": None if atm is not None else "no_atm_strike", "atm": atm,
             "put": ("available", None, put) if put is not None else ("unavailable", "no_delta_bracket" if atm is not None
                                                                         else "no_atm_strike", None),
             "call": ("available", None, call) if call is not None else ("unavailable", "no_delta_bracket" if atm is not None
                                                                           else "no_atm_strike", None),
             "lab": (labels or {}).get(d, {"atm": EXACT if atm is not None else None, "put25_iv": [EXACT] if put else [],
                                           "call25_iv": [EXACT] if call else []})}
        exps.append(e)
        frame_exp[str(d)] = {"status": e["status"], "reason": e["reason"], "forward": "1.00000000",
                             "atm_iv": None if atm is None else C.round_text(atm),
                             "put25_iv": {"status": e["put"][0], "reason": e["put"][1], "value": None},
                             "call25_iv": {"status": e["call"][0], "reason": e["call"][1], "value": None}}
        float_exp[str(d)] = {"atm_iv": atm, "put25_iv": put, "call25_iv": call}
        lab[str(d)] = e["lab"]
    ten = kernel([ExpiryIV(e["days"], e["status"], e["reason"], e["atm"]) for e in exps], tuple(tenor_targets))
    frame_ten = {str(t): {"status": r.status, "reason": r.reason, "iv": None, "method": r.method,
                          "expiries_used": None if r.expiries_used is None else list(r.expiries_used)}
                 for t, r in ten.items()}
    float_ten = {str(t): r.iv for t, r in ten.items()}
    res.frame = {"expiries": frame_exp, "tenors": frame_ten}
    res.coverage = {"listed_strikes": 12, "eligible_strikes": eligible, "per_expiry": {}, "contract_reasons": {}}
    res.params = {"delta_convention": "spot", "lane": "stock", "feed_delay_tag": "delayed" if delayed else "live"}
    return res, {"expiries": float_exp, "tenors": float_ten, "available": True}, lab, exps


def point(oid, expiries, params=None, **kw):
    res, floats, lab, _ = hand_frame(expiries, FRAME_TENORS[oid], **kw)
    return P.point_from_frame(oid, res, floats, params or {}, lab)


class Rounding(unittest.TestCase):
    """Derived points are the exact difference of the unrounded floats, x100, rounded ONCE; the fire decision uses the
    rounded decimal (R-35, R-48, R-181)."""

    def test_round_once_not_round_first(self):
        # 0.2000000049 - 0.1000000051 = 0.0999999998 -> 9.99999998 points; rounding each IV first gives 10.00000000
        r = point("M3A-4", {9: (0.1000000051, None, None), 30: (0.2000000049, None, None), 91: (0.3, None, None)})
        self.assertEqual(r.value["pairs"]["9_30"]["spread_points"], "9.99999998")
        self.assertEqual(r.value["pairs"]["9_30"]["longer"], "0.20000000")
        self.assertEqual(r.value["pairs"]["9_30"]["shorter"], "0.10000001")

    def test_fire_uses_the_rounded_decimal(self):
        # the float difference is 0.030000000000000027: 3.00000000 points after rounding, so "at least 3" fires
        r = point("M3A-4", {9: (0.2, None, None), 30: (0.23, None, None), 91: (0.4, None, None)}, {"at_least": "3"})
        self.assertEqual(r.value["pairs"]["9_30"]["spread_points"], "3.00000000")
        self.assertTrue(r.fired)
        r = point("M3A-4", {9: (0.2, None, None), 30: (0.23, None, None), 91: (0.4, None, None)},
                  {"at_least": "3.00000001"})
        self.assertFalse(r.fired)

    def test_half_even_tie_in_points(self):
        tie = Fraction(1, 2 ** 11)                # 100 * 1e8 / 2048 = 4882812.5: a true tie
        a, b = 0.25 + float(tie), 0.25
        r = point("M3A-5", {9: (b, None, None), 30: (a, None, None)})
        self.assertEqual(r.value["spread_points"], "0.04882812")        # 4882812 is even: round half to even
        a, b = 0.25 + 3 * float(tie), 0.25        # 14648437.5 -> 14648438 (even)
        r = point("M3A-5", {9: (b, None, None), 30: (a, None, None)})
        self.assertEqual(r.value["spread_points"], "0.14648438")

    def test_negative_call_distance_rounds_the_ratio_correctly(self):
        r = point("M3A-11", {20: (0.2, 0.3, 0.19), 40: (0.2, 0.3, 0.19)}, {"at_least": "-5"})
        pd = Fraction(r.value["put_distance"]), Fraction(r.value["call_distance"])
        self.assertLess(pd[1], 0)
        want = rhe((Fraction(0.3) - Fraction(0.2)) / (Fraction(0.19) - Fraction(0.2)) * 10 ** 8)
        self.assertEqual(r.value["ratio"], units_str(want))


class FireRules(unittest.TestCase):
    EXP = {9: (0.18, 0.2, 0.2), 30: (0.22, 0.25, 0.19), 91: (0.23, 0.3, 0.2)}

    def fire(self, oid, params):
        r = point(oid, self.EXP, params)
        self.assertEqual(r.status, "available", r.reason)
        return r.fired

    def test_directions_and_inclusive_thresholds_v5(self):
        # 9-30 spread = 4 points (0.22 - 0.18), up/down are mirror images
        self.assertTrue(self.fire("M3A-4", {"at_least": "4"}))
        self.assertFalse(self.fire("M3A-4", {"at_least": "4.00000001"}))
        self.assertTrue(self.fire("M3A-4", {"direction": "down", "at_most": "-4"}))      # x = 4 <= -(-4)
        self.assertFalse(self.fire("M3A-4", {"direction": "down", "at_most": "-3.99999999"}))
        self.assertFalse(self.fire("M3A-4", {"direction": "down", "at_most": "3"}))
        self.assertTrue(self.fire("M3A-4", {"direction": "either", "x": "4"}))
        self.assertTrue(self.fire("M3A-4", {"direction": "either", "x": "3.99999999"}))
        self.assertFalse(self.fire("M3A-4", {"direction": "either", "x": "4.00000001"}))

    def test_down_fires_at_minus_x_for_points(self):
        exp = {9: (0.22, 0.2, 0.2), 30: (0.18, 0.25, 0.19), 91: (0.23, 0.3, 0.2)}       # spread -4
        r = point("M3A-4", exp, {"direction": "down", "at_most": "4"})
        self.assertTrue(r.fired)
        r = point("M3A-4", exp, {"direction": "down", "at_most": "3.99999999"})
        self.assertTrue(r.fired)                                    # -4 <= -3.99999999
        r = point("M3A-4", exp, {"direction": "down", "at_most": "4.00000001"})
        self.assertFalse(r.fired)                                   # -4 <= -4.00000001 is false

    def test_defaults_per_output(self):
        for oid, thr in (("M3A-4", "3"), ("M3A-5", "3"), ("M3A-7", "5"), ("M3A-10", "3")):
            r = point(oid, self.EXP, {})
            self.assertEqual(r.params["at_least"], thr, oid)
            self.assertEqual(r.params["direction"], "up", oid)

    def test_v21_has_no_default_and_down_is_ratio_le_x(self):
        r = point("M3A-11", {30: (0.2, 0.25, 0.21)}, {})
        self.assertEqual((r.status, r.code), ("invalid_input", "threshold_required"))
        exp = {30: (0.2, 0.25, 0.21)}               # put distance 5, call distance 1: ratio 5
        self.assertEqual(point("M3A-11", exp, {"at_least": "5"}).value["ratio"], "5.00000000")
        self.assertTrue(point("M3A-11", exp, {"at_least": "5"}).fired)
        self.assertFalse(point("M3A-11", exp, {"at_least": "5.00000001"}).fired)
        self.assertTrue(point("M3A-11", exp, {"direction": "down", "at_most": "5"}).fired)
        self.assertFalse(point("M3A-11", exp, {"direction": "down", "at_most": "4.99999999"}).fired)
        self.assertTrue(point("M3A-11", exp, {"direction": "either", "x": "5"}).fired)

    def test_threshold_key_follows_the_direction(self):
        r = point("M3A-4", self.EXP, {"direction": "down", "at_least": "100"})       # wrong key: the default applies
        self.assertEqual(r.params["at_most"], "3")
        self.assertNotIn("at_least", r.params)

    def test_v5_pair_decides_the_fire_and_availability(self):
        exp = {9: (0.18, 0.2, 0.2), 30: (0.22, 0.25, 0.19)}                  # no 91 expiry: 30-91 has no bracket
        self.assertEqual(point("M3A-4", exp, {"pair": "9-30"}).status, "available")
        r = point("M3A-4", exp, {"pair": "30-91"})
        self.assertEqual((r.status, r.reason), ("unavailable", "no_bracketing_expiry"))
        shown = point("M3A-4", exp, {}).value["pairs"]
        self.assertEqual(list(shown), ["9_30"])
        both = point("M3A-4", self.EXP, {"pair": "30-91"})
        self.assertEqual(sorted(both.value["pairs"]), ["30_91", "9_30"])
        self.assertEqual(both.params["pair"], "30-91")
        self.assertEqual(point("M3A-4", self.EXP, {}).params["pair"], "9-30")        # default pair


class Precedence(unittest.TestCase):
    def test_frame_level_reason_wins(self):
        r = point("M3A-5", {30: (0.2, 0.25, 0.2)}, eligible=0)
        self.assertEqual(r.reason, "no_eligible_contract")                       # not fewer_than_two_expiries (R-162)
        r = point("M3A-5", {30: (0.2, 0.25, 0.2)})
        self.assertEqual(r.reason, "fewer_than_two_expiries")

    def test_v11_v21_order_atm_then_put_then_call(self):
        for oid in ("M3A-10", "M3A-11"):
            kw = {"at_least": "1"}
            # no 30-day bracket on ATM (single expiry at 45): ATM tenor reason first even though sides fail too
            r = point(oid, {45: (0.2, None, None)}, kw)
            self.assertEqual(r.reason, "no_bracketing_expiry", oid)
            # ATM fine (exact 30d expiry), put side missing, call side missing: put first
            r = point(oid, {30: (0.2, None, None)}, kw)
            self.assertEqual(r.reason, "no_delta_bracket", oid)
            # put fine, call missing
            r = point(oid, {30: (0.2, 0.25, None)}, kw)
            self.assertEqual(r.reason, "no_delta_bracket", oid)

    def test_side_reasons_differ_put_before_call(self):
        res, floats, lab, exps = hand_frame({30: (0.2, 0.25, 0.19)}, (30,))
        res.frame["expiries"]["30"]["put25_iv"] = {"status": "unavailable", "reason": "sigma_cap", "value": None}
        res.frame["expiries"]["30"]["call25_iv"] = {"status": "unavailable", "reason": "upper_asymptote", "value": None}
        floats["expiries"]["30"]["put25_iv"] = floats["expiries"]["30"]["call25_iv"] = None
        for oid in ("M3A-7", "M3A-10", "M3A-11"):
            r = P.point_from_frame(oid, res, floats, {"at_least": "1"}, lab)
            self.assertEqual(r.reason, "sigma_cap", oid)
        res.frame["expiries"]["30"]["put25_iv"] = {"status": "available", "reason": None, "value": None}
        floats["expiries"]["30"]["put25_iv"] = 0.25
        for oid in ("M3A-7", "M3A-10", "M3A-11"):
            r = P.point_from_frame(oid, res, floats, {"at_least": "1"}, lab)
            self.assertEqual(r.reason, "upper_asymptote", oid)

    def test_zero_denominator_after_rounding(self):
        # call IV 4e-10 above the ATM: the call distance rounds to 0.00000004? 4e-10 * 100 = 4e-8 -> 4 units; use 4e-11
        r = point("M3A-11", {30: (0.2, 0.25, 0.2 + 4e-11)}, {"at_least": "1"})
        self.assertEqual((r.status, r.reason), ("unavailable", "zero_denominator"))
        r = point("M3A-11", {30: (0.2, 0.25, 0.2 + 6e-11)}, {"at_least": "1"})
        self.assertEqual(r.status, "available")
        self.assertEqual(r.value["call_distance"], "0.00000001")

    def test_v6_skips_ineligible_expiries(self):
        exp = {5: (None, None, None), 7: (0.2, 0.25, 0.19), 14: (None, None, None), 21: (0.24, 0.3, 0.2),
               60: (0.3, 0.3, 0.2)}
        r = point("M3A-5", exp, {})
        self.assertEqual((r.value["nearest_days"], r.value["second_days"], r.value["spread_points"]),
                         (7, 21, "4.00000000"))


class Labels(unittest.TestCase):
    def test_only_used_expiries_are_labelled(self):
        lab = {7: {"atm": EXACT, "put25_iv": [EXACT], "call25_iv": [EXACT]},
               14: {"atm": EXACT, "put25_iv": [EXACT], "call25_iv": [EXACT]},
               21: {"atm": APPROX, "put25_iv": [APPROX], "call25_iv": [APPROX]}}
        exp = {7: (0.2, 0.25, 0.19), 14: (0.22, 0.27, 0.2), 21: (0.24, 0.3, 0.2)}
        r = point("M3A-5", exp, {}, labels=lab)
        self.assertEqual(r.labels, [EXACT])                          # 21 days is neither nearest nor second
        exp[7] = (None, None, None)
        lab[7] = {"atm": None, "put25_iv": [], "call25_iv": []}
        r = point("M3A-5", exp, {}, labels=lab)
        self.assertEqual(r.labels, [APPROX, EXACT])

    def test_delayed_and_sorted(self):
        exp = {7: (0.2, 0.25, 0.19), 21: (0.24, 0.3, 0.2)}
        r = point("M3A-5", exp, {}, delayed=True)
        self.assertEqual(r.labels, ["delayed", EXACT])

    def test_unavailable_has_no_labels_and_no_value(self):
        r = point("M3A-5", {7: (0.2, 0.25, 0.19)})
        self.assertEqual((r.value, r.fired, r.labels), (None, None, []))


class Envelope(unittest.TestCase):
    def test_echo_and_value_keys(self):
        exp = {9: (0.18, 0.2, 0.2), 30: (0.22, 0.25, 0.19), 91: (0.23, 0.3, 0.2)}
        r = point("M3A-7", exp, {"direction": "either", "x": "2"})
        self.assertEqual(r.params["delta_convention"], "spot")
        self.assertNotIn("delta_convention", r.value)
        self.assertEqual(r.params["direction"], "either")
        self.assertEqual(r.params["x"], "2")
        self.assertEqual(sorted(r.params), list(r.params))
        for oid in ("M3A-4", "M3A-5"):
            self.assertNotIn("delta_convention", point(oid, exp).params, oid)
        for oid in ("M3A-10", "M3A-11"):
            self.assertIn("delta_convention", point(oid, exp, {"at_least": "1"}).params, oid)

    def test_canonical_json_and_ids(self):
        exp = {9: (0.18, 0.2, 0.2), 30: (0.22, 0.25, 0.19), 91: (0.23, 0.3, 0.2)}
        for oid in OUTPUTS:
            r = point(oid, exp, {"at_least": "1"})
            self.assertEqual((r.output_id, r.series_id, r.session_id, r.lane), (oid, None, None, "stock"))
            self.assertEqual(json.loads(C.canonical_line(r))["output_id"], oid)
            self.assertIs(type(r.fired), bool)

    def test_coverage_is_the_frames(self):
        r = point("M3A-5", {7: (0.2, 0.25, 0.19), 21: (0.24, 0.3, 0.2)})
        self.assertEqual(r.coverage["eligible_strikes"], 10)


class Hostile(unittest.TestCase):
    def test_point_from_frame_never_raises(self):
        res, floats, lab, _ = hand_frame({9: (0.18, 0.2, 0.2), 30: (0.22, 0.25, 0.19), 91: (0.23, 0.3, 0.2)})
        junk = [None, 5, "x", [], {}, object(), {"expiries": 3, "tenors": 4, "available": True},
                {"expiries": {"9": None}, "tenors": {"30": None}}]
        for oid in OUTPUTS + ("M3A-3", "nope", None, 7):
            for f in (None, 5, res):
                for fl in junk + [floats]:
                    for lb in (None, 5, lab, {"9": 5}):
                        for pr in (None, 5, {}, {"direction": 5}, {"direction": "sideways"}, {"at_least": object()},
                                   {"at_least": "x"}, {"pair": 5}):
                            r = P.point_from_frame(oid, f, fl, pr, lb)
                            self.assertIn(r.status, ("available", "unavailable", "invalid_input"))

    def test_bad_direction_and_threshold(self):
        exp = {7: (0.2, 0.25, 0.19), 21: (0.24, 0.3, 0.2)}
        self.assertEqual(point("M3A-5", exp, {"direction": "sideways"}).code, "invalid_direction")
        self.assertEqual(point("M3A-5", exp, {"at_least": "abc"}).code, "malformed_type")
        self.assertEqual(point("M3A-5", exp, {"at_least": object()}).code, "malformed_type")
        self.assertEqual(P.point_from_frame("M3A-9", None, None).code, "malformed_type")

    def test_point_output_hostile_requests(self):
        for args in ((None, [], "100", 0, 0, 1, {}), ("M3A-4", None, "100", 0, 0, 1, {}),
                     ("M3A-4", [], "100", 0, 0, 1, 5), ("M3A-4", [], "100", 0, 0, 1, {"direction": 5}),
                     ("M3A-4", [], "100", 0, 0, 1, {"pair": "bad"}), ("M3A-11", [], "100", 0, 0, 1, {}),
                     ("M3A-0", [], "100", 0, 0, 1, {}), ("M3A-4", [], "0", 0, 0, 1, {})):
            r = P.point_output(*args)
            self.assertIn(r.status, ("invalid_input", "unavailable"), args)

    def test_structural_before_evaluation(self):
        r = P.point_output("M3A-11", [], "100", 0, 0, 1, {"evaluation_ns": 1})
        self.assertEqual((r.status, r.code), ("invalid_input", "threshold_required"))      # not no_eligible_contract
        r = P.point_output("M3A-11", [], "100", 0, 0, 1, {"evaluation_ns": 1, "at_least": "1"})
        self.assertEqual((r.status, r.reason), ("unavailable", "no_eligible_contract"))
        r = P.point_output("M3A-4", [], "0", 0, 0, 1, {"evaluation_ns": 1})
        self.assertEqual(r.code, "bad_spot")


class FrameReuse(unittest.TestCase):
    """One frame, five outputs: point_from_frame on a frame built once equals point_output for every owned row of the
    sample, and the trusted (cached chain) path gives the same bytes as the validating path."""

    def test_rows_through_a_shared_frame(self):
        from option_features.chainiv import IVChain
        done = 0
        for row in ROWS[::9]:
            if row["expected"]["status"] == "invalid_input":
                continue
            ch = row["inputs"]["chain"]
            cs = contracts_of(ch["contracts"])
            args = (row["output_id"], cs, ch["spot"], ch["rate"], ch["dividend_yield"], ch["cutoff_ns"],
                    dict(row["inputs"]["request"]))
            plain = P.point_output(*args)
            chain = IVChain(cs, ch["spot"], ch["rate"], ch["dividend_yield"], ch["cutoff_ns"],
                            row["inputs"]["request"]["stale_limit_ns"])
            cached = P.point_output(*args, chain=chain, contract_ivs=chain.contract_iv())
            self.assertEqual(C.canonical_line(plain), C.canonical_line(cached), row["id"])
            done += 1
        self.assertGreater(done, 15)


# ================================================================================================ perf W05 (M3A-B4)
def b4_inputs(n, rnd):
    """103 names' cached frames: 8 expiries bracketing 9, 30 and 91 days, every side available."""
    out = []
    for _ in range(n):
        base = rnd.uniform(0.15, 0.6)
        days = (5, 9, 14, 21, 30, 45, 91, 120)
        exp = {d: (base + 0.0005 * i, base + 0.0005 * i + rnd.uniform(0.01, 0.06), base + 0.0005 * i + rnd.uniform(-0.02, 0.03))
               for i, d in enumerate(days)}
        res, floats, lab, _ = hand_frame(exp, (9, 30, 91))
        out.append((res, floats, lab))
    return out


class W05(unittest.TestCase):
    """Perf W05 (gate M3A-B4): the five point outputs of this story from cached frames, 103 names. Budget <= 1 ms per
    name and <= 110 ms per batch (p95), hard 5 ms and 550 ms; every value equals the exact-rational reference. A unit
    SMOKE check (best of up to 3, floors unchanged), not the gate: the Tester's bench is."""

    NAMES = 103

    def _batch(self, frames):
        per = []
        t_batch = time.perf_counter()
        for res, floats, lab in frames:
            t0 = time.perf_counter()
            for oid in OUTPUTS:
                P.point_from_frame(oid, res, floats, {"at_least": "1"}, lab)
            per.append(time.perf_counter() - t0)
        return per, time.perf_counter() - t_batch

    def test_w05_smoke(self):
        frames = b4_inputs(self.NAMES, random.Random(5))
        for oid in OUTPUTS:                      # correctness before timing: values equal the reference
            for res, floats, lab in frames[:20]:
                got = P.point_from_frame(oid, res, floats, {"at_least": "1"}, lab)
                exps = [{"days": int(d), "status": it["status"], "reason": it["reason"],
                         "atm": floats["expiries"][d]["atm_iv"],
                         "put": (it["put25_iv"]["status"], it["put25_iv"]["reason"], floats["expiries"][d]["put25_iv"]),
                         "call": (it["call25_iv"]["status"], it["call25_iv"]["reason"], floats["expiries"][d]["call25_iv"]),
                         "lab": lab[d]} for d, it in res.frame["expiries"].items()]
                compare(self, oid, got, ref_point(oid, exps, 10, lab, {"at_least": "1"}), oid)
        self._batch(frames)                      # warm-up

        def sample():
            per_name, batch = [], []
            for _ in range(REPEATS):
                p, b = self._batch(frames)
                per_name.extend(p)
                batch.append(b)
            per_name.sort()
            batch.sort()
            return (per_name[int(0.95 * len(per_name)) - 1], batch[int(0.95 * len(batch)) - 1])

        (name_p95, batch_p95), used = H.best_of(
            sample, lambda a, b: (min(a[0], b[0]), min(a[1], b[1])),
            lambda r: r[0] <= B4_NAME_S and r[1] <= B4_BATCH_S)
        print("\nW05 M3A-B4 (5 point outputs per name, 103 cached frames): per name p95 %.3f ms, batch p95 %.2f ms "
              "(budget <= 1 ms and <= 110 ms, hard 5 ms and 550 ms; %s; %d attempt(s))"
              % (name_p95 * 1e3, batch_p95 * 1e3, LABEL, used))
        self.assertLessEqual(name_p95, B4_HARD_NAME_S)
        self.assertLessEqual(batch_p95, B4_HARD_BATCH_S)
        self.assertLessEqual(name_p95, B4_NAME_S)
        self.assertLessEqual(batch_p95, B4_BATCH_S)


if __name__ == "__main__":
    unittest.main()
