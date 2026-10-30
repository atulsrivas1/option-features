"""M2 story B: behaviour tests added after the independent Tester review of PR 79 (own tests, fixtures untouched):
strict types and parameters, bounded threshold cache, premiums above 2^53, pre-open clipping for F4/F7/F17/F18,
fractional N, F12 coverage from prints, and the incremental F12 sweep.

Label: synthetic workload, relative engineering budget (no claim about recorded data). Synthetic fixtures only.
"""
import os
import random
import unittest
from fractions import Fraction

from option_features import episodes as E, m2prints as _M, printtape as PT
from test_m2b_properties import LANES, M, NS, OPEN, SEEDS, Scenario

CONS = {"A": ("C", 1, "2026-11-20", "stock")}


class Strict(unittest.TestCase):
    def test_float_and_bad_parameters_are_malformed_type(self):
        tape = PT.build_tape([("A", OPEN + NS, "1.0000", 5, 100, 0, 0)], CONS)
        T = OPEN + 1000 * NS
        calls = (lambda: M.f4_large_prints(tape, T, n=1.5), lambda: M.f4_large_prints(tape, T, threshold_ticks=1e9),
                 lambda: M.f1_premium_surge(tape, T, OPEN, n=3.0), lambda: M.f7_concentration(tape, T, share_threshold=0.6),
                 lambda: M.f18_put_share(tape, T, at_least=0.5), lambda: M.f17_window_premium(tape, T, "A", threshold_ticks=1e9),
                 lambda: M.f4_large_prints(tape, T, n="x"), lambda: M.f1_premium_surge(tape, T, OPEN, n=True))
        for call in calls:
            r = call()
            self.assertEqual((r["status"], r["code"]), ("invalid_input", "malformed_type"))
        for kw in ({"quiet_gap": 0}, {"n_episodes": 0}, {"n": 1.5}, {"quiet_gap": True}):
            r = E.f12_episodes([], [], T, OPEN, **kw)
            self.assertEqual((r["status"], r["code"]), ("invalid_input", "malformed_type"), kw)

    def test_grid_not_60s(self):
        r = E.f12_episodes([], [], OPEN + 1000 * NS, OPEN, grid_s=30)
        self.assertEqual((r["status"], r["code"]), ("invalid_input", "grid_not_60s"))

    def test_non_int_window_is_window_not_allowed(self):
        tape = PT.build_tape([("A", OPEN + NS, "1.0000", 5, 100, 0, 0)], CONS)
        T = OPEN + 1000 * NS
        for call in (lambda: M.f4_large_prints(tape, T, window_s=300.0), lambda: M.f7_concentration(tape, T, window_s=300.0),
                     lambda: M.f17_window_premium(tape, T, "A", window_s=300.0), lambda: M.f18_put_share(tape, T, window_s=True, at_least=1)):
            self.assertEqual(call()["code"], "window_not_allowed")
        self.assertEqual(M.f4_large_prints(tape, T, n="3/2")["status"], "available")

    def test_price_ticks_is_strict(self):
        from option_features.flowgrid import price_ticks
        for bad in ("1e5", " 1", "1_0", "١", "--1", "", ".", "1.2.3", "1.00001", True, 1.5, None):
            with self.assertRaises((ValueError, TypeError)):
                price_ticks(bad)
        self.assertEqual((price_ticks(".5"), price_ticks("5."), price_ticks("1.00000"), price_ticks("-.5"), price_ticks("80")),
                         (5000, 50000, 10000, -5000, 800000))

    def test_non_int_fields_are_malformed_type(self):
        for p in (("A", 1.5, "1", 1, 100, 0, 0), ("A", 1, "1", 1.0, 100, 0, 0), ("A", 1, "1", 1, "100", 0, 0),
                  ("A", 1, 1.5, 1, 100, 0, 0), ("A", 1, True, 1, 100, 0, 0), ("A", 1, "1.00001", 1, 100, 0, 0)):
            self.assertEqual(PT.build_tape([p], CONS).error, "malformed_type", p)

    def test_precedence_pairs(self):
        a = ("A", 5, "1", 1, 100, 0, 1)
        cases = [([a, ("A", 4, "1", 1, 100, 0, 2)], "unordered_prints"),
                 ([("A", 1, "-1", 1, 0, 0, 0)], "negative_size_or_price"),
                 ([("A", 1, "1", 1, 0, 0, 0), ("Z", 2, "1", 1, 100, 0, 1)], "bad_multiplier"),
                 ([("Z", 1, "1.00001", 1, 100, 0, 0)], "unknown_contract"),
                 ([("A", 1, "x", 1, 100, 0, 0)], "malformed_type"),
                 ([a, ("A", 4, "1", 1.0, 100, 0, 2)], "unordered_prints")]
        for prints, code in cases:
            self.assertEqual(PT.build_tape(prints, CONS).error, code, prints)
        tape = PT.build_tape([], CONS)
        T = OPEN + NS
        self.assertEqual(M.f18_put_share(tape, T, window_s=45, at_least=1.5, delayed=True)["code"], "malformed_type")
        self.assertEqual(M.f18_put_share(tape, T, window_s=45, at_least="1/2", delayed=True)["code"], "window_not_allowed")
        self.assertEqual(M.f18_put_share(tape, T, at_least=None, at_most=None, delayed=True)["code"], "threshold_required")
        self.assertEqual(M.f1_premium_surge(tape, T, OPEN, n=1.5, delayed=True)["code"], "malformed_type")
        self.assertEqual(M.f1_premium_surge(tape, T, OPEN, delayed=True, session_in_calendar=False)["code"], "session_not_in_calendar")


