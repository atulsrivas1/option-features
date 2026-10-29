"""Public pure supplied-fact evaluator; no acquisition, clocks or persistence."""
from contextlib import ExitStack
from fractions import Fraction
import math
from option_feature_contracts import (
    Result, Coverage, ConvertedOperands, validate_snapshot, validate_request,
    validate_results, content_digest, record_digest, OUTPUT_UNITS,
)
from option_feature_contracts.schema import SCHEMAS
from . import selection
from .reference import Outcome, PRECEDENCE, unavailable, missing, rational_value, quote_faults, evaluate_reference, chain_activity
from .arithmetic import numerical_owner, decimal_exact, nearest_binary64, NumericalFailure
from .model import Operands, Undefined, forward
from .inverse import solve

REFERENCE_OUTPUTS = frozenset({"contract.dte", "contract.multiplier", "contract.moneyness", "liquidity.spread_bps", "liquidity.spread", "liquidity.midpoint", "quality.quote_coverage"})
YEAR_NS = 31536000000000000

def _profile_certification(definition):
    return {
        "unsupported_discrete_dividends": "unsupported_dividend_profile",
        "unsupported_stochastic_or_local": "unsupported_volatility_profile",
        "unsupported_other": "unsupported_model_profile", "unknown": "profile_uncertified",
    }.get(definition.model_profile_admission)

def _profile(definition, positive_time):
    faults = []
    if definition.exercise != "european":
        faults.append(("unsupported_profile", "unsupported_exercise"))
    if definition.deliverable != "scalar_underlying":
        faults.append(("unsupported_profile", "unsupported_deliverable"))
    if definition.payment_ns != definition.fixing_ns:
        faults.append(("unsupported_profile", "unsupported_payment_lag"))
    reason = _profile_certification(definition) if positive_time else None
    if reason is not None:
        faults.append(("unsupported_profile", reason))
    if definition.strike <= 0:
        faults.append(("invalid_input", "nonpositive_strike"))
    if definition.multiplier <= 0:
        faults.append(("invalid_input", "nonpositive_multiplier"))
    return faults

def _supplied(snapshot, request, definition, output_id):
    projection = output_id == "greeks.delta" and request.supplied_delta_policy == "absolute_from_signed"
    selected_id = "greeks.signed_delta" if projection else output_id
    metric = selection.supplied(snapshot, request, definition.contract_id, selected_id)
    records = (definition,)
    if metric is None:
        result = missing((r for r in snapshot.supplied_metrics if r.contract_id == definition.contract_id and r.output_id == selected_id), request, "missing_supplied_metric")
        return Outcome(None, result.faults, records+result.records), None, projection
    records += (metric,)
    faults = []
    if metric.unit != OUTPUT_UNITS[selected_id]:
        # Structural source units are representable; selected semantic mismatch
        # cannot be reinterpreted as another derivative.
        from option_feature_contracts import ContractValidationError
        raise ContractValidationError("/supplied_metrics", "invalid_config", "supplied output unit mismatch")
    if selected_id in {"greeks.delta", "greeks.gamma", "greeks.vega", "volatility.implied_volatility"} and metric.value < 0:
        faults.append(("invalid_input", "negative_supplied_measure"))
    if request.valuation_ns-metric.event_ns > request.eligibility.max_supplied_metric_age_ns:
        faults.append(("ineligible_input", "stale_supplied_metric"))
    return Outcome(None if faults else (abs(metric.value) if projection else metric.value), tuple(faults), records), metric, projection

