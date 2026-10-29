"""P1 quote gates, trade signing under the touch policy, and the batched stream classifier.

Pure and single-threaded (D4 amended): no I/O, clocks, threads or shared state.

Arithmetic is exact. Decimal prices are held as integer ticks of 10**-8 (`to_ticks`; more than
8 places is rejected, never rounded), times are integer nanoseconds, premium is
price x size x multiplier in integer ticks, and every ratio is a `Fraction`. Nothing here uses
binary64 except the legacy midpoint-split rule, which is delegated unchanged to the shipped
variants1 `epsilon_side`, so the default mode reproduces the legacy signing exactly.

Performance design (owner goal): `classify_stream` is a single pass that keeps one tuple of
precomputed per-contract quote state (`bid + epsilon`, `ask - epsilon`, validity code, time), so a
trade costs one dict lookup, one parse and at most four integer comparisons. Results are columnar
(`bytearray` codes, `array('q')` spread and midpoint-sum ticks); no per-record object, string or
Fraction is built on the hot path. Single-record and batch results are identical by test.
"""
from array import array
from collections import namedtuple
from decimal import Decimal
from fractions import Fraction

from .variants1.signing import epsilon_side

SCALE_DIGITS = 8
SCALE = 10 ** SCALE_DIGITS
STANDARD_MULTIPLIER = 100
DEFAULT_MAX_QUOTE_AGE_NS = 3_000_000_000
DEFAULT_STALE_LIMIT_NS = 10_000_000_000
ASK_LABEL = "ask-side proxy"
BID_LABEL = "bid-side proxy"
INSIDE_SPREAD_MODES = ("split", "unknown")

_POW = tuple(10 ** i for i in range(SCALE_DIGITS + 1))

# Quote gate codes for the spread (precedence: no_quote, invalid, crossed, locked, stale).
G_OK, G_NO_QUOTE, G_INVALID, G_CROSSED, G_LOCKED, G_STALE = range(6)
GATE_REASON = (None, "no_quote", "invalid_quote", "crossed_market", "locked_market", "stale_quote")

# Sign codes (precedence: no_quote, invalid, crossed, stale, then the touch rule; locked never blocks).
S_ASK, S_BID, S_INSIDE, S_AMBIGUOUS, S_NO_QUOTE, S_INVALID, S_CROSSED, S_STALE, S_DEAD_BAND = range(1, 10)
SIGN_REASON = {S_ASK: None, S_BID: None, S_INSIDE: "inside_spread", S_AMBIGUOUS: "ambiguous_touch",
               S_NO_QUOTE: "no_quote", S_INVALID: "invalid_quote", S_CROSSED: "crossed_market",
               S_STALE: "stale_quote", S_DEAD_BAND: "dead_band"}
TRADE_CODE_BASE = 16  # classify_stream stores a trade's sign code as TRADE_CODE_BASE + code

Sign = namedtuple("Sign", "status reason side label")
SpreadValues = namedtuple("SpreadValues", "spread midpoint spread_bps")
SignAggregate = namedtuple(
    "SignAggregate",
    "status reason ask_premium bid_premium unclassified_premium classified_premium "
    "call_ask_plus_put_bid_premium put_ask_plus_call_bid_premium unclassified_share_of_total "
    "ask_share_of_classified bid_share_of_classified labels")

_SIGN_RESULT = {
    S_ASK: Sign("available", None, "ask", ASK_LABEL),
    S_BID: Sign("available", None, "bid", BID_LABEL),
}
for _code, _reason in SIGN_REASON.items():
    if _reason is not None:
        _SIGN_RESULT[_code] = Sign("unclassified", _reason, None, None)
del _code, _reason


def to_ticks(value):
    """Exact integer ticks of 10**-8 from a decimal string, int, Decimal or Fraction; None passes through."""
    if value is None:
        return None
    kind = type(value)
    if kind is str:
        whole, _, frac = value.partition(".")
        digits = len(frac)
        if digits > SCALE_DIGITS:
            raise ValueError("more than %d decimal places: %r" % (SCALE_DIGITS, value))
        return int(whole + frac) * _POW[SCALE_DIGITS - digits]
    if kind is int:
        return value * SCALE
    scaled = Fraction(value) * SCALE
    if scaled.denominator != 1:
        raise ValueError("not representable in 10**-%d ticks: %r" % (SCALE_DIGITS, value))
    return scaled.numerator


def from_ticks(ticks):
    return Fraction(ticks, SCALE)


def spread_reason(bid, ask, age_ns, stale_limit_ns):
    """Design reason why the spread is unavailable, or None. bid and ask are ticks or None."""
    return GATE_REASON[_spread_gate(bid, ask, age_ns, stale_limit_ns)]


def _spread_gate(bid, ask, age_ns, stale_limit_ns):
    if bid is None:
        return G_NO_QUOTE if ask is None else G_INVALID
    if ask is None or bid <= 0:
        return G_INVALID
    if bid > ask:
        return G_CROSSED
    if bid == ask:
        return G_LOCKED
    if age_ns > stale_limit_ns:
        return G_STALE
    return G_OK


