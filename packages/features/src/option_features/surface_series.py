"""M3a story S10: series builder M3A-12 (R-48, R-153, R-189, R-194 to R-197).

Pure and single-threaded: no I/O, clocks or shared state; never raises on caller data (unusable values are
treated as unavailable and give no stored value). It never solves IV and never parses frame text: it reads the
unrounded binary64 values S05 exposes in `stats["floats"]` (R-189):
    {"expiries": {"<days>": {"atm_iv", "put25_iv", "call25_iv"}}, "tenors": {"<t>": float | None},
     "available": bool}
`available` is the S05 frame status (True iff the frame result is "available", R-141). History is written only from an
AVAILABLE frame (R-197), FAIL CLOSED: a record is stored only when floats.get("available") is True; a missing key or
any other value stores no scalar record and gives no value at its minute. The key is the S05c patch (a prerequisite
of S11), see the decision file.

Calls
    series_id(underlying, lane, metric)               -> "<UNDERLYING>/<lane>/<metric>", or None when `underlying`,
        `lane` or `metric` is empty, not exactly a str (a str subclass is refused), or contains "/". `underlying` is the adapter symbol; it must not contain
        "/"; the adapter normalises or rejects before S10 (build_records returns [] for such an underlying).
    scalar_units(floats, floats_fwd=None)             -> {metric: int} (10^-8 units); an unavailable metric is
        absent. atm_iv_close = ATM IV of the nearest eligible expiry (lowest days with a usable atm_iv);
        skew25 = put25 - call25 of that expiry (spot-convention frame); skew25_fwd the same on `floats_fwd`;
        iv30_close = tenor 30; term_30_91 = tenor 91 - tenor 30 (longer minus shorter, R-30, R-33; S10b). A difference is the EXACT binary64 difference
        rounded ONCE, half to even (integer arithmetic on as_integer_ratio, no Fraction); a single value is rounded once.
    grid_units(values)                                -> [int]: one entry per minute; None or an unusable value
        gives 0 (the M2 dense zero-fill convention; the store keeps non-zero entries only). In a minute series a
        stored 0 means "no value at that minute" (R-195): an IV that rounds to 0 at 10^-8 (below 5e-9) is stored as 0,
        i.e. as unavailable; S02b's read skips zero points.
    build_records(underlying, lane, session_id, close_floats, close_floats_fwd=None, minute_floats=None)
        (or `minute_columns=(atm_iv_floats, iv30_floats)` already extracted, skipping the per-minute dict reads)
        -> [(series_id, metric, window_s, session_id, grid, total)] in the order atm_iv, iv30 (minute grids,
        window_s 0, total the grid sum), atm_iv_close, iv30_close, skew25, skew25_fwd, term_30_91 (scalars: grid
        [], total the integer). `minute_floats` is a list of per-minute stats["floats"] (None for a missing
        minute). A series without a value gets no record (R-194): a minute series whose grid has no available entry
        (all None or unusable, a column that cannot be iterated, an empty column, or only values that round to 0) is
        MISSING for that session like a scalar (R-51), not a record of zeros. Negative values count as values.
    declare_series(store, series_ids)                 -> set of the ids now at retention 252 or more (add_series is
        called only for ids not yet there; never lowers). append_records calls it itself unless told `declared`.
    append_records(store, records, lane="stock", declared=None) -> AppendResult (a (count, code) tuple with
        .committed, .code, .partial): validates the WHOLE batch first (record shape, lane, calendar, grid length, grid
        and total types, grid element types, session order and duplicates against the store's retained sessions and
        the earlier records of the batch; the ring lane of a stored series through `baseline`) and appends nothing
        when a record fails (count 0, the structural code); declares add_series(series_id, 252) for every series id
        not already at 252 or more (ids in `declared` are taken as done), then store.append(series_id, metric,
        window_s, session_id, grid, total=total, lane=lane, delta_convention=...): "spot" for skew25, "forward" for
        skew25_fwd, None otherwise (R-160). A store error that validation did not see stops the batch: count is the
        number of records already committed (partial is True when it is above 0) and code the exception's `code`,
        its text, or its class name. Nothing is rolled back and a retry after a partial commit meets
        duplicate_session: the S11 runner builds a fresh store per run. The validation mirrors HistoryStore.append;
        drift is gated by TestValidateDrift. A store without `calendar` / `m3a_cols` / `add_series` (a fake or a null
        store) is only shape-checked.

Never raises on caller data: any Exception raised while reading caller objects (dict access, iteration) makes the
value unavailable (BaseException such as KeyboardInterrupt propagates). Performance: one pass per series; grids are
rounded in C-level passes (scale, floor, fraction check); a grid with unusable entries is masked once and takes the
same passes; only entries within the guard band of a rounding boundary (see `grid_units`), and large values, take
the exact integer path.
"""
from math import floor
from operator import sub

