"""Closed immutable records for option-flow-canonical1.

Constructors never coerce values. Validation is explicit at the pure boundary.
"""
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class FlowRational:
    numerator: int
    denominator: int


@dataclass(frozen=True, slots=True)
class FlowLimits:
    max_wire_bytes: int = 16777216
    max_records: int = 100000
    max_groups: int = 128
    max_streams: int = 128
    max_baselines_per_group: int = 32
    max_outputs: int = 64
    max_result_rows: int = 8192
    max_replay_cuts: int = 128
    max_integer_digits: int = 256


FLOW_LIMITS = FlowLimits()


@dataclass(frozen=True, slots=True)
class FlowBinding:
    binding_id: str
    source_id: str
    source_revision: str
    source_content_sha256: str
    provenance_mode: str
    rights_reference: str


@dataclass(frozen=True, slots=True)
class FlowReference:
    reference_id: str
    contract_id: str
    underlying_id: str
    currency: str
    action_basis_id: str
    right: str
    strike: Decimal
    multiplier: Decimal
    expiry_ordinal: int
    civil_ordinal: int | None
    civil_instant_ns: int | None
    civil_known_at_ns: int | None
    calendar_id: str | None
    calendar_revision: str | None
    spot: Decimal | None
    spot_event_ns: int | None
    spot_known_at_ns: int | None
    spot_stream_id: str | None
    spot_position: int | None
    effective_from_ns: int
    effective_to_ns: int | None
    known_at_ns: int
    revision_id: str
    input_binding_id: str


@dataclass(frozen=True, slots=True)
class FlowExecution:
    execution_id: str
    revision_id: str
    kind: str
    target_execution_id: str | None
    target_revision_id: str | None
    contract_id: str
    session_id: str
    stream_id: str
    position: int
    event_ns: int
    signing_boundary_ns: int
    known_at_ns: int
    price: Decimal | None
    quantity: int | None
    condition: str
    venue_id: str | None
    observed_side: str
    observed_side_semantics_id: str | None
    observed_side_known_at_ns: int | None
    reference_id: str
    input_binding_id: str


@dataclass(frozen=True, slots=True)
class FlowQuote:
    quote_id: str
    revision_id: str
    kind: str
    target_quote_id: str | None
    target_revision_id: str | None
    contract_id: str
    stream_id: str
    position: int
    event_ns: int
    known_at_ns: int
    bid: Decimal | None
    ask: Decimal | None
    condition: str
    input_binding_id: str


@dataclass(frozen=True, slots=True)
class FlowGroup:
    group_id: str
    kind: str
    underlying_id: str
    contract_ids: tuple[str, ...]
    right: str | None
    expiry_ordinal: int | None
    currency: str
    action_basis_id: str


@dataclass(frozen=True, slots=True)
class FlowPopulation:
    population_id: str
    group_id: str
    window_start_ns: int
    window_end_ns: int
    expected_contract_ids: tuple[str, ...]
    expected_execution_ids: tuple[str, ...]
    expected_quote_ids: tuple[str, ...]
    complete: bool
    known_at_ns: int
    input_binding_id: str


@dataclass(frozen=True, slots=True)
class FlowContextCertificate:
    certificate_id: str
    kind: str
    contract_id: str
    session_id: str
    stream_id: str
    session_start_ns: int
    through_position: int
    expected_root_ids: tuple[str, ...]
    complete: bool
    known_at_ns: int
    input_binding_id: str


@dataclass(frozen=True, slots=True)
class FlowBaseline:
    baseline_id: str
    group_id: str
    slot_id: str
    session_ordinal: int
    horizon_id: str
    window_start_ns: int
    window_end_ns: int
    known_at_ns: int
    policy_sha256: str
    population_sha256: str
    currency: str
    action_basis_id: str
    contracts: FlowRational | None
    trade_count: FlowRational | None
    premium: FlowRational | None
    member_record_sha256s: tuple[str, ...]
    complete: bool
    input_binding_id: str


@dataclass(frozen=True, slots=True)
class FlowCursor:
    stream_id: str
    max_position: int


@dataclass(frozen=True, slots=True)
class FlowSnapshot:
    schema_version: str
    bindings: tuple[FlowBinding, ...]
    references: tuple[FlowReference, ...]
    executions: tuple[FlowExecution, ...]
    quotes: tuple[FlowQuote, ...]
    groups: tuple[FlowGroup, ...]
    populations: tuple[FlowPopulation, ...]
    context_certificates: tuple[FlowContextCertificate, ...]
    baselines: tuple[FlowBaseline, ...]
    cursors: tuple[FlowCursor, ...]