def quote_spread(bid, ask):
    """Exact spread, midpoint and spread in bps of the midpoint for an available quote (ticks)."""
    total = ask + bid
    if total <= 0:
        raise ValueError("spread needs a positive midpoint")
    return SpreadValues(Fraction(ask - bid, SCALE), Fraction(total, 2 * SCALE), Fraction(20000 * (ask - bid), total))


def _touch_code(p, bid, ask, eps):
    """Touch policy on a valid quote: ask if p >= ask - eps, bid if p <= bid + eps (inclusive)."""
    hit_ask = p >= ask - eps
    if p <= bid + eps:
        return S_AMBIGUOUS if hit_ask else S_BID
    return S_ASK if hit_ask else S_INSIDE


def _check_params(inside_spread, epsilon, max_quote_age_ns):
    if inside_spread not in INSIDE_SPREAD_MODES:
        raise ValueError("inside_spread must be 'split' (legacy default) or 'unknown'")
    eps = to_ticks(epsilon)
    if eps < 0:
        raise ValueError("epsilon must be >= 0")
    if max_quote_age_ns < 0:
        raise ValueError("max_quote_age_ns must be >= 0")
    return eps


def _sign_code(p, bid, ask, qt, t, eps, max_age, split):
    """One trade against one quote (ticks, ns). bid and ask may be None; p is the trade price in ticks."""
    if (bid is None and ask is None) or qt > t:
        return S_NO_QUOTE
    age = t - qt
    if split:
        # Legacy order, unchanged: stale first, then validity, then ask-first epsilon with midpoint split.
        if age > max_age:
            return S_STALE
        if p is None or bid is None or ask is None or not (p > 0 and bid > 0 and ask >= bid):
            return S_INVALID
        side, _ = epsilon_side(p / SCALE, bid / SCALE, ask / SCALE, eps / SCALE)
        return S_ASK if side == "buy" else (S_BID if side == "sell" else S_DEAD_BAND)
    if p is None or p <= 0 or bid is None or ask is None or bid <= 0:
        return S_INVALID
    if bid > ask:
        return S_CROSSED
    if age > max_age:
        return S_STALE
    return _touch_code(p, bid, ask, eps)


def sign_trade(price, quote, trade_t_ns, *, inside_spread="split", epsilon=0, max_quote_age_ns=DEFAULT_MAX_QUOTE_AGE_NS):
    """Classify one trade against the quote in force.

    quote is None or (bid, ask, t_ns). A quote after the trade is unusable (no_quote); one at the trade
    time (same nanosecond) is usable. inside_spread="split" (default) is the legacy rule (ask-first
    epsilon, then midpoint split); "unknown" is the touch policy of the design profile: ask side if
    price >= ask - epsilon, bid side if price <= bid + epsilon (inclusive), both is unclassified
    `ambiguous_touch`, neither is unclassified `inside_spread`. Locked quotes sign normally.
    """
    eps = _check_params(inside_spread, epsilon, max_quote_age_ns)
    p = to_ticks(price)
    if quote is None:
        return _SIGN_RESULT[S_NO_QUOTE]
    bid, ask, qt = quote
    code = _sign_code(p, to_ticks(bid), to_ticks(ask), qt, trade_t_ns, eps, max_quote_age_ns, inside_spread == "split")
    return _SIGN_RESULT[code]


def sign_aggregate(trades, *, inside_spread="unknown", epsilon=0, max_quote_age_ns=DEFAULT_MAX_QUOTE_AGE_NS):
    """Premium by side. trades: iterable of (price, size, right, t_ns, quote); premium = price x size x 100.

    Unclassified premium includes every trade that could not be signed, whatever the reason. When no premium
    is classified the result is unavailable `no_classified_premium` and both shares are None (PO-P1-01).
    """
    eps = _check_params(inside_spread, epsilon, max_quote_age_ns)
    split = inside_spread == "split"
    ask = bid = unc = call_ask = put_bid = put_ask = call_bid = 0
    for price, size, right, t, quote in trades:
        p = to_ticks(price)
        premium = p * size
        if quote is None:
            code = S_NO_QUOTE
        else:
            qb, qa, qt = quote
            code = _sign_code(p, to_ticks(qb), to_ticks(qa), qt, t, eps, max_quote_age_ns, split)
        if code == S_ASK:
            ask += premium
            if right == "call":
                call_ask += premium
            else:
                put_ask += premium
        elif code == S_BID:
            bid += premium
            if right == "put":
                put_bid += premium
            else:
                call_bid += premium
        else:
            unc += premium
    m = STANDARD_MULTIPLIER
    classified = ask + bid
    total = classified + unc

    def money(x):
        return Fraction(x * m, SCALE)

    def share(a, b):
        return None if b == 0 else Fraction(a, b)

    status, reason = ("unavailable", "no_classified_premium") if classified == 0 else ("available", None)
    return SignAggregate(
        status, reason, money(ask), money(bid), money(unc), money(classified), money(call_ask + put_bid),
        money(put_ask + call_bid), share(unc, total), share(ask, classified), share(bid, classified),
        (("ask_premium", ASK_LABEL), ("bid_premium", BID_LABEL)))


