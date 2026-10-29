#!/usr/bin/env python3
"""M1 chain IV / ATM IV / 30-day constant-maturity IV fixture generator.  PROVENANCE: SYNTHETIC.

TEST ORACLE, NOT LIBRARY CODE.  Prices are flat-vol European Black-Scholes values
priced from a stated sigma (continuous r and q, ACT/365 calendar-day year), quantised to
a 4-decimal mid with a +/-0.0010 quote.  Expected IVs come from the stated sigma, never
from a solver.  Rules: PO_R28_DESIGN_RULINGS Q5, Q6 and section 2.  stdlib only.
    python gen_m1_iv.py --out <relative dir>      (writes m1_iv_cases.json, then self-checks)

TOLERANCE (fixed before any run): absolute 1e-4 on IV (0.01 vol points) for contract IV,
ATM IV and 30-day IV; absolute 1e-6 on the forward.  Quote quantisation is verified by
the self-check to cost under 2e-5.
"""
import argparse
import json
import math
import os
import random
import sys
from fractions import Fraction as F

SEED = 20261029
PROV = "SYNTHETIC"
QUAL = ("mock-data qualification only: passed on independently authored synthetic fixtures and synthetic "
        "workloads, Windows x64, CPython 3.12")
S = 10 ** 9
STALE = 10 * S
YEAR = 365
TOL_IV = "0.0001"
TOL_FWD = "0.000001"
APPROX = "approximate: European model on an American-style contract"
EXACT = "exact-model"
ROWS = []


def dec(fr, places=4):
    fr = F(fr)
    neg = fr < 0
    a = abs(fr) * 10 ** places
    n = (2 * a.numerator + a.denominator) // (2 * a.denominator)
    s = str(n).rjust(places + 1, "0")
    out = s[:-places] + "." + s[-places:]
    return ("-" if neg and n else "") + out


# ---------------------------------------------------------------- pricing (generator side)
def ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bs(S0, K, T, r, q, v, right):
    sq = v * math.sqrt(T)
    d1 = (math.log(S0 / K) + (r - q + 0.5 * v * v) * T) / sq
    d2 = d1 - sq
    if right == "call":
        return S0 * math.exp(-q * T) * ncdf(d1) - K * math.exp(-r * T) * ncdf(d2)
    return K * math.exp(-r * T) * ncdf(-d2) - S0 * math.exp(-q * T) * ncdf(-d1)


def vega(S0, K, T, r, q, v):
    sq = v * math.sqrt(T)
    d1 = (math.log(S0 / K) + (r - q + 0.5 * v * v) * T) / sq
    return S0 * math.exp(-q * T) * math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi) * math.sqrt(T)


# ---------------------------------------------------------------- chain builder
def contract(days, right, K, sigma, style, S0, r, q, kind="ok"):
    """kind: ok, locked, crossed, stale, bid0, oneside, excluded."""
    T = days / float(YEAR)
    p = bs(float(S0), float(K), T, float(r), float(q), float(sigma), right)
    assert p >= 0.02, (days, right, K, p)
    pr = F(dec(F(p), 4))
    h = F("0.0010")
    bid, ask, ev, cond = pr - h, pr + h, -2 * S, "regular"
    if kind == "locked":
        bid, ask = pr, pr
    elif kind == "crossed":
        bid, ask = pr + h, pr - h
    elif kind == "stale":
        ev = -30 * S
    elif kind == "excluded":
        cond = "excluded"
    c = {"id": "%dd-%s-%s" % (days, right[0].upper(), dec(F(K), 4)), "expiry_days": days, "right": right,
         "strike": dec(F(K), 4), "style": style, "bid": dec(bid), "ask": dec(ask), "event_ns": ev,
         "known_at_ns": ev, "condition": cond}
    if kind == "bid0":
        c["bid"] = "0.0000"
    if kind == "oneside":
        c["ask"] = None
    return c


def chain(S0, r, q, specs):
    """specs: list of dict(days, strikes, sig(K,right)->Fraction, style, mods{(right,K):kind|'absent'})."""
    cs, truth = [], {}
    for sp in specs:
        for K in sp["strikes"]:
            for right in ("call", "put"):
                kind = sp.get("mods", {}).get((right, K), "ok")
                if kind == "absent":
                    continue
                sg = F(sp["sig"](F(K), right))
                c = contract(sp["days"], right, F(K), sg, sp["style"], S0, r, q, kind)
                cs.append(c)
                truth[c["id"]] = dec(sg, 4)
    return cs, truth


def flat(base, off="0.0100"):
    return lambda K, right: F(base) + (-F(off) if right == "call" else F(off))


