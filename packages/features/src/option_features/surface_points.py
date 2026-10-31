"""M3a story S06: chain point outputs V5, V6, V8, V11, V21 (M3A-4, M3A-5, M3A-7, M3A-10, M3A-11) from a surface frame.

Pure and single-threaded: no I/O, clocks or shared state; never raises on caller data (a structural error is an
`invalid_input` result with a closed code). It never solves IV and never parses frame text: every value is computed
from the unrounded binary64 values S05 exposes in `stats["floats"]` (R-189) and the per-item statuses and reasons of
the frame, then rounded ONCE (half to even, exact integer arithmetic) to 10^-8 units: derived points are
100 x (exact difference of the floats) rounded once (R-48, R-181). All fire decisions use the rounded decimals,
inclusive (R-35).

Calls
    point_output(output_id, contracts, spot, rate, dividend_yield, cutoff_ns, params=None, chain=None,
                 contract_ivs=None, validate="scanned") -> m3a_common.Result
        Validates the request (S09, before any evaluation, R-131), builds the frame (S05) with the tenors the output
        needs, and derives the output. `chain` and `contract_ivs` are the trusted cache of `surface_frame`.
    point_from_frame(output_id, frame, floats, params=None, labels=None) -> Result
        The O(1) step the runner calls once per output on a frame it already has: `frame` is the M3A-0 Result of
        `surface_frame`, `floats` its `stats["floats"]`, `labels` its `stats["labels"]` (the per-expiry model labels,
        so only the expiries an output uses are labelled, R-180), `params` the validated request. Nothing is solved
        or scanned.
    The frame must have been built with the tenors the output reads: V5 [9, 30, 91], V11 and V21 [30]; V6 and V8 read
    only the per-expiry items (use tenors [] to skip the tenor step).

Outputs (IO contract section 3; `value` keys)
    M3A-4  V5   pairs {"9_30", "30_91": {longer, shorter, spread_points}}, longer minus shorter. The request `pair`
                ("9-30" default, "30-91") selects the pair that decides availability and fire; each pair that is
                available is shown.
    M3A-5  V6   nearest_days, second_days, spread_points: the nearest and second ELIGIBLE expiries (available items:
                an expiry without an ATM strike or failing coverage is skipped, R-32), second minus nearest.
    M3A-7  V8   put25_iv, call25_iv, skew_points (put minus call), tenor 30: each side is the constant-maturity
                value at 30 days of the per-expiry 25-delta IVs by linear total variance PER SIDE (R-28).
    M3A-10 V11  wings_mid = (put25 + call25) / 2 at 30 days, atm_iv (the 30-day tenor), curvature_points.
    M3A-11 V21  put_distance, call_distance (points: side minus ATM IV, x100, rounded once), ratio = put / call
                distance, as the exact ratio of the unrounded distances rounded once; a call distance that rounds to 0 is
                zero_denominator (R-38).
    `delta_convention` is echoed in `params` (R-184), V8 to V21 only.

Fire rules (R-35, R-84, R-133, R-36): `direction` in {up (default), down, either}; the threshold key follows the
direction: up `at_least`, down `at_most`, either `x`. Points forms: up fires at value >= thr, down at value <= -thr,
either at |value| >= thr; defaults 3 points (V5, V6, V11) and 5 (V8). V21 compares the ratio itself: up at ratio >=
thr, down at ratio <= thr (R-133), either at |ratio| >= thr; it has no default (threshold_required, S09, R-116).

Failure precedence (R-106, R-137, R-162): structural codes first; then no_eligible_contract when no contract of the
chain is eligible (a frame-level reason wins over every output-level count); then the output's own items: V5 the
shorter tenor, then the longer; V6 fewer_than_two_expiries; V8 the put side, then the call side; V11 and V21 the ATM
tenor, then the put side, then the call side; then zero_denominator (V21). A coverage-excluded bracketing expiry gives
no_bracketing_expiry and a bracketing expiry without a 25-delta bracket gives no_delta_bracket (R-139, R-178, the
tenor kernel).

Performance (M3A-B4: <= 1 ms per name): `point_from_frame` is dictionary lookups, one tenor-kernel call per side and
a few exact integer divisions; no Fraction objects on the hot path.
"""
from fractions import Fraction

from .m3a_common import Result, round_text, units_text
from .m3a_validate import validate_request
from .surfaceframe import surface_frame
from .tenors import ExpiryIV, tenors as _tenor_kernel

