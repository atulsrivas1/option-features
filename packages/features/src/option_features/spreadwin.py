"""M1 OC6: the current spread against the contract's own last five minutes, time-weighted, in bps of midpoint.

Pure and single-threaded. Ratio = current spread bps / time-weighted average spread bps over the closed
window [max(T - window, session_open), T]. Fires "narrower" when ratio <= narrower_max and "wider" when
ratio >= wider_min (both inclusive); otherwise not_fired.

Ruled definition (r28 rulings D1-D11): the quote in effect at time t is the latest known one (order key
(event, seq, known_at), known_at <= t); the quote in effect at the window start (carry-in) is the latest known
by then, and only quotes with event time at or after the session open exist (nothing carries across the open);
each quote's interval starts at its known_at (clipped to the window start) and the current quote is weighted
from there to T; only intervals of regular-condition, valid (0 < bid < ask) quotes carry weight and the
denominator is their total length, so invalid, locked, crossed and excluded-condition stretches and gaps count
nothing; no weight at all gives unavailable `no_window_spread`. Coverage (G5) counts regular-condition updates
with event time in the window and known by T (validity ignored); fewer than coverage_min gives
`low_quote_coverage`. Gate order: no_quote, excluded_condition, validity, stale_quote (event time, strictly more
than the limit), low_quote_coverage, no_window_spread. A single-venue feed does not affect OC6.

Performance design: one backward pass over only the window plus its carry-in (no intermediate list); prices are parsed to integer
ticks once per distinct (bid, ask); the sweep is a single pass with integer nanosecond weights accumulated per
distinct bid+ask sum s as sum(w * (ask - bid)) (no Fraction, linear in the window); the decision is made on a
binary64 ratio only when it is clear of both thresholds (FILTER_EPS, bound in the comment below) and otherwise
exactly: the exact average is the fraction sum_s num_s / s combined by a balanced integer tree with no gcd and
compared by integer cross-multiplication. Exact `Fraction` values are built lazily on the result properties. If known_at is not
monotone in order a general sweep (sort by known_at, running maximum) gives the same ruled semantics.
"""
from fractions import Fraction

from .quotehist import (DEFAULT_COVERAGE_MIN, DEFAULT_STALE_LIMIT_NS, DEFAULT_WINDOW_NS, order_updates,
                        latest_index, price_ticks, quote_fault, rational, Ticks)
from .quotes import SCALE, SCALE_DIGITS

_POW = tuple(10 ** i for i in range(SCALE_DIGITS + 1))

BPS = 20000  # 10**4 bps per unit, over the midpoint (ask + bid) / 2
# Float filter: the binary64 ratio decides only when it is farther than FILTER_EPS (relative) from a threshold. The
# ratio is dc*W / (sc * sum(n_s / s)) with every n_s / s a correctly rounded int division and a naive float sum of m
# positive terms, so its relative error is at most (m + 8) * 2**-53 (< 1.2e-10 for m <= 10**6 distinct sums; a window
# cannot have more distinct sums than updates). FILTER_EPS = 1e-9 leaves a factor of 8; inside it the exact integer
# decision runs, so results never depend on the filter (tested against the always-exact decision).
FILTER_EPS = 1e-9
MAX_FILTER_TERMS = 10 ** 6


class OC6Params:
    __slots__ = ("window_ns", "stale_limit_ns", "coverage_min", "np", "nq", "wp", "wq", "n_lo", "n_hi", "w_lo", "w_hi")

    def __init__(self, window_ns=DEFAULT_WINDOW_NS, stale_limit_ns=DEFAULT_STALE_LIMIT_NS,
                 coverage_min=DEFAULT_COVERAGE_MIN, narrower_max="0.75", wider_min="1.50"):
        for name, v in (("window_ns", window_ns), ("stale_limit_ns", stale_limit_ns), ("coverage_min", coverage_min)):
            if type(v) is not int or v < 0:
                raise ValueError("%s must be an int >= 0" % name)
        lo, hi = rational(narrower_max, "narrower_max"), rational(wider_min, "wider_min")
        if not lo < hi:
            raise ValueError("narrower_max must be below wider_min")
        self.window_ns, self.stale_limit_ns, self.coverage_min = window_ns, stale_limit_ns, coverage_min
        self.np, self.nq, self.wp, self.wq = lo.numerator, lo.denominator, hi.numerator, hi.denominator
        nf, wf = lo.numerator / lo.denominator, hi.numerator / hi.denominator
        self.n_lo, self.n_hi, self.w_lo, self.w_hi = nf * (1 - FILTER_EPS), nf * (1 + FILTER_EPS), wf * (1 - FILTER_EPS), wf * (1 + FILTER_EPS)


