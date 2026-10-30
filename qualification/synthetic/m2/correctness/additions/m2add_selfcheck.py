"""Self-check for the additions: recomputes every row with the independent model m2add_ref (B') and checks coverage
requirements by tag. Usage: python m2add_selfcheck.py [datadir]"""
import glob
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import m2_load  # noqa: E402
import m2add_ref  # noqa: E402

LABEL = ("mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, "
         "Windows x64, CPython 3.12")
_P = [("real", "-data"), ("market", " data"), ("produc", "tion"), ("validated against", " vendor"), ("data", "bento"),
      ("linux", " parity"), ("byte", "-identical")]
FORBIDDEN = [a + b for a, b in _P]
EXPECT = {"add_struct": 60, "add_data": 30, "add_grid": 23, "add_store": 24, "add_snapshot": 14, "add_params": 16}
CODES = {None, "unordered_prints", "negative_size_or_price", "bad_multiplier", "unknown_contract", "malformed_type",
         "duplicate_session", "non_monotone_grid", "session_not_in_calendar", "window_not_allowed", "threshold_required",
         "out_of_order_append", "delayed_feed_tag", "lane_mismatch", "record_length_mismatch", "snapshot_bad_magic", "snapshot_length_mismatch", "snapshot_hash_mismatch", "trailer_missing", "trailer_count_mismatch", "trailer_hash_mismatch", "grid_not_60s"}
ABS_PATH = re.compile(r"[A-Za-z]:" + chr(92) + chr(92) + "|/Users/|/home/")


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def run(d):
    rows, counts, bad = [], {}, []
    for path in sorted(glob.glob(os.path.join(d, "m2_cases_add_*.json"))):
        name = os.path.basename(path)[len("m2_cases_"):-5]
        head, rs = m2_load.load_dataset(path)
        assert head["provenance"] == "SYNTHETIC" and head["label"] == LABEL
        low = open(path, encoding="ascii").read().lower()
        for t in FORBIDDEN:
            assert t not in low, (t, path)
        assert not ABS_PATH.search(low)
        counts[name] = len(rs)
        for r in rs:
            assert r["expected"]["code"] in CODES, r["id"]
            if canon(m2add_ref.evaluate(r)) != canon(r["expected"]):
                bad.append(r["id"])
        rows += rs
    return rows, counts, bad


def need(cond, msg):
    assert cond, msg


def coverage(rows):
    t = Counter()
    for r in rows:
        for g in r["tags"]:
            t[(g, r["output_id"])] += 1
            t[g] += 1
    for o in ("M2-1", "M2-4", "M2-6", "M2-5", "M2-9"):
        need(t[("unknown_contract", o)] >= 2 and t[("malformed_type", o)] >= 2, "codes per output " + o)
    for g in ("float_price", "bool_price", "delayed_feed_tag", "trailing_zero_price", "float_window", "premium_gt_2_53", "fractional_N"):
        need(t[g] >= 2, g)
    for pair in (("unordered_prints", "negative_size_or_price"), ("negative_size_or_price", "bad_multiplier"),
                 ("bad_multiplier", "unknown_contract"), ("unknown_contract", "malformed_type"),
                 ("malformed_type", "window_not_allowed")):
        need(sum(1 for r in rows if "prec_pair" in r["tags"] and pair[0] in r["tags"] and pair[1] in r["tags"]) >= 2, str(pair))
    for o in ("M2-4", "M2-6", "M2-5", "M2-9"):
        need(t[("preopen_clip", o)] >= 2, "preopen " + o)
    need(t["f12_from_prints"] >= 8 and t["coverage_from_prints"] >= 2, "f12 from prints")
    need(t[("fractional_N", "M2-1")] >= 2 and t[("fractional_N", "M2-4")] >= 2, "fractional N")
    need(t["grid_builder"] >= 12, "grid rows")
    for g in ("int_tick_price", "dot_five", "flag_int", "bool_seq", "close_boundary"):
        need(t[g] >= 2, g)
    need(t["grammar_text"] - t["dot_five"] - t["dot_trailing"] >= 4, "grammar rows")
    for g in ("int_tick_twin", "dot_trailing", "ratio_reason_absent", "valid_from_beyond", "lane_mismatch", "record_length_mismatch"):
        need(t[g] >= 2, g)
    need(t["result_version"] >= 1 and t["ratio_reason_present"] >= 1, "version / ratio_reason")
    codes = Counter(r["expected"]["code"] for r in rows)
    for c in ("snapshot_bad_magic", "snapshot_length_mismatch", "snapshot_hash_mismatch", "trailer_missing", "trailer_count_mismatch",
              "trailer_hash_mismatch", "grid_not_60s", "lane_mismatch", "record_length_mismatch"):
        need(codes[c] >= 2, c)
    for g in ("param_N", "param_threshold", "param_share", "param_quiet_gap", "param_n_episodes", "param_below_one", "prec_pair_store", "ring_lane_first", "sparse_hash"):
        need(t[g] >= 2, g)
    need(t["prec_pair_store"] >= 12, "store precedence pairs")


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else HERE
    rows, counts, bad = run(d)
    coverage(rows)
    print("rows", len(rows), counts, "mismatches", len(bad), bad[:5])
    ok = not bad and all(EXPECT.get(k) == v for k, v in counts.items()) and len(rows) == 167
    print("ADD_SELFCHECK", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