class Bounded(unittest.TestCase):
    def test_large_threshold_cache_is_bounded(self):
        rng = random.Random(9)
        prints = [("A", OPEN + i, rng.randrange(1, 10 ** 6), rng.randrange(1, 500), 100, 0, i) for i in range(200_000)]
        tape = PT.build_tape(prints, CONS)
        for k in range(49):
            M.f4_large_prints(tape, OPEN + 10 ** 6, threshold_ticks=1000 * (k + 1), window_s=3600)
        self.assertLessEqual(len(tape.groups[("stock", "C")]._large), PT.LARGE_CACHE_THRESHOLDS)
        one = M.f4_large_prints(tape, OPEN + 10 ** 6, threshold_ticks=1000, window_s=3600)
        self.assertEqual(M.canonical_line(one), M.canonical_line(M.f4_large_prints(tape, OPEN + 10 ** 6, threshold_ticks=1000, window_s=3600)))

    def test_peak_memory_49_thresholds_on_1e6_tape(self):
        if os.name != "nt" or not os.environ.get("M2B_MEMORY"):
            self.skipTest("set M2B_MEMORY=1 (Windows) for the 1e6-print memory check")
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                               "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                                               "PagefileUsage", "PeakPagefileUsage")]
        rng = random.Random(3)
        prints = [("A", OPEN + i, rng.randrange(1, 10 ** 6), rng.randrange(1, 500), 100, 0, i) for i in range(1_000_000)]
        tape = PT.build_tape(prints, CONS)
        for k in range(49):
            M.f4_large_prints(tape, OPEN + 10 ** 6, threshold_ticks=1000 * (k + 1), window_s=3600)
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        self.assertLess(pmc.PeakWorkingSetSize, 1 << 30)


class SparseColumns(unittest.TestCase):
    def test_sparse_equals_dense_nonzero_entries(self):
        sc = Scenario(4)
        ids = sorted(sc.cons)
        dense = M.f17_sweep_columns(sc.tape, sc.cuts, ids, open_ns=OPEN)
        sparse = M.f17_sweep_columns(sc.tape, sc.cuts, ids, open_ns=OPEN, sparse=True)
        for T, d, sp in zip(sc.cuts, dense, sparse):
            self.assertEqual({c: v for c, v in zip(ids, d) if v}, {c: v for c, v in sp.items() if v})
            one = M.f17_columns(sc.tape, T, ids, open_ns=OPEN, sparse=True)
            self.assertEqual({c: v for c, v in one.items() if v}, {c: v for c, v in sp.items() if v})


class Exactness(unittest.TestCase):
    def test_premium_above_2_pow_53(self):
        big = 2 ** 53 + 1
        tape = PT.build_tape([("A", OPEN + NS, big, 3, 100, 0, 0), ("A", OPEN + 2 * NS, 1, 1, 100, 0, 1)], CONS)
        r = M.f17_window_premium(tape, OPEN + 10 * NS, "A", threshold_ticks=big * 300)
        self.assertEqual((r["value"]["window_premium"], r["fired"]), (big * 300 + 100, True))
        self.assertEqual(M.f1_premium_surge(tape, OPEN + 900 * NS, OPEN)["value"]["p900"], big * 300 + 100)


