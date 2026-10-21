# R25 option-native boundary proposal

Status: `proposed_for_review`, 2026-10-20, EQ182. This document specifies an original option-owned boundary for review; it is not frozen, implemented, numerically tested or accepted. [Model mathematics](MODEL_PROFILE.md) remain separately owned. This document makes no new formula or source-matrix equivalence claim. Its exact choices replace the open boundary choices in [canonical records](CANONICAL_RECORDS.md) only after independent review and a coordinator-recorded freeze commit.

The option contracts live in `option_feature_contracts`, calculations in `option_features`, conversion/serialization/storage in `option_feature_io`, and orchestration in `option_feature_workers`. Proposed initial distributions are respectively `option-feature-contracts`, `option-features`, `option-feature-io`, and `option-feature-workers`, each independently versioned. Distribution names are proposed local artifact names, not registry availability claims. Python support initially means `>=3.12,<3.13` with exact installed artifacts qualified in EQ187.

Existing equity records, closed codecs, database schemas and worker admission remain unchanged. R25 uses option-owned JSON, a separate option database, and an option-owned bounded execution shell. Supplied spot does not require an equity calculation: install or import an equity dependency only when an actually selected public API is used and independently qualified. Equity packages never import these option packages. I/O and workers call the pure evaluator; they do not reproduce numerical kernels.

## Canonical Python types

The following declarations are normative proposed field names, order and types. They are specification examples, not an implemented module. All dataclasses use `frozen=True, slots=True`; all collections are tuples. No inheritance from, mutation of, or registry additions to equity contracts are permitted. No arbitrary dictionaries, callbacks, datetime objects, implicit timezone conversion or arbitrary Python object deserialization cross this boundary.

```python
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

Right = Literal["call", "put"]
Origin = Literal["computed", "supplied"]
Status = Literal[
    "available", "unsupported_profile", "invalid_input", "missing_input",
    "ineligible_input", "not_applicable", "undefined",
    "nonidentifiable_inverse", "bracket_exceeded", "iteration_limit",
    "numerical_failure",
]

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
    model_profile_admission: Literal[
        "certified_vanilla_continuous_carry", "unsupported_discrete_dividends",
        "unsupported_stochastic_or_local", "unsupported_other", "unknown",
    ]
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
```

The public pure API is `evaluate(snapshot: Snapshot, request: Request) -> tuple[Result, ...]`. It performs no I/O, clock lookup, executor creation or storage writes. Each requested contract yields each selected contract output in `Request.contract_ids` order followed by `Request.output_ids` order. `chain.activity` is the only population output; it follows contract outputs once in request order. An empty `contract_ids` tuple is legal for population-only requests. A contract output with no requested contracts, an empty `output_ids`, duplicate requested identifiers or an unknown output is a boundary error. `contract_id=None` denotes a population output; it is never a substitute instrument ID. Chain outputs use the activity window's underlying ID.

The fixed R25 maximum AdmissionLimits values, in declaration order, are 16777216 bytes (16 MiB), 100000 snapshot records, 1000 requested contracts, 32 selected outputs, 32001 result rows and 4096 solver iterations. Callers may lower these positive integer limits, never raise them without a reviewed contract amendment. Limits are operational admission choices, not measured performance or hard OS memory guarantees. Request content binds its actual limits. Direct validation checks counts before sorting/hashing/evaluation; I/O checks byte limits before JSON parsing. Snapshot record count includes every top-level tuple element plus all expected member/sample/trade-ID references in window records; nesting is fixed by schema. Predicted result rows are contract count times selected contract-output count plus selected population-output count and must fit before evaluation. Solver `max_iterations` must fit the active limit, otherwise `ContractValidationError/invalid_solver_config`. Existing caller-owned tuples/bytes already occupy memory outside worker allocation; limits bound admitted protocol work, not the caller's RSS.

## Scalar and identity validation

Validation rejects bool as int or number, nonfinite floats/Decimals, integers outside signed int64 for UTC nanosecond clocks, and unknown fields or enum values. Integers used for counts and sequence are nonnegative. Civil ordinals are integers 1 through 3652059. Numeric fields require their declared Python type: floats are binary64, exact price/quantity fields are `Decimal`, and implicit int/float/Decimal coercion is forbidden. Finite negative economic values remain structurally representable and receive a per-output economic status where relevant. Interval ends, when present, must exceed starts. Windows must have start <= end. Required strings are nonempty Unicode without control characters; identifiers and revisions are at most 256 characters. Digest strings are lowercase SHA256 hex. Currency is an uppercase three-letter label whose economic/basis correspondence is checked on actual dependencies, not inferred by a symbol lookup.

Before any canonical formatting, expansion, hashing or Decimal arithmetic, reject every string longer than 1024 Unicode scalar values or 1024 UTF-8 bytes (the narrower 256-character identifier/revision rule still applies). Unpaired surrogates are invalid Unicode. Check character length before encoding a large incoming string. Every Decimal's finite coefficient is at most 128 digits and its exponent has absolute value <=1024, checked from its bounded structural representation before formatting it into plain notation. These are fixed serialization/admission limits, not numerical accuracy assurances. Bounds apply to direct Python construction as well as decoded input. Validate all collection/count/scalar limits before global expansion; use a bounded streaming canonical-size pass that aborts at the byte ceiling before materializing a complete canonical payload. Typed Result validation/serialization applies the same scalar bounds, including interval endpoints. Oversize structures raise `admission_limit_exceeded`, never attempt expansion and then claim a memory cap. Caller-owned objects remain outside hard memory control.

