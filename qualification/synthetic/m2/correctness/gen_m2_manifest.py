"""Writes MANIFEST.json: seed, row counts per file and output id, frozen facts, sha256 of every dataset file.
Usage: python gen_m2_manifest.py [datadir]  (default: this directory; no absolute paths are written)"""
import hashlib
import json
import os
import sys

FILES = ["F1", "F2", "F4", "F7", "F10F20", "F17", "F18F19", "F12", "lane", "structural", "delayed", "sessionopen",
         "halfday", "store"]


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    files, per_out, total, seed = {}, {}, 0, None
    for name in FILES:
        fn = "m2_cases_%s.json" % name
        raw = open(os.path.join(d, fn), "rb").read()
        lines = raw.decode("ascii").split("\n")
        head = json.loads(lines[0])
        seed = head["seed"]
        rows = [json.loads(l) for l in lines[1:-1]]
        files[fn] = {"rows": len(rows), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        total += len(rows)
        for r in rows:
            per_out[r["output_id"]] = per_out.get(r["output_id"], 0) + 1
    man = {"provenance": "SYNTHETIC",
           "label": "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12",
           "seed": seed, "total_rows": total, "rows_per_output_id": per_out, "files": files,
           "frozen_facts": {"t_ns_anchor": head["t_ns_anchor"], "grid_step_s": 60, "history_sessions_k": 20,
                            "allowed_windows_s": [60, 300, 900, 1800, 3600], "f1_horizons_s": [60, 900],
                            "full_session_minutes": 390, "half_day_minutes": 210, "short_grid_minutes": [2, 3, 4, 20, 40, 60, 70],
                            "premium_unit": "integer ticks (price x 10^4 x size x multiplier)", "threshold_ticks_default": 1000000000,
                            "grid_point_time": "open + 60 s x i, i = 0..minutes-1",
                            "side_vocabulary": ["ask", "bid", "unknown"]},
           "differential": {"cases_per_kind": 20000, "kinds": ["rank", "median_ratio", "episodes"],
                            "manifest": "m2_diff_manifest.json"}}
    with open(os.path.join(d, "MANIFEST.json"), "wb") as f:
        f.write((json.dumps(man, sort_keys=True, indent=1) + "\n").encode("ascii"))
    print(total)


if __name__ == "__main__":
    main()
