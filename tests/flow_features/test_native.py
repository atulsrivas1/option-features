"""Literal arithmetic and causal witnesses, not generated expected results."""
from dataclasses import replace
from decimal import Decimal
import unittest

from option_flow_contracts import (
    FlowBinding, FlowReference, FlowExecution, FlowQuote, FlowGroup,
    FlowPopulation, FlowContextCertificate, FlowSnapshot, FlowCursor,
    FlowPolicy, FlowRequest, FlowRational, FlowValidationError,
    FlowBaseline, FlowBaselineTarget,
    FLOW_LIMITS, flow_record_digest, encode_flow_results, decode_flow_results,
)
from option_flow_features import evaluate_flow, replay_flow, make_flow_checkpoint, restore_flow


def reference(contract, multiplier='100', right='call', expiry=20):
    return FlowReference('ref-'+contract,contract,'U','XTS','basis',right,Decimal('10'),
                         Decimal(multiplier),expiry,None,None,None,None,None,
                         None,None,None,None,None,0,None,0,'r1','b')


def execution(identity,contract,event,price,quantity=1,side='unknown',position=None,A=None):
    return FlowExecution(identity,'r1','new',None,None,contract,'session','s-'+contract,
                         event if position is None else position,event,event if A is None else A,event,
                         Decimal(price),quantity,'regular','venue',side,'supplied-side1',event,
                         'ref-'+contract,'b')


def tape(executions=(),references=(),quotes=(),certificates=(),*,expected=None,
         output_ids=('flow.premium',),profile='option-observed-side1',K=100,end=100):
    contracts=tuple(sorted({r.contract_id for r in references}))
    group=FlowGroup('g','underlying','U',contracts,None,None,'XTS','basis')
    binding=FlowBinding('b','synthetic','r1','a'*64,'synthetic','Original synthetic test')
    positions={}
    for value in executions+quotes:positions[value.stream_id]=max(positions.get(value.stream_id,0),value.position)
    cursors=tuple(FlowCursor(k,v) for k,v in sorted(positions.items()))
    population=FlowPopulation('pop','g',0,end,contracts,
                              tuple(sorted({e.execution_id for e in executions}) if expected is None else expected),
                              tuple(sorted({q.quote_id for q in quotes})),True,0,'b')
    snapshot=FlowSnapshot('option-flow-canonical1',(binding,),references,executions,quotes,(group,),
                          (population,),certificates,(),cursors)
    policy=FlowPolicy('r26-flow-policy1','option-origin-context1',profile,100,100,2,5,'horizon',1)
    request=FlowRequest('option-flow-request1',('g',),tuple(sorted(output_ids)),0,end,K,10,policy,(),
                        cursors,'option-flow-formulas1',FLOW_LIMITS)
    return snapshot,request


def values(rows):
    return {row.output_id:row.value for row in rows}


