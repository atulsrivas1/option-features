"""Independent second implementation B' for the additions (stdlib only). Wraps the merged reference model m2_ref (which is
itself independent of oracle A) and re-implements, with different techniques, the new rules: structural checks as an ordered
validator list, pre-open clipping, F12 from prints (prefix sums with bisect), and the grid builder (sorted times + prefix sums).
evaluate(row, mut) accepts a mutant name; each mutant changes one rule."""
import bisect
import decimal
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from fractions import Fraction  # noqa: E402

import m2_ref  # noqa: E402

NS = 1000000000
_M = None


def MU(n):
    return _M == n


def good_int(v):
    return type(v) is int


def grammar_ok(s):
    if not all(ord(c) < 128 for c in s):
        return False
    body = s[1:] if s.startswith("-") else s
    parts = body.split(".")
    if len(parts) > 2:
        return False
    if not all(c in "0123456789" for part in parts for c in part):
        return False
    if len(parts) == 1:
        return len(parts[0]) > 0
    return len(parts[0]) > 0 or len(parts[1]) > 0


def int_text(t):
    """integer ticks as a text decimal"""
    digits = str(abs(t)).rjust(5, "0")
    return ("-" if t < 0 else "") + digits[:-4] + "." + digits[-4:]


def text_price(v):
    if (MU("decimal_price_ok") and isinstance(v, decimal.Decimal)) or (MU("fraction_price_ok") and isinstance(v, Fraction)) \
            or (MU("bytes_price_ok") and isinstance(v, bytes)):
        return True
    if v is None and MU("none_price_ok"):
        return True
    if MU("float_price_ok") and type(v) is float:
        return True
    if MU("bool_price_ok") and type(v) is bool:
        return True
    if type(v) is int:
        return not MU("int_price_rejected")
    if type(v) is not str:
        return False
    if not MU("grammar_lenient") and not grammar_ok(v):
        return False
    try:
        x = Fraction(v)
    except Exception:
        return False
    if MU("trailing_zero_rejected") and "." in v and len(v.split(".")[1]) > 4:
        return False
    if MU("trailing_dot_rejected") and v.endswith("."):
        return False
    if MU("over_precision_ok"):
        return True
    return (x * 10000).denominator == 1


def v_unordered(inp, prm, out):
    ps = inp.get("prints") or []
    for i in range(len(ps) - 1):
        a, b = ps[i], ps[i + 1]
        gi = (lambda z: isinstance(z, int)) if MU("seq_bool_as_int") else good_int
        if MU("pair_float_compared"):
            gi = lambda z: isinstance(z, (int, float))
        if MU("stop_at_skipped") and not all(good_int(z) for z in (a[1], a[6], b[1], b[6])):
            return None
        if all(gi(z) for z in (a[1], a[6], b[1], b[6])) and (a[1] > b[1] or (a[1] == b[1] and a[6] > b[6])):
            return "unordered_prints"


def _sz_ok(p):
    return good_int(p[3]) or (MU("float_size_ok") and type(p[3]) is float)


def _mu_ok(p):
    return good_int(p[4]) or (MU("bool_multiplier_ok") and type(p[4]) is bool) or (MU("float_multiplier_ok") and type(p[4]) is float)


def _tm_ok(p):
    return good_int(p[1]) or (MU("float_time_ok") and type(p[1]) is float)


def _sq_ok(p):
    return good_int(p[6]) or (MU("seq_bool_ok") and type(p[6]) is bool)


def _cid_ok(p):
    return type(p[0]) is str or MU("contract_id_type_ignored")


def v_timeseq(inp, prm, out):
    if MU("types_last"):
        return None
    for p in inp.get("prints") or []:
        if not (_tm_ok(p) and _sq_ok(p)):
            return "malformed_type"


def v_negative(inp, prm, out):
    for p in inp.get("prints") or []:
        if not _sz_ok(p) and not MU("types_last"):
            return "malformed_type"
        if (type(p[3]) is int and p[3] < 0) or (type(p[2]) is int and p[2] < 0) or (type(p[2]) is str and text_price(p[2]) and Fraction(p[2]) < 0):
            return "negative_size_or_price"


def v_multiplier(inp, prm, out):
    for p in inp.get("prints") or []:
        if not _mu_ok(p) and not MU("types_last"):
            return "malformed_type"
        if type(p[4]) is int and p[4] <= 0:
            return "bad_multiplier"


