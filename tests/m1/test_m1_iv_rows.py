"""M1 story B rows (independently authored, qualification/synthetic/m1/m1_iv_cases.json).

One test method per row (test_<id>) so a failing row is named. The rows are read-only inputs:
test_rows_unedited pins their SHA-256 (LF-normalised) to the Tester's manifest.

Label: synthetic workload, relative engineering budget (no claim about recorded data). Synthetic fixtures only.
"""
import hashlib
import unittest

import m1_iv_adapter as A

DATA = A.load()
ROWS = DATA["rows"]
MANIFEST = A.ROWS_PATH.with_name("MANIFEST.sha256")


class RowIntegrity(unittest.TestCase):
    def test_rows_unedited(self):
        pinned = {}
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            digest, name = line.split(" *")
            pinned[name] = digest
        data = A.ROWS_PATH.read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(hashlib.sha256(data).hexdigest(), pinned["m1_iv_cases.json"])

    def test_row_count_and_groups(self):
        self.assertEqual(len(ROWS), 41)
        self.assertEqual(len({r["id"] for r in ROWS}), 41)
        self.assertEqual({r["group"] for r in ROWS}, {"contract_iv", "atm_iv", "iv_30d"})


class Rows(unittest.TestCase):
    pass


def _make(row):
    def test(self):
        got = A.run_row(row)
        diff = A.compare(row, got)
        self.assertIsNone(diff, "%s (%s): %s" % (row["id"], row["case"], diff))
    return test


for _row in ROWS:
    setattr(Rows, "test_" + _row["id"].replace("-", "_"), _make(_row))


if __name__ == "__main__":
    unittest.main()
