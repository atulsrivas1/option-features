"""S05 surface frame M3A-0: whole-row checks of the author1 rows S05 first-owns (SUR-*, COV-01..34, AME-*, D25-*
except D25-V1..V7, TEN-*: 313 rows), hostile-input guards, and perf row W02 (gate M3A-B1, per delta convention).
One test method per row id. D25-V1..V7 and COV-35..37 are first-owned by S09 and are not run here.

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12
"""
import json
import math
import statistics
import time
import unittest
from fractions import Fraction

import m3a_harness as H
from option_features.chainiv import ChainContract
from option_features import m3a_common as C
from option_features import surfaceframe as SF

FILES = ("m3a_cases_surface.json", "m3a_cases_coverage.json", "m3a_cases_american.json",
         "m3a_cases_delta25.json", "m3a_cases_tenors.json")
REPEATS = 30
B1_BUDGET_S = 0.1
B12_BUDGET = 200


def owned_rows():
    out = []
    for fn in FILES:
        for r in H.rows("author1", fn):
            if H.owners_of("author1", fn, r["id"]) == ["S05"]:
                out.append(r)
    return out


def contracts_of(raw):
    return [ChainContract(c["contract_id"], c["expiry_days"], c["right"], c["strike"], c["bid"], c["ask"],
                          c["event_ns"], c["known_at_ns"], c["style"], c["condition"]) for c in raw]


def run_row(row):
    ch = row["inputs"]["chain"]
    return SF.surface_frame(contracts_of(ch["contracts"]), ch["spot"], ch["rate"], ch["dividend_yield"],
                            ch["cutoff_ns"], row["params"])


def _close(test, got, want, tol, where):
    test.assertIsNotNone(got, where)
    test.assertLessEqual(abs(Fraction(got) - Fraction(want)), tol, (where, got, want))


def check_row(test, row, res):
    exp = row["expected"]
    rid = row["id"]
    tol = {k: Fraction(v) for k, v in exp["tolerance"].items()}
    test.assertEqual(res.output_id, "M3A-0", rid)
    test.assertEqual((res.status, res.reason, res.code), (exp["status"], exp["reason"], exp["code"]), rid)
    test.assertIsNone(res.value, rid)
    test.assertIsNone(res.fired, rid)
    if exp["status"] == "invalid_input":
        test.assertIsNone(res.frame, rid)
        return
    frame = res.frame
    want_frame = exp["frame"] or {}
    if "expiries" in want_frame:
        test.assertEqual(set(frame["expiries"]), set(want_frame["expiries"]), rid)
        for d, we in want_frame["expiries"].items():
            ge = frame["expiries"][d]
            where = (rid, d)
            test.assertEqual((ge["status"], ge["reason"]), (we["status"], we["reason"]), where)
            for key, tk in (("forward", "forward"), ("atm_iv", "iv")):
                if key in we:
                    if we[key] is None:
                        test.assertIsNone(ge[key], (where, key))
                    else:
                        _close(test, ge[key], we[key], tol[tk], (where, key))
            for side in ("put25_iv", "call25_iv"):
                if side in we:
                    gs, ws = ge[side], we[side]
                    test.assertEqual((gs["status"], gs["reason"]), (ws["status"], ws["reason"]), (where, side))
                    if ws["value"] is None:
                        test.assertIsNone(gs["value"], (where, side))
                    else:
                        _close(test, gs["value"], ws["value"], tol["iv"], (where, side))
    if "tenors" in want_frame:
        for t, wt in want_frame["tenors"].items():
            gt = frame["tenors"][t]
            where = (rid, "tenor", t)
            test.assertEqual((gt["status"], gt["reason"], gt["method"], gt["expiries_used"]),
                             (wt["status"], wt["reason"], wt["method"], wt["expiries_used"]), where)
            if wt["iv"] is None:
                test.assertIsNone(gt["iv"], where)
            else:
                _close(test, gt["iv"], wt["iv"], tol["iv"], where)
    if exp["coverage"] is not None:          # R-144: null = not asserted; else every key it gives
        for k, v in exp["coverage"].items():
            test.assertEqual(res.coverage[k], v, (rid, "coverage", k))
    if exp["labels"] is not None:
        test.assertEqual(res.labels, exp["labels"], (rid, "labels"))
    for k, v in (exp.get("echo") or {}).items():
        test.assertEqual(res.params.get(k), v, (rid, "echo", k))
    json.dumps(frame)                        # wire-ready: plain JSON values only
    C.canonical_line(res)


