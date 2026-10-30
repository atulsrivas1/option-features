"""M2 shared result type, closed sets and canonical serialization (flow completion; library module only, not on the wire).

Pure and single-threaded. Every value is an exact int or `Fraction`; there is no float anywhere in M2. A kernel that
returns results never raises for bad input: it returns a `Result` with status `invalid_input` and a `code`
(structural codes of docs/m2/M2_IO_CONTRACT.md); mutation APIs (store append, window totals) raise
`M2StructuralError` carrying the same code.

Canonical form (I/O contract section 4): one compact JSON object per result in the contract key order, rationals as
reduced "n/d" strings (integers as plain integers), results ordered by (output_id, series_id, session_id,
evaluation_ns), LF between lines. Worker counts, timings, cache statistics and store hashes never enter a result.
"""
from fractions import Fraction
import json

REASONS = ("insufficient_history", "session_not_complete", "insufficient_window", "zero_denominator")
CODES = ("unordered_prints", "negative_size_or_price", "bad_multiplier", "unknown_contract", "malformed_type",
         "grid_not_60s", "duplicate_session", "non_monotone_grid", "session_not_in_calendar", "window_not_allowed",
         "lane_mismatch", "record_length_mismatch", "threshold_required", "out_of_order_append", "delayed_feed_tag",
         "snapshot_bad_magic", "snapshot_length_mismatch", "snapshot_hash_mismatch", "snapshot_byteorder", "trailer_missing",
         "trailer_count_mismatch", "trailer_hash_mismatch")
ALLOWED_WINDOWS = (60, 300, 900, 1800, 3600)
STATUSES = ("available", "unavailable", "invalid_input")
KEY_ORDER = ("output_id", "series_id", "session_id", "evaluation_ns", "status", "reason", "code", "value", "fired",
             "params", "coverage", "label", "per_statistic", "parts_shown", "lane", "version")


class M2StructuralError(ValueError):
    def __init__(self, code, detail=""):
        super().__init__(code + (": " + detail if detail else ""))
        self.code = code


def _version():
    from . import __version__
    return __version__


class Result:
    """One M2 result. `value` holds ints and Fractions (never float); `coverage` is a dict or None."""
    __slots__ = ("output_id", "series_id", "session_id", "evaluation_ns", "status", "reason", "code", "value", "fired",
                 "params", "coverage", "label", "lane", "per_statistic", "parts_shown")

    def __init__(self, output_id, series_id, session_id, evaluation_ns, status, reason=None, code=None, value=None,
                 fired=None, params=None, coverage=None, label=None, lane="stock", per_statistic=None,
                 parts_shown=None):
        self.output_id, self.series_id, self.session_id, self.evaluation_ns = output_id, series_id, session_id, evaluation_ns
        self.status, self.reason, self.code, self.value, self.fired = status, reason, code, value, fired
        self.params, self.coverage, self.label, self.lane = params, coverage, label, lane
        self.per_statistic, self.parts_shown = per_statistic, parts_shown

    @classmethod
    def available(cls, output_id, series_id, session_id, evaluation_ns, value, fired=None, params=None, coverage=None,
                  label=None, lane="stock", per_statistic=None, parts_shown=None):
        return cls(output_id, series_id, session_id, evaluation_ns, "available", None, None, value, fired, params,
                   coverage, label, lane, per_statistic, parts_shown)

    @classmethod
    def unavailable(cls, output_id, series_id, session_id, evaluation_ns, reason, params=None, coverage=None,
                    label=None, lane="stock", per_statistic=None, parts_shown=None):
        return cls(output_id, series_id, session_id, evaluation_ns, "unavailable", reason, None, None, None, params,
                   coverage, label, lane, per_statistic, parts_shown)

    @classmethod
    def invalid(cls, output_id, code, series_id=None, session_id=None, evaluation_ns=None, params=None, lane="stock"):
        return cls(output_id, series_id, session_id, evaluation_ns, "invalid_input", None, code, None, None, params,
                   None, None, lane)

    def __repr__(self):
        return "Result(%s %s %s%s)" % (self.output_id, self.series_id, self.status,
                                       "" if self.reason is None and self.code is None else " " + str(self.reason or self.code))


def show(x):
    """int for an integral value, else the reduced "n/d" string (the wire form of every rational)."""
    if type(x) is int:
        return x
    if isinstance(x, Fraction):
        return int(x) if x.denominator == 1 else "%d/%d" % (x.numerator, x.denominator)
    if isinstance(x, dict):
        return {k: show(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [show(v) for v in x]
    return x


def to_wire(result):
    """Result as a dict in the contract key order, rationals shown; optional blocks only when set."""
    d = {}
    for k in KEY_ORDER:
        if k == "version":
            d[k] = _version()
            continue
        v = getattr(result, k)
        if v is None and k in ("per_statistic", "parts_shown"):
            continue
        d[k] = show(v)
    return d


def canonical_line(result):
    return json.dumps(to_wire(result), separators=(",", ":"), ensure_ascii=True)


def canonical_bytes(results):
    """Results sorted by (output_id, series_id, session_id, evaluation_ns), one canonical line each, LF; never
    completion order."""
    order = sorted(results, key=lambda r: (r.output_id, str(r.series_id), str(r.session_id), r.evaluation_ns or 0))
    return "".join(canonical_line(r) + "\n" for r in order).encode("ascii")
