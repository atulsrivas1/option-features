"""Additions: cutoff before session open gives an EMPTY window for F4, F7, F17 and F18 (counts and premiums zero, coverage zero,
status available; a zero denominator gives the usual zero_denominator). Single-cutoff rows plus an F17 sweep through cutoffs
straddling open (18 rows). Prints lie before open and between the cutoff and open (repro: prints at open-300, -90, -80, -70, -60 s,
cutoff open-100 s)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import m2add_oracle as A  # noqa: E402
from m2common import *  # noqa: E402,F401,F403
import m2common as C  # noqa: E402

A.install()


def build(rng):
    R = Rows("addcutoff", "M2A-CUT")
    T = ["additions", "preopen_clip", "cutoff_before_open"]
    PRE = [-300, -90, -80, -70, -60]               # seconds relative to open

    def session_for(cut):
        # cutoff = open + cut: the session open lies (-cut) ahead of the evaluation time
        return session("2026-06-01", S(cut), 390)

    def dt(u, cut):
        return S(u) - S(cut)

    def mk(kind, cut, extra=(), series="SYN1"):
        ps = []
        for j, u in enumerate(list(PRE) + list(extra)):
            if kind == "F18":
                ps.append(pr("P1" if j % 2 else "C1", dt(u, cut), "1.0000", 10 + j))
            elif kind == "F7":
                ps.append(pp("C1" if j % 2 else "C2", dt(u, cut), 100000 + 1000 * j))
            else:
                ps.append(pp("C1", dt(u, cut), 100000 + 1000 * j))
        return mkin(ps, sess=session_for(cut), series=series)

    def add(out, kind, cut, prm, tags, extra=(), series="SYN1"):
        R.add(out, "PO ruling: cutoff before session open gives an empty window", "Q7", mk(kind, cut, extra, series), prm, tags=T + tags)

    p4 = lambda thr: {"window_s": 300, "N": 1, "threshold_ticks": thr}
    add("M2-4", "F4", -100, p4(1), ["f4", "repro"])                                  # the repro: threshold 1 expects zeros
    add("M2-4", "F4", -100, p4(1000000000), ["f4"])
    add("M2-4", "F4", -310, p4(1), ["f4", "window_before_all_prints"])
    add("M2-4", "F4", Fr(-1, NS), p4(1), ["f4", "one_ns_before_open"])
    add("M2-6", "F7", -100, {"window_s": 300}, ["f7", "repro"])
    add("M2-6", "F7", -60, {"window_s": 300}, ["f7"])
    add("M2-6", "F7", -310, {"window_s": 300}, ["f7", "window_before_all_prints"])
    extra17 = [0, 10, 50]
    for cut in (-100, -60, -30, Fr(-1, NS), 0, Fr(1, NS), 30, 60):                   # F17 sweep straddling open
        add("M2-5", "F17", cut, {"window_s": 300}, ["f17", "sweep"], extra=extra17, series="C1")
    p18 = {"window_s": 300, "at_least": "1/2", "at_most": None}
    add("M2-9", "F18", -100, p18, ["f18", "repro"])
    add("M2-9", "F18", -60, p18, ["f18"])
    add("M2-9", "F18", 30, p18, ["f18", "straddle"], extra=[0, 10, 50])
    assert len(R.rows) == 18, len(R.rows)
    return R.rows


if __name__ == "__main__":
    C.main_for("add_cutoff", "addcutoff", build)