`Decimal` values originate from exact strings, never `Decimal(float)`. Conversion to finite positive binary64 where required is explicit inside the numerical boundary; a positive exact decimal that underflows to zero is `numerical_failure/precision_exhausted`, not a valid zero spot. Output rounding belongs in a viewer, not canonical results. Float negative zero is normalized to positive zero when canonicalized; economic observed zero remains a value rather than missingness.

Bindings are uniquely keyed by `binding_id`. Every row/population binding must exist. They name immutable source evidence and rights, and do not contain credentials, file paths or private data. A binding ID is not a digest: source content digests and record digests remain separately checked. Record digests hash the complete typed record content, including clocks, revision and binding. Supplying new clocks or a changed source revision therefore changes content identity.

Duplicate identities are rejected atomically, including an otherwise identical duplicate row. Definition identity is `(contract_id, revision_id)`; spot `(underlying_id, event_ns, revision_id)`; model fact `(underlying_id, contract_id, kind, effective_from_ns, revision_id)`; quote `(contract_id, event_ns, sequence, revision_id)`; supplied metric `(contract_id, output_id, event_ns, revision_id)`; trade `(trade_id, revision_id)`; certificate `certificate_id`; quote window `contract_id`. An identical identity with different values is never resolved by input ordering. Different revisions are retained; ambiguous eligible winners are a boundary error as specified below. Tuples may arrive in any order; canonicalization sorts snapshot rows by the full identity key (null contract ID uses an empty string only in the sort key), bindings/certificates by ID, member/sample/trade-ID sets lexically. Request contract/output order is semantic and preserved. Quality flags, binding IDs and record digests are sorted, duplicate-free tuples.

## Causal selection and admission

The request supplies both valuation and knowledge cutoff. No implicit current time is read. A record is causally usable only if `known_at_ns <= knowledge_cutoff_ns`. Definitions and model facts additionally require `effective_from_ns <= valuation_ns < effective_to_ns`, with null end meaning unbounded. Spot, quote and supplied metric events require `event_ns <= valuation_ns`. A latest revision never makes a future-known record eligible. No constraint requires known-at >= event/effective time: forward-effective facts may legitimately be known beforehand.

For definitions/model facts, select the causal active record with greatest `effective_from_ns`, then greatest `known_at_ns`. For spot/supplied metrics, select greatest eligible `event_ns`, then greatest `known_at_ns`. Quote selection uses greatest `(event_ns, sequence, known_at_ns)`. A tie between distinct revisions at a winning rank is `ContractValidationError/ambiguous_revision`; revision strings are not an invented chronological order. Staleness is checked on the selected latest causal event, not used to fall back to an older value. Excluded future-known records are recorded as exclusion evidence only if no causal candidate exists; they cannot suppress an available causal fact.

Model rates/carries require `contract_id=None`. Volatility may be contract-specific or an explicitly underlying-flat fact. Under the fixed `option-bsm1` selection profile, choose an eligible contract-specific volatility first; only if none is causally active choose an eligible underlying-flat volatility. The chosen record must agree with the definition's underlying/currency/action basis. An invalid chosen specific volatility never falls back to flat volatility. A future-known specific revision cannot hide a causal flat fact. This versioned priority is fixed, not derived from record order. Model fact identities and digests preserve the supplied contract scope.

Spot age, quote age and supplied metric age use valuation minus selected event and the caller's required nonnegative age limit. No default threshold or stale model-fact lifetime is invented: model facts have explicit effective intervals. Definition and spot must agree on actual underlying ID, currency and action basis for computations that consume both. Different option/underlying IDs are preserved throughout. Quotes are exact per-underlying-payoff-unit prices. An adapter converting a quoted per-contract premium must explicitly divide by the declared valid multiplier once and bind its conversion/source evidence; a kernel never guesses quote scale.

For DTE the definition and request civil binding IDs must match; the adapter certifies expiry and valuation ordinals against that immutable binding/timezone. The kernel uses no timezone database. Last trade, fixing and payment remain separate. BSM computations admit only European scalar-underlying payoff-equivalent contracts, positive multiplier, equal fixing/payment instants, and consistent basis/currency. Cash or physical settlement labels do not authorize an actual settlement workflow. Adjusted/basket/American/Bermudan definitions remain representable so independent reference outputs can survive their unsupported model status.

`model_profile_admission` is an explicit source-bound adapter certification carried by the definition's revision, causal clocks and immutable input binding. Only `certified_vanilla_continuous_carry` admits positive-time BSM mathematics. The two named unsupported cases return `unsupported_profile/unsupported_dividend_profile` or `unsupported_volatility_profile`; unsupported_other returns `unsupported_model_profile`; unknown returns `unsupported_profile/profile_uncertified`. European/scalar labels alone never certify absence of discrete cash-dividend, nonvanilla or stochastic/local-model requirements. Actual source qualification must justify the certification; synthetic examples declare a genuinely synthetic vanilla profile. This condition affects only outputs/branches using those positive-time model assumptions; terminal payoff/known-zero derivatives, reference metrics and supplied producer metrics do not gain unrelated requirements.

