"""Independently hand-derived synthetic probes; authored, not yet executed."""
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
import math
import unittest
from unittest.mock import patch

from option_feature_contracts import (
    InputBinding, CivilDateBinding, Definition, Spot, ModelFact, Quote,
    SuppliedMetric, Snapshot, Eligibility, SolverConfig, Request, R25_LIMITS,
    CoverageCertificate, QuoteCoverageWindow, Trade, ActivityWindow,
    ContractValidationError,
)
from option_features import evaluate

YEAR_NS = 31536000000000000

def definition(contract_id="c", **changes):
    value = Definition(contract_id, "u", "call", Decimal("100"), "USD", Decimal("10"), "scalar_underlying", "basis", "european", "certified_vanilla_continuous_carry", "cash", YEAR_NS, YEAR_NS, YEAR_NS, 719528, "UTC", "civil", "1", -1, None, 0, "b")
    return replace(value, **changes)

def snapshot(**changes):
    value = Snapshot(
        "option-canonical1", (InputBinding("b", "synthetic-original", "1", "0"*64, "synthetic", "original synthetic fixtures"),),
        (CivilDateBinding("civil", 0, 719163, "UTC", 0, "b"), CivilDateBinding("civil", YEAR_NS, 719528, "UTC", 0, "b")),
        (definition(),), (Spot("u", Decimal("100"), "USD", "basis", 0, 0, "1", "b"),),
        tuple(ModelFact("u", None, kind, value, "option-bsm1", "USD", "basis", -1, None, 0, "1", "b") for kind, value in (("rate", 0.0), ("carry", 0.0), ("volatility", 2.0))),
        (), (), (), (), (), None,
    )
    return replace(value, **changes)

def request(*outputs, **changes):
    return replace(Request("option-request1", ("c",), outputs, "computed_only", "exact_only", 0, 0, 719163, "civil", "option-bsm1", "r25-formulas1", Eligibility(YEAR_NS, YEAR_NS, YEAR_NS), SolverConfig("bisection1", "midpoint", 8.0, 256, 1e-10, 1e-10, 1e-10, 1e-10), R25_LIMITS), **changes)

def quote(bid="1", ask="3", **changes):
    return replace(Quote("c", None, Decimal(bid) if bid is not None else None, Decimal(ask) if ask is not None else None, "USD", "per_underlying_payoff_unit", 0, 0, 0, "1", "b"), **changes)

