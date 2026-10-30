"""Self-check: recomputes every expected value with the independent reference model (m2_ref, exact Fractions) from the
raw inputs, plus structural checks of the datasets. Usage: python m2_selfcheck.py [datadir]  (default: this directory)."""
import glob
import hashlib
import json
import os
import re
import sys

import m2_load
import m2_ref

LABEL = ("mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, "
         "Windows x64, CPython 3.12")
REASONS = {None, "insufficient_history", "session_not_complete", "insufficient_window", "zero_denominator"}
CODES = {None, "unordered_prints", "negative_size_or_price", "bad_multiplier", "duplicate_session", "non_monotone_grid",
         "session_not_in_calendar", "window_not_allowed", "delayed_feed_tag", "out_of_order_append", "threshold_required"}
_PIECES = [("real", "-data"), ("market", " data"), ("produc", "tion"), ("validated against", " vendor"), ("data", "bento"),
           ("linux", " parity"), ("byte", "-identical")]
FORBIDDEN = [a + b for a, b in _PIECES]
LISTED = {"M2-1": {"insufficient_window", "zero_denominator"}, "M2-2": {"insufficient_history", "session_not_complete", "insufficient_window"},
          "M2-3": {"insufficient_history", "insufficient_window"}, "M2-4": set(), "M2-5": set(), "M2-6": {"zero_denominator"},
          "M2-7": {"insufficient_history", "zero_denominator", "insufficient_window"},
          "M2-8": {"session_not_complete", "insufficient_history", "zero_denominator"}, "M2-9": {"zero_denominator"},
          "M2-10": {"session_not_complete", "insufficient_history", "zero_denominator"}, "M2-11": {"insufficient_window"},
          "M2-12": set()}
EXPECT_COUNTS = {"F1": 44, "F2": 105, "F4": 34, "F7": 38, "F10F20": 80, "F17": 32, "F18F19": 66, "F12": 54,
                 "lane": 8, "structural": 31, "delayed": 9, "sessionopen": 12, "halfday": 10, "store": 47}


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def expand_hash(sessions):
    h = hashlib.sha256()
    for s in sessions:
        g = [s["gs"]["base"]] * s["minutes"]
        for i, v in s["gs"]["over"]:
            g[i] = v
        h.update((s["session_id"] + ":" + ",".join(str(v) for v in g) + "\n").encode())
    return h.hexdigest()


def load(path):
    return m2_load.load_dataset(path)


def check_dir(d):
    bad, total = [], 0
    counts, reasons_seen = {}, {}
    by_out, gate_rows = {}, 0
    for path in sorted(glob.glob(os.path.join(d, "m2_cases_*.json"))):
        name = os.path.basename(path)[len("m2_cases_"):-5]
        head, rows = load(path)
        assert head["provenance"] == "SYNTHETIC" and head["label"] == LABEL, path
        assert head["row_count"] == len(rows), path
        counts[name] = len(rows)
        low = open(path, encoding="ascii").read().lower()
        for t in FORBIDDEN:
            assert t not in low, "forbidden term %r in %s" % (t, path)
        assert not re.search(r"[A-Za-z]:\|/Users/|/home/", low), "absolute path in " + path
        for r in rows:
            total += 1
            e = r["expected"]
            assert e["reason"] in REASONS, (r["id"], e["reason"])
            assert e["code"] in CODES, (r["id"], e["code"])
            assert e["status"] in ("available", "unavailable", "invalid_input"), r["id"]
            if e["status"] != "available":
                assert e["value"] is None and e["fired"] is None, r["id"]
            for h in ([] if e["code"] == "non_monotone_grid" else [r["inputs"].get("history")] + [p["history"] for p in (r["inputs"].get("parts") or {}).values()]):
                if h:
                    assert h["expansion_sha256"] == expand_hash(h["sessions"]), r["id"]
            by_out.setdefault(r["output_id"], {})
            by_out[r["output_id"]][e["reason"]] = by_out[r["output_id"]].get(e["reason"], 0) + 1
            gate_rows += "gate_order" in r["tags"]
            got = m2_ref.evaluate(r)
            if canon(got) != canon(e):
                bad.append((r["id"], got, e))
            reasons_seen.setdefault(r["family"], {}).setdefault(e["reason"], 0)
            reasons_seen[r["family"]][e["reason"]] += 1
    for o, seen in by_out.items():
        for rsn, n in seen.items():
            if rsn is not None:
                assert rsn in LISTED[o], "reason %s appears for %s where the matrix does not list it" % (rsn, o)
        for rsn in LISTED[o]:
            if o != "M2-3":
                assert seen.get(rsn, 0) >= 3, "reason %s has %d rows for %s" % (rsn, seen.get(rsn, 0), o)
    assert gate_rows >= 8, gate_rows
    print("reasons by output:", {o: {str(k): v for k, v in s.items()} for o, s in sorted(by_out.items())}, "gate_order rows", gate_rows)
    return total, counts, bad, reasons_seen


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    total, counts, bad, rs = check_dir(d)
    print("rows", total, "families", counts)
    for fam in sorted(rs):
        print(" ", fam, {str(k): v for k, v in sorted(rs[fam].items(), key=lambda z: str(z[0]))})
    for b in bad[:10]:
        print("MISMATCH", b[0], "\n  got     ", canon(b[1])[:600], "\n  expected", canon(b[2])[:600])
    print("mismatches", len(bad))
    ok = (not bad) and all(EXPECT_COUNTS.get(k) == v for k, v in counts.items()) and total >= 558
    print("SELFCHECK", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
