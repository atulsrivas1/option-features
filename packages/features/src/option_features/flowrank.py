"""M2 percentile and baseline outputs: F2a/F2b/F2c (percentile rank against 20 sessions of history), F2d (average
percentile), F10 (window volume against the window baseline, median and mean ratio), F20 (session total against the
last 20 session totals), F19 (put-to-call ratio percentile).

Pure and single-threaded. Counts and sums are exact integers read from `flowstore.HistoryView` (two bisects on one
cached sorted array for a rank, an index for the median); `Fraction` is built only for the output values.
Decisions are exact: `upper_share <= X/100` is `ge * 100 <= X * n` on integers (a Fraction path only when X is not an
int), ratios against a statistic are `Fraction(x) / statistic`. No float anywhere, hence no float filter is needed.

Rules (docs/m2/M2_CAPABILITY_MATRIX.md, AMB and review rulings):
- Rank: `rank_le = count(history <= x) / n`, `upper_share = count(history >= x) / n`; today is never in the history;
  fires iff upper_share <= X/100 (inclusive), so a constant history cannot fire.
- History = the K calendar sessions right before today, all stored under the same series, metric, window and lane,
  all complete; otherwise `insufficient_history` (no substitution). Intraday values are the 60 s grid values of those
  sessions after dropping the first W/60 points of each (AMB-4); end-of-day values are the session totals.
- F2c: x is a print count; the output value is prints per minute (count / (W/60) intraday, total / session minutes
  end of day). Ranks are taken on counts (same divisor), so no rate arithmetic is needed intraday.
- Gate order: invalid_input (calendar, window, delayed tag), insufficient_history, session_not_complete,
  insufficient_window, zero_denominator.
- Delayed feed tag: intraday F2 and F10 give invalid_input `delayed_feed_tag`; the end-of-day F2 form is computed and
  labelled "delayed"; F19 and F20 are not gated.
"""
from bisect import bisect_left, bisect_right
from collections import namedtuple
from fractions import Fraction

from .flowresult import ALLOWED_WINDOWS, Result

NS = 1000000000

SessionInfo = namedtuple("SessionInfo", "session_id open_ns close_ns minutes complete feed_delay_tag total total_source")
SessionInfo.__new__.__defaults__ = (None, None)

_METRIC_OUT = {"premium": "F2a", "contracts": "F2b", "prints": "F2c"}
_F10_METRIC = "contracts"


def _fires(ge, n, X):
    """upper_share <= X/100 on integers."""
    if type(X) is int:
        return ge * 100 <= X * n
    return Fraction(ge, n) <= Fraction(X) / 100


def _struct(store, session, window_s, windowed, gated_delay):
    if session.session_id not in store.calendar:
        return "session_not_in_calendar"
    if windowed and window_s not in ALLOWED_WINDOWS:
        return "window_not_allowed"
    if gated_delay and session.feed_delay_tag == "delayed":
        return "delayed_feed_tag"
    return None


# ------------------------------------------------------------------ F2a, F2b, F2c
def f2_rank(store, series_id, metric, x, session, evaluation_ns, window_s=300, form="intraday", X=5, K=20,
            lane="stock", coverage=None):
    intraday = form == "intraday"
    params = {"X": X, "K": K, "form": form, "metric": metric, "window_s": window_s if intraday else None}
    code = _struct(store, session, window_s, intraday, intraday)
    if code:
        return Result.invalid("M2-2", code, series_id, session.session_id, evaluation_ns, params, lane)
    sid = session.session_id
    view = store.baseline(series_id, metric, window_s, sid, K, lane)
    if view is None or (intraday and view.n == 0):
        return Result.unavailable("M2-2", series_id, sid, evaluation_ns, "insufficient_history", params, lane=lane)
    if intraday:
        if evaluation_ns - session.open_ns < window_s * NS:
            return Result.unavailable("M2-2", series_id, sid, evaluation_ns, "insufficient_window", params, lane=lane)
        n, le, ge = view.rank(x)
        mins = window_s // 60
        x_out = Fraction(x, mins) if metric == "prints" else (x if type(x) is int else Fraction(x))
        label = None
    else:
        if not session.complete:
            return Result.unavailable("M2-2", series_id, sid, evaluation_ns, "session_not_complete", params, lane=lane)
        total = session.total
        n = len(view.totals)
        if metric == "prints":
            mx = session.minutes
            le = ge = 0
            for v, m in zip(view.totals, view.minutes):
                lhs, rhs = v * mx, total * m
                if lhs <= rhs:
                    le += 1
                if lhs >= rhs:
                    ge += 1
            x_out = Fraction(total, mx)
        else:
            srt = view.eod_sorted()
            le = bisect_right(srt, total)
            ge = n - bisect_left(srt, total)
            x_out = total
        coverage = None
        label = "delayed" if session.feed_delay_tag == "delayed" else None
    value = {"x": x_out, "n": n, "rank_le": Fraction(le, n), "upper_share": Fraction(ge, n), "form": form,
             "metric": metric}
    return Result.available("M2-2", series_id, sid, evaluation_ns, value, _fires(ge, n, X), params, coverage, label, lane)