from .m3a_common import round_units

_SCALE = 10 ** 8
_FSCALE = 1e8
_FLOAT_ONLY = {float}
_FLOAT_OR_NONE = {float, type(None)}
_SMALL = 1.5e9             # _fast_small: |v * 1e8| below this (|v| below 15)
_BIG = 2.0 ** 16            # the fast path needs |v| < 2^16, so v * 1e8 < 2^43 (see grid_units)
_ERR = 2.0 ** -50           # four times the relative error of the two float operations (2 * 2^-53 -> 2^-52)
_W0 = (1.6e9 + 1.0) * _ERR  # the constant guard half-width of _fast_small, (max|t| + 1) * 2^-50 for |t| <= 1.6e9
_C0 = 0.5 + _W0
_LIM0 = _W0 + _W0
_CONV = {"skew25": "spot", "skew25_fwd": "forward"}     # delta_convention of the stored record (R-160)
_K = 252                    # retention declared per series id (R-114)
_SEQ = (list, tuple)
_INT_ONLY = {int}
_FIELDS = ("atm_iv", "iv30", "atm_iv_close", "iv30_close", "skew25", "skew25_fwd", "term_30_91")


def _prefix(underlying, lane):
    """"<underlying>/<lane>/" or None for an unusable underlying or lane (empty, not exactly a str, or with "/")."""
    if (type(underlying) is not str or type(lane) is not str or not underlying or not lane or "/" in underlying
            or "/" in lane):
        return None
    return "%s/%s/" % (underlying, lane)


def series_id(underlying, lane, metric):
    pre = _prefix(underlying, lane)
    if pre is None or type(metric) is not str or not metric or "/" in metric:
        return None
    return pre + metric


def _ok(x):
    """A usable value: a float (not bool) that is finite."""
    return type(x) is float and x - x == 0.0


def _avail(f):
    """True only for a frame that says `"available": True` (R-197, fail closed): a missing key, any other value, or a
    frame whose `get` raises is not available."""
    try:
        return f.get("available") is True
    except Exception:
        return False


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
    if not _avail(floats):
        return
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
                out["term_30_91"] = _diff_units(t91, t30)      # longer minus shorter (R-30, R-33)


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


def _fast(values):
    """The fast path on a non-empty list of floats (see grid_units). None when a value is too large for it; ValueError
    or OverflowError when a value is nan or inf."""
    mx = max(values)
    mn = min(values)
    if mx >= _BIG or mn <= -_BIG:
        return None
    w = _window(mx, mn)
    c = 0.5 + w
    u = [v * 1e8 + c for v in values]           # 1e8 == _FSCALE, a constant in the loop
    rs = list(map(floor, u))                    # nan or inf raise here
    lim = w + w
    if min(map(sub, u, rs)) < lim:              # d = u - rs, exact; the list is built only if a fix is needed
        for i in [i for i, x in enumerate(map(sub, u, rs)) if x < lim]:
            rs[i] = round_units(values[i])
    return rs


def _fast_small(values, holes):
    """The fast path with a constant guard band, for |v| < 15 (every real IV): one pass builds u = fl(fl(v * 1e8) + c0)
    with c0 = 0.5 + W0 and, when `holes`, 0.0 in place of None (0.0 rounds to 0 like an unusable entry). The same proof
    as `grid_units` holds with |t| <= 1.6e9 (checked on u, which is monotone in v) and W0 = (1.6e9 + 1) * 2^-50. None
    when a value is outside that range; ValueError or OverflowError for nan or inf."""
    c = _C0
    if holes:
        u = [(0.0 if v is None else v) * 1e8 + c for v in values]
    else:
        u = [v * 1e8 + c for v in values]
    if max(u) > _SMALL or min(u) < -_SMALL:
        return None
    rs = list(map(floor, u))                    # nan or inf raise here
    if min(map(sub, u, rs)) < _LIM0:
        for i in [i for i, x in enumerate(map(sub, u, rs)) if x < _LIM0]:
            rs[i] = round_units(0.0 if values[i] is None else values[i])
    return rs


def _fast_any(values):
    rs = _fast_small(values, False)
    return _fast(values) if rs is None else rs


