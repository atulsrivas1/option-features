"""M1 Stage 1: option plumbing and the libm-perturbation test (Developer-authored; PO ruling on acceptance test 3).

The independent Tester's own scripts are the authority; this is the Developer's own version of the method.
"""
import hashlib
import math
import random
import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from flint import arb, fmpq, ctx
from option_feature_contracts import SolverConfig
from option_features import evaluate, evaluator, floatfilter as ff, inverse, model
from option_features.arithmetic import numerical_owner, decimal_exact
from option_features.model import Operands

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "tests" / "features")]
from m1_filter_hooks import test_hooks  # noqa: E402
from test_stage1_float_filter import canon  # noqa: E402
import test_features as tf  # noqa: E402

CFG = SolverConfig("bisection1", "midpoint", 8.0, 256, 1e-10, 1e-10, 1e-10, 1e-10)


class PlumbingTests(unittest.TestCase):
    def test_float_filter_option_reaches_solve_and_off_restores_base_arb_counts(self):
        src = tf.snapshot(quotes=(tf.quote("7.9656", "7.9656"),))
        src = replace(src, model_facts=tuple(f for f in src.model_facts if f.kind != "volatility"))
        req = tf.request("volatility.implied_volatility")
        seen, n = [], [0]
        real_solve, real_eq = evaluator.solve, model.equation

        def spy(*a, **k):
            seen.append(k.get("float_filter"))
            return real_solve(*a, **k)
        evaluator.solve = spy
        model.equation = lambda *a, **k: n.__setitem__(0, n[0] + 1) or real_eq(*a, **k)
        try:
            on = evaluate(src, req)
            n_on, n[0] = n[0], 0
            off = evaluate(src, req, float_filter=False)
            n_off = n[0]
            n[0] = 0
            # base arb count: the same solve with the switch off called directly (the certified path)
            with numerical_owner() as owner:
                ops = Operands(Fraction(100), Fraction(100), Fraction(0), Fraction(0), Fraction(1), Fraction(0), 1)
                real_solve(ops, decimal_exact(Decimal("7.9656")), req.solver, None, owner, float_filter=False)
            n_direct = n[0]
        finally:
            evaluator.solve, model.equation = real_solve, real_eq
        self.assertEqual(seen, [True, False])
        self.assertEqual(on, off)                       # identical result bytes
        self.assertEqual(on[0].status, "available")
        self.assertLess(n_on * 2, n_off)                # filter on: far fewer certified evaluations
        self.assertEqual(n_off, n_direct)               # off: exactly the certified solve's evaluation count (evaluator adds none)


