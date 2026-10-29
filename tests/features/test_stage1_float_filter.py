"""M1 Stage 1 tests (Developer-authored; the independent Tester authors and runs its own checks).

Failing-first: these fail on origin/main (no option_features.floatfilter, no float_filter switch).
"""
import random
import sys
import unittest
from dataclasses import fields, is_dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from option_feature_contracts import SolverConfig, ConvertedOperands
from option_features import inverse, floatfilter, model
from option_features.arithmetic import numerical_owner, decimal_exact, nearest_binary64
from option_features.model import Operands

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "qualification" / "synthetic" / "perf"), str(ROOT / "tools")]
import gen_m1_solver_sets as gen  # noqa: E402
import m1_adversarial_sets as adv  # noqa: E402
from m1_filter_hooks import test_hooks  # noqa: E402

CFG = SolverConfig("bisection1", "midpoint", 8.0, 256, 1e-10, 1e-10, 1e-10, 1e-10)


def canon(o):
    if is_dataclass(o):
        return tuple((f.name, canon(getattr(o, f.name))) for f in fields(o))
    if isinstance(o, float):
        return o.hex()
    if isinstance(o, (tuple, list)):
        return tuple(canon(x) for x in o)
    if type(o).__name__ in ("arb", "acb"):
        return (type(o).__name__, o.str(radius=True, more=True))
    return (type(o).__name__, str(o)) if isinstance(o, (Decimal, Fraction)) else o


def prepared(c):
    S, K = decimal_exact(Decimal(c["spot"])), decimal_exact(Decimal(c["strike"]))
    rate, carry = Fraction.from_float(float(c["rate"])), Fraction.from_float(float(c["div"]))
    T = Fraction(c["T"]) if "T" in c else Fraction(c["t_days"], 365)
    ops = Operands(S, K, rate, carry, T, Fraction(0), 1 if c["right"] == "C" else -1)
    conv = ConvertedOperands(float(S), float(K), float(rate), float(carry), None, c["t_days"], nearest_binary64(T))
    return ops, decimal_exact(Decimal(c["price"])), conv


def solve(p, **kw):
    with numerical_owner() as owner:
        return canon(inverse.solve(p[0], p[1], CFG, p[2], owner, **kw))


def sample():
    out = [gen.contract(gen.DEFAULT_SEED, k, i) for k in ("flat", "mixed") for i in range(60)]
    return out + adv.adversarial(240)[::2] + adv.mutation_ties(40)


