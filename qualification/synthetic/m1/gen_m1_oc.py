#!/usr/bin/env python3
"""M1 OC5/OC6 fixture generator.  PROVENANCE: SYNTHETIC.

TEST ORACLE, NOT LIBRARY CODE.  Written from the design text and the PO rulings
only (OC 2.2, 2.3, 2.7, 12; PO_R28_DESIGN_RULINGS 1 and 4; OC5_OC6_FIXTURE_SPEC).
stdlib only, seeded, deterministic, LF output.  Usage:
    python gen_m1_oc.py --out <relative dir>      (writes m1_oc_cases.json, then self-checks)
"""
import argparse
import json
import os
import random
import sys
from fractions import Fraction as F

SEED = 20261029
PROV = "SYNTHETIC"
QUAL = ("mock-data qualification only: passed on independently authored synthetic fixtures and synthetic "
        "workloads, Windows x64, CPython 3.12")
S = 10 ** 9
SESSION_OPEN = -18000 * S
STALE = 10 * S
WINDOW = 300 * S
CMIN = 5
CLOSED = ["excluded_condition", "invalid_quote", "crossed_market", "locked_market", "stale_quote", "low_quote_coverage",
          "no_quote", "zero_displayed_size", "missing_size", "future_known", "no_window_spread",
          "not_consolidated", "american_itm", "style_unknown", "no_atm_strike", "no_bracketing_expiry"]


# ---------------------------------------------------------------- formatting
def dec(fr, places=4):
    neg = fr < 0
    a = abs(fr) * 10 ** places
    n = (2 * a.numerator + a.denominator) // (2 * a.denominator)
    s = str(n).rjust(places + 1, "0")
    out = s[:-places] + "." + s[-places:]
    return ("-" if neg and n else "") + out


def fx(fr):
    fr = F(fr)
    return str(fr.numerator) if fr.denominator == 1 else "%d/%d" % (fr.numerator, fr.denominator)


