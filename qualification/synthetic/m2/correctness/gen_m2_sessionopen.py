"""Session-open window rule (Q7): 12 rows. F1, F2, F10, F12 are insufficient_window before open + W, available at exactly W,
and the history n after dropping, per session, the grid points before open + W is asserted."""
from m2common import *

W = 900
MIN = 40


def hist_open(metric, base, planted, spike):
    cal, prior_ids, cur = mkcal([MIN] * 20, MIN)
    drop = W // 60
    ov = [[] for _ in range(20)]
    for t in range(planted[0]):
        ov[t % 20].append((drop + t // 20, planted[1]))
    recs = []
    for j, sid in enumerate(prior_ids):
        o = [(i, spike) for i in range(drop)] + ov[j]       # spikes at every dropped grid point (indices 0..14)
        recs.append(hs(sid, MIN, base=base, over=o))
    return cal, cur, hist("SYN1", metric, recs, window_s=W)


def build(rng):
    R = Rows("sessionopen", "M2-OPEN")
    d = lambda s: -S(s)
    base = [pp("C1", d(30), 20000), pp("C1", d(500), 80000)]
    tg = ["session_open", "insufficient_window"]
    for el, t in ((S(900) - 1, tg), (S(900), ["session_open", "elapsed_exact_W"]), (S(900) + 1, ["session_open", "elapsed_exact_W"])):
        R.add("M2-1", "matrix Q7", "Q7", mkin(base, sess=session("2026-06-01", el, 390)), {"filter": "all", "N": 3}, tags=t)   # 1-3
    for el, t in ((S(900) - 1, tg), (S(900), ["session_open", "elapsed_exact_W", "drop_pre_open", "history_n"]),
                  (S(900) + 1, ["session_open", "elapsed_exact_W", "drop_pre_open", "history_n"])):
        cal, cur, h = hist_open("premium", usd(100), (25, usd(1000)), usd(9000000))
        R.add("M2-2", "matrix Q7", "Q1,Q7", mkin([pp("C1", d(10), 1000)], sess=session(cur, el, MIN), cal=cal, histo=h),
              {"form": "intraday", "metric": "premium", "window_s": W, "X": 5, "K": 20}, tags=t)                           # 4-6
    for el, t in ((S(900) - 1, tg), (S(900), ["session_open", "elapsed_exact_W", "drop_pre_open", "history_n", "median_n"]),
                  (S(900) + 1, ["session_open", "elapsed_exact_W", "drop_pre_open", "history_n", "median_n"])):
        cal, cur, h = hist_open("contracts", 10, (100, 40), 7777)
        R.add("M2-7", "matrix Q7", "Q4,Q7", mkin([pr("C1", -S(10), "1.0000", 30)], sess=session(cur, el, MIN), cal=cal, histo=h),
              {"window_s": W, "N": "2", "filter": "all", "K": 20}, tags=t)                                              # 7-9
    pts = [None] * 15 + [[3000, 15000], [1000, 15000]]
    for kT, el, t in ((15, S(899) + 999999999, tg), (15, S(900), ["session_open", "elapsed_exact_W"]), (16, S(960), ["session_open", "elapsed_exact_W"])):
        R.add("M2-11", "matrix Q7", "Q7,Q11", {"t_ns": T0, "series_id": "SYN1", "points": pts, "session": session("2026-06-01", el, 390)},
              {"N": 3, "quiet_gap": 1, "n_episodes": 1, "grid_s": 60}, tags=t + ["f12"], pending=None)                   # 10-12
    for r in R.rows[9:]:
        v = r["expected"]["value"]
        if v and v["episode_count"] >= 1:
            pass
    assert len(R.rows) == 12
    return R.rows


if __name__ == "__main__":
    main_for("sessionopen", "sessionopen", build)
