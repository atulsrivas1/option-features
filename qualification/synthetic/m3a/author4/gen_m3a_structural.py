#!/usr/bin/env python3
"""Generator G6 (structural) and the lane family for Option Features M3a (SYNTHETIC, stdlib only).
Writes m3a_cases_structural.json (87 rows), m3a_cases_structural_aux.json (second instantiations of every
adjacent pair, used only to give every mutant two catching rows) and m3a_cases_lane.json (6 rows).
Expected values are constructed from the precedence lists of docs/m3a/M3A_IO_CONTRACT.md section 4 by
construction (the first injected code of the pair is the expected code); m3a_ref.py recomputes them
independently. No library code is imported. Usage: python gen_m3a_structural.py --out DIR [--seed N]"""
import argparse
import json
import os
import struct
from decimal import Decimal
from fractions import Fraction

from m3a_common import DEFAULT_SEED, calendar, sha, tag, write_rows

CUT = 1_000_000_000_000          # cutoff_ns of the base request (integer ns)
CAL = calendar(40, 9)            # 40 sessions, index 9 is a 210-minute half-day
SID = [c[0] for c in CAL]

PENDING_UNUSED = {
    "Q01": "delta_target ruled set is not stated in the contract (assumed {0.25}, decimal text)",
    "Q02": "parameter names for a fire rule asked without a threshold (assumed fire=true, threshold=null)",
    "Q03": "applicability of positions 16-18 when the parameter belongs to another output (assumed: 16 when minute is present, 17 when prior is present)",
    "Q04": "record_length_mismatch needs the session minutes; with the session absent from the calendar the minutes are unknown",
    "Q05": "trailer_missing and trailer_count_mismatch exclude each other on one text; pair row is nominal (a line without the #END prefix)",
    "Q06": "what threshold_out_of_range checks in a view read is not stated (assumed min_sessions > max_sessions or max_sessions > 252)",
}

# injection name per entry of the request list (19 codes in 18 positions)
INJ_NAME = ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10A", "P10B", "P11", "P12", "P13", "P14", "P15",
            "P16", "P17", "P18"]
CODE_OF = dict(zip(INJ_NAME, ["bad_cutoff", "bad_spot", "bad_rate", "invalid_mode", "invalid_lane", "bad_expiry",
                              "unknown_right", "duplicate_contract", "bad_strike", "malformed_type", "cutoff_mismatch",
                              "duplicate_contract", "tenor_not_allowed", "delta_not_allowed", "threshold_required",
                              "threshold_out_of_range", "minute_out_of_range", "prior_not_before_cutoff",
                              "delayed_feed_tag"]))
PEND_OF = {}


def contract(cid, right, strike):
    return {"contract_id": cid, "expiry_days": 30, "right": right, "strike": strike, "bid": "1.0000", "ask": "1.1000",
            "event_ns": CUT - 5_000_000_000, "known_at_ns": None, "style": "european", "condition": "regular"}


def base():
    inputs = {"entry": "request", "cutoff_ns": CUT, "spot": "100", "rate": "0.0500", "dividend_yield": "0.0100",
              "contracts": [contract("C1", "call", "100"), contract("C2", "put", "100")]}
    params = {"mode": "intraday", "lane": "stock", "evaluation_ns": CUT, "feed_delay_tag": "live",
              "output_id": "M3A-0", "tenors": [9, 30, 91], "delta_target": "0.25", "fire": False, "at_least": None, "at_most": None,
              "direction": "up", "iv_form": "atm", "delta_convention": "spot", "x": 5, "minute": None, "session_minutes": 390, "prior": None}
    return inputs, params


def inject(name, inputs, params, idx=0, var=0):
    cs = inputs["contracts"]
    if name == "P1":
        v = [-1, -5000][var]
        inputs["cutoff_ns"] = v
        params["evaluation_ns"] = v
    elif name == "P2":
        inputs["spot"] = ["0", -3][var]
    elif name == "P3":
        if var == 0:
            inputs["rate"] = "1.5"
        else:
            inputs["dividend_yield"] = "1.01"
    elif name == "P4":
        params["mode"] = ["weekly", ""][var]
    elif name == "P5":
        params["lane"] = ["etf", "ETF_INDEX"][var]
    elif name == "P6":
        cs[idx]["expiry_days"] = [0, -7][var]
    elif name == "P7":
        cs[idx]["right"] = ["straddle", "CALL"][var]
    elif name == "P8":
        if var == 0:
            cs[1]["contract_id"] = cs[0]["contract_id"]
        else:
            cs[0]["contract_id"] = cs[1]["contract_id"]
    elif name == "P9":
        cs[idx]["strike"] = ["0", "-5"][var]
    elif name == "P10A":
        if var == 0:
            cs[idx]["ask"] = "1.123456789"
        else:
            cs[idx]["bid"] = " 1"
    elif name == "P10B":
        params["evaluation_ns"] = [CUT + 1, CUT - 1][var]
    elif name == "P11":
        if var == 0:
            cs[1]["right"], cs[1]["strike"] = cs[0]["right"], cs[0]["strike"]
        else:
            cs[0]["right"], cs[0]["strike"] = cs[1]["right"], cs[1]["strike"]
    elif name == "P12":
        params["tenors"] = [[7], [9, 30, 92]][var]
    elif name == "P13":
        params["delta_target"] = ["0.10", "0.5"][var]
    elif name == "P14":
        params["fire"] = True
        params["output_id"] = "M3A-3"          # V4 uses thresholds
        params["mode"] = "intraday"
        if var:
            params["direction"] = "either"
    elif name == "P15":
        params["x"] = [101, -1][var]
        params["output_id"] = "M3A-1"          # V1 uses x
    elif name == "P16":
        params["output_id"], params["minute"] = "M3A-2", [390, -1][var]
    elif name == "P17":
        params["output_id"] = "M3A-3"
        params["prior"] = [{"kind": "frame", "time_ns": CUT},
                           {"kind": "session", "time_ns": CUT + 5_000_000_000}][var]
    elif name == "P18":
        params["feed_delay_tag"] = "delayed"
        params["output_id"] = "M3A-3"
        params["mode"] = "intraday"
    else:
        raise KeyError(name)


