"""Scenario helpers shared by the author-1 generators (G1 builders). SYNTHETIC, stdlib only."""
from decimal import Decimal as D, ROUND_HALF_EVEN
from m3a_oracle import (fwd, grid, smile, flat, fK, f8, compute, build, default_params, make_row, min_vega)


def ex(N, S, r, q, a, b=D(0), c=D(0), shift=D(0), step=D("0.35"), jlo=-4, jhi=4, off=D(0),
       style="european", over=None, K=None, tick=D("0.01"), kk=None):
    """One expiry spec. Strikes: explicit list K, or kk = list of k in units of sigma*sqrt(T), or a j-grid."""
    F = fwd(S, r, q, N)
    sd = a * (D(N) / 365).sqrt()
    if K is None and kk is not None:
        K = sorted({(F * (D(str(x)) * sd).exp()).quantize(tick, rounding=ROUND_HALF_EVEN) for x in kk})
    if K is None:
        K = grid(F, N, a, step, jlo, jhi, off, tick)
    sig = smile(F, a, b, c, shift) if (b != 0 or c != 0) else flat(a, shift)
    return dict(N=N, K=K, sig=sig, style=style, over=over or {})


OFFS = ("0.1", "0", "0.2", "-0.1", "0.25", "0.05", "0.15", "-0.2", "0.3", "-0.05", "0.12", "0.18", "-0.15", "0.35")


def ok_chain(N, S, r, q, a, b, c, sh=D(0), step=D("0.35"), style="european", need_diff=None):
    """First grid offset whose 25-delta points are clear (margin) and bracketed under BOTH conventions, vega >= 4.
    need_diff: minimum |IV25 spot - IV25 forward| required on the put side (divergence rows)."""
    from m3a_oracle import build as _b
    for off in OFFS:
        e = ex(N, S, r, q, a, b, c, sh, step, -4, 4, D(off), style=style)
        try:
            recs, truth = _b(S, r, q, [e])
        except AssertionError:
            continue
        frs = {cv: compute(S, r, q, recs, truth, default_params(delta_convention=cv)) for cv in ("spot", "forward")}
        good = True
        for cv, fr in frs.items():
            x = fr["expiries"][N]
            if x["status"] != "available" or x["put25_iv"]["status"] != "available" or x["call25_iv"]["status"] != "available"                     or not margin_ok(fr) or min_vega(fr, truth, {"atm", "p25", "c25"}) < 4:
                good = False
        if good and need_diff is not None:
            d = max(abs(D(frs["spot"]["expiries"][N][k]["value"]) - D(frs["forward"]["expiries"][N][k]["value"])) for k in ("put25_iv", "call25_iv"))
            good = d >= need_diff
        if good:
            return e
    raise SystemExit("no clear offset for %s" % ((N, str(S), str(r), str(q), str(a), str(b), str(c)),))


def margin_ok(frame, eps=D("0.0003"), target=D("0.25")):
    for N, sides in frame["g2"].items():
        for side, pts in sides.items():
            for p in pts:
                if abs(D(p["delta"]) - target) < eps:
                    return False
    return True


def describe(frame, N):
    e = frame["expiries"][N]
    if e["status"] != "available":
        return "expiry %d unavailable (%s)" % (N, e["reason"])
    parts = ["F=%s" % e["forward"], "ATM strike %s IV %s" % (e["atm_strike"], e["atm_iv"])]
    for s in ("put", "call"):
        r = e[s + "25_iv"]
        if r["status"] == "available":
            parts.append("%s: pair %s w=%s IV25=%s" % (s, "/".join(r["bracket"]), r["weight"], r["value"]))
        else:
            parts.append("%s: %s" % (s, r["reason"]))
    return "; ".join(parts)