def smile(base, slope, per):
    """base + slope*(K-100)/per for both rights, call -0.01, put +0.01."""
    return lambda K, right: F(base) + F(slope) * (K - 100) / F(per) + (F("-0.01") if right == "call" else F("0.01"))


def strikes_for(days):
    return ["99", "100", "101"] if days < 21 else ["95", "100", "105"]


# ---------------------------------------------------------------- oracle
def qclass(c):
    b, a = c["bid"], c["ask"]
    if b is None or a is None or F(b) <= 0:
        return "invalid_quote"
    b, a = F(b), F(a)
    return "crossed_market" if a < b else ("locked_market" if a == b else "ok")


def gate(c, T=0, lim=STALE):
    if c["event_ns"] > T or c["known_at_ns"] > T:
        return "no_quote"
    if c["condition"] != "regular":
        return "excluded_condition"
    k = qclass(c)
    if k != "ok":
        return k
    if T - c["event_ns"] > lim:
        return "stale_quote"
    return None


def fwd(S0, r, q, days):
    return float(S0) * math.exp((float(r) - float(q)) * days / float(YEAR))


def label_for(styles, mut):
    if None in styles and "V12" not in mut:
        return None, "style_unknown"
    if "american" in styles or None in styles:
        return (None if "V5" in mut else APPROX), None
    return EXACT, None


def analyze(row, mut=frozenset()):
    inp, truth = row["inputs"], row["oracle"]["sigma"]
    S0, r, q = inp["spot"], inp["rate"], inp["dividend_yield"]
    lim = row["request"]["stale_limit_ns"]
    by = {}
    for c in inp["contracts"]:
        by.setdefault(c["expiry_days"], {}).setdefault(F(c["strike"]), {})[c["right"]] = c
    info = {}
    for d, strikes in by.items():
        elig = {}
        for K, rs in strikes.items():
            e = {rt: c for rt, c in rs.items() if gate(c, 0, lim) is None or "V10" in mut}
            if e:
                elig[K] = e
        cands = [K for K, e in elig.items() if len(e) == 2 or ("V9" in mut)]
        Fw = fwd(S0, r, q, d)
        ref = float(S0) if "V1" in mut else Fw
        atm = None
        if cands:
            if "V2" in mut:
                atm = min(cands, key=lambda K: (abs(F(K) - F(ref)), -K))
            else:
                atm = min(cands, key=lambda K: (abs(F(K) - F(ref)), K))
        anyk = list(strikes.keys())
        near_any = min(anyk, key=lambda K: (abs(F(K) - F(Fw)), K)) if anyk else None
        info[d] = dict(strikes=strikes, elig=elig, F=Fw, atm=atm, near_any=near_any)
    return info


def contract_results(row, mut=frozenset()):
    info = analyze(row, mut)
    truth = row["oracle"]["sigma"]
    lim = row["request"]["stale_limit_ns"]
    out = {}
    for c in row["inputs"]["contracts"]:
        d, K = c["expiry_days"], F(c["strike"])
        i = info[d]
        g = gate(c, 0, lim) if "V10" not in mut else None
        if g:
            out[c["id"]] = dict(status="unavailable", reason=g, iv=None, label=None)
            continue
        if c["style"] is None and "V12" not in mut:
            out[c["id"]] = dict(status="unavailable", reason="style_unknown", iv=None, label=None)
            continue
        if c["style"] in ("american", None):
            ref = i["atm"] if "V13" in mut else i["near_any"]
            itm = (c["right"] == "call" and F(K) < F(i["F"])) or (c["right"] == "put" and F(K) > F(i["F"]))
            if itm and K != ref and "V6" not in mut:
                out[c["id"]] = dict(status="unavailable", reason="american_itm", iv=None, label=None)
                continue
            lab = None if "V5" in mut else APPROX
        else:
            lab = EXACT
        out[c["id"]] = dict(status="value", reason=None, iv=truth[c["id"]], label=lab)
    return out


def atm_for(row, d, mut=frozenset()):
    info = analyze(row, mut)
    truth = row["oracle"]["sigma"]
    if d not in info or info[d]["atm"] is None:
        return dict(status="unavailable", reason="no_atm_strike", strike=None, forward=None, call_iv=None,
                    put_iv=None, iv=None, label=None)
    i = info[d]
    K = i["atm"]
    e = i["elig"][K]
    styles = {c["style"] for c in e.values()}
    lab, rs = label_for(styles, mut)
    if rs:
        return dict(status="unavailable", reason=rs, strike=dec(K), forward="%.8f" % i["F"], call_iv=None,
                    put_iv=None, iv=None, label=None)
    sc = F(truth[e["call"]["id"]]) if "call" in e else None
    sp = F(truth[e["put"]["id"]]) if "put" in e else None
    if "V3" in mut:
        iv = sc
    else:
        vals = [x for x in (sc, sp) if x is not None]
        iv = sum(vals) / len(vals)
    return dict(status="value", reason=None, strike=dec(K), forward="%.8f" % i["F"],
                call_iv=None if sc is None else dec(sc, 4), put_iv=None if sp is None else dec(sp, 4), iv=dec(iv, 6), label=lab)


