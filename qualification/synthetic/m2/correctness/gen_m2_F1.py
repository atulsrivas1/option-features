"""M2-1 F1 premium surge: 36 rows (Q7 window rule, matrix M2-1)."""
from m2common import *


def build(rng):
    R = Rows("F1", "M2-F1")
    sid = "2026-06-01"

    def add(prints, tags, filt="all", N=3, el=S(1800), pending=None, noisy=False, ruling="Q7", contracts=None):
        ps = list(prints) + (noise(rng, 3) if noisy else [])
        sess = session(sid, el, 390)
        inp = mkin(ps, contracts=contracts, sess=sess)
        R.add("M2-1", "flow.md F1; matrix M2-1", ruling, inp, {"filter": filt, "N": N}, tags=tags, pending=pending)

    d = lambda s: -S(s)
    A, B = 20000, 80000
    base = lambda a=A: [pp("C1", d(30), a), pp("C1", d(500), B)]
    add(base(), ["f1_boundary_N", "float_ratio", "ratio_inverted", "f1_factor15"], noisy=True)           # 1 ratio == N
    add(base(Fr(19990)), ["f1_boundary_N", "float_ratio"])                                              # 2 just below
    add(base(Fr(20010)), ["f1_boundary_N", "float_ratio"])                                              # 3 just above
    add([], ["zero_denominator"])                                                                       # 4
    add([pp("C1", d(901), 50000)], ["zero_denominator", "win_open_start"])                              # 5
    mix = [pp("C1", d(30), A), pp("C1", d(500), B), pp("P1", d(20), 90000)]
    add(mix, ["filter"], filt="calls")                                                                  # 6
    add(mix, ["filter"], filt="puts")                                                                   # 7
    add(mix, ["filter"], filt="all")                                                                    # 8
    add([pp("C1", d(10), 5000)], ["overlap", "w900_for_60", "ratio_inverted", "f1_factor15"])           # 9 ratio 15
    add([pp("C1", d(61), 5000)], ["overlap", "w900_for_60", "ratio_inverted"])                          # 10 P60=0
    add([pp("C1", d(60), 7000), pp("C1", d(800), 21000)], ["win_open_start", "boundary60"])            # 11 at T-60 exactly
    add([pp("C1", -S(60) - 1, 7000), pp("C1", d(800), 21000)], ["boundary60", "w900_for_60"])           # 12 T-60-1ns
    add([pp("C1", 0, 7000), pp("C1", d(800), 21000)], ["win_open_end", "boundary60"])                   # 13 at T
    add([pp("C1", 1, 9000000), pp("C1", d(30), A), pp("C1", d(500), B)], ["lookahead", "win_open_end"])  # 14 T+1ns
    add([pp("C1", -S(900), 30000), pp("C1", d(30), 4000)], ["win_open_start", "boundary900"])          # 15 at T-900
    add([pp("C1", -S(900) - 1, 30000), pp("C1", d(30), 4000)], ["boundary900", "w900_for_60"])          # 16
    add(mix + [pr("C1", d(10), "50.0000", 10, mult=10)], ["nonstd_counted"])                            # 17
    add(mix + [pr("C1", d(10), "50.0000", 10, excl=1)], ["cond_excl_counted"])                          # 18
    add(mix + [pr("C1", d(10), "50.0000", 10, mult=10), pr("P1", d(40), "9.0000", 10, mult=1),
               pr("C1", d(11), "50.0000", 10, excl=1), pr("C1", d(12), "50.0000", 10, excl=1),
               pr("P1", d(13), "50.0000", 10, excl=1)], ["nonstd_counted", "cond_excl_counted"])        # 19
    add([pp("C1", d(30), 10000, seq=0), pp("C1", d(30), 10000, seq=1), pp("C1", d(500), 80000)],
        ["ties", "f1_boundary_N"])                                                                      # 20
    add(base(Fr(25000)), ["custom_N"], N=2)                                                             # 21 ratio 25000*15/105000=25/7
    add(base(), ["custom_N"], N=4)                                                                      # 22
    add([pp("C1", d(30 + i), 1000, size=10) for i in range(30)] + [pp("C1", d(400), 20000)], ["many_prints"])  # 23
    add([pp("C1", d(10), 4000), pp("P1", d(700), 90000)], ["filter", "float_ratio"], N=1)               # 24
    add(base(), ["insufficient_window"], el=S(900) - 1, pending=None)                                  # 25
    add([], ["insufficient_window", "gate_order"], el=S(600))                                           # 26 not zero_denominator
    add(base(), ["elapsed_exact_W"], el=S(900))                                                          # 27
    add(base(), ["elapsed_exact_W"], el=S(900) + 1)                                                      # 28
    add(base(), ["insufficient_window"], el=0)                                                           # 29
    add([pr("C1", d(10), "40.0000", 10, mult=10)], ["zero_denominator", "nonstd_counted"])               # 30
    add([pr("C1", d(10), "40.0000", 10, excl=1)], ["zero_denominator", "cond_excl_counted"])             # 31
    add([pp("C1", d(30), 18000), pp("C1", d(500), 82000)], ["float_ratio"])                              # 32 27/10
    add([pp("C1", d(30), 1000), pp("C1", d(500), 44000)], ["float_ratio", "f1_factor15"])                # 33 1/3
    add([pp("P1", d(30), 20000), pp("P1", d(500), 80000)], ["filter", "zero_denominator"], filt="calls")  # 34
    add([pp("P1", d(30), 20000), pp("P2", d(40), 5000), pp("P2", d(500), 75000), pp("C1", d(20), 99000)],
        ["filter"], filt="puts")                                                                         # 35
    add([pp("C1", d(30), 8000), pp("C2", d(31), 7000), pp("P2", d(32), 5000), pp("P1", d(890), 80000)],
        ["multi_contract"])                                                                              # 36
    add(mix + [pr("C1", d(10), "50.0000", 10, mult=10, excl=1)], ["both_excl", "cond_excl_counted"])  # 37 both flags: counted once, excluded_condition
    both2 = [pp("P1", d(30), 20000), pp("C1", d(500), 80000), pr("P1", d(20), "50.0000", 10, mult=10, excl=1),
             pr("C1", d(21), "50.0000", 10, mult=10, excl=1), pr("C1", d(22), "50.0000", 10, mult=10)]
    add(both2, ["both_excl", "cond_excl_counted", "nonstd_counted", "coverage_keys"])                    # 38 two both-flag prints + one nonstd only
    def addp(prints, tags, prm, el=S(1800)):
        R.add("M2-1", "flow.md F1; matrix M2-1", "Q7", mkin(prints, sess=session(sid, el, 390)), prm, tags=tags)
    addp(base(), ["no_window_param"], {"filter": "all", "N": 3, "window_s": 120})                     # 39 window ignored
    addp(base(), ["no_window_param"], {"filter": "all", "N": 3, "window_s": 3600})                    # 40
    addp(base(), ["default_omitted"], {})                                                              # 41 N=3, filter all
    addp(mix, ["default_omitted", "filter"], {"filter": "puts"})                                       # 42 N omitted
    addp([], ["gate_order", "insufficient_window", "zero_denominator"], {"filter": "all", "N": 3}, el=S(100))   # 43
    addp([pp("C1", d(901), 50000)], ["gate_order", "insufficient_window", "zero_denominator"], {"filter": "all", "N": 3}, el=S(300))  # 44
    assert len(R.rows) == 44, len(R.rows)
    return R.rows


if __name__ == "__main__":
    main_for("F1", "F1", build)
