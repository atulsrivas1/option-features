#!/usr/bin/env python3
"""Second implementation of the M3a structural precedence logic (SYNTHETIC, stdlib only).
Written from docs/m3a/M3A_IO_CONTRACT.md section 4 and the M2 contract section 9 (snapshot, text dump), not from the
generator. evaluate(row, mutations) returns the dict the row's `expected` is compared with. The `mutations` set drives
the mutants of m3a_mutants.py; an empty set is the reference behaviour."""
import hashlib
import math
import re
from decimal import Decimal
from fractions import Fraction

from m3a_common import untag

GRAM = re.compile(r"-?(\d+(\.\d*)?|\.\d+)", re.ASCII)
MODES, LANES, RIGHTS = ("intraday", "close"), ("stock", "etf_index"), ("call", "put")
TENORS = (9, 30, 91)
DELTA_OUT = ("M3A-0", "M3A-7", "M3A-8", "M3A-9", "M3A-10", "M3A-11")
REQ_ORDER = ["cut", "spot", "rate", "mode", "lane", "expiry", "right", "dupid", "strike", "type", "mismatch", "dupkey",
             "tenor", "delta", "ivform", "conv", "fire", "xrange", "minute", "prior", "convmis", "delayed"]
CODE = {"cut": "bad_cutoff", "spot": "bad_spot", "rate": "bad_rate", "mode": "invalid_mode", "lane": "invalid_lane",
        "expiry": "bad_expiry", "right": "unknown_right", "dupid": "duplicate_contract", "strike": "bad_strike",
        "type": "malformed_type", "mismatch": "cutoff_mismatch", "dupkey": "duplicate_contract",
        "tenor": "tenor_not_allowed", "delta": "delta_not_allowed", "ivform": "iv_form_not_allowed", "conv": "convention_not_allowed", "convmis": "convention_mismatch", "fire": "threshold_required",
        "xrange": "threshold_out_of_range", "minute": "minute_out_of_range", "prior": "prior_not_before_cutoff",
        "delayed": "delayed_feed_tag"}
HIST_ORDER = ["h_lane", "h_cal", "h_len", "h_mono", "h_dup", "h_ooo"]
HIST_CODE = {"h_lane": "lane_mismatch", "h_cal": "session_not_in_calendar", "h_len": "record_length_mismatch",
             "h_mono": "non_monotone_grid", "h_dup": "duplicate_session", "h_ooo": "out_of_order_append"}
SNAP_ORDER = ["magic", "length", "hash"]
SNAP_CODE = {"magic": "snapshot_bad_magic", "length": "snapshot_length_mismatch", "hash": "snapshot_hash_mismatch"}
TEXT_ORDER = ["missing", "count", "hash"]
TEXT_CODE = {"missing": "trailer_missing", "count": "trailer_count_mismatch", "hash": "trailer_hash_mismatch"}
VIEW_ORDER = ["v_cal", "v_minute", "v_type", "v_range", "v_conv"]
VIEW_CODE = {"v_cal": "session_not_in_calendar", "v_minute": "minute_out_of_range", "v_type": "malformed_type",
             "v_range": "threshold_out_of_range", "v_conv": "convention_mismatch"}
CLOSED = set(CODE.values()) | set(HIST_CODE.values()) | set(SNAP_CODE.values()) | set(TEXT_CODE.values()) | \
    set(VIEW_CODE.values())


def is_int(v, M=()):
    if "bool_int" in M and isinstance(v, bool):
        return True
    return isinstance(v, int) and not isinstance(v, bool)


def _places(text):
    frac = text.split(".")[1] if "." in text else ""
    return len(frac)     # R-164: length-based, not value-based (trailing zeros count)


