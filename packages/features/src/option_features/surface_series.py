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
    append_records(store, records, lane="stock")      -> (count, code): store.append(series_id, metric, 0,
        session_id, grid, total=total, lane=lane); a store error stops the batch and its code (the exception's
        `code` or text) is returned instead of raised.

Performance: one pass per series; grids are rounded in C-level passes (map) with an exactness check, falling
back to exact integer rounding only for tie-risk or hostile entries.
"""
from operator import sub

from .m3a_common import round_units

_SCALE = 10 ** 8
_FSCALE = 1e8
_FLOAT_ONLY = {float}
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
            d = int(k)
            if it["atm_iv"].__class__ is float and it["atm_iv"] - it["atm_iv"] == 0.0 and (bd is None or d < bd):
                bd, best = d, it
        except (TypeError, ValueError, KeyError, AttributeError):
            continue
    return best


def _tenor(floats, key):
    v = floats["tenors"].get(key)
    return v if _ok(v) else None


def _scalars(floats, out, fwd):
    try:
        it = _nearest(floats)
    except (TypeError, AttributeError, KeyError):
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
        except (TypeError, AttributeError):
            return
        if t30 is not None:
            out["iv30_close"] = round_units(t30)
            if t91 is not None:
                out["term_30_91"] = _diff_units(t30, t91)


def scalar_units(floats, floats_fwd=None):
    out = {}
    try:
        _scalars(floats, out, False)
    except (TypeError, AttributeError, KeyError, ValueError):
        pass
    if floats_fwd is not None:
        try:
            _scalars(floats_fwd, out, True)
        except (TypeError, AttributeError, KeyError, ValueError):
            pass
    return out


def _slow_grid(values):
    return [round_units(v) if _ok(v) else 0 for v in values]


def grid_units(values):
    if type(values) is not list:
        try:
            values = list(values)
        except TypeError:
            return []
    if not set(map(type, values)) <= _FLOAT_ONLY:
        return _slow_grid(values)
    try:
        fs = [v * _FSCALE for v in values]
        rs = list(map(round, fs))
        # the product is exact to ~1e-8 of a unit; far from a .5 tie round() equals half-even on the exact value
        if fs:
            d = list(map(sub, fs, rs))
            if max(d) > 0.49 or min(d) < -0.49:
                return _slow_grid(values)
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
    except (TypeError, AttributeError, KeyError, ValueError):
        a = None
    try:
        t = f["tenors"].get("30")
        t = t if _ok(t) else None
    except (TypeError, AttributeError, KeyError):
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
    cols = None
    if type(minute_columns) is tuple and len(minute_columns) == 2:
        cols = minute_columns                   # pre-extracted (atm_iv floats, iv30 floats), one per minute
    elif type(minute_floats) is list and minute_floats:
        cols = _minute_pair(minute_floats)
    if cols is not None:
        for metric, col in zip(("atm_iv", "iv30"), cols):
            grid = grid_units(col)
            out.append(("%s/%s/%s" % (underlying, lane, metric), metric, 0, session_id, grid, sum(grid)))
    sc = scalar_units(close_floats, close_floats_fwd)
    for metric in _FIELDS[2:]:
        v = sc.get(metric)
        if v is not None:
            out.append(("%s/%s/%s" % (underlying, lane, metric), metric, 0, session_id, [], v))
    return out


def append_records(store, records, lane="stock"):
    n = 0
    try:
        for sid, metric, window_s, session, grid, total in records:
            store.append(sid, metric, window_s, session, grid, total=total, lane=lane)
            n += 1
    except Exception as e:                      # a store error is a code, never an exception to the caller
        return n, str(getattr(e, "code", None) or e)
    return n, None
