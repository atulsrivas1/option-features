"""Referential, correction and semantic admission separate from arithmetic."""
from collections import defaultdict
from . import records as r
from .codec import _validate, fail, flow_record_digest


def _unique(values, key, path):
    result = {}
    for index, value in enumerate(values):
        identity = key(value)
        if identity in result:
            fail('identity_conflict', f'{path}/{index}')
        result[identity] = value
    return result


def _string_members(values, path):
    if len(set(values)) != len(values):
        fail('identity_conflict', path)


def _chains(values, family, path):
    root_field = family + '_id'
    indexed = _unique(values, lambda x: (getattr(x, root_field), x.revision_id), path)
    chains = defaultdict(list)
    children = set()
    for index, value in enumerate(values):
        pointer = f'{path}/{index}'
        root_id = getattr(value, root_field)
        chains[root_id].append(value)
        if value.kind == 'new':
            continue
        target_key = (getattr(value, 'target_' + root_field), value.target_revision_id)
        if target_key not in indexed:
            fail('missing_identity', pointer + '/target_revision_id')
        target = indexed[target_key]
        if target_key in children or target.kind == 'cancel':
            fail('invalid_correction', pointer + '/target_revision_id')
        children.add(target_key)
        immutable = ('contract_id', 'stream_id', 'event_ns')
        if family == 'execution':
            immutable += ('session_id', 'signing_boundary_ns')
        if (any(getattr(value, f) != getattr(target, f) for f in immutable)
            or value.position <= target.position or value.known_at_ns < target.known_at_ns):
            fail('invalid_correction', pointer)
    for identity, chain in sorted(chains.items()):
        chain.sort(key=lambda v: v.position)
        if chain[0].kind != 'new' or sum(v.kind == 'new' for v in chain) != 1:
            fail('invalid_correction', path)
        for previous, current in zip(chain, chain[1:]):
            if current.target_revision_id != previous.revision_id:
                fail('invalid_correction', path)
    return dict(chains)


def select_revision(chain, cutoff, cursors):
    """Internal pure selection shared with the evaluator, root order preserved."""
    selected = None
    for revision in chain:
        if revision.known_at_ns <= cutoff and revision.position <= cursors[revision.stream_id]:
            selected = revision
    return selected