def f2d_combine(a, b, c, window_s=300, X=5):
    """F2d from the F2a, F2b, F2c results (same series, session and evaluation). Percentile = 1 - upper_share, higher
    is more unusual; averaged exactly; `fired` is None in M2 (DR-M2-1); an unavailable part makes F2d unavailable with
    the reason of the first unavailable part, the parts still shown."""
    params = {"X": X, "window_s": window_s}
    for p in (a, b, c):
        if p.status == "invalid_input":
            return Result.invalid("M2-3", p.code, a.series_id, a.session_id, a.evaluation_ns, params, a.lane)
    shown, pcs, first = [], [], None
    for p in (a, b, c):
        if p.status == "available":
            pc = 1 - p.value["upper_share"]
            pcs.append(pc)
            shown.append({"status": "available", "reason": None, "percentile": pc})
        else:
            if first is None:
                first = p.reason
            shown.append({"status": "unavailable", "reason": p.reason, "percentile": None})
    if first is not None:
        return Result.unavailable("M2-3", a.series_id, a.session_id, a.evaluation_ns, first, params, lane=a.lane,
                                  parts_shown=shown)
    value = {"parts": pcs, "average": (pcs[0] + pcs[1] + pcs[2]) / 3, "direction": "higher_is_more_unusual"}
    return Result.available("M2-3", a.series_id, a.session_id, a.evaluation_ns, value, None, params, None, None, a.lane,
                            parts_shown=shown)


# ------------------------------------------------------------------ F10 and F20
def _stat_block(x, med, mean, N, default):
    """(per_statistic, default result tuple (status, reason, fired)) for statistics `med` and `mean` (Fractions)."""
    per = {}
    fired = {}
    for name, st in (("median", med), ("mean", mean)):
        if st == 0:
            per[name] = {"status": "unavailable", "reason": "zero_denominator", "ratio": None}
            fired[name] = None
        else:
            r = Fraction(x) / st
            per[name] = {"status": "available", "reason": None, "ratio": r}
            fired[name] = r >= N
    return per, fired[default]


def _na_stats(output_id, series_id, sid, ev, reason, params, default, lane):
    per = {k: {"status": "unavailable", "reason": reason, "ratio": None} for k in ("median", "mean")}
    return Result.unavailable(output_id, series_id, sid, ev, reason, params, None, default, lane, per_statistic=per)


def _finish_stats(output_id, series_id, sid, ev, x, med, mean, N, default, params, coverage, lane):
    per, fired = _stat_block(x, med, mean, N, default)
    if per[default]["status"] != "available":
        return Result.unavailable(output_id, series_id, sid, ev, "zero_denominator", params, coverage, default, lane,
                                  per_statistic=per)
    value = {"x": x, "median": med, "mean": mean, "per_statistic": per, "consumer_default": default}
    return Result.available(output_id, series_id, sid, ev, value, fired, params, coverage, default, lane)


def f10_baseline(store, series_id, x, session, evaluation_ns, window_s=300, N=2, K=20, consumer_default="median",
                 lane="stock", coverage=None):
    params = {"N": N, "K": K, "window_s": window_s, "consumer_default": consumer_default}
    code = _struct(store, session, window_s, True, True)
    if code:
        return Result.invalid("M2-7", code, series_id, session.session_id, evaluation_ns, params, lane)
    sid = session.session_id
    view = store.baseline(series_id, _F10_METRIC, window_s, sid, K, lane)
    if view is None or view.n == 0:
        return _na_stats("M2-7", series_id, sid, evaluation_ns, "insufficient_history", params, consumer_default, lane)
    if evaluation_ns - session.open_ns < window_s * NS:
        return _na_stats("M2-7", series_id, sid, evaluation_ns, "insufficient_window", params, consumer_default, lane)
    return _finish_stats("M2-7", series_id, sid, evaluation_ns, x, view.median(), view.mean(), N, consumer_default,
                         params, coverage, lane)


