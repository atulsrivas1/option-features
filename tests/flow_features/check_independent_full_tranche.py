"""Consume externally pinned independent expectations; never author goldens.

The artifact explicitly distinguishes complete result-wire goldens from limited
economic projections. Counts are actual operations, not claimed full coverage.
"""
from hashlib import sha256
from pathlib import Path
from fractions import Fraction
import json
import platform
import subprocess
import sys
import time

from option_flow_contracts import (
    FlowSnapshot, FlowValidationError, flow_from_payload, flow_record_digest,
    flow_canonical_bytes, encode_flow_results, encode_flow_snapshot, encode_flow_request,
    decode_flow_snapshot, decode_flow_request,
)
from option_flow_features import evaluate_flow,replay_flow,restore_flow,make_flow_checkpoint
from option_flow_features.engine import merge_flow_history
from option_flow_features.arithmetic import ExactArithmetic


def J(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


def rational(value):
    return None if value is None else f'{value.numerator}/{value.denominator}'


def equal(actual,expected,label):
    if actual!=expected:
        raise AssertionError(f'{label}: actual={actual!r} expected={expected!r}')


def first_difference(actual,expected,path=''):
    if type(actual) is not type(expected):return path,actual,expected
    if isinstance(actual,dict):
        if set(actual)!=set(expected):return path+'/keys',sorted(actual),sorted(expected)
        for key in sorted(actual):
            found=first_difference(actual[key],expected[key],path+'/'+key)
            if found:return found
    elif isinstance(actual,list):
        if len(actual)!=len(expected):return path+'/length',len(actual),len(expected)
        for index,(a,b) in enumerate(zip(actual,expected)):
            found=first_difference(a,b,f'{path}/{index}')
            if found:return found
    elif actual!=expected:return path,actual,expected
    return None


def suffix_records(payload):
    """Construct local typed records before merged referential validation.

    A valid suffix need not be a standalone referentially complete snapshot.
    This uses each registered record constructor boundary, then real restore.
    """
    names={'bindings':'flow_binding','references':'flow_reference','executions':'flow_execution',
           'quotes':'flow_quote','groups':'flow_group','populations':'flow_population',
           'context_certificates':'flow_context_certificate','baselines':'flow_baseline','cursors':'flow_cursor'}
    return FlowSnapshot(payload['schema_version'],**{
        name:tuple(flow_from_payload(kind,value) for value in payload[name]) for name,kind in names.items()})


def projection(rows,expected,output_checkpoint=None):
    supported={'available','undefined','unavailable','unsupported','coverage','evidence_operands','error',
               'signs','sign_reasons','sign_diagnostics_include','selected_quotes','active_execution_ids',
               'exclusions','tied_top_ids','available_at_at_least','cluster_values','cluster_members',
               'cluster_statuses','output_checkpoint','quality_flags_include','required_producer_ids',
               'sign_context_sha256'}
    assert set(expected)<=supported,('unhandled independent projection keys',set(expected)-supported)
    selected={row.output_id:row for row in rows if row.cluster_id is None}
    signs={}
    for row in rows:
        for witness in row.sign_witnesses:
            if witness.execution_id in signs:equal(witness,signs[witness.execution_id],'uniform sign witness')
            signs[witness.execution_id]=witness
    for output,value in expected.get('available',{}).items():
        row=selected[output]
        equal((row.status,row.reason,rational(row.value)),('available','ok',value),output)
    for status in ('undefined','unavailable','unsupported'):
        for output,reason in expected.get(status,{}).items():
            row=selected[output]
            equal((row.status,row.reason,row.value),(status,reason,None),output)
    for field,mapping in (('sign','signs'),('reason','sign_reasons'),('context_sha256','sign_context_sha256')):
        for identity,value in expected.get(mapping,{}).items():equal(getattr(signs[identity],field),value,mapping+'/'+identity)
    if 'signs' in expected:equal({identity:w.sign for identity,w in signs.items()},expected['signs'],'complete sign membership')
    for identity,diagnostics in expected.get('sign_diagnostics_include',{}).items():
        assert set(diagnostics)<=set(signs[identity].diagnostics),(identity,diagnostics,signs[identity])
    for identity,pair in expected.get('selected_quotes',{}).items():
        equal([signs[identity].quote_id,signs[identity].quote_revision_id],pair,'quote/'+identity)
    for row in rows:
        for field,value in expected.get('coverage',{}).items():equal(getattr(row.coverage,field),value,'coverage/'+field)
        operands={operand.name:rational(operand.value) for operand in row.evidence.operands}
        for field,value in expected.get('evidence_operands',{}).items():equal(operands[field],value,'operand/'+field)
        if 'active_execution_ids' in expected:equal(list(row.evidence.active_execution_ids),expected['active_execution_ids'],'active IDs')
        if 'exclusions' in expected:equal({e.execution_id:e.reason for e in row.evidence.exclusions},expected['exclusions'],'exclusions')
        if 'available_at_at_least' in expected:assert row.available_at_ns>=expected['available_at_at_least'],row
        if 'quality_flags_include' in expected:assert set(expected['quality_flags_include'])<=set(row.quality_flags),row
        if 'required_producer_ids' in expected:equal(list(row.evidence.required_producer_ids),expected['required_producer_ids'],'producer IDs')
    for output,ids in expected.get('tied_top_ids',{}).items():equal(list(selected[output].evidence.tied_top_ids),ids,'top IDs')
    clusters={row.cluster_id:row.evidence.cluster for row in rows if row.cluster_id is not None}
    ordered=sorted(clusters,key=lambda key:(clusters[key].first_event_ns,clusters[key].execution_ids))
    if 'cluster_members' in expected:equal([list(clusters[key].execution_ids) for key in ordered],expected['cluster_members'],'cluster members')
    for output,values in expected.get('cluster_values',{}).items():
        by_cluster={row.cluster_id:row for row in rows if row.output_id==output}
        equal([rational(by_cluster[key].value) for key in ordered],values,'cluster values/'+output)
    for output,statuses in expected.get('cluster_statuses',{}).items():
        by_cluster={row.cluster_id:row for row in rows if row.output_id==output}
        equal([[by_cluster[key].status,by_cluster[key].reason] for key in ordered],statuses,'cluster statuses/'+output)
    if 'output_checkpoint' in expected:equal(output_checkpoint,expected['output_checkpoint'],'output checkpoint')


def metadata(rows,expected,case):
    allowed={'contract_hhi_numerator','contract_hhi_denominator','hhi_operand_unit','observed_context_records',
             'context_record_sha256s','excluded_q0_from_context','mathematical_contracts','published_result_forbidden'}
    assert set(expected)<=allowed,('unhandled metadata predicates',set(expected)-allowed)
    if 'contract_hhi_numerator' in expected:
        row=next(row for row in rows if row.output_id=='flow.contract_hhi')
        equal(rational(row.numerator),expected['contract_hhi_numerator'],'HHI numerator')
        equal(rational(row.denominator),expected['contract_hhi_denominator'],'HHI denominator')
        units={o.name:o.unit for o in row.evidence.operands}
        equal((units['numerator'],units['denominator']),(expected['hhi_operand_unit'],)*2,'HHI operand units')
        assert case['full_result_goldens'],'observed-context narrative requires full independent row bytes'
    if 'context_record_sha256s' in expected:
        target=next(iter(case['expected_projection']['sign_context_sha256']))
        witness=next(w for w in rows[0].sign_witnesses if w.execution_id==target)
        certificate=next(c for c in case['snapshot']['context_certificates'] if c['certificate_id']==witness.context_certificate_id)
        certificate_hash=sha256(b'option-flow-record1\nflow_context_certificate\n'+J(certificate)).hexdigest()
        expected_context=sha256(b'option-flow-context1\n'+J([witness.signing_boundary_ns,
                            rows[0].policy_sha256,expected['context_record_sha256s'],certificate_hash])).hexdigest()
        equal(witness.context_sha256,expected_context,'minimal context member hashes')
        if 'excluded_q0_from_context' in expected:equal(expected['excluded_q0_from_context'],True,'excluded q0')


def operation(case):
    expected=case['expected_projection']
    request=decode_flow_request(case['request_wire'].encode())
    equal(flow_record_digest('flow_request',request),case['request_record_sha256'],'request record digest')
    equal(encode_flow_request(request).decode(),case['request_wire'],'request wire')
    if case['operation']=='restore':
        checkpoint=flow_from_payload('flow_checkpoint',case['checkpoint'])
        suffix=suffix_records(case['snapshot'])
        rows,output_checkpoint=restore_flow(checkpoint,suffix,request)
        merged=merge_flow_history(checkpoint,suffix,request)
        checkpoint_hash=flow_record_digest('flow_checkpoint',checkpoint)
        if 'input_checkpoint_sha256' in case:
            equal(checkpoint_hash,case['input_checkpoint_sha256'],'independent input checkpoint identity')
        direct=evaluate_flow(merged,request,input_checkpoint_sha256=checkpoint_hash)
        equal(encode_flow_results(rows),encode_flow_results(direct),'same-invocation restore/direct bytes')
    else:
        snapshot=decode_flow_snapshot(case['snapshot_wire'].encode())
        equal(flow_record_digest('flow_snapshot',snapshot),case['snapshot_record_sha256'],'snapshot record digest')
        equal(encode_flow_snapshot(snapshot).decode(),case['snapshot_wire'],'snapshot wire')
        if case['operation']=='replay':
            requests=tuple(flow_from_payload('flow_request',value) for value in case['requests'])
            cuts=replay_flow(snapshot,requests)
            assert set(expected)=={'cut_signs'},expected
            equal(len(cuts),len(expected['cut_signs']),'replay cut count')
            for rows,signs in zip(cuts,expected['cut_signs']):projection(rows,{'signs':signs})
            return 0
        equal(case['operation'],'evaluate','operation')
        rows=evaluate_flow(snapshot,request)
        try:output_checkpoint=make_flow_checkpoint(snapshot,request)
        except FlowValidationError as error:
            if error.code!='checkpoint_cut_mismatch':raise
            output_checkpoint=None
    assert 'error' not in expected,('expected exception absent',expected)
    projection(rows,expected,output_checkpoint)
    if 'expected_metadata_predicates' in case:metadata(rows,case['expected_metadata_predicates'],case)
    if case['full_result_goldens']:
        actual_payload=json.loads(flow_canonical_bytes(rows))
        difference=first_difference(actual_payload,case['expected_results'])
        assert difference is None,('full canonical payload difference',difference)
        equal(flow_record_digest('flow_results',rows),case['expected_results_record_sha256'],'full results record digest')
        equal(encode_flow_results(rows).decode(),case['expected_results_wire'],'full results envelope bytes')
        return len(rows)
    return 0


def check(path,expected_hash,lease='R26-LIBRARY-DEVELOPMENT-03'):
    raw=Path(path).read_bytes()
    equal(sha256(raw).hexdigest(),expected_hash,'externally pinned fixture SHA256')
    artifact=json.loads(raw);passed=[];failures=[];full_rows=0;full_cases=0;start=time.perf_counter()
    files=sorted(p for root in ('packages/flow-contracts','packages/flow-features','tests/flow_contracts','tests/flow_features')
                 for p in Path(root).rglob('*') if p.is_file())
    before={p.as_posix():sha256(p.read_bytes()).hexdigest() for p in files}
    for case in artifact['cases']:
        try:
            try:count=operation(case)
            except FlowValidationError as error:
                expected=case['expected_projection'].get('error')
                assert expected is not None,('unexpected boundary error',error.code,error.path)
                equal(error.code,expected['code'],'exception code')
                if 'path' in expected:equal(error.path,expected['path'],'exception path')
                count=0
            if case['full_result_goldens']:full_cases+=1;full_rows+=count
            passed.append(case['id'])
        except Exception as error:
            failure={'id':case['id'],'exception':type(error).__name__,'detail':str(error)}
            failures.append(failure);print(json.dumps({'failure':failure}),flush=True)
    primitives=[]
    for case in artifact['arithmetic_primitive_witnesses']:
        try:
            arithmetic=ExactArithmetic(case['max_integer_digits'])
            operands=[Fraction(int(q['numerator']),int(q['denominator'])) for q in case['operands']]
            try:
                result=(arithmetic.mul if case['operation']=='multiply' else arithmetic.add)(*operands)
            except FlowValidationError as error:equal(error.code,case['expected_error'],'primitive error')
            else:
                assert 'expected_error' not in case,case
                equal({'numerator':str(result.numerator),'denominator':str(result.denominator)},case['expected'],'primitive result')
            primitives.append(case['id'])
        except Exception as error:
            failure={'id':case['id'],'exception':type(error).__name__,'detail':str(error)}
            failures.append(failure);print(json.dumps({'failure':failure}),flush=True)
    after={p.as_posix():sha256(p.read_bytes()).hexdigest() for p in files}
    receipt={'lease':lease,'fixture_sha256':expected_hash,
             'actual_command':'PYTHONPATH=packages/flow-contracts/src;packages/flow-features/src PYTHONDONTWRITEBYTECODE=1 python -B tests/flow_features/check_independent_full_tranche.py <externally pinned artifact> '+expected_hash+' '+lease,
             'source_commit':
             subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip(),
             'python':platform.python_version(),'platform':platform.platform(),'case_count':len(artifact['cases']),
             'passed_count':len(passed),'passed':passed,'primitives_passed':primitives,'failures':failures,
             'full_golden_cases_passed':full_cases,'full_golden_rows_passed':full_rows,
             'elapsed_seconds':time.perf_counter()-start,'source_before':before,'source_after':after,
             'source_unchanged':before==after,'limitation':'Full oracle only for declared full-golden cases; source development, not installed qualification'}
    with Path('docs/r26/LIBRARY_IMPLEMENTATION.md').open('a',encoding='utf-8') as handle:
        handle.write('\n## Independent tranche2 actual development attempt\n\n```json\n'+json.dumps(receipt,indent=2)+'\n```\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('source_before','source_after','passed')},indent=2))
    return not failures and before==after


if __name__=='__main__':
    if len(sys.argv) not in (3,4):raise SystemExit('external artifact path, externally reviewed SHA256 and optional actual lease ID required')
    raise SystemExit(0 if check(*sys.argv[1:]) else 1)
