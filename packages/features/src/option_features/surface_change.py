"""M3a story S07: change outputs against a prior reading: V4 (M3A-3), V7 (M3A-6), V10 (M3A-9).

Pure and single-threaded; no I/O, no clocks, no solver, no hidden state (every call reads its arguments and the S02
store view and returns a new record; nothing is cached or kept between calls). A function never raises on caller data:
a frame or float it cannot read is `invalid_input` `malformed_type`.

Calls (frame = the S05 `surfaceframe.surface_frame` result, floats = its `stats["floats"]`, R-189)
    iv_change  (frame, floats, cutoff_ns, params)                                   -> Result M3A-3 (V4)
    gap_change (frame, floats, cutoff_ns, params, store, series_id, session_id)     -> Result M3A-6 (V7)
    skew_change(frame, floats, cutoff_ns, params, store, series_id, session_id)     -> Result M3A-9 (V10)
  * `params`: the request dict (IO contract section 2). Besides the frame parameters (tenors, mode, lane,
    feed_delay_tag, evaluation_ns, ...): V4 `iv_form`, `direction`, `at_least` / `at_most` / `x`, `prior` (the prior
    reading, R-40: {kind "frame" | "session", value, time_ns}); V7 and V10 `prior_sessions` (n, default 1), `direction`,
    thresholds; V10 also `prior_kind` ("frame", default, or "session"), `condition` ("change", default, or
    "sign_change"), `delta_convention`. `prior` (one reading) and `priors` (a list of readings, each {time_ns,
    delta_convention?, session_id?}) are checked at request position 17 for ALL supplied readings (R-92, R-134, R-160).
  * V4 and V10 frame kind take the prior reading as an INPUT (R-40; for a session prior of V4 the caller reads
    `atm_iv_close` / `iv30_close` and passes the value). V7 and V10 session kind read the n-th prior session close
    from the S02 store (`m3a_history.scalar_baseline`, series `series_id`, last n complete sessions before
    `session_id`, lane of the request); a store of the wrong convention is `convention_mismatch`.
  * The frame is built by the caller from the same request (V4 30d form: tenor 30; V7: tenors 30 and 91; V10: tenor 30
    and `delta_convention`; V4 to V7 take no convention, R-149). Only the items an output reads decide its status:
    another expiry's failed 25-delta side does not make V4 or V7 unavailable.
  * `floats["expiries"][days]["label"]` (the model label of the expiry's ATM legs; optional list `labels` of every label
    the expiry's frame items use, preferred when present) lets V4 and V7 carry the labels of the expiries they USED
    (R-180). S05 does not expose it yet (open question 1 of the decision file); absent, the labels of the frame are
    used.

Values (IO contract section 3; integers in 10^-8 units inside, half-even 8-decimal text at the envelope, one rounding):
  V4:  {iv_form, now, prior, change_points, change_ratio, prior_kind}. now = round-once of the selected IV: ATM form =
       `atm_iv` of the NEAREST ELIGIBLE expiry (R-151; an expiry failing coverage, low_surface_coverage, is skipped, any
       other failure of the nearest covered expiry is the reason, no fall-back), 30d form = the tenor-30 IV. prior =
       the reading rounded half-even to 8 decimals; change_points = (now - prior) x 100 (exact); change_ratio =
       (now - prior) / prior rounded once; prior 0 is `zero_denominator`. Fires on change_ratio in PERCENT (rounded
       decimal, inclusive, R-35): up at >= T, down at <= -T (R-133), either at |.| >= T; T = `at_least` | `at_most` |
       `x`, default 10, `direction` default up (R-84).
  V7:  {now, priors: [{session_id, gap}] most recent first (n entries), gap_change_points}. now = iv(91) - iv(30)
       (longer minus shorter, R-30), difference of the UNROUNDED floats rounded once; gap_change_points = (now - gap of
       the n-th prior) x 100, exact; threshold in points, default 2, `direction` default either; no slope (R-30).
  V10: {now, priors, change_points, sign_now, sign_prior, sign_changed, delta_convention}. now = skew at the 30-day
       tenor = put side minus call side, each side interpolated to 30 days by linear total variance (the S04 kernel on
       the 25-delta IVs: R-28, R-104, R-139, R-178), difference of the unrounded floats rounded once. `priors` is []
       for the frame kind. Signs are of the rounded values; changed = signs differ and neither is 0 (R-34). Fires on
       the change in points (as V7) or, for condition sign_change, when the sign changed (R-135).
  `params` echo (R-154, R-158): every parameter used with its default filled; `labels`: the model labels of the used
  expiries (plus "delayed"); `coverage`: the frame's.

Order of results (IO contract section 8 item 7, R-131, R-136, R-137): structural codes of the request list first (the
S09 validator on the parameters, merged with the frame's own code by position), then the history read's codes, then
upstream reasons (no_eligible_contract when no contract is eligible, then the output's items in order), then
`no_prior_reading` (empty store or no reading) / `insufficient_history` (fewer than n), then `zero_denominator`, then
the threshold.

Performance (M3A-B4, owner goal): O(expiries) arithmetic per call, one S09 parameter validation, one store read;
no Fraction on the common value path (integers; a Fraction only for a non-integral threshold or a prior text with more than 8 decimals).
"""
import re
from fractions import Fraction