def v_unknown(inp, prm, out):
    if MU("unknown_ignored"):
        return None
    known = inp.get("contracts") or {}
    for p in inp.get("prints") or []:
        if MU("contract_id_type_ignored"):
            if p[0] not in known:
                return "unknown_contract"
            continue
        if type(p[0]) is not str:
            if not MU("types_last"):
                return "malformed_type"
            continue
        if p[0] not in known:
            return "unknown_contract"


def v_malformed(inp, prm, out):
    for p in inp.get("prints") or []:
        fl = (p[5] in (0, 1) and type(p[5]) in (int, bool)) or MU("flag_any_ok") or (MU("flag_float_ok") and type(p[5]) is float)
        if not (text_price(p[2]) and fl):
            return "malformed_type"
        if MU("types_last") and not (_cid_ok(p) and _sz_ok(p) and _mu_ok(p) and _tm_ok(p) and _sq_ok(p)):
            return "malformed_type"


def window_bad(inp, prm, out):
    windowed = out in ("M2-3", "M2-4", "M2-5", "M2-6", "M2-7", "M2-9") or (out == "M2-2" and prm.get("form", "intraday") == "intraday")
    if not windowed or "window_s" not in prm:
        return False
    w = prm["window_s"]
    if MU("float_window_ok") and type(w) is float:
        return False
    allowed = (300,) if out == "M2-5" else (60, 300, 900, 1800, 3600)
    return not (good_int(w) and w in allowed)


def v_window_early(inp, prm, out):
    if MU("window_before_malformed") and window_bad(inp, prm, out):
        return "window_not_allowed"


def validators():
    order = [v_unordered, v_timeseq, v_negative, v_multiplier, v_unknown, v_malformed]
    if MU("window_before_malformed"):
        order = [v_unordered, v_timeseq, v_negative, v_multiplier, v_unknown, v_window_early, v_malformed]
    if MU("prec_malformed_first"):
        order = [v_malformed, v_unordered, v_timeseq, v_negative, v_multiplier, v_unknown, v_window_early]
    if MU("negative_before_unordered"):
        order = [v_negative, v_unordered, v_timeseq, v_multiplier, v_unknown, v_malformed]
    if MU("multiplier_before_negative"):
        order = [v_unordered, v_timeseq, v_multiplier, v_negative, v_unknown, v_malformed]
    if MU("malformed_before_unknown"):
        order = [v_unordered, v_timeseq, v_negative, v_multiplier, v_malformed, v_unknown]
    if MU("types_last"):
        order = [v_unordered, v_timeseq, v_negative, v_multiplier, v_unknown, v_malformed]
    return order


def precheck(inp, prm, out):
    for fn in validators():
        c = fn(inp, prm, out)
        if c:
            return c
    return None


def eligible_in(inp, prm, lo_ns, hi_ns, skip_clip=False):
    """own classification: prints with lo <= t <= hi; returns (eligible list, nonstandard, condition)"""
    T = inp["t_ns"]
    lane = prm.get("lane", "stock")
    filt = prm.get("filter", "all")
    el, ns_, cd = [], 0, 0
    for p in inp["prints"]:
        t = T + p[1]
        if t < lo_ns or t > hi_ns:
            continue
        c = inp["contracts"][p[0]]
        if c["lane"] != lane and not MU("g_lane_ignored"):
            continue
        if filt == "calls" and c["right"] != "C":
            continue
        if filt == "puts" and c["right"] != "P":
            continue
        if p[5] and not MU("g_cond_counted"):
            cd += 1
            continue
        if p[4] != 100 and not MU("g_nonstd_counted"):
            ns_ += 1
            continue
        el.append((t, Fraction(p[2]) * 10000 * p[3] * p[4], p[3], c["right"], p[0]))
    return el, ns_, cd


def f12_points(inp, prm):
    T, op = inp["t_ns"], inp["session"]["open_ns"]
    lo = T - 10 ** 18 if MU("f12_cov_all") else op
    el, ns_, cd = eligible_in(inp, prm, lo, T)
    el.sort(key=lambda z: z[0])
    times = [z[0] for z in el]
    pre = [0]
    for z in el:
        pre.append(pre[-1] + int(z[1]))
    kmax = (T - op) // (60 * NS)
    pts = []
    for k in range(kmax + 1):
        if 60 * k < 900:
            pts.append(None)
            continue
        tk = op + 60 * k * NS
        w60 = 900 if MU("f12_p60_window900") else 60

        def span(w):
            left = bisect.bisect_right(times, tk - w * NS) if MU("f12_start_open") else bisect.bisect_left(times, tk - w * NS)
            return pre[bisect.bisect_right(times, tk)] - pre[left]
        pts.append([span(w60), span(900)])
    return pts, (len(el), ns_, cd)


