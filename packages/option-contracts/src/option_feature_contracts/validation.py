"""Atomic structural admission; economic faults remain evaluator outcomes."""
from decimal import Decimal
import math
import json
import re
import unicodedata
from . import records as r
from .schema import BY_NAME, FIELDS, IDENTITY_FIELDS, OUTPUT_UNITS, SUPPLIED_OUTPUTS, REASONS_BY_STATUS

class ContractValidationError(ValueError):
    def __init__(self, path: str, code: str, message: str):
        self.path, self.code, self.message = path, code, message
        super().__init__(f"{path}: {code}: {message}")

def fail(path, code, message):
    raise ContractValidationError(path, code, message)

def validate_limits(limits=r.R25_LIMITS):
    if type(limits) is not r.AdmissionLimits:
        fail("/limits", "type_mismatch", "AdmissionLimits required")
    for name, _ in FIELDS[r.AdmissionLimits]:
        value = getattr(limits, name)
        if type(value) is not int:
            fail("/limits/" + name, "type_mismatch", "integer required")
        if not 0 < value <= getattr(r.R25_LIMITS, name):
            fail("/limits/" + name, "admission_limit_exceeded", "positive lowered limit required")

def scalar(value, descriptor, path, field=""):
    if descriptor.startswith("="):
        scalar(value, "s", path, field)
        if value not in descriptor[1:].split(","):
            fail(path, "unknown_enum", "unrecognized enum value")
        return
    expected = {"s": str, "h": str, "c": str, "d": Decimal, "f": float, "i": int, "n": int, "o": int, "b": bool}[descriptor]
    if type(value) is not expected:
        fail(path, "type_mismatch", "exact declared scalar type required")
    if expected is str:
        if not value or len(value) > 1024:
            fail(path, "out_of_range", "nonempty bounded text required")
        try:
            size = len(value.encode("utf-8"))
        except UnicodeEncodeError:
            fail(path, "out_of_range", "invalid Unicode scalar")
        if size > 1024 or any(unicodedata.category(c) == "Cc" for c in value):
            fail(path, "out_of_range", "invalid or oversized text")
        if (field.endswith(("_id", "_ids", "_revision", "_version")) or field in {"revision_id", "quality_flags"}) and len(value) > 256:
            fail(path, "out_of_range", "identifier exceeds 256 characters")
        if descriptor == "h" and re.fullmatch("[0-9a-f]{64}", value) is None:
            fail(path, "out_of_range", "lowercase SHA256 required")
        if descriptor == "c" and re.fullmatch("[A-Z]{3}", value) is None:
            fail(path, "out_of_range", "uppercase three-letter currency required")
    elif expected is Decimal:
        if not value.is_finite():
            fail(path, "nonfinite", "finite Decimal required")
        parts = value.as_tuple()
        if len(parts.digits) > 128 or abs(parts.exponent) > 1024:
            fail(path, "admission_limit_exceeded", "Decimal coefficient/exponent exceeds bounds")
        if any(parts.digits):
            digits = len(parts.digits)
            exponent = parts.exponent
            while digits > 1 and parts.digits[digits-1] == 0:
                digits -= 1
                exponent += 1
            if exponent >= 0:
                length = digits + exponent
            else:
                length = digits + 1 if digits + exponent > 0 else 2 - exponent
            if length + parts.sign > 1024:
                fail(path, "admission_limit_exceeded", "projected Decimal wire text exceeds string ceiling")
    elif expected is float:
        if not math.isfinite(value):
            fail(path, "nonfinite", "finite binary64 required")
    elif expected is int:
        low, high = (1, 3652059) if descriptor == "o" else ((0, 2**63-1) if descriptor == "n" else (-(2**63), 2**63-1))
        if not low <= value <= high:
            fail(path, "out_of_range", "integer outside declared range")