def _masked(values):
    """The mixed path: every entry that is not a usable float becomes 0.0 in a copy (one pass for the types, a second
    only if a float is nan or inf), the fast path runs on the copy, and the unusable entries are 0 in the result.
    None when a value is too large for the fast path."""
    n = len(values)
    odd = [i for i, t in enumerate(map(type, values)) if t is not float]
    if len(odd) == n:
        return [0] * n
    m = list(values)
    for i in odd:
        m[i] = 0.0
    try:
        rs = _fast_any(m)
    except (ValueError, OverflowError):         # nan or inf among the floats
        bad = [i for i, v in enumerate(m) if v - v != 0.0]
        if len(bad) + len(odd) == n:
            return [0] * n
        for i in bad:
            m[i] = 0.0
        odd += bad
        rs = _fast_any(m)
    if rs is not None:
        for i in odd:
            rs[i] = 0
    return rs


def grid_units(values):
    """Exact half-even rounding to 10^-8 units of every entry (see the module docstring); an entry that is not a
    usable float (None, bool, int, str, nan, inf, a float subclass) is 0.

    Assumes IEEE-754 binary64 round-to-nearest-even per operation, no fused multiply-add (v * 1e8 + c is two
    roundings), no x87 extended precision. Verified for CPython 3.12 on Windows x64. A different platform or build
    must re-run GuardBand and Differential before the fast path is trusted.

    Fast path (floats with |v| < 2^16). Let t = v * 10^8 (real), W = (max|v| * 1e8 + 1) * 2^-50 (`_window`), c the
    float 0.5 + W, ws = c - 0.5 (exact, about W), u = fl(fl(v * 1e8) + c), rs = floor(u), d = u - rs (exact).
    Each float operation errs by at most 2^-53 relative and 1e8 is exact, so e = u - (t + c) has |e| <= (|t| + 1) *
    2^-52 <= W / 4. The exact answer for a non-tie is floor(t + 1/2) = floor(X - ws) with X = t + c. If d >= 2W, no
    integer lies in (X - ws, X + e] (it would have to be within ws + e < 2W below X + e), so rs = floor(t + 1/2); and
    t + 1/2 is not an integer there (that would put d at ws + e < 2W), so there is no tie and round-half-up equals
    half-even. Every entry with d < 2W (this includes every tie, where d = ws + e) is rounded exactly instead
    (round_units). The result therefore equals exact half-even rounding of every entry (tests: GuardBand,
    Differential). Mixed path: unusable entries are masked to 0.0 first (maximum and minimum are taken over the
    masked copy) and set to 0 afterwards, so the result is bit-identical to `_slow_grid`. |v| >= 2^16 takes the exact
    integer path."""
    if type(values) is not list:
        try:
            values = list(values)
        except Exception:                       # caller data: an iterable that raises is no values
            return []
    if not values:
        return []
    try:
        kinds = set(map(type, values))
        try:
            if kinds <= _FLOAT_ONLY:
                rs = _fast_any(values)
            elif kinds <= _FLOAT_OR_NONE:           # the common hole: a missing minute is None
                if len(kinds) == 1:
                    return [0] * len(values)
                rs = _fast_small(values, True)
                if rs is None:
                    rs = _fast([0.0 if v is None else v for v in values])
            else:
                rs = _masked(values)
        except (ValueError, OverflowError):         # nan or inf among the floats
            rs = _masked(values)
        return _slow_grid(values) if rs is None else rs
    except Exception:
        return _slow_grid(values)


def minute_values_from_floats(f):
    """The minute value rule (R-191): one per-minute stats["floats"] -> (atm_iv, iv30). atm_iv is the ATM IV of the
    nearest eligible expiry (lowest days with a finite float atm_iv); iv30 is tenor "30". A missing or unusable
    value is None, and so is every value of a frame whose `available` is not True (R-197). Never raises. S11 calls
    this once per minute in its G0 loop and passes the two columns."""
    if not _avail(f):
        return None, None
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
    pre = _prefix(underlying, lane)
    if pre is None:
        return []
    out = []
    cols = None
    if type(minute_columns) in _SEQ and len(minute_columns) == 2:
        cols = minute_columns                   # pre-extracted (atm_iv floats, iv30 floats), one per minute
    elif type(minute_floats) in _SEQ and minute_floats:
        cols = _minute_pair(minute_floats)
    if cols is not None:
        for metric, col in (("atm_iv", cols[0]), ("iv30", cols[1])):
            grid = grid_units(col)
            if any(grid):                       # R-194: no available minute, no record (the session is missing)
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

    def __getnewargs__(self):                   # pickle, copy and deepcopy
        return tuple(self)

    committed = property(lambda self: self[0])
    code = property(lambda self: self[1])
    partial = property(lambda self: self[1] is not None and self[0] > 0)


