"""Generator for family HISTORY REUSE (M3A-12): scalar series in the M2 store (k up to 252, total scalar, window_s 0), read
forms scalar_baseline and same_minute_column, retention, canonical hash, lane, inherited store codes, memory formula. SYNTHETIC.
Store ops: ["s", series, metric, calendar_index_or_session_id, units, complete01, lane]  scalar record (grid empty, total = units)
           ["g", series, metric, calendar_index_or_session_id, {base, over, len}, complete01, lane]  dense minute grid, window_s 0
           ["seal", series, metric, calendar_index]
Queries: scalar_baseline, same_minute_column, retained, hashes."""
import os

import gen_m3a_g4 as G
import m3a_common as C
import m3a_ref as R

CS, CM = G.REF_SCALAR, G.REF_MIN
IDS_S = [c[0] for c in G.CAL_SCALAR]
IDS_M = [c[0] for c in G.CAL_MIN]


def sc(rng, idxs, series="SYN1", metric="iv30_close", complete=1, lane="stock", lo=5_000_000, hi=90_000_000):
    return [["s", series, metric, i, rng.randrange(lo, hi), complete, lane] for i in idxs]


def gcol(rng, idxs, m, series="SYN1", metric="iv30", complete=1, lane="stock", cal=G.CAL_MIN):
    ops = []
    for i in idxs:
        L = cal[i][1]
        ops.append(["g", series, metric, i, G.grid_gs(rng, L, m, rng.randrange(10_000_000, 80_000_000), 40_000_000), complete, lane])
    return ops


def row(n_id, cal_ref, ops, query, tags, rules, derivation, k_default=252, k_by_key=None, pending="RULED", alt=None):
    rid = "M3A-H-%03d" % n_id
    first = {}
    for op in ops:
        if op[0] != "seal":
            first.setdefault((op[1], op[2]), op[6])
    ops = [list(o) for o in ops]
    for o in ops:  # series id = <UNDERLYING>/<lane>/<metric>; the lane is that of the first append
        o[1] = "%s/%s/%s" % (o[1], first.get((o[1], o[2]), "stock"), o[2])
    if "series_id" in query:
        query = dict(query)
        query["series_id"] = "%s/%s/%s" % (query["series_id"], query.get("lane", "stock"), query["metric"])
    r = {"id": rid, "family": "history_reuse", "output_id": "M3A-12", "design_ref": "matrix M3A-12 and section 6; R-89, R-52",
         "ruling": rules, "tags": sorted(tags), "derivation": derivation,
         "inputs": {"calendar_ref": cal_ref, "store_config": {"k_default": k_default, "k_by_key": k_by_key or {}}, "ops": ops, "query": query},
         "params": {}}
    r["expected"] = R.store_eval(r, G.CALS)
    r["pending"] = pending
    if alt:
        r["alt_expected"] = alt
    return r


def rng(n):
    return G.rng_for("M3A-H-%03d" % n)


def qb(as_idx, **kw):
    q = {"q": "scalar_baseline", "series_id": "SYN1", "metric": "iv30_close", "as_of": IDS_S[as_idx]}
    q.update(kw)
    return q


def qc(as_idx, m, **kw):
    q = {"q": "same_minute_column", "series_id": "SYN1", "metric": "iv30", "as_of": IDS_M[as_idx], "minute": m}
    q.update(kw)
    return q


