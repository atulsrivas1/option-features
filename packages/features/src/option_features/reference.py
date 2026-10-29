"""Original reference, quote-count and breadth formulas; no I/O or backend."""
from dataclasses import dataclass
from fractions import Fraction
import math
from . import selection

SPREAD_OUTPUTS = frozenset({"liquidity.spread_bps", "liquidity.spread", "liquidity.midpoint"})
PRECEDENCE = ("unsupported_profile", "invalid_input", "missing_input", "ineligible_input", "not_applicable", "undefined", "nonidentifiable_inverse", "bracket_exceeded", "iteration_limit", "numerical_failure", "available")

@dataclass(frozen=True, slots=True)
class Outcome:
    value: float | None
    faults: tuple[tuple[str, str], ...] = ()
    records: tuple = ()
    flags: tuple[str, ...] = ()
    observed: int | None = None
    expected: int | None = None
    population_id: str | None = None

    @property
    def status(self):
        return min((status for status, _ in self.faults), key=PRECEDENCE.index) if self.faults else "available"

    @property
    def reason(self):
        return min(reason for status, reason in self.faults if status == self.status) if self.faults else "ok"

def unavailable(status, reason, records=()):
    return Outcome(None, ((status, reason),), records)

def rational_value(value, records=(), flags=(), **coverage):
    """Exact rational evaluation and reviewed nearest-even binary64 certificate."""
    try:
        result = float(value)
    except (OverflowError, ValueError):
        return unavailable("numerical_failure", "precision_exhausted", records)
    if not math.isfinite(result) or (value != 0 and abs(Fraction.from_float(result)-value) > Fraction(1, 10**12)*abs(value)):
        return unavailable("numerical_failure", "precision_exhausted", records)
    return Outcome(result, records=records, flags=flags, **coverage)

def quote_faults(quote, definition, request):
    faults = []
    if quote.currency != definition.currency:
        faults.append(("invalid_input", "currency_mismatch"))
    if any(x is not None and x < 0 for x in (quote.bid, quote.ask)):
        faults.append(("invalid_input", "negative_quote"))
    if quote.bid is not None and quote.ask is not None and quote.bid > quote.ask:
        faults.append(("invalid_input", "crossed_quote"))
    if request.valuation_ns - quote.event_ns > request.eligibility.max_quote_age_ns:
        faults.append(("ineligible_input", "stale_quote"))
    if quote.bid is None or quote.ask is None:
        faults.append(("ineligible_input", "one_sided_quote"))
    elif Fraction(quote.bid) + Fraction(quote.ask) == 0:
        faults.append(("undefined", "zero_midpoint"))
    return tuple(faults)

def spread_quote_faults(quote, definition, request):
    """P1 gate for the spread outputs only (OC4/G1, PO-P1-02); quote_faults stays as is for every other output.

    Precedence no_quote (handled by the caller), invalid, crossed, locked, stale: a bid <= 0 is invalid
    and suppresses the crossed and locked gates; locked is its own reason; stale is checked last.
    """
    faults = []
    bid, ask = quote.bid, quote.ask
    if quote.currency != definition.currency:
        faults.append(("invalid_input", "currency_mismatch"))
    if any(x is not None and x < 0 for x in (bid, ask)):
        faults.append(("invalid_input", "negative_quote"))
    elif bid is not None and bid == 0:
        faults.append(("invalid_input", "nonpositive_bid"))
    if bid is not None and ask is not None and bid > 0:
        if bid > ask:
            faults.append(("invalid_input", "crossed_quote"))
        elif bid == ask:
            faults.append(("invalid_input", "locked_market"))
    if request.valuation_ns - quote.event_ns > request.eligibility.max_quote_age_ns:
        faults.append(("ineligible_input", "stale_quote"))
    if bid is None or ask is None:
        faults.append(("ineligible_input", "one_sided_quote"))
    elif Fraction(bid) + Fraction(ask) == 0:
        faults.append(("undefined", "zero_midpoint"))
    return tuple(faults)

