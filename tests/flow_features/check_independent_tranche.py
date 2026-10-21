"""Consume an externally reviewed projection artifact, never generate goldens.

Usage: python -B check_independent_tranche.py ARTIFACT EXPECTED_SHA256
This checks only fields actually fixed independently; it is not a full-result
golden or installed integration qualification.
"""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import json
import sys

from option_flow_contracts import flow_from_payload, FlowValidationError
from option_flow_features import evaluate_flow


def rational(value):
    return None if value is None else f'{value.numerator}/{value.denominator}'


def check(path,expected_hash):
    raw=Path(path).read_bytes()
    assert sha256(raw).hexdigest()==expected_hash,'external fixture digest mismatch'
    artifact=json.loads(raw)
    passed=[]
    for case in artifact['cases']:
        expected=case['expected_projection']
        snapshot=flow_from_payload('flow_snapshot',case['snapshot'])
        request=flow_from_payload('flow_request',case['request'])
        try:
            rows=evaluate_flow(snapshot,request)
        except FlowValidationError as error:
            assert expected.get('error')=={'code':error.code,'path':error.path},(case['id'],error)
        else:
            assert 'error' not in expected,case['id']
            selected={row.output_id:row for row in rows}
            for output,value in expected.get('available',{}).items():
                row=selected[output]
                assert (row.status,row.reason,rational(row.value))==('available','ok',value),(case['id'],output,row)
            for status in ('undefined','unavailable','unsupported'):
                for output,reason in expected.get(status,{}).items():
                    row=selected[output]
                    assert (row.status,row.reason,row.value)==(status,reason,None),(case['id'],output,row)
            for row in rows:
                for field,value in expected.get('coverage',{}).items():
                    assert getattr(row.coverage,field)==value,(case['id'],field,row.coverage)
                operands={operand.name:rational(operand.value) for operand in row.evidence.operands}
                for name,value in expected.get('evidence_operands',{}).items():
                    assert operands[name]==value,(case['id'],name,operands)
        passed.append(case['id'])
    print(json.dumps({'passed_count':len(passed),'passed':passed,'fixture_sha256':expected_hash,
                      'proof':'independently fixed input/economic projection only; not full canonical result oracle'}))


if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('artifact path and externally reviewed SHA256 required')
    check(*sys.argv[1:])
