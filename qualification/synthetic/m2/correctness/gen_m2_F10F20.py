"""M2-7 F10 (40 rows) and M2-8 F20 (30 rows): median_ratio and mean_ratio asserted on every row (Q4, Q5)."""
from m2common import *

PEND_STAT = "PENDING-RULING:Q4 (statistic default) AMB-1"


def plant_list(vals, drop, minutes, nsess=20):
    ov = [[] for _ in range(nsess)]
    for t, v in enumerate(vals):
        i = drop + t // nsess
        assert i < minutes
        ov[t % nsess].append((i, v))
    return ov


def f10_hist(base, vals=(), W=300, minutes=20, nstore=20, nprior=20, incomplete_idx=None, cur_in_store=False,
             old_big=False, spike0=True, extra_ids=()):
    cal, prior_ids, cur = mkcal([minutes] * nprior, minutes)
    use = prior_ids[-nstore:] if nstore else []
    ov = plant_list(list(vals), W // 60, minutes, nsess=max(1, min(20, len(use)))) if use else []
    if len(use) > 20:
        ov = [[] for _ in range(len(use) - 20)] + ov
    recs = []
    for j, sid in enumerate(use):
        o = list(ov[j]) if j < len(ov) else []
        if spike0:
            o = [(0, 7777)] + o
        b = base
        if old_big and j == 0 and len(use) > 20:
            b, o = 100000, []
        recs.append(hs(sid, minutes, base=b, over=o, complete=not (incomplete_idx is not None and j == incomplete_idx)))
    for sid_ in extra_ids:
        recs.insert(0, hs(sid_, minutes, base=100000, over=[]))
    if cur_in_store:
        recs.append(hs(cur, minutes, base=100000, over=[]))
    return cal, cur, hist("SYN1", "contracts", recs, window_s=W)


def build(rng):
    R = Rows("F10", "M2-F10")

    def f10(x, tags, base=10, vals=(), W=300, minutes=20, el=None, N=2, prints=None, pending=None, filt="all", minimal=False, hmod=None, **kw):
        cal, cur, h = f10_hist(base, vals, W, minutes, **kw)
        if hmod:
            h.update(hmod)
        el = S(W + 900) if el is None else el
        ps = prints if prints is not None else ([pr("C1", -S(10), "1.0000", x)] if x else [])
        inp = mkin(ps, sess=session(cur, el, minutes), cal=cal, histo=h)
        prm = {} if minimal else {"window_s": W, "N": fmt(N), "filter": filt, "K": 20, "consumer_default": "median"}
        R.add("M2-7", "flow.md F10; matrix M2-7", "Q4,Q5", inp, prm, tags=list(tags) + (["default_omitted"] if minimal else []), pending=pending)

    T = ["f10", "both_ratios"]
    for x in (19, 20, 21):                                                       # 1-3
        f10(x, T + ["ratio_edge", "float_ratio"])
    f10(30, T + ["contrast", "stat_swap", "mean_as_median"], vals=[1000] * 15)   # 4 mean crosses? no: median crosses, mean not
    f10(12, T + ["contrast", "stat_swap", "mean_as_median"], vals=[0] * 140)     # 5 mean crosses, median not
    f10(30, T + ["even_median", "median_middle", "stat_swap"], vals=[20] * 149 + [100], base=10)  # 6 median 15, mean 4580/300
    f10(15, T + ["even_median", "median_middle"], vals=[20] * 149 + [100], base=10)               # 7
    f10(10, T + ["median_equals_value"])                                                         # 8
    f10(40, T + ["zero_denominator", "zero_stat"], base=0, vals=[20] * 30)       # 9 median 0, mean 2
    f10(5, T + ["zero_denominator", "zero_stat"], base=0, vals=[])               # 10 both zero
    f10(0, T + ["zero_denominator", "zero_stat"], base=0, vals=[20] * 30)        # 11 x=0 zero median
    f10(0, T + ["zero_numerator"])                                               # 12 ratio 0
    f10(25, T + ["gate_history", "nothing_stored"], nstore=0)                    # 13
    f10(25, T + ["gate_history", "history_count"], nstore=19)                    # 14
    f10(25, T + ["gate_history", "incomplete_session"], incomplete_idx=3)        # 15
    f10(25, T + ["today_excluded"], cur_in_store=True)                           # 16
    f10(25, T + ["history_count", "k21"], nprior=21, nstore=21, old_big=True)    # 17
    for W, mins in ((60, 20), (900, 40), (1800, 60), (3600, 70)):                # 18-21
        f10(30, T + ["window_len"], W=W, minutes=mins, vals=[40] * 10)
    f10(25, T + ["window_not_allowed", "structural"], W=120)                     # 22
    f10(25, T + ["window_not_allowed", "structural"], W=45)                      # 23
    f10(25, T + ["insufficient_window", "pre_open_window"], el=S(299))           # 24
    f10(25, T + ["insufficient_window", "pre_open_window"], el=0)                # 25
    f10(25, T + ["gate_order", "gate_history", "insufficient_window"], el=S(10), nstore=0)  # 26
    f10(25, T + ["elapsed_exact_W"], el=S(300))                                  # 27
    f10(0, T + ["nonstd_counted"], prints=[pr("C1", -S(10), "1.0000", 40, mult=10), pr("C1", -S(11), "1.0000", 25)])  # 28
    f10(0, T + ["cond_excl_counted"], prints=[pr("C1", -S(10), "1.0000", 40, excl=1), pr("C1", -S(11), "1.0000", 25)])  # 29
    f10(0, T + ["win_open_start"], prints=[pr("C1", -S(300), "1.0000", 20), pr("C1", -S(300) - 1, "1.0000", 500)])      # 30
    f10(0, T + ["win_open_end"], prints=[pr("C1", 0, "1.0000", 20), pr("C1", -S(5), "1.0000", 1)])                      # 31
    f10(0, T + ["lookahead"], prints=[pr("C1", 1, "1.0000", 900), pr("C1", -S(5), "1.0000", 20)])                       # 32
    f10(25, T + ["custom_N", "ratio_edge"], N=2)                          # 33 ratio 5/2 exactly
    f10(25, T + ["custom_N", "ratio_edge"], N=2)                          # 34
    f10(0, T + ["many_prints"], prints=[pr("C1", -S(5 + i), "1.0000", 3) for i in range(7)])  # 35 x=21
    f10(61, T + ["float_ratio"], vals=[20] * 149 + [100], base=10)               # 36 fraction ratios
    f10(0, T + ["multi_contract"], prints=[pr("C1", -S(5), "1.0000", 12), pr("P2", -S(6), "1.0000", 8), pr("C2", -S(7), "1.0000", 5)])  # 37 x=25
    f10(0, T + ["filter"], filt="puts", prints=[pr("C1", -S(5), "1.0000", 12), pr("P2", -S(6), "1.0000", 8), pr("P1", -S(7), "1.0000", 5)])  # 38 x=13
    f10(0, T + ["filter"], filt="calls", prints=[pr("C1", -S(5), "1.0000", 12), pr("P2", -S(6), "1.0000", 8), pr("C2", -S(7), "1.0000", 5)])  # 39 x=17
    f10(0, T + ["boundary_out"], prints=[pr("C1", -S(301), "1.0000", 900), pr("C1", -S(5), "1.0000", 20)])  # 40
    f10(25, T + ["window_mismatch", "gate_history"], hmod={"window_s": 900})                      # 41 AMB-8
    f10(25, T + ["window_mismatch", "gate_history"], W=900, minutes=40, hmod={"window_s": 300})  # 42
    f10(25, T, minimal=True)                                                                      # 43 defaults omitted (N 2, window 300, median)
    f10(25, T + ["sess_not_cal_current_only"], extra_ids=("2025-12-31",))                         # 44 history record outside calendar: no error
    f10(25, T + ["gate_order", "gate_history", "zero_denominator"], base=0, nstore=0)             # 45 history beats zero
    f10(25, T + ["gate_order", "gate_history", "insufficient_window"], el=S(10), nstore=19)       # 46
    assert len(R.rows) == 46, len(R.rows)

    # ------------------------------------------------------------------ F20
    R2 = Rows("F20", "M2-F20")

    def f20(x, totals, tags, complete=True, metric="contracts", src=None, N=2, nstore=20, nprior=20, incomplete_idx=None,
            cur_in_store=False, old_big=False, pending=None, minimal=False):
        cal, prior_ids, cur = mkcal([3] * nprior, 3)
        use = prior_ids[-nstore:] if nstore else []
        recs = []
        tl = list(totals)
        if len(use) > len(tl):
            tl = [tl[0]] * (len(use) - len(tl)) + tl
        elif len(use) < len(tl):
            tl = tl[len(tl) - len(use):]
        for j, sid in enumerate(use):
            t = tl[j]
            if old_big and j == 0 and len(use) > 20:
                t = 10 ** 9
            recs.append(hs(sid, 3, base=0, total=t, complete=not (incomplete_idx is not None and j == incomplete_idx)))
        if cur_in_store:
            recs.append(hs(cur, 3, base=0, total=10 ** 9))
        h = hist("SYN1", metric, recs)
        sess = session(cur, S(23400), 3, complete=complete, total=x, src=src)
        inp = mkin(None, contracts=CONTRACTS, sess=sess, cal=cal, histo=h)
        prm = {"metric": metric} if minimal else {"metric": metric, "N": fmt(N), "K": 20, "consumer_default": "mean"}
        R2.add("M2-8", "flow.md 2.3 F20; matrix M2-8", "Q4", inp, prm, tags=list(tags) + (["default_omitted"] if minimal else []), pending=pending)

    U = ["f20", "both_ratios"]
    flat = lambda v: [v] * 20
    f20(200, flat(100), U + ["ratio_edge", "float_ratio"])                                       # 1 ratio exactly 2
    f20(199, flat(100), U + ["ratio_edge", "float_ratio"])                                       # 2
    f20(201, flat(100), U + ["ratio_edge", "float_ratio"])                                       # 3
    f20(250, [100] * 19 + [10100], U + ["contrast", "stat_swap", "mean_as_median"])              # 4 median fires, mean not (default mean -> not fired)
    f20(130, [0] * 8 + [100] * 12, U + ["contrast", "stat_swap", "mean_as_median"])              # 5 mean fires, median not
    f20(300, [100] * 10 + [200] * 9 + [1000], U + ["even_median", "median_middle", "stat_swap"])  # 6 median 150 mean 190
    f20(150, [100] * 10 + [200] * 9 + [1000], U + ["even_median", "median_middle"])              # 7 median ratio 1
    f20(100, flat(100), U + ["median_equals_value"])                                             # 8
    f20(90, [0] * 11 + [100] * 9, U + ["zero_denominator", "zero_stat"])                         # 9 median 0, mean 45
    f20(90, flat(0), U + ["zero_denominator", "zero_stat"])                                      # 10 both zero
    f20(0, [0] * 11 + [100] * 9, U + ["zero_denominator", "zero_stat"])                          # 11
    f20(100, flat(100), U + ["session_not_complete"], complete=False)                            # 12
    f20(100, flat(100), U + ["session_not_complete"], complete=False, metric="premium")          # 13
    f20(100, flat(100), U + ["session_not_complete"], complete=False, incomplete_idx=None, N=3)  # 14
    f20(100, flat(100), U + ["gate_order", "gate_history", "session_not_complete"], complete=False, nstore=0)  # 15
    f20(100, flat(100), U + ["gate_history", "nothing_stored"], nstore=0)                        # 16
    f20(100, flat(100), U + ["gate_history", "history_count"], nstore=19)                        # 17
    f20(100, flat(100), U + ["gate_history", "incomplete_session"], incomplete_idx=5)            # 18
    f20(300, flat(100), U + ["today_excluded"], cur_in_store=True)                               # 19
    f20(300, flat(100), U + ["history_count", "k21"], nprior=21, nstore=21, old_big=True)        # 20
    f20(5000000, flat(1000000), U + ["premium_form", "float_ratio"], metric="premium")            # 21 ticks
    f20(2500000, [1000000] * 10 + [2000000] * 10, U + ["premium_form", "even_median"], metric="premium")  # 22
    f20(200, flat(100), U + ["degraded", "supplied_eod"], src="supplied_eod")                    # 23
    f20(60, [0] * 8 + [100] * 12, U + ["degraded", "supplied_eod", "contrast"], src="supplied_eod")  # 24
    f20(100, flat(100), U + ["degraded", "supplied_eod", "session_not_complete"], src="supplied_eod", complete=False)  # 25
    f20(150, flat(100), U + ["custom_N", "ratio_edge"], N=2)                              # 26
    f20(700, [100] * 19 + [10100], U + ["custom_N", "contrast"], N=2)                     # 27 mean 600 -> 7/6 exactly
    f20(1, [3] * 7 + [4] * 13, U + ["float_ratio"])                                              # 28 median 4 mean 71/20
    f20(10, flat(0), U + ["zero_denominator", "zero_stat"], metric="premium")                                     # 29
    f20(0, flat(0), U + ["zero_denominator", "zero_stat"])                                                    # 30
    f20(200, flat(100), U + ["rank"], minimal=True)                                                          # 31 defaults omitted
    f20(10, flat(0), U + ["gate_order", "session_not_complete", "zero_denominator"], complete=False)         # 32 SNC beats zero
    f20(10, flat(0), U + ["gate_order", "gate_history", "zero_denominator"], nstore=19)                      # 33 history beats zero
    f20(100, flat(100), U + ["gate_order", "gate_history", "session_not_complete"], complete=False, nstore=19)  # 34
    assert len(R2.rows) == 34, len(R2.rows)
    return R.rows, R2.rows


def build_all(rng):
    a, b = build(rng)
    return a + b


if __name__ == "__main__":
    main_for("F10F20", "F10,F20", build_all)