def missing(rows, request, missing_reason):
    rows = tuple(rows)
    if not rows:
        return unavailable("missing_input", missing_reason)
    if all(r.known_at_ns > request.knowledge_cutoff_ns for r in rows):
        return unavailable("ineligible_input", "future_known", rows)
    known = tuple(r for r in rows if r.known_at_ns <= request.knowledge_cutoff_ns)
    if known and all(hasattr(r, "event_ns") and r.event_ns > request.valuation_ns for r in known):
        return unavailable("ineligible_input", "future_event", rows)
    return unavailable("ineligible_input", "inactive_interval", rows)

def evaluate_reference(snapshot, request, definition, output_id):
    """Returns an Outcome only for the five contract-scoped reference outputs."""
    records = (definition,)
    if output_id == "contract.multiplier":
        faults = []
        if definition.deliverable != "scalar_underlying":
            faults.append(("unsupported_profile", "unsupported_deliverable"))
        if definition.multiplier <= 0:
            faults.append(("invalid_input", "nonpositive_multiplier"))
        return Outcome(None, tuple(faults), records) if faults else rational_value(Fraction(definition.multiplier), records)
    if output_id == "contract.dte":
        needed = ((request.valuation_ns, request.valuation_ordinal), (definition.fixing_ns, definition.expiry_ordinal))
        found = []
        faults = []
        for instant, ordinal in needed:
            rows = tuple(r for r in snapshot.civil_bindings if r.civil_binding_id == request.civil_binding_id and r.instant_ns == instant)
            record = next((r for r in rows if r.known_at_ns <= request.knowledge_cutoff_ns), None)
            if record is None:
                faults.append(("ineligible_input", "future_known") if rows else ("missing_input", "missing_civil_binding"))
                found.extend(rows)
            else:
                found.append(record)
                if record.ordinal != ordinal or record.timezone_id != definition.timezone_id or definition.civil_binding_id != request.civil_binding_id:
                    faults.append(("invalid_input", "civil_binding_mismatch"))
        records += tuple(found)
        if faults:
            return Outcome(None, tuple(faults), records)
        return rational_value(Fraction(definition.expiry_ordinal-request.valuation_ordinal), records)
    if output_id == "contract.moneyness":
        spot = selection.spot(snapshot, request, definition.underlying_id)
        if spot is None:
            result = missing((r for r in snapshot.spots if r.underlying_id == definition.underlying_id), request, "missing_spot")
            return Outcome(None, result.faults, records+result.records)
        records += (spot,)
        faults = []
        if definition.strike <= 0:
            faults.append(("invalid_input", "nonpositive_strike"))
        if spot.value <= 0:
            faults.append(("invalid_input", "nonpositive_spot"))
        if spot.currency != definition.currency:
            faults.append(("invalid_input", "currency_mismatch"))
        if spot.action_basis_id != definition.action_basis_id:
            faults.append(("invalid_input", "action_basis_mismatch"))
        if request.valuation_ns-spot.event_ns > request.eligibility.max_spot_age_ns:
            faults.append(("ineligible_input", "stale_spot"))
        return Outcome(None, tuple(faults), records) if faults else rational_value(Fraction(definition.strike)/Fraction(spot.value), records)
    if output_id in SPREAD_OUTPUTS:
        quote = selection.quote(snapshot, request, definition.contract_id)
        if quote is None:
            result = missing((r for r in snapshot.quotes if r.contract_id == definition.contract_id), request, "missing_quote")
            return Outcome(None, result.faults, records+result.records)
        records += (quote,)
        faults = spread_quote_faults(quote, definition, request)
        if faults:
            return Outcome(None, faults, records)
        bid, ask = Fraction(quote.bid), Fraction(quote.ask)
        if output_id == "liquidity.spread":
            return rational_value(ask-bid, records)
        if output_id == "liquidity.midpoint":
            return rational_value((ask+bid)/2, records)
        return rational_value(20000*(ask-bid)/(ask+bid), records)
    if output_id == "quality.quote_coverage":
        return quote_coverage(snapshot, request, definition)
    raise ValueError("reference output ID required")