from .m3a_common import Result, UNITS, units_text
from .m3a_history import scalar_baseline
from .m3a_validate import REQUEST_LIST, validate_request
from .tenors import tenors as _tenor_kernel

OUTPUT_V4, OUTPUT_V7, OUTPUT_V10 = "M3A-3", "M3A-6", "M3A-9"

_FIRST = {}
for _i, _slot in enumerate(REQUEST_LIST):
    for _j, _c in enumerate(_slot):
        _FIRST.setdefault(_c, (_i, _j))
_DECIMAL = re.compile(r"-?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)\Z", re.ASCII).match
_NAME = {"up": "at_least", "down": "at_most", "either": "x"}
_DEFAULT = {OUTPUT_V4: ("up", 10), OUTPUT_V7: ("either", 2), OUTPUT_V10: ("either", 2)}
_MT = "malformed_type"
_PCT_SCALE = 10 ** 6                      # ratio units (10^-8) to percent: percent = units / 10^6


class _Bad(Exception):
    """Internal: a caller value the output cannot read; becomes invalid_input with `code`."""

    def __init__(self, code=_MT):
        self.code = code


# ---- integer helpers ---------------------------------------------------------------------------------------------

def _rdiv(n, d):
    """round_half_even(n / d) for ints, d != 0."""
    if d < 0:
        n, d = -n, -d
    q, r = divmod(n, d)
    r += r
    if r > d or (r == d and q & 1):
        q += 1
    return q


def _frac_units(fr):
    """round_half_even(fr x 10^8) for a Fraction."""
    return _rdiv(fr.numerator * UNITS, fr.denominator)


def _units(x):
    """round_half_even(x x 10^8) of a binary64 (exact: integer arithmetic on its ratio); anything but a finite float
    is a caller error."""
    if x.__class__ is not float:
        raise _Bad()
    n, d = x.as_integer_ratio()                 # ValueError / OverflowError for nan, inf: caught by the caller
    return _rdiv(n * UNITS, d)


def _diff_units(a, b):
    """round_half_even((a - b) x 10^8) of the EXACT difference of two binary64 values (no float subtraction)."""
    if a.__class__ is not float or b.__class__ is not float:
        raise _Bad()
    na, da = a.as_integer_ratio()
    nb, db = b.as_integer_ratio()
    return _rdiv((na * db - nb * da) * UNITS, da * db)


def _sign(u):
    return (u > 0) - (u < 0)


def _fires(direction, x, thr):
    """Inclusive rule on rounded decimals: up x >= thr, down x <= -thr (R-133), either |x| >= thr."""
    if direction == "up":
        return x >= thr
    if direction == "down":
        return x <= -thr
    return x >= thr or x <= -thr


