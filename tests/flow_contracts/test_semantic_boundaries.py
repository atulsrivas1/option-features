"""Negative boundary witnesses requiring every public encoder to fail closed."""
import unittest

from option_flow_contracts import (
    FlowBinding, FlowSnapshot, FlowValidationError, flow_to_payload,
    flow_canonical_bytes, flow_record_digest, encode_flow_record, FlowCursor, FlowRational,
)


class SemanticBoundaryTests(unittest.TestCase):
    def test_generic_entrypoints_cannot_encode_duplicate_snapshot_identities(self):
        binding=FlowBinding('b','synthetic','r1','a'*64,'synthetic','Original synthetic facts')
        invalid=FlowSnapshot('option-flow-canonical1',(binding,binding),(),(),(),(),(),(),(),())
        for operation in (lambda:flow_to_payload(invalid),lambda:flow_canonical_bytes(invalid),
                          lambda:flow_record_digest('flow_snapshot',invalid),
                          lambda:encode_flow_record('flow_snapshot',invalid)):
            with self.subTest(operation=operation):
                with self.assertRaises(FlowValidationError) as caught:operation()
                self.assertEqual(caught.exception.code,'identity_conflict')

    def test_global_shape_error_precedes_earlier_scalar_bounds(self):
        invalid=FlowSnapshot('option-flow-canonical1',(),(),(),(),(),(),(),(),
                             (FlowCursor('s',-1),FlowCursor('t',True)))
        with self.assertRaises(FlowValidationError) as caught:flow_canonical_bytes(invalid)
        self.assertEqual((caught.exception.code,caught.exception.path),
                         ('type_mismatch','/cursors/1/max_position'))

    def test_huge_typed_integer_is_a_stable_resource_error(self):
        for value in (FlowRational(10**5000,1),FlowCursor('s',10**5000)):
            with self.assertRaises(FlowValidationError) as caught:flow_canonical_bytes(value)
            self.assertEqual(caught.exception.code,'resource_limit')
