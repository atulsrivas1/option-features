"""Original supplied-fact option mathematics; no I/O, discovery or caches.

The private stepping interface permits workers to observe cancellation between
deterministic reduction steps without callbacks or mutable global state.
"""
from dataclasses import replace
from hashlib import sha256
from itertools import groupby

from option_flow_contracts import (
    FlowSnapshot, FlowResult, FlowCoverage, FlowSignWitness, FlowOperand,
    FlowPartitionWeight, FlowExcluded, FlowCluster, FlowEvidence,
    FlowCheckpoint, FlowValidationError, flow_record_digest,
    flow_validate_request, flow_validate_snapshot, flow_validate_results,
    flow_canonical_bytes,
)
from option_flow_contracts.codec import _json, fail, _validate
from option_flow_contracts.records import FLOW_LIMITS
from option_flow_contracts.outputs import OUTPUT_UNITS
from option_flow_contracts.validation import (
    _chains, select_revision, PER_CLUSTER, carried_knowledge, validate_checkpoint,
)
from .arithmetic import ExactArithmetic


def _hash(domain, payload):
    return sha256((domain+'\n').encode()+_json(payload)).hexdigest()


def _root_view(chains, cutoff, cursors):
    return {identity:select_revision(chain,cutoff,cursors)
            for identity,chain in sorted(chains.items())}


def _context_certificate_steps(snapshot, root, kind, cutoff, cursors, chains):
    candidates=[]
    for certificate in snapshot.context_certificates:
        if (certificate.kind == kind and certificate.contract_id == root.contract_id
            and certificate.session_id == root.session_id and certificate.stream_id == root.stream_id
            and certificate.through_position >= root.position and certificate.complete
            and certificate.known_at_ns <= cutoff):
            candidates.append(certificate)
        yield None
    candidates.sort(key=lambda c:(c.through_position,c.certificate_id))
    if not candidates:
        return None,False
    memberships = []
    for certificate in candidates:
        retained=set();target_members=set();expected=set()
        for identity,chain in chains.items():
            if (chain[0].contract_id == root.contract_id and chain[0].stream_id == root.stream_id
                and certificate.session_start_ns <= chain[0].event_ns
                and chain[0].position <= certificate.through_position
                and (kind != 'execution_prefix' or chain[0].session_id == root.session_id)):
                retained.add(identity)
                if chain[0].position<=root.position:target_members.add(identity)
            yield None
        for identity in certificate.expected_root_ids:
            expected.add(identity)
            yield None
        if retained != expected:
            fail('identity_mismatch','/snapshot/context_certificates')
        # Compare the membership covered through the target, allowing longer certificates.
        memberships.append(target_members)
    for membership in memberships[1:]:
        if membership!=memberships[0]:fail('identity_conflict','/snapshot/context_certificates')
        yield None
    certificate = candidates[0]
    complete=True
    for identity in certificate.expected_root_ids:
        if select_revision(chains[identity],cutoff,cursors) is None:complete=False
        yield None
    return certificate,complete


