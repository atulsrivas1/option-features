#!/usr/bin/env python3
"""Generator for m3a_cases_tenors.json (TENORS family, >= 40 rows, M3A-0). SYNTHETIC. Seeded, deterministic.
G3 tenor oracle: constant-maturity IV at 9, 30, 91 days = linear total variance between the immediately bracketing
listed expiries (w = sigma_ATM^2 N/365), exact-expiry cases as is, no extrapolation (R-14, R-15, R-16, D14).
Flat smiles with stated 4-decimal ATM sigmas (put shifted by a stated amount), so every tenor value is an exact
rational function of stated decimals (iv2_rational in the oracle block)."""
import os, sys
from decimal import Decimal as D
import m3a_oracle as O
from m3a_scen import ex

FAMILY = "tenors"
NOTE = ("Tenor rows. Each expiry: five strikes at 96,98,100,102,104 percent of spot, both rights, flat sigma a "
        "(put side a+shift), ATM IV = a + shift/2 exactly. Tenor IV = sqrt(w_t*365/t) with w_t linear in days "
        "between the two immediately bracketing LISTED expiries; an exact expiry is used as is; a bracketing expiry "
        "without an ATM strike gives no_bracketing_expiry (D14); an exact expiry without one gives its own reason. "
        "Tolerance IV 1e-4. Method names are the M1 names (as_is, variance_interpolation).")
RN = ["R-14", "R-15", "R-16", "R-19", "R-28"]
DR = "VR sec 2.9 (V5 tenors 9/30/91), M3A-0 constant maturity"
STR = [D("0.96"), D("0.98"), D("1.00"), D("1.02"), D("1.04")]


def strikes(S):
    return [(S * m).quantize(D("0.01")) for m in STR]


def chain(S, r, q, spec, over_calls_for=()):
    exps = []
    for (N, a, sh) in spec:
        e = ex(N, S, r, q, D(a), D(0), D(0), D(sh), K=strikes(S))
        if N in over_calls_for:
            e["over"] = {(O.fK(K), "call"): {"drop": True} for K in e["K"]}
        exps.append(e)
    return exps


