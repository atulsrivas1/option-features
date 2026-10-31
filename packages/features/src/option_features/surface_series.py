"""M3a story S10: series builder M3A-12 (R-48, R-153, R-189).

Pure and single-threaded: no I/O, clocks or shared state; never raises on caller data (unusable values are
treated as unavailable and give no stored value). It never solves IV and never parses frame text: it reads the
unrounded binary64 values S05 exposes in `stats["floats"]` (R-189):
    {"expiries": {"<days>": {"atm_iv", "put25_iv", "call25_iv"}}, "tenors": {"<t>": float | None}}

Calls
    series_id(underlying, lane, metric)               -> "<UNDERLYING>/<lane>/<metric>"
    scalar_units(floats, floats_fwd=None)             -> {metric: int} (10^-8 units); an unavailable metric is
        absent. atm_iv_close = ATM IV of the nearest eligible expiry (lowest days with a usable atm_iv);
        skew25 = put25 - call25 of that expiry (spot-convention frame); skew25_fwd the same on `floats_fwd`;
        iv30_close = tenor 30; term_30_91 = tenor 30 - tenor 91. A difference is the EXACT binary64 difference
        rounded ONCE, half to even (integer arithmetic on as_integer_ratio, no Fraction); a single value is rounded once.
    grid_units(values)                                -> [int]: one entry per minute; None or an unusable value
        gives 0 (the M2 dense zero-fill convention; the store keeps non-zero entries only)
    build_records(underlying, lane, session_id, close_floats, close_floats_fwd=None, minute_floats=None)
        (or `minute_columns=(atm_iv_floats, iv30_floats)` already extracted, skipping the per-minute dict reads)
        -> [(series_id, metric, window_s, session_id, grid, total)] in the order atm_iv, iv30 (minute grids,
        window_s 0, total the grid sum), atm_iv_close, iv30_close, skew25, skew25_fwd, term_30_91 (scalars: grid
        [], total the integer). `minute_floats` is a list of per-minute stats["floats"] (None for a missing
        minute). A series without a value gets no record.
    append_records(store, records, lane="stock")      -> AppendResult (a (count, code) tuple with .committed, .code,
        .partial): validates the WHOLE batch first (record shape, lane, calendar, grid length, grid and total types, session
        order and duplicates against the store's retained sessions and earlier records of the batch) and appends
        nothing when a record fails (count 0, the structural code); declares add_series(series_id, 252) for every
        series id not already at 252 or more, then store.append(series_id, metric, window_s, session_id, grid,
        total=total, lane=lane, delta_convention=...): "spot" for skew25, "forward" for skew25_fwd, None otherwise
        (R-160). A store error that validation could not see (for example a ring of another lane) stops the batch:
        count is the number of records already committed (partial is True when it is above 0) and code the
        exception's `code` or text. Nothing is rolled back and a retry after a partial commit meets
        duplicate_session: the S11 runner builds a fresh store per run.

Never raises on caller data: any Exception raised while reading caller objects (dict access, iteration) makes the
value unavailable. Performance: one pass per series; grids are rounded in C-level passes (scale, floor, fraction
check); only entries within the guard band of a rounding boundary (see `grid_units`), and hostile or large values,
take the exact integer path.
"""
from math import floor
from operator import sub

from .m3a_common import round_units

_SCALE = 10 ** 8
_FSCALE = 1e8
_FLOAT_ONLY = {float}
_BIG = 2.0 ** 16            # the fast path needs |v| < 2^16, so v * 1e8 < 2^43 (see grid_units)
_ERR = 2.0 ** -50           # four times the relative error of the two float operations (2 * 2^-53 -> 2^-52)
_CONV = {"skew25": "spot", "skew25_fwd": "forward"}     # delta_convention of the stored record (R-160)
_K = 252                    # retention declared per series id (R-114)
_FIELDS = ("atm_iv", "iv30", "atm_iv_close", "iv30_close", "skew25", "skew25_fwd", "term_30_91")


def series_id(underlying, lane, metric):
    return "%s/%s/%s" % (underlying, lane, metric)


def _ok(x):
    """A usable value: a float (not bool) that is finite."""
    return type(x) is float and x - x == 0.0


def _diff_units(a, b):
    """round_half_even((a - b) * 10^8) of the exact binary64 difference, as an int."""
    na, da = a.as_integer_ratio()
    nb, db = b.as_integer_ratio()
    q, r = divmod((na * db - nb * da) * _SCALE, da * db)
    d = da * db
    r2 = r + r
    if r2 > d or (r2 == d and q & 1):
        q += 1
    return q


