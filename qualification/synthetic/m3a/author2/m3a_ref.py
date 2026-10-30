"""Oracle 1 (integer arithmetic) for the author-2 families V1, V3, V9, history reuse, units. Used by the generators.
Written from the ruled text only. evaluate(row, cals) returns the expected dict (only asserted keys).
reading selects the D3 reading of max_sessions: avail (last N available sessions) or cal (calendar window of N)."""
import json
import re
from fractions import Fraction

from m3a_common import EXACT, decode, expand_gs, r8, sha, show, text8

OUT = {"M3A-1": "iv30_close", "M3A-8": "skew25", "M3A-2": "iv30"}
ORDER = ("upstream", "insufficient", "complete", "zero_range")


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def parse_X(v):
    """Fraction, or None for a wrong type. M2 convention: int, Fraction or a/b text."""
    if _int(v):
        return Fraction(v)
    if isinstance(v, Fraction):
        return v
    if isinstance(v, str) and re.fullmatch(r"-?\d+/\d+", v) and int(v.split("/")[1]) != 0:
        return Fraction(v)
    return None


def req_series(row):
    """R-153: for V3 the result series_id is the REQUESTED form's series (atm default), even when the supplied history is the other series."""
    I = row["inputs"]
    sid = I["series"]["series_id"]
    if row["output_id"] == "M3A-2":
        want = {"atm": "atm_iv", "30d": "iv30"}.get(row["params"].get("iv_form", "atm"))
        if isinstance(want, str) and I["series"]["metric"] != want:
            return sid.rsplit("/", 1)[0] + "/" + want
    return sid


def head(row):
    I = row["inputs"]
    return {"output_id": row["output_id"], "series_id": req_series(row), "session_id": I["session"]["session_id"],
            "evaluation_ns": I["evaluation_ns"], "lane": I["lane"]}


def invalid(row, code):
    d = head(row)
    d.update(status="invalid_input", reason=None, code=code, value=None, fired=None)
    return d


def unavailable(row, reason):
    d = head(row)
    d.update(status="unavailable", reason=reason, code=None, value=None, fired=None)
    return d


def usable(row, cals, reading):
    """Usable history values, oldest first: ring retention, complete, strictly before, minute present, cap."""
    I, P = row["inputs"], row["params"]
    ids = [c[0] for c in cals[I["calendar_ref"]]]
    cur = ids.index(I["session"]["session_id"])
    recs = I["records"][-I.get("store_k", 252):]
    maxs = P.get("max_sessions", 252)
    minute = P.get("minute")
    metric = OUT[row["output_id"]]
    lo = cur - maxs if reading == "cal" else -10 ** 9
    items = []
    for r in recs:
        if r[0] >= cur or r[0] < lo or not r[-1]:
            continue
        if metric == "iv30":
            g = expand_gs(r[1])
            if minute >= len(g):
                continue
            items.append(g[minute])
        else:
            items.append(r[1])
    if reading == "avail":
        items = items[-maxs:]
    return items