`CivilDateBinding` makes that certification explicit: one causal record at the request valuation instant certifies its ordinal, and one at the definition fixing instant certifies its expiry ordinal, with matching civil-binding ID and timezone. Identity is `(civil_binding_id, instant_ns)`; duplicate certificates are rejected like other identities. Missing certificates yield `missing_input/missing_civil_binding`; future-known ones yield `ineligible_input/future_known`; known contradictory ordinals/binding/timezone yield `invalid_input/civil_binding_mismatch`. Bindings preserve adapter provenance but are not a kernel timezone lookup. Their absence affects DTE only, not unrelated outputs using UTC fixing instants.

Trade quantities are nonnegative integral contracts. Negative or fractional Trade.quantity is a structural `ContractValidationError/out_of_range`, explicitly an exception to representing finite negative economic price/rate operands for per-output validation. No shares, multiplier conversion or fractional quantity support is admitted. For each trade ID, select the latest causal known-at revision; tied distinct revisions are ambiguous. A latest `cancelled` or `excluded` classification suppresses that trade, rather than falling back to an older regular revision. A regular positive-size trade is eligible only in the half-open activity interval `[window_start_ns, window_end_ns)`, ending no later than valuation. The adapter supplies an explicit `trade_rule_id` naming its reviewed source-condition classification; the evaluator never interprets undocumented provider conditions. Every ActivityWindow trade ID must reference a supplied trade for an expected contract; unknown IDs/membership are boundary errors. Missing events outside the admitted list cannot be presumed absent without complete source certificates.

Coverage certificates have causal `known_at_ns` and bind exact contract sets and intervals. A quote-sample certificate must match the quote window contract/start/end; a trade-events certificate must match the exact activity member set/start/end. A current-quotes certificate must match the activity member set and have start=end=valuation (an as-of snapshot, not a time window). `complete=False`, future-known certification, absent certification or inconsistent certification never proves inactive zero activity. An inconsistent existing referenced certificate is a boundary error; a missing certificate returns `ineligible_input/completeness_unknown` on its dependent output. The adapter, source acceptance and independent fixtures establish whether a certificate is justified: setting a boolean in a public example does not prove provider completeness.

QuoteCoverageWindow and ActivityWindow themselves require `known_at_ns <= knowledge_cutoff_ns`; future-known plans/populations return `ineligible_input/future_known` without using leaked expected membership. Quote and activity membership requires an active causal definition for each relevant member. All activity members must name the window's exact underlying ID; no cross-underlying or missing-definition member is silently dropped to change the denominator. Inconsistent actual known member identities are `invalid_input`; missing causal definitions return `missing_input/missing_definition`. Quotes used by a slot/current-member check must match that selected definition's currency. Completeness is unavailable as `ineligible_input/incomplete_source` when the exact causal certificate states `complete=False`; absent/future-known certification is `ineligible_input/completeness_unknown`/`future_known`. No partial population score is normalized or presented available.

Each QuoteCoverageWindow is a per-contract explicitly supplied event-count sampling plan, not a chain member/time-weighted measure. Expected sample IDs are unique and supplied independently of observed quotes; denominator is their count. Quote rows with `sample_id=None` serve latest-quote use only. A nonnull sample ID must belong to that contract's declared window/expected IDs and have event in `[start,end)`; unknown slots are boundary errors. Repeated source updates within one sample ID count at most once after selecting the latest causal `(event_ns, sequence, known_at_ns)` quote revision. Missing expected sample IDs count as unobserved only when complete ingestion is certified; missing certification does not become an observed outage. Sampling-plan and source completeness binding IDs are retained as dependencies. No implicit resampling or expected-count-from-observed inference is allowed.

## Output readiness and returned outcomes

This is a dependency boundary, not a new numerical formula specification. No selected output requires unrelated records. The model profile and separately reviewed endpoint/solver/score specification must be frozen before implementation; unresolved mathematics cannot be guessed from this table.

| Output ID | Canonical unit | Required computed facts |
| --- | --- | --- |
| `contract.dte` | `calendar_days` | Active definition, certified civil binding/ordinals |
| `contract.multiplier` | `underlying_units_per_contract` | Active scalar definition and valid positive multiplier |
| `contract.moneyness` | `strike_spot_ratio` | Definition and eligible consistent spot |
| `liquidity.spread_bps` | `bps` | Eligible two-sided same-currency quote |
| `quality.quote_coverage` | `ratio` | Per-contract explicit expected sample IDs, complete causal quote ingestion certificate, eligible observed samples |
| `chain.activity` | `score` | Declared activity population/window, complete causal trade/current-quote coverage, admitted regular trades and eligible current member quotes |
| `pricing.price` | `currency_per_underlying_payoff_unit` | Admitted definition, spot, rate, carry, volatility |
| `greeks.delta` / `greeks.signed_delta` | `absolute_delta` / `signed_delta` | Same forward-model dependencies; catalogue delta is abs(dV/dS), signed derivative is a separate foundation output |
| `greeks.gamma` | `inverse_currency` | Same forward-model dependencies |
| `greeks.vega` / `greeks.rho` | `currency_per_unit_sigma` / `currency_per_unit_rate` | Same forward-model dependencies |
| `greeks.theta` | `currency_per_year` | Same forward-model dependencies |
| `volatility.implied_volatility` | `annual_decimal_volatility` | Admitted definition, spot, rate, carry, eligible midpoint quote and solver config; no supplied volatility required |

