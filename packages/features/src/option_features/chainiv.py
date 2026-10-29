"""M1 story B: per-contract IV, chain ATM IV, 30-day constant-maturity IV and the American-style labels.

Pure and single-threaded (D4 amended): no I/O, clocks, threads or shared state. Library modules only; not
on the wire (no schema change, no change to any frozen result bytes). Rulings: DECISIONS.md and
PO_R28_DESIGN_RULINGS (D12 to D14). Conventions (D12): ACT/365, expiry N x 24 h after the cutoff
(T = N/365), midpoint price, continuous rate and dividend yield.

Rules
- Gates per contract (first hit wins): no_quote (no bid and no ask, or not yet known at the cutoff),
  excluded_condition (condition other than "regular"), invalid_quote (one side missing, bid <= 0),
  crossed_market, locked_market, stale_quote (cutoff - event_ns > stale limit).
- Style: "european" gives label "exact-model"; "american" gives LABEL_APPROX, but only for the strike nearest
  the forward (across ALL listed strikes of the expiry, ties to the lower strike; K = F is not ITM) and for
  OTM contracts (call K >= F, put K <= F); other American contracts are unavailable "american_itm".
  Any other style value is unavailable "style_unknown" (after the quote gates).
- ATM IV for an expiry: F = S exp((r - q) T); the strike nearest F among strikes whose call AND put both pass
  the gates (ties to the lower strike); ATM IV = mean of call IV and put IV; the result carries strike,
  forward and both IVs. No such strike (or no such expiry): unavailable "no_atm_strike". An ATM leg of
  unknown style gives "style_unknown"; any American leg gives the approximate label. A solver failure on a
  leg is reported with the solver's reason (no fallback to another strike).
- 30-day IV: the listed expiry equal to the target is used as is (its ATM IV; a failure is reported with its
  own reason, "no_atm_strike" included, expiries_used empty). Otherwise the bracketing listed expiries
  (largest below, smallest above) are interpolated linearly in total variance IV^2 T and converted back at
  the target T; no extrapolation. No bracket, or a bracketing expiry without an ATM strike:
  "no_bracketing_expiry" (expiries_used shows the bracket once one exists). style_unknown and solver
  reasons propagate.

Performance design (owner goal): `IVChain` is built once per cutoff. Gates, strike indexes and the
forward are computed once per expiry; ATM and 30-day solve only the nearest-forward strike (two solves per
expiry, bisect on a sorted strike list); every contract is solved at most once (memo), so contract_iv after
atm_iv reuses the solves; American-ITM, gated and unknown-style contracts are never solved. The certified
solver (`inverse.solve`, Stage 0 hoist and Stage 1 float filter) is called unchanged, so IV values are
identical to the single-contract `evaluate` path for the same operands. One numerical-owner context per
public call (not per contract). Forward-versus-strike comparisons are exact when r == q and otherwise use a
float with a high-precision Decimal fallback inside a relative 1e-9 band, so a tie goes to the lower strike
only when it is a true tie.
"""
from bisect import bisect_right
from collections import namedtuple
from decimal import Decimal, localcontext
from fractions import Fraction
from math import exp, sqrt

from option_feature_contracts import SolverConfig, ConvertedOperands

from .arithmetic import numerical_owner, nearest_binary64
from .inverse import solve
from .model import Operands
from .quotes import SCALE, DEFAULT_STALE_LIMIT_NS, to_ticks, G_OK, GATE_REASON, _spread_gate

LABEL_EXACT = "exact-model"
LABEL_APPROX = "approximate: European model on an American-style contract"
YEAR_NS = 31536000000000000
DAY_NS = 86400 * 10 ** 9
DEFAULT_SOLVER = SolverConfig("bisection1", "midpoint", 8.0, 256, 1e-10, 1e-10, 1e-10, 1e-10)

_G_NO_QUOTE, _G_EXCLUDED = 1, 6
_REASON = GATE_REASON + ("excluded_condition",)
_NEAR = 1e-9  # relative band in which a float forward comparison is re-decided exactly

