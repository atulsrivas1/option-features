"""Closed, versioned field schemas; no annotation discovery or class-name loading.

Only the literal field names below are accessed. Input cannot register classes,
select an import, inspect dataclass metadata, or introduce additional fields.
"""
from . import records as r

# Descriptors: s=bounded text, d=Decimal, f=binary64, i=int64, n=count,
# o=civil ordinal, b=bool, h=SHA256, c=currency; ? optional; [] tuple.
SCHEMAS = {
    r.InputBinding: ("input_binding", "binding_id:s source_id:s source_revision:s source_content_sha256:h provenance_mode:=synthetic,licensed,public_permitted rights_reference:s"),
    r.CivilDateBinding: ("civil_date_binding", "civil_binding_id:s instant_ns:i ordinal:o timezone_id:s known_at_ns:i input_binding_id:s"),
    r.Definition: ("definition", "contract_id:s underlying_id:s right:=call,put strike:d currency:c multiplier:d deliverable:=scalar_underlying,adjusted,basket action_basis_id:s exercise:=european,american,bermudan model_profile_admission:=certified_vanilla_continuous_carry,unsupported_discrete_dividends,unsupported_stochastic_or_local,unsupported_other,unknown settlement:=cash,physical last_trade_ns:i fixing_ns:i payment_ns:i expiry_ordinal:o timezone_id:s civil_binding_id:s revision_id:s effective_from_ns:i effective_to_ns:?i known_at_ns:i input_binding_id:s"),
    r.Spot: ("spot", "underlying_id:s value:d currency:c action_basis_id:s event_ns:i known_at_ns:i revision_id:s input_binding_id:s"),
    r.ModelFact: ("model_fact", "underlying_id:s contract_id:?s kind:=rate,carry,volatility value:f model_id:s currency:c action_basis_id:s effective_from_ns:i effective_to_ns:?i known_at_ns:i revision_id:s input_binding_id:s"),
    r.Quote: ("quote", "contract_id:s sample_id:?s bid:?d ask:?d currency:c price_basis:=per_underlying_payoff_unit event_ns:i known_at_ns:i sequence:n revision_id:s input_binding_id:s"),
    r.SuppliedMetric: ("supplied_metric", "contract_id:s output_id:s value:f unit:s producer_model_id:s producer_formula_id:s event_ns:i known_at_ns:i revision_id:s input_binding_id:s"),
    r.Trade: ("trade", "trade_id:s contract_id:s quantity:d quantity_unit:=contracts classification:=regular,excluded,cancelled event_ns:i known_at_ns:i revision_id:s input_binding_id:s"),
    r.CoverageCertificate: ("coverage_certificate", "certificate_id:s kind:=trade_events,quote_samples,current_quotes contract_ids:[]s window_start_ns:i window_end_ns:i known_at_ns:i complete:b input_binding_id:s"),
    r.QuoteCoverageWindow: ("quote_coverage_window", "contract_id:s known_at_ns:i window_start_ns:i window_end_ns:i expected_sample_ids:[]s sampling_plan_id:s completeness_certificate_id:s input_binding_id:s"),
    r.ActivityWindow: ("activity_window", "population_id:s underlying_id:s expected_contract_ids:[]s known_at_ns:i window_start_ns:i window_end_ns:i trade_ids:[]s trade_rule_id:s trade_completeness_certificate_id:s quote_completeness_certificate_id:s input_binding_id:s"),
    r.Snapshot: ("snapshot", "schema_version:=option-canonical1 bindings:[]input_binding civil_bindings:[]civil_date_binding definitions:[]definition spots:[]spot model_facts:[]model_fact quotes:[]quote supplied_metrics:[]supplied_metric trades:[]trade coverage_certificates:[]coverage_certificate quote_coverage_windows:[]quote_coverage_window activity_window:?activity_window"),
    r.Eligibility: ("eligibility", "max_quote_age_ns:n max_spot_age_ns:n max_supplied_metric_age_ns:n"),
    r.SolverConfig: ("solver_config", "method:=bisection1 quote_basis:=midpoint max_sigma:f max_iterations:n price_abs_tol:f price_rel_tol:f vol_abs_tol:f vol_rel_tol:f"),
    r.AdmissionLimits: ("admission_limits", "max_wire_bytes:n max_snapshot_records:n max_requested_contracts:n max_selected_outputs:n max_result_rows:n max_solver_iterations:n"),
    r.Request: ("request", "schema_version:=option-request1 contract_ids:[]s output_ids:[]s origin_policy:=computed_only,supplied_only supplied_delta_policy:=exact_only,absolute_from_signed valuation_ns:i knowledge_cutoff_ns:i valuation_ordinal:o civil_binding_id:s model_id:=option-bsm1 formula_version:=r25-formulas1 eligibility:eligibility solver:solver_config limits:admission_limits"),
    r.Coverage: ("coverage", "observed:n expected:n population_id:s population_complete:b sampling:=event_count,population_member"),
    r.ConvertedOperands: ("converted_operands", "spot:f strike:f rate:f carry:f sigma:?f remaining_ns:i year_fraction:f"),
    r.PriceEnclosure: ("price_enclosure", "method_id:s method_version:s value_low:d value_high:d"),
    r.SolverEvidence: ("solver_evidence", "iterations:n target_price_exact:d target_price:?f candidate_sigma:?f candidate_price:?f lower_price_bound:?f upper_price_bound:?f lower_bound_enclosure:?price_enclosure upper_bound_enclosure:?price_enclosure candidate_price_enclosure:?price_enclosure worst_case_price_residual:?d converted_operands:?converted_operands sigma_low:?f sigma_high:?f price_residual:?f solver_config:solver_config boundary:=none,lower_boundary,upper_asymptote,sigma_cap vega:?f ill_conditioned:?b converged:b"),
    r.Result: ("result", "schema_version:=option-result1 contract_id:?s underlying_id:?s output_id:s currency:?c action_basis_id:?s origin:=computed,supplied value:?f unit:s status:=available,unsupported_profile,invalid_input,missing_input,ineligible_input,not_applicable,undefined,nonidentifiable_inverse,bracket_exceeded,iteration_limit,numerical_failure reason:s quality_flags:[]s coverage:?coverage solver_evidence:?solver_evidence pricing_evidence:?price_enclosure converted_operands:?converted_operands dependency_binding_ids:[]s dependency_record_sha256s:[]h valuation_ns:i knowledge_cutoff_ns:i model_id:s formula_version:s producer_model_id:?s producer_formula_id:?s config_sha256:h snapshot_sha256:h contracts_package_version:s calculation_package_version:s"),
}
BY_NAME = {name: cls for cls, (name, _) in SCHEMAS.items()}
FIELDS = {cls: tuple(token.split(":", 1) for token in declaration.split()) for cls, (_, declaration) in SCHEMAS.items()}

