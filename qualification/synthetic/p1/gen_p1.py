#!/usr/bin/env python3
"""P1 parity-closure fixture generator. SYNTHETIC data, stdlib only.

Usage: python gen_p1.py --out p1_cases.json
Expected values are computed here from the design text (option-contracts 2.2/2.3,
flow F3/F5/F6/F13-F16, PO rulings), never from library output.
All times are integer nanoseconds relative to T (the evaluation time, T = 0).
Decimals are strings with <= 4 places. Exact results are decimal strings when
the value terminates, else a reduced rational "p/q".
"""
import argparse
import json
import random
from fractions import Fraction as F

SEED = 20261029
S = 10 ** 9
FORBIDDEN = ["bullish", "bearish", "bull", "bear", "buy", "buying", "sell", "selling",
             "bought", "sold", "trade", "direction", "outlook", "conviction",
             "protection", "speculation", "aggressor", "aggressive"]
ALLOWED_LABELS = ["ask-side proxy", "bid-side proxy"]
REASONS = ["invalid_quote", "locked_market", "crossed_market", "stale_quote",
           "low_quote_coverage", "no_quote", "missing_reference", "inside_spread",
           "no_classified_premium", "ambiguous_touch"]


def fmt(x):
    x = F(x)
    n, d = x.numerator, x.denominator
    dd = d
    k2 = k5 = 0
    while dd % 2 == 0:
        dd //= 2
        k2 += 1
    while dd % 5 == 0:
        dd //= 5
        k5 += 1
    if dd != 1:
        return "%d/%d" % (n, d)
    k = max(k2, k5)
    scaled = abs(n) * (10 ** k) // d
    s = str(scaled).rjust(k + 1, "0")
    out = s[:-k] + "." + s[-k:] if k else s
    return ("-" if n < 0 else "") + out


