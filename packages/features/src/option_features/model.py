"""Original option-bsm1 equations and explicit one-sided endpoints."""
from dataclasses import dataclass, field
from fractions import Fraction
from .arithmetic import TIERS, NumericalFailure, ball_rational, enclosure, certify, certify_exact

@dataclass(frozen=True, slots=True)
class Operands:
    spot: Fraction
    strike: Fraction
    rate: Fraction
    carry: Fraction
    time: Fraction
    sigma: Fraction
    eta: int
    # Stage 0 hoist: optional per-contract memo of sigma-independent conversions. WARNING: valid only
    # across sigma variants of the SAME contract (spot, strike, rate, carry, time, eta); it is created
    # only inside inverse.solve and must never be shared between contracts. Keyed by precision tier.
    # Not part of identity, equality or repr.
    cache: dict | None = field(default=None, compare=False, repr=False)

class Undefined(ArithmeticError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)

def _discounted(operands, owner):
    arb, fmpq, ctx = owner
    cache = operands.cache
    if cache is not None:
        # Stage 0 hoist: the sigma-independent guard and the five ball conversions are computed once
        # per contract (balls once per precision tier), not once per solver iteration. Same values.
        guard = cache.get("guard")
        if guard is None:
            guard = cache["guard"] = abs(operands.rate*operands.time) > 512 or abs(operands.carry*operands.time) > 512
        if guard or operands.sigma > 4096:
            raise NumericalFailure()
        balls = cache.get(ctx.prec)
        if balls is None:
            balls = cache[ctx.prec] = tuple(ball_rational(x, arb, fmpq) for x in (operands.spot, operands.strike, operands.rate, operands.carry, operands.time))
        S, K, r, q, T = balls
        sigma = ball_rational(operands.sigma, arb, fmpq)
        A, B = S*(-q*T).exp(), K*(-r*T).exp()
        return S, K, r, q, T, sigma, A, B
    if abs(operands.rate*operands.time) > 512 or abs(operands.carry*operands.time) > 512 or operands.sigma > 4096:
        raise NumericalFailure()
    S, K, r, q, T, sigma = (ball_rational(x, arb, fmpq) for x in (operands.spot, operands.strike, operands.rate, operands.carry, operands.time, operands.sigma))
    A, B = S*(-q*T).exp(), K*(-r*T).exp()
    return S, K, r, q, T, sigma, A, B

def _terminal(operands, output_id):
    S, K, r, q, sigma, eta = operands.spot, operands.strike, operands.rate, operands.carry, operands.sigma, operands.eta
    signed_payoff = eta*(S-K)
    if output_id == "pricing.price":
        return max(signed_payoff, Fraction(0))
    if output_id in {"greeks.vega", "greeks.rho"}:
        return Fraction(0)
    if output_id in {"greeks.delta", "greeks.signed_delta", "greeks.gamma"}:
        if S == K:
            raise Undefined("nondifferentiable_payoff")
        if output_id == "greeks.gamma":
            return Fraction(0)
        delta = Fraction(eta if signed_payoff > 0 else 0)
        return abs(delta) if output_id == "greeks.delta" else delta
    if output_id == "greeks.theta":
        if S == K:
            if sigma > 0:
                raise Undefined("nonfinite_terminal_time_derivative")
            return -max(eta*(r-q)*S, Fraction(0))
        return eta*(q*S-r*K) if signed_payoff > 0 else Fraction(0)
    raise ValueError("unknown forward output")