def mk(rid, family, tags, rn, pend, design, inputs, params, code, derivation, extra=None):
    exp = {"status": "invalid_input", "reason": None, "code": code, "first_failing_code": code, "value": None,
           "fired": None}
    if extra:
        exp.update(extra)
    return {"id": rid, "family": family, "design_ref": design, "r_numbers": rn,
            "ruling": "PENDING-RULING" if pend else "RULED", "pending": pend, "tags": tags,
            "inputs": tag(inputs), "params": tag(params), "expected": exp, "derivation": derivation}


def req_row(rid, tags, names, code, derivation, rn, var=0, idxs=None, pend=None,
            design="IO contract section 4 (request list)", mutate=None):
    inputs, params = base()
    idxs = idxs or {}
    for n in names:
        inject(n, inputs, params, idxs.get(n, 0), var)
    if mutate:
        mutate(inputs, params)
    return mk(rid, "structural", tags, rn, pend or [], design, inputs, params, code, derivation)


# ---------------------------------------------------------------- history / snapshot / text / view builders
def hrec(session, lane="stock", kind="scalar", total=2_500_000_000, grid=None, grid_idx=None, series="SYN1/stock/iv30", conv=None):
    r = {"lane": lane, "series_id": series, "session_id": session, "complete": True}
    if kind == "scalar":
        r.update({"metric": "iv30", "window_s": 0, "grid": [], "total": total})
    else:
        g = grid if grid is not None else [2_000_000_000 + i for i in range(5)]
        r.update({"metric": "iv30", "window_s": 60, "grid": g, "total": sum(g)})
    if grid_idx is not None:
        r["grid_idx"] = grid_idx
    if conv is not None:
        r["convention"] = conv
    return r


def hist_row(rid, tags, rn, pend, entry, ops, code, op_index, derivation,
             design="M2 order, unchanged (IO contract section 4)", family="structural"):
    inputs = {"entry": entry, "calendar": CAL, "k": 252, "ops": ops}
    return mk(rid, family, tags, rn, pend, design, inputs, {}, code, derivation, {"op_index": op_index})


def jdump(d):
    return json.dumps(d, separators=(",", ":"), ensure_ascii=True)       # insertion order = canonical key order


def canon_line(rec):
    d = {"series_id": rec["series_id"], "metric": rec["metric"], "session_id": rec["session_id"],
         "window_s": rec["window_s"], "grid": rec["grid"]}
    if "grid_idx" in rec:
        d["grid_idx"] = rec["grid_idx"]
    d["total"] = rec["total"]
    d["complete"] = rec["complete"]
    h = sha((jdump(d) + "\n").encode("ascii"))
    d["content_sha256"] = h
    return jdump(d), h


def snap_build(recs, magic=b"M2SNAP1", len_delta=0, flip=False, trunc=0):
    body = "".join(canon_line(r)[0] + "\n" for r in recs).encode("ascii")
    hb = bytes.fromhex(sha(body))
    if flip:
        body = body[:10] + bytes([body[10] ^ 1]) + body[11:]
    total = 7 + 8 + 32 + len(body)
    out = magic + struct.pack("<Q", total + len_delta) + hb + body
    return out[:len(out) - trunc] if trunc else out


def snap_row(rid, tags, rn, pend, buf, code, derivation):
    inputs = {"entry": "snapshot_load", "calendar": CAL, "k": 252, "snapshot_hex": buf.hex()}
    return mk(rid, "structural", tags, rn, pend, "M2 section 9.7 (snapshot), IO contract section 4", inputs, {}, code,
              derivation)


def text_build(recs, trailer):
    lines = [canon_line(r)[0] for r in recs]
    chash = sha("\n".join(canon_line(r)[1] for r in recs).encode("ascii"))
    text = "".join(l + "\n" for l in lines)
    if trailer == "none":
        return text
    kind, n, h = trailer
    return text + "%s records=%d content_sha256=%s\n" % (kind, n, chash if h == "good" else h)


def text_row(rid, tags, rn, pend, text, code, derivation):
    inputs = {"entry": "text_load", "calendar": CAL, "k": 252, "text": text}
    return mk(rid, "structural", tags, rn, pend, "M2 section 9.7 (text dump), IO contract section 4", inputs, {}, code,
              derivation)


def view_row(rid, tags, rn, pend, form, as_of, minute, mn, mx, code, derivation, x=None, series=None, dc=None):
    inputs = {"entry": "view_read", "form": form, "series_id": "SYN1/stock/iv30", "lane": "stock", "as_of": as_of, "calendar": CAL}
    params = {"min_sessions": mn, "max_sessions": mx, "x": x}
    if form == "same_minute_column":
        params["minute"] = minute
    if series:
        inputs["series_id"] = series
    if dc is not None:
        params["delta_convention"] = dc
    return mk(rid, "structural", tags, rn, pend, "IO contract section 4 (view read, 4 positions)", inputs, params, code,
              derivation)


