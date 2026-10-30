"""M2-2 F2a-F2c (60), M2-3 F2d (12), F2d direction Q14 (8), F2c definition Q18 (8) = 88 rows."""
from f2lib import *


def build(rng):
    R = Rows("F2", "M2-F2")
    T = ["rank", "upper_share_boundary"]
    for m in ("premium", "contracts", "prints"):                       # A 9
        for k in (14, 15, 16):
            f2_intraday(R, m, k, tags=T + ["drop_pre_open", "fires_exclusive", "rank_strict_gt"])
    f2_intraday(R, "premium", 3, tags=T + ["top1"])                    # B 6
    f2_intraday(R, "premium", 18, tags=T + ["top6"], hvf=2)
    f2_intraday(R, "contracts", 150, tags=T + ["top50"])
    f2_intraday(R, "contracts", 0, tags=T + ["above_all"])
    f2_intraday(R, "prints", 3, tags=T + ["top1"], hvf=2)
    f2_intraday(R, "prints", 150, tags=T + ["top50"])
    for m in ("premium", "contracts", "prints"):                       # C 5
        f2_intraday(R, m, 0, const=True, tags=T + ["constant_history", "fires_exclusive"])
    f2_intraday(R, "premium", 0, zero=True, tags=T + ["zero_history", "fires_exclusive", "rank_le_as_upper"])
    f2_intraday(R, "contracts", 0, zero=True, tags=T + ["zero_history", "fires_exclusive", "rank_le_as_upper"])
    f2_intraday(R, "premium", 15, cur_in_store=True, tags=T + ["today_excluded"])        # D 2
    f2_intraday(R, "contracts", 15, cur_in_store=True, tags=T + ["today_excluded"], hvf=2)
    f2_intraday(R, "premium", 15, nstore=19, tags=["history_count", "gate_history"])      # E 9
    f2_intraday(R, "prints", 15, nstore=19, tags=["history_count", "gate_history"])
    f2_intraday(R, "contracts", 15, tags=["history_count"], hvf=2)
    f2_intraday(R, "premium", 15, nprior=21, nstore=21, old_big=True, tags=["history_count", "k21"])
    f2_intraday(R, "prints", 15, nprior=21, nstore=21, old_big=True, tags=["history_count", "k21"])
    f2_intraday(R, "premium", 15, incomplete_idx=7, tags=["incomplete_session", "gate_history"])
    f2_intraday(R, "prints", 15, incomplete_idx=7, tags=["incomplete_session", "gate_history"])
    f2_intraday(R, "premium", 15, nprior=19, nstore=19, extra_ids=("2025-12-31",),
                tags=["missing_calendar_session", "gate_history", "sess_not_cal_current_only"])
    f2_intraday(R, "contracts", 15, nprior=19, nstore=19, extra_ids=("2025-12-31",),
                tags=["missing_calendar_session", "gate_history", "sess_not_cal_current_only"])
    for m in ("premium", "contracts"):                                 # F 15
        for k in (0, 1, 2):
            f2_eod(R, m, k, tags=["eod", "upper_share_boundary", "rank", "fires_exclusive", "rank_strict_gt"])
    f2_eod(R, "premium", 1, complete=False, tags=["eod", "session_not_complete"])
    f2_eod(R, "contracts", 1, complete=False, tags=["eod", "session_not_complete"])
    f2_eod(R, "premium", 1, nstore=0, tags=["eod", "gate_history", "nothing_stored"])
    f2_eod(R, "contracts", 1, nstore=0, tags=["eod", "gate_history", "nothing_stored"])
    for m in ("premium", "contracts", "prints"):
        f2_intraday(R, m, 15, nstore=0, tags=["gate_history", "nothing_stored"])
    f2_eod(R, "premium", 2, X=10, tags=["eod", "upper_share_boundary", "fires_exclusive"])
    f2_eod(R, "premium", 2, X=10, complete=False, tags=["eod", "session_not_complete"])
    for m in ("premium", "contracts", "prints"):                       # G 6
        f2_intraday(R, m, 15, el=S(299), tags=["insufficient_window", "pre_open_window"])
    for m in ("premium", "contracts"):
        f2_intraday(R, m, 15, el=S(10), nstore=0, tags=["gate_order", "gate_history", "insufficient_window"])
    f2_eod(R, "premium", 1, complete=False, nstore=0, tags=["gate_order", "gate_history", "eod"])
    f2_intraday(R, "contracts", 19, W=60, minutes=20, tags=["window_len", "upper_share_boundary"])   # H 4
    f2_intraday(R, "premium", 25, W=900, minutes=40, tags=["window_len", "upper_share_boundary"])
    f2_intraday(R, "contracts", 30, W=1800, minutes=60, tags=["window_len", "upper_share_boundary"])
    f2_intraday(R, "premium", 10, W=3600, minutes=70, tags=["window_len", "upper_share_boundary"])
    f2_intraday(R, "premium", 3, X=1, tags=T + ["x_param", "fires_exclusive"])                       # I 4
    f2_intraday(R, "premium", 4, X=1, tags=T + ["x_param"])
    f2_intraday(R, "contracts", 30, X=10, tags=T + ["x_param", "fires_exclusive"])
    f2_intraday(R, "contracts", 31, X=10, tags=T + ["x_param"])
    assert len(R.rows) == 60, len(R.rows)
    D = ["f2d"]                                                        # F2d 12
    f2d(R, (0, 0, 0), tags=D)
    f2d(R, (15, 15, 15), tags=D)
    f2d(R, (3, 150, 60), tags=D)
    f2d(R, (15, 15, 15), hvf=1, tags=D + ["ties"])
    f2d(R, (15, 15, 15), missing=("F2a",), tags=D + ["part_unavailable", "gate_history", "partial_average"])
    f2d(R, (15, 15, 15), missing=("F2b",), tags=D + ["part_unavailable", "gate_history", "partial_average"])
    f2d(R, (15, 15, 15), missing=("F2c",), tags=D + ["part_unavailable", "gate_history", "partial_average"])
    f2d(R, (15, 15, 15), missing=("F2a", "F2c"), tags=D + ["part_unavailable", "precedence"])
    f2d(R, (15, 15, 15), missing=("F2b", "F2c"), tags=D + ["part_unavailable", "precedence"])
    f2d(R, (15, 15, 15), el=S(100), tags=D + ["insufficient_window", "precedence"])
    f2d(R, (15, 15, 15), el=S(100), missing=("F2b",), tags=D + ["precedence", "gate_order"])
    f2d(R, (15, 15, 15), el=S(100), missing=("F2a",), tags=D + ["precedence", "gate_order"])
    Q = ["f2d", "direction"]                                           # Q14 8
    f2d(R, (1, 2, 3), tags=Q + ["pct_is_upper_share"])
    f2d(R, (299, 299, 299), tags=Q + ["pct_is_upper_share"])
    f2d(R, (300, 300, 300), hvf=1, tags=Q + ["ties"])
    f2d(R, (150, 150, 150), hvf=1, tags=Q + ["ties"])
    f2d(R, (100, 200, 300), tags=Q + ["pct_is_upper_share"])
    f2d(R, (10, 20, 30), missing=("F2c",), tags=Q + ["part_unavailable", "partial_average"])
    f2d(R, (5, 10, 15), tags=Q + ["pct_is_upper_share"])
    f2d(R, (0, 300, 300), tags=Q + ["pct_is_upper_share"])
    C = ["f2c_rate", "window_len"]                                     # Q18 8
    for W, mins in ((60, 20), (300, 20), (900, 40), (1800, 60), (3600, 70)):
        f2_intraday(R, "prints", 15, W=W, minutes=mins, tags=C, ruling="Q18", ref="matrix M2-2 F2c; Q18", hvf=2)
    cal, cur, h = make_hist("prints", 15, 300, 20, hvf=2)
    prm = {"form": "intraday", "metric": "prints", "window_s": 300, "X": 5, "K": 20}
    for tag, extra in (("nonstd_counted", [pr("C1", -S(5), "1.0000", 1, mult=10), pr("C1", -S(6), "1.0000", 1, mult=10)]),
                       ("cond_excl_counted", [pr("C1", -S(5), "1.0000", 1, excl=1)])):
        inp = mkin(x_prints("prints") + extra, sess=session(cur, S(1800), 20), cal=cal, histo=h)
        R.add("M2-2", "matrix M2-2 F2c; Q18", "Q18", inp, prm, tags=C + [tag])
    inp = mkin([], contracts=CONTRACTS, sess=session(cur, S(1800), 20), cal=cal, histo=h)
    R.add("M2-2", "matrix M2-2 F2c; Q18", "Q18", inp, prm, tags=C + ["empty_window"])
    f2_intraday(R, "premium", 15, hmod={"window_s": 900}, tags=["window_mismatch", "gate_history"])          # AMB-8
    f2_intraday(R, "contracts", 15, hmod={"window_s": 900}, tags=["window_mismatch", "gate_history"])
    for k, tg in ((0, ["f2c_rate", "eod_divisor"]), (1, ["f2c_rate", "eod_divisor"]), (2, ["f2c_rate", "eod_divisor"])):   # AMB-10 F2c end of day
        f2_eod(R, "prints", k, tags=tg + ["eod", "rank"], ruling="Q18", ref="matrix M2-2 F2c end of day (PO-M2-AMB-10)")
    f2_eod(R, "prints", 1, complete=False, tags=["f2c_rate", "eod", "session_not_complete"], ruling="Q18")
    cal2, ids2, cur2 = mkcal([2] * 20, 4)
    recs2 = [hs(s_, 2, base=0, total=20) for s_ in ids2]
    R.add("M2-2", "matrix M2-2 F2c end of day", "Q18", mkin(None, contracts=CONTRACTS, sess=session(cur2, S(23400), 4, complete=True, total=36),
          cal=cal2, histo=hist("SYN1", "prints", recs2)), {"form": "end_of_day", "metric": "prints", "X": 5, "K": 20},
          tags=["f2c_rate", "eod_divisor", "eod", "f2c_eod_raw_count"])                                                 # rate 9 vs history 10
    f2_intraday(R, "premium", 15, minimal=True, tags=["rank"])                                              # AMB-19
    f2_eod(R, "contracts", 1, minimal=True, tags=["eod", "rank"])
    f2_intraday(R, "premium", 15, hmod={"lane": "etf_index"}, tags=["lane_mismatch", "lane", "gate_history"])  # lane mismatch
    f2_intraday(R, "contracts", 15, hmod={"lane": "etf_index"}, tags=["lane_mismatch", "lane", "gate_history"])
    f2d(R, (15, 15, 15), mismatch=("F2a",), tags=["window_mismatch", "part_unavailable", "gate_history"])     # F2d with AMB-8
    f2d(R, (15, 15, 15), mismatch=("F2c",), missing=("F2b",), tags=["window_mismatch", "part_unavailable", "precedence"])
    cal3, ids3, cur3 = mkcal([4] * 20, 2)
    recs3 = [hs(s_, 4, base=0, total=40) for s_ in ids3]
    R.add("M2-2", "matrix M2-2 F2c end of day", "Q18", mkin(None, contracts=CONTRACTS, sess=session(cur3, S(23400), 2, complete=True, total=22),
          cal=cal3, histo=hist("SYN1", "prints", recs3)), {"form": "end_of_day", "metric": "prints", "X": 5, "K": 20},
          tags=["f2c_rate", "eod_divisor", "eod", "f2c_eod_raw_count"])                                                 # rate 11 vs history 10
    f2_eod(R, "contracts", 1, complete=False, nstore=0, tags=["gate_order", "gate_history", "eod"])
    f2_eod(R, "prints", 1, extra={"window_s": 120}, tags=["f2c_rate", "eod_divisor", "eod", "no_window_param"], ruling="Q18")   # windowless: no window_not_allowed
    f2_eod(R, "contracts", 1, extra={"window_s": 45}, tags=["eod", "no_window_param"])
    assert len(R.rows) == 88 + 17, len(R.rows)
    return R.rows


if __name__ == "__main__":
    main_for("F2", "F2", build)
