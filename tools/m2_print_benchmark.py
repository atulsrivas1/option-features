#!/usr/bin/env python3
"""M2 story B benchmark: print-window families against the M2 gate budgets (docs/m2/M2_GATE_BUDGETS.md).

Label: synthetic workload, relative engineering budget. Developer evidence only; the independent Tester runs the
gates. No claim about recorded data, live latency or vendor feeds.

Gates measured here (single worker, single thread, library only; inputs built before the timer; timer =
`time.perf_counter_ns` around the compute call only, the garbage collector is paused inside the timed call
and run before it; one warm-up and >= 30 timed repeats; nearest-rank percentiles; all samples kept):
  M2-B5  F1, F4, F17 each alone over the rate streams of 1e5 and 1e6 prints (build tape + one cutoff)
  M2-B6  F7 concentration over the same streams
  M2-B7  F18 volume aggregation over the same streams (F19 belongs to story A)
  M2-B8  F12 episode scan: 390 points per name (500 names) and 1e6 points in sessions of 390
  M2-B10 one shared pass (F1, F4, F17, F7, F18 and the F12 grid) over the streams, and the ratio to six
         separate passes (the F2/F10 inputs are story A's grid builder)
  M2-B15 cutoff sweep print pass: 78 cutoffs of one size-M unit on one tape against 78 single-cutoff passes
Correctness checks run first against the Tester's truth in qualification/synthetic/m2/perf (window truth of
unit SYN1/21, episode totals); a mismatch aborts the run.

Usage: python tools/m2_print_benchmark.py [--repeats 30] [--sizes 100000,1000000] [--json FILE] [--quick]
"""
import argparse
import gc
import hashlib
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "features" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "option-contracts" / "src"))
PERF = ROOT / "qualification" / "synthetic" / "m2" / "perf"
sys.path.insert(0, str(PERF))

LABEL = "synthetic workload, relative engineering budget"
QUAL = ("mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, "
        "Windows x64, CPython 3.12")
NS = 1_000_000_000
SEED = 20261029
GATES_DOC = ROOT / "docs" / "m2" / "M2_GATE_BUDGETS.md"


def budget_text(gate):
    """Budget and Hard cells of the gate row, verbatim from the budgets document."""
    for line in GATES_DOC.read_text(encoding="utf-8").splitlines():
        if line.startswith("| %s |" % gate):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            return {"workload": cells[1], "metric": cells[2], "budget": cells[3], "hard": cells[4]}
    raise KeyError(gate)