# ---------------------------------------------------------------- structural rows
def build_structural():
    rows = []

    def add(r):
        r["id"] = "M3A-STRUCT-%03d" % (len(rows) + 1)
        rows.append(r)

    S = SID
    # 18 request code rows (position 10 contributes malformed_type; cutoff_mismatch has its own two rows)
    for nm in INJ_NAME:
        if nm == "P10B":
            continue
        add(req_row("", ["code", "request", nm], [nm], CODE_OF[nm],
                    "single injected defect at %s; every other check passes" % nm, ["R-69", "R-66"],
                    pend=PEND_OF.get(nm)))
    # 16 non-request code rows
    c = ["code", "history"]
    add(hist_row("", c, ["R-70", "R-66"], [], "history_append", [hrec(S[0]), hrec(S[1], lane="etf_index")],
                 "lane_mismatch", 1, "ring lane is the lane of the first append (stock); second append is etf_index"))
    add(hist_row("", c, ["R-70", "R-66"], [], "history_append", [hrec(S[0]), hrec("2026-06-01")],
                 "session_not_in_calendar", 1, "session 2026-06-01 is not in the calendar"))
    add(hist_row("", c, ["R-70", "R-66"], [], "history_append",
                 [hrec(S[0], kind="minute"), hrec(S[1], kind="minute", grid=[1] * 391)], "record_length_mismatch", 1,
                 "dense grid of 391 values on a 390-minute session"))
    add(hist_row("", c, ["R-70", "R-66"], [], "history_append",
                 [hrec(S[0], kind="minute"), hrec(S[1], kind="minute", grid=[7, 8, 9], grid_idx=[5, 3, 9])],
                 "non_monotone_grid", 1, "sparse indexes 5,3,9 are not increasing"))
    add(hist_row("", c, ["R-70", "R-66"], [], "history_append", [hrec(S[0]), hrec(S[1]), hrec(S[1])],
                 "duplicate_session", 2, "session equals the last appended session"))
    add(hist_row("", c, ["R-70", "R-66"], [], "history_append", [hrec(S[0]), hrec(S[1]), hrec(S[0])],
                 "out_of_order_append", 2, "session is earlier than the last appended session"))
    two = [hrec(S[0]), hrec(S[1])]
    add(snap_row("", ["code", "snapshot"], ["R-66"], [], snap_build(two, magic=b"X2SNAP1"), "snapshot_bad_magic",
                 "first magic byte differs"))
    add(snap_row("", ["code", "snapshot"], ["R-66"], [], snap_build(two, trunc=5), "snapshot_length_mismatch",
                 "truncated by 5 bytes; stored length no longer equals the byte count"))
    add(snap_row("", ["code", "snapshot"], ["R-66"], [], snap_build(two, flip=True), "snapshot_hash_mismatch",
                 "one body byte flipped; magic and length intact"))
    add(text_row("", ["code", "text"], ["R-66"], [], text_build(two, "none"), "trailer_missing", "no #END line"))
    add(text_row("", ["code", "text"], ["R-66"], [], text_build(two, ("#END", 3, "good")), "trailer_count_mismatch",
                 "trailer says 3 records, 2 lines parse"))
    add(text_row("", ["code", "text"], ["R-66"], [], text_build(two, ("#END", 2, "00" * 32)), "trailer_hash_mismatch",
                 "count correct, content hash zeroed"))
    add(view_row("", ["code", "view"], ["R-66", "R-89"], [], "scalar_baseline", "2026-12-31", None, 20, 252,
                 "session_not_in_calendar", "current session 2026-12-31 not in the calendar"))
    add(view_row("", ["code", "view"], ["R-54", "R-66"], [], "same_minute_column", S[20], 390, 20, 252,
                 "minute_out_of_range", "minute 390 on a 390-minute grid (valid 0..389)"))
    add(view_row("", ["code", "view"], ["R-72", "R-66"], [], "scalar_baseline", S[20], None, "20", 252,
                 "malformed_type", "min_sessions given as text"))
    add(view_row("", ["code", "view"], ["R-72", "R-66"], [], "scalar_baseline", S[20], None, 20, 252,
                 "threshold_out_of_range", "x = 101 outside 0..100 at view read (PO ruling Q06)", x=101))
    # 6 type rows (tagged encodings per R-65)
    tv = [("bid", 1.5, "float"), ("bid", Decimal("1.5"), "Decimal"), ("bid", Fraction(3, 2), "Fraction"),
          ("bid", True, "bool"), ("event_ns", None, "None"), ("bid", b"1.5", "bytes")]
    for field, val, nm in tv:
        def m(inputs, params, field=field, val=val):
            inputs["contracts"][0][field] = val
        add(req_row("", ["type", "request"], [], "malformed_type", "%s value in field %s" % (nm, field),
                    ["R-69", "R-65", "R-98"], mutate=m, design="IO contract section 1 and 4 (position 10)"))
    # 2 cutoff_mismatch rows
    add(req_row("", ["cutoff"], ["P10B"], "cutoff_mismatch", "evaluation_ns = cutoff_ns + 1, all types valid",
                ["R-100"]))

    def zero_cut(inputs, params):
        inputs["cutoff_ns"], params["evaluation_ns"] = 0, 1
        for k in inputs["contracts"]:
            k["event_ns"] = 0
        params["tenors"] = [7]
    add(req_row("", ["cutoff"], [], "cutoff_mismatch",
                "cutoff_ns 0 is valid, evaluation_ns 1 differs; the tenor list is also invalid at a later position",
                ["R-100"], mutate=zero_cut))

    # 3 spot rows
    def spot(v):
        def m(inputs, params):
            inputs["spot"] = v
        return m
    add(req_row("", ["spot"], [], "malformed_type", "9-decimal text spot (more than 8 places), position 2",
                ["R-98", "R-69"], mutate=spot("100.123456789")))
    add(req_row("", ["spot"], [], "malformed_type", "float 100.1 is not exactly representable in 8 decimals",
                ["R-98", "R-69"], mutate=spot(100.1)))
    add(req_row("", ["spot"], [], "bad_spot", "spot 0 is a value error (not > 0)", ["R-98", "R-69"], mutate=spot(0)))
    # PO batch 2: wrong-typed cutoff_ns, expiry_days, mode, lane, right are malformed_type (2 rows each)
    def wt(field, val, where):
        def m(inputs, params):
            if where == "i":
                inputs[field] = val
            elif where == "p":
                params[field] = val
            else:
                inputs["contracts"][0][field] = val
            if field == "cutoff_ns":
                params["evaluation_ns"] = CUT
        return m
    for field, vals, where in (("cutoff_ns", ("5", 1.5), "i"), ("expiry_days", (1.5, "30"), "c"),
                               ("mode", (5, None), "p"), ("lane", (3, None), "p"), ("right", (1, None), "c")):
        for v in vals:
            add(req_row("", ["typed", "request"], [], "malformed_type",
                        "wrong-typed %s (%r) is malformed_type at its own position (R-67, PO batch 2)" % (field, v),
                        ["R-67", "R-69"], mutate=wt(field, v, where)))
    for field, v, code in (("spot", float("nan"), "bad_spot"), ("spot", float("-inf"), "bad_spot"),
                           ("rate", float("inf"), "bad_rate"), ("dividend_yield", float("nan"), "bad_rate")):
        def mm(inputs, params, field=field, v=v):
            inputs[field] = v
        add(req_row("", ["nonfinite", "request"], [], code,
                    "non-finite float %s in %s is a value error (tagged float object)" % (v, field),
                    ["R-98", "R-65"], mutate=mm))
    # round 1 review: None bid/ask = missing quote (R-124, not structural); type rows, 2 each
    for fld in ("bid", "ask"):
        def mn(inputs, params, fld=fld):
            inputs["contracts"][0][fld] = None
        r = req_row("", ["quote_none", "request"], [], None, "None %s is a missing quote (M1 invalid_quote, R-124): no structural code" % fld,
                    ["R-124"], mutate=mn)
        r["expected"].update({"status": "valid"})
        add(r)
    for fld, vals, where in (("known_at_ns", ("5", 1.5), "c"), ("condition", (5, None), "c"), ("style", (3, None), "c"),
                             ("strike", ("abc", "1e5"), "c"), ("strike", ("100.123456789", "0.000000001"), "c")):
        for v in vals:
            def mt(inputs, params, fld=fld, v=v):
                inputs["contracts"][0][fld] = v
            add(req_row("", ["typed2", "request"], [], "malformed_type", "%s = %r is malformed_type (grammar, type or more than 8 decimals)" % (fld, v),
                        ["R-69", "R-98"], mutate=mt))
    # Owner decision 2: iv_form selector on V3 and V4 (position ASSUMED between delta_not_allowed and
    # threshold_required until PR 104 is read; pair rows with the neighbours are PENDING-RULING on the position)
    def ivf(v, extra=None):
        def m(inputs, params):
            params["output_id"], params["iv_form"] = "M3A-3", v
            if extra:
                extra(inputs, params)
        return m
    pos = ["IVF1"]
    for v in ("30D", ""):
        add(req_row("", ["ivform", "request"], [], "iv_form_not_allowed", "iv_form %r outside {atm, 30d} on V4" % v,
                    ["R-DEC2"], mutate=ivf(v)))
    for v in (5, None):
        add(req_row("", ["ivform", "request"], [], "malformed_type", "non-string iv_form %r is malformed_type at the iv_form position" % (v,),
                    ["R-DEC2", "R-67"], mutate=ivf(v)))
    for var, v in ((0, "fast"), (1, "")):
        r = req_row("", ["ivform", "ivpair", "request"], ["P13"], "delta_not_allowed", "delta_not_allowed (13) before iv_form_not_allowed (variant %d)" % var,
                    ["R-DEC2", "R-66"], var=var, mutate=ivf(v))
        add(r)
    for var, v in ((0, "fast"), (1, "")):
        def both(inputs, params):
            params["fire"] = True
        r = req_row("", ["ivform", "ivmixed", "request"], [], "iv_form_not_allowed", "iv_form_not_allowed before threshold_required (variant %d)" % var,
                    ["R-DEC2", "R-66"], mutate=ivf(v, both))
        add(r)
    def mix1(inputs, params):
        params["tenors"] = [7]
    add(req_row("", ["ivform", "mixed", "request"], [], "tenor_not_allowed", "tenor_not_allowed (12) precedes the non-string iv_form",
                ["R-DEC2", "R-67"], mutate=ivf(5, mix1)))
    def mix2(inputs, params):
        inputs["rate"] = "2"
    add(req_row("", ["ivform", "mixed", "request"], [], "bad_rate", "bad_rate (3) precedes the non-string iv_form",
                ["R-DEC2", "R-67"], mutate=ivf(None, mix2)))
    def mix3(inputs, params):
        params["fire"] = True
    add(req_row("", ["ivform", "mixed", "request"], [], "malformed_type", "non-string iv_form reports before threshold_required (14)",
                ["R-DEC2", "R-67"], mutate=ivf(5, mix3)))
    # Owner decision 3 (R-155 to R-161): slot 13 after iv_form_not_allowed; convention_mismatch slot 17 after prior_not_before_cutoff and last at view read; history append list unchanged (6 M2 positions)
    CP = []

    def dcv(v, extra=None):
        def m(inputs, params):
            params["output_id"], params["delta_convention"] = "M3A-7", v
            if extra:
                extra(inputs, params)
        return m
    for v in ("mid", "FORWARD"):
        add(req_row("", ["convention", "request"], [], "convention_not_allowed", "delta_convention %r outside {spot, forward} on V8" % v, ["R-DEC3"], mutate=dcv(v)))
    for v in (5, None):
        add(req_row("", ["convention", "request"], [], "malformed_type", "non-string delta_convention %r is malformed_type" % (v,), ["R-DEC3", "R-67"], mutate=dcv(v)))
    for var, v in ((0, "mid"), (1, "FORWARD")):
        add(req_row("", ["convention", "convmixed", "request"], ["P13"], "delta_not_allowed", "delta_not_allowed before convention_not_allowed, same slot 13 (variant %d)" % var, ["R-DEC3", "R-66"], var=var, mutate=dcv(v), pend=CP))
    for var, v in ((0, "mid"), (1, "FORWARD")):
        def ivbad(inputs, params, var=var):
            params["iv_form"] = "fast" if var == 0 else ""
        add(req_row("", ["convention", "convpair", "request"], [], "convention_not_allowed", "iv_form precedes convention in slot 13; no output uses both, so the confirmed equivalent pair is nominal (variant %d)" % var, ["R-DEC3", "R-66"], mutate=dcv(v, ivbad), pend=CP))

    for var, v in ((0, "mid"), (1, "FORWARD")):
        def firebad(inputs, params):
            params["fire"] = True
        add(req_row("", ["convention", "convpair", "request"], [], "convention_not_allowed", "convention_not_allowed (13) before threshold_required (14) on V8 (variant %d)" % var,
                    ["R-DEC3", "R-66"], mutate=dcv(v, firebad)))

    def mismatch(dc, pc, tm=1_000_000_000):
        def m(inputs, params):
            params["output_id"], params["delta_convention"] = "M3A-9", dc
            params["prior"] = {"kind": "session", "time_ns": CUT - tm}
            if pc:
                params["prior"]["convention"] = pc
        return m
    add(req_row("", ["convention", "request"], [], "convention_mismatch", "prior of convention forward, request default spot", ["R-DEC3"], mutate=mismatch("spot", "forward"), pend=CP))
    add(req_row("", ["convention", "request"], [], "convention_mismatch", "request forward, prior record without the field (= spot)", ["R-DEC3"], mutate=mismatch("forward", None), pend=CP))
    for var, tm in ((0, 0), (1, -5_000_000_000)):
        add(req_row("", ["convention", "convpair", "request"], [], "prior_not_before_cutoff", "prior at or after the cutoff and a convention mismatch: prior_not_before_cutoff first (variant %d)" % var, ["R-DEC3", "R-66"], mutate=mismatch("spot", "forward", tm), pend=CP))
    for var, tag_ in ((0, "delayed"), (1, "delayed")):
        def dm(inputs, params, var=var):
            mismatch("spot" if var == 0 else "forward", "forward" if var == 0 else None)(inputs, params)
            params["feed_delay_tag"] = "delayed"
        add(req_row("", ["convention", "convpair", "request"], [], "convention_mismatch", "convention_mismatch before delayed_feed_tag; no output uses both, nominal pair (variant %d)" % var, ["R-DEC3", "R-66"], mutate=dm, pend=CP))
    S0 = SID
    for series, dc in (("SYN1/stock/skew25_fwd", None), ("SYN1/stock/skew25", "forward")):
        add(view_row("", ["convention", "view"], ["R-DEC3"], CP, "scalar_baseline", S0[20], None, 20, 252, "convention_mismatch",
                     "series %s read with delta_convention %s" % (series, dc or "spot (default)"), series=series, dc=dc))
    for series, dc in (("SYN1/stock/skew25_fwd", None), ("SYN1/stock/skew25", "forward")):
        add(view_row("", ["convention", "convpair", "view"], ["R-DEC3", "R-66"], CP, "scalar_baseline", S0[20], None, 20, 252, "threshold_out_of_range",
                     "x outside 0..100 and a convention mismatch: threshold_out_of_range first", x=101, series=series, dc=dc))
    # fix round 2 (R-148, R-164, R-165, accept-side boundaries)
    for r in extra_rows(0):
        add(r)
    # 30 pair rows and 12 type-first rows
    for r in pair_rows(0):
        add(r)
    for r in typefirst_rows():
        add(r)
    assert len(rows) == 157, len(rows)
    return rows