def ts(ns):
    return ("%ds" % (ns // S)) if ns % S == 0 else ("%dns" % ns)


# ---------------------------------------------------------------- oracle
class Ambig(Exception):
    pass


def qclass(q):
    b, a = q["bid"], q["ask"]
    if b is None or a is None:
        return "invalid_quote"
    b, a = F(b), F(a)
    if b <= 0:
        return "invalid_quote"
    if a < b:
        return "crossed_market"
    if a == b:
        return "locked_market"
    return "ok"


def structural(inp):
    for q in inp["quotes"]:
        for k in ("bid", "ask"):
            if q[k] is not None and not isinstance(q[k], str):
                return "malformed_type"
    for s in inp.get("sizes", []):
        for k in ("bid_size", "ask_size"):
            v = s[k]
            if v is None:
                continue
            if not isinstance(v, int) or isinstance(v, bool):
                return "non_integer_size"
            if v < 0:
                return "negative_size"
    qs = inp["quotes"]
    for a, b in zip(qs, qs[1:]):
        if b["event_ns"] < a["event_ns"]:
            return "non_monotone_event_time"
    return None


def okey(q):
    return (q["event_ns"], q.get("seq", 0), q["known_at_ns"])


def causal_sorted(inp, mut):
    T = inp["T_ns"]
    c = [q for q in inp["quotes"] if q["event_ns"] <= T and ("M7" in mut or q["known_at_ns"] <= T)]
    c.sort(key=okey)
    for a, b in zip(c, c[1:]):
        if okey(a) == okey(b):
            raise Ambig()
    return c


def res(status, reason=None, value=None, label=None, aux=None, gates=None, trace="", code=None, rg=True):
    return dict(status=status, reason=reason, value=value, label=label, aux=aux or {},
                gates=gates or [], trace=trace, code=code, reason_gating=rg)


def stale_fn(T, req, mut):
    lim = req["stale_limit_ns"]
    if "M6b" in mut:
        lim += 1
    if "M6c" in mut:
        lim -= 1

    def stale(q):
        if "M6a" in mut:
            return False
        age = T - q["event_ns"]
        return age >= lim if "M19" in mut else age > lim
    return stale


def count_in_window(c, T, req, mut):
    win = req["window_ns"]
    if "M12a" in mut:
        win = 240 * S
    if "M12b" in mut:
        win = 360 * S
    lo = T - win
    if "X7" not in mut:
        lo = max(lo, req["session_open_ns"])
    reg = [q for q in c if ("M16" in mut or q["condition"] == "regular")]
    if "X6" in mut:
        reg = [q for q in reg if qclass(q) == "ok"]
    return [q for q in reg if (lo < q["event_ns"] if "M18" in mut else lo <= q["event_ns"]) and q["event_ns"] <= T]


GATE_ORDER = ["no_quote", "excluded_condition", "not_consolidated", "invalid_quote", "crossed_market",
              "locked_market", "stale_quote", "low_quote_coverage", "missing_size", "zero_displayed_size"]


def order_gates(found, mut):
    order = list(GATE_ORDER)
    if "X9" in mut:  # stale before validity
        order.remove("stale_quote")
        order.insert(order.index("invalid_quote"), "stale_quote")
    if "X10" in mut:  # coverage before stale
        order.remove("low_quote_coverage")
        order.insert(order.index("stale_quote"), "low_quote_coverage")
    if "X13" in mut:  # size reasons before validity
        for g in ("zero_displayed_size", "missing_size"):
            order.remove(g)
            order.insert(order.index("invalid_quote"), g)
    if "X14" in mut:  # not_consolidated after validity
        order.remove("not_consolidated")
        order.insert(order.index("stale_quote"), "not_consolidated")
    return [g for g in order if g in found]


def eval_oc5(inp, req, mut=frozenset()):
    sc = structural(inp)
    if sc:
        return res("structural_error", code=sc)
    T = inp["T_ns"]
    try:
        c = causal_sorted(inp, mut)
    except Ambig:
        return res("structural_error", code="ambiguous_ordering")
    stale = stale_fn(T, req, mut)
    if not c:
        return res("unavailable", "no_quote", gates=["no_quote"], trace="no causal quote at T")
    L = c[-1]
    if "M8" in mut:
        ok = [q for q in c if q["condition"] == "regular" and not stale(q)]
        if ok:
            L = ok[-1]
    found = set()
    if L["condition"] != "regular":
        found.add("excluded_condition")
    if inp.get("feed_kind", "consolidated") == "single_venue":
        found.add("not_consolidated")
    if "X12" in mut and inp.get("contract_standard", True) is False:
        found.add("invalid_quote")
    cl = qclass(L)
    if cl in ("invalid_quote", "crossed_market"):
        found.add(cl)
    if stale(L):
        found.add("stale_quote")
    if "M20" in mut and len(count_in_window(c, T, req, mut)) < req["coverage_min"]:
        found.add("low_quote_coverage")
    sz = next((s for s in inp.get("sizes", []) if s["rev"] == L["rev"]), None)
    bs = as_ = None
    if sz is None or sz["bid_size"] is None or sz["ask_size"] is None:
        found.add("missing_size")
    else:
        bs, as_ = sz["bid_size"], sz["ask_size"]
        if bs == 0 and as_ == 0 and "M9" not in mut:
            found.add("zero_displayed_size")
    gates = order_gates(found, mut)
    if gates:
        g = gates[0]
        return res("unavailable", g, gates=gates,
                   trace="gate %s (all failing: %s; latest quote ev=%s age=%s)" % (
                       g, ",".join(gates), ts(L["event_ns"]), ts(T - L["event_ns"])))
    thr = F(req["imbalance_threshold"])
    tot = bs + as_
    if "M9" in mut and tot == 0:
        imb = F(0)
    elif "M2" in mut:
        imb = F(bs, tot)
    elif "M4a" in mut or "M4b" in mut:
        d = bs if "M4a" in mut else as_
        if d == 0:
            return res("unavailable", "zero_displayed_size", gates=["zero_displayed_size"])
        imb = F(bs - as_, d)
    else:
        imb = F(bs - as_, tot)
    if "M2" in mut:
        fb, fa = imb >= thr, (1 - imb) >= thr
    elif "M1" in mut:
        fb, fa = imb > thr, imb < -thr
    elif "M5" in mut:
        fb, fa = abs(imb) >= thr, False
    else:
        fb, fa = imb >= thr, imb <= -thr
    label = "bid" if fb else ("ask" if fa else None)
    if "M3" in mut and label:
        label = "ask" if label == "bid" else "bid"
    tr = "imbalance=(%d-%d)/(%d+%d)=%s=%s; threshold %s inclusive -> %s" % (
        bs, as_, bs, as_, fx(imb), dec(imb), dec(thr, 4), label or "not fired")
    return res("fired" if label else "not_fired", None, imb, label, gates=[], trace=tr)


def eval_oc6(inp, req, mut=frozenset()):
    sc = structural(inp)
    if sc:
        return res("structural_error", code=sc)
    T = inp["T_ns"]
    try:
        c = causal_sorted(inp, mut)
    except Ambig:
        return res("structural_error", code="ambiguous_ordering")
    stale = stale_fn(T, req, mut)
    if not c:
        return res("unavailable", "no_quote", gates=["no_quote"], trace="no causal quote at T")
    L = c[-1]
    win = req["window_ns"]
    if "M12a" in mut:
        win = 240 * S
    if "M12b" in mut:
        win = 360 * S
    cmin = req["coverage_min"]
    if "M13a" in mut:
        cmin = 4
    if "M13b" in mut:
        cmin = 6
    opn = req["session_open_ns"]
    ws_raw = T - win
    ws = ws_raw if "X2" in mut else max(ws_raw, opn)
    found = set()
    if L["condition"] != "regular":
        found.add("excluded_condition")
    if "X11" in mut and inp.get("feed_kind", "consolidated") == "single_venue":
        found.add("not_consolidated")
    if "X12" in mut and inp.get("contract_standard", True) is False:
        found.add("invalid_quote")
    cl = qclass(L)
    if cl in ("invalid_quote", "crossed_market") or (cl == "locked_market" and "M15" not in mut):
        found.add(cl)
    if stale(L):
        found.add("stale_quote")
    cnt = len(count_in_window(c, T, req, mut))
    if cnt < cmin:
        found.add("low_quote_coverage")
    gates = order_gates(found, mut)
    if gates:
        g = gates[0]
        return res("unavailable", g, gates=gates,
                   trace="gate %s (all failing: %s; regular updates in window=%d; latest ev=%s)" % (
                       g, ",".join(gates), cnt, ts(L["event_ns"])))
    n = len(c)

    def start_of(u):
        return u["event_ns"] if "X8" in mut else u["known_at_ns"]
    segs = []
    for i, u in enumerate(c):
        if u["event_ns"] < opn and "X2" not in mut:
            continue
        st = start_of(u)
        nxt = start_of(c[i + 1]) if i + 1 < n else T
        start, end = max(st, ws), min(max(nxt, st), T)
        if st < ws and "X1" in mut:
            continue
        if end <= start:
            continue
        k = qclass(u)
        usable = u["condition"] == "regular" and (k == "ok" or ("X4" in mut and k in ("crossed_market", "locked_market")))
        if usable:
            a_, b_ = F(u["ask"]), F(u["bid"])
            segs.append((start, end, a_ - b_, a_ + b_, (float(u["ask"]) - float(u["bid"])) / ((float(u["ask"]) + float(u["bid"])) / 2) * 10000))
    price = "X5" in mut

    def val(sp, md):
        return sp if price else sp / (md / 2) * 10000
    if "M17" in mut:
        ups = [u for u in c if ws <= u["event_ns"] <= T and u["condition"] == "regular" and qclass(u) == "ok"]
        if not ups:
            return res("unavailable", "no_window_spread", gates=["no_window_spread"])
        avg = sum(val(F(u["ask"]) - F(u["bid"]), F(u["ask"]) + F(u["bid"])) for u in ups) / len(ups)
        wsum = len(ups)
    else:
        wsum = sum(e - s for s, e, _, _, _ in segs)
        if wsum == 0:
            return res("unavailable", "no_window_spread", gates=["no_window_spread"],
                       trace="count=%d but total valid weight is 0" % cnt)
        num = sum((e - s) * val(sp, md) for s, e, sp, md, _ in segs)
        avg = num / ((T - ws) if "X3" in mut else wsum)
    cur = F(L["ask"]) - F(L["bid"])
    mid = (F(L["ask"]) + F(L["bid"])) / 2
    curv = val(cur, mid * 2)
    nmax, wmin = F(req["narrower_max"]), F(req["wider_min"])
    if "M14" in mut:
        den = sum(e - s for s, e, _, _, _ in segs)
        favg = sum(float(e - s) * fs for s, e, _, _, fs in segs) / den
        fcur = (float(L["ask"]) - float(L["bid"])) / ((float(L["ask"]) + float(L["bid"])) / 2) * 10000
        ratio = fcur / favg
        label = "narrower" if ratio <= float(nmax) else ("wider" if ratio >= float(wmin) else None)
        return res("fired" if label else "not_fired", None, ratio, label)
    ratio = (avg / curv) if "M10" in mut else (curv / avg)
    if "M11" in mut:
        fn, fw = ratio < nmax, ratio > wmin
    else:
        fn, fw = ratio <= nmax, ratio >= wmin
    label = "narrower" if fn else ("wider" if fw else None)
    parts = " + ".join("%sbps*%s" % (fx(val(sp, md)), ts(e - s)) for s, e, sp, md, _ in segs)
    tr = ("window=[%s,%s] (open %s); time-weighted spread in bps of midpoint = %s over valid time %s; average=%s bps; "
          "current=%s bps; ratio=(%s)/(%s)=%s=%s; narrower<=%s wider>=%s -> %s; regular updates in window=%d") % (
        ts(ws), ts(T), ts(opn), parts, ts(wsum) if "M17" not in mut else "n/a", fx(avg), fx(curv),
        fx(curv), fx(avg), fx(ratio), dec(ratio, 4), dec(nmax, 4), dec(wmin, 4), label or "neither", cnt)
    aux = {"current_spread": fx(cur), "midpoint": fx(mid), "spread_bps": fx(cur / mid * 10000),
           "average_spread_bps": fx(avg)}
    return res("fired" if label else "not_fired", None, ratio, label, aux=aux, trace=tr)


EVAL = {"oc5": eval_oc5, "oc6": eval_oc6}


def expect(r):
    e = {"status": r["status"]}
    if r["status"] == "structural_error":
        e["code"] = r["code"]
        return e
    e["reason"] = r["reason"]
    if not r["reason_gating"]:
        e["reason_gating"] = False
    if r["value"] is not None:
        e["value"] = {"exact": fx(r["value"]), "decimal": dec(r["value"], 4), "precision": 4}
    e["label"] = r["label"]
    if r["aux"]:
        e["aux"] = r["aux"]
    e["model_label"] = None
    return e


# ---------------------------------------------------------------- builders
ROWS = []


def Q(rev, ev, bid, ask, known=None, cond="regular", seq=None):
    d = {"rev": rev, "event_ns": ev, "known_at_ns": ev if known is None else known,
         "bid": bid, "ask": ask, "condition": cond}
    if seq is not None:
        d["seq"] = seq
    return d


def sp_quote(rev, ev, spread, mid="10.0000", **kw):
    s, m = F(spread), F(mid)
    assert (s / 2 * 10000).denominator == 1, spread
    return Q(rev, ev, dec(m - s / 2), dec(m + s / 2), **kw)


class NS(int):
    pass


def stream6(items, mid="10.0000"):
    qs = []
    for i, it in enumerate(items, 1):
        ev, kind = (int(it[0]) if isinstance(it[0], NS) else it[0] * S), it[1]
        kw = dict(it[3]) if len(it) > 3 else {}
        if kind == "v":
            qs.append(sp_quote(i, ev, it[2], mid, **kw))
        elif kind == "x":
            qs.append(sp_quote(i, ev, it[2], mid, cond="excluded", **kw))
        elif kind == "crossed":
            qs.append(Q(i, ev, "10.0500", "9.9500", **kw))
        elif kind == "locked":
            qs.append(Q(i, ev, "10.0000", "10.0000", **kw))
        elif kind == "askNull":
            qs.append(Q(i, ev, "9.9500", None, **kw))
        elif kind == "bidNull":
            qs.append(Q(i, ev, None, "10.0500", **kw))
        elif kind == "bid0":
            qs.append(Q(i, ev, "0.0000", "0.1000", **kw))
        elif kind == "mid":
            qs.append(sp_quote(i, ev, it[2], it[4], **kw))
    return qs


def req5(thr="0.60", stale=STALE, opn=SESSION_OPEN):
    return {"session_open_ns": opn, "stale_limit_ns": stale, "imbalance_threshold": thr,
            "window_ns": WINDOW, "coverage_min": CMIN}


def req6(nmax="0.75", wmin="1.50", stale=STALE, opn=SESSION_OPEN):
    return {"session_open_ns": opn, "stale_limit_ns": stale, "narrower_max": nmax, "wider_min": wmin,
            "window_ns": WINDOW, "coverage_min": CMIN}


def auto_tags(op, r, extra):
    t = list(extra)
    st, rs = r["status"], r["reason"]
    if op == "oc5":
        if st in ("fired", "not_fired") or rs == "zero_displayed_size":
            t.append("pending:req10")
        if rs == "not_consolidated" or rs == "stale_quote":
            t.append("pending:req11")
    else:
        if st in ("fired", "not_fired") or rs in ("low_quote_coverage", "no_window_spread"):
            t.append("pending:req3")
        if rs == "stale_quote":
            t.append("pending:req11")
    if rs == "locked_market" or (op == "oc5" and st != "unavailable" and False):
        t.append("pending:req1")
    return sorted(set(t))


def add(id_, op, group, ref, case, quotes, sizes, req, tags=(), gating=True, feed="consolidated",
        style=None, alts=None, expected=None, T=0, note="", nonstd=False):
    inp = {"T_ns": T, "feed_kind": feed, "contract_style": style, "contract_standard": not nonstd,
           "quotes": quotes}
    if op == "oc5":
        inp["sizes"] = sizes
    r = EVAL[op](inp, req)
    row = {"id": id_, "group": group, "design_ref": ref, "case": case, "op": op, "inputs": inp, "request": req}
    if alts is not None:
        row["gating"] = False
        row["expected"] = None
        row["alternatives"] = alts(inp, req) if callable(alts) else alts
        row["tags"] = sorted(set(list(tags) + ["pending:ambiguity"]))
        row["derivation"] = note
    else:
        row["gating"] = gating
        row["expected"] = expected if expected is not None else expect(r)
        row["tags"] = auto_tags(op, r, tags)
        row["derivation"] = (note + " " if note else "") + r["trace"]
    ROWS.append(row)
    return row


def alt_by_flags(op, readings):
    def f(inp, req):
        out = []
        for name, flags, desc in readings:
            out.append({"name": name, "reading": desc, "expected": expect(EVAL[op](inp, req, frozenset(flags)))})
        return out
    return f


def man_alt(*items):
    return [{"name": n, "reading": d, "expected": e} for n, d, e in items]


def Z(status, reason=None, label=None, **kw):
    e = {"status": status, "reason": reason, "label": label, "model_label": None}
    e.update(kw)
    return e


def sz(rev, b, a):
    return {"rev": rev, "bid_size": b, "ask_size": a}


def stdq(rev=1, ev=-2 * S, bid="1.0000", ask="1.0500", **kw):
    return Q(rev, ev, bid, ask, **kw)


def one5(id_, case, b, a, thr="0.60", ref="OC 2.2 OC5; ruling Q1", **kw):
    quotes = kw.pop("quotes", None)
    if quotes is None:
        quotes = [stdq()]
    sizes = kw.pop("sizes", None)
    return add(id_, "oc5", "OC5", ref, case, quotes, sizes if sizes is not None else [sz(1, b, a)],
               kw.pop("req", None) or req5(thr), **kw)


def build():
    # ---------------- OC5
    one5("OC5-01", "1", 600, 100)
    one5("OC5-02", "2", 100, 600)
    one5("OC5-03", "3", 160, 40, note="inclusive boundary (M1).")
    one5("OC5-04", "4", 159, 41)
    one5("OC5-05a", "5", 40, 160)
    one5("OC5-05b", "5", 41, 159)
    one5("OC5-06", "6", 500, 500)
    one5("OC5-07a", "7", 1000000000, 999999999, note="exact big integers.")
    one5("OC5-07b", "7", 1000000000, 1)
    one5("OC5-07c", "7", 999999999, 1000000000)
    one5("OC5-08a", "8", 700, 100, thr="0.80")
    one5("OC5-08b", "8", 700, 100, thr="0.10")
    one5("OC5-08c", "8", 100, 300, thr="0.50", note="override threshold, inclusive at -0.50.")
    one5("OC5-09a", "9", 100, 0, ref="ruling Q2")
    one5("OC5-09b", "9", 0, 100, ref="ruling Q2")
    one5("OC5-10", "10", 0, 0, ref="ruling Q2")
    one5("OC5-11a", "11", None, None, ref="ruling Q2", tags=["pending:req10"])
    one5("OC5-11b", "11", 100, None, ref="ruling Q2", tags=["pending:req10"])
    one5("OC5-11c", "11", 0, 0, sizes=[], ref="ruling Q2", tags=["pending:req10"], note="no QuoteSize row for the revision.")
    one5("OC5-12a", "12", 600, 100, quotes=[stdq(bid=None)], ref="OC 2.3 invalid quote")
    one5("OC5-12b", "12", 600, 100, quotes=[stdq(ask=None)], ref="OC 2.3 invalid quote")
    one5("OC5-12c", "12", 600, 100, quotes=[stdq(bid="0.0000")], ref="OC 2.3 invalid quote (bid not above 0)",
         tags=["pending:req2"])
    one5("OC5-13", "13", 600, 100, quotes=[stdq(bid="1.0000", ask="1.0000")], ref="ruling Q8",
         tags=["pending:req1"], note="locked evaluates for OC5.")
    one5("OC5-14", "14", 600, 100, quotes=[stdq(bid="1.0500", ask="1.0000")], ref="OC 2.3 crossed")
    for sid, cs, ev, lim in (("15a", "age 30s", -30 * S, STALE), ("15b", "age 2s", -2 * S, STALE),
                             ("15c", "age exactly 10s fresh", -10 * S, STALE),
                             ("15d", "age 10s+1ns stale", -10 * S - 1, STALE),
                             ("15e", "limit 5s: age exactly 5s fresh", -5 * S, 5 * S),
                             ("15f", "limit 5s: age 5s+1ns stale", -5 * S - 1, 5 * S)):
        one5("OC5-" + sid, "15 " + cs, 600, 100, quotes=[stdq(ev=ev)], req=req5(stale=lim), ref="OC 2.3; ruling Q4")
    one5("OC5-16a", "16 event after T", 0, 0, ref="OC 2.3 causal",
         quotes=[stdq(1, -5 * S), stdq(2, 1 * S)], sizes=[sz(1, 600, 100), sz(2, 100, 600)])
    one5("OC5-16b", "16 known_at after T", 0, 0, ref="OC 2.3 causal",
         quotes=[stdq(1, -5 * S), stdq(2, -1 * S, known=1 * S)], sizes=[sz(1, 600, 100), sz(2, 100, 600)])
    one5("OC5-16c", "16 empty stream", 0, 0, quotes=[], sizes=[], ref="OC 2.3 causal")
    one5("OC5-16d", "16 only quote after T gives no_quote (D7)", 0, 0, ref="PO ruling D7",
         quotes=[stdq(1, 1 * S)], sizes=[sz(1, 600, 100)])
    one5("OC5-16e", "16 only quote known after T gives no_quote (D7)", 0, 0, ref="PO ruling D7",
         quotes=[stdq(1, -1 * S, known=1 * S)], sizes=[sz(1, 600, 100)])
    one5("OC5-17a", "17 latest excluded, older regular fresh", 0, 0, ref="R25 latest-causal rule",
         quotes=[stdq(1, -5 * S), stdq(2, -1 * S, cond="excluded")], sizes=[sz(1, 600, 100), sz(2, 100, 600)])
    one5("OC5-18a", "18 same event, sequence breaks tie", 0, 0, ref="spec 18",
         quotes=[stdq(1, -3 * S, seq=1), stdq(2, -3 * S, seq=2)], sizes=[sz(1, 600, 100), sz(2, 100, 600)])
    one5("OC5-18b", "18 same event, known_at breaks tie", 0, 0, ref="spec 18",
         quotes=[stdq(1, -3 * S), stdq(2, -3 * S, known=-2500000000)],
         sizes=[sz(1, 600, 100), sz(2, 100, 600)])
    one5("OC5-18c", "18 unresolved tie", 0, 0, ref="spec 18",
         quotes=[stdq(1, -3 * S), stdq(2, -3 * S)], sizes=[sz(1, 600, 100), sz(2, 100, 600)])
    one5("OC5-19", "19 sequence and known_at disagree", 0, 0, ref="spec 19 (sequence first)",
         quotes=[stdq(1, -3 * S, seq=2, known=-2900000000), stdq(2, -3 * S, seq=1, known=-2 * S)],
         sizes=[sz(1, 600, 100), sz(2, 100, 600)], note="sequence outranks known_at; rev1 is latest.")
    one5("OC5-24b", "24b low coverage does not block OC5", 0, 0, ref="ruling Q8",
         quotes=[stdq(1, -200 * S), stdq(2, -100 * S), stdq(3, -2 * S)],
         sizes=[sz(1, 600, 100), sz(2, 600, 100), sz(3, 600, 100)], note="3 regular updates in 5 minutes.")
    one5("OC5-NC", "single_venue feed", 600, 100, feed="single_venue", ref="ruling Q7")
    one5("OC5-AM", "American style: quote-only unaffected", 600, 100, style="american", ref="ruling section 2 item 6")
    one5("OC5-B1", "stale and crossed together: validity first (D6)", 600, 100, ref="PO ruling D6",
         quotes=[stdq(bid="1.0500", ask="1.0000", ev=-30 * S)])
    # combined rows: adjacent gate pairs (order no_quote, excluded_condition, not_consolidated, validity, stale, size)
    one5("OC5-G1", "no_quote + single_venue: no_quote first", 0, 0, quotes=[], sizes=[], feed="single_venue",
         ref="PO ruling gate order")
    one5("OC5-G2", "excluded latest + single_venue: excluded_condition first", 0, 0, feed="single_venue",
         quotes=[stdq(1, -5 * S), stdq(2, -1 * S, cond="excluded")], sizes=[sz(1, 600, 100), sz(2, 100, 600)],
         ref="PO ruling gate order")
    one5("OC5-G3", "single_venue + crossed: not_consolidated first", 600, 100, feed="single_venue",
         quotes=[stdq(bid="1.0500", ask="1.0000")], ref="PO ruling gate order")
    one5("OC5-G4", "missing size + stale: stale_quote first", None, None, quotes=[stdq(ev=-30 * S)],
         ref="PO ruling gate order (size after stale)")
    one5("OC5-G5", "zero sizes + stale: stale_quote first", 0, 0, quotes=[stdq(ev=-30 * S)],
         ref="PO ruling gate order (size after stale)")
    one5("OC5-G6", "missing size + invalid quote: invalid_quote first", None, None, quotes=[stdq(bid=None)],
         ref="PO ruling gate order (size after validity)")
    one5("OC5-G7", "zero sizes + crossed: crossed_market first", 0, 0, quotes=[stdq(bid="1.0500", ask="1.0000")],
         ref="PO ruling gate order (size after validity)")
    # structural
    one5("OC5-S01", "negative size", -5, 100, ref="R25 BOUNDARY", tags=["structural"])
    one5("OC5-S02", "non-integer size", 10.5, 100, ref="R25 BOUNDARY", tags=["structural"])
    one5("OC5-S03", "negative bid price is invalid_quote (D15)", 600, 100, quotes=[stdq(bid="-0.0500")], ref="PO ruling D15")
    one5("OC5-NSTD", "non-standard contract: quote-only unaffected", 600, 100, nonstd=True, ref="OC 2.3 non-standard")
    one5("OC5-S05", "malformed type (bid as number)", 600, 100, quotes=[stdq(bid=1.0)], ref="PO ruling D15", tags=["structural"])
    one5("OC5-S04", "non-monotone event time", 0, 0, quotes=[stdq(1, -2 * S), stdq(2, -5 * S)],
         sizes=[sz(1, 600, 100), sz(2, 600, 100)], ref="R25 BOUNDARY", tags=["structural"])

    # ---------------- OC6 helpers
    base = [(-300, "v", "0.1000"), (-240, "v", "0.1000"), (-180, "v", "0.1000"), (-120, "v", "0.1000"),
            (-60, "v", "0.1000")]

    def six(id_, case, items, ref="ruling Q3", req=None, mid="10.0000", **kw):
        return add(id_, "oc6", "OC6", ref, case, stream6(items, mid), None, req or req6(), **kw)

    six("OC6-20", "20 steady 0.10 then 0.06", base + [(0, "v", "0.0600")])
    six("OC6-21", "21 steady 0.10 then 0.20", base + [(0, "v", "0.2000")])
    six("OC6-22", "22 steady 0.10 then 0.10", base + [(0, "v", "0.1000")])
    steady2 = lambda s, c: [(-300, "v", s), (-240, "v", s), (-180, "v", s), (-120, "v", s), (-60, "v", s), (0, "v", c)]
    six("OC6-23a", "23 ratio exactly 0.75", steady2("0.2000", "0.1500"), note="inclusive (M11).")
    six("OC6-23b", "23 ratio exactly 1.50", steady2("0.2000", "0.3000"))
    six("OC6-23c", "23 ratio 0.7501", steady2("2.0000", "1.5002"))
    six("OC6-23d", "23 ratio 1.4999", steady2("2.0000", "2.9998"))
    six("OC6-24a", "24 exactly 5 updates in window", [(-400, "v", "0.1000"), (-240, "v", "0.1000"),
                                                      (-180, "v", "0.1000"), (-120, "v", "0.1000"),
                                                      (-60, "v", "0.1000"), (0, "v", "0.0600")],
        note="carry-in at -400 not counted.")
    six("OC6-24b", "24 only 4 updates in window", [(-330, "v", "0.1000"), (-180, "v", "0.1000"),
                                                   (-120, "v", "0.1000"), (-60, "v", "0.1000"),
                                                   (0, "v", "0.0600")], note="-330 is outside the 300 s window (M12).")
    six("OC6-24c", "24 (M16) 3 regular + 3 excluded", [(-250, "v", "0.1000"), (-200, "x", "0.1000"),
                                                       (-150, "x", "0.1000"), (-120, "v", "0.1000"),
                                                       (-60, "x", "0.1000"), (0, "v", "0.0600")])
    six("OC6-25a", "25 narrower_max 0.50 on ratio 0.60", base + [(0, "v", "0.0600")], req=req6(nmax="0.50"))
    six("OC6-25b", "25 narrower_max 0.50 on ratio 0.50", base + [(0, "v", "0.0500")], req=req6(nmax="0.50"))
    six("OC6-25c", "25 wider_min 2.0 on ratio 2.0", base + [(0, "v", "0.2000")], req=req6(wmin="2.0"))
    six("OC6-25d", "25 wider_min 2.0 on ratio 1.9", base + [(0, "v", "0.1900")], req=req6(wmin="2.0"))
    six("OC6-26", "26 crossed and locked intervals get zero weight",
        [(-300, "v", "0.1000"), (-250, "v", "0.1000"), (-200, "crossed"), (-150, "v", "0.3000"),
         (-100, "locked"), (-50, "v", "0.2000"), (0, "v", "0.1000")], note="valid time 200 s.")
    six("OC6-27", "27 4-minute quiet gap, time-weighted",
        [(-300, "v", "0.2000"), (-299, "v", "0.2000"), (-298, "v", "0.2000"), (-297, "v", "0.2000"),
         (-60, "v", "0.1000"), (0, "v", "0.1300")], note="simple mean would give 0.757 (neither), M17.")
    six("OC6-28a", "28 update exactly 300 s before T is inside",
        [(-300, "v", "0.1000"), (-240, "v", "0.1000"), (-180, "v", "0.1000"), (-120, "v", "0.1000"),
         (0, "v", "0.0500")])
    six("OC6-28b", "carry-in: quote in force before window start",
        [(-500, "v", "0.2000"), (-250, "v", "0.1000"), (-200, "v", "0.1000"), (-150, "v", "0.1000"),
         (-100, "v", "0.1000"), (0, "v", "0.0500")], note="carry-in 0.20 for [-300,-250).")
    six("OC6-28c", "zero weight for the current quote when spread changes exactly at T",
        [(-300, "v", "0.1000"), (-200, "v", "0.1000"), (-100, "v", "0.1000"), (-50, "v", "0.1000"),
         (0, "v", "0.3000")])
    six("OC6-29a", "29 current ask null", base + [(0, "askNull")], ref="OC 2.3 invalid")
    six("OC6-29b", "29 current bid null", base + [(0, "bidNull")], ref="OC 2.3 invalid")
    six("OC6-30a", "30 locked at T", base + [(0, "locked")], ref="ruling Q8")
    six("OC6-30b", "30 bid 0 positive ask", base + [(0, "bid0")], ref="OC 2.3 invalid", tags=["pending:req2"])
    six("OC6-30c", "crossed at T", base + [(0, "crossed")], ref="OC 2.3 crossed")
    six("OC6-31a", "31 tiny prices exact rational",
        [(-300, "mid", "0.0100", {}, "0.0150"), (-240, "mid", "0.0100", {}, "0.0150"),
         (-180, "mid", "0.0100", {}, "0.0150"), (-120, "mid", "0.0100", {}, "0.0150"),
         (-60, "mid", "0.0100", {}, "0.0150"), (0, "mid", "0.0020", {}, "0.0150")],
        note="bid/ask 0.0100/0.0200 then 0.0140/0.0160; midpoint 3/200.")
    six("OC6-32a", "32 single quote", [(-2, "v", "0.1000")])
    six("OC6-32b", "32 single quote at T", [(0, "v", "0.1000")])
    six("OC6-33a", "33 window crosses previous session", [(-400, "v", "0.5000"), (-250, "v", "0.5000"),
                                                          (-120, "v", "0.1000"), (-90, "v", "0.1000"),
                                                          (-60, "v", "0.1000"), (-30, "v", "0.1000"),
                                                          (0, "v", "0.0500")], req=req6(opn=-120 * S),
        note="session opens at -120 s; previous session never enters.")
    six("OC6-33b", "33 no carry across the open", [(-200, "v", "0.5000"), (-60, "v", "0.1000"),
                                                   (-50, "v", "0.1000"), (-40, "v", "0.1000"),
                                                   (-30, "v", "0.1000"), (0, "v", "0.0500")],
        req=req6(opn=-120 * S), note="[-120,-60) has no in-session quote: zero weight.")
    six("OC6-34a", "34 events after T excluded", base + [(0, "v", "0.0600"), (10, "v", "1.0000"), (20, "v", "1.0000")])
    six("OC6-34b", "34 known_at after T excluded",
        base + [(-10, "v", "0.6000", {"known": 5 * S}), (0, "v", "0.0600")])
    six("OC6-NWS", "no valid weight: five valid updates all at T",
        [(0, "v", "0.1000", {"seq": k}) for k in (1, 2, 3, 4, 5)], ref="ruling Q3 no_window_spread",
        note="ordered by seq; all intervals have zero length.")
    six("OC6-NQ", "empty stream", [], ref="OC 2.3")
    six("OC6-ST-a", "stale: age exactly 10s fresh",
        base + [(-10, "v", "0.1000")], ref="OC 2.3; ruling Q4",
        note="latest update at -10 s: age exactly 10 s is fresh; spread constant 0.10 so the ratio is 1 under any weighting.")
    six("OC6-ST-b", "stale: age 10s+1ns",
        base + [(NS(-10 * S - 1), "v", "0.1000")], ref="OC 2.3; ruling Q4")
    six("OC6-ST-c", "stale: age 30s", base + [(-30, "v", "0.1000")], ref="OC 2.3; ruling Q4")
    six("OC6-EX", "latest excluded condition", base + [(0, "x", "0.0600")], ref="OC 2.3",
        tags=[])
    six("OC6-AM", "American style: quote-only unaffected", base + [(0, "v", "0.0600")], style="american",
        ref="ruling section 2 item 6")
    # M14 boundary rows (binary64 vs exact)
    for tag, num, den, lbl in (("31b", 3, 4, "narrower"), ("31c", 3, 2, "wider")):
        found = None
        for ka in range(2, 600, 2):
            for kb in range(2, 600, 2):
                avg4 = F(2 * ka + kb, 3)
                c4 = avg4 * num / den
                if c4.denominator != 1 or c4 % 2 != 0 or c4 < 2:
                    continue
                a, b, c = dec(F(ka, 10000)), dec(F(kb, 10000)), dec(F(int(c4), 10000))
                items = [(-300, "v", a), (-200, "v", a), (-100, "v", b), (-50, "v", b), (0, "v", c)]
                inp = {"T_ns": 0, "quotes": stream6(items)}
                if eval_oc6(inp, req6(), frozenset(["M14"]))["label"] != lbl:
                    found = items
                    break
            if found:
                break
        assert found, "no binary64 boundary found for " + tag
        six("OC6-" + tag, "31 boundary exact %d/%d that binary64 misses" % (num, den), found,
            note="ratio exactly %d/%d in rational arithmetic (M14)." % (num, den))
    # rows formerly pending, now ruled (D1-D6)
    six("OC6-B1", "current quote earlier than T is weighted to T (D1)",
        [(-300, "v", "0.1000"), (-240, "v", "0.1000"), (-180, "v", "0.1000"), (-120, "v", "0.1000"),
         (-60, "v", "0.1000"), (-5, "v", "0.1500")], ref="PO ruling D1")
    six("OC6-B2", "midpoint moves: ratio in bps of midpoint (D2)",
        [(-300, "v", "0.1000"), (-240, "v", "0.1000"), (-180, "v", "0.1000"), (-120, "v", "0.1000"),
         (-60, "v", "0.1000"), (0, "mid", "0.1500", {}, "20.0000")], ref="PO ruling D2")
    six("OC6-B3", "coverage counts regular-condition updates, validity ignored (D3)",
        [(-300, "v", "0.1000"), (-200, "crossed"), (-100, "locked"), (-50, "v", "0.1000"), (0, "v", "0.0600")],
        ref="PO ruling D3")
    six("OC6-B4", "coverage clipped at session open (D4)",
        [(-200, "v", "0.5000"), (-90, "v", "0.1000"), (-60, "v", "0.1000"), (-30, "v", "0.1000"),
         (0, "v", "0.0500")], req=req6(opn=-120 * S), ref="PO ruling D4")
    six("OC6-B7", "interval starts at known_at (D5)",
        [(-300, "v", "0.1000"), (-240, "v", "0.1000"), (-180, "v", "0.1000"),
         (-120, "v", "0.4000", {"known": -60 * S}), (0, "v", "0.0500")], ref="PO ruling D5")
    six("OC6-B9", "stale before coverage (D6)", [(-30, "v", "0.1000")], ref="PO ruling D6")
    six("OC6-B11", "single_venue affects OC5 only (D6)", base + [(0, "v", "0.0600")], feed="single_venue",
        ref="PO ruling D6")
    six("OC6-NSTD", "non-standard contract: quote-only unaffected", base + [(0, "v", "0.0600")], nonstd=True,
        ref="OC 2.3 non-standard")
    rng = random.Random(SEED)
    t, burst = -300 * S, []
    for _ in range(40):
        burst.append((NS(t), "v", rng.choice(["0.2800", "0.3000", "0.3200"])))
        t += rng.randint(1, 2) * 10 ** 7
    six("OC6-BURST", "bursty updating: 40 updates in under 1 s, then quiet; time-weighted",
        burst + [(-299, "v", "0.1000"), (0, "v", "0.0800")], ref="ruling Q3 time-weighting",
        note="simple mean would be dominated by the burst (M17).")
    six("OC6-G1", "excluded latest + crossed: excluded_condition first", base + [(0, "crossed")], ref="PO ruling gate order")
    ROWS[-1]["inputs"]["quotes"][-1]["condition"] = "excluded"
    r = eval_oc6(ROWS[-1]["inputs"], ROWS[-1]["request"])
    ROWS[-1]["expected"], ROWS[-1]["derivation"] = expect(r), r["trace"]
    six("OC6-G2", "crossed + stale: crossed_market first", base + [(-30, "crossed")], ref="PO ruling gate order")
    six("OC6-S01", "non-monotone event time", [(-60, "v", "0.1000"), (-120, "v", "0.1000")],
        ref="R25 BOUNDARY", tags=["structural"])
    six("OC6-S02", "negative bid price is invalid_quote (D15)", base + [(0, "v", "0.1000")], ref="PO ruling D15")
    ROWS[-1]["inputs"]["quotes"][-1]["bid"] = "-0.0500"
    r = eval_oc6(ROWS[-1]["inputs"], ROWS[-1]["request"])
    ROWS[-1]["expected"] = expect(r)
    ROWS[-1]["derivation"] = r["trace"]


# ---------------------------------------------------------------- mutation report
MUTANTS = ["M1", "M2", "M3", "M4a", "M4b", "M5", "M6a", "M6b", "M6c", "M7", "M8", "M9", "M10", "M11", "M12a",
           "M12b", "M13a", "M13b", "M14", "M15", "M16", "M17", "M18", "M19", "M20", "X1", "X2", "X3", "X4", "X5", "X6", "X7", "X8", "X9", "X10", "X11", "X12", "X13", "X14"]


def differs(exp, got):
    if exp["status"] != got["status"]:
        return True
    if exp["status"] == "structural_error":
        return exp["code"] != got["code"]
    if exp.get("reason_gating", True) and exp["reason"] != got["reason"]:
        return True
    if exp["label"] != got["label"]:
        return True
    if "value" in exp:
        if got["value"] is None or abs(float(F(exp["value"]["exact"])) - float(got["value"])) > 1e-9:
            return True
    return False


def mutation_report():
    rep = {}
    for m in MUTANTS:
        hits = []
        for row in ROWS:
            if not row["gating"] or row["expected"] is None:
                continue
            got = EVAL[row["op"]](row["inputs"], row["request"], frozenset([m]))
            if differs(row["expected"], got):
                hits.append(row["id"])
        rep[m] = hits
    return rep


# ---------------------------------------------------------------- independent self-check (second implementation)
HAND = {  # literal values worked by hand from the rules
    "OC5-01": ("fired", "bid", "5/7"), "OC5-02": ("fired", "ask", "-5/7"), "OC5-03": ("fired", "bid", "3/5"),
    "OC5-04": ("not_fired", None, "59/100"), "OC5-06": ("not_fired", None, "0"),
    "OC5-07a": ("not_fired", None, "1/1999999999"), "OC5-07b": ("fired", "bid", "999999999/1000000001"),
    "OC5-08a": ("not_fired", None, "3/4"), "OC5-09a": ("fired", "bid", "1"), "OC5-09b": ("fired", "ask", "-1"),
    "OC6-20": ("fired", "narrower", "3/5"), "OC6-21": ("fired", "wider", "2"), "OC6-22": ("not_fired", None, "1"),
    "OC6-23a": ("fired", "narrower", "3/4"), "OC6-23b": ("fired", "wider", "3/2"),
    "OC6-23c": ("not_fired", None, "7501/10000"), "OC6-23d": ("not_fired", None, "14999/10000"),
    "OC6-26": ("fired", "narrower", "4/7"), "OC6-27": ("fired", "narrower", "13/18"),
    "OC6-28b": ("fired", "narrower", "3/7"), "OC6-31a": ("fired", "narrower", "1/5"),
    "OC6-33a": ("fired", "narrower", "1/2"), "OC6-28c": ("fired", "wider", "3"),
}


def b_valid(q):
    try:
        b, a = q["bid"], q["ask"]
        if b is None or a is None or F(b) <= 0:
            return "invalid_quote"
        return "crossed_market" if F(a) < F(b) else ("locked_market" if F(a) == F(b) else "ok")
    except Exception:
        return "invalid_quote"


def b_oc5(inp, req):
    T = inp["T_ns"]
    qs = sorted([q for q in inp["quotes"] if q["event_ns"] <= T and q["known_at_ns"] <= T],
                key=lambda q: (q["event_ns"], q.get("seq", 0), q["known_at_ns"]))
    if len({(q["event_ns"], q.get("seq", 0), q["known_at_ns"]) for q in qs}) != len(qs):
        return ("structural_error", None, None, None)
    if not qs:
        return ("unavailable", "no_quote", None, None)
    L = qs[-1]
    if L["condition"] != "regular":
        return ("unavailable", "excluded_condition", None, None)
    if inp["feed_kind"] != "consolidated":
        return ("unavailable", "not_consolidated", None, None)
    v = b_valid(L)
    if v in ("invalid_quote", "crossed_market"):
        return ("unavailable", v, None, None)
    if T - L["event_ns"] > req["stale_limit_ns"]:
        return ("unavailable", "stale_quote", None, None)
    z = [s for s in inp["sizes"] if s["rev"] == L["rev"]]
    if not z or z[0]["bid_size"] is None or z[0]["ask_size"] is None:
        return ("unavailable", "missing_size", None, None)
    b, a = z[0]["bid_size"], z[0]["ask_size"]
    if b + a == 0:
        return ("unavailable", "zero_displayed_size", None, None)
    x = F(b - a, b + a)
    t = F(req["imbalance_threshold"])
    return ("fired" if abs(x) >= t else "not_fired", "bid" if x >= t else ("ask" if x <= -t else None), x, None)


def b_oc6(inp, req):
    T = inp["T_ns"]
    qs = sorted([q for q in inp["quotes"] if q["event_ns"] <= T and q["known_at_ns"] <= T],
                key=lambda q: (q["event_ns"], q.get("seq", 0), q["known_at_ns"]))
    if not qs:
        return ("unavailable", "no_quote", None, None)
    L = qs[-1]
    if L["condition"] != "regular":
        return ("unavailable", "excluded_condition", None, None)
    v = b_valid(L)
    if v != "ok":
        return ("unavailable", v, None, None)
    if T - L["event_ns"] > req["stale_limit_ns"]:
        return ("unavailable", "stale_quote", None, None)
    ws = max(T - req["window_ns"], req["session_open_ns"])
    if sum(1 for q in qs if q["condition"] == "regular" and ws <= q["event_ns"] <= T) < req["coverage_min"]:
        return ("unavailable", "low_quote_coverage", None, None)
    pts = sorted({ws, T} | {q["known_at_ns"] for q in qs if ws < q["known_at_ns"] < T})
    tot = wt = F(0)
    for x0, x1 in zip(pts, pts[1:]):
        inforce = None
        for q in qs:
            if q["known_at_ns"] <= x0:
                inforce = q
        if inforce is None or inforce["event_ns"] < req["session_open_ns"]:
            continue
        if inforce["condition"] == "regular" and b_valid(inforce) == "ok":
            sp = F(inforce["ask"]) - F(inforce["bid"])
            md = (F(inforce["ask"]) + F(inforce["bid"])) / 2
            tot += (x1 - x0) * sp / md * 10000
            wt += x1 - x0
    if wt == 0:
        return ("unavailable", "no_window_spread", None, None)
    cb = (F(L["ask"]) - F(L["bid"])) / ((F(L["ask"]) + F(L["bid"])) / 2) * 10000
    r = cb / (tot / wt)
    nm, wm = F(req["narrower_max"]), F(req["wider_min"])
    return ("fired" if (r <= nm or r >= wm) else "not_fired", "narrower" if r <= nm else ("wider" if r >= wm else None), r, None)


def selfcheck(doc):
    bad = []
    for row in doc["rows"]:
        e = row["expected"]
        if not row["gating"] or e is None:
            continue
        if e["status"] == "structural_error":
            continue
        fn = b_oc5 if row["op"] == "oc5" else b_oc6
        st, a, b, _ = fn(row["inputs"], row["request"])
        if st == "structural_error":
            bad.append((row["id"], "B says structural"))
            continue
        if row["op"] == "oc5" and st in ("fired", "not_fired"):
            lab, val = a, b
        elif row["op"] == "oc6" and st in ("fired", "not_fired"):
            lab, val = a, b
        else:
            lab, val = None, None
        reason = a if st == "unavailable" else None
        if st != e["status"] or (e.get("reason_gating", True) and reason != e["reason"]) or lab != e["label"]:
            bad.append((row["id"], "status/reason/label", st, reason, lab, e))
            continue
        if val is not None and F(e["value"]["exact"]) != val:
            bad.append((row["id"], "value", fx(val), e["value"]))
    for k, (st, lab, ex) in HAND.items():
        row = next(r for r in doc["rows"] if r["id"] == k)
        e = row["expected"]
        if e["status"] != st or e["label"] != lab or F(e["value"]["exact"]) != F(ex):
            bad.append((k, "hand-value mismatch", e))
    # every mutant must be caught; M6 needs all three sub-variants
    for m, hits in doc["mutation_report"].items():
        if not hits:
            bad.append((m, "mutant survives"))
    # tie / structural rows
    for row in doc["rows"]:
        if row["expected"] and row["expected"]["status"] == "structural_error":
            if not any(t == "structural" for t in row["tags"]) and row["id"] != "OC5-18c":
                bad.append((row["id"], "untagged structural"))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--no-check", action="store_true")
    a = ap.parse_args()
    build()
    for row in ROWS:  # dependency tags
        qs = row["inputs"]["quotes"]
        t = set(row["tags"])
        if row["id"].startswith(("OC5-15", "OC6-ST")) or "stale_quote" in EVAL[row["op"]](row["inputs"], row["request"])["gates"]:
            t.add("pending:req11")
        if any(q["bid"] is not None and (q["bid"].startswith("-") or q["bid"] == "0.0000") for q in qs if isinstance(q["bid"], str)):
            t.add("pending:req2")
        e = row["expected"]
        if e["status"] == "unavailable" and e.get("reason") not in ("low_quote_coverage", "no_window_spread"):
            t.discard("pending:req3")
        if e["status"] == "unavailable" and e.get("reason") != "zero_displayed_size":
            t.discard("pending:req10") if row["id"] not in ("OC5-11a", "OC5-11b", "OC5-11c") else None
        row["tags"] = sorted(t)
    ids = [r["id"] for r in ROWS]
    assert len(ids) == len(set(ids)), "duplicate ids"
    doc = {
        "provenance": PROV, "qualification_label": QUAL, "generator": "gen_m1_oc.py", "seed": SEED, "schema_version": 1,
        "note": "Test oracle fixtures written from design text and PO rulings only. Times are integer ns relative to T=0. "
                "Decimals are strings with at most 4 places. Expected values are exact rationals.",
        "status_values": ["fired", "not_fired", "unavailable", "structural_error"],
        "closed_reasons": CLOSED,
        "defaults": {"stale_limit_ns": STALE, "window_ns": WINDOW, "coverage_min": CMIN,
                     "imbalance_threshold": "0.60", "narrower_max": "0.75", "wider_min": "1.50"},
        "mutation_report": mutation_report(),
        "rows": ROWS,
    }
    os.makedirs(a.out, exist_ok=True)
    p = os.path.join(a.out, "m1_oc_cases.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, ensure_ascii=True)
        f.write("\n")
    if not a.no_check:
        bad = selfcheck(doc)
        if bad:
            for b in bad:
                print("SELFCHECK FAIL", b, file=sys.stderr)
            sys.exit(1)
    g = sum(1 for r in ROWS if r["gating"])
    print("rows=%d gating=%d nongating=%d selfcheck=%s" % (len(ROWS), g, len(ROWS) - g, "skipped" if a.no_check else "ok"))


if __name__ == "__main__":
    main()
