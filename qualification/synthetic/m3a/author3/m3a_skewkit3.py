"""Smile builders and tuners for the 25-delta families (SYNTHETIC, stdlib only)."""
from decimal import Decimal as D
from m3a_oracle3 import Surf, spec_of, ex, bisect_param, fs, quant


def s30(b="-0.5", c="1.5", q="0.01", r="0.03", atm="0.20", days=30, n=5, extra=(), conv="spot", **kw):
    """single 30-day expiry (plus optional extra expiries) smile chain."""
    exps = [ex(days, "1000", r, q, atm=atm, b=b, c=c, n=n, **kw)] + list(extra)
    sp = spec_of(exps, r=r, q=q)
    sp["conv"] = conv
    return sp


def parts(spec, target=30):
    sf = Surf(spec, conv=spec.get("conv", "spot"))
    return sf.cm(target, "p25"), sf.cm(target, "c25"), sf.cm(target, "atm_iv")


def skew_pts(spec):
    p, c, _ = parts(spec)
    if isinstance(p, str):
        return D(500)
    if isinstance(c, str):
        return D(-500)
    return (p - c) * 100


def curv_pts(spec):
    p, c, a = parts(spec)
    if isinstance(p, str) or isinstance(c, str):
        return D(500)
    return ((p + c) / 2 - a) * 100


def ratio_of(spec):
    p, c, a = parts(spec)
    if isinstance(p, str) or isinstance(c, str):
        return D(-500)
    return (p - a) / (c - a)


def tune(fn_of_param, build, target, lo, hi):
    p = bisect_param(lambda x: fn_of_param(build(x)), lo, hi, D(target))
    return p


def skew_spec(target, c="1.5", q="0.01", r="0.03", atm="0.20", lo=None, hi=None, **kw):
    if lo is None:
        lo, hi = ("-2.2", "1.0") if D(target) >= -4 and D(target) <= 12 else ("-2.2", "1.0")
        if D(target) < -4:
            lo, hi = "-0.2", "2.5"
    b = tune(skew_pts, lambda b: s30(b=fs(b), c=c, q=q, r=r, atm=atm, **kw), target, lo, hi)
    return s30(b=fs(b), c=c, q=q, r=r, atm=atm, **kw)


def curv_spec(target, b="-0.5", q="0.01", r="0.03", atm="0.20", lo="0", hi="40", **kw):
    c = tune(curv_pts, lambda c: s30(b=b, c=fs(c), q=q, r=r, atm=atm, **kw), target, lo, hi)
    return s30(b=b, c=fs(c), q=q, r=r, atm=atm, **kw)


def deviant(spec, ktarget, right, kind, dsig, days=30):
    """make one contract ineligible (kind excl/cross/stale) and give its strike a deviant IV, so that using it shows."""
    from m3a_oracle3 import sigma_at, fwd
    e = [x for x in spec["expiries"] if x["days"] == days][0]
    F = fwd(spec["S"], spec["r"], spec["q"], days)
    K = min(e["strikes"], key=lambda t: abs(t - D(ktarget)))
    e["mods"][(K, right)] = kind
    e["over"][K] = sigma_at(e, F, K) + D(dsig)
    return spec