class PreOpen(unittest.TestCase):
    def test_clipped_windows(self):
        cons = {"C": ("C", 1, "2026-11-20", "stock"), "P": ("P", 2, "2026-12-18", "stock")}
        pre = [("C", OPEN - 100 * NS, "100.0000", 10, 100, 0, 0), ("P", OPEN - 5 * NS, "100.0000", 10, 100, 0, 1)]
        tape = PT.build_tape(pre + [("C", OPEN + 10 * NS, "1.0000", 10, 100, 0, 2)], cons)
        T = OPEN + 60 * NS
        pairs = ((lambda o: M.f4_large_prints(tape, T, threshold_ticks=1, open_ns=o), "large_count"),
                 (lambda o: M.f17_window_premium(tape, T, "C", open_ns=o), "window_premium"),
                 (lambda o: M.f18_put_share(tape, T, at_least="0", open_ns=o), "put_volume"),
                 (lambda o: M.f7_concentration(tape, T, open_ns=o), "total_premium"))
        for fn, key in pairs:
            clipped, plain = fn(OPEN), fn(OPEN - 1000 * NS)
            self.assertNotEqual(clipped["value"][key], plain["value"][key])
            self.assertEqual(clipped["coverage"]["eligible_count"], 1)
        sw = M.f7_sweep(tape, [T, OPEN + 61 * NS], open_ns=OPEN)
        self.assertEqual(M.canonical_line(sw[0]), M.canonical_line(M.f7_concentration(tape, T, open_ns=OPEN)))
        s17 = M.f17_sweep(tape, [T], ["C"], open_ns=OPEN)[0][0]
        self.assertEqual(M.canonical_line(s17), M.canonical_line(M.f17_window_premium(tape, T, "C", open_ns=OPEN)))
        self.assertEqual(M.f17_sweep_columns(tape, [T], ["C"], open_ns=OPEN), [[s17["value"]["window_premium"]]])
        self.assertEqual(M.f17_columns(tape, T, ["C"], open_ns=OPEN), [s17["value"]["window_premium"]])
        self.assertEqual(M.f18_sweep(tape, [T], at_least="0", open_ns=OPEN)[0]["value"]["put_volume"], 0)
        self.assertEqual(M.f4_sweep(tape, [T], threshold_ticks=1, open_ns=OPEN)[0]["value"]["large_count"], 1)

    def test_open_is_required_for_f4_f7_f17_f18(self):
        tape = PT.build_tape([("A", OPEN + NS, "1.0000", 5, 100, 0, 0)], CONS)
        T = OPEN + 60 * NS
        for call in (lambda: _M.f4_large_prints(tape, T), lambda: _M.f7_concentration(tape, T),
                     lambda: _M.f17_window_premium(tape, T, "A"), lambda: _M.f18_put_share(tape, T, at_least=1),
                     lambda: _M.f4_large_prints(tape, T, open_ns=1.5), lambda: _M.f7_sweep(tape, [T])[0],
                     lambda: _M.f17_sweep(tape, [T], ["A"])[0][0], lambda: _M.f18_sweep(tape, [T], at_least=1)[0]):
            r = call()
            self.assertEqual((r["status"], r["code"]), ("invalid_input", "malformed_type"))
        for call in (lambda: _M.f17_columns(tape, T), lambda: _M.f17_sweep_columns(tape, [T])):
            with self.assertRaises(ValueError):
                call()

    def test_sweeps_with_open_equal_single_on_random_streams(self):
        for seed in range(1, 1 + min(6, len(SEEDS))):
            sc = Scenario(seed)
            for W in (300, 3600):
                f7 = M.f7_sweep(sc.tape, sc.cuts, window_s=W, open_ns=OPEN)
                f17 = M.f17_sweep(sc.tape, sc.cuts, open_ns=OPEN)
                for T, a, b in zip(sc.cuts, f7, f17):
                    self.assertEqual(M.canonical_line(a), M.canonical_line(M.f7_concentration(sc.tape, T, window_s=W, open_ns=OPEN)))
                    self.assertEqual([M.canonical_line(r) for r in b], [M.canonical_line(r) for r in M.f17_many(sc.tape, T, open_ns=OPEN)])


