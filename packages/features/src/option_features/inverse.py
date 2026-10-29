"""Finite certified bisection, preserving a root-containing volatility bracket."""
from dataclasses import dataclass
from fractions import Fraction
from option_feature_contracts import SolverEvidence
from .arithmetic import (TIERS, NumericalFailure, decimal_exact, exact_decimal, nearest_binary64, certified_value, Ends)
from .model import Operands, bounds, forward
from .model import price_interval_ends as price_interval   # lazy Ends; tests may patch inverse.price_interval with a PriceEnclosure stub
from . import floatfilter

@dataclass(frozen=True, slots=True)
class InverseResult:
    value: float | None
    status: str
    reason: str
    evidence: SolverEvidence | None

def _fractions(enclosed):
    if type(enclosed) is Ends:
        return enclosed.fractions()
    return decimal_exact(enclosed.value_low), decimal_exact(enclosed.value_high)

def _diagnostic(value):
    try:
        return nearest_binary64(value)
    except NumericalFailure:
        return None

def _with_sigma(operands, sigma_f):
    return Operands(operands.spot, operands.strike, operands.rate, operands.carry, operands.time, sigma_f, operands.eta, operands.cache)

def _price(operands, sigma_f, target, owner):
    """sigma_f is Fraction.from_float(sigma), converted once by the caller. Returns the lazy enclosure (Ends;
    exact endpoint fractions and the Decimal enclosure are built on demand) and its ordering sign."""
    latest = None
    failure = NumericalFailure("bound_precision")
    shifted = _with_sigma(operands, sigma_f)
    for bits in TIERS:
        try:
            latest = price_interval(shifted, owner, bits)
            if type(latest) is not Ends:
                latest = Ends(enc=latest)
            sign = latest.sign_vs(target)
            if sign:
                return latest, sign
        except NumericalFailure as exc:
            failure = exc
    if latest is None:
        raise failure
    return latest, 0

def _reported(enclosed):
    """The PriceEnclosure to report for a candidate (lazy Ends, or an enclosure already built)."""
    return enclosed.enclosure() if type(enclosed) is Ends else enclosed

def _conditioning(operands, sigma_f, target, config, owner):
    """Certify the same Vega inequality for every available IV candidate."""
    try:
        certificate = forward(_with_sigma(operands, sigma_f), "greeks.vega", owner)
        volatility_tolerance = Fraction.from_float(config.vol_abs_tol)+Fraction.from_float(config.vol_rel_tol)*abs(sigma_f)
        price_tolerance = Fraction.from_float(config.price_abs_tol)+Fraction.from_float(config.price_rel_tol)*abs(target)
        maximum = max(abs(certificate.low), abs(certificate.high))
        minimum = min(abs(certificate.low), abs(certificate.high)) if certificate.low*certificate.high > 0 else Fraction(0)
        condition = True if maximum*volatility_tolerance <= price_tolerance else (False if minimum*volatility_tolerance > price_tolerance else None)
        return certificate.value, condition
    except NumericalFailure:
        return None, None

class _FilterAbort(Exception):
    """Internal: the float-filtered run met a state it cannot reproduce; rerun fully certified."""

def _midpoint(lo, hi):
    """nearest_binary64((Fraction(lo)+Fraction(hi))/2) without Fractions: fl(lo+hi) is the correctly rounded
    sum and halving is exact for normal results, so the two agree; tiny or huge brackets use the exact path."""
    if 1e-290 <= hi <= 1e300:
        return (lo+hi)/2
    return nearest_binary64((Fraction.from_float(lo)+Fraction.from_float(hi))/2)

def solve(operands, target, config, converted, owner, float_filter=True):
    """Target is exact rational midpoint; no supplied volatility is consumed. float_filter=False forces
    the fully certified path (always available; also the fallback for any doubt). Result bytes are
    identical either way (docs/M1_STAGE1_FLOAT_FILTER_BOUND.md)."""
    if float_filter:
        try:
            return _solve(operands, target, config, converted, owner, True)
        except _FilterAbort:
            pass
    return _solve(operands, target, config, converted, owner, False)