def parse_price(v, M=(), spot=False):
    """('ok', Fraction) or ('type', None). Chain strike/quote: text or non-bool int. Spot adds float and Fraction."""
    if is_int(v, M):
        return "ok", Fraction(int(v))
    if isinstance(v, str):
        if not GRAM.fullmatch(v):
            return "type", None
        if "price_ge8" in M:
            if _places(v) >= 8:
                return "type", None
        if "zero_trim" in M:
            if len(v.split(".")[1].rstrip("0") if "." in v else "") > 8 and not ("spot_rep_ok" in M and spot):
                return "type", None
            return "ok", Fraction(Decimal(v))
        if _places(v) > 8 and not ("spot_rep_ok" in M and spot):
            return "type", None
        return "ok", Fraction(Decimal(v))
    if spot and isinstance(v, (float, Fraction)) and not isinstance(v, bool):
        f = Fraction(v)
        if (f * 10 ** 8).denominator != 1 and "spot_rep_ok" not in M:
            return "type", None
        return "ok", f
    return "type", None


def parse_ratio(v, M=()):
    if is_int(v, M):
        return "ok", Fraction(int(v))
    if isinstance(v, str):
        if not GRAM.fullmatch(v):
            return "type", None
        return "ok", Fraction(Decimal(v))
    if isinstance(v, (float, Fraction)) and not isinstance(v, bool):
        return "ok", Fraction(v)
    return "type", None


def _order(base, M):
    o = list(base)
    for m in M:
        if m.startswith("swap:"):
            a, b = m[5:].split(",")
            if a in o and b in o:
                i, j = o.index(a), o.index(b)
                o[i], o[j] = o[j], o[i]
        elif m.startswith("move:"):
            a, b = m[5:].split(",before:")
            if a in o and b in o:
                o.remove(a)
                o.insert(o.index(b), a)
    return o


# ------------------------------------------------------------------ request
def _ck_request(pos, r, M, cs):
    """Checks that are not per contract. Returns a code or None."""
    if pos == "cut":
        v = r["cutoff_ns"]
        if not is_int(v, M):
            return "malformed_type"
        return CODE[pos] if v < 0 else None
    if pos == "spot":
        if isinstance(r["spot"], float) and not math.isfinite(r["spot"]):
            return CODE[pos]
        k, f = parse_price(r["spot"], M, spot=True)
        if k == "type":
            return None if "type_after_value" in M else "malformed_type"
        if "zero_spot_malformed" in M and f == 0:
            return "malformed_type"
        return CODE[pos] if f <= 0 else None
    if pos == "rate":
        pairs = [("rate", (lambda f: abs(f) >= 1) if "rate_ge1" in M else (lambda f: abs(f) > 1)), ("dividend_yield", lambda f: f < 0 or f > 1)]
        if "div_before_rate" in M:
            pairs.reverse()
        for name, bad in pairs:
            if isinstance(r[name], float) and not math.isfinite(r[name]):
                return CODE[pos]
            k, f = parse_ratio(r[name], M)
            if k == "type":
                return "malformed_type"
            if bad(f):
                return CODE[pos]
        return None
    if pos == "mode":
        if not isinstance(r["mode"], str):
            return "malformed_type"
        return CODE[pos] if r["mode"] not in MODES else None
    if pos == "lane":
        if not isinstance(r["lane"], str):
            return "malformed_type"
        return CODE[pos] if r["lane"] not in LANES else None
    if pos == "mismatch":
        if "skip_mismatch" in M:
            return None
        return CODE[pos] if r["evaluation_ns"] != r["cutoff_ns"] else None
    if pos == "tenor":
        return CODE[pos] if any((not is_int(t, M)) or t not in TENORS for t in r["tenors"]) else None
    if pos == "delta":
        k, f = parse_ratio(r["delta_target"], M)
        return CODE[pos] if (k == "type" or f != Fraction(1, 4)) else None
    if pos == "conv":
        if r["output_id"] not in DELTA_OUT:
            return None
        v = r.get("delta_convention", "spot")
        if not isinstance(v, str):
            return "malformed_type"
        return CODE[pos] if v not in ("spot", "forward") else None
    if pos == "convmis":
        p = r.get("prior")
        if p is None or r["output_id"] not in DELTA_OUT:
            return None
        return CODE[pos] if p.get("convention", "spot") != r.get("delta_convention", "spot") else None
    if pos == "ivform":
        if r["output_id"] not in ("M3A-2", "M3A-3"):
            return None
        v = r.get("iv_form", "atm")
        if not isinstance(v, str):
            return "malformed_type"
        return CODE[pos] if v not in ("atm", "30d") else None
    if pos == "fire":
        if r["output_id"] not in ("M3A-3", "M3A-4", "M3A-5", "M3A-6", "M3A-7", "M3A-9", "M3A-10", "M3A-11"):
            return None
        if "direction_unchecked" not in M and not isinstance(r.get("direction", "up"), str):
            return "malformed_type"
        return CODE[pos] if (r["fire"] and r["at_least"] is None and r["at_most"] is None) else None
    if pos == "xrange":
        x = r["x"]
        if r["output_id"] not in ("M3A-1", "M3A-2", "M3A-8"):
            return None
        return CODE[pos] if (x is not None and not (0 <= x < 100 if "x_lt100" in M else 0 <= x <= 100)) else None
    if pos == "minute":
        m = r.get("minute")
        if m is None or r["output_id"] != "M3A-2":
            return None
        hi = r["session_minutes"] + (1 if "minute_le" in M else 0) - (1 if "minute_lt_n1" in M else 0)
        return CODE[pos] if (not is_int(m, M) or not (0 <= m < hi)) else None
    if pos == "prior":
        p = r.get("prior")
        if p is None or r["output_id"] not in ("M3A-3", "M3A-6", "M3A-9"):
            return None
        if "prior_gt" in M:
            return CODE[pos] if p["time_ns"] > r["cutoff_ns"] else None
        if "prior_ge_m1" in M:
            return CODE[pos] if p["time_ns"] >= r["cutoff_ns"] - 1 else None
        return CODE[pos] if p["time_ns"] >= r["cutoff_ns"] else None
    if pos == "delayed":
        if r["feed_delay_tag"] != "delayed":
            return None
        out, mode = r["output_id"], r["mode"]
        hit = out == "M3A-2" or (mode == "intraday" and out in ("M3A-1", "M3A-3"))
        return CODE[pos] if hit else None
    return None


