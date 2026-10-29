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
from option_feature_contracts import PriceEnclosure

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

# --- M1 Stage 2: endpoint conversion on plain integers -------------------------------------------------------
# Every conversion function below returns exactly what the pre-Stage-2 code returned. arithmetic_legacy is the
# verbatim pre-Stage-2 code: the test oracle and the fallback behind set_fast_endpoints(False). Only the way
# the integers are computed changed (docs/M1_STAGE2_ENDPOINT_CONVERSION.md has the argument).
_FAST = True
_P10 = {}

def set_fast_endpoints(enabled):
    """Switch between the Stage 2 integer conversion (default) and the verbatim pre-Stage-2 code."""
    global _FAST
    _FAST = bool(enabled)

def fast_endpoints_enabled():
    return _FAST

def _legacy():
    from . import arithmetic_legacy
    return arithmetic_legacy

# Integers above this many bits are routed to the verbatim legacy code: CPython refuses str() of integers with
# more than 4300 digits (2**14000 < 10**4300), which the legacy len(str(...)) would turn into a ValueError.
# Nothing the solver admits comes near it; the route keeps even that class byte-identical by construction.
_LEGACY_BITS = 14000
_LEGACY_MANTISSA_BITS = 5000

def _p10(n):
    """10**n for n >= 0, memoised over the bounded range the conversion needs (n <= 4096)."""
    try:
        return _P10[n]
    except KeyError:
        value = 10**n
        if n <= 4096:
            _P10[n] = value
        return value

def decimal_exact(value):
    """Exact integer coefficient/exponent, independent of Decimal context."""
    if not _FAST or type(value) is not Decimal:
        return _legacy().decimal_exact(value)
    try:
        numerator, denominator = value.as_integer_ratio()   # exact, lowest terms, ignores the Decimal context
    except (ValueError, OverflowError):
        return _legacy().decimal_exact(value)               # NaN or Infinity: behaviour unchanged
    return Fraction(numerator, denominator)

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

def _finish(coefficient, exponent):
    """decimal_tuple without the Decimal: (stripped signed coefficient, exponent), (0, 0) for zero, or
    NumericalFailure. Mirrors decimal_tuple plus decimal_text: <= 128 digits, |exponent| <= 1024 and the
    projected wire text length <= 1024 (the rule in option_feature_contracts.validation.scalar)."""
    if coefficient == 0:
        return 0, 0
    text = str(coefficient)
    negative = text[0] == "-"
    body = text[1:] if negative else text
    stripped = body.rstrip("0")
    exponent += len(body) - len(stripped)
    digits = len(stripped)
    if digits > 128 or abs(exponent) > 1024:
        raise NumericalFailure()
    length = digits + exponent if exponent >= 0 else (digits + 1 if digits + exponent > 0 else 2 - exponent)
    if length + negative > 1024:
        raise NumericalFailure()
    return (-int(stripped) if negative else int(stripped)), exponent

def _decimal(coefficient, exponent):
    """The Decimal for an already stripped and validated pair. String construction is exact (never rounded)."""
    if coefficient == 0:
        return Decimal(0)
    return Decimal("%dE%d" % (coefficient, exponent))

def decimal_tuple(coefficient, exponent):
    if not _FAST:
        return _legacy().decimal_tuple(coefficient, exponent)
    return _decimal(*_finish(coefficient, exponent))

def _floor_log10(numerator, denominator):
    """floor(log10(numerator/denominator)) for positive integers. Exact: the estimate is only a start."""
    k = ((numerator.bit_length() - denominator.bit_length()) * 30103) // 100000
    while not (numerator >= denominator * _p10(k) if k >= 0 else numerator * _p10(-k) >= denominator):
        k -= 1
    while (numerator >= denominator * _p10(k + 1) if k + 1 >= 0 else numerator * _p10(-k - 1) >= denominator):
        k += 1
    return k

