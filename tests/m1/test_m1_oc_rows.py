"""M1 OC5/OC6 rows (independently authored, qualification/synthetic/m1/m1_oc_cases.json).

One test method per row (test_row_<id>) so a failing row is named. The rows are read-only inputs:
test_rows_unedited pins their SHA-256 (LF-normalised) to the Tester's manifest.

Label: synthetic fixtures only (mock-data qualification only: passed on independently authored synthetic
fixtures and synthetic workloads, Windows x64, CPython 3.12).
"""
import hashlib
import unittest

import m1_adapter as A

ROWS = A.load_rows()
MANIFEST = A.ROWS_PATH.with_name("MANIFEST.sha256")


class RowIntegrity(unittest.TestCase):
    def test_rows_unedited(self):
        pinned = {}
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            digest, name = line.split(" *")
            pinned[name] = digest
        data = A.ROWS_PATH.read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(hashlib.sha256(data).hexdigest(), pinned["m1_oc_cases.json"])

    def test_row_count_and_ids(self):
        self.assertEqual(len(ROWS), 110)
        self.assertEqual(len({r["id"] for r in ROWS}), 110)
        self.assertEqual({r["op"] for r in ROWS}, {"oc5", "oc6"})


def _make(row):
    def test(self):
        failure = A.check_row(row)
        self.assertIsNone(failure, "%s [%s]: %s" % (row["id"], row["group"], failure))
    return test


class RowsFullValidation(unittest.TestCase):
    """The same rows with validate="full" (whole-history validation) give the same answers."""

    def test_all_rows(self):
        for row in ROWS:
            with self.subTest(row=row["id"]):
                self.assertIsNone(A.check_row(row, "full"))


for _row in ROWS:
    setattr(RowIntegrity, "test_row_" + _row["id"].replace("-", "_"), _make(_row))

if __name__ == "__main__":
    unittest.main()
