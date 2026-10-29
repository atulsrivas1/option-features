"""Developer tests for the M2-G0 full-output unit (tools/m1_runner/workload.py). Synthetic data only.

Developer evidence only: the independent Tester authors and re-runs its own fixtures.
One unit returns the FULL output set: OC5, OC6, per-contract IV, ATM IV (all expiries), 30-day IV, and the P1
outputs (spread/locked/coverage gates, touch-policy signing, window_end premium windows, single-reference F5/F6
shares) over the unit's synthetic quote and trade streams. Rows: all families present, canonical order,
determinism (repeat, contract order, cached history), frozen print count, P1 families equal the library's
single-call functions, timing hooks are log-only.
CI-time: tiny shape "T" (40 contracts), a few seconds.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools")]
import m1_runner  # noqa: E402
from m1_runner import Runner, Spec, workload  # noqa: E402
from option_features import quotes, shares, windows  # noqa: E402

SPEC = Spec(shape="T", underlyings=("SYN1",), sessions=(1,), cutoffs=(5,))
KEY = "SYN1/01/005"
N = workload.chain_size("T")


def unit(spec=SPEC, key=KEY, **kw):
    return workload.compute_unit(spec, key, **kw)


class AllFamilies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = unit()
        cls.doc = json.loads(cls.data)

    def test_top_level_families(self):
        self.assertEqual(sorted(self.doc), ["atm", "iv", "iv30", "oc5", "oc6", "p1", "spot", "unit"])
        self.assertEqual(sorted(self.doc["p1"]), ["shares", "signing", "spread", "window"])

    def test_every_contract_has_every_per_contract_family(self):
        d = self.doc
        for fam in (d["iv"], d["oc5"], d["oc6"], d["p1"]["spread"], d["p1"]["window"]):
            self.assertEqual(len(fam), N)
        ids = [r[0] for r in d["iv"]]
        for fam in (d["oc5"], d["oc6"], d["p1"]["spread"], d["p1"]["window"]):
            self.assertEqual([r[0] for r in fam], ids)

    def test_all_expiries_atm_and_30_day(self):
        self.assertEqual([r[0] for r in self.doc["atm"]], sorted(workload.TINY["expiries_days"]))
        self.assertEqual(self.doc["iv30"][0], "available")

    def test_canonical_order_and_bytes(self):
        ids = [r[0] for r in self.doc["iv"]]
        self.assertEqual(ids, sorted(ids))
        again = json.dumps(self.doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
        self.assertEqual(again, self.data)

    def test_signing_covers_every_quote_and_print(self):
        s = self.doc["p1"]["signing"]
        self.assertEqual(s["trades"], N * SPEC.prints)
        self.assertEqual(s["records"], s["quotes"] + s["trades"])
        self.assertEqual(sum(c for _, c in s["code_counts"]), s["records"])
        classified = {code for code, _ in s["code_counts"] if code in (17, 18)}
        self.assertEqual(classified, {17, 18}, "the workload must exercise both ask-side and bid-side signing")

    def test_window_and_shares_shapes(self):
        row = self.doc["p1"]["window"][0]
        self.assertEqual([w[0] for w in row[1:]], list(workload.PRINT_WINDOWS_NS))
        self.assertEqual(len(self.doc["p1"]["shares"]["expiries"]), len(workload.TINY["expiries_days"]))


class Determinism(unittest.TestCase):
    def test_repeat_identical(self):
        self.assertEqual(unit(), unit())

    def test_contract_order_does_not_change_bytes(self):
        base = unit()
        for order in ("reversed", "shuffle:3", "shuffle:99"):
            self.assertEqual(unit(Spec(**{**SPEC._asdict(), "contract_order": order})), base, order)

    def test_cached_longer_history_does_not_change_bytes(self):
        long_hist = workload.SessionHistory(SPEC, "SYN1", 1, 20 * workload.gen.CUTOFF_STEP_NS)
        self.assertEqual(unit(history=long_hist), unit())

    def test_workload_changes_change_bytes(self):
        base = unit()
        self.assertNotEqual(unit(Spec(**{**SPEC._asdict(), "prints": SPEC.prints + 1})), base)
        self.assertNotEqual(unit(Spec(**{**SPEC._asdict(), "seed": SPEC.seed + 1})), base)


class FrozenWorkload(unittest.TestCase):
    def test_print_count_per_size_m_unit_is_frozen_and_at_most_40000(self):
        self.assertEqual(workload.PRINTS_PER_CONTRACT, 20)
        self.assertEqual(Spec(shape="M").prints * workload.chain_size("M"), 40000)

    def test_print_stream_is_a_pure_function_of_unit(self):
        a = workload.build_inputs(SPEC, KEY)
        b = workload.build_inputs(SPEC, KEY)
        self.assertEqual(a.prints, b.prints)
        self.assertEqual(sum(len(p) for p in a.prints), N * SPEC.prints)
        self.assertTrue(all(t <= a.cutoff_ns for rows in a.prints for t, *_ in rows))

    def test_bad_prints_value_is_rejected(self):
        for bad in (-1, 1001, 2.5, "20"):
            with self.assertRaises(ValueError):
                Spec(**{**SPEC._asdict(), "prints": bad}).validate()


class P1EqualsLibrary(unittest.TestCase):
    """Each P1 family in the result equals the library's own single-call function on the same inputs."""

    @classmethod
    def setUpClass(cls):
        cls.inp = workload.build_inputs(SPEC, KEY)
        cls.doc = json.loads(workload.compute_from_inputs(SPEC, cls.inp))
        cls.ids = [r.contract_id for r in cls.inp.rows]

    def test_windows_equal_window_premium(self):
        by_id = {r[0]: r for r in self.doc["p1"]["window"]}
        for i in (0, 7, N - 1):
            row = by_id[self.ids[i]]
            for w in row[1:]:
                ref = windows.window_premium(self.inp.prints[i], w[0], self.inp.cutoff_ns)
                self.assertEqual(w[1:], [workload._default(x) if isinstance(x, workload.Fraction) else x for x in ref])

    def test_shares_equal_single_call(self):
        allp = [p for rows in self.inp.share_prints for p in rows]
        ref = shares.single_reference_shares(allp, self.inp.civil_day, short_dte_max_days=workload.SHORT_DTE_MAX_DAYS,
                                             short_min_share=workload.Fraction(1, 2), otm_min_share=workload.Fraction(1, 4))
        text = json.dumps(list(ref), default=workload._default, sort_keys=True)
        self.assertEqual(json.dumps(self.doc["p1"]["shares"]["chain"], sort_keys=True), text)

    def test_signing_counts_equal_one_by_one_sign_trade(self):
        tuples = {}
        for r in self.inp.records:
            tuples.setdefault(r[1], []).append(r)
        want = {1: 0, 2: 0}
        for recs in tuples.values():
            quote = None
            for kind, _, t, x, y in recs:
                if kind == "q":
                    quote = None if (x is None and y is None) else (x, y, t)
                else:
                    sign = quotes.sign_trade(x, quote, t, inside_spread="unknown")
                    if sign.side == "ask":
                        want[1] += 1
                    elif sign.side == "bid":
                        want[2] += 1
        got = dict(self.doc["p1"]["signing"]["code_counts"])
        self.assertEqual((got.get(17, 0), got.get(18, 0)), (want[1], want[2]))

    def test_spread_rows_equal_quote_spread(self):
        by_id = {r[0]: r for r in self.doc["p1"]["spread"]}
        seen_open = 0
        for i, cid in enumerate(self.ids):
            k = self.inp.cut[i]
            row = by_id[cid]
            if not k:
                self.assertEqual(row[1], "no_quote")
                continue
            up = self.inp.hist.ups[i][k - 1]
            reason = quotes.spread_reason(int(up.bid), int(up.ask), self.inp.cutoff_ns - up.event_ns, quotes.DEFAULT_STALE_LIMIT_NS)
            self.assertEqual(row[1], reason)
            if reason is None:
                seen_open += 1
                self.assertEqual(row[2], workload._default(quotes.quote_spread(int(up.bid), int(up.ask)).spread))
        self.assertTrue(set(r[1] for r in by_id.values()) <= {None, "no_quote", "stale_quote", "locked_market", "crossed_market", "invalid_quote"})


class LogOnlyTiming(unittest.TestCase):
    def test_timing_hook_returns_same_bytes_and_all_families(self):
        tm = {}
        data = unit(timing=tm)
        self.assertEqual(data, unit())
        self.assertEqual(set(workload.FAMILIES) <= set(tm), True)
        self.assertEqual(set(workload.SYNTH) - {"synth_history_s"} <= set(tm), True)
        self.assertGreater(tm["compute_s"], 0)
        self.assertLessEqual(sum(tm[f] for f in workload.FAMILIES), tm["compute_s"] * 1.0001 + 1e-6)
        for word in (b"worker", b"compute_s", b"timing", b"synth_"):
            self.assertNotIn(word, data)

    def test_runner_logs_timing_outside_results(self):
        with Runner(workers=1) as r:
            res = r.run(SPEC)
        timing = res.log["chunk_wall_s"][0]["timing"]
        self.assertTrue(set(workload.FAMILIES) <= set(timing))
        self.assertNotIn("timing", json.dumps(res.log.get("digests", "")))
        with Runner(workers=1) as r:
            self.assertEqual(r.run(SPEC).result_sha256, res.result_sha256)


if __name__ == "__main__":
    unittest.main()