_UNITS = 10 ** 8
OUTPUT_IDS = ("M3A-4", "M3A-5", "M3A-7", "M3A-10", "M3A-11")
_DEFAULT_THRESHOLD = {"M3A-4": "3", "M3A-5": "3", "M3A-7": "5", "M3A-10": "3", "M3A-11": None}
_KEY = {"up": "at_least", "down": "at_most", "either": "x"}
_PAIRS = {"9-30": (9, 30, "9_30"), "30-91": (30, 91, "30_91")}
_FRAME_TENORS = {"M3A-4": [9, 30, 91], "M3A-5": [], "M3A-7": [], "M3A-10": [30], "M3A-11": [30]}
_USES_CONVENTION = ("M3A-7", "M3A-10", "M3A-11")
_FRAME_KEYS = ("delta_target", "min_strikes", "min_coverage", "stale_limit_ns", "feed_delay_tag", "mode", "lane",
               "evaluation_ns")


# ---------------------------------------------------------------------------------------------------- exact rounding
def _round_div(num, den):
    """round_half_even(num / den) for an int num and an int den > 0."""
    q, r = divmod(num, den)
    r2 = r + r
    if r2 > den or (r2 == den and q & 1):
        q += 1
    return q


def _diff_points(a, b):
    """round_half_even(100 x 10^8 x (a - b)) of two binary64 floats, exact (integer arithmetic)."""
    na, da = a.as_integer_ratio()
    nb, db = b.as_integer_ratio()
    return _round_div((na * db - nb * da) * (100 * _UNITS), da * db)


def _ratio_frac(a, b):
    na, da = a.as_integer_ratio()
    nb, db = b.as_integer_ratio()
    return Fraction(na, da), Fraction(nb, db)


def _frac_units(f, scale=1):
    return _round_div(f.numerator * scale * _UNITS, f.denominator)


def _fires(direction, value, thr, kind):
    """value: Fraction of the rounded decimal; thr: Fraction; inclusive (R-35)."""
    if direction == "up":
        return value >= thr
    if direction == "down":
        return value <= thr if kind == "ratio" else value <= -thr         # R-133
    return abs(value) >= thr


# ---------------------------------------------------------------------------------------------------- request reading
def _echo(output_id, frame, p, direction, key, thr_text):
    fp = frame.params or {}
    echo = {k: fp[k] for k in ("delta_target", "feed_delay_tag", "lane", "min_coverage", "min_strikes", "mode",
                               "stale_limit_ns") if k in fp}
    if output_id in _USES_CONVENTION:
        echo["delta_convention"] = fp.get("delta_convention", "spot")
    tenors = p.get("tenors")
    echo["tenors"] = list(tenors) if type(tenors) in (list, tuple) else list(_FRAME_TENORS[output_id])
    echo["direction"] = direction
    echo[key] = thr_text
    if output_id == "M3A-4":
        echo["pair"] = p.get("pair", "9-30")
    return {k: echo[k] for k in sorted(echo)}


def _unavailable(output_id, frame, reason, echo):
    return Result.unavailable(output_id, None, None, frame.evaluation_ns, reason, params=echo, coverage=frame.coverage,
                              lane=frame.lane)


# ---------------------------------------------------------------------------------------------------- the outputs
def _sides_cm(frame_exp, float_exp, side_key):
    """Constant-maturity 30-day value of one 25-delta side (R-28): the tenor kernel over the per-expiry items."""
    recs = []
    for d in sorted(frame_exp, key=int):
        item = frame_exp[d]
        side = item.get(side_key) if item.get("status") == "available" else None
        if side is not None and side["status"] == "available":
            recs.append(ExpiryIV(int(d), "available", None, float_exp[d][side_key]))
        else:
            reason = item["reason"] if side is None else side["reason"]
            recs.append(ExpiryIV(int(d), "unavailable", reason, None))
    return _tenor_kernel(recs, (30,))[30]


def _atm_labels(lab, days):
    out = []
    for d in days:
        item = lab.get(str(d))
        if item is not None and item["atm"] is not None:
            out.append(item["atm"])
    return out


def _side_labels(lab, tenor_result, key):
    out = []
    for d in tenor_result.expiries_used or ():
        item = lab.get(str(d))
        if item is not None:
            out.extend(item[key])
    return out