def iv30_for(row, mut=frozenset(), target=30):
    info = analyze(row, mut)
    listed = sorted(info)
    pool = sorted(d for d in info if info[d]["atm"] is not None) if "V14" in mut else listed
    fail = lambda r, used=(): dict(status="unavailable", reason=r, iv=None, label=None, expiries_used=list(used), method=None)
    if target in pool and "V8" not in mut:
        if info[target]["atm"] is None:
            return fail("no_atm_strike")
        chosen, method = [target], "as_is"
    else:
        lo = [d for d in pool if d < target]
        hi = [d for d in pool if d > target]
        if lo and hi:
            chosen = [max(lo), min(hi)]
        elif "V7" in mut and len(lo) >= 2:
            chosen = lo[-2:]
        elif "V7" in mut and len(hi) >= 2:
            chosen = hi[:2]
        else:
            return fail("no_bracketing_expiry")
        if any(info[d]["atm"] is None for d in chosen):
            return fail("no_bracketing_expiry", chosen)
        method = "variance_interpolation"
    parts = [atm_for(row, d, mut) for d in chosen]
    for p in parts:
        if p["status"] != "value":
            return fail(p["reason"], chosen)
    labs = [p["label"] for p in parts]
    lab = APPROX if APPROX in labs or (labs and None in labs) else EXACT
    if "V5" in mut and lab == APPROX:
        lab = None
    ivs = [F(p["iv"]) for p in parts]
    if method == "as_is":
        val = float(ivs[0])
    else:
        d1, d2 = chosen
        if "V4" in mut:
            val = float(ivs[0] + (ivs[1] - ivs[0]) * F(target - d1, d2 - d1))
        else:
            w1 = float(ivs[0]) ** 2 * d1 / YEAR
            w2 = float(ivs[1]) ** 2 * d2 / YEAR
            w = w1 + (w2 - w1) * (target - d1) / float(d2 - d1)
            val = math.sqrt(w / (target / float(YEAR)))
    return dict(status="value", reason=None, iv="%.10f" % val, label=lab, expiries_used=chosen, method=method)


def expected_for(row, mut=frozenset()):
    op = row["op"]
    if op == "contract_iv":
        return {"contracts": contract_results(row, mut), "tolerance_iv": TOL_IV}
    if op == "atm_iv":
        e = atm_for(row, row["request"]["expiry_days"], mut)
        e["tolerance_iv"], e["tolerance_forward"] = TOL_IV, TOL_FWD
        return e
    e = iv30_for(row, mut, row["request"]["target_days"])
    e["tolerance_iv"] = TOL_IV
    return e


# ---------------------------------------------------------------- row assembly
def add(id_, op, group, ref, case, S0, r, q, specs, req=None, tags=(), alts=None, note="", gating=True):
    cs, truth = chain(S0, r, q, specs)
    rng = random.Random("%d-%s" % (SEED, id_))
    rng.shuffle(cs)
    request = {"stale_limit_ns": STALE, "year_basis_days": YEAR, "time_to_expiry": "calendar days, expiry N*24h after cutoff",
               "price_input": "midpoint of bid and ask", "cutoff_ns": 0}
    request.update(req or {})
    row = {"id": id_, "group": group, "design_ref": ref, "case": case, "op": op,
           "inputs": {"T_ns": 0, "spot": S0, "rate": r, "dividend_yield": q, "contracts": cs},
           "request": request, "oracle": {"sigma": truth, "note": "stated flat-vol sigma per contract; not an input to the library"}}
    t = list(tags) + ["pending:req11" if op in ("atm_iv", "iv_30d") else "pending:req12"]
    if any(c["style"] != "european" for c in cs):
        t.append("pending:req12")
    if gating:
        row["gating"] = True
        row["expected"] = expected_for(row)
        row["derivation"] = (note + " " if note else "") + derive(row)
    else:
        row["gating"] = False
        row["expected"] = None
        row["alternatives"] = alts(row)
        row["derivation"] = note
        t.append("pending:ambiguity")
    row["tags"] = sorted(set(t))
    ROWS.append(row)
    check_vega(row)