def _sign_steps(snapshot, root, selected, policy, policy_hash, refs, executions, quotes, cursors, arithmetic):
    exact,add,sub,mul=arithmetic.exact,arithmetic.add,arithmetic.sub,arithmetic.mul
    method = policy.signing_profile
    A = root.signing_boundary_ns
    reference = refs[root.reference_id]
    context = [(root.position,'flow_reference',reference)]
    dependency = [reference]
    certificate = None; quote = None; predecessor = None
    diagnostics = set(); sign = 'unknown'; reason = 'observed_missing'
    clocks = [selected.known_at_ns]
    if reference.known_at_ns <= A:
        clocks.append(reference.known_at_ns)
    if method == 'option-observed-side1':
        if root.observed_side_semantics_id is None:
            reason = 'observed_missing'
        elif root.observed_side_known_at_ns > A:
            reason = 'observed_future'
        else:
            sign = root.observed_side
            reason = {'buy':'observed_buy','sell':'observed_sell','unknown':'observed_unknown'}[sign]
            clocks.append(root.observed_side_known_at_ns)
        context.append((root.position,'flow_execution',root))
    else:
        source = quotes if method == 'option-quote-midpoint1' else executions
        kind = 'quote_prefix' if method == 'option-quote-midpoint1' else 'execution_prefix'
        certificate, complete = yield from _context_certificate_steps(snapshot,root,kind,A,cursors,source)
        if certificate is not None:
            dependency.append(certificate); clocks.append(certificate.known_at_ns)
        if not complete:
            reason = 'quote_missing' if method == 'option-quote-midpoint1' else 'tick_seed_unavailable'
            diagnostics.add('incomplete_context')
        elif method == 'option-quote-midpoint1':
            candidates = []
            for identity, chain in sorted(quotes.items()):
                qroot = chain[0]
                revision = select_revision(chain,A,cursors)
                if (qroot.contract_id == root.contract_id and qroot.stream_id == root.stream_id
                    and identity in certificate.expected_root_ids
                    and qroot.event_ns >= certificate.session_start_ns
                    and qroot.position < root.position and qroot.event_ns <= root.event_ns
                    and revision is not None and revision.kind != 'cancel'):
                    candidates.append((qroot.position,revision))
                yield None
            quote = max(candidates,key=lambda x:x[0])[1] if candidates else None
            if quote is None:
                future=False
                for identity,chain in quotes.items():
                    if (identity in certificate.expected_root_ids
                        and chain[0].event_ns >= certificate.session_start_ns
                        and chain[0].contract_id == root.contract_id and chain[0].stream_id == root.stream_id
                        and chain[0].position < root.position and chain[0].event_ns <= root.event_ns
                        and select_revision(chain,A,cursors) is None):future=True
                    yield None
                reason = 'quote_future' if future else 'quote_missing'
            else:
                qroot = quotes[quote.quote_id][0]
                context.append((qroot.position,'flow_quote',quote)); dependency.append(quote)
                clocks.append(quote.known_at_ns)
                causes = []
                if root.event_ns-quote.event_ns > policy.max_quote_age_ns:
                    causes.append('quote_stale')
                if quote.bid is None or quote.ask is None:
                    causes.append('quote_one_sided')
                elif quote.bid == quote.ask:
                    causes.append('quote_locked')
                elif quote.bid > quote.ask:
                    causes.append('quote_crossed')
                if quote.condition != 'regular':
                    diagnostics.add('excluded_quote'); causes.insert(0,'quote_missing')
                if causes:
                    reason = causes[0]; diagnostics.update(causes)
                else:
                    comparison = arithmetic.compare(mul(exact(selected.price),2),add(exact(quote.bid),exact(quote.ask)))
                    sign = 'buy' if comparison > 0 else 'sell' if comparison < 0 else 'unknown'
                    reason = {'buy':'quote_above_midpoint','sell':'quote_below_midpoint','unknown':'quote_midpoint'}[sign]
                    if selected.price < quote.bid or selected.price > quote.ask:
                        diagnostics.add('outside_spread')
        else:
            candidates = []
            for identity, chain in sorted(executions.items()):
                eroot = chain[0]; revision = select_revision(chain,A,cursors)
                predecessor_reference=refs[eroot.reference_id]
                definition_fields=('underlying_id','currency','action_basis_id','right','strike','multiplier','expiry_ordinal')
                if (eroot.contract_id == root.contract_id and eroot.session_id == root.session_id
                    and identity in certificate.expected_root_ids
                    and eroot.event_ns >= certificate.session_start_ns
                    and predecessor_reference.known_at_ns <= A
                    and all(getattr(predecessor_reference,f)==getattr(reference,f) for f in definition_fields)
                    and eroot.stream_id == root.stream_id and eroot.position < root.position
                    and revision is not None and revision.kind != 'cancel' and revision.condition == 'regular'):
                    candidates.append((eroot.position,revision))
                yield None
            last_price = None; carry = 'unknown'
            for position, previous in sorted(candidates):
                prior_ref = refs[executions[previous.execution_id][0].reference_id]
                context.extend(((position,'flow_execution',previous),(position,'flow_reference',prior_ref)))
                dependency.extend((previous,prior_ref)); clocks.append(previous.known_at_ns)
                if prior_ref.known_at_ns <= A:
                    clocks.append(prior_ref.known_at_ns)
                if last_price is not None:
                    if previous.price > last_price: carry = 'buy'
                    elif previous.price < last_price: carry = 'sell'
                last_price = previous.price; predecessor = previous
                yield None
            if last_price is None:
                reason = 'tick_initial_unknown'
            elif selected.price > last_price:
                sign,reason = 'buy','tick_up'
            elif selected.price < last_price:
                sign,reason = 'sell','tick_down'
            else:
                sign = carry; reason = 'tick_carried' if carry != 'unknown' else 'tick_initial_unknown'
    # F43: minimal operand membership, deduplicated immutable identities. A
    # reference reused by several roots is anchored at their minimum position.
    identities={'flow_reference':('reference_id',),'flow_execution':('execution_id','revision_id'),
                'flow_quote':('quote_id','revision_id')}
    minimal={}
    for position,type_name,value in context:
        identity=(type_name,tuple(getattr(value,name) for name in identities[type_name]))
        if identity not in minimal or position<minimal[identity][0]:
            minimal[identity]=(position,type_name,value)
        yield None
    context_hashes=[]
    for _,type_name,value in sorted(minimal.values(),key=lambda x:(x[0],x[1])):
        context_hashes.append(flow_record_digest(type_name,value))
        yield None
    context_hash = _hash('option-flow-context1',[A,policy_hash,context_hashes,
                         flow_record_digest('flow_context_certificate',certificate) if certificate else None])
    failure_reasons={'observed_missing','observed_future','tick_seed_unavailable',
                     'quote_missing','quote_future','quote_order_unknown','quote_stale',
                     'quote_one_sided','quote_locked','quote_crossed'}
    if reason in failure_reasons:diagnostics.add(reason)
    witness = FlowSignWitness(root.execution_id,selected.revision_id,sign,method,reason,
                              tuple(sorted(diagnostics)),A,context_hash,
                              certificate.certificate_id if certificate else None,
                              quote.quote_id if quote else None,quote.revision_id if quote else None,
                              predecessor.execution_id if predecessor else None,
                              predecessor.revision_id if predecessor else None)
    return witness,dependency,max(clocks,default=0)