def equation(operands, output_id, owner):
    """One fresh expression from original rationals at caller-selected tier."""
    if operands.time == 0:
        return _terminal(operands, output_id)
    arb, _, _ = owner
    S, K, r, q, T, sigma, A, B = _discounted(operands, owner)
    eta = operands.eta
    if operands.sigma == 0:
        symbolic_kink = operands.spot == operands.strike and operands.rate == operands.carry
        H = A-B
        if symbolic_kink:
            sign = 0
        elif H > 0:
            sign = 1
        elif H < 0:
            sign = -1
        else:
            raise NumericalFailure("bound_precision")
        itm = eta*sign > 0
        if output_id == "pricing.price":
            return eta*H if itm else Fraction(0)
        if sign == 0:
            if output_id in {"greeks.delta", "greeks.signed_delta", "greeks.gamma", "greeks.rho"}:
                raise Undefined("nondifferentiable_zero_volatility")
            if output_id == "greeks.vega":
                return A*T.sqrt()/(2*arb.pi()).sqrt()
            if output_id == "greeks.theta":
                # At the admitted symbolic kink r=q and A=B exactly.
                return Fraction(0)
        if output_id in {"greeks.gamma", "greeks.vega"}:
            return Fraction(0)
        if output_id in {"greeks.delta", "greeks.signed_delta"}:
            if not itm:
                return Fraction(0)
            value = eta*(-q*T).exp()
            return abs(value) if output_id == "greeks.delta" else value
        if output_id == "greeks.rho":
            return eta*T*B if itm else Fraction(0)
        if output_id == "greeks.theta":
            return eta*(q*A-r*B) if itm else Fraction(0)
        raise ValueError("unknown forward output")
    sqrtT = T.sqrt()
    denominator = sigma*sqrtT
    if not denominator > 0:
        raise NumericalFailure()
    d1 = ((S/K).log()+(r-q+sigma*sigma/2)*T)/denominator
    d2 = d1-denominator
    if not (abs(d1) <= 1000000 and abs(d2) <= 1000000):
        raise NumericalFailure()
    sqrt2 = arb(2).sqrt()
    cdf1 = (-eta*d1/sqrt2).erfc()/2
    cdf2 = (-eta*d2/sqrt2).erfc()/2
    density = (-(d1*d1)/2).exp()/(2*arb.pi()).sqrt()
    if output_id == "pricing.price":
        return eta*(A*cdf1-B*cdf2)
    if output_id in {"greeks.delta", "greeks.signed_delta"}:
        value = eta*(-q*T).exp()*cdf1
        return abs(value) if output_id == "greeks.delta" else value
    if output_id == "greeks.gamma":
        return (-q*T).exp()*density/(S*sigma*sqrtT)
    if output_id == "greeks.vega":
        return A*density*sqrtT
    if output_id == "greeks.rho":
        return eta*T*B*cdf2
    if output_id == "greeks.theta":
        return -A*density*sigma/(2*sqrtT)+eta*q*A*cdf1-eta*r*B*cdf2
    raise ValueError("unknown forward output")

def forward(operands, output_id, owner):
    if operands.time == 0:
        return certify_exact(_terminal(operands, output_id))
    last_failure = NumericalFailure()
    for bits in TIERS:
        owner[2].prec = bits
        try:
            value = equation(operands, output_id, owner)
            return certify_exact(value) if type(value) is Fraction else certify(enclosure(value))
        except NumericalFailure as exc:
            last_failure = exc
    raise last_failure

def price_interval(operands, owner, bits):
    """A price enclosure without a point-value certificate, for inverse ordering."""
    owner[2].prec = bits
    value = equation(operands, "pricing.price", owner)
    if type(value) is Fraction:
        return certify_exact(value).enclosure
    return enclosure(value)

def bounds(operands, owner, bits):
    owner[2].prec = bits
    _, _, _, _, _, _, A, B = _discounted(operands, owner)
    H = operands.eta*(A-B)
    symbolic_kink = operands.spot == operands.strike and operands.rate == operands.carry
    if operands.rate == 0 and operands.carry == 0:
        lower_exact = max(operands.eta*(operands.spot-operands.strike), Fraction(0))
    elif symbolic_kink or H <= 0:
        lower_exact = Fraction(0)
    else:
        lower_exact = None
    upper_exact = operands.spot if operands.eta == 1 and operands.carry == 0 else (operands.strike if operands.eta == -1 and operands.rate == 0 else None)
    if lower_exact is None:
        if not H > 0:
            raise NumericalFailure("bound_precision")
        lower = enclosure(H)
    else:
        lower = certify_exact(lower_exact).enclosure
    upper = certify_exact(upper_exact).enclosure if upper_exact is not None else enclosure(A if operands.eta == 1 else B)
    return lower, upper, lower_exact, upper_exact
