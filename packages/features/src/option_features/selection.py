"""Original pure causal selection for the frozen option profile."""
from option_feature_contracts import ContractValidationError

def latest(rows, eligible, rank, path):
    candidates = tuple(row for row in rows if eligible(row))
    if not candidates:
        return None
    winning_rank = max(rank(row) for row in candidates)
    winners = tuple(row for row in candidates if rank(row) == winning_rank)
    if len(winners) != 1:
        raise ContractValidationError(path, "ambiguous_revision", "distinct revisions share winning causal rank")
    return winners[0]

def active(row, request):
    return row.known_at_ns <= request.knowledge_cutoff_ns and row.effective_from_ns <= request.valuation_ns and (row.effective_to_ns is None or request.valuation_ns < row.effective_to_ns)

def definition(snapshot, request, contract_id):
    return latest((r for r in snapshot.definitions if r.contract_id == contract_id), lambda r: active(r, request), lambda r: (r.effective_from_ns, r.known_at_ns), "/definitions")

def spot(snapshot, request, underlying_id):
    return latest((r for r in snapshot.spots if r.underlying_id == underlying_id), lambda r: r.known_at_ns <= request.knowledge_cutoff_ns and r.event_ns <= request.valuation_ns, lambda r: (r.event_ns, r.known_at_ns), "/spots")

def quote(snapshot, request, contract_id, sample_id=None):
    return latest((r for r in snapshot.quotes if r.contract_id == contract_id and (sample_id is None or r.sample_id == sample_id)), lambda r: r.known_at_ns <= request.knowledge_cutoff_ns and r.event_ns <= request.valuation_ns, lambda r: (r.event_ns, r.sequence, r.known_at_ns), "/quotes")

def model_fact(snapshot, request, definition, kind):
    rows = tuple(r for r in snapshot.model_facts if r.underlying_id == definition.underlying_id and r.kind == kind)
    if kind == "volatility":
        specific = tuple(r for r in rows if r.contract_id == definition.contract_id and active(r, request))
        rows = specific if specific else tuple(r for r in rows if r.contract_id is None)
    else:
        rows = tuple(r for r in rows if r.contract_id is None)
    return latest(rows, lambda r: active(r, request), lambda r: (r.effective_from_ns, r.known_at_ns), "/model_facts")

def supplied(snapshot, request, contract_id, output_id):
    return latest((r for r in snapshot.supplied_metrics if r.contract_id == contract_id and r.output_id == output_id), lambda r: r.known_at_ns <= request.knowledge_cutoff_ns and r.event_ns <= request.valuation_ns, lambda r: (r.event_ns, r.known_at_ns), "/supplied_metrics")

def trade(snapshot, request, trade_id):
    return latest((r for r in snapshot.trades if r.trade_id == trade_id), lambda r: r.known_at_ns <= request.knowledge_cutoff_ns, lambda r: r.known_at_ns, "/trades")