class Rows(unittest.TestCase):
    def test_owned_row_count(self):
        self.assertEqual(len(ROWS), 313)


def _make(row):
    def test(self):
        check_row(self, row, run_row(row))
    return test


ROWS = owned_rows()
for _r in ROWS:
    setattr(Rows, "test_" + _r["id"].replace("-", "_"), _make(_r))


# ---------------------------------------------------------------- hostile inputs: never raise (S03 follow-up)
def _flat_chain(strike_text=("95", "100", "105")):
    out = []
    for k in strike_text:
        for right in ("call", "put"):
            out.append(ChainContract("30-%s-%s" % (right[0], k), 30, right, k, "2.00", "2.02", 1, None, "european"))
    return out


class Hostile(unittest.TestCase):
    P = {"tenors": [30], "evaluation_ns": 10}

    def _code(self, *args, **kw):
        res = SF.surface_frame(*args, **kw)
        self.assertEqual(res.status, "invalid_input")
        return res.code

    def test_spot_zero_negative_nonfinite(self):
        for spot in ("0", 0, "-1"):
            self.assertEqual(self._code(_flat_chain(), spot, 0, 0, 10, self.P), "bad_spot", spot)
        for spot in (float("nan"), float("inf"), float("-inf")):
            self.assertEqual(self._code(_flat_chain(), spot, 0, 0, 10, self.P), "bad_spot", spot)
        for spot in ("1/2", " 1", "+1", "1_0", True, "1.123456789", 100.1, None):
            self.assertEqual(self._code(_flat_chain(), spot, 0, 0, 10, self.P), "malformed_type", spot)

    def test_strike_not_positive(self):
        for k in ("0", "-5", 0):
            ch = _flat_chain() + [ChainContract("bad", 30, "call", k, "1", "1.1", 1, None, "european")]
            self.assertEqual(self._code(ch, "100", 0, 0, 10, self.P), "bad_strike", k)
        ch = _flat_chain() + [ChainContract("bad", 30, "call", "abc", "1", "1.1", 1, None, "european")]
        self.assertEqual(self._code(ch, "100", 0, 0, 10, self.P), "malformed_type")

    def test_rate_nonfinite(self):
        for r in (float("nan"), float("inf"), 2):
            self.assertEqual(self._code(_flat_chain(), "100", r, 0, 10, self.P), "bad_rate", r)
        self.assertEqual(self._code(_flat_chain(), "100", 0, -0.1, 10, self.P), "bad_rate")

    def test_other_structural(self):
        self.assertEqual(self._code(_flat_chain(), "100", 0, 0, -1, self.P), "bad_cutoff")
        ch = _flat_chain() + [ChainContract("x", 30, "straddle", "100", "1", "1.1", 1, None, "european")]
        self.assertEqual(self._code(ch, "100", 0, 0, 10, self.P), "unknown_right")
        ch = _flat_chain() + [_flat_chain()[0]]
        self.assertEqual(self._code(ch, "100", 0, 0, 10, self.P), "duplicate_contract")
        ch = _flat_chain() + [ChainContract("x", 30, "call", "100", object(), "1.1", 1, None, "european")]
        self.assertEqual(self._code(ch, "100", 0, 0, 10, self.P), "malformed_type")
        self.assertEqual(self._code(_flat_chain(), "100", 0, 0, 10, {"evaluation_ns": 11}), "cutoff_mismatch")

    def test_nonfinite_or_negative_cached_iv_is_excluded(self):
        # a cached IV map with NaN, inf or negative values (never produced by IVChain) excludes those contracts
        # from the 25-delta scan instead of raising
        ch = _flat_chain(("90", "95", "100", "105", "110"))
        good = SF.surface_frame(ch, "100", 0, 0, 10, self.P)
        from option_features.chainiv import ContractIV
        for bad in (float("nan"), float("inf"), -0.1):
            ivs = {c.contract_id: ContractIV("available", None, bad, "exact-model") for c in ch}
            res = SF.surface_frame(ch, "100", 0, 0, 10, self.P, contract_ivs=ivs)
            self.assertIn(res.status, ("available", "unavailable"), bad)
            e = res.frame["expiries"]["30"]
            self.assertEqual(e["put25_iv"]["status"], "unavailable", bad)
            self.assertEqual(e["call25_iv"]["status"], "unavailable", bad)
        self.assertIn(good.status, ("available", "unavailable"))

    def test_empty_chain(self):
        res = SF.surface_frame([], "100", 0, 0, 10, self.P)
        self.assertEqual((res.status, res.reason, res.labels), ("unavailable", "no_eligible_contract", []))