def _ck_contract(pos, c, st, M):
    if pos == "expiry":
        if not is_int(c["expiry_days"], M):
            return "malformed_type"
        return CODE[pos] if c["expiry_days"] < 1 else None
    if pos == "right":
        if not isinstance(c["right"], str):
            return "malformed_type"
        return CODE[pos] if c["right"] not in RIGHTS else None
    if pos == "dupid":
        if "dup_id_late" in M:
            return None
        hit = c["contract_id"] in st["ids"]
        st["ids"].add(c["contract_id"])
        return CODE[pos] if hit else None
    if pos == "strike":
        if "strike_type_late" in M:
            k, f = parse_price(c["strike"], M)
            return CODE[pos] if (k == "ok" and f <= 0) else None
        k, f = parse_price(c["strike"], M)
        if k == "type":
            return "malformed_type"
        return CODE[pos] if f <= 0 else None
    if pos == "type":
        for fld in ("bid", "ask"):
            if c[fld] is None:
                continue      # None = missing quote (M1 invalid_quote), not structural (PO batch 2)
            if parse_price(c[fld], M)[0] == "type":
                return "malformed_type"
        if not isinstance(c["condition"], str) or not isinstance(c["style"], str):
            return "malformed_type"
        if not is_int(c["event_ns"], M):
            return "malformed_type"
        if c["known_at_ns"] is not None and not is_int(c["known_at_ns"], M):
            return "malformed_type"
        if "strike_type_late" in M and parse_price(c["strike"], M)[0] == "type":
            return "malformed_type"
        if "dup_id_late" in M:
            hit = c["contract_id"] in st["ids2"]
            st["ids2"].add(c["contract_id"])
            if hit:
                return "duplicate_contract"
        return None
    if pos == "dupkey":
        k, f = parse_price(c["strike"], M)
        if k != "ok" or not is_int(c["expiry_days"], M):
            return None
        key = (c["expiry_days"], f, c["right"])
        hit = key in st["keys"]
        st["keys"].add(key)
        return CODE[pos] if hit else None
    return None


PER_CONTRACT = {"expiry", "right", "dupid", "strike", "type", "dupkey"}


