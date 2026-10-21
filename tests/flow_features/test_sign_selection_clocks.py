"""Producer-authored literal causal-clock regressions; not oracle fixtures."""
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
import json
import unittest

from option_flow_contracts import FlowContextCertificate, FlowCursor, FlowQuote, FlowRational, flow_record_digest
from option_flow_features import evaluate_flow
from test_native import execution, reference, tape


def cancelled_quote(root,known=20,position=4):
    return replace(root,revision_id='cancel',kind='cancel',target_quote_id=root.quote_id,
                   target_revision_id=root.revision_id,position=position,known_at_ns=known,
                   bid=None,ask=None,condition='excluded')


def quote_tape(quotes,*,K=30):
    target=execution('target','A',15,'3',position=3,A=30)
    cert=FlowContextCertificate('ctx','quote_prefix','A','session','s-A',0,3,('q1','q2'),True,0,'b')
    snapshot,request=tape((target,),(reference('A'),),quotes,(cert,),K=K,end=16,
                          output_ids=('flow.signed_execution_premium',),profile='option-quote-midpoint1')
    snapshot=replace(snapshot,populations=(replace(snapshot.populations[0],window_start_ns=15),))
    return snapshot,replace(request,window_start_ns=15)


class SignSelectionClockTests(unittest.TestCase):
    def test_newer_quote_cancellation_contributes_clock_not_context_operand(self):
        q1=FlowQuote('q1','r1','new',None,None,'A','s-A',1,5,5,Decimal('1'),Decimal('3'),'regular','b')
        q2=replace(q1,quote_id='q2',position=2,event_ns=10,known_at_ns=10,bid=Decimal('3'),ask=Decimal('5'))
        snapshot,request=quote_tape((q1,q2,cancelled_quote(q2)))
        row=evaluate_flow(snapshot,request)[0]
        self.assertEqual((row.value,row.available_at_ns),(FlowRational(300,1),20))
        self.assertEqual((row.sign_witnesses[0].sign,row.sign_witnesses[0].quote_id),('buy','q1'))
        # Frozen F43 minimal operand hash includes q1/ref/ctx, not the removed q2.
        payload=[30,flow_record_digest('flow_policy',request.policy),
                 [flow_record_digest('flow_quote',q1),flow_record_digest('flow_reference',snapshot.references[0])],
                 flow_record_digest('flow_context_certificate',snapshot.context_certificates[0])]
        expected=sha256(b'option-flow-context1\n'+json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.assertEqual(row.sign_witnesses[0].context_sha256,expected)
        original,original_request=quote_tape((q1,q2))
        control=evaluate_flow(original,original_request)[0]
        self.assertEqual((control.value,control.available_at_ns),(FlowRational(-300,1),15))
        absent,absent_request=quote_tape((q1,q2,cancelled_quote(q2),cancelled_quote(q1,known=22,position=5)))
        control=evaluate_flow(absent,absent_request)[0]
        self.assertEqual((control.value,control.available_at_ns),(FlowRational(0,1),22))
        self.assertEqual((control.sign_witnesses[0].quote_id,control.sign_witnesses[0].reason),(None,'quote_missing'))

    def test_quote_irrelevant_or_unadmitted_removal_does_not_raise_clock(self):
        q1=FlowQuote('q1','r1','new',None,None,'A','s-A',1,5,5,Decimal('1'),Decimal('3'),'regular','b')
        q2=replace(q1,quote_id='q2',position=2,event_ns=10,known_at_ns=10)
        # Older-than-winner cancellation is not a selection cause.
        snapshot,request=quote_tape((q1,q2,cancelled_quote(q1,known=25)))
        self.assertEqual(evaluate_flow(snapshot,request)[0].available_at_ns,15)
        # A cancellation after A, or hidden by selected cursor, cannot change origin selection.
        for cancel,cursor,K in ((cancelled_quote(q2,known=35),4,40),(cancelled_quote(q2),3,30)):
            with self.subTest(known=cancel.known_at_ns,cursor=cursor):
                snapshot,request=quote_tape((q1,q2,cancel),K=K)
                request=replace(request,cut_cursors=(FlowCursor('s-A',cursor),))
                row=evaluate_flow(snapshot,request)[0]
                self.assertEqual((row.available_at_ns,row.sign_witnesses[0].quote_id),(15,'q2'))
        # Roots after the target prefix or on another stream are not selection causes.
        for other in (replace(q2,quote_id='other',position=4,event_ns=17,known_at_ns=17),
                      replace(q2,quote_id='other',stream_id='other-stream',position=1)):
            cancel=cancelled_quote(other,known=25,position=other.position+1)
            snapshot,request=quote_tape((q1,q2,other,cancel))
            row=evaluate_flow(snapshot,request)[0]
            self.assertEqual((row.available_at_ns,row.sign_witnesses[0].quote_id),(15,'q2'))

    def test_tick_cancelled_or_excluded_prewindow_prefix_contributes_clock(self):
        first=execution('first','A',5,'1',position=1)
        removed=execution('removed','A',10,'3',position=2)
        target=execution('target','A',15,'2',position=3,A=30)
        cert=FlowContextCertificate('ctx','execution_prefix','A','session','s-A',0,3,
                                    ('first','removed','target'),True,0,'b')
        for kind in ('cancel','replace'):
            revision=replace(removed,revision_id='change',kind=kind,target_execution_id='removed',
                             target_revision_id='r1',position=4,known_at_ns=20,condition='excluded',
                             price=None if kind=='cancel' else Decimal('3'),quantity=None if kind=='cancel' else 1,
                             observed_side='unknown')
            snapshot,request=tape((first,removed,target,revision),(reference('A'),),certificates=(cert,),
                                  profile='option-tick1',K=30,end=16,output_ids=('flow.signed_execution_premium',))
            snapshot=replace(snapshot,populations=(replace(snapshot.populations[0],window_start_ns=15),))
            request=replace(request,window_start_ns=15)
            with self.subTest(kind=kind):
                row=evaluate_flow(snapshot,request)[0]
                self.assertEqual((row.value,row.available_at_ns),(FlowRational(200,1),20))
                self.assertEqual((row.sign_witnesses[0].sign,row.sign_witnesses[0].predecessor_execution_id),('buy','first'))
                hidden=replace(request,cut_cursors=(FlowCursor('s-A',3),))
                control=evaluate_flow(snapshot,hidden)[0]
                self.assertEqual((control.value,control.available_at_ns),(FlowRational(-200,1),15))

    def test_tick_unrelated_or_future_removals_do_not_raise_clock(self):
        first=execution('first','A',5,'1',position=1)
        target=execution('target','A',15,'2',position=3,A=30)
        base=execution('removed','A',10,'3',position=2)
        for case in ('definition','session','stream','posttarget','afterA'):
            removed=base;refs=(reference('A'),);known=20;position=4
            expected_ids=('first','removed','target');K=30;value=200
            if case=='definition':
                removed=replace(base,reference_id='ref-other')
                refs+=(replace(refs[0],reference_id='ref-other',multiplier=Decimal('50')),)
            elif case=='session':
                removed=replace(base,session_id='other-session');expected_ids=('first','target')
            elif case=='stream':
                removed=replace(base,stream_id='other-stream');expected_ids=('first','target')
            elif case=='posttarget':
                removed=replace(base,event_ns=17,signing_boundary_ns=17,known_at_ns=17,position=4)
                expected_ids=('first','target');position=5
            else:
                known=35;K=40;value=-200
            revision=replace(removed,revision_id='cancel',kind='cancel',target_execution_id='removed',
                             target_revision_id='r1',position=position,known_at_ns=known,
                             price=None,quantity=None,condition='excluded',observed_side='unknown')
            cert=FlowContextCertificate('ctx','execution_prefix','A','session','s-A',0,3,
                                        expected_ids,True,0,'b')
            snapshot,request=tape((first,removed,target,revision),refs,certificates=(cert,),
                                  profile='option-tick1',K=K,end=16,output_ids=('flow.signed_execution_premium',))
            snapshot=replace(snapshot,populations=(replace(snapshot.populations[0],window_start_ns=15),))
            request=replace(request,window_start_ns=15)
            with self.subTest(case=case):
                row=evaluate_flow(snapshot,request)[0]
                self.assertEqual((row.value,row.available_at_ns),(FlowRational(value,1),15))


if __name__=='__main__':
    unittest.main()