The forward-model dependency rows describe interior computations, not an instruction to demand every operand at every endpoint. First select an active definition, relevant model admission and exact remaining time. An admitted expired definition establishes `not_applicable/expired` without missing r/q/sigma/spot overriding it; terminal IV establishes `nonidentifiable_inverse/terminal_price` before demanding inversion operands. At T=0, price and away-kink delta/gamma need S/K but no r/q/sigma; Vega/Rho are known zero from the admitted terminal profile without pricing facts. Terminal Theta selects only the actual branch operands: away from the kink an out-of-money result is zero, while the in-the-money derivative needs S/K/r/q; at the kink sigma distinguishes the nonfinite positive-volatility derivative from the zero-volatility directional case, which needs r/q/S. Missing unrelated facts never suppress an already determined zero, payoff or endpoint status. T>0 zero-volatility branches likewise request only the operands their selected formula actually needs. Known invalid relevant facts and unsupported known profiles remain explicit under the per-output precedence rules; unneeded facts are not validated economically for that output. Structural snapshot validation remains atomic.

Initial selected outputs are exactly those in the table. No per-contract/percentage-point/day projection API is implied by this initial set. Matrix coverage accounting remains in EQ182; foundation price/extra Greeks do not inflate the nine R25 feature declarations. Proposed `option-quote-count1` is eligible distinct samples divided by declared expected samples, with `Coverage.sampling="event_count"`, `population_id=sampling_plan_id` and independently certified ingestion. Quote sample eligibility uses causal nonnegative noncrossed two-sided positive-mid quotes and the caller's quote age at valuation. Missing/ineligible samples under complete ingestion produce an available ratio with `partial_quote_coverage`; an empty denominator is `undefined/empty_sampling_plan`. This is neither time-weighted coverage nor claimed legacy/private formula parity.

Proposed `option-chain-breadth1` consumes `ActivityWindow` without requiring open interest or a copied private score: expected membership, complete trade-window/current-quote coverage and source classification feed the separately reviewed original breadth score. The coordinator's mathematical proposal is `100*A/N`, where N is nonzero expected-member count and A counts distinct members with at least one eligible positive regular trade in the half-open window and an eligible current quote. Complete ingestion with no qualifying activity supports observed zero; incomplete certification yields unavailable status rather than a normalized subset score. `Coverage` records A/N, `sampling="population_member"` and the exact population ID. Empty membership is `undefined/empty_population`. This proposal needs independent formula/source-identity review before freeze and claims no parity with a private algorithm or future policy score.

`supplied_only` admits only `greeks.delta`, `greeks.signed_delta`, `greeks.gamma`, `greeks.vega`, `greeks.rho`, `greeks.theta`, and `volatility.implied_volatility`, with the exact corresponding unit in the table. Other output/origin combinations are boundary errors. Supplied output does not require r/q/sigma/spot/quote; it requires the requested contract identity, an active definition for underlying identity, and an eligible supplied metric. Its producer model/formula must be nonempty and are preserved exactly, never relabelled `option-bsm1`. Negative supplied gamma/vega/IV or negative absolute delta is `invalid_input/negative_supplied_measure`; signed delta/theta/rho can be negative. These structural/sign checks do not certify an unknown producer's mathematics. `computed_only` never implicitly falls back to a supplied value, and vice versa. A request cannot mix source-origin policies; callers use separate content-bound requests.

`supplied_delta_policy="exact_only"` selects only the exact requested metric with no transformation. `absolute_from_signed` is allowed only for a `supplied_only` request containing `greeks.delta`: that output selects the eligible `greeks.signed_delta` metric with unit `signed_delta` and applies the library's explicit abs projection. It never falls back to an already absolute metric. The result has `origin="computed"`, actual projection formula `option-absolute-delta1`, the true producer model and separate `producer_model_id`/`producer_formula_id` copied from its supplied parent. Its dependency record digest binds that entire supplied parent. Other outputs in the request retain exact selection. This policy is explicit canonical request content; a source label does not masquerade as an absolute-delta computation. Direct pass-through supplied results have `origin="supplied"` and producer fields populated; original model computations use null producer fields.

`Request.formula_version` is the frozen bundle ID `r25-formulas1`, not an instruction to relabel every output with one formula. The bundle maps each selected output to its actual model/reference/projection/coverage/activity formula version, and its registry definition is immutable source content bound by the contracts/calculation artifact cohort. Unknown bundle IDs are boundary errors. `Result.formula_version` records the individual formula actually used, including `option-quote-count1`, `option-chain-breadth1` or `option-absolute-delta1`; supplied pass-through records the actual producer formula. The coordinator must finalize the complete mapping before freeze; unresolved rows are not implementation authority.

The proposed complete computed mapping is `option-reference1` for DTE/moneyness/multiplier, `option-spread1` for spread, `option-quote-count1` for quote coverage, `option-chain-breadth1` for chain activity, and `option-bsm1` for price/all model Greeks/IV. The explicit supplied signed-to-absolute projection uses `option-absolute-delta1`; untransformed supplied metrics preserve their producer formula. Method versions for numerical certification are separate from these mathematical formula IDs.

