"""M3a story S05: the surface frame M3A-0 (assembler over chainiv, delta25 and tenors).

Pure and single-threaded: no I/O, clocks, threads or shared state. IV is solved once per chain and cutoff by
`chainiv.IVChain` (certified solver unchanged); this module never solves IV. It calls S03 (`delta25.delta25_point`)
for the 25-delta sides and S04 (`tenors.tenors`) for the constant-maturity tenors.

Calls
    surface_frame(contracts, spot, rate, dividend_yield, cutoff_ns, params=None, chain=None, contract_ivs=None,
                  stats=None) -> m3a_common.Result (output_id "M3A-0")
    expiry_records(...same arguments...) -> [tenors.ExpiryIV(days, status, reason, atm_iv)] ascending by days:
                  the coverage-gated per-expiry inputs of the tenor kernel (also used by tests/m3a/adapt_tenors.py)
    contracts     iterable of chainiv.ChainContract; spot, rate, dividend_yield, cutoff_ns as IO contract section 1
    params        request dict: tenors (default [9, 30, 91]), delta_convention ("spot"), delta_target ("0.25"),
                  min_strikes (4, R-20), min_coverage ("3/5", R-20), stale_limit_ns (10 s), feed_delay_tag ("live"),
                  mode, lane, evaluation_ns (must equal cutoff_ns)
    chain, contract_ivs   optional cache (trusted path, IO contract section 5): an IVChain already built for these
                  contracts and its contract_iv() map. When `chain` is None the inputs are validated in full and
                  the chain is built here. M3A-B1 measures the frame with both supplied.
    stats         optional dict; receives "evaluations" (delta evaluations of the frame, M3A-B12 counter)

Result (IO contract section 8, R-141, R-142): value null; frame = {"expiries": {days: {status, reason, forward,
atm_iv, put25_iv: {status, reason, value}, call25_iv: {...}}}, "tenors": {tenor: {status, reason, iv, method,
expiries_used}}}; IV and forward are half-even 8-decimal text. coverage = {listed_strikes, eligible_strikes,
per_expiry: {days: {listed_strikes, eligible_strikes}}, contract_reasons: {reason: count}}. labels: sorted model
labels of the contracts used (ATM legs and 25-delta bracket strikes) plus "delayed" under a delayed tag; [] when
unavailable (R-105). A structural error is invalid_input with `code` (no frame); this module never raises on
caller data.

Rules
- Contract eligibility: a contract is eligible when chainiv reports it available (M1 gates, style gates and a
  successful solve); otherwise its reason is counted in coverage.contract_reasons (R-109: a solver failure
  excludes that contract only).
- Coverage (R-103, R-20): listed strike = any contract record; eligible strike = at least one eligible contract;
  gate: eligible/listed >= min_coverage, eligible >= min_strikes, and at least 2 eligible strikes per right with
  |K - F| <= 0.1 F (inclusive; exact when r = q). Expiry order (R-104): no_atm_strike, then low_surface_coverage,
  then the ATM leg reason (style_unknown or a solver reason, as chainiv).
- ATM (R-109): the chainiv rule (nearest the forward, ties to the lower strike, chainiv's exact forward compare)
  applied to strikes whose call AND put are both eligible, so a solver failure on an ATM leg moves the ATM strike.
- 25-delta sides (S03) only on available expiries, from the eligible contracts of that right; a side of an
  unavailable expiry carries the expiry reason. A cached IV that is not a finite float >= 0 (a hostile cache; IVChain
  never returns one) excludes that contract everywhere, uncounted, so no NaN or inf reaches a kernel.
- Tenors (S04) from the coverage-gated records: a coverage-excluded expiry counts as no ATM (R-104, R-139, R-178).
- Frame status (R-141) and reason: first failing expiry (ascending); then no_eligible_contract when no contract is
  eligible (R-106; an empty chain); then tenors ascending; then 25-delta sides (expiries ascending, put then call).

Performance (owner goal; M3A-B1 <= 0.1 s, B12 <= 200): one pass over the contracts, one numerical-owner context
for all kernel calls, bracketed kernel search (S03), tenors from the cached ATM IVs (S04). No extra IV solves.
"""
import math
import re
from collections import Counter
from fractions import Fraction