class ReferenceTests(unittest.TestCase):
    def test_reference_independent_of_missing_model_facts(self):
        results = evaluate(snapshot(model_facts=()), request("contract.dte", "contract.multiplier", "contract.moneyness"))
        self.assertEqual(tuple(r.value for r in results), (365.0, 10.0, 1.0))
        self.assertTrue(all(r.status == "available" for r in results))

    def test_quote_locked_crossed_zero_and_spread(self):
        # P1 (PO-P1-02) supersedes the R25 results for a locked quote (was available 0.0) and for bid 0
        # (was undefined zero_midpoint): spread outputs now give locked_market and nonpositive_bid.
        cases = (("2", "2", "invalid_input", "locked_market", None), ("1", "3", "available", "ok", 10000.0), ("3", "1", "invalid_input", "crossed_quote", None), ("0", "0", "invalid_input", "nonpositive_bid", None))
        for bid, ask, status, reason, value in cases:
            with self.subTest(bid=bid, ask=ask):
                result, = evaluate(snapshot(quotes=(quote(bid, ask),)), request("liquidity.spread_bps"))
                self.assertEqual((result.status, result.reason, result.value), (status, reason, value))

    def test_future_definition_never_replaces_causal_revision(self):
        old = definition(multiplier=Decimal("10"))
        future = replace(old, revision_id="2", known_at_ns=1, multiplier=Decimal("20"))
        base, = evaluate(snapshot(definitions=(old,)), request("contract.multiplier"))
        actual, = evaluate(snapshot(definitions=(future, old)), request("contract.multiplier"))
        self.assertEqual(actual.value, 10.0)
        self.assertEqual(actual.dependency_record_sha256s, base.dependency_record_sha256s)
        self.assertNotEqual(actual.snapshot_sha256, base.snapshot_sha256)

    def test_winning_revision_tie_is_atomic(self):
        with self.assertRaises(ContractValidationError) as caught:
            evaluate(snapshot(definitions=(definition(), definition(revision_id="2"))), request("contract.multiplier"))
        self.assertEqual(caught.exception.code, "ambiguous_revision")

    def test_quote_slot_count_has_known_denominator(self):
        cert = CoverageCertificate("cert", "quote_samples", ("c",), -4, 1, 0, True, "b")
        window = QuoteCoverageWindow("c", 0, -4, 1, ("s0", "s1", "s2", "s3"), "sampling", "cert", "b")
        quotes = tuple(quote(sample_id=sample, event_ns=-3+i, sequence=i) for i, sample in enumerate(("s0", "s2", "s3")))
        result, = evaluate(snapshot(quotes=quotes, coverage_certificates=(cert,), quote_coverage_windows=(window,)), request("quality.quote_coverage"))
        self.assertEqual(result.value, 0.75)
        self.assertEqual((result.coverage.observed, result.coverage.expected), (3, 4))
        self.assertIn("partial_quote_coverage", result.quality_flags)

    def test_breadth_is_percentage_of_population_not_trade_count(self):
        ids = ("c", "c2", "c3", "c4")
        certs = (CoverageCertificate("trades", "trade_events", ids, -10, 0, 0, True, "b"), CoverageCertificate("quotes", "current_quotes", ids, 0, 0, 0, True, "b"))
        activity = ActivityWindow("population", "u", ids, 0, -10, 0, ("t1", "t2"), "synthetic-regular1", "trades", "quotes", "b")
        trades = (Trade("t1", "c", Decimal("1"), "contracts", "regular", -2, 0, "1", "b"), Trade("t2", "c", Decimal("2"), "contracts", "regular", -1, 0, "1", "b"))
        result, = evaluate(snapshot(definitions=tuple(definition(c) for c in ids), quotes=tuple(quote(contract_id=c) for c in ids), trades=trades, coverage_certificates=certs, activity_window=activity), request("chain.activity", contract_ids=()))
        self.assertEqual(result.value, 25.0)
        self.assertEqual((result.coverage.observed, result.coverage.expected), (1, 4))

    def test_supplied_abs_projection_preserves_parent_model(self):
        metric = SuppliedMetric("c", "greeks.signed_delta", -0.6, "signed_delta", "synthetic-producer1", "producer-formula1", 0, 0, "1", "b")
        result, = evaluate(snapshot(model_facts=(), spots=(), supplied_metrics=(metric,)), request("greeks.delta", origin_policy="supplied_only", supplied_delta_policy="absolute_from_signed"))
        self.assertEqual((result.value, result.origin, result.model_id, result.formula_version), (0.6, "computed", "synthetic-producer1", "option-absolute-delta1"))

