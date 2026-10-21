"""Frozen option-canonical1 records. Construction is separate from admission."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Right = Literal["call", "put"]
Origin = Literal["computed", "supplied"]
Status = Literal["available", "unsupported_profile", "invalid_input", "missing_input", "ineligible_input", "not_applicable", "undefined", "nonidentifiable_inverse", "bracket_exceeded", "iteration_limit", "numerical_failure"]

@dataclass(frozen=True, slots=True)
class InputBinding:
    binding_id: str
    source_id: str
    source_revision: str
    source_content_sha256: str
    provenance_mode: Literal["synthetic", "licensed", "public_permitted"]
    rights_reference: str

@dataclass(frozen=True, slots=True)
class CivilDateBinding:
    civil_binding_id: str
    instant_ns: int
    ordinal: int
    timezone_id: str
    known_at_ns: int
    input_binding_id: str

@dataclass(frozen=True, slots=True)
class Definition:
    contract_id: str
    underlying_id: str
    right: Right
    strike: Decimal
    currency: str
    multiplier: Decimal
    deliverable: Literal["scalar_underlying", "adjusted", "basket"]
    action_basis_id: str
    exercise: Literal["european", "american", "bermudan"]
    model_profile_admission: Literal["certified_vanilla_continuous_carry", "unsupported_discrete_dividends", "unsupported_stochastic_or_local", "unsupported_other", "unknown"]
    settlement: Literal["cash", "physical"]
    last_trade_ns: int
    fixing_ns: int
    payment_ns: int
    expiry_ordinal: int
    timezone_id: str
    civil_binding_id: str
    revision_id: str
    effective_from_ns: int
    effective_to_ns: int | None
    known_at_ns: int
    input_binding_id: str

@dataclass(frozen=True, slots=True)
class Spot:
    underlying_id: str
    value: Decimal
    currency: str
    action_basis_id: str
    event_ns: int
    known_at_ns: int
    revision_id: str
    input_binding_id: str

@dataclass(frozen=True, slots=True)
class ModelFact:
    underlying_id: str
    contract_id: str | None
    kind: Literal["rate", "carry", "volatility"]
    value: float
    model_id: str
    currency: str
    action_basis_id: str
    effective_from_ns: int
    effective_to_ns: int | None
    known_at_ns: int
    revision_id: str
    input_binding_id: str

@dataclass(frozen=True, slots=True)
class Quote:
    contract_id: str
    sample_id: str | None
    bid: Decimal | None
    ask: Decimal | None
    currency: str
    price_basis: Literal["per_underlying_payoff_unit"]
    event_ns: int
    known_at_ns: int
    sequence: int
    revision_id: str
    input_binding_id: str

@dataclass(frozen=True, slots=True)
class SuppliedMetric:
    contract_id: str
    output_id: str
    value: float
    unit: str
    producer_model_id: str
    producer_formula_id: str
    event_ns: int
    known_at_ns: int
    revision_id: str
    input_binding_id: str

@dataclass(frozen=True, slots=True)
class Trade:
    trade_id: str
    contract_id: str
    quantity: Decimal
    quantity_unit: Literal["contracts"]
    classification: Literal["regular", "excluded", "cancelled"]
    event_ns: int
    known_at_ns: int
    revision_id: str
    input_binding_id: str

@dataclass(frozen=True, slots=True)
class CoverageCertificate:
    certificate_id: str
    kind: Literal["trade_events", "quote_samples", "current_quotes"]
    contract_ids: tuple[str, ...]
    window_start_ns: int
    window_end_ns: int
    known_at_ns: int
    complete: bool
    input_binding_id: str

@dataclass(frozen=True, slots=True)
class QuoteCoverageWindow:
    contract_id: str
    known_at_ns: int
    window_start_ns: int
    window_end_ns: int
    expected_sample_ids: tuple[str, ...]
    sampling_plan_id: str
    completeness_certificate_id: str
    input_binding_id: str

@dataclass(frozen=True, slots=True)
class ActivityWindow:
    population_id: str
    underlying_id: str
    expected_contract_ids: tuple[str, ...]
    known_at_ns: int
    window_start_ns: int
    window_end_ns: int
    trade_ids: tuple[str, ...]
    trade_rule_id: str
    trade_completeness_certificate_id: str
    quote_completeness_certificate_id: str
    input_binding_id: str

@dataclass(frozen=True, slots=True)
class Snapshot:
    schema_version: Literal["option-canonical1"]
    bindings: tuple[InputBinding, ...]
    civil_bindings: tuple[CivilDateBinding, ...]
    definitions: tuple[Definition, ...]
    spots: tuple[Spot, ...]
    model_facts: tuple[ModelFact, ...]
    quotes: tuple[Quote, ...]
    supplied_metrics: tuple[SuppliedMetric, ...]
    trades: tuple[Trade, ...]
    coverage_certificates: tuple[CoverageCertificate, ...]
    quote_coverage_windows: tuple[QuoteCoverageWindow, ...]
    activity_window: ActivityWindow | None

@dataclass(frozen=True, slots=True)
class Eligibility:
    max_quote_age_ns: int
    max_spot_age_ns: int
    max_supplied_metric_age_ns: int

@dataclass(frozen=True, slots=True)
class SolverConfig:
    method: Literal["bisection1"]
    quote_basis: Literal["midpoint"]
    max_sigma: float
    max_iterations: int
    price_abs_tol: float
    price_rel_tol: float
    vol_abs_tol: float
    vol_rel_tol: float

@dataclass(frozen=True, slots=True)
class AdmissionLimits:
    max_wire_bytes: int
    max_snapshot_records: int
    max_requested_contracts: int
    max_selected_outputs: int
    max_result_rows: int
    max_solver_iterations: int

R25_LIMITS = AdmissionLimits(16777216, 100000, 1000, 32, 32001, 4096)

@dataclass(frozen=True, slots=True)
class Request:
    schema_version: Literal["option-request1"]
    contract_ids: tuple[str, ...]
    output_ids: tuple[str, ...]
    origin_policy: Literal["computed_only", "supplied_only"]
    supplied_delta_policy: Literal["exact_only", "absolute_from_signed"]
    valuation_ns: int
    knowledge_cutoff_ns: int
    valuation_ordinal: int
    civil_binding_id: str
    model_id: Literal["option-bsm1"]
    formula_version: str
    eligibility: Eligibility
    solver: SolverConfig
    limits: AdmissionLimits

@dataclass(frozen=True, slots=True)
class Coverage:
    observed: int
    expected: int
    population_id: str
    population_complete: bool
    sampling: Literal["event_count", "population_member"]

@dataclass(frozen=True, slots=True)
class ConvertedOperands:
    spot: float
    strike: float
    rate: float
    carry: float
    sigma: float | None
    remaining_ns: int
    year_fraction: float

@dataclass(frozen=True, slots=True)
class PriceEnclosure:
    method_id: str
    method_version: str
    value_low: Decimal
    value_high: Decimal

@dataclass(frozen=True, slots=True)
class SolverEvidence:
    iterations: int
    target_price_exact: Decimal
    target_price: float | None
    candidate_sigma: float | None
    candidate_price: float | None
    lower_price_bound: float | None
    upper_price_bound: float | None
    lower_bound_enclosure: PriceEnclosure | None
    upper_bound_enclosure: PriceEnclosure | None
    candidate_price_enclosure: PriceEnclosure | None
    worst_case_price_residual: Decimal | None
    converted_operands: ConvertedOperands | None
    sigma_low: float | None
    sigma_high: float | None
    price_residual: float | None
    solver_config: SolverConfig
    boundary: Literal["none", "lower_boundary", "upper_asymptote", "sigma_cap"]
    vega: float | None
    ill_conditioned: bool | None
    converged: bool

@dataclass(frozen=True, slots=True)
class Result:
    schema_version: Literal["option-result1"]
    contract_id: str | None
    underlying_id: str | None
    output_id: str
    currency: str | None
    action_basis_id: str | None
    origin: Origin
    value: float | None
    unit: str
    status: Status
    reason: str
    quality_flags: tuple[str, ...]
    coverage: Coverage | None
    solver_evidence: SolverEvidence | None
    pricing_evidence: PriceEnclosure | None
    converted_operands: ConvertedOperands | None
    dependency_binding_ids: tuple[str, ...]
    dependency_record_sha256s: tuple[str, ...]
    valuation_ns: int
    knowledge_cutoff_ns: int
    model_id: str
    formula_version: str
    producer_model_id: str | None
    producer_formula_id: str | None
    config_sha256: str
    snapshot_sha256: str
    contracts_package_version: str
    calculation_package_version: str
