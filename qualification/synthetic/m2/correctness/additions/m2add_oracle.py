"""Oracle A' for the additions (stdlib only): wraps the merged oracle A (m2common) without altering it.
Adds: unknown_contract and malformed_type (structural, after bad_multiplier), float window_s = window_not_allowed,
prints before open clipped for F4/F7/F17/F18, F12 built from prints, and the trade-to-grid builder (output M2-GRID)."""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fractions import Fraction as Fr  # noqa: E402

import m2common as C  # noqa: E402

NS = C.NS
ORIG = dict(C.ORACLE)
ORIG_STORE = C.o_store
VERSION = "0.2.0a1"
WINDOWED = ("M2-3", "M2-4", "M2-6", "M2-7", "M2-9")


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


GRAMMAR = re.compile(r"-?([0-9]+(\.[0-9]*)?|\.[0-9]+)", re.ASCII)


def price_ok(p):
    if isinstance(p, bool):
        return False
    if isinstance(p, int):
        return True                                   # integer ticks
    if not isinstance(p, str) or not GRAMMAR.fullmatch(p):
        return False
    try:
        v = Fr(p)
    except (ValueError, ZeroDivisionError):
        return False
    return (v * 10000).denominator == 1


def flag_ok(f):
    return isinstance(f, (bool, int)) and f in (0, 1)