def main(argv):
    rows = []
    S0, r0, q0 = D("100"), D("0.03"), D("0.01")

    def row(rid, case, spec, tenors, deriv, S=S0, r=r0, q=q0, drop=(), pending=None, tags=()):
        for S_try in (S, D("250")):
            exps = chain(S_try, r, q, spec, drop)
            recs, truth = O.build(S_try, r, q, exps)
            P = O.default_params(tenors=tenors)
            fr = O.compute(S_try, r, q, recs, truth, P)
            mv = O.min_vega(fr, truth, {"tenors"})
            if mv is None or mv >= 4:
                break
        foc = "tenors.%d" % tenors[0]
        t0 = fr["tenors"][tenors[0]]
        rows.append(O.make_row(rid, FAMILY, DR, RN, case, S_try, r, q, recs, truth, P, {"tenors", "exp"}, foc,
                               deriv, tags=["tenors"] + list(tags), pending=pending))
        return fr

    def drv(fr):
        out = []
        for t, tr in sorted(fr["tenors"].items()):
            if tr["status"] == "available":
                out.append("tenor %d: %s from %s -> IV %s" % (t, tr["method"], tr["expiries_used"], tr["iv"]))
            else:
                out.append("tenor %d: %s" % (t, tr["reason"]))
        return "; ".join(out) + "; w_i=sigma_i^2 N_i/365 linear in days, IV=sqrt(w_t*365/t)"

    n = [0]

    def R_(case, spec, tenors=(9, 30, 91), **kw):
        n[0] += 1
        rid = "TEN-%02d" % n[0]
        tmp = None
        # derive text after computing: build once to describe
        S = kw.get("S", S0)
        r, q = kw.get("r", r0), kw.get("q", q0)
        exps = chain(S, r, q, spec, kw.get("drop", ()))
        recs, truth = O.build(S, r, q, exps)
        fr = O.compute(S, r, q, recs, truth, O.default_params(tenors=list(tenors)))
        kw2 = {k: v for k, v in kw.items()}
        return row(rid, case, spec, list(tenors), drv(fr), **kw2)

    # T1 exact 30-day expiry (6 rows): used as is, others per chain
    R_("exact 30d expiry only: 30 as is; 9 and 91 have no bracket (no extrapolation)", [(30, "0.2000", "0.0100")])
    R_("exact 30d among 14d and 60d: 30 as is, not interpolated", [(14, "0.1800", "0"), (30, "0.2500", "0.0100"), (60, "0.3200", "0")])
    R_("exact 30d with 21d and 35d neighbours of very different level", [(21, "0.1500", "0"), (30, "0.3000", "0"), (35, "0.4500", "0")], tenors=(30,))
    R_("exact 30d, put shift -0.02", [(30, "0.2200", "-0.0200")], tenors=(30,))
    R_("exact 30d at S=250 r=0.05 q=0", [(30, "0.2400", "0.0100")], S=D("250"), r=D("0.05"), q=D("0"), tenors=(30,))
    R_("exact 30d, request 9 and 30 only", [(30, "0.2100", "0")], tenors=(9, 30))

    # T2 brackets (12 rows)
    R_("30d from 21d 0.20 and 49d 0.30 (IV linear would be 0.2321)", [(21, "0.2000", "0"), (49, "0.3000", "0")], tenors=(30,))
    R_("30d from 29d and 31d", [(29, "0.2200", "0.0100"), (31, "0.2800", "0.0100")], tenors=(30,))
    R_("30d from 21d and 35d among four expiries (bracket is the immediate pair)", [(14, "0.1500", "0"), (21, "0.2000", "0"), (35, "0.2800", "0"), (60, "0.3500", "0")], tenors=(30,))
    R_("30d from 7d and 90d (wide bracket)", [(7, "0.1800", "0"), (90, "0.3600", "0")], tenors=(30,))
    R_("9d from 7d and 14d", [(7, "0.2000", "0"), (14, "0.2600", "0")], tenors=(9,), S=D("250"))
    R_("9d from 5d and 12d, inverted term structure", [(5, "0.4000", "0"), (12, "0.2400", "0.0100")], tenors=(9,), S=D("250"))
    R_("9d from 8d and 10d", [(8, "0.2200", "0"), (10, "0.2600", "0")], tenors=(9,), S=D("250"))
    R_("91d from 60d and 120d", [(60, "0.2200", "0"), (120, "0.3000", "0")], tenors=(91,))
    R_("91d from 90d and 92d", [(90, "0.2500", "0.0100"), (92, "0.2700", "0.0100")], tenors=(91,))
    R_("91d from 30d and 180d, q=0.03", [(30, "0.2000", "0"), (180, "0.3200", "0")], tenors=(91,), q=D("0.03"))
    R_("91d from 45d and 365d", [(45, "0.1800", "0"), (365, "0.3400", "0")], tenors=(91,))
    R_("all three tenors from 7d, 14d, 60d, 120d: 9d, 91d interpolated, 30d from 14d/60d", [(7, "0.2000", "0"), (14, "0.2300", "0"), (60, "0.2800", "0"), (120, "0.3100", "0")], S=D("250"))

    # T3 no bracket, no extrapolation (10 rows)
    R_("all expiries below 30d: no bracket", [(7, "0.2000", "0"), (14, "0.2200", "0"), (21, "0.2400", "0"), (28, "0.2500", "0")], tenors=(30,))
    R_("all expiries above 30d: no bracket", [(35, "0.2400", "0"), (60, "0.2800", "0")], tenors=(30,))
    R_("single expiry 29d: 30 has no bracket", [(29, "0.2200", "0")], tenors=(30,))
    R_("single expiry 31d: 30 has no bracket", [(31, "0.2200", "0")], tenors=(30,))
    R_("expiries 30 and 91 only: 9 below the shortest, no extrapolation", [(30, "0.2200", "0"), (91, "0.2800", "0")], tenors=(9,))
    R_("expiries 9 and 30 only: 91 above the longest, no extrapolation", [(9, "0.2000", "0"), (30, "0.2200", "0")], tenors=(91,), S=D("250"))
    R_("single expiry 10d: 9d below it", [(10, "0.2200", "0")], tenors=(9,), S=D("250"))
    R_("single expiry 90d: 91d above it", [(90, "0.2200", "0")], tenors=(91,))
    R_("expiries 120 and 180: 91 below the shortest", [(120, "0.2800", "0"), (180, "0.3000", "0")], tenors=(91,))
    R_("expiries 3 and 5: 9 above the longest (S=250)", [(3, "0.2200", "0"), (5, "0.2400", "0")], tenors=(9,), S=D("250"))

    # T4 expiry lacking an ATM strike
    R_("lower bracket 21d has no call quotes: 30 has no usable bracket (D14, no skipping)", [(21, "0.2000", "0"), (49, "0.3000", "0"), (60, "0.3200", "0")], tenors=(30,), drop=(21,))
    R_("upper bracket 49d has no call quotes: 21d ok, 60d ok, bracket is 21/49 so 30 is unavailable", [(21, "0.2000", "0"), (49, "0.3000", "0"), (60, "0.3200", "0")], tenors=(30,), drop=(49,))
    R_("91 bracket 60/120: 120d lacks call quotes", [(60, "0.2200", "0"), (120, "0.3000", "0")], tenors=(91,), drop=(120,))
    R_("9 bracket 7/14: 7d lacks call quotes", [(7, "0.2000", "0"), (14, "0.2600", "0")], tenors=(9,), S=D("250"), drop=(7,))
    R_("9 bracket 7/14: 7d lacks call quotes although 5d is listed and ok (no skipping to 5/14)", [(5, "0.2200", "0"), (7, "0.2000", "0"), (14, "0.2600", "0")], tenors=(9,), S=D("250"), drop=(7,))
    R_("91 bracket 60/120: 60d lacks call quotes although 45d is listed and ok", [(45, "0.2000", "0"), (60, "0.2200", "0"), (120, "0.3000", "0")], tenors=(91,), drop=(60,))
    R_("91 bracket 60/120: 120d lacks call quotes although 180d is listed and ok", [(60, "0.2200", "0"), (120, "0.3000", "0"), (180, "0.3400", "0")], tenors=(91,), drop=(120,))
    pend = {"question": "Q-02", "pick": "no_atm_strike",
            "alternatives": ["low_surface_coverage"],
            "text": "exact 30d expiry without any strike eligible for both rights: M1 D14 gives no_atm_strike, but the surface coverage gate "
                    "(E < min_strikes) also fails; M3a precedence between the two is not written."}
    R_("exact 30d expiry has no call quotes: its own reason, no fallback to neighbours (D14)", [(21, "0.2000", "0"), (30, "0.2500", "0"), (49, "0.3000", "0")], tenors=(30,), drop=(30,), pending=pend)
    R_("exact 30d expiry only, no call quotes", [(30, "0.2500", "0")], tenors=(30,), drop=(30,), pending=pend)

    # T5 multi-tenor frames (6 rows)
    R_("all tenors exact: 9, 30, 91 expiries listed", [(9, "0.2000", "0"), (30, "0.2400", "0"), (91, "0.2800", "0")], S=D("250"))
    R_("9 exact, 30 and 91 interpolated", [(9, "0.1900", "0"), (14, "0.2100", "0"), (60, "0.2600", "0"), (120, "0.3000", "0")], S=D("250"))
    R_("9 and 91 interpolated, 30 exact", [(7, "0.2000", "0"), (14, "0.2200", "0"), (30, "0.2500", "0.0100"), (60, "0.2800", "0"), (120, "0.3200", "0")], S=D("250"))
    R_("inverted term structure (long IV below short IV)", [(7, "0.4500", "0"), (14, "0.4000", "0"), (60, "0.3000", "0"), (120, "0.2500", "0")], S=D("250"))
    R_("negative rate and zero dividend", [(9, "0.2000", "0"), (21, "0.2300", "0"), (35, "0.2600", "0"), (91, "0.3000", "0")], S=D("250"), r=D("-0.01"), q=D("0"))
    R_("flat term structure (every tenor equals the level)", [(7, "0.2200", "0"), (21, "0.2200", "0"), (60, "0.2200", "0"), (120, "0.2200", "0")], S=D("250"))
    assert len(rows) >= 40, len(rows)
    hdr = O.header(FAMILY, rows, os.path.basename(__file__), NOTE)
    h = O.write_dataset(os.path.join(O.out_dir(argv), "m3a_cases_tenors.json"), hdr, rows)
    print("m3a_cases_tenors.json", len(rows), h)


if __name__ == "__main__":
    main(sys.argv)