def _solve(operands, target, config, converted, owner, use_filter):
    iterations = 0
    lo, hi = 0.0, config.max_sigma
    lower = upper = candidate_enclosure = None
    candidate = candidate_price = residual_point = worst_residual = None
    boundary = "none"
    vega = ill_conditioned = None
    target_decimal = None
    fl = Fraction.from_float

    pending = None   # sigma of the last filter-skipped midpoint whose candidate/enclosure are not yet computed

    def result(value, status, reason, converged=False):
        nonlocal pending, candidate, candidate_enclosure
        if pending is not None:
            try:
                enclosed = _price(operands, fl(pending), target, owner)[0]
            except NumericalFailure:
                raise _FilterAbort()
            candidate, candidate_enclosure, pending = pending, enclosed, None
        candidate_enclosure = _reported(candidate_enclosure) if candidate_enclosure is not None else None
        evidence = None
        if target_decimal is not None:
            evidence = SolverEvidence(
                iterations, target_decimal, _diagnostic(target), candidate,
                candidate_price,
                _diagnostic(sum(_fractions(lower), Fraction(0))/2) if lower is not None else None,
                _diagnostic(sum(_fractions(upper), Fraction(0))/2) if upper is not None else None,
                lower, upper, candidate_enclosure, worst_residual, converted,
                lo, hi, residual_point, config, boundary, vega,
                ill_conditioned, converged,
            )
        return InverseResult(value, status, reason, evidence)

    try:
        target_decimal = exact_decimal(target)
        admitted = False
        lower_exact = upper_exact = None
        bound_failure = None
        bound_succeeded = False
        for bits in TIERS:
            try:
                lower, upper, lower_exact, upper_exact = bounds(operands, owner, bits)
                bound_succeeded = True
                ll, lh = _fractions(lower)
                ul, uh = _fractions(upper)
                if target < ll or target > uh:
                    return result(None, "invalid_input", "price_out_of_bounds")
                if lower_exact is not None and target == lower_exact:
                    # Mathematical lower/upper must be distinct; positive S,K,T
                    # ensure it analytically for every finite admitted r,q.
                    lo = hi = candidate = 0.0
                    candidate_enclosure = lower
                    candidate_price = _diagnostic(target)
                    residual_point = 0.0 if candidate_price is not None and Fraction.from_float(candidate_price) == target else (_diagnostic(Fraction.from_float(candidate_price)-target) if candidate_price is not None else None)
                    worst_residual = exact_decimal(Fraction(0))
                    boundary = "lower_boundary"
                    vega, ill_conditioned = _conditioning(operands, Fraction(0), target, config, owner)
                    return result(0.0, "available", "ok", True)
                if upper_exact is not None and target == upper_exact:
                    boundary = "upper_asymptote"
                    return result(None, "nonidentifiable_inverse", "upper_asymptote")
                if target > lh and target < ul:
                    admitted = True
                    break
            except NumericalFailure as exc:
                bound_failure = exc
                continue
        if not admitted:
            if not bound_succeeded and bound_failure is not None:
                return result(None, "numerical_failure", bound_failure.reason)
            return result(None, "numerical_failure", "bound_precision")
        # Stage 0: per-contract memo of sigma-independent conversions (balls once per tier, guard once)
        operands = Operands(operands.spot, operands.strike, operands.rate, operands.carry, operands.time, operands.sigma, operands.eta, {})
        ff = floatfilter.make(operands, target, config) if use_filter else None
        if ff is not None and ff.sign(hi)[0] > 0:
            cap_enclosure, cap_sign = None, 1   # float certainly above the target at the cap; the cap enclosure is otherwise unused
        else:
            cap_enclosure, cap_sign = _price(operands, fl(hi), target, owner)
        if cap_sign < 0:
            boundary = "sigma_cap"
            candidate, candidate_enclosure = hi, cap_enclosure
            return result(None, "bracket_exceeded", "sigma_cap")
        if cap_sign == 0:
            # Strictly positive finite-sigma BSM has no admitted generic
            # symbolic cap equality proof. Rounded equality never qualifies.
            candidate, candidate_enclosure = hi, cap_enclosure
            return result(None, "numerical_failure", "bound_precision")
        price_tolerance = Fraction.from_float(config.price_abs_tol)+Fraction.from_float(config.price_rel_tol)*abs(target)
        residual_low, residual_high = target-price_tolerance, target+price_tolerance
        vol_abs_f, vol_rel_f = Fraction.from_float(config.vol_abs_tol), Fraction.from_float(config.vol_rel_tol)
        vol_abs, vol_rel = config.vol_abs_tol, config.vol_rel_tol

        def acceptable(sigma, sigma_f, enclosed):
            nonlocal pending, candidate, candidate_enclosure, candidate_price, residual_point, worst_residual, vega, ill_conditioned
            pending = None
            candidate, candidate_enclosure = sigma, enclosed
            # residual > price_tolerance  <=>  an endpoint lies outside [target-tol, target+tol]: integer compares
            # decide it without Fractions; the exact residual is built only for an accepted candidate.
            if not enclosed.within(residual_low, residual_high):
                return False
            width = fl(hi)-fl(lo)
            volatility_tolerance = vol_abs_f+vol_rel_f*abs(sigma_f)
            if width > volatility_tolerance:
                return False
            a, b = _fractions(enclosed)
            worst_residual = exact_decimal(max(abs(a-target), abs(b-target)))
            candidate_price = certified_value(enclosed)
            residual_point = _diagnostic(Fraction.from_float(candidate_price)-target)
            vega, ill_conditioned = _conditioning(operands, sigma_f, target, config, owner)
            return True

        for index in range(config.max_iterations):
            iterations = index+1
            midpoint = _midpoint(lo, hi) if ff is not None else nearest_binary64((fl(lo)+fl(hi))/2)
            if not lo < midpoint < hi:
                # No invented interval collapse when adjacent binary64 values
                # remain. A terminal candidate can still meet both criteria.
                lo_f = fl(lo)
                candidate_enclosure = _price(operands, lo_f, target, owner)[0]
                if acceptable(lo, lo_f, candidate_enclosure):
                    return result(lo, "available", "ok", True)
                return result(None, "numerical_failure", "precision_exhausted")
            if ff is not None:
                fsign, resid_ok = ff.sign(midpoint)
                if fsign:
                    # The float price is certainly on one side. Skip the enclosure only when the base loop
                    # would also reject this candidate before and after the contraction (see the bound note).
                    w2 = (hi-midpoint) if fsign < 0 else (midpoint-lo)
                    if resid_ok or w2*(1-2**-30) > (vol_abs+vol_rel*abs(midpoint))*(1+2**-30):
                        pending = midpoint
                        if fsign < 0:
                            lo = midpoint
                        else:
                            hi = midpoint
                        continue
            mid_f = fl(midpoint)
            candidate_enclosure, sign = _price(operands, mid_f, target, owner)
            if acceptable(midpoint, mid_f, candidate_enclosure):
                return result(midpoint, "available", "ok", True)
            if sign < 0:
                lo = midpoint
            elif sign > 0:
                hi = midpoint
            else:
                left = nearest_binary64((fl(lo)+mid_f)/2)
                right = nearest_binary64((mid_f+fl(hi))/2)
                if not lo < left < midpoint < right < hi:
                    return result(None, "numerical_failure", "precision_exhausted")
                left_f, right_f = fl(left), fl(right)
                _, left_sign = _price(operands, left_f, target, owner)
                _, right_sign = _price(operands, right_f, target, owner)
                if left_sign < 0 and right_sign > 0:
                    lo, hi = left, right
                else:
                    return result(None, "numerical_failure", "bound_precision")
            # After a certified contraction check the current already-enclosed
            # candidate against the new bracket, without extra price work.
            if lo <= midpoint <= hi and acceptable(midpoint, mid_f, candidate_enclosure):
                return result(midpoint, "available", "ok", True)
        return result(None, "iteration_limit", "iteration_budget")
    except NumericalFailure as exc:
        return result(None, "numerical_failure", exc.reason)
