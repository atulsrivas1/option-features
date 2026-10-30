"""Second implementation (exact Fractions, Decimal rounding, bisect ranks, ring objects) written separately from m3a_ref.py.
Used by m3a_selfcheck.py and, with one rule changed at a time (MU), by m3a_mutants.py."""
import bisect
import hashlib
import json
import re
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction

from m3a_common import decode

_MU = None


def MU(name):
    return _MU == name


def isint(v):
    return type(v) is int


def to_units(x):
    """Round once from the exact binary64 value with the decimal module."""
    mode = ROUND_HALF_UP if MU("round_half_up") else ROUND_DOWN if MU("round_trunc") else ROUND_HALF_EVEN
    with localcontext() as ctx:
        ctx.prec = 80
        d = Decimal(x).quantize(Decimal("1E-8"), rounding=mode)
        return int(d.scaleb(8))


def fmt(u):
    neg = u < 0 and not (MU("negative_zero_text") and False)
    s = "%d.%08d" % (abs(u) // 10 ** 8, abs(u) % 10 ** 8)
    if u < 0:
        return "-" + s
    return "-" + s if (MU("negative_zero_text") and u == 0) else s


def shown(fr):
    fr = Fraction(fr)
    if MU("share_unreduced"):
        return "%d/%d" % (fr.numerator, fr.denominator) if fr.denominator != 1 else 1
    if fr.denominator == 1:
        return "%d/1" % fr.numerator if MU("integral_as_fraction") else fr.numerator
    return "%d/%d" % (fr.numerator, fr.denominator)


def parse_X(v):
    if isint(v):
        return Fraction(v)
    if isinstance(v, Fraction):
        return v
    if MU("x_float_ok") and isinstance(v, float):
        return Fraction(v)
    if MU("x_decimal_ok") and isinstance(v, Decimal):
        return Fraction(v)
    if isinstance(v, str):
        m = re.fullmatch(r"(-?\d+)/(\d+)", v)
        if m and int(m.group(2)):
            return Fraction(int(m.group(1)), int(m.group(2)))
    return None


class Ring:
    def __init__(self, k):
        self.k, self.recs = k, []

    def push(self, rec):
        self.recs.append(rec)
        while len(self.recs) > self.k:
            del self.recs[0]


def gs_vals(gs):
    out = [gs["base"]] * gs["len"]
    for i, v in gs["over"]:
        out[i] = v
    return out


def _req_sid(row):
    I = row["inputs"]
    sid = I["series"]["series_id"]
    if row["output_id"] == "M3A-2":
        w = {"atm": "atm_iv", "30d": "iv30"}.get(row["params"].get("iv_form", "atm"))
        if w is not None and I["series"]["metric"] != w:
            head_, _, _ = sid.rpartition("/")
            return head_ + "/" + w
    return sid


def result(row, status, reason=None, code=None, value=None, fired=None, extra=None):
    I = row["inputs"]
    r = {"output_id": row["output_id"], "series_id": _req_sid(row), "session_id": I["session"]["session_id"],
         "evaluation_ns": I["evaluation_ns"], "lane": I["lane"], "status": status, "reason": reason, "code": code, "value": value, "fired": fired}
    if extra:
        r.update(extra)
    return r


def pct(row, cals):
    I, P = row["inputs"], decode(row["params"])
    oid = row["output_id"]
    cal = cals[I["calendar_ref"]]
    sids = [c[0] for c in cal]

    def bad(c):
        return result(row, "invalid_input", code=c)
    mode = P.get("mode", "intraday")
    form = conv = None

    def selector():
        nonlocal form, conv
        if oid == "M3A-2":
            form = P.get("iv_form", "30d" if MU("iv_form_default_30d") else "atm")
            if not isinstance(form, str) and not MU("iv_form_type_ok"):
                return bad("malformed_type")
            if form not in ("atm", "30d") and not MU("iv_form_invalid_ok"):
                return bad("iv_form_not_allowed")
        if oid == "M3A-8":
            conv = P.get("delta_convention", "forward" if MU("conv_default_forward") else "spot")
            if not isinstance(conv, str) and not MU("conv_type_ok"):
                return bad("malformed_type")
            if conv not in ("spot", "forward") and not MU("conv_invalid_ok"):
                return bad("convention_not_allowed")
        return None

    dmin = 10 if MU("min_default_10") else 20
    mins, maxs = P.get("min_sessions", dmin), P.get("max_sessions", 252)
    X = P.get("x", P.get("X", 10 if MU("x_default_10") else 5))

    def bad(c):
        return result(row, "invalid_input", code=c)
    if mode not in ("intraday", "close"):
        return bad("invalid_mode")
    if I["lane"] not in ("stock", "etf_index"):
        return bad("invalid_lane")
    if MU("selector_first"):
        c = selector()
        if c:
            return c
    Xf = parse_X(X)
    if MU("x_before_sessions"):
        if Xf is None:
            return bad("malformed_type")
        if Xf < 0 or Xf > 100:
            return bad("threshold_out_of_range")
    for v in (mins, maxs):
        if not isint(v) or (v < 1 and not (MU("min_sessions_zero_ok") and v == 0)):
            return bad("malformed_type")
    if not MU("selector_first"):
        c = selector()
        if c:
            return c
    if Xf is None:
        return bad("malformed_type")
    lo_ok, hi_ok = (Xf > 0, Xf < 100) if MU("x_range_exclusive") else (Xf >= 0, Xf <= 100)
    if not (lo_ok and hi_ok):
        return bad("threshold_out_of_range")
    sess = I["session"]
    sid = sess["session_id"]
    mm = None
    if oid == "M3A-2":
        mm = P.get("minute")
        if not isint(mm):
            return bad("malformed_type")
        cm = cal[sids.index(sid)][1] if sid in sids else None
        if cm is not None:
            lo = -10 ** 6 if MU("negative_minute_ok") else 0
            hi = cm + 1 if MU("minute_range_inclusive") else cm
            if not (lo <= mm < hi):
                return bad("minute_out_of_range")
    late = MU("mismatch_after_delayed")
    if oid == "M3A-8" and not MU("conv_mismatch_ignored") and not late:
        have = I.get("records_convention", "forward" if I["series"]["metric"] == "skew25_fwd" else "spot")
        if have != conv:
            return bad("convention_mismatch")
    delayed = sess["feed_delay_tag"] == "delayed"
    if delayed and not MU("delayed_ignored") and (mode == "intraday" or oid == "M3A-2" or MU("delayed_close_rejected")):
        return bad("delayed_feed_tag")
    if sid not in sids:
        return bad("session_not_in_calendar")
    cur = sids.index(sid)
    if oid == "M3A-8" and late and not MU("conv_mismatch_ignored"):
        have = I.get("records_convention", "forward" if I["series"]["metric"] == "skew25_fwd" else "spot")
        if have != conv:
            return bad("convention_mismatch")
    now = I["now"]
    up = now.get("unavailable")
    xu = None
    if up is None:
        if oid == "M3A-8":
            if MU("round_parts_first"):
                xu = to_units(now["put25_iv"]) - to_units(now["call25_iv"])
            else:
                xu = to_units(now["put25_iv"] - now["call25_iv"])
        else:
            xu = to_units(now["float"])
    # history through a ring of every stored record
    ring = Ring(60 if MU("retention_60") else I.get("store_k", 252))
    for rec in I["records"]:
        ring.push(rec)
    vals, stored_idx = [], []
    mixed = oid == "M3A-2" and I["series"]["metric"] != {"atm": "atm_iv", "30d": "iv30"}.get(form) and not MU("form_mix_allowed")
    lane_ok = (I["ring_lane"] == I["lane"] or MU("lane_ignored")) and not mixed
    for rec in (ring.recs if lane_ok else []):
        idx, payload, done = rec
        if not done and not MU("incomplete_counted"):
            continue
        if MU("lookahead_included"):
            if idx == cur and False:
                continue
        elif idx > cur or (idx == cur and not MU("today_included")):
            continue
        if oid == "M3A-2":
            g = gs_vals(payload)
            j = mm + 1 if MU("minute_off_by_one") else mm
            if j >= len(g):
                if MU("minute_substituted"):
                    vals.append(g[-1])
                    stored_idx.append(idx)
                elif MU("halfday_zero"):
                    vals.append(0)
                    stored_idx.append(idx)
                continue
            vals.append(g[j])
        else:
            vals.append(payload)
        stored_idx.append(idx)
    if MU("missing_zero_padded") and stored_idx:
        gaps = [i for i in range(stored_idx[0], cur) if i not in set(stored_idx)]
        vals = vals + [0] * len(gaps)
    if not MU("cap_ignored"):
        vals = vals[:maxs] if MU("cap_oldest") else vals[-maxs:]
    n = len(vals)
    fails = []

    def f_up():
        if up is not None and not MU("upstream_last"):
            fails.append(("up", up))

    def f_ins():
        if n < (mins - 1 if MU("accept_19") else mins):
            fails.append(("ins", "insufficient_history"))

    def f_cmp():
        if mode == "close" and not sess["complete"] and not MU("complete_ignored"):
            fails.append(("cmp", "session_not_complete"))

    def f_zr():
        if n and not MU("zero_range_skipped"):
            span = vals + ([xu] if MU("zero_range_with_x") and xu is not None else [])
            if min(span) == max(span):
                fails.append(("zr", "zero_range_history"))
    seq = [f_up, f_cmp, f_ins, f_zr] if MU("order_complete_first") else [f_up, f_ins, f_cmp, f_zr]
    for f in seq:
        f()
    if MU("upstream_last") and up is not None:
        fails.append(("up", up))
    if fails:
        return result(row, "unavailable", reason=fails[0][1])
    srt = sorted(vals)
    gt = n - bisect.bisect_right(srt, xu)
    eq = bisect.bisect_right(srt, xu) - bisect.bisect_left(srt, xu)
    ge, le = gt + eq, bisect.bisect_right(srt, xu)
    if MU("rank_strict_gt"):
        up_share = Fraction(gt, n)
    elif MU("ties_split"):
        up_share = (gt + Fraction(eq, 2)) / n
    elif MU("mean_rank"):
        up_share = Fraction(ge + n - le, 2 * n)
    else:
        up_share = Fraction(ge, n)
    lo_share = Fraction(le, n)
    tail = P.get("tail", "top")
    basis = up_share
    if tail == "bottom":
        basis = up_share if MU("bottom_uses_upper") else lo_share
    elif MU("top_uses_lower"):
        basis = lo_share
    if oid == "M3A-2":
        basis = up_share
    fired = basis * 100 < Xf if MU("fires_exclusive") else basis * 100 <= Xf
    val = {"x": fmt(xu), "n": n}
    if oid == "M3A-2":
        val.update(minute=mm, rank_le=le, upper_share=shown(up_share))
    else:
        form = ("end_of_day" if mode == "intraday" else "intraday") if MU("form_swapped") else ("intraday" if mode == "intraday" else "end_of_day")
        val.update(rank_le=le, upper_share=shown(up_share), lower_share=shown(lo_share), form=form)
    labels = [I.get("model_label", "exact-model")]
    if delayed and not MU("labels_no_delayed"):
        labels.append("delayed")
    echo = {"x": shown(Xf), "min_sessions": mins, "max_sessions": maxs}
    if oid == "M3A-2":
        echo.update(minute=mm, mode="intraday")
        if not MU("iv_form_not_echoed"):
            echo["iv_form"] = form
    else:
        echo.update(mode=mode, tail=tail)
        if oid == "M3A-8" and not MU("conv_not_echoed"):
            echo["delta_convention"] = conv
    labels.sort()
    return result(row, "available", value=val, fired=bool(fired), extra={"params": echo, "labels": labels})


def pad_sub(a, b):
    return a - b


def store(row, cals):
    I = row["inputs"]
    cal = cals[I["calendar_ref"]]
    sids = [c[0] for c in cal]
    minutes = {c[0]: c[1] for c in cal}
    cfg = I["store_config"]
    rings, lanes = {}, {}
    arrival = 0

    def bad(c):
        return {"status": "invalid_input", "code": c, "reason": None, "value": None}
    for op in I["ops"]:
        if op[0] == "seal":
            if MU("seal_ignored"):
                continue
            for rec in rings.get((op[1], op[2]), Ring(0)).recs:
                if rec["sid"] == sids[op[3]]:
                    rec["done"] = True
            continue
        kind, ser, met, idx, pay, done, lane = op[:7]
        key = (ser, met)
        sid = sids[idx] if isint(idx) else idx
        if key in lanes and lanes[key] != lane and not MU("lane_unchecked"):
            return bad("lane_mismatch")
        if sid not in minutes and not MU("calendar_unchecked"):
            return bad("session_not_in_calendar")
        if kind == "g" and pay["len"] > minutes.get(sid, 10 ** 9) and not MU("length_unchecked"):
            return bad("record_length_mismatch")
        ring = rings.get(key)
        k = 253 if MU("retention_253") else (cfg["k_default"] if MU("per_series_k_ignored") else cfg["k_by_key"].get("%s|%s|0" % key, cfg["k_default"]))
        if ring is None:
            ring = rings[key] = Ring(k)
        if ring.recs:
            last, cur = sids.index(ring.recs[-1]["sid"]), (sids.index(sid) if sid in sids else len(sids))
            if cur == last:
                if not MU("dup_allowed"):
                    return bad("duplicate_session")
            elif cur < last and not MU("oop_ignored"):
                return bad("out_of_order_append")
        lanes.setdefault(key, lane)
        ring.push({"sid": sid, "kind": kind, "pay": pay, "done": bool(done), "lane": lane, "arr": arrival,
                   "conv": ("forward" if MU("missing_conv_as_forward") else "spot") if len(op) < 8 else op[7]})
        arrival += 1
    q = I["query"]
    ok = {"status": "available", "code": None, "reason": None}
    if q["q"] == "retained":
        ok["value"] = {"retained": {"%s|%s|0" % k: [r["sid"] for r in rings[k].recs] for k in sorted(rings)}}
        return ok
    if q["q"] == "hashes":
        lines, hs = [], []
        order = list(rings) if MU("dump_unsorted") else sorted(rings)
        for k in order:
            for r in sorted(rings[k].recs, key=lambda r: r["sid"]):
                body = '{"series_id":%s,"metric":%s,"session_id":%s,"window_s":0,"grid":[],"total":%d,"complete":%s' % (
                    json.dumps(k[0]), json.dumps(k[1]), json.dumps(r["sid"]), r["pay"], "true" if (r["done"] or MU("complete_not_hashed")) else "false")
                if MU("arrival_hashed"):
                    body += ',"arrival":%d' % r["arr"]
                body += "}"
                h = hashlib.sha256((body + "\n").encode()).hexdigest()
                hs.append(h)
                lines.append(body[:-1] + ',"content_sha256":"' + h + '"}')
        ok["value"] = {"n_lines": len(lines), "dump_sha256": hashlib.sha256("".join(l + "\n" for l in lines).encode()).hexdigest(),
                       "content_sha256_digest": hashlib.sha256("\n".join(hs).encode()).hexdigest()}
        return ok
    as_of = q["as_of"]
    if as_of not in minutes:
        return bad("session_not_in_calendar")
    if MU("conv_before_threshold") and "delta_convention" in q:
        if any(r["conv"] != q["delta_convention"] for r in rings.get((q["series_id"], q["metric"]), Ring(0)).recs):
            return bad("convention_mismatch")
    mins, maxs = q.get("min_sessions", 20), q.get("max_sessions", 252)
    if q["q"] == "same_minute_column":
        m = q["minute"]
        if not isint(m):
            return bad("malformed_type")
        if not 0 <= m < minutes[as_of]:
            return bad("minute_out_of_range")
    for v in (mins, maxs):
        if not isint(v) or (v < 1 and not (MU("min_sessions_zero_ok") and v == 0)):
            return bad("malformed_type")
    if "x" in q or "X" in q:
        xq = parse_X(q["x"] if "x" in q else q["X"])
        if xq is None:
            return bad("malformed_type")
        if (xq < 0 or xq > 100) and not MU("store_x_unchecked"):
            return bad("threshold_out_of_range")
    if "delta_convention" in q and not MU("conv_unchecked_at_read") and not MU("conv_before_threshold"):
        if any(r["conv"] != q["delta_convention"] for r in rings.get((q["series_id"], q["metric"]), Ring(0)).recs):
            return bad("convention_mismatch")
    ring = rings.get((q["series_id"], q["metric"]), Ring(0))
    ss, vv = [], []
    for r in ring.recs:
        before = r["sid"] <= as_of if MU("as_of_inclusive") else r["sid"] < as_of
        if not r["done"] or not before or (r["lane"] != q.get("lane", "stock") and not MU("lane_ignored")):
            continue
        if q["q"] == "scalar_baseline":
            ss.append(r["sid"])
            vv.append(r["pay"])
        else:
            g = gs_vals(r["pay"])
            j = q["minute"] + 1 if MU("minute_off_by_one") else q["minute"]
            if j < len(g):
                ss.append(r["sid"])
                vv.append(g[j])
    if not MU("cap_ignored"):
        ss, vv = ss[-maxs:], vv[-maxs:]
    if len(vv) < mins:
        return {"status": "unavailable", "code": None, "reason": "insufficient_history", "value": {"n": len(vv), "sessions": None, "values": None}}
    return {"status": "available", "code": None, "reason": None, "value": {"n": len(vv), "sessions": ss, "values": vv}}


def memory(row):
    p = row["inputs"]
    if p["kind"] == "grid_bytes":
        width = 4 if MU("mem_4_bytes") else 8
        raw = p["names"] * p["k"] * p["grid"] * width
        copies = 2 if (MU("mem_copies_2") and p["copies"] == 3) else p["copies"]
        tot = raw * copies
        return {"status": "available", "reason": None, "code": None,
                "value": {"raw_bytes": raw, "total_bytes": tot, "within_768MiB": tot <= 768 * 1024 * 1024}}
    recs = p["names"] * p["series"] * p["k"]
    return {"status": "available", "reason": None, "code": None, "value": {"records": recs, "scalar_bytes": recs * 8}}


def units(row):
    p = row["inputs"]
    ok = {"status": "available", "reason": None, "code": None}
    if p["kernel"] == "skew_points":
        u = to_units(p["put25_iv"] - p["call25_iv"])
        mult = 1000 if MU("points_x1000") else 100
        with localcontext() as ctx:
            ctx.prec = 80
            pts = to_units(Decimal(p["put25_iv"] - p["call25_iv"]) * mult)  # R-181: x100 at full precision, round once
        ok["value"] = {"skew25_units": u, "skew_points": fmt(pts)}
    else:
        u = to_units(p["float"])
        ok["value"] = {"units": u, "text": fmt(u)}
    return ok


def evaluate(row, cals, mut=None):
    global _MU
    _MU = mut
    try:
        if row["family"] == "history_reuse":
            return memory(row) if "kind" in row["inputs"] else store(row, cals)
        if "kernel" in row["inputs"]:
            return units(row)
        return pct(row, cals)
    finally:
        _MU = None