def derive(row):
    e = row["expected"]
    if row["op"] == "contract_iv":
        return "each contract priced from its stated sigma (ACT/365, r=%s q=%s); American ITM test: call K<F, put K>F, exempt the strike nearest F." % (
            row["inputs"]["rate"], row["inputs"]["dividend_yield"])
    if row["op"] == "atm_iv":
        return "F=S*exp((r-q)T)=%s; nearest eligible-both-rights strike (ties lower) = %s; ATM IV = mean(call %s, put %s) = %s." % (
            e["forward"], e["strike"], e["call_iv"], e["put_iv"], e["iv"]) if e["status"] == "value" else "no usable ATM strike or style: %s" % e["reason"]
    if e["status"] != "value":
        return "unavailable: %s" % e["reason"]
    return "expiries used %s (%s); variance interpolation w=IV^2*d/365 linear in days to 30d, IV=sqrt(w/(30/365)) = %s." % (
        e["expiries_used"], e["method"], e["iv"])


def check_vega(row):
    S0, r, q = float(row["inputs"]["spot"]), float(row["inputs"]["rate"]), float(row["inputs"]["dividend_yield"])
    byid = {c["id"]: c for c in row["inputs"]["contracts"]}
    for cid, sg in row["oracle"]["sigma"].items():
        c = byid[cid]
        if gate(c) is None:
            T = c["expiry_days"] / float(YEAR)
            assert vega(S0, float(c["strike"]), T, r, q, float(sg)) >= 4.0, (row["id"], cid)


