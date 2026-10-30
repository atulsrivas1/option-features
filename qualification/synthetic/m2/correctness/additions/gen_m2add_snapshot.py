"""Additions: snapshot load rows (magic M2SNAP1 + 8-byte LE total length + SHA-256 of the body + body) and text dump rows
(canonical lines + trailer '#END records=N content_sha256=<hex>'); one defect per row (14 rows)."""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import m2add_oracle as A  # noqa: E402
import m2add_store_a as SA  # noqa: E402
from m2common import *  # noqa: E402,F401,F403
import m2common as C  # noqa: E402
from gen_m2_store import CAL  # noqa: E402

A.install()
SID = [c["session_id"] for c in CAL]


def source_ops():
    def rec(series, metric, i, grid, idx=None):
        r = {"series_id": series, "metric": metric, "window_s": 300, "session_id": SID[i], "grid": grid, "total": sum(grid), "complete": True}
        if idx is not None:
            r["grid_idx"] = idx
        return ["append", r]
    return [rec("SYN1", "premium", 0, [1, 2, 3]), rec("SYN1", "premium", 1, [4, 5]), rec("SYN1", "premium", 2, [6, 7], idx=[0, 2]),
            rec("SYN2", "contracts", 0, [9, 8, 7]), rec("SYN2", "contracts", 1, [3, 3, 3])]


def canonical_lines(ops):
    ring = {}
    for op in ops:
        r = op[1]
        ring.setdefault((r["series_id"], r["metric"], r["window_s"]), []).append(r)
    lines, hashes = [], []
    for key in sorted(ring):
        for x in sorted(ring[key], key=lambda z: z["session_id"]):
            ln = SA.line(key[0], key[1], key[2], x["session_id"], x["grid"], x.get("grid_idx"), x["total"], x["complete"])
            h = hashlib.sha256((ln + "\n").encode()).hexdigest()
            hashes.append(h)
            lines.append(ln[:-1] + ',"content_sha256":"' + h + '"}')
    return lines, hashlib.sha256("\n".join(hashes).encode()).hexdigest()


def snapshot(body, length=None, magic=b"M2SNAP1", digest=None):
    total = 7 + 8 + 32 + len(body) if length is None else length
    return magic + total.to_bytes(8, "little") + (hashlib.sha256(body).digest() if digest is None else digest) + body


def build(rng):
    R = Rows("addsnap", "M2A-SNAP")
    ops = source_ops()
    lines, digest = canonical_lines(ops)
    body = "".join(l + "\n" for l in lines).encode("ascii")
    good = snapshot(body)
    q = {"series_id": "SYN1", "metric": "premium", "window_s": 300, "as_of": SID[6]}

    def snap_row(raw, tags):
        R.add("M2-12", "PR 81 section 9.7 (snapshot)", "Q3", {"k": 20, "calendar": CAL, "snapshot_hex": raw.hex(), "query": q}, {"K": 20},
              tags=["additions", "snapshot"] + tags)

    def dump_row(text, tags):
        R.add("M2-12", "PR 81 section 9.7 (text dump)", "Q3", {"k": 20, "calendar": CAL, "dump_text": text, "query": q}, {"K": 20},
              tags=["additions", "text_dump"] + tags)

    snap_row(good, ["snapshot_control"])
    snap_row(b"X" + good[1:], ["snapshot_bad_magic", "structural"])
    snap_row(snapshot(body, magic=b"M2SNAP2"), ["snapshot_bad_magic", "structural"])
    snap_row(snapshot(body, length=len(good) + 1), ["snapshot_length_mismatch", "structural"])
    snap_row(good[:-1], ["snapshot_length_mismatch", "structural", "truncated"])
    flipped = bytearray(good)
    flipped[60] ^= 1
    snap_row(bytes(flipped), ["snapshot_hash_mismatch", "structural"])
    snap_row(snapshot(body, digest=bytes(32)), ["snapshot_hash_mismatch", "structural"])
    text = "".join(l + "\n" for l in lines)
    n = len(lines)
    trailer = "#END records=%d content_sha256=%s\n" % (n, digest)
    dump_row(text + trailer, ["dump_control"])
    dump_row(text, ["trailer_missing", "structural"])
    dump_row(text + "#BEGIN records=%d\n" % n, ["trailer_missing", "structural"])
    dump_row(text + "#END records=%d content_sha256=%s\n" % (n + 1, digest), ["trailer_count_mismatch", "structural"])
    dump_row(text + "#END records=%d content_sha256=%s\n" % (n - 1, digest), ["trailer_count_mismatch", "structural"])
    wrong = ("0" if digest[0] != "0" else "1") + digest[1:]
    dump_row(text + "#END records=%d content_sha256=%s\n" % (n, wrong), ["trailer_hash_mismatch", "structural"])
    dump_row(text + "#END records=%d content_sha256=%s\n" % (n, "0" * 64), ["trailer_hash_mismatch", "structural"])
    assert len(R.rows) == 14, len(R.rows)
    return R.rows


if __name__ == "__main__":
    C.main_for("add_snapshot", "addsnap", build)