class NativeTests(unittest.TestCase):
    def test_four_trade_hand_witness(self):
        refs=(reference('A'),reference('B',right='put'),reference('C','50','put',21))
        trades=(execution('a','A',11,'2',3,'buy'),execution('b','A',12,'1.5',2,'sell'),
                execution('c','B',13,'4',1,'buy'),execution('d','C',14,'2'))
        expected={'flow.trade_count':(4,1),'flow.contracts':(7,1),'flow.share_equivalent':(650,1),
                  'flow.premium':(1400,1),'flow.buy_proxy_premium':(1000,1),'flow.sell_proxy_premium':(300,1),
                  'flow.unknown_premium':(100,1),'flow.signed_execution_premium':(700,1),
                  'flow.known_sign_imbalance':(7,13),'flow.total_premium_imbalance':(1,2),
                  'flow.unknown_premium_share':(1,14),'flow.sign_event_coverage':(3,4),
                  'flow.sign_premium_coverage':(13,14),'flow.right_positive_premium':(600,1),
                  'flow.right_negative_premium':(700,1),'flow.net_directional_premium':(-100,1),
                  'flow.call_premium':(900,1),'flow.put_premium':(500,1),'flow.put_call_premium_ratio':(5,9),
                  'flow.contract_hhi':(1,2),'flow.contract_top_share':(9,14),
                  'flow.expiry_hhi':(85,98),'flow.expiry_top_share':(13,14)}
        snapshot,request=tape(trades,refs,output_ids=tuple(expected))
        rows=evaluate_flow(snapshot,request)
        self.assertEqual(values(rows),{key:FlowRational(*value) for key,value in expected.items()})
        self.assertEqual(len(rows),23)
        self.assertTrue(all(row.coverage.population_complete for row in rows))
        self.assertEqual(rows[0].coverage.unknown_sign_count,1)
        self.assertEqual(decode_flow_results(encode_flow_results(rows)),rows)

    def test_complete_empty_is_zero_and_ratio_undefined(self):
        snapshot,request=tape(references=(reference('A'),),
                              output_ids=('flow.premium','flow.sign_event_coverage'))
        rows={r.output_id:r for r in evaluate_flow(snapshot,request)}
        self.assertEqual(rows['flow.premium'].value,FlowRational(0,1))
        self.assertEqual(rows['flow.sign_event_coverage'].reason,'zero_denominator')
        self.assertEqual(rows['flow.sign_event_coverage'].denominator,FlowRational(0,1))
        self.assertEqual(rows['flow.premium'].coverage.expected_count,0)

    def test_declared_future_member_is_not_erased(self):
        trades=(execution('a','A',10,'2'),replace(execution('b','A',11,'3'),known_at_ns=30,signing_boundary_ns=30))
        snapshot,request=tape(trades,(reference('A'),),K=20,end=20)
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual((row.status,row.reason,row.value),('unavailable','incomplete_population',None))
        self.assertIsNone(row.coverage.expected_count)
        self.assertEqual(row.coverage.observed_count,1)
        self.assertEqual(next(o.value for o in row.evidence.operands if o.name=='premium'),FlowRational(200,1))

    def test_A_after_K_guard_and_admissible_control(self):
        snapshot,request=tape((execution('a','A',10,'2',A=30),),(reference('A'),),K=20,end=15)
        with self.assertRaises(FlowValidationError) as caught:evaluate_flow(snapshot,request)
        self.assertEqual((caught.exception.code,caught.exception.path),
                         ('identity_mismatch','/request/knowledge_cutoff_ns'))
        self.assertEqual(evaluate_flow(snapshot,replace(request,knowledge_cutoff_ns=30))[0].value,FlowRational(200,1))

    def test_tick_historical_context_preserves_later_cancelled_predecessor(self):
        a=execution('a','A',10,'100');b=execution('b','A',20,'101')
        cancel=replace(a,revision_id='r2',kind='cancel',target_execution_id='a',target_revision_id='r1',
                       position=30,known_at_ns=30,price=None,quantity=None,condition='excluded',observed_side='unknown')
        cert=FlowContextCertificate('ctx','execution_prefix','A','session','s-A',0,20,('a','b'),True,0,'b')
        snapshot,request=tape((a,b,cancel),(reference('A'),),certificates=(cert,),profile='option-tick1',K=35,end=25,
                              output_ids=('flow.premium','flow.buy_proxy_premium'))
        rows=evaluate_flow(snapshot,request)
        self.assertEqual(values(rows)['flow.buy_proxy_premium'],FlowRational(10100,1))
        self.assertEqual(rows[0].sign_witnesses[0].sign,'buy')
        self.assertEqual(rows[0].sign_witnesses[0].predecessor_execution_id,'a')

    def test_quote_correction_does_not_change_origin_context(self):
        trade=execution('t','A',15,'2',position=15)
        correction=replace(trade,revision_id='r2',kind='replace',target_execution_id='t',
                           target_revision_id='r1',position=17,known_at_ns=17,price=Decimal('2.5'))
        quote=FlowQuote('q','r1','new',None,None,'A','s-A',12,12,12,Decimal('1'),Decimal('3'),'regular','b')
        qcorrection=replace(quote,revision_id='r2',kind='replace',target_quote_id='q',target_revision_id='r1',
                            position=16,known_at_ns=16,bid=Decimal('2'),ask=Decimal('4'))
        cert=FlowContextCertificate('ctx','quote_prefix','A','session','s-A',0,15,('q',),True,0,'b')
        snapshot,request=tape((trade,correction),(reference('A'),),(quote,qcorrection),(cert,),
                              profile='option-quote-midpoint1',K=18,end=18)
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual(row.sign_witnesses[0].sign,'buy')
        self.assertEqual(row.sign_witnesses[0].quote_revision_id,'r1')
        self.assertGreaterEqual(row.available_at_ns,17)

    def test_reserved_equity_outputs_are_explicitly_unsupported(self):
        snapshot,request=tape(references=(reference('A'),),output_ids=('cross.share_equivalent_participation',))
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual((row.status,row.reason),('unsupported','equity_integration_unqualified'))
        self.assertEqual(row.evidence.required_producer_ids,('EQ153','EQ158'))

    def test_checkpoint_restore_identity_and_empty_suffix(self):
        snapshot,request=tape((execution('a','A',10,'2'),),(reference('A'),))
        checkpoint=make_flow_checkpoint(snapshot,request)
        suffix=FlowSnapshot('option-flow-canonical1',(),(),(),(),(),(),(),(),snapshot.cursors)
        restored,output=restore_flow(checkpoint,suffix,request)
        expected=evaluate_flow(snapshot,request,input_checkpoint_sha256=flow_record_digest('flow_checkpoint',checkpoint))
        self.assertEqual(restored,expected)
        self.assertEqual(output,checkpoint)

    def test_negative_dte_only_invalidates_dte_reference(self):
        ref=replace(reference('A'),strike=Decimal('100'),expiry_ordinal=9,
                    civil_ordinal=10,civil_instant_ns=11,civil_known_at_ns=10,
                    calendar_id='calendar',calendar_revision='r1',spot=Decimal('90'),
                    spot_event_ns=10,spot_known_at_ns=10,spot_stream_id='s-A',spot_position=0)
        expected={'flow.premium':FlowRational(200,1),'flow.trade_count':FlowRational(1,1),
                  'flow.contracts':FlowRational(1,1),'flow.dte_reference_coverage':FlowRational(0,1),
                  'flow.short_dte_observed_lower_share':FlowRational(0,1),'flow.otm_premium_share':FlowRational(1,1)}
        snapshot,request=tape((execution('a','A',11,'2',side='buy'),),(ref,),
                              output_ids=tuple(expected)+('flow.short_dte_premium_share','flow.short_dte_known_reference_share'))
        rows={r.output_id:r for r in evaluate_flow(snapshot,request)}
        for key,value in expected.items():self.assertEqual(rows[key].value,value)
        self.assertEqual(rows['flow.short_dte_premium_share'].reason,'missing_dte_reference')
        self.assertEqual(rows['flow.short_dte_known_reference_share'].reason,'zero_denominator')
        self.assertEqual(rows['flow.premium'].coverage.dte_eligible_count,0)
        self.assertEqual(rows['flow.premium'].coverage.otm_eligible_count,1)
        self.assertEqual(rows['flow.premium'].evidence.exclusions,())

    def test_baseline_median_mad_and_robust_z_literal(self):
        outputs=('activity.relative_volume','activity.relative_trade_count','activity.contracts_median',
                 'activity.trade_count_median','activity.premium_median','activity.premium_mad','activity.premium_robust_z')
        snapshot,request=tape((execution('a','A',50,'0.01',11),),(reference('A'),),output_ids=outputs,end=60)
        request=replace(request,window_start_ns=40,target_session_ordinal=10,
                        baseline_targets=(FlowBaselineTarget('g',('s1','s2','s3','s4')),))
        snapshot=replace(snapshot,populations=(replace(snapshot.populations[0],window_start_ns=40,window_end_ns=60),))
        policy_hash=flow_record_digest('flow_policy',request.policy)
        baselines=tuple(FlowBaseline('base'+str(i),'g','s'+str(i),i,'horizon',i*5,i*5+20,0,
                                    policy_hash,'c'*64,'XTS','basis',FlowRational(v,1),FlowRational(v,1),
                                    FlowRational(v,1),(),True,'b') for i,v in enumerate((2,4,6,8),1))
        # Distinct completed windows must not overlap; use negative-free intervals.
        baselines=tuple(replace(b,window_start_ns=(i-1)*20,window_end_ns=i*20) for i,b in enumerate(baselines,1))
        request=replace(request,window_start_ns=80,window_end_ns=100)
        trades=(replace(snapshot.executions[0],event_ns=90,signing_boundary_ns=90,known_at_ns=90,position=90,
                        observed_side_known_at_ns=90),)
        snapshot=replace(snapshot,executions=trades,cursors=(FlowCursor('s-A',90),),
                         populations=(replace(snapshot.populations[0],window_start_ns=80,window_end_ns=100),),baselines=baselines)
        request=replace(request,cut_cursors=snapshot.cursors)
        rows={r.output_id:r for r in evaluate_flow(snapshot,request)}
        self.assertEqual(rows['activity.relative_volume'].value,FlowRational(11,5))
        self.assertEqual(rows['activity.relative_trade_count'].value,FlowRational(1,5))
        self.assertEqual(rows['activity.premium_median'].value,FlowRational(5,1))
        self.assertEqual(rows['activity.premium_mad'].value,FlowRational(2,1))
        self.assertEqual(rows['activity.premium_robust_z'].value,FlowRational(5000,2471))

    def test_three_adjacent_gap_cluster_span_exceeds_gap(self):
        trades=tuple(execution('t'+str(event),'A',event,'3',position=event,side='unknown') for event in (10,15,20))
        quote=FlowQuote('q','r1','new',None,None,'A','s-A',1,1,1,Decimal('1'),Decimal('3'),'regular','b')
        cert=FlowContextCertificate('ctx','quote_prefix','A','session','s-A',0,20,('q',),True,0,'b')
        outputs=('execution.cluster_premium','execution.cluster_trade_count','execution.cluster_contracts',
                 'execution.cluster_span_ns','execution.cluster_venue_count','execution.cluster_coverage')
        snapshot,request=tape(trades,(reference('A'),),(quote,),(cert,),output_ids=outputs,profile='option-quote-midpoint1')
        rows=evaluate_flow(snapshot,request)
        self.assertEqual(values(rows),{'execution.cluster_premium':FlowRational(900,1),
                                      'execution.cluster_trade_count':FlowRational(3,1),
                                      'execution.cluster_contracts':FlowRational(3,1),
                                      'execution.cluster_span_ns':FlowRational(10,1),
                                      'execution.cluster_venue_count':FlowRational(1,1),
                                      'execution.cluster_coverage':FlowRational(1,1)})
        self.assertEqual(len({row.cluster_id for row in rows if row.cluster_id}),1)
        self.assertEqual(decode_flow_results(encode_flow_results(rows)),rows)

    def test_unknown_midpoint_breaks_cluster(self):
        trades=(execution('a','A',10,'3'),execution('b','A',12,'2'),execution('c','A',14,'3'))
        quote=FlowQuote('q','r1','new',None,None,'A','s-A',1,1,1,Decimal('1'),Decimal('3'),'regular','b')
        cert=FlowContextCertificate('ctx','quote_prefix','A','session','s-A',0,14,('q',),True,0,'b')
        snapshot,request=tape(trades,(reference('A'),),(quote,),(cert,),output_ids=('execution.cluster_premium',),profile='option-quote-midpoint1')
        rows=evaluate_flow(snapshot,request)
        self.assertEqual(len(rows),2)
        self.assertTrue(all(row.value==FlowRational(300,1) for row in rows))

    def test_replay_uses_same_ledger_with_future_correction(self):
        root=execution('a','A',10,'2')
        correction=replace(root,kind='replace',revision_id='r2',target_execution_id='a',target_revision_id='r1',
                           position=30,known_at_ns=30,price=Decimal('3'))
        snapshot,request=tape((root,correction),(reference('A'),),K=35,end=20)
        early=replace(request,knowledge_cutoff_ns=20,cut_cursors=(FlowCursor('s-A',10),))
        rows=replay_flow(snapshot,(early,request))
        self.assertEqual(rows[0][0].value,FlowRational(200,1))
        self.assertEqual(rows[1][0].value,FlowRational(300,1))
        self.assertEqual(rows[0][0].snapshot_sha256,rows[1][0].snapshot_sha256)
        self.assertNotEqual(rows[0][0].request_sha256,rows[1][0].request_sha256)
        with self.assertRaises(FlowValidationError) as caught:make_flow_checkpoint(snapshot,early)
        self.assertEqual(caught.exception.code,'checkpoint_cut_mismatch')

    def test_lowered_integer_budget_applies_before_publication(self):
        snapshot,request=tape((execution('a','A',10,'2',5),),(reference('A'),))
        request=replace(request,limits=replace(FLOW_LIMITS,max_integer_digits=2))
        with self.assertRaises(FlowValidationError) as caught:evaluate_flow(snapshot,request)
        self.assertEqual(caught.exception.code,'resource_limit')

    def test_original_definition_known_after_A_rejected_and_controls(self):
        snapshot,request=tape((execution('a','A',11,'2'),),(replace(reference('A'),known_at_ns=12),),K=20,end=20)
        with self.assertRaises(FlowValidationError) as caught:evaluate_flow(snapshot,request)
        self.assertEqual((caught.exception.code,caught.exception.path),
                         ('identity_mismatch','/snapshot/executions/0/reference_id'))
        admitted=replace(snapshot,executions=(replace(snapshot.executions[0],signing_boundary_ns=12),))
        self.assertEqual(evaluate_flow(admitted,request)[0].value,FlowRational(200,1))
        future_unused=replace(reference('UNUSED'),known_at_ns=30)
        admitted=replace(admitted,references=admitted.references+(future_unused,))
        self.assertEqual(evaluate_flow(admitted,request)[0].value,FlowRational(200,1))
        # A pre-window retained execution root cannot hide an invalid definition.
        later=replace(request,window_start_ns=12)
        with self.assertRaises(FlowValidationError) as caught:evaluate_flow(snapshot,later)
        self.assertEqual(caught.exception.code,'identity_mismatch')


if __name__=='__main__':unittest.main()
