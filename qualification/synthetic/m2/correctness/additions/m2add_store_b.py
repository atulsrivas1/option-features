"""Independent second implementation B' of the history store for the additions (different structure from m2add_store_a):
ordered check functions, per-key state objects, string-built canonical lines. Stdlib only. MU(name) is supplied by the caller."""
import hashlib
import json
import re


def canon(series, metric, win, sid, grid, gidx, total, complete):
    s = '{"series_id":%s,"metric":%s,"session_id":%s,"window_s":%s,"grid":[%s]' % (
        json.dumps(series), json.dumps(metric), json.dumps(sid), json.dumps(win), ",".join(str(g) for g in grid))
    if gidx is not None:
        s += ',"grid_idx":[%s]' % ",".join(str(g) for g in gidx)
    return s + ',"total":%d,"complete":%s}' % (total, "true" if complete else "false")


def checks(MU):
    def lane(st, r, key, cal):
        if key in st["lane"] and st["lane"][key] != r.get("lane", "stock") and not MU("store_lane_ignored"):
            return "lane_mismatch"

    def calendar(st, r, key, cal):
        if r["session_id"] not in cal:
            return "session_not_in_calendar"

    def length(st, r, key, cal):
        m = cal.get(r["session_id"], 0)
        gi = r.get("grid_idx")
        if gi is None:
            if len(r["grid"]) > m and not MU("store_length_ignored"):
                return "record_length_mismatch"
        elif not all(0 <= i < m for i in gi) and not MU("store_sparse_range_ignored"):
            return "record_length_mismatch"

    def mono(st, r, key, cal):
        gi = r.get("grid_idx")
        if gi is not None and any(gi[i + 1] <= gi[i] for i in range(len(gi) - 1)):
            return "non_monotone_grid"

    def dup(st, r, key, cal):
        if key in st["last"] and st["last"][key] == r["session_id"]:
            return "duplicate_session"

    def order(st, r, key, cal):
        if key in st["last"]:
            ids = list(cal)
            if ids.index(r["session_id"]) < ids.index(st["last"][key]):
                return "out_of_order_append"
    seq = [lane, calendar, length, mono, dup, order]
    if MU("prec_calendar_first"):
        seq = [calendar, lane, length, mono, dup, order]
    if MU("prec_length_after_mono"):
        seq = [lane, calendar, mono, length, dup, order]
    if MU("prec_dup_before_mono"):
        seq = [lane, calendar, length, dup, mono, order]
    if MU("prec_order_before_dup"):
        seq = [lane, calendar, length, mono, order, dup]
    return seq


def state(ops, cal_ids, k, query, MU):
    ring = {}
    for op in ops:
        if op[0] == "append":
            r = dict(op[1])
            key = (r["series_id"], r["metric"], r["window_s"])
            ring.setdefault(key, []).append(r)
            keep = k + 1 if MU("store_k_plus_1") else k
            while len(ring[key]) > keep:
                ring[key].pop(0)
        else:
            for x in ring.get((op[1], op[2], op[3]), []):
                if x["session_id"] == op[4]:
                    x["complete"] = True
    lines, hashes, retained = [], [], {}
    for key in sorted(ring):
        ents = sorted(ring[key], key=lambda z: z["session_id"])
        retained["|".join(str(p) for p in key)] = [e["session_id"] for e in ents]
        for e in ents:
            gi = None if MU("store_grid_idx_dropped") else e.get("grid_idx")
            ln = canon(key[0], key[1], key[2], e["session_id"], e["grid"], gi, e["total"], e["complete"])
            h = hashlib.sha256((ln + ("" if MU("store_hash_no_lf") else "\n")).encode()).hexdigest()
            hashes.append(h)
            lines.append(ln[:-1] + ',"content_sha256":"' + h + '"}')
    view = None
    if query:
        ents = sorted(ring.get((query["series_id"], query["metric"], query["window_s"]), []), key=lambda z: z["session_id"])
        view = [e["session_id"] for e in ents if e["complete"] and e["session_id"] < query["as_of"]][-k:]
    return {"retained": retained, "view": view,
            "dump_sha256": hashlib.sha256("".join(x + "\n" for x in lines).encode()).hexdigest(), "n_lines": len(lines),
            "content_sha256_digest": hashlib.sha256("\n".join(hashes).encode()).hexdigest()}


def rebuild(text_lines, inp, MU):
    ops = []
    for ln in text_lines:
        r = json.loads(ln)
        r.pop("content_sha256", None)
        ops.append(["append", r])
    return state(ops, [c["session_id"] for c in inp["calendar"]], inp.get("k", 20), inp.get("query"), MU)


def run(inp, MU, invalid, ok):
    if "snapshot_hex" in inp:
        raw = bytes.fromhex(inp["snapshot_hex"])
        magic, declared, digest, body = raw[0:7], int.from_bytes(raw[7:15], "little"), raw[15:47], raw[47:]
        if magic != b"M2SNAP1" and not MU("snap_magic_ignored"):
            return invalid("snapshot_bad_magic")
        if declared != len(raw) and not MU("snap_length_ignored"):
            return invalid("snapshot_length_mismatch")
        if hashlib.sha256(body).digest() != digest and not MU("snap_hash_ignored"):
            return invalid("snapshot_hash_mismatch")
        return ok(rebuild([x for x in body.decode("ascii").split("\n") if x], inp, MU))
    if "dump_text" in inp:
        rows = [x for x in inp["dump_text"].split("\n") if x]
        if (not rows or not rows[-1].startswith("#END ")) and not MU("trailer_ignored"):
            return invalid("trailer_missing")
        mt = re.fullmatch(r"#END records=([0-9]+) content_sha256=([0-9a-f]+)", rows[-1])
        body = rows[:-1]
        if int(mt.group(1)) != len(body) and not MU("trailer_count_ignored"):
            return invalid("trailer_count_mismatch")
        v = rebuild(body, inp, MU)
        if v["content_sha256_digest"] != mt.group(2) and not MU("trailer_hash_ignored"):
            return invalid("trailer_hash_mismatch")
        return ok(v)
    ops = inp.get("store_ops", inp.get("ops"))
    cal = {c["session_id"]: c["minutes"] for c in inp["calendar"]}
    st = {"lane": {}, "last": {}}
    seq = checks(MU)
    for op in ops:
        if op[0] != "append":
            continue
        r = op[1]
        key = (r["series_id"], r["metric"], r["window_s"])
        for chk in seq:
            code = chk(st, r, key, cal)
            if code:
                return invalid(code)
        st["lane"].setdefault(key, r.get("lane", "stock"))
        st["last"][key] = r["session_id"]
    return ok(state(ops, [c["session_id"] for c in inp["calendar"]], inp.get("k", 20), inp.get("query"), MU))
