"""option-flow-variants1 contracts: canonical bytes, digests and closed-record validation."""
from .canonical import (
    VariantValidationError, canonical_json, content_digest, record_digest, cohort_digest, work_digest,
    group_id, span_id, context_digest, b2f, f2b, is_bits, bits_finite, b64num, i64num, FORMULA,
)
from .schema import validate_shape, validate_scalars, validate_coherence, RECORDS, UNIONS