def evaluate(row, cals, reading="avail", order=ORDER):
    I, P = row["inputs"], decode(row["params"])
    oid = row["output_id"]
    cal = cals[I["calendar_ref"]]
    ids = [c[0] for c in cal]
    mode = P.get("mode", "intraday")
    if mode not in ("intraday", "close"):
        return invalid(row, "invalid_mode")
    if I["lane"] not in ("stock", "etf_index"):
        return invalid(row, "invalid_lane")
    mins = P.get("min_sessions", 20)
    maxs = P.get("max_sessions", 252)
    for v in (mins, maxs):
        if not _int(v) or v < 1:
            return invalid(row, "malformed_type")
    form = None
    if oid == "M3A-2":
        form = P.get("iv_form", "atm")
        if not isinstance(form, str):
            return invalid(row, "malformed_type")
        if form not in ("atm", "30d"):
            return invalid(row, "iv_form_not_allowed")
    conv = None
    if oid == "M3A-8":
        conv = P.get("delta_convention", "spot")
        if not isinstance(conv, str):
            return invalid(row, "malformed_type")
        if conv not in ("spot", "forward"):
            return invalid(row, "convention_not_allowed")
    X = parse_X(P.get("x", P.get("X", 5)))
    if X is None:
        return invalid(row, "malformed_type")
    if X < 0 or X > 100:
        return invalid(row, "threshold_out_of_range")
    sid = I["session"]["session_id"]
    cur = ids.index(sid) if sid in ids else None
    if oid == "M3A-2":
        m = P.get("minute")
        if not _int(m):
            return invalid(row, "malformed_type")
        if cur is not None and not (0 <= m < cal[cur][1]):
            return invalid(row, "minute_out_of_range")
    if oid == "M3A-8":
        stored = I.get("records_convention", "forward" if I["series"]["metric"] == "skew25_fwd" else "spot")
        if stored != conv:
            return invalid(row, "convention_mismatch")
    delayed = I["session"]["feed_delay_tag"] == "delayed"
    if delayed and (mode == "intraday" or oid == "M3A-2"):
        return invalid(row, "delayed_feed_tag")
    if cur is None:
        return invalid(row, "session_not_in_calendar")
    now = I["now"]
    up = now.get("unavailable")
    units = None
    if up is None:
        units = r8(now["put25_iv"] - now["call25_iv"]) if oid == "M3A-8" else r8(now["float"])
    want = {"atm": "atm_iv", "30d": "iv30"}.get(form)
    mixed = oid == "M3A-2" and I["series"]["metric"] != want
    hist = [] if (I["ring_lane"] != I["lane"] or mixed) else usable(row, cals, reading)
    n = len(hist)
    fails = []
    if up is not None:
        fails.append(("upstream", up))
    if n < mins:
        fails.append(("insufficient", "insufficient_history"))
    if mode == "close" and not I["session"]["complete"]:
        fails.append(("complete", "session_not_complete"))
    if n >= 1 and min(hist) == max(hist):
        fails.append(("zero_range", "zero_range_history"))
    fails.sort(key=lambda f: order.index(f[0]))
    if fails:
        r = unavailable(row, fails[0][1])
        r["_all_reasons"] = [f[1] for f in fails]
        return r
    ge = sum(1 for h in hist if h >= units)
    le = sum(1 for h in hist if h <= units)
    ush, lsh = Fraction(ge, n), Fraction(le, n)
    tail = P.get("tail", "top")
    val = {"x": text8(units), "n": n}
    echo = {"x": show(X), "min_sessions": mins, "max_sessions": maxs}
    if oid == "M3A-2":
        val.update(minute=P["minute"], rank_le=le, upper_share=show(ush))
        fired = ush <= X / 100
        echo.update(minute=P["minute"], mode="intraday", iv_form=form)
    else:
        val.update(rank_le=le, upper_share=show(ush), lower_share=show(lsh),
                   form="intraday" if mode == "intraday" else "end_of_day")
        fired = (ush <= X / 100) if tail == "top" else (lsh <= X / 100)
        echo.update(mode=mode, tail=tail)
        if oid == "M3A-8":
            echo["delta_convention"] = conv
    d = head(row)
    labels = sorted([I.get("model_label", EXACT)] + (["delayed"] if delayed else []))
    d.update(status="available", reason=None, code=None, value=val, fired=bool(fired), params=echo, labels=labels)
    return d


# ------------------------------------------------------------------------------------------------ store
def canon_line(series, metric, win, sid, grid, total, complete):
    return '{"series_id":%s,"metric":%s,"session_id":%s,"window_s":%d,"grid":[%s],"total":%d,"complete":%s}' % (
        json.dumps(series), json.dumps(metric), json.dumps(sid), win, ",".join(str(g) for g in grid), total,
        "true" if complete else "false")


def _bad(code):
    return {"status": "invalid_input", "code": code, "reason": None, "value": None}