def flow_validate_snapshot(snapshot, limits=r.FLOW_LIMITS):
    if type(snapshot) is not r.FlowSnapshot:
        fail('type_mismatch', '/snapshot')
    _validate(limits, r.FLOW_LIMITS, '/limits', [0])
    _validate(snapshot, limits, '/snapshot', [0])
    groups = _unique(snapshot.groups, lambda x: x.group_id, '/snapshot/groups')
    refs = _unique(snapshot.references, lambda x: x.reference_id, '/snapshot/references')
    bindings = _unique(snapshot.bindings, lambda x: x.binding_id, '/snapshot/bindings')
    cursors = _unique(snapshot.cursors, lambda x: x.stream_id, '/snapshot/cursors')
    populations = _unique(snapshot.populations, lambda x: x.population_id, '/snapshot/populations')
    _unique(snapshot.context_certificates, lambda x: x.certificate_id, '/snapshot/context_certificates')
    _unique(snapshot.baselines, lambda x: x.baseline_id, '/snapshot/baselines')
    _unique(snapshot.baselines, lambda x: (x.group_id,x.slot_id), '/snapshot/baselines')
    if len(groups) > limits.max_groups or len(cursors) > limits.max_streams:
        fail('resource_limit', '/snapshot')
    for family in ('references','executions','quotes','populations','context_certificates','baselines'):
        for index, record in enumerate(getattr(snapshot, family)):
            if record.input_binding_id not in bindings:
                fail('missing_identity', f'/snapshot/{family}/{index}/input_binding_id')
    positions = set(); stream_contract = {}; event_order = defaultdict(list)
    for family in ('executions','quotes'):
        for index, record in enumerate(getattr(snapshot, family)):
            pointer = f'/snapshot/{family}/{index}'
            if record.stream_id not in cursors:
                fail('missing_identity', pointer + '/stream_id')
            if record.position > cursors[record.stream_id].max_position:
                fail('identity_mismatch', pointer + '/position')
            position = record.stream_id, record.position
            if position in positions:
                fail('identity_conflict', pointer + '/position')
            positions.add(position)
            if record.stream_id in stream_contract and stream_contract[record.stream_id] != record.contract_id:
                fail('identity_mismatch', pointer + '/stream_id')
            stream_contract[record.stream_id] = record.contract_id
            if record.kind == 'new':
                event_order[record.stream_id].append((record.position, record.event_ns))
            if family == 'executions':
                if record.reference_id not in refs:
                    fail('missing_identity', pointer + '/reference_id')
                reference = refs[record.reference_id]
                if record.kind == 'new' and reference.known_at_ns > record.signing_boundary_ns:
                    fail('identity_mismatch', pointer + '/reference_id')
                if (reference.contract_id != record.contract_id
                    or not reference.effective_from_ns <= record.event_ns
                    or (reference.effective_to_ns is not None and record.event_ns >= reference.effective_to_ns)
                    or (reference.civil_instant_ns is not None and reference.civil_instant_ns != record.event_ns)):
                    fail('identity_mismatch', pointer + '/reference_id')
    for stream, points in sorted(event_order.items()):
        events = [event for _, event in sorted(points)]
        if events != sorted(events):
            fail('identity_mismatch', '/snapshot/cursors')
    execution_chains = _chains(snapshot.executions, 'execution', '/snapshot/executions')
    quote_chains = _chains(snapshot.quotes, 'quote', '/snapshot/quotes')
    for chain in execution_chains.values():
        root_ref = refs[chain[0].reference_id]
        definition = ('contract_id','underlying_id','currency','action_basis_id','right','strike','multiplier','expiry_ordinal')
        for revision in chain[1:]:
            reference = refs[revision.reference_id]
            if any(getattr(reference, f) != getattr(root_ref, f) for f in definition):
                fail('identity_mismatch', '/snapshot/references')
    for index, group in enumerate(snapshot.groups):
        pointer = f'/snapshot/groups/{index}'
        _string_members(group.contract_ids, pointer + '/contract_ids')
        for contract in group.contract_ids:
            members = [ref for ref in refs.values() if ref.contract_id == contract]
            if not members:
                fail('missing_identity', pointer + '/contract_ids')
            for reference in members:
                if (reference.underlying_id != group.underlying_id or reference.currency != group.currency
                    or reference.action_basis_id != group.action_basis_id
                    or (group.right is not None and reference.right != group.right)
                    or (group.expiry_ordinal is not None and reference.expiry_ordinal != group.expiry_ordinal)):
                    fail('identity_mismatch', pointer)
    for index, population in enumerate(snapshot.populations):
        pointer = f'/snapshot/populations/{index}'
        if population.group_id not in groups:
            fail('missing_identity', pointer + '/group_id')
        group = groups[population.group_id]
        if set(population.expected_contract_ids) != set(group.contract_ids):
            fail('identity_mismatch', pointer + '/expected_contract_ids')
        for field, collection in (('expected_execution_ids', execution_chains), ('expected_quote_ids', quote_chains)):
            _string_members(getattr(population, field), pointer + '/' + field)
            for identity in getattr(population, field):
                if identity not in collection:
                    fail('missing_identity', pointer + '/' + field)
                if collection[identity][0].contract_id not in group.contract_ids:
                    fail('identity_mismatch', pointer + '/' + field)
    quote_sessions = {}
    for index, certificate in enumerate(snapshot.context_certificates):
        pointer = f'/snapshot/context_certificates/{index}'
        _string_members(certificate.expected_root_ids, pointer + '/expected_root_ids')
        collection = execution_chains if certificate.kind == 'execution_prefix' else quote_chains
        if certificate.stream_id not in cursors:
            fail('missing_identity', pointer + '/stream_id')
        for identity in certificate.expected_root_ids:
            if identity not in collection:
                fail('missing_identity', pointer + '/expected_root_ids')
            root = collection[identity][0]
            if (root.contract_id != certificate.contract_id or root.stream_id != certificate.stream_id
                or root.position > certificate.through_position or root.event_ns < certificate.session_start_ns
                or (certificate.kind == 'execution_prefix' and root.session_id != certificate.session_id)):
                fail('identity_mismatch', pointer + '/expected_root_ids')
            if certificate.kind == 'quote_prefix':
                if identity in quote_sessions and quote_sessions[identity] != certificate.session_id:
                    fail('identity_conflict', pointer + '/session_id')
                quote_sessions[identity] = certificate.session_id
    for index, baseline in enumerate(snapshot.baselines):
        pointer = f'/snapshot/baselines/{index}'
        if baseline.group_id not in groups:
            fail('missing_identity', pointer + '/group_id')
        if sum(x.group_id == baseline.group_id for x in snapshot.baselines) > limits.max_baselines_per_group:
            fail('resource_limit', pointer)
        _string_members(baseline.member_record_sha256s, pointer + '/member_record_sha256s')
        for field in ('contracts','trade_count','premium'):
            value = getattr(baseline, field)
            if value is not None and (value.numerator < 0 or (field != 'premium' and value.denominator != 1)):
                fail('invalid_scalar', pointer + '/' + field)
    return None


