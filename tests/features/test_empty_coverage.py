"""Complete empty populations preserve evidence; unknown completeness does not."""
from dataclasses import replace
import unittest
from option_feature_contracts import CoverageCertificate, QuoteCoverageWindow, ActivityWindow
from option_features import evaluate
from test_features import snapshot, request

class EmptyCoverageTests(unittest.TestCase):
    def test_complete_empty_quote_plan_retains_zero_over_zero_coverage(self):
        window = QuoteCoverageWindow("c", 0, -10, 0, (), "declared-empty-plan", "samples", "b")
        certificate = CoverageCertificate("samples", "quote_samples", ("c",), -10, 0, 0, True, "b")
        value = snapshot(quote_coverage_windows=(window,), coverage_certificates=(certificate,))
        result, = evaluate(value, request("quality.quote_coverage"))
        self.assertEqual((result.status, result.reason, result.value), ("undefined", "empty_sampling_plan", None))
        self.assertEqual((result.coverage.observed, result.coverage.expected, result.coverage.population_id, result.coverage.population_complete, result.coverage.sampling), (0, 0, "declared-empty-plan", True, "event_count"))
        cases = (
            (replace(value, coverage_certificates=()), "completeness_unknown"),
            (replace(value, coverage_certificates=(replace(certificate, complete=False),)), "incomplete_source"),
            (replace(value, coverage_certificates=(replace(certificate, known_at_ns=1),)), "future_known"),
            (replace(value, quote_coverage_windows=(replace(window, known_at_ns=1),)), "future_known"),
        )
        for unknown, reason in cases:
            with self.subTest(reason=reason):
                output, = evaluate(unknown, request("quality.quote_coverage"))
                self.assertEqual((output.status, output.reason), ("ineligible_input", reason))
                self.assertIsNone(output.coverage)

    def test_complete_empty_activity_retains_zero_over_zero_coverage(self):
        window = ActivityWindow("declared-empty-population", "u", (), 0, -10, 0, (), "synthetic-regular1", "trades", "quotes", "b")
        certificates = (CoverageCertificate("trades", "trade_events", (), -10, 0, 0, True, "b"), CoverageCertificate("quotes", "current_quotes", (), 0, 0, 0, True, "b"))
        value = snapshot(definitions=(), spots=(), model_facts=(), activity_window=window, coverage_certificates=certificates)
        config = request("chain.activity", contract_ids=())
        result, = evaluate(value, config)
        self.assertEqual((result.status, result.reason, result.value), ("undefined", "empty_population", None))
        self.assertEqual((result.coverage.observed, result.coverage.expected, result.coverage.population_id, result.coverage.population_complete, result.coverage.sampling), (0, 0, "declared-empty-population", True, "population_member"))
        cases = (
            (replace(value, coverage_certificates=certificates[1:]), "completeness_unknown"),
            (replace(value, coverage_certificates=(replace(certificates[0], complete=False), certificates[1])), "incomplete_source"),
            (replace(value, coverage_certificates=(replace(certificates[0], known_at_ns=1), certificates[1])), "future_known"),
            (replace(value, activity_window=replace(window, known_at_ns=1)), "future_known"),
        )
        for unknown, reason in cases:
            with self.subTest(reason=reason):
                output, = evaluate(unknown, config)
                self.assertEqual((output.status, output.reason), ("ineligible_input", reason))
                self.assertIsNone(output.coverage)

    def test_missing_plan_or_population_never_fabricates_empty_coverage(self):
        quote, = evaluate(snapshot(), request("quality.quote_coverage"))
        activity, = evaluate(snapshot(), request("chain.activity", contract_ids=()))
        self.assertEqual((quote.status, quote.reason), ("missing_input", "missing_sampling_plan"))
        self.assertEqual((activity.status, activity.reason), ("missing_input", "missing_population"))
        self.assertIsNone(quote.coverage)
        self.assertIsNone(activity.coverage)

if __name__ == "__main__":
    unittest.main()