def _level(v):
    """A threshold value (int, Fraction or decimal text) as an exact number (an int when the text is whole), else a
    caller error."""
    t = v.__class__
    if t is int or t is Fraction:
        return v
    if t is str and _DECIMAL(v) is not None:
        return int(v) if v.isdigit() else Fraction(v)
    raise _Bad()


def _text_units(v):
    """round_half_even(decimal text x 10^8) as an int; the text already matched the decimal grammar. Whole
    arithmetic when the text has at most 8 decimals (no Fraction); None otherwise."""
    neg = v[:1] == "-"
    if neg:
        v = v[1:]
    ip, _, fp = v.partition(".")
    if len(fp) > 8:
        return None
    u = int(ip or 0) * UNITS + int(fp + "0" * (8 - len(fp)))
    return -u if neg else u


# ---- structural -------------------------------------------------------------------------------------------------

def _rank(code):
    return _FIRST.get(code, (99, 0))


def _structural(oid, cutoff_ns, params, frame):
    """First failing code of the request list over the parameters (S09 `validate_request` with no contracts: the chain
    codes at positions 6 to 9 and 11 belong to the frame), merged with the frame's own code by position and slot."""
    code = validate_request(oid, (), "1", 0, 0, cutoff_ns, params)
    fcode = None
    if frame is not None and frame.status == "invalid_input":
        fcode = frame.code
    if fcode is None:
        return code
    if code is None or _rank(fcode) <= _rank(code):
        return fcode
    return code


def _reading_units(rec, want_kind=None):
    """(kind, units) of a supplied prior reading: a dict {kind, value, ...}; value text / int / Fraction / finite
    float, rounded half-even to 10^-8."""
    if rec.__class__ is not dict:
        raise _Bad()
    kind = rec.get("kind")
    if kind.__class__ is not str or (kind != "frame" and kind != "session"):
        raise _Bad()
    v = rec.get("value")
    t = v.__class__
    if t is str:
        if _DECIMAL(v) is None:
            raise _Bad()
        u = _text_units(v)
        if u is None:
            u = _frac_units(Fraction(v))
    elif t is int:
        u = v * UNITS
    elif t is Fraction:
        u = _frac_units(v)
    elif t is float:
        u = _frac_units(Fraction(v))                 # ValueError / OverflowError for nan, inf
    else:
        raise _Bad()
    return kind, u


def _threshold(p, direction, default):
    """(echo key, echo value, exact threshold) of the rule for `direction`."""
    name = _NAME[direction]
    v = p.get(name)
    if v is None:
        return name, str(default), default
    return name, (str(v) if v.__class__ is Fraction else v), _level(v)


def _labels(frame, floats, days, delayed):
    """Model labels of the expiries `days` (those the output used); the frame's labels when the floats carry none."""
    fl = floats["expiries"]
    out = []
    for d in days:
        item = fl[str(d)]
        ls = item.get("labels")
        if ls is not None:
            out.extend(ls)
            continue
        lab = item.get("label")
        if lab is None:
            out = list(frame.labels)
            break
        out.append(lab)
    if delayed:
        out.append("delayed")
    return out


def _cov(frame):
    """A copy of the frame coverage (the result never aliases the frame's dicts)."""
    c = frame.coverage
    if c.__class__ is not dict:
        return c
    out = dict(c)
    pe = c.get("per_expiry")
    if pe.__class__ is dict:
        out["per_expiry"] = {k: dict(v) if v.__class__ is dict else v for k, v in pe.items()}
    cr = c.get("contract_reasons")
    if cr.__class__ is dict:
        out["contract_reasons"] = dict(cr)
    return out


def _eligible_none(frame):
    cov = frame.coverage
    return cov is not None and cov["eligible_strikes"] == 0


def _ordered(items):
    return sorted(items, key=int)


# ---- V4 ---------------------------------------------------------------------------------------------------------

