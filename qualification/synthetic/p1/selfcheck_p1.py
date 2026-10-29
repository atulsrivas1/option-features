#!/usr/bin/env python3
"""Independent self-check: recomputes every expected value from raw row inputs with a
separately written reference model, then applies each listed mutation to that model and
confirms the mapped rows fail. Stdlib only. Usage: python selfcheck_p1.py p1_cases.json"""
import json
import re
import sys
from fractions import Fraction as F
from math import gcd

SEC = 10 ** 9


def show(x):
    x = F(x)
    n, d = x.numerator, x.denominator
    t = d
    for p in (2, 5):
        while t % p == 0:
            t //= p
    if t != 1:
        return str(n) + "/" + str(d)
    s = 0
    while (n * 10 ** s) % d:
        s += 1
    v = abs(n) * 10 ** s // d
    txt = str(v)
    if s:
        txt = txt.rjust(s + 1, "0")
        txt = txt[:-s] + "." + txt[-s:]
    return ("-" if n < 0 else "") + txt


def num(s):
    return None if s is None else F(s)


def gate(q, mut):
    """returns reason or None for quote gates (no age)."""
    if q is None:
        return "no_quote"
    b, a = num(q["bid"]), num(q["ask"])
    if b is None and a is None:
        return "no_quote"
    if b is None or a is None:
        return "invalid_quote"
    bad_bid = (b < 0) if "M01" in mut else (b <= 0)
    if bad_bid:
        return "invalid_quote"
    if a < b:
        return "crossed_market"
    if a == b:
        return "locked_market"
    return None


def op_spread(inp, par, mut):
    q = inp["quote"]
    r = gate(q, mut)
    if "M31" in mut and q and r != "no_quote" and -q["t_rel_ns"] > par["stale_limit_ns"]:
        return {"status": "unavailable", "reason": "stale_quote", "value": None}
    if "M01" in mut and q and r is None and False:
        pass
    if r in ("invalid_quote", "no_quote"):
        return {"status": "unavailable", "reason": r, "value": None}
    b, a = num(q["bid"]), num(q["ask"])
    if r == "crossed_market":
        if "M04" in mut:
            sp = b - a
            mid = (a + b) / 2
            return {"status": "available", "reason": None,
                    "value": {"spread": show(sp), "midpoint": show(mid),
                              "spread_bps": show(sp / mid * 10000)}}
        return {"status": "unavailable", "reason": r, "value": None}
    if r == "locked_market":
        if "M03" in mut:
            return {"status": "available", "reason": None,
                    "value": {"spread": "0", "midpoint": show(a), "spread_bps": "0"}}
        return {"status": "unavailable", "reason": r, "value": None}
    if -q["t_rel_ns"] > par["stale_limit_ns"]:
        return {"status": "unavailable", "reason": "stale_quote", "value": None}
    sp = a - b
    mid = (a + b) / 2
    den = a if "M02" in mut else mid
    return {"status": "available", "reason": None,
            "value": {"spread": show(sp), "midpoint": show(mid),
                      "spread_bps": show(sp / den * 10000)}}