def _reference_state(root, reference, policy):
    """Independent causal reference admission, including reviewed F41 policy."""
    A = root.signing_boundary_ns; diagnostics_dte=set(); diagnostics_otm=set()
    definition_ok = reference.known_at_ns <= A
    dte_ok = definition_ok and reference.civil_ordinal is not None and reference.civil_known_at_ns <= A
    if reference.civil_ordinal is not None and reference.expiry_ordinal < reference.civil_ordinal:
        dte_ok=False
    if not dte_ok:
        diagnostics_dte.add('missing_dte_reference')
        if reference.known_at_ns > A or (reference.civil_known_at_ns is not None and reference.civil_known_at_ns > A):
            diagnostics_dte.add('future_reference')
    spot_ok = definition_ok and reference.spot is not None
    if spot_ok:
        if reference.spot_known_at_ns > A:
            spot_ok=False;diagnostics_otm.add('future_reference')
        if (reference.spot_event_ns > root.event_ns or reference.spot_stream_id != root.stream_id
            or reference.spot_position >= root.position):
            spot_ok=False
        elif root.event_ns-reference.spot_event_ns > policy.max_spot_age_ns:
            spot_ok=False;diagnostics_otm.add('stale_reference')
    if not spot_ok:
        diagnostics_otm.add('missing_spot_reference')
    short = dte_ok and 0 <= reference.expiry_ordinal-reference.civil_ordinal <= policy.short_dte_max_days
    otm = spot_ok and (reference.strike > reference.spot if reference.right == 'call' else reference.strike < reference.spot)
    return dte_ok,short,spot_ok,otm,diagnostics_dte,diagnostics_otm


def _dependency_steps(dependencies):
    hashes=set();binding_ids=set()
    for dependency in dependencies:
        type_name='flow_'+''.join(('_'+c.lower()) if c.isupper() else c
                                 for c in type(dependency).__name__[4:]).lstrip('_')
        hashes.add(flow_record_digest(type_name,dependency))
        binding=getattr(dependency,'input_binding_id',None)
        if binding:binding_ids.add(binding)
        yield None
    return hashes,binding_ids


def _reduce_group_steps(entries,group,references,arithmetic,*,need_dte_totals=True,need_otm_totals=True):
    zero=arithmetic.exact(0);add=arithmetic.add
    totals={name:zero for name in ('premium','contracts','share_equivalent','buy','sell','unknown','call','put','positive','negative')}
    contracts={identity:zero for identity in sorted(group.contract_ids)}
    expiry_ids=set()
    for reference in references:
        if reference.contract_id in contracts:expiry_ids.add(str(reference.expiry_ordinal))
        yield None
    expiries={identity:zero for identity in sorted(expiry_ids)}
    signed=0;dte=0;otm=0;known_dte=zero;short=zero;known_otm=zero;otm_premium=zero
    diagnostics=set();active_ids=[];active_revisions=[];witnesses=[]
    for root,selected,reference,premium,witness,state in entries:
        totals['premium']=add(totals['premium'],premium)
        totals['contracts']=add(totals['contracts'],selected.quantity)
        totals['share_equivalent']=add(totals['share_equivalent'],arithmetic.mul(selected.quantity,arithmetic.exact(reference.multiplier)))
        side={'buy':'buy','sell':'sell','unknown':'unknown'}[witness.sign]
        totals[side]=add(totals[side],premium)
        totals[reference.right]=add(totals[reference.right],premium)
        if witness.sign!='unknown':
            signed=arithmetic.sum_integer(signed,1)
            direction='positive' if (witness.sign=='buy')==(reference.right=='call') else 'negative'
            totals[direction]=add(totals[direction],premium)
        if state[0]:
            dte=arithmetic.sum_integer(dte,1)
            if need_dte_totals:known_dte=add(known_dte,premium)
        if state[1] and need_dte_totals:short=add(short,premium)
        if state[2]:
            otm=arithmetic.sum_integer(otm,1)
            if need_otm_totals:known_otm=add(known_otm,premium)
        if state[3] and need_otm_totals:otm_premium=add(otm_premium,premium)
        contracts[root.contract_id]=add(contracts[root.contract_id],premium)
        expiry=str(reference.expiry_ordinal);expiries[expiry]=add(expiries[expiry],premium)
        diagnostics.add(witness.reason);diagnostics.update(witness.diagnostics)
        diagnostics.update(state[4]);diagnostics.update(state[5])
        active_ids.append(root.execution_id);active_revisions.append(selected.revision_id);witnesses.append(witness)
        yield None
    return (totals,contracts,expiries,signed,dte,otm,known_dte,short,known_otm,otm_premium,
            diagnostics,tuple(active_ids),tuple(active_revisions),tuple(witnesses))


def _finish_cluster_steps(current,policy_hash):
    root,selected,reference,premium,witness,*_=current[0]
    ids=[];revisions=[];venues=set();unknown=0
    for entry in current:
        ids.append(entry[0].execution_id);revisions.append(entry[1].revision_id)
        if entry[1].venue_id is None:unknown+=1
        else:venues.add(entry[1].venue_id)
        yield None
    cluster_id=_hash('option-flow-cluster1',['option-quote-cluster1',root.contract_id,root.session_id,
                     policy_hash,witness.quote_id,witness.quote_revision_id,witness.sign,ids,revisions])
    record=FlowCluster(cluster_id,'option-quote-cluster1',root.contract_id,root.session_id,
                       witness.quote_id,witness.quote_revision_id,witness.sign,tuple(ids),tuple(revisions),
                       current[0][0].event_ns,current[-1][0].event_ns,tuple(sorted(venues)),unknown)
    return record,tuple(current)