class OC6Result:
    """status fired | not_fired | unavailable; label narrower | wider when fired; exact values are lazy Fractions."""
    __slots__ = ("status", "reason", "label", "regular_update_count", "_dc", "_sc", "_acc", "_w", "_nd")

    def __init__(self, status, reason, label, count, dc=0, sc=0, acc=None, w=0, nd=None):
        self.status, self.reason, self.label, self.regular_update_count = status, reason, label, count
        self._dc, self._sc, self._acc, self._w, self._nd = dc, sc, acc, w, nd

    def _exact(self):
        """(num, den) with sum over windows of weight * spread / (bid + ask) = num / den, unreduced; cached."""
        if self._nd is None:
            acc = self._acc
            self._nd = _tree_sum([(n, s) for s, n in acc.items()]) if len(acc) > 1 else (next(iter(acc.values())), next(iter(acc)))
        return self._nd

    @property
    def value(self):
        if not self._w:
            return None
        n, d = self._exact()
        return Fraction(self._dc * d * self._w, self._sc * n)

    @property
    def current_spread(self):
        return Fraction(self._dc, SCALE) if self._w else None

    @property
    def midpoint(self):
        return Fraction(self._sc, 2 * SCALE) if self._w else None

    @property
    def spread_bps(self):
        return Fraction(BPS * self._dc, self._sc) if self._w else None

    @property
    def average_spread_bps(self):
        if not self._w:
            return None
        n, d = self._exact()
        return Fraction(BPS * n, d * self._w)

    def __repr__(self):
        return "OC6Result(%s, %s, %s, %s)" % (self.status, self.reason, self.label, self.value)


def _unavailable(reason, count):
    return OC6Result("unavailable", reason, None, count)


def _tree_sum(pairs):
    """Sum of n/d pairs as one (num, den) without reduction, by balanced pairwise merging."""
    while len(pairs) > 1:
        nxt = [(n1 * d2 + n2 * d1, d1 * d2) for (n1, d1), (n2, d2) in zip(pairs[::2], pairs[1::2])]
        if len(pairs) & 1:
            nxt.append(pairs[-1])
        pairs = nxt
    return pairs[0]


def _ticks(v):
    """price_ticks with the plain decimal-string case inlined."""
    kind = type(v)
    if kind is Ticks:
        return v
    if kind is str:
        whole, _, frac = v.partition(".")
        n = len(frac)
        if n <= SCALE_DIGITS:
            try:
                return int(whole + frac) * _POW[SCALE_DIGITS - n]
            except ValueError:
                pass
    return price_ticks(v)


def _state(key, cache):
    """(ask - bid, ask + bid) in ticks for a usable quote (0 < bid < ask), else None; cached per distinct (bid, ask)."""
    bid, ask = key
    ub = None if bid is None else _ticks(bid)
    ua = None if ask is None else _ticks(ask)
    st = (ua - ub, ua + ub) if ub is not None and ua is not None and 0 < ub < ua else None
    cache[key] = st
    return st


def _scan_monotone(ups, i, t_ns, open_ns, wstart):
    """Single backward pass when known_at never decreases in order (the normal case); None if it does.

    Returns (acc, total_weight_ns, regular_count) with acc = {ask + bid: sum(weight_ns * (ask - bid))}.
    """
    acc = {}
    wtot = count = 0
    nxt = t_ns
    cache = {}
    for j in range(i, -1, -1):
        u = ups[j]
        e = u[1]
        ka = u[2]
        if e > t_ns or ka > t_ns:
            continue
        if e < open_ns:
            break
        key = (u[3], u[4])
        st = cache.get(key, 0)
        if st == 0:
            st = _state(key, cache)
        if u[5]:
            if e >= wstart:
                count += 1
        else:
            st = None
        s = ka if ka > wstart else wstart
        if s > nxt:
            return None
        if st is not None and nxt > s:
            w = nxt - s
            k = st[1]
            acc[k] = acc.get(k, 0) + w * st[0]
            wtot += w
        nxt = s
        if e < wstart and ka <= wstart:
            break
    return acc, wtot, count


