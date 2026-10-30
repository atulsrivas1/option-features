"""M3a tenor kernel (S04): constant-maturity IV at tenors 9, 30 and 91 days from cached per-expiry ATM IVs.

Pure, single-threaded, no I/O, no clocks, no IV solve (IV comes from chainiv.IVChain via S05).

Input: `expiries`, an iterable of per-expiry records (days, status, reason, atm_iv) where days is a positive int,
status is "available" or "unavailable", reason is None or the expiry's closed-set reason (for example
no_atm_strike, low_surface_coverage, solver reasons) and atm_iv is a binary64 float (None when unavailable).
`ExpiryIV` is the named form; plain 4-tuples work too. Input order does not matter.

Output: {tenor: TenorIV(status, reason, iv, method, expiries_used)} in the order of `targets`.
  available   -> reason None, iv binary64 float (rounding to 8 decimals is S01's, at the envelope),
                 method "as_is" with expiries_used (days,) or "variance_interpolation" with (lo, hi)
  unavailable -> iv None, method None, expiries_used None
Rules (the M1 iv_30d(target_days) rule, R-104, R-139, R-178):
  - an expiry exactly at the tenor is used as is; if it is unavailable the tenor carries that expiry's reason
    (an exact expiry failing coverage gives low_surface_coverage, R-178)
  - otherwise the nearest listed expiry below and above bracket the tenor; none below or none above:
    no_bracketing_expiry (no extrapolation)
  - a bracketing expiry without an ATM strike or excluded by coverage counts as no ATM: no_bracketing_expiry
    (R-104, R-139); any other expiry reason is passed through; the lower expiry is judged first
  - variance interpolation is linear in total variance w = iv^2 * days: w_t = w_lo + (w_hi - w_lo)(t-lo)/(hi-lo),
    iv = sqrt(w_t / t). Same float operations as chainiv.IVChain.iv_30d, so the values are byte-equal.
Tenor membership ({9, 30, 91}, tenor_not_allowed) is validated by S09, not here.
"""
from collections import namedtuple
from math import sqrt

TENORS = (9, 30, 91)

ExpiryIV = namedtuple("ExpiryIV", "days status reason atm_iv")
TenorIV = namedtuple("TenorIV", "status reason iv method expiries_used")

_BRACKET_NO_ATM = ("no_atm_strike", "low_surface_coverage")
_NO_BRACKET = TenorIV("unavailable", "no_bracketing_expiry", None, None, None)


def tenors(expiries, targets=TENORS):
    recs = expiries if type(expiries) is list else list(expiries)
    # ascending by days; skip the sort when already ordered (the usual case: IVChain.atm_iv_all is ascending)
    prev = 0
    for r in recs:
        if r[0] < prev:
            recs = sorted(recs, key=_days)
            break
        prev = r[0]
    out = {}
    for t in targets:
        lo = hi = None
        exact = None
        for r in recs:
            d = r[0]
            if d < t:
                lo = r
            elif d > t:
                hi = r
                break
            else:
                exact = r
                break
        if exact is not None:
            if exact[1] != "available":
                out[t] = TenorIV("unavailable", exact[2], None, None, None)
            else:
                out[t] = TenorIV("available", None, exact[3], "as_is", (t,))
            continue
        if lo is None or hi is None:
            out[t] = _NO_BRACKET
            continue
        if lo[1] != "available":
            out[t] = _failed(lo[2])
            continue
        if hi[1] != "available":
            out[t] = _failed(hi[2])
            continue
        d_lo, d_hi = lo[0], hi[0]
        w_lo = lo[3] * lo[3] * d_lo
        w_hi = hi[3] * hi[3] * d_hi
        variance = w_lo + (w_hi - w_lo) * (t - d_lo) / (d_hi - d_lo)
        out[t] = TenorIV("available", None, sqrt(variance / t), "variance_interpolation", (d_lo, d_hi))
    return out


def _days(r):
    return r[0]


def _failed(reason):
    if reason in _BRACKET_NO_ATM:
        return _NO_BRACKET
    return TenorIV("unavailable", reason, None, None, None)