Result currency/action-basis context is actual typed data, never inferred from an instrument symbol or unit string during readback. Model/price/Greek/moneyness outputs retain the admitted definition/spot currency and action basis; matched model facts and quote currency must agree where used. A dimensionless output may use currency=None where currency is irrelevant, but retains any action basis used to derive its value. Pure DTE/coverage/activity may have null currency/basis only when no such basis enters their admitted formula. Supplied metrics inherit the actual admitted contract context and preserve producer identity. Missing/unsupported outputs may retain known context but never fabricate unknown currency/basis. `inverse_currency` and `currency_per_year` consequently remain interpretable after storage.

Every available result has a finite value and `reason="ok"`; every unavailable result has `value=None`. Each result includes selected dependency binding IDs and complete canonical record digests, including relevant excluded records when explaining why no causal dependency was admitted. Computed model outputs use model/formula identities actually applied; nonmodel reference outputs use `model_id="not_applicable"` and their separately frozen formula identity. Supplied outputs use producer identities. `config_sha256` hashes the complete canonical request, and `snapshot_sha256` hashes the complete snapshot; the latter records the frozen input universe without falsely making every row a mathematical dependency. Identical frozen-snapshot replay preserves complete result identity. Adding future-known or unrelated source rows changes snapshot/result/work content identity honestly, while an already causally ready output's value/status and selected dependency bindings/digests remain invariant. `solver_evidence` is nonnull only for a computed inverse attempt, including failed attempts where evidence exists. It preserves the exact Decimal midpoint target, converted target, actual candidate/residual/bracket/iterations, complete solver tolerances, boundary classification, Vega and conditioning decision. Unavailable diagnostics remain null, never fabricated zero/false. `price_residual` is candidate_price minus target_price; `converged=True` only after the model profile's two convergence tests or exact lower-bound case. No nondeterministic timestamp, worker ID or path appears in `Result`.

Malformed structures/configurations fail atomically before any output via `ContractValidationError(path: str, code: str, message: str)`. `path` is a JSON Pointer and codes are `type_mismatch`, `unknown_field`, `unknown_enum`, `nonfinite`, `out_of_range`, `duplicate_identity`, `ambiguous_revision`, `missing_binding`, `unsupported_output_origin`, or `invalid_config`. Error messages are explanatory, not identity inputs. Such exceptions must not be converted into partial results or a generic numerical failure.

Admission also uses codes `admission_limit_exceeded` and `invalid_solver_config`. These are boundary errors, never partial per-contract numerical results. `nondifferentiable_zero_volatility` is a defined per-output reason for the model profile's zero-volatility kink. Endpoint reasons remain distinct from missing inputs.

`PriceEnclosure` retains exact finite Decimal interval endpoints with low<=high, not an unqualified point estimate labelled proof. Method ID/version identify the actual reviewed forward-error method, whose exact implementation is cohort-bound. `ConvertedOperands` records binary64 operand/year-fraction previews and exact integer remaining time; source-record digests bind the original exact economic operands actually used by the rational/Arb method. IV retains candidate/bound enclosures and the exact nonnegative maximum of abs(candidate lower-target exact) and abs(candidate upper-target exact) as worst-case residual. Solver acceptance must apply the numerical profile's certified bound/error criteria, not just point residual. Forward-model Results can carry the actual forward enclosure and converted operands in their separate fields. Uncomputed/unavailable certificates are null. C04's concrete enclosure method is selected in NUMERICAL_METHOD.md; actual implementation/artifact qualification remains open. These types represent eventual evidence and do not establish that an implementation or computed enclosure is valid. No result is declared numerically accepted from typed fields alone.

After structural validation, each output independently selects its dependencies, evaluates admissible profile and semantic conditions, and returns one status. Deterministic precedence for faults on that output's dependencies is `unsupported_profile`, `invalid_input`, `missing_input`, `ineligible_input`, `not_applicable`, `undefined`, `nonidentifiable_inverse`, `bracket_exceeded`, `iteration_limit`, `numerical_failure`, then `available`. Evaluate no mathematical stage after a prerequisite has failed. Earlier status means only a detected fault on known relevant inputs; absence never fabricates a profile fault. Multiple reasons at the winning status use lexically first reason as `reason`, with all detected reason codes as sorted quality flags. Other known independent faults may also appear as flags, never unrequested-input faults.

Initial reasons are `unsupported_dividend_profile`, `unsupported_volatility_profile`, `unsupported_model_profile`, `profile_uncertified`, `nondifferentiable_zero_volatility`, `unsupported_exercise`, `unsupported_deliverable`, `unsupported_payment_lag`, `currency_mismatch`, `action_basis_mismatch`, `nonpositive_strike`, `nonpositive_multiplier`, `nonpositive_spot`, `negative_volatility`, `negative_quote`, `crossed_quote`, `negative_supplied_measure`, `missing_definition`, `missing_civil_binding`, `civil_binding_mismatch`, `missing_spot`, `missing_rate`, `missing_carry`, `missing_volatility`, `missing_quote`, `missing_supplied_metric`, `missing_population`, `missing_activity`, `missing_sampling_plan`, `completeness_unknown`, `incomplete_source`, `future_known`, `future_event`, `inactive_interval`, `stale_spot`, `stale_quote`, `stale_supplied_metric`, `one_sided_quote`, `expired`, `empty_population`, `empty_sampling_plan`, `zero_midpoint`, `nondifferentiable_payoff`, `nonfinite_terminal_time_derivative`, `upper_asymptote`, `terminal_price`, `price_out_of_bounds`, `bound_precision`, `sigma_cap`, `iteration_budget`, `precision_exhausted`, and `nonfinite_arithmetic`. Endpoint/score review may add named reasons before freeze. Adding reasons after freeze changes the contract version or requires an explicitly compatible documented amendment. Available-only flags include `partial_quote_coverage`, `zero_activity`, `lower_boundary`, and `ill_conditioned`, where the mathematics specifies their meaning.

