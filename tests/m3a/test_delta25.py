"""S03: the 25-delta point kernel (`option_features.delta25`), both delta conventions (R-155 to R-157).

First owner of perf rows W03 (M3A-B2) and W14 (M3A-B12). Item-level checks (not ownership) on the `p25`/`c25`
items of the author1 delta25 rows on available expiries (rows first-owned by S05/S09). Unit tests with a stubbed
solver for the four solver reasons no fixture row reaches (R-128 note): the failing contract is excluded (R-109).
Expectations come from the row files, the author4 workload truth and an independent float reference written
here (delta for every strike, then the first crossing); the library is never asked for its own expectation.

Label: synthetic workload, relative engineering budget. mock-data qualification only: passed on independently
authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12.
"""
import math
import random
import statistics
import time
import unittest
from fractions import Fraction
from unittest import mock

import adapt_delta25 as A
from option_features import chainiv
from option_features.delta25 import delta25_point
from option_features.inverse import InverseResult

KEYS = {"status", "reason", "value", "strikes_used", "evaluations"}
TARGET = 0.25
B2_BUDGET_S, B2_HARD_S = 0.002, 0.010
B12_BUDGET, B12_HARD = 200, 400
REPEATS = 30


def _ncdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def ref_delta(S, K, T, r, q, s, right, convention):
    d1 = (math.log(S / K) + (r - q + 0.5 * s * s) * T) / (s * math.sqrt(T))
    eq = 1.0 if convention == "forward" else math.exp(-q * T)
    return eq * (_ncdf(d1) if right == "call" else _ncdf(-d1))


def ref_point(strikes, ivs, atm, S, r, q, days, right, convention):
    """Independent float reference: delta for EVERY usable strike on the scan path, then the first pair that
    brackets 0.25 inclusive scanning outward from the ATM strike, IV linear in delta (R-09, R-10, R-16, R-21)."""
    T = days / 365.0
    pts = [(k, s) for k, s in zip(strikes, ivs) if s is not None]
    pts = [p for p in pts if p[0] <= atm][::-1] if right == "put" else [p for p in pts if p[0] >= atm]
    pts = [(k, s, ref_delta(S, float(k), T, r, q, s, right, convention)) for k, s in pts]
    for i in range(len(pts) - 1):
        (k1, s1, d1), (k2, s2, d2) = pts[i], pts[i + 1]
        if (d1 - TARGET) * (d2 - TARGET) <= 0 and not (d1 == d2 and d1 != TARGET):
            w = 0.0 if d1 == d2 else (TARGET - d1) / (d2 - d1)
            return "available", s1 + w * (s2 - s1), (k1, k2)
    return "unavailable", None, ()


def _call(strikes, ivs, atm, S=100, r="0.02", q="0", days=30, right="call", convention="spot", **kw):
    return delta25_point([Fraction(k) for k in strikes], ivs, Fraction(atm), Fraction(S),
                         Fraction.from_float(float(r)), Fraction.from_float(float(q)), days, right, convention, **kw)


def _grid(lo, hi, step):
    out, k = [], Fraction(lo)
    while k <= Fraction(hi):
        out.append(k)
        k += Fraction(step)
    return out


def _smile(strikes, atm_iv=0.2, slope=-0.15, curve=0.4, F=100.0):
    return [atm_iv + slope * math.log(float(k) / F) + curve * math.log(float(k) / F) ** 2 for k in strikes]


class Shape(unittest.TestCase):
    def test_record_shape_and_available_point(self):
        ks = _grid(80, 120, 1)
        got = _call(ks, _smile(ks), 100)
        self.assertEqual(set(got), KEYS)
        self.assertEqual(got["status"], "available")
        self.assertIsNone(got["reason"])
        self.assertIsInstance(got["value"], float)
        self.assertEqual(len(got["strikes_used"]), 2)

    def test_conventions_validated(self):
        ks = _grid(90, 110, 1)
        for bad in ("Spot", "fwd", "", None, 1):
            with self.assertRaises(ValueError):
                _call(ks, _smile(ks), 100, convention=bad)

    def test_bad_right_rejected(self):
        ks = _grid(90, 110, 1)
        with self.assertRaises(ValueError):
            _call(ks, _smile(ks), 100, right="both")