def flow_validate_request(request, snapshot=None):
    if type(request) is not r.FlowRequest:
        fail('type_mismatch', '/request')
    _validate(request.limits, r.FLOW_LIMITS, '/request/limits', [0])
    _validate(request, request.limits, '/request', [0])
    for field in ('group_ids','output_ids'):
        _string_members(getattr(request, field), '/request/' + field)
    from .outputs import OUTPUT_UNITS
    for index, output in enumerate(request.output_ids):
        if output not in OUTPUT_UNITS:
            fail('invalid_scalar', f'/request/output_ids/{index}')
    targets = _unique(request.baseline_targets, lambda x: x.group_id, '/request/baseline_targets')
    cuts = _unique(request.cut_cursors, lambda x: x.stream_id, '/request/cut_cursors')
    if snapshot is None:
        return None
    flow_validate_snapshot(snapshot, request.limits)
    groups = {g.group_id:g for g in snapshot.groups}
    cursors = {c.stream_id:c.max_position for c in snapshot.cursors}
    if set(cuts) != set(cursors) or any(c.max_position > cursors[s] for s,c in cuts.items()):
        fail('identity_mismatch', '/request/cut_cursors')
    for group in request.group_ids:
        if group not in groups:
            fail('missing_identity', '/request/group_ids')
    chains = _chains(snapshot.executions, 'execution', '/snapshot/executions')
    cut_values = {s:c.max_position for s,c in cuts.items()}
    for identity, chain in sorted(chains.items()):
        selected = select_revision(chain, request.knowledge_cutoff_ns, cut_values)
        root = chain[0]
        if (selected is not None and selected.kind != 'cancel' and selected.condition == 'regular'
            and request.window_start_ns <= root.event_ns < request.window_end_ns
            and any(root.contract_id in groups[g].contract_ids for g in request.group_ids)
            and root.signing_boundary_ns > request.knowledge_cutoff_ns):
            fail('identity_mismatch', '/request/knowledge_cutoff_ns')
    policy_hash = flow_record_digest('flow_policy', request.policy)
    for group_id, target in targets.items():
        if group_id not in groups:
            fail('missing_identity', '/request/baseline_targets')
        _string_members(target.slot_ids, '/request/baseline_targets/slot_ids')
        group = groups[group_id]; previous = None
        for slot in target.slot_ids:
            baseline = next((x for x in snapshot.baselines if x.group_id == group_id and x.slot_id == slot), None)
            if baseline is None:
                continue
            if (baseline.policy_sha256 != policy_hash or baseline.horizon_id != request.policy.horizon_id
                or baseline.currency != group.currency or baseline.action_basis_id != group.action_basis_id
                or baseline.window_end_ns - baseline.window_start_ns != request.window_end_ns - request.window_start_ns
                or baseline.window_end_ns > request.window_start_ns
                or baseline.session_ordinal >= request.target_session_ordinal
                or (previous is not None and (baseline.session_ordinal <= previous.session_ordinal
                                             or baseline.window_start_ns < previous.window_end_ns))):
                fail('identity_mismatch', '/request/baseline_targets')
            previous = baseline
    predicted = len(request.group_ids) * len(request.output_ids) * max(1, len(chains))
    # Exact conservative bound is refined by selected per-group eligible roots.
    cluster_outputs = sum(x in PER_CLUSTER for x in request.output_ids)
    predicted = 0
    for identity in request.group_ids:
        eligible = sum(1 for chain in chains.values()
                       if chain[0].contract_id in groups[identity].contract_ids
                       and request.window_start_ns <= chain[0].event_ns < request.window_end_ns
                       and (selected := select_revision(chain, request.knowledge_cutoff_ns, cut_values)) is not None
                       and selected.kind != 'cancel' and selected.condition == 'regular')
        predicted += len(request.output_ids) - cluster_outputs + max(1, eligible) * cluster_outputs
    if predicted > request.limits.max_result_rows:
        fail('resource_limit', '/request/output_ids')
    return None


