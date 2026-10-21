"""Cancellation can stop real context/reducer work after one record step."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from option_flow_contracts import FlowContextCertificate
from option_flow_features import engine
from option_flow_features.arithmetic import ExactArithmetic
from test_native import reference, execution, tape


class CountingLedger(dict):
    reads=0

    def items(self):
        for item in super().items():
            self.reads+=1
            yield item


class CooperativeStepTests(unittest.TestCase):
    def test_context_membership_scan_stops_after_first_root(self):
        roots=tuple(execution('e'+str(i),'A',i+1,'1') for i in range(40))
        certificate=FlowContextCertificate('ctx','execution_prefix','A','session','s-A',0,40,
                                            tuple(sorted(e.execution_id for e in roots)),True,0,'b')
        snapshot,request=tape(roots,(reference('A'),),certificates=(certificate,),profile='option-tick1')
        ledger=CountingLedger({e.execution_id:[e] for e in roots})
        steps=engine._context_certificate_steps(snapshot,roots[-1],'execution_prefix',40,{'s-A':40},ledger)
        next(steps)  # One certificate eligibility step, before any root scan.
        self.assertEqual(ledger.reads,0)
        next(steps)  # One actual membership root, then caller can cancel/close.
        self.assertEqual(ledger.reads,1)
        steps.close()
        self.assertEqual(ledger.reads,1)

    def test_dependency_hashing_stops_before_second_record(self):
        first=reference('A');second=reference('B')
        original=engine.flow_record_digest
        calls=[]
        def recording(kind,value):
            calls.append(value)
            return original(kind,value)
        with patch.object(engine,'flow_record_digest',recording):
            steps=engine._dependency_steps([first,second])
            next(steps)
            self.assertEqual(calls,[first])
            steps.close()
            self.assertEqual(calls,[first])

    def test_group_reduction_yields_before_next_entry(self):
        roots=(execution('a','A',10,'2'),execution('b','A',11,'3'))
        snapshot,request=tape(roots,(reference('A'),))
        rows=engine.evaluate_flow(snapshot,request)
        witness={w.execution_id:w for w in rows[0].sign_witnesses}
        arithmetic=ExactArithmetic(256)
        entries=tuple((root,root,snapshot.references[0],arithmetic.exact(200 if root.execution_id=='a' else 300),
                       witness[root.execution_id],(False,False,False,False,set(),set())) for root in roots)
        steps=engine._reduce_group_steps(entries,snapshot.groups[0],snapshot.references,arithmetic)
        # Reference inventory step then a real first economic reduction step.
        next(steps)
        next(steps)
        self.assertEqual(steps.gi_frame.f_locals['totals']['premium'],arithmetic.exact(200))
        steps.close()