class Rules(unittest.TestCase):
    def _check(self, strikes, ivs, atm, S=100, r=0.02, q=0.0, days=30, right="call", convention="spot"):
        got = _call(strikes, ivs, atm, S, repr(r), repr(q), days, right, convention)
        rf = Fraction.from_float(r)
        status, value, used = ref_point(strikes, ivs, Fraction(atm), S, float(rf), float(Fraction.from_float(q)),
                                        days, right, convention)
        self.assertEqual(got["status"], status, (right, convention))
        self.assertEqual(tuple(got["strikes_used"]), tuple(used))
        if value is None:
            self.assertEqual(got["reason"], "no_delta_bracket")
            self.assertIsNone(got["value"])
        else:
            self.assertIsNone(got["reason"])
            self.assertAlmostEqual(got["value"], value, delta=1e-10)
        return got

    def test_both_sides_both_conventions_match_reference(self):
        ks = _grid(70, 130, Fraction(1, 2))
        for q in (0.0, 0.03):
            for right in ("put", "call"):
                for conv in ("spot", "forward"):
                    self._check(ks, _smile(ks), 100, q=q, right=right, convention=conv)

    def test_forward_equals_spot_when_no_yield_and_differs_with_yield(self):
        ks = _grid(70, 130, Fraction(1, 2))
        for right in ("put", "call"):
            a = _call(ks, _smile(ks), 100, q="0", right=right)
            b = _call(ks, _smile(ks), 100, q="0", right=right, convention="forward")
            self.assertEqual(a, b)
            a = _call(ks, _smile(ks), 100, q="0.05", days=180, right=right)
            b = _call(ks, _smile(ks), 100, q="0.05", days=180, right=right, convention="forward")
            self.assertNotEqual(a["value"], b["value"])

    def test_no_extrapolation(self):
        ks = _grid(100, 103, 1)          # call deltas stay near 0.5: no bracket, no extrapolation (R-16)
        got = self._check(ks, [0.2] * len(ks), 100)
        self.assertEqual(got["evaluations"], len(ks))
        got = self._check(ks, [0.2] * len(ks), 100, right="put")
        self.assertEqual(got["status"], "unavailable")

    def test_fewer_than_two_strikes(self):
        self._check([Fraction(100)], [0.2], 100)
        self._check([], [], 100)

    def test_first_crossing_outward_on_non_monotone_delta(self):
        ks = _grid(100, 130, 1)
        ivs = [0.2] * len(ks)
        # a high-IV bump near 112 lifts call delta back above 0.25 after a first crossing near 107
        for i, k in enumerate(ks):
            if 109 <= k <= 116:
                ivs[i] = 0.9
        got = self._check(ks, ivs, 100, days=20)
        k1, k2 = got["strikes_used"]
        self.assertLess(k2, 109)

    def test_evaluations_stop_at_first_crossing(self):
        ks = _grid(60, 140, Fraction(1, 2))
        got = _call(ks, _smile(ks), 100)
        k2 = got["strikes_used"][1]
        self.assertEqual(got["evaluations"], sum(1 for k in ks if 100 <= k <= k2))
        self.assertLess(got["evaluations"], len([k for k in ks if k >= 100]))

    def test_excluded_contract_is_skipped(self):
        ks = _grid(80, 120, 1)
        ivs = _smile(ks)
        base = _call(ks, ivs, 100)
        k1, k2 = base["strikes_used"]
        holed = [None if k == k2 else s for k, s in zip(ks, ivs)]
        got = self._check(ks, holed, 100)
        self.assertNotIn(k2, got["strikes_used"])

    def test_exact_target_inclusive(self):
        # forward put delta N(-d1) at sigma chosen so the put at K=90 is exactly representable? Instead: two equal
        # IVs give equal deltas only at equal strikes; inclusiveness is checked against the reference on a dense grid.
        ks = _grid(80, 100, Fraction(1, 100))
        self._check(ks, [0.25] * len(ks), 100, right="put", convention="forward", r=0.0)

    def test_certified_only_gives_identical_bytes(self):
        rng = random.Random(20261030)
        for _ in range(60):
            S = rng.choice((50, 100, 250))
            ks = _grid(S * Fraction(6, 10), S * Fraction(14, 10), Fraction(S, 100) * rng.choice((1, 2, 5)))
            ivs = _smile(ks, rng.uniform(0.08, 0.9), rng.uniform(-0.4, 0.1), rng.uniform(0, 1.5), S)
            ivs = [max(s, 0.01) for s in ivs]
            atm = min(ks, key=lambda k: (abs(k - S), k))
            kw = dict(S=S, r=repr(rng.choice((0.0, 0.02, 0.05))), q=repr(rng.choice((0.0, 0.01, 0.04))),
                      days=rng.choice((1, 7, 30, 91, 365)))
            for right in ("put", "call"):
                for conv in ("spot", "forward"):
                    a = _call(ks, ivs, atm, right=right, convention=conv, **kw)
                    b = _call(ks, ivs, atm, right=right, convention=conv, certified_only=True, **kw)
                    self.assertEqual(a, b)

    def test_randomized_against_reference(self):
        rng = random.Random(25)
        for _ in range(150):
            S = 100
            ks = _grid(60, 140, rng.choice((Fraction(1, 2), 1, Fraction(5, 2))))
            ivs = [max(0.02, s + rng.uniform(-0.03, 0.03)) for s in _smile(ks, rng.uniform(0.1, 0.6))]
            if rng.random() < 0.2:
                ivs = [None if rng.random() < 0.15 else s for s in ivs]
            atm = min(ks, key=lambda k: (abs(k - S), k))
            q = rng.choice((0.0, 0.02))
            for right in ("put", "call"):
                for conv in ("spot", "forward"):
                    self._check(ks, ivs, atm, q=q, days=rng.choice((3, 30, 120)), right=right, convention=conv)


