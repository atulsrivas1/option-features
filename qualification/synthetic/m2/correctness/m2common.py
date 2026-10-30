"""Shared helpers and oracle A for the M2 synthetic fixture generators (stdlib only).

Oracle A computes every expected value from the written rules (matrix, I/O contract).
It is NOT used by the self-check, which has its own implementation (m2_ref.py).
"""
import bisect
import datetime
import hashlib
import json
import os
import random
from fractions import Fraction as Fr

NS = 10 ** 9
LABEL = ("mock-data qualification only: passed on independently authored synthetic "
         "fixtures and synthetic workloads, Windows x64, CPython 3.12")
T0 = 1790000000000000000
ALLOWED = (60, 300, 900, 1800, 3600)
PRINT_FIELDS = ["contract_id", "time_rel_ns", "price", "size", "multiplier",
                "condition_excluded", "seq", "side(optional)"]
THR_TICKS = 10 ** 9          # 100,000 USD in ticks


def fmt(x):
    x = Fr(x)
    return int(x) if x.denominator == 1 else "%d/%d" % (x.numerator, x.denominator)


def tick(price):
    v = Fr(price) * 10000
    assert v.denominator == 1, price
    return int(v)


def usd(x):
    return int(Fr(x) * 10000)


def S(x):
    return int(Fr(x) * NS)