def _v4_now(frame, floats, form):
    """(float, used days, None) or (None, None, reason)."""
    fx = frame.frame["expiries"]
    if form == "30d":
        t = frame.frame["tenors"]["30"]
        if t["status"] != "available":
            return None, None, t["reason"]
        return floats["tenors"]["30"], t["expiries_used"], None
    low = None
    for d in _ordered(fx):
        e = fx[d]
        if e["status"] == "available":
            return floats["expiries"][d]["atm_iv"], (int(d),), None
        if e["reason"] == "low_surface_coverage":
            low = low or e["reason"]
            continue
        return None, None, e["reason"]
    return None, None, low or "no_eligible_contract"


def _iv_change(frame, floats, cutoff_ns, p):
    oid = OUTPUT_V4
    form = p.get("iv_form", "atm")
    direction, default = _DEFAULT[oid][0], _DEFAULT[oid][1]
    direction = p.get("direction", direction)
    tname, tval, thr = _threshold(p, direction, default)
    rec = p.get("prior")
    kind = u_prior = None
    if rec is not None:
        kind, u_prior = _reading_units(rec)
    delayed = p.get("feed_delay_tag", "live") == "delayed"
    echo = {"direction": direction, "feed_delay_tag": "delayed" if delayed else "live", "iv_form": form,
            "lane": p.get("lane", "stock"), "mode": p.get("mode", "intraday"), tname: tval}
    echo = {k: echo[k] for k in sorted(echo)}
    lane = echo["lane"]
    sid = None
    if _eligible_none(frame):
        return Result.unavailable(oid, sid, None, cutoff_ns, "no_eligible_contract", params=echo,
                                  coverage=_cov(frame), lane=lane)
    now, used, why = _v4_now(frame, floats, form)
    if why is not None:
        return Result.unavailable(oid, sid, None, cutoff_ns, why, params=echo, coverage=_cov(frame), lane=lane)
    u_now = _units(now)
    if rec is None:
        return Result.unavailable(oid, sid, None, cutoff_ns, "no_prior_reading", params=echo,
                                  coverage=_cov(frame), lane=lane)
    if u_prior == 0:
        return Result.unavailable(oid, sid, None, cutoff_ns, "zero_denominator", params=echo,
                                  coverage=_cov(frame), lane=lane)
    change = u_now - u_prior
    ratio = _rdiv(change * UNITS, u_prior)
    value = {"iv_form": form, "now": units_text(u_now), "prior": units_text(u_prior),
             "change_points": units_text(change * 100), "change_ratio": units_text(ratio), "prior_kind": kind}
    fired = _fires(direction, ratio, thr * _PCT_SCALE)
    return Result.available(oid, sid, None, cutoff_ns, value, fired, echo, _cov(frame),
                            _labels(frame, floats, used, delayed), lane)


# ---- store read (V7, V10) ----------------------------------------------------------------------------------------

def _get(p, name, default):
    """A parameter, its default when absent or None (a None that S09 does not reject: prior_sessions, prior_kind,
    condition)."""
    v = p.get(name)
    return default if v is None else v


def _prior_sessions(p):
    return _get(p, "prior_sessions", 1)


def _read_priors(store, series_id, session_id, n, lane, conv):
    """(code, reason, values, sessions): the last n scalar closes before session_id. The status of the read is
    checked before any value is used (R-192): invalid_input -> code; unavailable -> no_prior_reading (n 0, an empty
    store, R-136) or insufficient_history (fewer than n); available -> values ascending."""
    if store is None:
        return None, "no_prior_reading", None, None
    if series_id.__class__ is not str:
        raise _Bad()
    metric = series_id.rpartition("/")[2]
    if conv is None:
        r = scalar_baseline(store, series_id, metric, session_id, n, n, lane)
    else:
        r = scalar_baseline(store, series_id, metric, session_id, n, n, lane, delta_convention=conv)
    if r.status == "invalid_input":
        return r.code, None, None, None
    if r.status != "available":
        return None, ("no_prior_reading" if r.value["n"] == 0 else "insufficient_history"), None, None
    return None, None, r.value["values"], r.value["sessions"]