def _scan_general(ups, i, t_ns, open_ns, wstart):
    """Same semantics when known_at is not monotone in order: at each time the quote in effect is the
    highest-ordered one already known (sort by known_at, running maximum)."""
    sel = []
    count = 0
    cache = {}
    for j in range(i, -1, -1):
        u = ups[j]
        e, ka = u[1], u[2]
        if e > t_ns or ka > t_ns:
            continue
        if e < open_ns:
            break
        key = (u[3], u[4])
        st = cache.get(key, 0)
        if st == 0:
            st = _state(key, cache)
        if u[5]:
            sel.append((ka, st))
            if e >= wstart:
                count += 1
        else:
            sel.append((ka, None))
        if e < wstart and ka <= wstart:
            break
    sel.reverse()
    acc = {}
    wtot = 0
    order = sorted(range(len(sel)), key=lambda j: (sel[j][0], j))
    cur = -1
    tprev = wstart
    for j in order:
        k = sel[j][0]
        if k > tprev:
            if cur >= 0 and sel[cur][1] is not None:
                st = sel[cur][1]
                w = k - tprev
                acc[st[1]] = acc.get(st[1], 0) + w * st[0]
                wtot += w
            tprev = k
        if j > cur:
            cur = j
    if cur >= 0 and sel[cur][1] is not None and t_ns > tprev:
        st = sel[cur][1]
        w = t_ns - tprev
        acc[st[1]] = acc.get(st[1], 0) + w * st[0]
        wtot += w
    return acc, wtot, count


def _oc6(t_ns, updates, session_open_ns, window_ns, limit, cov_min, np_, nq, wp, wq, n_lo, n_hi, w_lo, w_hi):
    ups = order_updates(updates)
    i = latest_index(ups, t_ns)
    if i < 0:
        return _unavailable("no_quote", 0)
    _, ev, _, bid, ask, regular, _ = ups[i]
    if not regular:
        return _unavailable("excluded_condition", 0)
    b, a = price_ticks(bid), price_ticks(ask)
    fault = quote_fault(b, a)
    if fault is not None:
        return _unavailable(fault, 0)
    if t_ns - ev > limit:
        return _unavailable("stale_quote", 0)
    wstart = t_ns - window_ns
    if wstart < session_open_ns:
        wstart = session_open_ns
    # backward scan: the window and its carry-in only (earlier quotes can never be in effect inside the window)
    scan = _scan_monotone(ups, i, t_ns, session_open_ns, wstart)
    if scan is None:
        scan = _scan_general(ups, i, t_ns, session_open_ns, wstart)
    acc, wtot, count = scan
    if count < cov_min:
        return _unavailable("low_quote_coverage", count)
    if wtot == 0:
        return _unavailable("no_window_spread", count)
    dc, sc = a - b, a + b
    nd = None
    status, label = "fired", None
    r = None
    if len(acc) <= MAX_FILTER_TERMS:
        tot = 0.0
        for k, n in acc.items():
            tot += n / k
        r = dc * wtot / (sc * tot)
        if r < n_lo:
            label = "narrower"
        elif r > w_hi:
            label = "wider"
        elif n_hi < r < w_lo:
            status = "not_fired"
        else:
            r = None
    if r is None:  # inside the filter margin (or too many terms): exact integer decision
        num, den = nd = _tree_sum([(n, k) for k, n in acc.items()]) if len(acc) > 1 else (next(iter(acc.values())), next(iter(acc)))
        left = dc * den * wtot  # ratio = left / (sc * num)
        right = sc * num
        if left * nq <= np_ * right:
            label = "narrower"
        elif left * wq >= wp * right:
            label = "wider"
        else:
            status = "not_fired"
    return OC6Result(status, None, label, count, dc, sc, acc, wtot, nd)


def oc6(updates, t_ns, session_open_ns, params=None, consolidated=True, standard=True):
    """One contract. updates: QuoteUpdate records; t_ns and session_open_ns: int ns. Raises OCStructuralError.

    `consolidated` and `standard` are accepted for symmetry with OC5 and have no effect: a single-venue feed
    does not block OC6 (D6) and a non-standard contract is evaluated.
    """
    p = params or OC6Params()
    return _oc6(t_ns, updates, session_open_ns, p.window_ns, p.stale_limit_ns, p.coverage_min, p.np, p.nq, p.wp, p.wq, p.n_lo, p.n_hi, p.w_lo, p.w_hi)


def oc6_many(items, params=None):
    """Many contracts: items is an iterable of (t_ns, updates, session_open_ns); identical to `oc6` per item."""
    p = params or OC6Params()
    args = (p.window_ns, p.stale_limit_ns, p.coverage_min, p.np, p.nq, p.wp, p.wq, p.n_lo, p.n_hi, p.w_lo, p.w_hi)
    return [_oc6(t, u, o, *args) for t, u, o in items]
