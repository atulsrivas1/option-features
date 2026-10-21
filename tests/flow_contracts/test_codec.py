"""Source-development checks with literal independent expectations."""
from dataclasses import replace
from decimal import Decimal, localcontext
from hashlib import sha256
import json
import unittest

from option_flow_contracts import (
    FlowBinding, FlowRational, FlowValidationError, FLOW_LIMITS,
    FlowSnapshot, FlowCursor, flow_canonical_bytes, flow_record_digest,
    encode_flow_record, decode_flow_record, flow_validate_snapshot,
)
from option_flow_contracts.codec import decimal_text


class CodecTests(unittest.TestCase):
    def setUp(self):
        self.binding = FlowBinding('b', 'synthetic', 'r1', 'a'*64,
                                   'synthetic', 'Original synthetic facts')

    def error(self, code, operation):
        with self.assertRaises(FlowValidationError) as caught:
            operation()
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_literal_canonical_binding_and_domain(self):
        expected = ('{"binding_id":"b","provenance_mode":"synthetic",'
                    '"rights_reference":"Original synthetic facts",'
                    '"source_content_sha256":"' + 'a'*64 + '",'
                    '"source_id":"synthetic","source_revision":"r1"}').encode()
        self.assertEqual(flow_canonical_bytes(self.binding), expected)
        self.assertEqual(flow_record_digest('flow_binding', self.binding),
                         sha256(b'option-flow-record1\nflow_binding\n'+expected).hexdigest())

    def test_roundtrip_and_whitespace(self):
        wire = encode_flow_record('flow_binding', self.binding)
        self.assertEqual(decode_flow_record('flow_binding', wire), self.binding)
        self.error('noncanonical', lambda: decode_flow_record('flow_binding', wire+b'\n'))

    def test_duplicate_keys_before_digest(self):
        self.error('field_set', lambda: decode_flow_record('flow_binding',
                    b'{"schema_version":"x","schema_version":"y"}'))

    def test_boolean_and_subclasses_are_not_integers(self):
        self.error('type_mismatch', lambda: flow_canonical_bytes(FlowRational(True, 1)))
        class Impostor(FlowBinding):
            pass
        self.error('type_mismatch', lambda: flow_canonical_bytes(
            Impostor('b','s','r','a'*64,'synthetic','original')))

    def test_rational_reduced_and_string_encoding(self):
        self.assertEqual(flow_canonical_bytes(FlowRational(-7,13)),
                         b'{"denominator":"13","numerator":"-7"}')
        self.error('invalid_scalar', lambda: flow_canonical_bytes(FlowRational(2,4)))
        self.error('invalid_scalar', lambda: flow_canonical_bytes(FlowRational(0,2)))

    def test_context_independent_decimal_normalization(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(decimal_text(Decimal('12345.000000000000000000000000')), '12345')
            self.assertEqual(decimal_text(Decimal('1.0000000000000000000')), '1')
            self.assertEqual(decimal_text(Decimal('0.000000000000000001')), '0.000000000000000001')
            self.assertEqual(decimal_text(Decimal('-0.000000000000000000000')), '0')
        self.error('resource_limit', lambda: decimal_text(Decimal('0.0000000000000000001')))

    def test_record_field_closure(self):
        payload = json.loads(encode_flow_record('flow_binding', self.binding))
        payload['payload']['extra'] = 1
        self.error('field_set', lambda: decode_flow_record('flow_binding',
                   json.dumps(payload,separators=(',',':'),sort_keys=True).encode()))

    def test_limits_and_bad_tokens(self):
        self.error('resource_limit', lambda: decode_flow_record('flow_binding',
                   b' '*33, replace(FLOW_LIMITS,max_wire_bytes=32)))
        self.error('invalid_utf8', lambda: decode_flow_record('flow_binding',b'\xff'))
        self.error('resource_limit', lambda: decode_flow_record('flow_binding',b'['*33))
        self.error('type_mismatch', lambda: decode_flow_record('flow_binding',b'1.2'))

    def test_duplicate_binding_identity_is_not_deduplicated(self):
        snapshot = FlowSnapshot('option-flow-canonical1',(self.binding,self.binding),
                                (),(),(),(),(),(),(),())
        self.error('identity_conflict', lambda: flow_validate_snapshot(snapshot))

    def test_empty_snapshot_and_cursor_bounds(self):
        snapshot = FlowSnapshot('option-flow-canonical1',(),(),(),(),(),(),(),(),())
        flow_validate_snapshot(snapshot)
        self.error('invalid_scalar', lambda: flow_canonical_bytes(FlowCursor('s',2**63)))

    def test_numeric_token_reports_the_scalar_pointer(self):
        # The digest is deliberately wrong; scalar admission must happen first.
        wire=(b'{"content_sha256":"'+b'a'*64+b'","payload":{"max_position":1.5,'
              b'"stream_id":"s"},"record_type":"flow_cursor","schema_version":"option-flow-json1"}')
        error=self.error('type_mismatch',lambda:decode_flow_record('flow_cursor',wire))
        self.assertEqual(error.path,'/payload/max_position')


if __name__ == '__main__':
    unittest.main()
