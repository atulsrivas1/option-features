"""M2-5 F17 contract premium over fixed trailing 300 s: 30 rows (Q9, matrix M2-5)."""
from m2common import *


def build(rng):
    R = Rows("F17", "M2-F17")
    sess = session("2026-06-01", S(4000), 390)

    def add(prints, tags, cid="C1", X=None, pending=None, noisy=False, T=None):
        ps = list(prints) + (noise(rng, 2) if noisy else [])
        prm = {"window_s": 300}
        if X is not None:
            prm["threshold_ticks"] = X
        R.add("M2-5", "flow.md F17; matrix M2-5", "Q9", mkin(ps, sess=sess, series=cid), prm, tags=tags, pending=pending)

    d = lambda s: -S(s)
    add([pp("C1", d(10 + i), 25000) for i in range(4)], ["f17_inclusive", "split_block", "threshold_edge"], noisy=True)  # 1
    add([pp("C1", d(10 + i), Fr("24999.9975"), size=1) if False else pp("C1", d(10 + i), 25000) for i in range(3)]
        + [pp("C1", d(40), Fr("24999.99"), size=1)], ["f17_inclusive", "split_block", "threshold_edge"])        # 2
    add([pp("C1", d(10), 100000)], ["f17_inclusive", "threshold_edge"])                                          # 3
    add([pp("C1", d(10 + i), 10000) for i in range(10)], ["split_block", "f17_inclusive"])                       # 4
    add([pp("C1", -S(300), 60000), pp("C1", d(10), 40000)], ["win_open_start", "f17_inclusive"])                 # 5
    add([pp("C1", -S(300) - 1, 60000), pp("C1", d(10), 40000)], ["win_open_start", "boundary_out"])              # 6
    add([pp("C1", d(10), 40000), pp("C1", 0, 60000)], ["win_open_end", "f17_inclusive"])                         # 7
    add([pp("C1", d(10), 40000), pp("C1", 1, 60000)], ["lookahead", "win_open_end"])                            # 8
    two = [pp("C1", d(10), 60000), pp("C2", d(20), 60000)]
    add(two, ["f17_per_name", "isolation"], cid="C1")                                                            # 9
    add(two, ["f17_per_name", "isolation"], cid="C2")                                                            # 10
    add([pp("C1", d(10), 60000)], ["no_prints", "isolation", "reason_never"], cid="P2")                                          # 11
    add([pp("C1", d(400), 600000)], ["no_prints", "boundary_out"], cid="C1")                                     # 12
    add([pr("C1", d(10), "600.0000", 10, mult=10), pp("C1", d(20), 100000)], ["nonstd_counted"])                 # 13
    add([pr("C1", d(10), "600.0000", 10, excl=1), pp("C1", d(20), 100000)], ["cond_excl_counted"])               # 14
    # tumbling mutant: T mod 300 s = 200 s, aligned bucket starts at T-200 s; prints at T-250 s are inside the trailing window
    add([pp("C1", d(250), 70000), pp("C1", d(100), 30000)], ["f17_tumbling", "f17_inclusive"])                   # 15
    add([pp("C1", d(250), 99999), pp("C1", d(100), 1)], ["f17_tumbling", "f17_inclusive"])                       # 16
    add([pp("C1", d(10), 50000)], ["threshold_param", "f17_inclusive"], X=usd(50000))                            # 17
    add([pp("C1", d(10), Fr("49999.99"), size=1)], ["threshold_param", "f17_inclusive"], X=usd(50000))           # 18
    add([pp("C1", d(5 + i), 1000, size=10) for i in range(60)] + [pp("C1", d(100), 40000)], ["many_prints", "split_block"])  # 19
    add([pp("C1", d(10), 50000, seq=0), pp("C1", d(10), 50000, seq=1)], ["ties", "f17_inclusive"])               # 20
    add([pp("C1", d(10), 10000000)], ["big_block"])                                                              # 21
    add([pr("C1", d(10), "333.3333", 1, mult=100), pr("C1", d(11), "333.3333", 1), pr("C1", d(12), "333.3334", 1)],
        ["f17_inclusive", "threshold_edge", "split_block"])                                                      # 22: 33333.33+33333.33+33333.34
    add([pr("C1", d(10), "333.3333", 1), pr("C1", d(11), "333.3333", 1), pr("C1", d(12), "333.3333", 1)],
        ["f17_inclusive", "threshold_edge", "split_block"])                                                      # 23: 99999.99
    add([pp("P1", d(10), 70000), pp("P1", d(20), 30000), pp("C1", d(30), 900000)], ["f17_per_name", "isolation"], cid="P1")  # 24
    add([pp("C1", d(299), 100000)], ["win_open_start"])                                                           # 25
    add([pp("C1", d(10), 100000), pp("C1", d(11), 1, size=1) if False else pp("C1", d(11), 100)], ["f17_inclusive"])  # 26
    add([pp("C1", d(10), 99999), pp("C1", d(11), 1, size=1)], ["f17_inclusive", "threshold_edge"])               # 27 99999.00+0.01
    add([], ["no_prints", "reason_never"], cid="C1")                                                                              # 28
    add([pp("C2", d(10), 100000), pp("C1", d(10), 5000)], ["f17_per_name", "isolation"], cid="C2")                # 29
    add([pp("C1", d(10), 20000), pp("C1", d(150), 30000), pp("C1", d(290), 50000)], ["win_open_start", "f17_inclusive", "f17_tumbling"])  # 30
    R.add("M2-5", "flow.md F17; matrix M2-5", "Q9", mkin([pp("C1", d(10), 100000)], sess=sess, series="C1"), {}, tags=["default_omitted", "f17_inclusive"])  # 31
    add([pr("C1", d(10), "1000.0000", 10, mult=10, excl=1), pr("C1", d(11), "1000.0000", 10, mult=10), pp("C1", d(12), 100000)],
        ["coverage_keys", "both_excl"])                                                                # 32
    assert len(R.rows) == 32, len(R.rows)
    return R.rows


if __name__ == "__main__":
    main_for("F17", "F17", build)
