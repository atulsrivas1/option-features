"""M3a history rank outputs (story S08): M3A-1 (V1), M3A-2 (V3, both `iv_form` forms) and M3A-8 (V9, both
`delta_convention` forms).

Pure and single-threaded: no I/O, no clocks, no solver, no hidden state. The history is read ONLY through the S02 read
forms (`m3a_history.scalar_baseline` for V1 and V9, `m3a_history.same_minute_column` for V3); never through a
`HistoryView`, a sorted copy or a merged array (S02b decision item 7). A read is used only after its status is checked
(R-192): an unavailable read has `values` None and is reported as `insufficient_history`; an invalid_input read is
reported as its code.

Calls (each returns an `m3a_common.Result`; they never raise on caller data):
  rank_v1(store, underlying, session, evaluation_ns, now, params=None, upstream_reason=None, labels=("exact-model",),
          cutoff_ns=None)                                   -> M3A-1, series "<U>/<lane>/iv30_close" (scalar)
  rank_v3(store, underlying, session, evaluation_ns, now, params=None, ...)
                                                            -> M3A-2, series atm_iv (iv_form "atm", default) or iv30
                                                               ("30d"), minute series at `params["minute"]`
  rank_v9(store, underlying, session, evaluation_ns, put25_iv, call25_iv, params=None, ...)
                                                            -> M3A-8, series skew25 (delta_convention "spot", default)
                                                               or skew25_fwd ("forward")
`session` is any object with `session_id`, `complete` and `feed_delay_tag` (the M2 `SessionInfo`). `now` is the current
value as a binary64 float (V1: the 30-day IV; V3: the IV of the selected form at the minute); V9 takes the two unrounded
25-delta IVs and ranks their EXACT binary64 difference rounded once, half to even, to 10^-8 (R-48, R-189; the rule of the
S10 builder, so the current value and the stored history are the same quantity). `upstream_reason` (a closed-set reason
such as `no_bracketing_expiry`) says the upstream frame value is unavailable; `now` is then not read. `params` is the
request dict: mode ("intraday" default, "close"), lane ("stock" default), feed_delay_tag (overrides the session's), x
(percentile, default 5: a non-bool int, a Fraction, or integer / "a/b" text), tail ("top" default, "bottom"; V1 and V9),
min_sessions (20), max_sessions (252), minute (V3), iv_form (V3), delta_convention (V9). The input `params` is never
changed.

Rules (M2 rank and Q2 tie rules; docs/m3a/M3A_RULING_LIST.md R-42..R-58, R-110..R-114, R-131 item 7, R-143, R-195):
  * history = the last `max_sessions` available sessions strictly before the session (complete, same lane, and for V3 a
    non-zero value at the minute: a stored 0 in a minute series is a hole and is never ranked);
  * rank_le = count(history <= x), ge = count(history >= x); ties count in both; upper_share = ge / n and
    lower_share = rank_le / n (exact, reduced "a/b" or an int); top X fires when upper_share <= X/100, bottom X when
    lower_share <= X/100, on integers; V3 is top only and has no lower_share;
  * a constant history is unavailable `zero_range_history` (R-46: deliberate exception to M2 Q2);
  * V1 and V9 under mode "close" need a sealed session (`session_not_complete`) and, under a delayed tag, are computed and
    labelled "delayed"; intraday V1, V9 and V3 under a delayed tag are invalid_input `delayed_feed_tag` (R-58).
  * a current V3 value of 0 at the minute is unavailable and is never ranked: reason `no_atm_strike` (form atm) or
    `no_bracketing_expiry` (form 30d), the reasons of the upstream frame value that a 0 grid point stands for.

Order of the codes (IO contract section 4; decision file item 3): bad_cutoff / malformed_type of the cutoff, then request
position 4 (mode; V3 is intraday only), 5 (lane), `session_not_in_calendar` (view read position 1), position 10 (types in
the order evaluation_ns, feed_delay_tag, tail, min_sessions, max_sessions, upstream_reason, the current values, then
`cutoff_mismatch`), `invalid_session_window` (view read position 3), position 13 (iv_form, delta_convention), 15 (x), 16
(minute), 17 (a stored record of the other convention, found by the read: `convention_mismatch`), 18
(`delayed_feed_tag`). Structural codes come before any evaluation (R-131). Among result reasons the order is: upstream and
current-zero, `insufficient_history`, `session_not_complete`, `zero_range_history`.

Value (key order of the contract; `iv_form` and `delta_convention` live in `params` only, R-184):
  V1, V9: x (8-decimal text), n, rank_le, upper_share, lower_share, form ("intraday" | "end_of_day")
  V3:     x, n, minute, rank_le, upper_share
`params` echo (keys sorted, defaults filled): V1 max_sessions, min_sessions, mode, tail, x; V3 iv_form, max_sessions,
min_sessions, minute, mode, x; V9 delta_convention, max_sessions, min_sessions, mode, tail, x. An invalid_input result
carries no params. `labels` is the given model label(s) plus "delayed", sorted (R-132); unavailable and invalid results
have labels [].

Performance (M3A-B5, B5n): one read, then two C-level passes over at most 252 ints (`sum(map(operator.lt, values,
repeat(x)))` for count(< x) and `values.count(x)` for the ties) give rank_le, ge and, in the rare constant case, the
zero-range test (a third `count` only when every value lies on one side of x); a sort is about twice as slow on varying
data (branch mispredictions). Structural checks use exact-type tests on the hot path; no per-call memo.
"""
from itertools import repeat
from math import gcd
from operator import lt as _lt

