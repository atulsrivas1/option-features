#!/usr/bin/env python3
"""Generator for m3a_cases_surface.json (SURFACE FRAME family, >= 80 rows, M3A-0). SYNTHETIC. Seeded, deterministic.
Forward F = S exp((r-q) N/365); ATM = strike nearest F among strikes with both rights eligible (ties lower), ATM IV =
mean(call IV, put IV) at that strike (M1 D12/D13/D14 conventions); coverage counts; M1 contract gate reasons; labels
(model label, plus delayed); delayed tag and mode; all-excluded and empty chains; multi-expiry frames."""
import os, sys, copy
from decimal import Decimal as D
import m3a_oracle as O
from m3a_scen import ex, ok_chain

FAMILY = "surface"
NOTE = ("Surface frame rows. Quotes are BSM midpoints of stated 6-decimal sigma (4-decimal bid/ask, spread 0.002), chain "
        "records are exactly the M1 ChainContract field set. Expected forward within 1e-6, ATM IV within 1e-4, counts exact. "
        "Per-expiry status, reason and field values are asserted under items.expiries (shape is an authoring choice, see "
        "AUTHORING_NOTES defect D-01). The gate order of M1 is no_quote, excluded_condition, invalid_quote, crossed_market, "
        "locked_market, stale_quote, then style gates; a contract counts under its first failing reason.")
RN = ["R-07", "R-11", "R-12", "R-17", "R-20", "R-24", "R-26", "R-63", "R-83", "R-90"]
DR = "VR sec 2.3-2.4 (surface frame), OC gates; M3A-0"
CANDS = (D("100"), D("250"), D("300"))
WANT = {"fwd", "atm", "exp", "cov", "labels"}


