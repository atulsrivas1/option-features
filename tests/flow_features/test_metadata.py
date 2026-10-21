"""F43 metadata witnesses using independent literal JSON/hash construction."""
from hashlib import sha256
from decimal import Decimal
import json
import unittest

from option_flow_contracts import FlowQuote, FlowContextCertificate
from option_flow_features import evaluate_flow
from test_native import reference, execution, tape


def J(payload):
    return json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


def R(kind,payload):
    return sha256(('option-flow-record1\n'+kind+'\n').encode()+J(payload)).hexdigest()


def policy(profile):
    return {'schema_version':'r26-flow-policy1','temporal_profile':'option-origin-context1',
            'signing_profile':profile,'max_quote_age_ns':100,'max_spot_age_ns':100,
            'short_dte_max_days':2,'cluster_max_adjacent_gap_ns':5,'horizon_id':'horizon',
            'minimum_matched_prior_windows':1}


REF={'reference_id':'ref-A','contract_id':'A','underlying_id':'U','currency':'XTS','action_basis_id':'basis',
     'right':'call','strike':'10','multiplier':'100','expiry_ordinal':20,
     'civil_ordinal':None,'civil_instant_ns':None,'civil_known_at_ns':None,'calendar_id':None,'calendar_revision':None,
     'spot':None,'spot_event_ns':None,'spot_known_at_ns':None,'spot_stream_id':None,'spot_position':None,
     'effective_from_ns':0,'effective_to_ns':None,'known_at_ns':0,'revision_id':'r1','input_binding_id':'b'}
EXEC={'execution_id':'a','revision_id':'r1','kind':'new','target_execution_id':None,'target_revision_id':None,
      'contract_id':'A','session_id':'session','stream_id':'s-A','position':10,'event_ns':10,
      'signing_boundary_ns':10,'known_at_ns':10,'price':'1','quantity':'1','condition':'regular','venue_id':'venue',
      'observed_side':'unknown','observed_side_semantics_id':'supplied-side1','observed_side_known_at_ns':10,
      'reference_id':'ref-A','input_binding_id':'b'}


def context(A,profile,records,certificate=None):
    return sha256(b'option-flow-context1\n'+J([A,R('flow_policy',policy(profile)),
                  records,R('flow_context_certificate',certificate) if certificate else None])).hexdigest()


def cert_payload(kind,ids,through):
    return {'certificate_id':'ctx','kind':kind,'contract_id':'A','session_id':'session','stream_id':'s-A',
            'session_start_ns':0,'through_position':through,'expected_root_ids':ids,'complete':True,
            'known_at_ns':0,'input_binding_id':'b'}


class MetadataTests(unittest.TestCase):
    def test_observed_minimal_context_is_original_root_and_reference(self):
        snapshot,request=tape((execution('a','A',10,'1'),),(reference('A'),))
        witness=evaluate_flow(snapshot,request)[0].sign_witnesses[0]
        expected=context(10,'option-observed-side1',[R('flow_execution',EXEC),R('flow_reference',REF)])
        self.assertEqual(witness.context_sha256,expected)

    def test_tick_reused_reference_deduplicates_at_minimum_root_position(self):
        cert=FlowContextCertificate('ctx','execution_prefix','A','session','s-A',0,20,('a','b'),True,0,'b')
        snapshot,request=tape((execution('a','A',10,'1'),execution('b','A',20,'2')),
                              (reference('A'),),certificates=(cert,),profile='option-tick1')
        witness=next(w for w in evaluate_flow(snapshot,request)[0].sign_witnesses if w.execution_id=='b')
        expected=context(20,'option-tick1',[R('flow_execution',EXEC),R('flow_reference',REF)],
                         cert_payload('execution_prefix',['a','b'],20))
        self.assertEqual(witness.context_sha256,expected)

    def test_quote_context_binds_only_selected_latest_market(self):
        old=FlowQuote('q0','r1','new',None,None,'A','s-A',5,5,5,Decimal('0'),Decimal('1'),'regular','b')
        selected=FlowQuote('q1','r1','new',None,None,'A','s-A',8,8,8,Decimal('1'),Decimal('3'),'regular','b')
        cert=FlowContextCertificate('ctx','quote_prefix','A','session','s-A',0,10,('q0','q1'),True,0,'b')
        snapshot,request=tape((execution('a','A',10,'3'),),(reference('A'),),(old,selected),(cert,),
                              profile='option-quote-midpoint1')
        witness=evaluate_flow(snapshot,request)[0].sign_witnesses[0]
        quote={'quote_id':'q1','revision_id':'r1','kind':'new','target_quote_id':None,'target_revision_id':None,
               'contract_id':'A','stream_id':'s-A','position':8,'event_ns':8,'known_at_ns':8,
               'bid':'1','ask':'3','condition':'regular','input_binding_id':'b'}
        expected=context(10,'option-quote-midpoint1',[R('flow_quote',quote),R('flow_reference',REF)],
                         cert_payload('quote_prefix',['q0','q1'],10))
        self.assertEqual(witness.context_sha256,expected)
        self.assertEqual(witness.quote_id,'q1')

    def test_ratio_operands_preserve_dimensions(self):
        snapshot,request=tape((execution('a','A',10,'2',side='buy'),),(reference('A'),),
                              output_ids=('flow.contract_hhi','flow.sign_event_coverage','flow.known_sign_imbalance'))
        rows={r.output_id:r for r in evaluate_flow(snapshot,request)}
        for output,unit in (('flow.contract_hhi','group_currency_squared'),
                            ('flow.sign_event_coverage','executions'),('flow.known_sign_imbalance','group_currency')):
            operands={v.name:v for v in rows[output].evidence.operands}
            self.assertEqual((operands['numerator'].unit,operands['denominator'].unit),(unit,unit))
            self.assertEqual(rows[output].unit,'ratio')
