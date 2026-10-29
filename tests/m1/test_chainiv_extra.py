"""Developer tests for option_features.chainiv beyond the 41 independent rows (the Tester authors its own).

Covers what the rows cannot reach (mutants X4, X10, X11 in tools/m1_iv_mutation_check.py): stale boundary,
excluded_condition, not-yet-known quotes; plus input-order independence, solve economy (ATM solves only the
nearest-forward strike), bit-identity of chain IV with a direct fully certified solve, exact tie handling when
r != q, and input validation. Synthetic data only.
"""
import json
import math
import random
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools")]
from option_features import chainiv, inverse  # noqa: E402
from option_features.arithmetic import numerical_owner, nearest_binary64  # noqa: E402
from option_features.model import Operands  # noqa: E402
from option_feature_contracts import ConvertedOperands  # noqa: E402
import m1_chain_benchmark as bench  # noqa: E402

C = chainiv.ChainContract
LIM = 10_000_000_000


def pair(strike, expiry=30, **kw):
    """A valid European call and put at one strike (flat 0.20 vol, spot 100, r 0.03, q 0.01 prices)."""
    out = []
    for right in ("call", "put"):
        mid = round(bench.bs(right, float(strike), expiry / 365.0, 0.20), 4)
        d = dict(contract_id="%s-%s-%d" % (right, strike, expiry), expiry_days=expiry, right=right, strike=strike,
                 bid="%.4f" % (mid - 0.001), ask="%.4f" % (mid + 0.001), event_ns=-1_000_000_000,
                 known_at_ns=-1_000_000_000, style="european", condition="regular")
        d.update(kw)
        out.append(C(**d))
    return out


def chain(contracts, **kw):
    return chainiv.IVChain(contracts, "100.0000", "0.0300", "0.0100", 0, **kw)


class Gates(unittest.TestCase):
    def reason(self, **kw):
        cs = pair("100.0000", **kw)
        return chain(cs).contract_iv()["call-100.0000-30"]

    def test_stale_boundary_is_exclusive(self):
        self.assertEqual(self.reason(event_ns=-LIM, known_at_ns=-LIM).status, "available")
        r = self.reason(event_ns=-LIM - 1, known_at_ns=-LIM - 1)
        self.assertEqual((r.status, r.reason), ("unavailable", "stale_quote"))

    def test_excluded_condition_beats_validity(self):
        r = self.reason(condition="auction", bid="0.0000")
        self.assertEqual(r.reason, "excluded_condition")

    def test_not_yet_known_is_no_quote(self):
        self.assertEqual(self.reason(known_at_ns=1).reason, "no_quote")

    def test_both_sides_missing_is_no_quote_one_side_invalid(self):
        self.assertEqual(self.reason(bid=None, ask=None).reason, "no_quote")
        self.assertEqual(self.reason(bid=None).reason, "invalid_quote")
        self.assertEqual(self.reason(ask=None).reason, "invalid_quote")
        self.assertEqual(self.reason(bid="-0.0100").reason, "invalid_quote")

    def test_known_at_none_means_event_time(self):
        self.assertEqual(self.reason(known_at_ns=None).status, "available")


class Economy(unittest.TestCase):
    def setUp(self):
        self.rows = bench.make_chain("S")
        self.calls = []
        self.real = chainiv.solve

        def counted(*a, **k):
            self.calls.append(a[1])
            return self.real(*a, **k)
        chainiv.solve = counted

    def tearDown(self):
        chainiv.solve = self.real

    def test_atm_solves_two_contracts_per_expiry(self):
        out = chain(self.rows).atm_iv_all()
        self.assertEqual(len(out), 5)
        self.assertEqual(len(self.calls), 10)

    def test_30d_solves_four_then_contract_iv_reuses_them(self):
        ch = chain(self.rows)
        first = ch.iv_30d(30)
        self.assertEqual(len(self.calls), 4)
        ch.contract_iv()
        ch.contract_iv()
        self.assertEqual(ch.iv_30d(30), first)
        self.assertEqual(len(self.calls), len(ch._memo))   # every contract that reached the solver was solved once

    def test_unmodelled_contracts_never_reach_the_solver(self):
        ch = chain(self.rows)
        out = ch.contract_iv()
        self.assertEqual(len(self.calls), sum(1 for v in out.values() if v.status == "available" or v.reason not in
                                              ("american_itm", "style_unknown", "no_quote", "excluded_condition",
                                               "invalid_quote", "crossed_market", "locked_market", "stale_quote")))
        self.assertTrue(any(v.reason == "american_itm" for v in out.values()))