def main(argv):
    rows = []
    n = [0]

    def srow(case, build_exps, r, q, params=None, want=WANT, focus=None, pending=None, tags=(), rn=(), S_c=CANDS, keep_cov=False,
             shuffle=None, derivation=None):
        P = params or O.default_params()
        for S in S_c:
            exps = build_exps(S)
            recs, truth = O.build(S, r, q, exps)
            fr = O.compute(S, r, q, recs, truth, P)
            mv = O.min_vega(fr, truth, want)
            if mv is None or mv >= 4:
                break
        if shuffle:
            recs = shuffle(recs)
        n[0] += 1
        N0 = sorted({c["expiry_days"] for c in recs})[0] if recs else 30
        if focus is None:
            focus = "expiries.%d.atm_iv" % N0
        d = derivation or "; ".join("N=%d F=%s %s%s" % (N, e["forward"], e["status"] if e["status"] != "available" else "ATM strike %s IV %s" % (e["atm_strike"], e["atm_iv"]),
                                                       "" if not e["reason"] else "/" + e["reason"]) for N, e in sorted(fr["expiries"].items()))
        rows.append(O.make_row("SUR-%02d" % n[0], FAMILY, DR, list(RN) + list(rn), case, S, r, q, recs, truth, P, set(want), focus, d,
                               tags=["surface"] + list(tags), pending=pending, keep_cov=keep_cov))
        return fr

    def fgrid(N, S, r, q, a, b=D(0), c=D(0), sh=D(0), step=D("0.35"), jlo=-4, jhi=4, off=D(0), **kw):
        return ex(N, S, r, q, a, b, c, sh, step, jlo, jhi, off, **kw)

    # ---- S1 forward rows (20): flat sigma, grid around F
    F1 = [(0.03, 0.01, 30), (0, 0, 30), (0.05, 0, 91), (0, 0.03, 91), (-0.02, 0.01, 60), (0.03, 0.03, 45), (0.10, 0, 365), (0.04, 0.02, 182),
          (0.03, 0.01, 1), (0.03, 0.01, 2), (0.03, 0.01, 7), (0.03, 0.01, 9), (0.03, 0.01, 14), (0.06, 0, 730), (-0.01, 0, 30), (0.02, 0.05, 120),
          (1.0, 0, 30), (-1.0, 0, 30), (0.0, 1.0, 30), (0.08, 0.01, 21)]
    for (r_, q_, N) in F1:
        r_, q_ = D(str(r_)), D(str(q_))
        a = D("0.22")
        srow("forward: r=%s q=%s N=%d (F = S exp((r-q)N/365))" % (r_, q_, N),
             lambda S, N=N, r_=r_, q_=q_, a=a: [fgrid(N, S, r_, q_, a, sh=D("0.01"), step=min(D("0.35"), (D("0.04") / (a * (D(N) / 365).sqrt())).quantize(D("0.001"))))], r_, q_, tags=["forward"],
             focus="expiries.%d.forward" % N, rn=["R-24"])

    # ---- S2 ATM IV on smiles (10) and ties (4)
    S2 = [(365, "0.05", "0.01", "0.2", "-0.3", "0.5", "0"), (365, "0.06", "0", "0.25", "-0.2", "0.4", "0.01"), (182, "0.05", "0.01", "0.2", "0.2", "0.3", "0"),
          (365, "0.08", "0.01", "0.3", "-0.4", "1.0", "-0.01"), (180, "0.07", "0", "0.22", "-0.5", "0.6", "0.02"), (300, "0.04", "0.01", "0.18", "0.3", "0.2", "0"),
          (365, "0.03", "0.05", "0.2", "-0.3", "0.5", "0"), (250, "0.0", "0.04", "0.25", "-0.35", "0.8", "0.01"), (30, "0.03", "0.01", "0.2", "-0.3", "0.5", "0"),
          (91, "0.05", "0.02", "0.3", "-0.2", "0.4", "0.02")]
    for (N, r_, q_, a, b, c, sh) in S2:
        r_, q_, a, b, c, sh = D(r_), D(q_), D(a), D(b), D(c), D(sh)
        srow("ATM IV on a smile (a=%s b=%s c=%s put shift %s), N=%d, r=%s q=%s: strike nearest F, not nearest spot" % (a, b, c, sh, N, r_, q_),
             lambda S, N=N, r_=r_, q_=q_, a=a, b=b, c=c, sh=sh: [fgrid(N, S, r_, q_, a, b, c, sh, step=D("0.25"))], r_, q_, tags=["atm_smile"],
             focus="expiries.%d.atm_iv" % N, rn=["R-07"])
    for (N, b, c, sh, tag) in [(30, "-0.5", "0.5", "0", "tie 100/101 goes to the lower strike"), (60, "-1.0", "2.0", "0.01", "tie with a steep smile"),
                               (91, "0.6", "1.0", "0", "tie, call-skewed smile"), (21, "-0.3", "0.3", "-0.01", "tie, negative put shift")]:
        def bld(S, N=N, b=D(b), c=D(c), sh=D(sh)):
            Ks = [D(x) for x in (S - 3, S - 2, S - 1, S, S + 1, S + 2, S + 3, S + 4)] if S == D("100") else [S + D(x) for x in range(-3, 5)]
            return [ex(N, S, D(0), D(0), D("0.25"), b, c, sh, K=[K + D("0.5") - D("0.5") for K in Ks])]
        # S = 100.5 is not in CANDS: use explicit spot below
        def bld2(S, N=N, b=D(b), c=D(c), sh=D(sh)):
            Sx = D("100.5")
            from m3a_oracle import fwd, smile
            Ks = [D(x) for x in range(97, 105)]
            return [dict(N=N, K=Ks, sig=smile(fwd(Sx, D(0), D(0), N), D("0.25"), b, c, sh), style="european", over={})]
        P = O.default_params()
        exps = bld2(None)
        recs, truth = O.build(D("100.5"), D(0), D(0), exps)
        fr = O.compute(D("100.5"), D(0), D(0), recs, truth, P)
        n[0] += 1
        rows.append(O.make_row("SUR-%02d" % n[0], FAMILY, DR, RN + ["R-10"], "forward exactly between strikes 100 and 101 (S=100.5, r=q=0): " + tag,
                               D("100.5"), D(0), D(0), recs, truth, P, set(WANT), "expiries.%d.atm_iv" % N,
                               "F=100.5 exactly, tie between 100 and 101 -> lower strike 100 (M1 D13); ATM IV = mean(call, put) at 100: " + fr["expiries"][N]["atm_iv"],
                               tags=["surface", "tie_strike"]))

    # ---- S3 coverage counts and contract reasons (14)
    def over_for(Ks, spec):
        o = {}
        for (idx, right, mode, cond) in spec:
            d_ = {}
            if mode:
                d_["mode"] = mode
            if cond:
                d_["cond"] = cond
            o[(O.fK(Ks[idx]), right)] = d_
        return o
    r3, q3 = D("0.03"), D("0.01")
    S3 = [("stale call at the ATM strike", [(4, "call", "stale", None)]),
          ("nonstandard condition on two puts", [(2, "put", None, "nonstandard"), (6, "put", None, "opening")]),
          ("crossed put and locked call", [(1, "put", "crossed", None), (7, "call", "locked", None)]),
          ("negative bid and zero bid", [(0, "put", "neg", None), (8, "call", "zerobid", None)]),
          ("missing bid and missing ask", [(3, "call", "nobid", None), (5, "put", "noask", None)]),
          ("quote after the cutoff (no_quote)", [(2, "call", "noquote", None), (6, "call", "noquote", None), (7, "put", "noquote", None)]),
          ("stale and nonstandard on the same contract: first reason is excluded_condition", [(4, "put", "stale", "nonstandard")]),
          ("crossed and nonstandard: excluded_condition first", [(2, "call", "crossed", "nonstandard")]),
          ("no_quote and stale: no_quote first (event after the cutoff cannot also be stale)", [(5, "put", "noquote", "nonstandard")]),
          ("six different failures", [(0, "call", "stale", None), (1, "put", "crossed", None), (2, "call", "locked", None), (6, "put", "neg", None), (7, "call", None, "nonstandard"), (8, "put", "noquote", None)]),
          ("put and call both stale at the nearest strike: ATM moves to the next strike", [(4, "call", "stale", None), (4, "put", "stale", None)]),
          ("whole outer strike dead (both rights stale at strikes 0 and 8)", [(0, "call", "stale", None), (0, "put", "stale", None), (8, "call", "stale", None), (8, "put", "stale", None)]),
          ("one excluded contract per right at the ATM strike (call stale, put locked)", [(4, "call", "stale", None), (4, "put", "locked", None)]),
          ("clean chain: no contract reasons", [])]
    for (case, spec) in S3:
        def bld(S, spec=spec):
            e = fgrid(30, S, r3, q3, D("0.2"), D("-0.3"), D("0.5"), D("0.01"), step=D("0.3"))
            e["over"] = over_for(e["K"], spec)
            return [e]
        srow("contract reasons: " + case, bld, r3, q3, tags=["contract_reasons"], focus="expiries.30.atm_iv", rn=["R-90"])

    # ---- S4 labels and S5 delayed/mode (14)
    for (mode, tag, lane, case) in [("intraday", "live", "stock", "intraday live: model label only"), ("intraday", "delayed", "stock", "intraday delayed: computed, labels exact-model then delayed"),
                                    ("close", "live", "stock", "close live: model label only"), ("close", "delayed", "stock", "close delayed: computed and labelled delayed"),
                                    ("intraday", "live", "etf_index", "lane etf_index: same values"), ("close", "delayed", "etf_index", "close, delayed, etf_index lane")]:
        P = O.default_params(mode=mode, feed_delay_tag=tag, lane=lane)
        srow(case, lambda S: [fgrid(30, S, r3, q3, D("0.2"), D("-0.3"), D("0.5"), D("0.01"))], r3, q3, params=P, tags=["delayed" if tag == "delayed" else "live", "labels"],
             focus="expiries.30.atm_iv", rn=["R-56", "R-58", "R-73"])
    for (a, b, case) in [("0.2", "0", "exact-model label on a flat European chain"), ("0.3", "-0.2", "exact-model label on a smile"), ("0.15", "0.1", "exact-model label, call-skewed smile")]:
        srow(case, lambda S, a=D(a), b=D(b): [fgrid(45, S, r3, q3, a, b, D("0.3"))], r3, q3, tags=["labels"], focus="expiries.45.atm_iv", rn=["R-63"])
    srow("label text exactly 'exact-model' (no extra words)", lambda S: [fgrid(30, S, r3, q3, D("0.2"))], r3, q3, tags=["labels"], focus="expiries.30.atm_iv", rn=["R-63"])
    srow("European chain with style None contracts excluded: remaining are exact-model", lambda S: [fgrid(30, S, r3, q3, D("0.2"), over={})], r3, q3, tags=["labels"], focus="expiries.30.atm_iv", rn=["R-63"])
    # style None on two outer strikes (excluded, counted as style_unknown), label stays exact-model
    def bld_u(S):
        e = fgrid(30, S, r3, q3, D("0.2"), D("-0.3"), D("0.5"))
        e["over"] = {(O.fK(e["K"][0]), "call"): {"style": None}, (O.fK(e["K"][0]), "put"): {"style": None}, (O.fK(e["K"][8]), "call"): {"style": None}}
        return [e]
    srow("three contracts with style None (style_unknown), the rest European: label exact-model", bld_u, r3, q3, tags=["labels", "contract_reasons"], focus="expiries.30.atm_iv", rn=["R-11"])

    # ---- S6 all-excluded and empty chains (6)
    q02 = {"question": "Q-02", "pick": "no_atm_strike (as M1 for an expiry with no usable quotes)", "alternatives": ["low_surface_coverage"],
           "text": "an expiry with no eligible strike fails both the ATM and the coverage gate; their order is not written"}
    q06 = {"question": "Q-06", "pick": "PO ruling batch 2: unavailable result labels = []", "alternatives": [],
           "text": "matrix 3: result carries labels; unavailable results carry value null and fired null; nothing says whether labels stay"}
    q12 = {"question": "Q-12", "pick": "PO ruling batch 2: empty chain gives frame unavailable, reason no_eligible_contract; each tenor no_bracketing_expiry", "alternatives": [],
           "text": "an empty chain has no expiry; the contract gives no frame-level reason"}
    for (case, spec_all, pend, params) in [
            ("all contracts stale: frame unavailable, every expiry no_atm_strike", "stale", q02, None),
            ("all contracts nonstandard condition", "cond", q02, None),
            ("all contracts crossed", "crossed", q02, None),
            ("all contracts style None (style_unknown)", "style", q02, None),
            ("all stale under a delayed tag", "stale", dict(q02, **{"questions_also": ["Q-06"]}), O.default_params(feed_delay_tag="delayed"))]:
        def bld(S, spec_all=spec_all):
            e = fgrid(30, S, r3, q3, D("0.2"), D("0"), D("0"))
            e2 = fgrid(60, S, r3, q3, D("0.2"))
            for ee in (e, e2):
                ov = {}
                for K in ee["K"]:
                    for rt in ("call", "put"):
                        ov[(O.fK(K), rt)] = ({"mode": "stale"} if spec_all == "stale" else {"cond": "nonstandard"} if spec_all == "cond" else
                                             {"mode": "crossed"} if spec_all == "crossed" else {"style": None})
                ee["over"] = ov
            return [e, e2]
        lab = ["delayed"] if params and params["feed_delay_tag"] == "delayed" else None
        srow(case, bld, r3, q3, params=params, want={"exp", "cov", "labels"}, focus="frame", pending=pend, tags=["all_excluded"], rn=["R-71"], keep_cov=True)
    # empty chain
    P = O.default_params()
    n[0] += 1
    rows.append(O.make_row("SUR-%02d" % n[0], FAMILY, DR, RN + ["R-71", "R-16"], "empty chain (no contracts): unavailable no_eligible_contract, every tenor no_bracketing_expiry", D("100"), r3, q3, [], {}, P,
                           {"tenors", "cov", "labels"}, "frame", "no expiry listed: nothing to bracket (no extrapolation); frame reason no_eligible_contract (Q-12 ruled); coverage all zero", tags=["surface", "all_excluded", "empty"],
                           pending=q12, keep_cov=True))

    # ---- S7 multi-expiry frames (12 rows incl. 2 shuffled chains and 1 expiry without ATM)
    def three(S, Ns=(9, 30, 91), drops=(), smile_=True):
        out = []
        for N in Ns:
            e = fgrid(N, S, r3, q3, D("0.2") + D(N) / D(2000), D("-0.3") if smile_ else D(0), D("0.5") if smile_ else D(0), D("0.01"), step=D("0.35"))
            if N in drops:
                e["over"] = {(O.fK(K), "call"): {"drop": True} for K in e["K"]}
            out.append(e)
        return out
    for Ns in [(9, 30, 91), (7, 30, 60), (14, 45, 120), (21, 30, 49), (9, 91, 182), (30, 60, 91)]:
        srow("three expiries %s: forward and ATM IV per expiry, totals are sums" % (Ns,), lambda S, Ns=Ns: three(S, Ns), r3, q3, tags=["multi_expiry"],
             focus="expiries.%d.atm_iv" % Ns[1], rn=["R-27"])
    srow("three expiries, the 30d expiry has no call quotes: it is unavailable, the others are served", lambda S: three(S, drops=(30,)), r3, q3, tags=["multi_expiry", "no_atm"],
         focus="expiries.30", pending=q02, rn=["R-27"])
    srow("three expiries, 9d expiry has no call quotes", lambda S: three(S, drops=(9,)), r3, q3, tags=["multi_expiry", "no_atm"], focus="expiries.9", pending=q02, rn=["R-27"])
    srow("three expiries listed in descending order in the chain (output ascending)", lambda S: three(S, (91, 30, 9)), r3, q3, tags=["multi_expiry", "order"], focus="expiries.30.atm_iv")
    srow("contracts of three expiries in reverse input order", lambda S: three(S), r3, q3, tags=["multi_expiry", "order"], focus="expiries.30.atm_iv", shuffle=lambda rc: list(reversed(rc)))
    srow("contracts of three expiries interleaved (every 3rd first)", lambda S: three(S), r3, q3, tags=["multi_expiry", "order"], focus="expiries.30.atm_iv",
         shuffle=lambda rc: rc[0::3] + rc[1::3] + rc[2::3])
    srow("two expiries with different forwards, r=0.05 q=0 (carry differs per expiry)", lambda S: [fgrid(30, S, D("0.05"), D(0), D("0.2")), fgrid(365, S, D("0.05"), D(0), D("0.25"))],
         D("0.05"), D(0), tags=["multi_expiry"], focus="expiries.365.forward")
    srow("single expiry N=365 with shuffled strikes order irrelevant", lambda S: [fgrid(365, S, r3, q3, D("0.25"))], r3, q3, tags=["order"], focus="expiries.365.atm_iv",
         shuffle=lambda rc: rc[::-1])
    for (N, r_, q_, a_) in [(3, "0.03", "0.01", "0.25"), (45, "-0.03", "0.02", "0.35"), (400, "0.07", "0.02", "0.3")]:
        r_, q_, a_ = D(r_), D(q_), D(a_)
        srow("forward and ATM IV, N=%d r=%s q=%s sigma %s" % (N, r_, q_, a_),
             lambda S, N=N, r_=r_, q_=q_, a_=a_: [fgrid(N, S, r_, q_, a_, sh=D("0.02"), step=min(D("0.35"), (D("0.04") / (a_ * (D(N) / 365).sqrt())).quantize(D("0.001"))))],
             r_, q_, tags=["forward"], focus="expiries.%d.forward" % N)
    # ---- solver failures of ONE contract (PO batches 2 and Q-13, from the solver text): strictly outside the bounds =
    # price_out_of_bounds; exactly the upper bound = upper_asymptote; exactly the lower bound = available (IV 0.0), no failure.
    q13 = {"question": "Q-13", "pick": "PO ruling: strictly below lower or strictly above upper bound = price_out_of_bounds; exactly upper = upper_asymptote; exactly lower = available with IV 0.0",
           "alternatives": [], "text": "sigma_cap, precision_exhausted, bound_precision, iteration_budget need solver internals: not in fixtures (unit level, Developer)"}
    def solver_chain(S, specs):
        e = fgrid(30, S, r3, q3, D("0.2"), D("-0.3"), D("0.5"), D("0.01"), step=D("0.3"))
        e["over"] = {(O.fK(e["K"][i]), rt): {"bound": b} for (i, rt, b) in specs}
        return [e]
    def solver_chain0(S, specs):
        e = fgrid(30, S, D(0), D(0), D("0.2"), D("-0.3"), D("0.5"), D("0.01"), step=D("0.3"))
        e["over"] = {(O.fK(e["K"][i]), rt): {"bound": b} for (i, rt, b) in specs}
        return [e]
    for case, specs in [("ITM call at the lowest strike priced below intrinsic: price_out_of_bounds", [(0, "call", "below")]),
                        ("ITM put at the highest strike priced below intrinsic: price_out_of_bounds", [(8, "put", "below")]),
                        ("call at the ATM strike priced below its lower bound: price_out_of_bounds, ATM moves", [(4, "call", "below")]),
                        ("call priced strictly above the upper bound S e^{-qT}: price_out_of_bounds", [(1, "call", "above")]),
                        ("put priced strictly above the upper bound K e^{-rT}: price_out_of_bounds", [(7, "put", "above")]),
                        ("put at the ATM strike strictly above the upper bound: price_out_of_bounds, ATM moves", [(4, "put", "above")]),
                        ("one below-lower and one above-upper in one chain: two price_out_of_bounds", [(0, "call", "below"), (8, "put", "above")]),
                        ("three strictly-outside contracts counted per contract", [(0, "call", "below"), (8, "put", "below"), (2, "call", "above")])]:
        srow("solver failure on one contract (excluded, counted): " + case, lambda S, specs=specs: solver_chain(S, specs), r3, q3,
             tags=["solver_reason", "contract_reasons"], focus="expiries.30.atm_iv", pending=q13, rn=["R-86"])
    for case, specs in [("call priced exactly at the upper bound S (r=q=0): upper_asymptote, contract excluded", [(1, "call", "at_upper")]),
                        ("put priced exactly at the upper bound K (r=q=0): upper_asymptote", [(7, "put", "at_upper")]),
                        ("ATM call priced exactly at S: upper_asymptote, ATM moves", [(4, "call", "at_upper")]),
                        ("two exact-upper contracts: upper_asymptote 2", [(1, "call", "at_upper"), (7, "put", "at_upper")]),
                        ("ITM call priced exactly at its lower bound S-K (r=q=0): available, IV 0.0, no contract reason", [(0, "call", "at_lower")]),
                        ("ITM put priced exactly at its lower bound K-S (r=q=0): available, no contract reason", [(8, "put", "at_lower")]),
                        ("exact lower on both wings: no contract reason, nothing excluded", [(0, "call", "at_lower"), (8, "put", "at_lower")]),
                        ("exact lower, exact upper and strictly below in one chain", [(0, "call", "at_lower"), (8, "put", "at_upper"), (1, "call", "below")])]:
        srow("solver bound equality (r=q=0): " + case, lambda S, specs=specs: solver_chain0(S, specs), D(0), D(0),
             tags=["solver_reason", "contract_reasons", "bound_equality"], focus="expiries.30.atm_iv", pending=q13, rn=["R-86"])
    # ---- frame carries 25-delta points: both delta conventions (owner decision 3; default spot)
    for (N, q_, a_, b_, c_) in [(91, "0.02", "0.2", "-0.3", "0.5"), (365, "0.08", "0.2", "-0.3", "0.5"), (30, "0", "0.25", "-0.2", "0.4")]:
        q_ = D(q_)
        e_ = ok_chain(N, D(100), r3, q_, D(a_), D(b_), D(c_), D(0))
        for cv in ("spot", "forward"):
            srow("frame with 25-delta points, %s delta, N=%d q=%s" % (cv, N, q_), lambda S, e_=e_: [copy.deepcopy(e_)], r3, q_,
                 params=O.default_params(delta_convention=cv), want=WANT | {"p25", "c25"}, focus="expiries.%d.put25_iv" % N, S_c=(D(100),),
                 tags=["convention", cv], rn=["OD-3", "R-04"])
    assert len(rows) >= 80, len(rows)
    hdr = O.header(FAMILY, rows, os.path.basename(__file__), NOTE)
    h = O.write_dataset(os.path.join(O.out_dir(argv), "m3a_cases_surface.json"), hdr, rows)
    print("m3a_cases_surface.json", len(rows), h)


if __name__ == "__main__":
    main(sys.argv)