def machine():
    info = {"cpu": platform.processor(), "logical_cores": os.cpu_count(), "python": sys.version, "os": platform.platform()}

    def run(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception as exc:
            return "n/a (%s)" % type(exc).__name__
    if os.name == "nt":
        info["cpu_detail"] = run(["powershell", "-NoProfile", "-Command",
                                  "Get-CimInstance Win32_Processor | Select-Object -First 1 Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json -Compress"])
        info["ram_bytes"] = run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
        info["power_plan"] = run(["powercfg", "/getactivescheme"])
        info["load_percent_before"] = run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"])
    return info


def nearest(sorted_vals, q):
    return sorted_vals[max(0, math.ceil(q * len(sorted_vals)) - 1)]


def sample(fn, repeats, warmup=1):
    keep = None
    for _ in range(warmup):
        keep = fn()
    ts = []
    for _ in range(repeats):
        gc.collect()
        gc.disable()
        t0 = time.perf_counter_ns()
        keep = fn()
        t1 = time.perf_counter_ns()
        gc.enable()
        ts.append(t1 - t0)
    return ts, keep


def stats(ts, n_items=None):
    s = sorted(ts)
    d = {"repeats": len(ts), "p50_ns": nearest(s, 0.5), "p95_ns": nearest(s, 0.95), "max_ns": s[-1], "min_ns": s[0],
         "samples_ns": ts}
    if n_items:
        d["items"] = n_items
        d["rate_p50"] = int(n_items * NS / d["p50_ns"])
        d["rate_at_p95_time"] = int(n_items * NS / d["p95_ns"])
    return d


def verdict_rate(stat, floor, hard):
    r = stat["rate_at_p95_time"]
    return "PASS" if r >= floor else ("BUDGET MISS (hard met)" if r >= hard else "HARD BREACH")


# ------------------------------------------------------------------------------------------------ workloads
def load_generator():
    import gen_m2_workloads as G
    return G


def stream_inputs(G, n):
    prints = list(G.stream_prints(SEED, n))
    cons = {}
    for p in prints:
        c = p[0]
        if c not in cons:
            right, strike, exp = G.contract(c)
            cons[c] = (right, strike, exp, "stock")
    return prints, cons, G.session_open_ns(1)


def unit_inputs(G, underlying, k):
    prints = list(G.unit_prints(SEED, underlying, k))
    lane = G.lane(underlying)
    cons = {}
    for p in prints:
        c = p[0]
        if c not in cons:
            right, strike, exp = G.contract(c)
            cons[c] = (right, strike, exp, lane)
    return prints, cons, G.session_open_ns(k), lane


# ------------------------------------------------------------------------------------------------ correctness
def check_truth(G, man):
    from option_features import episodes as E, m2prints as M, printtape as PT
    out = {}
    # window truth of the unit SYN1/21: eligible prints, F4 large prints, F17 contracts >= threshold, premium
    prints, cons, op, lane = unit_inputs(G, "SYN1", 21)
    tape = PT.build_tape(prints, cons)
    cuts = [op + i * G.B_NS for i in range(1, G.CUTOFFS + 1)]
    f4 = M.f4_sweep(tape, cuts, threshold_ticks=G.LARGE_PREM, lane=lane, open_ns=op)
    f17 = M.f17_sweep(tape, cuts, threshold_ticks=G.LARGE_PREM, lane=lane, open_ns=op)
    groups = tape.select(lane, "all")
    h = hashlib.sha256()
    for i, (T, r4, rows17) in enumerate(zip(cuts, f4, f17), 1):
        prem = tape.stats(groups, T - G.B_NS, T)[0]
        row = (i, r4["coverage"]["eligible_count"], r4["value"]["large_count"], sum(1 for r in rows17 if r["fired"]), prem)
        h.update(("%d,%d,%d,%d,%d\n" % row).encode())
    want = man["window_truth"][0]["sha256"]
    out["window_truth_sha256"] = h.hexdigest()
    assert h.hexdigest() == want, "window truth mismatch (SYN1/21): %s != %s" % (h.hexdigest(), want)
    # episode truth: points (state, a, b) -> p60 = a, p900 = 15 b, N = 1 (fired iff a >= b), 15 leading points
    ep = {e["series"]: e for e in man["episodes"]}[500]
    tot = {1: 0, 5: 0}
    for s in range(500):
        pts = G.episode_points(SEED, (500, 1, s), G.MINUTES, s % G.DENSE_EVERY == 0)
        p60 = [None] * 15 + [a for _st, a, _b in pts]
        p900 = [None] * 15 + [15 * b for _st, _a, b in pts]
        for gap in (1, 5):
            sc = E.scan_episodes(p60, p900, len(p60) - 1, 1, 1, gap)
            tot[gap] += sc[0]
            if s < 3:
                sample = ep["sample"][s]["gap%d" % gap]
                assert sc[0] == sample[0] and sc[1] - 15 == sample[1], (s, gap, sc, sample)
    assert tot[1] == ep["truth_gap1_total"] and tot[5] == ep["truth_gap5_total"], (tot, ep["truth_gap1_total"], ep["truth_gap5_total"])
    out["episode_totals_500_series"] = {"gap1": tot[1], "gap5": tot[5]}
    return out


# ------------------------------------------------------------------------------------------------ gates
def family_calls(M, E, PT):
    """name -> function(tape, T, open_ns) for each family (single cutoff)."""
    return {
        "F1": lambda tape, T, op: M.f1_premium_surge(tape, T, op),
        "F4": lambda tape, T, op: M.f4_large_prints(tape, T, open_ns=op),
        "F17": lambda tape, T, op: M.f17_many(tape, T, open_ns=op),
        "F7": lambda tape, T, op: M.f7_concentration(tape, T, open_ns=op),
        "F18": lambda tape, T, op: M.f18_put_share(tape, T, at_least="1/2", at_most="1/4", open_ns=op),
        "F12": lambda tape, T, op: E.f12_from_tape(tape, T, op),
    }


def gate_rate_families(G, M, E, PT, sizes, repeats, report):
    calls = family_calls(M, E, PT)
    gates = {"M2-B5": ("F1", "F4", "F17"), "M2-B6": ("F7",), "M2-B7": ("F18",)}
    floors = {"M2-B5": (100_000, 20_000), "M2-B6": (100_000, 20_000), "M2-B7": (200_000, 40_000)}
    streams = {}
    for n in sizes:
        t0 = time.perf_counter()
        streams[n] = stream_inputs(G, n)
        print("  stream %d prints built in %.1f s (untimed)" % (n, time.perf_counter() - t0), flush=True)
    for gate, fams in gates.items():
        entry = report["gates"].setdefault(gate, {"budget_text": budget_text(gate), "families": {}})
        for fam in fams:
            fam_entry = entry["families"].setdefault(fam, {})
            for n, (prints, cons, op) in streams.items():
                T = op + 21_600 * NS
                fn = calls[fam]

                def run(prints=prints, cons=cons, op=op, T=T, fn=fn):
                    return fn(PT.build_tape(prints, cons), T, op)
                ts, keep = sample(run, repeats)
                st = stats(ts, n)
                st["verdict"] = verdict_rate(st, *floors[gate])
                fam_entry[str(n)] = st
                print("  %s %s n=%d: p50 %.3f s, p95 %.3f s, rate p50 %d/s, at p95 %d/s [%s]" % (
                    gate, fam, n, st["p50_ns"] / NS, st["p95_ns"] / NS, st["rate_p50"], st["rate_at_p95_time"], st["verdict"]), flush=True)
            sizes_sorted = sorted(fam_entry, key=int)
            if len(sizes_sorted) == 2:
                a, b = fam_entry[sizes_sorted[0]]["p95_ns"], fam_entry[sizes_sorted[1]]["p95_ns"]
                fam_entry["time_ratio_large_over_small_p95"] = round(b / a, 2)
                fam_entry["ratio_verdict"] = "PASS" if b / a <= 12 else "FAIL"
    # tape build alone (informational: the ingest part every family pays once)
    info = report["informational"].setdefault("tape_build", {})
    for n, (prints, cons, op) in streams.items():
        ts, _ = sample(lambda prints=prints, cons=cons: PT.build_tape(prints, cons), repeats)
        info[str(n)] = stats(ts, n)
        print("  tape build n=%d: p50 %.3f s, rate p50 %d/s" % (n, info[str(n)]["p50_ns"] / NS, info[str(n)]["rate_p50"]), flush=True)
    return streams


def gate_b10(G, M, E, PT, streams, repeats, report):
    calls = family_calls(M, E, PT)
    entry = report["gates"].setdefault("M2-B10", {"budget_text": budget_text("M2-B10"), "sizes": {}})
    for n, (prints, cons, op) in streams.items():
        T = op + 21_600 * NS

        def shared(prints=prints, cons=cons, op=op, T=T):
            tape = PT.build_tape(prints, cons)
            return [fn(tape, T, op) for fn in calls.values()]

        def separate(prints=prints, cons=cons, op=op, T=T):
            return [fn(PT.build_tape(prints, cons), T, op) for fn in calls.values()]
        ts, shared_keep = sample(shared, repeats)
        st = stats(ts, n)
        st["verdict"] = verdict_rate(st, 50_000, 20_000)
        ts2, sep_keep = sample(separate, max(5, repeats // 6))
        st2 = stats(ts2, n)
        same = [M.canonical_line(r) for r in shared_keep if "output_id" in r] == [M.canonical_line(r) for r in sep_keep if "output_id" in r]
        entry["sizes"][str(n)] = {"shared_pass": st, "six_separate_passes": st2, "shared_over_separate_p50": round(st["p50_ns"] / st2["p50_ns"], 3),
                                  "shared_equals_separate": same}
        print("  M2-B10 n=%d: shared p50 %.3f s (rate at p95 %d/s) [%s]; six separate p50 %.3f s; ratio %.3f; equal=%s" % (
            n, st["p50_ns"] / NS, st["rate_at_p95_time"], st["verdict"], st2["p50_ns"] / NS, st["p50_ns"] / st2["p50_ns"], same), flush=True)
        assert same, "shared pass differs from separate passes"


def gate_b8(G, E, repeats, report):
    entry = report["gates"].setdefault("M2-B8", {"budget_text": budget_text("M2-B8")})
    cols = []
    for s in range(500):
        pts = G.episode_points(SEED, (500, 1, s), G.MINUTES, s % G.DENSE_EVERY == 0)
        cols.append(([None] * 15 + [a for _st, a, _b in pts], [None] * 15 + [15 * b for _st, _a, b in pts]))
    n_pts = 500 * (G.MINUTES + 15)

    def per_name():
        return [E.scan_episodes(p60, p900, len(p60) - 1, 1, 1, 1)[0] for p60, p900 in cols]
    ts, keep = sample(per_name, repeats)
    st = stats(ts, n_pts)
    st["verdict"] = verdict_rate(st, 500_000, 100_000)
    st["unit"] = "500 names x (390 + 15 leading) points, scan only"
    entry["per_name_390"] = st
    one = sorted(t / 500 for t in ts)
    entry["per_name_390"]["per_session_p95_ns"] = int(nearest(one, 0.95))
    print("  M2-B8 390 points per name: p50 %.4f s per 500 names, rate p50 %d/s, at p95 %d/s, per session p95 %.3f ms [%s]" % (
        st["p50_ns"] / NS, st["rate_p50"], st["rate_at_p95_time"], nearest(one, 0.95) / 1e6, st["verdict"]), flush=True)
    # 1e6 points stream in sessions of 390
    t0 = time.perf_counter()
    sess, i, k = [], 0, 0
    n = 1_000_000
    while i < n:
        m = min(G.MINUTES, n - i)
        pts = G.episode_points(SEED, ("stream", k), m)
        sess.append(([None] * 15 + [a for _s, a, _b in pts], [None] * 15 + [15 * b for _s, _a, b in pts]))
        i += m
        k += 1
    print("  episode stream built in %.1f s (untimed), %d sessions" % (time.perf_counter() - t0, len(sess)), flush=True)

    def stream_scan():
        return sum(E.scan_episodes(p60, p900, len(p60) - 1, 1, 1, 1)[0] for p60, p900 in sess)
    ts, keep = sample(stream_scan, repeats)
    st = stats(ts, n + 15 * len(sess))
    st["verdict"] = verdict_rate(st, 500_000, 100_000)
    entry["stream_1e6"] = st
    man_total = json.loads((PERF / "m2_workload_manifest.json").read_text())["episode_stream"]["truth_gap1_total"]
    st["episodes_gap1_total"] = keep
    st["truth_gap1_total"] = man_total
    assert keep == man_total, (keep, man_total)
    print("  M2-B8 1e6 points: p50 %.3f s, rate p50 %d/s, at p95 %d/s [%s]; episodes %d = truth %d" % (
        st["p50_ns"] / NS, st["rate_p50"], st["rate_at_p95_time"], st["verdict"], keep, man_total), flush=True)


def gate_b15(G, M, E, PT, repeats, report):
    """Print pass = tape build + the family windows at the cutoffs; F17 per-contract results are reads and are
    gated apart (M2-B15r), so the gate figure uses the columnar F17 print pass. The figure with every result
    record materialised is reported beside it."""
    entry = report["gates"].setdefault("M2-B15", {"budget_text": budget_text("M2-B15")})
    prints, cons, op, lane = unit_inputs(G, "SYN1", 21)
    cuts = [op + i * G.B_NS for i in range(1, G.CUTOFFS + 1)]
    thr = G.LARGE_PREM
    mid = cuts[len(cuts) // 2]

    def one_pass(T):
        tape = PT.build_tape(prints, cons)
        return (M.f1_premium_surge(tape, T, op, lane=lane), M.f4_large_prints(tape, T, threshold_ticks=thr, lane=lane, open_ns=op),
                M.f17_columns(tape, T, lane=lane, open_ns=op), M.f7_concentration(tape, T, lane=lane, open_ns=op),
                M.f18_put_share(tape, T, at_least="1/2", lane=lane, open_ns=op))

    def sweep_pass():
        tape = PT.build_tape(prints, cons)
        return (M.f1_sweep(tape, cuts, op, lane=lane), M.f4_sweep(tape, cuts, threshold_ticks=thr, lane=lane, open_ns=op),
                M.f17_sweep_columns(tape, cuts, lane=lane, open_ns=op), M.f7_sweep(tape, cuts, lane=lane, open_ns=op),
                M.f18_sweep(tape, cuts, at_least="1/2", lane=lane, open_ns=op))

    def one_full(T):
        tape = PT.build_tape(prints, cons)
        return (M.f1_premium_surge(tape, T, op, lane=lane), M.f4_large_prints(tape, T, threshold_ticks=thr, lane=lane, open_ns=op),
                M.f17_many(tape, T, threshold_ticks=thr, lane=lane, open_ns=op), M.f7_concentration(tape, T, lane=lane, open_ns=op),
                M.f18_put_share(tape, T, at_least="1/2", lane=lane, open_ns=op))

    def sweep_full():
        tape = PT.build_tape(prints, cons)
        return (M.f1_sweep(tape, cuts, op, lane=lane), M.f4_sweep(tape, cuts, threshold_ticks=thr, lane=lane, open_ns=op),
                M.f17_sweep(tape, cuts, threshold_ticks=thr, lane=lane, open_ns=op), M.f7_sweep(tape, cuts, lane=lane, open_ns=op),
                M.f18_sweep(tape, cuts, at_least="1/2", lane=lane, open_ns=op))

    def ratios(one, sweep):
        ts1, k1 = sample(lambda: one(mid), repeats)
        ts78, k78 = sample(sweep, repeats)
        s1, s78 = stats(ts1, len(prints)), stats(ts78, len(prints))
        return s1, s78, k1, k78, {"ratio_p50": round(s78["p50_ns"] / (78 * s1["p50_ns"]), 4),
                                  "ratio_p95": round(s78["p95_ns"] / (78 * s1["p95_ns"]), 4),
                                  "ratio_sweep_p95_over_78_single_p50": round(s78["p95_ns"] / (78 * s1["p50_ns"]), 4)}
    s1, s78, k1, k78, r = ratios(one_pass, sweep_pass)
    j = len(cuts) // 2
    assert M.canonical_line(k1[0]) == M.canonical_line(k78[0][j]) and M.canonical_line(k1[3]) == M.canonical_line(k78[3][j])
    assert k1[2] == k78[2][j]
    f1, f78, g1, g78, rf = ratios(one_full, sweep_full)
    assert [M.canonical_line(x) for x in g1[2]] == [M.canonical_line(x) for x in g78[2][j]]
    entry.update({"unit": "SYN1/21, %d prints, 78 cutoffs (T = open + 300 s x i), F1 F4 F17 F7 F18" % len(prints),
                  "print_pass_gate_figure": dict(r, single_cutoff_pass=s1, sweep_78_cutoffs=s78,
                                                 verdict="PASS" if max(r.values()) <= 0.25 else "FAIL"),
                  "with_all_results_materialised_informational": dict(rf, single_cutoff_pass=f1, sweep_78_cutoffs=f78)})
    tb, _ = sample(lambda: PT.build_tape(prints, cons), repeats)
    entry["tape_build_p50_ns"] = stats(tb)["p50_ns"]
    print("  M2-B15 print pass: single p50 %.4f s; 78-cutoff sweep p50 %.4f s (tape build %.4f s); ratios %s (budget <= 0.25, hard 0.5) [%s]" % (
        s1["p50_ns"] / NS, s78["p50_ns"] / NS, entry["tape_build_p50_ns"] / NS, json.dumps(r), entry["print_pass_gate_figure"]["verdict"]), flush=True)
    print("  M2-B15 with every result record materialised (informational): single p50 %.4f s, sweep p50 %.4f s, ratios %s" % (
        f1["p50_ns"] / NS, f78["p50_ns"] / NS, json.dumps(rf)), flush=True)


def gate_b15_overlap(G, M, E, PT, repeats, report):
    """M2-B15 definition used here: ratio = (cost of one sweep over 78 cutoffs) / (78 x cost of one single-cutoff
    evaluation), measured two ways: "with_tape_build" (the tape build is inside both sides: print pass = build +
    windows) and "prebuilt" (tape prebuilt, queries only: the strict reuse ratio). RULED: the gate (<= 0.25, hard
    0.5) applies to overlapping-cutoff sweeps, i.e. 900 s windows with cutoffs 300 s apart; 3600 s windows with
    cutoffs 10 s apart is informational; non-overlapping spacing (window equal to spacing) has no reuse to measure
    and is informational; F17 with a per-cutoff sparse read is informational (B15r gates reads; performance idea
    candidate, see DECISIONS.md)."""
    entry = report["gates"].setdefault("M2-B15", {"budget_text": budget_text("M2-B15")})
    prints, cons, op, lane = unit_inputs(G, "SYN1", 21)
    tape = PT.build_tape(prints, cons)

    def cuts_of(spacing_s):
        return [op + 20_000 * NS + spacing_s * NS * i for i in range(78)]
    c300, c10 = cuts_of(300), cuts_of(10)
    # name -> (cutoffs, gated, one(tape, T), sweep(tape))
    cases = {
        "F7_900s_window_cutoffs_300s_apart (GATED, overlapping)": (c300, True,
            lambda t, T: M.f7_concentration(t, T, window_s=900, lane=lane, open_ns=op),
            lambda t: M.f7_sweep(t, c300, window_s=900, lane=lane, open_ns=op)),
        "F7_3600s_window_cutoffs_10s_apart (informational)": (c10, False,
            lambda t, T: M.f7_concentration(t, T, window_s=3600, lane=lane, open_ns=op),
            lambda t: M.f7_sweep(t, c10, window_s=3600, lane=lane, open_ns=op)),
        "F7_300s_window_cutoffs_300s_apart (informational, no overlap)": (c300, False,
            lambda t, T: M.f7_concentration(t, T, window_s=300, lane=lane, open_ns=op),
            lambda t: M.f7_sweep(t, c300, window_s=300, lane=lane, open_ns=op)),
        "F17_300s_advance_only_cutoffs_10s_apart (informational)": (c10, False,
            lambda t, T: M._f17_scan(t.select(lane, "all"), M.start_of(T, 300 * NS, op), T),
            lambda t: sum(1 for _ in M._f17_slide(t.select(lane, "all"), c10, op))),
        "F17_300s_with_sparse_reads_cutoffs_10s_apart (informational, B15r)": (c10, False,
            lambda t, T: M.f17_columns(t, T, lane=lane, open_ns=op, sparse=True),
            lambda t: M.f17_sweep_columns(t, c10, lane=lane, open_ns=op, sparse=True)),
        "F12_incremental_cutoffs_10s_apart (informational)": (c10, False,
            lambda t, T: E.f12_from_tape(t, T, op, lane=lane),
            lambda t: E.f12_sweep(t, c10, op, lane=lane)),
    }
    out = {}
    for name, (cuts, gated, one, sweep) in cases.items():
        mid = cuts[39]
        a1, _ = sample(lambda: one(PT.build_tape(prints, cons), mid), repeats)
        a78, _ = sample(lambda: sweep(PT.build_tape(prints, cons)), repeats)
        q1, _ = sample(lambda: one(tape, mid), repeats)
        q78, _ = sample(lambda: sweep(tape), repeats)
        w = {"with_tape_build": {"ratio_p50": round(stats(a78)["p50_ns"] / (78 * stats(a1)["p50_ns"]), 4),
                                 "ratio_p95": round(stats(a78)["p95_ns"] / (78 * stats(a1)["p95_ns"]), 4)},
             "prebuilt": {"ratio_p50": round(stats(q78)["p50_ns"] / (78 * stats(q1)["p50_ns"]), 4),
                          "ratio_p95": round(stats(q78)["p95_ns"] / (78 * stats(q1)["p95_ns"]), 4)},
             "single_query_p50_ns": stats(q1)["p50_ns"], "sweep_queries_p50_ns": stats(q78)["p50_ns"], "gated": gated}
        worst = max(w["with_tape_build"]["ratio_p95"], w["prebuilt"]["ratio_p95"])
        w["verdict"] = (("PASS" if worst <= 0.25 else ("with tape build: %s; prebuilt: %s (budget 0.25, hard 0.5)" % (
            "PASS" if w["with_tape_build"]["ratio_p95"] <= 0.25 else "FAIL",
            "PASS" if w["prebuilt"]["ratio_p95"] <= 0.25 else ("BUDGET MISS, hard met" if w["prebuilt"]["ratio_p95"] <= 0.5 else "HARD BREACH")))) if gated
                        else "informational (worst %.3f)" % worst)
        out[name] = w
        print("  M2-B15 %s: with tape build %s; prebuilt %s [%s]" % (
            name, json.dumps(w["with_tape_build"]), json.dumps(w["prebuilt"]), w["verdict"]), flush=True)
    entry["definition"] = ("ratio = sweep over 78 cutoffs / (78 x single cutoff); with_tape_build counts the tape build on both "
                           "sides, prebuilt is queries only; gate applies to overlapping sweeps (900 s windows, 300 s apart)")
    entry["overlap_cases"] = out


def p1_t1_marker(report):
    p = ROOT / "docs" / "p1" / "P1_T1_REPORT.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    report["p1_t1_regression_marker"] = {
        "source": "docs/p1/P1_T1_REPORT.json (recorded, not re-measured by this run)",
        "records_per_s_p50_1e5": d["sizes"]["100000"]["rate_p50"], "records_per_s_at_p95_1e5": d["sizes"]["100000"]["rate_at_p95_time"],
        "records_per_s_p50_1e6": d["sizes"]["1000000"]["rate_p50"], "records_per_s_at_p95_1e6": d["sizes"]["1000000"]["rate_at_p95_time"],
        "informational_alarm_below_records_per_s_1e6": 531146}
    print("  P1-T1 recorded marker: %s" % json.dumps(report["p1_t1_regression_marker"]), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=30)
    ap.add_argument("--sizes", default="100000,1000000")
    ap.add_argument("--json", default=None)
    ap.add_argument("--quick", action="store_true", help="smoke run: 3 repeats, 1e5 only (not a gate result)")
    args = ap.parse_args()
    repeats = 3 if args.quick else args.repeats
    sizes = [100_000] if args.quick else [int(s) for s in args.sizes.split(",")]
    if repeats < 30:
        print("note: the protocol asks for >= 30 timed repeats; %d is a smoke run, not a gate result" % repeats)
    from option_features import episodes as E, m2prints as M, printtape as PT
    G = load_generator()
    man = json.loads((PERF / "m2_workload_manifest.json").read_text(encoding="utf-8"))
    print(QUAL)
    print("M2 story B print-window gates (%s)" % LABEL)
    report = {"qualification_label": QUAL, "label": LABEL, "evidence": "Developer evidence only; the independent Tester must re-run",
              "seed": SEED, "repeats": repeats, "warmup": 1, "machine": machine(), "gates": {}, "informational": {},
              "timer": "time.perf_counter_ns around the compute call only; gc collected before and paused inside the timed call"}
    print("machine:", json.dumps(report["machine"]))
    report["truth_checks"] = check_truth(G, man)
    print("truth checks passed:", json.dumps(report["truth_checks"]), flush=True)
    streams = gate_rate_families(G, M, E, PT, sizes, repeats, report)
    gate_b10(G, M, E, PT, streams, repeats, report)
    del streams
    gate_b8(G, E, repeats, report)
    gate_b15(G, M, E, PT, repeats, report)
    gate_b15_overlap(G, M, E, PT, repeats, report)
    p1_t1_marker(report)
    report["not_measured"] = ["M2-B18 trade-to-grid (story A grid builder)", "M2-B1..B4, B9, B11..B17 (store, percentile, runner)",
                              "worker scaling (library is single-threaded; the opt-in runner owns parallelism)",
                              "real-size or recorded-data performance"]
    report["after_label"] = LABEL
    if args.json:
        Path(args.json).write_text(json.dumps(report, sort_keys=True, indent=1) + "\n", encoding="utf-8", newline="\n")
        print("wrote", args.json)


if __name__ == "__main__":
    main()
