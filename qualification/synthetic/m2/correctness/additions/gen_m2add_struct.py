"""Additions: structural rows for unknown_contract, malformed_type, precedence pairs, delayed + unknown contract,
trailing-zero text price, float window_s, integer-tick prices, decimal grammar, flag and seq types (53 rows).
Independent of the merged files."""
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
    R = Rows("addstruct", "M2A-STR")
    sess = session("2026-06-01", S(1800), 390)
    d = lambda s: -S(s)
    PR = {"M2-1": {"filter": "all", "N": 3},
          "M2-4": {"window_s": 300, "N": 1, "threshold_ticks": 1000000000},
          "M2-6": {"window_s": 300},
          "M2-5": {"window_s": 300},
          "M2-9": {"window_s": 300, "at_least": "1/2", "at_most": None}}
    sid = {"M2-5": "C1"}
    T = ["structural", "additions"]

    def row(out, prints, tags, prm=None, se=None, series=None):
        inp = mkin(prints, sess=se or sess, series=series or sid.get(out, "SYN1"), raw=True)
        R.add(out, "PO rulings after PR 79 (structural codes)", "Q6", inp, prm if prm is not None else PR[out], tags=T + tags)

    ok = lambda i=0: P("C1", d(10 + i), "1.0000", 5, seq=i)
    for out in PR:                                                                        # unknown_contract 10
        row(out, [P("ZZ9", d(10), "1.0000", 5, seq=0)], ["unknown_contract"])
        row(out, [P("C1", d(20), "1.0000", 5, seq=0), P("ZZ9", d(5), "1.0000", 5, seq=1)], ["unknown_contract"])
    mal = {"M2-1": [P("C1", d(10), True, 5), P("C1", d(10), 1.5, 5)],
           "M2-4": [P("C1", d(10), 1.5, 5), P("C1", d(10), True, 5)],
           "M2-6": [P("C1", d(10), 1.5, 5), P("C1", d(10), "1.00001", 5)],
           "M2-5": [P("C1", d(10), True, 5), P("C1", d(10), "1.0000", 1.5)],
           "M2-9": [P("C1", -10500000000.5, "1.0000", 5), P("C1", d(10), "1.0000", 5, mult=True)]}
    tagmap = {"M2-1": [["bool_price", "malformed_type"], ["float_price", "malformed_type"]],
              "M2-4": [["float_price", "malformed_type"], ["bool_price", "malformed_type"]],
              "M2-6": [["float_price", "malformed_type"], ["over_precision", "malformed_type"]],
              "M2-5": [["bool_price", "malformed_type"], ["float_size", "malformed_type"]],
              "M2-9": [["float_time", "malformed_type"], ["bool_multiplier", "malformed_type"]]}
    for out in PR:                                                                        # malformed_type 10
        for p, tg in zip(mal[out], tagmap[out]):
            row(out, [p], tg)
    # precedence pairs (2 rows each); the first failing code in the contract list order is reported
    row("M2-1", [P("C1", d(20), "-1.0000", 5, seq=0), P("C1", d(30), "1.0000", 5, seq=1)], ["prec_pair", "unordered_prints", "negative_size_or_price"])
    row("M2-4", [P("C1", d(10), "1.0000", 5, seq=1), P("C1", d(10), "1.0000", -2, seq=0)], ["prec_pair", "unordered_prints", "negative_size_or_price"])
    row("M2-1", [P("C1", d(10), "-1.0000", 5, mult=0, seq=0)], ["prec_pair", "negative_size_or_price", "bad_multiplier"])
    row("M2-6", [P("C1", d(10), "1.0000", -3, seq=0), P("C1", d(9), "1.0000", 5, mult=-100, seq=1)], ["prec_pair", "negative_size_or_price", "bad_multiplier"])
    row("M2-4", [P("ZZ9", d(10), "1.0000", 5, mult=0, seq=0)], ["prec_pair", "bad_multiplier", "unknown_contract"])
    row("M2-5", [P("C1", d(10), "1.0000", 5, mult=0, seq=0), P("ZZ9", d(9), "1.0000", 5, seq=1)], ["prec_pair", "bad_multiplier", "unknown_contract"])
    row("M2-1", [P("ZZ9", d(10), 1.5, 5, seq=0)], ["prec_pair", "unknown_contract", "malformed_type"])
    row("M2-9", [P("C1", d(10), "1.0000", 5, seq=0), P("ZZ9", d(9), "1.0000", 5, seq=1), P("C1", d(8), True, 5, seq=2)], ["prec_pair", "unknown_contract", "malformed_type"])
    row("M2-4", [P("C1", d(10), 1.5, 5, seq=0)], ["prec_pair", "malformed_type", "window_not_allowed"], prm={"window_s": 120, "N": 1, "threshold_ticks": 1000000000})
    row("M2-6", [P("C1", d(10), "1.0000", 2.5, seq=0)], ["prec_pair", "malformed_type", "window_not_allowed"], prm={"window_s": 300.0})
    dl = session("2026-06-01", S(1800), 390, delay="delayed")                             # F1 delayed + unknown contract
    row("M2-1", [P("ZZ9", d(10), "1.0000", 5, seq=0)], ["delayed_feed_tag", "unknown_contract", "gate_order"], se=dl)
    row("M2-1", [P("C1", d(10), "1.0000", 5, seq=0), P("ZZ9", d(8), "1.0000", 5, seq=1)], ["delayed_feed_tag", "unknown_contract", "gate_order"], se=dl)
    # trailing zeros in a text price are accepted
    base = [P("C1", d(500), "80.000000", 1000, seq=0), P("C1", d(30), "20.00000", 1000, seq=1)]
    row("M2-1", base, ["trailing_zero_price", "accepted"])
    row("M2-4", [P("C1", d(10), "1000.00000", 100, seq=0)], ["trailing_zero_price", "accepted"])
    # float window_s is window_not_allowed (even when equal to an allowed integer)
    row("M2-4", [ok(0)], ["float_window", "window_not_allowed"], prm={"window_s": 300.0, "N": 1, "threshold_ticks": 1000000000})
    row("M2-6", [ok(0)], ["float_window", "window_not_allowed"], prm={"window_s": 900.0})
    row("M2-1", [P("C1", d(10), "2.00001", 5)], ["over_precision", "malformed_type"])
    row("M2-1", [P("C1", -10500000000.5, "1.0000", 5)], ["float_time", "malformed_type"])
    row("M2-4", [P("C1", d(10), "1.0000", 5, mult=True)], ["bool_multiplier", "malformed_type"])
    row("M2-9", [P("C1", d(10), "3.12345", 5)], ["over_precision", "malformed_type"])
    # integer (non-bool) prices are integer ticks and valid
    row("M2-1", [P("C1", d(500), 800000, 1000, seq=0), P("C1", d(30), 200000, 1000, seq=1)], ["int_tick_price", "accepted"])
    row("M2-4", [P("C1", d(10), 10000000, 100, seq=0)], ["int_tick_price", "accepted"])
    # text decimal grammar (ASCII): optional minus, digits with optional fraction, or a leading dot; '.5' valid;
    # plus sign, exponent, spaces and non-ASCII digits are malformed_type
    row("M2-1", [P("C1", d(10), "+1.0000", 5, seq=0)], ["grammar_text", "malformed_type", "grammar_plus"])
    row("M2-4", [P("C1", d(10), "1e3", 5, seq=0)], ["grammar_text", "malformed_type", "grammar_exp"])
    row("M2-6", [P("C1", d(10), " 1.0000", 5, seq=0)], ["grammar_text", "malformed_type", "grammar_space"])
    row("M2-9", [P("C1", d(10), chr(0xff11) + ".0000", 5, seq=0)], ["grammar_text", "malformed_type", "grammar_unicode"])
    row("M2-1", [P("C1", d(500), ".8", 100000, seq=0), P("C1", d(30), ".2", 100000, seq=1)], ["grammar_text", "dot_five", "accepted"])
    row("M2-4", [P("C1", d(10), ".5", 20000, seq=0)], ["grammar_text", "dot_five", "accepted"])
    # condition_excluded flag: 0/1 as int or bool valid, other values malformed_type; a bool seq is malformed_type
    row("M2-4", [P("C1", d(11), "1000.0000", 100, excl=1, seq=0), P("C1", d(10), "1000.0000", 100, seq=1)], ["flag_int", "accepted"])
    row("M2-4", [P("C1", d(11), "1000.0000", 100, excl=True, seq=0), P("C1", d(10), "1000.0000", 100, seq=1)], ["flag_int", "accepted"])
    row("M2-6", [P("C1", d(10), "1.0000", 5, excl=2, seq=0)], ["flag_int", "malformed_type"])
    row("M2-1", [P("C1", d(10), "1.0000", 5, seq=True)], ["bool_seq", "malformed_type"])
    row("M2-6", [P("C1", d(10), "1.0000", 5, seq=True)], ["bool_seq", "malformed_type"])
    row("M2-1", [P("C1", d(10), "1.0000", 5, excl=3, seq=0)], ["flag_int", "malformed_type"])
    # integer ticks (dollars x 10^4) versus text decimals: equal results
    row("M2-4", [P("C1", d(10), "1000.0000", 10, seq=0)], ["int_tick_twin", "accepted"])
    row("M2-4", [P("C1", d(10), 10000000, 10, seq=0)], ["int_tick_twin", "accepted"])
    pq = {"window_s": 300, "at_least": "1/2", "at_most": None}
    row("M2-9", [P("P1", d(11), "5.0000", 30, seq=0), P("C1", d(10), "5.0000", 30, seq=1)], ["int_tick_twin", "accepted"], prm=pq)
    row("M2-9", [P("P1", d(11), 50000, 30, seq=0), P("C1", d(10), 50000, 30, seq=1)], ["int_tick_twin", "accepted"], prm=pq)
    # trailing dot is valid in the text grammar
    row("M2-4", [P("C1", d(10), "1000.", 100, seq=0)], ["grammar_text", "dot_trailing", "accepted"])
    row("M2-9", [P("P1", d(11), "1.", 5, seq=0), P("C1", d(10), "1.", 5, seq=1)], ["grammar_text", "dot_trailing", "accepted"], prm=pq)
    row("M2-6", [P("C1", d(10), True, 5)], ["prec_pair", "malformed_type", "window_not_allowed", "bool_price"], prm={"window_s": 45})
    assert len(R.rows) == 61, len(R.rows)
    return R.rows


if __name__ == "__main__":
    C.main_for("add_struct", "addstruct", build)
