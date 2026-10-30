"""Additions: store-append rows (key store_ops; lane optional, default stock; the ring lane is the lane of the first append of
(series_id, metric, window_s)): lane_mismatch, record_length_mismatch, valid controls, ring lane from the first append,
and precedence pairs of the ruled store-append order lane_mismatch, session_not_in_calendar, record_length_mismatch,
non_monotone_grid, duplicate_session, out_of_order_append (22 rows)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import m2add_oracle as A  # noqa: E402
from m2common import *  # noqa: E402,F401,F403
import m2common as C  # noqa: E402
from gen_m2_store import CAL  # noqa: E402

A.install()
SID = [c["session_id"] for c in CAL]
ABSENT = "2031-01-01"


def build(rng):
    R = Rows("addstore", "M2A-STORE")

    def rec(i, grid=(1, 2, 3), lane="stock", idx=None, sid=None, series="SYN1"):
        r = {"series_id": series, "metric": "premium", "window_s": 300, "session_id": sid or SID[i], "grid": list(grid),
             "total": sum(grid), "complete": True, "lane": lane}
        if idx is not None:
            r["grid_idx"] = list(idx)
        return ["append", r]

    def row(ops, tags):
        R.add("M2-12", "PO rulings after PR 79 and PR 81 (store records)", "Q3",
              {"k": 20, "calendar": CAL, "store_ops": ops, "query": {"series_id": "SYN1", "metric": "premium", "window_s": 300, "as_of": SID[6]}},
              {"K": 20}, tags=["additions", "store"] + tags)

    row([rec(0), rec(1), rec(2, lane="etf_index")], ["lane_mismatch", "structural"])
    row([rec(0, lane="etf_index"), rec(1, lane="stock")], ["lane_mismatch", "structural"])
    row([rec(0), rec(1, grid=(1, 2, 3, 4))], ["record_length_mismatch", "structural", "dense_too_long"])
    row([rec(0), rec(1, grid=(5, 6), idx=(0, 5))], ["record_length_mismatch", "structural", "sparse_outside"])
    row([rec(0), rec(1, grid=(7,))], ["zero_padded_control"])
    row([rec(0), rec(1, grid=(5, 6), idx=(0, 2))], ["sparse_inside_control", "sparse_hash"])
    row([rec(0), rec(1), rec(2, grid=(1, 2, 3, 4, 5))], ["record_length_mismatch", "structural", "dense_too_long"])
    row([rec(0), rec(1, grid=(5, 6), idx=(1, 3))], ["record_length_mismatch", "structural", "sparse_outside"])
    # sparse records: equal values at different indices hash differently (grid_idx is part of the canonical line)
    row([rec(0, grid=(5, 6), idx=(0, 1)), rec(1, grid=(5, 6), idx=(0, 2))], ["sparse_hash", "sparse_inside_control"])
    row([rec(0, grid=(5, 6), idx=(1, 2)), rec(1, grid=(5, 6), idx=(0, 2))], ["sparse_hash", "sparse_inside_control"])
    # ring lane = lane of the first append (per series, metric, window)
    row([rec(0, lane="etf_index"), rec(1, lane="etf_index"), rec(2, lane="etf_index")], ["ring_lane_first"])
    row([rec(0, lane="etf_index"), rec(0, lane="stock", series="SYN2"), rec(1, lane="etf_index"), rec(1, lane="stock", series="SYN2")], ["ring_lane_first"])
    # precedence pairs of the ruled order (the earlier code in the order wins); two rows per adjacent pair
    P = ["prec_pair_store", "structural"]
    row([rec(0), rec(1, lane="etf_index", sid=ABSENT)], P + ["lane_mismatch", "session_not_in_calendar"])                         # lane, calendar
    row([rec(0, lane="etf_index"), rec(1, lane="stock", sid=ABSENT)], P + ["lane_mismatch", "session_not_in_calendar"])
    row([rec(0), rec(1, grid=(1, 2, 3, 4), sid=ABSENT)], P + ["session_not_in_calendar", "record_length_mismatch"])                # calendar, length
    row([rec(0), rec(1, grid=(5, 6), idx=(0, 5), sid=ABSENT)], P + ["session_not_in_calendar", "record_length_mismatch"])
    row([rec(0), rec(1, grid=(5, 6), idx=(4, 1))], P + ["record_length_mismatch", "non_monotone_grid"])                           # length, non-monotone
    row([rec(0), rec(1, grid=(5, 6, 7), idx=(2, 1, 5))], P + ["record_length_mismatch", "non_monotone_grid"])
    row([rec(0), rec(1), rec(1, grid=(5, 6), idx=(1, 0))], P + ["non_monotone_grid", "duplicate_session"])                       # non-monotone, duplicate
    row([rec(2), rec(2, grid=(5, 6), idx=(2, 2))], P + ["non_monotone_grid", "duplicate_session"])
    row([rec(0), rec(1), rec(2), rec(1)], P + ["duplicate_session", "out_of_order_append"])                                       # earlier and stored: out of order
    row([rec(0), rec(3), rec(3)], P + ["duplicate_session", "out_of_order_append"])                                               # equal to the last: duplicate
    row([rec(0), rec(1, grid=(1, 2, 3, 4), lane="etf_index")], P + ["lane_mismatch", "record_length_mismatch"])                   # extras
    row([rec(0), rec(3), rec(1, grid=(5, 6), idx=(1, 0))], P + ["non_monotone_grid", "out_of_order_append"])
    assert len(R.rows) == 24, len(R.rows)
    return R.rows


if __name__ == "__main__":
    C.main_for("add_store", "addstore", build)
