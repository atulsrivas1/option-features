"""Finite certified bisection, preserving a root-containing volatility bracket."""
from dataclasses import dataclass, replace
from fractions import Fraction
from option_feature_contracts import SolverEvidence
from .arithmetic import (TIERS, NumericalFailure, decimal_exact, exact_decimal, nearest_binary64, certify)
from .model import bounds, forward, price_interval

@dataclass(frozen=True, slots=True)
class InverseResult:
    value: float | None
    status: str
    reason: str
    evidence: SolverEvidence | None

def _fractions(enclosed):
    return decimal_exact(enclosed.value_low), decimal_exact(enclosed.value_high)

def _diagnostic(value):
    try:
        return nearest_binary64(value)
    except NumericalFailure:
        return None

def _price(operands, sigma, target, owner):
    latest = None
    failure = NumericalFailure("bound_precision")
    for bits in TIERS:
        try:
            latest = price_interval(replace(operands, sigma=Fraction.from_float(sigma)), owner, bits)
            low, high = _fractions(latest)
            if high < target:
                return latest, -1
            if low > target:
                return latest, 1
        except NumericalFailure as exc:
            failure = exc
    if latest is None:
        raise failure
    return latest, 0

def _conditioning(operands, sigma, target, config, owner):
    """Certify the same Vega inequality for every available IV candidate."""
    try:
        certificate = forward(replace(operands, sigma=Fraction.from_float(sigma)), "greeks.vega", owner)
        volatility_tolerance = Fraction.from_float(config.vol_abs_tol)+Fraction.from_float(config.vol_rel_tol)*abs(Fraction.from_float(sigma))
        price_tolerance = Fraction.from_float(config.price_abs_tol)+Fraction.from_float(config.price_rel_tol)*abs(target)
        maximum = max(abs(certificate.low), abs(certificate.high))
        minimum = min(abs(certificate.low), abs(certificate.high)) if certificate.low*certificate.high > 0 else Fraction(0)
        condition = True if maximum*volatility_tolerance <= price_tolerance else (False if minimum*volatility_tolerance > price_tolerance else None)
        return certificate.value, condition
    except NumericalFailure:
        return None, None

def solve(operands, target, config, converted, owner):
    """Target is exact rational midpoint; no supplied volatility is consumed."""
    iterations = 0
    lo, hi = 0.0, config.max_sigma
    lower = upper = candidate_enclosure = None
    candidate = candidate_price = residual_point = worst_residual = None
    boundary = "none"
    vega = ill_conditioned = None
    target_decimal = None

    def result(value, status, reason, converged=False):
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
                    vega, ill_conditioned = _conditioning(operands, candidate, target, config, owner)
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
        cap_enclosure, cap_sign = _price(operands, hi, target, owner)
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

        def acceptable(sigma, enclosed):
            nonlocal candidate, candidate_enclosure, candidate_price, residual_point, worst_residual, vega, ill_conditioned
            candidate, candidate_enclosure = sigma, enclosed
            a, b = _fractions(enclosed)
            residual = max(abs(a-target), abs(b-target))
            width = Fraction.from_float(hi)-Fraction.from_float(lo)
            volatility_tolerance = Fraction.from_float(config.vol_abs_tol)+Fraction.from_float(config.vol_rel_tol)*abs(Fraction.from_float(sigma))
            if residual > price_tolerance or width > volatility_tolerance:
                return False
            worst_residual = exact_decimal(residual)
            point = certify(enclosed)
            candidate_price = point.value
            residual_point = _diagnostic(Fraction.from_float(point.value)-target)
            vega, ill_conditioned = _conditioning(operands, sigma, target, config, owner)
            return True

        for index in range(config.max_iterations):
            iterations = index+1
            midpoint = nearest_binary64((Fraction.from_float(lo)+Fraction.from_float(hi))/2)
            if not lo < midpoint < hi:
                # No invented interval collapse when adjacent binary64 values
                # remain. A terminal candidate can still meet both criteria.
                candidate_enclosure, _ = _price(operands, lo, target, owner)
                if acceptable(lo, candidate_enclosure):
                    return result(lo, "available", "ok", True)
                return result(None, "numerical_failure", "precision_exhausted")
            candidate_enclosure, sign = _price(operands, midpoint, target, owner)
            if acceptable(midpoint, candidate_enclosure):
                return result(midpoint, "available", "ok", True)
            if sign < 0:
                lo = midpoint
            elif sign > 0:
                hi = midpoint
            else:
                left = nearest_binary64((Fraction.from_float(lo)+Fraction.from_float(midpoint))/2)
                right = nearest_binary64((Fraction.from_float(midpoint)+Fraction.from_float(hi))/2)
                if not lo < left < midpoint < right < hi:
                    return result(None, "numerical_failure", "precision_exhausted")
                _, left_sign = _price(operands, left, target, owner)
                _, right_sign = _price(operands, right, target, owner)
                if left_sign < 0 and right_sign > 0:
                    lo, hi = left, right
                else:
                    return result(None, "numerical_failure", "bound_precision")
            # After a certified contraction check the current already-enclosed
            # candidate against the new bracket, without extra price work.
            if lo <= midpoint <= hi and acceptable(midpoint, candidate_enclosure):
                return result(midpoint, "available", "ok", True)
        return result(None, "iteration_limit", "iteration_budget")
    except NumericalFailure as exc:
        return result(None, "numerical_failure", exc.reason)