def dec4(i):
    return "%d.%04d" % (i // 10000, i % 10000)


ROWS = []


def add(rid, group, ref, pend, tags, inputs, params, expected, deriv, open_item=None):
    if isinstance(pend, int):
        pend = [pend]
    ROWS.append({"id": rid, "group": group, "design_ref": ref,
                 "pending_design_request": pend, "open_item": open_item,
                 "tags": tags, "inputs": inputs, "params": params,
                 "expected": expected, "derivation": deriv})


# ---------------------------------------------------------------- spread
def exp_spread(quote, stale_ns=10 * S):
    if quote is None:
        return ("unavailable", "no_quote", None)
    b, a = quote["bid"], quote["ask"]
    if b is None and a is None:
        return ("unavailable", "no_quote", None)
    if b is None or a is None or F(b) <= 0:
        return ("unavailable", "invalid_quote", None)
    b, a = F(b), F(a)
    if a < b:
        return ("unavailable", "crossed_market", None)
    if a == b:
        return ("unavailable", "locked_market", None)
    if -quote["t_rel_ns"] > stale_ns:
        return ("unavailable", "stale_quote", None)
    sp = a - b
    mid = (a + b) / 2
    return ("available", None, {"spread": fmt(sp), "midpoint": fmt(mid),
                                "spread_bps": fmt(sp / mid * 10000)})


def spread_row(rid, group, ref, pend, tags, bid, ask, t=0, note=None, open_item=None,
               nullrec=False):
    quote = None if nullrec else {"bid": bid, "ask": ask, "t_rel_ns": t}
    st, rs, val = exp_spread(quote)
    if st == "available":
        b, a = F(bid), F(ask)
        d = ("spread=ask-bid=%s-%s=%s; midpoint=(%s+%s)/2=%s; spread_bps=%s/%s*10000=%s"
             % (bid, ask, fmt(a - b), ask, bid, fmt((a + b) / 2), fmt(a - b),
                fmt((a + b) / 2), val["spread_bps"]))
    else:
        d = "quote bid=%s ask=%s age=%dns -> %s by OC 2.3 gate table%s" % (
            bid, ask, -t, rs, (" (" + note + ")") if note else "")
    add(rid, group, ref, pend, tags,
        {"op": "spread", "quote": quote}, {"stale_limit_ns": 10 * S},
        {"status": st, "reason": rs, "value": val}, d, open_item)


# ---------------------------------------------------------------- signing
def exp_sign(quote, price, trade_t, eps, max_age):
    price, eps = F(price), F(eps)
    if quote is None or quote["t_rel_ns"] > trade_t:
        return ("unclassified", "no_quote", None)
    b, a = quote["bid"], quote["ask"]
    if b is None and a is None:
        return ("unclassified", "no_quote", None)
    if b is None or a is None or F(b) <= 0:
        return ("unclassified", "invalid_quote", None)
    b, a = F(b), F(a)
    if a < b:
        return ("unclassified", "crossed_market", None)
    age = trade_t - quote["t_rel_ns"]
    if age > max_age:
        return ("unclassified", "stale_quote", None)
    at_ask = price >= a - eps
    at_bid = price <= b + eps
    if at_ask and at_bid:
        return ("unclassified", "ambiguous_touch", None)
    if at_ask:
        return ("available", None, "ask")
    if at_bid:
        return ("available", None, "bid")
    return ("unclassified", "inside_spread", None)


def exp_sign_legacy(quote, price, trade_t):
    """Legacy default: touch rule first, then midpoint split (design audit item 4)."""
    price = F(price)
    b, a = F(quote["bid"]), F(quote["ask"])
    if b <= 0 or a < b:
        return ("unclassified", "invalid_quote", None)
    if trade_t - quote["t_rel_ns"] > 3 * S:
        return ("unclassified", "stale_quote", None)
    if price >= a:
        return ("available", None, "ask")
    if price <= b:
        return ("available", None, "bid")
    mid = (a + b) / 2
    return ("available", None, "ask" if price > mid else "bid")


def sign_expected_dict(st, rs, side):
    lab = {"ask": "ask-side proxy", "bid": "bid-side proxy"}.get(side)
    return {"status": st, "reason": rs, "side": side, "label": lab, "value": None}


def sign_row(rid, group, ref, pend, tags, bid, ask, price, qt=-1 * S, eps="0.0100",
             max_age=3 * S, open_item=None, nullrec=False, legacy=False, right="call"):
    quote = None if nullrec else {"bid": bid, "ask": ask, "t_rel_ns": qt}
    trade = {"price": price, "size": 1, "t_rel_ns": 0, "right": right}
    if legacy:
        params = {}
        st, rs, side = exp_sign_legacy(quote, price, 0)
    else:
        params = {"inside_spread": "unknown", "epsilon": eps, "max_quote_age_ns": max_age}
        st, rs, side = exp_sign(quote, price, 0, eps, max_age)
    if nullrec:
        d = "no quote record -> unclassified no_quote"
    else:
        age = 0 - qt
        d = "quote %s/%s age=%dns (limit %s); price %s" % (
            bid, ask, age, "3000000000" if legacy else max_age, price)
        if st == "available":
            if legacy and F(price) > F(bid) and F(price) < F(ask):
                d += "; inside spread, midpoint=%s -> %s side (legacy midpoint split)" % (
                    fmt((F(bid) + F(ask)) / 2), side)
            elif legacy:
                d += "; at/beyond %s -> %s side" % (side, side)
            else:
                e = F(eps)
                d += "; ask-eps=%s bid+eps=%s -> %s side" % (
                    fmt(F(ask) - e), fmt(F(bid) + e), side)
        else:
            d += "; -> %s (%s)" % (st, rs)
    add(rid, group, ref, pend, tags, {"op": "sign", "quote": quote, "trade": trade},
        params, sign_expected_dict(st, rs, side), d, open_item)


# ---------------------------------------------------------------- build
def build():
    rng = random.Random(SEED)
    # ---- (a) spread, valid and invalid
    spread_row("A01", "spread_oc4", "OC 2.2 OC4", None, ["legacy_mode"], "1.0000", "1.0200")
    spread_row("A02", "spread_oc4", "OC 2.2 OC4", None, ["legacy_mode"], "0.9500", "1.0500")
    spread_row("A03", "spread_oc4", "OC 2.2 OC4", None, ["legacy_mode"], "2.0000", "2.5000")
    spread_row("A04", "spread_oc4", "OC 2.2 OC4", None, [], "0.0100", "0.0200")
    spread_row("A05", "spread_oc4", "OC 2.2 OC4", None, [], "4.9500", "5.0500")
    spread_row("A06", "spread_oc4", "OC 2.2 OC4", None, [], "0.0100", "0.0101")
    spread_row("A07", "spread_oc4", "OC 2.3 invalid quote", 2, [], "0.0000", "0.0500",
               note="bid not above 0")
    spread_row("A08", "spread_oc4", "OC 2.3 invalid quote", 2, [], "-0.0100", "0.0500",
               note="negative bid")
    spread_row("A09", "spread_oc4", "OC 2.3 invalid quote", None, [], None, "1.0000",
               note="one-sided: bid null")
    spread_row("A10", "spread_oc4", "OC 2.3 invalid quote", None, [], "1.0000", None,
               note="one-sided: ask null")
    spread_row("A11", "spread_oc4", "OC 2.3 gates, data capability", None, [], None, None,
               nullrec=True, note="no quote record")
    spread_row("A12", "spread_oc4", "OC 2.3 crossed", None, [], "1.0500", "1.0000")
    spread_row("A13", "spread_oc4", "OC 2.3 invalid vs locked precedence", 2, [],
               "0.0000", "0.0000", note="bid 0 == ask 0; invalid first by assumption")
    spread_row("A14", "spread_oc4", "OC 2.3 invalid vs crossed precedence", 2, [],
               "-2.0000", "-3.0000", note="bid<=0 and ask<bid; invalid first by assumption")
    spread_row("A15", "spread_oc4", "OC 2.3 invalid quote (both null in a record)", None, [],
               None, None, note="record present, both fields null")
    for i in range(12):
        bi = rng.randint(1, 99999)
        ai = bi + rng.randint(1, 500)
        spread_row("A%02d" % (16 + i), "spread_oc4", "OC 2.2 OC4 (seeded random)", None,
                   ["seeded"], dec4(bi), dec4(ai))
    # ---- (b) locked
    spread_row("B01", "locked_g2", "OC 2.3 locked market", 1, [], "2.0000", "2.0000")
    spread_row("B02", "locked_g2", "OC 2.3 locked market", 1, [], "0.0500", "0.0500")
    spread_row("B03", "locked_g2", "OC 2.3 locked market", 1, [], "0.0001", "0.0001")
    sign_row("B04", "locked_g2", "DSR req 1 option A: signing unaffected", 1, [], "2.0000",
             "2.0000", "2.0100", eps="0.0000")
    sign_row("B05", "locked_g2", "DSR req 1 option A: signing unaffected", 1, [], "2.0000",
             "2.0000", "1.9900", eps="0.0000")
    sign_row("B06", "locked_g2", "DSR req 1: trade at the locked price", 1, [], "2.0000",
             "2.0000", "2.0000", eps="0.0000")
    # ---- (e) touch policy
    base = ("10.0000", "10.1000")
    cases = [
        ("E01", "10.1000", "0.0100", None), ("E02", "10.1100", "0.0100", None),
        ("E03", "10.2000", "0.0100", None),
        ("E04", "10.0900", "0.0100", None),
        ("E05", "10.0899", "0.0100", None), ("E06", "10.0000", "0.0100", None),
        ("E07", "9.9900", "0.0100", None),
        ("E08", "10.0100", "0.0100", None),
        ("E09", "10.0101", "0.0100", None), ("E10", "10.0500", "0.0100", None),
        ("E11", "10.0999", "0.0000", None), ("E12", "10.1000", "0.0000", None),
        ("E13", "10.0001", "0.0000", None), ("E14", "10.0000", "0.0000", None),
    ]
    for rid, px, eps, oi in cases:
        sign_row(rid, "touch_f13_f16", "Flow F13-F16, DSR req 8 option A", None, [],
                 base[0], base[1], px, eps=eps, open_item=oi)
    sign_row("E15", "touch_f13_f16", "OC 2.3 invalid quote, DSR req 2 option A", 2, [],
             "0.0000", "0.0500", "0.0500")
    sign_row("E16", "touch_f13_f16", "OC 2.3 invalid quote, DSR req 2 option A", 2, [],
             "0.0000", "0.0500", "0.0000")
    sign_row("E17", "touch_f13_f16", "OC 2.3 invalid quote", None, [], None, "10.1000",
             "10.1000")
    sign_row("E18", "touch_f13_f16", "OC 2.3 crossed (scope for signing unclear)", None, [],
             "10.1000", "10.0000", "10.1000")
    sign_row("E19", "touch_f13_f16", "Flow 2.3 unusable quote", None, [], None, None,
             "10.1000", nullrec=True)
    sign_row("E20", "touch_f13_f16", "Flow F13-F16 right-independent", None, [], base[0],
             base[1], "10.0000", right="put")
    # ---- (f) quote age
    for rid, age, oi in [("Q01", 2 * S + 999999999, None), ("Q02", 3 * S, None),
                         ("Q03", 3 * S + 1, None), ("Q04", 3 * S + 1000000, None),
                         ("Q05", 1, None), ("Q06", 10 * S, None)]:
        sign_row(rid, "quote_age", "Flow 2.3 quote within 3 s, DSR req 8", None, [],
                 base[0], base[1], "10.1000", qt=-age)
    sign_row("Q07", "quote_age", "Flow 2.3 quote within 3 s", None, [], base[0], base[1],
             "10.0000", qt=-3 * S)
    sign_row("Q08", "quote_age", "Flow 2.3 quote within 3 s", None, [], base[0], base[1],
             "10.0000", qt=-(3 * S + 1))
    spread_row("Q09", "quote_age", "OC 2.3 stale quote (10 s, PO ruling Q4)", None, [],
               "1.0000", "1.0200", t=-10 * S)
    spread_row("Q10", "quote_age", "OC 2.3 stale quote (10 s, PO ruling Q4)", None, [],
               "1.0000", "1.0200", t=-(10 * S + 1))
    spread_row("Q11", "quote_age", "OC 2.3 stale (3 s limit does not apply to spread)", None,
               [], "1.0000", "1.0200", t=-(3 * S + 1))
    # ---- aggregates
    def agg_row(rid, pend, trades, oi=None, note=""):
        ask = bid = unc = f13 = f14 = F(0)
        out_t = []
        for tr in trades:
            quote = tr["quote"]
            prem = F(tr["price"]) * tr["size"] * 100
            st, rs, side = exp_sign(quote, tr["price"], 0, "0.0100", 3 * S)
            out_t.append({"price": tr["price"], "size": tr["size"], "right": tr["right"],
                          "t_rel_ns": 0, "quote": quote})
            if side == "ask":
                ask += prem
                if tr["right"] == "call":
                    f13 += prem
                else:
                    f14 += prem
            elif side == "bid":
                bid += prem
                if tr["right"] == "put":
                    f13 += prem
                else:
                    f14 += prem
            else:
                unc += prem
        cl = ask + bid
        tot = cl + unc
        val = {"ask_premium": fmt(ask), "bid_premium": fmt(bid),
               "unclassified_premium": fmt(unc), "classified_premium": fmt(cl),
               "call_ask_plus_put_bid_premium": fmt(f13),
               "put_ask_plus_call_bid_premium": fmt(f14),
               "unclassified_share_of_total": fmt(unc / tot)}
        if cl == 0:
            val["ask_share_of_classified"] = None
            val["bid_share_of_classified"] = None
            reason = "no_classified_premium"
            shares_status = "unavailable"
        else:
            val["ask_share_of_classified"] = fmt(ask / cl)
            val["bid_share_of_classified"] = fmt(bid / cl)
            reason = None
            shares_status = "available"
        d = ("premium=price*size*100 per print; ask=%s bid=%s unclassified=%s; "
             "classified=%s total=%s; F13=call-ask+put-bid=%s F14=put-ask+call-bid=%s%s"
             % (fmt(ask), fmt(bid), fmt(unc), fmt(cl), fmt(tot), fmt(f13), fmt(f14), note))
        add(rid, "aggregate_f13_f16", "Flow F13-F16, 2.3 unclassified", pend, [],
            {"op": "sign_aggregate", "trades": out_t},
            {"inside_spread": "unknown", "epsilon": "0.0100", "max_quote_age_ns": 3 * S},
            {"status": shares_status, "reason": reason, "value": val,
             "labels": {"ask_premium": "ask-side proxy", "bid_premium": "bid-side proxy"}},
            d, oi)

    q1 = {"bid": "10.0000", "ask": "10.1000", "t_rel_ns": -S}
    agg_row("S01", None, [
        {"price": "10.1000", "size": 2, "right": "call", "quote": q1},
        {"price": "10.0000", "size": 3, "right": "put", "quote": q1},
        {"price": "10.0000", "size": 1, "right": "call", "quote": q1},
        {"price": "10.1000", "size": 1, "right": "put", "quote": q1},
        {"price": "10.0500", "size": 4, "right": "call", "quote": q1},
        {"price": "10.0700", "size": 1, "right": "put", "quote": q1}])
    agg_row("S02", None, [
        {"price": "10.0500", "size": 2, "right": "call", "quote": q1},
        {"price": "10.0600", "size": 3, "right": "put", "quote": q1}])
    agg_row("S03", 2, [
        {"price": "10.1000", "size": 1, "right": "call",
         "quote": {"bid": "10.0000", "ask": "10.1000", "t_rel_ns": -4 * S}},
        {"price": "0.0500", "size": 10, "right": "put",
         "quote": {"bid": "0.0000", "ask": "0.0500", "t_rel_ns": -S}},
        {"price": "10.1000", "size": 1, "right": "call", "quote": q1}])
    # ---- (c) window_end
    def prints_dict(lst):
        return [{"t_rel_ns": t, "right": r, "price": p, "size": z, "multiplier": m}
                for (t, r, p, z, m) in lst]

    def win_row(rid, pend, tags, plist, L, end, oi=None, text=""):
        std = [x for x in plist if x[4] == 100]
        if end is None:
            wend = max(x[0] for x in std)
            mode = "legacy last-print anchor"
        else:
            wend = end
            mode = "explicit window_end"
        wstart = wend - L
        inc = [x for x in std if wstart <= x[0] <= wend]
        call = sum((F(x[2]) * x[3] * 100 for x in inc if x[1] == "call"), F(0))
        put = sum((F(x[2]) * x[3] * 100 for x in inc if x[1] == "put"), F(0))
        params = {"window_ns": L}
        if end is not None:
            params["window_end_ns"] = end
        val = {"total_premium": fmt(call + put), "call_premium": fmt(call),
               "put_premium": fmt(put), "window_start_ns": wstart, "window_end_ns": wend,
               "included_count": len(inc),
               "excluded_nonstandard_count": len(plist) - len(std)}
        d = ("%s: window=[%d,%d]; included=%s; call=%s put=%s total=%s%s" % (
            mode, wstart, wend, [x[0] for x in inc], fmt(call), fmt(put),
            fmt(call + put), text))
        add(rid, "window_end_f3", "Flow F3, PO plan V2 s1 F3", pend, tags,
            {"op": "window_premium", "prints": prints_dict(plist)}, params,
            {"status": "available", "reason": None, "value": val}, d, oi)

    a = (-100 * S, "call", "1.0000", 10, 100)
    b = (-85 * S, "put", "2.0000", 6, 100)
    c = (-30 * S, "call", "0.5000", 30, 100)
    L = 60 * S
    win_row("C01", None, [], [a, b, c], L, 0, text="; b (-85s) and a (-100s) are outside")
    win_row("C02", None, ["legacy_mode"], [a, b, c], L, None,
            text="; anchor is last print -30s so b is inside; differs from C01")
    d0 = (0, "call", "1.0000", 5, 100)
    win_row("C03", None, [], [c, d0], L, 0, oi="window_closed_both_ends", text="; print exactly at window_end is included")
    win_row("C04", None, ["legacy_mode"], [c, d0], L, None, text="; last print at 0 == T")
    e1 = (1, "call", "1.0000", 7, 100)
    win_row("C05", None, [], [c, e1], L, 0, oi="window_closed_both_ends", text="; print at +1ns is after window_end")
    win_row("C06", None, ["legacy_mode"], [c, e1], L, None,
            text="; anchor moves to +1ns so the later print is inside")
    st0 = (-60 * S, "put", "1.0000", 8, 100)
    win_row("C07", None, [], [st0, c], L, 0, oi="window_closed_both_ends",
            text="; print exactly at start included (closed window, assumed by analogy to Q3)")
    st1 = (-60 * S - 1, "put", "1.0000", 8, 100)
    win_row("C08", None, [], [st1, c], L, 0, text="; print 1ns before start excluded")
    ns = (-10 * S, "call", "1.0000", 10, 10)
    win_row("C09", None, [], [ns, c], L, 0, text="; non-standard multiplier excluded")
    win_row("C10", None, [], [a, b, c], L, -30 * S,
            text="; explicit end earlier than T is honoured; c exactly at end included")
    win_row("C11", None, [], [a, b], 60 * S, 0,
            text="; no print in window")

    # ---- (d) single reference
    def pr(i, right, strike, exp, spot, price, size):
        return {"id": i, "right": right, "strike": strike, "expiry": exp, "spot": spot,
                "price": price, "size": size}

    D1 = [pr("p1", "call", "105.0000", "2026-03-03", "100.0000", "1.0000", 10),
          pr("p2", "put", "95.0000", "2026-03-04", "100.0000", "2.0000", 5),
          pr("p3", "call", "100.0000", "2026-03-05", "100.0000", "1.0000", 20),
          pr("p4", "call", "110.0000", None, "100.0000", "1.0000", 10),
          pr("p5", "put", "90.0000", "2026-03-02", None, "1.0000", 30),
          pr("p6", "call", "100.0000", None, None, "1.0000", 10)]
    D2 = D1[:5]
    civil = "2026-03-02"

    def day(s):
        y, m, dd = [int(x) for x in s.split("-")]
        return y * 372 + m * 31 + dd  # only used for 2026-03 differences below

    def dte(s):
        return int(s[-2:]) - 2

    def shares(plist, thr_short=None, thr_otm=None):
        tot = sum(F(x["price"]) * x["size"] * 100 for x in plist)
        prem = lambda x: F(x["price"]) * x["size"] * 100

        def blk(sel_ref, sel_hit, thr):
            ref = [x for x in plist if sel_ref(x)]
            hit = [x for x in ref if sel_hit(x)]
            refp = sum((prem(x) for x in ref), F(0))
            hp = sum((prem(x) for x in hit), F(0))
            if not ref:
                return {"status": "unavailable", "reason": "missing_reference",
                        "premium": None, "share": None, "coverage": "0", "fired": None,
                        "lower_bound": True, "label": None}
            o = {"status": "available", "reason": None, "premium": fmt(hp),
                 "share": fmt(hp / tot), "coverage": fmt(refp / tot), "fired": None,
                 "lower_bound": True, "label": None}
            if thr is not None:
                o["fired"] = hp / tot >= F(thr)
                o["label"] = "at least %s%% of total eligible premium" % fmt(F(thr) * 100)
            return o
        has_e = lambda x: x["expiry"] is not None
        has_s = lambda x: x["spot"] is not None
        both = lambda x: has_e(x) and has_s(x)
        short = lambda x: dte(x["expiry"]) <= 2
        otm = lambda x: (F(x["strike"]) > F(x["spot"])) if x["right"] == "call" else (
            F(x["strike"]) < F(x["spot"]))
        return {"total_premium": fmt(tot),
                "short_dte": blk(has_e, short, thr_short),
                "otm": blk(has_s, otm, thr_otm),
                "joint_short_dte": blk(both, short, thr_short),
                "joint_otm": blk(both, otm, thr_otm)}

    def ref_row(rid, pend, tags, plist, ts=None, to=None, oi=None, d=""):
        params = {"short_dte_max_days": 2}
        if ts is not None:
            params["short_min_share"] = ts
        if to is not None:
            params["otm_min_share"] = to
        add(rid, "single_ref_f5_f6", "Flow F5/F6, DSR req 6 option A", pend, tags,
            {"op": "single_ref_shares", "civil_date": civil, "prints": plist}, params,
            {"status": "available", "reason": None, "value": shares(plist, ts, to)}, d, oi)

    ref_row("D01", None, [], D1, d=(
        "premium p1..p6 = 1000,1000,2000,1000,3000,1000 total 9000. short (expiry known: "
        "p1,p2,p3,p5=7000 referenced): p1(dte1)+p2(dte2)+p5(dte0)=5000 -> 5000/9000=5/9, "
        "coverage 7000/9000=7/9. otm (spot known: p1..p4=5000): p1 call 105>100, p2 put 95<100, "
        "p4 call 110>100 = 3000 -> 1/3, p3 ATM strict not OTM, coverage 5/9. joint (both: "
        "p1,p2,p3=4000): short 2000 -> 2/9, otm 2000 -> 2/9, coverage 4/9"))
    ref_row("D02", None, [], D1, ts="0.7000", d=(
        "short share 5/9=0.5556 < 0.7 so not fired (denominator is total 9000); a "
        "referenced-only denominator would give 5000/7000=0.7143 >= 0.7 and wrongly fire"))
    ref_row("D03", None, [], D1, ts="0.5000", d="5/9 >= 0.5 fired; label states lower bound")
    ref_row("D04", None, [], D2, to="0.3750", d=(
        "D2 = p1..p5 total 8000; otm 3000/8000=0.375 equals threshold -> fired (at least)"))
    ref_row("D05", None, [], D2, to="0.3751", d="0.375 < 0.3751 -> not fired")
    nospot = [dict(x, spot=None) for x in D1]
    ref_row("D06", None, [], nospot, d=(
        "no print has a spot: otm and joint unavailable missing_reference; short still "
        "available: 5000/9000 over referenced 7000 coverage 7/9"))
    noexp = [dict(x, expiry=None) for x in D1]
    ref_row("D07", None, [], noexp, d=(
        "no print has an expiry: short and joint unavailable missing_reference; otm "
        "available 3000/9000=1/3"))
    dd = [pr("q1", "call", "100.0000", "2026-03-02", None, "1.0000", 10),
          pr("q2", "call", "100.0000", "2026-03-04", None, "1.0000", 10),
          pr("q3", "call", "100.0000", "2026-03-05", None, "1.0000", 10)]
    ref_row("D08", None, [], dd, d=(
        "dte 0,2,3 each 1000 total 3000; dte<=2 inclusive -> 2000/3000=2/3; dte 3 excluded; "
        "no spot needed"))
    ss = [pr("r1", "put", "99.0000", None, "100.0000", "1.0000", 10),
          pr("r2", "call", "101.0000", None, "100.0000", "1.0000", 10),
          pr("r3", "put", "100.0000", None, "100.0000", "1.0000", 10),
          pr("r4", "call", "100.0000", None, "100.0000", "1.0000", 10)]
    ref_row("D09", None, [], ss, d=(
        "otm needs spot only: put 99<100 yes, call 101>100 yes, put 100 and call 100 are at "
        "the money not OTM: 2000/4000=1/2; short unavailable missing_reference"))
    JD = [pr("j1", "call", "105.0000", "2026-03-03", "100.0000", "1.0000", 10),
          pr("j2", "call", "105.0000", "2026-03-03", None, "2.0000", 10),
          pr("j3", "call", "110.0000", None, "100.0000", "4.0000", 10),
          pr("j4", "call", "90.0000", "2026-03-07", "100.0000", "8.0000", 10)]
    add("D10", "single_ref_f5_f6", "Flow F5/F6 joint outputs retained (legacy amounts)", None,
        ["legacy_mode"], {"op": "joint_amounts", "civil_date": civil, "prints": JD},
        {"short_dte_max_days": 2},
        {"status": "available", "reason": None,
         "value": {"joint_short_premium": "1000", "joint_otm_premium": "1000",
                   "reference_premium": "9000"}},
        "j1 1000 (both refs, dte1, call 105>100), j2 2000 (expiry only), j3 4000 (spot only, "
        "call 110>100), j4 8000 (both refs, dte5, call 90<100 so in the money). Joint needs "
        "both: reference=j1+j4=9000; joint short=j1=1000; joint otm=j1=1000. A single-reference "
        "reading would give short 3000 and otm 5000")
    spread_row("R01", "gate_precedence", "OC 2.3 precedence (PO ruling)", None, [], None,
               "1.0000", t=-11 * S, note="stale and one-sided: invalid first")
    spread_row("R02", "gate_precedence", "OC 2.3 precedence (PO ruling)", None, [], "1.0500",
               "1.0000", t=-11 * S, note="stale and crossed: crossed first")
    spread_row("R03", "gate_precedence", "OC 2.3 precedence (PO ruling)", 1, [], "2.0000",
               "2.0000", t=-11 * S, note="stale and locked: locked first")
    sign_row("R04", "gate_precedence", "OC 2.3 precedence (PO ruling)", None, [], None,
             "10.1000", "10.1000", qt=-4 * S)
    sign_row("R05", "gate_precedence", "OC 2.3 precedence (PO ruling)", None, [], "10.1000",
             "10.0000", "10.1000", qt=-4 * S)
    sign_row("R06", "gate_precedence", "locked does not block signing; staleness does", 1, [],
             "2.0000", "2.0000", "2.0100", qt=-4 * S, eps="0.0000")
    sign_row("T01", "quote_timing", "quote at the same ns as the trade", None, [], base[0],
             base[1], "10.1000", qt=0)
    ROWS[-1]["tags"].append("same_ns_quote_usable")
    sign_row("T02", "quote_timing", "quote after the trade", None, [], base[0], base[1],
             "10.1000", qt=1)
    sign_row("E21", "touch_f13_f16", "ambiguous_touch (PO ruling)", None, [], base[0],
             base[1], "10.0500", eps="0.0600")
    sign_row("E22", "touch_f13_f16", "wide epsilon, price beyond ask only", None, [], base[0],
             base[1], "10.1000", eps="0.0600")
    sign_row("E23", "touch_f13_f16", "wide epsilon, price near bid only", None, [], base[0],
             base[1], "10.0300", eps="0.0600")

    # ---- (g) G5 gate coverage
    def gate_row(rid, pend, ups, oi=None, d=""):
        cnt = sum(1 for (t, cd) in ups if cd == "regular" and -300 * S <= t <= 0)
        ok = cnt >= 5
        add(rid, "g5_coverage", "OC 2.3 low quote coverage, PO ruling Q3, DSR req 3", pend, [],
            {"op": "quote_coverage_gate",
             "updates": [{"t_rel_ns": t, "cond": cd} for (t, cd) in ups]},
            {"window_ns": 300 * S, "min_regular_updates": 5},
            {"status": "available" if ok else "unavailable",
             "reason": None if ok else "low_quote_coverage",
             "value": {"regular_update_count": cnt},
             "blocks": [] if ok else ["OC6"]},
            "regular updates in [-300e9,0]: %d, minimum 5 -> %s%s" % (
                cnt, "ok" if ok else "low_quote_coverage", d), oi)

    R = "regular"
    X = "excluded"
    gate_row("G01", 3, [(-250 * S, R), (-200 * S, R), (-100 * S, R), (-50 * S, R)])
    gate_row("G02", 3, [(-250 * S, R), (-200 * S, R), (-100 * S, R), (-50 * S, R),
                        (-10 * S, R)])
    gate_row("G03", 3, [(-250 * S, R), (-200 * S, R), (-100 * S, R), (-50 * S, R),
                        (-10 * S, X)], d="; excluded-condition update not counted")
    gate_row("G04", 3, [(-300 * S, R), (-200 * S, R), (-100 * S, R), (-50 * S, R),
                        (-10 * S, R)], d="; update exactly 300 s before T is inside")
    gate_row("G05", 3, [(-300 * S - 1, R), (-200 * S, R), (-100 * S, R), (-50 * S, R),
                        (-10 * S, R)], d="; update 300 s + 1 ns before T is outside")
    gate_row("G06", 3, [(-250 * S, R), (-200 * S, R), (-100 * S, R), (-50 * S, R),
                        (0, R)], d="; update exactly at T is inside")
    gate_row("G07", 3, [(-250 * S, R), (-200 * S, R), (-100 * S, R), (-50 * S, R),
                        (1, R)], d="; update after T not counted")
    gate_row("G08", 3, [(-250 * S, R), (-240 * S, X), (-200 * S, R), (-150 * S, X),
                        (-100 * S, R), (-50 * S, X), (-20 * S, R), (-10 * S, R),
                        (-5 * S, R)])
    gate_row("G09", 3, [])
    gate_row("G10", 3, [(-250 * S, X), (-240 * S, X), (-230 * S, X), (-220 * S, X),
                        (-210 * S, X), (-200 * S, R)], d="; five excluded updates give 1")

    # ---- labels
    labs = sorted({v for r in ROWS for v in [r["expected"].get("label")] if v})
    for r in ROWS:
        for v in (r["expected"].get("labels") or {}).values():
            labs.append(v)
    labs = sorted(set(labs))
    add("L01", "label_check", "DSR req 8, plan V2 s1 F13-F16, V3 s5", None, [],
        {"op": "label_check", "labels": labs},
        {"allowed_labels": ALLOWED_LABELS, "forbidden_words": FORBIDDEN},
        {"status": "available", "reason": None,
         "value": {"labels_allowed_only": True, "forbidden_word_hits": []}},
        "every label emitted by the touch rows is exactly 'ask-side proxy' or "
        "'bid-side proxy' and matches no forbidden word (case-insensitive, whole word)")
    add("L02", "label_check", "DSR req 8 (checker control)", None, ["checker_control"],
        {"op": "label_check", "labels": ["bullish-side proxy", "bid-side proxy",
                                         "Buy-side proxy"]},
        {"allowed_labels": ALLOWED_LABELS, "forbidden_words": FORBIDDEN},
        {"status": "available", "reason": None,
         "value": {"labels_allowed_only": False,
                   "forbidden_word_hits": ["bullish", "buy"]}},
        "control: a label with direction wording must be flagged; bullish and Buy hit, "
        "'bullish-side proxy' also not in the allowed set")

    # ---- (h) legacy default rows
    qlg = ("10.0000", "10.1000")
    for rid, px in [("H01", "10.1000"), ("H02", "10.1100"), ("H03", "10.0000"),
                    ("H04", "9.9900"), ("H05", "10.0600"), ("H06", "10.0400")]:
        sign_row(rid, "legacy_default", "workers-vs-conditions F13 note, conflict item 4",
                 None, ["legacy_mode"], qlg[0], qlg[1], px, legacy=True,
                 open_item="legacy_midpoint_epsilon_not_probed")
    sign_row("H07", "legacy_default", "legacy: bid<=0 already rejected", 2, ["legacy_mode"],
             "0.0000", "0.0500", "0.0500", legacy=True)
    sign_row("H08", "legacy_default", "legacy: locked quote still signs", 1,
             ["legacy_mode"], "2.0000", "2.0000", "2.0100", legacy=True)
    sign_row("H09", "legacy_default", "legacy: locked quote still signs", 1,
             ["legacy_mode"], "2.0000", "2.0000", "1.9900", legacy=True)
    add("H10", "legacy_default", "legacy: trade exactly at the midpoint", None, ["legacy_mode"],
        {"op": "sign", "quote": {"bid": "10.0000", "ask": "10.1000", "t_rel_ns": -S},
         "trade": {"price": "10.0500", "size": 1, "t_rel_ns": 0, "right": "call"}}, {},
        {"status": "not_asserted", "reason": None, "side": None, "label": None, "value": None},
        "midpoint tie side is not derivable from the design; record legacy bytes later. "
        "Legacy age-limit assertion intentionally omitted.",
        "legacy_midpoint_tie_side_unknown")
    for r in ROWS:
        if r["id"] in ("H07", "H08", "H09"):
            r["pending_design_request"] = None
            continue
        lst = list(r["pending_design_request"] or [])
        op = r["inputs"]["op"]
        if (r["group"] != "legacy_default" and
                op in ("sign", "sign_aggregate", "label_check") and 8 not in lst):
            lst.append(8)
        if r["id"] in ["D%02d" % k for k in range(1, 10)] and 6 not in lst:
            lst.append(6)
        r["pending_design_request"] = sorted(lst) or None
    for r in ROWS:
        r["needs_byte_mapping"] = "legacy_mode" in r["tags"]

    mutations = MUTATIONS
    return {"dataset": {"provenance": "SYNTHETIC", "seed": SEED,
                        "generator": "gen_p1.py",
                        "authored_by": "Tester, from design text only",
                        "time_unit": "integer ns relative to T (evaluation time = 0)",
                        "value_format": "exact decimal string if terminating else p/q",
                        "closed_reasons": REASONS, "qualification_label":
                        "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12"},
            "rows": ROWS, "mutations": mutations}


MUTATIONS = [
    {"id": "M01", "desc": "spread treats bid = 0 as valid", "rows": ["A07", "A13"]},
    {"id": "M02", "desc": "spread_bps divides by ask instead of midpoint", "rows": ["A01", "A02"]},
    {"id": "M03", "desc": "locked quote gives spread 0 available", "rows": ["B01", "B02", "B03"]},
    {"id": "M04", "desc": "crossed quote returns an absolute-value spread", "rows": ["A12"]},
    {"id": "M05", "desc": "locked gate also withholds signing (request 1 option B)", "rows": ["B04", "B05"]},
    {"id": "M06", "desc": "inside-spread price split at midpoint instead of unclassified", "rows": ["E05", "E09", "E10", "S01", "S02"]},
    {"id": "M07", "desc": "epsilon comparison exclusive at the boundary", "rows": ["E04", "E08"]},
    {"id": "M08", "desc": "quote age 3 s treated as stale (exclusive limit)", "rows": ["Q02", "Q07"]},
    {"id": "M09", "desc": "quote age limit off by one ns (3 s + 1 ns passes)", "rows": ["Q03", "Q08"]},
    {"id": "M10", "desc": "window_end ignored, last-print anchor always used", "rows": ["C01", "C05"]},
    {"id": "M11", "desc": "window excludes a print exactly at window_end", "rows": ["C03"]},
    {"id": "M12", "desc": "window includes a print after window_end", "rows": ["C05"]},
    {"id": "M13", "desc": "window start boundary exclusive", "rows": ["C07"]},
    {"id": "M14", "desc": "share denominator is referenced premium only", "rows": ["D02", "D01"]},
    {"id": "M15", "desc": "short share also requires spot (joint coupling)", "rows": ["D06", "D01"]},
    {"id": "M16", "desc": "OTM share also requires expiry", "rows": ["D07", "D09"]},
    {"id": "M17", "desc": "joint output needs only one of civil date and spot", "rows": ["D01", "D10"]},
    {"id": "M18", "desc": "short-dated limit off by one day (dte <= 3)", "rows": ["D08"]},
    {"id": "M19", "desc": "coverage counts excluded-condition updates", "rows": ["G03", "G10"]},
    {"id": "M20", "desc": "coverage window excludes update at exactly -300 s", "rows": ["G04"]},
    {"id": "M21", "desc": "coverage minimum is 6 instead of 5", "rows": ["G02"]},
    {"id": "M22", "desc": "unclassified premium added to ask side", "rows": ["S01", "S02"]},
    {"id": "M23", "desc": "signing accepts bid = 0", "rows": ["E15", "E16", "S03"]},
    {"id": "M24", "desc": "ask-side label reads 'bullish-side proxy'", "rows": ["E01", "E02"]},
    {"id": "M25", "desc": "share threshold exclusive (> instead of >=)", "rows": ["D04"]},
    {"id": "M26", "desc": "window_end hard-coded to T instead of the request value", "rows": ["C10"]},
    {"id": "M27", "desc": "OTM test inclusive at the money", "rows": ["D01", "D09"]},
    {"id": "M29", "desc": "joint short amount needs expiry only", "rows": ["D10"]},
    {"id": "M30", "desc": "double touch (locked or wide epsilon) resolved as ask", "rows": ["B06", "E21"]},
    {"id": "M31", "desc": "stale checked before validity gates", "rows": ["R01", "R02", "R04", "R05"]},
    {"id": "M32", "desc": "quote at the same ns as the trade is unusable", "rows": ["T01"]},
    {"id": "M33", "desc": "quote after the trade is usable", "rows": ["T02"]},
    {"id": "M28", "desc": "coverage gate also blocks nothing (blocks list empty)", "rows": ["G01"]},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="p1_cases.json")
    args = ap.parse_args()
    data = build()
    with open(args.out, "w", newline="\n", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=1, ensure_ascii=True) + "\n")


if __name__ == "__main__":
    main()