from .arithmetic import numerical_owner
from .chainiv import IVChain, LABEL_APPROX, LABEL_EXACT, _Forward
from .delta25 import delta25_point
from .m3a_common import Result, round_text
from .quotes import SCALE, to_ticks
from .tenors import ExpiryIV, TENORS, tenors as tenor_kernel

OUTPUT_ID = "M3A-0"
LOCAL_DEFAULTS = {"tenors": list(TENORS), "delta_convention": "spot", "delta_target": "0.25", "min_strikes": 4,
                  "min_coverage": "3/5", "stale_limit_ns": 10 * 10 ** 9, "feed_delay_tag": "live", "mode": "intraday",
                  "lane": "stock"}
ECHO = ("delta_convention", "delta_target", "feed_delay_tag", "lane", "min_coverage", "min_strikes", "mode",
        "stale_limit_ns", "tenors")
_PRICE = re.compile(r"-?(\d+(\.\d*)?|\.\d+)\Z", re.ASCII)
_SIDES = (("put", "put25_iv"), ("call", "call25_iv"))


class _Invalid(Exception):
    def __init__(self, code):
        Exception.__init__(self, code)
        self.code = code


# ---------------------------------------------------------------- structural validation (untrusted path)
def _is_int(x):
    return type(x) is int


def _decimal_text_ok(x):
    if not _PRICE.match(x):
        return False
    return len(x.partition(".")[2]) <= 8


def _price_kind(x):
    """'ok' for decimal text (<= 8 places) or a non-bool int, else 'type'."""
    if type(x) is str:
        return "ok" if _decimal_text_ok(x) else "type"
    return "ok" if _is_int(x) else "type"


def _spot_code(s):
    t = type(s)
    if t is str:
        if not _decimal_text_ok(s):
            return "malformed_type"
        return None if Fraction(s) > 0 else "bad_spot"
    if t is int:
        return None if s > 0 else "bad_spot"
    if t is float:
        if not math.isfinite(s):
            return "bad_spot"
        if (Fraction(s) * SCALE).denominator != 1:
            return "malformed_type"
        return None if s > 0 else "bad_spot"
    if t is Fraction:
        if (s * SCALE).denominator != 1:
            return "malformed_type"
        return None if s > 0 else "bad_spot"
    return "malformed_type"


def _rate_value(x):
    t = type(x)
    if t is str:
        if not _PRICE.match(x):
            raise _Invalid("malformed_type")
        return float(Fraction(x))
    if t is int or t is float or t is Fraction:
        return float(x)
    raise _Invalid("malformed_type")


