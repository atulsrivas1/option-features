"""M2-4 F4 large print count: 30 rows (Q8, matrix M2-4)."""
from m2common import *


def build(rng):
    R = Rows("F4", "M2-F4")
    sess = session("2026-06-01", S(4000), 390)

    def add(prints, tags, N=1, W=300, thr=None, pending=None, noisy=False):
        ps = list(prints) + (noise(rng, 2) if noisy else [])
        prm = {"window_s": W, "N": N, "threshold_ticks": thr if thr is not None else 1000000000}
        R.add("M2-4", "flow.md F4 (large prints); matrix M2-4", "Q8", mkin(ps, sess=sess), prm, tags=tags, pending=pending)

    d = lambda s: -S(s)
    add([pp("C1", d(10), 100000)], ["f4_inclusive", "threshold_edge"], noisy=True)                  # 1
    add([pp("C1", d(10), Fr("99999.99"), size=1)], ["f4_inclusive", "threshold_edge"])              # 2
    add([pp("C1", d(10), Fr("100000.01"), size=1)], ["f4_inclusive", "threshold_edge"])             # 3
    big = lambda i, cid="C1": pp(cid, d(10 + i), 100000)
    add([big(0), big(1), big(2)], ["n_edge"], N=3)                                                   # 4
    add([big(0), big(1)], ["n_edge"], N=3)                                                           # 5
    add([big(0), big(1), big(2), big(3)], ["n_edge"], N=3)                                           # 6
    add([pp("C1", d(10), 100000, side="unknown"), pp("P1", d(11), 150000, side="ask"),
         pp("P1", d(12), 120000, side="bid")], ["f4_side"])                                         # 7
    add([pp("C1", d(10), 100000, side="unknown")], ["f4_side"])                                      # 8
    add([pr("C1", d(10), "1000.0000", 10, mult=10), big(1)], ["nonstd_counted"])                     # 9 nonstd premium 100000?
    add([pr("C1", d(10), "1000.0000", 10, excl=1), big(1)], ["cond_excl_counted"])                   # 10
    add([], ["empty_window", "reason_never"])                                                        # 11
    add([pp("C1", -S(300), 100000)], ["win_open_start"])                                             # 12
    add([pp("C1", -S(300) - 1, 100000)], ["win_open_start", "boundary_out"])                         # 13
    add([pp("C1", 0, 100000)], ["win_open_end"])                                                     # 14
    add([pp("C1", 1, 100000)], ["lookahead", "win_open_end"])                                        # 15
    add([pp("C1", d(61), 100000)], ["window_len", "w300_for_other"], W=60)                           # 16 outside 60
    add([pp("C1", d(800), 100000)], ["window_len"], W=900)                                           # 17
    add([pp("C1", d(1700), 100000), pp("C1", d(1801), 100000)], ["window_len"], W=1800)              # 18
    add([pp("C1", d(3500), 100000), pp("C1", d(3601), 100000)], ["window_len"], W=3600)              # 19
    add([pp("C1", d(10), 250000), pp("P2", d(20), 100000), pp("P1", d(30), 99999, size=1)], ["premium_sum"])  # 20
    add([pp("C1", d(10 + i), 25000) for i in range(8)], ["split_block", "f4_per_print"])             # 21
    add([pp("C1", d(10), 50000), pp("C1", d(11), Fr("49999.99"), size=1)], ["threshold_param", "f4_inclusive"],
        thr=usd(50000))                                                                              # 22
    add([big(0), big(1)], ["threshold_param", "n_edge"], N=2, thr=usd(100000))                       # 23
    add([big(0, "C1"), big(1, "P1"), big(2, "C2"), big(3, "P2")], ["both_rights"])                   # 24
    add([pp("C1", d(10), 100000, seq=0), pp("C1", d(10), 100000, seq=1)], ["ties", "n_edge"], N=2)   # 25
    add([pp("C1", d(10), 1000000)], ["premium_sum"])                                                 # 26
    add([pr("C1", d(10), "333.3333", 3), pr("C1", d(11), "333.3334", 3)], ["f4_inclusive", "threshold_edge"])  # 27
    add([pr("C1", d(10), "1.0000", 10, mult=1), pr("C1", d(11), "9.0000", 1, mult=100)], ["nonstd_counted"])   # 28
    add([pp("C1", d(10), 100000, side="unknown"), pr("C1", d(20), "5000.0000", 20, mult=10),
         pr("P1", d(30), "5.0000", 5, excl=1)], ["f4_side", "nonstd_counted", "cond_excl_counted"])  # 29
    add([pp("C1", d(100), 100000), pp("C1", d(250), 100000), pp("C1", d(299), 100000)], ["n_edge", "win_open_start"], N=3)  # 30
    tw = [pp("C1", d(10), 100000), pp("P1", d(20), 150000), pp("C2", d(30), 120000), pp("P2", d(40), 5000)]
    tws = [pp("C1", d(10), 100000, side="ask"), pp("P1", d(20), 150000, side="bid"), pp("C2", d(30), 120000, side="unknown"),
           pp("P2", d(40), 5000, side="ask")]
    add(tws, ["side_twin", "f4_side"], N=3)                                                            # 31
    add(tw, ["side_twin", "f4_side"], N=3)                                                             # 32 equal result without side
    R.add("M2-4", "flow.md F4; matrix M2-4", "Q8", mkin([pp("C1", d(10), 100000), pp("C1", d(20), 100000)], sess=sess), {},
          tags=["default_omitted"])                                                                    # 33 window 300, N 1, threshold default
    add([pr("C1", d(10), "1000.0000", 10, mult=10, excl=1), pr("C1", d(11), "1000.0000", 10, mult=10),
         pr("P1", d(12), "1000.0000", 10, excl=1), pp("C1", d(13), 100000)], ["coverage_keys", "both_excl"])  # 34
    assert len(R.rows) == 34, len(R.rows)
    return R.rows


if __name__ == "__main__":
    main_for("F4", "F4", build)
