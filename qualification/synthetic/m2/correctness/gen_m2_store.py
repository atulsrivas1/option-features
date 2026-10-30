"""M2-12 history store: 40 rows (append, seal, ring at K and K+1, content hash under shuffled arrival, view as of a session,
no look-ahead, structural errors). Record content is seeded; expected values come from the rules in the I/O contract."""
from m2common import *

CAL = [{"session_id": s_, "minutes": 3} for s_ in weekdays(30)]
SID = [c["session_id"] for c in CAL]


def build(rng):
    R = Rows("store", "M2-STORE")

    def rec(series, metric, i, complete=True, grid=None, win=300):
        g = grid if grid is not None else [rng.randrange(0, 50) for _ in range(3)]
        return {"series_id": series, "metric": metric, "window_s": win, "session_id": SID[i], "grid": g, "total": sum(g), "complete": complete}

    def row(ops, tags, query=None, k=20, pending=None, cal=None):
        inp = {"k": k, "calendar": cal or CAL, "ops": ops}
        if query:
            inp["query"] = query
        return R.add("M2-12", "matrix section 5; IO contract section 4", "Q3,Q15", inp, {"K": k}, tags=["store"] + tags, pending=pending)

    A = lambda r_: ["append", r_]
    q = lambda i, s="SYN1", m="premium", w=300: {"series_id": s, "metric": m, "window_s": w, "as_of": SID[i]}
    seq = lambda n, **kw: [A(rec("SYN1", "premium", i, **kw)) for i in range(n)]
    for n in (1, 5, 20):                                                                            # 1-3
        row(seq(n), ["append"], q(n))
    for n in (21, 22, 25):                                                                          # 4-6
        row(seq(n), ["retention_k", "store_k_plus_1"], q(n))
    ops = [A(rec("SYN1", "premium", i, complete=(i != 4))) for i in range(20)]
    row(ops, ["incomplete"], q(20))                                                                 # 7
    row(ops + [["seal", "SYN1", "premium", 300, SID[4]]], ["seal"], q(20))                               # 8
    ops = seq(19) + [A(rec("SYN1", "premium", 19, complete=False))]
    row(ops, ["incomplete"], q(20))                                                                 # 9
    base = {}
    keys = [("SYN1", "premium"), ("SYN2", "premium"), ("SYN1", "contracts"), ("SYN3", "contracts")]
    recs = {kk: [rec(kk[0], kk[1], i) for i in range(4)] for kk in keys}
    outs = []
    for t in range(4):                                                                              # 9-12 -> rows 10-13 ( shuffled series arrival )
        r2 = rng
        pos = {kk: 0 for kk in keys}
        ops = []
        order = []
        while any(pos[kk] < 4 for kk in keys):
            cand = [kk for kk in keys if pos[kk] < 4]
            kk = cand[r2.randrange(len(cand))] if t else cand[0]
            ops.append(A(recs[kk][pos[kk]]))
            pos[kk] += 1
        outs.append(row(ops, ["shuffled_arrival", "store_sort", "store_arrival_hash"], q(4)))
    assert len({o["expected"]["value"]["dump_sha256"] for o in outs}) == 1
    for i, asof in ((10, "mid"), (0, "first"), (28, "beyond"), (7, "stored")):                       # 14-17 view as of a session
        row(seq(12), ["view_as_of", "no_lookahead", "store_view_current"], q(i))
    for i in (3, 12, 24):                                                                           # 18-20 no look-ahead / K window
        row(seq(25), ["no_lookahead", "view_as_of", "store_view_current"], q(i))
    row(seq(5) + [A(rec("SYN1", "premium", 3))], ["out_of_order", "structural"], q(5))         # 21 earlier session already stored
    r_bad = rec("SYN1", "premium", 5)
    r_bad["grid_idx"] = [0, 2, 1]
    row(seq(5) + [A(r_bad)], ["non_monotone_grid", "structural"], q(6))                              # 22
    r_nc = rec("SYN1", "premium", 0)
    r_nc["session_id"] = "2031-01-01"
    row([A(r_nc)], ["session_not_in_calendar", "structural"], q(1))                                  # 23
    row(seq(3) + [A(rec("SYN1", "premium", 1))] if False else [A(rec("SYN1", "premium", 5)), A(rec("SYN1", "premium", 2))],
        ["out_of_order", "structural"], q(6), pending="RULED PO-M2-AMB-13 (out_of_order_append), pending design ratification where design is silent")  # 24
    gap_cal = [{"session_id": SID[i], "minutes": 3} for i in range(0, 30, 2)]
    sparse = lambda idxs: [A(rec("SYN1", "premium", i)) for i in idxs]
    row(sparse(range(0, 20, 2)), ["calendar_gap", "view_as_of"], q(20), cal=CAL)                    # 25
    row(sparse([0, 1, 5, 6, 9]), ["calendar_gap", "view_as_of"], q(10))                             # 26
    row(sparse([3, 10, 11, 25]), ["calendar_gap", "view_as_of", "no_lookahead"], q(12))              # 27
    row(sparse([0, 29]), ["calendar_gap", "view_as_of"], q(29))                                      # 28
    ops = seq(22) + [A(rec("SYN1", "contracts", i)) for i in range(3)] + [A(rec("SYN2", "premium", i)) for i in range(7)]
    row(ops, ["isolation", "retention_k", "store_k_plus_1"], q(22))                                  # 29
    row(ops, ["isolation"], q(3, "SYN1", "contracts"))                                               # 30
    row(ops, ["isolation"], q(7, "SYN2", "premium"))                                                 # 31
    row(ops, ["isolation", "nothing_stored"], q(5, "SYN9", "premium"))                               # 32
    many = [A(rec("S%02d" % s_, "premium", i, grid=[s_ + i])) for s_ in range(60) for i in range(3)]  # 33
    row(many, ["series_60", "store_sort"], q(3, "S07"))
    row(list(reversed(many)) if False else [A(rec("S%02d" % s_, "premium", i, grid=[s_ + i])) for i in range(3) for s_ in range(59, -1, -1)],
        ["series_60", "shuffled_arrival", "store_sort", "store_arrival_hash"], q(3, "S07"))          # 34
    row([A(rec("SYN1", "premium", 0, grid=[1, 2, 3]))], ["content_hash"], q(1))                      # 35
    row([A(rec("SYN1", "premium", 0, grid=[1, 2, 3], complete=False))], ["content_hash", "incomplete"], q(1))  # 36
    ops = [A(rec("SYN1", "premium", i, complete=(i != 3))) for i in range(21)]
    row(ops, ["incomplete", "retention_k"], q(21))                                                   # 37 ring drops s0; s3 incomplete
    ops = [A(rec("SYN1", "premium", i, complete=(i != 0))) for i in range(21)]
    row(ops, ["incomplete", "retention_k"], q(21))                                                   # 38 incomplete one dropped by ring
    ops = [A(rec("SYN1", "premium", i, complete=(i != 24))) for i in range(25)]
    row(ops, ["incomplete", "retention_k"], q(25))                                                   # 39
    ops = [A(rec("SYN1", "premium", i, complete=False)) for i in range(5)] + [["seal", "SYN1", "premium", 300, SID[i]] for i in (0, 2)]
    row(ops, ["seal", "incomplete"], q(5))                                                           # 40
    two_w = [A(rec("SYN1", "premium", i)) for i in range(5)] + [A(rec("SYN1", "premium", i, win=900)) for i in range(3)]
    row(two_w, ["store_window", "isolation"], q(5))                                                  # 41 window 300 key
    row(two_w, ["store_window", "isolation"], q(5, w=900))                                           # 42 window 900 key
    row(two_w, ["store_window", "isolation", "nothing_stored"], q(5, w=60))                          # 43 no such key
    row([A(rec("SYN1", "premium", i, win=900)) for i in range(21)], ["store_window", "retention_k", "store_k_plus_1"], q(21, w=900))  # 44
    row([A(rec("SYN1", "premium", 7)), A(rec("SYN1", "premium", 6))], ["out_of_order", "structural"], q(8))   # 45 earlier session
    row(seq(5) + [A(rec("SYN1", "premium", 4))], ["duplicate_session", "structural"], q(5))          # 46 same as the last append
    row([A(rec("SYN1", "premium", 0)), A(rec("SYN1", "premium", 1)), A(rec("SYN2", "premium", 1)), A(rec("SYN1", "premium", 1))],
        ["duplicate_session", "structural"], q(2))                                                   # 47 duplicate on a series whose last session is repeated
    assert len(R.rows) == 47, len(R.rows)
    return R.rows


if __name__ == "__main__":
    main_for("store", "store", build)