def accept_row(tags, derivation, rn, mutate):
    r = req_row("", ["boundary", "request"] + tags, [], None, derivation, rn, mutate=mutate)
    r["expected"].update({"status": "valid"})
    return r


def extra_rows(var):
    """Fix round 2. var 0 = primary (13 rows), var 1 = aux (3 rows)."""
    S = SID
    rows = []
    if var == 1:
        rows.append(hist_row("", ["loadscan"], ["R-148"], [], "history_load",
                             [hrec(S[0]), hrec(S[1]), hrec(S[0], total=2_500_000_002), hrec(S[2], lane="etf_index")],
                             "out_of_order_append", 2,
                             "record-major load (R-148): record 2 is out of order, record 3 has the wrong lane; the first failing record reports; a position-major scan would give lane_mismatch (variant 1)"))
        def tz(inputs, params):
            inputs["contracts"][0]["strike"] = "2.000000000"
        rows.append(req_row("", ["typed3"], [], "malformed_type", "strike '2.000000000' has 9 decimal places, trailing zero included: malformed_type (R-164, length-based; variant 1)", ["R-164", "R-69"], mutate=tz))
        def dr(inputs, params):
            params["output_id"], params["direction"] = "M3A-3", None
        rows.append(req_row("", ["typed3"], [], "malformed_type", "non-string direction None is malformed_type at the threshold slot (R-165; variant 1)", ["R-165", "R-67"], mutate=dr))
        return rows
    # accept side
    def x100(inputs, params):
        params["output_id"], params["x"] = "M3A-1", 100
    rows.append(accept_row(["x"], "x = 100 on V1 is inside 0..100: no structural code", ["R-98", "R-69"], x100))
    def m389(inputs, params):
        params["output_id"], params["minute"], params["session_minutes"] = "M3A-2", 389, 390
    rows.append(accept_row(["minute"], "minute 389 is the last minute of a 390-minute grid: no structural code", ["R-54", "R-69"], m389))
    def p8(inputs, params):
        inputs["contracts"][0]["strike"] = "100.12345678"
    rows.append(accept_row(["price"], "strike with exactly 8 decimals is valid (R-164)", ["R-164", "R-98"], p8))
    def s8(inputs, params):
        inputs["spot"] = "100.12345678"
    rows.append(accept_row(["price"], "spot text with exactly 8 decimals is valid (R-98)", ["R-98"], s8))
    for rv in ("1", "-1"):
        def rt(inputs, params, rv=rv):
            inputs["rate"] = rv
        rows.append(accept_row(["rate"], "|rate| = 1 (%s) is inside the allowed range: no structural code" % rv, ["R-98"], rt))
    for out in ("M3A-3", "M3A-6"):
        def pr(inputs, params, out=out):
            params["output_id"] = out
            params["prior"] = {"kind": "session", "time_ns": CUT - 1}
        rows.append(accept_row(["prior"], "prior one ns before the cutoff on %s is accepted (strictly before)" % out, ["R-DEC3", "R-69"], pr))
    v = view_row("", ["boundary", "view", "x"], ["R-98"], [], "scalar_baseline", S[20], None, 20, 252, None, "x = 100 at view read is accepted", x=100)
    v["expected"].update({"status": "valid"})
    rows.append(v)
    v = view_row("", ["boundary", "view", "minute"], ["R-54"], [], "same_minute_column", S[20], 389, 20, 252, None, "minute 389 on a 390-minute session at view read is accepted")
    v["expected"].update({"status": "valid"})
    rows.append(v)
    rows.append(hist_row("", ["loadscan"], ["R-148"], [], "history_load",
                         [hrec(S[0]), hrec(S[1]), hrec(S[0], total=2_500_000_001), hrec(S[2], lane="etf_index")],
                         "out_of_order_append", 2,
                         "record-major load (R-148): record 2 is out of order, record 3 has the wrong lane; the first failing record reports; a position-major scan would give lane_mismatch"))
    def tz(inputs, params):
        inputs["contracts"][0]["strike"] = "1.000000000"
    rows.append(req_row("", ["typed3"], [], "malformed_type", "strike '1.000000000' has 9 decimal places, trailing zero included: malformed_type (R-164, length-based)", ["R-164", "R-69"], mutate=tz))
    def dr(inputs, params):
        params["output_id"], params["direction"] = "M3A-3", 5
    rows.append(req_row("", ["typed3"], [], "malformed_type", "non-string direction 5 is malformed_type at the threshold slot (R-165); the out-of-range direction string row is DEFERRED (no contract code)", ["R-165", "R-67"], mutate=dr))
    assert len(rows) == 13, len(rows)
    return rows


