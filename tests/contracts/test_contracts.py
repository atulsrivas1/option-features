"""Authored independent contract probes; not executed during EQ142 hold."""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import hashlib
import unittest
from unittest.mock import patch

from option_feature_contracts import (
    InputBinding, Snapshot, ModelFact, R25_LIMITS, ContractValidationError,
    canonical_bytes, content_digest, record_digest, to_payload, from_payload,
    validate_snapshot, validate_limits, decimal_text,
)

def binding():
    return InputBinding("b", "synthetic", "1", "0" * 64, "synthetic", "original fixture")

def snapshot(bindings=()):
    return Snapshot("option-canonical1", bindings, (), (), (), (), (), (), (), (), (), None)

class ContractTests(unittest.TestCase):
    def test_empty_snapshot_golden_bytes_are_hand_written(self):
        expected = b'{"activity_window":null,"bindings":[],"civil_bindings":[],"coverage_certificates":[],"definitions":[],"model_facts":[],"quote_coverage_windows":[],"quotes":[],"schema_version":"option-canonical1","spots":[],"supplied_metrics":[],"trades":[]}'
        self.assertEqual(canonical_bytes(snapshot()), expected)
        self.assertEqual(content_digest("snapshot", snapshot()), hashlib.sha256(b"option-json1\nsnapshot\n" + expected).hexdigest())

    def test_record_and_envelope_domains_differ(self):
        value = binding()
        self.assertNotEqual(record_digest("input_binding", value), content_digest("input_binding", value))

    def test_record_is_frozen(self):
        with self.assertRaises(FrozenInstanceError):
            binding().binding_id = "changed"

    def test_identical_duplicate_binding_is_rejected_atomically(self):
        with self.assertRaises(ContractValidationError) as caught:
            validate_snapshot(snapshot((binding(), binding())))
        self.assertEqual(caught.exception.code, "duplicate_identity")

    def test_raise_limit_and_boolean_limit_rejected(self):
        for bad in (replace(R25_LIMITS, max_wire_bytes=16777217), replace(R25_LIMITS, max_wire_bytes=True)):
            with self.assertRaises(ContractValidationError):
                validate_limits(bad)

    def test_decimal_representation_independent_of_context(self):
        from decimal import localcontext
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(decimal_text(Decimal("12345.67000")), "12345.67")
            self.assertEqual(decimal_text(Decimal("-0.00")), "0")

    def test_decimal_structural_and_wire_limits_intersection(self):
        # 1E1024 satisfies exponent bounds but expands to 1025 wire characters.
        with self.assertRaises(ContractValidationError) as caught:
            decimal_text(Decimal("1E1024"))
        self.assertEqual(caught.exception.code, "admission_limit_exceeded")
        self.assertEqual(len(decimal_text(Decimal("1E1023"))), 1024)

    def test_roundtrip_is_typed_and_unknown_field_rejected(self):
        value = snapshot((binding(),))
        payload = to_payload(value)
        self.assertEqual(from_payload("snapshot", payload), value)
        payload["unknown"] = None
        with self.assertRaises(ContractValidationError) as caught:
            from_payload("snapshot", payload)
        self.assertEqual(caught.exception.code, "unknown_field")

    def test_scalar_bound_precedes_unicode_encoding(self):
        bad = replace(binding(), rights_reference="x" * 1025)
        with self.assertRaises(ContractValidationError):
            canonical_bytes(bad)

    def test_surrogate_is_rejected(self):
        with self.assertRaises(ContractValidationError):
            canonical_bytes(replace(binding(), rights_reference="\ud800"))

    def test_exact_byte_ceiling(self):
        value = snapshot()
        size = len(canonical_bytes(value))
        self.assertEqual(len(canonical_bytes(value, replace(R25_LIMITS, max_wire_bytes=size))), size)
        with self.assertRaises(ContractValidationError):
            canonical_bytes(value, replace(R25_LIMITS, max_wire_bytes=size-1))

    def test_raw_aggregate_snapshot_count_fails_before_typed_expansion(self):
        payload = to_payload(snapshot())
        payload["bindings"] = [{}, {}]
        payload["spots"] = [{}, {}]
        with patch("option_feature_contracts.canonical._decode", side_effect=AssertionError("typed expansion attempted")):
            with self.assertRaises(ContractValidationError) as caught:
                from_payload("snapshot", payload, replace(R25_LIMITS, max_snapshot_records=3))
        self.assertEqual(caught.exception.code, "admission_limit_exceeded")

    def test_raw_reference_count_fails_before_typed_expansion(self):
        payload = to_payload(snapshot())
        payload["quote_coverage_windows"] = [{"expected_sample_ids": ["a", "b", "c"]}]
        with patch("option_feature_contracts.canonical._decode", side_effect=AssertionError("typed expansion attempted")):
            with self.assertRaises(ContractValidationError) as caught:
                from_payload("snapshot", payload, replace(R25_LIMITS, max_snapshot_records=3))
        self.assertEqual(caught.exception.code, "admission_limit_exceeded")

    def test_rate_carry_contract_scope_rejected_direct_and_wire(self):
        for kind in ("rate", "carry"):
            valid = ModelFact("u", None, kind, 0.0, "option-bsm1", "USD", "basis", 0, None, 0, "1", "b")
            with self.assertRaises(ContractValidationError) as direct:
                canonical_bytes(replace(valid, contract_id="c"))
            self.assertEqual(direct.exception.code, "invalid_config")
            payload = to_payload(valid)
            payload["contract_id"] = "c"
            with self.assertRaises(ContractValidationError) as wire:
                from_payload("model_fact", payload)
            self.assertEqual(wire.exception.code, "invalid_config")

if __name__ == "__main__":
    unittest.main()
