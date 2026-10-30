"""M3a common (story S01): closed reason and code sets, number forms and rounding, the M3a result envelope.

Pure and single-threaded; no I/O, no clocks, no solver. Used by every other M3a story.

Number forms (docs/m3a/M3A_IO_CONTRACT.md section 3, RULED):
  * solver-derived values are binary64 floats internally and half-even 8-decimal STRINGS in a result;
  * the stored history form is an integer in 10^-8 units (R-48), `UNITS` = 10**8;
  * one rounding only: derived values (skew25, term_30_91, points) are rounded ONCE from the exact binary64 difference of
    the unrounded inputs, never from rounded parts; rounding is exact (integer arithmetic on the binary64 value, no
    float multiplication), half to even;
  * quote-derived exact values (counts, coverage ratios, shares) are ints or reduced "n/d" strings (`ratio_text`).

Records returned (plain, no hidden state):
  round_units(x) -> int (10^-8 units); units_text(u) -> "-12.34000000"; round_text(x) -> text;
  skew_units(put, call) -> int; skew_points_units(put, call) -> int (points = 100 x difference, one rounding, R-181);
  ratio_text(n, d) -> int | "n/d"; sort_labels(iterable) -> sorted unique list (R-132);
  params_echo(params, names) -> dict of the named parameters, defaults filled, keys sorted (R-154, R-158, R-184);
  Result (slots: output_id, series_id, session_id, evaluation_ns, status, reason, code, value, fired, params, coverage,
          labels, lane, frame) with constructors available / unavailable / invalid;
  canonical_line(result) -> str; canonical_bytes(results) -> bytes.

Canonical form (IO contract section 6): one compact ASCII JSON object per result in KEY_ORDER, LF between lines, results
ordered by (output_id, series_id, session_id, evaluation_ns). `frame` (M3A-0 only, docs/decisions/2026-10-30-m3a-s01.md)
sits directly after `value` and is omitted when None, so every other output keeps exactly the key list of section 3.
Nested dicts keep the producer's insertion order (as M2); producers build them in the contract key order. The `version`
is the library version string.
"""
import json

from . import __version__

UNITS = 10 ** 8

# docs/m3a/M3A_CAPABILITY_MATRIX.md section 5 (closed; a new reason needs a PO ruling). `insufficient_window` is not used.
SURFACE_REASONS = (
    "no_atm_strike", "no_bracketing_expiry",
    "price_out_of_bounds", "upper_asymptote", "sigma_cap", "precision_exhausted", "bound_precision", "iteration_budget",
    "insufficient_history", "session_not_complete", "zero_denominator",
    "no_eligible_contract", "no_delta_bracket", "low_surface_coverage", "fewer_than_two_expiries", "no_prior_reading",
    "zero_range_history",
)
# per-contract M1 gate reasons: they exclude a contract and are counted in coverage.contract_reasons; never a result reason
CONTRACT_REASONS = ("no_quote", "excluded_condition", "invalid_quote", "crossed_market", "locked_market", "stale_quote",
                    "american_itm", "style_unknown")
# structural codes (IO contract section 4): request list (22 distinct codes), history append/load, snapshot, text load,
# view read. `invalid_param` is NOT a code (contract-codes decision 2026-10-30).
CODES = (
    "bad_cutoff", "bad_spot", "bad_rate", "invalid_mode", "invalid_lane", "bad_expiry", "unknown_right",
    "duplicate_contract", "bad_strike", "malformed_type", "cutoff_mismatch", "tenor_not_allowed", "delta_not_allowed",
    "iv_form_not_allowed", "convention_not_allowed", "threshold_required", "threshold_out_of_range",
    "invalid_direction", "minute_out_of_range", "prior_not_before_cutoff", "convention_mismatch", "delayed_feed_tag",
    "lane_mismatch", "session_not_in_calendar", "record_length_mismatch", "non_monotone_grid", "duplicate_session",
    "out_of_order_append",
    "snapshot_bad_magic", "snapshot_length_mismatch", "snapshot_hash_mismatch",
    "trailer_missing", "trailer_count_mismatch", "trailer_hash_mismatch",
    "invalid_session_window",
)
STATUSES = ("available", "unavailable", "invalid_input")
KEY_ORDER = ("output_id", "series_id", "session_id", "evaluation_ns", "status", "reason", "code", "value", "fired",
             "params", "coverage", "labels", "lane", "version")

# ruled defaults (matrix section 4 and IO contract section 2); every parameter USED is echoed with its default filled
DEFAULTS = {"mode": "intraday", "lane": "stock", "stale_limit_ns": 10 * 10 ** 9, "iv_form": "atm",
            "delta_convention": "spot", "delta_target": 0.25, "min_sessions": 20, "max_sessions": 252,
            "prior_sessions": 1}

_REASONS = frozenset(SURFACE_REASONS)
_CODES = frozenset(CODES)
_STATUSES = frozenset(STATUSES)


# ---- rounding ---------------------------------------------------------------------------------------------------

def round_scaled_units(x, scale):
    """round_half_even(x * scale * 10^8) as an int, exact for the binary64 (or int) `x` and an int `scale` >= 1.

    Integer arithmetic on x.as_integer_ratio(): no float product, no Fraction, no Decimal object."""
    t = type(x)
    if t is float:
        try:
            n, d = x.as_integer_ratio()
        except OverflowError:
            raise ValueError("non-finite value") from None
        except ValueError:
            raise ValueError("non-finite value") from None
    elif t is int:
        n, d = x, 1
    else:
        raise TypeError("expected float or int, got " + t.__name__)
    q, r = divmod(n * scale * UNITS, d)          # d > 0: floor division, 0 <= r < d
    r2 = r + r
    if r2 > d or (r2 == d and q & 1):
        q += 1
    return q