def _clusters_steps(entries,policy,policy_hash):
    clusters=[];current=[];key=None
    for entry in sorted(entries,key=lambda e:(e[0].contract_id,e[0].session_id,e[0].stream_id,e[0].position)):
        root,selected,reference,premium,witness,*_=entry
        newkey=(root.contract_id,root.session_id,root.stream_id,reference.currency,reference.action_basis_id,
                witness.quote_id,witness.quote_revision_id,witness.sign)
        if witness.sign=='unknown' or witness.quote_id is None:
            if current:clusters.append((yield from _finish_cluster_steps(current,policy_hash)))
            current=[];key=None
        else:
            if current and (newkey!=key or root.event_ns-current[-1][0].event_ns>policy.cluster_max_adjacent_gap_ns):
                clusters.append((yield from _finish_cluster_steps(current,policy_hash)))
                current=[]
            current.append(entry);key=newkey
        yield None
    if current:clusters.append((yield from _finish_cluster_steps(current,policy_hash)))
    return clusters


def _evaluate_steps(snapshot,request,input_checkpoint_sha256=None):
    """Yield bounded deterministic checkpoints; return the final result tuple."""
    flow_validate_request(request,snapshot)
    arithmetic=ExactArithmetic(request.limits.max_integer_digits)
    exact,add,sub,mul=arithmetic.exact,arithmetic.add,arithmetic.sub,arithmetic.mul
    div,total,wire,median=arithmetic.div,arithmetic.total,arithmetic.wire,arithmetic.median
    if input_checkpoint_sha256 is not None:
        if type(input_checkpoint_sha256) is not str or len(input_checkpoint_sha256) != 64:
            fail('invalid_scalar','/input_checkpoint_sha256')
    snapshot_hash=flow_record_digest('flow_snapshot',snapshot)
    request_hash=flow_record_digest('flow_request',request)
    if (len(flow_canonical_bytes(snapshot))>request.limits.max_wire_bytes
        or len(flow_canonical_bytes(request))>request.limits.max_wire_bytes):
        fail('resource_limit','/request/limits/max_wire_bytes')
    policy=request.policy;policy_hash=flow_record_digest('flow_policy',policy)
    refs={v.reference_id:v for v in snapshot.references}
    groups={v.group_id:v for v in snapshot.groups}
    cursors={v.stream_id:v.max_position for v in request.cut_cursors}
    executions=_chains(snapshot.executions,'execution','/snapshot/executions')
    quotes=_chains(snapshot.quotes,'quote','/snapshot/quotes')
    active=_root_view(executions,request.knowledge_cutoff_ns,cursors)
    results=[]
    yield None
    for group_id in request.group_ids:
        group=groups[group_id];entries=[];exclusions=[];dependencies=[group];clocks=[];certificates=[]
        populations=[p for p in snapshot.populations if p.group_id==group_id
                     and p.window_start_ns==request.window_start_ns and p.window_end_ns==request.window_end_ns]
        if len(populations)>1:fail('identity_conflict','/snapshot/populations')
        population=populations[0] if populations else None
        if population:dependencies.append(population)
        complete=bool(population and population.complete and population.known_at_ns<=request.knowledge_cutoff_ns)
        if population and population.known_at_ns<=request.knowledge_cutoff_ns:clocks.append(population.known_at_ns)
        corrected=False
        group_streams=set()
        for identity,chain in sorted(executions.items()):
            root=chain[0]
            if root.contract_id not in group.contract_ids:continue
            group_streams.add(root.stream_id);dependencies.extend(chain)
            selected=active[identity]
            if selected is not None and request.window_start_ns<=root.event_ns<request.window_end_ns:
                # A known cancellation/exclusion establishes the selected economic
                # population just as a retained eligible revision contributes value.
                clocks.append(selected.known_at_ns)
            dependencies.append(refs[root.reference_id])
            if selected:dependencies.append(refs[selected.reference_id])
            visible=[v for v in chain if v.known_at_ns<=request.knowledge_cutoff_ns and v.position<=cursors[v.stream_id]]
            corrected |= any(v.kind!='new' for v in visible)
            if selected is None:reason='future_known'
            elif selected.kind=='cancel':reason='cancelled'
            elif not request.window_start_ns<=root.event_ns<request.window_end_ns:reason='outside_window'
            elif selected.condition!='regular':reason='excluded'
            else:reason=None
            if reason:
                exclusions.append(FlowExcluded(identity,selected.revision_id if selected else root.revision_id,reason))
            else:
                reference=refs[root.reference_id]
                witness,used,available=yield from _sign_steps(snapshot,root,selected,policy,policy_hash,refs,executions,quotes,cursors,arithmetic)
                dependencies.extend(used);clocks.append(available)
                if witness.context_certificate_id:certificates.append(witness.context_certificate_id)
                premium=mul(mul(exact(selected.price),selected.quantity),exact(reference.multiplier))
                state=_reference_state(root,reference,policy)
                entries.append((root,selected,reference,premium,witness,state))
                if state[0]:clocks.extend((reference.known_at_ns,reference.civil_known_at_ns))
                if state[2]:clocks.extend((reference.known_at_ns,reference.spot_known_at_ns))
            yield None
        observed_ids={entry[0].execution_id for entry in entries}
        if population and population.known_at_ns<=request.knowledge_cutoff_ns:
            if not observed_ids<=set(population.expected_execution_ids):
                fail('identity_mismatch','/snapshot/populations')
            for identity in population.expected_execution_ids:
                declared_root=executions[identity][0]
                if (declared_root.contract_id in group.contract_ids
                    and request.window_start_ns<=declared_root.event_ns<request.window_end_ns
                    and active.get(identity) is None):complete=False
                yield None
            if complete:
                expected={identity for identity in population.expected_execution_ids
                          if active[identity] is not None
                          and active[identity].kind!='cancel' and active[identity].condition=='regular'
                          and request.window_start_ns<=executions[identity][0].event_ns<request.window_end_ns}
                if expected != observed_ids:fail('identity_mismatch','/snapshot/populations')
        for chain in quotes.values():
            if chain[0].stream_id in group_streams:
                dependencies.extend(chain)
                corrected |= any(v.kind!='new' and v.known_at_ns<=request.knowledge_cutoff_ns
                                 and v.position<=cursors[v.stream_id] for v in chain)
            yield None
        (totals,contract_weights,expiry_weights,signed,dte_count,otm_count,
         known_dte,short_premium,known_otm,otm_premium,group_diagnostics,
         active_ids,active_revisions,group_witnesses)=yield from _reduce_group_steps(
             entries,group,snapshot.references,arithmetic,
             need_dte_totals=any(output.startswith(('flow.dte_','flow.short_dte_')) for output in request.output_ids),
             need_otm_totals=any(output.startswith('flow.otm_') for output in request.output_ids))
        count=len(entries)
        T=totals['premium'];C=totals['contracts'];U=totals['share_equivalent']
        A=totals['buy'];B=totals['sell'];Z=totals['unknown']
        call=totals['call'];put=totals['put'];plus=totals['positive'];minus=totals['negative']
        coverage=FlowCoverage(population.population_id if population else None,complete,count if complete else None,
                              count,count,signed,count-signed,dte_count,otm_count)
        weights=[]
        for kind,partition in (('contract',contract_weights),('expiry',expiry_weights)):
            for key,value in sorted(partition.items()):
                weights.append(FlowPartitionWeight(kind,key,wire(value)))
                yield None
        base={'count':(exact(count),'executions'),'contracts':(C,'contracts'),'share_equivalent':(U,'payoff_units'),
              'premium':(T,'group_currency'),'buy_premium':(A,'group_currency'),'sell_premium':(B,'group_currency'),
              'unknown_premium':(Z,'group_currency'),'signed_premium':(sub(A,B),'group_currency'),
              'call_premium':(call,'group_currency'),'put_premium':(put,'group_currency')}
        flags=set()
        if signed<count:flags.add('partial_sign_coverage')
        if dte_count<count:flags.add('partial_dte_coverage')
        if otm_count<count:flags.add('partial_otm_coverage')
        if policy.signing_profile!='option-observed-side1':flags.add('proxy_direction')
        if corrected:flags.add('corrected_history')
        if complete and count==0:flags.add('complete_empty')
        need_clusters=any(output.startswith('execution.') for output in request.output_ids)
        clusters=(yield from _clusters_steps(entries,policy,policy_hash)) if need_clusters and complete and policy.signing_profile=='option-quote-midpoint1' else []
        cluster_metrics={};clustered_premium=exact(0)
        for cluster,members in clusters:
            premium=exact(0);contracts=exact(0)
            for entry in members:
                premium=add(premium,entry[3]);contracts=add(contracts,entry[1].quantity)
                yield None
            cluster_metrics[cluster.cluster_id]=(premium,contracts)
            clustered_premium=add(clustered_premium,premium)
            yield None
        for output in request.output_ids:
            cluster_rows=clusters if output in PER_CLUSTER and complete and policy.signing_profile=='option-quote-midpoint1' else [(None,())]
            for cluster,members in cluster_rows:
                operands=dict(base);diagnostics=set(flags);row_flags=set(flags);deps=list(dependencies)
                diagnostics.update(group_diagnostics)
                status='available';reason='ok';value=None;numerator=None;denominator=None;ties=();selected_baselines=[];slots=()
                is_ratio=False;baseline_clocks=[]
                if output.startswith('cross.'):
                    status,reason='unsupported','equity_integration_unqualified'
                elif output.startswith('execution.') and policy.signing_profile!='option-quote-midpoint1':
                    status,reason='unsupported','unsupported_profile'
                elif not complete and not output.startswith('activity.'):
                    status,reason='unavailable','incomplete_population'
                elif output.startswith('activity.'):
                    metric='contracts' if output in ('activity.contracts_median','activity.relative_volume') else 'trade_count' if output in ('activity.trade_count_median','activity.relative_trade_count') else 'premium'
                    target=next((t for t in request.baseline_targets if t.group_id==group_id),None)
                    slots=target.slot_ids if target else ()
                    selected_baselines=[next((b for b in snapshot.baselines if b.group_id==group_id and b.slot_id==slot),None) for slot in slots]
                    deps.extend(b for b in selected_baselines if b is not None)
                    if any(b is not None for b in selected_baselines):row_flags.add('supplied_baseline');diagnostics.add('supplied_baseline')
                    causes=[]
                    if not slots:causes.append('missing_baseline')
                    if any(b is None for b in selected_baselines):causes.append('incomplete_baseline')
                    if any(b is not None and (not b.complete or getattr(b,metric) is None) for b in selected_baselines):causes.append('incomplete_baseline')
                    if any(b is not None and b.known_at_ns>request.knowledge_cutoff_ns for b in selected_baselines):causes.append('future_reference')
                    if slots and len(slots)<policy.minimum_matched_prior_windows:causes.append('insufficient_history')
                    diagnostics.update(causes)
                    if causes:status,reason='unavailable',causes[0]
                    current=C if metric=='contracts' else exact(count) if metric=='trade_count' else T
                    metric_unit='contracts' if metric=='contracts' else 'executions' if metric=='trade_count' else 'group_currency'
                    if output in ('activity.relative_volume','activity.relative_trade_count','activity.premium_robust_z'):
                        operands['current']=(current,metric_unit)
                    admitted_baseline_count=sum(
                        b is not None and b.complete and b.known_at_ns<=request.knowledge_cutoff_ns
                        and getattr(b,metric) is not None for b in selected_baselines)
                    baseline_clocks=[b.known_at_ns for b in selected_baselines
                                     if b is not None and b.known_at_ns<=request.knowledge_cutoff_ns]
                    operands['baseline_count']=(exact(admitted_baseline_count),'executions')
                    if status=='available':
                        history=[exact(getattr(b,metric)) for b in selected_baselines]
                        middle=median(history)
                        operands['median']=(middle,metric_unit)
                        if output in ('activity.premium_mad','activity.premium_robust_z'):
                            mad=median([abs(sub(v,middle)) for v in history])
                            operands['mad']=(mad,'group_currency')
                        if output.endswith('_median'):value=middle
                        elif output=='activity.premium_mad':value=mad
                        elif output=='activity.premium_robust_z':
                            scale=div(7413,5000);operands['mad_scale']=(scale,'ratio')
                            numerator=sub(current,middle);denominator=mul(scale,mad);is_ratio=True
                            if denominator==0:status,reason='undefined','zero_mad'
                        else:numerator=current;denominator=middle;is_ratio=True
                elif output in PER_CLUSTER:
                    premium,contracts=cluster_metrics[cluster.cluster_id]
                    operands.update({'cluster_premium':(premium,'group_currency'),'cluster_contracts':(contracts,'contracts'),
                                     'cluster_count':(exact(len(members)),'executions'),
                                     'cluster_span':(exact(cluster.last_event_ns-cluster.first_event_ns),'nanoseconds'),
                                     'known_venue_count':(exact(len(cluster.venue_ids)),'venues'),
                                     'unknown_venue_count':(exact(cluster.unknown_venue_count),'venues')})
                    value={'execution.cluster_premium':premium,'execution.cluster_contracts':contracts,
                           'execution.cluster_trade_count':exact(len(members)),
                           'execution.cluster_span_ns':exact(cluster.last_event_ns-cluster.first_event_ns),
                           'execution.cluster_venue_count':exact(len(cluster.venue_ids))}[output]
                    if output=='execution.cluster_venue_count' and cluster.unknown_venue_count:
                        status,reason='unavailable','missing_venue_reference'
                elif output=='execution.cluster_coverage':
                    numerator=clustered_premium;denominator=T;is_ratio=True
                elif output.startswith('flow.dte_') or output.startswith('flow.short_dte_') or output.startswith('flow.otm_'):
                    dte=not output.startswith('flow.otm_');known_index=0 if dte else 2;qualified_index=1 if dte else 3
                    known=known_dte if dte else known_otm;qualified=short_premium if dte else otm_premium
                    operands['known_reference_premium']=(known,'group_currency');operands['qualified_premium']=(qualified,'group_currency')
                    full=output in ('flow.short_dte_premium_share','flow.otm_premium_share')
                    if full and (dte_count if dte else otm_count)<count:
                        status,reason='unavailable','missing_dte_reference' if dte else 'missing_spot_reference'
                    numerator=known if output.endswith('reference_coverage') else qualified
                    denominator=known if output.endswith('known_reference_share') else T;is_ratio=True
                else:
                    totals={'flow.trade_count':exact(count),'flow.contracts':C,'flow.share_equivalent':U,'flow.premium':T,
                            'flow.buy_proxy_premium':A,'flow.sell_proxy_premium':B,'flow.unknown_premium':Z,
                            'flow.signed_execution_premium':sub(A,B),'flow.right_positive_premium':plus,
                            'flow.right_negative_premium':minus,'flow.net_directional_premium':sub(plus,minus),
                            'flow.call_premium':call,'flow.put_premium':put}
                    ratios={'flow.known_sign_imbalance':(sub(A,B),add(A,B)),
                            'flow.total_premium_imbalance':(sub(A,B),T),'flow.unknown_premium_share':(Z,T),
                            'flow.sign_event_coverage':(exact(signed),exact(count)),
                            'flow.sign_premium_coverage':(add(A,B),T),'flow.put_call_premium_ratio':(put,call)}
                    if output in totals:value=totals[output]
                    elif output in ratios:numerator,denominator=ratios[output];is_ratio=True
                    else:
                        partition=contract_weights if output.startswith('flow.contract_') else expiry_weights
                        denominator=mul(T,T) if output.endswith('_hhi') else T
                        numerator=exact(0);top_ids=[]
                        for key,weight in sorted(partition.items()):
                            if output.endswith('_hhi'):numerator=add(numerator,mul(weight,weight))
                            elif weight>numerator:numerator=weight;top_ids=[key]
                            elif weight==numerator:top_ids.append(key)
                            yield None
                        if output.endswith('_top_share') and T>0:ties=tuple(top_ids)
                        is_ratio=True
                if not complete and output.startswith('activity.'):
                    # Historical summaries are independently supplied operands.
                    # Preserve their admitted evidence while current full-population
                    # availability retains higher-priority missingness.
                    if reason!='ok':diagnostics.add(reason)
                    status,reason='unavailable','incomplete_population'
                if status=='unavailable' and reason=='incomplete_population':
                    # Full-population value remains unavailable; observed partial
                    # base operands still exist and must not disappear from proof.
                    partial_ratio_ids=('flow.known_sign_imbalance','flow.total_premium_imbalance',
                                       'flow.unknown_premium_share','flow.sign_event_coverage',
                                       'flow.sign_premium_coverage','flow.put_call_premium_ratio')
                    if output in partial_ratio_ids:
                        if output=='flow.known_sign_imbalance':numerator,denominator=sub(A,B),add(A,B)
                        elif output=='flow.total_premium_imbalance':numerator,denominator=sub(A,B),T
                        elif output=='flow.unknown_premium_share':numerator,denominator=Z,T
                        elif output=='flow.sign_event_coverage':numerator,denominator=exact(signed),exact(count)
                        elif output=='flow.sign_premium_coverage':numerator,denominator=add(A,B),T
                        else:numerator,denominator=put,call
                        is_ratio=True
                    elif output in ('flow.contract_hhi','flow.expiry_hhi','flow.contract_top_share','flow.expiry_top_share'):
                        partition=contract_weights if output.startswith('flow.contract_') else expiry_weights
                        denominator=mul(T,T) if output.endswith('_hhi') else T
                        numerator=exact(0);top_ids=[]
                        for key,weight in sorted(partition.items()):
                            if output.endswith('_hhi'):numerator=add(numerator,mul(weight,weight))
                            elif weight>numerator:numerator=weight;top_ids=[key]
                            elif weight==numerator:top_ids.append(key)
                            yield None
                        if output.endswith('_top_share') and T>0:ties=tuple(top_ids)
                        is_ratio=True
                    elif output.startswith('flow.dte_') or output.startswith('flow.short_dte_') or output.startswith('flow.otm_'):
                        dte=not output.startswith('flow.otm_')
                        known=known_dte if dte else known_otm
                        qualified=short_premium if dte else otm_premium
                        operands['known_reference_premium']=(known,'group_currency')
                        operands['qualified_premium']=(qualified,'group_currency')
                        numerator=known if output.endswith('reference_coverage') else qualified
                        denominator=known if output.endswith('known_reference_share') else T
                        is_ratio=True
                if is_ratio and numerator is not None and denominator is not None:
                    operand_unit=('contracts' if output=='activity.relative_volume'
                                  else 'executions' if output in ('activity.relative_trade_count','flow.sign_event_coverage')
                                  else 'group_currency_squared' if output.endswith('_hhi')
                                  else 'group_currency')
                    operands['numerator']=(numerator,operand_unit)
                    operands['denominator']=(denominator,operand_unit)
                    if status=='available':
                        if denominator==0:status,reason='undefined','zero_denominator'
                        else:value=div(numerator,denominator)
                if status!='available':value=None
                if reason!='ok':diagnostics.add(reason)
                dep_hashes,binding_ids=yield from _dependency_steps(deps)
                evidence=FlowEvidence(active_ids,active_revisions,
                                      tuple(exclusions),tuple(FlowOperand(k,wire(v),unit) for k,(v,unit) in sorted(operands.items())),
                                      tuple(weights),ties,cluster,slots,
                                      tuple(flow_record_digest('flow_baseline',b) for b in selected_baselines if b is not None),
                                      ('EQ153','EQ158') if output.startswith('cross.') else (),tuple(sorted(diagnostics)))
                row=FlowResult('option-flow-result1',group_id,output,cluster.cluster_id if cluster else None,
                               request.window_start_ns,request.window_end_ns,request.knowledge_cutoff_ns,
                               max(clocks+baseline_clocks,default=0),'option-origin-context1',group.currency,group.action_basis_id,
                               'computed',wire(value) if value is not None else None,OUTPUT_UNITS[output],status,reason,
                               tuple(sorted(row_flags)),coverage,group_witnesses,evidence,
                               wire(numerator) if numerator is not None else None,wire(denominator) if denominator is not None else None,
                               tuple(sorted(b.baseline_id for b in selected_baselines if b is not None)),
                               tuple(sorted(binding_ids)),tuple(sorted(dep_hashes)),policy_hash,request_hash,snapshot_hash,
                               input_checkpoint_sha256,'option-flow-formulas1','0.1.0a1','0.1.0a1')
                results.append(row)
                yield None
    final=tuple(sorted(results,key=lambda row:(row.group_id,row.output_id,row.cluster_id or '')))
    flow_validate_results(final,request)
    if len(flow_canonical_bytes(final))>request.limits.max_wire_bytes:
        fail('resource_limit','/results')
    return final