def side_of(q, price, tt, par, mut):
    """returns (status, reason, side)"""
    price = F(price)
    if q is None:
        return ("unclassified", "no_quote", None)
    if "M33" not in mut and (q["t_rel_ns"] >= tt if "M32" in mut else q["t_rel_ns"] > tt):
        return ("unclassified", "no_quote", None)
    b, a = num(q["bid"]), num(q["ask"])
    if "M31" in mut and tt - q["t_rel_ns"] > par.get("max_quote_age_ns", 3 * SEC):
        return ("unclassified", "stale_quote", None)
    if b is None and a is None:
        return ("unclassified", "no_quote", None)
    if b is None or a is None:
        return ("unclassified", "invalid_quote", None)
    if (b < 0 if "M23" in mut else b <= 0):
        return ("unclassified", "invalid_quote", None)
    if a < b:
        return ("unclassified", "crossed_market", None)
    if a == b and "M05" in mut:
        return ("unclassified", "locked_market", None)
    age = tt - q["t_rel_ns"]
    lim = par.get("max_quote_age_ns", 3 * SEC)
    if "legacy" in par:
        lim = 3 * SEC
    if "M08" in mut:
        stale = age >= lim
    elif "M09" in mut:
        stale = age > lim + 1
    else:
        stale = age > lim
    if stale:
        return ("unclassified", "stale_quote", None)
    if "inside_spread" not in par:
        # legacy default: touch then midpoint split
        if price >= a:
            return ("available", None, "ask")
        if price <= b:
            return ("available", None, "bid")
        return ("available", None, "ask" if price > (a + b) / 2 else "bid")
    eps = F(par["epsilon"])
    if "M07" in mut:
        at_ask, at_bid = price > a - eps, price < b + eps
        if price >= a:
            at_ask = True
        if price <= b:
            at_bid = True
    else:
        at_ask, at_bid = price >= a - eps, price <= b + eps
    if at_ask and at_bid:
        return ("available", None, "ask") if "M30" in mut else ("unclassified", "ambiguous_touch", None)
    if at_ask:
        return ("available", None, "ask")
    if at_bid:
        return ("available", None, "bid")
    if "M06" in mut:
        return ("available", None, "ask" if price > (a + b) / 2 else "bid")
    return ("unclassified", "inside_spread", None)


def label(side, mut):
    if side == "ask":
        return "bullish-side proxy" if "M24" in mut else "ask-side proxy"
    if side == "bid":
        return "bid-side proxy"
    return None


def op_sign(inp, par, mut):
    st, rs, sd = side_of(inp["quote"], inp["trade"]["price"], inp["trade"]["t_rel_ns"], par, mut)
    return {"status": st, "reason": rs, "side": sd, "label": label(sd, mut), "value": None}


def op_agg(inp, par, mut):
    ask = bid = unc = f13 = f14 = F(0)
    for t in inp["trades"]:
        pm = F(t["price"]) * t["size"] * 100
        st, rs, sd = side_of(t["quote"], t["price"], t["t_rel_ns"], par, mut)
        if st == "unclassified" and "M22" in mut:
            sd = "ask"
        if sd == "ask":
            ask += pm
            if t["right"] == "call":
                f13 += pm
            else:
                f14 += pm
        elif sd == "bid":
            bid += pm
            if t["right"] == "put":
                f13 += pm
            else:
                f14 += pm
        else:
            unc += pm
    if "M22" in mut:
        unc = F(0)
        for t in inp["trades"]:
            st, _, _ = side_of(t["quote"], t["price"], t["t_rel_ns"], par, mut)
            if st != "available":
                unc += F(t["price"]) * t["size"] * 100
        # M22 counts inside-spread premium on the ask side; recompute honestly
        ask = bid = f13 = f14 = F(0)
        for t in inp["trades"]:
            pm = F(t["price"]) * t["size"] * 100
            st, rs, sd = side_of(t["quote"], t["price"], t["t_rel_ns"], par, mut)
            if rs == "inside_spread":
                sd = "ask"
            if sd == "ask":
                ask += pm
                f13 += pm if t["right"] == "call" else 0
                f14 += pm if t["right"] == "put" else 0
            elif sd == "bid":
                bid += pm
                f13 += pm if t["right"] == "put" else 0
                f14 += pm if t["right"] == "call" else 0
        unc = F(0)
        for t in inp["trades"]:
            pm = F(t["price"]) * t["size"] * 100
            st, rs, sd = side_of(t["quote"], t["price"], t["t_rel_ns"], par, mut)
            if sd is None and rs != "inside_spread":
                unc += pm
    cl = ask + bid
    tot = cl + unc
    v = {"ask_premium": show(ask), "bid_premium": show(bid),
         "unclassified_premium": show(unc), "classified_premium": show(cl),
         "call_ask_plus_put_bid_premium": show(f13),
         "put_ask_plus_call_bid_premium": show(f14),
         "unclassified_share_of_total": show(unc / tot),
         "ask_share_of_classified": show(ask / cl) if cl else None,
         "bid_share_of_classified": show(bid / cl) if cl else None}
    return {"status": "available" if cl else "unavailable",
            "reason": None if cl else "no_classified_premium", "value": v,
            "labels": {"ask_premium": "ask-side proxy", "bid_premium": "bid-side proxy"}}