def round_units(x):
    """Half-even rounding of a binary64 (or int) to 10^-8 units (the stored integer form)."""
    return round_scaled_units(x, 1)


def units_text(u):
    """Decimal text with exactly 8 places from integer 10^-8 units; zero has no sign."""
    if u < 0:
        u = -u
        return "-%d.%08d" % divmod(u, UNITS)
    return "%d.%08d" % divmod(u, UNITS)


def round_text(x):
    return units_text(round_units(x))


def skew_units(put, call):
    """Derived series value (skew25, term_30_91 and kin): the difference of the UNROUNDED inputs, rounded once."""
    return round_units(put - call)


def skew_points_units(put, call):
    """Points (1 point = 0.01 annual vol): full precision x100, then one rounding (R-181)."""
    return round_scaled_units(put - call, 100)


def ratio_text(n, d):
    """Exact quote-derived ratio: an int when integral, else the reduced "n/d" string (d >= 1)."""
    if d < 1:
        raise ValueError("denominator must be >= 1")
    if n % d == 0:
        return n // d
    a, b = n, d
    while b:
        a, b = b, a % b
    a = abs(a)
    return "%d/%d" % (n // a, d // a)


def sort_labels(labels):
    """Lexicographic ASCII sort of the distinct labels, including "delayed" (R-132)."""
    return sorted(set(labels))


def params_echo(params, names):
    """The parameters USED, with defaults filled, keys sorted. A name with neither a value nor a default is omitted."""
    out = {}
    for k in sorted(names):
        if k in params:
            out[k] = params[k]
        elif k in DEFAULTS:
            out[k] = DEFAULTS[k]
    return out


# ---- envelope ---------------------------------------------------------------------------------------------------

class Result:
    """One M3a result. `value`, `params`, `coverage`, `frame` are dicts (or None) of already-formed wire values."""
    __slots__ = ("output_id", "series_id", "session_id", "evaluation_ns", "status", "reason", "code", "value", "fired",
                 "params", "coverage", "labels", "lane", "frame")

    def __init__(self, output_id, series_id, session_id, evaluation_ns, status, reason=None, code=None, value=None,
                 fired=None, params=None, coverage=None, labels=None, lane="stock", frame=None):
        if status not in _STATUSES:
            raise ValueError("unknown status: %r" % (status,))
        if reason is not None and reason not in _REASONS:
            raise ValueError("reason outside the closed set: %r" % (reason,))
        if code is not None and code not in _CODES:
            raise ValueError("code outside the closed set: %r" % (code,))
        self.output_id, self.series_id, self.session_id, self.evaluation_ns = output_id, series_id, session_id, evaluation_ns
        self.status, self.reason, self.code, self.value, self.fired = status, reason, code, value, fired
        self.params, self.coverage, self.lane, self.frame = params, coverage, lane, frame
        self.labels = sort_labels(labels) if labels else []

    @classmethod
    def available(cls, output_id, series_id, session_id, evaluation_ns, value, fired=None, params=None, coverage=None,
                  labels=None, lane="stock", frame=None):
        return cls(output_id, series_id, session_id, evaluation_ns, "available", None, None, value, fired, params,
                   coverage, labels, lane, frame)

    @classmethod
    def unavailable(cls, output_id, series_id, session_id, evaluation_ns, reason, params=None, coverage=None,
                    lane="stock", frame=None):
        """value and fired are null and labels is [] (R-105); a frame may still show its per-item values (R-141)."""
        if reason is None:
            raise ValueError("an unavailable result needs a reason")
        return cls(output_id, series_id, session_id, evaluation_ns, "unavailable", reason, None, None, None, params,
                   coverage, None, lane, frame)

    @classmethod
    def invalid(cls, output_id, code, series_id=None, session_id=None, evaluation_ns=None, params=None, lane="stock"):
        if code is None:
            raise ValueError("an invalid_input result needs a code")
        return cls(output_id, series_id, session_id, evaluation_ns, "invalid_input", None, code, None, None, params,
                   None, None, lane, None)

    def __repr__(self):
        return "Result(%s %s %s%s)" % (self.output_id, self.series_id, self.status,
                                       "" if self.reason is None and self.code is None else " " + str(self.reason or self.code))


def _wire(r):
    d = {"output_id": r.output_id, "series_id": r.series_id, "session_id": r.session_id,
         "evaluation_ns": r.evaluation_ns, "status": r.status, "reason": r.reason, "code": r.code, "value": r.value}
    if r.frame is not None:
        d["frame"] = r.frame
    d["fired"] = r.fired
    d["params"] = r.params
    d["coverage"] = r.coverage
    d["labels"] = r.labels
    d["lane"] = r.lane
    d["version"] = __version__
    return d


_dumps = json.JSONEncoder(separators=(",", ":"), ensure_ascii=True).encode


def canonical_line(result):
    return _dumps(_wire(result))


def canonical_bytes(results):
    """Results sorted by (output_id, series_id, session_id, evaluation_ns), one line each, LF; never completion order."""
    order = sorted(results, key=lambda r: (r.output_id, "" if r.series_id is None else r.series_id,
                                           "" if r.session_id is None else r.session_id,
                                           0 if r.evaluation_ns is None else r.evaluation_ns))
    return "".join([_dumps(_wire(r)) + "\n" for r in order]).encode("ascii")