class BeforeOpen(unittest.TestCase):
    """A cutoff before session open gives an empty window: zero counts, premiums and coverage, never negative."""

    def test_tester_repro_and_all_families(self):
        cons = {"C": ("C", 1, "2026-11-20", "stock"), "P": ("P", 2, "2026-12-18", "stock")}
        prints = [(("C", "P")[i % 2], OPEN + off * NS, "1.0000", 5, 100 if i != 3 else 10, 0, i)
                  for i, off in enumerate((-300, -90, -80, -70, -60))]
        tape = PT.build_tape(prints, cons)
        T = OPEN - 100 * NS
        r = M.f4_large_prints(tape, T, threshold_ticks=1)
        self.assertEqual((r["status"], r["value"], r["coverage"]["eligible_count"], r["fired"]),
                         ("available", {"large_count": 0, "large_premium": 0}, 0, False))
        self.assertEqual(r["coverage"], {"eligible_count": 0, "nonstandard_count": 0, "excluded_condition_count": 0,
                                         "unavailable_points": 0})
        r = M.f7_concentration(tape, T)
        self.assertEqual((r["status"], r["reason"], r["coverage"]["eligible_count"]), ("unavailable", "zero_denominator", 0))
        r = M.f18_put_share(tape, T, at_least="1/2")
        self.assertEqual((r["status"], r["reason"], r["coverage"]["eligible_count"]), ("unavailable", "zero_denominator", 0))
        r = M.f17_window_premium(tape, T, "C")
        self.assertEqual((r["value"]["window_premium"], r["fired"], r["coverage"]["eligible_count"]), (0, False, 0))
        self.assertEqual(M.f17_columns(tape, T, ["C"]), [0])
        for out in (M.f4_sweep(tape, [T], threshold_ticks=1)[0], M.f7_sweep(tape, [T])[0], M.f18_sweep(tape, [T], at_least="1/2")[0]):
            self.assertEqual(out["coverage"]["eligible_count"], 0)
        self.assertEqual(M.f17_sweep(tape, [T], ["C"])[0][0]["value"]["window_premium"], 0)
        self.assertEqual(M.f17_sweep_columns(tape, [T], ["C"]), [[0]])

    def test_counts_never_negative_on_random_streams(self):
        for seed in range(1, 1 + min(6, len(SEEDS))):
            sc = Scenario(seed)
            cuts = [OPEN - s * NS for s in (1, 60, 100, 900, 4000)] + [OPEN, OPEN + 1] + sc.cuts[:6]
            for W in (60, 300, 3600):
                results = (M.f4_sweep(sc.tape, cuts, window_s=W, threshold_ticks=1)
                           + M.f7_sweep(sc.tape, cuts, window_s=W) + M.f18_sweep(sc.tape, cuts, window_s=W, at_least="0")
                           + [r for row in M.f17_sweep(sc.tape, cuts) for r in row])
                singles = ([M.f4_large_prints(sc.tape, T, window_s=W, threshold_ticks=1) for T in cuts]
                           + [M.f7_concentration(sc.tape, T, window_s=W) for T in cuts]
                           + [M.f18_put_share(sc.tape, T, window_s=W, at_least="0") for T in cuts])
                for r in results + singles:
                    cv = r["coverage"]
                    if cv is not None:
                        self.assertTrue(all(v >= 0 for v in cv.values()), (seed, W, r))
                    v = r["value"]
                    if v:
                        self.assertTrue(all(x >= 0 for x in v.values() if isinstance(x, (int, Fraction))), (seed, W, r))
                for T, a, b in zip(cuts, M.f7_sweep(sc.tape, cuts, window_s=W), singles[len(cuts):2 * len(cuts)]):
                    self.assertEqual(M.canonical_line(a), M.canonical_line(b))
                    if T < OPEN:
                        self.assertEqual(a["coverage"]["eligible_count"], 0)


class FractionalThresholds(unittest.TestCase):
    """Exact comparison with a fractional N (a floor of N or of the ratio would flip these)."""

    def test_f4_count_against_fractional_n(self):
        tape = PT.build_tape([("A", OPEN + 100 * NS, "10.0000", 3, 100, 0, 0)], CONS)
        T = OPEN + 200 * NS
        self.assertFalse(M.f4_large_prints(tape, T, threshold_ticks=1, n="3/2")["fired"])      # count 1 < 3/2
        self.assertTrue(M.f4_large_prints(tape, T, threshold_ticks=1, n="1")["fired"])
        self.assertFalse(M.f4_large_prints(tape, T, threshold_ticks=1, n="5/4")["fired"])

    def test_f1_ratio_against_fractional_n(self):
        def tape_for(a, b):                      # p900 = (a + b) units, p60 = b units; ratio = 15 b / (a + b)
            return PT.build_tape([("A", OPEN + 400 * NS, 10000, a, 100, 0, 0), ("A", OPEN + 870 * NS, 10000, b, 100, 0, 1)], CONS)
        T = OPEN + 900 * NS
        t32 = tape_for(9, 1)                     # ratio 3/2
        for n, want in (("3/2", True), ("7/4", False), (2, False), ("5/4", True), ("1", True)):
            r = M.f1_premium_surge(t32, T, OPEN, n=n)
            self.assertEqual((r["value"]["ratio"], r["fired"]), (Fraction(3, 2), want), n)
        t2 = tape_for(13, 2)                     # ratio 2
        for n, want in (("5/2", False), ("2", True), ("9/4", False), ("3/2", True)):
            self.assertEqual(M.f1_premium_surge(t2, T, OPEN, n=n)["fired"], want, n)