def build():
    S0, r, q = "100.0000", "0.0300", "0.0100"
    k3 = ["95", "100", "105"]

    def sp(days, base="0.2000", style="european", strikes=None, mods=None, sig=None):
        return dict(days=days, strikes=strikes or strikes_for(days), sig=sig or flat(base), style=style, mods=mods or {})

    # ---- per-contract IV
    add("IV-C01", "contract_iv", "contract_iv", "ruling Q5; OC 2.2 OC3 (European)", "flat vol European, call 0.21 put 0.19",
        S0, r, q, [sp(30, "0.2000", sig=lambda K, rt: F("0.21") if rt == "call" else F("0.19"))])
    add("IV-C02", "contract_iv", "contract_iv", "ruling section 2 items 1-2", "American: OTM and nearest-to-forward approximate, ITM american_itm",
        S0, r, q, [sp(30, style="american")], note="F=100.1645: call 95 ITM, call 100 nearest, call 105 OTM; put 95 OTM, put 100 OTM, put 105 ITM.")
    add("IV-C03", "contract_iv", "contract_iv", "ruling section 2 item 3", "unknown style (ITM and OTM alike)",
        S0, r, q, [sp(30, style=None)])
    add("IV-C04", "contract_iv", "contract_iv", "OC 2.3 gates on modeled values", "quote gates block modeled values",
        S0, r, q, [sp(30, mods={("call", "95"): "locked", ("put", "95"): "crossed", ("call", "100"): "stale",
                                ("put", "100"): "bid0", ("call", "105"): "oneside"})],
        tags=["pending:req1", "pending:req2"])
    add("IV-C05", "contract_iv", "contract_iv", "ruling section 2", "American, seven strikes",
        S0, r, q, [sp(30, style="american", strikes=["95", "97.5", "100", "102.5", "105"])])
    add("IV-C06", "contract_iv", "contract_iv", "ruling section 2", "American, strike exactly at forward (r=q)",
        S0, "0.0200", "0.0200", [sp(30, style="american")], note="F=100 exactly: call 100 is neither ITM nor OTM.")
    add("IV-C07", "contract_iv", "contract_iv", "ruling Q5 smile", "European smile, 60 days",
        S0, r, q, [sp(60, style="european", strikes=["90", "95", "100", "105", "110"],
                      sig=lambda K, rt: F("0.20") + F("0.002") * abs(K - 100) + (F("-0.01") if rt == "call" else F("0.01")))])
    add("IV-C08", "contract_iv", "contract_iv", "ruling Q5", "European, one year, r=0.10 q=0",
        S0, "0.1000", "0.0000", [sp(365, strikes=["100", "105", "110", "115"])])
    add("IV-C09", "contract_iv", "contract_iv", "PO ruling D13", "nearest strike overall (call 100 absent): put 105 is ITM",
        S0, r, q, [sp(30, style="american", mods={("call", "100"): "absent"})],
        note="nearest-to-forward is the single strike nearest F across all listed strikes (100), not the ATM-IV candidate (105).")

    # ---- ATM IV
    atm1 = lambda base: lambda K, rt: F(base) + F("0.002") * (K - 100) / 5 + (F("-0.01") if rt == "call" else F("0.01"))
    rq = {"expiry_days": 30}
    add("IV-A01", "atm_iv", "atm_iv", "ruling Q5", "European nearest forward, mean of call and put",
        S0, r, q, [sp(30, sig=atm1("0.20"))], req=rq)
    tie = lambda K, rt: F("0.20") + F("0.01") * (K - 100) + (F("-0.01") if rt == "call" else F("0.01"))
    add("IV-A02", "atm_iv", "atm_iv", "ruling Q5 ties", "tie between 100 and 101 goes to 100",
        "100.5000", "0.0200", "0.0200", [sp(30, strikes=["99", "100", "101", "102"], sig=tie)], req=rq,
        note="r=q so F=S=100.5 exactly.")
    add("IV-A03", "atm_iv", "atm_iv", "ruling Q5 forward", "forward 110.52, strike 110 not spot-nearest 100",
        S0, "0.1000", "0.0000", [sp(365, strikes=["100", "105", "110", "115", "120"], sig=atm1("0.20"))],
        req={"expiry_days": 365})
    add("IV-A04", "atm_iv", "atm_iv", "ruling Q5 both rights", "call missing at the nearest strike",
        S0, r, q, [sp(30, sig=atm1("0.20"), mods={("call", "100"): "absent"})], req=rq)
    add("IV-A05", "atm_iv", "atm_iv", "ruling Q5 eligible", "put crossed at the nearest strike",
        S0, r, q, [sp(30, sig=atm1("0.20"), mods={("put", "100"): "crossed"})], req=rq)
    add("IV-A06", "atm_iv", "atm_iv", "ruling Q5", "no strike has both rights",
        S0, r, q, [sp(30, mods={("put", "95"): "absent", ("put", "100"): "absent", ("call", "105"): "absent"})], req=rq)
    add("IV-A07", "atm_iv", "atm_iv", "ruling Q5", "requested expiry has no contracts",
        S0, r, q, [sp(30)], req={"expiry_days": 60})
    add("IV-A08", "atm_iv", "atm_iv", "ruling Q5 / OC 2.3 stale", "all quotes stale",
        S0, r, q, [sp(30, mods={(rt, k): "stale" for rt in ("call", "put") for k in k3})], req=rq)
    add("IV-A09", "atm_iv", "atm_iv", "ruling section 2", "American ATM labelled approximate (call 100 is ITM side but nearest)",
        S0, r, q, [sp(30, style="american", sig=atm1("0.20"))], req=rq)
    add("IV-A10", "atm_iv", "atm_iv", "ruling section 2 item 3", "unknown style",
        S0, r, q, [sp(30, style=None)], req=rq)
    mixed = [dict(days=30, strikes=k3, sig=flat("0.20"), style="european")]
    cs, truth = chain(S0, r, q, mixed)
    for c in cs:
        if c["right"] == "put":
            c["style"] = "american"
    row = {"id": "IV-A12", "op": "atm_iv", "group": "atm_iv", "design_ref": "ruling section 2 (pending)",
           "case": "call European, put American at the ATM strike",
           "inputs": {"T_ns": 0, "spot": S0, "rate": r, "dividend_yield": q, "contracts": cs},
           "request": {"stale_limit_ns": STALE, "year_basis_days": YEAR, "cutoff_ns": 0, "expiry_days": 30,
                       "price_input": "midpoint of bid and ask", "time_to_expiry": "calendar days, expiry N*24h after cutoff"},
           "oracle": {"sigma": truth, "note": "stated flat-vol sigma per contract; not an input to the library"}}
    row.update(gating=True, expected=expected_for(row), derivation="PO ruling D13: any American leg at the ATM strike gives the approximate label.",
               tags=["pending:req12"])
    ROWS.append(row)
    add("IV-A17", "atm_iv", "atm_iv", "ruling Q5; parity-consistent chain", "put-call parity consistent: same sigma on both rights",
        S0, r, q, [sp(30, strikes=k3, sig=lambda K, rt: F("0.2200"))], req=rq,
        note="C - P = S*exp(-qT) - K*exp(-rT) at every strike, so call IV = put IV = 0.22 (checked by the self-check).")
    add("IV-A13", "atm_iv", "atm_iv", "ruling Q5", "two expiries in the chain; request uses only 30d",
        S0, r, q, [sp(30, sig=atm1("0.20")), sp(60, "0.3000")], req=rq)
    add("IV-A14", "atm_iv", "atm_iv", "ruling Q5 eligible", "put stale at the nearest strike",
        S0, r, q, [sp(30, sig=atm1("0.20"), mods={("put", "100"): "stale"})], req=rq)
    add("IV-A15", "atm_iv", "atm_iv", "ruling Q5 ties", "tie with a smile; upper strike has a different IV",
        "100.5000", "0.0200", "0.0200", [sp(30, strikes=["100", "101"], sig=tie)], req=rq)
    add("IV-A16", "atm_iv", "atm_iv", "ruling Q5 forward", "forward 100.1645 picks 100.25 over spot-nearest 100",
        S0, r, q, [sp(30, strikes=["99.75", "100", "100.25", "100.5"],
                      sig=lambda K, rt: F("0.20") + F("0.04") * (K - 100) + (F("-0.01") if rt == "call" else F("0.01")))], req=rq)

    # ---- 30-day IV
    R30 = {"target_days": 30}

    def t30(id_, case, bases, style="european", inelig=(), tags=(), gating=True, alts=None, ref="ruling Q6", note=""):
        specs = []
        for d, b in bases.items():
            mods = {("put", k): "absent" for k in strikes_for(d)} if d in inelig else {}
            specs.append(sp(d, b, style=style, mods=mods))
        add(id_, "iv_30d", "iv_30d", ref, case, S0, r, q, specs, req=R30, tags=tags, gating=gating, alts=alts, note=note)

    t30("IV-T01", "21d 0.20 and 49d 0.30 interpolate in total variance", {21: "0.2000", 49: "0.3000"},
        note="linear-in-IV would be 0.2321, variance gives 0.2574.")
    t30("IV-T02", "exact 30d expiry used as is", {21: "0.2000", 30: "0.2500", 49: "0.3000"})
    t30("IV-T03", "all expiries below 30d", {7: "0.1800", 21: "0.2000"})
    t30("IV-T04", "all expiries above 30d", {35: "0.2500", 60: "0.3000"})
    t30("IV-T05", "single expiry at 29d", {29: "0.2000"})
    t30("IV-T06", "single expiry at 31d", {31: "0.2000"})
    t30("IV-T07", "four expiries, bracket is 21d and 35d", {7: "0.1800", 21: "0.2200", 35: "0.2600", 60: "0.3000"})
    t30("IV-T08", "29d and 31d", {29: "0.2000", 31: "0.3000"})
    t30("IV-T09", "upper bracket has no eligible strike", {21: "0.2000", 49: "0.3000"}, inelig=(49,), ref="PO ruling D14")
    t30("IV-T10a", "American expiries: approximate label", {21: "0.2000", 49: "0.3000"}, style="american", ref="ruling section 2")
    t30("IV-T10b", "unknown style", {21: "0.2000", 49: "0.3000"}, style=None, ref="ruling section 2 item 3")
    t30("IV-T11", "14d and 91d", {14: "0.2200", 91: "0.2700"})
    t30("IV-T14", "only a 30d expiry", {30: "0.2500"})
    t30("IV-T16", "American exact 30d expiry", {30: "0.2500"}, style="american", ref="ruling section 2")
    t30("IV-T12", "21d ok, 49d ineligible, 60d ok: bracket is 21d/49d (D14)", {21: "0.2000", 49: "0.2500", 60: "0.3000"}, inelig=(49,),
        ref="PO ruling D14")
    t30("IV-T13", "30d expiry listed but no ATM strike: no_atm_strike, no fallback (D14)",
        {21: "0.2000", 30: "0.2500", 49: "0.3000"}, inelig=(30,), ref="PO ruling D14")