def ticks_text(t):
    s = "-" if t < 0 else ""
    a = abs(t)
    return "%s%d.%04d" % (s, a // 10000, a % 10000)


def norm(inp):
    """integer prices are integer ticks: restate them as text decimals for the merged oracle"""
    if "prints" not in inp:
        return inp
    i2 = dict(inp)
    i2["prints"] = [[p[0], p[1], ticks_text(p[2]) if (isinstance(p[2], int) and not isinstance(p[2], bool)) else p[2]] + list(p[3:])
                    for p in inp["prints"]]
    return i2


def precheck(inp):
    ps = inp.get("prints") or []
    for a, b in zip(ps, ps[1:]):
        if is_int(a[1]) and is_int(b[1]) and is_int(a[6]) and is_int(b[6]) and (a[1], a[6]) > (b[1], b[6]):
            return "unordered_prints"
    for p in ps:
        if (is_int(p[3]) and p[3] < 0) or (price_ok(p[2]) and Fr(p[2]) < 0):
            return "negative_size_or_price"
    for p in ps:
        if is_int(p[4]) and p[4] <= 0:
            return "bad_multiplier"
    cons = inp.get("contracts") or {}
    for p in ps:
        if p[0] not in cons:
            return "unknown_contract"
    for p in ps:
        if not (price_ok(p[2]) and is_int(p[3]) and is_int(p[4]) and is_int(p[1]) and is_int(p[6]) and flag_ok(p[5])):
            return "malformed_type"
    return None


def _clip(inp):
    T, op = inp["t_ns"], inp["session"]["open_ns"]
    i2 = dict(inp)
    i2["prints"] = [p for p in inp["prints"] if T + p[1] >= op]
    return i2


def _f12_points(inp, prm):
    T, op = inp["t_ns"], inp["session"]["open_ns"]
    el = T - op
    e, ns_, cd = C.classify(inp, prm, el)
    kmax = el // (60 * NS)
    pts = []
    for k in range(kmax + 1):
        if 60 * k < 900:
            pts.append(None)
            continue
        tk = op + 60 * k * NS
        p60 = sum(x["prem"] for x in e if tk - 60 * NS <= x["t"] <= tk)
        p900 = sum(x["prem"] for x in e if tk - 900 * NS <= x["t"] <= tk)
        pts.append([p60, p900])
    return pts, (len(e), ns_, cd)


def grid_oracle(inp, prm):
    code = precheck(inp)
    if code:
        return C.invalid(code)
    inp = norm(inp)
    w = prm.get("window_s", 60)
    if not is_int(w) or w not in C.ALLOWED:
        return C.invalid("window_not_allowed")
    op, minutes = inp["session"]["open_ns"], inp["session"]["minutes"]
    close = op + minutes * 60 * NS
    metric = prm["metric"]
    only = prm.get("contract_id")
    lane = prm.get("lane", "stock")
    el, ns_, cd = [], 0, 0
    T = inp["t_ns"]
    for p in inp["prints"]:
        t = T + p[1]
        if t < op or t > close:
            continue
        c = inp["contracts"][p[0]]
        if c["lane"] != lane or (only is not None and p[0] != only):
            continue
        if p[5]:
            cd += 1
            continue
        if p[4] != 100:
            ns_ += 1
            continue
        tk = C.tick(p[2])
        f = {"premium": tk * p[3] * p[4], "contracts": p[3], "prints": 1,
             "put_volume": p[3] if c["right"] == "P" else 0, "call_volume": p[3] if c["right"] == "C" else 0}[metric]
        el.append((t, f))
    grid = []
    for i in range(minutes):
        ti = op + 60 * i * NS
        grid.append(sum(f for t, f in el if ti - w * NS <= t <= ti))
    total = sum(f for _, f in el)
    if only is not None:
        sp = [[i, v] for i, v in enumerate(grid) if v != 0]
        val = {"form": "sparse", "sparse": sp, "zero_count": minutes - len(sp), "total": total, "valid_from": w // 60}
    else:
        val = {"form": "dense", "grid": grid, "total": total, "valid_from": w // 60}
    return C.res(value=val, cv=C.cov(len(el), ns_, cd)), \
        "grid point i at open + 60 s x i; value = %s over [t_i - %d s, t_i] of session prints in [open, close]; total = %d over %d eligible prints" % (
            metric, w, total, len(el))


def store_oracle(inp, prm):
    import m2add_store_a as SA
    return SA.store(inp, prm, C.invalid, lambda **kw: C.res(**kw))


FRACTION_PARAMS = {"M2-1": ("N",), "M2-4": ("N",), "M2-6": ("share_threshold",), "M2-7": ("N",), "M2-8": ("N",),
                   "M2-9": ("at_least", "at_most"), "M2-11": ("N",), "M2-2": ("X",), "M2-10": ("X",)}
INT_PARAMS = {"M2-4": ("threshold_ticks",), "M2-5": ("threshold_ticks",), "M2-11": ("quiet_gap", "n_episodes")}
FRACTION_TEXT = re.compile(r"-?[0-9]+(/[0-9]+)?")


def param_code(out, prm):
    """parameter-level malformed_type (bool and float values) and grid_not_60s"""
    for k in FRACTION_PARAMS.get(out, ()):
        v = prm.get(k)
        if v is not None and not (is_int(v) or (isinstance(v, str) and FRACTION_TEXT.fullmatch(v))):
            return "malformed_type"
    for k in INT_PARAMS.get(out, ()):
        v = prm.get(k)
        if v is not None and (not is_int(v) or (k in ("quiet_gap", "n_episodes") and v < 1)):
            return "malformed_type"
    if out == "M2-11" and "grid_s" in prm and not (is_int(prm["grid_s"]) and prm["grid_s"] == 60):
        return "grid_not_60s"
    return None


def wrap(out):
    def fn(inp, prm):
        r, d = _fn(inp, prm)
        if "expect_version" in prm:
            r["version"] = VERSION
        return r, d

    def _fn(inp, prm):
        if "prints" in inp:
            code = precheck(inp)
            if code:
                return C.invalid(code)
        code = param_code(out, prm)
        if code:
            return C.invalid(code)
        inp = norm(inp)
        prm2 = dict(prm)
        if out in WINDOWED and "window_s" in prm2 and not is_int(prm2["window_s"]):
            prm2["window_s"] = -1
        if out == "M2-2" and prm2.get("form", "intraday") == "intraday" and "window_s" in prm2 and not is_int(prm2["window_s"]):
            prm2["window_s"] = -1
        if out == "M2-5" and "window_s" in prm2 and not is_int(prm2["window_s"]):
            prm2["window_s"] = -1
        i2 = inp
        if out in ("M2-4", "M2-5", "M2-6", "M2-9") and "prints" in inp:
            i2 = _clip(inp)
        if out == "M2-11" and "prints" in inp:
            pts, counts = _f12_points(inp, prm2)
            i2 = dict(inp)
            i2["points"] = pts
            r, d = ORIG[out](i2, prm2)
            if r["status"] == "available" or r["reason"] == "zero_denominator":
                r["coverage"] = C.cov(counts[0], counts[1], counts[2], (r["coverage"] or {}).get("unavailable_points", 0))
            return r, d + "; built from prints"
        return ORIG[out](i2, prm2)
    return fn


def install():
    for k in list(ORIG):
        C.ORACLE[k] = wrap(k)
    C.ORACLE["M2-GRID"] = grid_oracle
    C.o_store = store_oracle
