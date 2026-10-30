#!/usr/bin/env python3
"""Generator for m3a_cases_american.json (AMERICAN LABELS family, >= 20 rows, M3A-0). SYNTHETIC. Seeded, deterministic.
Rules (R-11, M1 D13): contracts of American style are modelled with the European model and labelled
"approximate: European model on an American-style contract"; an American contract in the money (call K < F, put K > F)
is excluded as american_itm, except the one strike nearest F over all listed strikes (ties lower; K = F is not in the
money); style None is excluded as style_unknown. Quotes of American-style contracts are priced with the European model
at the stated sigma (that is what the library inverts), so expected IVs are the stated sigmas."""
import os, sys
from decimal import Decimal as D
import m3a_oracle as O
from m3a_scen import ex, margin_ok, describe

FAMILY = "american"
NOTE = ("American-style and style-unknown rows. Labels are the M1 strings verbatim; the delayed tag appends 'delayed'. Counts of "
        "american_itm and style_unknown are contract counts (coverage.contract_reasons). Eligible-strike counts are not asserted "
        "here (Q-01: an American chain has only one strike with both rights eligible).")
RN = ["R-04", "R-09", "R-11", "R-12", "R-63", "R-90"]
DR = "option-contracts 2.x (American labels), M1 D13; R-11"
r0, q0 = D("0.03"), D("0.01")
WANT = {"fwd", "atm", "p25", "c25", "labels", "creasons", "exp"}


def smile_exp(N, a, b, c, S, r, q, style="european", over=None):
    """First grid offset whose 25-delta brackets keep a clear margin (>= 3e-4 from 0.25) and both sides exist."""
    for off in ("0.1", "0", "0.2", "-0.1", "0.25", "0.05", "0.15", "-0.2", "0.3", "-0.05"):
        e = ex(N, S, r, q, D(a), D(b), D(c), D(0), D("0.35"), -4, 4, D(off), style=style, over=over)
        recs, truth = O.build(S, r, q, [e])
        fr = O.compute(S, r, q, recs, truth, O.default_params())
        x = fr["expiries"][N]
        if x["status"] == "available" and x["put25_iv"]["status"] == "available" and x["call25_iv"]["status"] == "available"                 and margin_ok(fr) and O.min_vega(fr, truth, {"atm", "p25", "c25"}) >= 4:
            return e
    raise SystemExit("no offset for %s" % ((N, a, b, c),))


