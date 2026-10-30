"""S04 tenors: item checks on the TEN rows (author1; first owner S05), kernel properties, differential against
the M1 iv_30d rule, and perf row W04 (gate M3A-B3). One test method per row id.
Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12
"""
import statistics
import time
import unittest
from math import sqrt

import adapt_tenors as A
from option_features import tenors as T

ROWS = A.load_rows()
TOL = 3e-5   # row tolerance for iv


class Kernel(unittest.TestCase):
    E = [(5, "available", None, 0.20), (33, "available", None, 0.24), (89, "available", None, 0.26),
         (120, "available", None, 0.25)]

    def test_exact_as_is(self):
        r = T.tenors([(30, "available", None, 0.3), (60, "available", None, 0.2)])[30]
        self.assertEqual((r.status, r.iv, r.method, r.expiries_used), ("available", 0.3, "as_is", (30,)))

    def test_interpolation_total_variance(self):
        res = T.tenors(self.E)
        r = res[91]
        self.assertEqual(r.method, "variance_interpolation")
        self.assertEqual(r.expiries_used, (89, 120))
        self.assertAlmostEqual(r.iv, sqrt((0.26 ** 2 * 89 + (0.25 ** 2 * 120 - 0.26 ** 2 * 89) * 2 / 31) / 91), 15)
        self.assertEqual(res[30].expiries_used, (5, 33))

    def test_no_extrapolation(self):
        r = T.tenors([(30, "available", None, 0.3)])
        self.assertEqual((r[9].status, r[9].reason, r[9].iv, r[9].expiries_used),
                         ("unavailable", "no_bracketing_expiry", None, None))
        self.assertEqual(r[91].reason, "no_bracketing_expiry")

    def test_unsorted_input(self):
        self.assertEqual(T.tenors(list(reversed(self.E))), T.tenors(self.E))

    def test_exact_failing_keeps_reason(self):
        r = T.tenors([(30, "unavailable", "low_surface_coverage", None)])[30]   # R-178
        self.assertEqual((r.status, r.reason, r.expiries_used), ("unavailable", "low_surface_coverage", None))

    def test_bracket_excluded_is_no_bracketing_expiry(self):
        for reason in ("no_atm_strike", "low_surface_coverage"):   # R-104, R-139
            r = T.tenors([(5, "unavailable", reason, None), (33, "available", None, 0.2)])[9]
            self.assertEqual(r.reason, "no_bracketing_expiry", reason)
        r = T.tenors([(5, "available", None, 0.2), (33, "unavailable", "solver_failed", None)])[9]
        self.assertEqual(r.reason, "solver_failed")

    def test_lower_failing_reported_first(self):
        r = T.tenors([(5, "unavailable", "solver_failed", None), (33, "unavailable", "style_unknown", None)])[9]
        self.assertEqual(r.reason, "solver_failed")

    def test_differential_vs_m1_iv_30d(self):
        # same rule as chainiv.IVChain.iv_30d on real ATM IVs (byte-equal floats), all TEN chains
        for row in ROWS:
            chain = A.chain_of(row)
            ins = [(d, a.status, a.reason, a.iv) for d, a in chain.atm_iv_all().items()]
            res = T.tenors(ins)
            for t in (9, 30, 91):
                m1 = chain.iv_30d(t)
                self.assertEqual(res[t].iv, m1.iv, (row["id"], t))
                self.assertEqual(res[t].method, m1.method, (row["id"], t))
                self.assertEqual(res[t].status, m1.status, (row["id"], t))


def _make(row):
    def test(self):
        got = A.run_row(row)
        exp = row["expected"]["frame"]["tenors"]
        self.assertEqual(set(got), set(exp), row["id"])
        for t, e in exp.items():
            g = got[t]
            self.assertEqual((g["status"], g["reason"], g["method"], g["expiries_used"]),
                             (e["status"], e["reason"], e["method"], e["expiries_used"]), (row["id"], t))
            if e["iv"] is None:
                self.assertIsNone(g["iv"], (row["id"], t))
            else:
                self.assertLessEqual(abs(float(g["iv"]) - float(e["iv"])), TOL, (row["id"], t))
    return test


for _r in ROWS:
    setattr(Kernel, "test_item_" + _r["id"].replace("-", "_"), _make(_r))


class PerfW04(unittest.TestCase):
    """M3A-B3: tenors 9, 30, 91 from cached ATM IVs, size M (8 expiries per chain), <= 0.1 s, hard 0.5 s."""

    def test_W04(self):
        days = [5, 12, 19, 26, 33, 61, 89, 119]   # manifest size M expiries
        ins = [(d, "available", None, 0.16 + 0.0004 * d ** 0.5) for d in days]
        T.tenors(ins)   # warm-up
        runs = []
        for _ in range(30):
            t0 = time.perf_counter()
            for _ in range(103):   # one unit per name
                T.tenors(ins)
            runs.append(time.perf_counter() - t0)
        p95 = sorted(runs)[int(0.95 * len(runs)) - 1]
        print("\nW04 103 names x tenors 9/30/91 over 8 cached ATM IVs: p50 %.6f s p95 %.6f s "
              "(budget <= 0.1 s p95, hard 0.5 s; synthetic workload, relative engineering budget)"
              % (statistics.median(runs), p95))
        self.assertLessEqual(p95, 0.1)
        r = T.tenors(ins)
        self.assertEqual(r[30].expiries_used, (26, 33))
        self.assertEqual(r[91].expiries_used, (89, 119))


if __name__ == "__main__":
    unittest.main()
