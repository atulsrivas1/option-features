"""Test adapter for M2 story B (print-window families): maps the independently authored M2 rows
(qualification/synthetic/m2/correctness, never edited) onto the library API and reshapes the answer into the
row `expected` vocabulary. Rows covered: F1 (M2-1), F4 (M2-4), F17 (M2-5), F7 (M2-6), F18 (M2-9) and F12
(M2-11), plus the lane, structural, delayed-feed and session-open rows that touch those outputs.

Label: synthetic workload, relative engineering budget (no claim about recorded data). Synthetic fixtures only.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORRECTNESS = ROOT / "qualification" / "synthetic" / "m2" / "correctness"
if str(CORRECTNESS) not in sys.path:
    sys.path.insert(0, str(CORRECTNESS))

import m2_load  # noqa: E402  (independent loader shipped with the fixtures)

MINE = ("M2-1", "M2-4", "M2-5", "M2-6", "M2-9", "M2-11")
FILES = ("F1", "F4", "F17", "F7", "F18F19", "F12", "lane", "structural", "delayed", "sessionopen")
EXPECTED_ROWS = {"F1": 44, "F4": 34, "F17": 32, "F7": 38, "F18F19": 33, "F12": 54, "lane": 5, "structural": 18,
                 "delayed": 4, "sessionopen": 6}


def load_rows():
    rows = []
    for f in FILES:
        _, rs = m2_load.load_dataset(str(CORRECTNESS / ("m2_cases_%s.json" % f)))
        rows.extend((f, r) for r in rs if r["output_id"] in MINE)
    return rows


def _prints(inp):
    t = inp["t_ns"]
    out = []
    for p in inp.get("prints") or []:
        out.append((p[0], t + p[1]) + tuple(p[2:]))
    return out


def _contracts(inp):
    return {cid: (c["right"], c["strike"], c["expiry"], c["lane"]) for cid, c in (inp.get("contracts") or {}).items()}


def _common(inp, prm):
    s = inp["session"]
    cal = inp.get("calendar")
    return dict(lane=prm.get("lane", "stock"), delayed=s["feed_delay_tag"] == "delayed",
                series_id=inp["series_id"], session_id=s.get("session_id"),
                session_in_calendar=True if cal is None else any(c["session_id"] == s["session_id"] for c in cal))


def run_row(row):
    """Library answer for one row, reshaped into the row's `expected` vocabulary."""
    from option_features import episodes as E, m2prints as M, printtape as PT
    inp, prm, out = row["inputs"], row["params"], row["output_id"]
    common = _common(inp, prm)
    T = inp["t_ns"]
    if out == "M2-11":
        pts = inp["points"]
        p60 = [None if p is None else p[0] for p in pts]
        p900 = [None if p is None else p[1] for p in pts]
        res = E.f12_episodes(p60, p900, T, inp["session"]["open_ns"], n=prm.get("N", 3),
                             n_episodes=prm.get("n_episodes", 1), quiet_gap=prm.get("quiet_gap", 1), **common)
        return shape(res)
    tape = PT.build_tape(_prints(inp), _contracts(inp))
    if out == "M2-1":
        res = M.f1_premium_surge(tape, T, inp["session"]["open_ns"], n=prm.get("N", 3), flt=prm.get("filter", "all"),
                                 **common)
    elif out == "M2-4":
        res = M.f4_large_prints(tape, T, window_s=prm.get("window_s", 300),
                                threshold_ticks=prm.get("threshold_ticks", 10 ** 9), n=prm.get("N", 1), **common)
    elif out == "M2-5":
        common.pop("series_id")
        res = M.f17_window_premium(tape, T, inp["series_id"], window_s=prm.get("window_s", 300),
                                   threshold_ticks=prm.get("threshold_ticks", 10 ** 9), **common)
    elif out == "M2-6":
        res = M.f7_concentration(tape, T, window_s=prm.get("window_s", 300),
                                 share_threshold=prm.get("share_threshold", "3/5"), **common)
    else:
        res = M.f18_put_share(tape, T, window_s=prm.get("window_s", 300), at_least=prm.get("at_least"),
                              at_most=prm.get("at_most"), **common)
    return shape(res)


def shape(res):
    from option_features.m2prints import to_wire
    w = to_wire(res)
    e = {k: w[k] for k in ("status", "reason", "code", "value", "fired", "label", "coverage")}
    if w.get("ratio_reason"):
        e["ratio_reason"] = w["ratio_reason"]
    return e


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"))