def request_code(r, M):
    order = _order(REQ_ORDER, M)
    cs = r["contracts"]
    code = None
    if "contract_major" in M:
        # wrong scan: all positions for contract 0, then contract 1 ... (R-101 says position-major)
        sts = {p: {"ids": set(), "ids2": set(), "keys": set()} for p in PER_CONTRACT}
        for c in cs:
            for p in order:
                if p in PER_CONTRACT:
                    code = _ck_contract(p, c, sts[p], M)
                    if code:
                        return _fin(code, M)
        for p in order:
            if p not in PER_CONTRACT:
                code = _ck_request(p, r, M, cs)
                if code:
                    return _fin(code, M)
        return None
    for p in order:
        if p in PER_CONTRACT:
            st = {"ids": set(), "ids2": set(), "keys": set()}
            for c in cs:
                code = _ck_contract(p, c, st, M)
                if code:
                    return _fin(code, M)
            if p == "type":
                # request-level type check of the same slot: evaluation_ns (after the per-contract fields)
                if not is_int(r["evaluation_ns"], M):
                    return _fin("malformed_type", M)
        else:
            code = _ck_request(p, r, M, cs)
            if code:
                return _fin(code, M)
    if "type_after_value" in M and parse_price(r["spot"], M, spot=True)[0] == "type":
        return _fin("malformed_type", M)
    return None


def _fin(code, M):
    if "foreign_code" in M and code == "malformed_type":
        return "bad_input"
    return code


# ------------------------------------------------------------------ history
def history_code(ops, cal, M):
    minutes = {s: m for s, m in cal}
    order = _order(HIST_ORDER, M)
    ring = {}
    pre = []                                   # per op: (ring lane, previous session of the ring)
    for o in ops:
        key = (o["series_id"], o["metric"], o["window_s"])
        st = ring.setdefault(key, {"lane": o["lane"], "last": None})
        pre.append((st["lane"], st["last"]))
        st["last"] = o["session_id"]
    if "load_position_major" in M:
        for p in order:
            for i, o in enumerate(ops):
                lane, last = pre[i]
                s_ = o["session_id"]
                hit = (p == "h_lane" and o["lane"] != lane) or (p == "h_cal" and s_ not in minutes) or                       (p == "h_dup" and last is not None and s_ == last) or (p == "h_ooo" and last is not None and s_ < last)
                if hit:
                    return HIST_CODE[p], i
        return None, None
    for i, o in enumerate(ops):             # RECORD-MAJOR (PO R-141..R-150, as M2)
        for p in order:
            lane, last = pre[i]
            s = o["session_id"]
            hit = False
            if p == "h_lane":
                hit = o["lane"] != lane
            elif p == "h_cal":
                hit = s not in minutes
            elif p == "h_len":
                if s in minutes:
                    n = minutes[s]
                    idx = o.get("grid_idx")
                    if idx is not None:
                        hit = any(not (0 <= x < n) for x in idx)
                    else:
                        hit = len(o["grid"]) > n
            elif p == "h_mono":
                idx = o.get("grid_idx")
                hit = idx is not None and any(idx[j] >= idx[j + 1] for j in range(len(idx) - 1))
            elif p == "h_dup":
                hit = last is not None and s == last
            elif p == "h_ooo":
                hit = last is not None and s < last
            if hit:
                return HIST_CODE[p], i
    return None, None


# ------------------------------------------------------------------ snapshot and text
def snapshot_code(buf, M):
    order = _order(SNAP_ORDER, M)
    for p in order:
        if p == "magic":
            if buf[:7] != b"M2SNAP1":
                return SNAP_CODE[p]
        elif p == "length":
            if len(buf) < 47 or int.from_bytes(buf[7:15], "little") != len(buf):
                return SNAP_CODE[p]
        elif p == "hash":
            if len(buf) >= 47 and hashlib.sha256(buf[47:]).digest() != buf[15:47]:
                return SNAP_CODE[p]
    return None


