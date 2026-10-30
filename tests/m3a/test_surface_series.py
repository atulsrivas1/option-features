"""S10: series builder (`option_features.surface_series`). First owner of perf row W08 (M3A-B6); no fixture row.

Inputs are `stats['floats']` dicts of S05 (R-189): {'expiries': {days: {atm_iv, put25_iv, call25_iv}},
'tenors': {t: float|None}}. Until the S05 patch is on main, `floats_from_frame_inputs` below builds them from
fixture values (test-local helper). The store is a minimal FAKE implementing only `append` as the plan states it;
S02 (the real history store) is not used here. Expectations come from the author2 units rows (M3A-U-010, 012,
018, 019, V9-036 values) and from an exact Fraction reference written here, never from the library.

Label: synthetic workload, relative engineering budget. mock-data qualification only: passed on independently
authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12.
"""
import gc
import math
import random
import statistics
import time
import unittest
from fractions import Fraction

import m3a_harness as H
from option_features import surface_series as S
from option_features import surfaceframe as SF
from option_features.chainiv import ChainContract

W08_FLOOR, W08_HARD = 25000.0, 5000.0
REPEATS = 30


def floats_from_frame_inputs(expiries, tenors):
    """expiries {days: (atm, put, call)}, tenors {t: float|None} -> the S05 stats['floats'] shape."""
    return {"expiries": {str(d): {"atm_iv": a, "put25_iv": p, "call25_iv": c} for d, (a, p, c) in expiries.items()},
            "tenors": {str(t): v for t, v in tenors.items()}}


def exact_round(fr):
    q, r = divmod(fr * 10 ** 8, 1)
    q = int(q)
    if r > Fraction(1, 2) or (r == Fraction(1, 2) and q & 1):
        q += 1
    return q


class FakeStore:
    def __init__(self):
        self.calls = []

    def append(self, series_id, metric, window_s, session_id, grid, total=None, complete=True, grid_idx=None,
               lane="stock", minutes=None):
        self.calls.append((series_id, metric, window_s, session_id, list(grid), total, lane))