ChainContract = namedtuple(
    "ChainContract", "contract_id expiry_days right strike bid ask event_ns known_at_ns style condition",
    defaults=(None, None, "regular"))
ContractIV = namedtuple("ContractIV", "status reason iv label")
AtmIV = namedtuple("AtmIV", "status reason strike forward call_iv put_iv iv label")
IV30 = namedtuple("IV30", "status reason iv label expiries_used method")

_NO_ATM = AtmIV("unavailable", "no_atm_strike", None, None, None, None, None, None)


def _exact(x):
    if isinstance(x, Fraction):
        return x
    if isinstance(x, float):
        return Fraction.from_float(x)
    return Fraction(Decimal(x) if isinstance(x, str) else x)


class _Forward:
    """F in ticks of 10**-8, F = S exp(drift). Exact comparisons when drift == 0 (F = S), else float with an
    exact Decimal fallback near a tie (a tie is impossible for drift != 0: F is irrational)."""
    __slots__ = ("s", "drift", "f", "_exact")

    def __init__(self, s_ticks, drift):
        self.s, self.drift, self._exact = s_ticks, drift, None
        self.f = float(s_ticks) if drift == 0 else (s_ticks * exp(float(drift)) if abs(drift) < 700 else None)

    def value(self):
        return self.f / SCALE if self.f is not None else float(self._decimal()) / SCALE

    def _decimal(self):
        if self._exact is None:
            with localcontext() as ctx:
                ctx.prec = 80
                self._exact = Decimal(self.s) * (Decimal(self.drift.numerator) / Decimal(self.drift.denominator)).exp()
        return self._exact

    def cmp(self, num, mult=1):
        """Sign of num - mult * F (num is an integer count of ticks)."""
        if self.drift == 0:
            d = num - mult * self.s
            return (d > 0) - (d < 0)
        if self.f is not None:
            d = num - mult * self.f
            if abs(d) > _NEAR * (mult * self.f + 1.0):
                return 1 if d > 0 else -1
        with localcontext() as ctx:
            ctx.prec = 80
            d = Decimal(num) - mult * self._decimal()
        return (d > 0) - (d < 0)

    def nearest(self, strikes):
        """Strike (ticks) nearest F in a non-empty ascending list; a true tie goes to the lower strike."""
        n = len(strikes)
        idx = bisect_right(strikes, self.f if self.f is not None else float(self._decimal()))
        if idx == 0:
            return strikes[0]
        if idx == n:
            return strikes[-1]
        lo, hi = strikes[idx - 1], strikes[idx]
        return lo if self.cmp(lo + hi, 2) >= 0 else hi


class _Expiry:
    __slots__ = ("days", "legs", "T", "Tf", "converted_t", "fwd", "_all", "_atm", "_nearest")

    def __init__(self, days):
        self.days = days
        self.legs = {}      # strike ticks -> [call index or None, put index or None]
        self.T = self.Tf = self.converted_t = self.fwd = self._all = self._atm = self._nearest = None


