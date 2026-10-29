"""Option-native contracts; imports only Python standard-library code."""
from .records import (
    Right, Origin, Status, InputBinding, CivilDateBinding, Definition, Spot,
    ModelFact, Quote, SuppliedMetric, Trade, CoverageCertificate,
    QuoteCoverageWindow, ActivityWindow, Snapshot, Eligibility, SolverConfig,
    AdmissionLimits, R25_LIMITS, Request, Coverage, ConvertedOperands,
    PriceEnclosure, SolverEvidence, Result,
)
from .validation import (
    ContractValidationError, validate_limits, validate_record,
    validate_snapshot, validate_request, validate_results,
)
from .canonical import (
    to_payload, from_payload, canonical_bytes, content_digest, record_digest,
    decimal_text,
)
from .schema import OUTPUT_UNITS, SUPPLIED_OUTPUTS

__version__ = "0.2.0a1"
