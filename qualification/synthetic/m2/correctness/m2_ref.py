"""Independent second implementation (reference model) of the M2 rules, exact Fractions, stdlib only.

Written separately from m2common (oracle A): different decomposition, no shared code. It reads only the raw row
(inputs, params). A mutation name can be passed to evaluate(); each mutant changes exactly one rule.
"""
import hashlib
import json
from fractions import Fraction

NS = 1000000000
ALLOWED_W = (60, 300, 900, 1800, 3600)
_MUT = None


def MU(name):
    return _MUT == name


def F(x):
    return Fraction(x)


def show(x):
    x = Fraction(x)
    if x.denominator == 1:
        return int(x)
    return str(x.numerator) + "/" + str(x.denominator)


def ticks_of(price_text):
    v = Fraction(price_text) * 10000
    if v.denominator != 1:
        raise ValueError("price has more than 4 decimals")
    return int(v)


def out(status="available", reason=None, code=None, value=None, fired=None, label=None, coverage=None, **more):
    d = {"status": status, "reason": reason, "code": code, "value": value, "fired": fired, "label": label,
         "coverage": coverage}
    d.update(more)
    return d


def cover(n, nonstd, cond, unavail=0):
    return {"eligible_count": n, "nonstandard_count": nonstd, "excluded_condition_count": cond,
            "unavailable_points": unavail}


# ------------------------------------------------------------------ structural
def structural_code(output, inp, prm):
    prints = inp.get("prints") or []
    if not MU("skip_unordered"):
        for i in range(len(prints) - 1):
            a, b = prints[i], prints[i + 1]
            if a[1] > b[1] or (a[1] == b[1] and a[6] > b[6]):
                return "unordered_prints"
    for p in prints:
        if p[3] < 0 or Fraction(p[2]) < 0:
            return "negative_size_or_price"
    for p in prints:
        if p[4] <= 0:
            return "bad_multiplier"
    hs_ = []
    if inp.get("history"):
        hs_.append(inp["history"])
    for k in sorted(inp.get("parts") or {}):
        hs_.append(inp["parts"][k]["history"])
    for h in hs_:
        seen = set()
        for r in h["sessions"]:
            if r["session_id"] in seen:
                return "duplicate_session"
            seen.add(r["session_id"])
    for h in hs_:
        for r in h["sessions"]:
            prev = None
            for idx, _v in r["gs"]["over"]:
                if idx < 0 or idx >= r["minutes"] or (prev is not None and idx <= prev):
                    return "non_monotone_grid"
                prev = idx
    if inp.get("calendar") is not None:
        if not any(c["session_id"] == inp["session"]["session_id"] for c in inp["calendar"]):
            return "session_not_in_calendar"
    w = prm.get("window_s", 300)
    needs_w = output in ("M2-4", "M2-6", "M2-7", "M2-9", "M2-3") or (output == "M2-2" and prm.get("form", "intraday") == "intraday")
    if needs_w and not MU("skip_window_check") and w not in ALLOWED_W:
        return "window_not_allowed"
    if output == "M2-5" and w != 300 and not MU("skip_window_check"):
        return "window_not_allowed"
    if output == "M2-9" and prm.get("at_least") is None and prm.get("at_most") is None:
        return "threshold_required"
    delayed = inp["session"]["feed_delay_tag"] == "delayed"
    gated = output in ("M2-1", "M2-11", "M2-7", "M2-3") or (output == "M2-2" and prm.get("form", "intraday") == "intraday")
    if delayed and gated and not MU("delay_ignored"):
        return "delayed_feed_tag"
    return None


def bad(code):
    return out("invalid_input", code=code)


