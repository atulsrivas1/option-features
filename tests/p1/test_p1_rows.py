"""P1 parity-closure rows (independently authored, qualification/synthetic/p1/p1_cases.json).

One test method per row (test_<id>) so a failing row is named. The rows are read-only
inputs: test_rows_unedited pins their SHA-256 (LF-normalised) to the Tester's manifest.

Label: synthetic workload, relative engineering budget (no real-data claim). Synthetic fixtures only.
"""
import hashlib
from fractions import Fraction
import unittest

import p1_adapter as A

ROWS = A.load_rows()
MANIFEST = A.ROWS_PATH.with_name("MANIFEST.sha256")


class RowIntegrity(unittest.TestCase):
    def test_rows_unedited(self):
        pinned = {}
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            digest, name = line.split(" *")
            pinned[name] = digest
        data = A.ROWS_PATH.read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(hashlib.sha256(data).hexdigest(), pinned["p1_cases.json"])

    def test_row_count_and_coverage(self):
        self.assertEqual(len(ROWS), 121)
        self.assertEqual(len({r["id"] for r in ROWS}), 121)
        self.assertEqual({r["inputs"]["op"] for r in ROWS}, set(A.DISPATCH))


class LegacyDirect(unittest.TestCase):
    """Legacy-mode sign rows (H group) against the unchanged variants1 rule, independent of any P1 code."""

    def test_h_rows_use_legacy_epsilon_side(self):
        from option_features.variants1.signing import epsilon_side
        checked = 0
        for row in ROWS:
            if row["group"] != "legacy_default" or row["expected"]["status"] != "available":
                continue
            q, t = row["inputs"]["quote"], row["inputs"]["trade"]
            side, reason = epsilon_side(float(Fraction(t["price"])), float(Fraction(q["bid"])), float(Fraction(q["ask"])), 0.0)
            want = {"ask": "buy", "bid": "sell"}[row["expected"]["side"]]
            with self.subTest(row=row["id"]):
                self.assertEqual((side, reason), (want, "classified"))
            checked += 1
        self.assertEqual(checked, 8)


def _make(row):
    def test(self):
        failure = A.check_row(row)
        self.assertIsNone(failure, "%s [%s]: %s" % (row["id"], row["group"], failure))
    return test


for _row in ROWS:
    setattr(RowIntegrity, "test_row_" + _row["id"], _make(_row))

if __name__ == "__main__":
    unittest.main()