def build():
    rows = []
    A = rows.append
    # scalar_baseline (R-51)
    A(row(1, CS, sc(rng(1), range(0, 30)), qb(30), ["scalar_baseline", "basic"], ["R-89", "R-51"], "30 complete sessions before as_of: all 30, oldest first, integer units"))
    A(row(2, CS, sc(rng(2), range(0, 252)), qb(252), ["scalar_baseline", "n252", "retention"], ["R-52", "R-89"], "252 stored, k 252: the max_sessions default reads all 252"))
    A(row(3, CS, sc(rng(3), range(0, 260)), qb(260), ["scalar_baseline", "retention", "n252"], ["R-52", "R-89"], "260 appended, k 252: the ring keeps sessions 8..259; the baseline has 252"))
    ids = [i for i in range(0, 40) if i not in (3, 9, 10, 17, 22, 23, 30, 31)]
    A(row(4, CS, sc(rng(4), ids), qb(40), ["scalar_baseline", "missing_days", "r51"], ["R-51"], "8 missing days skipped; n = 32; no zero padding (exception to M2 Q3)"))
    o = sc(rng(5), range(0, 30))
    for i in (4, 8, 12, 16, 20):
        o[i][5] = 0
    A(row(5, CS, o, qb(30), ["scalar_baseline", "incomplete_day", "r51"], ["R-51", "R-47"], "5 stored incomplete sessions skipped; n = 25"))
    o = sc(rng(6), range(0, 22))
    o[5][5] = 0
    o.append(["seal", "SYN1", "iv30_close", 5])
    A(row(7, CS, o, qb(22), ["scalar_baseline", "seal"], ["R-47"], "an incomplete record sealed later becomes complete and is counted: n = 22"))
    A(row(8, CS, sc(rng(8), range(0, 19)), qb(19), ["scalar_baseline", "insufficient"], ["R-47", "R-51"], "19 available < min_sessions 20"))
    ids = [i for i in range(0, 27) if i not in (2, 5, 8, 11, 14, 17, 20)]
    A(row(9, CS, sc(rng(9), ids), qb(27), ["scalar_baseline", "missing_days", "n20"], ["R-51"], "20 available among 27 calendar sessions: exactly min_sessions, available"))
    ids = [i for i in range(0, 30) if i % 4 != 0]
    A(row(10, CS, sc(rng(10), ids), qb(30), ["scalar_baseline", "missing_days", "no_zero_padding"], ["R-51"], "22 stored of 30 calendar: 22 values, none zero-padded"))
    A(row(11, CS, sc(rng(11), range(0, 40)), qb(40, max_sessions=10, min_sessions=5), ["scalar_baseline", "cap"], ["R-44"], "max_sessions 10: the 10 most recent only"))
    A(row(12, CS, sc(rng(12), range(0, 7)), qb(7, min_sessions=5), ["scalar_baseline", "min_sessions_param"], ["R-44"], "min_sessions 5 with 7 available"))
    A(row(13, CS, sc(rng(13), range(0, 30)), qb(25), ["scalar_baseline", "no_lookahead"], ["R-47"], "30 stored, as_of index 25: only sessions 0..24 are before as_of"))
    A(row(14, CS, sc(rng(14), range(0, 30)), qb(30, min_sessions=0), ["scalar_baseline", "structural"], ["R-72", "R-66"], "min_sessions 0 is malformed_type (view read position 3)"))
    A(row(15, CS, sc(rng(15), range(0, 30)), {"q": "scalar_baseline", "series_id": "SYN1", "metric": "iv30_close", "as_of": "2099-01-05"}, ["scalar_baseline", "structural"], ["R-66"], "as_of not in the calendar: session_not_in_calendar (view read position 1)"))
    # retention in the ring counts every stored record (complete or not)
    o = sc(rng(16), range(0, 252))
    for i in (60, 61):
        o[i][5] = 0
    A(row(16, CS, o, qb(252), ["scalar_baseline", "retention", "incomplete_day"], ["R-52", "R-47"], "252 stored of which 2 incomplete: n = 250 (the ring counts every stored record)"))
    # same_minute_column (R-43, R-55)
    A(row(17, CM, gcol(rng(17), range(0, 60), 10), qc(60, 10), ["same_minute_column", "basic"], ["R-43", "R-89"], "minute 10 of 60 prior sessions (half-days have 12 minutes so minute 10 exists)"))
    A(row(18, CM, gcol(rng(18), range(0, 60), 14), qc(60, 14), ["same_minute_column", "half_day"], ["R-43", "R-55"], "minute 14: sessions 16, 33, 50 have 12 minutes and are skipped"))
    A(row(19, CM, gcol(rng(19), range(0, 40), 11), qc(40, 11), ["same_minute_column", "half_day"], ["R-55"], "minute 11 exists on a 12-minute half-day: nothing skipped"))
    A(row(20, CM, gcol(rng(20), range(0, 40), 12), qc(40, 12), ["same_minute_column", "half_day"], ["R-55"], "minute 12 is the first minute a half-day lacks: sessions 16 and 33 skipped"))
    A(row(21, CM, gcol(rng(21), range(0, 40), 5), qc(135, 12), ["same_minute_column", "structural", "half_day_current"], ["R-54", "R-55"], "as_of session 135 is a half-day of 12 minutes: minute 12 is minute_out_of_range"))
    A(row(22, CM, gcol(rng(22), range(0, 40), 5), qc(40, 30), ["same_minute_column", "structural"], ["R-54"], "minute 30 on a 30-minute session"))
    ids = [i for i in range(0, 40) if i % 2 == 0]
    A(row(23, CM, gcol(rng(23), ids, 5), qc(40, 5), ["same_minute_column", "available", "missing_days"], ["R-51"], "20 sessions stored of 40: exactly 20 values at minute 5, available"))
    A(row(24, CM, gcol(rng(24), range(0, 19), 5), qc(19, 5), ["same_minute_column", "insufficient"], ["R-47"], "19 sessions: insufficient_history"))
    o = gcol(rng(25), range(0, 30), 5)
    for i in (2, 7, 11):
        o[i][5] = 0
    A(row(26, CM, o, qc(30, 5), ["same_minute_column", "incomplete_day"], ["R-47"], "3 incomplete sessions skipped: 27 values"))
    A(row(27, CM, gcol(rng(27), range(0, 40), 5), qc(40, 5.0), ["same_minute_column", "structural", "type_first"], ["R-67"], "float minute: malformed_type"))
    # retention k
    A(row(28, CS, sc(rng(28), range(0, 300)), {"q": "retained"}, ["retention", "k252"], ["R-52"], "300 appended, k 252: the ring keeps the last 252 sessions"))
    A(row(29, CS, sc(rng(29), range(0, 30), series="PRM", metric="premium"), {"q": "retained"}, ["retention", "m2_default"], ["R-52"], "M2 series with the default k 20 keeps 20 of 30", k_default=20))
    A(row(30, CS, sc(rng(30), range(0, 70), series="PRM", metric="premium"), {"q": "retained"}, ["retention", "m2_cap60"], ["R-52"], "M2 series with k 60 keeps 60 of 70 (M2 cap unchanged)", k_default=60))
    o = sc(rng(31), range(0, 80), series="SYN1", metric="iv30_close") + sc(rng(32), range(0, 80), series="PRM", metric="premium")
    A(row(31, CS, o, {"q": "retained"}, ["retention", "per_series_k"], ["R-52"], "iv30 k 252 keeps 80; premium k 60 keeps 60 in the same store: per-series k",
          k_default=60, k_by_key={"SYN1/stock/iv30_close|iv30_close|0": 252}, pending="PENDING-RULING:D9"))
    # canonical text and hash (scalar total, window_s 0)
    a = sc(rng(33), range(0, 5))
    A(row(32, CS, a, {"q": "hashes"}, ["hash", "scalar_total"], ["R-48", "R-89"], "scalar series: canonical line carries grid [], total = units, window_s 0; hashes re-derived from the line text"))
    a, b = sc(rng(34), range(0, 6), series="AAA"), sc(rng(35), range(0, 6), series="BBB")
    arr1 = [x for p in zip(a, b) for x in p]
    arr2 = b[:3] + a[:2] + b[3:] + a[2:]
    A(row(33, CS, arr1, {"q": "hashes"}, ["hash", "arrival", "twin"], ["R-89"], "two series interleaved A1,B1,A2,B2...; twin of 34 (same digest)"))
    A(row(34, CS, arr2, {"q": "hashes"}, ["hash", "arrival", "twin"], ["R-89"], "same records, different interleaving between series: identical dump and digest (content hash stable under shuffled arrival)"))
    o = sc(rng(36), range(0, 4))
    o[2][5] = 0
    A(row(35, CS, o, {"q": "hashes"}, ["hash", "complete_flag"], ["R-47"], "an incomplete record carries complete=false in the line, so the hash differs from the sealed form"))
    o2 = [list(x) for x in o] + [["seal", "SYN1", "iv30_close", 2]]
    A(row(36, CS, o2, {"q": "hashes"}, ["hash", "complete_flag", "seal"], ["R-47"], "after seal the line carries complete=true: hash differs from 35"))
    o = [["s", "SYN1", "skew25", i, -1_000_000 - 37 * i, 1, "stock"] for i in range(0, 4)]
    A(row(37, CS, o, {"q": "hashes"}, ["hash", "negative_total"], ["R-48"], "skew25 totals are signed integers in 10^-8 units"))
    # lane
    o = sc(rng(38), range(0, 5)) + [["s", "SYN1", "iv30_close", 5, 123, 1, "etf_index"]]
    A(row(38, CS, o, {"q": "retained"}, ["lane", "lane_mismatch"], ["R-73", "R-70"], "a record whose lane differs from the ring lane (first append) is lane_mismatch"))
    o = sc(rng(39), range(0, 30), lane="etf_index")
    A(row(39, CS, o, qb(30, lane="stock"), ["lane", "lane_read"], ["R-73"], "ring lane etf_index read with lane stock: lane filter leaves no sessions", pending="PENDING-RULING:D5",
          alt=[{"reading": "R-73 text: history lane mismatch is lane_mismatch", "expected": {"status": "invalid_input", "reason": None, "code": "lane_mismatch", "value": None}}]))
    A(row(40, CS, sc(rng(40), range(0, 30), lane="etf_index"), qb(30, lane="etf_index"), ["lane", "isolation"], ["R-73"], "etf_index ring read with lane etf_index: all 30"))
    # inherited store codes
    o = sc(rng(41), range(0, 4)) + sc(rng(42), [2])
    A(row(41, CS, o, {"q": "retained"}, ["store_code", "out_of_order_append"], ["R-70"], "append of an earlier session: out_of_order_append"))
    o = sc(rng(43), range(0, 4)) + sc(rng(44), [3])
    A(row(42, CS, o, {"q": "retained"}, ["store_code", "duplicate_session"], ["R-70"], "append of the last stored session again: duplicate_session"))
    o = sc(rng(45), range(0, 3)) + [["s", "SYN1", "iv30_close", "2099-03-03", 5, 1, "stock"]]
    A(row(43, CS, o, {"q": "retained"}, ["store_code", "session_not_in_calendar"], ["R-70"], "a session not in the calendar: session_not_in_calendar"))
    o = gcol(rng(46), range(0, 3), 5) + [["g", "SYN1", "iv30", 3, {"base": 1, "over": [], "len": 31}, 1, "stock"]]
    A(row(44, CM, o, {"q": "retained"}, ["store_code", "record_length_mismatch"], ["R-70"], "a dense grid of 31 values on a 30-minute session: record_length_mismatch"))
    o = sc(rng(47), range(0, 3)) + [["s", "SYN1", "iv30_close", 1, 5, 1, "etf_index"]]
    A(row(45, CS, o, {"q": "retained"}, ["store_code", "precedence", "pair"], ["R-66", "R-70"], "lane_mismatch and out_of_order_append both present: lane_mismatch is listed first and is reported"))
    # more inherited codes and hash rows
    A(row(50, CS, sc(rng(50), range(0, 10)) + sc(rng(51), [5]), {"q": "retained"}, ["store_code", "out_of_order_append"], ["R-70"], "session 5 appended after session 9: out_of_order_append"))
    A(row(51, CS, sc(rng(52), [0, 1]) + sc(rng(53), [1]), {"q": "retained"}, ["store_code", "duplicate_session"], ["R-70"], "session 1 appended twice in a row: duplicate_session"))
    A(row(52, CS, sc(rng(54), range(0, 30)), qb(10, min_sessions=5), ["scalar_baseline", "no_lookahead", "as_of_exclusive"], ["R-47"], "as_of index 10 with 30 stored: the 10 earlier sessions, as_of itself excluded"))
    A(row(53, CM, gcol(rng(55), range(0, 30), 5), qc(20, 5), ["same_minute_column", "no_lookahead", "as_of_exclusive"], ["R-47"], "as_of index 20 with 30 stored: 20 earlier sessions, as_of excluded"))
    A(row(54, CS, sc(rng(56), range(0, 300)) + sc(rng(57), range(0, 300), series="SYN1", metric="skew25"), {"q": "retained"}, ["retention", "per_series_k"], ["R-52"],
          "iv30 k 252 and skew25 k 100 in one store: per-series k", k_default=20, k_by_key={"SYN1/stock/iv30_close|iv30_close|0": 252, "SYN1/stock/skew25|skew25|0": 100}, pending="PENDING-RULING:D9"))
    o = sc(rng(58), range(0, 5))
    o[1][5] = 0
    o[3][5] = 0
    A(row(55, CS, o, {"q": "hashes"}, ["hash", "complete_flag"], ["R-47"], "two incomplete records carry complete=false in their lines"))
    z, a_, m_ = sc(rng(59), range(0, 3), series="ZZZ"), sc(rng(60), range(0, 3), series="AAA"), sc(rng(61), range(0, 3), series="MMM")
    A(row(56, CS, z + a_ + m_, {"q": "hashes"}, ["hash", "ordering"], ["R-89"], "series arrive ZZZ, AAA, MMM: the dump is in (series, metric, session) order"))
    A(row(57, CM, gcol(rng(62), range(0, 3), 5) + [["g", "SYN1", "iv30", "2099-03-03", {"base": 1, "over": [], "len": 5}, 1, "stock"]], {"q": "retained"},
          ["store_code", "session_not_in_calendar"], ["R-70"], "a minute grid for a session not in the calendar: session_not_in_calendar"))
    A(row(58, CM, gcol(rng(63), range(0, 3), 5) + [["g", "SYN1", "iv30", 16, {"base": 1, "over": [], "len": 13}, 1, "stock"]], {"q": "retained"},
          ["store_code", "record_length_mismatch", "half_day"], ["R-70", "R-55"], "a grid of 13 values on the 12-minute half-day (index 16): record_length_mismatch"))
    ids = [i for i in range(0, 60) if i not in (35, 38, 41, 44, 47, 50, 52, 55, 57, 58)]
    r = row(59, CS, sc(rng(64), ids), qb(60, max_sessions=30, min_sessions=5), ["scalar_baseline", "cap", "missing_days", "d3"], ["R-44", "R-51"],
            "50 stored, 10 missing in the last 30 calendar sessions, max_sessions 30: last 30 available sessions", pending="PENDING-RULING:D3")
    cal_ids = set(IDS_S[30:60])
    keep = [(a, b) for a, b in zip(r["expected"]["value"]["sessions"], r["expected"]["value"]["values"])]
    allrecs = [(IDS_S[o[3]], o[4]) for o in r["inputs"]["ops"]]
    alt = [(a, b) for a, b in allrecs if a in cal_ids]
    r["alt_expected"] = [{"reading": "calendar window of max_sessions", "expected": {"status": "available", "code": None, "reason": None,
                          "value": {"n": len(alt), "sessions": [a for a, _ in alt], "values": [b for _, b in alt]}}}]
    assert len(alt) < 30
    A(r)
    # ATM form series (owner decision 2): atm_iv minute series, atm_iv_close scalar, no mixing with iv30 / iv30_close
    def qa(as_idx, m, metric="atm_iv", **kw):
        return qc(as_idx, m, metric=metric, **kw)
    A(row(60, CM, gcol(rng(65), range(0, 60), 10, metric="atm_iv"), qa(60, 10), ["same_minute_column", "atm_form"], ["R-81", "R-89"], "atm_iv minute series, minute 10 of 60 prior sessions"))
    A(row(61, CM, gcol(rng(66), range(0, 60), 14, metric="atm_iv"), qa(60, 14), ["same_minute_column", "atm_form", "half_day"], ["R-55", "R-81"], "atm_iv minute 14: the 12-minute half-days skipped"))
    A(row(62, CM, gcol(rng(67), range(0, 40), 5, metric="iv30"), qa(40, 5), ["same_minute_column", "atm_form", "no_mixing"], ["R-81"], "only iv30 minute records stored; reading atm_iv finds no series: insufficient_history"))
    A(row(63, CS, sc(rng(68), range(0, 30), metric="atm_iv_close"), qb(30, metric="atm_iv_close"), ["scalar_baseline", "atm_form"], ["R-81", "R-51"], "atm_iv_close scalar baseline: 30 sessions"))
    A(row(64, CS, sc(rng(69), range(0, 19), metric="atm_iv_close"), qb(19, metric="atm_iv_close"), ["scalar_baseline", "atm_form", "insufficient"], ["R-47"], "19 sessions: insufficient_history"))
    A(row(65, CS, sc(rng(70), range(0, 30), metric="iv30_close"), qb(30, metric="atm_iv_close"), ["scalar_baseline", "atm_form", "no_mixing"], ["R-81"], "only iv30_close stored; atm_iv_close is a different series: insufficient_history"))
    # OWNER DECISION 3: skew25 (spot) and skew25_fwd (forward) series; convention_mismatch at store read
    def scc(r, idxs, metric, conv=None):
        ops = sc(r, idxs, metric=metric)
        return [o + [conv] if conv else o for o in ops]

    def qd(as_idx, metric, conv):
        return qb(as_idx, metric=metric, delta_convention=conv)
    A(row(66, CS, scc(rng(71), range(0, 30), "skew25_fwd", "forward"), qd(30, "skew25_fwd", "forward"), ["scalar_baseline", "convention", "forward"], ["R-89"], "skew25_fwd records carry convention forward; read forward: 30 sessions"))
    A(row(67, CS, scc(rng(72), range(0, 30), "skew25_fwd", "forward"), qd(30, "skew25_fwd", "spot"), ["scalar_baseline", "convention", "convention_mismatch"], ["R-89"], "forward records read with spot: convention_mismatch"))
    A(row(68, CS, scc(rng(73), range(0, 30), "skew25", "forward"), qd(30, "skew25", "spot"), ["scalar_baseline", "convention", "convention_mismatch"], ["R-89"], "a forward record inside the skew25 series read as spot: convention_mismatch"))
    A(row(69, CS, scc(rng(74), range(0, 30), "skew25_fwd"), qd(30, "skew25_fwd", "forward"), ["scalar_baseline", "convention", "convention_mismatch", "no_field"], ["R-89"], "records without a convention field are spot: forward read gives convention_mismatch"))
    A(row(70, CS, scc(rng(75), range(0, 30), "skew25"), qd(30, "skew25", "spot"), ["scalar_baseline", "convention", "spot"], ["R-89"], "records without the field are spot: spot read, 30 sessions"))
    def qdx(as_idx, metric, conv, **kw):
        return qb(as_idx, metric=metric, delta_convention=conv, **kw)
    fw = scc(rng(76), range(0, 30), "skew25_fwd", "forward")
    A(row(71, CS, fw, qdx(30, "skew25_fwd", "spot", X=101), ["scalar_baseline", "convention", "precedence_pair"], ["R-66", "R-160"], "view read: threshold_out_of_range (position 4) before convention_mismatch (position 5)"))
    A(row(72, CS, fw, qdx(30, "skew25_fwd", "spot", X=-1, min_sessions=5), ["scalar_baseline", "convention", "precedence_pair"], ["R-66", "R-160"], "X -1 and a mismatch: threshold_out_of_range first"))
    A(row(73, CS, fw, qdx(30, "skew25_fwd", "spot", min_sessions=0), ["scalar_baseline", "convention", "precedence_pair"], ["R-66", "R-160"], "min_sessions 0 (position 3) before convention_mismatch (position 5)"))
    A(row(74, CS, fw, qdx(30, "skew25_fwd", "spot", X=50), ["scalar_baseline", "convention", "convention_mismatch"], ["R-160"], "valid X 50 with a mismatch: convention_mismatch"))
    # memory against the M2 formula
    def mem(n_id, inputs, why, tags):
        r = {"id": "M3A-H-%03d" % n_id, "family": "history_reuse", "output_id": "M3A-12", "design_ref": "budgets M3A-B8; R-52, R-79", "ruling": ["R-52", "R-79"],
             "tags": ["memory"] + tags, "derivation": why, "inputs": inputs, "params": {}}
        r["expected"] = R.mem_eval(r)
        r["pending"] = "RULED"
        return r
    A(mem(46, {"kind": "grid_bytes", "names": 103, "k": 252, "grid": 390, "copies": 1}, "103 x 252 x 390 x 8 = 80,982,720 bytes raw", ["raw"]))
    A(mem(47, {"kind": "grid_bytes", "names": 103, "k": 252, "grid": 390, "copies": 3}, "x 3 copies (raw, sorted copy, merged array) = 242,948,160, inside the 768 MiB store budget (805,306,368 bytes, R-79)", ["layout3"]))
    A(mem(48, {"kind": "grid_bytes", "names": 400, "k": 252, "grid": 390, "copies": 3}, "400 names x 252 x 390 x 8 x 3 copies = 943,488,000 exceeds the 768 MiB store budget (805,306,368 bytes, R-79)", ["over_budget"]))
    A(mem(49, {"kind": "scalar_bytes", "names": 103, "series": 5, "k": 252}, "103 names x 5 scalar series per name x 252 sessions = 129,780 records (budget M3A-B6)", ["records"]))
    A(mem(75, {"kind": "grid_bytes", "names": 300, "k": 252, "grid": 390, "copies": 3}, "300 names x 252 x 390 x 8 x 3 copies = 707,616,000, inside the 768 MiB store budget (805,306,368 bytes, R-79)", ["within_budget"]))
    return rows


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    rows = build()
    h = G.header("history_reuse", {"ops_format": __doc__})
    C.write_dataset(os.path.join(here, "m3a_cases_history.json"), h, rows)
    return rows


if __name__ == "__main__":
    print(len(main()))