def pair_rows(var):
    S = SID
    o = 0 if var == 0 else 4              # session offset so the aux variant differs
    out = []
    for i in range(18):
        a, b = INJ_NAME[i], INJ_NAME[i + 1]
        pend = sorted(set(PEND_OF.get(a, []) + PEND_OF.get(b, [])))
        order = [b, a] if (a, b) in (("P16", "P17"), ("P14", "P15")) else [a, b]   # minute unused unless output is M3A-2 (PO Q03)
        out.append(req_row("", ["pair", "request", a + "+" + b], order, CODE_OF[a],
                           "both defects present; the earlier list entry %s must be reported (variant %d; where both "
                           "are per-contract the earlier defect sits on the later contract)" % (a, var),
                           ["R-66", "R-101"], var=var, idxs={a: 1, b: 0}, pend=pend))
    t = ["pair", "history"]
    rn = ["R-66", "R-70"]
    out.append(hist_row("", t, rn, [], "history_append",
                        [hrec(S[o]), hrec("2026-06-01", lane="etf_index", total=2_600_000_000 + o)],
                        "lane_mismatch", 1, "lane mismatch and session not in calendar: lane_mismatch first"))
    out.append(hist_row("", t, rn, [], "history_append",
                        [hrec(S[o], kind="minute"), hrec("2026-06-0%d" % (1 + var), kind="minute", grid=[1] * (391 + var))],
                        "session_not_in_calendar", 1, "session absent and grid longer than any session"))
    out.append(hist_row("", t, rn, [], "history_append",
                        [hrec(S[o], kind="minute"),
                         hrec(S[o + 1], kind="minute", grid=[7, 8, 9], grid_idx=[0, 400 + var, 2])],
                        "record_length_mismatch", 1, "index outside [0,390) and indexes not increasing"))
    out.append(hist_row("", t, rn, [], "history_append",
                        [hrec(S[o], kind="minute"), hrec(S[o + 1], kind="minute"),
                         hrec(S[o + 1], kind="minute", grid=[7, 8, 9], grid_idx=[5, 3 - var, 9])],
                        "non_monotone_grid", 2, "indexes not increasing and session equals the last session"))
    out.append(hist_row("", t, rn, [], "history_load",
                        [hrec(S[o]), hrec(S[o + 1]), hrec(S[o + 1], total=2_500_000_001 + var), hrec(S[o])],
                        "duplicate_session", 2,
                        "load stream: record 2 repeats the last session, record 3 is earlier; one record cannot be "
                        "both, so the errors sit in different records and the list order decides"))
    recs = [hrec(S[o], total=2_500_000_000 + var), hrec(S[o + 1], total=2_510_000_000 + var)]
    if var:
        recs.append(hrec(S[o + 2], total=2_520_000_000))
    out.append(snap_row("", ["pair", "snapshot"], ["R-66"], [], snap_build(recs, magic=b"X2SNAP1", len_delta=1 + var),
                        "snapshot_bad_magic", "bad magic and wrong stored length"))
    out.append(snap_row("", ["pair", "snapshot"], ["R-66"], [], snap_build(recs, len_delta=1 + var, flip=True),
                        "snapshot_length_mismatch", "wrong stored length and a flipped body byte"))
    out.append(text_row("", ["pair", "text"], ["R-66"], [], text_build(recs, ("#TRAILER", 3 + var, "good")),
                        "trailer_missing", "no line starts with #END; the decoy is a parseable #-prefixed comment line, not a non-JSON data line (nominal pair, Q05)"))
    out.append(text_row("", ["pair", "text"], ["R-66"], [], text_build(recs, ("#END", 5 + var, "00" * 32)),
                        "trailer_count_mismatch", "wrong count and wrong hash"))
    asof = "2026-12-3%d" % (1 - var)
    out.append(view_row("", ["pair", "view"], ["R-66"], [], "same_minute_column", asof, 999 + var, 20, 252,
                        "session_not_in_calendar", "session absent and minute out of range"))
    hd = S[9] if var else S[20]            # the half-day (210 minutes) in the aux variant
    out.append(view_row("", ["pair", "view"], ["R-66", "R-54"], [], "same_minute_column", hd, 390 - 180 * var, 0, 252,
                        "minute_out_of_range", "minute beyond the session grid and min_sessions 0"))
    out.append(view_row("", ["pair", "view"], ["R-66", "R-72"], [], "scalar_baseline", S[20 + var], None, 0 - var,
                        252, "malformed_type", "min_sessions below 1 and x outside 0..100", x=-1 if var else 101))
    assert len(out) == 30
    return out


