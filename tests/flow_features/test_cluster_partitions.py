"""Producer-authored hand regressions, separate from independent oracle fixtures."""
from dataclasses import replace
from decimal import Decimal
import unittest

from option_flow_contracts import FlowContextCertificate, FlowQuote, FlowRational
from option_flow_features import evaluate_flow
from test_native import execution, reference, tape


OUTPUTS=('execution.cluster_premium','execution.cluster_trade_count',
         'execution.cluster_contracts','execution.cluster_span_ns',
         'execution.cluster_venue_count','execution.cluster_coverage')


def scenario(refs, facts):
    # One original quote signs every root: price4 is buy, price2 is midpoint unknown.
    quote=FlowQuote('q','r1','new',None,None,'A','s-A',1,1,1,
                    Decimal('1'),Decimal('3'),'regular','b')
    trades=tuple(replace(execution(identity,'A',event,price,position=event),reference_id=ref_id)
                 for identity,event,price,ref_id in facts)
    certificates=tuple(FlowContextCertificate('ctx-'+e.execution_id,'quote_prefix','A','session','s-A',
                                               0,e.position,('q',),True,0,'b') for e in trades)
    return tape(trades,refs,(quote,),certificates,output_ids=OUTPUTS,profile='option-quote-midpoint1')


class ClusterPartitionTests(unittest.TestCase):
    def assert_clusters(self,rows,expected,coverage):
        # Literal expected maps: ordered members -> (premium, count, span).
        premiums={row.evidence.cluster.execution_ids:row.value for row in rows
                  if row.output_id=='execution.cluster_premium'}
        self.assertEqual(premiums,{ids:FlowRational(premium,1) for ids,(premium,count,span) in expected.items()})
        self.assertEqual(len(rows),5*len(expected)+1)
        for output,field in (('execution.cluster_trade_count',1),('execution.cluster_contracts',1),
                             ('execution.cluster_span_ns',2)):
            actual={row.evidence.cluster.execution_ids:row.value for row in rows if row.output_id==output}
            self.assertEqual(actual,{ids:FlowRational(values[field],1) for ids,values in expected.items()})
        for row in rows:
            self.assertEqual((row.status,row.reason),('available','ok'))
            if row.output_id=='execution.cluster_venue_count':self.assertEqual(row.value,FlowRational(1,1))
            if row.output_id=='execution.cluster_coverage':self.assertEqual(row.value,FlowRational(*coverage))

    def test_each_economic_definition_field_partitions_same_quote(self):
        first=reference('A')
        for field,value,premium in (('right','put',400),('strike',Decimal('11'),400),
                                    ('multiplier',Decimal('50'),200),('expiry_ordinal',21,400)):
            with self.subTest(field=field):
                second=replace(first,reference_id='ref-other',**{field:value})
                snapshot,request=scenario((first,second),(('a',2,'4','ref-A'),('b',3,'4','ref-other')))
                self.assert_clusters(evaluate_flow(snapshot,request),
                                     {('a',):(400,1,0),('b',):(premium,1,0)},(1,1))

    def test_same_definition_with_different_reference_metadata_joins(self):
        first=reference('A')
        second=replace(first,reference_id='ref-other',revision_id='copy',known_at_ns=1,effective_from_ns=1)
        snapshot,request=scenario((first,second),(('a',2,'4','ref-A'),('b',3,'4','ref-other')))
        self.assert_clusters(evaluate_flow(snapshot,request),{('a','b'):(800,2,1)},(1,1))

    def test_definition_partitions_precede_certified_position_order(self):
        first=reference('A');second=replace(first,reference_id='ref-other',multiplier=Decimal('50'))
        snapshot,request=scenario((first,second),
                                 (('a',2,'4','ref-A'),('b',3,'4','ref-other'),('c',4,'4','ref-A')))
        self.assert_clusters(evaluate_flow(snapshot,request),
                             {('a','c'):(800,2,2),('b',):(200,1,0)},(1,1))

    def test_unknown_in_same_definition_breaks_only_its_run(self):
        first=reference('A');second=replace(first,reference_id='ref-other',right='put')
        snapshot,request=scenario((first,second),
                                 (('a',2,'4','ref-A'),('u',3,'2','ref-A'),
                                  ('b',4,'4','ref-other'),('c',5,'4','ref-A')))
        self.assert_clusters(evaluate_flow(snapshot,request),
                             {('a',):(400,1,0),('b',):(400,1,0),('c',):(400,1,0)},(6,7))

    def test_unknown_in_other_definition_cannot_break_run(self):
        first=reference('A');second=replace(first,reference_id='ref-other',right='put')
        snapshot,request=scenario((first,second),
                                 (('a',2,'4','ref-A'),('u',3,'2','ref-other'),('c',4,'4','ref-A')))
        self.assert_clusters(evaluate_flow(snapshot,request),{('a','c'):(800,2,2)},(4,5))


if __name__=='__main__':
    unittest.main()