def _outward_parts(numerator, denominator, upper):
    """Directed (floor or ceiling) 127-digit coefficient of numerator/denominator, stripped and validated."""
    magnitude = -numerator if numerator < 0 else numerator
    exponent = max(-1024, _floor_log10(magnitude, denominator) - 126)
    if exponent >= 0:
        denominator *= _p10(exponent)
    else:
        numerator *= _p10(-exponent)
    coefficient = -((-numerator)//denominator) if upper else numerator//denominator
    return _finish(coefficient, exponent)

def outward_decimal(value, upper):
    if not _FAST:
        return _legacy().outward_decimal(value, upper)
    if value == 0:
        return Decimal(0)
    numerator, denominator = value.numerator, value.denominator
    if numerator.bit_length() > _LEGACY_BITS or denominator.bit_length() > _LEGACY_BITS:
        return _legacy().outward_decimal(value, upper)
    return _decimal(*_outward_parts(numerator, denominator, upper))

def _parts_of(value):
    """(coefficient, exponent) of an already stripped Decimal produced by the legacy code."""
    sign, digits, exponent = value.as_tuple()
    if not any(digits):
        return 0, 0
    coefficient = int("".join(map(str, digits)))
    return (-coefficient if sign else coefficient), exponent

def dyadic_endpoint_parts(bound, upper):
    """(coefficient, exponent) of the outward decimal endpoint of an arb endpoint; same admission rules as before."""
    if not bound.is_finite():
        raise NumericalFailure()
    mantissa_native, exponent_native = bound.man_exp()
    mantissa = int(mantissa_native)
    if not mantissa:
        return 0, 0
    # Compare compact native exponent before constructing any huge integer.
    magnitude = exponent_native + abs(mantissa).bit_length()-1
    if magnitude > 4096:
        raise NumericalFailure()
    if magnitude < -8192:
        if mantissa > 0:
            return _finish(1, -1024) if upper else (0, 0)
        return (0, 0) if upper else _finish(-1, -1024)
    exponent = int(exponent_native)
    if abs(mantissa).bit_length() > _LEGACY_MANTISSA_BITS:
        return _parts_of(_legacy().dyadic_endpoint(bound, upper))
    if exponent >= 0:
        return _outward_parts(mantissa << exponent, 1, upper)
    shift = -exponent
    decimal_exponent = max(-1024, _floor_log10(-mantissa if mantissa < 0 else mantissa, 1 << shift) - 126)
    if decimal_exponent < 0:
        # floor/ceiling of mantissa*10**-x / 2**shift is a right shift of an exact integer: no division.
        scaled = mantissa * _p10(-decimal_exponent)
        return _finish(-((-scaled) >> shift) if upper else scaled >> shift, decimal_exponent)
    return _outward_parts(mantissa, 1 << shift, upper)

def dyadic_endpoint(bound, upper):
    if not _FAST:
        return _legacy().dyadic_endpoint(bound, upper)
    return _decimal(*dyadic_endpoint_parts(bound, upper))

def _compare_parts(a, b):
    """Sign of a - b for (coefficient, exponent) pairs."""
    (ca, ea), (cb, eb) = a, b
    if ea > eb:
        ca *= _p10(ea - eb)
    elif eb > ea:
        cb *= _p10(eb - ea)
    return (ca > cb) - (ca < cb)

def _fraction(coefficient, exponent):
    return Fraction(coefficient * _p10(exponent)) if exponent >= 0 else Fraction(coefficient, _p10(-exponent))

def _vs(coefficient, exponent, numerator, denominator):
    """Sign of coefficient*10**exponent - numerator/denominator (denominator > 0)."""
    if exponent >= 0:
        left, right = coefficient * _p10(exponent) * denominator, numerator
    else:
        left, right = coefficient * denominator, numerator * _p10(-exponent)
    return (left > right) - (left < right)

class Ends:
    """A price enclosure whose decimal endpoints stay integers until a consumer needs them.

    sign_vs (ordering against an exact target) and fractions() never build a Decimal; enclosure() builds the
    PriceEnclosure that the solver reports. Built from an arb ball (enclosure_ends) or, for exact rational
    prices and for the switched-off legacy path, around an existing PriceEnclosure."""
    __slots__ = ("_low", "_high", "_fr", "_enc")

    def __init__(self, low=None, high=None, enc=None):
        self._low, self._high, self._enc, self._fr = low, high, enc, None

    def fractions(self):
        if self._fr is None:
            if self._enc is not None:
                self._fr = (decimal_exact(self._enc.value_low), decimal_exact(self._enc.value_high))
            else:
                self._fr = (_fraction(*self._low), _fraction(*self._high))
        return self._fr

    def sign_vs(self, target):
        """-1 if the whole enclosure lies below target, 1 if wholly above, 0 if target is not excluded."""
        if self._enc is not None or self._fr is not None:
            low, high = self.fractions()
            return -1 if high < target else (1 if low > target else 0)
        numerator, denominator = target.numerator, target.denominator
        if _vs(*self._high, numerator, denominator) < 0:
            return -1
        return 1 if _vs(*self._low, numerator, denominator) > 0 else 0

    def within(self, low, high):
        """True iff low <= endpoint <= high for both endpoints, with exact rational bounds (integer compares)."""
        if self._enc is not None or self._fr is not None:
            low_end, high_end = self.fractions()
            return low <= low_end and high_end <= high
        ln, ld, hn, hd = low.numerator, low.denominator, high.numerator, high.denominator
        return (_vs(*self._low, ln, ld) >= 0 and _vs(*self._high, ln, ld) >= 0
                and _vs(*self._low, hn, hd) <= 0 and _vs(*self._high, hn, hd) <= 0)

    def enclosure(self):
        if self._enc is None:
            self._enc = PriceEnclosure("option-arb-bsm1", "1", _decimal(*self._low), _decimal(*self._high))
        return self._enc

def enclosure_ends(ball):
    if not ball.is_finite():
        raise NumericalFailure()
    if not _FAST:
        return Ends(enc=_legacy().enclosure(ball))
    low, high = dyadic_endpoint_parts(ball.lower(), False), dyadic_endpoint_parts(ball.upper(), True)
    if _compare_parts(low, high) > 0:
        raise NumericalFailure()
    return Ends(low, high)

def enclosure(ball):
    if not _FAST:
        return _legacy().enclosure(ball)
    return enclosure_ends(ball).enclosure()

@dataclass(frozen=True, slots=True)
class Certified:
    value: float
    enclosure: PriceEnclosure
    low: Fraction
    high: Fraction

def _certified(low, high):
    value = nearest_binary64((low+high)/2)
    exact_value = Fraction.from_float(value)
    error = max(abs(exact_value-low), abs(exact_value-high))
    if (low != 0 or high != 0) and error > Fraction(1, 10**12)*max(abs(low), abs(high)):
        raise NumericalFailure()
    return value

def certified_value(ends):
    """certify(ends.enclosure()).value without materialising the enclosure."""
    return _certified(*ends.fractions())

def certify(enclosed):
    low, high = decimal_exact(enclosed.value_low), decimal_exact(enclosed.value_high)
    return Certified(_certified(low, high), enclosed, low, high)

def certify_exact(value):
    return certify(PriceEnclosure("option-arb-bsm1", "1", outward_decimal(value, False), outward_decimal(value, True)))

def ball_rational(value, arb, fmpq):
    return arb(fmpq(value.numerator, value.denominator))
