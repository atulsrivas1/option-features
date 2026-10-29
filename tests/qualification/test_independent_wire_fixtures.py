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
from option_feature_contracts import from_payload, ContractValidationError
from option_features import evaluate

REQUIRED_FAMILIES = frozenset({"interior", "terminal", "zero_volatility", "time", "iv_bounds", "conditioning", "units", "readiness", "profile", "quotes"})

# P1 (PO-P1-02) supersedes two frozen R25 results for liquidity.spread_bps. The frozen fixture file is
# not edited; the consumer asserts the P1 status and reason for these ids instead.
P1_SUPERSEDED = {
    "quote-locked": {"status": "invalid_input", "reason": "locked_market", "quality_flags": ("locked_market",)},
    "quote-zero": {"status": "invalid_input", "reason": "nonpositive_bid", "quality_flags": ("nonpositive_bid", "zero_midpoint")},
}

class IndependentWireFixtures(unittest.TestCase):
    def assert_coverage(self, result, expected):
        if expected is None:
            self.assertIsNone(result.coverage)
            return
        fields = {"observed", "expected", "population_id", "population_complete", "sampling"}
        self.assertEqual(set(expected), fields)
        self.assertIsNotNone(result.coverage)
        self.assertEqual({name: getattr(result.coverage, name) for name in fields}, expected)

    def assert_convergence_criteria(self, result, request):
        evidence = result.solver_evidence
        self.assertIsNotNone(evidence)
        self.assertTrue(evidence.converged)
        sigma = Fraction.from_float(result.value)
        price_tol = Fraction.from_float(request.solver.price_abs_tol)+Fraction.from_float(request.solver.price_rel_tol)*abs(Fraction(evidence.target_price_exact))
        vol_tol = Fraction.from_float(request.solver.vol_abs_tol)+Fraction.from_float(request.solver.vol_rel_tol)*abs(sigma)
        self.assertIsNotNone(evidence.worst_case_price_residual)
        self.assertLessEqual(Fraction(evidence.worst_case_price_residual), price_tol)
        self.assertLessEqual(Fraction.from_float(evidence.sigma_high)-Fraction.from_float(evidence.sigma_low), vol_tol)
        self.assertLessEqual(evidence.sigma_low, result.value)
        self.assertGreaterEqual(evidence.sigma_high, result.value)

    def assert_solver(self, result, wanted, request):
        assertions = wanted["solver_assertions"]
        allowed = {"presence", "if_present", "boundary", "converged", "iterations", "target_price_exact", "vega", "oracle_vega", "oracle_vega_interval", "admissible_candidate_sigma_interval", "ill_conditioned", "require_sigma_contains_oracle", "require_both_convergence_criteria"}
        self.assertFalse(set(assertions)-allowed, "unknown solver assertion")
        presence = assertions["presence"]
        self.assertIn(presence, {"required", "absent", "not_fixed_by_contract"})
        evidence = result.solver_evidence
        if presence == "absent":
            self.assertIsNone(evidence)
            self.assertEqual(set(assertions), {"presence"})
            return
        if presence == "required":
            self.assertIsNotNone(evidence)
        if evidence is None:
            # Known target/boundary details constrain evidence if it exists;
            # they do not strengthen an explicitly unfixed presence policy.
            return
        constraints = dict(assertions.get("if_present", {}))
        self.assertFalse(set(constraints)-(allowed-{"presence", "if_present"}), "unknown conditional solver assertion")
        constraints.update({key: value for key, value in assertions.items() if key not in {"presence", "if_present"}})
        for name in ("boundary", "iterations", "converged", "ill_conditioned"):
            if name in constraints:
                if name in {"converged", "ill_conditioned"}:
                    self.assertIs(getattr(evidence, name), constraints[name], name)
                else:
                    self.assertEqual(getattr(evidence, name), constraints[name], name)
        if "target_price_exact" in constraints:
            self.assertEqual(evidence.target_price_exact, Decimal(constraints["target_price_exact"]))
        if "vega" in constraints:
            if constraints["vega"] is None:
                self.assertIsNone(evidence.vega)
            else:
                self.assertIsNotNone(evidence.vega)
                self.assertEqual(Fraction.from_float(evidence.vega), Fraction(Decimal(str(constraints["vega"]))))
        if "oracle_vega_interval" in constraints:
            interval = constraints["oracle_vega_interval"]
            self.assertEqual(set(interval), {"low", "high", "uncertainty_kind", "relative_padding"})
            self.assertEqual(interval["uncertainty_kind"], "empirical_two_precision_plus_outward_relative_padding")
            self.assertEqual(Fraction(Decimal(interval["relative_padding"])), Fraction(1, 10**58))
            low, high = Fraction(Decimal(interval["low"])), Fraction(Decimal(interval["high"]))
            self.assertGreaterEqual(low, 0)
            self.assertGreaterEqual(high, low)
            self.assertIsNotNone(evidence.vega)
            self.assertGreaterEqual(Fraction.from_float(evidence.vega), low)
            self.assertLessEqual(Fraction.from_float(evidence.vega), high)
        elif "oracle_vega" in constraints:
            self.assertIsNotNone(evidence.vega)
            reference = Fraction(Decimal(constraints["oracle_vega"]))
            relative, absolute = Fraction(Decimal(wanted["relative_tolerance"])), Fraction(Decimal(wanted["absolute_tolerance"]))
            self.assertTrue(0 <= relative <= Fraction(1, 10**10))
            self.assertTrue(0 <= absolute <= Fraction(1, 10**10))
            self.assertLessEqual(abs(Fraction.from_float(evidence.vega)-reference), absolute+relative*abs(reference))
        if "admissible_candidate_sigma_interval" in constraints:
            interval = constraints["admissible_candidate_sigma_interval"]
            self.assertEqual(set(interval), {"low", "high"})
            low, high = Fraction(Decimal(interval["low"])), Fraction(Decimal(interval["high"]))
            self.assertGreaterEqual(low, 0)
            self.assertGreaterEqual(high, low)
            self.assertIsNotNone(result.value)
            self.assertGreaterEqual(Fraction.from_float(result.value), low)
            self.assertLessEqual(Fraction.from_float(result.value), high)
        if constraints.get("require_sigma_contains_oracle"):
            reference = Fraction(Decimal(wanted["oracle_decimal"]))
            self.assertLessEqual(Fraction.from_float(evidence.sigma_low), reference)
            self.assertGreaterEqual(Fraction.from_float(evidence.sigma_high), reference)
        if constraints.get("require_both_convergence_criteria"):
            self.assert_convergence_criteria(result, request)

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
        exception_cases = artifact["exception_cases"]
        canonical_cases = json.dumps({"cases": cases, "exception_cases": exception_cases}, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.assertEqual(hashlib.sha256(canonical_cases).hexdigest(), artifact["cases_sha256"])
        self.assertRegex(artifact["external_review_receipt_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(cases)
        identifiers = [case["id"] for case in cases+exception_cases]
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
                    override = P1_SUPERSEDED.get(case["id"]) if wanted["output_id"] == "liquidity.spread_bps" else None
                    for name in ("output_id", "contract_id", "underlying_id", "status", "reason", "unit", "origin", "model_id", "formula_version", "producer_model_id", "producer_formula_id"):
                        self.assertEqual(getattr(result, name), override[name] if override and name in override else wanted[name], name)
                    self.assertEqual(result.quality_flags, override["quality_flags"] if override else tuple(wanted["quality_flags"]))
                    self.assertEqual(result.dependency_binding_ids, tuple(wanted["dependency_binding_ids"]))
                    self.assertEqual(result.dependency_record_sha256s, tuple(wanted["dependency_record_sha256s"]))
                    self.assert_coverage(result, wanted["coverage"])
                    self.assert_solver(result, wanted, request)
                    if override:
                        self.assertIsNone(result.value)
                        continue
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
                        self.assert_convergence_criteria(result, request)
                        self.assertLessEqual(Fraction.from_float(evidence.sigma_low), reference)
                        self.assertGreaterEqual(Fraction.from_float(evidence.sigma_high), reference)
        self.assertTrue(exception_cases, "required independent structural cases are missing")
        for case in exception_cases:
            with self.subTest(exception_case=case["id"]):
                self.assertEqual(case["expected_exception"], "ContractValidationError")
                self.assertIn(case["reason_assertion"], {"class_only", "exact_reason"})
                with self.assertRaises(ContractValidationError) as caught:
                    snapshot = from_payload("snapshot", case["snapshot_payload"])
                    request = from_payload("request", case["request_payload"])
                    evaluate(snapshot, request)
                if case["reason_assertion"] == "exact_reason":
                    self.assertIsInstance(case["expected_reason"], str)
                    self.assertEqual(caught.exception.code, case["expected_reason"])
                else:
                    self.assertIsNone(case["expected_reason"])

if __name__ == "__main__":
    unittest.main()
