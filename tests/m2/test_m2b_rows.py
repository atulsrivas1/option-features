"""M2 story B rows (F1, F4, F17, F7, F18, F12 and the lane, structural, delayed-feed, session-open rows that
touch them), independently authored under qualification/synthetic/m2/correctness (read only).

One test method per row (test_<id>) so a failing row is named. Label: synthetic workload, relative
engineering budget (no claim about recorded data). Synthetic fixtures only.
"""
import hashlib
import unittest

import m2b_adapter as A

ROWS = A.load_rows()


class RowIntegrity(unittest.TestCase):
    def test_fixtures_unedited(self):
        pinned = {}
        for line in (A.CORRECTNESS / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
            digest, name = line.split(None, 1)
            pinned[name.strip().lstrip("*")] = digest
        for f in A.FILES:
            name = "m2_cases_%s.json" % f
            data = (A.CORRECTNESS / name).read_bytes().replace(b"\r\n", b"\n")
            self.assertEqual(hashlib.sha256(data).hexdigest(), pinned[name], name)

    def test_row_counts(self):
        by = {}
        for f, r in ROWS:
            by[f] = by.get(f, 0) + 1
        self.assertEqual(by, A.EXPECTED_ROWS)
        self.assertEqual(len({r["id"] for _, r in ROWS}), len(ROWS))


def _make(row):
    def test(self):
        got = A.run_row(row)
        self.assertEqual(A.canon(got), A.canon(row["expected"]), row["id"])
    return test


class Rows(unittest.TestCase):
    pass


for _f, _row in ROWS:
    setattr(Rows, "test_" + _row["id"].replace("-", "_"), _make(_row))

if __name__ == "__main__":
    unittest.main()
