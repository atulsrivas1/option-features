"""M3a story S03: the 25-delta point kernel (one expiry, one right), both delta conventions.

Pure and single-threaded: no I/O, clocks, threads or shared state. Reads `chainiv` results only (the contract
IVs are solved once per chain and cutoff by `chainiv.IVChain` and passed in; this module never solves IV).

Call
    delta25_point(strikes, ivs, atm_strike, spot, rate, carry, expiry_days, right, convention="spot",
                  owner=None, certified_only=False)
    strikes      ascending strikes (Fraction) of the eligible contracts of ONE expiry and ONE right
    ivs          the cached contract IV (float) per strike; None marks a contract excluded by a solver failure
                 (R-109): it is skipped, the scan continues over its neighbours
    atm_strike   the expiry ATM strike (Fraction; chainiv rule: nearest the forward among strikes whose call and
                 put both pass, ties to the lower strike); the forward is used only through it
    spot, rate, carry   Fractions exactly as IVChain holds them (spot decimal, rate and yield via binary64)
    expiry_days  positive int, T = expiry_days/365 (ACT/365, D12)
    right        "put" or "call"; convention "spot" or "forward" (R-155); anything else raises ValueError
    owner        an open `arithmetic.numerical_owner()` context, or None to open one for this call
Returns the record {status, reason, value, strikes_used, evaluations}:
    available:   status "available", reason None, value float IV at |delta| = 0.25, strikes_used (K_inner, K_outer)
    unavailable: status "unavailable", reason "no_delta_bracket", value None, strikes_used ()
    evaluations: delta evaluations spent (one per strike visited; M3A-B12 counter, summed per chain by callers)

Rules (R-04, R-09, R-10, R-16, R-21, R-74, R-156, R-157)
- delta at the contract's own IV, T = days/365, absolute value: spot call e^{-qT} N(d1), put e^{-qT} N(-d1);
  forward call N(d1), put N(-d1). Only the requested convention is computed.
- Scan outward from the ATM strike over the usable strikes of the right (puts: strikes <= ATM, descending;
  calls: strikes >= ATM, ascending). The FIRST consecutive pair (d_i, d_i+1) with (d_i - 0.25)(d_i+1 - 0.25) <= 0
  is the bracket (target inclusive); IV = s_i + w (s_i+1 - s_i), w = (0.25 - d_i)/(d_i+1 - d_i) (w = 0 when the
  two deltas are equal). No bracket, or fewer than two usable strikes: no_delta_bracket; no extrapolation.

Performance design (owner goal; M3A-B2, B12, B1 per convention)
- Bracketed search (R-74): the scan stops at the first crossing, so the cost is the distance from ATM to the
  25-delta strike, never every contract. No list copies: indexes walk the caller's sequences in place.
- Float filter with certified fallback (R-05, Developer choice, identical bytes): each visited strike gets a
  binary64 delta; its side of 0.25 is trusted only when |d - 0.25| > FILTER_MARGIN and sigma sqrt(T) >=
  FILTER_MIN_SD. Otherwise, and ALWAYS for the two bracket strikes whose values enter the interpolation, the
  certified delta is used (`model.forward(..., "greeks.delta")` for spot, the same arb expression without the
  e^{-qT} factor for forward). The binary64 error of the float delta is below 1e-12 in this regime, far inside
  the margin, so every bracket decision equals the all-certified decision; `certified_only=True` runs the
  all-certified path (tests assert equal records).
"""
from fractions import Fraction
from math import erfc, exp, log, sqrt

from .arithmetic import TIERS, NumericalFailure, ball_rational, certify, enclosure, numerical_owner
from .model import Operands, Undefined, forward as certified_forward

CONVENTIONS = ("spot", "forward")
TARGET = Fraction(1, 4)
_TARGET_F = 0.25
FILTER_MARGIN = 1e-6
FILTER_MIN_SD = 1e-3
_RSQRT2 = 1.0 / sqrt(2.0)
_NO_BRACKET_STATUS = ("unavailable", "no_delta_bracket")


def _certified_delta(S, K, r, q, T, sigma, eta, convention, owner):
    """Correctly certified |delta| as binary64 (model certification), or None when undefined."""
    op = Operands(S, K, r, q, T, Fraction.from_float(sigma), eta)
    try:
        if convention == "spot":
            return certified_forward(op, "greeks.delta", owner).value
        if sigma == 0:
            spot = certified_forward(op, "greeks.delta", owner).value      # e^{-qT} or 0 at sigma 0
            return 1.0 if spot > 0 else 0.0
        return _forward_delta(op, owner)
    except (NumericalFailure, Undefined):
        return None


