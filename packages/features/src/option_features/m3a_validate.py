"""M3a structural validation wrappers (story S09): the entry-point precedence lists of docs/m3a/M3A_IO_CONTRACT.md
section 4, type-first per field, the first failing code reported.

Pure and single-threaded; no I/O, no clocks, no solver. Every function returns a closed structural code
(`m3a_common.CODES`) or None; the caller builds the `invalid_input` result (`m3a_common.Result.invalid`) before any
evaluation (R-131).

Entry points
  validate_request(output_id, contracts, spot, rate, dividend_yield, cutoff_ns, params, validate="scanned")
      -> code | None. `contracts`: M1 `ChainContract` records (or any 10-tuple in its field order). `params`: the
      request parameters (dict). Position-major scan (R-101): the lowest failing position wins, ties by contract
      order, within one position the fields in the order written; a wrong-typed field reports `malformed_type` at the
      position of that field's value check (R-67, R-107), a field without a value code at position 10.
  validate_view_read(calendar, as_of, form, min_sessions, max_sessions, x=None, minute=None, series_id=None,
                     delta_convention="spot") -> code | None  (view-read list, 5 positions).
  store_call(fn, *args, **kwargs) -> (value, code): the M2 history append and load, snapshot and text-load lists are
      the M2 store's, unchanged (R-70); the wrapper maps `M2StructuralError` to its code.
  m1_error_code(exc) -> code: an M1 `ValueError` (IVChain construction) mapped to its structural code.

Positions applied per output (R-120, R-149, R-168, R-174): `tenors` and `delta_target` on the chain-reading outputs
M3A-0 and M3A-3..M3A-11; `iv_form` on M3A-2 and M3A-3; `delta_convention` on M3A-0 and M3A-7..M3A-11 (ignored, not
validated, on V1 to V7); percentile `x` (and `tail`) on M3A-1, M3A-2, M3A-8; `at_least`, `at_most`, `direction` on
M3A-3..M3A-7 and M3A-9..M3A-11; `minute` on M3A-2; priors on M3A-3, M3A-6, M3A-9 (convention check on M3A-9);
`delayed_feed_tag` on M3A-2 and on intraday M3A-1, M3A-3, M3A-8. A parameter that is absent or None is not
supplied, except the selectors with a default (mode, lane, feed_delay_tag, delta_target, iv_form, delta_convention,
direction), for which a supplied None is `malformed_type`.

`validate="scanned"` (hot-path default) and `"full"` give the same codes; every M3a output reads the whole chain (the
frame counts every listed strike), so the contracts read are the chain and both scan it once
(docs/decisions/2026-10-30-m3a-s09.md).

Performance: one pass over the contracts with exact-type dispatch (`type(x) is int`, never isinstance on the hot
path), one compiled grammar match per text quote, early exit on the lowest possible position, no Fraction or Decimal
unless a value sits exactly on a range boundary.
"""
import re
from decimal import Decimal
from fractions import Fraction
from math import isfinite

from .chainiv import ChainContract as _CC
from .flowresult import M2StructuralError

REQUEST_LIST = (
    ("bad_cutoff",), ("bad_spot",), ("bad_rate",), ("invalid_mode",), ("invalid_lane",), ("bad_expiry",),
    ("unknown_right",), ("duplicate_contract",), ("bad_strike",), ("malformed_type", "cutoff_mismatch"),
    ("duplicate_contract",), ("tenor_not_allowed",),
    ("delta_not_allowed", "iv_form_not_allowed", "convention_not_allowed"), ("threshold_required",),
    ("threshold_out_of_range", "invalid_direction"), ("minute_out_of_range",),
    ("prior_not_before_cutoff", "convention_mismatch"), ("delayed_feed_tag",),
)
VIEW_READ_LIST = (
    ("session_not_in_calendar",), ("minute_out_of_range",), ("malformed_type", "invalid_session_window"),
    ("threshold_out_of_range",), ("convention_mismatch",),
)

