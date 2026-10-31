"""M3a history reads (story S02): `scalar_baseline` and `same_minute_column` over the M2 store (option_features.flowstore).

Pure and single-threaded; no I/O, no clocks; reads only: a read never changes a value and never builds a HistoryView,
a sorted copy or a merged array (M3A-B8 duty, R-79), and keeps no per-call memo (R-193: derived read state counts as
dropped on every call). It reads the ring's M3a layout (flowstore._Cols), kept in step with the ring at append, seal
and eviction (built once on the first read of a loaded ring): session-ordered columns of ids, totals, complete flags,
grid lengths and conventions, and one contiguous int64 block per minute series holding the grids themselves (no
second copy; R-193 items 4 and 1). A read is a bisect for `as_of`, bounds arithmetic and slices; the minute column is
one strided slice of the block.

Series (R-89, R-153, R-159): series_id "<UNDERLYING>/<lane>/<metric>", window_s 0. Scalar series (atm_iv_close,
iv30_close, skew25, skew25_fwd, term_30_91): empty grid, the value is the record `total` in 10^-8 units (R-48).
Minute series (atm_iv, iv30): dense grid on the session grid, the value at a minute index is the grid entry (an
implicit zero is the value 0). Retention per series via `HistoryStore.add_series(series_id, k)`, k up to 252 (R-114).

Selection (both forms): the stored, complete records of the series strictly before `as_of`, same lane (a series of
another lane is not read: insufficient_history, R-112); missing and incomplete days are skipped, n counts the sessions
used (R-51, owner decision 5); the LAST `max_sessions` available sessions are used (R-110); `same_minute_column` also
skips a session whose grid is shorter than minute + 1 (no zero-padding, R-43, R-113). n < min_sessions is unavailable
insufficient_history (the value then carries only n).

View-read structural codes (IO contract section 4, PR 112), first failing code reported. Positions 1 to 4 and the
value part of 5 are the shared S09 rule `m3a_validate.validate_view_read` (R-190: one rule for request and view read):
  1 session_not_in_calendar  `as_of` not a calendar session (a non-text as_of is malformed_type)
  2 minute_out_of_range      minute outside [0, minutes of the `as_of` session) (same_minute_column; a non-int minute
                             is malformed_type here, type-first)
  3 malformed_type           min_sessions or max_sessions not an int >= 1 (bool is not an int), then
    invalid_session_window   max_sessions < min_sessions (value code, after the type checks of the slot)
  4 threshold_out_of_range   `x` outside 0..100; `x` is a non-bool int, Fraction, or integer / "a/b" text; float,
                             Decimal, bool and other text are malformed_type here (R-190 item 3)
  5 convention_mismatch      skew-type series only (metric not convention-free, R-159): the request convention
                             differs from the metric's (`_fwd` = forward) or from a selected record's
                             `delta_convention` (absent = "spot"), R-160. Not supplied = "spot"; a supplied None, a
                             non-string or another string is malformed_type at this slot (R-190 items 1 and 2)
A series_id, metric or lane that is not exactly a str, or a window_s that is not exactly an int, is malformed_type
(exact types, as S09: a subclass could run caller code). min_sessions or max_sessions None means the default (20, 252).

Record returned (`HistoryRead`, plain slots, no hidden state): status in {available, unavailable, invalid_input},
reason (insufficient_history or None), code (structural or None), value:
  available:     {"values": tuple of ints (10^-8 units), "sessions": tuple of session ids ascending, "n": int}
  unavailable:   {"values": None, "sessions": None, "n": int}
  invalid_input: None
Memory formula helpers (budgets M3A-B8, rows M3A-H-046..049, 075): `grid_store_bytes`, `scalar_store_bytes`.
"""
from bisect import bisect_left

from .flowstore import _sparse
from .m3a_validate import validate_view_read

STORE_BUDGET_BYTES = 768 * 1024 * 1024       # M3A-B8 store budget (RULED), 805,306,368 B
STORE_HARD_BYTES = 1024 * 1024 * 1024        # M3A-B8 hard limit per worker, 1,073,741,824 B
CONVENTION_FREE = frozenset(("atm_iv", "atm_iv_close", "iv30", "iv30_close", "term_30_91"))   # R-159
_SCALAR = object()                           # `minute` marker of the scalar form


class HistoryRead:
    __slots__ = ("status", "reason", "code", "value")

    def __init__(self, status, reason, code, value):
        self.status, self.reason, self.code, self.value = status, reason, code, value

    def __repr__(self):
        return "HistoryRead(%s %s)" % (self.status, self.reason or self.code or "n=%d" % self.value["n"])


def _invalid(code):
    return HistoryRead("invalid_input", None, code, None)


_NOT_GIVEN = object()                        # `delta_convention` not supplied: "spot" (R-190 item 2)


def _checks(store, series_id, metric, window_s, as_of, min_sessions, max_sessions, x, minute, delta_convention):
    """Positions 1 to 5 except the record scan: the shared S09 rule (m3a_validate.validate_view_read, R-190), so
    request and view read cannot drift; plus a key that cannot be looked up (unhashable) is malformed_type."""
    # exact types (as S09): a str or int subclass could run caller code in hash or ==
    if type(series_id) is not str or type(metric) is not str or type(window_s) is not int:
        return "malformed_type"
    conv = "spot" if delta_convention is _NOT_GIVEN else delta_convention
    form = "scalar_baseline" if minute is _SCALAR else "same_minute_column"
    if minute is not _SCALAR and minute is None:
        minute = "missing"                   # a minute is required for this form: malformed_type at position 2
    try:
        return validate_view_read(store.calendar, as_of, form, min_sessions, max_sessions, x,
                                  None if minute is _SCALAR else minute,
                                  metric if isinstance(metric, str) and metric not in CONVENTION_FREE else None,
                                  conv)
    except (TypeError, ValueError, ArithmeticError):
        return "malformed_type"


