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
from datetime import date, timedelta
from fractions import Fraction

import m3a_harness as H
from option_features import m3a_history as MH
from option_features import surface_series as S
from option_features import surfaceframe as SF
from option_features.chainiv import ChainContract
from option_features.flowgrid import Calendar
from option_features.flowstore import HistoryStore

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
               lane="stock", minutes=None, delta_convention=None):
        self.calls.append((series_id, metric, window_s, session_id, list(grid), total, lane, delta_convention))


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

    def test_forward_floats_never_overwrite_spot_scalars(self):
        s = floats_from_frame_inputs({30: (0.3, 0.5, 0.25)}, {30: 0.28, 91: 0.2})
        w = floats_from_frame_inputs({30: (0.9, 0.45, 0.25)}, {30: 0.99, 91: 0.5})   # forward ATM and tenors differ
        v = S.scalar_units(s, w)
        self.assertEqual(v["atm_iv_close"], 30000000)
        self.assertEqual(v["iv30_close"], 28000000)
        self.assertEqual(v["term_30_91"], 8000000)
        self.assertEqual(v["skew25_fwd"], 20000000)
        self.assertEqual(S.scalar_units(None, w), {"skew25_fwd": 20000000})

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


class GridExactness(unittest.TestCase):
    """Review fixes: huge values (v * 1e8 beyond 2^53) and the tie guard."""

    def test_huge_value_repros(self):
        for x in (123456789.12345679, 1e12 + 0.123):
            self.assertEqual(S.grid_units([x, x]), [exact_round(Fraction(x))] * 2, x)
        self.assertEqual(S.grid_units([123456789.12345679] * 2), [12345678912345679] * 2)

    def test_around_the_threshold(self):
        rnd = random.Random(11)
        for base in (2.0 ** 16, 2.0 ** 20, 1e8, 2.0 ** 26, 2.0 ** 30):
            xs = []
            for e in (-1, -1e-3, 0, 1e-3, 1):
                xs += [base * (1 + e * 1e-6) + rnd.random() * 1e-3 for _ in range(300)]
                xs += [-(base * (1 + e * 1e-6)) - rnd.random() * 1e-3 for _ in range(50)]
            xs += [base - 1e-3, base, base + 1e-3, 2.0 ** 16 - 1e-9, 2.0 ** 16 + 1e-9, 2.0 ** 20 - 1e-9, 2.0 ** 20 + 1e-9]
            self.assertEqual(S.grid_units(xs), [exact_round(Fraction(x)) for x in xs], base)

    def test_mixed_huge_and_normal_grid(self):
        xs = [0.25] * 100 + [123456789.12345679] + [0.3] * 100
        self.assertEqual(S.grid_units(xs), [exact_round(Fraction(x)) for x in xs])

    def test_ties_after_scaling_use_the_exact_path(self):
        # (k + 0.5) / 1e8 is not a dyadic tie: the float product reads a tie, the exact value is not
        xs = [(k + 0.5) / 1e8 for k in range(1, 4000)]
        want = [exact_round(Fraction(x)) for x in xs]
        self.assertNotEqual([round(x * 1e8) for x in xs], want)       # the plain float path would be wrong
        self.assertEqual(S.grid_units(xs), want)
        self.assertEqual(S.grid_units([7.5e-08]), [7])
        self.assertEqual(S.grid_units([1.65e-07]), [17])


