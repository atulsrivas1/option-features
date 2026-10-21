"""Assertion-engine probes; orchestration fakes are not numerical evidence."""
from decimal import Decimal
from types import SimpleNamespace
import unittest
from option_feature_contracts import Coverage
import test_independent_wire_fixtures as fixture_consumer

class ConsumerAssertionTests(unittest.TestCase):
    def setUp(self):
        self.checker = fixture_consumer.IndependentWireFixtures()

    def test_complete_coverage_and_null_are_checked(self):
        expected = dict(observed=1, expected=4, population_id="declared", population_complete=True, sampling="event_count")
        result = SimpleNamespace(coverage=Coverage(**expected))
        self.checker.assert_coverage(result, expected)
        with self.assertRaises(AssertionError):
            self.checker.assert_coverage(result, None)
        with self.assertRaises(AssertionError):
            self.checker.assert_coverage(result, dict(expected, observed=0))
        self.checker.assert_coverage(SimpleNamespace(coverage=None), None)

    def test_solver_presence_variants_and_conditional_fields(self):
        empty = SimpleNamespace(solver_evidence=None)
        self.checker.assert_solver(empty, {"solver_assertions": {"presence": "absent"}}, None)
        self.checker.assert_solver(empty, {"solver_assertions": {"presence": "not_fixed_by_contract", "if_present": {"converged": False}}}, None)
        self.checker.assert_solver(empty, {"solver_assertions": {"presence": "not_fixed_by_contract", "target_price_exact": "10", "if_present": {"converged": False}}}, None)
        with self.assertRaises(AssertionError):
            self.checker.assert_solver(empty, {"solver_assertions": {"presence": "required"}}, None)
        actual = SimpleNamespace(solver_evidence=SimpleNamespace(converged=True))
        with self.assertRaises(AssertionError):
            self.checker.assert_solver(actual, {"solver_assertions": {"presence": "not_fixed_by_contract", "if_present": {"converged": False}}}, None)

    def test_independently_fixed_lower_evidence_fields_are_checked(self):
        evidence = SimpleNamespace(boundary="lower_boundary", iterations=0, converged=True, target_price_exact=Decimal("10"), vega=0.0, ill_conditioned=True)
        actual = SimpleNamespace(solver_evidence=evidence)
        assertions = dict(presence="required", boundary="lower_boundary", iterations=0, converged=True, target_price_exact="10", vega="0", ill_conditioned=True)
        self.checker.assert_solver(actual, {"solver_assertions": assertions}, None)
        for name, wrong in (("iterations", 1), ("boundary", "none"), ("target_price_exact", "11"), ("vega", "1"), ("ill_conditioned", False)):
            with self.subTest(field=name), self.assertRaises(AssertionError):
                self.checker.assert_solver(actual, {"solver_assertions": dict(assertions, **{name: wrong})}, None)

    def test_candidate_small_residual_cannot_hide_wide_bracket(self):
        actual = SimpleNamespace(value=0.0, solver_evidence=SimpleNamespace(converged=True, target_price_exact=Decimal("10"), worst_case_price_residual=Decimal("0"), sigma_low=0.0, sigma_high=1.0))
        request = SimpleNamespace(solver=SimpleNamespace(price_abs_tol=1e-10, price_rel_tol=1e-10, vol_abs_tol=1e-10, vol_rel_tol=1e-10))
        with self.assertRaises(AssertionError):
            self.checker.assert_convergence_criteria(actual, request)

    def test_candidate_vega_interval_checks_membership_without_point_substitution(self):
        # Synthetic dyadic values probe only consumer assertion semantics;
        # these are not numerical expectations for a production option case.
        interval = {"low": "0.5", "high": "1.5", "uncertainty_kind": "empirical_two_precision_plus_outward_relative_padding", "relative_padding": "1e-58"}
        wanted = {"solver_assertions": {"presence": "required", "oracle_vega": "1", "oracle_vega_interval": interval}}
        self.checker.assert_solver(SimpleNamespace(solver_evidence=SimpleNamespace(vega=1.25)), wanted, None)
        for invalid in (0.25, 1.75, None):
            with self.subTest(vega=invalid), self.assertRaises(AssertionError):
                self.checker.assert_solver(SimpleNamespace(solver_evidence=SimpleNamespace(vega=invalid)), wanted, None)
        for low, high in (("-0.5", "1.5"), ("1.5", "0.5")):
            invalid = {"solver_assertions": {"presence": "required", "oracle_vega_interval": dict(interval, low=low, high=high)}}
            with self.subTest(low=low, high=high), self.assertRaises(AssertionError):
                self.checker.assert_solver(SimpleNamespace(solver_evidence=SimpleNamespace(vega=1.0)), invalid, None)
        for field, wrong in (("uncertainty_kind", "rigorous_enclosure"), ("relative_padding", "1e-57")):
            invalid = {"solver_assertions": {"presence": "required", "oracle_vega_interval": dict(interval, **{field: wrong})}}
            with self.subTest(field=field), self.assertRaises(AssertionError):
                self.checker.assert_solver(SimpleNamespace(solver_evidence=SimpleNamespace(vega=1.0)), invalid, None)

    def test_admissible_candidate_sigma_interval_checks_independent_domain(self):
        wanted = {"solver_assertions": {"presence": "required", "admissible_candidate_sigma_interval": {"low": "0.5", "high": "1.5"}}}
        self.checker.assert_solver(SimpleNamespace(value=1.25, solver_evidence=SimpleNamespace()), wanted, None)
        for invalid in (0.25, 1.75, None):
            with self.subTest(value=invalid), self.assertRaises(AssertionError):
                self.checker.assert_solver(SimpleNamespace(value=invalid, solver_evidence=SimpleNamespace()), wanted, None)
        for low, high in (("-0.5", "1.5"), ("1.5", "0.5")):
            invalid = {"solver_assertions": {"presence": "required", "admissible_candidate_sigma_interval": {"low": low, "high": high}}}
            with self.subTest(low=low, high=high), self.assertRaises(AssertionError):
                self.checker.assert_solver(SimpleNamespace(value=1.0, solver_evidence=SimpleNamespace()), invalid, None)

    def test_point_vega_fallback_keeps_frozen_tolerance(self):
        wanted = {"solver_assertions": {"presence": "required", "oracle_vega": "1"}, "relative_tolerance": "1e-10", "absolute_tolerance": "0"}
        self.checker.assert_solver(SimpleNamespace(solver_evidence=SimpleNamespace(vega=1.0)), wanted, None)
        with self.assertRaises(AssertionError):
            self.checker.assert_solver(SimpleNamespace(solver_evidence=SimpleNamespace(vega=1.25)), wanted, None)

if __name__ == "__main__":
    unittest.main()