PER_CLUSTER = frozenset(('execution.cluster_premium','execution.cluster_trade_count',
                        'execution.cluster_contracts','execution.cluster_span_ns',
                        'execution.cluster_venue_count'))


def flow_validate_results(results, request=None):
    if request is not None:
        flow_validate_request(request)
    _validate(results, request.limits if request is not None else r.FLOW_LIMITS, '/results', [0])
    _unique(results, lambda x:(x.group_id,x.output_id,x.cluster_id), '/results')
    from .outputs import OUTPUT_UNITS
    reasons = {'available': {'ok'}, 'undefined': {'zero_denominator','zero_mad','insufficient_pairs','zero_variance'},
               'unavailable': {'incomplete_population','missing_baseline','incomplete_baseline','insufficient_history',
                               'missing_dte_reference','missing_spot_reference','missing_venue_reference','future_reference',
                               'stale_reference','incompatible_equity_operand','missing_equity_operand'},
               'unsupported': {'unsupported_profile','unsupported_deliverable','equity_integration_unqualified'}}
    request_hash=flow_record_digest('flow_request',request) if request is not None else None
    policy_hash=flow_record_digest('flow_policy',request.policy) if request is not None else None
    census=defaultdict(list)
    group_coverage={}
    group_cluster_ids=defaultdict(set)
    for index, row in enumerate(results):
        pointer = f'/results/{index}'
        if row.output_id not in OUTPUT_UNITS or row.unit != OUTPUT_UNITS[row.output_id]:
            fail('identity_mismatch', pointer + '/unit')
        if row.output_id in ('cross.share_equivalent_participation',
                             'cross.premium_turnover_participation','cross.lag_correlation'):
            for field,expected in (('status','unsupported'),('reason','equity_integration_unqualified'),
                                   ('value',None),('numerator',None),('denominator',None)):
                if getattr(row,field)!=expected:
                    fail('identity_mismatch',pointer+'/'+field)
            if row.evidence.required_producer_ids!=('EQ153','EQ158'):
                fail('identity_mismatch',pointer+'/evidence/required_producer_ids')
        if row.status not in reasons or row.reason not in reasons[row.status]:
            fail('invalid_scalar', pointer + '/reason')
        if (row.status == 'available') != (row.value is not None):
            fail('identity_mismatch', pointer + '/value')
        if row.status == 'available' and row.available_at_ns > row.knowledge_cutoff_ns:
            fail('identity_mismatch', pointer + '/available_at_ns')
        coverage = row.coverage
        if (coverage.signed_count + coverage.unknown_sign_count != coverage.eligible_count
            or coverage.observed_count != coverage.eligible_count
            or coverage.dte_eligible_count > coverage.eligible_count
            or coverage.otm_eligible_count > coverage.eligible_count
            or (coverage.population_complete and coverage.expected_count != coverage.observed_count)
            or (not coverage.population_complete and coverage.expected_count is not None)):
            fail('identity_mismatch', pointer + '/coverage')
        if (row.cluster_id is None) != (row.evidence.cluster is None):
            fail('identity_mismatch', pointer + '/cluster_id')
        if row.evidence.cluster is not None and row.cluster_id != row.evidence.cluster.cluster_id:
            fail('identity_mismatch', pointer + '/cluster_id')
        if row.output_id not in PER_CLUSTER and row.cluster_id is not None:
            fail('identity_mismatch',pointer+'/cluster_id')
        if request is not None:
            if row.group_id not in request.group_ids or row.output_id not in request.output_ids:
                fail('identity_mismatch',pointer+'/output_id')
            for field,expected in (
                ('request_sha256',request_hash),('policy_sha256',policy_hash),
                ('window_start_ns',request.window_start_ns),('window_end_ns',request.window_end_ns),
                ('knowledge_cutoff_ns',request.knowledge_cutoff_ns),
                ('temporal_profile',request.policy.temporal_profile),('formula_version',request.formula_version)):
                if getattr(row,field)!=expected:
                    fail('identity_mismatch',pointer+'/'+field)
            if any(w.method!=request.policy.signing_profile for w in row.sign_witnesses):
                fail('identity_mismatch',pointer+'/sign_witnesses')
            if row.group_id in group_coverage and row.coverage!=group_coverage[row.group_id]:
                fail('identity_mismatch',pointer+'/coverage')
            group_coverage[row.group_id]=row.coverage
            census[(row.group_id,row.output_id)].append(row)
            if row.output_id in PER_CLUSTER and row.cluster_id is not None:
                group_cluster_ids[row.group_id].add(row.cluster_id)
    if request is not None:
        for group in request.group_ids:
            for output in request.output_ids:
                rows=census[(group,output)]
                if output not in PER_CLUSTER:
                    if len(rows)!=1 or rows[0].cluster_id is not None:
                        fail('identity_mismatch','/results')
                    continue
                unsupported=request.policy.signing_profile!='option-quote-midpoint1'
                incomplete=group in group_coverage and not group_coverage[group].population_complete
                if unsupported or incomplete:
                    expected=('unsupported','unsupported_profile') if unsupported else ('unavailable','incomplete_population')
                    if len(rows)!=1 or rows[0].cluster_id is not None or (rows[0].status,rows[0].reason)!=expected:
                        fail('identity_mismatch','/results')
                elif any(row.cluster_id is None for row in rows):
                    fail('identity_mismatch','/results')
                elif {row.cluster_id for row in rows}!=group_cluster_ids[group]:
                    fail('identity_mismatch','/results')
    return None