class IVChain:
    """One chain at one cutoff. `contracts`: iterable of ChainContract (bid, ask, strike decimal strings,
    ints or Fractions with at most 8 places; event_ns and known_at_ns integer ns; known_at_ns None means
    event_ns). spot, rate, dividend_yield: decimal strings, ints, Fractions or floats (rate and yield go
    through binary64 like the R25 volatility facts). Not thread safe; one numerical context per call."""

    def __init__(self, contracts, spot, rate, dividend_yield, cutoff_ns, stale_limit_ns=DEFAULT_STALE_LIMIT_NS,
                 solver=DEFAULT_SOLVER):
        self._solver = solver
        self._cutoff = cutoff_ns
        self._spot_ticks = to_ticks(spot)
        self._S = Fraction(self._spot_ticks, SCALE)
        self._rate = Fraction.from_float(float(rate))
        self._carry = Fraction.from_float(float(dividend_yield))
        if self._S <= 0:
            raise ValueError("spot must be positive")
        self._items = []     # per contract: (contract, strike ticks, midpoint2 ticks or None, gate code, expiry)
        self._ids = {}
        self._expiries = {}
        self._memo = {}
        self._owner = None
        eligible_gate = G_OK
        for c in contracts:
            days = c.expiry_days
            if type(days) is not int or days <= 0:
                raise ValueError("expiry_days must be a positive integer: %r" % (days,))
            if c.right not in ("call", "put"):
                raise ValueError("right must be call or put: %r" % (c.right,))
            if c.contract_id in self._ids:
                raise ValueError("duplicate contract id %r" % (c.contract_id,))
            strike = to_ticks(c.strike)
            if strike <= 0:
                raise ValueError("strike must be positive")
            bid, ask = to_ticks(c.bid), to_ticks(c.ask)
            known = c.event_ns if c.known_at_ns is None else c.known_at_ns
            if known > cutoff_ns or (bid is None and ask is None):
                gate = _G_NO_QUOTE
            elif c.condition != "regular":
                gate = _G_EXCLUDED
            else:
                gate = _spread_gate(bid, ask, cutoff_ns - c.event_ns, stale_limit_ns)
            index = len(self._items)
            exp_rec = self._expiries.get(days)
            if exp_rec is None:
                exp_rec = self._expiries[days] = _Expiry(days)
            slot = exp_rec.legs.setdefault(strike, [None, None])
            side = 0 if c.right == "call" else 1
            if slot[side] is not None:
                raise ValueError("duplicate contract for expiry, strike and right: %r" % (c.contract_id,))
            slot[side] = index
            self._ids[c.contract_id] = index
            self._items.append((c, strike, (bid + ask) if gate == eligible_gate else None, gate, exp_rec))

    # ------------------------------------------------------------------ per-expiry shared operands
    def _prepare(self, e):
        if e.T is None:
            e.T = Fraction(e.days, 365)
            e.Tf = nearest_binary64(e.T)
            e.fwd = _Forward(self._spot_ticks, (self._rate - self._carry) * e.T)
        return e

    def _all_strikes(self, e):
        if e._all is None:
            e._all = sorted(e.legs)
        return e._all

    def _atm_strike(self, e):
        """Nearest-forward strike among strikes whose call and put both pass the gates, or None."""
        if e._atm is None:
            items = self._items
            both = sorted(k for k, (ci, pi) in e.legs.items()
                          if ci is not None and pi is not None and items[ci][3] == G_OK and items[pi][3] == G_OK)
            e._atm = (self._prepare(e).fwd.nearest(both),) if both else ()
        return e._atm[0] if e._atm else None

    def _nearest_listed(self, e):
        if e._nearest is None:
            e._nearest = self._prepare(e).fwd.nearest(self._all_strikes(e))
        return e._nearest

    # ------------------------------------------------------------------ the certified solve (memoised)
    def _iv(self, index):
        """(sigma, None) or (None, reason) for an eligible, modelled contract; solved at most once."""
        hit = self._memo.get(index)
        if hit is not None:
            return hit
        c, strike, two_mid, _, e = self._items[index]
        self._prepare(e)
        K = Fraction(strike, SCALE)
        operands = Operands(self._S, K, self._rate, self._carry, e.T, Fraction(0), 1 if c.right == "call" else -1)
        converted = ConvertedOperands(float(self._S), float(K), float(self._rate), float(self._carry), None,
                                      e.days * DAY_NS, e.Tf)
        result = solve(operands, Fraction(two_mid, 2 * SCALE), self._solver, converted, self._owner)
        hit = (result.value, None) if result.status == "available" else (None, result.reason)
        self._memo[index] = hit
        return hit

    def _with_owner(self, fn, *args):
        if self._owner is not None:
            return fn(*args)
        with numerical_owner() as owner:
            self._owner = owner
            try:
                return fn(*args)
            finally:
                self._owner = None

    # ------------------------------------------------------------------ per-contract IV
    def _contract(self, index):
        c, strike, _, gate, e = self._items[index]
        if gate != G_OK:
            return ContractIV("unavailable", _REASON[gate], None, None)
        style = c.style
        if style == "european":
            label = LABEL_EXACT
        elif style == "american":
            if strike != self._nearest_listed(e):
                sign = e.fwd.cmp(strike)       # K - F; K = F is not ITM
                if (c.right == "call" and sign < 0) or (c.right == "put" and sign > 0):
                    return ContractIV("unavailable", "american_itm", None, None)
            label = LABEL_APPROX
        else:
            return ContractIV("unavailable", "style_unknown", None, None)
        value, reason = self._iv(index)
        if reason is not None:
            return ContractIV("unavailable", reason, None, None)
        return ContractIV("available", None, value, label)

    def contract_iv(self):
        """{contract_id: ContractIV} for every contract, in input order."""
        def run():
            for _, _, _, _, e in self._items:
                if e.fwd is None:
                    self._prepare(e)
            return {c[0].contract_id: self._contract(i) for i, c in enumerate(self._items)}
        return self._with_owner(run)

    # ------------------------------------------------------------------ ATM IV
    def atm_iv(self, expiry_days):
        return self._with_owner(self._atm_iv, expiry_days)

    def atm_iv_all(self):
        """{expiry_days: AtmIV} for every listed expiry, ascending."""
        return self._with_owner(lambda: {d: self._atm_iv(d) for d in sorted(self._expiries)})

    def _atm_iv(self, expiry_days):
        e = self._expiries.get(expiry_days)
        if e is None:
            return _NO_ATM
        strike = self._atm_strike(e)
        if strike is None:
            return _NO_ATM
        K = Fraction(strike, SCALE)
        forward = e.fwd.value()
        ci, pi = e.legs[strike]
        legs = (self._items[ci][0], self._items[pi][0])
        if any(c.style not in ("european", "american") for c in legs):
            return AtmIV("unavailable", "style_unknown", K, forward, None, None, None, None)
        call_iv, call_reason = self._iv(ci)
        put_iv, put_reason = self._iv(pi)
        if call_reason is not None or put_reason is not None:
            return AtmIV("unavailable", call_reason or put_reason, K, forward, call_iv, put_iv, None, None)
        label = LABEL_APPROX if any(c.style == "american" for c in legs) else LABEL_EXACT
        return AtmIV("available", None, K, forward, call_iv, put_iv, (call_iv + put_iv) / 2, label)

    # ------------------------------------------------------------------ 30-day constant maturity
    def iv_30d(self, target_days=30):
        return self._with_owner(self._iv_30d, target_days)

    def _iv_30d(self, target):
        if target in self._expiries:
            a = self._atm_iv(target)
            if a.status != "available":
                return IV30("unavailable", a.reason, None, None, (), None)
            return IV30("available", None, a.iv, a.label, (target,), "as_is")
        lower = [d for d in self._expiries if d < target]
        upper = [d for d in self._expiries if d > target]
        if not lower or not upper:
            return IV30("unavailable", "no_bracketing_expiry", None, None, (), None)
        lo, hi = max(lower), min(upper)
        used = (lo, hi)
        a_lo, a_hi = self._atm_iv(lo), self._atm_iv(hi)
        for a in (a_lo, a_hi):
            if a.status != "available":
                reason = "no_bracketing_expiry" if a.reason == "no_atm_strike" else a.reason
                return IV30("unavailable", reason, None, None, used, None)
        w_lo, w_hi = a_lo.iv * a_lo.iv * lo, a_hi.iv * a_hi.iv * hi
        variance = w_lo + (w_hi - w_lo) * (target - lo) / (hi - lo)
        label = LABEL_APPROX if LABEL_APPROX in (a_lo.label, a_hi.label) else LABEL_EXACT
        return IV30("available", None, sqrt(variance / target), label, used, "variance_interpolation")