class TenorInputs(unittest.TestCase):
    """expiry_records feeds tenors.py the coverage-gated status (R-103, R-104), never a row's expected frame."""

    def test_coverage_failed_expiry_is_unavailable(self):
        rows = [r for r in ROWS if r["id"] == "COV-04"]
        ch = rows[0]["inputs"]["chain"]
        recs = SF.expiry_records(contracts_of(ch["contracts"]), ch["spot"], ch["rate"], ch["dividend_yield"],
                                 ch["cutoff_ns"], rows[0]["params"])
        self.assertEqual([(r.days, r.status, r.reason, r.atm_iv) for r in recs],
                         [(30, "unavailable", "low_surface_coverage", None)])


# ---------------------------------------------------------------- perf row W02 (M3A-B1, per convention)
class PerfW02(unittest.TestCase):
    def test_W02(self):
        """M3A-B1: surface increment on the size-M workload chain, contract IVs cached, one cutoff, tenors 9, 30,
        91, per delta convention; p95 over 30 repeats after one warm-up (synthetic workload, relative engineering
        budget); delta evaluations per chain <= 200 (M3A-B12)."""
        import adapt_delta25 as A
        gen = A.workload_module()
        raw = gen.chain("M")
        prepared, truth, _ = A.workload("M")
        contracts = contracts_of(raw["contracts"])
        args = (contracts, raw["spot"], raw["rate"], raw["dividend_yield"], raw["cutoff_ns"])
        for conv in ("spot", "forward"):
            params = {"tenors": [9, 30, 91], "delta_convention": conv, "evaluation_ns": raw["cutoff_ns"]}
            stats = {}
            res = SF.surface_frame(*args, params=params, chain=prepared.chain, contract_ivs=prepared.ivs,
                                   stats=stats)                                   # warm-up
            times = []
            for _ in range(REPEATS):
                t0 = time.perf_counter()
                SF.surface_frame(*args, params=params, chain=prepared.chain, contract_ivs=prepared.ivs)
                times.append(time.perf_counter() - t0)
            p95 = statistics.quantiles(times, n=20)[18]
            print("\nW02 M3A-B1 %s size M: frame increment p50 %.2f ms p95 %.2f ms, %d delta evaluations "
                  "(budget <= 0.1 s p95, hard 0.5 s; <= 200 evaluations, hard 400; synthetic workload, relative "
                  "engineering budget)" % (conv, statistics.median(times) * 1e3, p95 * 1e3, stats["evaluations"]))
            self.assertLessEqual(p95, B1_BUDGET_S, conv)
            self.assertLessEqual(stats["evaluations"], B12_BUDGET, conv)
            self.assertEqual(len(res.frame["expiries"]), len(truth["expiries"]))
            for t in ("9", "30", "91"):
                self.assertIn(t, res.frame["tenors"])
            if conv == "spot":
                for ex in truth["expiries"]:
                    got = res.frame["expiries"][str(ex["expiry_days"])]
                    for side, key in (("put25_iv", "put25"), ("call25_iv", "call25")):
                        if ex[key] is not None and float(ex["atm_vega"]) >= 4:
                            self.assertEqual(got[side]["status"], "available", (ex["expiry_days"], side))
                            self.assertLessEqual(abs(float(got[side]["value"]) - float(ex[key]["iv"])), 1e-4)

    def test_G0_share_informational(self):
        """Informational G0 share: the whole M3A-0 build with no cache (IVChain, every contract IV, frame)."""
        import adapt_delta25 as A
        raw = A.workload_module().chain("M")
        contracts = contracts_of(raw["contracts"])
        params = {"tenors": [9, 30, 91], "evaluation_ns": raw["cutoff_ns"]}
        times = []
        for _ in range(3):
            t0 = time.perf_counter()
            SF.surface_frame(contracts, raw["spot"], raw["rate"], raw["dividend_yield"], raw["cutoff_ns"], params)
            times.append(time.perf_counter() - t0)
        print("\nW02 G0 share (informational): full M3A-0 build size M, %d contracts, uncached: min %.3f s, "
              "max %.3f s (3 runs)" % (len(contracts), min(times), max(times)))
        self.assertTrue(math.isfinite(min(times)))