## Canonical wire and hash API

The contract package owns field/schema validation and pure canonical-content/digest rules; the I/O package owns envelope byte encoding/decoding and storage. This prevents calculations from requiring I/O imports. Public I/O APIs:

```python
encode_snapshot(value: Snapshot) -> bytes
decode_snapshot(data: bytes, limits: AdmissionLimits = R25_LIMITS) -> Snapshot
encode_request(value: Request) -> bytes
decode_request(data: bytes, limits: AdmissionLimits = R25_LIMITS) -> Request
encode_results(value: tuple[Result, ...]) -> bytes
decode_results(data: bytes, limits: AdmissionLimits = R25_LIMITS) -> tuple[Result, ...]
```

Each is strict `option-json1` UTF-8, without BOM, using envelope fields exactly `wire_version`, `record_type`, `payload`, `content_sha256`; record types are `snapshot`, `request`, and `results`. Envelope version is `option-json1`. Payload recursively expands exactly the explicit schemas above, includes all optional fields as JSON null, and preserves semantic request/result order. Snapshot ordering follows canonical identity sorting. Decoders reject duplicate JSON keys at every depth, unknown/missing fields, noncanonical decimal strings and nonfinite numeric tokens. They accept JSON whitespace/object-key ordering differences but validate the digest from canonical payload bytes, never raw incoming text. Returned Python objects pass the same validation as direct construction. Envelope claims never bypass recomputation.

`R25_LIMITS` is the exact AdmissionLimits maximum instance specified above. Decoder-supplied lower limits are validated independently before payload parsing and cannot be raised by incoming request fields. All encoders also enforce the fixed wire byte ceiling; request/result encoders additionally enforce any available lower request limits at their owning orchestration boundary. A request's lower limits apply to its snapshot/results even if they were decoded earlier under fixed maxima. Schemas bound nesting; the decoder rejects unexpected nesting rather than recursively accepting arbitrary trees. These checks do not advertise a process-memory sandbox.

Canonical JSON is Python 3.12 stdlib `json.dumps(..., ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))`, encoded UTF-8, no trailing newline. This algorithm is explicitly version-scoped rather than claiming language-neutral JSON float canonicalization. Float serialization uses normalized positive zero `0.0`; all declared float fields stay floats even when mathematically integral. Exact Decimal fields serialize as plain decimal strings: no exponent or plus sign, no redundant leading zeros, no trailing fractional zeros, zero exactly `"0"`. Unicode content is not normalized: byte-distinct IDs remain distinct. Integers are JSON integers. Schema-specific encode/decode implementations are explicit; no class-name imports, `pickle`, `eval`, or arbitrary dataclass reflection registry is allowed.

Individual-record `record_type` literals are closed and explicit: `InputBinding=input_binding`, `CivilDateBinding=civil_date_binding`, `Definition=definition`, `Spot=spot`, `ModelFact=model_fact`, `Quote=quote`, `SuppliedMetric=supplied_metric`, `Trade=trade`, `CoverageCertificate=coverage_certificate`, `QuoteCoverageWindow=quote_coverage_window`, `ActivityWindow=activity_window`, `Snapshot=snapshot`, `Eligibility=eligibility`, `SolverConfig=solver_config`, `AdmissionLimits=admission_limits`, `Request=request`, `Coverage=coverage`, `ConvertedOperands=converted_operands`, `PriceEnclosure=price_enclosure`, `SolverEvidence=solver_evidence`, and `Result=result`. Class names, alternate casing and inferred spellings are not hash-domain aliases. This clarification makes the existing schema names portable for independent fixture authors; it changes no declared record fields, formula or implemented domain spelling. The three envelope types remain `snapshot`, `request` and `results` as defined above.

Let `C(x)` mean canonical payload bytes. Record digest is SHA256 of UTF-8 `"option-record1\n" + record_type + "\n"` followed by `C(record)`. Envelope content digest is SHA256 of UTF-8 `"option-json1\n" + record_type + "\n"` followed by `C(payload)`. Snapshot/config hashes are those corresponding envelope content digests. Result-tuple digest is the results envelope content digest. Hashes exclude their own envelope digest field. Result digests include all value/status/quality/coverage/solver/provenance/version fields; a numerical value alone never defines equality. EQ185 tests independent golden bytes, tampering, unknown/duplicate fields, Decimal cases and full typed roundtrips. Cross-platform byte parity is a separately executed EQ187 gate, not inferred from this specification.

## Separate storage and atomic publication

EQ185 implements a separate `option-generation1` DuckDB sink. The caller selects an explicit destination; no calculation chooses a path. Never insert these tables into, migrate, or silently overwrite an equity database. Sink open creates a new empty target or validates an existing exact option schema/version. Nonempty unrecognized targets fail `StorageSchemaError`. DuckDB/library versions and installed wheel hashes belong in the release cohort, not assumed from source references.

