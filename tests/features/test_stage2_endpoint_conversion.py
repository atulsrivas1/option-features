"""M1 Stage 2 tests (Developer-authored; the independent Tester authors and runs its own checks).

Failing-first: these fail on origin/main (no fast conversion API, no switch). The oracle is
option_features.arithmetic_legacy, a verbatim copy of the pre-Stage-2 conversion, pinned by SHA-256.
Environment: M1S2_EQUIV_N (default 150000 to keep the features suite under 60 s; the full 1,000,000 is one command: python tools/m1_conversion_equivalence.py) and M1S2_EQUIV_WORKERS (default min(24, cores)).
"""
import hashlib
import os
import sys
import unittest
from dataclasses import fields, is_dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

from option_feature_contracts import SolverConfig, ConvertedOperands
from option_features import arithmetic, arithmetic_legacy, inverse
from option_features.arithmetic import numerical_owner, decimal_exact, nearest_binary64
from option_features.model import Operands

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "qualification" / "synthetic" / "perf"), str(ROOT / "tools")]
import gen_m1_solver_sets as gen  # noqa: E402
import m1_adversarial_sets as adv  # noqa: E402
import m1_conversion_equivalence as equiv  # noqa: E402

CFG = SolverConfig("bisection1", "midpoint", 8.0, 256, 1e-10, 1e-10, 1e-10, 1e-10)
LEGACY_SHA256 = "29c03617a1e7c4e1409df086848f08f3744847b45aae14cef5c507b08637f073"


def canon(o):
    if is_dataclass(o):
        return tuple((f.name, canon(getattr(o, f.name))) for f in fields(o))
    if isinstance(o, float):
        return o.hex()
    if isinstance(o, (tuple, list)):
        return tuple(canon(x) for x in o)
    if type(o).__name__ in ("arb", "acb"):
        return (type(o).__name__, o.str(radius=True, more=True))
    if isinstance(o, Decimal):
        return ("Decimal", tuple(o.as_tuple()))
    return (type(o).__name__, str(o)) if isinstance(o, Fraction) else o


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
    out = [gen.contract(gen.DEFAULT_SEED, k, i) for k in ("flat", "mixed") for i in range(80)]
    return out + adv.adversarial(300)[::2] + adv.mutation_ties(40)


class OracleTests(unittest.TestCase):
    def test_oracle_is_the_pinned_verbatim_copy(self):
        data = Path(arithmetic_legacy.__file__).read_bytes().replace(bytes((13, 10)), bytes((10,)))   # normalise checkout line endings
        self.assertEqual(hashlib.sha256(data).hexdigest(), LEGACY_SHA256)

    def test_fast_path_is_on_by_default_and_switchable(self):
        self.assertTrue(arithmetic.fast_endpoints_enabled())
        try:
            arithmetic.set_fast_endpoints(False)
            self.assertFalse(arithmetic.fast_endpoints_enabled())
        finally:
            arithmetic.set_fast_endpoints(True)
        self.assertTrue(arithmetic.fast_endpoints_enabled())


class EquivalenceTests(unittest.TestCase):
    def test_randomized_equivalence_one_million(self):
        n = int(os.environ.get("M1S2_EQUIV_N", "150000"))   # full 1,000,000: M1S2_EQUIV_N=1000000 or python tools/m1_conversion_equivalence.py
        workers = int(os.environ.get("M1S2_EQUIV_WORKERS", str(min(24, os.cpu_count() or 1))))
        report = equiv.run(n, workers, 20261029)
        self.assertEqual(report["mismatches"], 0, report["first_mismatches"])
        self.assertGreaterEqual(report["inputs"], n)
        for kind in ("ball", "bound", "rational", "decimal", "tuple"):
            self.assertGreater(report["comparisons_by_class"].get(kind, 0), 0, kind)

    def test_directed_rounding_contains_exact_value_and_is_outward(self):
        for v in (Fraction(1, 3), Fraction(-1, 3), Fraction(2, 7), Fraction(10**100 + 1, 10**50), Fraction(1, 10**900), Fraction(-5, 10**7)):
            low, high = arithmetic.outward_decimal(v, False), arithmetic.outward_decimal(v, True)
            self.assertLessEqual(Fraction(low), v)
            self.assertGreaterEqual(Fraction(high), v)
            self.assertEqual((low.as_tuple(), high.as_tuple()), (arithmetic_legacy.outward_decimal(v, False).as_tuple(), arithmetic_legacy.outward_decimal(v, True).as_tuple()))

    def test_ends_ordering_and_materialisation(self):
        with numerical_owner() as (arb, fmpq, ctx):
            for bits in arithmetic.TIERS:
                ctx.prec = bits
                ball = arb(fmpq(1, 3)) * 7
                ends = arithmetic.enclosure_ends(ball)
                enc = arithmetic_legacy.enclosure(ball)
                self.assertEqual(canon(ends.enclosure()), canon(enc))
                low, high = ends.fractions()
                self.assertEqual((low, high), (decimal_exact(enc.value_low), decimal_exact(enc.value_high)))
                self.assertEqual(ends.sign_vs(Fraction(2)), 1)
                self.assertEqual(ends.sign_vs(Fraction(3)), -1)
                self.assertEqual(ends.sign_vs(Fraction(7, 3)), 0)