class LibmPerturbationTests(unittest.TestCase):
    """exp, log, erfc perturbed by relative s*2^-40 with deterministic hashed sign and per-contract salt; ties are
    built so the PERTURBED float gap is 1.001*E(divisor). Shipped bound clean at s in {1, 8, 64}; bound/10 at s=16
    and bound/100 at s=1 must produce byte differences or the build fails."""
    real = (ff.exp, ff.log, ff.erfc)
    salt = [0]

    @classmethod
    def perturb(cls, s):
        def wrap(fn, kind):
            def f(x):
                h = hashlib.md5(("%d%s%s" % (cls.salt[0], kind, float(x).hex())).encode()).digest()[0] & 1
                return fn(x) * (1 + (1 if h else -1) * s * ff.U)
            return f
        ff.exp, ff.log, ff.erfc = wrap(cls.real[0], "x"), wrap(cls.real[1], "l"), wrap(cls.real[2], "e")

    @classmethod
    def restore(cls):
        ff.exp, ff.log, ff.erfc = cls.real

    @staticmethod
    def exact(S, K, T, r, q, sig, eta):
        ctx.prec = 400
        f = lambda fr: arb(fmpq(fr.numerator, fr.denominator))
        Sa, Ka, Ta = f(S), f(K), f(T)
        ra, qa, sa = f(Fraction.from_float(r)), f(Fraction.from_float(q)), f(Fraction.from_float(sig))
        vs = sa * Ta.sqrt()
        d1 = ((Sa / Ka).log() + (ra - qa + sa * sa / 2) * Ta) / vs
        d2 = d1 - vs
        A, B = Sa * (-qa * Ta).exp(), Ka * (-ra * Ta).exp()
        cdf = lambda x: (-x / arb(2).sqrt()).erfc() / 2
        v = A * cdf(d1) - B * cdf(d2) if eta == 1 else B * cdf(-d2) - A * cdf(-d1)
        man, ex = v.mid().man_exp()
        return Fraction(int(man) * (1 << int(ex))) if int(ex) >= 0 else Fraction(int(man), 1 << -int(ex))

    def build(self, div, s, n, need_err):
        g = random.Random(1000 + int(div) * 7 + int(s))
        out, tries = [], 0
        while len(out) < n and tries < 6000:
            tries += 1
            S = Fraction(g.randint(100, 100000), 100)
            K = max(Fraction(1, 100), Fraction(int(float(S) * math.exp(g.choice((-1, 1)) * g.uniform(0.5, 3)) * 100), 100))
            T = Fraction(g.randint(1, 300), 10 ** g.choice((4, 5, 6)))
            r, q, eta = g.choice((0.0, 0.02, -0.03, 0.2)), g.choice((0.0, 0.01, 0.1)), g.choice((1, -1))
            j = g.randint(1, 8)
            sig = 8.0 * (2 * g.randrange(2 ** j) + 1) / 2 ** (j + 1)
            ops = Operands(S, K, Fraction.from_float(r), Fraction.from_float(q), T, Fraction(0), eta)
            p = self.exact(S, K, T, r, q, sig, eta)
            if float(p) < 1e-6:
                continue
            best = None
            self.perturb(s)
            try:
                for sl in range(96):
                    self.salt[0] = sl
                    f = ff.make(ops, Fraction(1), CFG)
                    ev = f._eval(sig) if f else None
                    if ev is None:
                        best = None
                        break
                    e_units = (ev[0] - float(p)) / (ff.U * ev[1])
                    if best is None or abs(e_units) > abs(best[2]):
                        best = (ev[0], ev[1], e_units, sl)
            finally:
                self.restore()
            if best is None:
                continue
            pf, sc, err, sl = best
            if need_err and abs(err) < 1.01 * ff.C_BOUND / div:
                continue
            E = ff.C_BOUND * ff.U * sc / div
            t = decimal_exact(Decimal(format(pf - (1 if err >= 0 else -1) * 1.001 * E, ".17g")))
            if t > 0:
                out.append((ops, t, sl))
        return out

    def run_set(self, contracts, div, s):
        diffs = 0
        for ops, t, sl in contracts:
            with numerical_owner() as owner:
                ref = canon(inverse.solve(ops, t, CFG, None, owner, float_filter=False))
            self.perturb(s)
            self.salt[0] = sl
            try:
                with test_hooks(bound_divisor=div), numerical_owner() as owner:
                    got = canon(inverse.solve(ops, t, CFG, None, owner))
            finally:
                self.restore()
            diffs += got != ref
        return diffs

    def test_shipped_bound_clean_under_libm_perturbation(self):
        for s in (1, 8, 64):
            cs = self.build(1, s, 40, False)
            self.assertGreaterEqual(len(cs), 20)
            self.assertEqual(self.run_set(cs, 1, s), 0, "shipped bound must be clean at s=%d" % s)

    def test_shrunk_bounds_are_detected_under_libm_perturbation(self):
        for div, s in ((10, 16), (100, 1)):
            cs = self.build(div, s, 40, True)
            self.assertGreaterEqual(len(cs), 5, "could not build attack ties for divisor %d s=%d" % (div, s))
            self.assertGreater(self.run_set(cs, div, s), 0, "bound/%d at s=%d NOT detected: the build must fail" % (div, s))


if __name__ == "__main__":
    unittest.main()
