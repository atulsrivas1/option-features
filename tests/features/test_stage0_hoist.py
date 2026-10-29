"""M1 Stage 0 regression tests (Developer-authored; the independent Tester authors its own checks)."""
import sys
import unittest
from dataclasses import fields, is_dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from option_feature_contracts import SolverConfig, ConvertedOperands
from option_features import inverse
from option_features.arithmetic import numerical_owner, decimal_exact, nearest_binary64
from option_features.model import Operands

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "qualification" / "synthetic" / "perf"))
import gen_m1_solver_sets as gen  # noqa: E402

CFG = SolverConfig("bisection1", "midpoint", 8.0, 256, 1e-10, 1e-10, 1e-10, 1e-10)


def canon(o):
    if is_dataclass(o):
        return tuple((f.name, canon(getattr(o, f.name))) for f in fields(o))
    if isinstance(o, float):
        return o.hex()
    if isinstance(o, (tuple, list)):
        return tuple(canon(x) for x in o)
    return (type(o).__name__, str(o)) if isinstance(o, (Decimal, Fraction)) else o


def prepared(kind, i):
    c = gen.contract(gen.DEFAULT_SEED, kind, i)
    S, K = decimal_exact(Decimal(c["spot"])), decimal_exact(Decimal(c["strike"]))
    rate, carry = Fraction.from_float(float(c["rate"])), Fraction.from_float(float(c["div"]))
    T = Fraction(c["t_days"], 365)
    ops = Operands(S, K, rate, carry, T, Fraction(0), 1 if c["right"] == "C" else -1)
    conv = ConvertedOperands(float(S), float(K), float(rate), float(carry), None, c["t_days"], nearest_binary64(T))
    return ops, decimal_exact(Decimal(c["price"])), conv


def solve(p):
    with numerical_owner() as owner:
        return canon(inverse.solve(p[0], p[1], CFG, p[2], owner))


def solve_nocache(p):
    real = inverse.Operands
    with patch.object(inverse, "Operands", lambda *a: real(*a[:7], None)):
        return solve(p)


class Stage0HoistTests(unittest.TestCase):
    def test_every_precision_tier_key_matches_no_cache_reference(self):
        tiers = (16, 32, 64, 128, 256, 512, 1024, 2048)
        with patch.object(inverse, "TIERS", tiers):
            for kind in ("flat", "mixed"):
                for i in range(500):
                    p = prepared(kind, i)
                    self.assertEqual(solve(p), solve_nocache(p), (kind, i))

    def test_consecutive_solves_on_different_contracts_equal_isolated(self):
        ps = [prepared("mixed", i) for i in range(40)]
        isolated = [solve_nocache(p) for p in ps]
        again = [solve(p) for p in ps]            # one process, consecutive calls
        self.assertEqual(again, isolated)
        self.assertEqual([solve(p) for p in reversed(ps)], list(reversed(isolated)))


if __name__ == "__main__":
    unittest.main()