def carried_knowledge(snapshot):
    """All carried clocks, rather than just economically contributing clocks."""
    for family in ('references','executions','quotes','populations','context_certificates','baselines'):
        for value in getattr(snapshot, family):
            yield value.known_at_ns
            for name in ('civil_known_at_ns','spot_known_at_ns','observed_side_known_at_ns'):
                clock = getattr(value, name, None)
                if clock is not None:
                    yield clock


def validate_checkpoint(checkpoint):
    if type(checkpoint) is not r.FlowCheckpoint:
        fail('type_mismatch', '/checkpoint')
    _validate(checkpoint, r.FLOW_LIMITS, '/checkpoint', [0])
    request, history = checkpoint.prior_request, checkpoint.history
    flow_validate_request(request, history)
    if (checkpoint.history_sha256 != flow_record_digest('flow_snapshot', history)
        or checkpoint.prior_request_sha256 != flow_record_digest('flow_request', request)
        or checkpoint.policy_sha256 != flow_record_digest('flow_policy', request.policy)):
        fail('digest_mismatch', '/checkpoint')
    if ({c.stream_id:c.max_position for c in history.cursors} !=
        {c.stream_id:c.max_position for c in request.cut_cursors}
        or any(clock > request.knowledge_cutoff_ns for clock in carried_knowledge(history))):
        fail('checkpoint_cut_mismatch', '/checkpoint')


def validate_publication(publication):
    from hashlib import sha256
    from .codec import _json
    if type(publication) is not r.FlowPublication:
        fail('type_mismatch', '/publication')
    flow_validate_request(publication.request)
    _validate(publication, publication.request.limits, '/publication', [0])
    flow_validate_results(publication.results, publication.request)
    if publication.request_sha256 != flow_record_digest('flow_request', publication.request):
        fail('digest_mismatch', '/publication/request_sha256')
    expected_work = sha256(b'option-flow-work1\n' + _json([
        publication.snapshot_sha256, publication.request_sha256,
        publication.cohort_sha256, publication.input_checkpoint_sha256])).hexdigest()
    if publication.work_sha256 != expected_work:
        fail('digest_mismatch', '/publication/work_sha256')
    bindings = _unique(publication.bindings, lambda b:b.binding_id, '/publication/bindings')
    for index, result in enumerate(publication.results):
        if (result.snapshot_sha256 != publication.snapshot_sha256
            or result.checkpoint_sha256 != publication.input_checkpoint_sha256
            or not set(result.dependency_binding_ids) <= set(bindings)):
            fail('identity_mismatch', f'/publication/results/{index}')
    if publication.output_checkpoint is not None:
        validate_checkpoint(publication.output_checkpoint)
        if (publication.output_checkpoint.history_sha256 != publication.snapshot_sha256
            or publication.output_checkpoint.prior_request_sha256 != publication.request_sha256
            or any(bindings.get(b.binding_id) != b for b in publication.output_checkpoint.history.bindings)):
            fail('identity_mismatch', '/publication/output_checkpoint')
    if not publication.results and not set(publication.request.output_ids) <= PER_CLUSTER:
        fail('identity_mismatch', '/publication/results')
