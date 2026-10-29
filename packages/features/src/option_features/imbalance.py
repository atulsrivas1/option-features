"""M1 OC5: displayed size imbalance of the latest causal quote, (bid_size - ask_size) / (bid_size + ask_size).

Pure and single-threaded. Sizes live in `QuoteSize` records keyed by quote revision (see quotehist).
Fires when |imbalance| >= threshold (inclusive); label "bid" for a positive and "ask" for a negative imbalance.

Gate order (ruled): no_quote, excluded_condition (latest quote, no fallback to an older one),
not_consolidated, validity (invalid_quote, crossed_market; a locked quote still evaluates, ruling Q8), stale_quote (event time, strictly
more than the limit; exactly the limit is fresh), then the size reasons missing_size (no QuoteSize row or a
missing side) and zero_displayed_size (both sides 0). Low OC6 coverage never blocks OC5.

Performance design: the threshold is hoisted into an integer fraction in `OC5Params`, so the decision is two
integer multiplications and a comparison; the exact `Fraction` value is built lazily on `.value`. Unavailable
outcomes are shared immutable results. `oc5_many` evaluates many contracts with every per-call constant bound once.
"""
from fractions import Fraction

from .quotehist import (DEFAULT_STALE_LIMIT_NS, order_updates, latest_index, price_ticks, quote_fault,
                        size_map, rational)

OC5_LABELS = ("bid", "ask")


class OC5Params:
    __slots__ = ("stale_limit_ns", "p", "q")

    def __init__(self, imbalance_threshold="0.60", stale_limit_ns=DEFAULT_STALE_LIMIT_NS):
        th = rational(imbalance_threshold, "imbalance_threshold")
        if th > 1:
            raise ValueError("imbalance_threshold must be in (0, 1]")
        if type(stale_limit_ns) is not int or stale_limit_ns < 0:
            raise ValueError("stale_limit_ns must be an int >= 0")
        self.stale_limit_ns = stale_limit_ns
        self.p, self.q = th.numerator, th.denominator


class OC5Result:
    """status fired | not_fired | unavailable; reason set only when unavailable; label bid | ask when fired."""
    __slots__ = ("status", "reason", "label", "_diff", "_total")

    def __init__(self, status, reason, label, diff, total):
        self.status, self.reason, self.label, self._diff, self._total = status, reason, label, diff, total

    @property
    def value(self):
        return None if self._total is None else Fraction(self._diff, self._total)

    def __repr__(self):
        return "OC5Result(%s, %s, %s, %s)" % (self.status, self.reason, self.label, self.value)


_UNAVAILABLE = {r: OC5Result("unavailable", r, None, 0, None) for r in (
    "no_quote", "excluded_condition", "not_consolidated", "invalid_quote", "crossed_market",
    "stale_quote", "missing_size", "zero_displayed_size")}


def _oc5(t_ns, updates, sizes, consolidated, limit, p, q):
    ups = order_updates(updates)
    smap = size_map(sizes)
    i = latest_index(ups, t_ns)
    if i < 0:
        return _UNAVAILABLE["no_quote"]
    rev, ev, _, bid, ask, regular, _ = ups[i]
    if not regular:
        return _UNAVAILABLE["excluded_condition"]
    if not consolidated:
        return _UNAVAILABLE["not_consolidated"]
    fault = quote_fault(price_ticks(bid), price_ticks(ask))
    if fault is not None and fault != "locked_market":  # a locked quote still evaluates (ruling Q8)
        return _UNAVAILABLE[fault]
    if t_ns - ev > limit:
        return _UNAVAILABLE["stale_quote"]
    sz = smap.get(rev)
    if sz is None or sz[0] is None or sz[1] is None:
        return _UNAVAILABLE["missing_size"]
    b, a = sz
    total = b + a
    if total == 0:
        return _UNAVAILABLE["zero_displayed_size"]
    diff = b - a
    if (diff if diff > 0 else -diff) * q >= p * total:
        return OC5Result("fired", None, "bid" if diff > 0 else "ask", diff, total)
    return OC5Result("not_fired", None, None, diff, total)


def oc5(updates, sizes, t_ns, params=None, consolidated=True, standard=True):
    """One contract. updates: QuoteUpdate records; sizes: QuoteSize records; t_ns: evaluation time (int ns).

    consolidated=False is a single-venue feed (OC5 only: not_consolidated). `standard` has no effect (a
    non-standard contract is evaluated). Raises OCStructuralError.
    """
    params = params or OC5Params()
    return _oc5(t_ns, updates, sizes, consolidated, params.stale_limit_ns, params.p, params.q)


def oc5_many(items, params=None):
    """Many contracts: items is an iterable of (t_ns, updates, sizes, consolidated); returns results in order.

    Identical to calling `oc5` per item (tested); a structural error in any item raises.
    """
    params = params or OC5Params()
    limit, p, q = params.stale_limit_ns, params.p, params.q
    return [_oc5(t, u, s, c, limit, p, q) for t, u, s, c in items]
