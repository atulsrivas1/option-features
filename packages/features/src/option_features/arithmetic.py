"""Bounded exact conversion and option-arb-bsm1 enclosure machinery.

Only numerical_owner imports flint. Callers must not concurrently mutate flint
context outside this library. Source implementation is not backend qualification.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
import math
import threading
from option_feature_contracts import PriceEnclosure, ContractValidationError, decimal_text

TIERS = (128, 256, 512, 1024, 2048)
_LOCK = threading.Lock()
_LOCAL = threading.local()

class NumericalFailure(ArithmeticError):
    def __init__(self, reason="precision_exhausted"):
        self.reason = reason
        super().__init__(reason)

@contextmanager
def numerical_owner():
    if getattr(_LOCAL, "active", False):
        raise RuntimeError("reentrant option numerical context ownership")
    with _LOCK:
        _LOCAL.active = True
        try:
            from flint import arb, fmpq, ctx
            previous_precision, previous_threads = ctx.prec, ctx.threads
            try:
                ctx.threads = 1
                yield arb, fmpq, ctx
            finally:
                try:
                    ctx.prec = previous_precision
                finally:
                    ctx.threads = previous_threads
        finally:
            _LOCAL.active = False

def decimal_exact(value):
    """Exact integer coefficient/exponent, independent of Decimal context."""
    sign, digits, exponent = value.as_tuple()
    coefficient = 0
    for digit in digits:
        coefficient = coefficient*10 + digit
    if sign:
        coefficient = -coefficient
    return Fraction(coefficient * 10**exponent) if exponent >= 0 else Fraction(coefficient, 10**(-exponent))

def nearest_binary64(value):
    """CPython Fraction->float rounds nearest-even; qualify ties independently."""
    try:
        point = float(value)
    except (OverflowError, ValueError) as exc:
        raise NumericalFailure() from exc
    if not math.isfinite(point):
        raise NumericalFailure()
    return 0.0 if point == 0 else point

def exact_decimal(value):
    """Finite decimal only, exact and bounded; never round a solver residual."""
    denominator, twos, fives = value.denominator, 0, 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
        if twos > 1024:
            raise NumericalFailure()
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
        if fives > 1024:
            raise NumericalFailure()
    if denominator != 1:
        raise NumericalFailure()
    places = max(twos, fives)
    coefficient = value.numerator * 2**(places-twos) * 5**(places-fives)
    return decimal_tuple(coefficient, -places)

def decimal_tuple(coefficient, exponent):
    if coefficient == 0:
        return Decimal(0)
    while coefficient % 10 == 0:
        coefficient //= 10
        exponent += 1
    digits = tuple(int(c) for c in str(abs(coefficient)))
    if len(digits) > 128 or abs(exponent) > 1024:
        raise NumericalFailure()
    value = Decimal((int(coefficient < 0), digits, exponent))
    try:
        decimal_text(value)  # enforce projected wire text intersection too
    except ContractValidationError as exc:
        raise NumericalFailure() from exc
    return value

def _power10(exponent):
    return Fraction(10**exponent) if exponent >= 0 else Fraction(1, 10**(-exponent))

def outward_decimal(value, upper):
    if value == 0:
        return Decimal(0)
    absolute = abs(value)
    # At most bounded ~2500 decimal digits after dyadic magnitude admission.
    order = len(str(absolute.numerator)) - len(str(absolute.denominator))
    if absolute < _power10(order):
        order -= 1
    elif absolute >= _power10(order+1):
        order += 1
    exponent = max(-1024, order-126)
    quotient = value / _power10(exponent)
    coefficient = -((-quotient.numerator)//quotient.denominator) if upper else quotient.numerator//quotient.denominator
    return decimal_tuple(coefficient, exponent)

def dyadic_endpoint(bound, upper):
    if not bound.is_finite():
        raise NumericalFailure()
    mantissa_native, exponent_native = bound.man_exp()
    mantissa = int(mantissa_native)
    if not mantissa:
        return Decimal(0)
    # Compare compact native exponent before constructing any huge denominator.
    magnitude = exponent_native + abs(mantissa).bit_length()-1
    if magnitude > 4096:
        raise NumericalFailure()
    if magnitude < -8192:
        if mantissa > 0:
            return decimal_tuple(1, -1024) if upper else Decimal(0)
        return Decimal(0) if upper else decimal_tuple(-1, -1024)
    exponent = int(exponent_native)
    value = Fraction(mantissa * 2**exponent) if exponent >= 0 else Fraction(mantissa, 2**(-exponent))
    return outward_decimal(value, upper)

@dataclass(frozen=True, slots=True)
class Certified:
    value: float
    enclosure: PriceEnclosure
    low: Fraction
    high: Fraction

def enclosure(ball):
    if not ball.is_finite():
        raise NumericalFailure()
    low, high = dyadic_endpoint(ball.lower(), False), dyadic_endpoint(ball.upper(), True)
    if low > high:
        raise NumericalFailure()
    return PriceEnclosure("option-arb-bsm1", "1", low, high)

def certify(enclosed):
    low, high = decimal_exact(enclosed.value_low), decimal_exact(enclosed.value_high)
    value = nearest_binary64((low+high)/2)
    exact_value = Fraction.from_float(value)
    error = max(abs(exact_value-low), abs(exact_value-high))
    if (low != 0 or high != 0) and error > Fraction(1, 10**12)*max(abs(low), abs(high)):
        raise NumericalFailure()
    return Certified(value, enclosed, low, high)

def certify_exact(value):
    return certify(PriceEnclosure("option-arb-bsm1", "1", outward_decimal(value, False), outward_decimal(value, True)))

def ball_rational(value, arb, fmpq):
    return arb(fmpq(value.numerator, value.denominator))