def _forward_delta(op, owner):
    """N(eta d1) by the model's arb expression (same d1 and erfc form as model.equation, no e^{-qT})."""
    arb, fmpq, ctx = owner
    failure = NumericalFailure()
    for bits in TIERS:
        ctx.prec = bits
        try:
            S, K, r, q, T, sigma = (ball_rational(x, arb, fmpq) for x in (op.spot, op.strike, op.rate, op.carry,
                                                                          op.time, op.sigma))
            den = sigma * T.sqrt()
            if not den > 0:
                raise NumericalFailure()
            d1 = ((S / K).log() + (r - q + sigma * sigma / 2) * T) / den
            if not abs(d1) <= 1000000:
                raise NumericalFailure()
            return certify(enclosure((-op.eta * d1 / arb(2).sqrt()).erfc() / 2)).value
        except NumericalFailure as exc:
            failure = exc
    raise failure


def delta25_point(strikes, ivs, atm_strike, spot, rate, carry, expiry_days, right, convention="spot",
                  owner=None, certified_only=False):
    if convention not in CONVENTIONS or type(convention) is not str:
        raise ValueError("delta_convention must be 'spot' or 'forward': %r" % (convention,))
    if right == "call":
        eta = 1
    elif right == "put":
        eta = -1
    else:
        raise ValueError("right must be call or put: %r" % (right,))
    if type(expiry_days) is not int or expiry_days <= 0:
        raise ValueError("expiry_days must be a positive integer: %r" % (expiry_days,))
    if owner is None:
        with numerical_owner() as opened:
            return _search(strikes, ivs, atm_strike, spot, rate, carry, expiry_days, eta, convention, opened,
                           certified_only)
    return _search(strikes, ivs, atm_strike, spot, rate, carry, expiry_days, eta, convention, owner, certified_only)


def _search(strikes, ivs, atm, S, r, q, days, eta, convention, owner, certified_only):
    n = len(strikes)
    T = Fraction(days, 365)
    Tf = days / 365.0
    sqrtT = sqrt(Tf)
    Sf, rf, qf = float(S), float(r), float(q)
    lnS = log(Sf)
    drift = (rf - qf) * Tf
    scale = 1.0 if convention == "forward" else exp(-qf * Tf)
    # scan order: calls from the first strike >= ATM upward, puts from the last strike <= ATM downward
    if eta == 1:
        i, stop, step = 0, n, 1
        while i < n and strikes[i] < atm:
            i += 1
    else:
        i, stop, step = n - 1, -1, -1
        while i >= 0 and strikes[i] > atm:
            i -= 1
    evaluations = 0
    prev = None            # (index, sigma, side of 0.25: -1, 0, +1, certified delta or None)
    while i != stop:
        sigma = ivs[i]
        if sigma is None:
            i += step
            continue
        evaluations += 1
        K = strikes[i]
        dc = None
        side = 0
        sd = sigma * sqrtT
        if not certified_only and sd >= FILTER_MIN_SD:
            d1 = (lnS - log(float(K)) + drift + 0.5 * sigma * sigma * Tf) / sd
            df = scale * 0.5 * erfc(-eta * d1 * _RSQRT2)
            gap = df - _TARGET_F
            if gap > FILTER_MARGIN:
                side = 1
            elif gap < -FILTER_MARGIN:
                side = -1
        if side == 0:
            dc = _certified_delta(S, K, r, q, T, sigma, eta, convention, owner)
            if dc is None:                 # undefined certified delta: skipped like an excluded contract
                i += step
                continue
            side = (dc > _TARGET_F) - (dc < _TARGET_F)
        if prev is not None and prev[2] * side <= 0:
            j, s1, side1, d1c = prev
            if not (side1 == side and side != 0):
                if d1c is None:
                    d1c = _certified_delta(S, strikes[j], r, q, T, s1, eta, convention, owner)
                if dc is None:
                    dc = _certified_delta(S, K, r, q, T, sigma, eta, convention, owner)
                if d1c is not None and dc is not None:
                    w = 0.0 if d1c == dc else (_TARGET_F - d1c) / (dc - d1c)
                    return {"status": "available", "reason": None, "value": s1 + w * (sigma - s1),
                            "strikes_used": (strikes[j], K), "evaluations": evaluations}
        prev = (i, sigma, side, dc)
        i += step
    return {"status": _NO_BRACKET_STATUS[0], "reason": _NO_BRACKET_STATUS[1], "value": None, "strikes_used": (),
            "evaluations": evaluations}