MUT = ["V1", "V2", "V3", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V12", "V13", "V14"]


def mutation_report():
    rep = {}
    for m in MUT:
        hits = []
        for row in ROWS:
            if not row["gating"]:
                continue
            got = expected_for(row, frozenset([m]))
            if got != row["expected"]:
                hits.append(row["id"])
        rep[m] = hits
    return rep


# ---------------------------------------------------------------- independent self-check
def px(Sv, K, T, r, q, v, right):
    sq = v * math.sqrt(T)
    d1 = (math.log(Sv / K) + (r - q) * T + 0.5 * v * v * T) / sq
    d2 = d1 - sq
    N = lambda x: 0.5 * math.erfc(-x / math.sqrt(2.0))
    call = Sv * math.exp(-q * T) * N(d1) - K * math.exp(-r * T) * N(d2)
    if right == "call":
        return call
    return call - Sv * math.exp(-q * T) + K * math.exp(-r * T)


def invert(price, Sv, K, T, r, q, right):
    lo, hi = 1e-4, 5.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if px(Sv, K, T, r, q, mid, right) < price:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def sc_iv(row):
    """Recompute everything from raw quotes by inversion; returns (per-contract, atm-by-expiry, iv30)."""
    inp = row["inputs"]
    Sv, r, q = float(inp["spot"]), float(inp["rate"]), float(inp["dividend_yield"])
    maxerr = 0.0
    per = {}
    byx = {}
    for c in inp["contracts"]:
        T = c["expiry_days"] / 365.0
        Fw = Sv * math.exp((r - q) * T)
        ok = (c["condition"] == "regular" and c["bid"] is not None and c["ask"] is not None and
              0 < float(c["bid"]) < float(c["ask"]) and 0 - c["event_ns"] <= row["request"]["stale_limit_ns"])
        iv = None
        if ok:
            mid = (float(c["bid"]) + float(c["ask"])) / 2
            iv = invert(mid, Sv, float(c["strike"]), T, r, q, c["right"])
            maxerr = max(maxerr, abs(iv - float(row["oracle"]["sigma"][c["id"]])))
        per[c["id"]] = (c, iv)
        byx.setdefault(c["expiry_days"], {}).setdefault(float(c["strike"]), {})[c["right"]] = (c, iv)
    atm = {}
    for d, ks in byx.items():
        T = d / 365.0
        Fw = Sv * math.exp((r - q) * T)
        good = sorted(k for k, rs in ks.items() if all(rt in rs and rs[rt][1] is not None for rt in ("call", "put")))
        if not good:
            atm[d] = None
            continue
        best = min(good, key=lambda k: (round(abs(k - Fw), 9), k))
        atm[d] = (best, Fw, ks[best]["call"], ks[best]["put"])
    return per, atm, maxerr


def selfcheck(doc):
    bad = []
    maxerr_all = 0.0
    for row in doc["rows"]:
        if not row["gating"]:
            continue
        per, atm, me = sc_iv(row)
        maxerr_all = max(maxerr_all, me)
        e = row["expected"]
        tol = float(TOL_IV)
        if row["op"] == "contract_iv":
            Sv = float(row["inputs"]["spot"])
            for cid, (c, iv) in per.items():
                ex = e["contracts"][cid]
                d = c["expiry_days"]
                Fw = Sv * math.exp((float(row["inputs"]["rate"]) - float(row["inputs"]["dividend_yield"])) * d / 365.0)
                lst = {float(x["strike"]) for x, _ in per.values() if x["expiry_days"] == d}
                nearest = min(lst, key=lambda kk: (round(abs(kk - Fw), 9), kk))
                if iv is None:
                    exp_reason = ex["reason"]
                    if ex["status"] != "unavailable" or exp_reason not in ("invalid_quote", "crossed_market", "locked_market", "stale_quote"):
                        bad.append((row["id"], cid, "gate mismatch", ex))
                    continue
                if c["style"] is None:
                    if ex["reason"] != "style_unknown":
                        bad.append((row["id"], cid, "style_unknown", ex))
                    continue
                k = float(c["strike"])
                itm = (c["right"] == "call" and k < Fw) or (c["right"] == "put" and k > Fw)
                if c["style"] == "american" and itm and k != nearest:
                    if ex["reason"] != "american_itm":
                        bad.append((row["id"], cid, "american_itm", ex))
                    continue
                want = APPROX if c["style"] == "american" else EXACT
                if ex["status"] != "value" or ex["label"] != want or abs(iv - float(ex["iv"])) > tol:
                    bad.append((row["id"], cid, "value", iv, ex))
        elif row["op"] == "atm_iv":
            a = atm.get(row["request"]["expiry_days"])
            if a is None:
                if e["reason"] != "no_atm_strike":
                    bad.append((row["id"], "atm none", e))
                continue
            k, Fw, (cc, civ), (pc, piv) = a
            styles = {cc["style"], pc["style"]}
            if None in styles:
                if e["reason"] != "style_unknown":
                    bad.append((row["id"], "style", e))
                continue
            want = APPROX if "american" in styles else EXACT
            if (abs(float(e["strike"]) - k) > 0 or abs(float(e["forward"]) - Fw) > float(TOL_FWD) or e["label"] != want
                    or abs(float(e["iv"]) - (civ + piv) / 2) > tol or abs(float(e["call_iv"]) - civ) > tol
                    or abs(float(e["put_iv"]) - piv) > tol):
                bad.append((row["id"], "atm", k, Fw, civ, piv, e))
        else:
            tgt = row["request"]["target_days"]
            listed = sorted({x["expiry_days"] for x, _ in per.values()})
            ivs = {d: (atm[d][2][1] + atm[d][3][1]) / 2 for d in listed if atm.get(d)}
            sty = lambda d: {atm[d][2][0]["style"], atm[d][3][0]["style"]}
            if tgt in listed:
                if not atm.get(tgt):
                    if e["reason"] != "no_atm_strike":
                        bad.append((row["id"], "exact30 no atm", e))
                    continue
                use, val = [tgt], ivs[tgt]
            else:
                lo = [d for d in listed if d < tgt]
                hi = [d for d in listed if d > tgt]
                if not lo or not hi:
                    if e["reason"] != "no_bracketing_expiry":
                        bad.append((row["id"], "nobr", e))
                    continue
                d1, d2 = max(lo), min(hi)
                if not atm.get(d1) or not atm.get(d2):
                    if e["reason"] != "no_bracketing_expiry":
                        bad.append((row["id"], "nobr inelig", e))
                    continue
                use = [d1, d2]
                w1, w2 = ivs[d1] ** 2 * d1, ivs[d2] ** 2 * d2
                w = w1 + (w2 - w1) * (tgt - d1) / (d2 - d1)
                val = math.sqrt(w / tgt)
            allsty = set().union(*[sty(d) for d in use])
            if None in allsty:
                if e["reason"] != "style_unknown":
                    bad.append((row["id"], "style30", e))
                continue
            want = APPROX if "american" in allsty else EXACT
            if e["status"] != "value" or e["label"] != want or abs(val - float(e["iv"])) > tol or e["expiries_used"] != use:
                bad.append((row["id"], "iv30", val, e))
    # hand-worked literals
    hand = {"IV-T01": math.sqrt((0.04 * 21 + (0.09 * 49 - 0.04 * 21) * 9 / 28.0) / 30.0),
            "IV-T02": 0.25, "IV-T08": math.sqrt((0.04 * 29 + (0.09 * 31 - 0.04 * 29) * 0.5) / 30.0),
            "IV-T07": math.sqrt((0.22 ** 2 * 21 + (0.26 ** 2 * 35 - 0.22 ** 2 * 21) * 9 / 14.0) / 30.0),
            "IV-T14": 0.25}
    for k, v in hand.items():
        row = next(r for r in doc["rows"] if r["id"] == k)
        if abs(float(row["expected"]["iv"]) - v) > 1e-9:
            bad.append((k, "hand value", v, row["expected"]["iv"]))
    for k, st in (("IV-A01", "100.0000"), ("IV-A02", "100.0000"), ("IV-A03", "110.0000"), ("IV-A04", "105.0000"),
                  ("IV-A16", "100.2500")):
        row = next(r for r in doc["rows"] if r["id"] == k)
        if row["expected"]["strike"] != st:
            bad.append((k, "hand strike", st, row["expected"]["strike"]))
    pr = next(r for r in doc["rows"] if r["id"] == "IV-A17")
    Sv, rr, qq = float(pr["inputs"]["spot"]), float(pr["inputs"]["rate"]), float(pr["inputs"]["dividend_yield"])
    mids = {}
    for c in pr["inputs"]["contracts"]:
        mids[(c["right"], c["strike"])] = (float(c["bid"]) + float(c["ask"])) / 2
    for k in {k for _, k in mids}:
        T = 30 / 365.0
        lhs = mids[("call", k)] - mids[("put", k)]
        rhs = Sv * math.exp(-qq * T) - float(k) * math.exp(-rr * T)
        if abs(lhs - rhs) > 2e-4:
            bad.append(("IV-A17", "parity", k, lhs, rhs))
    for m, hits in doc["mutation_report"].items():
        if not hits:
            bad.append((m, "mutant survives"))
    if maxerr_all > 2e-5:
        bad.append(("quantisation", maxerr_all))
    return bad, maxerr_all


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--no-check", action="store_true")
    a = ap.parse_args()
    build()
    for row in ROWS:
        if any(0 - c["event_ns"] > row["request"]["stale_limit_ns"] for c in row["inputs"]["contracts"]):
            row["tags"] = sorted(set(row["tags"]) | {"pending:req11"})
    ids = [r["id"] for r in ROWS]
    assert len(ids) == len(set(ids))
    doc = {"provenance": PROV, "qualification_label": QUAL, "generator": "gen_m1_iv.py", "seed": SEED, "schema_version": 1,
           "note": "Flat-vol European BS prices from stated sigma. Expected IVs are the stated sigmas (or exact functions of them). "
                   "Tolerance fixed before the run: IV 1e-4 absolute, forward 1e-6 absolute.",
           "tolerance": {"iv_abs": TOL_IV, "forward_abs": TOL_FWD}, "approx_label": APPROX, "exact_label": EXACT,
           "closed_reasons": ["excluded_condition", "invalid_quote", "crossed_market", "locked_market", "stale_quote", "no_quote",
                              "no_atm_strike", "no_bracketing_expiry", "american_itm", "style_unknown"],
           "mutation_report": mutation_report(), "rows": ROWS}
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "m1_iv_cases.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, ensure_ascii=True)
        f.write("\n")
    msg = "skipped"
    if not a.no_check:
        bad, me = selfcheck(doc)
        if bad:
            for b in bad:
                print("SELFCHECK FAIL", b, file=sys.stderr)
            sys.exit(1)
        msg = "ok (max quantisation IV error %.2e)" % me
    g = sum(1 for r in ROWS if r["gating"])
    print("rows=%d gating=%d nongating=%d selfcheck=%s" % (len(ROWS), g, len(ROWS) - g, msg))


if __name__ == "__main__":
    main()