def typefirst_rows(var=0):
    rows = []
    V = var == 1

    def r(tags, rn, code, derivation, mutate):
        rows.append(req_row("", ["typefirst"] + tags, [], code, derivation + (" (variant 1)" if V else ""), rn,
                            mutate=mutate,
                            design="IO contract section 4 (type-first per field, R-67; scan order R-101)"))

    def m1(i, p):
        i["spot"], i["cutoff_ns"], p["evaluation_ns"] = ("abc", -2, -2) if V else (None, -1, -1)
    r(["spotfield"], ["R-67"], "bad_cutoff", "spot type error at position 2, bad_cutoff at position 1 is earlier", m1)

    def m2(i, p):
        i["spot"], i["rate"] = (Fraction(1, 3), "2") if V else (True, "2")
    r(["spotfield"], ["R-67"], "malformed_type", "wrong-typed spot at position 2, before the bad_rate value error at 3", m2)

    def m3(i, p):
        i["rate"], p["mode"] = (Decimal("0.05"), "") if V else (b"0.05", "weekly")
    r(["rate"], ["R-67"], "malformed_type", "wrong-typed rate at position 3, before invalid_mode at 4", m3)

    def m4(i, p):
        i["rate"], p["lane"] = ("3/4", "ETF") if V else ("1/2", "etf")
    r(["rate"], ["R-67", "R-98"], "malformed_type", "'a/b' text rate is malformed_type at position 3, before invalid_lane", m4)

    def m5(i, p):
        i["rate"], i["dividend_yield"] = ("-2", None) if V else ("2", True)
    r(["rate", "dividend_yield"], ["R-67"], "bad_rate", "same position, fields in order written: rate (value error) before dividend_yield (type error)", m5)

    def m6(i, p):
        i["rate"], i["dividend_yield"] = (None, "2") if V else (True, "-1")
    r(["rate", "dividend_yield"], ["R-67"], "malformed_type", "same position: rate type error is checked before the dividend_yield value error", m6)

    def m7(i, p):
        i["contracts"][0]["strike"], i["contracts"][1]["right"] = (True, "CALL") if V else (100.5, "straddle")
    r(["strike"], ["R-67", "R-101"], "unknown_right", "wrong-typed strike reports at position 9; unknown_right at 7 is earlier", m7)

    def m8(i, p):
        i["contracts"][0]["strike"], i["contracts"][1]["strike"] = (1.5, "-3") if V else (None, "-1")
    r(["strike"], ["R-67", "R-101"], "malformed_type", "same position 9: contract order decides; first contract has the type error", m8)

    def m9(i, p):
        i["contracts"][0]["strike"], i["contracts"][1]["strike"] = ("-3", 1.5) if V else ("-1", None)
    r(["strike"], ["R-67", "R-101"], "bad_strike", "same position 9: contract order decides; first contract has the value error", m9)

    def m10(i, p):
        i["contracts"][1]["ask" if V else "bid"], p["tenors"] = (Fraction(1, 2), [8]) if V else (b"1", [7])
    r(["bid"], ["R-67"], "malformed_type", "type error at position 10 precedes tenor_not_allowed at 12", m10)

    def m11(i, p):
        i["contracts"][1]["contract_id"], i["contracts"][1]["bid"] = "C1", (Decimal("2.5") if V else 2.5)
    r(["duplicate"], ["R-102"], "duplicate_contract", "R-102(a): shared id (position 8) beats the wrong-typed bid of the second contract (position 10)", m11)

    def m12(i, p):
        c = i["contracts"][1]
        c["right"], c["strike"] = "call", "100"
        c["ask" if V else "bid"] = b"x" if V else 2.5
    r(["duplicate"], ["R-102"], "malformed_type", "R-102(b): same expiry/strike/right under different ids (position 11) loses to the wrong-typed field (position 10)", m12)
    assert len(rows) == 12
    return rows


