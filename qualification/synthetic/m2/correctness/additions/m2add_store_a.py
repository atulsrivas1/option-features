"""Oracle A' for the history store (additions): append validation in the ruled order, canonical lines (sparse records carry
grid_idx; the grid is kept as supplied, no padding), snapshot and text-dump load checks. Stdlib only."""
import hashlib
import json
import re

ORDER = ("lane_mismatch", "session_not_in_calendar", "record_length_mismatch", "non_monotone_grid",
         "duplicate_session", "out_of_order_append")


def line(series, metric, win, sid, grid, grid_idx, total, complete):
    parts = [("series_id", series), ("metric", metric), ("session_id", sid), ("window_s", win), ("grid", grid)]
    if grid_idx is not None:
        parts.append(("grid_idx", grid_idx))
    parts += [("total", total), ("complete", complete)]
    return json.dumps(dict(parts), separators=(",", ":"))


def append_code(ops, cal):
    ring_lane, last = {}, {}
    ids = list(cal)
    for op in ops:
        if op[0] != "append":
            continue
        r = op[1]
        key = (r["series_id"], r["metric"], r["window_s"])
        lane = r.get("lane", "stock")
        if key in ring_lane and ring_lane[key] != lane:
            return "lane_mismatch"
        if r["session_id"] not in cal:
            return "session_not_in_calendar"
        m = cal[r["session_id"]]
        gi = r.get("grid_idx")
        if (gi is None and len(r["grid"]) > m) or (gi is not None and any(i < 0 or i >= m for i in gi)):
            return "record_length_mismatch"
        if gi is not None and any(b <= a for a, b in zip(gi, gi[1:])):
            return "non_monotone_grid"
        if key in last:
            if ids.index(r["session_id"]) == ids.index(last[key]):
                return "duplicate_session"
            if ids.index(r["session_id"]) < ids.index(last[key]):
                return "out_of_order_append"
        ring_lane.setdefault(key, lane)
        last[key] = r["session_id"]
    return None


def build(ops, cal_list, k, query):
    ring = {}
    for op in ops:
        if op[0] == "append":
            r = dict(op[1])
            key = (r["series_id"], r["metric"], r["window_s"])
            lst = ring.setdefault(key, [])
            lst.append(r)
            if len(lst) > k:
                lst.pop(0)
        elif op[0] == "seal":
            for x in ring.get((op[1], op[2], op[3]), []):
                if x["session_id"] == op[4]:
                    x["complete"] = True
    out_lines, hashes, retained = [], [], {}
    for key in sorted(ring):
        ents = sorted(ring[key], key=lambda z: z["session_id"])
        retained["%s|%s|%s" % key] = [x["session_id"] for x in ents]
        for x in ents:
            ln = line(key[0], key[1], key[2], x["session_id"], x["grid"], x.get("grid_idx"), x["total"], x["complete"])
            h = hashlib.sha256((ln + "\n").encode()).hexdigest()
            hashes.append(h)
            out_lines.append(ln[:-1] + ',"content_sha256":"' + h + '"}')
    dump = hashlib.sha256("".join(l + "\n" for l in out_lines).encode()).hexdigest()
    view = None
    if query:
        ents = sorted(ring.get((query["series_id"], query["metric"], query["window_s"]), []), key=lambda z: z["session_id"])
        view = [x["session_id"] for x in ents if x["complete"] and x["session_id"] < query["as_of"]][-k:]
    return {"retained": retained, "view": view, "dump_sha256": dump, "n_lines": len(out_lines),
            "content_sha256_digest": hashlib.sha256("\n".join(hashes).encode()).hexdigest()}


def _from_lines(lines, inp):
    ops = []
    for ln in lines:
        r = json.loads(ln)
        r.pop("content_sha256", None)
        ops.append(["append", r])
    return build(ops, [c["session_id"] for c in inp["calendar"]], inp.get("k", 20), inp.get("query"))


def store(inp, prm, invalid, res):
    """returns (result, derivation); invalid(code) and res(**kw) are supplied by the caller (shape helpers)"""
    if "snapshot_hex" in inp:
        b = bytes.fromhex(inp["snapshot_hex"])
        if b[:7] != b"M2SNAP1":
            return invalid("snapshot_bad_magic")
        if int.from_bytes(b[7:15], "little") != len(b):
            return invalid("snapshot_length_mismatch")
        if hashlib.sha256(b[47:]).digest() != b[15:47]:
            return invalid("snapshot_hash_mismatch")
        return res(value=_from_lines([x for x in b[47:].decode("ascii").split("\n") if x], inp)), "snapshot loaded; checks magic, length, body hash passed"
    if "dump_text" in inp:
        rows = [x for x in inp["dump_text"].split("\n") if x]
        if not rows or not rows[-1].startswith("#END "):
            return invalid("trailer_missing")
        m = re.fullmatch(r"#END records=([0-9]+) content_sha256=([0-9a-f]+)", rows[-1])
        body = rows[:-1]
        if int(m.group(1)) != len(body):
            return invalid("trailer_count_mismatch")
        v = _from_lines(body, inp)
        if v["content_sha256_digest"] != m.group(2):
            return invalid("trailer_hash_mismatch")
        return res(value=v), "text dump loaded; trailer count and hash verified"
    ops = inp.get("store_ops", inp.get("ops"))
    cal = {c["session_id"]: c["minutes"] for c in inp["calendar"]}
    code = append_code(ops, cal)
    if code:
        return invalid(code)
    v = build(ops, [c["session_id"] for c in inp["calendar"]], inp.get("k", 20), inp.get("query"))
    return res(value=v), "ring keeps the last K sessions per (series, metric, window); lines carry grid_idx for sparse records; hashes include LF"