def f20_baseline(store, series_id, metric, session, evaluation_ns, window_s=300, N=2, K=20, consumer_default="mean",
                 lane="stock"):
    params = {"N": N, "K": K, "metric": metric, "consumer_default": consumer_default}
    code = _struct(store, session, window_s, False, False)
    if code:
        return Result.invalid("M2-8", code, series_id, session.session_id, evaluation_ns, params, lane)
    sid = session.session_id
    view = store.baseline(series_id, metric, window_s, sid, K, lane)
    if view is None:
        return _na_stats("M2-8", series_id, sid, evaluation_ns, "insufficient_history", params, consumer_default, lane)
    if not session.complete:
        return _na_stats("M2-8", series_id, sid, evaluation_ns, "session_not_complete", params, consumer_default, lane)
    srt = view.eod_sorted()
    n = len(srt)
    h = n // 2
    med = Fraction(srt[h]) if n % 2 else Fraction(srt[h - 1] + srt[h], 2)
    mean = Fraction(sum(srt), n)
    coverage = {"degraded": True} if session.total_source == "supplied_eod" else None
    return _finish_stats("M2-8", series_id, sid, evaluation_ns, session.total, med, mean, N, consumer_default, params,
                         coverage, lane)


# ------------------------------------------------------------------ F19
def f19_percentile(store, series_id, put, call, session, evaluation_ns, window_s=300, X=5, K=20, lane="stock"):
    params = {"X": X, "K": K}
    code = _struct(store, session, window_s, False, False)
    if code:
        return Result.invalid("M2-10", code, series_id, session.session_id, evaluation_ns, params, lane)
    sid = session.session_id
    pv = store.baseline(series_id, "put_volume", window_s, sid, K, lane)
    cv = store.baseline(series_id, "call_volume", window_s, sid, K, lane)
    if pv is None or cv is None or pv.sessions != cv.sessions:
        return Result.unavailable("M2-10", series_id, sid, evaluation_ns, "insufficient_history", params, lane=lane)
    ratios = [(p, c) for p, c in zip(pv.totals, cv.totals) if c > 0]
    if len(ratios) < K:
        return Result.unavailable("M2-10", series_id, sid, evaluation_ns, "insufficient_history", params, lane=lane)
    if not session.complete:
        return Result.unavailable("M2-10", series_id, sid, evaluation_ns, "session_not_complete", params, lane=lane)
    if call == 0:
        return Result.unavailable("M2-10", series_id, sid, evaluation_ns, "zero_denominator", params, lane=lane)
    le = ge = 0
    for p, c in ratios:
        lhs, rhs = put * c, p * call     # put/call <= p/c  <=>  put*c <= p*call (c, call > 0)
        if rhs <= lhs:
            le += 1
        if rhs >= lhs:
            ge += 1
    n = len(ratios)
    value = {"ratio": Fraction(put, call), "n": n, "rank_le": Fraction(le, n), "upper_share": Fraction(ge, n)}
    return Result.available("M2-10", series_id, sid, evaluation_ns, value, _fires(ge, n, X), params, lane=lane)


# ------------------------------------------------------------------ fused and batched forms
def flow_pack(store, series_id, session, evaluation_ns, window_s, premium, volume, count, X=5, N=2, K=20,
              consumer_default="median", lane="stock", coverage=None):
    """F2a, F2b, F2c, F2d and F10 for one series (a fused read: the contracts view serves F2b and F10, the three views
    are looked up once); equal to the separate calls."""
    a = f2_rank(store, series_id, "premium", premium, session, evaluation_ns, window_s, "intraday", X, K, lane, coverage)
    b = f2_rank(store, series_id, "contracts", volume, session, evaluation_ns, window_s, "intraday", X, K, lane, coverage)
    c = f2_rank(store, series_id, "prints", count, session, evaluation_ns, window_s, "intraday", X, K, lane, coverage)
    d = f2d_combine(a, b, c, window_s, X)
    e = f10_baseline(store, series_id, volume, session, evaluation_ns, window_s, N, K, consumer_default, lane, coverage)
    return a, b, c, d, e


def flow_pack_many(store, session, evaluation_ns, window_s, items, X=5, N=2, K=20, consumer_default="median",
                   lane="stock"):
    """`items`: iterable of (series_id, premium, volume, count, coverage). Same order out, equal to flow_pack each."""
    return [flow_pack(store, s, session, evaluation_ns, window_s, p, v, c, X, N, K, consumer_default, lane, cov)
            for s, p, v, c, cov in items]


def f2_rank_many(store, items, session, evaluation_ns, window_s=300, form="intraday", X=5, K=20, lane="stock"):
    """`items`: iterable of (series_id, metric, x, coverage)."""
    return [f2_rank(store, s, m, x, session, evaluation_ns, window_s, form, X, K, lane, cov) for s, m, x, cov in items]


def f10_baseline_many(store, items, session, evaluation_ns, window_s=300, N=2, K=20, consumer_default="median",
                      lane="stock"):
    """`items`: iterable of (series_id, x, coverage)."""
    return [f10_baseline(store, s, x, session, evaluation_ns, window_s, N, K, consumer_default, lane, cov)
            for s, x, cov in items]
