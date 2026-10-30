"""Loader for the compact dataset format (stdlib only): restores calendars, contracts, history sessions and store ops,
and verifies expansion_sha256 / ops_sha256. Independent of the generators."""
import hashlib
import json


def _cj(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def _hist(h, calids):
    h = dict(h)
    sess = []
    pay = h.pop("payloads")
    for sid, pi in h["sessions"]:
        if isinstance(sid, int):
            sid = calids[sid]
        minutes, comp, base, over, total, put, call = pay[pi]
        if total is None:
            g = [base] * minutes
            for i, v in over:
                g[i] = v
            total = sum(g)
        d = {"session_id": sid, "minutes": minutes, "complete": bool(comp), "gs": {"base": base, "over": over},
             "total": total}
        if put is not None:
            d["put"], d["call"] = put, call
        sess.append(d)
    h["sessions"] = sess
    return h


def expand_row(row, head):
    r = json.loads(_cj(row))
    i = r["inputs"]
    if "calendar_ref" in i:
        i["calendar"] = [{"session_id": s, "minutes": m} for s, m in head["calendars"][i.pop("calendar_ref")]]
    if "contracts_ref" in i:
        i["contracts"] = head["contracts"][i.pop("contracts_ref")]
    calids = [c["session_id"] for c in i.get("calendar", [])]
    if "history" in i:
        i["history"] = _hist(i["history"], calids)
    for p in (i.get("parts") or {}).values():
        p["history"] = _hist(p["history"], calids)
    if "ops" in i:
        ops = []
        for op in i["ops"]:
            if op[0] == "a":
                rec = {"series_id": op[1], "metric": op[2], "window_s": op[3], "session_id": op[4], "grid": op[5],
                       "total": sum(op[5]) if op[6] is None else op[6], "complete": bool(op[7])}
                if op[8] is not None:
                    rec["grid_idx"] = op[8]
                ops.append(["append", rec])
            else:
                ops.append(["seal"] + op[1:])
        i["ops"] = ops
        assert hashlib.sha256(_cj(ops).encode()).hexdigest() == i.pop("ops_sha256"), r["id"] + ": ops hash"
    return r


def load_dataset(path):
    raw = open(path, "rb").read()
    assert b"\r" not in raw, path + ": CR found"
    text = raw.decode("ascii")
    lines = text.split("\n")
    assert lines[-1] == "", path + ": missing final LF"
    head = json.loads(lines[0])
    rows = [expand_row(json.loads(l), head) for l in lines[1:-1]]
    return head, rows