def _priors_list(values, sessions):
    """Most recent first: [{session_id, gap}]."""
    return [{"session_id": s, "gap": units_text(v)} for s, v in zip(reversed(sessions), reversed(values))]


# ---- V7 ---------------------------------------------------------------------------------------------------------

def _gap_change(frame, floats, cutoff_ns, p, store, series_id, session_id):
    oid = OUTPUT_V7
    n = _prior_sessions(p)
    direction = p.get("direction", _DEFAULT[oid][0])
    tname, tval, thr = _threshold(p, direction, _DEFAULT[oid][1])
    delayed = p.get("feed_delay_tag", "live") == "delayed"
    lane = p.get("lane", "stock")
    echo = {"direction": direction, "feed_delay_tag": "delayed" if delayed else "live", "lane": lane,
            "mode": p.get("mode", "intraday"), "prior_sessions": n, tname: tval}
    echo = {k: echo[k] for k in sorted(echo)}
    sid = series_id if series_id.__class__ is str else None
    code, reason, values, sessions = _read_priors(store, series_id, session_id, n, lane, None)
    if code is not None:
        return Result.invalid(oid, code, sid, session_id, cutoff_ns, None, lane)
    cov = _cov(frame)
    if _eligible_none(frame):
        reason = "no_eligible_contract"
    else:
        ft = frame.frame["tenors"]
        for t in ("30", "91"):
            if ft[t]["status"] != "available":
                reason = ft[t]["reason"]
                break
    if reason is not None:
        return Result.unavailable(oid, sid, session_id, cutoff_ns, reason, params=echo, coverage=cov, lane=lane)
    fl = floats["tenors"]
    u_now = _diff_units(fl["91"], fl["30"])
    change = (u_now - values[0]) * 100
    value = {"now": units_text(u_now), "priors": _priors_list(values, sessions), "gap_change_points": units_text(change)}
    used = list(ft["30"]["expiries_used"]) + list(ft["91"]["expiries_used"])
    return Result.available(oid, sid, session_id, cutoff_ns, value, _fires(direction, change, thr * UNITS), echo, cov,
                            _labels(frame, floats, used, delayed), lane)


# ---- V10 --------------------------------------------------------------------------------------------------------

def _side_records(frame, floats):
    """Per-expiry records of the put and call 25-delta IVs for the tenor kernel: (days, status, reason, iv)."""
    fx, fl = frame.frame["expiries"], floats["expiries"]
    put, call = [], []
    for d in _ordered(fx):
        e, days = fx[d], int(d)
        if e["status"] != "available":
            rec = (days, "unavailable", e["reason"], None)
            put.append(rec)
            call.append(rec)
            continue
        item = fl[d]
        for key, out in (("put25_iv", put), ("call25_iv", call)):
            s = e[key]
            if s["status"] == "available":
                out.append((days, "available", None, item[key]))
            else:
                out.append((days, "unavailable", s["reason"], None))
    return put, call