def _validate(contracts, spot, rate, dividend_yield, cutoff_ns, p):
    """First failing code of IO contract section 4 (request list) for the fields this frame reads, else None."""
    if not _is_int(cutoff_ns):
        return "malformed_type"
    if cutoff_ns < 0:
        return "bad_cutoff"
    code = _spot_code(spot)
    if code:
        return code
    try:
        r, q = _rate_value(rate), _rate_value(dividend_yield)
    except (_Invalid, OverflowError, ZeroDivisionError) as exc:
        return getattr(exc, "code", "malformed_type")
    if not (math.isfinite(r) and abs(r) <= 1 and math.isfinite(q) and 0 <= q <= 1):
        return "bad_rate"
    for key, allowed, value_code in (("mode", ("intraday", "close"), "invalid_mode"),
                                     ("lane", ("stock", "etf_index"), "invalid_lane")):
        v = p[key]
        if type(v) is not str:
            return "malformed_type"
        if v not in allowed:
            return value_code
    for c in contracts:                                                  # 6 bad_expiry (type-first)
        if not _is_int(c.expiry_days):
            return "malformed_type"
        if c.expiry_days < 1:
            return "bad_expiry"
    for c in contracts:                                                  # 7 unknown_right
        if type(c.right) is not str:
            return "malformed_type"
        if c.right not in ("call", "put"):
            return "unknown_right"
    ids = set()
    for c in contracts:                                                  # 8 duplicate id
        try:
            if c.contract_id in ids:
                return "duplicate_contract"
            ids.add(c.contract_id)
        except TypeError:
            return "malformed_type"
    for c in contracts:                                                  # 9 bad_strike
        if _price_kind(c.strike) != "ok":
            return "malformed_type"
        if Fraction(c.strike) <= 0:
            return "bad_strike"
    for c in contracts:                                                  # 10 malformed_type
        for x in (c.bid, c.ask):
            if x is not None and _price_kind(x) != "ok":
                return "malformed_type"
        if not _is_int(c.event_ns) or not (c.known_at_ns is None or _is_int(c.known_at_ns)):
            return "malformed_type"
        if type(c.condition) is not str:      # any style value is accepted: not european/american = style_unknown
            return "malformed_type"
    for key in ("stale_limit_ns", "min_strikes"):
        if not _is_int(p[key]) or p[key] < 0:
            return "malformed_type"
    if type(p["min_coverage"]) is not str or not re.fullmatch(r"\d+/[1-9]\d*", p["min_coverage"], re.ASCII):
        return "malformed_type"
    if type(p["feed_delay_tag"]) is not str or type(p["tenors"]) not in (list, tuple):
        return "malformed_type"
    if any(not _is_int(t) for t in p["tenors"]):
        return "malformed_type"
    ev = p.get("evaluation_ns")
    if ev is not None:
        if not _is_int(ev):
            return "malformed_type"
        if ev != cutoff_ns:
            return "cutoff_mismatch"
    seen = set()
    for c in contracts:                                                  # 11 duplicate expiry, strike, right
        key = (c.expiry_days, Fraction(c.strike), c.right)
        if key in seen:
            return "duplicate_contract"
        seen.add(key)
    dt = p["delta_target"]                                               # 13
    if type(dt) is str:
        if not _PRICE.match(dt):
            return "malformed_type"
        if Fraction(dt) != Fraction(1, 4):
            return "delta_not_allowed"
    elif type(dt) in (float, Fraction):
        if dt != 0.25:
            return "delta_not_allowed"
    else:
        return "malformed_type"
    conv = p["delta_convention"]
    if type(conv) is not str:
        return "malformed_type"
    if conv not in ("spot", "forward"):
        return "convention_not_allowed"
    return None


# ---------------------------------------------------------------- assembly
def _params(params):
    p = dict(LOCAL_DEFAULTS)
    if params:
        p.update(params)
    return p


def _usable_iv(x):
    return type(x) is float and math.isfinite(x) and x >= 0.0


class _Expiry:
    __slots__ = ("days", "listed", "eligible", "legs", "labels", "status", "reason", "fwd", "atm_strike", "atm_iv",
                 "atm_label")

    def __init__(self, days):
        self.days = days
        self.listed = set()                     # strike ticks with any record
        self.eligible = {}                      # strike ticks -> [call ContractIV or None, put ContractIV or None]
        self.legs = {"put": [], "call": []}     # (strike Fraction, iv float or None) of eligible contracts
        self.labels = {}                        # (strike Fraction, right) -> model label
        self.status = self.reason = self.fwd = self.atm_strike = self.atm_iv = self.atm_label = None