def _walk(value, descriptor, path, budget, field=""):
    """Validate and stream exact canonical byte counts before expansion."""
    def charge(count):
        budget[0] -= count
        if budget[0] < 0:
            fail(path, "admission_limit_exceeded", "canonical byte ceiling")
    if descriptor.startswith("?"):
        if value is None:
            charge(4)
            return
        return _walk(value, descriptor[1:], path, budget, field)
    if descriptor.startswith("[]"):
        if type(value) is not tuple:
            fail(path, "type_mismatch", "tuple required")
        if len(value) > budget[1]:
            fail(path, "admission_limit_exceeded", "collection exceeds record ceiling")
        charge(2 + max(0, len(value)-1))
        for i, item in enumerate(value):
            _walk(item, descriptor[2:], path + "/" + str(i), budget, field)
        return
    if descriptor in BY_NAME:
        cls = BY_NAME[descriptor]
        if type(value) is not cls:
            fail(path, "type_mismatch", "exact canonical record type required")
        charge(2 + max(0, len(FIELDS[cls])-1))
        for name, desc in FIELDS[cls]:
            charge(len(name) + 3)  # ASCII schema key, quotes and colon
            _walk(getattr(value, name), desc, path + "/" + name, budget, name)
        _record_constraints(value, path)
        return
    scalar(value, descriptor, path, field)
    if type(value) is Decimal:
        from .canonical import decimal_text
        encoded_value = decimal_text(value)
    elif type(value) is float and value == 0:
        encoded_value = 0.0
    else:
        encoded_value = value
    charge(len(json.dumps(encoded_value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")))

def _unique(values, path):
    if len(set(values)) != len(values):
        fail(path, "duplicate_identity", "duplicate identity")

def _record_constraints(value, path):
    cls = type(value)
    if cls in (r.Definition, r.ModelFact):
        if value.effective_to_ns is not None and value.effective_to_ns <= value.effective_from_ns:
            fail(path, "invalid_config", "interval end must exceed start")
    if cls is r.ModelFact and value.kind in {"rate", "carry"} and value.contract_id is not None:
        fail(path + "/contract_id", "invalid_config", "rate/carry require explicit underlying scope")
    if cls in (r.CoverageCertificate, r.QuoteCoverageWindow, r.ActivityWindow):
        if value.window_end_ns < value.window_start_ns:
            fail(path, "invalid_config", "window end precedes start")
    if cls is r.AdmissionLimits:
        validate_limits(value)
    if cls is r.SolverConfig:
        if value.max_iterations < 1 or any(x <= 0 for x in (value.max_sigma, value.price_abs_tol, value.price_rel_tol, value.vol_abs_tol, value.vol_rel_tol)):
            fail(path, "invalid_solver_config", "positive solver controls required")
    if cls is r.PriceEnclosure and value.value_low > value.value_high:
        fail(path, "invalid_config", "reversed enclosure")
    if cls is r.Trade and (value.quantity < 0 or value.quantity != value.quantity.to_integral_value()):
        fail(path + "/quantity", "out_of_range", "nonnegative integral contract quantity required")
    if cls is r.Coverage and value.observed > value.expected:
        fail(path, "invalid_config", "observed count exceeds population")
    if cls is r.Result:
        if value.reason not in REASONS_BY_STATUS[value.status]:
            fail(path + "/reason", "unknown_enum", "reason does not belong to frozen status vocabulary")
        if value.output_id not in OUTPUT_UNITS or value.unit != OUTPUT_UNITS[value.output_id]:
            fail(path, "invalid_config", "unknown output or inconsistent unit")
        if (value.status == "available") != (value.value is not None) or (value.status == "available" and value.reason != "ok"):
            fail(path, "invalid_config", "status/value/reason inconsistency")
        for name in ("quality_flags", "dependency_binding_ids", "dependency_record_sha256s"):
            items = getattr(value, name)
            if items != tuple(sorted(set(items))):
                fail(path + "/" + name, "invalid_config", "sorted duplicate-free evidence required")
    for name in {r.CoverageCertificate: ("contract_ids",), r.QuoteCoverageWindow: ("expected_sample_ids",), r.ActivityWindow: ("expected_contract_ids", "trade_ids")}.get(cls, ()):
        _unique(getattr(value, name), path + "/" + name)

def validate_record(value, limits=r.R25_LIMITS):
    validate_limits(limits)
    from .schema import SCHEMAS
    if type(value) not in SCHEMAS:
        fail("", "type_mismatch", "closed canonical record required")
    _walk(value, SCHEMAS[type(value)][0], "", [limits.max_wire_bytes, r.R25_LIMITS.max_snapshot_records])

def validate_snapshot(snapshot, limits=r.R25_LIMITS):
    validate_limits(limits)
    if type(snapshot) is not r.Snapshot:
        fail("", "type_mismatch", "Snapshot required")
    # Counts are checked before sorting, sets, hashing or payload expansion.
    total = 0
    for name, desc in FIELDS[r.Snapshot]:
        value = getattr(snapshot, name)
        if desc.startswith("[]"):
            if type(value) is not tuple:
                fail("/" + name, "type_mismatch", "tuple required")
            total += len(value)
    for window in snapshot.quote_coverage_windows:
        if type(window) is not r.QuoteCoverageWindow or type(window.expected_sample_ids) is not tuple:
            fail("/quote_coverage_windows", "type_mismatch", "typed window required")
        total += len(window.expected_sample_ids)
    for cert in snapshot.coverage_certificates:
        if type(cert) is not r.CoverageCertificate or type(cert.contract_ids) is not tuple:
            fail("/coverage_certificates", "type_mismatch", "typed certificate required")
        total += len(cert.contract_ids)
    if snapshot.activity_window is not None:
        w = snapshot.activity_window
        if type(w) is not r.ActivityWindow or type(w.expected_contract_ids) is not tuple or type(w.trade_ids) is not tuple:
            fail("/activity_window", "type_mismatch", "typed activity window required")
        total += 1 + len(w.expected_contract_ids) + len(w.trade_ids)
    if total > limits.max_snapshot_records:
        fail("", "admission_limit_exceeded", "snapshot record/reference ceiling")
    validate_record(snapshot, limits)
    bindings = {b.binding_id for b in snapshot.bindings}
    for name, desc in FIELDS[r.Snapshot]:
        if not desc.startswith("[]"):
            continue
        rows = getattr(snapshot, name)
        if not rows:
            continue
        names = IDENTITY_FIELDS[type(rows[0])]
        _unique(tuple(tuple(getattr(row, key) for key in names) for row in rows), "/" + name)
        if name != "bindings":
            for i, row in enumerate(rows):
                if row.input_binding_id not in bindings:
                    fail(f"/{name}/{i}/input_binding_id", "missing_binding", "unknown input binding")
    if snapshot.activity_window is not None and snapshot.activity_window.input_binding_id not in bindings:
        fail("/activity_window/input_binding_id", "missing_binding", "unknown input binding")
    certificates = {c.certificate_id: c for c in snapshot.coverage_certificates}
    windows = {w.contract_id: w for w in snapshot.quote_coverage_windows}
    for i, quote in enumerate(snapshot.quotes):
        if quote.sample_id is not None:
            w = windows.get(quote.contract_id)
            if w is None or quote.sample_id not in w.expected_sample_ids or not w.window_start_ns <= quote.event_ns < w.window_end_ns:
                fail(f"/quotes/{i}/sample_id", "invalid_config", "sample requires matching declared slot and event window")
    for i, w in enumerate(snapshot.quote_coverage_windows):
        cert = certificates.get(w.completeness_certificate_id)
        if cert is not None and (cert.kind != "quote_samples" or set(cert.contract_ids) != {w.contract_id} or cert.window_start_ns != w.window_start_ns or cert.window_end_ns != w.window_end_ns):
            fail(f"/quote_coverage_windows/{i}", "invalid_config", "inconsistent existing quote-sample certificate")
    w = snapshot.activity_window
    if w is not None:
        trades = {}
        for trade in snapshot.trades:
            trades.setdefault(trade.trade_id, []).append(trade)
        for trade_id in w.trade_ids:
            if trade_id not in trades or any(t.contract_id not in w.expected_contract_ids for t in trades[trade_id]):
                fail("/activity_window/trade_ids", "invalid_config", "unknown trade or unexpected membership")
        cert = certificates.get(w.trade_completeness_certificate_id)
        if cert is not None and (cert.kind != "trade_events" or set(cert.contract_ids) != set(w.expected_contract_ids) or (cert.window_start_ns, cert.window_end_ns) != (w.window_start_ns, w.window_end_ns)):
            fail("/activity_window", "invalid_config", "inconsistent existing trade certificate")
        cert = certificates.get(w.quote_completeness_certificate_id)
        if cert is not None and (cert.kind != "current_quotes" or set(cert.contract_ids) != set(w.expected_contract_ids) or cert.window_start_ns != cert.window_end_ns):
            fail("/activity_window", "invalid_config", "inconsistent existing current-quotes certificate")

def validate_request(request, limits=r.R25_LIMITS):
    validate_limits(limits)
    if type(request) is not r.Request:
        fail("", "type_mismatch", "Request required")
    validate_limits(request.limits)
    for name in ("contract_ids", "output_ids"):
        values = getattr(request, name)
        if type(values) is not tuple:
            fail("/" + name, "type_mismatch", "tuple required")
        bound = min(getattr(limits, "max_requested_contracts" if name == "contract_ids" else "max_selected_outputs"), getattr(request.limits, "max_requested_contracts" if name == "contract_ids" else "max_selected_outputs"))
        if len(values) > bound:
            fail("/" + name, "admission_limit_exceeded", "request count ceiling")
    from dataclasses import replace
    effective_limits = replace(limits, max_wire_bytes=min(limits.max_wire_bytes, request.limits.max_wire_bytes))
    validate_record(request, effective_limits)
    for name in ("contract_ids", "output_ids"):
        _unique(getattr(request, name), "/" + name)
    if not request.output_ids or any(o not in OUTPUT_UNITS for o in request.output_ids):
        fail("/output_ids", "invalid_config", "known nonempty selected outputs required")
    contract_count = sum(o != "chain.activity" for o in request.output_ids)
    if contract_count and not request.contract_ids:
        fail("/contract_ids", "invalid_config", "contract outputs need contracts")
    rows = len(request.contract_ids) * contract_count + ("chain.activity" in request.output_ids)
    if rows > min(limits.max_result_rows, request.limits.max_result_rows):
        fail("", "admission_limit_exceeded", "predicted result row ceiling")
    if request.solver.max_iterations > min(limits.max_solver_iterations, request.limits.max_solver_iterations):
        fail("/solver/max_iterations", "invalid_solver_config", "solver iteration ceiling")
    if request.origin_policy == "supplied_only" and any(o not in SUPPLIED_OUTPUTS for o in request.output_ids):
        fail("/output_ids", "unsupported_output_origin", "unsupported supplied output")
    if request.supplied_delta_policy == "absolute_from_signed" and (request.origin_policy != "supplied_only" or "greeks.delta" not in request.output_ids):
        fail("/supplied_delta_policy", "unsupported_output_origin", "projection needs supplied absolute delta request")

def validate_results(results, limits=r.R25_LIMITS):
    validate_limits(limits)
    if type(results) is not tuple:
        fail("", "type_mismatch", "result tuple required")
    if len(results) > limits.max_result_rows:
        fail("", "admission_limit_exceeded", "result row ceiling")
    _walk(results, "[]result", "", [limits.max_wire_bytes, max(limits.max_snapshot_records, limits.max_result_rows)])