class Scalars(unittest.TestCase):
    def test_u010_round_once(self):
        f = floats_from_frame_inputs({30: (0.2, 0.3000000049, 0.1000000051)}, {30: 0.2, 91: 0.2})
        self.assertEqual(S.scalar_units(f)["skew25"], 20000000)       # rounded-first would give 19,999,999

    def test_v9_036_round_once(self):
        f = floats_from_frame_inputs({30: (0.2, 0.2000000049, 0.1000000051)}, {})
        self.assertEqual(S.scalar_units(f)["skew25"], 10000000)

    def test_tie_minus_3_512(self):
        f = floats_from_frame_inputs({30: (0.2, 0.248046875, 0.25390625)}, {})
        self.assertEqual(S.scalar_units(f)["skew25"], -585938)         # half-even, not -585,937

    def test_tie_positive_even(self):
        f = floats_from_frame_inputs({30: (0.2, 0.25, 0.248046875)}, {})
        self.assertEqual(S.scalar_units(f)["skew25"], 195312)

    def test_negative_zero(self):
        f = floats_from_frame_inputs({30: (0.2, 0.1, 0.100000004)}, {})
        v = S.scalar_units(f)["skew25"]
        self.assertEqual(v, 0)
        self.assertEqual(str(v), "0")

    def test_stored_integer_rows(self):
        f = floats_from_frame_inputs({7: (0.3500000049, None, None)}, {30: -0.0100000051})
        v = S.scalar_units(f)
        self.assertEqual(v["atm_iv_close"], 35000000)                  # U-018
        self.assertEqual(v["iv30_close"], -1000001)                    # U-019

    def test_term_and_nearest_expiry(self):
        f = floats_from_frame_inputs({60: (0.5, 0.6, 0.4), 14: (0.21, 0.3, 0.2), 30: (0.3, 0.5, 0.1)},
                                     {30: 0.25, 91: 0.2})
        v = S.scalar_units(f)
        self.assertEqual(v["atm_iv_close"], 21000000)                  # nearest = 14 days
        self.assertEqual(v["skew25"], 10000000)
        self.assertEqual(v["term_30_91"], 5000000)

    def test_nearest_eligible_skips_unavailable(self):
        f = floats_from_frame_inputs({7: (None, None, None), 30: (0.3, 0.5, 0.25)}, {})
        v = S.scalar_units(f)
        self.assertEqual(v["atm_iv_close"], 30000000)
        self.assertEqual(v["skew25"], 25000000)

    def test_missing_side_omitted(self):
        f = floats_from_frame_inputs({30: (0.3, None, 0.25)}, {30: None, 91: 0.2})
        v = S.scalar_units(f)
        self.assertNotIn("skew25", v)
        self.assertNotIn("iv30_close", v)
        self.assertNotIn("term_30_91", v)
        self.assertIn("atm_iv_close", v)

    def test_forward_convention(self):
        s = floats_from_frame_inputs({30: (0.3, 0.5, 0.25)}, {})
        w = floats_from_frame_inputs({30: (0.3, 0.45, 0.25)}, {})
        v = S.scalar_units(s, w)
        self.assertEqual(v["skew25"], 25000000)
        self.assertEqual(v["skew25_fwd"], 20000000)
        self.assertNotIn("skew25_fwd", S.scalar_units(s))

    def test_exact_difference_matches_fraction_reference(self):
        rnd = random.Random(7)
        for _ in range(3000):
            p, c = rnd.uniform(0.05, 1.5), rnd.uniform(0.05, 1.5)
            if rnd.random() < 0.3:
                p = round(p * 2 ** 12) / 2 ** 12
                c = round(c * 2 ** 12) / 2 ** 12
            f = floats_from_frame_inputs({30: (0.3, p, c)}, {30: p, 91: c})
            v = S.scalar_units(f)
            want = exact_round(Fraction(p) - Fraction(c))
            self.assertEqual(v["skew25"], want)
            self.assertEqual(v["term_30_91"], want)

    def test_hostile_never_raises(self):
        bad = [None, {}, [], 5, "x", {"expiries": 3, "tenors": 4}, {"expiries": {"x": 1}, "tenors": {"30": "a"}},
               {"expiries": {"30": {"atm_iv": float("nan"), "put25_iv": float("inf"), "call25_iv": True}},
                "tenors": {"30": float("nan"), "91": float("-inf")}}]
        for b in bad:
            self.assertEqual(S.scalar_units(b, b), {})


class Grids(unittest.TestCase):
    def test_values_and_unavailable(self):
        self.assertEqual(S.grid_units([0.3500000049, None, -0.0100000051, 0.0]), [35000000, 0, -1000001, 0])

    def test_tie_in_grid_uses_exact_path(self):
        self.assertEqual(S.grid_units([0.248046875 - 0.25390625, 0.5, 1 / 512]), [-585938, 50000000, 195312])

    def test_hostile_grid(self):
        self.assertEqual(S.grid_units([float("nan"), float("inf"), "a", True, 0.1]), [0, 0, 0, 0, 10000000])
        self.assertEqual(S.grid_units(None), [])

    def test_random_vs_reference(self):
        rnd = random.Random(3)
        g = [rnd.uniform(0.0, 3.0) for _ in range(5000)] + [k / 2 ** 20 for k in range(0, 4000, 7)]
        self.assertEqual(S.grid_units(g), [exact_round(Fraction(x)) for x in g])


FRAME_KEYS = ("tenors", "delta_convention", "delta_target", "min_strikes", "min_coverage", "mode", "lane",
              "feed_delay_tag", "stale_limit_ns", "evaluation_ns")


def _frame(row_chain, params):
    ch = row_chain
    cs = [ChainContract(c["contract_id"], c["expiry_days"], c["right"], c["strike"], c["bid"], c["ask"],
                        c["event_ns"], c["known_at_ns"], c["style"], c["condition"]) for c in ch["contracts"]]
    stats = {}
    p = {k: params[k] for k in FRAME_KEYS if k in params}
    res = SF.surface_frame(cs, ch["spot"], ch["rate"], ch["dividend_yield"], ch["cutoff_ns"], p, stats=stats)
    return res, stats