class BoundaryTests(unittest.TestCase):
    """Endpoint exactly on target, on target +- tolerance, both signs: kills within/sign_vs boundary mutants."""

    def test_within_and_sign_vs_at_exact_boundaries(self):
        for sign in (1, -1):
            for low, high in ((Fraction(3, 8), Fraction(5, 8)), (Fraction(-5, 8), Fraction(-3, 8)), (Fraction(1, 3), Fraction(2, 3))):
                lo, hi = sign * low, sign * high
                lo, hi = min(lo, hi), max(lo, hi)
                for enc_kind in ("parts", "enc"):
                    def mk():
                        if enc_kind == "enc":
                            return arithmetic.Ends(enc=arithmetic_legacy.PriceEnclosure("option-arb-bsm1", "1", arithmetic_legacy.outward_decimal(lo, False), arithmetic_legacy.outward_decimal(hi, True)))
                        return arithmetic.Ends(arithmetic._finish(*self._parts(lo, False)), arithmetic._finish(*self._parts(hi, True)))
                    e = mk()
                    L, H = e.fractions()
                    for t in (L, H, (L + H) / 2, L - Fraction(1, 10**9), H + Fraction(1, 10**9)):
                        self.assertEqual(e.sign_vs(t), -1 if H < t else (1 if L > t else 0), (sign, enc_kind, t))
                    tol = Fraction(1, 8)
                    for t in (L + tol, H - tol, L + tol + Fraction(1, 10**9), H - tol - Fraction(1, 10**9), L, H):
                        want = abs(L - t) <= tol and abs(H - t) <= tol
                        self.assertEqual(mk().within(t - tol, t + tol), want, (sign, enc_kind, t))

    @staticmethod
    def _parts(v, upper):
        # exact endpoints are decimal rationals here, so the outward parts are the value itself
        num, den = v.numerator, v.denominator
        return arithmetic._outward_parts(num, den, upper)

    def test_solver_with_target_exactly_on_enclosure_edge_matches_legacy(self):
        """Prices whose exact mid is a bound or a tolerance edge, both signs of the exponent, fast versus legacy."""
        cases = [c for c in sample() if c.get("right") in ("C", "P")][:40]
        for c in cases:
            p = prepared(c)
            for target in (p[1], p[1] + Fraction(1, 10**4), p[1] - Fraction(1, 10**4), Fraction(0), Fraction(1, 10**10)):
                p2 = (p[0], target, p[2])
                fast = solve(p2)
                try:
                    arithmetic.set_fast_endpoints(False)
                    legacy = solve(p2)
                finally:
                    arithmetic.set_fast_endpoints(True)
                self.assertEqual(fast, legacy)


class SolverTests(unittest.TestCase):
    def test_fast_equals_legacy_on_every_solver_field(self):
        cases = sample()
        fast = [solve(prepared(c)) for c in cases]
        try:
            arithmetic.set_fast_endpoints(False)
            legacy = [solve(prepared(c)) for c in cases]
        finally:
            arithmetic.set_fast_endpoints(True)
        self.assertEqual(sum(a == b for a, b in zip(fast, legacy)), len(cases))

    def test_filter_off_and_fast_off_are_both_identical(self):
        cases = sample()[:120]
        ref = [solve(prepared(c)) for c in cases]
        try:
            arithmetic.set_fast_endpoints(False)
            both_off = [solve(prepared(c), float_filter=False) for c in cases]
        finally:
            arithmetic.set_fast_endpoints(True)
        self.assertEqual(ref, both_off)

    def test_decimal_materialisations_are_deferred(self):
        """Only the result's enclosures may be materialised as Decimals, not every bisection step."""
        made = [0]
        real = arithmetic._decimal

        def counting(c, e):
            made[0] += 1
            return real(c, e)
        arithmetic._decimal = counting
        try:
            per = []
            for c in sample()[:60]:
                made[0] = 0
                solve(prepared(c))
                per.append(made[0])
        finally:
            arithmetic._decimal = real
        self.assertLessEqual(max(per), 16, per)


if __name__ == "__main__":
    unittest.main()