class Identity(unittest.TestCase):
    def test_bit_identical_to_direct_certified_solve(self):
        rows = [r for r in bench.make_chain("S") if r.style == "european"][:40]
        got = chain(rows).contract_iv()
        checked = 0
        with numerical_owner() as owner:
            for r in rows:
                v = got[r.contract_id]
                if v.status != "available":
                    continue
                S, K = Fraction(100), Fraction(r.strike)
                rate, carry = Fraction.from_float(0.03), Fraction.from_float(0.01)
                T = Fraction(r.expiry_days, 365)
                ops = Operands(S, K, rate, carry, T, Fraction(0), 1 if r.right == "call" else -1)
                conv = ConvertedOperands(100.0, float(K), 0.03, 0.01, None, r.expiry_days * 86400 * 10 ** 9, nearest_binary64(T))
                target = (Fraction(r.bid) + Fraction(r.ask)) / 2
                for ff in (True, False):
                    direct = inverse.solve(ops, target, chainiv.DEFAULT_SOLVER, conv, owner, float_filter=ff)
                    self.assertEqual(direct.value, v.iv)
                checked += 1
        self.assertGreater(checked, 20)

    def test_input_order_independent(self):
        rows = bench.make_chain("S")[:120]
        base = chain(rows).contract_iv()
        shuffled = rows[:]
        random.Random(7).shuffle(shuffled)
        again = chain(shuffled)
        self.assertEqual({k: base[k] for k in base}, again.contract_iv())
        self.assertEqual(chain(rows).atm_iv_all(), again.atm_iv_all())
        self.assertEqual(chain(rows).iv_30d(30), again.iv_30d(30))


class Ties(unittest.TestCase):
    def test_near_tie_with_nonzero_drift_is_decided_exactly(self):
        mid = 10050000000  # 100.5 in ticks, between strikes 100 and 101
        up = chainiv._Forward(mid, Fraction(1, 10 ** 12))
        down = chainiv._Forward(mid, Fraction(-1, 10 ** 12))
        strikes = [100 * 10 ** 8, 101 * 10 ** 8]
        self.assertEqual(up.nearest(strikes), 101 * 10 ** 8)
        self.assertEqual(down.nearest(strikes), 100 * 10 ** 8)

    def test_exact_tie_goes_lower(self):
        f = chainiv._Forward(10050000000, Fraction(0))
        self.assertEqual(f.nearest([100 * 10 ** 8, 101 * 10 ** 8]), 100 * 10 ** 8)

    def test_forward_value(self):
        ch = chain(pair("100.0000"))
        a = ch.atm_iv(30)
        self.assertAlmostEqual(a.forward, 100.0 * math.exp(0.02 * 30 / 365), places=7)


class Validation(unittest.TestCase):
    def test_bad_inputs_raise(self):
        good = pair("100.0000")
        with self.assertRaises(ValueError):
            chain(good + good)  # duplicate ids
        with self.assertRaises(ValueError):
            chain([good[0]._replace(expiry_days=0)])
        with self.assertRaises(ValueError):
            chain([good[0]._replace(right="x")])
        with self.assertRaises(ValueError):
            chain([good[0]._replace(contract_id="other")] + [good[0]])  # same expiry, strike, right

    def test_empty_chain(self):
        ch = chain([])
        self.assertEqual(ch.contract_iv(), {})
        self.assertEqual(ch.atm_iv(30).reason, "no_atm_strike")
        self.assertEqual(ch.iv_30d(30).reason, "no_bracketing_expiry")

    def test_solver_failure_is_reported_not_raised(self):
        # a price above the no-arbitrage upper bound (call mid above spot) is out of bounds
        cs = [c._replace(bid="150.0000", ask="150.0020") if c.right == "call" else c for c in pair("100.0000")]
        r = chain(cs).contract_iv()["call-100.0000-30"]
        self.assertEqual((r.status, r.iv), ("unavailable", None))
        self.assertEqual(r.reason, "price_out_of_bounds")
        a = chain(cs).atm_iv(30)
        self.assertEqual((a.status, a.reason, a.iv), ("unavailable", "price_out_of_bounds", None))


if __name__ == "__main__":
    unittest.main()