# ------------------------------------------------------------------ print windows
def collect(inp, prm, width_s, only_cid=None, apply_filter=True):
    T = inp["t_ns"]
    lo = T - width_s * NS
    if MU("f17_tumbling") and only_cid is not None:
        lo = T - (T % (300 * NS))
    rows, nonstd, cond = [], 0, 0
    want_lane = prm.get("lane", "stock")
    for p in inp["prints"]:
        cid, rel, price, size, mult, excl = p[0], p[1], p[2], p[3], p[4], p[5]
        side = p[7] if len(p) > 7 else None
        t = T + rel
        if MU("win_open_start"):
            inside = t > lo
        else:
            inside = t >= lo
        if MU("win_open_end"):
            inside = inside and t < T
        elif not MU("lookahead"):
            inside = inside and t <= T
        if not inside:
            continue
        c = inp["contracts"][cid]
        if c["lane"] != want_lane and not MU("lane_ignored"):
            continue
        if only_cid is not None and cid != only_cid and not MU("f17_per_name"):
            continue
        if apply_filter:
            f = prm.get("filter", "all")
            if (f == "calls" and c["right"] != "C") or (f == "puts" and c["right"] != "P"):
                continue
        if MU("both_nonstd_first"):
            if mult != 100:
                nonstd += 1
                continue
            if excl:
                cond += 1
                continue
        else:
            if excl and not MU("cond_excl_counted"):
                cond += 1
                continue
            if mult != 100 and not MU("nonstd_counted") and not excl:
                nonstd += 1
                continue
        if (MU("f4_side_known") or MU("f18_unknown_dropped")) and side == "unknown":
            continue
        tk = ticks_of(price)
        rows.append({"cid": cid, "prem": tk * size * mult, "size": size, "right": c["right"], "strike": c["strike"],
                     "expiry": c["expiry"], "t": t})
    return rows, nonstd, cond


def total_prem(rows):
    s = 0
    for r in rows:
        s += r["prem"]
    return s


def elapsed_ns(inp):
    return inp["t_ns"] - inp["session"]["open_ns"]


def ratio_of(a, b):
    if MU("float_ratio"):
        return Fraction(float(a) / float(b))
    return Fraction(a) / Fraction(b)


# ------------------------------------------------------------------ M2-1
def ev_f1(inp, prm):
    c = structural_code("M2-1", inp, prm)
    if c:
        return bad(c)
    n_thr = F(prm.get("N", 3))
    if MU("zero_before_window"):
        z, _, _ = collect(inp, prm, 900)
        if total_prem(z) == 0:
            return out("unavailable", "zero_denominator", label=prm.get("filter", "all"))
    if elapsed_ns(inp) < 900 * NS and not MU("f2_clip"):
        return out("unavailable", "insufficient_window")
    r60, _, _ = collect(inp, prm, 900 if MU("w900_for_60") else 60)
    r900, nn, cc = collect(inp, prm, 900)
    p60, p900 = total_prem(r60), total_prem(r900)
    cv = cover(len(r900), nn, cc)
    lab = prm.get("filter", "all")
    if p900 == 0 or (MU("f1_floor") and p900 < 10 ** 9):
        return out("unavailable", "zero_denominator", coverage=cv, label=lab)
    if MU("f1_factor15"):
        ratio = ratio_of(p60, p900)
    elif MU("ratio_inverted"):
        ratio = ratio_of(p900, 15 * p60) if p60 else Fraction(0)
    else:
        ratio = ratio_of(15 * p60, p900)
    return out(value={"p60": p60, "p900": p900, "ratio": show(ratio)}, fired=ratio >= n_thr, label=lab, coverage=cv)


# ------------------------------------------------------------------ M2-4 / M2-5 / M2-6 / M2-9
def ev_f4(inp, prm):
    c = structural_code("M2-4", inp, prm)
    if c:
        return bad(c)
    w = prm.get("window_s", 300)
    thr = prm.get("threshold_ticks", 10 ** 9)
    rows, nn, cc = collect(inp, prm, w)
    cnt, lp = 0, 0
    for r in rows:
        ok = r["prem"] > thr if MU("f4_exclusive") else r["prem"] >= thr
        if ok:
            cnt += 1
            lp += r["prem"]
    return out(value={"large_count": cnt, "large_premium": lp},
               fired=cnt >= F(prm.get("N", 1)), coverage=cover(len(rows), nn, cc))