def op_window(inp, par, mut):
    L = par["window_ns"]
    std = [p for p in inp["prints"] if p["multiplier"] == 100]
    if "window_end_ns" in par and "M10" not in mut:
        end = 0 if "M26" in mut else par["window_end_ns"]
    else:
        end = max(p["t_rel_ns"] for p in std)
    start = end - L

    def inside(t):
        lo = t > start if "M13" in mut else t >= start
        hi = t < end if "M11" in mut else t <= end
        if "M12" in mut:
            hi = True
        return lo and hi
    inc = [p for p in std if inside(p["t_rel_ns"])]
    call = sum((F(p["price"]) * p["size"] * 100 for p in inc if p["right"] == "call"), F(0))
    put = sum((F(p["price"]) * p["size"] * 100 for p in inc if p["right"] == "put"), F(0))
    return {"status": "available", "reason": None,
            "value": {"total_premium": show(call + put), "call_premium": show(call),
                      "put_premium": show(put), "window_start_ns": start,
                      "window_end_ns": end, "included_count": len(inc),
                      "excluded_nonstandard_count": len(inp["prints"]) - len(std)}}


def days_to(exp, civil):
    y1, m1, d1 = map(int, exp.split("-"))
    y0, m0, d0 = map(int, civil.split("-"))
    import datetime
    return (datetime.date(y1, m1, d1) - datetime.date(y0, m0, d0)).days


def op_refs(inp, par, mut):
    ps = inp["prints"]
    pm = lambda p: F(p["price"]) * p["size"] * 100
    total = sum((pm(p) for p in ps), F(0))
    mx = par["short_dte_max_days"] + (1 if "M18" in mut else 0)

    def block(ref, hit, thr):
        rp = [p for p in ps if ref(p)]
        if not rp:
            return {"status": "unavailable", "reason": "missing_reference", "premium": None,
                    "share": None, "coverage": "0", "fired": None, "lower_bound": True,
                    "label": None}
        hp = sum((pm(p) for p in rp if hit(p)), F(0))
        refp = sum((pm(p) for p in rp), F(0))
        den = refp if "M14" in mut else total
        share = hp / den
        o = {"status": "available", "reason": None, "premium": show(hp),
             "share": show(share), "coverage": show(refp / total), "fired": None,
             "lower_bound": True, "label": None}
        if thr is not None:
            t = F(thr)
            o["fired"] = (share > t) if "M25" in mut else (share >= t)
            o["label"] = "at least %s%% of total eligible premium" % show(t * 100)
        return o
    e = lambda p: p["expiry"] is not None
    s = lambda p: p["spot"] is not None
    short = lambda p: days_to(p["expiry"], inp["civil_date"]) <= mx
    if "M27" in mut:
        otm = lambda p: (F(p["strike"]) >= F(p["spot"])) if p["right"] == "call" else (
            F(p["strike"]) <= F(p["spot"]))
    else:
        otm = lambda p: (F(p["strike"]) > F(p["spot"])) if p["right"] == "call" else (
            F(p["strike"]) < F(p["spot"]))
    ts, to = par.get("short_min_share"), par.get("otm_min_share")
    sref = (lambda p: e(p) and s(p)) if "M15" in mut else e
    oref = (lambda p: e(p) and s(p)) if "M16" in mut else s
    jref = (lambda p: e(p) or s(p)) if "M17" in mut else (lambda p: e(p) and s(p))
    # joint blocks need both values to classify; with OR (M17) missing values break, so guard
    def jshort(p):
        return p["expiry"] is not None and short(p)

    def jotm(p):
        return p["spot"] is not None and otm(p)
    return {"status": "available", "reason": None, "value": {
        "total_premium": show(total),
        "short_dte": block(sref, short, ts), "otm": block(oref, otm, to),
        "joint_short_dte": block(jref, jshort, ts), "joint_otm": block(jref, jotm, to)}}