def _v5(frame, floats, p, lab):
    ften = frame.frame["tenors"]
    fl = floats["tenors"]
    pairs = {}
    reasons = {}
    for name, (short, long_, label) in _PAIRS.items():
        ts, tl = ften.get(str(short)), ften.get(str(long_))
        if ts is None or tl is None:
            reasons[name] = "no_bracketing_expiry"
            continue
        bad = ts if ts["status"] != "available" else (tl if tl["status"] != "available" else None)
        if bad is not None:
            reasons[name] = bad["reason"]
            continue
        a, b = fl[str(long_)], fl[str(short)]
        pairs[name] = (label, {"longer": round_text(a), "shorter": round_text(b),
                               "spread_points": units_text(_diff_points(a, b))}, _diff_points(a, b),
                       _atm_labels(lab, (ts["expiries_used"] or []) + (tl["expiries_used"] or [])))
    want = p.get("pair", "9-30")
    if want not in pairs:
        return reasons.get(want, "no_bracketing_expiry"), None
    value = {"pairs": {v[0]: v[1] for v in pairs.values()}}
    return None, (value, pairs[want][2], "pts", [x for v in pairs.values() for x in v[3]])


def _v6(frame, floats, p, lab):
    fe = frame.frame["expiries"]
    avail = sorted([int(d) for d, it in fe.items() if it["status"] == "available"])
    if len(avail) < 2:
        return "fewer_than_two_expiries", None
    n, s = avail[0], avail[1]
    a, b = floats["expiries"][str(s)]["atm_iv"], floats["expiries"][str(n)]["atm_iv"]
    pts = _diff_points(a, b)
    return None, ({"nearest_days": n, "second_days": s, "spread_points": units_text(pts)}, pts, "pts",
                   _atm_labels(lab, (n, s)))


def _sides(frame, floats):
    put = _sides_cm(frame.frame["expiries"], floats["expiries"], "put25_iv")
    call = _sides_cm(frame.frame["expiries"], floats["expiries"], "call25_iv")
    return put, call


def _v8(frame, floats, p, lab):
    put, call = _sides(frame, floats)
    if put.status != "available":
        return put.reason, None
    if call.status != "available":
        return call.reason, None
    pts = _diff_points(put.iv, call.iv)
    return None, ({"put25_iv": round_text(put.iv), "call25_iv": round_text(call.iv), "skew_points": units_text(pts),
                   "tenor": 30}, pts, "pts", _side_labels(lab, put, "put25_iv") + _side_labels(lab, call, "call25_iv"))


def _atm30(frame, floats):
    t = frame.frame["tenors"].get("30")
    if t is None:
        return None, "no_bracketing_expiry", ()
    if t["status"] != "available":
        return None, t["reason"], ()
    return floats["tenors"]["30"], None, t["expiries_used"]


def _v11(frame, floats, p, lab):
    atm, reason, used = _atm30(frame, floats)
    if reason is not None:
        return reason, None
    put, call = _sides(frame, floats)
    if put.status != "available":
        return put.reason, None
    if call.status != "available":
        return call.reason, None
    fp, fc = _ratio_frac(put.iv, call.iv)
    fa = Fraction(*atm.as_integer_ratio())
    mid = (fp + fc) / 2
    pts = _frac_units(mid - fa, 100)
    return None, ({"wings_mid": units_text(_frac_units(mid)), "atm_iv": round_text(atm),
                   "curvature_points": units_text(pts)}, pts, "pts",
                  _atm_labels(lab, used) + _side_labels(lab, put, "put25_iv") + _side_labels(lab, call, "call25_iv"))


def _v21(frame, floats, p, lab):
    atm, reason, used = _atm30(frame, floats)
    if reason is not None:
        return reason, None
    put, call = _sides(frame, floats)
    if put.status != "available":
        return put.reason, None
    if call.status != "available":
        return call.reason, None
    pd = _diff_points(put.iv, atm)
    cd = _diff_points(call.iv, atm)
    if cd == 0:                                 # the call distance is 0 after rounding (R-38)
        return "zero_denominator", None
    # the ratio is the exact ratio of the two unrounded distances, rounded once (R-181): (P - A) / (C - A)
    np_, dp = put.iv.as_integer_ratio()
    nc, dc = call.iv.as_integer_ratio()
    na, da = atm.as_integer_ratio()
    num = (np_ * da - na * dp) * dc
    den = (nc * da - na * dc) * dp
    if den < 0:                                 # _round_div needs a positive denominator
        num, den = -num, -den
    ratio = _round_div(num * _UNITS, den)
    return None, ({"put_distance": units_text(pd), "call_distance": units_text(cd), "ratio": units_text(ratio)},
                  ratio, "ratio",
                  _atm_labels(lab, used) + _side_labels(lab, put, "put25_iv") + _side_labels(lab, call, "call25_iv"))