# ---------------------------------------------------------------- R-189: unrounded floats in stats; params guard
def _row(rid):
    return next(r for r in ROWS if r["id"] == rid)


def _run(row, params=None, **kw):
    ch = row["inputs"]["chain"]
    return SF.surface_frame(contracts_of(ch["contracts"]), ch["spot"], ch["rate"], ch["dividend_yield"],
                            ch["cutoff_ns"], row["params"] if params is None else params, **kw)


class Floats(unittest.TestCase):
    def _check(self, res, floats):
        self.assertEqual(set(floats["expiries"]), set(res.frame["expiries"]))
        for d, item in res.frame["expiries"].items():
            fl = floats["expiries"][d]
            self.assertEqual(set(fl), {"atm_iv", "put25_iv", "call25_iv"})
            pairs = [("atm_iv", item["atm_iv"]), ("put25_iv", item["put25_iv"]["value"]),
                     ("call25_iv", item["call25_iv"]["value"])]
            for key, text in pairs:
                if text is None:
                    self.assertIsNone(fl[key], (d, key))
                else:
                    self.assertIs(type(fl[key]), float, (d, key))
                    self.assertEqual(C.round_text(fl[key]), text, (d, key))
        self.assertEqual(set(floats["tenors"]), set(res.frame["tenors"]))
        for t, item in res.frame["tenors"].items():
            if item["iv"] is None:
                self.assertIsNone(floats["tenors"][t], t)
            else:
                self.assertEqual(C.round_text(floats["tenors"][t]), item["iv"], t)

    def test_floats_round_to_frame_text_on_all_rows(self):
        n_null = n_val = 0
        for row in ROWS:
            if row["expected"]["status"] == "invalid_input":
                continue
            stats = {}
            res = _run(row, stats=stats)
            self._check(res, stats["floats"])
            for fl in stats["floats"]["expiries"].values():
                for v in fl.values():
                    n_null += v is None
                    n_val += v is not None
        self.assertGreater(n_null, 0)
        self.assertGreater(n_val, 0)

    def test_stats_none_unchanged(self):
        row = _row("TEN-01")
        a, b = _run(row), _run(row, stats={})
        self.assertEqual(C.canonical_line(a), C.canonical_line(b))

    def test_cache_path_fills_floats(self):
        from option_features.chainiv import IVChain
        row = _row("D25-R01")
        ch = row["inputs"]["chain"]
        cs = contracts_of(ch["contracts"])
        chain = IVChain(cs, ch["spot"], ch["rate"], ch["dividend_yield"], ch["cutoff_ns"])
        stats = {}
        res = SF.surface_frame(cs, ch["spot"], ch["rate"], ch["dividend_yield"], ch["cutoff_ns"], row["params"],
                               chain=chain, contract_ivs=chain.contract_iv(), stats=stats)
        self._check(res, stats["floats"])
        self.assertIsNotNone(stats["floats"]["expiries"]["14"]["put25_iv"])


