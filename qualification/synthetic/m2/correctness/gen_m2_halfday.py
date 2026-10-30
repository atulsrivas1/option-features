"""Half-day sessions (Q1, Q3): 10 rows. Grid length per session comes from the calendar; counts use actual length."""
from m2common import *

FULL, HALF = 390, 210


def fill_seq(count, value, drop, minutes_list):
    """plant `count` values sequentially, session by session, at indices >= drop"""
    ov = [[] for _ in minutes_list]
    left = count
    for j, m in enumerate(minutes_list):
        for i in range(drop, m):
            if left == 0:
                break
            ov[j].append((i, value))
            left -= 1
    assert left == 0
    return ov


def build(rng):
    R = Rows("halfday", "M2-HALF")

    def world(minutes_list, cur_minutes=FULL):
        cal, prior_ids, cur = mkcal(minutes_list, cur_minutes)
        return cal, prior_ids, cur

    def hist_for(prior_ids, minutes_list, metric, base, count, value, drop=5, spikes=True, extra_value=None):
        ov = fill_seq(count, value, drop, minutes_list)
        if extra_value is not None:
            jj = max(j for j in range(len(ov)) if ov[j])
            ov[jj][-1] = (ov[jj][-1][0], extra_value)
        recs = []
        for j, sid in enumerate(prior_ids):
            o = ([(0, 10 ** 9)] if spikes else []) + ov[j]
            recs.append(hs(sid, minutes_list[j], base=base, over=o))
        return hist("SYN1", metric, recs, window_s=300)

    mixed = [FULL] * 7 + [HALF] + [FULL] * 6 + [HALF] + [FULL] * 3 + [HALF] + [FULL] * 1      # 17 full + 3 half
    n_mixed = sum(m - 5 for m in mixed)                                                           # 7160
    allhalf = [HALF] * 20
    x_prem = [pp("C1", -S(10), 1000, size=10)]
    xv = usd(1000)
    prm = lambda m: {"form": "intraday", "metric": m, "window_s": 300, "X": 5, "K": 20}
    T = ["half_day", "grid_length"]
    for k, tags in ((358, ["upper_share_boundary"]), (359, ["upper_share_boundary"])):             # 1-2 exactly 5% of 7160
        cal, ids, cur = world(mixed)
        h = hist_for(ids, mixed, "premium", usd(100), k, xv)
        R.add("M2-2", "matrix Q1,Q3", "Q1,Q3", mkin(x_prem, sess=session(cur, S(1800), FULL), cal=cal, histo=h), prm("premium"),
              tags=T + tags + ["half_day_390", "fires_exclusive"])
    cal, ids, cur = world(mixed)
    h = hist_for(ids, mixed, "contracts", 5, 357, 40)                                              # 3 k=357 fires
    R.add("M2-2", "matrix Q1,Q3", "Q1,Q3", mkin([pr("C1", -S(10), "1.0000", 40)], sess=session(cur, S(1800), FULL), cal=cal, histo=h),
          prm("contracts"), tags=T + ["upper_share_boundary", "half_day_390"])
    cal, ids, cur = world(allhalf)                                                                 # 4 n = 20*205 = 4100, k=205
    h = hist_for(ids, allhalf, "premium", usd(100), 205, xv)
    R.add("M2-2", "matrix Q1,Q3", "Q1,Q3", mkin(x_prem, sess=session(cur, S(1800), FULL), cal=cal, histo=h), prm("premium"),
          tags=T + ["upper_share_boundary", "half_day_390", "fires_exclusive"])
    cal, ids, cur = world([FULL] * 20, HALF)                                                       # 5 today half day
    h = hist_for(ids, [FULL] * 20, "premium", usd(100), 385, xv)
    R.add("M2-2", "matrix Q1,Q3", "Q1,Q3", mkin(x_prem, sess=session(cur, S(1800), HALF), cal=cal, histo=h), prm("premium"),
          tags=T + ["upper_share_boundary", "today_half_day"])
    # F10 median over mixed lengths: half the 7160 values are 10, half are 30 -> median (10+30)/2 = 20
    cal, ids, cur = world(mixed)                                                                   # 6
    h = hist_for(ids, mixed, "contracts", 10, n_mixed // 2, 30, extra_value=1000)
    R.add("M2-7", "matrix Q1,Q4", "Q1,Q4", mkin([pr("C1", -S(10), "1.0000", 40)], sess=session(cur, S(1800), FULL), cal=cal, histo=h),
          {"window_s": 300, "N": "2", "filter": "all", "K": 20}, tags=T + ["median_n", "even_median", "half_day_390"])
    cal, ids, cur = world([HALF] * 19 + [FULL])                                                    # 7 mean weighted by actual length
    ml = [HALF] * 19 + [FULL]
    h = hist_for(ids, ml, "contracts", 10, 100, 50)
    R.add("M2-7", "matrix Q1,Q4", "Q1,Q4", mkin([pr("C1", -S(10), "1.0000", 40)], sess=session(cur, S(1800), FULL), cal=cal, histo=h),
          {"window_s": 300, "N": "2", "filter": "all", "K": 20}, tags=T + ["median_n", "half_day_390"])
    # F20: half-day sessions are sessions; totals count as given
    cal, ids, cur = world(mixed)                                                                   # 8
    recs = [hs(sid, mixed[j], base=0, total=(300 if mixed[j] == HALF else 600)) for j, sid in enumerate(ids)]
    R.add("M2-8", "matrix Q3", "Q3,Q4", mkin(None, contracts=CONTRACTS, sess=session(cur, S(23400), FULL, complete=True, total=900), cal=cal,
          histo=hist("SYN1", "contracts", recs)), {"metric": "contracts", "N": "2", "K": 20}, tags=T + ["half_day_session_counts"])
    cal, ids, cur = world(mixed)                                                                   # 9 F19 over half days
    recs = [hs(sid, mixed[j], base=0, total=0, put=10 + j, call=10) for j, sid in enumerate(ids)]
    R.add("M2-10", "matrix Q3", "Q3,Q13", mkin(None, contracts=CONTRACTS, sess=session(cur, S(23400), FULL, complete=True, put=28, call=10), cal=cal,
          histo=hist("SYN1", "put_volume", recs)), {"X": 5, "K": 20}, tags=T + ["half_day_session_counts"])
    cal, ids, cur = world(mixed)                                                                   # 10 half-day record missing: not substituted
    h = hist_for(ids, mixed, "premium", usd(100), 358, xv)
    h["sessions"] = [s for s in h["sessions"] if s["minutes"] != HALF or s["session_id"] != ids[7]]
    h["expansion_sha256"] = exp_hash(h["sessions"])
    R.add("M2-2", "matrix Q3", "Q3", mkin(x_prem, sess=session(cur, S(1800), FULL), cal=cal, histo=h), prm("premium"),
          tags=T + ["gate_history", "missing_calendar_session"])
    assert len(R.rows) == 10, len(R.rows)
    return R.rows


if __name__ == "__main__":
    main_for("halfday", "halfday", build)