Storage tables are exactly `option_schema(version VARCHAR PRIMARY KEY)`, `generations(run_key VARCHAR PRIMARY KEY, work_sha256 VARCHAR, request_sha256 VARCHAR, snapshot_sha256 VARCHAR, cohort_sha256 VARCHAR, results_sha256 VARCHAR, result_count BIGINT, state VARCHAR)`, `result_rows(run_key VARCHAR, ordinal BIGINT, canonical_json VARCHAR, PRIMARY KEY(run_key, ordinal))`, and `source_bindings(run_key VARCHAR, binding_id VARCHAR, record_sha256 VARCHAR, canonical_json VARCHAR, PRIMARY KEY(run_key, binding_id))`. Schema version is one `option-generation1` row. Committed generation state is exactly `committed`; no partially prepared state is publicly visible. Each result row stores the canonical `Result` payload and each source row the canonical `InputBinding` payload, using the record digests above. Bindings are scoped by run so a caller-selected binding ID cannot alias different immutable sources across runs. Results are an ordered contiguous sequence starting at ordinal zero.

The additional exact records and protocols below are frozen/slotted like the canonical records. They belong to I/O and workers respectively; protocol declarations do not introduce a dependency from calculations onto either layer.

```python
from typing import Protocol

@dataclass(frozen=True, slots=True)
class Publication:
    run_key: str
    work_sha256: str
    request_sha256: str
    snapshot_sha256: str
    cohort_sha256: str
    results: tuple[Result, ...]
    bindings: tuple[InputBinding, ...]

@dataclass(frozen=True, slots=True)
class CommitReceipt:
    run_key: str
    work_sha256: str
    results_sha256: str
    result_count: int
    outcome: Literal["committed", "already_committed"]
    readback_verified: bool

class ResultSink(Protocol):
    def commit(self, publication: Publication) -> CommitReceipt: ...
    def read(self, run_key: str) -> Publication | None: ...
```

Commit validates/recomputes every digest it can derive and demands all result dependency bindings exist in the supplied bindings. It also requires each Result config/snapshot hash to equal the publication request/snapshot hash. Nonempty exact cohort/source identities are required; a digest-looking string is not independent artifact verification. The sink cannot reconstruct a request or artifact cohort from summary hashes and does not claim to do so: the worker's separately verified manifest supplies those identities.

One sink owner serializes writes. A transaction inserts the complete generation, ordered result rows and source bindings atomically. Same run key and complete identical publication content returns `already_committed` after full readback; same key with any changed content raises `PublicationConflict`, even if numeric results agree. A rollback leaves no visible generation. Readers return only committed generations and verify schema, row count/ordinal continuity, every reconstructed typed record, dependency bindings and ordered results digest. Corruption raises `StorageIntegrityError`, not an empty successful read. Existing-generation retries also compare bindings, not just six summary digests. An empty result publication is invalid for this release; an empty expected population still produces its explicitly undefined selected result.

## Worker execution, retry and cancellation

EQ186 owns an option-native execution boundary; no existing equity worker callback/admission compatibility is presumed. Required APIs:

```python
execute(snapshot: Snapshot, request: Request, execution: ExecutionConfig,
        cohort: Cohort, run_key: str, sink: ResultSink | None,
        cancel: CancellationToken) -> RunReceipt
replay(items: tuple[ReplayItem, ...], execution: ExecutionConfig,
       cohort: Cohort, sink: ResultSink | None,
       cancel: CancellationToken) -> tuple[RunReceipt, ...]
```

Exact worker-side dataclasses/protocols:

```python
@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    mode: Literal["batch", "replay"]
    max_workers: int
    max_inflight: int
    memory_budget_bytes: int
    logical_task_bytes: int
    io_slots: int
    backend_threads: Literal[1]

@dataclass(frozen=True, slots=True)
class Artifact:
    distribution: str
    version: str
    source_commit: str
    wheel_sha256: str
    role: Literal["contracts", "calculations", "io", "workers", "dependency"]

@dataclass(frozen=True, slots=True)
class Cohort:
    cohort_version: Literal["option-cohort1"]
    python_version: str
    platform_id: str
    artifacts: tuple[Artifact, ...]

@dataclass(frozen=True, slots=True)
class ReplayItem:
    snapshot: Snapshot
    request: Request
    run_key: str

@dataclass(frozen=True, slots=True)
class RunReceipt:
    run_key: str
    work_sha256: str
    outcome: Literal["computed", "committed", "already_committed", "cancelled"]
    results: tuple[Result, ...]
    commit_receipt: CommitReceipt | None
    cancellation_observed: bool

class CancellationToken(Protocol):
    def is_cancelled(self) -> bool: ...
```

Replay processes independent snapshots in caller order; it is not an incremental update/restore/merge API. All resource integers are positive, reject bool, and satisfy `max_inflight <= max_workers`; a logical task reservation exceeding total memory fails before dispatch. Initial qualification supports `max_workers=max_inflight=io_slots=1` for both modes. `execute` requires mode batch; `replay` requires mode replay. An optional parallel mode requires a separately reviewed explicit contract/version and direct/worker/stored parity, resource and cancellation evidence; merely setting a larger number does not qualify it. Replay bounds total item admission by processing one item at a time; its tuple is caller-owned input, not an unbounded executor queue.