def main(argv):
    rows = []
    n = [0]

    def add(case, S, r, q, exps, params=None, want=WANT, focus=None, pending=None, tags=(), rn=(), need25=True, labels="auto"):
        P = params or O.default_params()
        recs, truth = O.build(S, r, q, exps)
        fr = O.compute(S, r, q, recs, truth, P)
        N0 = exps[0]["N"]
        x = fr["expiries"][N0]
        if need25 and x["status"] == "available":
            assert margin_ok(fr), case
        n[0] += 1
        d = describe(fr, N0) if x["status"] == "available" else "expiry %d unavailable (%s)" % (N0, x["reason"])
        d += "; contract reasons %s" % (fr["coverage"]["contract_reasons"],)
        rows.append(O.make_row("AME-%02d" % n[0], FAMILY, DR, list(RN) + list(rn), case, S, r, q, recs, truth, P, set(want),
                               focus or "expiries.%d.atm_iv" % N0, d, tags=["american"] + list(tags), pending=pending, g2=False, labels=labels))
        return fr

    S = D("100")
    # A1 exact-model on European chains (3)
    for (a, b, c) in [("0.2", "-0.3", "0.5"), ("0.25", "-0.1", "0.3"), ("0.3", "0.1", "0.2")]:
        add("European chain: label exact-model, no american_itm", S, r0, q0, [smile_exp(30, a, b, c, S, r0, q0)], tags=["european"])
    # A2 American smile chains (4)
    for (N, a, b, c, off) in [(30, "0.2", "-0.3", "0.5", "0.1"), (60, "0.25", "-0.2", "0.4", "0.2"), (30, "0.3", "0.1", "0.6", "-0.1"), (91, "0.22", "-0.4", "0.8", "0.15")]:
        e = smile_exp(N, a, b, c, S, r0, q0, style="american")
        add("American chain N=%d: OTM legs only, label approximate, 25-delta from the OTM legs" % N, S, r0, q0, [e], tags=["american_chain"])
    # A3 american_itm exclusions (5)
    Ks = [D(x) for x in ("96", "98", "100", "102", "104")]
    add("American, strikes 96..104, F=100.16: calls 96, 98 and puts 102, 104 are in the money (4 american_itm); 100 nearest exempt",
        S, r0, q0, [ex(30, S, r0, q0, D("0.2"), K=Ks, style="american")], want={"fwd", "atm", "labels", "creasons", "exp"}, tags=["american_itm"], need25=False)
    add("American, r=q so F=100 exactly on a strike: strike 100 is neither in nor out of the money (4 american_itm)",
        S, D("0.02"), D("0.02"), [ex(30, S, D("0.02"), D("0.02"), D("0.2"), K=[D(x) for x in ("98", "99", "100", "101", "102")], style="american")],
        want={"fwd", "atm", "labels", "creasons", "exp"}, tags=["american_itm", "k_equals_f"], need25=False)
    Sx = D("100.5")
    add("American, F=100.5 exactly between strikes 100 and 101: nearest strike is the lower one (100) and is exempt; call 100 stays, put 101 is in the money",
        Sx, D(0), D(0), [dict(N=30, K=[D(x) for x in ("98", "99", "100", "101", "102", "103")], sig=O.flat(D("0.2")), style="american", over={})],
        want={"fwd", "atm", "labels", "creasons", "exp"}, tags=["american_itm", "tie_strike"], need25=False)
    add("American, F=101.3 nearest strike 101 above spot: calls 99, 100 and puts 102, 103 excluded, 101 exempt",
        S, D("0.10"), D("0"), [ex(45, S, D("0.10"), D("0"), D("0.2"), K=[D(x) for x in ("99", "100", "101", "102", "103", "104")], style="american")],
        want={"fwd", "atm", "labels", "creasons", "exp"}, tags=["american_itm"], need25=False)
    add("American, q=0.03 r=0.01 (F below spot): strikes 94..102",
        S, D("0.01"), D("0.03"), [ex(91, S, D("0.01"), D("0.03"), D("0.25"), K=[D(x) for x in ("94", "96", "97", "98", "99", "100", "101", "102")], style="american")],
        want={"fwd", "atm", "labels", "creasons", "exp"}, tags=["american_itm"], need25=False)
    # A4 style_unknown (4)
    q02 = {"question": "Q-02", "pick": "no_atm_strike", "alternatives": ["low_surface_coverage"], "text": "all contracts style_unknown: no eligible strike; ATM and coverage gate order not written"}
    e = ex(30, S, r0, q0, D("0.2"), D(0), D(0), D(0), D("0.35"), -4, 4, D(0), over={})
    e["over"] = {(O.fK(K), rt): {"style": None} for K in e["K"] for rt in ("call", "put")}
    add("every contract style None: style_unknown, frame unavailable", S, r0, q0, [e], want={"exp", "creasons", "labels"}, focus="frame", pending=q02, tags=["style_unknown"], need25=False)
    e = smile_exp(30, "0.2", "-0.3", "0.5", S, r0, q0)
    e["over"] = {(O.fK(e["K"][0]), "call"): {"style": None}, (O.fK(e["K"][0]), "put"): {"style": None}, (O.fK(e["K"][8]), "call"): {"style": None}}
    add("three outer contracts style None, the rest European: served, label exact-model, style_unknown 3", S, r0, q0, [e], tags=["style_unknown"])
    e = smile_exp(30, "0.2", "-0.3", "0.5", S, r0, q0)
    jATM = min(range(len(e["K"])), key=lambda i: abs(e["K"][i] - O.fwd(S, r0, q0, 30)))
    e["over"] = {(O.fK(e["K"][jATM]), "call"): {"style": None}}
    add("call at the ATM strike has style None: ATM moves to the next both-rights strike, style_unknown 1", S, r0, q0, [e], tags=["style_unknown"], need25=False)
    e = smile_exp(30, "0.2", "-0.3", "0.5", S, r0, q0, style="american")
    e["over"] = {(O.fK(e["K"][0]), "put"): {"style": None}, (O.fK(e["K"][1]), "call"): {"style": None}}
    add("American chain with two style None contracts: approximate label, style_unknown 2", S, r0, q0, [e], tags=["style_unknown", "american_chain"])
    # A5 label text with delayed (2)
    e = smile_exp(30, "0.2", "-0.3", "0.5", S, r0, q0, style="american")
    add("American chain, delayed tag: labels = [approximate text, delayed]", S, r0, q0, [e], params=O.default_params(feed_delay_tag="delayed"), tags=["labels", "delayed"])
    add("American chain, close mode, delayed tag", S, r0, q0, [e], params=O.default_params(mode="close", feed_delay_tag="delayed"), tags=["labels", "delayed"], rn=["R-58"])
    # A6 mixed styles (2)
    q05 = {"question": "Q-05", "pick": "PO ruling batch 2: mixed frame carries both model labels, sorted list",
           "alternatives": [], "text": "R-63: a labels list (model label, plus delayed): which model label when expiries differ is not written"}
    e1 = smile_exp(30, "0.2", "-0.3", "0.5", S, r0, q0)
    e2 = smile_exp(60, "0.25", "-0.3", "0.5", S, r0, q0, style="american")
    add("expiry 30 European, expiry 60 American in one chain: values per expiry, labels = both model labels sorted", S, r0, q0, [e1, e2],
        want={"fwd", "atm", "exp", "creasons", "labels"}, pending=q05, tags=["mixed_style"], need25=False)
    add("expiry 30 American, expiry 60 European: tenor 30 and 60 values per expiry", S, r0, q0,
        [smile_exp(30, "0.2", "-0.3", "0.5", S, r0, q0, style="american"),
         smile_exp(60, "0.25", "-0.3", "0.5", S, r0, q0)],
        want={"fwd", "atm", "exp", "creasons", "labels"}, pending=q05, tags=["mixed_style"], need25=False)
    assert len(rows) >= 20, len(rows)
    hdr = O.header(FAMILY, rows, os.path.basename(__file__), NOTE)
    h = O.write_dataset(os.path.join(O.out_dir(argv), "m3a_cases_american.json"), hdr, rows)
    print("m3a_cases_american.json", len(rows), h)


if __name__ == "__main__":
    main(sys.argv)