class TextParameters(unittest.TestCase):
    def test_rational_text_grammar(self):
        tape = PT.build_tape([("A", OPEN + NS, "1.0000", 5, 100, 0, 0)], CONS)
        T = OPEN + 900 * NS
        for bad in ("1_0", " 3 ", "3 ", "1e3", "+3", "3/", "/3", "1/0", "\u0663", "", "1.", "--1"):
            r = M.f1_premium_surge(tape, T, OPEN, n=bad)
            self.assertEqual((r["status"], r["code"]), ("invalid_input", "malformed_type"), bad)
        for good in ("3", "-3", "3/2", ".5", "0.5", "2.50"):
            self.assertEqual(M.f1_premium_surge(tape, T, OPEN, n=good)["status"], "available", good)
        r = E.f12_episodes([], [], T, OPEN, grid_s=60.0)
        self.assertEqual((r["status"], r["code"]), ("invalid_input", "malformed_type"))


class FractionalAndCoverage(unittest.TestCase):
    def test_fractional_n_and_f12_coverage_from_prints(self):
        cons = {"A": ("C", 1, "2026-11-20", "stock"), "B": ("P", 1, "2026-11-20", "stock"), "Z": ("C", 1, "x", "etf_index")}
        prints = [("A", OPEN + 100 * NS, "10.0000", 3, 100, 0, 0), ("A", OPEN + 110 * NS, "10.0000", 3, 50, 0, 1),
                  ("B", OPEN + 120 * NS, "10.0000", 3, 100, 1, 2), ("Z", OPEN + 130 * NS, "10.0000", 3, 100, 0, 3),
                  ("A", OPEN + 1000 * NS, "10.0000", 9, 100, 0, 4)]
        tape = PT.build_tape(prints, cons)
        T = OPEN + 1000 * NS
        self.assertTrue(M.f4_large_prints(tape, T, threshold_ticks=1, n="3/2", window_s=3600)["fired"])
        self.assertFalse(M.f4_large_prints(tape, T, threshold_ticks=10 ** 9, n="3/2", window_s=3600)["fired"])
        self.assertEqual(M.f1_premium_surge(tape, T, OPEN, n="3/2")["params"]["N"], Fraction(3, 2))
        r = E.f12_from_tape(tape, T, OPEN)
        self.assertEqual(r["coverage"], {"eligible_count": 2, "nonstandard_count": 1, "excluded_condition_count": 1,
                                         "unavailable_points": r["value"]["unavailable_points"]})
        self.assertEqual(E.f12_from_tape(tape, T, OPEN, lane="etf_index")["coverage"]["eligible_count"], 1)
        cols = E.f1_grid_columns(tape, OPEN, 16)
        self.assertEqual(E.f12_episodes(*cols, T, OPEN)["coverage"]["eligible_count"], 0)


class F12Sweep(unittest.TestCase):
    def test_incremental_sweep_equals_f12_from_tape_at_every_cutoff(self):
        for seed in range(1, 1 + min(8, len(SEEDS))):
            sc = Scenario(seed, n=500, span_s=4200)
            cuts = [OPEN + s * NS for s in (0, 899, 900, 901, 960, 1500, 1500, 2400, 4200)] + sc.cuts
            for lane in LANES:
                for flt in ("all", "puts"):
                    for gap in (1, 3):
                        kw = dict(n=2, n_episodes=2, quiet_gap=gap, flt=flt, lane=lane)
                        fwd = E.f12_sweep(sc.tape, cuts, OPEN, **kw)
                        rev = E.f12_sweep(sc.tape, cuts[::-1], OPEN, **kw)[::-1]
                        for T, a, b in zip(cuts, fwd, rev):
                            one = E.f12_from_tape(sc.tape, T, OPEN, **kw)
                            self.assertEqual(M.canonical_line(a), M.canonical_line(one), (seed, T))
                            self.assertEqual(M.canonical_line(b), M.canonical_line(one))

    def test_sweep_structural_errors(self):
        out = E.f12_sweep(PT.build_tape([], {}), [OPEN + 1000 * NS, OPEN], OPEN, delayed=True)
        self.assertEqual([r["code"] for r in out], ["delayed_feed_tag"] * 2)


if __name__ == "__main__":
    unittest.main()
