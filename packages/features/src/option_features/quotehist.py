"""M1 shared pieces for OC5 and OC6: the quote update and QuoteSize records, input validation, event ordering.

Pure and single-threaded (D4 amended). QuoteSize is a new additive record keyed by quote revision, so the
frozen R25 Quote bytes are untouched; these records are library inputs, not wire records.

Ordering (D9): updates are ordered by (event_ns, seq, known_at_ns); a missing seq sorts before any seq; two
updates equal on all three are an `ambiguous_ordering` structural error. Event time must not decrease in the
order given (`non_monotone_event_time`). The latest quote at T is the last in that order with
event_ns <= T and known_at_ns <= T (D7, no look-ahead).

Prices are decimal strings, ints (whole units), Decimals, Fractions or `Ticks` (pre-converted integer ticks of
10**-8, the fast path for repeated windows over the same updates); a binary float is `malformed_type`.

Structural errors (`OCStructuralError.code`): malformed_type, non_monotone_event_time, ambiguous_ordering,
negative_size, non_integer_size, duplicate_size_revision. They raise; every other outcome is a result.
"""
from collections import namedtuple
from decimal import Decimal
from fractions import Fraction

from .quotes import to_ticks

QuoteUpdate = namedtuple("QuoteUpdate", "rev event_ns known_at_ns bid ask regular seq", defaults=(None,))
QuoteSize = namedtuple("QuoteSize", "rev bid_size ask_size")

DEFAULT_STALE_LIMIT_NS = 10_000_000_000
DEFAULT_WINDOW_NS = 300_000_000_000
DEFAULT_COVERAGE_MIN = 5



class Ticks(int):
    """A price already in integer ticks of 10**-8 (see `as_ticks`). Convert once at ingest and reuse it in every
    window evaluation; a plain int price means whole units, so the two must not be mixed in one call."""
    __slots__ = ()


def as_ticks(value):
    """Ticks (or None) for a decimal string, int, Decimal or Fraction; raises OCStructuralError if not exact."""
    return None if value is None else Ticks(price_ticks(value))


_PRICE_TYPES = frozenset((str, int, Decimal, Fraction, Ticks))


class OCStructuralError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code


def order_updates(updates):
    """Validate every update and return them in (event, seq, known_at) order (the input list when already ordered)."""
    ups = updates if type(updates) is list else list(updates)
    prev = None
    tie = False
    types = _PRICE_TYPES
    kinds = set()
    for u in ups:
        _, ev, ka, bid, ask, reg, seq = u
        kinds.add(type(bid))
        kinds.add(type(ask))
        if (type(ev) is not int or type(ka) is not int or type(reg) is not bool
                or (seq is not None and type(seq) is not int)
                or (bid is not None and type(bid) not in types) or (ask is not None and type(ask) not in types)):
            raise OCStructuralError("malformed_type", "update %r" % (u,))
        if prev is not None:
            if ev < prev:
                raise OCStructuralError("non_monotone_event_time")
            if ev == prev:
                tie = True
        prev = ev
    if Ticks in kinds and int in kinds:
        raise OCStructuralError("malformed_type", "int (whole units) and Ticks prices mixed in one call")
    if tie:
        def key(u):
            return (u[1], u[6] is not None, u[6] or 0, u[2])
        ups = sorted(ups, key=key)
        for a, b in zip(ups, ups[1:]):
            if key(a) == key(b):
                raise OCStructuralError("ambiguous_ordering")
    return ups


def latest_index(ups, t_ns):
    """Index of the latest update known and occurring at or before t_ns in the ordered list, or -1."""
    i = len(ups) - 1
    while i >= 0:
        u = ups[i]
        if u[1] <= t_ns and u[2] <= t_ns:
            return i
        i -= 1
    return -1


def price_ticks(value):
    if type(value) is Ticks:
        return value
    try:
        return to_ticks(value)
    except (ValueError, ArithmeticError):
        raise OCStructuralError("malformed_type", "price %r" % (value,)) from None


def quote_fault(bid, ask):
    """Validity gate on tick values (precedence invalid: a missing side or bid <= 0; crossed: bid > ask, so ask <= 0 with bid > 0 is crossed; locked); None when the quote is usable."""
    if bid is None or ask is None or bid <= 0:
        return "invalid_quote"
    if bid > ask:
        return "crossed_market"
    if bid == ask:
        return "locked_market"
    return None


def size_map(sizes):
    """{rev: (bid_size, ask_size)} after validating every row (None means missing)."""
    out = {}
    for rev, bs, as_ in sizes:
        for v in (bs, as_):
            if v is None:
                continue
            kind = type(v)
            if kind is int:
                if v < 0:
                    raise OCStructuralError("negative_size", "rev %r" % (rev,))
            elif kind is float:
                raise OCStructuralError("non_integer_size", "rev %r" % (rev,))
            else:
                raise OCStructuralError("malformed_type", "size %r" % (v,))
        if rev in out:
            raise OCStructuralError("duplicate_size_revision", "rev %r" % (rev,))
        out[rev] = (bs, as_)
    return out


def rational(value, name):
    """Exact positive Fraction from a decimal string, int, Decimal or Fraction (binary floats are rejected)."""
    if type(value) not in (str, int, Decimal, Fraction):
        raise ValueError("%s must be a decimal string, int, Decimal or Fraction" % name)
    r = Fraction(value)
    if r <= 0:
        raise ValueError("%s must be positive" % name)
    return r