def build_aux():
    rows = pair_rows(1) + typefirst_rows(1) + extra_rows(1)
    for i, r in enumerate(rows):
        r["id"] = "M3A-STRUCT-AUX-%03d" % (i + 1)
        r["tags"] = r["tags"] + ["aux"]
    return rows


# ---------------------------------------------------------------- lane rows (6)
def lane_rows():
    cal = CAL

    def recs(lane, a, b, base_total):
        return [{"lane": lane, "session_id": cal[j][0], "total": base_total + j * 1000, "complete": True}
                for j in range(a, b)]

    def read_row(i, lane, rr, mn, as_of, reason, extra, derivation, rn):
        inputs = {"entry": "lane_read", "form": "scalar_baseline", "series_id": "SYN1/%s/iv30" % lane, "metric": "iv30",
                  "lane": lane, "as_of": as_of, "calendar": cal, "records": rr}
        params = {"min_sessions": mn, "max_sessions": 252}
        exp = {"status": "available" if reason is None else "unavailable", "reason": reason, "code": None,
               "value": None, "fired": None}
        exp.update(extra)
        return {"id": "M3A-LANE-%03d" % i, "family": "lane", "design_ref": "R-73; matrix section 6 (lane in the series id)",
                "r_numbers": rn, "ruling": "RULED", "pending": [], "tags": ["lane"], "inputs": tag(inputs),
                "params": tag(params), "expected": exp, "derivation": derivation}

    stock22, etf22 = recs("stock", 0, 22, 2_000_000_000), recs("etf_index", 0, 22, 3_000_000_000)
    rows = []
    r1 = hist_row("M3A-LANE-001", ["lane"], ["R-73", "R-70"], [], "history_append",
                  [hrec(SID[0]), hrec(SID[1], lane="etf_index")], "lane_mismatch", 1,
                  "lane isolation at append: ring lane stock, record etf_index", "R-73; IO contract section 4",
                  family="lane")
    rows.append(r1)
    inputs, params = base()
    params["lane"] = "ETF_INDEX"
    rows.append(mk("M3A-LANE-002", "lane", ["lane"], ["R-73", "R-88"], [], "R-73; IO contract section 4 position 5",
                   inputs, params, "invalid_lane", "lane value outside {stock, etf_index}"))
    rows.append(read_row(3, "etf_index", stock22, 20, cal[22][0], "insufficient_history", {"n": 0, "values": [], "sessions": []},
                         "only stock sessions are stored; an etf_index read finds none", ["R-73", "R-89"]))
    rows.append(read_row(4, "stock", stock22 + etf22, 20, cal[22][0], None,
                         {"n": 22, "values": [r["total"] for r in stock22], "sessions": [r["session_id"] for r in stock22]},
                         "same name in both lanes: the stock read returns the 22 stock values only, oldest first",
                         ["R-73", "R-89"]))
    rows.append(read_row(5, "etf_index", stock22 + etf22, 20, cal[22][0], None,
                         {"n": 22, "values": [r["total"] for r in etf22], "sessions": [r["session_id"] for r in etf22]},
                         "the etf_index read returns the etf_index values only", ["R-73", "R-89"]))
    mixed = [{"lane": "stock" if j % 5 != 4 else "etf_index", "session_id": cal[j][0], "total": 2_000_000_000 + j,
              "complete": True} for j in range(25)]
    st = [r["total"] for r in mixed if r["lane"] == "stock"]
    rows.append(read_row(6, "stock", mixed, 21, cal[25][0], "insufficient_history", {"n": len(st), "values": st, "sessions": [r["session_id"] for r in mixed if r["lane"] == "stock"]},
                         "25 stored sessions interleave two lanes, 20 are stock; min_sessions 21 is reached only if "
                         "the lanes were pooled, so the stock read is insufficient_history with n 20",
                         ["R-73", "R-51"]))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    extra = {"pending_questions": {}, "rulings_applied": "PO batch 2, round 1 review, PR 104 positions (head 1ec672f), convention_mismatch at request and view read only; see AUTHORING_NOTES.md", "calendar_sessions": len(CAL), "cutoff_ns_base": CUT}
    s, x, l = build_structural(), build_aux(), lane_rows()
    write_rows(os.path.join(a.out, "m3a_cases_structural.json"), "structural", a.seed, s, extra)
    write_rows(os.path.join(a.out, "m3a_cases_structural_aux.json"), "structural_aux", a.seed, x, extra)
    write_rows(os.path.join(a.out, "m3a_cases_lane.json"), "lane", a.seed, l, extra)
    print("structural", len(s), "aux", len(x), "lane", len(l))


if __name__ == "__main__":
    main()