def ev_f17(inp, prm):
    c = structural_code("M2-5", inp, prm)
    if c:
        return bad(c)
    x = prm.get("threshold_ticks", 10 ** 9)
    rows, nn, cc = collect(inp, prm, 300, only_cid=inp["series_id"])
    s = total_prem(rows)
    fired = s > x if MU("f17_exclusive") else s >= x
    return out(value={"window_premium": s}, fired=fired, coverage=cover(len(rows), nn, cc))


def ev_f7(inp, prm):
    c = structural_code("M2-6", inp, prm)
    if c:
        return bad(c)
    w = prm.get("window_s", 300)
    th = F(prm.get("share_threshold", "3/5"))
    rows, nn, cc = collect(inp, prm, w)
    cv = cover(len(rows), nn, cc)
    den = total_prem(rows)
    if MU("f7_denominator_all"):
        # denominator wrongly includes nonstandard prints of the window
        T = inp["t_ns"]
        extra = 0
        for p in inp["prints"]:
            t = T + p[1]
            cc_ = inp["contracts"][p[0]]
            fl = prm.get("filter", "all")
            right_ok = not ((fl == "calls" and cc_["right"] != "C") or (fl == "puts" and cc_["right"] != "P"))
            if T - w * NS <= t <= T and p[4] != 100 and p[4] > 0 and cc_["lane"] == prm.get("lane", "stock") and right_ok:
                extra += ticks_of(p[2]) * p[3] * p[4]
        den = den + extra
    if total_prem(rows) == 0:
        return out("unavailable", "zero_denominator", coverage=cv)
    by_s, by_e = {}, {}
    for r in rows:
        ks = (r["strike"], r["expiry"]) if MU("f7_strike_not_summed") else r["strike"]
        ke = (r["expiry"], r["strike"]) if MU("f7_expiry_not_summed") else r["expiry"]
        by_s[ks] = by_s.get(ks, 0) + r["prem"]
        by_e[ke] = by_e.get(ke, 0) + r["prem"]
    best_s = max(by_s.values())
    cand_s = [k for k in by_s if by_s[k] == best_s]
    top_s = max(cand_s) if MU("f7_tie_highest_strike") else min(cand_s)
    best_e = max(by_e.values())
    cand_e = [k for k in by_e if by_e[k] == best_e]
    top_e = max(cand_e) if MU("f7_tie_latest_expiry") else min(cand_e)
    top_s_val = top_s[0] if isinstance(top_s, tuple) else top_s
    top_e_val = top_e[0] if isinstance(top_e, tuple) else top_e
    ss, es = Fraction(best_s, den), Fraction(best_e, den)
    return out(value={"top_strike": top_s_val, "strike_share": show(ss), "top_expiry": top_e_val,
                      "expiry_share": show(es), "total_premium": total_prem(rows)},
               fired=(ss >= th or es >= th), coverage=cv)


def _set(v):
    global _MUT
    old = _MUT
    _MUT = v
    return old


def ev_f18(inp, prm):
    c = structural_code("M2-9", inp, prm)
    if c:
        return bad(c)
    w = prm.get("window_s", 300)
    rows, nn, cc = collect(inp, prm, w, apply_filter=False)
    cv = cover(len(rows), nn, cc)
    pv = sum(r["size"] for r in rows if r["right"] == "P")
    cvol = sum(r["size"] for r in rows if r["right"] == "C")
    if pv + cvol == 0:
        return out("unavailable", "zero_denominator", coverage=cv, label="put")
    share = Fraction(cvol if MU("f18_swap") else pv, pv + cvol)
    ratio = None if cvol == 0 else Fraction(pv, cvol)
    al, am = prm.get("at_least"), prm.get("at_most")
    fired = False
    if al is not None:
        fired = fired or (share > F(al) if MU("f18_exclusive") else share >= F(al))
    if am is not None:
        fired = fired or (share < F(am) if MU("f18_exclusive") else share <= F(am))
    more = {}
    if ratio is None:
        more["ratio_reason"] = "zero_denominator"
    return out(value={"put_volume": pv, "call_volume": cvol, "put_share": show(share),
                      "put_call_ratio": None if ratio is None else show(ratio)}, fired=fired, label="put", coverage=cv, **more)