def _skew_change(frame, floats, cutoff_ns, p, store, series_id, session_id):
    oid = OUTPUT_V10
    n = _prior_sessions(p)
    conv = p.get("delta_convention", "spot")
    kind = _get(p, "prior_kind", "frame")
    cond = _get(p, "condition", "change")
    direction = p.get("direction", _DEFAULT[oid][0])
    tname, tval, thr = _threshold(p, direction, _DEFAULT[oid][1])
    delayed = p.get("feed_delay_tag", "live") == "delayed"
    lane = p.get("lane", "stock")
    echo = {"condition": cond, "delta_convention": conv, "direction": direction,
            "feed_delay_tag": "delayed" if delayed else "live", "lane": lane, "mode": p.get("mode", "intraday"),
            "prior_kind": kind, "prior_sessions": n, tname: tval}
    echo = {k: echo[k] for k in sorted(echo)}
    sid = series_id if series_id.__class__ is str else None
    fparams = frame.params
    if fparams.__class__ is dict and fparams.get("delta_convention", conv) != conv:
        return Result.invalid(oid, "convention_mismatch", sid, session_id, cutoff_ns, None, lane)
    values = sessions = None
    u_prior = None
    reason = None
    if kind == "session":
        code, reason, values, sessions = _read_priors(store, series_id, session_id, n, lane, conv)
        if code is not None:
            return Result.invalid(oid, code, sid, session_id, cutoff_ns, None, lane)
    else:
        rec = p.get("prior")
        if rec is None:
            reason = "no_prior_reading"
        else:
            u_prior = _reading_units(rec)[1]
    cov = _cov(frame)
    used = ()
    if _eligible_none(frame):
        upstream = "no_eligible_contract"
    else:
        precs, crecs = _side_records(frame, floats)
        tp = _tenor_kernel(precs, (30,))[30]
        tc = _tenor_kernel(crecs, (30,))[30]
        upstream = (tp.reason if tp.status != "available" else tc.reason if tc.status != "available" else None)
        if upstream is None:
            used = tuple(tp.expiries_used) + tuple(tc.expiries_used)
    if upstream is not None:
        reason = upstream
    if reason is not None:
        return Result.unavailable(oid, sid, session_id, cutoff_ns, reason, params=echo, coverage=cov, lane=lane)
    u_now = _diff_units(tp.iv, tc.iv)
    if kind == "session":
        u_prior = values[0]
        priors = _priors_list(values, sessions)
    else:
        priors = []
    change = (u_now - u_prior) * 100
    s_now, s_prior = _sign(u_now), _sign(u_prior)
    changed = s_now * s_prior < 0
    value = {"now": units_text(u_now), "priors": priors, "change_points": units_text(change), "sign_now": s_now,
             "sign_prior": s_prior, "sign_changed": changed, "delta_convention": conv}
    fired = changed if cond == "sign_change" else _fires(direction, change, thr * UNITS)
    return Result.available(oid, sid, session_id, cutoff_ns, value, fired, echo, cov,
                            _labels(frame, floats, used, delayed), lane)


# ---- public calls -------------------------------------------------------------------------------------------------

def _guard(oid, frame, floats, cutoff_ns, params, store, series_id, session_id, run):
    """Structural first; then `run`; a value the output cannot read is malformed_type; never an exception."""
    p = params if params.__class__ is dict else None
    sid = series_id if series_id.__class__ is str else None
    ev = cutoff_ns if cutoff_ns.__class__ is int else None
    lane = "stock"
    try:
        if frame.__class__ is not Result:
            return Result.invalid(oid, _MT, sid, session_id if session_id.__class__ is str else None, ev, None, lane)
        code = _structural(oid, cutoff_ns, params, frame)
        if p is not None and p.get("lane").__class__ is str:
            lane = p["lane"]
        if code is not None:
            return Result.invalid(oid, code, sid, session_id if session_id.__class__ is str else None, ev, None, lane)
        if p is None or floats.__class__ is not dict or frame.frame.__class__ is not dict:
            return Result.invalid(oid, _MT, sid, session_id if session_id.__class__ is str else None, ev, None, lane)
        return run(frame, floats, cutoff_ns, p) if store is _NO_STORE else run(frame, floats, cutoff_ns, p, store,
                                                                              series_id, session_id)
    except _Bad as exc:
        return Result.invalid(oid, exc.code, sid, session_id if session_id.__class__ is str else None, ev, None, lane)
    except Exception:
        return Result.invalid(oid, _MT, sid, session_id if session_id.__class__ is str else None, ev, None, lane)


_NO_STORE = object()


def iv_change(frame, floats, cutoff_ns, params):
    return _guard(OUTPUT_V4, frame, floats, cutoff_ns, params, _NO_STORE, None, None, _iv_change)


def gap_change(frame, floats, cutoff_ns, params, store=None, series_id=None, session_id=None):
    return _guard(OUTPUT_V7, frame, floats, cutoff_ns, params, store, series_id, session_id, _gap_change)


def skew_change(frame, floats, cutoff_ns, params, store=None, series_id=None, session_id=None):
    return _guard(OUTPUT_V10, frame, floats, cutoff_ns, params, store, series_id, session_id, _skew_change)