def text_code(text, M):
    import json
    order = _order(TEXT_ORDER, M)
    lines = [l for l in text.split("\n") if l != ""]
    trailers = [l for l in lines if l.startswith("#END ")]
    recs = [l for l in lines if not l.startswith("#")]
    for p in order:
        if p == "missing":
            if not trailers:
                return TEXT_CODE[p]
        elif trailers:
            f = dict(x.split("=", 1) for x in trailers[-1].split()[1:])
            if p == "count" and int(f["records"]) != len(recs):
                return TEXT_CODE[p]
            if p == "hash":
                h = hashlib.sha256("\n".join(json.loads(l)["content_sha256"] for l in recs).encode("ascii")).hexdigest()
                if f["content_sha256"] != h:
                    return TEXT_CODE[p]
    return None


# ------------------------------------------------------------------ view read
def view_code(inp, par, M):
    minutes = dict((s, m) for s, m in inp["calendar"])
    order = _order(VIEW_ORDER, M)
    for p in order:
        if p == "v_cal" and inp["as_of"] not in minutes:
            return VIEW_CODE[p]
        if p == "v_minute" and inp["form"] == "same_minute_column" and inp["as_of"] in minutes:
            m = par["minute"]
            if not is_int(m, M) or not (0 <= m < minutes[inp["as_of"]] - (1 if "minute_lt_n1" in M else 0)):
                return VIEW_CODE[p]
        if p == "v_type":
            for k in ("min_sessions", "max_sessions"):
                if not is_int(par[k], M) or par[k] < 1:
                    return VIEW_CODE[p]
        if p == "v_conv":
            mt = inp["series_id"].split("/")[-1]
            if mt in ("skew25", "skew25_fwd") and ("forward" if mt.endswith("_fwd") else "spot") != par.get("delta_convention", "spot"):
                return VIEW_CODE[p]
        if p == "v_range":
            x = par.get("x")
            if x is not None and not (0 <= x < 100 if "x_lt100" in M else 0 <= x <= 100):
                return VIEW_CODE[p]
    return None


# ------------------------------------------------------------------ lane read
def lane_read(inp, par, M):
    cal = [s for s, _ in inp["calendar"]]
    pos = {s: i for i, s in enumerate(cal)}
    cur = pos[inp["as_of"]]
    rs = [r for r in inp["records"] if r["complete"] and pos[r["session_id"]] < cur
          and ("lane_pool" in M or r["lane"] == inp["lane"])]
    rs.sort(key=lambda r: pos[r["session_id"]])
    rs = rs[-par["max_sessions"]:]
    vals = [r["total"] for r in rs]
    if len(vals) < par["min_sessions"]:
        return {"status": "unavailable", "reason": "insufficient_history", "code": None, "n": len(vals), "values": None, "sessions": None}  # R-192
    return {"status": "available", "reason": None, "code": None, "n": len(vals), "values": vals, "sessions": [r["session_id"] for r in rs]}


# ------------------------------------------------------------------ entry
def invalid(code, **extra):
    if code is None:
        return {"status": "valid", "reason": None, "code": None, "first_failing_code": None}
    d = {"status": "invalid_input", "reason": None, "code": code, "first_failing_code": code}
    d.update(extra)
    return d


def evaluate(row, M=frozenset()):
    inp, par = untag(row["inputs"]), untag(row["params"])
    e = inp["entry"]
    if e == "request":
        r = dict(inp)
        r.update(par)
        return invalid(request_code(r, M))
    if e in ("history_append", "history_load"):
        code, i = history_code(inp["ops"], inp["calendar"], M)
        return invalid(code, op_index=i)
    if e == "snapshot_load":
        return invalid(snapshot_code(bytes.fromhex(inp["snapshot_hex"]), M))
    if e == "text_load":
        return invalid(text_code(inp["text"], M))
    if e == "view_read":
        return invalid(view_code(inp, par, M))
    if e == "lane_read":
        return lane_read(inp, par, M)
    raise ValueError(e)


def agrees(row, got):
    exp = row["expected"]
    for k in ("status", "reason", "code", "first_failing_code", "op_index", "n", "values", "sessions"):
        if k in exp and exp[k] != got.get(k):
            return False
    return True
