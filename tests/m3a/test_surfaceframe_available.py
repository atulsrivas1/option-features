"""S05c: stats["floats"]["available"] (R-197). True exactly when the frame result status is "available".

Differential: `s05c_golden_main.json` holds, per fixture row, the sha256 of (canonical result line + the floats
dict without the new key) computed on main f8aada1 (before S05c). The frame text, hashes and other floats keys must be
byte-identical after the patch. Fixtures (hash-pinned) are read only. Regenerate nothing: the golden is from main.

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows
x64, CPython 3.12.
"""
import hashlib
import json
import os
import unittest
from unittest import mock

import m3a_harness as H
import test_surface_series as TS
import test_surfaceframe as TF
from option_features import m3a_common as C
from option_features import surface_series as S
from option_features import surfaceframe as SF

GOLDEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s05c_golden_main.json")
A3 = ("m3a_cases_v5.json", "m3a_cases_v6.json", "m3a_cases_v8.json", "m3a_cases_v10.json", "m3a_cases_v11.json",
      "m3a_cases_v21.json")


_ROWS = []


def all_rows():
    if _ROWS:
        return _ROWS
    out = [("a1", r) for r in TF.owned_rows()]
    for fn in A3:
        out.extend(("a3:" + fn, r) for r in H.rows("author3", fn) if "chain" in r["inputs"])
    _ROWS.extend(out)
    return _ROWS


_MEMO = {}


def run(row):
    key = id(row)
    if key not in _MEMO:
        _MEMO[key] = _run(row)
    return _MEMO[key]


def _run(row):
    ch = row["inputs"]["chain"]
    stats = {}
    res = SF.surface_frame(TF.contracts_of(ch["contracts"]), ch["spot"], ch["rate"], ch["dividend_yield"],
                           ch["cutoff_ns"], row["params"], stats=stats)
    return res, stats


def digest(res, stats):
    fl = {k: v for k, v in stats.get("floats", {}).items() if k != "available"}
    blob = C.canonical_line(res) + "\n" + json.dumps(fl, sort_keys=True) + "\n" + repr(sorted(stats))
    return hashlib.sha256(blob.encode()).hexdigest()


class Availability(unittest.TestCase):
    def test_flag_matches_status_on_every_row(self):
        seen = {}
        for tag, row in all_rows():
            res, stats = run(row)
            if res.status == "invalid_input":
                self.assertNotIn("floats", stats, row["id"])      # no floats at all: S10 fails closed
                seen["invalid_input"] = seen.get("invalid_input", 0) + 1
                continue
            flag = stats["floats"]["available"]
            self.assertIs(type(flag), bool, row["id"])
            self.assertIs(flag, res.status == "available", row["id"])
            seen[res.status] = seen.get(res.status, 0) + 1
        self.assertGreater(seen.get("available", 0), 20)
        self.assertGreater(seen.get("unavailable", 0), 20)
        self.assertGreater(seen.get("invalid_input", 0), 0)

    def test_every_unavailable_reason_is_false(self):
        reasons = set()
        for _, row in all_rows():
            res, stats = run(row)
            if res.status == "unavailable":
                reasons.add(res.reason)
                self.assertIs(stats["floats"]["available"], False, row["id"])
        self.assertGreaterEqual(len(reasons), 3, reasons)

    def test_status_vocabulary_is_closed(self):
        self.assertEqual({res.status for _, r in all_rows() for res in [run(r)[0]]},
                         {"available", "unavailable", "invalid_input"})

    def test_no_stats_no_error(self):
        _, row = all_rows()[0]
        ch = row["inputs"]["chain"]
        SF.surface_frame(TF.contracts_of(ch["contracts"]), ch["spot"], ch["rate"], ch["dividend_yield"],
                         ch["cutoff_ns"], row["params"])

    def test_frame_with_values_but_unavailable_is_false(self):
        """An unavailable frame may still carry some float values (an available expiry beside a failed one)."""
        n = 0
        for _, row in all_rows():
            res, stats = run(row)
            if res.status == "unavailable" and any(v is not None for e in stats["floats"]["expiries"].values()
                                                   for v in e.values()):
                self.assertIs(stats["floats"]["available"], False, row["id"])
                n += 1
        self.assertGreater(n, 0)


class Differential(unittest.TestCase):
    def test_identical_to_main(self):
        with open(GOLDEN, encoding="utf-8") as f:
            golden = json.load(f)
        rows_ = all_rows()
        self.assertEqual(len(rows_), len(golden))
        for tag, row in rows_:
            res, stats = run(row)
            self.assertEqual(digest(res, stats), golden[tag + "|" + row["id"]], row["id"])


class EndToEndSeries(unittest.TestCase):
    """Real S05 output (no flag added by the test) through S10 build_records."""

    def test_records_only_for_available_frames(self):
        with_records = without = 0
        for _, row in all_rows():
            res, stats = run(row)
            if "floats" not in stats:
                continue
            recs = S.build_records("E2E", "stock", 1, stats["floats"])
            if res.status == "available":
                self.assertTrue(recs, row["id"])
                self.assertTrue(all(r[0].startswith("E2E/stock/") for r in recs), row["id"])
                with_records += 1
            else:
                self.assertEqual(recs, [], row["id"])
                without += 1
        self.assertGreater(with_records, 20)
        self.assertGreater(without, 20)

    def test_minute_grids_zero_for_unavailable_real_frames(self):
        av = un = None
        for _, row in all_rows():
            res, stats = run(row)
            if res.status == "available" and av is None:
                av = stats["floats"]
            if res.status == "unavailable" and "floats" in stats and un is None \
                    and any(v is not None for e in stats["floats"]["expiries"].values() for v in e.values()):
                un = stats["floats"]
        self.assertIsNotNone(av)
        self.assertIsNotNone(un)
        self.assertEqual(S.minute_values_from_floats(un), (None, None))
        self.assertNotEqual(S.minute_values_from_floats(av), (None, None))

    def test_forward_frame_unavailable_gives_no_skew25_fwd(self):
        pairs = []
        for _, row in all_rows():
            res, stats = run(row)
            if "floats" in stats:
                pairs.append((res.status, stats["floats"]))
        av = [f for st, f in pairs if st == "available"]
        un = [f for st, f in pairs if st == "unavailable"]
        positive = [f for f in av if any(r[0].endswith("/skew25_fwd")
                                         for r in S.build_records("E2E", "stock", 1, av[0], close_floats_fwd=f))]
        self.assertTrue(positive)                                   # control: an available forward frame stores it
        for f in un:
            recs = S.build_records("E2E", "stock", 1, av[0], close_floats_fwd=f)
            self.assertFalse(any(r[0].endswith("/skew25_fwd") for r in recs))


if __name__ == "__main__":
    unittest.main()

