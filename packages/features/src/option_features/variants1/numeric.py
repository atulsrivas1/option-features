"""Binary64 and checked signed64 arithmetic for option-flow-variants1.

Each operation rounds once (Python float arithmetic is IEEE binary64 nearest-even,
no FMA, subnormals kept). Nonfinite intermediates raise NumericOverflow.
"""
import math
from decimal import Decimal, localcontext
from option_feature_contracts.variants1.canonical import b2f, f2b, I64_MAX, I64_MIN


class NumericOverflow(ArithmeticError):
    """Nonfinite binary64 or signed64 overflow; mapped to numeric_overflow by callers."""


def fin(x):
    if not math.isfinite(x):
        raise NumericOverflow()
    return x


def add(a, b):
    return fin(a + b)


def sub(a, b):
    return fin(a - b)


def mul(a, b):
    return fin(a * b)


def div(a, b):
    if b == 0:
        raise NumericOverflow()
    return fin(a / b)


def rn_int(n):
    return fin(float(n))


def num_zero(x):
    return x == 0.0


def chk(n):
    if n > I64_MAX or n < I64_MIN:
        raise NumericOverflow()
    return n


def cadd(a, b):
    return chk(a + b)


def csub(a, b):
    return chk(a - b)


def cmul(a, b):
    return chk(a * b)


def fixed(x, digits):
    """Fixed_d of a finite binary64: exact value, nearest/ties-even, '-' kept for negative or -0."""
    with localcontext() as ctx:
        ctx.prec = 2000
        q = Decimal(x).quantize(Decimal(1).scaleb(-digits), rounding="ROUND_HALF_EVEN")
        text = format(q, "f")
    if math.copysign(1.0, x) < 0 and not text.startswith("-"):
        text = "-" + text
    return text


def quantile(sorted_vals, p):
    """q = RN(v_lo + RN(RN(v_hi - v_lo) * RN(x - RN(lo)))) with x = RN(p * RN(n-1))."""
    n = len(sorted_vals)
    x = mul(p, rn_int(n - 1))
    lo = math.floor(x)
    hi = math.ceil(x)
    vlo, vhi = sorted_vals[lo], sorted_vals[hi]
    return add(vlo, mul(sub(vhi, vlo), sub(x, rn_int(lo))))