class StubbedSolverReasons(unittest.TestCase):
    """R-128 note: sigma_cap, precision_exhausted, bound_precision and iteration_budget are not reached by any
    fixture row; a stubbed solver returns each on one contract and that contract is excluded from the search."""

    REASONS = (("bracket_exceeded", "sigma_cap"), ("numerical_failure", "precision_exhausted"),
               ("numerical_failure", "bound_precision"), ("iteration_limit", "iteration_budget"))

    def _chain(self):
        cs = []
        S, T, r = 100.0, 30 / 365.0, 0.02
        for k in range(80, 121):
            for right in ("call", "put"):
                s = 0.2 + 0.002 * abs(k - 100)
                d1 = (math.log(S / k) + (r + 0.5 * s * s) * T) / (s * math.sqrt(T))
                d2 = d1 - s * math.sqrt(T)
                if right == "call":
                    p = S * _ncdf(d1) - k * math.exp(-r * T) * _ncdf(d2)
                else:
                    p = k * math.exp(-r * T) * _ncdf(-d2) - S * _ncdf(-d1)
                p = max(p, 0.05)
                cs.append(chainiv.ChainContract("%s%d" % (right[0], k), 30, right, str(k), "%.4f" % (p - 0.001),
                                                "%.4f" % (p + 0.001), 10 ** 12, None, "european", "regular"))
        return cs

    def test_four_uncovered_reasons_exclude_the_contract(self):
        cs = self._chain()
        base = A.Prepared(cs, "100", "0.02", "0", 10 ** 12 + 1).point(30, "call")
        self.assertEqual(base["status"], "available")
        victim = base["strikes_used"][1]
        real = chainiv.solve
        for status, reason in self.REASONS:
            def fake(operands, target, config, converted, owner, float_filter=True):
                if operands.eta == 1 and operands.strike == victim:
                    return InverseResult(None, status, reason, None)
                return real(operands, target, config, converted, owner, float_filter)
            with mock.patch.object(chainiv, "solve", fake):
                p = A.Prepared(cs, "100", "0.02", "0", 10 ** 12 + 1)
                self.assertEqual(p.ivs["c%d" % victim].reason, reason)
                got = p.point(30, "call")
            self.assertEqual(got["status"], "available", reason)
            self.assertNotIn(victim, got["strikes_used"], reason)
            legs = [x for x in p.legs[(30, "call")]]
            want = ref_point([k for k, _ in legs], [s for _, s in legs], p.atm[30].strike, 100.0,
                             float(p.rate), 0.0, 30, "call", "spot")
            self.assertEqual(tuple(got["strikes_used"]), want[2], reason)
            self.assertAlmostEqual(got["value"], want[1], delta=1e-10)


# ---------------------------------------------------------------- author1 delta25 item checks (not ownership)
class D25Items(unittest.TestCase):
    def test_fixture_unedited(self):
        self.assertTrue(A.manifest_ok(A.AUTHOR1, "m3a_cases_delta25.json"))


