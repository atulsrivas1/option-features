#!/usr/bin/env python3
"""Generator for m3a_cases_delta25.json (25-DELTA BRACKET family, 60 rows, M3A-0). SYNTHETIC. Seeded, deterministic.
G1 smile builder + G2 25-delta oracle (exact 60-digit deltas of the true sigma, delta-linear interpolation)."""
import os, random, sys
from decimal import Decimal as D
import m3a_oracle as O
from m3a_scen import ex, margin_ok, describe, ok_chain

FAMILY = "delta25"
NOTE = ("25-delta bracket rows. Quotes are BSM midpoints of the stated 6-decimal sigma (4-decimal bid/ask, spread 0.002). "
        "Expected IV25 = delta-linear interpolation between the first bracketing pair scanning outward from the ATM "
        "strike (R-04, R-09, R-10, R-21); delta = spot delta e^{-qT}N(+-d1) at the contract own sigma. "
        "Brackets and weights are oracle information only (not output keys). Tolerance IV 1e-4.")
RN = ["R-04", "R-05", "R-06", "R-09", "R-10", "R-16", "R-21"]
DR = "VR sec 2.9 (V8 25-delta), M3A-0"


def ab(x):
    return D(str(x))


def main(argv):
    rng = random.Random(O.SEED + 25)
    pick = lambda L: L[int(rng.random() * len(L))]
    rows = []

    # ---- D1 regular smiles (34 rows)
    n1 = 0
    while n1 < 34:
        N = pick([30, 21, 45, 60, 91, 14, 9, 120, 30, 60])
        S = ab(pick([100, 100, 150, 250]))
        r = ab(pick(["0.03", "0", "0.05", "-0.01", "0.02"]))
        q = ab(pick(["0.01", "0", "0.02", "0.03"]))
        a, b, c = ab(pick(["0.12", "0.18", "0.22", "0.3", "0.4"])), ab(pick(["-0.5", "-0.25", "-0.1", "0", "0.1", "0.3"])), ab(pick(["0", "0.2", "0.6", "1.0", "2.0"]))
        sh = ab(pick(["0", "0", "0.01", "-0.015", "0.03"]))
        st, off = ab(pick(["0.3", "0.35", "0.4"])), ab(pick(["0", "0.15", "0.3", "-0.2"]))
        try:
            e = ex(N, S, r, q, a, b, c, sh, st, -4, 4, off)
            recs, truth = O.build(S, r, q, [e])
            P = O.default_params()
            fr = O.compute(S, r, q, recs, truth, P)
        except AssertionError:
            continue
        x = fr["expiries"][N]
        if x["status"] != "available" or x["put25_iv"]["status"] != "available" or x["call25_iv"]["status"] != "available":
            continue
        if not margin_ok(fr) or O.min_vega(fr, truth, {"atm", "p25", "c25"}) < 4:
            continue
        n1 += 1
        focus = "expiries.%d.%s" % (N, "put25_iv" if n1 % 2 else "call25_iv")
        shown = " (put shift %s)" % sh if sh != 0 else ""
        rows.append(O.make_row(
            "D25-R%02d" % n1, FAMILY, DR, RN,
            "smile a=%s b=%s c=%s%s, N=%d, S=%s r=%s q=%s" % (a, b, c, shown, N, S, r, q),
            S, r, q, recs, truth, P, {"fwd", "atm", "p25", "c25", "cov"}, focus,
            describe(fr, N), tags=["delta25", "regular"] + (["put_shift"] if sh != 0 else []), g2=True))

    # ---- D4 target exactly on a listed strike (6 rows): solve the strike with delta = 0.25 (+-1e-9)
    tdone = 0
    for (N, side, a, b, c, S) in [(30, "put", "0.2", "-0.2", "0.5", 100), (30, "call", "0.2", "-0.2", "0.5", 100),
                                  (60, "put", "0.25", "-0.1", "0.3", 100), (60, "call", "0.25", "0.1", "0.3", 100),
                                  (91, "put", "0.3", "-0.3", "1.0", 100), (14, "call", "0.15", "0.05", "0.2", 150)]:
        S, r, q = ab(S), ab("0.03"), ab("0.01")
        a, b, c = ab(a), ab(b), ab(c)
        F = O.fwd(S, r, q, N)
        T = D(N) / 365
        sig = O.smile(F, a, b, c)
        lo_k, hi_k = (D("-1.3"), D("-0.1")) if side == "put" else (D("0.1"), D("1.3"))
        sd = a * T.sqrt()

        def f(k):
            K = F * (k * sd).exp()
            return O.delta_abs(S, K, T, r, q, sig(K, side), side) - D("0.25")
        flo, fhi = f(lo_k), f(hi_k)
        for _ in range(80):
            mid = (lo_k + hi_k) / 2
            fm = f(mid)
            if (fm > 0) == (flo > 0):
                lo_k, flo = mid, fm
            else:
                hi_k = mid
        Kstar = (F * (((lo_k + hi_k) / 2) * sd).exp()).quantize(D("1e-8"))
        base = ex(N, S, r, q, a, b, c, D(0), D("0.35"), -4, 4, D(0))
        # replace the grid strike nearest to Kstar on the requested side by Kstar
        Ks = [K for K in base["K"]]
        j = min(range(len(Ks)), key=lambda i: abs(Ks[i] - Kstar))
        Ks[j] = Kstar
        e = ex(N, S, r, q, a, b, c, D(0), K=sorted(set(Ks)))
        recs, truth = O.build(S, r, q, [e])
        P = O.default_params()
        fr = O.compute(S, r, q, recs, truth, P)
        x = fr["expiries"][N]
        assert x["status"] == "available" and x[side + "25_iv"]["status"] == "available", (N, side)
        assert O.min_vega(fr, truth, {"atm", "p25", "c25"}) >= 4
        tdone += 1
        row = O.make_row("D25-T%02d" % tdone, FAMILY, DR, RN + ["R-62"],
                         "target exactly on listed strike %s (%s side), delta within 1e-8 of 0.25" % (O.fK(Kstar), side),
                         S, r, q, recs, truth, P, {"fwd", "atm", "p25", "c25", "cov"},
                         "expiries.%d.%s25_iv" % (N, side), describe(fr, N) + "; strike solved so |delta-0.25|<1e-8: IV25 is the sigma of that strike",
                         tags=["delta25", "target_on_strike", "near_threshold:R-62"], g2=True)
        row["oracle"]["on_strike_value"] = str(sig(Kstar, side))
        rows.append(row)

    # ---- D5 steep skew, non-monotone delta (first crossing outward decides, not the last) (6 rows)
    n5 = 0
    D5 = [(91, "0.1", "0", "20", "put"), (91, "0.12", "0", "20", "put"), (91, "0.08", "-0.5", "20", "put"),
          (91, "0.06", "-0.5", "20", "put"), (91, "0.05", "0.5", "5", "call"), (91, "0.05", "1.0", "5", "call"),
          (91, "0.05", "0.5", "10", "call"), (91, "0.05", "0", "10", "call"), (91, "0.08", "0", "10", "call")]
    for (N, a, b, c, side) in D5:
        S, r, q = ab(100), ab("0.02"), ab("0.01")
        a, b, c = ab(a), ab(b), ab(c)
        if side == "call":
            kk = [-0.1, 0.0, 0.02, 0.04, 0.06, 0.1, 0.14, 0.18, 0.22, 0.26, 0.3, 0.34, 0.38, 0.42]
        else:
            kk = [-0.26, -0.22, -0.18, -0.14, -0.1, -0.06, -0.03, 0.0, 0.1, 0.3]
        F = O.fwd(S, r, q, N)
        e = ex(N, S, r, q, a, b, c, D(0), K=sorted({(F * D(str(k)).exp()).quantize(D("0.01")) for k in kk}))
        try:
            recs, truth = O.build(S, r, q, [e])
        except AssertionError:
            continue
        P = O.default_params()
        fr = O.compute(S, r, q, recs, truth, P)
        x = fr["expiries"][N]
        if x["status"] != "available":
            continue
        pts = fr["g2"][str(N)][side]
        cr = 0
        for i in range(len(pts) - 1):
            fi, fj = D(pts[i]["delta"]) - D("0.25"), D(pts[i + 1]["delta"]) - D("0.25")
            if fi * fj <= 0:
                cr += 1
        if cr < 2 or not margin_ok(fr) or O.min_vega(fr, truth, {"atm", "p25", "c25"}) < 4:
            continue
        n5 += 1
        row = O.make_row("D25-N%02d" % n5, FAMILY, DR, RN, "steep skew, non-monotone %s delta (%d crossings of 0.25), N=%d" % (side, cr, N),
                         S, r, q, recs, truth, P, {"fwd", "atm", "p25", "c25", "cov"},
                         "expiries.%d.%s25_iv" % (N, side), describe(fr, N) + "; %d crossings outward: the first one decides (R-10)" % cr,
                         tags=["delta25", "non_monotone", "steep_skew"], g2=True)
        row["oracle"]["crossings"] = cr
        rows.append(row)
    assert n5 >= 6, n5

    # ---- D6 no_delta_bracket (8 rows)
    d6 = []
    # (a) narrow grids: both sides unavailable
    for (N, S, a) in [(30, 100, "0.2"), (60, 100, "0.3"), (9, 250, "0.25")]:
        S_, r, q = ab(S), ab("0.03"), ab("0.01")
        e = ex(N, S_, r, q, ab(a), D(0), D(0), D(0), D("0.12"), -4, 4, D(0))
        d6.append(("narrow grid (+-0.5 sd): both targets outside the listed deltas, N=%d" % N, S_, r, q, [e], "put25_iv", None))
    # (b) one-sided: wide put side, narrow call side
    for (N, a) in [(30, "0.2"), (45, "0.25")]:
        S_, r, q = ab(100), ab("0.03"), ab("0.01")
        e = ex(N, S_, r, q, ab(a), D(0), D(0), D(0), kk=[-1.4, -1.05, -0.7, -0.35, 0.0, 0.1, 0.2, 0.3])
        d6.append(("wide put side, call side stops inside 25 delta, N=%d" % N, S_, r, q, [e], "call25_iv", None))
    # (c) outer put quotes missing -> put side has no bracket, call side fine
    S_, r, q = ab(100), ab("0.03"), ab("0.01")
    base = ex(30, S_, r, q, ab("0.2"), ab("-0.1"), ab("0.5"), D(0), D("0.35"), -4, 4, D(0))
    F = O.fwd(S_, r, q, 30)
    Ks = base["K"]
    over = {}
    # drop put quotes of the three lowest strikes (beyond the crossing)
    for K in Ks[:3]:
        over[(O.fK(K), "put")] = {"drop": True}
    base["over"] = over
    d6.append(("put quotes of the three lowest strikes absent: put side lacks a bracket", S_, r, q, [base], "put25_iv", None))
    # (d) bracket strike excluded (stale): the next eligible strike is used; value changes; and (e) both bracket strikes excluded
    base = ex(30, S_, r, q, ab("0.2"), ab("-0.2"), ab("0.5"), D(0), D("0.35"), -4, 4, D(0))
    recs0, truth0 = O.build(S_, r, q, [base])
    fr0 = O.compute(S_, r, q, recs0, truth0, O.default_params())
    br = fr0["expiries"][30]["call25_iv"]["bracket"]
    base2 = ex(30, S_, r, q, ab("0.2"), ab("-0.2"), ab("0.5"), D(0), D("0.35"), -4, 4, D(0),
               over={(br[1], "call"): {"mode": "stale"}})
    d6.append(("call bracket strike %s stale: the next eligible strike forms the pair" % br[1], S_, r, q, [base2], "call25_iv", ["stale"]))
    Kup = [K for K in base["K"] if K >= D(br[1])]
    base3 = ex(30, S_, r, q, ab("0.2"), ab("-0.2"), ab("0.5"), D(0), D("0.35"), -4, 4, D(0),
               over={(O.fK(K), "call"): {"mode": "stale"} for K in Kup})
    d6.append(("call strikes from %s outward all stale: only the ATM strike and one more remain on the call side" % br[1],
               S_, r, q, [base3], "call25_iv", ["stale"]))
    base4 = ex(30, S_, r, q, ab("0.2"), ab("-0.2"), ab("0.5"), D(0), D("0.35"), -4, 4, D(0),
               over={(br[0], "call"): {"mode": "locked"}, (br[1], "call"): {"mode": "crossed"}})
    d6.append(("both call bracket strikes (%s locked, %s crossed) excluded: pair is the ATM strike and the next eligible strike" % (br[0], br[1]),
               S_, r, q, [base4], "call25_iv", ["locked", "crossed"]))
    n6 = 0
    for (case, S2, r2, q2, exps, fkey, tg) in d6:
        recs, truth = O.build(S2, r2, q2, exps)
        P = O.default_params()
        fr = O.compute(S2, r2, q2, recs, truth, P)
        N = exps[0]["N"]
        n6 += 1
        # focus: the side that is unavailable for narrow rows, else named key
        if not margin_ok(fr):
            raise SystemExit("D6 margin %s" % case)
        rows.append(O.make_row("D25-X%02d" % n6, FAMILY, DR, RN + ["R-16"], case, S2, r2, q2, recs, truth, P,
                               {"fwd", "atm", "p25", "c25", "cov"}, "expiries.%d.%s" % (N, fkey), describe(fr, N),
                               tags=["delta25", "no_delta_bracket" if fr["expiries"][N][fkey.replace("_iv", "_iv")]["status"] == "unavailable" else "excluded_bracket"] + (tg or []), g2=True))

    # ---- D7 minimum strikes (6 rows)
    n7 = 0
    for (N, S, a, kk, mn, tag) in [(30, 100, "0.2", [-0.9, -0.15, 0.2, 0.9], 4, "four strikes, default min_strikes 4"),
                                    (60, 100, "0.25", [-0.95, -0.2, 0.15, 0.85], 4, "four strikes, N=60"),
                                    (21, 100, "0.3", [-0.85, -0.1, 0.25, 0.95], 4, "four strikes, N=21"),
                                    (30, 100, "0.2", [-0.9, -0.15, 0.2], 2, "three strikes, min_strikes 2: call side has only one strike at or above the ATM strike"),
                                    (45, 100, "0.22", [-0.9, -0.15, 0.2], 2, "three strikes, min_strikes 2, N=45"),
                                    (30, 100, "0.2", [-0.9, -0.15], 2, "two strikes, min_strikes 2: put pair brackets, call side has no pair")]:
        S_, r, q = ab(S), ab("0.03"), ab("0.01")
        e = ex(N, S_, r, q, ab(a), D(0), D(0), D(0), kk=kk)
        recs, truth = O.build(S_, r, q, [e])
        P = O.default_params(min_strikes=mn)
        fr = O.compute(S_, r, q, recs, truth, P)
        x = fr["expiries"][N]
        assert x["status"] == "available", (tag, x)
        n7 += 1
        rows.append(O.make_row("D25-M%02d" % n7, FAMILY, DR, RN + ["R-20", "R-21"], "minimum strikes: " + tag, S_, r, q, recs, truth, P,
                               {"fwd", "atm", "p25", "c25", "cov"}, "expiries.%d.put25_iv" % N, describe(fr, N),
                               tags=["delta25", "min_strikes"], g2=True))
    # ================= OWNER DECISION 3: delta_convention in {spot, forward} (default spot) =================
    import copy
    OD = ["OD-3"]
    def margin_row(rw):
        for N, sd in rw["oracle"]["g2"].items():
            for side, pts in sd.items():
                for p in pts:
                    if abs(D(p["delta"]) - D("0.25")) < D("0.0003"):
                        return False
        return True
    base = {r_["id"]: r_ for r_ in rows}
    clones = []
    for rid in ["D25-R%02d" % i for i in range(1, 13)] + ["D25-T01", "D25-T02", "D25-N01", "D25-N04", "D25-N05", "D25-N07", "D25-X01", "D25-X04", "D25-X06",
                                                            "D25-X07", "D25-X09", "D25-M01", "D25-M04", "D25-M06"]:
        if rid not in base:
            continue
        c = O.clone_row(base[rid], rid + "F", "forward", " [forward delta]", tags=["convention", "forward"])
        if margin_row(c):
            clones.append(c)
        else:
            print("skip clone", rid)
    rows.extend(clones)
    def pair(tag, N, S, r, q, a, b, c, sh=D(0), need_diff=None, note=""):
        e = ok_chain(N, S, r, q, a, b, c, sh, need_diff=need_diff)
        recs, truth = O.build(S, r, q, [e])
        out = {}
        for cv in ("spot", "forward"):
            P = O.default_params(delta_convention=cv)
            fr = O.compute(S, r, q, recs, truth, P)
            out[cv] = (fr, O.make_row("D25-%s-%s" % (tag, "S" if cv == "spot" else "F"), FAMILY, DR, RN + OD + ["R-04"],
                                      "%s, %s delta, N=%d q=%s" % (note, cv, N, q), S, r, q, recs, truth, P, {"fwd", "atm", "p25", "c25", "cov"},
                                      "expiries.%d.put25_iv" % N, describe(fr, N), tags=["delta25", "convention", cv], g2=True))
        return out
    sym_done = 0
    # q = 0: spot = forward exactly (same formula); tolerance 0, values identical
    for i, (N, a, b, c) in enumerate([(9, "0.2", "-0.3", "0.5"), (30, "0.25", "-0.2", "0.4"), (60, "0.3", "-0.1", "0.3")]):
        S = ab(250) if N == 9 else ab(100)
        o = pair("Q0-%d" % (i + 1), N, S, ab("0.03"), D(0), ab(a), ab(b), ab(c), note="q=0: spot delta equals forward delta (e^{-qT}=1)")
        for k in ("put25_iv", "call25_iv"):
            assert o["spot"][0]["expiries"][N][k]["value"] == o["forward"][0]["expiries"][N][k]["value"]
        for cv in o:
            o[cv][1]["oracle"]["equality"] = "q=0: both conventions give identical IV25 (exact, tolerance 0)"
            rows.append(o[cv][1])
        # symmetry bookkeeping
        sym_done += 1
    # tiny T: N=2, q=0.05: e^{-qT}=0.99973, results equal within 3e-5 (stated tolerance)
    for i, (N, a) in enumerate([(2, "0.2"), (3, "0.25")]):
        o = pair("TT-%d" % (i + 1), N, ab(300), ab("0.03"), ab("0.05"), ab(a), ab("-0.2"), ab("0.4"), note="tiny T with q=0.05: conventions agree within the 3e-5 IV tolerance")
        for k in ("put25_iv", "call25_iv"):
            dv = abs(D(o["spot"][0]["expiries"][N][k]["value"]) - D(o["forward"][0]["expiries"][N][k]["value"]))
            assert dv < D("0.00003"), (N, k, dv)
        for cv in o:
            o[cv][1]["oracle"]["equality"] = "tiny T: |IV25 spot - IV25 forward| < 3e-5"
            rows.append(o[cv][1])
    # divergence: long expiry or high q: different IV (>= 2e-4)
    for i, (N, q, a, b, c) in enumerate([(365, "0.08", "0.2", "-0.3", "0.5"), (730, "0.05", "0.2", "-0.2", "0.3"), (180, "0.10", "0.25", "-0.3", "0.4"), (365, "0.03", "0.3", "-0.3", "0.6")]):
        o = pair("DV-%d" % (i + 1), N, ab(100), ab("0.03"), ab(q), ab(a), ab(b), ab(c), need_diff=D("0.0002"), note="divergence: long expiry or high q, other IV25")
        for cv in o:
            o[cv][1]["oracle"]["divergence"] = "spot and forward delta pick different pairs/IV25 (difference >= 2e-4)"
            rows.append(o[cv][1])
    # call-25 / put-75 symmetry: forward delta always, spot delta only when q = 0 (oracle information, checked here)
    for i, (N, q) in enumerate([(30, "0"), (60, "0"), (91, "0"), (30, "0.05"), (91, "0.05"), (365, "0.08")]):
        S, r_, q_ = ab(100), ab("0.03"), ab(q)
        e = ok_chain(N, S, r_, q_, ab("0.2"), D(0), D(0), D(0))     # flat smile: call and put IV equal at every strike
        recs, truth = O.build(S, r_, q_, [e])
        P = O.default_params(delta_convention="forward")
        fr = O.compute(S, r_, q_, recs, truth, P)
        T = D(N) / 365
        sym = {}
        for cv in ("spot", "forward"):
            worst = D(0)
            for K in e["K"]:
                sg = truth[O.cid(N, "call", K)]["sigma"]
                tot = O.delta_abs(S, K, T, r_, q_, sg, "call", cv) + O.delta_abs(S, K, T, r_, q_, sg, "put", cv)    # call delta + |put delta|
                worst = max(worst, abs(tot - (D(1) if cv == "forward" else (-q_ * T).exp())))
            sym[cv] = format(worst, ".3e")
        assert D(sym["forward"]) < D("1e-40")
        rw = O.make_row("D25-SY-%d" % (i + 1), FAMILY, DR, RN + OD + ["R-04"], "call-25 / put-75 symmetry bookkeeping, forward delta, N=%d q=%s (flat smile)" % (N, q), S, r_, q_, recs, truth, P,
                        {"fwd", "atm", "p25", "c25", "cov"}, "expiries.%d.put25_iv" % N, describe(fr, N), tags=["delta25", "convention", "forward", "symmetry"], g2=True)
        rw["oracle"]["symmetry"] = {"statement": "call delta + |put delta| at one strike and one sigma: forward delta = 1 always; spot delta = e^{-qT} (= 1 only when q = 0), so call-25 strike = put-75 strike only under forward delta (and under spot when q=0)",
                                    "max_abs_deviation_from_expected_sum": sym, "q_is_zero": q == "0"}
        rows.append(rw)
    # default (key omitted) rows: result echoes spot
    for rid in ("D25-R01", "D25-R02"):
        rows.append(O.clone_row(base[rid], rid + "D", "spot", " [delta_convention omitted: default spot, echoed]", omit=True, tags=["convention", "default"]))
    # selector validation: single error each (value code convention_not_allowed, wrong type malformed_type)
    e0 = ok_chain(30, ab(100), ab("0.03"), ab("0.01"), ab("0.2"), ab("-0.3"), ab("0.5"))
    recs0, truth0 = O.build(ab(100), ab("0.03"), ab("0.01"), [e0])
    for i, (bad, code) in enumerate([("Spot", "convention_not_allowed"), ("forward ", "convention_not_allowed"), ("", "convention_not_allowed"), ("delta", "convention_not_allowed"),
                                     (25, "malformed_type"), (None, "malformed_type"), (True, "malformed_type")]):
        P = O.default_params(delta_convention=bad)
        rows.append(O.invalid_row("D25-V%d" % (i + 1), FAMILY, "owner decision 3: delta_convention selector", OD, "delta_convention = %r" % (bad,), ab(100), ab("0.03"), ab("0.01"),
                                  copy.deepcopy(recs0), P, code, "only the selector is wrong; code %s (string outside {spot, forward} is a value code, a non-string is a type error)" % code,
                                  tags=["convention", "selector"]))
    assert len(rows) >= 60, len(rows)
    hdr = O.header(FAMILY, rows, os.path.basename(__file__), NOTE)
    h = O.write_dataset(os.path.join(O.out_dir(argv), "m3a_cases_delta25.json"), hdr, rows)
    print("m3a_cases_delta25.json", len(rows), h)


if __name__ == "__main__":
    main(sys.argv)
