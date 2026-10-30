"""Lane isolation (Q16): 6 rows. Shares and baselines never cross lanes."""
from m2common import *
from f2lib import f2_intraday, make_hist, x_prints

LC = dict(CONTRACTS)
LC["XC1"] = K("C", 1000000, EXP1, lane="etf_index")
LC["XP1"] = K("P", 1000000, EXP1, lane="etf_index")


def build(rng):
    R = Rows("lane", "M2-LANE")
    sess = session("2026-06-01", S(4000), 390)
    V = lambda cid, dt, q: pr(cid, dt, "1.0000", q)
    d = lambda s: -S(s)
    mix = [V("P1", d(10), 20), V("C1", d(11), 80), V("XP1", d(12), 900), V("XC1", d(13), 100)]
    R.add("M2-9", "matrix Q16", "Q16", mkin(mix, contracts=LC, sess=sess), {"window_s": 300, "at_least": "1/10", "at_most": None, "lane": "stock"},
          tags=["lane_mixed", "lane"])                                                                     # 1 stock share 1/5
    R.add("M2-9", "matrix Q16", "Q16", mkin(mix, contracts=LC, sess=sess), {"window_s": 300, "at_least": "1/10", "at_most": None, "lane": "etf_index"},
          tags=["lane_mixed", "lane"])                                                                     # 2 etf share 9/10
    big = [pp("C100", d(10), 70000), pp("C110", d(11), 30000), pp("XC", d(12), 900000)]
    con = {"C100": K("C", 1000000, EXP1), "C110": K("C", 1100000, EXP1), "XC": K("C", 1100000, EXP1, lane="etf_index")}
    R.add("M2-6", "matrix Q16", "Q16", mkin(big, contracts=con, sess=sess), {"window_s": 300, "lane": "stock"},
          tags=["lane_mixed", "lane"])                                                                     # 3
    R.add("M2-6", "matrix Q16", "Q16", mkin(big, contracts=con, sess=sess), {"window_s": 300, "lane": "etf_index"},
          tags=["lane_mixed", "lane"])                                                                     # 4
    cal, cur, h = make_hist("contracts", 15, 300, 20, hvf=2)       # stock-lane history
    inp = mkin(x_prints("contracts"), sess=session(cur, S(1800), 20), cal=cal, histo=h)
    R.add("M2-7", "matrix Q16", "Q16", inp, {"window_s": 300, "N": "2", "filter": "all", "K": 20, "lane": "etf_index"},
          tags=["lane_mixed", "lane", "gate_history"])                                                     # 5 history lane mismatch
    mix1 = [pp("C1", d(30), 20000), pp("C1", d(500), 80000), pp("XC1", d(30), 400000), pp("XC1", d(500), 10000)]
    R.add("M2-1", "matrix Q16", "Q16", mkin(mix1, contracts=LC, sess=sess), {"filter": "all", "N": 3, "lane": "stock"},
          tags=["lane_mixed", "lane"])                                                                     # 6
    cal, cur, h = make_hist("contracts", 15, 300, 20, hvf=2)
    h["lane"] = "etf_index"                                                                          # 7 etf history, etf request, etf contract prints
    xe = [pr("XC1", -S(10), "1.0000", 40)]
    R.add("M2-7", "matrix Q16", "Q16", mkin(xe, contracts=LC, sess=session(cur, S(1800), 20), cal=cal, histo=h),
          {"window_s": 300, "N": 2, "filter": "all", "K": 20, "lane": "etf_index", "consumer_default": "median"}, tags=["lane", "lane_match"])
    cal2, prior_ids, cur2 = mkcal([3] * 20, 3)
    recs = [hs(s_, 3, base=0, total=100) for s_ in prior_ids]
    for lane_h in ("etf_index", "stock"):                                                            # 8: lane match; 9 added below as mismatch
        pass
    R.add("M2-8", "matrix Q16", "Q16", mkin(None, contracts=LC, sess=session(cur2, S(23400), 3, complete=True, total=200), cal=cal2,
          histo=hist("SYN1", "contracts", recs, lane="stock")), {"metric": "contracts", "N": 2, "K": 20, "lane": "etf_index", "consumer_default": "mean"},
          tags=["lane", "lane_mismatch", "gate_history"])                                            # 8 stock history, etf request
    assert len(R.rows) == 8
    return R.rows


if __name__ == "__main__":
    main_for("lane", "lane", build)
