"""M2-6 F7 concentration: 36 rows (Q10, matrix M2-6)."""
from m2common import *

E1, E2, E3 = "2026-11-20", "2026-12-18", "2027-01-15"
CON7 = {
    "C100a": K("C", 1000000, E1), "P100a": K("P", 1000000, E1), "C100b": K("C", 1000000, E2),
    "C110a": K("C", 1100000, E1), "C110b": K("C", 1100000, E2), "P90a": K("P", 900000, E1),
    "P90b": K("P", 900000, E2), "C120c": K("C", 1200000, E3), "P120c": K("P", 1200000, E3),
}


def build(rng):
    R = Rows("F7", "M2-F7")
    sess = session("2026-06-01", S(4000), 390)

    def add(prints, tags, W=300, th=None, pending=None, noisy=False):
        ps = list(prints) + (noise(rng, 2, cids=list(CON7)) if noisy else [])
        prm = {"window_s": W}
        if th is not None:
            prm["share_threshold"] = th
        R.add("M2-6", "flow.md F7; matrix M2-6", "Q10", mkin(ps, contracts=CON7, sess=sess), prm, tags=tags, pending=pending)

    d = lambda s: -S(s)
    # shares exactly 0.60 / just below / just above (strike 100 over E1+E2 and both rights)
    add([pp("C100a", d(10), 30000), pp("P100a", d(11), 20000), pp("C100b", d(12), 10000),
         pp("C110b", d(13), 20000), pp("C120c", d(14), 20000)], ["share_edge", "f7_strike_sum"], noisy=True)   # 1 strike 60000/100000, expiry max 50%
    add([pp("C100a", d(10), 30000), pp("P100a", d(11), 20000), pp("C100b", d(12), Fr("9999.99"), size=1),
         pp("C110b", d(13), 20000), pp("C120c", d(14), Fr("20000.01"), size=1)], ["share_edge", "f7_strike_sum"])  # 2 just below
    add([pp("C100a", d(10), 30000), pp("P100a", d(11), 20000), pp("C100b", d(12), Fr("10000.01"), size=1),
         pp("C110b", d(13), 20000), pp("C120c", d(14), Fr("19999.99"), size=1)], ["share_edge", "f7_strike_sum"])  # 3 just above
    add([pp("C100a", d(10), 35000), pp("C100b", d(11), 35000), pp("C110a", d(12), 15000), pp("P90b", d(13), 15000)],
        ["f7_strike_sum", "fire_strike_only"])                                                                  # 4 70% strike, expiry 50/50
    add([pp("C100a", d(10), 35000), pp("P100a", d(11), 35000), pp("C110b", d(12), 10000), pp("P90b", d(13), 20000)],
        ["f7_strike_sum", "fire_strike_only"])                                                                  # 5 across rights
    add([pp("C100a", d(10), 20000), pp("C110a", d(11), 20000), pp("P90a", d(12), 20000), pp("C100b", d(13), 20000),
         pp("C110b", d(14), 20000)], ["f7_expiry_sum", "fire_expiry_only", "share_edge"])                       # 6 expiry E1 60%
    add([pp("C100a", d(10), 70000), pp("C110b", d(11), 30000)], ["fire_both"])                                  # 7
    add([pp("C100a", d(10), 25000), pp("C110b", d(11), 25000), pp("P90a", d(12), 25000), pp("C120c", d(13), 25000)],
        ["fire_none"])                                                                                          # 8
    add([pp("C100a", d(10), 50000), pp("C110a", d(11), 50000)], ["f7_tie_strike", "ties"])                      # 9 tie strike -> 100
    add([pp("C100a", d(10), 50000), pp("C100b", d(11), 50000)], ["f7_tie_expiry", "ties"])                      # 10 tie expiry -> E1
    add([pp("C100a", d(10), 12345)], ["single_print"])                                                          # 11
    add([], ["zero_denominator", "reason_closed"])                                                              # 12
    add([pr("C100a", d(10), "50.0000", 10, mult=10)], ["zero_denominator", "nonstd_counted"])                   # 13
    add([pr("C100a", d(10), "500.0000", 10, mult=10), pp("C110b", d(11), 10000), pp("C100a", d(12), 15000)],
        ["f7_denominator", "nonstd_counted"])                                                                   # 14
    add([pr("C100a", d(10), "500.0000", 10, excl=1), pp("C110b", d(11), 10000), pp("C100a", d(12), 15000)],
        ["f7_denominator", "cond_excl_counted"])                                                                # 15
    add([pp("C100a", -S(300), 70000), pp("C110b", d(10), 30000)], ["win_open_start"])                           # 16
    add([pp("C100a", -S(300) - 1, 70000), pp("C110b", d(10), 30000)], ["win_open_start", "boundary_out"])       # 17
    add([pp("C100a", 1, 700000), pp("C110b", d(10), 30000), pp("C100a", d(20), 10000)], ["lookahead", "win_open_end"])  # 18
    add([pp("C100a", d(30), 70000), pp("C110b", d(61), 30000)], ["window_len"], W=60)                           # 19
    add([pp("C100a", d(30), 70000), pp("C110b", d(800), 30000)], ["window_len"], W=900)                         # 20
    add([pp("C100a", d(30), 70000), pp("C110b", d(3500), 30000), pp("C110b", d(3700), 900000)], ["window_len"], W=3600)  # 21
    add([pp("C100a", d(10), 10000), pp("C110a", d(11), 20000), pp("P90a", d(12), 30000), pp("C120c", d(13), 25000),
         pp("C100b", d(14), 15000)], ["f7_strike_sum", "f7_expiry_sum"])                                        # 22
    add([pp("C100a", d(10), 10000), pp("C110b", d(11), 20000), pp("P90b", d(12), 30000), pp("C120c", d(13), 15000),
         pp("C100b", d(14), 25000)], ["f7_expiry_sum", "f7_strike_sum"])                                        # 23
    add([pp("C100a", d(10), 7000), pp("C110a", d(11), 5000)], ["fraction_share"])                               # 24 7/12
    add([pp("C100a", d(10), 1000), pp("C110a", d(11), 1000)], ["share_edge", "f7_tie_strike"], th="1/2")        # 25 exactly 1/2
    add([pp("C100a", d(10), 4000), pp("C100b", d(11), 4000), pp("C110a", d(12), 5000), pp("C120c", d(13), 3000)],
        ["f7_strike_sum", "f7_expiry_sum"])                                                                     # 26
    add([pp("C100a", d(10), 30000), pp("P100a", d(11), 30000), pp("C110b", d(12), 40000)], ["share_edge", "f7_strike_sum", "both_rights"])  # 27
    # strike summed across expiries beats the single largest contract
    add([pp("C110a", d(10), 40000), pp("C100a", d(11), 30000), pp("C100b", d(12), 30000)], ["f7_strike_sum", "top_strike_summed"])  # 28 top 100 (60000) vs 110 (40000)
    add([pp("C100a", d(10), 40000), pp("C110b", d(11), 30000), pp("C120c", d(12), 15000), pp("P120c", d(13), 15000),
         pp("P90b", d(14), 30000)], ["f7_expiry_sum", "top_expiry_summed"])                                     # 29
    add([pp("C100a", d(10), 20000), pp("C110a", d(11), 20000), pp("P90a", d(12), 20000)], ["f7_tie_strike", "f7_tie_expiry", "ties"])  # 30 3-way strike tie, expiry all E1
    add([pp("C120c", d(10), 20000), pp("C110b", d(11), 20000), pp("C100a", d(12), 20000)], ["f7_tie_strike", "f7_tie_expiry", "ties"])  # 31 3-way both
    add([pr("C100a", d(10), "5000.0000", 100, excl=1)], ["zero_denominator", "cond_excl_counted"])                                          # 32
    add([pr("C100a", d(10), "5000.0000", 100, mult=10), pp("C110b", d(11), 40000), pp("C100b", d(12), 35000),
         pp("C100a", d(13), 25000)], ["f7_denominator", "nonstd_counted", "f7_strike_sum"])                    # 33
    add([pp("C100a", d(10), 30000, seq=0), pp("C100a", d(10), 30000, seq=1), pp("C110a", d(11), 40000)],
        ["ties", "share_edge"])                                                                                  # 34
    add([pp("C100a", d(10), 36000), pp("C110b", d(11), 24000), pp("P90a", d(12), 20000), pp("C120c", d(13), 20000)],
        ["share_edge", "fire_both"], th="9/25")                                                                  # 35 36% = 9/25 exactly
    add([pp("C100a", d(10), 60000), pp("C110b", d(11), 40000)], ["share_edge", "fire_both", "f7_strike_sum"])  # 36 strike 0.6; expiry E1 .6 too
    R.add("M2-6", "flow.md F7; matrix M2-6", "Q10", mkin([pp("C100a", d(10), 70000), pp("C110b", d(11), 30000)], contracts=CON7, sess=sess), {},
          tags=["default_omitted"])                                                                    # 37
    add([pr("C100a", d(10), "500.0000", 10, mult=10, excl=1), pr("C100a", d(11), "500.0000", 10, mult=10), pp("C110b", d(12), 10000),
         pp("C100a", d(13), 15000)], ["coverage_keys", "both_excl", "f7_denominator"])                 # 38
    assert len(R.rows) == 38, len(R.rows)
    return R.rows


if __name__ == "__main__":
    main_for("F7", "F7", build)