def _nearest(floats):
    """(days, item) of the nearest eligible expiry (lowest days with a usable atm_iv), else None."""
    best = None
    bd = None
    for k, it in floats["expiries"].items():
        try:
            a = it["atm_iv"]
            if a.__class__ is float and a - a == 0.0:
                d = int(k)
                if bd is None or d < bd:
                    bd, best = d, it
        except Exception:
            continue
    return best


def _tenor(floats, key):
    v = floats["tenors"].get(key)
    return v if _ok(v) else None


def _scalars(floats, out, fwd):
    try:
        it = _nearest(floats)
    except Exception:
        it = None
    if it is not None:
        if not fwd:
            out["atm_iv_close"] = round_units(it["atm_iv"])
        p, c = it.get("put25_iv"), it.get("call25_iv")
        if _ok(p) and _ok(c):
            out["skew25_fwd" if fwd else "skew25"] = _diff_units(p, c)
    if not fwd:
        try:
            t30 = _tenor(floats, "30")
            t91 = _tenor(floats, "91")
        except Exception:
            return
        if t30 is not None:
            out["iv30_close"] = round_units(t30)
            if t91 is not None:
                out["term_30_91"] = _diff_units(t30, t91)


def scalar_units(floats, floats_fwd=None):
    out = {}
    try:
        _scalars(floats, out, False)
    except Exception:                           # caller data: unusable means unavailable, never an exception
        pass
    if floats_fwd is not None:
        try:
            _scalars(floats_fwd, out, True)
        except Exception:
            pass
    return out


def _slow_grid(values):
    return [round_units(v) if _ok(v) else 0 for v in values]


def _window(mx, mn):
    """Half-width of the guard band for values in [mn, mx]: (max|v| * 1e8 + 1) * 2^-50."""
    m = mx if mx > -mn else -mn
    return (m * _FSCALE + 1.0) * _ERR


def grid_units(values):
    """Exact half-even rounding to 10^-8 units of every entry (see the module docstring).

    Fast path (floats with |v| < 2^16). Let t = v * 10^8 (real), W = (max|v| * 1e8 + 1) * 2^-50 (`_window`), c the
    float 0.5 + W, ws = c - 0.5 (exact, about W), u = fl(fl(v * 1e8) + c), rs = floor(u), d = u - rs (exact).
    Each float operation errs by at most 2^-53 relative and 1e8 is exact, so e = u - (t + c) has |e| <= (|t| + 1) *
    2^-52 <= W / 4. The exact answer for a non-tie is floor(t + 1/2) = floor(X - ws) with X = t + c. If d >= 2W, no
    integer lies in (X - ws, X + e] (it would have to be within ws + e < 2W below X + e), so rs = floor(t + 1/2); and
    t + 1/2 is not an integer there (that would put d at ws + e < 2W), so there is no tie and round-half-up equals
    half-even. Every entry with d < 2W (this includes every tie, where d = ws + e) is rounded exactly instead
    (round_units). The result therefore equals exact half-even rounding of every entry (tests: GuardBand,
    Differential). Anything else (non-float, non-finite, |v| >= 2^16) takes the exact integer path."""
    if type(values) is not list:
        try:
            values = list(values)
        except Exception:                       # caller data: an iterable that raises is no values
            return []
    if not values:
        return []
    if not set(map(type, values)) <= _FLOAT_ONLY:
        return _slow_grid(values)
    try:
        mx = max(values)
        mn = min(values)
        if mx >= _BIG or mn <= -_BIG:
            return _slow_grid(values)
        w = _window(mx, mn)
        c = 0.5 + w
        u = [v * 1e8 + c for v in values]       # 1e8 == _FSCALE, a constant in the loop
        rs = list(map(floor, u))                # nan or inf raise here and take the exact path
        lim = w + w
        if min(map(sub, u, rs)) < lim:          # d = u - rs, exact; the list is built only if a fix is needed
            for i in [i for i, x in enumerate(map(sub, u, rs)) if x < lim]:
                rs[i] = round_units(values[i])
        return rs
    except (TypeError, ValueError, OverflowError):
        return _slow_grid(values)


def minute_values_from_floats(f):
    """The minute value rule (R-191): one per-minute stats["floats"] -> (atm_iv, iv30). atm_iv is the ATM IV of the
    nearest eligible expiry (lowest days with a finite float atm_iv); iv30 is tenor "30". A missing or unusable
    value is None. Never raises. S11 calls this once per minute in its G0 loop and passes the two columns."""
    try:
        it = _nearest(f)
        a = None if it is None else it["atm_iv"]
    except Exception:
        a = None
    try:
        t = f["tenors"].get("30")
        t = t if _ok(t) else None
    except Exception:
        t = None
    return a, t


def _minute_pair(minute_floats):
    """(atm_iv values, iv30 values) per minute, through minute_values_from_floats."""
    atm, iv30 = [], []
    for f in minute_floats:
        a, t = minute_values_from_floats(f)
        atm.append(a)
        iv30.append(t)
    return atm, iv30


