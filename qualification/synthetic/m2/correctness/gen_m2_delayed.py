"""Delayed-feed tag (M2-1 column): 8 rows. F1, F12, intraday F2 and intraday F10 give invalid_input delayed_feed_tag;
end-of-day forms are computed and labelled delayed."""
from m2common import *
from f2lib import f2_intraday, f2_eod
from gen_m2_F10F20 import f10_hist


def build(rng):
    R = Rows("delayed", "M2-DLY")
    d = lambda s: -S(s)
    tg = ["delayed", "delay_ignored"]
    base = [pp("C1", d(30), 20000), pp("C1", d(500), 80000)]
    R.add("M2-1", "matrix M2-1 degradation", "Q11", mkin(base, sess=session("2026-06-01", S(1800), 390, delay="delayed")),
          {"filter": "all", "N": 3}, tags=tg)                                                  # 1
    pts = [None] * 15 + [[3000, 15000], [1000, 15000]]
    R.add("M2-11", "matrix M2-11 Q11", "Q11", {"t_ns": T0, "series_id": "SYN1", "points": pts,
          "session": session("2026-06-01", S(60 * 16), 390, delay="delayed")},
          {"N": 3, "quiet_gap": 1, "n_episodes": 1, "grid_s": 60}, tags=tg)                    # 2
    f2_intraday(R, "premium", 15, delay="delayed", tags=tg + ["f2"])                           # 3
    f2_intraday(R, "prints", 15, delay="delayed", tags=tg + ["f2"])                            # 4
    cal, cur, h = f10_hist(10, [], 300, 20)
    R.add("M2-7", "matrix M2-7", "Q4,Q5", mkin([pr("C1", -S(10), "1.0000", 25)], sess=session(cur, S(1800), 20, delay="delayed"), cal=cal, histo=h),
          {"window_s": 300, "N": "2", "filter": "all", "K": 20}, tags=tg + ["f10"])             # 5
    f2_eod(R, "premium", 1, delay="delayed", tags=["delayed", "eod", "label_delayed"])         # 6
    f2_eod(R, "contracts", 2, delay="delayed", tags=["delayed", "eod", "label_delayed"])       # 7
    R.add("M2-1", "matrix M2-1", "Q11", mkin([], sess=session("2026-06-01", S(100), 390, delay="delayed")),
          {"filter": "all", "N": 3}, tags=tg + ["gate_order", "insufficient_window"])          # 8 invalid_input before insufficient_window
    R.add("M2-11", "matrix M2-11", "Q11", {"t_ns": T0, "series_id": "SYN1", "points": [None] * 15 + [[3000, 15000]],
          "session": session("2026-06-01", S(100), 390, delay="delayed")}, {"N": 3, "quiet_gap": 1, "n_episodes": 1, "grid_s": 60},
          tags=tg + ["gate_order", "insufficient_window"])                                         # 9
    assert len(R.rows) == 9
    return R.rows


if __name__ == "__main__":
    main_for("delayed", "delayed", build)