def weekdays(n, start=datetime.date(2026, 1, 5)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def mkcal(prior_minutes, cur_minutes):
    ids = weekdays(len(prior_minutes) + 1)
    cal = [{"session_id": ids[i], "minutes": m} for i, m in enumerate(list(prior_minutes) + [cur_minutes])]
    return cal, ids[:-1], ids[-1]


def expand(gs, minutes):
    g = [gs["base"]] * minutes
    for i, v in gs["over"]:
        g[i] = v
    return g


def hs(sid, minutes, base=0, over=(), complete=True, total=None, put=None, call=None):
    d = {"session_id": sid, "minutes": minutes, "complete": complete,
         "gs": {"base": base, "over": [[i, v] for i, v in sorted(over)]}}
    d["total"] = sum(expand(d["gs"], minutes)) if total is None else total
    if put is not None:
        d["put"] = put
        d["call"] = call
    return d


def exp_hash(sessions):
    h = hashlib.sha256()
    for s in sessions:
        h.update((s["session_id"] + ":" + ",".join(str(v) for v in expand(s["gs"], s["minutes"])) + "\n").encode())
    return h.hexdigest()


def hist(series, metric, sessions, lane="stock", window_s=None):
    return {"series_id": series, "metric": metric, "lane": lane, "window_s": window_s, "sessions": sessions,
            "expansion_sha256": exp_hash(sessions)}


def spread(k, value, drop, minutes, nsess=20):
    """plant k history points of `value` round-robin over sessions at grid index >= drop"""
    ov = [[] for _ in range(nsess)]
    for t in range(k):
        i = drop + t // nsess
        assert i < minutes
        ov[t % nsess].append((i, value))
    return ov


def K(right, strike, expiry, lane="stock"):
    return {"underlying": "SYN1", "right": right, "strike": strike, "expiry": expiry, "lane": lane}


EXP1, EXP2 = "2026-11-20", "2026-12-18"
CONTRACTS = {"C1": K("C", 1000000, EXP1), "P1": K("P", 1000000, EXP1),
             "C2": K("C", 1100000, EXP2), "P2": K("P", 1100000, EXP2)}


def pr(cid, dt_ns, price, size, mult=100, excl=0, seq=None, side=None):
    return [cid, dt_ns, price, size, mult, excl, seq, side]


def pp(cid, dt_ns, usd_prem, size=10, **kw):
    """print whose premium is exactly usd_prem USD (price = usd/(size*100))"""
    p = Fr(usd_prem) / (size * 100)
    assert (p * 10000).denominator == 1, (usd_prem, size)
    w = int(p)
    return pr(cid, dt_ns, "%d.%04d" % (w, int((p - w) * 10000)), size, **kw)


def mkprints(lst):
    out, n = [], 0
    for idx, p in sorted(enumerate(lst), key=lambda ip: (ip[1][1], ip[0])):
        p = list(p)
        p[6] = n if p[6] is None else p[6]
        n += 1
        if p[7] is None:
            p = p[:7]
        out.append(p)
    return out


def session(sid, elapsed_ns, minutes, complete=False, delay="live", total=None, put=None, call=None, src=None):
    d = {"session_id": sid, "open_ns": T0 - elapsed_ns, "close_ns": T0 - elapsed_ns + minutes * 60 * NS,
         "minutes": minutes, "complete": complete, "feed_delay_tag": delay}
    if total is not None:
        d["total"] = total
    if put is not None:
        d["put"] = put
        d["call"] = call
    if src:
        d["total_source"] = src
    return d


def mkin(prints=None, contracts=None, sess=None, cal=None, histo=None, series="SYN1", **kw):
    inp = {"t_ns": T0, "series_id": series}
    if sess is None:
        sess = session("2026-06-01", S(1800), 390)
    inp["session"] = sess
    if contracts is not None:
        inp["contracts"] = contracts
    elif prints is not None:
        inp["contracts"] = CONTRACTS
    if prints is not None:
        inp["prints"] = mkprints(prints) if not kw.pop("raw", False) else prints
    if cal is not None:
        inp["calendar"] = cal
    if histo is not None:
        inp["history"] = histo
    inp.update(kw)
    return inp


# ---------------------------------------------------------------- results
def cov(n, ns, cd, un=0):
    return {"eligible_count": n, "nonstandard_count": ns, "excluded_condition_count": cd, "unavailable_points": un}


def res(status="available", reason=None, code=None, value=None, fired=None, label=None, cv=None, **extra):
    d = {"status": status, "reason": reason, "code": code, "value": value, "fired": fired,
         "label": label, "coverage": cv}
    d.update(extra)
    return d


def invalid(code):
    return res("invalid_input", code=code), "invalid_input %s (gate 1)" % code


def unavail(reason, why, cv=None, **extra):
    return res("unavailable", reason, cv=cv, **extra), why


# ---------------------------------------------------------------- validation
def validate(out, inp, prm):
    ps = inp.get("prints") or []
    for a, b in zip(ps, ps[1:]):
        if (a[1], a[6]) > (b[1], b[6]):
            return "unordered_prints"
    for p in ps:
        if p[3] < 0 or Fr(p[2]) < 0:
            return "negative_size_or_price"
    for p in ps:
        if p[4] <= 0:
            return "bad_multiplier"
    h = inp.get("history")
    allh = []
    if h:
        allh = [h]
    for pt in (inp.get("parts") or {}).values():
        allh.append(pt["history"])
    for h in allh:
        ids = [s["session_id"] for s in h["sessions"]]
        if len(ids) != len(set(ids)):
            return "duplicate_session"
    for h in allh:
        for s in h["sessions"]:
            last = -1
            for i, v in s["gs"]["over"]:
                if i <= last or i >= s["minutes"] or i < 0:
                    return "non_monotone_grid"
                last = i
    cal = inp.get("calendar")
    if cal is not None and inp["session"]["session_id"] not in [c["session_id"] for c in cal]:
        return "session_not_in_calendar"
    if out in ("M2-4", "M2-6", "M2-7", "M2-9") or (out == "M2-2" and prm.get("form", "intraday") == "intraday") \
            or out == "M2-3":
        if prm.get("window_s", 300) not in ALLOWED:
            return "window_not_allowed"
    if out == "M2-5" and prm.get("window_s", 300) != 300:
        return "window_not_allowed"
    if out == "M2-9" and prm.get("at_least") is None and prm.get("at_most") is None:
        return "threshold_required"
    d = inp["session"]["feed_delay_tag"] == "delayed"
    if d and (out in ("M2-1", "M2-11", "M2-7", "M2-3") or (out == "M2-2" and prm.get("form", "intraday") == "intraday")):
        return "delayed_feed_tag"
    return None


# ---------------------------------------------------------------- windows
def classify(inp, prm, W_ns, cid_only=None, ignore_filter=False):
    T = inp["t_ns"]
    el, ns_, cd = [], 0, 0
    lane = prm.get("lane", "stock")
    filt = "all" if ignore_filter else prm.get("filter", "all")
    for p in inp["prints"]:
        cid, rel, price, size, mult, excl = p[0], p[1], p[2], p[3], p[4], p[5]
        side = p[7] if len(p) > 7 else None
        t = T + rel
        if t < T - W_ns or t > T:
            continue
        c = inp["contracts"][cid]
        if c["lane"] != lane:
            continue
        if cid_only is not None and cid != cid_only:
            continue
        if filt == "calls" and c["right"] != "C":
            continue
        if filt == "puts" and c["right"] != "P":
            continue
        if excl:
            cd += 1
            continue
        if mult != 100:
            ns_ += 1
            continue
        tk = tick(price)
        el.append({"cid": cid, "t": t, "prem": tk * size * mult, "size": size, "right": c["right"],
                   "strike": c["strike"], "expiry": c["expiry"], "side": side})
    return el, ns_, cd


def elapsed(inp):
    return inp["t_ns"] - inp["session"]["open_ns"]


# ---------------------------------------------------------------- history
def prior_view(inp, hist_, K_=20, win=None):
    if win is not None and hist_.get("window_s") != win:
        return None
    cal = inp["calendar"]
    cur = inp["session"]["session_id"]
    idx = [c["session_id"] for c in cal].index(cur)
    if idx < K_:
        return None
    if hist_.get("lane", "stock") != inp.get("params_lane", "stock"):
        return None
    recs = {r["session_id"]: r for r in hist_["sessions"]}
    out = []
    for c in cal[idx - K_:idx]:
        r = recs.get(c["session_id"])
        if r is None or not r["complete"]:
            return None
        out.append((c, r))
    return out


def rank(vals, x):
    s = sorted(vals)
    n = len(s)
    return n, Fr(bisect.bisect_right(s, x), n), Fr(n - bisect.bisect_left(s, x), n)


def median(vals):
    s = sorted(vals)
    n = len(s)
    if n % 2:
        return Fr(s[n // 2])
    return (Fr(s[n // 2 - 1]) + Fr(s[n // 2])) / 2


# ---------------------------------------------------------------- oracle A
def _p(prm, k, d):
    v = prm.get(k, d)
    return v


def o_f1(inp, prm):
    code = validate("M2-1", inp, prm)
    if code:
        return invalid(code)
    N = Fr(prm.get("N", 3))
    if elapsed(inp) < 900 * NS:
        return unavail("insufficient_window", "elapsed %d ns < 900 s: insufficient_window" % elapsed(inp))
    e60, _, _ = classify(inp, prm, 60 * NS)
    e900, ns_, cd = classify(inp, prm, 900 * NS)
    p60, p900 = sum(e["prem"] for e in e60), sum(e["prem"] for e in e900)
    cv = cov(len(e900), ns_, cd)
    label = prm.get("filter", "all")
    if p900 == 0:
        return unavail("zero_denominator", "P60=%d P900=0 ticks: zero_denominator" % p60, cv=cv, label=label)
    ratio = Fr(15) * p60 / p900
    fired = ratio >= N
    return res(value={"p60": p60, "p900": p900, "ratio": fmt(ratio)}, fired=fired, label=label, cv=cv), \
        "P60=%d P900=%d ticks; ratio=15*%d/%d=%s; N=%s; fired=%s" % (p60, p900, p60, p900, fmt(ratio), fmt(N), fired)


def o_f4(inp, prm):
    code = validate("M2-4", inp, prm)
    if code:
        return invalid(code)
    W = prm.get("window_s", 300)
    thr = prm.get("threshold_ticks", THR_TICKS)
    N = Fr(prm.get("N", 1))
    e, ns_, cd = classify(inp, prm, W * NS)
    big = [x for x in e if x["prem"] >= thr]
    lp = sum(x["prem"] for x in big)
    fired = len(big) >= N
    return res(value={"large_count": len(big), "large_premium": lp}, fired=fired,
               cv=cov(len(e), ns_, cd)), \
        "eligible=%d; prints with premium>=%d ticks: %d (premium sum %d); N=%s; fired=%s" % (
            len(e), thr, len(big), lp, fmt(N), fired)


def o_f17(inp, prm):
    code = validate("M2-5", inp, prm)
    if code:
        return invalid(code)
    X = prm.get("threshold_ticks", THR_TICKS)
    e, ns_, cd = classify(inp, prm, 300 * NS, cid_only=inp["series_id"])
    s = sum(x["prem"] for x in e)
    return res(value={"window_premium": s}, fired=s >= X, cv=cov(len(e), ns_, cd)), \
        "contract %s: sum of %d eligible premiums = %d ticks; X=%d; fired=%s" % (inp["series_id"], len(e), s, X, s >= X)


def o_f7(inp, prm):
    code = validate("M2-6", inp, prm)
    if code:
        return invalid(code)
    W = prm.get("window_s", 300)
    th = Fr(prm.get("share_threshold", "3/5"))
    e, ns_, cd = classify(inp, prm, W * NS)
    cv = cov(len(e), ns_, cd)
    tot = sum(x["prem"] for x in e)
    if tot == 0:
        return unavail("zero_denominator", "no eligible premium: zero_denominator", cv=cv)
    bs, be = {}, {}
    for x in e:
        bs[x["strike"]] = bs.get(x["strike"], 0) + x["prem"]
        be[x["expiry"]] = be.get(x["expiry"], 0) + x["prem"]
    ts = min(bs, key=lambda k: (-bs[k], k))
    te = min(be, key=lambda k: (-be[k], k))
    ss, es = Fr(bs[ts], tot), Fr(be[te], tot)
    fired = ss >= th or es >= th
    return res(value={"top_strike": ts, "strike_share": fmt(ss), "top_expiry": te, "expiry_share": fmt(es),
                      "total_premium": tot}, fired=fired, cv=cv), \
        "total=%d; strike %d=%d/%d=%s; expiry %s=%d/%d=%s; th=%s; fired=%s" % (
            tot, ts, bs[ts], tot, fmt(ss), te, be[te], tot, fmt(es), fmt(th), fired)


def _hist_gate(inp, prm, hist_, win=None):
    inp2 = dict(inp)
    inp2["params_lane"] = prm.get("lane", "stock")
    return prior_view(inp2, hist_, 20, win)


def f2_core(inp, prm, hist_, metric, x_fn, form):
    """returns (result, derivation) for one F2 part; x_fn() -> Fraction value on history scale"""
    W = prm.get("window_s", 300)
    X = Fr(prm.get("X", 5))
    view = _hist_gate(inp, prm, hist_, W if form == "intraday" else None)
    if view is None:
        return unavail("insufficient_history", "fewer than 20 complete prior sessions stored (or history window/lane differs): insufficient_history")
    sess = inp["session"]
    if form == "end_of_day" and not sess["complete"]:
        return unavail("session_not_complete", "end-of-day form, session not sealed complete")
    if form == "intraday" and elapsed(inp) < W * NS:
        return unavail("insufficient_window", "elapsed < W=%d s: insufficient_window" % W)
    div = Fr(W // 60) if (metric == "prints" and form == "intraday") else Fr(1)
    if form == "intraday":
        vals = []
        for c, r in view:
            vals += [Fr(v) / div for v in expand(r["gs"], r["minutes"])[W // 60:]]
        nd = "n=sum(minutes-%d)=%d" % (W // 60, len(vals))
    else:
        if metric == "prints":
            vals = [Fr(r["total"], c["minutes"]) for c, r in view]
        else:
            vals = [Fr(r["total"]) for c, r in view]
        nd = "n=20 totals"
    x, cv_ = x_fn()
    n, rl, us = rank(vals, x)
    fired = us <= X / 100
    v = {"x": fmt(x), "n": n, "rank_le": fmt(rl), "upper_share": fmt(us), "form": form, "metric": metric}
    lab = "delayed" if sess["feed_delay_tag"] == "delayed" else None
    return res(value=v, fired=fired, label=lab, cv=cv_), \
        "%s; x=%s; count(h>=x)=%s of %d -> upper_share=%s; count(h<=x) -> rank_le=%s; X/100=%s; fired=%s" % (
            nd, fmt(x), fmt(us * n), n, fmt(us), fmt(rl), fmt(X / 100), fired)


def _x_from_prints(inp, prm, metric):
    W = prm.get("window_s", 300)

    def fn():
        e, ns_, cd = classify(inp, prm, W * NS)
        if metric == "premium":
            x = Fr(sum(z["prem"] for z in e))
        elif metric == "contracts":
            x = Fr(sum(z["size"] for z in e))
        else:
            x = Fr(len(e), W // 60)
        return x, cov(len(e), ns_, cd)
    return fn


def o_f2(inp, prm):
    form = prm.get("form", "intraday")
    code = validate("M2-2", inp, prm)
    if code:
        return invalid(code)
    metric = prm["metric"]
    if form == "intraday":
        fn = _x_from_prints(inp, prm, metric)
    else:
        sess = inp["session"]
        if metric == "prints":
            fn = lambda: (Fr(sess["total"], sess["minutes"]), None)
        else:
            fn = lambda: (Fr(sess["total"]), None)
    return f2_core(inp, prm, inp["history"], metric, fn, form)


def o_f2d(inp, prm):
    code = validate("M2-3", inp, prm)
    if code:
        return invalid(code)
    parts, outs, notes = ["F2a", "F2b", "F2c"], [], []
    metrics = {"F2a": "premium", "F2b": "contracts", "F2c": "prints"}
    for pn in parts:
        pt = inp["parts"][pn]
        r, d = f2_core(inp, prm, pt["history"], metrics[pn], (lambda pt=pt: (Fr(pt["x"]), None)), "intraday")
        outs.append(r)
        notes.append("%s: %s" % (pn, d))
    shown = []
    for r in outs:
        if r["status"] == "available":
            shown.append({"status": "available", "reason": None,
                          "percentile": fmt(1 - Fr(r["value"]["upper_share"]))})
        else:
            shown.append({"status": "unavailable", "reason": r["reason"], "percentile": None})
    bad = [r for r in outs if r["status"] != "available"]
    if bad:
        return res("unavailable", bad[0]["reason"], parts_shown=shown), " | ".join(notes) + " => first unavailable part reason"
    pc = [1 - Fr(r["value"]["upper_share"]) for r in outs]
    avg = sum(pc) / 3
    return res(value={"parts": [fmt(p) for p in pc], "average": fmt(avg), "direction": "higher_is_more_unusual"},
               parts_shown=shown), " | ".join(notes) + " => percentiles %s average=%s" % (
        ",".join(str(fmt(p)) for p in pc), fmt(avg))


def _ratio_block(x, vals, N, name_default):
    med = median(vals)
    mean = Fr(sum(Fr(v) for v in vals), len(vals))
    per = {}
    for nm, st in (("median", med), ("mean", mean)):
        if st == 0:
            per[nm] = {"status": "unavailable", "reason": "zero_denominator", "ratio": None, "fired": None}
        else:
            r = x / st
            per[nm] = {"status": "available", "reason": None, "ratio": fmt(r), "fired": r >= N}
    return med, mean, per


def _finish_ratio(x, med, mean, per, default, extra_label=None, **ex):
    d = per[default]
    ps = {k: {"status": v["status"], "reason": v["reason"], "ratio": v["ratio"]} for k, v in per.items()}
    val = {"x": fmt(x), "median": fmt(med), "mean": fmt(mean), "per_statistic": ps, "consumer_default": default}
    if d["status"] != "available":
        return res("unavailable", d["reason"], label=default, per_statistic=ps, **ex)
    return res(value=val, fired=d["fired"], label=default, **ex)


def o_f10(inp, prm):
    code = validate("M2-7", inp, prm)
    if code:
        return invalid(code)
    W = prm.get("window_s", 300)
    N = Fr(prm.get("N", 2))
    view = _hist_gate(inp, prm, inp["history"], W)
    if view is None:
        return unavail("insufficient_history", "fewer than 20 complete prior sessions: insufficient_history",
                       label="median", per_statistic=_per_na("insufficient_history"))
    if elapsed(inp) < W * NS:
        return unavail("insufficient_window", "elapsed < W: insufficient_window", label="median",
                       per_statistic=_per_na("insufficient_window"))
    vals = []
    for c, r in view:
        vals += expand(r["gs"], r["minutes"])[W // 60:]
    e, ns_, cd = classify(inp, prm, W * NS)
    x = Fr(sum(z["size"] for z in e))
    med, mean, per = _ratio_block(x, vals, N, "median")
    r = _finish_ratio(x, med, mean, per, "median", cv=cov(len(e), ns_, cd))
    r["coverage"] = cov(len(e), ns_, cd)
    return r, "n=%d; x=%s; median=%s mean=%s; median_ratio=%s mean_ratio=%s; N=%s; fired(median)=%s" % (
        len(vals), fmt(x), fmt(med), fmt(mean), per["median"]["ratio"], per["mean"]["ratio"], fmt(N),
        per["median"]["fired"])


def _per_na(reason):
    return {k: {"status": "unavailable", "reason": reason, "ratio": None} for k in ("median", "mean")}


def o_f20(inp, prm):
    code = validate("M2-8", inp, prm)
    if code:
        return invalid(code)
    N = Fr(prm.get("N", 2))
    sess = inp["session"]
    view = _hist_gate(inp, prm, inp["history"])
    if view is None:
        return unavail("insufficient_history", "fewer than 20 complete prior sessions: insufficient_history",
                       label="mean", per_statistic=_per_na("insufficient_history"))
    if not sess["complete"]:
        return unavail("session_not_complete", "session not sealed complete", label="mean",
                       per_statistic=_per_na("session_not_complete"))
    vals = [r["total"] for c, r in view]
    x = Fr(sess["total"])
    med, mean, per = _ratio_block(x, vals, N, "mean")
    ex = {}
    if sess.get("total_source") == "supplied_eod":
        ex["cv"] = {"degraded": True}
    r = _finish_ratio(x, med, mean, per, "mean", **ex)
    return r, "20 totals sorted; median=(10th+11th)/2=%s mean=%s; x=%s; median_ratio=%s mean_ratio=%s; N=%s; fired(mean)=%s" % (
        fmt(med), fmt(mean), fmt(x), per["median"]["ratio"], per["mean"]["ratio"], fmt(N), per["mean"]["fired"])


def o_f18(inp, prm):
    code = validate("M2-9", inp, prm)
    if code:
        return invalid(code)
    W = prm.get("window_s", 300)
    al, am = prm.get("at_least"), prm.get("at_most")
    e, ns_, cd = classify(inp, prm, W * NS, ignore_filter=True)
    cv = cov(len(e), ns_, cd)
    pv = sum(z["size"] for z in e if z["right"] == "P")
    cvv = sum(z["size"] for z in e if z["right"] == "C")
    tot = pv + cvv
    if tot == 0:
        return unavail("zero_denominator", "no eligible volume: zero_denominator", cv=cv, label="put")
    sh = Fr(pv, tot)
    ratio = None if cvv == 0 else Fr(pv, cvv)
    fired = False
    if al is not None and sh >= Fr(al):
        fired = True
    if am is not None and sh <= Fr(am):
        fired = True
    ex = {}
    if ratio is None:
        ex["ratio_reason"] = "zero_denominator"
    return res(value={"put_volume": pv, "call_volume": cvv, "put_share": fmt(sh),
                      "put_call_ratio": None if ratio is None else fmt(ratio)}, fired=fired, label="put", cv=cv, **ex), \
        "put=%d call=%d total=%d share=%s ratio=%s at_least=%s at_most=%s fired=%s" % (
            pv, cvv, tot, fmt(sh), "n/a" if ratio is None else fmt(ratio), al, am, fired)


def o_f19(inp, prm):
    code = validate("M2-10", inp, prm)
    if code:
        return invalid(code)
    X = Fr(prm.get("X", 5))
    sess = inp["session"]
    cal = inp["calendar"]
    idx = [c["session_id"] for c in cal].index(sess["session_id"])
    recs = {r["session_id"]: r for r in inp["history"]["sessions"]}
    ratios = []
    if idx >= 20:
        for c in cal[idx - 20:idx]:
            r = recs.get(c["session_id"])
            if r is not None and r["complete"] and r["call"] > 0:
                ratios.append(Fr(r["put"], r["call"]))
    if len(ratios) < 20:
        return unavail("insufficient_history", "%d usable prior ratios < 20: insufficient_history" % len(ratios))
    if not sess["complete"]:
        return unavail("session_not_complete", "session not sealed complete")
    if sess["call"] == 0:
        return unavail("zero_denominator", "call volume 0 today: zero_denominator")
    x = Fr(sess["put"], sess["call"])
    n, rl, us = rank(ratios, x)
    fired = us <= X / 100
    return res(value={"ratio": fmt(x), "n": n, "rank_le": fmt(rl), "upper_share": fmt(us)}, fired=fired), \
        "x=%d/%d=%s; 20 prior put/call ratios; count(h>=x)=%s; upper_share=%s; rank_le=%s; fired=%s" % (
            sess["put"], sess["call"], fmt(x), fmt(us * n), fmt(us), fmt(rl), fired)


def o_f12(inp, prm):
    code = validate("M2-11", inp, prm)
    if code:
        return invalid(code)
    N = Fr(prm.get("N", 3))
    gap = prm.get("quiet_gap", 1)
    nep = prm.get("n_episodes", 1)
    el = elapsed(inp)
    if el < 900 * NS:
        return unavail("insufficient_window", "elapsed < 900 s: insufficient_window")
    open_ns = inp["session"]["open_ns"]
    kmax = el // (60 * NS)
    pts = inp["points"]
    eps, in_ep, qrun, un = 0, False, 0, 0
    first = last = None
    peak, peak_k = None, None
    for k in range(0, kmax + 1):
        pt = pts[k] if k < len(pts) else None
        fired = False
        if pt is None or pt[1] == 0:
            un += 1
        else:
            r = Fr(15) * pt[0] / pt[1]
            if peak is None or r > peak:
                peak, peak_k = r, k
            if r >= N:
                fired = True
        if fired:
            if not in_ep:
                eps += 1
                in_ep = True
                if first is None:
                    first = k
                last = k
            qrun = 0
        elif in_ep:
            qrun += 1
            if qrun >= gap:
                in_ep = False
    v = {"episode_count": eps, "first_ns": None if first is None else open_ns + first * 60 * NS,
         "last_ns": None if last is None else open_ns + last * 60 * NS,
         "peak_ratio": None if peak is None else fmt(peak),
         "peak_ns": None if peak_k is None else open_ns + peak_k * 60 * NS, "unavailable_points": un, "quiet_gap": gap}
    return res(value=v, fired=eps >= nep, cv=cov(0, 0, 0, un)), \
        "grid points 0..%d; unavailable=%d; episodes=%d (rising edges with quiet_gap=%d); first idx=%s last idx=%s peak=%s at idx %s" % (
            kmax, un, eps, gap, first, last, None if peak is None else fmt(peak), peak_k)


ORACLE = {"M2-1": o_f1, "M2-2": o_f2, "M2-3": o_f2d, "M2-4": o_f4, "M2-5": o_f17, "M2-6": o_f7,
          "M2-7": o_f10, "M2-8": o_f20, "M2-9": o_f18, "M2-10": o_f19, "M2-11": o_f12}


# ---------------------------------------------------------------- store
def line_of(series, metric, win, sid, grid, total, complete):
    d = [("series_id", series), ("metric", metric), ("session_id", sid), ("window_s", win), ("grid", grid), ("total", total),
         ("complete", complete)]
    return json.dumps(dict(d), separators=(",", ":"))


def o_store(inp, prm):
    k = inp.get("k", 20)
    cal = [c["session_id"] for c in inp["calendar"]]
    ring = {}
    for step in inp["ops"]:
        if step[0] == "append":
            r = step[1]
            key = (r["series_id"], r["metric"], r["window_s"])
            if r["session_id"] not in cal:
                return res("invalid_input", code="session_not_in_calendar"), "record session not in calendar"
            lst = ring.setdefault(key, [])
            if lst:
                last_i, cur_i = cal.index(lst[-1]["session_id"]), cal.index(r["session_id"])
                if cur_i < last_i:
                    return res("invalid_input", code="out_of_order_append"), "append earlier than the last session: out_of_order_append"
                if cur_i == last_i:
                    return res("invalid_input", code="duplicate_session"), "append equal to the last session: duplicate_session"
            g = r["grid"]
            gi = r.get("grid_idx", list(range(len(g))))
            if any(b <= a_ for a_, b in zip(gi, gi[1:])):
                return res("invalid_input", code="non_monotone_grid"), "non monotone grid"
            lst.append(dict(r))
            if len(lst) > k:
                lst.pop(0)
        elif step[0] == "seal":
            for x in ring.get((step[1], step[2], step[3]), []):
                if x["session_id"] == step[4]:
                    x["complete"] = True
    lines = []
    for key in sorted(ring):
        for x in sorted(ring[key], key=lambda z: z["session_id"]):
            ln = line_of(key[0], key[1], key[2], x["session_id"], x["grid"], x["total"], x["complete"])
            h = hashlib.sha256((ln + chr(10)).encode()).hexdigest()
            lines.append((ln[:-1] + ',"content_sha256":"' + h + '"}', h))
    dump = hashlib.sha256(("".join(l + "\n" for l, _ in lines)).encode()).hexdigest()
    ret = {"%s|%s|%s" % key: [x["session_id"] for x in sorted(v, key=lambda z: z["session_id"])] for key, v in sorted(ring.items())}
    q = inp.get("query")
    view = None
    if q:
        lst = ring.get((q["series_id"], q["metric"], q["window_s"]), [])
        view = [x["session_id"] for x in sorted(lst, key=lambda z: z["session_id"])
                if x["complete"] and x["session_id"] < q["as_of"]][-k:]
    return res(value={"retained": ret, "view": view, "dump_sha256": dump, "n_lines": len(lines),
                      "content_sha256_digest": hashlib.sha256(chr(10).join(h for _, h in lines).encode()).hexdigest()}), \
        "ring keeps last %d sessions per (series,metric); view = complete sessions strictly before as_of; dump hash over sorted canonical lines" % k


# ---------------------------------------------------------------- rows
class Rows:
    def __init__(self, family, prefix):
        self.family, self.prefix, self.rows = family, prefix, []

    def add(self, output_id, design_ref, ruling, inputs, params, tags=(), pending=None, expected=None,
            family=None, series=None, sub=None):
        params = dict(params)
        for k_ in ("N", "X"):
            if isinstance(params.get(k_), str) and Fr(params[k_]).denominator == 1:
                params[k_] = int(Fr(params[k_]))
        tags = list(tags)
        if output_id in ("M2-7", "M2-8") and "default_omitted" not in tags and "consumer_default" not in params:
            params["consumer_default"] = "median" if output_id == "M2-7" else "mean"
        if output_id == "M2-12":
            exp, der = o_store(inputs, params)
        elif expected is not None:
            exp, der = expected
        else:
            exp, der = ORACLE[output_id](inputs, params)
        rid = "%s-%03d" % (self.prefix, len(self.rows) + 1)
        row = {"id": rid, "family": family or self.family, "output_id": output_id, "design_ref": design_ref,
               "ruling": ruling, "tags": [], "inputs": inputs, "params": params,
               "expected": exp, "derivation": der}
        R_ = "RULED PO-M2-AMB-%s, pending design ratification where design is silent"
        interim = [q_ for q_ in ruling.split(",") if q_ in ("Q1", "Q3")]
        if not pending and interim:
            pending = "RULED " + "/".join(interim) + " (interim, pending design ratification)"
        if output_id in ("M2-7", "M2-8"):
            pending = R_ % "1"
        elif output_id == "M2-11":
            pending = R_ % "5,7"
        if pending:
            row["pending"] = pending
        row["tags"] = sorted(set(tags) | set("amb-%d" % n for n in auto_amb(row, set(tags))))
        self.rows.append(row)
        return row


def auto_amb(row, t):
    o, e, inp, prm = row["output_id"], row["expected"], row["inputs"], row["params"]
    a = []
    if o in ("M2-7", "M2-8"):
        a.append(1)
    if any(len(p) > 7 for p in inp.get("prints", [])) or "side_twin" in t:
        a.append(2)
    if o in ("M2-1", "M2-4", "M2-5", "M2-6"):
        a.append(3)
    if t & {"drop_pre_open", "history_n", "window_len", "session_open", "grid_length"}:
        a.append(4)
    if o == "M2-11" and (((e.get("value") or {}).get("episode_count") or 0) >= 1 or "unavail_first15" in t):
        a.append(5)
    if e.get("code") == "threshold_required":
        a.append(6)
    if o == "M2-11" and e.get("reason") == "insufficient_window":
        a.append(7)
    if t & {"window_mismatch", "store_window"}:
        a.append(8)
    if e.get("label") is not None:
        a.append(9)
    if prm.get("metric") == "prints" or "f2c_rate" in t:
        a.append(10)
    if o == "M2-3":
        a.append(11)
    if o == "M2-10":
        a.append(12)
    if e.get("code") == "out_of_order_append" or (row["family"] == "store" and t & {"content_hash", "retention_k", "incomplete", "seal", "store_sort", "store_arrival_hash"}):
        a.append(13)
    if t & {"both_excl", "nonstd_counted", "cond_excl_counted"}:
        a.append(14)
    if "amb15" in t or ("gate_order" in t and row["family"] == "structural"):
        a.append(15)
    if t & {"bad_multiplier", "non_monotone_grid", "duplicate_session"}:
        a.append(16)
    if t & {"gate_history", "history_count", "missing_calendar_session", "incomplete_session", "nothing_stored"}:
        a.append(17)
    if t & {"window_not_allowed", "no_window_param"}:
        a.append(18)
    if "default_omitted" in t:
        a.append(19)
    return a


def dumps(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")


def _cj(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def _hist_compact(h, calids):
    h = dict(h)
    pay, idx, sess = [], {}, []
    for s in h["sessions"]:
        try:
            tot = None if s["total"] == sum(expand(s["gs"], s["minutes"])) else s["total"]
        except IndexError:
            tot = s["total"]
        p = [s["minutes"], 1 if s["complete"] else 0, s["gs"]["base"], s["gs"]["over"], tot, s.get("put"), s.get("call")]
        k = _cj(p)
        if k not in idx:
            idx[k] = len(pay)
            pay.append(p)
        sid = s["session_id"]
        sess.append([calids.index(sid) if sid in calids else sid, idx[k]])
    h["payloads"], h["sessions"] = pay, sess
    return h


def compactify(rows):
    """intern calendars and contracts; compact history sessions and store ops (all reversible by m2_load.expand_row)"""
    cals, cons, out = {}, {}, []
    for r in rows:
        r = json.loads(_cj(r))
        i = r["inputs"]
        if "calendar" in i:
            k = "cal-" + hashlib.sha256(_cj(i["calendar"]).encode()).hexdigest()[:8]
            cals[k] = [[c["session_id"], c["minutes"]] for c in i.pop("calendar")]
            i["calendar_ref"] = k
        if "contracts" in i:
            k = "con-" + hashlib.sha256(_cj(i["contracts"]).encode()).hexdigest()[:8]
            cons[k] = i.pop("contracts")
            i["contracts_ref"] = k
        calids = cals[i["calendar_ref"]] if "calendar_ref" in i else []
        calids = [x[0] for x in calids]
        if "history" in i:
            i["history"] = _hist_compact(i["history"], calids)
        for p in (i.get("parts") or {}).values():
            p["history"] = _hist_compact(p["history"], calids)
        if "ops" in i:
            i["ops_sha256"] = hashlib.sha256(_cj(i["ops"]).encode()).hexdigest()
            comp = []
            for op in i["ops"]:
                if op[0] == "append":
                    x = op[1]
                    comp.append(["a", x["series_id"], x["metric"], x["window_s"], x["session_id"], x["grid"],
                                 None if x["total"] == sum(x["grid"]) else x["total"], 1 if x["complete"] else 0,
                                 x.get("grid_idx")])
                else:
                    comp.append(["s"] + list(op[1:]))
            i["ops"] = comp
        out.append(r)
    return cals, cons, out


def write_dataset(outdir, name, family, seed, rows):
    os.makedirs(outdir, exist_ok=True)
    cals, cons, rows = compactify(rows)
    head = {"provenance": "SYNTHETIC", "label": LABEL, "family": family, "seed": seed,
            "t_ns_anchor": T0, "print_fields": PRINT_FIELDS, "row_count": len(rows),
            "calendars": cals, "contracts": cons, "format": "compact v1: see m2_load.py"}
    lines = [dumps(head)] + [dumps(r) for r in rows]
    path = os.path.join(outdir, "m2_cases_%s.json" % name)
    with open(path, "wb") as f:
        f.write("".join(lines).encode("ascii"))
    return path


def noise(rng, n, W_max_ns=3601 * NS, cids=("C1", "P1", "C2", "P2")):
    """prints older than any allowed window: must never matter"""
    out = []
    for i in range(n):
        out.append(pr(rng.choice(list(cids)), -(W_max_ns + rng.randrange(1, 10 ** 9)),
                      "%d.0000" % rng.randrange(1, 90), rng.randrange(1, 50)))
    return out


def main_for(name, family, build, seed=20261029):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--seed", type=int, default=seed)
    a = ap.parse_args()
    rows = build(random.Random(a.seed))
    p = write_dataset(a.out, name, family, a.seed, rows)
    print(os.path.basename(p), len(rows))