def evaluate_flow(snapshot,request,*,input_checkpoint_sha256=None):
    steps=_evaluate_steps(snapshot,request,input_checkpoint_sha256)
    while True:
        try:next(steps)
        except StopIteration as finished:return finished.value


def make_flow_checkpoint(snapshot,request):
    flow_validate_request(request,snapshot)
    if ({c.stream_id:c.max_position for c in request.cut_cursors} !=
        {c.stream_id:c.max_position for c in snapshot.cursors}
        or any(clock>request.knowledge_cutoff_ns for clock in carried_knowledge(snapshot))):
        fail('checkpoint_cut_mismatch','/checkpoint')
    checkpoint=FlowCheckpoint('option-flow-checkpoint1',snapshot,request,
                              flow_record_digest('flow_snapshot',snapshot),flow_record_digest('flow_request',request),
                              flow_record_digest('flow_policy',request.policy),'option-flow-formulas1')
    flow_canonical_bytes(checkpoint)
    return checkpoint


def _monotonic(previous,current):
    if (previous.group_ids!=current.group_ids or previous.output_ids!=current.output_ids
        or previous.window_start_ns!=current.window_start_ns or previous.policy!=current.policy
        or current.window_end_ns<previous.window_end_ns or current.knowledge_cutoff_ns<previous.knowledge_cutoff_ns):
        fail('identity_mismatch','/request')
    old={c.stream_id:c.max_position for c in previous.cut_cursors}
    new={c.stream_id:c.max_position for c in current.cut_cursors}
    if not set(old)<=set(new) or any(new[s]<position for s,position in old.items()):
        fail('checkpoint_cut_mismatch','/request/cut_cursors')