def build_records(underlying, lane, session_id, close_floats, close_floats_fwd=None, minute_floats=None,
                  minute_columns=None):
    if type(underlying) is not str or type(lane) is not str:
        return []
    out = []
    pre = "%s/%s/" % (underlying, lane)
    cols = None
    if type(minute_columns) is tuple and len(minute_columns) == 2:
        cols = minute_columns                   # pre-extracted (atm_iv floats, iv30 floats), one per minute
    elif type(minute_floats) is list and minute_floats:
        cols = _minute_pair(minute_floats)
    if cols is not None:
        for metric, col in (("atm_iv", cols[0]), ("iv30", cols[1])):
            grid = grid_units(col)
            out.append((pre + metric, metric, 0, session_id, grid, sum(grid)))
    sc = scalar_units(close_floats, close_floats_fwd)
    for metric in _FIELDS[2:]:
        v = sc.get(metric)
        if v is not None:
            out.append((pre + metric, metric, 0, session_id, [], v))
    return out


class AppendResult(tuple):
    """(committed, code). code is None on success; otherwise the batch stopped: `committed` records were already
    stored (0 when the batch was rejected by validation, which appends nothing)."""
    __slots__ = ()

    def __new__(cls, committed, code):
        return tuple.__new__(cls, (committed, code))

    committed = property(lambda self: self[0])
    code = property(lambda self: self[1])
    partial = property(lambda self: self[1] is not None and self[0] > 0)


_SEQ = (list, tuple)


def _validate(store, recs, lane):
    """The first failing record's structural code (the order of HistoryStore.append: lane, calendar, length, order,
    then types), or None. Public store APIs only: `calendar`, `strict_calendar`, `m3a_cols` (retained sessions). A ring
    of another lane is not visible through them: the store raises lane_mismatch for it during the append."""
    if type(lane) is not str:
        return "malformed_type"
    cal = getattr(store, "calendar", None)
    strict = getattr(store, "strict_calendar", True)
    cols_of = getattr(store, "m3a_cols", None)
    infix = "/" + lane + "/"
    last = {}                                   # (series, metric, window) -> last session seen in this batch
    for r in recs:
        try:
            sid, metric, window_s, session, grid, total = r
        except (TypeError, ValueError):
            return "malformed_type"
        if type(sid) is not str or type(metric) is not str:
            return "malformed_type"
        if infix not in sid and sid.count("/") >= 2:      # "<UNDERLYING>/<lane>/<metric>" of another lane
            return "lane_mismatch"
        bad_type = type(grid) not in _SEQ or type(total) is not int      # the store reports it after its structural codes
        if cal is None and cols_of is None:     # nothing to check against (a fake or null store)
            if bad_type:
                return "malformed_type"
            continue
        try:
            if cal is not None:
                pos = cal.position(session)
                if pos is None:
                    if strict:
                        return "session_not_in_calendar"
                elif type(grid) in _SEQ and len(grid) > cal.minutes[pos]:
                    return "record_length_mismatch"
            key = (sid, metric, window_s)
            prev = last.get(key)
            if prev is None and cols_of is not None:
                cols = cols_of(sid, metric, window_s)
                if cols is not None and cols.ids:
                    prev = cols.ids[-1]
            if prev is not None:
                if session == prev:
                    return "duplicate_session"
                if session < prev:
                    return "out_of_order_append"
            last[key] = session
        except Exception:
            return "malformed_type"
        if bad_type:
            return "malformed_type"
    return None


def append_records(store, records, lane="stock"):
    """See the module docstring. Returns an AppendResult; never raises on a store or caller error."""
    try:
        try:
            recs = list(records)
        except Exception:
            return AppendResult(0, "malformed_type")
        code = _validate(store, recs, lane)
        if code is not None:
            return AppendResult(0, code)
        add = getattr(store, "add_series", None)
        k_of = getattr(store, "k_of", None)
        if add is not None:                     # retention 252 per series id before its first append, never lowered
            seen = set()
            for r in recs:
                sid = r[0]
                if sid not in seen:
                    seen.add(sid)
                    if k_of is None or k_of(sid) < _K:
                        add(sid, _K)
    except Exception as e:
        return AppendResult(0, str(getattr(e, "code", None) or e))
    n = 0
    try:
        for sid, metric, window_s, session, grid, total in recs:
            store.append(sid, metric, window_s, session, grid, total=total, lane=lane,
                         delta_convention=_CONV.get(metric))
            n += 1
    except Exception as e:                      # a store error is a code, never an exception to the caller
        return AppendResult(n, str(getattr(e, "code", None) or e))
    return AppendResult(n, None)
