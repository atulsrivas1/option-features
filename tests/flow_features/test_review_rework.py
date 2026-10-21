"""Adversarial literals for independently reported review defects."""
from dataclasses import replace
from decimal import Decimal
import unittest

from option_flow_contracts import (
    FlowContextCertificate, FlowQuote, FlowCursor, FlowBaseline,
    FlowBaselineTarget, FlowRational, FlowValidationError,
    flow_record_digest, flow_validate_results,
)
from option_flow_features import evaluate_flow, replay_flow, make_flow_checkpoint, restore_flow
from option_flow_features.engine import merge_flow_history
from test_native import reference, execution, tape


class ReviewReworkTests(unittest.TestCase):
    def test_previous_session_quote_is_outside_certified_prefix(self):
        trade=execution('a','A',11,'3')
        quote=FlowQuote('old','r1','new',None,None,'A','s-A',1,1,1,
                        Decimal('1'),Decimal('3'),'regular','b')
        cert=FlowContextCertificate('ctx','quote_prefix','A','session','s-A',10,11,(),True,0,'b')
        snapshot,request=tape((trade,),(reference('A'),),(quote,),(cert,),profile='option-quote-midpoint1')
        witness=evaluate_flow(snapshot,request)[0].sign_witnesses[0]
        self.assertEqual((witness.sign,witness.reason,witness.quote_id),('unknown','quote_missing',None))

    def test_tick_different_definition_cannot_seed_target(self):
        prior=replace(execution('a','A',10,'1'),reference_id='ref-old')
        target=execution('b','A',20,'2')
        old=replace(reference('A'),reference_id='ref-old',strike=Decimal('20'))
        cert=FlowContextCertificate('ctx','execution_prefix','A','session','s-A',0,20,('a','b'),True,0,'b')
        snapshot,request=tape((prior,target),(reference('A'),old),certificates=(cert,),profile='option-tick1')
        witness=next(w for w in evaluate_flow(snapshot,request)[0].sign_witnesses if w.execution_id=='b')
        self.assertEqual((witness.sign,witness.reason,witness.predecessor_execution_id),('unknown','tick_initial_unknown',None))

    def test_tick_future_definition_at_target_A_cannot_seed(self):
        prior=replace(execution('a','A',10,'1',A=30),reference_id='ref-old')
        target=execution('b','A',20,'2')
        old=replace(reference('A'),reference_id='ref-old',known_at_ns=25)
        cert=FlowContextCertificate('ctx','execution_prefix','A','session','s-A',0,20,('a','b'),True,0,'b')
        snapshot,request=tape((prior,target),(reference('A'),old),certificates=(cert,),profile='option-tick1')
        witness=next(w for w in evaluate_flow(snapshot,request)[0].sign_witnesses if w.execution_id=='b')
        self.assertEqual(witness.sign,'unknown')

    def test_result_census_cannot_omit_selected_scalar(self):
        snapshot,request=tape((execution('a','A',10,'2'),),(reference('A'),),
                              output_ids=('flow.premium','flow.trade_count'))
        rows=evaluate_flow(snapshot,request)
        with self.assertRaises(FlowValidationError):flow_validate_results(rows[:1],request)

    def test_forged_result_request_fields_rejected(self):
        snapshot,request=tape((execution('a','A',10,'2'),),(reference('A'),))
        row=evaluate_flow(snapshot,request)[0]
        for changed in (replace(row,window_start_ns=1),replace(row,knowledge_cutoff_ns=101),
                        replace(row,policy_sha256='d'*64)):
            with self.subTest(changed=changed):
                with self.assertRaises(FlowValidationError):flow_validate_results((changed,),request)

    def test_base_rows_retain_actual_reference_causes(self):
        ref=replace(reference('A'),spot=Decimal('9'),spot_event_ns=0,spot_known_at_ns=0,
                    spot_stream_id='s-A',spot_position=0)
        snapshot,request=tape((execution('a','A',10,'2'),),(ref,))
        request=replace(request,policy=replace(request.policy,max_spot_age_ns=1))
        row=evaluate_flow(snapshot,request)[0]
        self.assertTrue({'missing_dte_reference','missing_spot_reference','stale_reference'} <= set(row.evidence.diagnostics))
        self.assertEqual((row.status,row.value),('available',FlowRational(200,1)))

    def test_invalid_restore_and_replay_request_are_closed_errors(self):
        snapshot,request=tape((execution('a','A',10,'2'),),(reference('A'),))
        checkpoint=make_flow_checkpoint(snapshot,request)
        for operation in (lambda:merge_flow_history(checkpoint,snapshot,object()),
                          lambda:replay_flow(snapshot,(request,object()))):
            with self.assertRaises(FlowValidationError) as caught:operation()
            self.assertEqual(caught.exception.code,'type_mismatch')

    def test_replay_obeys_lowered_cut_limit(self):
        snapshot,request=tape((execution('a','A',10,'2'),),(reference('A'),))
        request=replace(request,limits=replace(request.limits,max_replay_cuts=1))
        with self.assertRaises(FlowValidationError) as caught:replay_flow(snapshot,(request,request))
        self.assertEqual(caught.exception.code,'resource_limit')

    def test_premium_median_does_not_compute_unneeded_MAD(self):
        snapshot,request=tape((execution('a','A',90,'0'),),(reference('A','1'),),
                              output_ids=('activity.contracts_median',))
        request=replace(request,window_start_ns=80,window_end_ns=100,
                        limits=replace(request.limits,max_integer_digits=3),
                        baseline_targets=(FlowBaselineTarget('g',('s1','s2','s3','s4')),))
        policy=flow_record_digest('flow_policy',request.policy)
        vals=(FlowRational(0,1),FlowRational(1,9),FlowRational(1,8),FlowRational(1,7))
        # Premium summaries may be rational; contracts/trade_count remain integers.
        request=replace(request,output_ids=('activity.premium_median',))
        baselines=tuple(FlowBaseline('b'+str(i),'g','s'+str(i),i,'horizon',(i-1)*20,i*20,0,
                                    policy,'c'*64,'XTS','basis',FlowRational(0,1),FlowRational(0,1),value,(),True,'b')
                        for i,value in enumerate(vals,1))
        snapshot=replace(snapshot,baselines=baselines,populations=(replace(snapshot.populations[0],window_start_ns=80),))
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual(row.value,FlowRational(17,144))
        self.assertNotIn('mad',{operand.name for operand in row.evidence.operands})

    def test_missing_baseline_preserves_other_actual_causes(self):
        snapshot,request=tape((execution('a','A',90,'1'),),(reference('A'),),
                              output_ids=('activity.relative_volume',))
        request=replace(request,window_start_ns=80,window_end_ns=100,
                        baseline_targets=(FlowBaselineTarget('g',('s1','s2','s3')),))
        policy=flow_record_digest('flow_policy',request.policy)
        future=FlowBaseline('base2','g','s2',2,'horizon',20,40,101,policy,'c'*64,
                            'XTS','basis',FlowRational(1,1),FlowRational(1,1),FlowRational(1,1),(),True,'b')
        incomplete=replace(future,baseline_id='base3',slot_id='s3',session_ordinal=3,
                           window_start_ns=40,window_end_ns=60,known_at_ns=0,complete=False)
        snapshot=replace(snapshot,baselines=(future,incomplete),populations=(replace(snapshot.populations[0],window_start_ns=80),))
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual(row.reason,'incomplete_baseline')
        self.assertTrue({'incomplete_baseline','future_reference'} <= set(row.evidence.diagnostics))

    def test_future_member_outside_selected_window_does_not_poison_population(self):
        observed=execution('a','A',10,'2')
        outside=execution('b','A',30,'3')
        snapshot,request=tape((observed,outside),(reference('A'),),K=20,end=20)
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual((row.status,row.value,row.coverage.population_complete),('available',FlowRational(200,1),True))
        self.assertEqual(row.coverage.expected_count,1)
        # The immutable event's inside-window control must retain F39 missingness.
        inside=replace(outside,event_ns=11,signing_boundary_ns=30,known_at_ns=30)
        snapshot=replace(snapshot,executions=(observed,inside))
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual((row.status,row.reason,row.coverage.population_complete),('unavailable','incomplete_population',False))

    def test_incomplete_population_retains_computable_ratio_operands(self):
        snapshot,request=tape((execution('a','A',10,'2',side='buy'),),(reference('A'),),
                              output_ids=('flow.contract_hhi','flow.contract_top_share',
                                          'flow.sign_event_coverage','flow.known_sign_imbalance',
                                          'flow.total_premium_imbalance'))
        snapshot=replace(snapshot,populations=(replace(snapshot.populations[0],complete=False),))
        rows={row.output_id:row for row in evaluate_flow(snapshot,request)}
        operands={'flow.contract_hhi':(40000,40000),'flow.contract_top_share':(200,200),
                  'flow.sign_event_coverage':(1,1),'flow.known_sign_imbalance':(200,200),
                  'flow.total_premium_imbalance':(200,200)}
        for output,(numerator,denominator) in operands.items():
            row=rows[output]
            self.assertEqual((row.status,row.reason,row.value),('unavailable','incomplete_population',None))
            self.assertEqual((row.numerator,row.denominator),(FlowRational(numerator,1),FlowRational(denominator,1)))
            evidence={operand.name:operand.value for operand in row.evidence.operands}
            self.assertEqual((evidence['numerator'],evidence['denominator']),(row.numerator,row.denominator))
        self.assertEqual(rows['flow.contract_top_share'].evidence.tied_top_ids,('A',))

    def test_incomplete_population_retains_actual_reference_operands(self):
        observed=execution('a','A',11,'2',side='buy')
        future=replace(execution('b','B',12,'3'),known_at_ns=30,signing_boundary_ns=30)
        ref=replace(reference('A'),expiry_ordinal=12,civil_ordinal=10,civil_instant_ns=11,
                    civil_known_at_ns=11,calendar_id='cal',calendar_revision='r1',spot=Decimal('9'),
                    spot_event_ns=10,spot_known_at_ns=10,spot_stream_id='s-A',spot_position=10)
        outputs=('flow.dte_reference_coverage','flow.short_dte_premium_share',
                 'flow.short_dte_known_reference_share','flow.short_dte_observed_lower_share',
                 'flow.otm_reference_coverage','flow.otm_premium_share',
                 'flow.otm_known_reference_share','flow.otm_observed_lower_share')
        snapshot,request=tape((observed,future),(ref,reference('B')),K=20,end=20,output_ids=outputs)
        for row in evaluate_flow(snapshot,request):
            self.assertEqual((row.status,row.reason,row.value),('unavailable','incomplete_population',None))
            self.assertEqual((row.numerator,row.denominator),(FlowRational(200,1),FlowRational(200,1)))
            operands={operand.name:operand.value for operand in row.evidence.operands}
            self.assertEqual(operands['known_reference_premium'],FlowRational(200,1))
            self.assertEqual(operands['qualified_premium'],FlowRational(200,1))

    def test_incomplete_population_retains_admitted_activity_baseline(self):
        snapshot,request=tape((execution('a','A',90,'2'),),(reference('A'),),
                              output_ids=('activity.relative_volume',))
        request=replace(request,window_start_ns=80,
                        baseline_targets=(FlowBaselineTarget('g',('s1','s2')),))
        policy=flow_record_digest('flow_policy',request.policy)
        one=FlowBaseline('one','g','s1',1,'horizon',0,20,0,policy,'c'*64,'XTS','basis',
                         FlowRational(2,1),None,None,('e'*64,),True,'b')
        two=replace(one,baseline_id='two',slot_id='s2',session_ordinal=2,
                     window_start_ns=20,window_end_ns=40,contracts=FlowRational(4,1))
        snapshot=replace(snapshot,baselines=(one,two),populations=(replace(snapshot.populations[0],
                          window_start_ns=80,complete=False),))
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual((row.status,row.reason,row.value),('unavailable','incomplete_population',None))
        self.assertEqual((row.numerator,row.denominator),(FlowRational(1,1),FlowRational(3,1)))
        operands={operand.name:operand.value for operand in row.evidence.operands}
        self.assertEqual((operands['current'],operands['median']),(FlowRational(1,1),FlowRational(3,1)))
        self.assertEqual(row.baseline_ids,('one','two'))
        self.assertEqual(row.evidence.baseline_slot_ids,('s1','s2'))
        hashes=(flow_record_digest('flow_baseline',one),flow_record_digest('flow_baseline',two))
        self.assertEqual(row.evidence.baseline_record_sha256s,hashes)
        self.assertTrue(set(hashes)<=set(row.dependency_record_sha256s))
        missing=evaluate_flow(replace(snapshot,baselines=(one,)),request)[0]
        self.assertEqual(missing.reason,'incomplete_population')
        self.assertIn('incomplete_baseline',missing.evidence.diagnostics)
        self.assertNotIn('median',{operand.name for operand in missing.evidence.operands})
        self.assertIsNone(missing.numerator)
        self.assertEqual(missing.baseline_ids,('one',))

    def test_unselected_reference_subset_sum_cannot_block_base_output(self):
        trades=[];refs=[]
        for identity,event,price in (('a',11,'9.99'),('b',12,'0.01'),('c',13,'0.02'),('d',14,'0.98')):
            ref=replace(reference('A','1',expiry=12),reference_id='ref-'+identity)
            if identity in ('a','c'):
                ref=replace(ref,civil_ordinal=10,civil_instant_ns=event,civil_known_at_ns=event,
                            calendar_id='cal',calendar_revision='r1')
            refs.append(ref)
            trades.append(replace(execution(identity,'A',event,price),reference_id=ref.reference_id))
        snapshot,request=tape(tuple(trades),tuple(refs))
        request=replace(request,limits=replace(request.limits,max_integer_digits=3))
        self.assertEqual(evaluate_flow(snapshot,request)[0].value,FlowRational(11,1))
        # OTM family has no known spot; it must not evaluate unrelated DTE sums.
        otm=replace(request,output_ids=('flow.otm_reference_coverage',))
        self.assertEqual(evaluate_flow(snapshot,otm)[0].value,FlowRational(0,1))
        dte=replace(request,output_ids=('flow.dte_reference_coverage',))
        with self.assertRaises(FlowValidationError) as caught:evaluate_flow(snapshot,dte)
        self.assertEqual(caught.exception.code,'resource_limit')

    def test_unselected_clusters_cannot_block_base_output(self):
        # Corrected independent D3 witness; an earlier D2 draft was withdrawn
        # before runtime because its quote subtraction itself exceeded D2.
        trades=tuple(replace(execution(identity,'A',event,price,position=event),stream_id=stream)
                     for identity,event,price,stream in (('a',10,'9.99','S1'),('b',20,'0.01','S2'),
                                                         ('c',30,'0.02','S1'),('d',40,'0.98','S2')))
        quotes=(FlowQuote('q1','r1','new',None,None,'A','S1',1,1,1,Decimal('0'),Decimal('0.02'),'regular','b'),
                FlowQuote('q2','r1','new',None,None,'A','S2',2,2,2,Decimal('0'),Decimal('0.01'),'regular','b'))
        certificates=tuple(FlowContextCertificate('ctx'+str(position),'quote_prefix','A','session',stream,0,
                                                  position,(quote_id,),True,0,'b')
                           for position,stream,quote_id in ((10,'S1','q1'),(30,'S1','q1'),
                                                            (20,'S2','q2'),(40,'S2','q2')))
        snapshot,request=tape(trades,(reference('A','1'),),quotes,certificates,profile='option-quote-midpoint1')
        request=replace(request,limits=replace(request.limits,max_integer_digits=3),
                        policy=replace(request.policy,cluster_max_adjacent_gap_ns=20))
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual(row.value,FlowRational(11,1))
        self.assertTrue(all(w.sign=='buy' for w in row.sign_witnesses))
        selected=replace(request,output_ids=('execution.cluster_premium',))
        with self.assertRaises(FlowValidationError) as caught:evaluate_flow(snapshot,selected)
        self.assertEqual(caught.exception.code,'resource_limit')
        incomplete=replace(snapshot,populations=(replace(snapshot.populations[0],complete=False),))
        row=evaluate_flow(incomplete,selected)[0]
        self.assertEqual((row.status,row.reason,row.value,row.cluster_id),
                         ('unavailable','incomplete_population',None,None))
        self.assertIsNone(row.evidence.cluster)

    def test_quote_midpoint_uses_comparison_not_unneeded_difference(self):
        trade=execution('a','A',2,'0.04',position=2)
        quote=FlowQuote('q','r1','new',None,None,'A','s-A',1,1,1,
                        Decimal('0'),Decimal('0.05'),'regular','b')
        cert=FlowContextCertificate('ctx','quote_prefix','A','session','s-A',0,2,('q',),True,0,'b')
        snapshot,request=tape((trade,),(reference('A','1'),),(quote,),(cert,),
                              profile='option-quote-midpoint1',output_ids=('flow.buy_proxy_premium',))
        request=replace(request,limits=replace(request.limits,max_integer_digits=2))
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual(row.value,FlowRational(1,25))
        self.assertEqual((row.sign_witnesses[0].sign,row.sign_witnesses[0].reason),
                         ('buy','quote_above_midpoint'))

    def test_baseline_count_and_clock_exclude_missing_future_metrics(self):
        snapshot,request=tape(references=(reference('A'),),K=20,end=11,
                              output_ids=('activity.relative_volume',))
        request=replace(request,window_start_ns=10,
                        baseline_targets=(FlowBaselineTarget('g',('s1','s2','s3')),))
        policy=flow_record_digest('flow_policy',request.policy)
        known=FlowBaseline('known','g','s1',1,'horizon',0,1,5,policy,'c'*64,'XTS','basis',
                           FlowRational(2,1),None,None,('e'*64,),True,'b')
        future=replace(known,baseline_id='future',slot_id='s3',session_ordinal=3,
                        window_start_ns=2,window_end_ns=3,known_at_ns=30,contracts=FlowRational(4,1))
        snapshot=replace(snapshot,baselines=(known,future),
                         populations=(replace(snapshot.populations[0],window_start_ns=10),))
        row=evaluate_flow(snapshot,request)[0]
        operands={operand.name:operand.value for operand in row.evidence.operands}
        self.assertEqual((row.status,row.reason),('unavailable','incomplete_baseline'))
        self.assertEqual(operands['baseline_count'],FlowRational(1,1))
        self.assertEqual(row.available_at_ns,5)
        self.assertNotIn('median',operands)
        self.assertIn('future_reference',row.evidence.diagnostics)
        self.assertEqual(row.evidence.baseline_slot_ids,('s1','s2','s3'))
        self.assertIn(flow_record_digest('flow_baseline',future),row.dependency_record_sha256s)

    def test_known_null_or_incomplete_baseline_contributes_status_clock(self):
        snapshot,request=tape(references=(reference('A'),),K=20,end=11,
                              output_ids=('activity.relative_volume',))
        request=replace(request,window_start_ns=10,
                        baseline_targets=(FlowBaselineTarget('g',('s1',)),))
        policy=flow_record_digest('flow_policy',request.policy)
        baseline=FlowBaseline('known','g','s1',1,'horizon',0,1,7,policy,'c'*64,'XTS','basis',
                              None,None,None,('e'*64,),True,'b')
        for value in (baseline,replace(baseline,known_at_ns=9,complete=False,contracts=FlowRational(2,1))):
            with self.subTest(baseline=value):
                current=replace(snapshot,baselines=(value,),populations=(replace(snapshot.populations[0],window_start_ns=10),))
                row=evaluate_flow(current,request)[0]
                operands={operand.name:operand.value for operand in row.evidence.operands}
                self.assertEqual((row.status,row.reason),('unavailable','incomplete_baseline'))
                self.assertEqual(operands['baseline_count'],FlowRational(0,1))
                self.assertEqual(row.available_at_ns,value.known_at_ns)
                self.assertNotIn('median',operands)

    def test_sign_failure_diagnostics_distinguish_normal_classifications(self):
        root=execution('a','A',10,'2')
        cases=[]
        for side,semantics,clock,reason in (('unknown',None,None,'observed_missing'),
                                            ('unknown','supplied-side1',20,'observed_future')):
            snapshot,request=tape((replace(root,observed_side=side,observed_side_semantics_id=semantics,
                                           observed_side_known_at_ns=clock),),(reference('A'),))
            cases.append((snapshot,request,reason,()))
        for profile,reason in (('option-quote-midpoint1','quote_missing'),('option-tick1','tick_seed_unavailable')):
            snapshot,request=tape((root,),(reference('A'),),profile=profile)
            cases.append((snapshot,request,reason,('incomplete_context',)))
        empty=FlowContextCertificate('ctx','quote_prefix','A','session','s-A',0,10,(),True,0,'b')
        snapshot,request=tape((root,),(reference('A'),),certificates=(empty,),profile='option-quote-midpoint1')
        cases.append((snapshot,request,'quote_missing',()))
        for snapshot,request,reason,additional in cases:
            with self.subTest(reason=reason,additional=additional):
                row=evaluate_flow(snapshot,request)[0];witness=row.sign_witnesses[0]
                self.assertEqual(witness.reason,reason)
                self.assertEqual(witness.diagnostics.count(reason),1)
                self.assertTrue(set(additional)<=set(witness.diagnostics))
                self.assertIn(reason,row.evidence.diagnostics)
        # Supplied unknown and known buy are classifications, not admission errors.
        for side,reason in (('unknown','observed_unknown'),('buy','observed_buy')):
            snapshot,request=tape((replace(root,observed_side=side),),(reference('A'),))
            row=evaluate_flow(snapshot,request)[0]
            self.assertNotIn(reason,row.sign_witnesses[0].diagnostics)
            self.assertIn(reason,row.evidence.diagnostics)
        quote=FlowQuote('q','r1','new',None,None,'A','s-A',1,1,1,
                        Decimal('1'),Decimal('3'),'regular','b')
        quote_cert=FlowContextCertificate('ctx','quote_prefix','A','session','s-A',0,10,('q',),True,0,'b')
        snapshot,request=tape((root,),(reference('A'),),(quote,),(quote_cert,),profile='option-quote-midpoint1')
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual(row.sign_witnesses[0].reason,'quote_midpoint')
        self.assertNotIn('quote_midpoint',row.sign_witnesses[0].diagnostics)
        tick_cert=replace(quote_cert,kind='execution_prefix',expected_root_ids=('a',))
        snapshot,request=tape((root,),(reference('A'),),certificates=(tick_cert,),profile='option-tick1')
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual(row.sign_witnesses[0].reason,'tick_initial_unknown')
        self.assertNotIn('tick_initial_unknown',row.sign_witnesses[0].diagnostics)

    def test_selected_cancel_and_exclusion_status_clocks_are_causal(self):
        root=execution('a','A',10,'2')
        cancel=replace(root,revision_id='r2',kind='cancel',target_execution_id='a',target_revision_id='r1',
                        position=30,known_at_ns=30,price=None,quantity=None,condition='excluded',observed_side='unknown')
        excluded=replace(root,revision_id='r2',kind='replace',target_execution_id='a',target_revision_id='r1',
                          position=30,known_at_ns=30,condition='excluded')
        for revision in (cancel,excluded):
            with self.subTest(kind=revision.kind):
                snapshot,request=tape((root,revision),(reference('A'),),K=35,end=20)
                row=evaluate_flow(snapshot,request)[0]
                self.assertEqual(row.value,FlowRational(0,1))
                self.assertEqual(row.available_at_ns,30)
        # A later-known revision outside the selected window is provenance only.
        outside=execution('b','A',40,'1',position=40)
        outside_cancel=replace(outside,revision_id='r2',kind='cancel',target_execution_id='b',target_revision_id='r1',
                                position=80,known_at_ns=80,price=None,quantity=None,condition='excluded',observed_side='unknown')
        snapshot,request=tape((root,cancel,outside,outside_cancel),(reference('A'),),K=100,end=20)
        self.assertEqual(evaluate_flow(snapshot,request)[0].available_at_ns,30)
        # A future in-window cancellation is not the selected revision at K35.
        future=replace(cancel,known_at_ns=90,position=90)
        snapshot,request=tape((root,future),(reference('A'),),K=35,end=20)
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual((row.value,row.available_at_ns),(FlowRational(200,1),10))
