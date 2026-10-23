"""option-flow-variants1 canonical JSON, digests and binary64 bit helpers.

Pure standard-library code. Records are validated JSON-compatible dicts whose
integer wire-string fields are already in their canonical decimal form.
"""
import hashlib
import json
import math
import struct

SCHEMA_CANONICAL = "option-flow-variants-canonical1"
SCHEMA_REQUEST = "option-flow-variants-request1"
SCHEMA_RESULT = "option-flow-variants-result1"
SCHEMA_CHECKPOINT = "option-flow-variants-checkpoint1"
SCHEMA_JSON = "option-flow-variants-json1"
SCHEMA_GENERATION = "option-flow-variants-generation1"
SCHEMA_COHORT = "option-flow-variants-cohort1"
SCHEMA_PRODUCERS = "option-flow-variants-producers1"
FORMULA = "option-flow-variants1"

I64_MAX = 9223372036854775807
I64_MIN = -9223372036854775808


class VariantValidationError(Exception):
    """Closed validation error: code and RFC6901 path; stage is informational."""

    def __init__(self, code, path, stage=None):
        super().__init__("%s at %s" % (code, path))
        self.code = code
        self.path = path
        self.stage = stage


def fail(code, path, stage=None):
    raise VariantValidationError(code, path, stage)


def canonical_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(domain, record_type, payload):
    head = domain + "\n" + ((record_type + "\n") if record_type else "")
    return hashlib.sha256(head.encode("utf-8") + canonical_json(payload)).hexdigest()


def content_digest(record_type, payload):
    return _digest("option-flow-variants-json1", record_type, payload)


def record_digest(record_type, payload):
    return _digest("option-flow-variants-record1", record_type, payload)


def cohort_digest(cohort):
    return _digest("option-flow-variants-cohort1", None, cohort)


def work_digest(snapshot_record_hash, request_record_hash, cohort_hash, input_checkpoint_record_hash):
    return _digest("option-flow-variants-work1", None,
                   [snapshot_record_hash, request_record_hash, cohort_hash, input_checkpoint_record_hash])


def group_id(op_id, scope_id, kind, parent_anchor_id, subset_start_id, price_ticks, price_scale, side,
             policy_record_hash, money_basis):
    return _digest("option-flow-variants-group1", None,
                   [op_id, scope_id, kind, parent_anchor_id, subset_start_id, price_ticks, price_scale, side,
                    policy_record_hash, money_basis])


def span_id(op_id, scope_id, anchor_id, asof_control_id, policy_record_hash):
    return _digest("option-flow-variants-span1", None, [op_id, scope_id, anchor_id, asof_control_id, policy_record_hash])


def context_digest(root_id, a_ns, policy_record_hash, ordered_record_hashes):
    return _digest("option-flow-variants-context1", None, [root_id, a_ns, policy_record_hash, list(ordered_record_hashes)])


# ---- binary64 bit helpers -------------------------------------------------

def is_bits(text):
    if type(text) is not str or len(text) != 16:
        return False
    return all(c in "0123456789abcdef" for c in text)


def bits_finite(text):
    return ((int(text, 16) >> 52) & 0x7FF) != 0x7FF


def b2f(text):
    return struct.unpack(">d", bytes.fromhex(text))[0]


def f2b(value):
    if not math.isfinite(value):
        raise ArithmeticError("nonfinite")
    return struct.pack(">d", value).hex()


def is_neg_zero(value):
    return value == 0 and math.copysign(1.0, value) < 0


def b64num(value):
    return {"bits": f2b(value), "kind": "b64"}


def i64num(value):
    return {"integer": str(value), "kind": "i64"}