def _make_item(row):
    def test(self):
        items = A.row_items(row)
        if not items:
            self.skipTest("%s: no 25-delta side on an available expiry (frame-level row, owner S05/S09)" % row["id"])
        p = A.prepare_row(row)
        tol = float(Fraction((row["expected"].get("tolerance") or {}).get("iv", "0.00003")))
        for days, right, want in items:
            got = p.point(days, right, A.row_convention(row))
            self.assertIsNotNone(got, (row["id"], days, right, "ATM"))
            self.assertEqual((got["status"], got["reason"]), (want["status"], want["reason"]), (row["id"], days, right))
            if want["status"] == "available":
                self.assertLessEqual(abs(got["value"] - float(Fraction(want["value"]))), tol, (row["id"], days, right))
    return test


for _row in A.d25_rows():
    setattr(D25Items, "test_%s_p25_c25" % _row["id"].replace("-", "_"), _make_item(_row))


# ---------------------------------------------------------------- perf rows W03 (M3A-B2) and W14 (M3A-B12)
class _Workloads:
    cache = {}

    @classmethod
    def get(cls, size):
        if size not in cls.cache:
            cls.cache[size] = A.workload(size)
        return cls.cache[size]


class PerfRows(unittest.TestCase):
    def test_W03(self):
        """M3A-B2 per convention: one 25-delta point, size-M chain, IVs cached; p95 over 30 repeats after one
        warm-up (synthetic workload, relative engineering budget); spot value within 1e-4 of the chain truth on
        expiries with ATM vega >= 4, forward value against the independent reference."""
        prepared, truth, _ = _Workloads.get("M")
        for conv in ("spot", "forward"):
            worst = []
            for ex in truth["expiries"]:
                days = ex["expiry_days"]
                for right, key in (("put", "put25"), ("call", "call25")):
                    prepared.point(days, right, conv)              # warm-up
                    times = []
                    for _ in range(REPEATS):
                        t0 = time.perf_counter()
                        got = prepared.point(days, right, conv)
                        times.append(time.perf_counter() - t0)
                    p95 = statistics.quantiles(times, n=20)[18]
                    worst.append(p95)
                    if conv == "spot" and ex[key] is not None and float(ex["atm_vega"]) >= 4:
                        self.assertEqual(got["status"], "available", (days, right))
                        self.assertLessEqual(abs(got["value"] - float(ex[key]["iv"])), 1e-4, (days, right))
                    legs = prepared.legs[(days, right)]
                    want = ref_point([k for k, _ in legs], [s for _, s in legs], prepared.atm[days].strike,
                                     float(prepared.spot), float(prepared.rate), float(prepared.carry), days, right, conv)
                    self.assertEqual(got["status"], want[0], (conv, days, right))
                    if want[1] is not None:
                        self.assertAlmostEqual(got["value"], want[1], delta=1e-10)
            print("\nW03 M3A-B2 %s: worst point p95 %.3f ms (budget 2 ms, hard 10 ms; synthetic workload, relative "
                  "engineering budget)" % (conv, max(worst) * 1e3))
            self.assertLessEqual(max(worst), B2_BUDGET_S, conv)

    def test_W14(self):
        """M3A-B12 per convention: delta evaluations per chain counted by the SUT, sizes S, M, L; size M gated
        at 200 (hard 400). Also prints the M3A-B1 kernel share (all points of the size-M chain) as a hook for S05."""
        for size in ("S", "M", "L"):
            prepared, truth, manifest = _Workloads.get(size)
            for conv in ("spot", "forward"):
                total = 0
                t0 = time.perf_counter()
                for ex in truth["expiries"]:
                    for right in ("put", "call"):
                        total += prepared.point(ex["expiry_days"], right, conv)["evaluations"]
                wall = time.perf_counter() - t0
                print("\nW14 M3A-B12 size %s %s: %d delta evaluations per chain (naive %d); kernel wall %.1f ms "
                      "(M3A-B1 share, informational)" % (size, conv, total, manifest["facts"]["naive_delta_evaluations"],
                                                        wall * 1e3))
                if size == "M":
                    self.assertLessEqual(total, B12_BUDGET, conv)
                self.assertLess(total, manifest["facts"]["naive_delta_evaluations"], (size, conv))


if __name__ == "__main__":
    unittest.main()