class Stage1Tests(unittest.TestCase):
    def test_filter_equals_certified_on_every_field(self):
        used = 0
        for c in sample():
            p = prepared(c)
            self.assertEqual(solve(p), solve(p, float_filter=False), c)
            used += floatfilter.make(p[0], p[1], CFG) is not None
        self.assertGreater(used, 150)

    def test_switch_false_never_uses_the_filter(self):
        calls = []
        real = floatfilter.make
        floatfilter.make = lambda *a: calls.append(1) or real(*a)
        try:
            p = prepared(gen.contract(gen.DEFAULT_SEED, "flat", 3))
            solve(p, float_filter=False)
            self.assertEqual(calls, [])
            solve(p)
            self.assertEqual(calls, [1])
        finally:
            floatfilter.make = real

    def test_filter_reduces_enclosure_calls_and_switch_restores_them(self):
        n = [0]
        real = model.equation
        model.equation = lambda *a, **k: n.__setitem__(0, n[0] + 1) or real(*a, **k)
        try:
            ps = [prepared(gen.contract(gen.DEFAULT_SEED, "flat", i)) for i in range(15)]
            for p in ps:
                solve(p, float_filter=False)
            certified = n[0]
            n[0] = 0
            for p in ps:
                solve(p)
            self.assertLess(n[0] * 2, certified)
        finally:
            model.equation = real

    def test_midpoint_matches_fraction_path(self):
        g = random.Random(7)
        for _ in range(20000):
            lo = g.choice((0.0, g.uniform(0, 8), g.uniform(0, 1e-3), g.uniform(0, 1e-200)))
            hi = lo + g.choice((g.uniform(0, 8), g.uniform(0, 1e-9), 2.0 ** -g.randint(1, 60), 5e-324 * g.randint(1, 9)))
            if not hi > lo:
                continue
            ref = nearest_binary64((Fraction.from_float(lo) + Fraction.from_float(hi)) / 2)
            self.assertEqual(inverse._midpoint(lo, hi).hex(), ref.hex(), (lo, hi))

    def test_domain_gates_disable_the_filter(self):
        for c in adv.domain(10):
            p = prepared(c)
            self.assertIsNone(floatfilter.make(p[0], p[1], CFG), c)
        ok = prepared(gen.contract(gen.DEFAULT_SEED, "flat", 1))
        self.assertIsNotNone(floatfilter.make(ok[0], ok[1], CFG))
        big = SolverConfig("bisection1", "midpoint", 500.0, 256, 1e-10, 1e-10, 1e-10, 1e-10)
        self.assertIsNone(floatfilter.make(ok[0], ok[1], big))
        o = ok[0]
        self.assertIsNone(floatfilter.make(Operands(o.spot, o.strike, o.rate, o.carry, Fraction(0), Fraction(0), 1), ok[1], CFG))

    def test_float_error_is_below_the_proven_worst_case_and_sign_matches_certified(self):
        g = random.Random(11)
        checked = 0
        with numerical_owner() as owner:
            for c in g.sample(sample(), 150):
                ops, target, conv = prepared(c)
                ff = floatfilter.make(ops, target, CFG)
                if ff is None:
                    continue
                for _ in range(6):
                    sigma = g.choice((g.uniform(0.01, 1.0), g.uniform(1.0, 8.0), 8.0 * g.randrange(1, 4096) / 4096))
                    ev = ff._eval(sigma)
                    if ev is None:
                        continue
                    sf = Fraction.from_float(sigma)
                    enc = model.price_interval(Operands(ops.spot, ops.strike, ops.rate, ops.carry, ops.time, sf, ops.eta, {}), owner, 512)
                    exact = (decimal_exact(enc.value_low) + decimal_exact(enc.value_high)) / 2
                    err = abs(Fraction(ev[0]) - exact)
                    self.assertLessEqual(err, Fraction(floatfilter.W_COEFF * floatfilter.U * ev[1]), (c, sigma))
                    sgn, _ = ff.sign(sigma)
                    if sgn:
                        self.assertEqual(sgn, -1 if exact < target else 1, (c, sigma))
                    checked += 1
        self.assertGreater(checked, 300)

    def test_shrunk_bound_mutation_is_detected_and_control_is_clean(self):
        ties = [prepared(c) for c in adv.mutation_ties(60)]
        ref = [solve(p, float_filter=False) for p in ties]
        with test_hooks(bound_divisor=1, inject=5.0):
            self.assertEqual([solve(p) for p in ties], ref)           # control: zero differences
        with test_hooks(bound_divisor=1, inject=30.0):
            self.assertEqual([solve(p) for p in ties], ref)           # headroom: 6x the proven worst case
        with test_hooks(bound_divisor=10, inject=5.0):
            mutant = [solve(p) for p in ties]
        self.assertTrue(any(a != b for a, b in zip(mutant, ref)), "shrunk-bound mutation NOT detected: the build must fail")
        self.assertIs(floatfilter.make, floatfilter.make)

    def test_no_mutable_hook_state_in_the_shipped_module(self):
        self.assertFalse(hasattr(floatfilter, "_TEST") or hasattr(floatfilter, "test_hooks"))
        with test_hooks(bound_divisor=10, inject=5):
            pass
        self.assertEqual(floatfilter.make.__module__, floatfilter.__name__)   # wrapper removed after the block

    def test_deferred_enclosure_failure_reruns_certified(self):
        # if the deferred candidate enclosure cannot be computed, the solve reruns fully certified
        p = prepared(gen.contract(gen.DEFAULT_SEED, "mixed", 5))
        ref = solve(p, float_filter=False)
        real = inverse._price
        state = {"deferred": False}

        def flaky(operands, sigma_f, target, owner):
            if state["deferred"] and state.get("armed"):
                raise inverse.NumericalFailure("injected")
            return real(operands, sigma_f, target, owner)
        orig_solve = inverse._solve

        def spy(*a):
            if a[-1] and not state.get("armed"):
                state["armed"] = True
                inverse._price = flaky
                state["deferred"] = True
                try:
                    return orig_solve(*a)
                finally:
                    inverse._price = real
            return orig_solve(*a)
        inverse._solve = spy
        try:
            got = solve(p)
        finally:
            inverse._solve, inverse._price = orig_solve, real
        self.assertEqual(got, ref)


if __name__ == "__main__":
    unittest.main()
