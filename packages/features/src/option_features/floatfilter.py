"""Float64 filter for the certified IV bisection (M1 Stage 1).

The filter never produces a value. It only answers: "is the float64 Black-Scholes price at this sigma
certainly below / above the target by more than a conservative, platform-independent error bound?".
When it is not certain, the caller uses the certified enclosure path. The derivation of the constants
is in docs/M1_STAGE1_FLOAT_FILTER_BOUND.md and must be read with this file.

Uses only IEEE-754 +, -, *, /, sqrt (correctly rounded on every platform) and the libm functions
exp, log, erfc, for which the proof assumes a relative error of at most U = 2**-40 (about 4096 ulp).
"""
from math import erfc, exp, isfinite, log, sqrt

U = 2.0 ** -40          # assumed libm relative error bound (exp, log, erfc); true libms are near 2**-52
W_COEFF = 5.0           # proven worst-case float price error is at most W_COEFF * U * SCALE (derived: 3.2, rounded up)
C_BOUND = 40.0          # bound E = C_BOUND * U * SCALE; safety factor C_BOUND / W_COEFF = 8 (12.5 over derived 3.2)
Z_MAX = 1.0e5           # filter disabled for a sigma whose conditioning factor Z exceeds this
D_MAX = 30.0            # filter disabled when |d1| or |d2| exceeds this: keeps the true price far above the
                        # certified path's enclosure-text limits (true price >= ~1e-250 there; see the note)
SCALE_MIN, SCALE_MAX = 1.0e-20, 1.0e20   # admitted range for spot and strike
EXP_ARG_MAX = 64.0      # admitted |rate*T|, |carry*T|
T_MIN, T_MAX = 2.0 ** -30, 1.0e3
SIGMA_MAX = 100.0
INV_SQRT2 = 0.7071067811865476


class FloatFilter:
    __slots__ = ("eta", "lnsk", "rq", "T", "sT", "A", "B", "absdrift", "t", "ptol2", "bound_k", "inject", "scale0")

    def __init__(self, eta, lnsk, rq, T, sT, A, B, absdrift, t, ptol2, bound_k, inject):
        self.eta, self.lnsk, self.rq, self.T, self.sT, self.A, self.B = eta, lnsk, rq, T, sT, A, B
        self.absdrift, self.t, self.ptol2, self.bound_k, self.inject = absdrift, t, ptol2, bound_k, inject
        self.scale0 = A + B

    def _eval(self, sigma):
        """(float price incl. test injection, SCALE) or None outside the admitted sigma domain."""
        if not 0.0 < sigma <= SIGMA_MAX:
            return None
        s2 = sigma * sigma
        vs = sigma * self.sT
        z = (self.absdrift + s2 * self.T + 1.0) / vs
        if not z <= Z_MAX:
            return None
        d1 = (self.lnsk + (self.rq + 0.5 * s2) * self.T) / vs
        d2 = d1 - vs
        if not (abs(d1) <= D_MAX and abs(d2) <= D_MAX):
            return None
        eta = self.eta
        n1 = 0.5 * erfc(-eta * d1 * INV_SQRT2)
        n2 = 0.5 * erfc(-eta * d2 * INV_SQRT2)
        scale = self.scale0 * (1.0 + z)
        return eta * (self.A * n1 - self.B * n2) + self.inject * scale, scale

    def sign(self, sigma):
        """Return (sgn, resid_ok). sgn = -1 / +1 when float price is below / above target by more than E;
        0 when not certain (also for any sigma outside the admitted domain). resid_ok: additionally
        |price - target| is certainly above the price tolerance."""
        try:
            ev = self._eval(sigma)
            if ev is None:
                return 0, False
            p, scale = ev
            e = self.bound_k * scale
            gap = p - self.t
            if not (isfinite(gap) and isfinite(e)):
                return 0, False
            if gap > e:
                return 1, gap > e + self.ptol2
            if gap < -e:
                return -1, -gap > e + self.ptol2
            return 0, False
        except (ValueError, OverflowError, ZeroDivisionError):
            return 0, False


def make(operands, target, config, bound_divisor=1.0, inject=0.0):
    """FloatFilter for one contract, or None when the contract is outside the admitted domain (then the
    caller runs the full certified path). Any exception or non-finite value means None.
    bound_divisor and inject are TEST-ONLY knobs (tools/m1_filter_hooks.py wraps make to set them); the
    library never passes them, so there is no mutable global state in this module."""
    try:
        eta = operands.eta
        if eta not in (1, -1) or operands.time <= 0 or not operands.spot > 0 or not operands.strike > 0:
            return None
        if not 0.0 < config.max_sigma <= SIGMA_MAX:
            return None
        S, K, r, q, T, t = (float(x) for x in (operands.spot, operands.strike, operands.rate, operands.carry, operands.time, target))
        if not (SCALE_MIN <= S <= SCALE_MAX and SCALE_MIN <= K <= SCALE_MAX and T_MIN <= T <= T_MAX and t > 0.0):
            return None
        if not (abs(r * T) <= EXP_ARG_MAX and abs(q * T) <= EXP_ARG_MAX):
            return None
        A, B = S * exp(-q * T), K * exp(-r * T)
        lnsk = log(S / K)
        absdrift = abs(lnsk) + (abs(r) + abs(q)) * T
        ptol = config.price_abs_tol + config.price_rel_tol * t
        if not all(isfinite(x) for x in (A, B, lnsk, absdrift, sqrt(T), ptol)) or not (A > 0.0 and B > 0.0):
            return None
        bound_k = C_BOUND * U / bound_divisor
        return FloatFilter(float(eta), lnsk, r - q, T, sqrt(T), A, B, absdrift, t, 2.0 * ptol, bound_k, inject * U)
    except (ValueError, OverflowError, ZeroDivisionError, TypeError, AttributeError):
        return None