class EndpointTests(unittest.TestCase):
    def test_terminal_payoff_and_known_zeroes_do_not_require_carry_certification(self):
        source = snapshot(definitions=(definition(fixing_ns=0, payment_ns=0, model_profile_admission="unknown"),), spots=(Spot("u", Decimal("110"), "USD", "basis", 0, 0, "1", "b"),), model_facts=())
        results = evaluate(source, request("pricing.price", "greeks.delta", "greeks.gamma", "greeks.vega", "greeks.rho"))
        self.assertEqual(tuple(r.value for r in results), (10.0, 1.0, 0.0, 0.0, 0.0))
        self.assertTrue(all(r.status == "available" for r in results))

    def test_terminal_all_branches_do_not_import_native_backend(self):
        import builtins
        original_import = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name == "flint" or name.startswith("flint."):
                raise AssertionError("terminal evaluation imported native backend")
            return original_import(name, *args, **kwargs)
        outputs = ("pricing.price", "greeks.delta", "greeks.signed_delta", "greeks.gamma", "greeks.vega", "greeks.rho", "greeks.theta", "volatility.implied_volatility")
        for side in ("call", "put"):
            for S in ("90", "100", "110"):
                for sigma in (0.0, 0.25):
                    source = snapshot(definitions=(definition(right=side, fixing_ns=0, payment_ns=0),), spots=(Spot("u", Decimal(S), "USD", "basis", 0, 0, "1", "b"),))
                    source = replace(source, model_facts=tuple(replace(f, value=sigma) if f.kind == "volatility" else f for f in source.model_facts))
                    with patch("builtins.__import__", guarded):
                        results = evaluate(source, request(*outputs))
                    eta = 1 if side == "call" else -1
                    payoff = max(eta*(int(S)-100), 0)
                    self.assertEqual(results[0].value, float(payoff))
                    self.assertEqual(results[4].value, 0.0)
                    self.assertEqual(results[5].value, 0.0)
                    self.assertEqual(results[-1].reason, "terminal_price")
                    if S == "100":
                        self.assertEqual(results[1].reason, "nondifferentiable_payoff")
                        self.assertEqual(results[3].reason, "nondifferentiable_payoff")
                        self.assertEqual(results[6].reason, "nonfinite_terminal_time_derivative" if sigma > 0 else "ok")
                    else:
                        self.assertEqual(results[2].value, float(eta if payoff else 0))
                        self.assertEqual(results[3].value, 0.0)
                        self.assertEqual(results[6].value, 0.0)

    def test_valid_extremal_clock_difference_is_per_output_precision_failure(self):
        low, high = -(2**63), 2**63-1
        source = snapshot(definitions=(definition(fixing_ns=high, payment_ns=high, effective_from_ns=low, known_at_ns=low),), spots=(Spot("u", Decimal("100"), "USD", "basis", low, low, "1", "b"),))
        source = replace(source, model_facts=tuple(replace(f, effective_from_ns=low, known_at_ns=low) for f in source.model_facts))
        result, = evaluate(source, request("pricing.price", valuation_ns=low, knowledge_cutoff_ns=low))
        self.assertEqual((result.status, result.reason, result.converted_operands), ("numerical_failure", "precision_exhausted", None))

    def test_terminal_call_payoff_and_independent_greek_zeroes(self):
        definition0 = definition(fixing_ns=0, payment_ns=0, expiry_ordinal=719163)
        value = snapshot(definitions=(definition0,), spots=(Spot("u", Decimal("110"), "USD", "basis", 0, 0, "1", "b"),), model_facts=())
        results = evaluate(value, request("pricing.price", "greeks.delta", "greeks.gamma", "greeks.vega", "greeks.rho", "volatility.implied_volatility"))
        self.assertEqual(tuple(r.value for r in results), (10.0, 1.0, 0.0, 0.0, 0.0, None))
        self.assertEqual(results[-1].reason, "terminal_price")

    def test_terminal_zeroes_need_no_spot_or_model_facts(self):
        results = evaluate(snapshot(definitions=(definition(fixing_ns=0, payment_ns=0),), spots=(), model_facts=()), request("greeks.vega", "greeks.rho"))
        self.assertEqual(tuple(r.value for r in results), (0.0, 0.0))

