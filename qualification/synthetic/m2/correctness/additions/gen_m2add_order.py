"""mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Additions: the adjacent-pair ordering rule (25 rows, F1/F4/F7/F17/F18, five streams each). unordered_prints compares adjacent prints only;
a pair with a non-int time or seq is skipped, the rest of the stream is still checked. Precedence follows the single list: unordered_prints
comes before malformed_type, so a genuine unordered adjacent pair anywhere in the stream is reported even when another print is malformed."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import m2add_oracle as A  # noqa: E402
from m2common import *  # noqa: E402,F401,F403
import m2common as C  # noqa: E402

A.install()


def P(cid, dt, price, size, mult=100, excl=0, seq=0):
    return [cid, dt, price, size, mult, excl, seq]


def build(rng):
    R = Rows("addorder", "M2A-ORD")
    sess = session("2026-06-01", S(1800), 390)
    d = lambda s: -S(s)
    PR = {"M2-1": {"filter": "all", "N": 3},
          "M2-4": {"window_s": 300, "N": 1, "threshold_ticks": 1000000000},
          "M2-6": {"window_s": 300},
          "M2-5": {"window_s": 300},
          "M2-9": {"window_s": 300, "at_least": "1/2", "at_most": None}}
    sid = {"M2-5": "C1"}
    T = ["structural", "additions", "order_stream"]
    ok = lambda dt, seq: P("C1", dt, "1.0000", 5, seq=seq)
    FT = -30500000000.5                                    # a float time (-30.5 s)

    def row(out, prints, tags):
        R.add(out, "adjacent-pair ordering rule; first applicable check in the section 9 list", "Q6",
              mkin(prints, sess=sess, series=sid.get(out, "SYN1"), raw=True), PR[out], tags=T + tags)

    for out in PR:
        # float seq next to a genuine out-of-order pair (C, D): unordered_prints wins over malformed_type
        row(out, [ok(d(40), 0), ok(d(30), 1.5), ok(d(20), 0), ok(d(25), 1)], ["order_float_seq", "prec_multi", "unordered_prints"])
        # float time next to a genuine out-of-order pair
        row(out, [ok(d(40), 0), ok(FT, 1), ok(d(20), 2), ok(d(25), 3)], ["order_float_time", "prec_multi", "unordered_prints"])
        # mixed typed and untyped, several pairs, no genuine fault in the compared pairs: malformed_type
        row(out, [ok(d(50), 0), ok(d(40), True), ok(d(30), 1), ok(d(20), 2)], ["order_mixed_ok", "malformed_type"])
        # mixed, a malformed key first and a genuine unordered adjacent pair later: unordered_prints wins
        row(out, [ok(d(50), True), ok(d(40), 0), ok(d(45), 1), ok(d(30), 2)], ["order_mixed_fault", "prec_multi", "unordered_prints"])
        # an apparent decrease across a skipped pair is not compared: malformed_type
        row(out, [ok(d(20), 0), ok(d(30), 1.5)], ["order_skipped_pair", "malformed_type"])
    assert len(R.rows) == 25, len(R.rows)
    return R.rows


if __name__ == "__main__":
    C.main_for("add_order", "addorder", build)
