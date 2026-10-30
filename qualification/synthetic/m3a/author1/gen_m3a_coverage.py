#!/usr/bin/env python3
"""Generator for m3a_cases_coverage.json (COVERAGE GATES family, >= 24 rows, M3A-0). SYNTHETIC. Seeded, deterministic.
Gate (R-20, R-83, my reading Q-01): per expiry, listed = strikes with any contract record, eligible = strikes with at
least one eligible quote; the expiry is served only if eligible >= min_strikes and eligible/listed >= min_coverage (3/5,
inclusive) and each right has >= 2 eligible strikes within +-10 percent of the forward (Q-09); otherwise it is
unavailable with low_surface_coverage. Dead strikes (both rights stale) make listed larger than eligible."""
import os, sys, copy
from decimal import Decimal as D
import m3a_oracle as O
from m3a_scen import ex

FAMILY = "coverage"
NOTE = ("Coverage gate rows. Flat sigma 0.20, S=100 (S=250 for 1 and 2 day expiries), r=0.03, q=0.01 unless stated. Live strikes have "
        "both rights quoted; dead strikes have both rights stale (counted as listed, not eligible). Rows whose outcome "
        "depends on the unratified reading of listed/eligible strikes (Q-01), of min_strikes (Q-08), of the near-the-money "
        "rule (Q-09) or of the tenor use of a coverage-excluded expiry (Q-10) are PENDING-RULING with the pick and the "
        "alternatives stated. expiry_days boundary rows follow R-13 (>= 1; bad_expiry otherwise).")
RN = ["R-13", "R-20", "R-83"]
DR = "OC gates; matrix 4 (min_strikes, min_coverage); R-20, R-83; R-13"
S0, r0, q0 = D("100"), D("0.03"), D("0.01")