def diff_values(rnd, n):
    """n values: IV-like, near-ties ((k + 0.5) / 1e8 and its neighbours), dyadic ties, negatives, +-0.0, zeros, values
    around 2^16, 2^20 and 1e8, plus real floats from the fixture rows."""
    xs = []
    for _ in range(n // 8):
        xs.append(rnd.uniform(0.0, 3.0))
        k = rnd.randrange(0, 3 * 10 ** 8)
        c = (k + 0.5) / 1e8
        xs.append(c)
        xs.append(math.nextafter(c, 1e9))
        xs.append(math.nextafter(c, -1e9))
        xs.append((2 * rnd.randrange(0, 10 ** 5) + 1) / 512)
        xs.append(-rnd.uniform(0.0, 3.0))
        base = rnd.choice((2.0 ** 16, 2.0 ** 20, 1e8))
        xs.append(base * (1 + rnd.uniform(-1e-6, 1e-6)))
        xs.append(rnd.choice((0.0, -0.0, 1.0, 5e-324, 1e-9, 4.9999999999999996e-09, 5e-09, 1.5e-8)))
    return xs


class Differential(unittest.TestCase):
    """grid_units against `_slow_grid` (integer half-even, the S01 helper) and the Fraction reference."""

    def _check(self, xs, grid=390):
        for i in range(0, len(xs), grid):
            g = xs[i:i + grid]
            got = S.grid_units(g)
            self.assertEqual(got, S._slow_grid(g))
            self.assertEqual(got, [exact_round(Fraction(x)) for x in g])

    def test_random_and_adversarial(self):
        self._check(diff_values(random.Random(2026), 24000))

    def test_fixture_floats(self):
        xs = []
        for fn in ("m3a_cases_units.json",):
            for r in H.rows("author2", fn):
                for v in r["inputs"].values():
                    if type(v) is float:
                        xs.append(v)
                    elif type(v) is dict:
                        xs += [x for x in v.values() if type(x) is float]
        for row in _sample_rows():
            fl = _frame(row["inputs"]["chain"], row["params"])[1].get("floats")
            if fl:
                for it in fl["expiries"].values():
                    xs += [x for x in it.values() if type(x) is float]
                xs += [x for x in fl["tenors"].values() if type(x) is float]
        self.assertGreater(len(xs), 100)
        self._check(xs, 17)
        self._check(xs, 390)


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
        self.assertEqual(st.calls[4], ("SYN1/stock/skew25", "skew25", 0, 5, [], 25000000, "stock", "spot"))
        self.assertEqual(st.calls[5][7], "forward")                    # skew25_fwd
        self.assertEqual([c[7] for c in st.calls], [None, None, None, None, "spot", "forward", None])

    def test_append_store_error_returns_code(self):
        class Bad:
            def append(self, *a, **k):
                raise ValueError("duplicate_session")
        n, code = S.append_records(Bad(), S.build_records("U", "stock", 5, self.close))
        self.assertEqual(n, 0)
        self.assertEqual(code, "duplicate_session")


def _dates(n):
    d0 = date(2025, 1, 2)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def real_store(n_sessions, k=20):
    return HistoryStore(Calendar([(d, 390) for d in _dates(n_sessions)]), k=k)


def session_inputs(i):
    """Inputs of session i with values that differ per session (so a read-back can be matched)."""
    close = floats_from_frame_inputs({30: (0.2 + i * 1e-3, 0.3 + i * 2e-3, 0.2 + i * 1e-3)},
                                     {30: 0.25 + i * 1e-3, 91: 0.2})
    fwd = floats_from_frame_inputs({30: (0.2, 0.29 + i * 3e-3, 0.2 + i * 1e-3)}, {})
    cols = ([0.3 + i * 1e-4 + m * 1e-6 for m in range(390)], [0.25 + i * 1e-4 + m * 1e-6 for m in range(390)])
    return close, fwd, cols


def records_for(i, dates, name="U", lane="stock"):
    close, fwd, cols = session_inputs(i)
    return S.build_records(name, lane, dates[i], close, fwd, minute_columns=cols)


CONV = {"skew25": "spot", "skew25_fwd": "forward"}


class AppendRealStore(unittest.TestCase):
    """D1, D2, D4: append_records against the REAL S02 HistoryStore."""

    def fill(self, n, k=20):
        dates = _dates(n + 1)
        st = real_store(n + 1, k)
        for i in range(n):
            self.assertEqual(S.append_records(st, records_for(i, dates), "stock"), (7, None))
        return st, dates

    def test_d1_forward_round_trip(self):
        st, dates = self.fill(25)
        want = [S.scalar_units(session_inputs(i)[0], session_inputs(i)[1])["skew25_fwd"] for i in range(25)]
        r = MH.scalar_baseline(st, "U/stock/skew25_fwd", "skew25_fwd", dates[25], min_sessions=20,
                               delta_convention="forward")
        self.assertEqual((r.status, r.code), ("available", None))
        self.assertEqual(r.value["n"], 25)
        self.assertEqual(list(r.value["values"]), want)

    def test_d1_conventions_are_stored(self):
        st, dates = self.fill(25)
        spot = MH.scalar_baseline(st, "U/stock/skew25", "skew25", dates[25], min_sessions=20)
        self.assertEqual(spot.status, "available")
        want = [S.scalar_units(session_inputs(i)[0])["skew25"] for i in range(25)]
        self.assertEqual(list(spot.value["values"]), want)
        a = MH.scalar_baseline(st, "U/stock/skew25", "skew25", dates[25], min_sessions=20, delta_convention="forward")
        self.assertEqual((a.status, a.code), ("invalid_input", "convention_mismatch"))
        b = MH.scalar_baseline(st, "U/stock/skew25_fwd", "skew25_fwd", dates[25], min_sessions=20)
        self.assertEqual((b.status, b.code), ("invalid_input", "convention_mismatch"))

    def test_d1_convention_free_metrics_read_fine(self):
        st, dates = self.fill(25)
        for m in ("atm_iv_close", "iv30_close", "term_30_91"):
            r = MH.scalar_baseline(st, "U/stock/" + m, m, dates[25], min_sessions=20)
            self.assertEqual((r.status, r.value["n"]), ("available", 25), m)

    def test_d1_conventions_survive_a_text_round_trip(self):
        st, dates = self.fill(21)
        back = HistoryStore.load(st.dump(), st.calendar, series_k={"U/stock/skew25_fwd": 252})
        r = MH.scalar_baseline(back, "U/stock/skew25_fwd", "skew25_fwd", dates[21], min_sessions=20,
                               delta_convention="forward")
        self.assertEqual((r.status, r.value["n"]), ("available", 21))

    def test_d2_all_sixty_sessions_are_retained(self):
        st, dates = self.fill(60)                          # store k is 20; S10 declares 252 per series id
        for m in ("atm_iv_close", "iv30_close", "skew25", "skew25_fwd", "term_30_91"):
            kw = {"delta_convention": CONV[m]} if m in CONV else {}
            r = MH.scalar_baseline(st, "U/stock/" + m, m, dates[60], min_sessions=20, **kw)
            self.assertEqual((r.status, r.value["n"]), ("available", 60), m)
        r = MH.same_minute_column(st, "U/stock/atm_iv", "atm_iv", dates[60], 100, min_sessions=20)
        self.assertEqual((r.status, r.value["n"]), ("available", 60))
        for m in ("atm_iv", "iv30", "atm_iv_close", "skew25", "skew25_fwd"):
            self.assertEqual(st.k_of("U/stock/" + m), 252)

    def test_d2_declares_only_when_needed_and_never_lowers(self):
        calls = []

        class Spy:
            def __init__(self, k):
                self.k = k

            def k_of(self, sid):
                return self.k

            def add_series(self, sid, k):
                calls.append((sid, k))

            def append(self, *a, **kw):
                pass
        recs = records_for(0, _dates(2))
        self.assertEqual(S.append_records(Spy(252), recs, "stock"), (7, None))
        self.assertEqual(calls, [])
        self.assertEqual(S.append_records(Spy(300), recs, "stock"), (7, None))
        self.assertEqual(calls, [])
        self.assertEqual(S.append_records(Spy(60), recs, "stock"), (7, None))
        self.assertEqual(sorted(calls), sorted((r[0], 252) for r in recs))

    def test_d2_declared_before_first_append(self):
        order = []

        class Spy:
            def k_of(self, sid):
                return 20

            def add_series(self, sid, k):
                order.append(("add", sid))

            def append(self, sid, *a, **kw):
                order.append(("append", sid))
        S.append_records(Spy(), records_for(0, _dates(2)), "stock")
        self.assertEqual(len({o[1] for o in order}), 7)
        for sid in {o[1] for o in order}:
            self.assertEqual([o[0] for o in order if o[1] == sid][0], "add", sid)

    def test_d4_prevalidated_batches_commit_nothing(self):
        for code, bump in (("duplicate_session", 0), ("out_of_order_append", 1)):
            for j in range(7):
                st, dates = self.fill(2)
                batch = records_for(2, dates)
                # series j already holds session 2 (duplicate) or session 3 (out of order)
                sid, metric = batch[j][0], batch[j][1]
                st.append(sid, metric, 0, dates[2 + bump], batch[j][4], total=batch[j][5], lane="stock",
                          delta_convention=CONV.get(metric))
                before = st.content_hash()
                got = S.append_records(st, batch, "stock")
                self.assertEqual(tuple(got), (0, code), (code, j))
                self.assertEqual(got.committed, 0)
                self.assertFalse(got.partial)
                self.assertEqual(st.content_hash(), before, (code, j))

    def test_d4_structural_failures_are_prevalidated(self):
        st, dates = self.fill(2)
        batch = records_for(2, dates)
        before = st.content_hash()
        for j in range(7):
            bad = list(batch)
            r = list(bad[j])
            r[3] = "1999-01-01"                                # not in the calendar
            bad[j] = tuple(r)
            self.assertEqual(tuple(S.append_records(st, bad, "stock")), (0, "session_not_in_calendar"), j)
            r[3] = dates[2]
            r[4] = [1] * 391                                   # longer than the session
            bad[j] = tuple(r)
            self.assertEqual(tuple(S.append_records(st, bad, "stock")), (0, "record_length_mismatch"), j)
            self.assertEqual(st.content_hash(), before, j)
        self.assertEqual(tuple(S.append_records(st, batch, "etf_index")), (0, "lane_mismatch"))   # ids say stock
        self.assertEqual(st.content_hash(), before)
        self.assertEqual(S.append_records(st, batch, "stock"), (7, None))

    def test_d4_a_batch_that_repeats_a_series_session_is_rejected_whole(self):
        st, dates = self.fill(2)
        batch = records_for(2, dates)
        before = st.content_hash()
        got = S.append_records(st, batch + [batch[3]], "stock")
        self.assertEqual(tuple(got), (0, "duplicate_session"))
        self.assertEqual(st.content_hash(), before)

    def _lane_trap(self, j):
        """A real store whose series j holds a record of another lane: not visible through the public read API, so the
        store (not the pre-validation) raises lane_mismatch at record j."""
        dates = _dates(4)
        batch = records_for(2, dates)
        st = real_store(4)
        st.append(batch[j][0], batch[j][1], 0, dates[0], [], total=1, lane="etf_index")
        return st, dates, batch

    def test_d4_store_error_mid_batch_reports_committed_count(self):
        for j in range(7):
            st, dates, batch = self._lane_trap(j)
            got = S.append_records(st, batch, "stock")
            self.assertEqual(tuple(got), (j, "lane_mismatch"), j)
            self.assertEqual(got.committed, j)
            self.assertEqual(got.partial, j > 0)
            stored = [b[0] for b in batch if dates[2] in st.retained().get("%s|%s|0" % (b[0], b[1]), [])]
            self.assertEqual(stored, [b[0] for b in batch[:j]])

    def test_d4_retry_after_partial_commit_is_a_duplicate(self):
        st, dates, batch = self._lane_trap(4)
        self.assertEqual(tuple(S.append_records(st, batch, "stock")), (4, "lane_mismatch"))
        self.assertEqual(tuple(S.append_records(st, batch, "stock")), (0, "duplicate_session"))

    def test_d4_malformed_records(self):
        st = real_store(3)
        before = st.content_hash()
        for bad in ([("a", "b")], [None], [("U/stock/iv30", "iv30", 0, _dates(3)[0], [1], 1, 9)], 5):
            got = S.append_records(st, bad, "stock")
            self.assertEqual(tuple(got), (0, "malformed_type"), bad)
        self.assertEqual(S.append_records(st, [], "stock"), (0, None))
        self.assertEqual(st.content_hash(), before)


class Boom(dict):
    def __getitem__(self, k):
        raise RuntimeError("boom")

    def get(self, *a):
        raise RuntimeError("boom")

    def items(self):
        raise RuntimeError("boom")


class BoomList:
    def __iter__(self):
        raise RuntimeError("boom")

    def __len__(self):
        raise RuntimeError("boom")


class RaisingCaller(unittest.TestCase):
    """D5: caller data whose access raises any Exception never escapes the builder."""

    def test_scalar_units(self):
        good = floats_from_frame_inputs({30: (0.3, 0.5, 0.25)}, {30: 0.28, 91: 0.2})
        for bad in (Boom(), {"expiries": Boom(), "tenors": Boom()}, {"expiries": {"30": Boom()}, "tenors": Boom()},
                    {"expiries": {"30": {"atm_iv": 0.3, "put25_iv": 0.5, "call25_iv": Boom()}}, "tenors": Boom()}):
            S.scalar_units(bad, bad)
        self.assertEqual(S.scalar_units(Boom(), good), {"skew25_fwd": 25000000})
        self.assertEqual(S.scalar_units(good, Boom())["skew25"], 25000000)

    def test_minute_values(self):
        for bad in (Boom(), {"expiries": Boom(), "tenors": Boom()}, {"expiries": {"30": Boom()}, "tenors": Boom()}):
            self.assertEqual(S.minute_values_from_floats(bad), (None, None))
        self.assertEqual(S.minute_values_from_floats({"expiries": {"30": {"atm_iv": 0.3}}, "tenors": Boom()}),
                         (0.3, None))

    def test_build_records(self):
        good = floats_from_frame_inputs({30: (0.3, 0.5, 0.25)}, {30: 0.28, 91: 0.2})
        self.assertEqual(S.build_records("U", "stock", 1, Boom()), [])
        self.assertEqual(S.build_records("U", "stock", 1, Boom(), Boom(), minute_floats=[Boom(), None]), [
            ("U/stock/atm_iv", "atm_iv", 0, 1, [0, 0], 0), ("U/stock/iv30", "iv30", 0, 1, [0, 0], 0)])
        recs = S.build_records("U", "stock", 1, good, Boom(), minute_columns=(BoomList(), BoomList()))
        self.assertEqual([r[1] for r in recs], ["atm_iv", "iv30", "atm_iv_close", "iv30_close", "skew25",
                                                "term_30_91"])
        self.assertEqual(recs[0][4], [])
        self.assertEqual(S.grid_units(BoomList()), [])
        self.assertEqual(S.grid_units([0.1, Boom()]), [10000000, 0])


class GuardBand(unittest.TestCase):
    """D3: the proof of the fast path's guard band (see grid_units). For |v| < 2^16, t = v * 10^8 (real) and the float
    u = fl(fl(v * 1e8) + 0.5): each operation errs by at most 2^-53 relative (1e8 is exactly representable), so
    |u - (t + 1/2)| <= (|t| + 1) * 2^-52. The band half-width is W = (|v|max * 1e8 + 1) * 2^-50, four times that. An
    entry whose frac(u) is within W of 0 or 1 is rounded exactly; outside the band floor(u) = floor(t + 1/2) (no
    integer lies between u and t + 1/2), which is round-half-up of t, and equals half-even because t + 1/2 is not an
    integer there. Every tie (t + 1/2 integral) has frac(u) within the error of 0 or 1, hence inside the band."""

    def test_error_bound_random_and_adversarial(self):
        rnd = random.Random(5)
        xs = [rnd.uniform(-1.0, 1.0) * 10 ** rnd.uniform(-9, 4.8) for _ in range(6000)]
        xs += [(k + 0.5) / 1e8 for k in rnd.sample(range(10 ** 9), 600)]
        xs += [math.nextafter((k + 0.5) / 1e8, 9.0) for k in rnd.sample(range(10 ** 9), 300)]
        xs += [math.nextafter((k + 0.5) / 1e8, -9.0) for k in rnd.sample(range(10 ** 9), 300)]
        xs += [(2 * k + 1) / 2 ** rnd.randrange(1, 40) for k in rnd.sample(range(10 ** 6), 400)]
        xs += [2.0 ** 16 - 2.0 ** -37 * i for i in range(1, 51)] + [-(2.0 ** 16 - 2.0 ** -37 * i) for i in range(1, 51)]
        worst = 0.0
        for v in xs:
            if abs(v) >= 2.0 ** 16:
                continue
            u = v * 1e8 + 0.5
            err = abs(Fraction(u) - (Fraction(v) * 10 ** 8 + Fraction(1, 2)))
            bound = (abs(Fraction(v)) * 10 ** 8 + 1) * Fraction(1, 2 ** 52)
            self.assertLessEqual(err, bound, v)
            worst = max(worst, float(err / bound))
        self.assertLessEqual(worst, 1.0)

    def test_window_is_four_times_the_bound(self):
        self.assertEqual(S._window(0.0, 0.0), 2.0 ** -50)
        self.assertAlmostEqual(S._window(1.0, 0.5), (1e8 + 1) * 2.0 ** -50, delta=1e-12)
        self.assertLess(S._window(2.0 ** 16 - 1e-9, 0.0), 0.01)

    def test_band_catches_every_tie_and_near_tie(self):
        rnd = random.Random(9)
        xs = [(2 * k + 1) / 2 ** rnd.randrange(1, 28) for k in range(0, 4000, 3)]
        xs += [-x for x in xs[:500]]
        xs += [math.nextafter(x, 4.0) for x in xs[:500]] + [math.nextafter(x, -4.0) for x in xs[:500]]
        got = S.grid_units(xs)
        self.assertEqual(got, [exact_round(Fraction(x)) for x in xs])
        self.assertEqual(got, S._slow_grid(xs))

    def test_random_full_precision_has_almost_no_exact_path(self):
        rnd = random.Random(1)
        xs = [rnd.uniform(0.1, 1.0) for _ in range(20000)]
        calls = []
        orig = S.round_units
        S.round_units = lambda x: (calls.append(x), orig(x))[1]
        try:
            self.assertEqual(S.grid_units(xs), [exact_round(Fraction(x)) for x in xs])
        finally:
            S.round_units = orig
        self.assertLess(len(calls), 10)                        # the old 0.01 window sent about 2 percent (400)


class W08(unittest.TestCase):
    """Perf W08 (M3A-B6): 252 sessions x 103 names x 7 series = 181,692 records BUILT from minute columns, then handed
    to a NULL store: W08 gates the series build only (the real store append belongs to S02's B6 gate; the end-to-end
    figure with a real HistoryStore is printed as informational). The workload is realistic: random full-precision
    IV floats (not smooth), a different column per name and session. Floor 25,000 records/s at p5, hard 5,000."""

    SESSIONS = 2

    def _workload(self):
        rnd = random.Random(808)
        names = ["SYN%03d" % i for i in range(103)]
        cols = [([rnd.uniform(0.1, 1.0) for _ in range(390)], [rnd.uniform(0.1, 1.0) for _ in range(390)])
                for _ in range(self.SESSIONS * len(names))]

        def u():
            return rnd.uniform(0.1, 1.0)
        closes = [(floats_from_frame_inputs({7: (u(), u(), u()), 30: (u(), u(), u())}, {30: u(), 91: u()}),
                   floats_from_frame_inputs({7: (u(), u(), u())}, {}))
                  for _ in cols]
        return names, cols, closes

    def _run(self, names, cols, closes, store, dates=None):
        n = 0
        t0 = time.perf_counter()
        for i, c in enumerate(cols):
            close, fwd = closes[i]
            sid = i // len(names) if dates is None else dates[i // len(names)]
            recs = S.build_records(names[i % len(names)], "stock", sid, close, fwd, minute_columns=c)
            S.append_records(store, recs, "stock")
            n += len(recs)
        return n, time.perf_counter() - t0

    def _measure(self, names, cols, closes, store):
        self._run(names, cols, closes, store)
        gc.collect()
        gc.freeze()                                                    # as the runner does after load
        rates = []
        try:
            for _ in range(REPEATS):
                n, dt = self._run(names, cols, closes, store)
                rates.append(n / dt)
        finally:
            gc.unfreeze()
        rates.sort()
        return rates

    def test_w08_throughput(self):
        names, cols, closes = self._workload()

        class Null:
            def append(self, *a, **k):
                pass
        # TODO: use m3a_harness.best_of once the perf-smoke chore (PR 123) is on main; this local loop is the same
        # rule: best of up to 3 attempts, floors unchanged.
        best = None
        for _ in range(3):
            rates = self._measure(names, cols, closes, Null())
            p5 = rates[max(0, math.ceil(0.05 * len(rates)) - 1)]
            if best is None or p5 > best[0]:
                best = (p5, rates)
            if p5 >= W08_FLOOR:
                break
        p5, rates = best
        full_n = 252 * 103 * 7
        self.assertEqual(full_n, 181692)
        med = statistics.median(rates)
        print("\nW08 records/s: p5 %.0f p50 %.0f min %.0f (budget >= %.0f, hard %.0f); full set %d records ~ %.2f s at p50"
              % (p5, med, rates[0], W08_FLOOR, W08_HARD, full_n, full_n / med))
        self.assertGreaterEqual(p5, W08_HARD)
        self.assertGreaterEqual(p5, W08_FLOOR)

    def test_w08_informational_end_to_end(self):
        """Not gated: build + append into a real HistoryStore (the append gate is S02's B6)."""
        names, cols, closes = self._workload()
        k = len(names)
        names, cols, closes = names[:20], cols[:20] + cols[k:k + 20], closes[:20] + closes[k:k + 20]
        dates = _dates(2)
        st = HistoryStore(Calendar([(d, 390) for d in dates]), k=20)
        n, dt = self._run(names, cols, closes, st, dates)
        print("W08 informational, build + real HistoryStore append (%d records): %.0f records/s" % (n, n / dt))
        self.assertEqual(n, 7 * 40)


if __name__ == "__main__":
    unittest.main()
