"""Structural invalid_input rows: 24 (3 per closed code of matrix section 4). One violation per row unless tagged gate_order."""
from m2common import *
from f2lib import f2_intraday, make_hist, x_prints
from gen_m2_F10F20 import f10_hist


def build(rng):
    R = Rows("structural", "M2-STR")
    sess = session("2026-06-01", S(4000), 390)
    d = lambda s: -S(s)
    ok = lambda cid, dt, usd_, seq: pp(cid, dt, usd_, seq=seq)
    T = ["structural"]

    def pr_row(out, prints, prm, tags, sid="SYN1", se=None):
        inp = mkin(prints, sess=se or sess, series=sid, raw=True)
        R.add(out, "matrix section 4; IO contract section 2", "Q6", inp, prm, tags=T + tags)

    F1p = {"filter": "all", "N": 3}
    # unordered_prints x3
    pr_row("M2-1", [ok("C1", d(10), 1000, 0), ok("C1", d(20), 1000, 1)], F1p, ["unordered_prints"])                 # 1 time decreasing
    pr_row("M2-4", [ok("C1", d(10), 1000, 5), ok("C1", d(10), 1000, 4)], {"window_s": 300, "N": 1}, ["unordered_prints"])  # 2 seq decreasing at same ns
    pr_row("M2-6", [ok("C1", d(10), 1000, 0), ok("C1", d(30), 1000, 1), ok("C1", d(5), 1000, 2)], {"window_s": 300}, ["unordered_prints"])  # 3
    # negative_size_or_price x3
    pr_row("M2-4", [pr("C1", d(10), "10.0000", -1, seq=0)], {"window_s": 300, "N": 1}, ["negative_size_or_price"])      # 4
    pr_row("M2-5", [pr("C1", d(10), "-1.0000", 5, seq=0)], {"window_s": 300}, ["negative_size_or_price"])               # 5
    pr_row("M2-9", [pr("P1", d(10), "1.0000", -5, seq=0), pr("C1", d(9), "1.0000", 5, seq=1)], {"window_s": 300, "at_least": "1/2", "at_most": None}, ["negative_size_or_price"])  # 6
    # bad_multiplier x3 (10 is a valid nonstandard multiplier; 0 and negative are bad)
    pr_row("M2-1", [pr("C1", d(10), "1.0000", 5, mult=0, seq=0)], F1p, ["bad_multiplier"])                           # 7
    pr_row("M2-4", [pr("C1", d(10), "1.0000", 5, mult=-100, seq=0)], {"window_s": 300, "N": 1}, ["bad_multiplier"])   # 8
    pr_row("M2-6", [pr("C1", d(10), "1.0000", 5, mult=0, seq=0)], {"window_s": 300}, ["bad_multiplier"])              # 9
    # duplicate_session x3
    def hist_row(out, cal, cur, h, prm, tags, el=S(1800), minutes=20, prints=None):
        inp = mkin(prints, sess=session(cur, el, minutes), cal=cal, histo=h) if prints is not None else None
        return inp

    cal, cur, h = make_hist("premium", 15, 300, 20)
    h["sessions"].append(dict(h["sessions"][3]))
    h["expansion_sha256"] = exp_hash(h["sessions"])
    R.add("M2-2", "matrix section 4", "Q6", mkin(x_prints("premium"), sess=session(cur, S(1800), 20), cal=cal, histo=h),
          {"form": "intraday", "metric": "premium", "window_s": 300, "X": 5, "K": 20}, tags=T + ["duplicate_session"])   # 10
    cal, cur, h = f10_hist(10, [], 300, 20)
    h["sessions"].append(dict(h["sessions"][0]))
    h["expansion_sha256"] = exp_hash(h["sessions"])
    R.add("M2-7", "matrix section 4", "Q6", mkin([pr("C1", -S(10), "1.0000", 25)], sess=session(cur, S(1800), 20), cal=cal, histo=h),
          {"window_s": 300, "N": "2", "filter": "all", "K": 20}, tags=T + ["duplicate_session"])                          # 11
    cal, prior_ids, cur = mkcal([3] * 20, 3)
    recs = [hs(s_, 3, base=0, total=100) for s_ in prior_ids] + [hs(prior_ids[5], 3, base=0, total=100)]
    R.add("M2-8", "matrix section 4", "Q6", mkin(None, contracts=CONTRACTS, sess=session(cur, S(23400), 3, complete=True, total=200), cal=cal, histo=hist("SYN1", "contracts", recs)),
          {"metric": "contracts", "N": "2", "K": 20}, tags=T + ["duplicate_session"])                                       # 12
    # non_monotone_grid x3 (sparse grid indices out of order, duplicated or out of range)
    for out, bad, tag in (("M2-2", [[7, 5], [6, 5]], "out_of_order"), ("M2-7", [[6, 5], [6, 9]], "duplicate_index"), ("M2-2", [[3, 5], [25, 5]], "out_of_range")):
        if out == "M2-2":
            cal, cur, h = make_hist("premium", 15, 300, 20)
            prm = {"form": "intraday", "metric": "premium", "window_s": 300, "X": 5, "K": 20}
            ps = x_prints("premium")
        else:
            cal, cur, h = f10_hist(10, [], 300, 20)
            prm = {"window_s": 300, "N": "2", "filter": "all", "K": 20}
            ps = [pr("C1", -S(10), "1.0000", 25)]
        h["sessions"][4]["gs"]["over"] = bad
        h["expansion_sha256"] = "not-expandable:invalid-grid"
        R.add(out, "matrix section 4", "Q6", mkin(ps, sess=session(cur, S(1800), 20), cal=cal, histo=h), prm, tags=T + ["non_monotone_grid", tag])  # 13-15
    # session_not_in_calendar x3
    cal, cur, h = make_hist("premium", 15, 300, 20)
    R.add("M2-2", "matrix section 4", "Q6", mkin(x_prints("premium"), sess=session("2031-01-01", S(1800), 20), cal=cal, histo=h),
          {"form": "intraday", "metric": "premium", "window_s": 300, "X": 5, "K": 20}, tags=T + ["session_not_in_calendar"])   # 16
    cal, cur, h = f10_hist(10, [], 300, 20)
    R.add("M2-7", "matrix section 4", "Q6", mkin([pr("C1", -S(10), "1.0000", 25)], sess=session("2031-01-01", S(1800), 20), cal=cal, histo=h),
          {"window_s": 300, "N": "2", "filter": "all", "K": 20}, tags=T + ["session_not_in_calendar", "gate_order", "insufficient_history"])  # 17 (history also unusable)
    cal, prior_ids, cur = mkcal([3] * 20, 3)
    recs = [hs(s_, 3, base=0, total=100, put=10 + i, call=10) for i, s_ in enumerate(prior_ids)]
    R.add("M2-10", "matrix section 4", "Q6", mkin(None, contracts=CONTRACTS, sess=session("2031-01-01", S(23400), 3, complete=True, put=30, call=10), cal=cal, histo=hist("SYN1", "put_volume", recs)),
          {"X": 5, "K": 20}, tags=T + ["session_not_in_calendar"])                                                          # 18
    # window_not_allowed x3
    pr_row("M2-4", [ok("C1", d(10), 1000, 0)], {"window_s": 120, "N": 1}, ["window_not_allowed"])                           # 19
    pr_row("M2-6", [ok("C1", d(10), 1000, 0)], {"window_s": 45}, ["window_not_allowed", "gate_order"])                       # 20
    pr_row("M2-5", [ok("C1", d(10), 1000, 0)], {"window_s": 600}, ["window_not_allowed"], sid="C1")                          # 21 F17 fixed at 300
    # delayed_feed_tag x3
    dl = session("2026-06-01", S(1800), 390, delay="delayed")
    pr_row("M2-1", [ok("C1", d(10), 1000, 0)], F1p, ["delayed_feed_tag"], se=dl)                                             # 22
    R.add("M2-11", "matrix section 4", "Q11", {"t_ns": T0, "series_id": "SYN1", "points": [None] * 15 + [[3000, 15000]],
          "session": session("2026-06-01", S(60 * 15), 390, delay="delayed")}, {"N": 3, "quiet_gap": 1, "n_episodes": 1, "grid_s": 60},
          tags=T + ["delayed_feed_tag"])                                                                                      # 23
    cal, cur, h = f10_hist(10, [], 300, 20, nstore=0)
    R.add("M2-7", "matrix section 4", "Q4,Q5", mkin([pr("C1", -S(10), "1.0000", 25)], sess=session(cur, S(100), 20, delay="delayed"), cal=cal, histo=h),
          {"window_s": 300, "N": "2", "filter": "all", "K": 20}, tags=T + ["delayed_feed_tag", "gate_order", "insufficient_history"])  # 24
    pr_row("M2-9", [pr("P1", d(10), "1.0000", 5, seq=0)], {"window_s": 300, "at_least": None, "at_most": None}, ["threshold_required"])  # 25
    from gen_m2_store import CAL
    sids = [c["session_id"] for c in CAL]
    mk = lambda i: {"series_id": "SYN1", "metric": "premium", "window_s": 300, "session_id": sids[i], "grid": [1, 2, 3], "total": 6, "complete": True}
    R.add("M2-12", "matrix section 4; PO-M2-AMB-13", "Q3", {"k": 20, "calendar": CAL, "ops": [["append", mk(5)], ["append", mk(2)]],
          "query": {"series_id": "SYN1", "metric": "premium", "window_s": 300, "as_of": sids[6]}}, {"K": 20}, tags=T + ["out_of_order"])     # 26
    pr_row("M2-1", [ok("C1", d(20), 1000, 0), ok("C1", d(10), 1000, 1), pr("C1", d(5), "1.0000", -3, seq=2)], F1p, ["amb15", "unordered_prints", "negative_size_or_price"])  # 27 two errors: first in listed order
    pr_row("M2-4", [pr("C1", d(10), "1.0000", 5, mult=0, seq=0)], {"window_s": 120, "N": 1}, ["amb15", "bad_multiplier", "window_not_allowed"])  # 28
    pr_row("M2-5", [pr("C1", d(10), "-1.0000", 5, mult=0, seq=0)], {"window_s": 300}, ["amb15", "negative_size_or_price", "bad_multiplier"], sid="C1")   # 29
    cal, cur, h = make_hist("premium", 15, 300, 20)
    h["sessions"].append(dict(h["sessions"][3]))
    h["expansion_sha256"] = exp_hash(h["sessions"])
    R.add("M2-2", "matrix section 4", "Q6", mkin(x_prints("premium"), sess=session(cur, S(1800), 20), cal=cal, histo=h),
          {"form": "intraday", "metric": "premium", "window_s": 120, "X": 5, "K": 20}, tags=T + ["amb15", "duplicate_session", "window_not_allowed"])  # 30
    from gen_m2_store import CAL as CAL2
    sids2 = [c["session_id"] for c in CAL2]
    mk2 = lambda i: {"series_id": "SYN1", "metric": "premium", "window_s": 300, "session_id": sids2[i], "grid": [1, 2, 3], "total": 6, "complete": True}
    R.add("M2-12", "matrix section 4", "Q3", {"k": 20, "calendar": CAL2, "ops": [["append", mk2(3)], ["append", mk2(3)]],
          "query": {"series_id": "SYN1", "metric": "premium", "window_s": 300, "as_of": sids2[6]}}, {"K": 20}, tags=T + ["duplicate_session"])   # 31
    assert len(R.rows) == 31, len(R.rows)
    return R.rows


if __name__ == "__main__":
    main_for("structural", "structural", build)