def _model(snapshot, request, definition, output_id, owner):
    records = [definition]
    remaining = definition.fixing_ns-request.valuation_ns
    faults = _profile(definition, remaining > 0)
    if remaining < 0:
        faults.append(("not_applicable", "expired"))
    elif remaining == 0 and output_id == "volatility.implied_volatility":
        faults.append(("nonidentifiable_inverse", "terminal_price"))
    if faults:
        return Outcome(None, tuple(faults), tuple(records)), None, None, None
    if remaining == 0 and output_id in {"greeks.vega", "greeks.rho"}:
        return rational_value(Fraction(0), tuple(records)), None, None, None
    selected_spot = selection.spot(snapshot, request, definition.underlying_id)
    if selected_spot is None:
        absent = missing((r for r in snapshot.spots if r.underlying_id == definition.underlying_id), request, "missing_spot")
        faults.extend(absent.faults)
        records.extend(absent.records)
    else:
        records.append(selected_spot)
        if selected_spot.value <= 0:
            faults.append(("invalid_input", "nonpositive_spot"))
        if selected_spot.currency != definition.currency:
            faults.append(("invalid_input", "currency_mismatch"))
        if selected_spot.action_basis_id != definition.action_basis_id:
            faults.append(("invalid_input", "action_basis_mismatch"))
        if request.valuation_ns-selected_spot.event_ns > request.eligibility.max_spot_age_ns:
            faults.append(("ineligible_input", "stale_spot"))
    terminal_branch = None
    need_rate_carry = remaining > 0
    need_sigma = remaining > 0 and output_id != "volatility.implied_volatility"
    if remaining == 0 and output_id == "greeks.theta" and selected_spot is not None:
        sign = (1 if definition.right == "call" else -1)*(decimal_exact(selected_spot.value)-decimal_exact(definition.strike))
        terminal_branch = "itm" if sign > 0 else ("otm" if sign < 0 else "kink")
        need_rate_carry = terminal_branch == "itm"
        need_sigma = terminal_branch == "kink"
        if terminal_branch != "otm":
            reason = _profile_certification(definition)
            if reason is not None:
                faults.append(("unsupported_profile", reason))
    selected = {}

    def get_fact(kind):
        fact = selection.model_fact(snapshot, request, definition, kind)
        if fact is None:
            absent = missing((r for r in snapshot.model_facts if r.underlying_id == definition.underlying_id and r.kind == kind and (r.contract_id is None or (kind == "volatility" and r.contract_id == definition.contract_id))), request, "missing_"+kind)
            faults.extend(absent.faults)
            records.extend(absent.records)
            return
        selected[kind] = fact
        records.append(fact)
        if fact.currency != definition.currency:
            faults.append(("invalid_input", "currency_mismatch"))
        if fact.action_basis_id != definition.action_basis_id:
            faults.append(("invalid_input", "action_basis_mismatch"))
        if fact.model_id != "option-bsm1":
            faults.append(("unsupported_profile", "unsupported_model_profile"))
        if kind == "volatility" and fact.value < 0:
            faults.append(("invalid_input", "negative_volatility"))

    if need_sigma:
        get_fact("volatility")
    if terminal_branch == "kink" and "volatility" in selected:
        if selected["volatility"].value > 0:
            faults.append(("undefined", "nonfinite_terminal_time_derivative"))
        elif selected["volatility"].value == 0:
            need_rate_carry = True
    if need_rate_carry:
        get_fact("rate")
        get_fact("carry")
    quote = None
    if output_id == "volatility.implied_volatility":
        quote = selection.quote(snapshot, request, definition.contract_id)
        if quote is None:
            absent = missing((r for r in snapshot.quotes if r.contract_id == definition.contract_id), request, "missing_quote")
            faults.extend(absent.faults)
            records.extend(absent.records)
        else:
            records.append(quote)
            faults.extend(quote_faults(quote, definition, request))
    if faults:
        return Outcome(None, tuple(faults), tuple(records)), None, None, None
    try:
        if remaining > 2**63-1:
            raise NumericalFailure()
        S, K = decimal_exact(selected_spot.value), decimal_exact(definition.strike)
        rate = Fraction.from_float(selected["rate"].value) if "rate" in selected else Fraction(0)
        carry = Fraction.from_float(selected["carry"].value) if "carry" in selected else Fraction(0)
        sigma = Fraction.from_float(selected["volatility"].value) if "volatility" in selected else Fraction(0)
        T = Fraction(remaining, YEAR_NS)
        spot_preview, strike_preview, time_preview = nearest_binary64(S), nearest_binary64(K), nearest_binary64(T)
        if spot_preview <= 0 or strike_preview <= 0 or (remaining > 0 and time_preview <= 0):
            raise NumericalFailure()
        operands = Operands(S, K, rate, carry, T, sigma, 1 if definition.right == "call" else -1)
        converted = ConvertedOperands(spot_preview, strike_preview, float(rate), float(carry), float(sigma) if "volatility" in selected else None, remaining, time_preview)
        if output_id == "volatility.implied_volatility":
            inverse = solve(operands, (decimal_exact(quote.bid)+decimal_exact(quote.ask))/2, request.solver, converted, owner())
            flags = ()
            if inverse.evidence is not None:
                flags = tuple(flag for flag, present in (("lower_boundary", inverse.evidence.boundary == "lower_boundary"), ("ill_conditioned", inverse.evidence.ill_conditioned is True)) if present)
            outcome = Outcome(inverse.value, () if inverse.status == "available" else ((inverse.status, inverse.reason),), tuple(records), flags)
            return outcome, None, converted, inverse.evidence
        certified = forward(operands, output_id, None if remaining == 0 else owner())
        return Outcome(certified.value, records=tuple(records)), certified.enclosure, converted, None
    except Undefined as exc:
        return unavailable("undefined", exc.reason, tuple(records)), None, None, None
    except NumericalFailure as exc:
        return unavailable("numerical_failure", exc.reason, tuple(records)), None, None, None