# ------------------------------------------------------------------ history
def grid_values(rec, cal_minutes):
    m = 390 if MU("half_day_390") else cal_minutes
    g = [rec["gs"]["base"]] * m
    for idx, v in rec["gs"]["over"]:
        if idx < m:
            g[idx] = v
    return g


def prior_records(inp, hist, prm, K=20, win=None):
    if win is not None and hist.get("window_s") != win:
        return None
    if MU("accept_19"):
        K = 19
    cal = inp["calendar"]
    ids = [c["session_id"] for c in cal]
    pos = ids.index(inp["session"]["session_id"])
    if hist.get("lane", "stock") != prm.get("lane", "stock") and not MU("lane_ignored"):
        return None
    byid = {}
    for r in hist["sessions"]:
        byid[r["session_id"]] = r
    if MU("missing_substituted"):
        cur = inp["session"]["session_id"]
        have = sorted([r for r in hist["sessions"] if r["complete"] and r["session_id"] < cur],
                      key=lambda r: r["session_id"])
        if len(have) < K:
            return None
        minutes = {c["session_id"]: c["minutes"] for c in cal}
        return [({"minutes": minutes.get(r["session_id"], r["minutes"])}, r) for r in have[-K:]]
    if pos < K:
        return None
    if MU("today_included"):
        window = cal[pos - K + 1:pos + 1]
    else:
        window = cal[pos - K:pos]
    got = []
    for c in window:
        r = byid.get(c["session_id"])
        if r is None:
            return None
        if not r["complete"] and not MU("incomplete_counted"):
            return None
        got.append((c, r))
    return got


def count_rank(values, x):
    n = len(values)
    le = 0
    ge = 0
    for v in values:
        if MU("ties_as_below"):
            if v < x:
                le += 1
        elif v <= x:
            le += 1
        if MU("rank_strict_gt"):
            if v > x:
                ge += 1
        elif v >= x:
            ge += 1
    upper = Fraction(le, n) if MU("rank_le_as_upper") else Fraction(ge, n)
    return n, Fraction(le, n), upper


