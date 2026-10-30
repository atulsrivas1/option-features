"""M2 story B kernels against the Tester's frozen workload truth (qualification/synthetic/m2/perf, read only):
the window truth of unit SYN1/21 (eligible prints, F4 large prints, F17 contracts at or above $100,000, window
premium at 78 cutoffs, SHA-256 of the truth rows) and the episode totals of the 500-series workload.

Label: synthetic workload, relative engineering budget (no claim about recorded data). Synthetic fixtures only.
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

PERF = Path(__file__).resolve().parents[2] / "qualification" / "synthetic" / "m2" / "perf"
sys.path.insert(0, str(PERF))

import gen_m2_workloads as G  # noqa: E402  (the Tester's generator; never edited)
from option_features import episodes as E, m2prints as M, printtape as PT  # noqa: E402

MAN = json.loads((PERF / "m2_workload_manifest.json").read_text(encoding="utf-8"))
SEED = MAN["seed"]


class WorkloadTruth(unittest.TestCase):
    def test_window_truth_unit_syn1_21(self):
        prints = list(G.unit_prints(SEED, "SYN1", 21))
        cons = {}
        for p in prints:
            if p[0] not in cons:
                right, strike, exp = G.contract(p[0])
                cons[p[0]] = (right, strike, exp, "stock")
        tape = PT.build_tape(prints, cons)
        op = G.session_open_ns(21)
        cuts = [op + i * G.B_NS for i in range(1, G.CUTOFFS + 1)]
        f4 = M.f4_sweep(tape, cuts, threshold_ticks=G.LARGE_PREM)
        f17 = M.f17_sweep(tape, cuts, threshold_ticks=G.LARGE_PREM)
        groups = tape.select("stock", "all")
        h = hashlib.sha256()
        for i, (T, r4, rows17) in enumerate(zip(cuts, f4, f17), 1):
            prem = tape.stats(groups, T - G.B_NS, T)[0]
            row = (i, r4["coverage"]["eligible_count"], r4["value"]["large_count"], sum(1 for r in rows17 if r["fired"]), prem)
            h.update(("%d,%d,%d,%d,%d\n" % row).encode())
        self.assertEqual(h.hexdigest(), MAN["window_truth"][0]["sha256"])

    def test_episode_totals_500_series(self):
        ep = {e["series"]: e for e in MAN["episodes"]}[500]
        tot = {1: 0, 5: 0}
        for s in range(500):
            pts = G.episode_points(SEED, (500, 1, s), G.MINUTES, s % G.DENSE_EVERY == 0)
            p60 = [None] * 15 + [a for _st, a, _b in pts]          # fired iff a >= b, i.e. 15 a >= 1 x 15 b
            p900 = [None] * 15 + [15 * b for _st, _a, b in pts]
            for gap in (1, 5):
                sc = E.scan_episodes(p60, p900, len(p60) - 1, 1, 1, gap)
                tot[gap] += sc[0]
                if s < 3:
                    want = ep["sample"][s]["gap%d" % gap]
                    self.assertEqual((sc[0], sc[1] - 15), (want[0], want[1]))
        self.assertEqual((tot[1], tot[5]), (ep["truth_gap1_total"], ep["truth_gap5_total"]))


if __name__ == "__main__":
    unittest.main()