@dataclass(frozen=True, slots=True)
class FlowPolicy:
    schema_version: str
    temporal_profile: str
    signing_profile: str
    max_quote_age_ns: int
    max_spot_age_ns: int
    short_dte_max_days: int
    cluster_max_adjacent_gap_ns: int
    horizon_id: str
    minimum_matched_prior_windows: int


@dataclass(frozen=True, slots=True)
class FlowBaselineTarget:
    group_id: str
    slot_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FlowRequest:
    schema_version: str
    group_ids: tuple[str, ...]
    output_ids: tuple[str, ...]
    window_start_ns: int
    window_end_ns: int
    knowledge_cutoff_ns: int
    target_session_ordinal: int
    policy: FlowPolicy
    baseline_targets: tuple[FlowBaselineTarget, ...]
    cut_cursors: tuple[FlowCursor, ...]
    formula_version: str
    limits: FlowLimits


@dataclass(frozen=True, slots=True)
class FlowCoverage:
    population_id: str | None
    population_complete: bool
    expected_count: int | None
    observed_count: int
    eligible_count: int
    signed_count: int
    unknown_sign_count: int
    dte_eligible_count: int
    otm_eligible_count: int


@dataclass(frozen=True, slots=True)
class FlowSignWitness:
    execution_id: str
    revision_id: str
    sign: str
    method: str
    reason: str
    diagnostics: tuple[str, ...]
    signing_boundary_ns: int
    context_sha256: str
    context_certificate_id: str | None
    quote_id: str | None
    quote_revision_id: str | None
    predecessor_execution_id: str | None
    predecessor_revision_id: str | None


@dataclass(frozen=True, slots=True)
class FlowOperand:
    name: str
    value: FlowRational
    unit: str


@dataclass(frozen=True, slots=True)
class FlowPartitionWeight:
    partition_kind: str
    partition_id: str
    premium: FlowRational


@dataclass(frozen=True, slots=True)
class FlowExcluded:
    execution_id: str
    revision_id: str
    reason: str


@dataclass(frozen=True, slots=True)
class FlowCluster:
    cluster_id: str
    profile: str
    contract_id: str
    session_id: str
    quote_id: str
    quote_revision_id: str
    sign: str
    execution_ids: tuple[str, ...]
    execution_revision_ids: tuple[str, ...]
    first_event_ns: int
    last_event_ns: int
    venue_ids: tuple[str, ...]
    unknown_venue_count: int


@dataclass(frozen=True, slots=True)
class FlowEvidence:
    active_execution_ids: tuple[str, ...]
    active_revision_ids: tuple[str, ...]
    exclusions: tuple[FlowExcluded, ...]
    operands: tuple[FlowOperand, ...]
    partition_weights: tuple[FlowPartitionWeight, ...]
    tied_top_ids: tuple[str, ...]
    cluster: FlowCluster | None
    baseline_slot_ids: tuple[str, ...]
    baseline_record_sha256s: tuple[str, ...]
    required_producer_ids: tuple[str, ...]
    diagnostics: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FlowResult:
    schema_version: str
    group_id: str
    output_id: str
    cluster_id: str | None
    window_start_ns: int
    window_end_ns: int
    knowledge_cutoff_ns: int
    available_at_ns: int
    temporal_profile: str
    currency: str
    action_basis_id: str
    origin: str
    value: FlowRational | None
    unit: str
    status: str
    reason: str
    quality_flags: tuple[str, ...]
    coverage: FlowCoverage
    sign_witnesses: tuple[FlowSignWitness, ...]
    evidence: FlowEvidence
    numerator: FlowRational | None
    denominator: FlowRational | None
    baseline_ids: tuple[str, ...]
    dependency_binding_ids: tuple[str, ...]
    dependency_record_sha256s: tuple[str, ...]
    policy_sha256: str
    request_sha256: str
    snapshot_sha256: str
    checkpoint_sha256: str | None
    formula_version: str
    contracts_package_version: str
    calculation_package_version: str


@dataclass(frozen=True, slots=True)
class FlowCheckpoint:
    schema_version: str
    history: FlowSnapshot
    prior_request: FlowRequest
    history_sha256: str
    prior_request_sha256: str
    policy_sha256: str
    formula_version: str


@dataclass(frozen=True, slots=True)
class FlowPublication:
    schema_version: str
    run_key: str
    work_sha256: str
    request: FlowRequest
    request_sha256: str
    snapshot_sha256: str
    cohort_sha256: str
    input_checkpoint_sha256: str | None
    results: tuple[FlowResult, ...]
    bindings: tuple[FlowBinding, ...]
    output_checkpoint: FlowCheckpoint | None


class FlowValidationError(ValueError):
    """Stable boundary error code and JSON pointer; prose is nonnormative."""
    def __init__(self, code: str, path: str):
        self.code, self.path = code, path
        super().__init__(f"{code}: {path}")