class ParamsAndOrder(unittest.TestCase):
    def test_params_not_a_dict_never_raises(self):
        row = _row("SUR-01")
        for bad in ([1, 2], "x", 5, ("a",)):
            res = _run(row, params=bad)
            self.assertEqual((res.status, res.code), ("invalid_input", "malformed_type"), bad)

    def test_default_min_coverage_is_3_of_5(self):
        row = _row("COV-01")                          # exactly 3 eligible of 5 listed strikes
        p = {k: v for k, v in row["params"].items() if k != "min_coverage"}
        self.assertEqual(_run(row, p).frame["expiries"]["30"]["status"], "available")
        self.assertEqual(_run(row, p).params["min_coverage"], "3/5")
        p["min_coverage"] = "4/5"
        self.assertEqual(_run(row, p).frame["expiries"]["30"]["reason"], "low_surface_coverage")

    def test_both_sides_fail_put_then_call(self):
        row = _row("COV-01")                          # 3 strikes: neither side brackets 0.25
        res = _run(row)
        e = res.frame["expiries"]["30"]
        self.assertEqual((e["put25_iv"]["reason"], e["call25_iv"]["reason"]), ("no_delta_bracket", "no_delta_bracket"))
        self.assertEqual((res.status, res.reason), ("unavailable", "no_delta_bracket"))
        self.assertEqual(list(e)[-2:], ["put25_iv", "call25_iv"])


# ---------------------------------------------------------------- R-189 strength: floats are the unrounded kernel values
_SOLVER_REASONS = {"price_out_of_bounds", "upper_asymptote", "sigma_cap", "precision_exhausted", "bound_precision",
                   "iteration_budget"}


def _independent(row):
    """Expected floats by calling chainiv, delta25 and tenors directly (no surfaceframe code), for rows where the
    chainiv ATM equals the eligible-leg ATM (no solver failure, every expiry covered as the row expects)."""
    from option_features.chainiv import IVChain
    from option_features.delta25 import delta25_point
    from option_features.tenors import tenors as tenor_kernel
    ch = row["inputs"]["chain"]
    cs = contracts_of(ch["contracts"])
    chain = IVChain(cs, ch["spot"], ch["rate"], ch["dividend_yield"], ch["cutoff_ns"], row["params"]["stale_limit_ns"])
    ivs = chain.contract_iv()
    S = Fraction(ch["spot"])
    r, q = Fraction.from_float(float(ch["rate"])), Fraction.from_float(float(ch["dividend_yield"]))
    conv = row["params"].get("delta_convention", "spot")
    want_exp = row["expected"]["frame"]["expiries"]
    exps, recs = {}, []
    for d in sorted(int(x) for x in want_exp):
        st = want_exp[str(d)]["status"]
        a = chain.atm_iv(d)
        fl = {"atm_iv": None, "put25_iv": None, "call25_iv": None}
        if st == "available":
            fl["atm_iv"] = a.iv
            for right, key in (("put", "put25_iv"), ("call", "call25_iv")):
                legs = sorted((Fraction(c.strike), ivs[c.contract_id].iv) for c in cs
                              if c.expiry_days == d and c.right == right and ivs[c.contract_id].status == "available")
                pt = delta25_point([k for k, _ in legs], [v for _, v in legs], a.strike, S, r, q, d, right, conv)
                fl[key] = pt["value"]
        exps[str(d)] = fl
        recs.append((d, st, want_exp[str(d)]["reason"], fl["atm_iv"]))
    ten = tenor_kernel(recs, sorted(set(row["params"]["tenors"])))
    return {"expiries": exps, "tenors": {str(t): v.iv for t, v in ten.items()}}