def _units(text):
    return int(Fraction(text) * 10 ** 8)


def _sample_rows():
    """20 chain rows: 14 of author1 (surface, coverage, american, delta25, tenors; evenly spaced) and 6 of author3
    (v5, v6, v8, v11, v21, v10: first row each)."""
    out = []
    a1 = []
    for fn in ("m3a_cases_surface.json", "m3a_cases_coverage.json", "m3a_cases_american.json",
               "m3a_cases_delta25.json", "m3a_cases_tenors.json"):
        a1.extend(r for r in H.rows("author1", fn) if "chain" in r["inputs"])
    step = max(1, len(a1) // 14)
    out.extend(a1[::step][:14])
    for fn in ("m3a_cases_v5.json", "m3a_cases_v6.json", "m3a_cases_v8.json", "m3a_cases_v11.json",
               "m3a_cases_v21.json", "m3a_cases_v10.json"):
        out.append(next(r for r in H.rows("author3", fn) if "chain" in r["inputs"]))
    return out


class EndToEnd(unittest.TestCase):
    """Real S05 `surface_frame` -> `stats['floats']` -> series scalars. Expectations: the frame's own 8-decimal text
    (one rounding of the same float: exact for single values) and an exact Fraction difference of the floats."""

    def test_sample_of_20_rows(self):
        rows_ = _sample_rows()
        self.assertEqual(len(rows_), 20)
        seen_scalars = 0
        for row in rows_:
            res, stats = _frame(row["inputs"]["chain"], row["params"])
            if "floats" not in stats:
                continue
            fl = stats["floats"]
            sc = S.scalar_units(fl)
            avail = [(int(d), it) for d, it in res.frame["expiries"].items() if it["atm_iv"] is not None]
            if not avail:
                self.assertNotIn("atm_iv_close", sc, row["id"])
                continue
            d0, it = min(avail)
            self.assertEqual(sc["atm_iv_close"], _units(it["atm_iv"]), row["id"])
            f0 = fl["expiries"][str(d0)]
            if f0["put25_iv"] is not None and f0["call25_iv"] is not None:
                want = exact_round(Fraction(f0["put25_iv"]) - Fraction(f0["call25_iv"]))
                self.assertEqual(sc["skew25"], want, row["id"])
                self.assertLessEqual(abs(sc["skew25"] - (_units(it["put25_iv"]["value"]) -
                                                         _units(it["call25_iv"]["value"]))), 1, row["id"])
                seen_scalars += 1
            t30, t91 = res.frame["tenors"].get("30"), res.frame["tenors"].get("91")
            if t30 and t30["iv"] is not None:
                self.assertEqual(sc["iv30_close"], _units(t30["iv"]), row["id"])
                if t91 and t91["iv"] is not None:
                    want = exact_round(Fraction(fl["tenors"]["30"]) - Fraction(fl["tenors"]["91"]))
                    self.assertEqual(sc["term_30_91"], want, row["id"])
            recs = S.build_records("E2E", "stock", 1, fl)
            self.assertTrue(all(r[0].startswith("E2E/stock/") for r in recs), row["id"])
        self.assertGreater(seen_scalars, 3)

    def test_minute_columns_from_real_frames(self):
        row = next(r for r in H.rows("author3", "m3a_cases_v8.json") if "chain" in r["inputs"])
        frames = [_frame(row["inputs"]["chain"], row["params"])[1]["floats"] for _ in range(3)]
        atm, iv30 = zip(*(S.minute_values_from_floats(f) for f in frames))
        self.assertTrue(all(type(v) is float for v in atm))
        a = S.build_records("E2E", "stock", 1, frames[0], minute_floats=frames)
        b = S.build_records("E2E", "stock", 1, frames[0], minute_columns=(list(atm), list(iv30)))
        self.assertEqual(a, b)

    def _stubbed(self, put, call):
        row = next(r for r in H.rows("author3", "m3a_cases_v8.json") if "chain" in r["inputs"])
        from unittest import mock

        def fake(strikes, ivs, atm, S_, r, q, days, right, conv, owner):
            return {"status": "available", "reason": None, "value": put if right == "put" else call,
                    "strikes_used": [], "evaluations": 0}
        with mock.patch.object(SF, "delta25_point", fake):
            res, stats = _frame(row["inputs"]["chain"], row["params"])
        return S.scalar_units(stats["floats"])

    def test_u010_through_real_frame(self):
        self.assertEqual(self._stubbed(0.3000000049, 0.1000000051)["skew25"], 20000000)

    def test_tie_minus_3_512_through_real_frame(self):
        self.assertEqual(self._stubbed(0.248046875, 0.25390625)["skew25"], -585938)

    def test_v9_036_through_real_frame(self):
        self.assertEqual(self._stubbed(0.2000000049, 0.1000000051)["skew25"], 10000000)


class MinuteValue(unittest.TestCase):
    def test_rule(self):
        f = floats_from_frame_inputs({60: (0.5, 0.6, 0.4), 14: (0.21, 0.3, 0.2)}, {30: 0.25, 91: 0.2})
        self.assertEqual(S.minute_values_from_floats(f), (0.21, 0.25))

    def test_skips_unusable_expiry_and_tenor(self):
        f = floats_from_frame_inputs({7: (None, None, None), 30: (0.3, 0.5, 0.25)}, {30: None})
        self.assertEqual(S.minute_values_from_floats(f), (0.3, None))

    def test_hostile(self):
        for b in (None, {}, 5, "x", {"expiries": 3, "tenors": 4}, {"expiries": {"30": {"atm_iv": float("nan")}},
                                                                     "tenors": {"30": float("inf")}}):
            self.assertEqual(S.minute_values_from_floats(b), (None, None))

    def test_frames_path_uses_the_rule(self):
        frames = [floats_from_frame_inputs({30: (0.3, 0.5, 0.25), 7: (0.2, 0.5, 0.25)}, {30: 0.28}), None]
        self.assertEqual(S._minute_pair(frames), ([0.2, None], [0.28, None]))


class Records(unittest.TestCase):
    def setUp(self):
        self.close = floats_from_frame_inputs({30: (0.3, 0.5, 0.25)}, {30: 0.28, 91: 0.2})
        self.fwd = floats_from_frame_inputs({30: (0.3, 0.45, 0.25)}, {})
        m = [floats_from_frame_inputs({30: (0.3 + i / 1000, 0.5, 0.25)}, {30: 0.28 + i / 1000, 91: 0.2})
             for i in range(3)]
        m.insert(1, None)
        self.minutes = m

    def test_series_ids_and_shapes(self):
        self.assertEqual(S.series_id("SYN1", "stock", "iv30"), "SYN1/stock/iv30")
        recs = S.build_records("SYN1", "stock", 5, self.close, self.fwd, self.minutes)
        self.assertEqual([r[1] for r in recs], ["atm_iv", "iv30", "atm_iv_close", "iv30_close", "skew25",
                                                "skew25_fwd", "term_30_91"])
        by = {r[1]: r for r in recs}
        self.assertEqual(by["skew25"], ("SYN1/stock/skew25", "skew25", 0, 5, [], 25000000))
        self.assertEqual(by["atm_iv"][4], [30000000, 0, 30100000, 30200000])
        self.assertEqual(by["iv30"][4], [28000000, 0, 28100000, 28200000])
        self.assertEqual(by["atm_iv"][2], 0)
        self.assertEqual(by["atm_iv"][5], sum(by["atm_iv"][4]))

    def test_minute_columns_equal_frames(self):
        a = S.build_records("SYN1", "stock", 5, self.close, self.fwd, self.minutes)
        cols = ([30000000 / 1e8, None, 0.3 + 1 / 1000, 0.3 + 2 / 1000], [0.28, None, 0.28 + 1 / 1000, 0.28 + 2 / 1000])
        b = S.build_records("SYN1", "stock", 5, self.close, self.fwd, minute_columns=cols)
        self.assertEqual(a, b)

    def test_no_minutes_no_grid_records(self):
        recs = S.build_records("SYN1", "etf_index", 5, self.close)
        self.assertEqual([r[1] for r in recs], ["atm_iv_close", "iv30_close", "skew25", "term_30_91"])

    def test_unavailable_close_gives_no_scalar_records(self):
        self.assertEqual(S.build_records("SYN1", "stock", 5, None), [])

    def test_hostile_args(self):
        self.assertEqual(S.build_records(None, "stock", 5, self.close), [])
        self.assertEqual(S.build_records("U", "stock", 5, self.close, minute_floats=7)[0][1], "atm_iv_close")

    def test_append_through_fake_store(self):
        recs = S.build_records("SYN1", "stock", 5, self.close, self.fwd, self.minutes)
        st = FakeStore()
        self.assertEqual(S.append_records(st, recs, "stock"), (7, None))
        self.assertEqual(len(st.calls), 7)
        self.assertEqual(st.calls[4], ("SYN1/stock/skew25", "skew25", 0, 5, [], 25000000, "stock"))

    def test_append_store_error_returns_code(self):
        class Bad:
            def append(self, *a, **k):
                raise ValueError("duplicate_session")
        n, code = S.append_records(Bad(), S.build_records("U", "stock", 5, self.close))
        self.assertEqual(n, 0)
        self.assertEqual(code, "duplicate_session")


class W08(unittest.TestCase):
    """Perf W08 (M3A-B6): 252 sessions x 103 names x 7 series = 181,692 records built and appended to a FAKE
    store (the real store append cost is S02's and is not in this number). Floor 25,000 records/s at p5, hard 5,000.
    Each measured pass builds 2 sessions x 103 names x 7 series with two dense 390-minute grids per name-session."""

    def test_w08_throughput(self):
        names = ["SYN%03d" % i for i in range(103)]
        base = [floats_from_frame_inputs({30: (0.2 + 0.0001 * m, 0.3, 0.2)}, {30: 0.25 + 0.0001 * m, 91: 0.2})
                for m in range(390)]
        close = floats_from_frame_inputs({7: (0.21, 0.3, 0.2), 30: (0.25, 0.31, 0.21)}, {30: 0.25, 91: 0.2})
        fwd = floats_from_frame_inputs({7: (0.21, 0.29, 0.2)}, {})

        class Null:
            def append(self, *a, **k):
                pass
        st = Null()

        cols = ([f["expiries"]["30"]["atm_iv"] for f in base], [f["tenors"]["30"] for f in base])

        def run(sessions, frames=False):
            n = 0
            t0 = time.perf_counter()
            for s in range(sessions):
                for nm in names:
                    if frames:
                        recs = S.build_records(nm, "stock", s, close, fwd, base)
                    else:
                        recs = S.build_records(nm, "stock", s, close, fwd, minute_columns=cols)
                    S.append_records(st, recs, "stock")
                    n += len(recs)
            return n, time.perf_counter() - t0

        run(1)
        gc.collect()
        gc.freeze()                                                    # as the runner does after load
        rates = []
        try:
            for _ in range(REPEATS):
                n, dt = run(2)
                rates.append(n / dt)
        finally:
            gc.unfreeze()
        rates.sort()
        p5 = rates[max(0, math.ceil(0.05 * len(rates)) - 1)]
        full_n = 252 * 103 * 7
        self.assertEqual(full_n, 181692)
        med = statistics.median(rates)
        print("\nW08 records/s: p5 %.0f p50 %.0f min %.0f (budget >= %.0f, hard %.0f); full set %d records ~ %.2f s at p50"
              % (p5, med, rates[0], W08_FLOOR, W08_HARD, full_n, full_n / med))
        n, dt = run(2, True)
        print("W08 informational (per-minute frame dicts read inside the builder, not gated): %.0f records/s" % (n / dt))
        self.assertGreaterEqual(p5, W08_HARD)
        self.assertGreaterEqual(p5, W08_FLOOR)


if __name__ == "__main__":
    unittest.main()