def _assemble(contracts, spot, rate, dividend_yield, cutoff_ns, p, chain, contract_ivs):
    if contract_ivs is None:
        if chain is None:
            chain = IVChain(contracts, spot, rate, dividend_yield, cutoff_ns, p["stale_limit_ns"])
        contract_ivs = chain.contract_iv()
    expiries = {}
    reasons = Counter()
    any_eligible = False
    for c in contracts:
        e = expiries.get(c.expiry_days)
        if e is None:
            e = expiries[c.expiry_days] = _Expiry(c.expiry_days)
        kt = to_ticks(c.strike)
        e.listed.add(kt)
        got = contract_ivs[c.contract_id]
        if got.status == "available":
            if not _usable_iv(got.iv):          # hostile cache (never from IVChain): excluded, no closed reason
                continue
            any_eligible = True
            slot = e.eligible.get(kt)
            if slot is None:
                slot = e.eligible[kt] = [None, None]
            k = Fraction(kt, SCALE)
            if c.right == "call":
                slot[0] = got
            else:
                slot[1] = got
            e.legs[c.right].append((k, got.iv))
            e.labels[(k, c.right)] = got.label
        else:
            reasons[got.reason] += 1
    s_ticks = to_ticks(spot)
    S = Fraction(s_ticks, SCALE)
    r_x, q_x = Fraction.from_float(float(rate)), Fraction.from_float(float(dividend_yield))
    num, den = (int(x) for x in p["min_coverage"].split("/"))
    order = sorted(expiries)
    for d in order:
        e = expiries[d]
        e.fwd = _Forward(s_ticks, (r_x - q_x) * Fraction(d, 365))
        for legs in e.legs.values():
            legs.sort(key=_first)
        # ATM (chainiv rule on the ELIGIBLE legs, R-109): nearest the forward among strikes whose call and put are
        # both available (gates, style and solve), ties to the lower strike
        both = sorted(k for k, (ci, pi) in e.eligible.items() if ci is not None and pi is not None)
        if not both:
            e.status, e.reason = "unavailable", "no_atm_strike"
        elif not _covered(e, num, den, p["min_strikes"]):
            e.status, e.reason = "unavailable", "low_surface_coverage"
        else:
            kt = e.fwd.nearest(both)
            ci, pi = e.eligible[kt]
            e.status = "available"
            e.atm_strike = Fraction(kt, SCALE)
            e.atm_iv = (ci.iv + pi.iv) / 2
            e.atm_label = LABEL_APPROX if LABEL_APPROX in (ci.label, pi.label) else LABEL_EXACT
    return [expiries[d] for d in order], reasons, any_eligible, S, r_x, q_x


def _first(x):
    return x[0]


def _covered(e, num, den, min_strikes):
    n_el, n_li = len(e.eligible), len(e.listed)
    if n_el * den < num * n_li or n_el < min_strikes:
        return False
    fwd = e.fwd
    for side in (0, 1):
        near = 0
        for kt, slot in e.eligible.items():
            # |K - F| <= 0.1 F  <=>  10 K - 9 F >= 0 and 10 K - 11 F <= 0 (exact comparisons of chainiv)
            if slot[side] is not None and fwd.cmp(10 * kt, 9) >= 0 and fwd.cmp(10 * kt, 11) <= 0:
                near += 1
                if near >= 2:
                    break
        if near < 2:
            return False
    return True


def _records(exps):
    return [ExpiryIV(e.days, e.status, e.reason, e.atm_iv) for e in exps]


def expiry_records(contracts, spot, rate, dividend_yield, cutoff_ns, params=None, chain=None, contract_ivs=None):
    """Coverage-gated per-expiry tenor inputs; raises ValueError on a structural error (callers that need the
    never-raise contract use surface_frame)."""
    contracts = list(contracts)
    p = _params(params)
    if chain is None:
        code = _validate(contracts, spot, rate, dividend_yield, cutoff_ns, p)
        if code:
            raise ValueError(code)
    return _records(_assemble(contracts, spot, rate, dividend_yield, cutoff_ns, p, chain, contract_ivs)[0])


def _side(status, reason, value):
    return {"status": status, "reason": reason, "value": value}