def _sample_rows():
    out = []
    for row in ROWS:
        e = row["expected"]
        if e["status"] == "invalid_input" or not (e["frame"] or {}).get("expiries"):
            continue
        if _SOLVER_REASONS & set((e["coverage"] or {}).get("contract_reasons") or {}):
            continue
        if "solver" in row["case"] or "ATM moves" in row["case"]:
            continue
        out.append(row)
    step = max(1, len(out) // 30)
    return out[::step][:30]


class FloatsStrength(unittest.TestCase):
    def test_some_float_differs_from_its_text(self):
        differs = 0
        for row in ROWS:
            if row["expected"]["status"] == "invalid_input":
                continue
            stats = {}
            res = _run(row, stats=stats)
            for d, fl in stats["floats"]["expiries"].items():
                item = res.frame["expiries"][d]
                texts = (item["atm_iv"], item["put25_iv"]["value"], item["call25_iv"]["value"])
                for v, t in zip((fl["atm_iv"], fl["put25_iv"], fl["call25_iv"]), texts):
                    differs += v is not None and v != float(t)
            for t, v in stats["floats"]["tenors"].items():
                differs += v is not None and v != float(res.frame["tenors"][t]["iv"])
        self.assertGreater(differs, 100)

    def test_floats_equal_independent_kernel_values(self):
        rows = _sample_rows()
        self.assertEqual(len(rows), 30)
        for row in rows:
            stats = {}
            _run(row, stats=stats)
            want = _independent(row)
            self.assertEqual(stats["floats"]["expiries"], want["expiries"], row["id"])
            self.assertEqual(stats["floats"]["tenors"], want["tenors"], row["id"])

    def test_round_once_case_like_U_010(self):
        # a float whose 8-decimal text loses information: the stats value must keep it
        row = _row("D25-R01")
        stats = {}
        res = _run(row, stats=stats)
        put = stats["floats"]["expiries"]["14"]["put25_iv"]
        self.assertNotEqual(put, float(res.frame["expiries"]["14"]["put25_iv"]["value"]))
        self.assertEqual(put, _independent(row)["expiries"]["14"]["put25_iv"])


class HostileStats(unittest.TestCase):
    def test_nonfinite_ivs_never_reach_floats_or_frame(self):
        from option_features.chainiv import ContractIV
        ch = _flat_chain(("90", "95", "100", "105", "110"))
        for bad in (float("nan"), float("inf"), float("-inf")):
            ivs = {c.contract_id: ContractIV("available", None, bad, "exact-model") for c in ch}
            stats = {}
            res = SF.surface_frame(ch, "100", 0, 0, 10, {"tenors": [30], "evaluation_ns": 10}, contract_ivs=ivs,
                                   stats=stats)
            vals = [v for fl in stats["floats"]["expiries"].values() for v in fl.values()]
            vals += list(stats["floats"]["tenors"].values())
            self.assertTrue(all(v is None or math.isfinite(v) for v in vals), bad)
            line = C.canonical_line(res)
            self.assertNotIn("nan", line.lower())
            self.assertNotIn("inf", line.lower())

    def test_params_none_and_hostile_mapping(self):
        row = _row("SUR-01")
        self.assertIn(_run(row, params=None).status, ("available", "unavailable"))   # defaults: no raise

        class Boom(dict):
            def get(self, *a):
                raise RuntimeError("get")

            def update(self, *a, **k):
                raise RuntimeError("update")

            def keys(self):
                raise RuntimeError("keys")

            def __iter__(self):
                raise RuntimeError("iter")

            def items(self):
                raise RuntimeError("items")

        res = _run(row, params=Boom(row["params"]))
        self.assertIn(res.status, ("invalid_input", "available", "unavailable"))
        res = _run(row, params=Boom())
        self.assertIn(res.status, ("invalid_input", "available", "unavailable"))


if __name__ == "__main__":
    unittest.main()