def middle_value(values):
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return Fraction(s[(n - 1) // 2])
    lo, hi = Fraction(s[n // 2 - 1]), Fraction(s[n // 2])
    if MU("median_lower_middle"):
        return lo
    if MU("median_upper_middle"):
        return hi
    return (lo + hi) / 2


def ev_f2_part(inp, prm, hist, metric, x_fn, form):
    w = prm.get("window_s", 300)
    pct = F(prm.get("X", 5))
    # gate order: history, session complete (eod), window
    steps = ["h", "c", "w"]
    if MU("gate_order_swap") or MU("f2_window_first"):
        steps = ["w", "h", "c"]
    if MU("snc_first") and form == "end_of_day":
        steps = ["c", "h", "w"]
    recs = None
    for st in steps:
        if st == "h":
            recs = prior_records(inp, hist, prm, 20, w if form == "intraday" else None)
            if recs is None:
                return out("unavailable", "insufficient_history")
        elif st == "c":
            if form == "end_of_day" and not inp["session"]["complete"]:
                return out("unavailable", "session_not_complete")
        else:
            if form == "intraday" and elapsed_ns(inp) < w * NS and not MU("f2_clip"):
                return out("unavailable", "insufficient_window")
    mins = Fraction(w // 60)
    vals = []
    if form == "intraday":
        skip = 0 if MU("f2_no_drop") else w // 60
        for c, r in recs:
            g = grid_values(r, c["minutes"])
            for v in g[skip:]:
                vals.append(Fraction(v) / (mins if metric == "prints" else 1))
    else:
        for c, r in recs:
            if metric == "prints" and not MU("f2c_eod_raw_count"):
                vals.append(Fraction(r["total"], c["minutes"]))
            else:
                vals.append(Fraction(r["total"]))
    x, cv = x_fn()
    n, le, up = count_rank(vals, x)
    fired = up < pct / 100 if MU("fires_exclusive") else up <= pct / 100
    label = "delayed" if inp["session"]["feed_delay_tag"] == "delayed" else None
    return out(value={"x": show(x), "n": n, "rank_le": show(le), "upper_share": show(up), "form": form,
                      "metric": metric}, fired=fired, label=label, coverage=cv)


def x_from_window(inp, prm, metric):
    w = prm.get("window_s", 300)

    def go():
        rows, nn, cc = collect(inp, prm, w)
        if metric == "premium":
            x = Fraction(total_prem(rows))
        elif metric == "contracts":
            x = Fraction(sum(r["size"] for r in rows))
        else:
            x = Fraction(len(rows), w if MU("f2c_per_second") else w // 60)
        return x, cover(len(rows), nn, cc)
    return go


def ev_f2(inp, prm):
    c = structural_code("M2-2", inp, prm)
    if c:
        return bad(c)
    form = prm.get("form", "intraday")
    if form == "intraday":
        fn = x_from_window(inp, prm, prm["metric"])
    else:
        if prm["metric"] == "prints" and not MU("f2c_eod_raw_count"):
            fn = (lambda: (Fraction(inp["session"]["total"], inp["session"]["minutes"]), None))
        else:
            fn = (lambda: (Fraction(inp["session"]["total"]), None))
    return ev_f2_part(inp, prm, inp["history"], prm["metric"], fn, form)


def ev_f2d(inp, prm):
    c = structural_code("M2-3", inp, prm)
    if c:
        return bad(c)
    names = ("F2a", "F2b", "F2c")
    mets = ("premium", "contracts", "prints")
    res_ = []
    for nm, mt in zip(names, mets):
        pt = inp["parts"][nm]
        res_.append(ev_f2_part(inp, prm, pt["history"], mt, (lambda pt=pt: (Fraction(pt["x"]), None)), "intraday"))
    shown = []
    for r in res_:
        if r["status"] == "available":
            up = Fraction(r["value"]["upper_share"])
            pc = up if MU("f2d_pct_upper") else 1 - up
            shown.append({"status": "available", "reason": None, "percentile": show(pc)})
        else:
            shown.append({"status": "unavailable", "reason": r["reason"], "percentile": None})
    unav = [r for r in res_ if r["status"] != "available"]
    if unav and not MU("f2d_partial"):
        return out("unavailable", unav[0]["reason"], parts_shown=shown)
    pcs = [Fraction(s["percentile"]) for s in shown if s["percentile"] is not None]
    if not pcs:
        return out("unavailable", unav[0]["reason"], parts_shown=shown)
    avg = sum(pcs) / len(pcs)
    parts = [None if s_["percentile"] is None else show(Fraction(s_["percentile"])) for s_ in shown]
    return out(value={"parts": parts, "average": show(avg), "direction": "higher_is_more_unusual"}, parts_shown=shown)


# ------------------------------------------------------------------ F10 / F20
def stats_block(x, values, n_thr, default):
    med = middle_value(values)
    if MU("mean_instead_of_median"):
        med = Fraction(sum(Fraction(v) for v in values), len(values))
    mean = Fraction(sum(Fraction(v) for v in values), len(values))
    if MU("mean_as_median"):
        med, mean = mean, med
    per = {}
    for nm, st in (("median", med), ("mean", mean)):
        if st == 0 and not MU("zero_stat_available"):
            per[nm] = {"status": "unavailable", "reason": "zero_denominator", "ratio": None, "fired": None}
        elif st == 0:
            per[nm] = {"status": "available", "reason": None, "ratio": 0, "fired": False}
        else:
            r = ratio_of(x, st)
            per[nm] = {"status": "available", "reason": None, "ratio": show(r), "fired": r >= n_thr}
    return med, mean, per


def stat_result(x, med, mean, per, default, **more):
    d = per[default]
    ps = {k: {"status": v["status"], "reason": v["reason"], "ratio": v["ratio"]} for k, v in per.items()}
    if d["status"] != "available":
        return out("unavailable", d["reason"], label=default, per_statistic=ps, **more)
    return out(value={"x": show(x), "median": show(med), "mean": show(mean), "per_statistic": ps,
                      "consumer_default": default}, fired=d["fired"], label=default, **more)


def na_stats(reason, default):
    return out("unavailable", reason, label=default,
               per_statistic={k: {"status": "unavailable", "reason": reason, "ratio": None} for k in ("median", "mean")})


def ev_f10(inp, prm):
    c = structural_code("M2-7", inp, prm)
    if c:
        return bad(c)
    w = prm.get("window_s", 300)
    default = "mean" if MU("f10_mean_default") else "median"
    n_thr = F(prm.get("N", 2))
    steps = ["h", "w"] if not (MU("gate_order_swap") or MU("f10_window_first")) else ["w", "h"]
    recs = None
    for st in steps:
        if st == "h":
            recs = prior_records(inp, inp["history"], prm, 20, w)
            if recs is None:
                return na_stats("insufficient_history", default)
        elif elapsed_ns(inp) < w * NS and not MU("f2_clip"):
            return na_stats("insufficient_window", default)
    skip = 0 if MU("f2_no_drop") else w // 60
    vals = []
    for c_, r in recs:
        vals.extend(grid_values(r, c_["minutes"])[skip:])
    rows, nn, cc = collect(inp, prm, w)
    x = Fraction(sum(r["size"] for r in rows))
    med, mean, per = stats_block(x, vals, n_thr, default)
    res_ = stat_result(x, med, mean, per, default)
    res_["coverage"] = cover(len(rows), nn, cc)
    return res_


def ev_f20(inp, prm):
    c = structural_code("M2-8", inp, prm)
    if c:
        return bad(c)
    default = "median" if MU("f20_median_default") else "mean"
    n_thr = F(prm.get("N", 2))
    if MU("snc_first") and not inp["session"]["complete"]:
        return na_stats("session_not_complete", default)
    recs = prior_records(inp, inp["history"], prm)
    if recs is None:
        return na_stats("insufficient_history", default)
    if not inp["session"]["complete"]:
        return na_stats("session_not_complete", default)
    totals = [r["total"] for _c, r in recs]
    x = Fraction(inp["session"]["total"])
    med, mean, per = stats_block(x, totals, n_thr, default)
    more = {}
    if inp["session"].get("total_source") == "supplied_eod":
        more["coverage"] = {"degraded": True}
    return stat_result(x, med, mean, per, default, **more)


# ------------------------------------------------------------------ F19
def ev_f19(inp, prm):
    c = structural_code("M2-10", inp, prm)
    if c:
        return bad(c)
    pct = F(prm.get("X", 5))
    cal = inp["calendar"]
    ids = [c_["session_id"] for c_ in cal]
    pos = ids.index(inp["session"]["session_id"])
    byid = {r["session_id"]: r for r in inp["history"]["sessions"]}
    ratios = []
    if pos >= 20:
        for c_ in cal[pos - 20:pos]:
            r = byid.get(c_["session_id"])
            if r is None or not r["complete"]:
                continue
            if r["call"] > 0:
                ratios.append(Fraction(r["put"], r["call"]))
            elif MU("f19_zero_counted"):
                ratios.append(Fraction(0))
    if MU("snc_first") and not inp["session"]["complete"]:
        return out("unavailable", "session_not_complete")
    if len(ratios) < 20:
        return out("unavailable", "insufficient_history")
    s = inp["session"]
    if not s["complete"]:
        return out("unavailable", "session_not_complete")
    if s["call"] == 0:
        return out("unavailable", "zero_denominator")
    x = Fraction(s["put"], s["call"])
    n, le, up = count_rank(ratios, x)
    if MU("zscore_instead"):
        mean = sum(ratios) / n
        var = sum((r - mean) ** 2 for r in ratios) / n
        sd = float(var) ** 0.5
        z = Fraction((float(x - mean) / sd) if sd else 0.0)
        return out(value={"ratio": show(x), "n": n, "rank_le": show(le), "upper_share": show(z)}, fired=z >= 1)
    fired = up < pct / 100 if MU("fires_exclusive") else up <= pct / 100
    return out(value={"ratio": show(x), "n": n, "rank_le": show(le), "upper_share": show(up)}, fired=fired)


# ------------------------------------------------------------------ F12
def ev_f12(inp, prm):
    c = structural_code("M2-11", inp, prm)
    if c:
        return bad(c)
    n_thr = F(prm.get("N", 3))
    gap = prm.get("quiet_gap", 1)
    if MU("f12_gap_minus1"):
        gap = max(1, gap - 1)
    if MU("f12_gap_plus1"):
        gap += 1
    need = prm.get("n_episodes", 1)
    el = elapsed_ns(inp)
    if el < 900 * NS and not MU("f2_clip"):
        return out("unavailable", "insufficient_window")
    opn = inp["session"]["open_ns"]
    last_idx = el // (60 * NS)
    pts = list(inp["points"])
    if MU("f12_lookahead"):
        last_idx = len(pts) - 1

    def state_of(pt):
        if pt is None or pt[1] == 0:
            return None
        return Fraction(15 * pt[0], pt[1])

    in_ep, quiet, eps = False, 0, 0
    prior = inp.get("prior_session_points")
    if MU("f12_merge_sessions") and prior:
        for pt in prior:
            s = state_of(pt)
            if s is not None and s >= n_thr:
                in_ep, quiet = True, 0
            elif in_ep:
                quiet += 1
                if quiet >= gap:
                    in_ep = False
    first = last = None
    peak = peak_k = None
    unav = 0
    for k in range(last_idx + 1):
        pt = pts[k] if k < len(pts) else None
        s = state_of(pt)
        if s is None:
            unav += 1
            if MU("f12_unavail_not_quiet"):
                continue
        if s is not None:
            better = (peak is None) or (s > peak) or (MU("f12_peak_latest") and s == peak)
            if better:
                peak, peak_k = s, k
        if s is not None and s >= n_thr:
            if not in_ep:
                eps += 1
                in_ep = True
                if first is None:
                    first = k
                last = k
            quiet = 0
        elif in_ep:
            quiet += 1
            if quiet >= gap:
                in_ep = False
    v = {"episode_count": eps, "first_ns": None if first is None else opn + first * 60 * NS,
         "last_ns": None if last is None else opn + last * 60 * NS,
         "peak_ratio": None if peak is None else show(peak),
         "peak_ns": None if peak_k is None else opn + peak_k * 60 * NS, "unavailable_points": unav, "quiet_gap": prm.get("quiet_gap", 1)}
    return out(value=v, fired=eps >= need, coverage=cover(0, 0, 0, unav))


# ------------------------------------------------------------------ store
def canon_line(series, metric, win, sid, grid, total, complete, arrival=None):
    body = '{"series_id":%s,"metric":%s,"session_id":%s,"window_s":%s,"grid":[%s],"total":%d,"complete":%s' % (
        json.dumps(series), json.dumps(metric), json.dumps(sid), json.dumps(win), ",".join(str(g) for g in grid), total,
        "true" if complete else "false")
    if arrival is not None:
        body += ',"arrival":%d' % arrival
    return body + "}"


def ev_store(inp, prm):
    k = inp.get("k", 20)
    keep = k + 1 if MU("store_k_plus_1") else k
    ids = [c["session_id"] for c in inp["calendar"]]
    ring = {}
    arrival = 0
    for op in inp["ops"]:
        if op[0] == "append":
            r = op[1]
            key = (r["series_id"], r["metric"], r["window_s"])
            if r["session_id"] not in ids:
                return out("invalid_input", code="session_not_in_calendar")
            cur = ring.setdefault(key, [])
            if cur:
                last_i, cur_i = ids.index(cur[-1]["rec"]["session_id"]), ids.index(r["session_id"])
                if cur_i < last_i:
                    return out("invalid_input", code="out_of_order_append")
                if cur_i == last_i:
                    return out("invalid_input", code="duplicate_session")
            gi = r.get("grid_idx")
            if gi is not None:
                for a in range(len(gi) - 1):
                    if gi[a + 1] <= gi[a]:
                        return out("invalid_input", code="non_monotone_grid")
            cur.append({"rec": dict(r), "arr": arrival})
            arrival += 1
            while len(cur) > keep:
                cur.pop(0)
        elif op[0] == "seal":
            for e in ring.get((op[1], op[2], op[3]), []):
                if e["rec"]["session_id"] == op[4]:
                    e["rec"]["complete"] = True
    keys = list(ring)
    if not MU("store_no_sort"):
        keys.sort()
    lines, hashes, retained = [], [], {}
    for key in keys:
        ents = ring[key]
        if not MU("store_no_sort"):
            ents = sorted(ents, key=lambda e: e["rec"]["session_id"])
        retained["%s|%s|%s" % key] = [e["rec"]["session_id"] for e in ents]
        for e in ents:
            r = e["rec"]
            ln = canon_line(r["series_id"], r["metric"], r["window_s"], r["session_id"], r["grid"], r["total"], r["complete"],
                            e["arr"] if MU("store_arrival_hash") else None)
            h = hashlib.sha256((ln + chr(10)).encode()).hexdigest()
            hashes.append(h)
            lines.append(ln[:-1] + ',"content_sha256":"' + h + '"}')
    dump = hashlib.sha256("".join(l + "\n" for l in lines).encode()).hexdigest()
    retained = {kk: retained[kk] for kk in sorted(retained)}
    view = None
    q = inp.get("query")
    if q:
        ents = sorted(ring.get((q["series_id"], q["metric"], q["window_s"]), []), key=lambda e: e["rec"]["session_id"])
        pick = []
        for e in ents:
            sid = e["rec"]["session_id"]
            before = sid <= q["as_of"] if MU("store_view_current") else sid < q["as_of"]
            if e["rec"]["complete"] and before:
                pick.append(sid)
        view = pick[-k:]
    return out(value={"retained": retained, "view": view, "dump_sha256": dump, "n_lines": len(lines),
                      "content_sha256_digest": hashlib.sha256(chr(10).join(hashes).encode()).hexdigest()})


DISPATCH = {"M2-1": ev_f1, "M2-2": ev_f2, "M2-3": ev_f2d, "M2-4": ev_f4, "M2-5": ev_f17, "M2-6": ev_f7,
            "M2-7": ev_f10, "M2-8": ev_f20, "M2-9": ev_f18, "M2-10": ev_f19, "M2-11": ev_f12, "M2-12": ev_store}


def evaluate(row, mut=None):
    global _MUT
    _MUT = mut
    try:
        return DISPATCH[row["output_id"]](row["inputs"], row["params"])
    finally:
        _MUT = None