def _conv_code(metric, delta_convention, convs):
    """Position 5, record scan (validate_view_read already checked the value and the metric's own convention):
    a selected record whose `delta_convention` (absent = "spot") differs from the request (R-160)."""
    if metric in CONVENTION_FREE:
        return None
    want = "spot" if delta_convention is _NOT_GIVEN else delta_convention
    ok = {None, "spot"} if want == "spot" else {want}
    return "convention_mismatch" if set(convs) - ok else None


def _select(store, series_id, metric, window_s, lane, as_of, mx, minute):
    """(record conventions, sessions, values) of the read, ascending, from the ring's M3a layout (flowstore._Cols):
    bounds arithmetic and slices when the window is all complete (and, for a minute, every grid is in the block and
    long enough); otherwise the window is selected index by index."""
    ring = store._rings.get((series_id, metric, window_s))
    if ring is None or ring.lane != lane:
        return (), (), ()
    c = ring.m3a
    if c is None:
        c = store.m3a_cols(series_id, metric, window_s)
    ids = c.ids
    cut = bisect_left(ids, as_of)                    # strictly before as_of: no look-ahead
    lo = cut - mx if cut > mx else 0
    done = c.done
    if minute is _SCALAR:
        if False not in done[lo:cut]:
            return (() if metric in CONVENTION_FREE else c.conv[lo:cut]), tuple(ids[lo:cut]), tuple(c.tot[lo:cut])
        pick = [i for i in range(cut) if done[i]]
        pick = pick[len(pick) - mx:] if len(pick) > mx else pick
        tot, conv = c.tot, c.conv
        return [conv[i] for i in pick], tuple([ids[i] for i in pick]), tuple([tot[i] for i in pick])
    if (cut > lo and c.mv is not None and False not in done[lo:cut] and False not in c.inb[lo:cut]
            and min(c.mins[lo:cut]) > minute):
        col = c.mv[minute::c.stride].tolist()        # one strided pass over the block: row r = slot r
        h = c.head
        if h:
            col = col[h:] + col[:h]                  # session order
        return c.conv[lo:cut], tuple(ids[lo:cut]), tuple(col[lo:cut])
    mins, recs = c.mins, c.recs
    pick = [i for i in range(cut) if done[i] and mins[i] > minute]   # short grids are skipped (R-43, R-113)
    pick = pick[len(pick) - mx:] if len(pick) > mx else pick
    conv = c.conv
    return ([conv[i] for i in pick], tuple([ids[i] for i in pick]),
            tuple([_probe(recs[i], minute) for i in pick]))


def _probe(r, minute):
    """Grid value at `minute` (< r.minutes) of one record; an index without a stored point is the value 0."""
    if r.vals is None:
        _sparse(r)
    idx = r.idx
    if len(idx) == r.minutes:
        return r.vals[minute]
    j = bisect_left(idx, minute)
    return r.vals[j] if j < len(idx) and idx[j] == minute else 0


def _read(store, series_id, metric, as_of, min_sessions, max_sessions, lane, delta_convention, x, window_s, minute):
    if min_sessions is None:                 # None = the default, as validate_view_read documents
        min_sessions = 20
    if max_sessions is None:
        max_sessions = 252
    if type(lane) is not str:
        return _invalid("malformed_type")
    code = _checks(store, series_id, metric, window_s, as_of, min_sessions, max_sessions, x, minute, delta_convention)
    if code is not None:
        return _invalid(code)
    convs, sessions, values = _select(store, series_id, metric, window_s, lane, as_of, max_sessions, minute)
    code = _conv_code(metric, delta_convention, convs)
    if code is not None:
        return _invalid(code)
    n = len(values)
    if n < min_sessions:
        return HistoryRead("unavailable", "insufficient_history", None, {"values": None, "sessions": None, "n": n})
    return HistoryRead("available", None, None, {"values": values, "sessions": sessions, "n": n})


def scalar_baseline(store, series_id, metric, as_of, min_sessions=20, max_sessions=252, lane="stock",
                    delta_convention=_NOT_GIVEN, x=None, window_s=0):
    """The last `max_sessions` available session values (record totals) of a scalar series before `as_of`."""
    return _read(store, series_id, metric, as_of, min_sessions, max_sessions, lane, delta_convention, x, window_s,
                 _SCALAR)


def same_minute_column(store, series_id, metric, as_of, minute, min_sessions=20, max_sessions=252, lane="stock",
                       delta_convention=_NOT_GIVEN, x=None, window_s=0):
    """The grid value at index `minute` of the last `max_sessions` available sessions of a minute series before
    `as_of`; sessions whose grid is shorter than minute + 1 are skipped."""
    return _read(store, series_id, metric, as_of, min_sessions, max_sessions, lane, delta_convention, x, window_s,
                 minute)


def grid_store_bytes(names, k, grid, copies):
    """Store formula of budgets M3A-B8 for minute grids: names x k x grid x 8 B, times the copies of the layout."""
    raw = names * k * grid * 8
    total = raw * copies
    return {"raw_bytes": raw, "total_bytes": total, "within_768MiB": total <= STORE_BUDGET_BYTES}


def scalar_store_bytes(names, series, k):
    """Scalar series formula: names x series x k records of 8 B."""
    records = names * series * k
    return {"records": records, "scalar_bytes": records * 8}