class NumericalTests(unittest.TestCase):
    def test_both_rights_exact_itm_lower_root_has_zero_vega_and_conditioning(self):
        # At r=q0,T1,sigma0 an ITM payoff is locally unchanged by sigma:
        # right-sigma Vega0. Positive tolerances therefore satisfy the frozen
        # conditioning inequality exactly, for either option right.
        for side, spot_value in (("call", "110"), ("put", "90")):
            with self.subTest(right=side):
                source = snapshot(definitions=(definition(right=side),), spots=(Spot("u", Decimal(spot_value), "USD", "basis", 0, 0, "1", "b"),), quotes=(quote("10", "10"),))
                source = replace(source, model_facts=tuple(f for f in source.model_facts if f.kind != "volatility"))
                result, = evaluate(source, request("volatility.implied_volatility"))
                self.assertEqual((result.status, result.reason, result.value), ("available", "ok", 0.0))
                self.assertEqual(result.quality_flags, ("ill_conditioned", "lower_boundary"))
                evidence = result.solver_evidence
                self.assertEqual((evidence.vega, evidence.ill_conditioned), (0.0, True))
                self.assertEqual((evidence.boundary, evidence.converged, evidence.iterations), ("lower_boundary", True, 0))
                self.assertEqual((evidence.sigma_low, evidence.sigma_high), (0.0, 0.0))
                self.assertEqual((evidence.target_price_exact, evidence.worst_case_price_residual), (Decimal("10"), Decimal("0")))

    def test_zero_volatility_symbolic_kinks_and_one_sided_vega(self):
        outputs = ("pricing.price", "greeks.signed_delta", "greeks.gamma", "greeks.vega", "greeks.rho", "greeks.theta")
        for side in ("call", "put"):
            for spot_value in ("90", "100", "110"):
                source = snapshot(definitions=(definition(right=side),), spots=(Spot("u", Decimal(spot_value), "USD", "basis", 0, 0, "1", "b"),))
                source = replace(source, model_facts=tuple(replace(f, value=0.0) if f.kind == "volatility" else f for f in source.model_facts))
                results = evaluate(source, request(*outputs))
                eta = 1 if side == "call" else -1
                itm = eta*(int(spot_value)-100) > 0
                self.assertEqual(results[0].value, float(max(eta*(int(spot_value)-100), 0)))
                if spot_value == "100":
                    for index in (1, 2, 4):
                        self.assertEqual(results[index].reason, "nondifferentiable_zero_volatility")
                    self.assertAlmostEqual(results[3].value, 100/math.sqrt(2*math.pi), delta=1e-10)
                    self.assertEqual(results[5].value, 0.0)
                else:
                    self.assertEqual(results[1].value, float(eta if itm else 0))
                    self.assertEqual(results[2].value, 0.0)
                    self.assertEqual(results[3].value, 0.0)
                    self.assertEqual(results[4].value, float(eta*100 if itm else 0))
                    self.assertEqual(results[5].value, 0.0)

    def test_terminal_directional_theta_uses_exact_dyadic_rates(self):
        for side, expected in (("call", -12.5), ("put", 0.0)):
            source = snapshot(definitions=(definition(right=side, fixing_ns=0, payment_ns=0),))
            source = replace(source, model_facts=tuple(replace(f, value={"rate": 0.25, "carry": 0.125, "volatility": 0.0}[f.kind]) for f in source.model_facts))
            result, = evaluate(source, request("greeks.theta"))
            self.assertEqual((result.status, result.value), ("available", expected))

    def test_unknown_specific_sigma_cannot_hide_causal_flat_sigma(self):
        baseline = snapshot()
        future = replace(next(f for f in baseline.model_facts if f.kind == "volatility"), contract_id="c", revision_id="future", known_at_ns=1, value=3.0)
        result, = evaluate(replace(baseline, model_facts=baseline.model_facts+(future,)), request("pricing.price"))
        original, = evaluate(baseline, request("pricing.price"))
        self.assertEqual(result.value, original.value)
        self.assertEqual(result.dependency_record_sha256s, original.dependency_record_sha256s)

    def test_invalid_specific_sigma_never_falls_back_to_flat_sigma(self):
        baseline = snapshot()
        invalid = replace(next(f for f in baseline.model_facts if f.kind == "volatility"), contract_id="c", value=-1.0)
        result, = evaluate(replace(baseline, model_facts=baseline.model_facts+(invalid,)), request("pricing.price"))
        self.assertEqual((result.status, result.reason), ("invalid_input", "negative_volatility"))

    def test_smooth_put_against_original_normal_symmetry_derivation(self):
        # S=K100,r=q0,sigma2,T1 => d1=1,d2=-1.
        # This binary64 independent erfc probe complements the mandatory
        # separately generated80/140digit oracle; it does not replace that gate.
        results = evaluate(snapshot(definitions=(definition(right="put"),)), request("pricing.price", "greeks.signed_delta", "greeks.delta", "greeks.gamma"))
        phi1 = math.exp(-0.5)/math.sqrt(2*math.pi)
        Phi1 = math.erfc(-1/math.sqrt(2))/2
        expected = (100*(2*Phi1-1), Phi1-1, 1-Phi1, phi1/200)
        for result, reference in zip(results, expected):
            self.assertEqual(result.status, "available")
            self.assertAlmostEqual(result.value, reference, delta=1e-10+1e-10*abs(reference))

    def test_exact_lower_bound_asymptote_and_invalid_price(self):
        for price, status, reason, expected in (("10", "available", "ok", 0.0), ("9", "invalid_input", "price_out_of_bounds", None), ("100", "nonidentifiable_inverse", "upper_asymptote", None)):
            result, = evaluate(snapshot(definitions=(definition(right="put"),), spots=(Spot("u", Decimal("90"), "USD", "basis", 0, 0, "1", "b"),), quotes=(quote(price, price),), model_facts=tuple(f for f in snapshot().model_facts if f.kind != "volatility")), request("volatility.implied_volatility"))
            self.assertEqual((result.status, result.reason, result.value), (status, reason, expected))

    def test_context_restored_after_exception_and_reentrant_rejected(self):
        from flint import ctx
        from option_features.arithmetic import numerical_owner
        original = ctx.prec, ctx.threads
        with self.assertRaises(RuntimeError):
            with numerical_owner() as (_, _, context):
                context.prec = 256
                with numerical_owner():
                    pass
        self.assertEqual((ctx.prec, ctx.threads), original)

if __name__ == "__main__":
    unittest.main()
