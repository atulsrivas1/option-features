"""Pure schema-specific canonical content; envelopes belong to option I/O."""
from decimal import Decimal
import hashlib
import json
from . import records as r
from .schema import SCHEMAS, FIELDS, BY_NAME, IDENTITY_FIELDS
from .validation import fail, scalar, validate_record, validate_snapshot, validate_request, validate_results, validate_limits

def decimal_text(value):
    scalar(value, "d", "")
    sign, digits, exponent = value.as_tuple()
    if not any(digits):
        return "0"
    text = "".join(str(d) for d in digits)
    if exponent >= 0:
        text += "0" * exponent
    else:
        split = len(text) + exponent
        text = (text[:split] + "." + text[split:]) if split > 0 else "0." + "0" * (-split) + text
        text = text.rstrip("0").rstrip(".")
    return ("-" if sign else "") + text

def _admit(value, limits):
    if type(value) is r.Snapshot:
        validate_snapshot(value, limits)
    elif type(value) is r.Request:
        validate_request(value, limits)
    elif type(value) is tuple:
        validate_results(value, limits)
    else:
        validate_record(value, limits)

def _sort_key(row):
    return tuple("" if getattr(row, key) is None else getattr(row, key) for key in IDENTITY_FIELDS[type(row)])

def _payload(value):
    cls = type(value)
    if value is None or cls in (str, int, bool):
        return value
    if cls is float:
        return 0.0 if value == 0 else value
    if cls is Decimal:
        return decimal_text(value)
    if cls is tuple:
        return [_payload(x) for x in value]
    # Only literal schema-listed fields are accessed; no reflection discovery.
    result = {}
    for name, desc in FIELDS[cls]:
        item = getattr(value, name)
        if cls is r.Snapshot and desc.startswith("[]"):
            item = tuple(sorted(item, key=_sort_key))
        if name in {"expected_contract_ids", "expected_sample_ids", "trade_ids"} or (cls is r.CoverageCertificate and name == "contract_ids"):
            item = tuple(sorted(item))
        result[name] = _payload(item)
    return result

def to_payload(value, limits=r.R25_LIMITS):
    _admit(value, limits)
    # Admission walks bounded typed records/scalars before any payload expansion.
    return _payload(value)

def canonical_bytes(value, limits=r.R25_LIMITS):
    payload = to_payload(value, limits)
    encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    pieces, count = [], 0
    for chunk in encoder.iterencode(payload):
        encoded = chunk.encode("utf-8")
        count += len(encoded)
        if count > limits.max_wire_bytes:
            fail("", "admission_limit_exceeded", "canonical byte ceiling")
        pieces.append(encoded)
    return b"".join(pieces)

def _check_record_type(record_type, value):
    expected = "results" if type(value) is tuple else SCHEMAS.get(type(value), (None,))[0]
    if record_type != expected:
        fail("", "type_mismatch", "record type does not match value")

def content_digest(record_type, value, limits=r.R25_LIMITS):
    _check_record_type(record_type, value)
    return hashlib.sha256(("option-json1\n" + record_type + "\n").encode("utf-8") + canonical_bytes(value, limits)).hexdigest()

def record_digest(record_type, value, limits=r.R25_LIMITS):
    _check_record_type(record_type, value)
    return hashlib.sha256(("option-record1\n" + record_type + "\n").encode("utf-8") + canonical_bytes(value, limits)).hexdigest()

def _decode(value, descriptor, path, limits):
    if descriptor.startswith("?"):
        return None if value is None else _decode(value, descriptor[1:], path, limits)
    if descriptor.startswith("[]"):
        if type(value) is not list:
            fail(path, "type_mismatch", "JSON array required")
        if len(value) > max(limits.max_snapshot_records, limits.max_result_rows):
            fail(path, "admission_limit_exceeded", "array count ceiling")
        return tuple(_decode(x, descriptor[2:], path + "/" + str(i), limits) for i, x in enumerate(value))
    if descriptor in BY_NAME:
        cls = BY_NAME[descriptor]
        if type(value) is not dict:
            fail(path, "type_mismatch", "JSON object required")
        expected = {name for name, _ in FIELDS[cls]}
        if set(value) != expected:
            fail(path, "unknown_field" if set(value) - expected else "type_mismatch", "exact fields required, including null optionals")
        return cls(*(_decode(value[name], desc, path + "/" + name, limits) for name, desc in FIELDS[cls]))
    if descriptor == "d":
        if type(value) is not str:
            fail(path, "type_mismatch", "canonical Decimal text required")
        if len(value) > 1024:
            fail(path, "admission_limit_exceeded", "Decimal text exceeds bounded expansion")
        try:
            result = Decimal(value)
        except Exception as exc:
            fail(path, "type_mismatch", "invalid Decimal text")
        scalar(result, "d", path)
        if decimal_text(result) != value:
            fail(path, "invalid_config", "noncanonical Decimal text")
        return result
    scalar(value, descriptor, path)
    return value

def from_payload(record_type, payload, limits=r.R25_LIMITS):
    validate_limits(limits)
    if type(record_type) is not str:
        fail("", "type_mismatch", "explicit closed record type text required")
    if record_type != "results" and record_type not in BY_NAME:
        fail("", "unknown_enum", "unknown closed record type")
    if record_type == "results" and type(payload) is list and len(payload) > limits.max_result_rows:
        fail("", "admission_limit_exceeded", "result count ceiling before typed expansion")
    if record_type == "snapshot" and type(payload) is dict:
        count = sum(len(payload[name]) for name, desc in FIELDS[r.Snapshot] if desc.startswith("[]") and type(payload.get(name)) is list)
        if count > limits.max_snapshot_records:
            fail("", "admission_limit_exceeded", "snapshot count ceiling before typed expansion")
        for name, member_field in (("quote_coverage_windows", "expected_sample_ids"), ("coverage_certificates", "contract_ids")):
            for row in payload.get(name, ()) if type(payload.get(name)) is list else ():
                if type(row) is dict and type(row.get(member_field)) is list:
                    count += len(row[member_field])
                    if count > limits.max_snapshot_records:
                        fail("/"+name, "admission_limit_exceeded", "snapshot reference ceiling before typed expansion")
        activity = payload.get("activity_window")
        if type(activity) is dict:
            count += 1
            for name in ("expected_contract_ids", "trade_ids"):
                if type(activity.get(name)) is list:
                    count += len(activity[name])
            if count > limits.max_snapshot_records:
                fail("/activity_window", "admission_limit_exceeded", "snapshot reference ceiling before typed expansion")
    if record_type == "request" and type(payload) is dict:
        for name, ceiling in (("contract_ids", limits.max_requested_contracts), ("output_ids", limits.max_selected_outputs)):
            embedded = payload.get("limits")
            field = "max_requested_contracts" if name == "contract_ids" else "max_selected_outputs"
            if type(embedded) is dict and type(embedded.get(field)) is int:
                ceiling = min(ceiling, embedded[field])
            values = payload.get(name)
            if type(values) is list and len(values) > ceiling:
                fail("/" + name, "admission_limit_exceeded", "request count ceiling before typed expansion")
    value = _decode(payload, "[]result" if record_type == "results" else record_type, "", limits)
    _admit(value, limits)
    return value