def merge_flow_history(checkpoint,suffix,request):
    flow_validate_request(request)
    validate_checkpoint(checkpoint)
    if type(suffix) is not FlowSnapshot:fail('type_mismatch','/suffix')
    _validate(suffix,request.limits,'/suffix',[0])
    _monotonic(checkpoint.prior_request,request)
    history=checkpoint.history;old_cursors={c.stream_id:c.max_position for c in history.cursors}
    for family in ('executions','quotes'):
        for revision in getattr(suffix,family):
            if revision.stream_id in old_cursors and revision.position<=old_cursors[revision.stream_id]:
                fail('checkpoint_cut_mismatch','/suffix/'+family)
    identity_fields={'bindings':('binding_id',),'references':('reference_id',),
                     'executions':('execution_id','revision_id'),'quotes':('quote_id','revision_id'),
                     'groups':('group_id',),'populations':('population_id',),
                     'context_certificates':('certificate_id',),'baselines':('baseline_id',)}
    merged={}
    for family,names in identity_fields.items():
        records={tuple(getattr(v,n) for n in names):v for v in getattr(history,family)}
        seen=set()
        for value in getattr(suffix,family):
            key=tuple(getattr(value,n) for n in names)
            if key in seen:fail('identity_conflict','/suffix/'+family)
            seen.add(key)
            if key in records and records[key]!=value:fail('identity_conflict','/suffix/'+family)
            records[key]=value
        merged[family]=tuple(records[k] for k in sorted(records))
    cursors={c.stream_id:c for c in history.cursors}
    if len({c.stream_id for c in suffix.cursors})!=len(suffix.cursors):fail('identity_conflict','/suffix/cursors')
    for cursor in suffix.cursors:
        if cursor.stream_id in cursors and cursor.max_position<cursors[cursor.stream_id].max_position:
            fail('checkpoint_cut_mismatch','/suffix/cursors')
        cursors[cursor.stream_id]=cursor
    combined=FlowSnapshot('option-flow-canonical1',**merged,cursors=tuple(cursors[k] for k in sorted(cursors)))
    flow_validate_request(request,combined)
    flow_canonical_bytes(combined)
    return combined


def restore_flow(checkpoint,suffix,request):
    merged=merge_flow_history(checkpoint,suffix,request)
    results=evaluate_flow(merged,request,input_checkpoint_sha256=flow_record_digest('flow_checkpoint',checkpoint))
    try:output=make_flow_checkpoint(merged,request)
    except FlowValidationError as error:
        if error.code!='checkpoint_cut_mismatch':raise
        output=None
    return results,output


def replay_flow(snapshot,requests):
    if type(requests) is not tuple:fail('type_mismatch','/requests')
    if not requests or len(requests)>FLOW_LIMITS.max_replay_cuts:fail('resource_limit','/requests')
    for request in requests:
        flow_validate_request(request)
        if len(requests)>request.limits.max_replay_cuts:fail('resource_limit','/requests')
    results=[]
    for index,request in enumerate(requests):
        if index:_monotonic(requests[index-1],request)
        results.append(evaluate_flow(snapshot,request))
    return tuple(results)
