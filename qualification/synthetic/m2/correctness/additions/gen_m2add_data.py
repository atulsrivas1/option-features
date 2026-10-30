"""Additions: pre-open clipping for F4/F7/F17/F18 (8), F12 built from prints incl. coverage (8), premium above 2^53 and
fractional N (8) = 24 rows."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import m2add_oracle as A  # noqa: E402
from m2common import *  # noqa: E402,F401,F403
import m2common as C  # noqa: E402

A.install()


def build(rng):
    R = Rows("adddata", "M2A-DAT")
    d = lambda s: -S(s)
    T = ["additions"]
    # ---- prints before open are excluded from F4/F7/F17/F18 windows (clipped at open); open is 200 s before T
    so = session("2026-06-01", S(200), 390)
    OP = S(200)

    def pre(out, prints, prm, tags, series="SYN1"):
        R.add(out, "PO rulings after PR 79 (clip at open)", "Q7", mkin(prints, sess=so, series=series), prm, tags=T + ["preopen_clip"] + tags)

    p4 = {"window_s": 300, "N": 1, "threshold_ticks": 1000000000}
    pre("M2-4", [pp("C1", d(250), 100000), pp("C1", d(100), 100000)], p4, ["f4"])
    pre("M2-4", [pp("C1", -OP - 1, 100000), pp("C1", -OP, 100000)], p4, ["f4", "at_open_included"])
    pre("M2-6", [pp("C1", d(250), 900000), pp("C1", d(100), 50000), pp("C2", d(90), 50000)], {"window_s": 300}, ["f7"])
    pre("M2-6", [pp("C1", -OP - 1, 700000), pp("C2", -OP, 30000), pp("C1", d(50), 10000)], {"window_s": 300}, ["f7", "at_open_included"])
    pre("M2-5", [pp("C1", d(250), 100000), pp("C1", d(100), 60000)], {"window_s": 300}, ["f17"], series="C1")
    pre("M2-5", [pp("C1", -OP - 1, 100000), pp("C1", -OP, 100000)], {"window_s": 300}, ["f17", "at_open_included"], series="C1")
    p18 = {"window_s": 300, "at_least": "1/2", "at_most": None}
    V = lambda cid, dt, q: pr(cid, dt, "1.0000", q)
    pre("M2-9", [V("P1", d(250), 900), V("C1", d(100), 50), V("P1", d(90), 50)], p18, ["f18"])
    pre("M2-9", [V("C1", -OP - 1, 500), V("P1", -OP, 10), V("C1", d(50), 10)], p18, ["f18", "at_open_included"])

    # ---- F12 built from prints: one print per grid minute (premium 10,000 USD) plus planted bursts
    prm12 = {"N": 3, "quiet_gap": 1, "n_episodes": 1, "grid_s": 60}

    def f12(kT, tags, bursts=(), extra_ns=0, extra=(), filt=None, pre_open=()):
        el = S(60 * kT) + extra_ns
        ps = [pp("C1", S(60 * m) - el, 10000) for m in range(0, kT + 1)]
        for m, usd_ in bursts:
            ps.append(pp("C1", S(60 * m) - el, usd_))
        ps += [e(el) for e in extra]
        ps += [pp("C1", -el - S(s_), 777777) for s_ in pre_open]
        prm = dict(prm12)
        if filt:
            prm["filter"] = filt
        R.add("M2-11", "flow.md F12 from prints; PO-M2-AMB-5", "Q11", mkin(ps, sess=session("2026-06-01", el, 390)), prm,
              tags=T + ["f12_from_prints"] + tags)

    f12(25, ["episode"], bursts=[(20, 1000000)])
    f12(30, ["two_episodes"], bursts=[(18, 1000000), (24, 1000000)])
    f12(25, ["peak_zero_episodes", "coverage_from_prints"])
    f12(25, ["filter"], bursts=[(20, 1000000)], filt="calls", extra=[lambda el: pp("P1", S(60 * 21) - el, 5000000)])
    f12(25, ["coverage_from_prints", "nonstd_counted", "cond_excl_counted"],
        extra=[lambda el: pr("C1", S(60 * 20) - el, "1000.0000", 100, mult=10), lambda el: pr("C1", S(60 * 20) - el, "1000.0000", 100, excl=1)])
    f12(25, ["coverage_from_prints", "preopen_excluded"], pre_open=(10, 600))
    f12(22, ["off_grid", "episode"], bursts=[(20, 1000000)], extra_ns=30 * NS)
    f12(25, ["episode", "burst_at_T"], bursts=[(25, 1000000)])

    f12(25, ["coverage_from_prints", "preopen_excluded", "nonstd_counted"],
        extra=[lambda el: pr("C1", -el - S(30), "1000.0000", 100, mult=10), lambda el: pr("C1", S(60 * 21) - el, "1000.0000", 100, mult=10)])
    # ---- premium above 2^53 (exact integers) and fractional N (3/2)
    sess = session("2026-06-01", S(1800), 390)
    big = lambda i: pr("C1", d(10 + i), "99999999.9999", 1000000, seq=i)
    R.add("M2-4", "ticks above 2^53", "Q8", mkin([big(0)], sess=sess, raw=True), p4, tags=T + ["premium_gt_2_53", "f4"])
    R.add("M2-4", "ticks above 2^53", "Q8", mkin([big(1), big(0)], sess=sess, raw=True), p4, tags=T + ["premium_gt_2_53", "f4"])
    R.add("M2-5", "ticks above 2^53", "Q9", mkin([big(0)], sess=sess, series="C1", raw=True), {"window_s": 300}, tags=T + ["premium_gt_2_53", "f17"])
    R.add("M2-5", "ticks above 2^53", "Q9", mkin([big(1), big(0)], sess=sess, series="C1", raw=True), {"window_s": 300, "threshold_ticks": 10 ** 21},
          tags=T + ["premium_gt_2_53", "f17"])
    fr1 = lambda a: [pp("C1", d(500), 90000), pp("C1", d(30), a)]
    R.add("M2-1", "fractional N", "Q7", mkin(fr1(10000), sess=sess), {"filter": "all", "N": "3/2"}, tags=T + ["fractional_N", "f1"])
    R.add("M2-1", "fractional N", "Q7", mkin(fr1(9990), sess=sess), {"filter": "all", "N": "3/2"}, tags=T + ["fractional_N", "f1"])
    R.add("M2-1", "fractional N", "Q7", mkin([pp("C1", d(500), 110000), pp("C1", d(30), 10000)], sess=sess),
          {"filter": "all", "N": "3/2"}, tags=T + ["fractional_N", "f1"])                                      # ratio 5/4: would fire only if N were truncated to 1
    R.add("M2-4", "fractional N", "Q8", mkin([pp("C1", d(10), 100000)], sess=sess), {"window_s": 300, "N": "3/2", "threshold_ticks": 1000000000},
          tags=T + ["fractional_N", "f4"])
    R.add("M2-4", "fractional N", "Q8", mkin([pp("C1", d(10), 100000), pp("C1", d(11), 100000)], sess=sess), {"window_s": 300, "N": "3/2", "threshold_ticks": 1000000000},
          tags=T + ["fractional_N", "f4"])
    V = lambda cid, dt, q: pr(cid, dt, "1.0000", q)
    p18 = {"window_s": 300, "at_least": "1/2", "at_most": None}
    R.add("M2-9", "ratio_reason omitted when the ratio is available", "Q12", mkin([V("P1", d(11), 30), V("C1", d(10), 10)], sess=sess), p18,
          tags=T + ["ratio_reason_absent", "f18"])
    R.add("M2-9", "ratio_reason omitted when the ratio is available", "Q12", mkin([V("P1", d(12), 5), V("C1", d(10), 15), V("P2", d(9), 5)], sess=sess), p18,
          tags=T + ["ratio_reason_absent", "f18"])
    R.add("M2-9", "ratio_reason present when the ratio is unavailable", "Q12", mkin([V("P1", d(11), 30)], sess=sess), p18,
          tags=T + ["ratio_reason_present", "f18"])
    R.add("M2-1", "result version", "Q7", mkin([pp("C1", d(500), 80000), pp("C1", d(30), 20000)], sess=sess),
          {"filter": "all", "N": 3, "expect_version": "0.2.0a1"}, tags=T + ["result_version", "f1", "harness_checked"])
    assert len(R.rows) == 30, len(R.rows)
    return R.rows


if __name__ == "__main__":
    C.main_for("add_data", "adddata", build)