def certificate(snapshot, request, certificate_id):
    record = next((r for r in snapshot.coverage_certificates if r.certificate_id == certificate_id), None)
    if record is None:
        return None, (("ineligible_input", "completeness_unknown"),)
    if record.known_at_ns > request.knowledge_cutoff_ns:
        return record, (("ineligible_input", "future_known"),)
    if not record.complete:
        return record, (("ineligible_input", "incomplete_source"),)
    return record, ()

def quote_coverage(snapshot, request, definition):
    records = (definition,)
    window = next((r for r in snapshot.quote_coverage_windows if r.contract_id == definition.contract_id), None)
    if window is None:
        return unavailable("missing_input", "missing_sampling_plan", records)
    records += (window,)
    if window.known_at_ns > request.knowledge_cutoff_ns:
        return unavailable("ineligible_input", "future_known", records)
    cert, faults = certificate(snapshot, request, window.completeness_certificate_id)
    if cert is not None:
        records += (cert,)
    if faults:
        return Outcome(None, faults, records)
    expected = len(window.expected_sample_ids)
    if not expected:
        return Outcome(None, (("undefined", "empty_sampling_plan"),), records,
                       observed=0, expected=0, population_id=window.sampling_plan_id)
    observed = 0
    for sample_id in window.expected_sample_ids:
        quote = selection.quote(snapshot, request, definition.contract_id, sample_id)
        if quote is not None:
            records += (quote,)
            if window.window_start_ns <= quote.event_ns < window.window_end_ns and not quote_faults(quote, definition, request):
                observed += 1
    return rational_value(Fraction(observed, expected), records, ("partial_quote_coverage",) if observed < expected else (), observed=observed, expected=expected, population_id=window.sampling_plan_id)

def chain_activity(snapshot, request):
    window = snapshot.activity_window
    if window is None:
        return unavailable("missing_input", "missing_population")
    records = (window,)
    if window.known_at_ns > request.knowledge_cutoff_ns:
        return unavailable("ineligible_input", "future_known", records)
    faults = []
    for certificate_id in (window.trade_completeness_certificate_id, window.quote_completeness_certificate_id):
        cert, problems = certificate(snapshot, request, certificate_id)
        if cert is not None:
            records += (cert,)
        faults.extend(problems)
        if cert is not None and cert.kind == "current_quotes" and cert.window_start_ns != request.valuation_ns:
            from option_feature_contracts import ContractValidationError
            raise ContractValidationError("/activity_window", "invalid_config", "current-quote certificate must match valuation")
    if window.window_end_ns > request.valuation_ns:
        faults.append(("ineligible_input", "future_event"))
    definitions = {}
    for contract_id in window.expected_contract_ids:
        definition = selection.definition(snapshot, request, contract_id)
        if definition is None:
            faults.append(("missing_input", "missing_definition"))
        else:
            records += (definition,)
            definitions[contract_id] = definition
            if definition.underlying_id != window.underlying_id:
                faults.append(("invalid_input", "action_basis_mismatch"))
    if faults:
        return Outcome(None, tuple(faults), records)
    expected = len(window.expected_contract_ids)
    if not expected:
        return Outcome(None, (("undefined", "empty_population"),), records,
                       observed=0, expected=0, population_id=window.population_id)
    traded = set()
    for trade_id in window.trade_ids:
        trade = selection.trade(snapshot, request, trade_id)
        if trade is not None:
            records += (trade,)
            if trade.classification == "regular" and trade.quantity > 0 and window.window_start_ns <= trade.event_ns < window.window_end_ns:
                traded.add(trade.contract_id)
    active = set()
    for contract_id in window.expected_contract_ids:
        quote = selection.quote(snapshot, request, contract_id)
        if quote is not None:
            records += (quote,)
            if contract_id in traded and not quote_faults(quote, definitions[contract_id], request):
                active.add(contract_id)
    observed = len(active)
    return rational_value(Fraction(100*observed, expected), records, ("zero_activity",) if not observed else (), observed=observed, expected=expected, population_id=window.population_id)
