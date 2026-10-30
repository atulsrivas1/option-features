"""M3a fixture integrity (story S01): manifests of author1..4 unchanged, and the first-owner table of the build plan
section 3a covers every fixture row id and every perf row id exactly once.

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12
"""
import collections
import unittest

import m3a_harness as H


class Manifests(unittest.TestCase):
    pass


def _manifest_test(name):
    def test(self):
        self.assertEqual(H.manifest_mismatches(name), [], name)
    return test


for _n in H.SETS:
    setattr(Manifests, "test_manifest_" + _n, _manifest_test(_n))


class RowOwnership(unittest.TestCase):
    def test_every_fixture_row_has_exactly_one_first_owner(self):
        per_story = collections.Counter()
        per_author = collections.Counter()
        seen = set()
        for s in H.SETS:
            for fn in H.row_files(s):
                for r in H.raw_rows(s, fn):
                    rid = r["id"]
                    self.assertNotIn((s, fn, rid), seen)
                    seen.add((s, fn, rid))
                    owners = H.owners_of(s, fn, rid)
                    self.assertEqual(len(owners), 1, "%s/%s %s owners=%s" % (s, fn, rid, owners))
                    per_story[owners[0]] += 1
                    per_author[s] += 1
        self.assertEqual(sum(per_author.values()), 1232)
        self.assertEqual(dict(per_author), H.EXPECTED_AUTHOR_COUNTS)
        for story, n in H.EXPECTED_FIXTURE_COUNTS.items():
            self.assertEqual(per_story.get(story, 0), n, story)

    def test_row_ids_unique_across_all_files(self):
        ids = [r["id"] for s in H.SETS for fn in H.row_files(s) for r in H.raw_rows(s, fn)]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_perf_row_has_exactly_one_first_owner(self):
        rows = H.perf_rows()
        ids = [r["id"] for r in rows]
        self.assertEqual(len(ids), 71)
        self.assertEqual(len(set(ids)), 71)
        claimed = collections.Counter()
        for story, rids in H.PERF_OWNERS.items():
            self.assertEqual(len(rids), H.EXPECTED_PERF_COUNTS[story], story)
            claimed.update(rids)
        self.assertEqual(sorted(claimed), sorted(ids))
        self.assertTrue(all(n == 1 for n in claimed.values()))

    def test_owner_of_lookup(self):
        self.assertEqual(H.owner_of("M3A-U-001"), "S01")
        self.assertEqual(H.owner_of("D25-V3"), "S09")
        self.assertEqual(H.owner_of("COV-34"), "S05")
        self.assertEqual(H.owner_of("COV-35"), "S09")
        self.assertIsNone(H.owner_of("NO-SUCH-ROW"))


class Decoding(unittest.TestCase):
    def test_tagged_types_decode(self):
        from decimal import Decimal
        from fractions import Fraction
        d = H.decode({"a": {"py_type": "Decimal", "text": "1.50"}, "b": [{"py_type": "Fraction", "text": "3/4"}],
                      "c": {"py_type": "bytes", "hex": "00ff"}, "d": {"py_type": "float", "text": "inf"},
                      "e": {"py_type": "float", "text": "nan"}})
        self.assertEqual(d["a"], Decimal("1.50"))
        self.assertEqual(d["b"], [Fraction(3, 4)])
        self.assertEqual(d["c"], b"\x00\xff")
        self.assertEqual(d["d"], float("inf"))
        self.assertNotEqual(d["e"], d["e"])

    def test_rows_where(self):
        got = H.rows("author2", "m3a_cases_units.json", where=lambda r: r["output_id"] == "M3A-7")
        self.assertEqual([r["id"] for r in got], ["M3A-U-014", "M3A-U-015", "M3A-U-016", "M3A-U-017"])


if __name__ == "__main__":
    unittest.main()
