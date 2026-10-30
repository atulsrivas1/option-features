"""M3a history reads (story S02): `scalar_baseline` and `same_minute_column` over the M2 store (option_features.flowstore).

Pure and single-threaded; no I/O, no clocks; reads only: a read never changes a record and never builds a HistoryView,
a sorted copy or a merged array (M3A-B8 duty, R-79). History is read through the M2 store only, no second copy (build
plan 1.3); the selection (the complete records before `as_of`, with their session ids and value columns as tuples) is
cached on the ring like the M2 views, at most 4 per ring, and dropped by any append, seal or eviction of that ring
(correct by construction); a read then slices or indexes it.

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
A series_id, metric or window_s that cannot be looked up (unhashable) is malformed_type (totality).

Record returned (`HistoryRead`, plain slots, no hidden state): status in {available, unavailable, invalid_input},
reason (insufficient_history or None), code (structural or None), value:
  available:     {"values": tuple of ints (10^-8 units), "sessions": tuple of session ids ascending, "n": int}
  unavailable:   {"values": None, "sessions": None, "n": int}
  invalid_input: None
Memory formula helpers (budgets M3A-B8, rows M3A-H-046..049, 075): `grid_store_bytes`, `scalar_store_bytes`.
"""
from bisect import bisect_left

from .flowstore import _FULL_IDX, _sparse
from .m3a_validate import validate_view_read

STORE_BUDGET_BYTES = 768 * 1024 * 1024       # M3A-B8 store budget (RULED), 805,306,368 B
STORE_HARD_BYTES = 1024 * 1024 * 1024        # M3A-B8 hard limit per worker, 1,073,741,824 B
CONVENTION_FREE = frozenset(("atm_iv", "atm_iv_close", "iv30", "iv30_close", "term_30_91"))   # R-159
_CACHE = 4                                   # cached reads per ring (as the M2 view cache, flowstore._VIEW_CACHE)
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
    try:
        hash((series_id, metric, window_s))
    except TypeError:
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


def _conv_code(metric, delta_convention, recs):
    """Position 5, record scan (validate_view_read already checked the value and the metric's own convention):
    a selected record whose `delta_convention` (absent = "spot") differs from the request (R-160)."""
    if metric in CONVENTION_FREE:
        return None
    want = "spot" if delta_convention is _NOT_GIVEN else delta_convention
    for r in recs:
        if (r.conv or "spot") != want:
            return "convention_mismatch"
    return None


class _Base:
    """The complete records of one ring strictly before one `as_of`, ascending, with columns built on first use.
    Cached on the ring (cleared by any append, seal, eviction or drop_caches, as the M2 views), so the 78 cutoffs of
    a session select once and each later read (another minute, another max_sessions) only slices or indexes.
    Built to touch as few objects as possible (a cold read is memory-bound): session ids come from the ring keys
    when every record is complete, and a grid is known to hold every point when its index array is the store's
    shared full index (flowstore._full_idx), so no per-record length or minutes object is read."""
    __slots__ = ("recs", "sids", "totals", "vals", "low", "full")

    def __init__(self, recs, sids):
        self.recs, self.sids = recs, sids
        self.totals = self.vals = None
        self.low = 0
        self.full = False

    def grid_columns(self):
        recs = self.recs
        vals = [r.vals for r in recs]
        if not all(vals):           # a lazily loaded record (vals None; an empty array is also falsy): parse once
            for r in recs:
                if r.vals is None:
                    _sparse(r)
            vals = [r.vals for r in recs]
        self.vals = tuple(vals)
        shared = {id(a): len(a) for a in _FULL_IDX.values()}
        ids = set(map(id, [r.idx for r in recs]))
        self.full = ids.issubset(shared)
        self.low = min([shared[i] for i in ids]) if self.full and ids else 0


def _base(store, series_id, metric, window_s, lane, as_of):
    ring = store._rings.get((series_id, metric, window_s))
    if ring is None or ring.lane != lane:
        return None
    views = ring.views
    key = ("m3a", as_of)
    got = views.get(key)
    if got is None:
        recs = ring.recs
        rl = list(recs.values())
        cut = len(rl)
        if rl and rl[-1].session_id >= as_of:                 # strictly before as_of: no look-ahead
            cut = bisect_left(list(recs), as_of)              # ids ascend (the append order is checked)
            rl = rl[:cut]
        sel = [r for r in rl if r.complete]
        if len(sel) == len(recs):
            sids = tuple(recs)
        else:
            sids = tuple([r.session_id for r in sel])
        got = _Base(tuple(sel), sids)
        if len(views) >= _CACHE:
            del views[next(iter(views))]
        views[key] = got
    return got


def _select(store, series_id, metric, window_s, lane, as_of, max_sessions, minute):
    """(records, sessions, values) of the read, ascending."""
    b = _base(store, series_id, metric, window_s, lane, as_of)
    if b is None:
        return (), (), ()
    recs = b.recs
    cut = len(recs) - max_sessions if len(recs) > max_sessions else 0
    if minute is _SCALAR:
        if b.totals is None:
            b.totals = tuple([r.total for r in recs])
        return recs[cut:], b.sids[cut:], b.totals[cut:]
    if b.vals is None:
        b.grid_columns()
    if b.full and minute < b.low:                             # every session has the minute: slice, then index
        return recs[cut:], b.sids[cut:], tuple([v[minute] for v in b.vals[cut:]])
    pick = [i for i, r in enumerate(recs) if r.minutes > minute]   # short grids are skipped (R-43, R-113)
    if len(pick) > max_sessions:
        pick = pick[len(pick) - max_sessions:]
    sids = b.sids
    return (tuple([recs[i] for i in pick]), tuple([sids[i] for i in pick]),
            tuple([_probe(recs[i], minute) for i in pick]))


def _probe(r, minute):
    """Grid value at `minute` (< r.minutes) of a parsed record; an index without a stored point is the value 0."""
    idx = r.idx
    if len(idx) == r.minutes:
        return r.vals[minute]
    j = bisect_left(idx, minute)
    return r.vals[j] if j < len(idx) and idx[j] == minute else 0


def _read(store, series_id, metric, as_of, min_sessions, max_sessions, lane, delta_convention, x, window_s, minute):
    code = _checks(store, series_id, metric, window_s, as_of, min_sessions, max_sessions, x, minute, delta_convention)
    if code is not None:
        return _invalid(code)
    recs, sessions, values = _select(store, series_id, metric, window_s, lane, as_of, max_sessions, minute)
    code = _conv_code(metric, delta_convention, recs)
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