def _norm(inp):
    if "prints" not in inp:
        return inp
    i2 = dict(inp)
    i2["prints"] = [[p[0], p[1], ("%d.0000" % p[2] if MU("int_price_as_usd") else int_text(p[2])) if type(p[2]) is int else p[2]] + list(p[3:])
                    for p in inp["prints"]]
    return i2


def grid_b(inp, prm):
    code = precheck(inp, prm, "M2-GRID")
    if code:
        return m2_ref.out("invalid_input", code=code)
    inp = _norm(inp)
    w = prm.get("window_s", 60)
    if not good_int(w) or w not in (60, 300, 900, 1800, 3600):
        return m2_ref.out("invalid_input", code="window_not_allowed")
    op = inp["session"]["open_ns"]
    minutes = 390 if MU("g_half_day_390") else inp["session"]["minutes"]
    close = op + minutes * 60 * NS
    lo = op - 10 ** 18 if MU("g_preopen_included") else op
    hi = close + 10 ** 18 if MU("g_postclose_included") else close
    el, ns_, cd = eligible_in(inp, prm, lo, hi)
    only = prm.get("contract_id")
    metric = prm["metric"]
    rows = []
    for t, prem, size, right, cid in el:
        if only is not None and cid != only:
            continue
        v = {"premium": int(prem), "contracts": size, "prints": 1,
             "put_volume": size if right == "P" else 0, "call_volume": size if right == "C" else 0}[metric]
        rows.append((t, v))
    rows.sort()
    times = [r[0] for r in rows]
    pre = [0]
    for r in rows:
        pre.append(pre[-1] + r[1])
    grid = []
    for i in range(minutes):
        ti = op + 60 * i * NS
        a = bisect.bisect_right(times, ti - w * NS) if MU("g_window_open_start") else bisect.bisect_left(times, ti - w * NS)
        grid.append(pre[bisect.bisect_right(times, ti)] - pre[a])
    total = pre[-1]
    cnt_el = len(rows) if only is not None else len(el)
    if only is not None:
        # coverage counts for a contract series cover only that contract
        el2, ns2, cd2 = [], 0, 0
        T = inp["t_ns"]
        for p in inp["prints"]:
            if p[0] != only:
                continue
            t = T + p[1]
            if t < lo or t > hi:
                continue
            c = inp["contracts"][p[0]]
            if c["lane"] != prm.get("lane", "stock") and not MU("g_lane_ignored"):
                continue
            if p[5] and not MU("g_cond_counted"):
                cd2 += 1
            elif p[4] != 100 and not MU("g_nonstd_counted"):
                ns2 += 1
        ns_, cd = ns2, cd2
        sp = [[i, v] for i, v in enumerate(grid) if v != 0]
        val = {"form": "sparse", "sparse": sp, "zero_count": minutes - len(sp) - (1 if MU("g_sparse_zero_wrong") else 0),
               "total": total, "valid_from": min(w // 60, minutes) if MU("g_valid_from_clipped") else w // 60}
    else:
        val = {"form": "dense", "grid": grid, "total": total, "valid_from": min(w // 60, minutes) if MU("g_valid_from_clipped") else w // 60}
    return m2_ref.out(value=val, coverage=m2_ref.cover(cnt_el, ns_, cd))


def store_b(inp, prm):
    import m2add_store_b as SB
    return SB.run(inp, MU, lambda code: m2_ref.out("invalid_input", code=code), lambda v: m2_ref.out(value=v))


def param_problem(out, prm):
    """own parameter validation: wrong types are malformed_type; the grid step must be the int 60"""
    spec = {"M2-1": ("N",), "M2-4": ("N", "threshold_ticks"), "M2-5": ("threshold_ticks",), "M2-6": ("share_threshold",),
            "M2-7": ("N",), "M2-8": ("N",), "M2-9": ("at_least", "at_most"), "M2-11": ("N", "quiet_gap", "n_episodes"),
            "M2-2": ("X",), "M2-10": ("X",)}
    ints_only = ("threshold_ticks", "quiet_gap", "n_episodes")
    if not MU("param_types_ignored"):
        for key in spec.get(out, ()):
            if key not in prm or prm[key] is None:
                continue
            v = prm[key]
            if type(v) is int:
                if key in ("quiet_gap", "n_episodes") and v < 1 and not MU("param_below_one_ok"):
                    return "malformed_type"
                continue
            if type(v) is str and key not in ints_only and v.lstrip("-").replace("/", "", 1).isdigit() and v.count("/") <= 1:
                continue
            return "malformed_type"
    if out == "M2-11" and "grid_s" in prm and not MU("grid_60_ignored"):
        if not (type(prm["grid_s"]) is int and prm["grid_s"] == 60):
            return "grid_not_60s"
    return None


def evaluate(row, mut=None):
    global _M
    _M = mut
    try:
        out, inp, prm = row["output_id"], row["inputs"], dict(row["params"])
        if out == "M2-12":
            return store_b(inp, prm)
        if out == "M2-GRID":
            return grid_b(inp, prm)
        pc = param_problem(out, prm)
        if pc and not ("prints" in inp and precheck(inp, prm, out)):
            return m2_ref.out("invalid_input", code=pc)
        res = _eval(out, inp, prm)
        if "expect_version" in prm:
            res["version"] = "0.2.0a1"
        if MU("ratio_reason_null_present") and out == "M2-9" and res["status"] == "available" and "ratio_reason" not in res:
            res["ratio_reason"] = None
        return res
    finally:
        _M = None


def _eval(out, inp, prm):
    if "prints" in inp:
        code = precheck(inp, prm, out)
        if code:
            return m2_ref.out("invalid_input", code=code)
        inp = _norm(inp)
    T0_, OP_ = inp["t_ns"], inp["session"]["open_ns"]
    if T0_ < OP_ and out in ("M2-4", "M2-5", "M2-6", "M2-9"):
        if MU("cutoff_unavailable"):
            return m2_ref.out("unavailable", "insufficient_window")
        if MU("negative_counts"):
            w_ = prm.get("window_s", 300)
            mine = lambda p: out != "M2-5" or p[0] == inp["series_id"]
            win = [p for p in inp["prints"] if T0_ - w_ * NS <= T0_ + p[1] <= T0_ and mine(p)]
            before = [p for p in inp["prints"] if T0_ + p[1] < OP_ and mine(p)]
            prem = lambda ps: sum(int(Fraction(p[2]) * 10000) * p[3] * p[4] for p in ps if p[4] == 100 and not p[5])
            vol = lambda ps, right: sum(p[3] for p in ps if p[4] == 100 and not p[5] and inp["contracts"][p[0]]["right"] == right)
            cv = m2_ref.cover(0, 0, 0)
            if out == "M2-4":
                return m2_ref.out(value={"large_count": len(win) - len(before), "large_premium": prem(win) - prem(before)}, fired=False, coverage=cv)
            if out == "M2-5":
                return m2_ref.out(value={"window_premium": prem(win) - prem(before)}, fired=False, coverage=cv)
            if out == "M2-6":
                return m2_ref.out(value={"total_premium": prem(win) - prem(before)}, fired=False, coverage=cv)
            return m2_ref.out(value={"put_volume": vol(win, "P") - vol(before, "P"), "call_volume": vol(win, "C") - vol(before, "C")}, fired=False, coverage=cv)
    if window_bad(inp, prm, out):
        prm["window_s"] = -1
    if MU("n_truncated") and "N" in prm:
        prm["N"] = int(Fraction(prm["N"]))
    i2 = inp
    if out in ("M2-4", "M2-5", "M2-6", "M2-9") and "prints" in inp and not MU("preopen_not_clipped"):
        i2 = dict(inp)
        i2["prints"] = [p for p in inp["prints"] if inp["t_ns"] + p[1] >= inp["session"]["open_ns"]]
    counts = None
    if out == "M2-11" and "prints" in inp:
        pts, counts = f12_points(inp, prm)
        i2 = dict(inp)
        i2["points"] = pts
    res = m2_ref.evaluate({"output_id": out, "inputs": i2, "params": prm})
    if counts is not None and res["status"] == "available":
        res["coverage"] = m2_ref.cover(counts[0], counts[1], counts[2], res["coverage"]["unavailable_points"])
    if MU("big_float") and res["status"] == "available" and res["value"]:
        for k in ("large_premium", "window_premium"):
            if k in res["value"]:
                res["value"][k] = int(float(res["value"][k]))
    return res