from .m3a_common import SURFACE_REASONS, Result, round_units, units_text
from .m3a_history import same_minute_column, scalar_baseline
from .m3a_validate import x_value
from .surface_series import _diff_units

V1, V3, V9 = 0, 1, 2
_OID = ("M3A-1", "M3A-2", "M3A-8")
_MODES = frozenset(("intraday", "close"))
_LANES = frozenset(("stock", "etf_index"))
_TAGS = frozenset(("live", "delayed"))
_TAILS = frozenset(("top", "bottom"))
_FORMS = {"atm": "atm_iv", "30d": "iv30"}
_ZERO_REASON = {"atm": "no_atm_strike", "30d": "no_bracketing_expiry"}       # the upstream reasons a 0 grid point stands for
_CONVS = {"spot": "skew25", "forward": "skew25_fwd"}
_REASONS = frozenset(SURFACE_REASONS)
_NOPARAMS = {}
_MT = "malformed_type"


def _share(a, n):
    """Reduced "a/b", or the int 0 or 1 (a <= n), the same as m3a_common.ratio_text."""
    if a == 0:
        return 0
    if a == n:
        return 1
    g = gcd(a, n)
    return "%d/%d" % (a // g, n // g)


def _invalid(kind, code, underlying, p, sid, ev):
    """invalid_input result: the series of the requested lane and form when they are valid, else the defaults."""
    lane, metric = "stock", ("iv30_close", "atm_iv", "skew25")[kind]
    if type(p) is dict:
        ln = p.get("lane")
        if type(ln) is str and ln in _LANES:
            lane = ln
        if kind != V1:
            sel = p.get("iv_form") if kind == V3 else p.get("delta_convention")
            if type(sel) is str:
                metric = (_FORMS if kind == V3 else _CONVS).get(sel, metric)
    series = "%s/%s/%s" % (underlying, lane, metric) if type(underlying) is str else None
    return Result.invalid(_OID[kind], code, series, sid if type(sid) is str else None, ev if type(ev) is int else None,
                          None, lane)


def _run(kind, store, underlying, session, ev, params, upstream, labels, cutoff_ns, now, put, call):
    try:
        sid, complete, tag = session.session_id, session.complete, session.feed_delay_tag
    except Exception:
        sid = complete = tag = None
    p = _NOPARAMS if params is None else params
    code = None
    try:
        while True:                                 # one pass: `code` is the first structural code, `break` on it
            if cutoff_ns is None:
                cut = ev
            elif type(cutoff_ns) is int:
                cut = cutoff_ns
            else:
                code = _MT
                break
            if type(cut) is not int:
                code = _MT
                break
            if cut < 0:
                code = "bad_cutoff"
                break
            if type(p) is not dict:                 # wrong-typed params: reported at position 10 (after 4, 5, calendar)
                pbad, p = True, _NOPARAMS
            else:
                pbad = False
            get = p.get
            mode = get("mode", "intraday")          # position 4
            if type(mode) is not str:
                code = _MT
                break
            if mode not in _MODES or (kind == V3 and mode != "intraday"):
                code = "invalid_mode"
                break
            lane = get("lane", "stock")             # position 5
            if type(lane) is not str:
                code = _MT
                break
            if lane not in _LANES:
                code = "invalid_lane"
                break
            if type(underlying) is not str or not underlying or "/" in underlying or type(sid) is not str:
                code = _MT                          # the symbol must be a series-id part (as S10 `series_id`)
                break
            cal = store.calendar
            pos = cal.position(sid)                 # view read position 1
            if pos is None:
                code = "session_not_in_calendar"
                break
            if pbad or type(ev) is not int:         # position 10: types, in the order of the module docstring
                code = _MT
                break
            if "feed_delay_tag" in p:
                tag = p["feed_delay_tag"]
            if type(tag) is not str or tag not in _TAGS:
                code = _MT
                break
            tail = get("tail")
            if tail is not None and (type(tail) is not str or tail not in _TAILS):
                code = _MT
                break
            mn = get("min_sessions")
            if mn is None:
                mn = 20
            elif type(mn) is not int or mn < 1:
                code = _MT
                break
            mx = get("max_sessions")
            if mx is None:
                mx = 252
            elif type(mx) is not int or mx < 1:
                code = _MT
                break
            if upstream is not None:
                if type(upstream) is not str or upstream not in _REASONS:
                    code = _MT
                    break
            elif kind == V9:
                tp, tc = type(put), type(call)
                if ((tp is not float and tp is not int) or (tc is not float and tc is not int)
                        or (tp is float and put - put != 0.0) or (tc is float and call - call != 0.0)):
                    code = _MT
                    break
            else:
                tn = type(now)
                if (tn is not float and tn is not int) or (tn is float and now - now != 0.0):
                    code = _MT
                    break
            if type(labels) is not tuple:
                if type(labels) is str:
                    labels = (labels,)
                elif labels is None:
                    labels = ()
                else:
                    labels = tuple(labels)          # a non-iterable raises TypeError: malformed_type below
            for lb in labels:
                if type(lb) is not str:
                    code = _MT
                    break
            if code is not None:
                break
            if ev != cut:
                code = "cutoff_mismatch"
                break
            if mx < mn:
                code = "invalid_session_window"
                break
            if kind == V3:                          # position 13
                form = get("iv_form", "atm")
                if type(form) is not str:
                    code = _MT
                    break
                metric = _FORMS.get(form)
                if metric is None:
                    code = "iv_form_not_allowed"
                    break
            elif kind == V9:
                conv = get("delta_convention", "spot")
                if type(conv) is not str:
                    code = _MT
                    break
                metric = _CONVS.get(conv)
                if metric is None:
                    code = "convention_not_allowed"
                    break
            else:
                metric = "iv30_close"
            x = get("x")                            # position 15
            if x is None:
                x = xv = 5
            elif type(x) is int:
                xv = x
                if xv < 0 or xv > 100:
                    code = "threshold_out_of_range"
                    break
            else:
                xv = x_value(x)                     # int, Fraction, or None; "1/0" raises ZeroDivisionError
                if xv is None:
                    code = _MT
                    break
                if xv < 0 or xv > 100:
                    code = "threshold_out_of_range"
                    break
                x = xv.numerator if xv.denominator == 1 else "%d/%d" % (xv.numerator, xv.denominator)
            if kind == V3:                          # position 16
                minute = get("minute")
                if type(minute) is not int:
                    code = _MT
                    break
                if minute < 0 or minute >= cal.minutes[pos]:
                    code = "minute_out_of_range"
                    break
            break
    except Exception:                               # TypeError, ArithmeticError and any hostile object: never raise
        code = _MT
    if code is not None:
        return _invalid(kind, code, underlying, params, sid, ev)
    series = "%s/%s/%s" % (underlying, lane, metric)
    if kind == V3:
        res = same_minute_column(store, series, metric, sid, minute, mn, mx, lane)
    elif kind == V9:
        res = scalar_baseline(store, series, metric, sid, mn, mx, lane, conv)
    else:
        res = scalar_baseline(store, series, metric, sid, mn, mx, lane)
    status = res.status
    oid = _OID[kind]
    if status == "invalid_input":                   # position 17 (a record of the other convention) or a read code
        return Result.invalid(oid, res.code, series, sid, ev, None, lane)
    if tag == "delayed" and (kind == V3 or mode == "intraday"):         # position 18
        return Result.invalid(oid, "delayed_feed_tag", series, sid, ev, None, lane)
    tail = tail or "top"
    if kind == V3:
        params_out = {"iv_form": form, "max_sessions": mx, "min_sessions": mn, "minute": minute, "mode": mode, "x": x}
    elif kind == V9:
        params_out = {"delta_convention": conv, "max_sessions": mx, "min_sessions": mn, "mode": mode, "tail": tail,
                      "x": x}
    else:
        params_out = {"max_sessions": mx, "min_sessions": mn, "mode": mode, "tail": tail, "x": x}
    if upstream is not None:
        return Result.unavailable(oid, series, sid, ev, upstream, params_out, None, lane)
    xu = _diff_units(put, call) if kind == V9 else round_units(now)
    if kind == V3 and xu == 0:                      # a 0 at the minute is a hole: never ranked (S02b item 7)
        return Result.unavailable(oid, series, sid, ev, _ZERO_REASON[form], params_out, None, lane)
    if status != "available":                       # R-192: values are None on an unavailable read
        return Result.unavailable(oid, series, sid, ev, "insufficient_history", params_out, None, lane)
    if mode == "close" and not complete:
        return Result.unavailable(oid, series, sid, ev, "session_not_complete", params_out, None, lane)
    vals = res.value["values"]
    n = len(vals)
    below = sum(map(_lt, vals, repeat(xu)))         # count(history < x): one C-level pass, no sort
    eq = vals.count(xu)
    if eq == n or ((below == 0 or below == n) and vals.count(vals[0]) == n):
        return Result.unavailable(oid, series, sid, ev, "zero_range_history", params_out, None, lane)
    le = below + eq
    ge = n - below
    if type(xv) is int:
        xn, xd = xv, 1
    else:
        xn, xd = xv.numerator, xv.denominator
    if kind == V3:
        value = {"x": units_text(xu), "n": n, "minute": minute, "rank_le": le, "upper_share": _share(ge, n)}
        fired = ge * 100 * xd <= xn * n
    else:
        value = {"x": units_text(xu), "n": n, "rank_le": le, "upper_share": _share(ge, n), "lower_share": _share(le, n),
                 "form": "intraday" if mode == "intraday" else "end_of_day"}
        fired = (le if tail == "bottom" else ge) * 100 * xd <= xn * n
    if tag == "delayed":
        labels = labels + ("delayed",)
    return Result.available(oid, series, sid, ev, value, fired, params_out, None, labels, lane)


def rank_v1(store, underlying, session, evaluation_ns, now, params=None, upstream_reason=None,
            labels=("exact-model",), cutoff_ns=None):
    """M3A-1: rank of the 30-day IV `now` against the iv30_close scalar history (see the module docstring)."""
    return _run(V1, store, underlying, session, evaluation_ns, params, upstream_reason, labels, cutoff_ns, now, None,
                None)


def rank_v3(store, underlying, session, evaluation_ns, now, params=None, upstream_reason=None,
            labels=("exact-model",), cutoff_ns=None):
    """M3A-2: rank of the IV `now` (form atm or 30d) against the same grid minute of the prior sessions."""
    return _run(V3, store, underlying, session, evaluation_ns, params, upstream_reason, labels, cutoff_ns, now, None,
                None)


def rank_v9(store, underlying, session, evaluation_ns, put25_iv, call25_iv, params=None, upstream_reason=None,
            labels=("exact-model",), cutoff_ns=None):
    """M3A-8: rank of the 25-delta skew (put minus call, exact difference rounded once) against the skew history of the
    requested delta convention."""
    return _run(V9, store, underlying, session, evaluation_ns, params, upstream_reason, labels, cutoff_ns, None,
                put25_iv, call25_iv)
