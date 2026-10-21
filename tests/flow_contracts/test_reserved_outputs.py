"""Producer-authored closed-boundary regressions; no numerical producer imports."""
from dataclasses import fields, is_dataclass, replace
from hashlib import sha256
import json
import unittest

from option_flow_contracts import (
    FLOW_LIMITS, FlowCoverage, FlowEvidence, FlowPolicy, FlowRational, FlowRequest,
    FlowResult, FlowValidationError, decode_flow_record, decode_flow_results,
    encode_flow_record, encode_flow_results, flow_canonical_bytes,
    flow_record_digest, flow_to_payload, flow_validate_results,
)


OUTPUTS=('cross.share_equivalent_participation','cross.premium_turnover_participation',
         'cross.lag_correlation')


def literal(output):
    policy=FlowPolicy('r26-flow-policy1','option-origin-context1','option-observed-side1',
                      100,100,7,5,'horizon',1)
    request=FlowRequest('option-flow-request1',('g',),(output,),0,10,10,10,policy,(),(),
                        'option-flow-formulas1',FLOW_LIMITS)
    row=FlowResult(
        schema_version='option-flow-result1',group_id='g',output_id=output,cluster_id=None,
        window_start_ns=0,window_end_ns=10,knowledge_cutoff_ns=10,available_at_ns=0,
        temporal_profile='option-origin-context1',currency='XTS',action_basis_id='basis',origin='computed',
        value=None,unit='ratio',status='unsupported',reason='equity_integration_unqualified',quality_flags=(),
        coverage=FlowCoverage('pop',True,0,0,0,0,0,0,0),sign_witnesses=(),
        evidence=FlowEvidence((),(),(),(),(),(),None,(),(),('EQ153','EQ158'),()),
        numerator=None,denominator=None,baseline_ids=(),dependency_binding_ids=(),dependency_record_sha256s=(),
        policy_sha256=flow_record_digest('flow_policy',policy),
        request_sha256=flow_record_digest('flow_request',request),snapshot_sha256='a'*64,
        checkpoint_sha256=None,formula_version='option-flow-formulas1',
        contracts_package_version='0.1.0a1',calculation_package_version='0.1.0a1')
    return row,request


def literal_payload(value):
    # Build adversarial envelopes without asking production to encode an invalid row.
    if type(value) is FlowRational:
        return {'numerator':str(value.numerator),'denominator':str(value.denominator)}
    if is_dataclass(value):
        return {f.name:literal_payload(getattr(value,f.name)) for f in fields(value)}
    if type(value) is tuple:
        return [literal_payload(v) for v in value]
    return value


def literal_wire(kind,value):
    payload=literal_payload(value)
    def canonical(v):
        return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    digest=sha256(('option-flow-json1\n'+kind+'\n').encode()+canonical(payload)).hexdigest()
    return canonical({'schema_version':'option-flow-json1','record_type':kind,
                      'content_sha256':digest,'payload':payload})


class ReservedOutputTests(unittest.TestCase):
    def test_closed_unsupported_controls_roundtrip(self):
        for output in OUTPUTS:
            with self.subTest(output=output):
                row,request=literal(output)
                self.assertIsNone(flow_validate_results((row,)))
                self.assertIsNone(flow_validate_results((row,),request))
                self.assertEqual(decode_flow_results(encode_flow_results((row,))),(row,))
                self.assertEqual(decode_flow_record('flow_result',literal_wire('flow_result',row)),row)
                self.assertEqual(encode_flow_results((row,)),literal_wire('flow_results',(row,)))

    def test_reserved_outputs_reject_false_capabilities_at_every_boundary(self):
        for output in OUTPUTS:
            row,request=literal(output)
            mutations=(
                ('available',replace(row,status='available',reason='ok',value=FlowRational(1,1))),
                ('wrong-reason',replace(row,reason='unsupported_profile')),
                ('nonnull-value',replace(row,value=FlowRational(1,1))),
                ('nonnull-ratio',replace(row,numerator=FlowRational(1,1),denominator=FlowRational(1,1))),
                ('missing-producers',replace(row,evidence=replace(row.evidence,required_producer_ids=()))),
                ('one-producer',replace(row,evidence=replace(row.evidence,required_producer_ids=('EQ153',)))),
                ('wrong-producer',replace(row,evidence=replace(row.evidence,required_producer_ids=('EQ153','EQ159')))),
                ('extra-producer',replace(row,evidence=replace(row.evidence,required_producer_ids=('EQ153','EQ158','EQ159')))),
            )
            for mutation,bad in mutations:
                operations=(
                    lambda:flow_validate_results((bad,)),lambda:flow_validate_results((bad,),request),
                    lambda:flow_to_payload(bad),lambda:flow_canonical_bytes((bad,)),
                    lambda:flow_record_digest('flow_results',(bad,)),
                    lambda:encode_flow_record('flow_result',bad),
                    lambda:encode_flow_record('flow_results',(bad,)),lambda:encode_flow_results((bad,)),
                    lambda:decode_flow_record('flow_result',literal_wire('flow_result',bad)),
                    lambda:decode_flow_record('flow_results',literal_wire('flow_results',(bad,))),
                    lambda:decode_flow_results(literal_wire('flow_results',(bad,))),
                )
                for boundary,operation in enumerate(operations):
                    with self.subTest(output=output,mutation=mutation,boundary=boundary):
                        with self.assertRaises(FlowValidationError) as caught:operation()
                        self.assertEqual(caught.exception.code,'identity_mismatch')


if __name__=='__main__':
    unittest.main()
