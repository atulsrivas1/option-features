"""Additions: parameter-level malformed_type (N, thresholds, shares, quiet_gap, n_episodes with float or bool values, quiet_gap and
n_episodes below 1) and grid_not_60s (16 rows). One defect per row."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import m2add_oracle as A  # noqa: E402
from m2common import *  # noqa: E402,F401,F403
import m2common as C  # noqa: E402

A.install()


def build(rng):
    R = Rows("addparams", "M2A-PAR")
    sess = session("2026-06-01", S(1800), 390)
    d = lambda s: -S(s)
    prints = [pp("C1", d(500), 80000), pp("C1", d(30), 20000)]
    f1 = {"filter": "all", "N": 3}
    f4 = {"window_s": 300, "N": 1, "threshold_ticks": 1000000000}
    f12 = {"N": 3, "quiet_gap": 1, "n_episodes": 1, "grid_s": 60}

    def pr_row(out, prm, tags, series="SYN1"):
        R.add(out, "PO rulings: parameter types", "Q6", mkin(prints, sess=sess, series=series), prm, tags=["additions", "param_malformed"] + tags)

    def f12_row(over, tags):
        prm = dict(f12)
        prm.update(over)
        inp = {"t_ns": T0, "series_id": "SYN1", "points": [None] * 15 + [[3000, 15000]], "session": session("2026-06-01", S(900), 390)}
        R.add("M2-11", "PO rulings: parameter types", "Q11", inp, prm, tags=["additions"] + tags)

    pr_row("M2-1", dict(f1, N=1.5), ["param_N", "malformed_type"])
    pr_row("M2-4", dict(f4, N=True), ["param_N", "malformed_type"])
    pr_row("M2-4", dict(f4, threshold_ticks=1000000000.0), ["param_threshold", "malformed_type"])
    pr_row("M2-5", {"window_s": 300, "threshold_ticks": True}, ["param_threshold", "malformed_type"], series="C1")
    pr_row("M2-6", {"window_s": 300, "share_threshold": 0.6}, ["param_share", "malformed_type"])
    pr_row("M2-6", {"window_s": 300, "share_threshold": True}, ["param_share", "malformed_type"])
    pr_row("M2-9", {"window_s": 300, "at_least": 0.5, "at_most": None}, ["param_share", "malformed_type"])
    pr_row("M2-9", {"window_s": 300, "at_least": "1/2", "at_most": True}, ["param_share", "malformed_type"])
    f12_row({"quiet_gap": 1.0}, ["param_quiet_gap", "param_malformed", "malformed_type"])
    f12_row({"quiet_gap": True}, ["param_quiet_gap", "param_malformed", "malformed_type"])
    f12_row({"n_episodes": 1.0}, ["param_n_episodes", "param_malformed", "malformed_type"])
    f12_row({"n_episodes": True}, ["param_n_episodes", "param_malformed", "malformed_type"])
    f12_row({"grid_s": 30}, ["grid_not_60s"])
    f12_row({"grid_s": 120}, ["grid_not_60s"])
    f12_row({"quiet_gap": 0}, ["param_below_one", "param_malformed", "malformed_type"])
    f12_row({"n_episodes": 0}, ["param_below_one", "param_malformed", "malformed_type"])
    assert len(R.rows) == 16, len(R.rows)
    return R.rows


if __name__ == "__main__":
    C.main_for("add_params", "addparams", build)
