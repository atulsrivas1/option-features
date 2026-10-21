"""Mandatory acceptance gate; missing independent fixture artifact is a failure.

This suite consumes evidence authored and reviewed independently of production.
It never creates expectations from production. Run separately from unit probes.
"""
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import unittest
from option_feature_contracts import from_payload
from option_features import evaluate

REQUIRED_FAMILIES = frozenset({"interior", "terminal", "zero_volatility", "time", "iv_bounds", "conditioning", "units", "readiness", "profile", "quotes"})

class IndependentWireFixtures(unittest.TestCase):
    def test_independently_reviewed_exact_wire_fixture_artifact(self):
        source_path = os.environ.get("R25_INDEPENDENT_WIRE_FIXTURES")
        digest = os.environ.get("R25_INDEPENDENT_WIRE_FIXTURES_SHA256", "")
        self.assertTrue(source_path, "required independent wire fixture artifact is missing; no acceptance can be inferred")
        self.assertRegex(digest, r"^[0-9a-f]{64}$", "independently recorded artifact SHA256 required")
        data = Path(source_path).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
        artifact = json.loads(data)
        self.assertEqual(artifact["schema_version"], "r25-independent-wire-fixtures1")
        self.assertEqual(artifact["state"], "independently_reviewed_wire_fixture_candidate")
        self.assertNotEqual(artifact["author"], "/root/r25_library_implementation")
        self.assertNotEqual(artifact["reviewer"], artifact["author"])
        self.assertNotEqual(artifact["reviewer"], "/root/r25_library_implementation")
        self.assertFalse(artifact["production_imports"])
        self.assertEqual(artifact["dependency"], "mpmath==1.3.0")
        self.assertEqual(artifact["precision_decimal_digits"], [80, 140])
        self.assertRegex(artifact["generator_source_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(artifact["reviewed_source_commit"], r"^[0-9a-f]{40}$")
        cases = artifact["cases"]
        self.assertTrue(cases)
        identifiers = [case["id"] for case in cases]
        self.assertEqual(len(set(identifiers)), len(identifiers))
        covered = {family for case in cases for family in case["families"]}
        self.assertTrue(REQUIRED_FAMILIES <= covered, "missing independently instantiated normative numerical fixture families")
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(case["operand_domain"], "exact_wire_decimal_and_binary64_ratios")
                snapshot = from_payload("snapshot", case["snapshot_payload"])
                request = from_payload("request", case["request_payload"])
                actual = evaluate(snapshot, request)
                expected = case["expected"]
                self.assertEqual(len(actual), len(expected))
                for result, wanted in zip(actual, expected):
                    for name in ("output_id", "contract_id", "underlying_id", "status", "reason", "unit", "origin", "model_id", "formula_version", "producer_model_id", "producer_formula_id"):
                        self.assertEqual(getattr(result, name), wanted[name], name)
                    self.assertEqual(result.quality_flags, tuple(wanted["quality_flags"]))
                    self.assertEqual(result.dependency_binding_ids, tuple(wanted["dependency_binding_ids"]))
                    self.assertEqual(result.dependency_record_sha256s, tuple(wanted["dependency_record_sha256s"]))
                    if result.status != "available":
                        self.assertIsNone(result.value)
                        self.assertIsNone(wanted["oracle_decimal"])
                        continue
                    reference = Fraction(Decimal(wanted["oracle_decimal"]))
                    relative = Fraction(Decimal(wanted["relative_tolerance"]))
                    absolute = Fraction(Decimal(wanted["absolute_tolerance"]))
                    self.assertGreaterEqual(relative, 0)
                    self.assertGreaterEqual(absolute, 0)
                    self.assertLessEqual(relative, Fraction(1, 10**10), "exceeds frozen relative regression maximum")
                    self.assertLessEqual(absolute, Fraction(1, 10**10), "exceeds frozen absolute regression maximum")
                    if reference != 0:
                        self.assertLess(absolute + relative*abs(reference), abs(reference), "fixture tolerance cannot admit zero for a nonzero tail")
                    self.assertLessEqual(abs(Fraction.from_float(result.value)-reference), absolute+relative*abs(reference))
                    if wanted.get("require_pricing_enclosure"):
                        self.assertIsNotNone(result.pricing_evidence)
                        lower = Fraction(result.pricing_evidence.value_low)
                        upper = Fraction(result.pricing_evidence.value_high)
                        oracle_uncertainty = Fraction(Decimal(wanted["oracle_uncertainty"]))
                        self.assertGreaterEqual(oracle_uncertainty, 0)
                        # Empirical oracle-band overlap is consistency only,
                        # not rigorous inclusion proof of the true value.
                        self.assertLessEqual(lower, reference+oracle_uncertainty)
                        self.assertGreaterEqual(upper, reference-oracle_uncertainty)
                    if result.output_id == "volatility.implied_volatility" and result.origin == "computed":
                        evidence = result.solver_evidence
                        self.assertIsNotNone(evidence)
                        self.assertTrue(evidence.converged)
                        self.assertLessEqual(Fraction.from_float(evidence.sigma_low), reference)
                        self.assertGreaterEqual(Fraction.from_float(evidence.sigma_high), reference)
                        sigma = Fraction.from_float(result.value)
                        price_tol = Fraction.from_float(request.solver.price_abs_tol)+Fraction.from_float(request.solver.price_rel_tol)*abs(Fraction(evidence.target_price_exact))
                        vol_tol = Fraction.from_float(request.solver.vol_abs_tol)+Fraction.from_float(request.solver.vol_rel_tol)*abs(sigma)
                        self.assertLessEqual(Fraction(evidence.worst_case_price_residual), price_tol)
                        self.assertLessEqual(Fraction.from_float(evidence.sigma_high)-Fraction.from_float(evidence.sigma_low), vol_tol)

if __name__ == "__main__":
    unittest.main()