def surface_frame(contracts, spot, rate, dividend_yield, cutoff_ns, params=None, chain=None, contract_ivs=None,
                  stats=None):
    p = _params(params)
    echo = {k: p[k] for k in sorted(ECHO)}
    lane = p["lane"] if type(p["lane"]) is str else None
    ev = p.get("evaluation_ns", cutoff_ns)
    try:
        contracts = list(contracts)
    except TypeError:
        return Result.invalid(OUTPUT_ID, "malformed_type", evaluation_ns=ev, params=echo, lane=lane)
    if chain is None:
        try:
            code = _validate(contracts, spot, rate, dividend_yield, cutoff_ns, p)
        except (TypeError, ValueError, ArithmeticError, AttributeError):
            code = "malformed_type"
        if code:
            return Result.invalid(OUTPUT_ID, code, evaluation_ns=ev, params=echo, lane=lane)
    try:
        exps, reasons, any_eligible, S, r_x, q_x = _assemble(contracts, spot, rate, dividend_yield, cutoff_ns, p,
                                                             chain, contract_ivs)
    except (TypeError, ValueError, ArithmeticError, AttributeError, KeyError):
        return Result.invalid(OUTPUT_ID, "malformed_type", evaluation_ns=ev, params=echo, lane=lane)
    conv = p["delta_convention"]
    evaluations = 0
    labels = set()
    frame_exp = {}
    side_fail = None
    with numerical_owner() as owner:
        for e in exps:
            item = {"status": e.status, "reason": e.reason, "forward": round_text(e.fwd.value()),
                    "atm_iv": None, "put25_iv": None, "call25_iv": None}
            if e.status == "available":
                item["atm_iv"] = round_text(e.atm_iv)
                labels.add(e.atm_label)
                for right, key in _SIDES:
                    legs = e.legs[right]
                    pt = delta25_point([k for k, _ in legs], [s for _, s in legs], e.atm_strike, S, r_x, q_x, e.days,
                                       right, conv, owner)
                    evaluations += pt["evaluations"]
                    if pt["status"] == "available":
                        item[key] = _side("available", None, round_text(pt["value"]))
                        for k in pt["strikes_used"]:
                            labels.add(e.labels[(k, right)])
                    else:
                        item[key] = _side("unavailable", pt["reason"], None)
                        if side_fail is None:
                            side_fail = pt["reason"]
            else:
                item["put25_iv"] = _side("unavailable", e.reason, None)
                item["call25_iv"] = _side("unavailable", e.reason, None)
            frame_exp[str(e.days)] = item
    targets = sorted(set(p["tenors"]))
    ten = tenor_kernel(_records(exps), targets)
    frame_ten = {}
    tenor_fail = None
    for t in targets:
        r = ten[t]
        frame_ten[str(t)] = {"status": r.status, "reason": r.reason, "iv": None if r.iv is None else round_text(r.iv),
                             "method": r.method,
                             "expiries_used": None if r.expiries_used is None else list(r.expiries_used)}
        if r.status != "available" and tenor_fail is None:
            tenor_fail = r.reason
    if stats is not None:
        stats["evaluations"] = evaluations
    coverage = {"listed_strikes": sum(len(e.listed) for e in exps),
                "eligible_strikes": sum(len(e.eligible) for e in exps),
                "per_expiry": {str(e.days): {"listed_strikes": len(e.listed), "eligible_strikes": len(e.eligible)}
                               for e in exps},
                "contract_reasons": dict(sorted(reasons.items()))}
    frame = {"expiries": frame_exp, "tenors": frame_ten}
    reason = next((e.reason for e in exps if e.status != "available"), None)
    if reason is None and not any_eligible:
        reason = "no_eligible_contract"
    if reason is None:
        reason = tenor_fail or side_fail
    if reason is not None:
        return Result.unavailable(OUTPUT_ID, None, None, ev, reason, params=echo, coverage=coverage, lane=lane,
                                  frame=frame)
    if p["feed_delay_tag"] == "delayed":
        labels.add("delayed")
    return Result.available(OUTPUT_ID, None, None, ev, None, params=echo, coverage=coverage, labels=labels,
                            lane=lane, frame=frame)
