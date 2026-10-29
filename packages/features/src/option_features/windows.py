"""P1 window premium with an explicit window end (F3) and count coverage for quote updates (G5).

Pure and single-threaded. Exact integer arithmetic (see `quotes.to_ticks`): premium is
price x size x 100 in integer ticks, returned as `Fraction`. Windows are closed at both ends.

F3: `window_end_ns=None` is the legacy mode (the window ends at the last standard print, the
last-print anchor); an integer `window_end_ns` is the explicit end (the evaluation time) and the
window is [end - window_ns, end]. Prints after the end are never counted in explicit mode.

Batching: `WindowIndex` and `QuoteUpdateIndex` build sorted arrays and prefix sums once; every
further window or cutoff is two binary searches (O(log n)) and no per-print work.
"""
from bisect import bisect_left, bisect_right
from collections import namedtuple
from fractions import Fraction

from .quotes import SCALE, STANDARD_MULTIPLIER, to_ticks

WindowPremium = namedtuple(
    "WindowPremium",
    "total_premium call_premium put_premium window_start_ns window_end_ns included_count excluded_nonstandard_count")
CountCoverage = namedtuple("CountCoverage", "status reason regular_update_count blocks")

_EMPTY = Fraction(0)


def _money(ticks):
    return Fraction(ticks * STANDARD_MULTIPLIER, SCALE)


def window_premium(prints, window_ns, window_end_ns=None):
    """prints: iterable of (t_ns, right, price, size, multiplier). Only multiplier 100 prints carry premium.

    A print with another multiplier is counted in excluded_nonstandard_count when it lies in the window.
    Legacy mode with no standard print has no anchor: zero premium, window bounds None.
    """
    if window_ns < 0:
        raise ValueError("window_ns must be >= 0")
    std = STANDARD_MULTIPLIER
    if window_end_ns is None:
        if not isinstance(prints, (list, tuple)):
            prints = list(prints)
        end = None
        for t, _, _, _, mult in prints:
            if mult == std and (end is None or t > end):
                end = t
        if end is None:
            return WindowPremium(_EMPTY, _EMPTY, _EMPTY, None, None, 0, sum(1 for p in prints if p[4] != std))
    else:
        end = window_end_ns
    start = end - window_ns
    tk = to_ticks
    call = put = included = excluded = 0
    for t, right, price, size, mult in prints:
        if start <= t <= end:
            if mult == std:
                included += 1
                if right == "call":
                    call += tk(price) * size
                else:
                    put += tk(price) * size
            else:
                excluded += 1
    return WindowPremium(_money(call + put), _money(call), _money(put), start, end, included, excluded)


class WindowIndex:
    """Prefix-sum index over prints for many windows on the same print set."""
    __slots__ = ("_t", "_call", "_put", "_bad")

    def __init__(self, prints):
        std = STANDARD_MULTIPLIER
        tk = to_ticks
        good, bad = [], []
        for t, right, price, size, mult in prints:
            if mult == std:
                v = tk(price) * size
                good.append((t, v, 0) if right == "call" else (t, 0, v))
            else:
                bad.append(t)
        good.sort(key=lambda r: r[0])
        self._t = [g[0] for g in good]
        call, put, c, p = [0], [0], 0, 0
        for _, vc, vp in good:
            c += vc
            p += vp
            call.append(c)
            put.append(p)
        self._call, self._put = call, put
        bad.sort()
        self._bad = bad

    def query(self, window_ns, window_end_ns=None):
        if window_ns < 0:
            raise ValueError("window_ns must be >= 0")
        times = self._t
        if window_end_ns is None:
            if not times:
                return WindowPremium(_EMPTY, _EMPTY, _EMPTY, None, None, 0, len(self._bad))
            end = times[-1]
        else:
            end = window_end_ns
        start = end - window_ns
        lo, hi = bisect_left(times, start), bisect_right(times, end)
        call = self._call[hi] - self._call[lo]
        put = self._put[hi] - self._put[lo]
        bad = self._bad
        return WindowPremium(_money(call + put), _money(call), _money(put), start, end, hi - lo,
                             bisect_right(bad, end) - bisect_left(bad, start))

    def query_many(self, window_ns, window_ends):
        query = self.query
        return [query(window_ns, e) for e in window_ends]


def _coverage(count, min_regular_updates):
    if count < min_regular_updates:
        return CountCoverage("unavailable", "low_quote_coverage", count, ("OC6",))
    return CountCoverage("available", None, count, ())


def quote_count_coverage(updates, t_eval_ns, window_ns, min_regular_updates):
    """G5: regular-condition updates with event time in [t_eval - window_ns, t_eval]; fewer than
    min_regular_updates gives unavailable `low_quote_coverage`, which blocks OC6 only (not OC5).

    updates: iterable of (t_ns, regular) with regular a bool (excluded-condition updates never count).
    """
    start = t_eval_ns - window_ns
    count = 0
    for t, regular in updates:
        if regular and start <= t <= t_eval_ns:
            count += 1
    return _coverage(count, min_regular_updates)


class QuoteUpdateIndex:
    """Sorted regular-update times for many cutoffs on the same update set."""
    __slots__ = ("_t",)

    def __init__(self, updates):
        self._t = sorted(t for t, regular in updates if regular)

    def coverage(self, t_eval_ns, window_ns, min_regular_updates):
        times = self._t
        count = bisect_right(times, t_eval_ns) - bisect_left(times, t_eval_ns - window_ns)
        return _coverage(count, min_regular_updates)

    def coverage_many(self, t_evals, window_ns, min_regular_updates):
        cover = self.coverage
        return [cover(t, window_ns, min_regular_updates) for t in t_evals]