_MT = "malformed_type"
# chain quotes, strikes and spot text: the M2 price grammar, at most 8 decimal places (R-164: length-based)
_PRICE8_RE = r"-?(?:[0-9]+(?:\.[0-9]{0,8})?|\.[0-9]{1,8})"
_PRICE8 = re.compile(_PRICE8_RE + r"\Z", re.ASCII).match
_PAIR8 = re.compile(_PRICE8_RE + r"\|" + _PRICE8_RE + r"\Z", re.ASCII).match     # "bid|ask" in one match
# rate, dividend yield, delta target, threshold text: the same grammar, no place limit
_DECIMAL = re.compile(r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z", re.ASCII).match
# percentile x: an integer or "a/b" text (the M2 rational parameter form)
_RATIONAL = re.compile(r"-?[0-9]+(?:/[0-9]+)?\Z", re.ASCII).match
_TICK_DEN = 10 ** 8

_MODES = frozenset(("intraday", "close"))
_LANES = frozenset(("stock", "etf_index"))
_RIGHTS = frozenset(("call", "put"))
_TENORS = frozenset((9, 30, 91))
_IV_FORMS = frozenset(("atm", "30d"))
_CONVENTIONS = frozenset(("spot", "forward"))
_DIRECTIONS = frozenset(("up", "down", "either"))
_FEED_TAGS = frozenset(("live", "delayed"))
_TAILS = frozenset(("top", "bottom"))
_PAIRS = frozenset(("9-30", "30-91"))
_PRIOR_KINDS = frozenset(("frame", "session"))
_CONDITIONS = frozenset(("change", "sign_change"))
_QUARTER = Fraction(1, 4)
_SCALARS = frozenset((bool, int, float, complex, str, bytes, bytearray, Fraction, Decimal, list, tuple, set,
                      frozenset, type(None)))

_CHAIN_OUT = frozenset(("M3A-0", "M3A-3", "M3A-4", "M3A-5", "M3A-6", "M3A-7", "M3A-8", "M3A-9", "M3A-10", "M3A-11"))
_IVFORM_OUT = frozenset(("M3A-2", "M3A-3"))
_CONV_OUT = frozenset(("M3A-0", "M3A-7", "M3A-8", "M3A-9", "M3A-10", "M3A-11"))
_PCT_OUT = frozenset(("M3A-1", "M3A-2", "M3A-8"))
_LEVEL_OUT = frozenset(("M3A-3", "M3A-4", "M3A-5", "M3A-6", "M3A-7", "M3A-9", "M3A-10", "M3A-11"))
_PRIOR_OUT = frozenset(("M3A-3", "M3A-6", "M3A-9"))
_HISTORY_OUT = frozenset(("M3A-1", "M3A-2", "M3A-8"))
_DELAY_INTRADAY = frozenset(("M3A-1", "M3A-3", "M3A-8"))
_OUTPUTS = frozenset("M3A-%d" % i for i in range(12))
_NO_DEFAULT_THRESHOLD = "M3A-11"          # V21 (R-116)


def _exact_text(s):
    """Exact Fraction of a grammar-valid decimal text or "a/b" text, without the int string-length limit (Decimal
    parses any length); None for a zero denominator."""
    if len(s) < 4000:
        try:
            return Fraction(s)
        except ZeroDivisionError:
            return None
    num, slash, den = s.partition("/")
    n = Fraction(Decimal(num))
    if not slash:
        return n
    d = Fraction(Decimal(den))
    return None if d == 0 else n / d


def _positive_text(s):
    """Sign of a grammar-valid decimal text: True when > 0 (no leading '-' and a non-zero digit)."""
    return s[0] != "-" and s.strip("0.") != ""


def _ticks(v):
    """Integer 10^-8 ticks of a validated strike (text within 8 places, or a non-bool int)."""
    if type(v) is int:
        return v * _TICK_DEN
    if v[0] == "-":
        return -_ticks(v[1:])
    whole, _, frac = v.partition(".")
    if len(whole) > 4000:
        return int(Decimal(whole + "." + frac).scaleb(8))
    return int(whole or "0") * _TICK_DEN + (int(frac.ljust(8, "0")) if frac else 0)


# ---- request scalars -------------------------------------------------------------------------------------------

def _spot_code(s):
    t = type(s)
    if t is str:
        if _PRICE8(s) is None:
            return _MT
        return None if _positive_text(s) else "bad_spot"
    if t is int:
        return None if s > 0 else "bad_spot"
    if t is float:
        if not isfinite(s):
            return "bad_spot"
        if s.as_integer_ratio()[1] > 256:           # binary64 n/2^k is 8-decimal exact iff 2^k divides 10^8
            return _MT
        return None if s > 0 else "bad_spot"
    if t is Fraction:
        if _TICK_DEN % s.denominator:
            return _MT
        return None if s > 0 else "bad_spot"
    return _MT


def _real(v):
    """(code, value): a rate-like scalar as float or exact (int, Fraction); text keeps its string for the exact
    boundary test. `code` is malformed_type for a wrong type or grammar."""
    t = type(v)
    if t is str:
        if _DECIMAL(v) is None:
            return _MT, None
        return None, v
    if t is int or t is float or t is Fraction:
        return None, v
    return _MT, None


def _in_range(v, lo, hi):
    """lo <= v <= hi for a finite-checked rate-like value; text is decided in binary64 and re-decided exactly only
    when its binary64 value sits on a bound (rounding is monotone, so a strict float inequality is exact)."""
    t = type(v)
    if t is str:
        f = float(v)
        if lo < f < hi:
            return True
        if f == lo or f == hi:
            e = _exact_text(v)
            return lo <= e <= hi
        return False
    if t is float and not isfinite(v):
        return False
    return lo <= v <= hi


def _rate_code(rate, q):
    code, v = _real(rate)
    if code:
        return code
    if not _in_range(v, -1, 1):
        return "bad_rate"
    code, v = _real(q)
    if code:
        return code
    if not _in_range(v, 0, 1):
        return "bad_rate"
    return None


def _selector(params, name, allowed, value_code, default):
    v = params.get(name, default)
    if type(v) is not str:
        return _MT
    return None if v in allowed else value_code


def _delta_target_code(v):
    t = type(v)
    if t is str:
        if v == "0.25":
            return None
        if _DECIMAL(v) is None:
            return _MT
        return None if _exact_text(v) == _QUARTER else "delta_not_allowed"
    if t is float or t is int or t is Fraction:
        return None if v == 0.25 else "delta_not_allowed"
    return _MT


def _x_value(x):
    """Exact percentile x (int or Fraction), or None when malformed (float, bool, Decimal, other text)."""
    t = type(x)
    if t is int:
        return x
    if t is Fraction:
        return x
    if t is str and _RATIONAL(x) is not None:
        return _exact_text(x)
    return None


x_value = _x_value          # public: the one percentile-x type rule (R-190), shared with m3a_history (S02)


def _level_ok(v):
    """A level threshold (`at_least`, `at_most`): non-bool int, Fraction or decimal text."""
    t = type(v)
    return t is int or t is Fraction or (t is str and _DECIMAL(v) is not None)


def _rational_param_ok(v):
    """A ratio parameter (`min_coverage`): non-bool int, Fraction, decimal text or "a/b" text with b > 0."""
    t = type(v)
    if t is int or t is Fraction:
        return True
    if t is not str:
        return False
    if _DECIMAL(v) is not None:
        return True
    return _RATIONAL(v) is not None and "/" in v and v.partition("/")[2].strip("0") != ""


def _slot10_params(oid, p):
    """Type checks of the request fields without a value code (position 10), in a fixed order."""
    g = p.get
    v = g("evaluation_ns")
    if v is not None and type(v) is not int:
        return _MT
    if "feed_delay_tag" in p and (type(p["feed_delay_tag"]) is not str or p["feed_delay_tag"] not in _FEED_TAGS):
        return _MT
    v = g("stale_limit_ns")
    if v is not None and (type(v) is not int or v < 0):
        return _MT
    v = g("min_strikes")
    if v is not None and (type(v) is not int or v < 0):
        return _MT
    v = g("min_coverage")
    if v is not None and not _rational_param_ok(v):
        return _MT
    v = g("session_minutes")
    if v is not None and (type(v) is not int or v < 1):
        return _MT
    v = g("fire")
    if v is not None and type(v) is not bool:
        return _MT
    if oid in _LEVEL_OUT:
        for name in ("at_least", "at_most"):          # no value code: typed at position 10
            v = g(name)
            if v is not None and not _level_ok(v):
                return _MT
    if oid in _PCT_OUT:
        v = g("tail")
        if v is not None and (type(v) is not str or v not in _TAILS):
            return _MT
    if oid in _HISTORY_OUT:
        for name in ("min_sessions", "max_sessions"):
            v = g(name)
            if v is not None and (type(v) is not int or v < 1):
                return _MT
    if oid == "M3A-4":
        v = g("pair")
        if v is not None and (type(v) is not str or v not in _PAIRS):
            return _MT
    if oid == "M3A-6" or oid == "M3A-3" or oid == "M3A-9":
        v = g("prior_sessions")
        if v is not None and (type(v) is not int or v < 1):
            return _MT
    if oid == "M3A-9":
        v = g("prior_kind")
        if v is not None and (type(v) is not str or v not in _PRIOR_KINDS):
            return _MT
        v = g("condition")
        if v is not None and (type(v) is not str or v not in _CONDITIONS):
            return _MT
    return None


def _priors(p):
    """The supplied prior readings: `prior` (one, or None) then `priors` (a list or tuple, or None); None when either
    has a wrong type (malformed_type). A reading is a dict or a record with attributes (not a builtin scalar)."""
    one, many = p.get("prior"), p.get("priors")
    out = []
    if one is not None:
        out.append(one)
    if many is not None:
        tm = type(many)
        if tm is not list and tm is not tuple:
            return None
        out.extend(many)
    for pr in out:
        if type(pr) is not dict and (type(pr) in _SCALARS or not hasattr(pr, "time_ns")):
            return None
    return out


def _prior_get(pr, name, default=None):
    if type(pr) is dict:
        return pr.get(name, default)
    return getattr(pr, name, default)


def _prior_convention(pr):
    c = _prior_get(pr, "delta_convention")
    if c is None:
        c = _prior_get(pr, "convention", "spot")
    return c


# ---- request list ----------------------------------------------------------------------------------------------

def _contracts_code(contracts):
    """(position, code) of the lowest failing contract position (6, 7, 8, 9, 10 or 11), ties by contract order;
    (99, None) when every contract passes. One pass; stops at position 6 (nothing lower is a contract position)."""
    best_pos, best_code = 99, None
    ids = set()
    keys = set()
    strike_ticks = {}         # strike text -> ticks, valid and positive
    price = _PRICE8
    pair8 = _PAIR8
    for c in contracts:
        if type(c) is not _CC and (not isinstance(c, tuple) or len(c) != 10):
            return 6, _MT                    # not a contract record: its expiry_days cannot be read
        cid, days, right, strike, bid, ask, ev, known, style, cond = c
        # position 6: expiry_days
        if type(days) is not int:
            return 6, _MT
        if days < 1:
            return 6, "bad_expiry"
        if best_pos <= 7:
            continue
        # position 7: right
        if type(right) is not str:
            best_pos, best_code = 7, _MT
            continue
        if right not in _RIGHTS:
            best_pos, best_code = 7, "unknown_right"
            continue
        # position 8: contract id, type-first (a non-text id is malformed_type here), then duplicate_contract
        if type(cid) is not str:
            best_pos, best_code = 8, _MT
            continue
        if cid in ids:
            best_pos, best_code = 8, "duplicate_contract"
            continue
        ids.add(cid)
        if best_pos <= 9:
            continue
        # position 9: strike (type-first); a strike text is validated and converted once per call (memo)
        ts = type(strike)
        if ts is str:
            tk = strike_ticks.get(strike)
            if tk is None:
                if price(strike) is None:
                    best_pos, best_code = 9, _MT
                    continue
                if not _positive_text(strike):
                    best_pos, best_code = 9, "bad_strike"
                    continue
                tk = strike_ticks[strike] = _ticks(strike)
        elif ts is int:
            if strike <= 0:
                best_pos, best_code = 9, "bad_strike"
                continue
            tk = strike * _TICK_DEN
        else:
            best_pos, best_code = 9, _MT
            continue
        if best_pos <= 10:
            continue
        # position 10: every field without a value code, in the order written
        tb, ta = type(bid), type(ask)
        if tb is str and ta is str:
            if pair8(bid + "|" + ask) is None:          # both quotes in one grammar match
                best_pos, best_code = 10, _MT
                continue
        elif (tb is not int and bid is not None and (tb is not str or price(bid) is None)) or \
                (ta is not int and ask is not None and (ta is not str or price(ask) is None)):
            best_pos, best_code = 10, _MT
            continue
        if type(ev) is not int or (known is not None and type(known) is not int) or type(style) is not str \
                or type(cond) is not str:
            best_pos, best_code = 10, _MT
            continue
        if best_pos <= 11:
            continue
        # position 11: same expiry, strike and right twice (strike compared by value)
        key = (days, right, tk)
        if key in keys:
            best_pos, best_code = 11, "duplicate_contract"
            continue
        keys.add(key)
    return best_pos, best_code


def validate_request(output_id, contracts, spot, rate, dividend_yield, cutoff_ns, params, validate="scanned"):
    """First failing code of the request list (18 positions, 23 codes), or None."""
    if validate != "scanned" and validate != "full":
        raise ValueError('validate must be "scanned" or "full"')
    # caller-supplied containers: exact types, so no caller method (__eq__, __hash__, get, __iter__) ever runs
    if type(params) is dict:
        p, params_ok = params, True
    else:
        p, params_ok = {}, params is None
    oid_ok = type(output_id) is str and output_id in _OUTPUTS
    oid = output_id if oid_ok else None
    # 1 cutoff
    if type(cutoff_ns) is not int:
        return _MT
    if cutoff_ns < 0:
        return "bad_cutoff"
    # 2 spot, 3 rate and dividend yield
    code = _spot_code(spot)
    if code:
        return code
    code = _rate_code(rate, dividend_yield)
    if code:
        return code
    # 4 mode, 5 lane
    mode = p.get("mode", "intraday")
    if type(mode) is not str:
        return _MT
    if mode not in _MODES or (oid == "M3A-2" and mode != "intraday"):   # V3 is intraday only (R-175, D7)
        return "invalid_mode"
    code = _selector(p, "lane", _LANES, "invalid_lane", "stock")
    if code:
        return code
    # 6 to 11 on the contracts (position-major, one pass); a container that is not a list or tuple is malformed_type
    tc = type(contracts)
    if tc is not list and tc is not tuple:
        return _MT
    pos, code = _contracts_code(contracts)
    if pos <= 10:
        return code
    # 10: request fields without a value code, then cutoff_mismatch
    if not (params_ok and oid_ok):
        return _MT
    c10 = _slot10_params(oid, p)
    if c10:
        return c10
    ev = p.get("evaluation_ns")
    if ev is not None and ev != cutoff_ns:
        return "cutoff_mismatch"
    if pos == 11:
        return code
    chain_out = oid in _CHAIN_OUT
    # 12 tenors
    if chain_out and "tenors" in p:
        tenors = p["tenors"]
        tt = type(tenors)
        if tt is not list and tt is not tuple:
            return _MT
        for t in tenors:
            if type(t) is not int:
                return _MT
            if t not in _TENORS:
                return "tenor_not_allowed"
    # 13 delta_target, iv_form, delta_convention
    if chain_out and "delta_target" in p:
        code = _delta_target_code(p["delta_target"])
        if code:
            return code
    if oid in _IVFORM_OUT and "iv_form" in p:
        code = _selector(p, "iv_form", _IV_FORMS, "iv_form_not_allowed", "atm")
        if code:
            return code
    conv_out = oid in _CONV_OUT
    if conv_out:
        code = _selector(p, "delta_convention", _CONVENTIONS, "convention_not_allowed", "spot")
        if code:
            return code
    # 14 threshold_required
    pct = oid in _PCT_OUT
    level = oid in _LEVEL_OUT
    if p.get("fire") is True or oid == _NO_DEFAULT_THRESHOLD:
        if pct:
            if p.get("x") is None:
                return "threshold_required"
        elif level and p.get("at_least") is None and p.get("at_most") is None:
            return "threshold_required"
    # 15 threshold_out_of_range (x), then invalid_direction
    if pct:
        x = p.get("x")
        if x is not None:
            xv = _x_value(x)
            if xv is None:
                return _MT
            if xv < 0 or xv > 100:
                return "threshold_out_of_range"
    elif level:
        if "direction" in p:
            code = _selector(p, "direction", _DIRECTIONS, "invalid_direction", "up")
            if code:
                return code
    # 16 minute (V3)
    if oid == "M3A-2":
        m = p.get("minute")
        if m is not None:
            if type(m) is not int:
                return _MT
            sm = p.get("session_minutes")
            if m < 0 or (sm is not None and m >= sm):
                return "minute_out_of_range"
    # 17 priors: every prior's time (R-134), then the convention (R-160, convention outputs only)
    if oid in _PRIOR_OUT:
        priors = _priors(p)
        if priors is None:
            return _MT
        if priors:
            for pr in priors:
                t = _prior_get(pr, "time_ns")
                if t is not None:
                    if type(t) is not int:
                        return _MT
                    if t >= cutoff_ns:
                        return "prior_not_before_cutoff"
            if conv_out:
                want = p.get("delta_convention", "spot")
                for pr in priors:
                    c = _prior_convention(pr)
                    if type(c) is not str:
                        return _MT
                    if c != want:
                        return "convention_mismatch"
    # 18 delayed feed
    if p.get("feed_delay_tag") == "delayed" and (oid == "M3A-2" or (oid in _DELAY_INTRADAY and mode == "intraday")):
        return "delayed_feed_tag"
    return None


# ---- view read -------------------------------------------------------------------------------------------------

def _series_convention(series_id):
    """'spot' or 'forward' for a skew-type series (metric skew25 / <metric>_fwd), None for a convention-free one."""
    if type(series_id) is not str:
        return None
    metric = series_id.rpartition("/")[2]
    if not metric.startswith("skew"):
        return None
    return "forward" if metric.endswith("_fwd") else "spot"


def validate_view_read(calendar, as_of, form, min_sessions, max_sessions, x=None, minute=None, series_id=None,
                       delta_convention="spot"):
    """First failing code of the view-read list (`scalar_baseline`, `same_minute_column`), or None. `calendar` is an
    M2 `Calendar` (position(), minutes)."""
    if type(as_of) is not str:
        return _MT
    pos = calendar.position(as_of)
    if pos is None:
        return "session_not_in_calendar"
    if type(form) is not str:
        return _MT
    if form == "same_minute_column" and minute is not None:
        if type(minute) is not int:
            return _MT
        if minute < 0 or minute >= calendar.minutes[pos]:
            return "minute_out_of_range"
    mn = 20 if min_sessions is None else min_sessions
    mx = 252 if max_sessions is None else max_sessions
    if type(mn) is not int or type(mx) is not int or mn < 1 or mx < 1:
        return _MT
    if mx < mn:
        return "invalid_session_window"
    if x is not None:
        xv = _x_value(x)
        if xv is None:
            return _MT
        if xv < 0 or xv > 100:
            return "threshold_out_of_range"
    sc = _series_convention(series_id)
    if sc is not None:
        if type(delta_convention) is not str or delta_convention not in _CONVENTIONS:
            return _MT
        if sc != delta_convention:
            return "convention_mismatch"
    return None


# ---- store and M1 mapping --------------------------------------------------------------------------------------

def store_call(fn, *args, **kwargs):
    """(value, None), or (None, code) when the M2 store raises its structural error (append, load, snapshot, text)."""
    try:
        return fn(*args, **kwargs), None
    except M2StructuralError as e:
        return None, e.code


_M1_MESSAGES = (
    ("spot must be positive", "bad_spot"),
    ("expiry_days must be", "bad_expiry"),
    ("right must be", "unknown_right"),
    ("duplicate contract", "duplicate_contract"),
    ("strike must be positive", "bad_strike"),
)


def m1_error_code(exc):
    """Structural code of an M1 ValueError raised by `chainiv.IVChain` (R-69); any other M1 input error (more than 8
    places, not representable, wrong type) is malformed_type."""
    try:
        text = str(exc) if isinstance(exc, BaseException) else ""
    except Exception:          # a hostile argument (deep nesting, a failing __str__) is no M1 message
        return _MT
    for prefix, code in _M1_MESSAGES:
        if text.startswith(prefix):
            return code
    return _MT