OUTPUT_UNITS = {
    "contract.dte": "calendar_days", "contract.multiplier": "underlying_units_per_contract",
    "contract.moneyness": "strike_spot_ratio", "liquidity.spread_bps": "bps",
    "quality.quote_coverage": "ratio", "chain.activity": "score",
    "pricing.price": "currency_per_underlying_payoff_unit", "greeks.delta": "absolute_delta",
    "greeks.signed_delta": "signed_delta", "greeks.gamma": "inverse_currency",
    "greeks.vega": "currency_per_unit_sigma", "greeks.rho": "currency_per_unit_rate",
    "greeks.theta": "currency_per_year", "volatility.implied_volatility": "annual_decimal_volatility",
}
SUPPLIED_OUTPUTS = frozenset({"greeks.delta", "greeks.signed_delta", "greeks.gamma", "greeks.vega", "greeks.rho", "greeks.theta", "volatility.implied_volatility"})

REASONS_BY_STATUS = {
    "available": frozenset({"ok"}),
    "unsupported_profile": frozenset({"unsupported_dividend_profile", "unsupported_volatility_profile", "unsupported_model_profile", "profile_uncertified", "unsupported_exercise", "unsupported_deliverable", "unsupported_payment_lag"}),
    "invalid_input": frozenset({"currency_mismatch", "action_basis_mismatch", "nonpositive_strike", "nonpositive_multiplier", "nonpositive_spot", "negative_volatility", "negative_quote", "crossed_quote", "negative_supplied_measure", "civil_binding_mismatch", "price_out_of_bounds"}),
    "missing_input": frozenset({"missing_definition", "missing_civil_binding", "missing_spot", "missing_rate", "missing_carry", "missing_volatility", "missing_quote", "missing_supplied_metric", "missing_population", "missing_activity", "missing_sampling_plan"}),
    "ineligible_input": frozenset({"completeness_unknown", "incomplete_source", "future_known", "future_event", "inactive_interval", "stale_spot", "stale_quote", "stale_supplied_metric", "one_sided_quote"}),
    "not_applicable": frozenset({"expired"}),
    "undefined": frozenset({"empty_population", "empty_sampling_plan", "zero_midpoint", "nondifferentiable_payoff", "nondifferentiable_zero_volatility", "nonfinite_terminal_time_derivative"}),
    "nonidentifiable_inverse": frozenset({"upper_asymptote", "terminal_price"}),
    "bracket_exceeded": frozenset({"sigma_cap"}),
    "iteration_limit": frozenset({"iteration_budget"}),
    "numerical_failure": frozenset({"bound_precision", "precision_exhausted", "nonfinite_arithmetic"}),
}

IDENTITY_FIELDS = {
    r.InputBinding: ("binding_id",), r.CivilDateBinding: ("civil_binding_id", "instant_ns"),
    r.Definition: ("contract_id", "revision_id"),
    r.Spot: ("underlying_id", "event_ns", "revision_id"),
    r.ModelFact: ("underlying_id", "contract_id", "kind", "effective_from_ns", "revision_id"),
    r.Quote: ("contract_id", "event_ns", "sequence", "revision_id"),
    r.SuppliedMetric: ("contract_id", "output_id", "event_ns", "revision_id"),
    r.Trade: ("trade_id", "revision_id"), r.CoverageCertificate: ("certificate_id",),
    r.QuoteCoverageWindow: ("contract_id",),
}