def op_gate(inp, par, mut):
    lo = -par["window_ns"] + (1 if "M20" in mut else 0)
    n = 0
    for u in inp["updates"]:
        if (u["cond"] == "regular" or "M19" in mut) and lo <= u["t_rel_ns"] <= 0:
            n += 1
    need = 6 if "M21" in mut else par["min_regular_updates"]
    ok = n >= need
    blocks = [] if ok else ["OC6"]
    if "M28" in mut:
        blocks = []
    return {"status": "available" if ok else "unavailable",
            "reason": None if ok else "low_quote_coverage",
            "value": {"regular_update_count": n}, "blocks": blocks}


def op_label(inp, par, mut):
    hits = []
    allowed = True
    for lab in inp["labels"]:
        if lab not in par["allowed_labels"]:
            allowed = False
        for w in par["forbidden_words"]:
            if re.search(r"\b" + w + r"\b", lab, re.I):
                hits.append(w)
    return {"status": "available", "reason": None,
            "value": {"labels_allowed_only": allowed,
                      "forbidden_word_hits": sorted(set(hits), key=hits.index)}}


def op_joint(inp, par, mut):
    ps = inp["prints"]
    pm = lambda p: F(p["price"]) * p["size"] * 100
    mx = par["short_dte_max_days"]
    both = lambda p: p["expiry"] is not None and p["spot"] is not None
    ref = sum((pm(p) for p in ps if both(p) or ("M17" in mut and (p["expiry"] or p["spot"]))), F(0))
    sh = sum((pm(p) for p in ps if p["expiry"] is not None and (both(p) or "M29" in mut)
              and days_to(p["expiry"], inp["civil_date"]) <= mx), F(0))
    ot = sum((pm(p) for p in ps if both(p) and ((F(p["strike"]) > F(p["spot"]))
              if p["right"] == "call" else (F(p["strike"]) < F(p["spot"])))), F(0))
    return {"status": "available", "reason": None,
            "value": {"joint_short_premium": show(sh), "joint_otm_premium": show(ot),
                      "reference_premium": show(ref)}}


OPS = {"joint_amounts": op_joint, "spread": op_spread, "sign": op_sign, "sign_aggregate": op_agg,
       "window_premium": op_window, "single_ref_shares": op_refs,
       "quote_coverage_gate": op_gate, "label_check": op_label}


def run_row(row, mut):
    par = dict(row["params"])
    if row["group"] == "legacy_default":
        par = {}
    return OPS[row["inputs"]["op"]](row["inputs"], par, mut)


def matches(row, got):
    exp = row["expected"]
    keys = set(exp) - {"blocks"} if False else set(exp)
    for k in keys:
        if k not in got or got[k] != exp[k]:
            return False
    return True


def main():
    data = json.load(open(sys.argv[1]))
    assert data["dataset"]["provenance"] == "SYNTHETIC"
    rows = data["rows"]
    bad = []
    for r in rows:
        if r["expected"].get("status") == "not_asserted":
            continue
        if not matches(r, run_row(r, set())):
            bad.append(r["id"])
    print("rows:", len(rows), "baseline mismatches:", bad)
    labs = set()
    for r in rows:
        if r["expected"].get("label"):
            labs.add(r["expected"]["label"])
        for v in (r["expected"].get("labels") or {}).values():
            labs.add(v)
    l01 = [r for r in rows if r["id"] == "L01"][0]
    if set(l01["inputs"]["labels"]) != labs:
        bad.append("L01-union")
    ok = not bad
    # mutations
    for m in data["mutations"]:
        failing = []
        for r in rows:
            if r["expected"].get("status") == "not_asserted":
                continue
            try:
                g = run_row(r, {m["id"]})
            except Exception:
                failing.append(r["id"])
                continue
            if not matches(r, g):
                failing.append(r["id"])
        missing = [x for x in m["rows"] if x not in failing]
        print(m["id"], "caught by", len(failing), "rows; mapped:", m["rows"],
              "MISSING" if missing else "ok", missing or "")
        if missing:
            ok = False
    print("SELF-CHECK", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