class StreamClassification:
    """Columnar result of `classify_stream`; index i is record i of the input.

    codes[i] is a gate code (0..5, GATE_REASON) for a quote and TRADE_CODE_BASE + a sign code
    (SIGN_REASON) for a trade. spread[i] and mid2[i] are the spread (ask - bid) and the midpoint sum
    (ask + bid) in ticks for a quote whose gate is open, else 0. Premiums are exact integer ticks
    x size x 100 (divide by SCALE for money).
    """
    __slots__ = ("codes", "spread", "mid2", "ask_premium", "bid_premium", "unclassified_premium", "quotes", "trades")

    def __init__(self, codes, spread, mid2, ask, bid, unclassified, quotes, trades):
        self.codes, self.spread, self.mid2 = codes, spread, mid2
        self.ask_premium, self.bid_premium, self.unclassified_premium = ask, bid, unclassified
        self.quotes, self.trades = quotes, trades

    def count(self, code):
        return self.codes.count(code)

    def sign(self, i):
        return _SIGN_RESULT[self.codes[i] - TRADE_CODE_BASE]

    def spread_reason(self, i):
        return GATE_REASON[self.codes[i]]

    def spread_bps(self, i):
        total = self.mid2[i]
        return Fraction(20000 * self.spread[i], total) if total else None


def classify_stream(records, *, epsilon=0, max_quote_age_ns=DEFAULT_MAX_QUOTE_AGE_NS):
    """Spread gate for every quote and touch-policy sign for every trade, in one pass.

    records: sequence (an iterable is materialised once) of tuples ordered by non-decreasing time, else
    ValueError. Records at equal time apply in input order.
      ("q", contract, t_ns, bid, ask)    bid and ask are decimal strings or None
      ("t", contract, t_ns, price, size) price is a decimal string, size is an int
    A trade is signed against the latest quote of its contract at or before it (touch policy,
    inside_spread="unknown"); a quote with neither bid nor ask replaces the state and reads as no_quote.
    The legacy midpoint split is not a batch mode: use `sign_trade(..., inside_spread="split")`.

    Hoisted out of the loop: parameter checks, epsilon in ticks, preallocated columnar outputs and the
    per-contract `(time, bid + epsilon, ask - epsilon, validity)` quote state. A decimal string with exactly
    four places (the common tick format, 10**-8 ticks = text without the point x 10**4) is parsed inline;
    any other format falls back to `to_ticks`, with identical results.
    """
    eps = _check_params("unknown", epsilon, max_quote_age_ns)
    if not isinstance(records, (list, tuple)):
        records = list(records)
    n = len(records)
    tk = to_ticks
    codes = bytearray(n)
    spread = array("q", bytes(8 * n))
    mid2 = array("q", bytes(8 * n))
    last = {}
    last_get = last.get
    ask_sum = bid_sum = unc_sum = 0
    quotes = 0
    prev = None
    base = TRADE_CODE_BASE
    for i, (kind, c, t, x, y) in enumerate(records):
        if prev is not None and t < prev:
            raise ValueError("records must be ordered by time")
        prev = t
        if kind == "q":
            quotes += 1
            if x is None:
                gate, bid, ask = (G_NO_QUOTE if y is None else G_INVALID), 0, 0
                qcode = S_NO_QUOTE if y is None else S_INVALID
            else:
                bid = int(x.replace(".", "")) * 10000 if x[-5:-4] == "." else tk(x)
                if y is None:
                    gate, ask, qcode = G_INVALID, 0, S_INVALID
                else:
                    ask = int(y.replace(".", "")) * 10000 if y[-5:-4] == "." else tk(y)
                    if bid <= 0:
                        gate, qcode = G_INVALID, S_INVALID
                    elif bid > ask:
                        gate, qcode = G_CROSSED, S_CROSSED
                    elif bid == ask:
                        gate, qcode = G_LOCKED, 0
                    else:
                        gate, qcode = G_OK, 0
                        spread[i] = ask - bid
                        mid2[i] = ask + bid
            codes[i] = gate
            last[c] = (t, bid + eps, ask - eps, qcode)
        else:
            p = int(x.replace(".", "")) * 10000 if x[-5:-4] == "." else tk(x)
            prem = p * y
            q = last_get(c)
            if q is None or q[3] == S_NO_QUOTE:
                code = S_NO_QUOTE
            else:
                qt, bid_hi, ask_lo, qcode = q
                if p <= 0 or qcode == S_INVALID:
                    code = S_INVALID
                elif qcode:
                    code = qcode
                elif t - qt > max_quote_age_ns:
                    code = S_STALE
                elif p >= ask_lo:
                    code = S_AMBIGUOUS if p <= bid_hi else S_ASK
                elif p <= bid_hi:
                    code = S_BID
                else:
                    code = S_INSIDE
            if code == S_ASK:
                ask_sum += prem
            elif code == S_BID:
                bid_sum += prem
            else:
                unc_sum += prem
            codes[i] = base + code
    m = STANDARD_MULTIPLIER
    return StreamClassification(codes, spread, mid2, ask_sum * m, bid_sum * m, unc_sum * m, quotes, n - quotes)