def strike_sets(E, L, S=S0):
    live = [S + i for i in range(-(E // 2), E - E // 2)]
    dead = []
    for i in range(L - E):
        dead.append(S - 15 - i // 2 if i % 2 == 0 else S + 15 + i // 2)
    return live, dead


def cexp(N, E, L, S=S0, r=r0, q=q0, a="0.2", drop_calls=False):
    live, dead = strike_sets(E, L, S)
    over = {}
    for K in dead:
        for rt in ("call", "put"):
            over[(O.fK(K), rt)] = {"mode": "stale"}
    if drop_calls:
        for K in live + dead:
            over[(O.fK(K), "call")] = {"drop": True}
    return ex(N, S, r, q, D(a), D(0), D(0), D(0), K=sorted(live + dead), over=over)


def main(argv):
    rows = []
    n = [0]

    def add(case, exps, params=None, pending=None, S=S0, r=r0, q=q0, want=("fwd", "atm", "exp", "cov"), tags=(), focus=None, rn=()):
        recs, truth = O.build(S, r, q, exps)
        P = params or O.default_params()
        n[0] += 1
        N0 = exps[0]["N"]
        fr = O.compute(S, r, q, recs, truth, P)
        if focus is None:
            focus = "expiries.%d" % N0
        d = "; ".join("N=%d: %s (listed %d, eligible %d)%s" % (
            N, fr["expiries"][N]["status"] + ("" if not fr["expiries"][N]["reason"] else "/" + fr["expiries"][N]["reason"]),
            fr["coverage"]["per_expiry"][str(N)]["listed_strikes"], fr["coverage"]["per_expiry"][str(N)]["eligible_strikes"],
            "" if fr["expiries"][N]["status"] != "available" else " ATM IV " + fr["expiries"][N]["atm_iv"]) for N in sorted(fr["expiries"]))
        rows.append(O.make_row("COV-%02d" % n[0], FAMILY, DR, list(RN) + list(rn), case, S, r, q, recs, truth, P, set(want), focus,
                               d, tags=["coverage"] + list(tags), pending=pending, keep_cov=True))
        return fr

    q01 = lambda t: {"question": "Q-01", "pick": "listed = strikes with any record; eligible = strikes with >=1 eligible quote (either right); ratio eligible/listed >= 3/5 inclusive",
                     "alternatives": ["R-83 literal (listed = eligible either right) makes the ratio always 1", "eligible = both rights eligible", "count contracts not strikes"], "text": t}
    # C1 ratio gate
    for (E, L, mn, tag) in [(3, 5, 3, "exactly 3/5"), (6, 10, 4, "exactly 6/10"), (9, 15, 4, "exactly 9/15"),
                            (5, 9, 4, "5/9 just below 3/5"), (4, 7, 4, "4/7 just below 3/5"), (3, 6, 3, "3/6 = 1/2"),
                            (7, 12, 4, "7/12 just below 3/5"), (4, 6, 4, "4/6 above 3/5"), (7, 11, 4, "7/11 above 3/5")]:
        add("ratio gate: %d eligible of %d listed strikes (%s), min_strikes %d" % (E, L, tag, mn), [cexp(30, E, L)],
            params=O.default_params(min_strikes=mn), pending=q01("coverage ratio"), tags=["ratio"])
    # C2 min_strikes
    q08 = {"question": "Q-08", "pick": "min_strikes counts strikes (eligible strikes >= min_strikes)",
           "alternatives": ["4 eligible contracts with at least 2 per right (matrix wording) would pass 2 strikes with both rights"],
           "text": "matrix: min_strikes 4 eligible strikes (at least 2 per right within +-10 percent of the forward)"}
    for (E, mn, pend, tag) in [(4, 4, None, "4 strikes, default 4: served"), (4, 5, None, "4 strikes, min_strikes 5: low_surface_coverage"),
                               (5, 5, None, "5 strikes, min_strikes 5: served"), (3, 3, None, "3 strikes, min_strikes 3: served"),
                               (3, 4, q08, "3 strikes, default 4: low_surface_coverage"), (2, 4, q08, "2 strikes, default 4: low_surface_coverage")]:
        add("min_strikes: " + tag, [cexp(30, E, E)], params=O.default_params(min_strikes=mn), pending=pend, tags=["min_strikes"], rn=["R-21"])
    # C3 one expiry per gate in one chain
    add("three expiries: 21 ok, 30 has 3 strikes (low), 45 ok", [cexp(21, 5, 5), cexp(30, 3, 3), cexp(45, 5, 5)],
        focus="expiries.30", tags=["multi_expiry", "min_strikes"])
    add("three expiries: 14 ratio 4/8 (low), 30 ok, 60 has no call quotes (no_atm_strike)", [cexp(14, 4, 8), cexp(30, 6, 6), cexp(60, 5, 5, drop_calls=True)],
        focus="expiries.14", pending=q01("per-expiry ratio and ATM precedence"), tags=["multi_expiry", "ratio"])
    add("three expiries all served; totals are the sums of the per-expiry counts", [cexp(9, 5, 5, S=D("250")), cexp(30, 6, 6, S=D("250")), cexp(91, 7, 7, S=D("250"))],
        S=D("250"), focus="expiries.30", tags=["multi_expiry"])
    # C4 expiry_min_days (R-13)
    def inv(case, N_value, code, pending=None, S=S0, scope="one"):
        nonlocal rows
        exps = [cexp(30, 5, 5, S=S)] + ([cexp(60, 5, 5, S=S)] if scope == "two" else [])
        recs, truth = O.build(S, r0, q0, exps)
        recs = copy.deepcopy(recs)
        if scope == "one":
            recs[3]["expiry_days"] = N_value
        elif scope == "all":
            for c_ in recs:
                c_["expiry_days"] = N_value
        else:
            for c_ in recs:
                if c_["expiry_days"] == 60:
                    c_["expiry_days"] = N_value
        n[0] += 1
        rows.append(O.invalid_row("COV-%02d" % n[0], FAMILY, "R-13 expiry_days >= 1 (M1)", ["R-13", "R-18"], case, S, r0, q0, recs, O.default_params(),
                                  code, "contract with expiry_days %r in an otherwise valid chain: request position 6" % (N_value,), tags=["expiry_min_days"], pending=pending))
    add("expiry_days = 1 (the minimum): served, T = 1/365", [cexp(1, 5, 5, S=D("300"))], S=D("300"), tags=["expiry_min_days"], rn=["R-17"])
    add("expiry_days = 2: served", [cexp(2, 5, 5, S=D("250"))], S=D("250"), tags=["expiry_min_days"], rn=["R-17"])
    inv("expiry_days = 0 is invalid_input bad_expiry (R-18)", 0, "bad_expiry")
    inv("every contract of the chain has expiry_days 0", 0, "bad_expiry", scope="all")
    inv("a valid 30d expiry plus a whole 0-day expiry: the 0-day contracts make the request invalid", 0, "bad_expiry", scope="two")
    inv("expiry_days = -1 is invalid_input bad_expiry", -1, "bad_expiry")
    inv("expiry_days = -30 on one contract of a valid chain", -30, "bad_expiry")
    pend_t = {"question": "Q-11", "pick": "malformed_type", "alternatives": ["bad_expiry"],
              "text": "position 6 says bad_expiry is 'not an int >= 1'; the type-first rule says a wrong type is malformed_type at the position of the check; both read the same slot"}
    inv("expiry_days given as text \"30\"", "30", "malformed_type", pending=pend_t)
    inv("expiry_days given as float 30.0", 30.0, "malformed_type", pending=pend_t)
    # C5 near-the-money rule
    q09 = {"question": "Q-09", "pick": "each right needs >= 2 eligible strikes within +-10 percent of the forward (inclusive); otherwise low_surface_coverage",
           "alternatives": ["the parenthetical of R-20 / matrix 4 is informative only and does not gate"], "text": "R-83 wording"}
    S = D("100")
    r_ = q_ = D("0")
    far = ex(30, S, r_, q_, D("0.2"), D(0), D(0), D(0), K=[D("85"), D("88"), D("112"), D("115")])
    add("four strikes, all beyond +-10 percent of the forward: no near strikes (S=100, r=q=0)", [far], S=S, r=r_, q=q_, pending=q09, tags=["near_rule"])
    edge = ex(30, S, r_, q_, D("0.2"), D(0), D(0), D(0), K=[D("90"), D("100"), D("110"), D("120")])
    add("strikes 90, 100, 110, 120 with F = 100: 90 and 110 sit exactly at +-10 percent (inclusive: served)", [edge], S=S, r=r_, q=q_, pending=q09, tags=["near_rule", "boundary"])
    out2 = ex(30, S, r_, q_, D("0.2"), D(0), D(0), D(0), K=[D("89"), D("100"), D("111"), D("120")])
    add("strikes 89, 100, 111, 120: only the 100 strike is within +-10 percent (low_surface_coverage)", [out2], S=S, r=r_, q=q_, pending=q09, tags=["near_rule", "boundary"])
    # C6 tenor use of a coverage-excluded expiry
    q10 = {"question": "Q-10", "pick": "a coverage-excluded expiry is treated like an expiry without an ATM strike (D14): bracket -> no_bracketing_expiry; exact -> its own reason low_surface_coverage",
           "alternatives": ["excluded expiries are skipped for tenors", "exact expiry reports no_bracketing_expiry"], "text": "matrix 5: expiry unavailable low_surface_coverage; tenors read ATM IV"}
    recs_args = dict(S=S0)
    add("tenor 30 bracket is 21 (ok) / 49 (3 strikes, low coverage)", [cexp(21, 5, 5), cexp(49, 3, 3)], params=O.default_params(tenors=[30]),
        want=("tenors", "exp"), focus="tenors.30", pending=q10, tags=["tenor_coverage"])
    add("tenor 30 exact expiry has 3 strikes (low coverage)", [cexp(21, 5, 5), cexp(30, 3, 3), cexp(49, 5, 5)], params=O.default_params(tenors=[30]),
        want=("tenors", "exp"), focus="tenors.30", pending=q10, tags=["tenor_coverage"])
    add("tenor 30 bracket is 21 (3 strikes, low coverage) / 49 (ok): no_bracketing_expiry", [cexp(21, 3, 3), cexp(49, 5, 5)], params=O.default_params(tenors=[30]),
        want=("tenors", "exp"), focus="tenors.30", pending=q10, tags=["tenor_coverage"])
    add("tenor 91 bracket is 60 (ok) / 120 (3 strikes, low coverage): no_bracketing_expiry", [cexp(60, 5, 5), cexp(120, 3, 3)], params=O.default_params(tenors=[91]),
        want=("tenors", "exp"), focus="tenors.91", pending=q10, tags=["tenor_coverage"])
    # structural request codes are reported before any evaluation, also when an upstream reason exists (RULED)
    def inv2(case, exps, params, N_value, S=S0):
        recs, truth = O.build(S, r0, q0, exps)
        recs = copy.deepcopy(recs)
        recs[2]["expiry_days"] = N_value
        n[0] += 1
        rows.append(O.invalid_row("COV-%02d" % n[0], FAMILY, "request position 6 before evaluation (RULED)", ["R-13", "R-66"], case, S, r0, q0, recs, params,
                                  "bad_expiry", "structural code first: the chain would otherwise be unavailable, but position 6 is reported", tags=["structural_first", "expiry_min_days"]))
    def stale_all(e, mode="stale"):
        e["over"] = {(O.fK(K), rt): {"mode": mode} for K in e["K"] for rt in ("call", "put")}
        return e
    inv2("all contracts stale (would be unavailable) plus one expiry_days 0: invalid_input bad_expiry", [stale_all(cexp(30, 5, 5))], O.default_params(), 0)
    inv2("low coverage expiry (3 strikes) plus expiry_days -1: invalid_input bad_expiry", [cexp(30, 3, 3)], O.default_params(), -1)
    inv2("delayed tag, all contracts crossed, expiry_days 0: invalid_input bad_expiry", [stale_all(cexp(30, 5, 5), "crossed")], O.default_params(feed_delay_tag="delayed"), 0)
    assert len(rows) >= 24
    hdr = O.header(FAMILY, rows, os.path.basename(__file__), NOTE)
    h = O.write_dataset(os.path.join(O.out_dir(argv), "m3a_cases_coverage.json"), hdr, rows)
    print("m3a_cases_coverage.json", len(rows), h)


if __name__ == "__main__":
    main(sys.argv)
