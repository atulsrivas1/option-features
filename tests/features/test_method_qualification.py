"""Independent rational witnesses and bounded control-flow qualification.

Rational series below do not import production maths or an oracle dependency.
Synthetic inverse collaborators test decisions only, not BSM accuracy.
"""
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction as Q
from functools import lru_cache
from math import isqrt
import builtins
import threading
import unittest
from unittest.mock import patch

from option_feature_contracts import PriceEnclosure, SolverConfig
from option_features import arithmetic as a, inverse, model


def dyadic(bound):
    mantissa, exponent = map(int, bound.man_exp())
    return Q(mantissa * 2**exponent) if exponent >= 0 else Q(mantissa, 2**-exponent)


def sqrt_bounds(value, digits=740):
    """Integer floor square root proves both endpoints, without libm."""
    scale = 10**digits
    root = isqrt(value.numerator * scale**2 // value.denominator)
    lo, hi = Q(root, scale), Q(root+1, scale)
    assert lo*lo <= value <= hi*hi
    return lo, hi


def alternating_atan(x, terms):
    partial = sum(((-1)**k*x**(2*k+1)/ (2*k+1) for k in range(terms)), Q(0))
    other = partial + (-1)**terms*x**(2*terms+1)/(2*terms+1)
    return min(partial, other), max(partial, other)


@lru_cache(maxsize=1)
def witnesses():
    # exp(1/3): positive Taylor series; tail <= first omitted term/(1-x).
    x, term, partial = Q(1, 3), Q(1), Q(1)
    for k in range(1, 450):
        term *= x/k
        partial += term
    exponential = partial, partial + term*x/450/(1-x)
    # log(3/2)=2*atanh(1/5); positive geometric majorant for tail.
    z, count = Q(1, 5), 540
    partial = 2*sum((z**(2*k+1)/(2*k+1) for k in range(count)), Q(0))
    logarithm = partial, partial + 2*z**(2*count+1)/((2*count+1)*(1-z*z))
    # Machin identity pi=16 atan(1/5)-4 atan(1/239); alternating tails.
    p, q = alternating_atan(Q(1, 5), 540), alternating_atan(Q(1, 239), 170)
    pi = 16*p[0]-4*q[1], 16*p[1]-4*q[0]
    sqrt_pi_lo = sqrt_bounds(pi[0])[0]
    sqrt_pi_hi = sqrt_bounds(pi[1])[1]
    def erfc_witness(x, count):
        # Integrate the exp(-t*t) series exactly. Early terms can grow for
        # x=8, but from the truncation onward the alternating tail decreases.
        term = partial = x
        for k in range(1, count):
            term *= -x*x*(2*k-1)/(k*(2*k+1))
            partial += term
        assert x*x < count
        other = partial + term*(-x*x)*(2*count-1)/(count*(2*count+1))
        integral_lo, integral_hi = min(partial, other), max(partial, other)
        return 1-2*integral_hi/sqrt_pi_lo, 1-2*integral_lo/sqrt_pi_hi
    return {"exp": exponential, "log": logarithm, "sqrt": sqrt_bounds(Q(2)),
            "erfc": erfc_witness(Q(1, 2), 400), "erfc_tail": erfc_witness(Q(8), 1500)}


class IndependentRationalWitnessTests(unittest.TestCase):
    def test_nontrivial_transcendentals_through_all_inclusion_layers(self):
        references = witnesses()
        with a.numerical_owner() as owner:
            arb, fmpq, ctx = owner
            for bits in a.TIERS:
                ctx.prec = bits
                expressions = {
                    "exp": a.ball_rational(Q(1, 3), arb, fmpq).exp(),
                    "log": a.ball_rational(Q(3, 2), arb, fmpq).log(),
                    "sqrt": arb(2).sqrt(), "erfc": a.ball_rational(Q(1, 2), arb, fmpq).erfc(),
                    "erfc_tail": arb(8).erfc(),
                }
                for name, ball in expressions.items():
                    with self.subTest(bits=bits, operation=name):
                        lo, hi = references[name]
                        self.assertLess(hi-lo, Q(1, 10**700))
                        raw_lo, raw_hi = dyadic(ball.lower()), dyadic(ball.upper())
                        # Witness is narrower than even 2048-bit native error.
                        # Both independent rational endpoints must be enclosed.
                        self.assertLessEqual(raw_lo, lo)
                        self.assertGreaterEqual(raw_hi, hi)
                        stored = a.enclosure(ball)
                        self.assertLessEqual(Q(stored.value_low), raw_lo)
                        self.assertGreaterEqual(Q(stored.value_high), raw_hi)
                        self.assertLessEqual(Q(stored.value_low), lo)
                        self.assertGreaterEqual(Q(stored.value_high), hi)
                        for endpoint in (stored.value_low, stored.value_high):
                            self.assertLessEqual(len(endpoint.as_tuple().digits), 128)
                            self.assertLessEqual(abs(endpoint.as_tuple().exponent), 1024)

    def test_rational_conversion_and_exact_endpoint_export_each_tier(self):
        with a.numerical_owner() as owner:
            arb, fmpq, ctx = owner
            for bits in a.TIERS:
                ctx.prec = bits
                for value in (Q(1, 3), Q(-17, 19), Q(10**80+1, 97), Q(1, 10**300)):
                    ball = a.ball_rational(value, arb, fmpq)
                    low, high = dyadic(ball.lower()), dyadic(ball.upper())
                    self.assertLessEqual(low, value)
                    self.assertGreaterEqual(high, value)
                    self.assertLessEqual(Q(a.dyadic_endpoint(ball.lower(), False)), low)
                    self.assertGreaterEqual(Q(a.dyadic_endpoint(ball.upper(), True)), high)

    def test_complementary_backend_identities_are_separate_from_witnesses(self):
        with a.numerical_owner() as (arb, fmpq, ctx):
            for bits in a.TIERS:
                ctx.prec = bits
                for value in (Q(1, 2), Q(8), Q(-8)):
                    x = a.ball_rational(value, arb, fmpq)
                    for residual in (x.erfc()+(-x).erfc()-2, x.exp()*(-x).exp()-1):
                        self.assertLessEqual(dyadic(residual.lower()), 0)
                        self.assertGreaterEqual(dyadic(residual.upper()), 0)

    def test_actual_bsm_parity_equal_gamma_vega_and_monotonicity(self):
        operands = model.Operands(Q(103), Q(97), Q(-1, 32), Q(1, 64), Q(7, 13), Q(3, 8), 1)
        with a.numerical_owner() as owner:
            arb, fmpq, ctx = owner
            for bits in a.TIERS:
                ctx.prec = bits
                put = replace(operands, eta=-1)
                call_price = model.equation(operands, "pricing.price", owner)
                put_price = model.equation(put, "pricing.price", owner)
                S, K, r, q, T = (a.ball_rational(v, arb, fmpq) for v in (operands.spot, operands.strike, operands.rate, operands.carry, operands.time))
                residual = call_price-put_price-(S*(-q*T).exp()-K*(-r*T).exp())
                self.assertLessEqual(dyadic(residual.lower()), 0)
                self.assertGreaterEqual(dyadic(residual.upper()), 0)
                for output in ("greeks.gamma", "greeks.vega"):
                    residual = model.equation(operands, output, owner)-model.equation(put, output, owner)
                    self.assertLessEqual(dyadic(residual.lower()), 0)
                    self.assertGreaterEqual(dyadic(residual.upper()), 0)
                larger = model.equation(replace(operands, sigma=Q(1, 2)), "pricing.price", owner)
                self.assertGreater(dyadic(larger.lower()), dyadic(call_price.upper()))


class ContextOwnershipTests(unittest.TestCase):
    def test_backend_import_failure_releases_ownership_and_lock(self):
        original_import = builtins.__import__
        def fail_backend(name, *args, **kwargs):
            if name == "flint":
                raise ImportError("injected native backend import failure")
            return original_import(name, *args, **kwargs)
        with patch.object(builtins, "__import__", side_effect=fail_backend):
            with self.assertRaisesRegex(ImportError, "injected"):
                with a.numerical_owner():
                    self.fail("import failure yielded owner")
        self.assertFalse(getattr(a._LOCAL, "active", False))
        with a.numerical_owner() as owner:
            self.assertEqual(owner[2].threads, 1)

    def test_context_restored_after_normal_body_and_each_failure_stage(self):
        from flint import ctx
        ambient = ctx.prec, ctx.threads
        try:
            for stage in ("normal", "body", "equation", "export"):
                with self.subTest(stage=stage):
                    # A non-default supported prior setting makes both pinning
                    # and restoration observable. No native work runs while
                    # this isolated test seeds the saved context under the lock.
                    with a._LOCK:
                        ctx.prec, ctx.threads = 96, 2
                    try:
                        with a.numerical_owner() as owner:
                            owner[2].prec = 512
                            self.assertEqual(owner[2].threads, 1)
                            if stage == "body":
                                raise ValueError("injected body failure")
                            if stage == "equation":
                                model.equation(model.Operands(Q(1), Q(1), Q(513), Q(0), Q(1), Q(1), 1), "pricing.price", owner)
                            if stage == "export":
                                a.enclosure(owner[0]((1, 5000)))
                    except (ValueError, a.NumericalFailure):
                        self.assertNotEqual(stage, "normal")
                    else:
                        self.assertEqual(stage, "normal")
                    self.assertEqual((ctx.prec, ctx.threads), (96, 2))
                    self.assertFalse(getattr(a._LOCAL, "active", False))
        finally:
            # Assertions and injected exceptions must not leak test settings.
            with a._LOCK:
                ctx.prec, ctx.threads = ambient

    def test_reentrancy_rejected_and_subsequent_owner_succeeds(self):
        with a.numerical_owner():
            with self.assertRaisesRegex(RuntimeError, "reentrant"):
                with a.numerical_owner():
                    self.fail("nested owner admitted")
        with a.numerical_owner() as owner:
            self.assertEqual(owner[2].threads, 1)

    def test_two_actual_threads_serialize_numerical_context(self):
        from flint import ctx
        previous = ctx.prec, ctx.threads
        attempted, entered, finished = threading.Event(), threading.Event(), threading.Event()
        errors = []
        def second():
            attempted.set()
            try:
                with a.numerical_owner() as owner:
                    entered.set()
                    owner[2].prec = 256
            except BaseException as exc:
                errors.append(exc)
            finally:
                finished.set()
        with a.numerical_owner() as owner:
            owner[2].prec = 128
            worker = threading.Thread(target=second, daemon=True)
            worker.start()
            self.assertTrue(attempted.wait(5))
            self.assertFalse(entered.wait(0.05))
            self.assertEqual(owner[2].prec, 128)
        self.assertTrue(finished.wait(5))
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertFalse(errors)
        self.assertTrue(entered.is_set())
        self.assertEqual((ctx.prec, ctx.threads), previous)


class ControlledInverseDecisionTests(unittest.TestCase):
    """Literal monotone synthetic prices exercise finite decisions, never BSM."""
    def setUp(self):
        self.operands = model.Operands(Q(1), Q(1), Q(0), Q(0), Q(1), Q(1), 1)
        self.config = SolverConfig("bisection1", "midpoint", 2.0, 3, 1e-10, 1e-10, 1e-10, 1e-10)
        self.zero = self.interval(Q(0))
        self.ten = self.interval(Q(10))

    @staticmethod
    def interval(value, radius=Q(0)):
        return PriceEnclosure("option-arb-bsm1", "1", a.exact_decimal(value-radius), a.exact_decimal(value+radius))

    def run_synthetic(self, price, config=None, midpoint=None):
        calls = []
        def interval(operands, owner, bits):
            calls.append((operands.sigma, bits))
            return price(operands.sigma)
        with patch.object(inverse, "bounds", return_value=(self.zero, self.ten, Q(0), Q(10))), patch.object(inverse, "price_interval", side_effect=interval):
            if midpoint is None:
                result = inverse.solve(self.operands, Q(1), config or self.config, None, None)
            else:
                with patch.object(inverse, "nearest_binary64", side_effect=midpoint):
                    result = inverse.solve(self.operands, Q(1), config or self.config, None, None)
        self.assertLessEqual(len(calls), 15*((config or self.config).max_iterations+2))
        return result, calls

    def test_exact_midpoint_overlap_rescues_and_retains_wide_bracket(self):
        result, calls = self.run_synthetic(self.interval)
        self.assertEqual((result.status, result.reason), ("iteration_limit", "iteration_budget"))
        self.assertEqual(result.evidence.iterations, 3)
        self.assertLess(result.evidence.sigma_low, 1)
        self.assertGreater(result.evidence.sigma_high, 1)
        self.assertFalse(result.evidence.converged)
        self.assertEqual([bits for sigma, bits in calls if sigma == 1][:5], list(a.TIERS))
        self.assertIn((Q(1, 2), 128), calls)
        self.assertIn((Q(3, 2), 128), calls)

    def test_cap_overlap_refines_five_tiers_and_never_claims_exact_root(self):
        result, calls = self.run_synthetic(lambda sigma: self.interval(Q(1), Q(1, 100)))
        self.assertEqual((result.status, result.reason), ("numerical_failure", "bound_precision"))
        self.assertEqual(calls, [(Q(2), bits) for bits in a.TIERS])
        self.assertEqual(result.evidence.iterations, 0)

    def test_cap_strictly_below_target_is_bracket_exceeded(self):
        result, calls = self.run_synthetic(lambda sigma: self.interval(Q(1, 2)))
        self.assertEqual((result.status, result.reason), ("bracket_exceeded", "sigma_cap"))
        self.assertEqual(calls, [(Q(2), 128)])
        self.assertEqual(result.evidence.iterations, 0)

    def test_all_forward_tiers_failure_is_bounded_and_explicit(self):
        def failure(sigma):
            raise a.NumericalFailure()
        result, calls = self.run_synthetic(failure)
        self.assertEqual((result.status, result.reason), ("numerical_failure", "precision_exhausted"))
        self.assertEqual(calls, [(Q(2), bits) for bits in a.TIERS])

    def test_uncertain_economic_bound_never_reaches_price_solver(self):
        with patch.object(inverse, "bounds", return_value=(self.interval(Q(1), Q(1, 10)), self.ten, None, Q(10))) as bounds, patch.object(inverse, "price_interval") as price:
            result = inverse.solve(self.operands, Q(1), self.config, None, None)
        self.assertEqual((result.status, result.reason), ("numerical_failure", "bound_precision"))
        self.assertEqual([call.args[-1] for call in bounds.call_args_list], list(a.TIERS))
        price.assert_not_called()

    def test_unresolved_rescue_does_not_discard_unknown_side(self):
        result, calls = self.run_synthetic(lambda sigma: self.interval(Q(2)) if sigma == 2 else self.interval(Q(1), Q(1, 100)))
        self.assertEqual((result.status, result.reason), ("numerical_failure", "bound_precision"))
        self.assertEqual((result.evidence.sigma_low, result.evidence.sigma_high), (0, 2))
        self.assertEqual(len(calls), 16)

    def test_representable_stagnation_refuses_invented_width_collapse(self):
        # Explicit collaborator forces rounded midpoint onto lo; logic-only.
        result, _ = self.run_synthetic(self.interval, midpoint=lambda value: float(value) if value >= 1 else 0.0)
        # Real first midpoint is an exact root and rescue contracts; next left
        # probe is forced onto lo, so no representable progress is certified.
        self.assertEqual((result.status, result.reason), ("numerical_failure", "precision_exhausted"))
        self.assertFalse(result.evidence.converged)

    def test_small_price_residual_cannot_waive_width(self):
        result, _ = self.run_synthetic(self.interval, replace(self.config, max_iterations=1))
        self.assertEqual(result.status, "iteration_limit")
        self.assertEqual(result.evidence.candidate_price_enclosure.value_low, Decimal(1))
        self.assertGreater(result.evidence.sigma_high-result.evidence.sigma_low, 0.9)


if __name__ == "__main__":
    unittest.main()

