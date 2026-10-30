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

    def test_non_string_style_is_malformed_type(self):   # R-187
        ch = _flat_chain() + [ChainContract("x", 30, "call", "100.5", "1", "1.1", 1, None, 5)]
        self.assertEqual(self._code(ch, "100", 0, 0, 10, self.P), "malformed_type")
        for style in (None, "bermudan"):
            ch = _flat_chain() + [ChainContract("x", 30, "call", "100.5", "1", "1.1", 1, None, style)]
            self.assertNotEqual(SF.surface_frame(ch, "100", 0, 0, 10, self.P).status, "invalid_input", style)

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


if __name__ == "__main__":
    unittest.main()