def _code(e):
    """The code of a store error: its `code`, else its text, else the exception class name."""
    try:
        return str(getattr(e, "code", None) or e) or type(e).__name__
    except Exception:                           # a hostile exception (its code or text raises) never escapes
        return type(e).__name__


def _validate(store, recs, lane):
    """The first failing record's structural code (the order of HistoryStore.append: ring lane, calendar, length,
    order, then types), or None. Mirrors HistoryStore.append; drift is gated by TestValidateDrift. Public store
    APIs only: `calendar`, `strict_calendar`, `m3a_cols` (retained sessions), `baseline` (ring lane)."""
    if type(lane) is not str:
        return "malformed_type"
    cal = getattr(store, "calendar", None)
    strict = getattr(store, "strict_calendar", True)
    cols_of = getattr(store, "m3a_cols", None)
    baseline = getattr(store, "baseline", None)
    last = {}                                   # (series, metric, window) -> last session seen in this batch
    for r in recs:
        try:
            sid, metric, window_s, session, grid, total = r
        except (TypeError, ValueError):
            return "malformed_type"
        if type(sid) is not str or type(metric) is not str:
            return "malformed_type"
        parts = sid.rsplit("/", 2)
        if len(parts) == 3 and parts[1] != lane:        # "<UNDERLYING>/<lane>/<metric>" of another lane
            return "lane_mismatch"
        bad_type = type(grid) not in _SEQ or type(total) is not int      # the store reports it after its structure
        if cal is None and cols_of is None:     # nothing to check against (a fake or null store)
            if bad_type:
                return "malformed_type"
            continue
        try:
            key = (sid, metric, window_s)
            prev = last.get(key)
            if prev is None and cols_of is not None:
                cols = cols_of(sid, metric, window_s)
                if cols is not None and cols.ids:
                    prev = cols.ids[-1]
                    if cal is not None and baseline is not None and cols.done[-1]:
                        pos = cal.position(prev)           # the ring lane: a view of the last session exists
                        if pos is not None and pos + 1 < len(cal.ids):     # only for the ring's own lane
                            if baseline(sid, metric, window_s, cal.ids[pos + 1], 1, lane) is None:
                                return "lane_mismatch"
            if cal is not None:
                pos = cal.position(session)
                if pos is None:
                    if strict:
                        return "session_not_in_calendar"
                elif type(grid) in _SEQ and len(grid) > cal.minutes[pos]:
                    return "record_length_mismatch"
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
        if cols_of is not None and not _INT_ONLY.issuperset(map(type, grid)):    # exact ints (not bool): the store's rule
            return "malformed_type"
    return None


def declare_series(store, series_ids):
    """Retention 252 for every id (R-114): add_series only for ids whose k_of is below 252, never lowering. Returns the
    set of ids that are at 252 or more afterwards (declared now or already). A store without add_series: empty set."""
    add = getattr(store, "add_series", None)
    if add is None:
        return set()
    k_of = getattr(store, "k_of", None)
    done = set()
    for sid in series_ids:
        if sid not in done:
            if k_of is None or k_of(sid) < _K:
                add(sid, _K)
            done.add(sid)
    return done


def append_records(store, records, lane="stock", declared=None):
    """See the module docstring. Returns an AppendResult; never raises on a store or caller error. `declared`: a set
    of series ids the caller already declared at 252 (from declare_series); their k_of check is skipped."""
    try:
        try:
            recs = list(records)
        except Exception:
            return AppendResult(0, "malformed_type")
        code = _validate(store, recs, lane)
        if code is not None:
            return AppendResult(0, code)
        ids = [r[0] for r in recs]
        if declared:
            ids = [i for i in ids if i not in declared]
        if ids:
            declare_series(store, ids)
    except Exception as e:
        return AppendResult(0, _code(e))
    n = 0
    try:
        for sid, metric, window_s, session, grid, total in recs:
            store.append(sid, metric, window_s, session, grid, total=total, lane=lane,
                         delta_convention=_CONV.get(metric))
            n += 1
    except Exception as e:                      # a store error is a code, never an exception to the caller
        return AppendResult(n, _code(e))
    return AppendResult(n, None)
