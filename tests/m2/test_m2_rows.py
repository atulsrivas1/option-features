"""M2 story A rows (independently authored, qualification/synthetic/m2/correctness): one test per owned row.

Owned outputs: M2-2 (F2a-c), M2-3 (F2d), M2-7 (F10), M2-8 (F20), M2-10 (F19), M2-12 (history store). A failing row
is named. The rows are read-only inputs: test_rows_unedited pins their SHA-256 to the Tester's manifest.

Developer evidence only; the independent Tester must re-run. Label: mock-data qualification only: passed on
independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12.
"""
import hashlib
import unittest

import m2_adapter as A

ROWS = A.load_rows()


class RowIntegrity(unittest.TestCase):
    def test_rows_unedited(self):
        for name, digest in A.manifest_hashes().items():
            data = (A.ROWS_DIR / name).read_bytes().replace(b"\r\n", b"\n")
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest, name)

    def test_row_counts(self):
        by = {}
        for r in ROWS:
            by[r["output_id"]] = by.get(r["output_id"], 0) + 1
        self.assertEqual(len(ROWS), 363)
        self.assertEqual(by, {"M2-2": 101, "M2-3": 22, "M2-7": 58, "M2-8": 37, "M2-10": 35, "M2-12": 87, "M2-GRID": 23})
        self.assertEqual(len({r["id"] for r in ROWS}), len(ROWS))


def _make(row):
    def test(self):
        failure = A.check_row(row)
        self.assertIsNone(failure, "%s %s: %s" % (row["id"], row["tags"], failure))
    return test


for _row in ROWS:
    setattr(RowIntegrity, "test_row_" + _row["id"].replace("-", "_"), _make(_row))

if __name__ == "__main__":
    unittest.main()