The default sequential whole-request evaluator is the supported baseline: preserve ordered input facts and deterministic result ordering, and compute population outputs once from the exact declared population. One coordinator owns all CPU, logical-memory and I/O reservations, including nested libraries. Native numerical backend threads are one in the qualified environment. These are logical resource reservations and bounded in-flight counts; they are not hard RSS, OS job-object or cgroup limits. Resource estimates and admission/release receipts must expose their unit and actual limitations. A failed task releases its reservations in a finally path; no parallel speed/performance claim is delivered by this baseline.

Before dispatch, verify actual schema counts and canonical input byte lengths against request/fixed limits. The worker computes a declared conservative logical estimate `max(1048576, 4*(snapshot_wire_bytes+request_wire_bytes)+4096*predicted_result_rows)` bytes and rejects `logical_task_bytes` smaller than that estimate or greater than total memory budget. This operational estimate is reproducible admission accounting, not a proved bound on Python/DuckDB allocation or a benchmark claim. Canonical output beyond admitted byte/row limits fails before any publication. One active whole-request task plus fixed count/iteration ceilings bounds actual dispatched work; a caller's unchecked task-byte assertion alone never authorizes more work.

`Cohort` contains `cohort_version="option-cohort1"`, `python_version`, `platform_id`, and sorted `Artifact` records. Each `Artifact` has distribution name, exact version, source commit (40 lowercase hex), wheel SHA256, and `role` (`contracts`, `calculations`, `io`, `workers`, or `dependency`). Every installed runtime distribution in the qualified environment is bound, including exact transitive dependencies; standard library identity is Python/environment evidence. The worker verifies the supplied cohort against an installed-artifact verification receipt before execution; an arbitrary manifest alone is not verification. No unbound user callbacks/plugins are admitted in R25.

Work identity is SHA256 of UTF-8 `"option-work1\n"` followed by canonical content with keys `snapshot_sha256`, `request_sha256`, `execution` (complete config), `cohort_sha256` (domain `option-cohort1\n` plus canonical cohort), and `worker_implementation_sha256` (the worker wheel digest verified in the cohort). Model/formula/schema identities are already bound in the request, snapshot and exact artifacts. The caller's `run_key` is a stable storage key, not proof of content identity. Any changed source, input, configuration, artifact or execution semantics creates a different work identity; reusing a run key then conflicts. Retry never swaps a callback or upgrades a dependency invisibly.

`CancellationToken.is_cancelled() -> bool` is a worker-side protocol, not part of canonical inputs or a numerical callback. Initial sequential cancellation checks occur before evaluation and after it returns, then immediately before publication. The bounded solver's configured iteration budget bounds one solve; R25 does not promise interruption inside a solve or whole-request kernel. A requested cancellation waits for any already-started evaluation to finish. If cancellation wins before commit, do not commit; a computed result is not a published result. If atomic commit has occurred, report committed visibility truth even if cancellation was requested concurrently. Failure after commit recovers by identical publication/readback and reports actual visibility. No cancellation/failure receipt claims successful stored output without readback.

`RunReceipt` is frozen with fields `run_key`, `work_sha256`, `outcome: Literal["computed","committed","already_committed","cancelled"]`, `results: tuple[Result,...]`, `commit_receipt: CommitReceipt|None`, and `cancellation_observed: bool`. `computed` is allowed only when no sink was requested; it explicitly does not mean published. Cancelled receipts contain no returned results/commit receipt. Failed validation/execution/publication raises typed errors with the work identity when available; it does not return a success-shaped receipt. A sink publication exception triggers recovery readback for the same expected content; mismatched or corrupt content raises, never masks a conflict. Resource/run telemetry may contain real elapsed times but lives outside deterministic Result values/hashes and cannot mutate them.

## Handoff and unresolved freeze requirements

The library author owns records, pure validation/digests and evaluator semantics; I/O owns strict option-json1, synthetic conversion and separate generation sink; workers own verified artifact cohort admission, bounded execution and publication/recovery. Each author uses the same frozen contract commit and independent fixtures. Coordinator review, fresh independent PR review and exact-commit appropriate local validation precede merges. Hosted Actions completion is not a merge gate. Release validation still requires actually executed supported-platform evidence, full direct/worker/stored value/status/quality/coverage/solver/provenance identity parity, and an actual stored-output browser demo. No such evidence is claimed by this proposal.

Before freeze, the coordinator must reconcile the separate mathematics document's Greek endpoints, IV tolerances/error budgets and activity-score identity with independent review. In particular an original bounded activity score does not prove equivalence to a particular private algorithm, and event-count quote coverage does not deliver time-weighted source coverage. Missing mathematical choices keep the relevant implementation story unready. The implementation handoff must pin package versions, exact frozen formula IDs, source commit and expected fixture hashes; names in this proposal alone are not an artifact lock or a release.

## Selected C04 operand and evidence interpretation

[NUMERICAL_METHOD.md](NUMERICAL_METHOD.md) is the concrete option-arb-bsm1/version1 method. Its original economic Decimals, exact rational time and exact dyadic model/candidate values are the certified operands. ConvertedOperands.spot/strike/year_fraction are binary64 previews and representability diagnostics; they do not redefine those original real operands. PriceEnclosure method/version and outward persisted Decimal endpoints plus exact worst-case residual evidence make the eventual certificate auditable. The source method is selected; fresh exact-source review, actual implementation/installed-artifact/numerical/context/platform qualification remain distinct requirements. No source-only review asserts those executions passed.