def evaluate(snapshot, request):
    """Pure option-request1 evaluation, preserving semantic output order."""
    validate_request(request)
    validate_snapshot(snapshot, request.limits)
    config_hash = content_digest("request", request, request.limits)
    snapshot_hash = content_digest("snapshot", snapshot, request.limits)
    results = []

    def append_result(contract_id, definition, output_id, outcome, pricing=None, converted=None, solver=None, metric=None, projection=False):
        origin = "supplied" if request.origin_policy == "supplied_only" and not projection else "computed"
        formula = "option-reference1" if output_id.startswith("contract.") else {"liquidity.spread_bps": "option-spread1", "liquidity.spread": "option-spread1", "liquidity.midpoint": "option-spread1", "quality.quote_coverage": "option-quote-count1", "chain.activity": "option-chain-breadth1"}.get(output_id, "option-bsm1")
        model_id = "not_applicable" if output_id in REFERENCE_OUTPUTS or output_id == "chain.activity" else "option-bsm1"
        if request.origin_policy == "supplied_only" and metric is None:
            model_id = "not_applicable"
            formula = "option-absolute-delta1" if projection else "not_applicable"
        if metric is not None:
            model_id = metric.producer_model_id
            formula = "option-absolute-delta1" if projection else metric.producer_formula_id
        coverage = None
        if outcome.observed is not None:
            coverage = Coverage(outcome.observed, outcome.expected, outcome.population_id, True, "population_member" if output_id == "chain.activity" else "event_count")
        basis_relevant = output_id not in {"contract.dte", "quality.quote_coverage", "chain.activity"}
        currency_relevant = basis_relevant and output_id != "contract.multiplier"
        dependency_bindings = tuple(sorted({record.input_binding_id for record in outcome.records}))
        dependency_digests = tuple(sorted({record_digest(SCHEMAS[type(record)][0], record) for record in outcome.records}))
        underlying_id = definition.underlying_id if definition is not None else (snapshot.activity_window.underlying_id if output_id == "chain.activity" and snapshot.activity_window is not None else None)
        flags = tuple(sorted(set(outcome.flags) | {reason for _, reason in outcome.faults}))
        results.append(Result(
            "option-result1", contract_id, underlying_id, output_id,
            definition.currency if definition is not None and currency_relevant else None,
            definition.action_basis_id if definition is not None and basis_relevant else None,
            origin, outcome.value, OUTPUT_UNITS[output_id], outcome.status, outcome.reason,
            flags, coverage, solver, pricing, converted, dependency_bindings, dependency_digests,
            request.valuation_ns, request.knowledge_cutoff_ns, model_id, formula,
            metric.producer_model_id if metric is not None else None,
            metric.producer_formula_id if metric is not None else None,
            config_hash, snapshot_hash, "0.1.0a1", "0.1.0a1",
        ))

    with ExitStack() as stack:
        active_owner = None
        def get_owner():
            nonlocal active_owner
            if active_owner is None:
                active_owner = stack.enter_context(numerical_owner())
            return active_owner
        for contract_id in request.contract_ids:
            definition = selection.definition(snapshot, request, contract_id)
            for output_id in request.output_ids:
                if output_id == "chain.activity":
                    continue
                if definition is None:
                    outcome = missing((r for r in snapshot.definitions if r.contract_id == contract_id), request, "missing_definition")
                    append_result(contract_id, None, output_id, outcome)
                elif request.origin_policy == "supplied_only":
                    outcome, metric, projection = _supplied(snapshot, request, definition, output_id)
                    append_result(contract_id, definition, output_id, outcome, metric=metric, projection=projection)
                elif output_id in REFERENCE_OUTPUTS:
                    append_result(contract_id, definition, output_id, evaluate_reference(snapshot, request, definition, output_id))
                else:
                    outcome, pricing, converted, solver = _model(snapshot, request, definition, output_id, get_owner)
                    append_result(contract_id, definition, output_id, outcome, pricing, converted, solver)
        for output_id in request.output_ids:
            if output_id == "chain.activity":
                append_result(None, None, output_id, chain_activity(snapshot, request))
    final = tuple(results)
    validate_results(final, request.limits)
    return final