def store_eval(row, cals):
    I = row["inputs"]
    cal = cals[I["calendar_ref"]]
    ids = [c[0] for c in cal]
    mins_of = dict(cal)
    cfg = I["store_config"]
    ring, lane_of = {}, {}
    for op in I["ops"]:
        if op[0] == "seal":
            for rec in ring.get((op[1], op[2], 0), []):
                if rec["sid"] == ids[op[3]]:
                    rec["complete"] = True
            continue
        kind, series, metric, idx, payload, complete, lane = op[:7]
        key = (series, metric, 0)
        sid = ids[idx] if isinstance(idx, int) else idx
        if key in lane_of and lane_of[key] != lane:
            return _bad("lane_mismatch")
        if sid not in mins_of:
            return _bad("session_not_in_calendar")
        if kind == "g" and payload["len"] > mins_of[sid]:
            return _bad("record_length_mismatch")
        cur = ring.setdefault(key, [])
        if cur:
            li, ci = ids.index(cur[-1]["sid"]), ids.index(sid)
            if ci == li:
                return _bad("duplicate_session")
            if ci < li:
                return _bad("out_of_order_append")
        lane_of.setdefault(key, lane)
        k = cfg["k_by_key"].get("%s|%s|0" % (series, metric), cfg["k_default"])
        cur.append({"sid": sid, "kind": kind, "payload": payload, "complete": bool(complete), "lane": lane,
                    "conv": op[7] if len(op) > 7 else "spot"})
        while len(cur) > k:
            cur.pop(0)
    q = I["query"]
    ok = {"status": "available", "code": None, "reason": None}
    if q["q"] == "retained":
        ok["value"] = {"retained": {"%s|%s|%d" % kk: [r["sid"] for r in ring[kk]] for kk in sorted(ring)}}
        return ok
    if q["q"] == "hashes":
        lines, hs = [], []
        for kk in sorted(ring):
            for r in sorted(ring[kk], key=lambda r: r["sid"]):
                ln = canon_line(kk[0], kk[1], 0, r["sid"], [], r["payload"], r["complete"])
                h = sha(ln + "\n")
                hs.append(h)
                lines.append(ln[:-1] + ',"content_sha256":"%s"}' % h)
        ok["value"] = {"n_lines": len(lines), "dump_sha256": sha("".join(x + "\n" for x in lines)),
                       "content_sha256_digest": sha("\n".join(hs))}
        return ok
    key = (q["series_id"], q["metric"], 0)
    as_of = q["as_of"]
    if as_of not in mins_of:
        return _bad("session_not_in_calendar")
    mins, maxs = q.get("min_sessions", 20), q.get("max_sessions", 252)
    if q["q"] == "same_minute_column":
        m = q["minute"]
        if not _int(m):
            return _bad("malformed_type")
        if not (0 <= m < mins_of[as_of]):
            return _bad("minute_out_of_range")
    for v in (mins, maxs):
        if not _int(v) or v < 1:
            return _bad("malformed_type")
    if "x" in q or "X" in q:
        xq = parse_X(q["x"] if "x" in q else q["X"])
        if xq is None:
            return _bad("malformed_type")
        if xq < 0 or xq > 100:
            return _bad("threshold_out_of_range")
    if "delta_convention" in q:
        if any(r["conv"] != q["delta_convention"] for r in ring.get(key, [])):
            return _bad("convention_mismatch")
    recs = [r for r in ring.get(key, []) if r["complete"] and r["sid"] < as_of and r["lane"] == q.get("lane", "stock")]
    sess, vals = [], []
    for r in recs:
        if q["q"] == "scalar_baseline":
            sess.append(r["sid"])
            vals.append(r["payload"])
        else:
            g = expand_gs(r["payload"])
            if q["minute"] < len(g):
                sess.append(r["sid"])
                vals.append(g[q["minute"]])
    sess, vals = sess[-maxs:], vals[-maxs:]
    if len(vals) < mins:
        return {"status": "unavailable", "code": None, "reason": "insufficient_history",
                "value": {"n": len(vals), "sessions": None, "values": None}}
    return {"status": "available", "code": None, "reason": None, "value": {"n": len(vals), "sessions": sess, "values": vals}}


def mem_eval(row):
    p = row["inputs"]
    if p["kind"] == "grid_bytes":
        raw = p["names"] * p["k"] * p["grid"] * 8
        tot = raw * p["copies"]
        return {"status": "available", "reason": None, "code": None,
                "value": {"raw_bytes": raw, "total_bytes": tot, "within_768MiB": tot <= 768 * 2 ** 20}}
    b = p["names"] * p["series"] * p["k"]
    return {"status": "available", "reason": None, "code": None, "value": {"records": b, "scalar_bytes": b * 8}}


def units_eval(row):
    p = row["inputs"]
    ok = {"status": "available", "reason": None, "code": None}
    if p["kernel"] == "skew_points":
        d = p["put25_iv"] - p["call25_iv"]
        u = r8(d)
        ok["value"] = {"skew25_units": u, "skew_points": text8(r8(Fraction(d) * 100))}  # R-181: x100 at full precision, round once
    else:
        u = r8(p["float"])
        ok["value"] = {"units": u, "text": text8(u)}
    return ok