_COMPUTE = {"M3A-4": _v5, "M3A-5": _v6, "M3A-7": _v8, "M3A-10": _v11, "M3A-11": _v21}


def point_from_frame(output_id, frame, floats, params=None, labels=None):
    if type(output_id) is not str or output_id not in _COMPUTE:
        return Result.invalid(output_id if type(output_id) is str else "M3A-4", "malformed_type")
    try:
        return _point(output_id, frame, floats, params if type(params) is dict else {}, labels)
    except Exception:                           # caller data of an unexpected shape: never raise
        return Result.invalid(output_id, "malformed_type", evaluation_ns=getattr(frame, "evaluation_ns", None))


def _point(output_id, frame, floats, p, labels):
    direction = p.get("direction", "up")
    if direction not in _KEY:
        return Result.invalid(output_id, "invalid_direction", evaluation_ns=frame.evaluation_ns, lane=frame.lane)
    key = _KEY[direction]
    thr_in = p.get(key)
    if thr_in is None:
        thr_in = _DEFAULT_THRESHOLD[output_id]
    if thr_in is None:
        return Result.invalid(output_id, "threshold_required", evaluation_ns=frame.evaluation_ns, lane=frame.lane)
    thr_text = thr_in if type(thr_in) is str else str(thr_in)
    echo = _echo(output_id, frame, p, direction, key, thr_text)
    if frame.status == "invalid_input":
        return Result.invalid(output_id, frame.code, evaluation_ns=frame.evaluation_ns, params=echo, lane=frame.lane)
    cov = frame.coverage or {}
    if cov.get("eligible_strikes", 0) == 0:     # R-106, R-162: a frame-level reason wins over output-level counts
        return _unavailable(output_id, frame, "no_eligible_contract", echo)
    lab = labels or {}
    reason, got = _COMPUTE[output_id](frame, floats, p, lab)
    if reason is not None:
        return _unavailable(output_id, frame, reason, echo)
    value, x_units, kind, used_labels = got
    if echo.get("feed_delay_tag") == "delayed":
        used_labels = used_labels + ["delayed"]
    thr = Fraction(thr_in)
    fired = bool(_fires(direction, Fraction(x_units, _UNITS), thr, kind))
    return Result.available(output_id, None, None, frame.evaluation_ns, value, fired, echo, frame.coverage,
                            used_labels, frame.lane)


def point_output(output_id, contracts, spot, rate, dividend_yield, cutoff_ns, params=None, chain=None,
                 contract_ivs=None, validate="scanned"):
    p = params if type(params) is dict else ({} if params is None else params)
    if type(output_id) is not str or output_id not in _COMPUTE:
        return Result.invalid(output_id if type(output_id) is str else "M3A-4", "malformed_type",
                              evaluation_ns=cutoff_ns if type(cutoff_ns) is int else None)
    try:
        contracts = list(contracts)
        code = validate_request(output_id, contracts, spot, rate, dividend_yield, cutoff_ns, p, validate)
    except (TypeError, ValueError, AttributeError):
        code = "malformed_type"
    oid = output_id if output_id in _COMPUTE else "M3A-4"
    if code is not None:
        ev = p.get("evaluation_ns", cutoff_ns) if type(p) is dict else cutoff_ns
        return Result.invalid(oid, code, evaluation_ns=ev if type(ev) is int else None)
    fp = {k: p[k] for k in _FRAME_KEYS if k in p}
    fp["tenors"] = list(_FRAME_TENORS[output_id])
    if output_id in _USES_CONVENTION and "delta_convention" in p:
        fp["delta_convention"] = p["delta_convention"]
    stats = {}
    frame = surface_frame(contracts, spot, rate, dividend_yield, cutoff_ns, fp, chain, contract_ivs, stats)
    return point_from_frame(output_id, frame, stats.get("floats"), p, stats.get("labels"))
