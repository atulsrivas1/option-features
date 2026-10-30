#!/usr/bin/env python3
"""Worker-scaling and store measurements for the M2 binding of the opt-in runner (heavy, not a CI test).

Label: synthetic workload, relative engineering budget; no claim about recorded data. Developer evidence only: the
independent Tester must re-run. M2-G0 at N workers lives in tools/m2_g0_bench.py (phases g0 and scale).

Phases (python tools/m2_runner_bench.py --report R.json --phase NAME [options]); each appends to the report:
  freeze   machine and workload facts, truth checks (window, episode, rank at N = 500), written BEFORE the first measured run
  b16      history-view transfer to workers: per-worker start (attach, content_hash, gc.freeze) at 2,000 and 6,000 series,
           private vs shared bytes, at 4 workers and at N workers, >= 30 repeats
  b17      store round trip, 250,000 records, canonical LF dump and load, >= 30 repeats, hash compared
  b18      trade-to-grid, 25 sessions of one underlying (963,076 prints), >= 30 repeats, totals checked against the reference
  scaling  S01 (>= 2.0x at 4 workers, multi-underlying, family all) and S02 proxy (>= 1.8x, print-pass families), curve to N
  b12      the whole workload (5 x 5 x 78 cutoffs, family all, size M) ONCE at N workers; --subset K runs every K-th cutoff
           and reports 'extrapolated'
Budgets are printed verbatim from docs/m2/M2_GATE_BUDGETS.md. N is capped at --max-workers (24).
"""
import argparse
import gc
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "qualification" / "synthetic" / "m2" / "perf")]
import m1_runner  # noqa: E402
import m1_runner_bench as mb  # noqa: E402
import m2_print_benchmark as pb  # noqa: E402
from m1_runner import Runner, Spec  # noqa: E402
from m1_runner import m2workload as M  # noqa: E402
from m1_runner import runner as R  # noqa: E402

LABEL = mb.LABEL
GIB = 1 << 30
MIB = 1 << 20
SEED = 20261029


def budget(gate):
    return pb.budget_text(gate)


def pct(v, p):
    return mb.pct(v, p)


def stats(v):
    return {"n": len(v), "p50": pct(v, 50), "p95": pct(v, 95), "max": max(v), "samples": v}


def make_runner(workers, a, **kw):
    return Runner(workers=workers, b9_peak_bytes=a.b9_peak_bytes, aggregate_hard_bytes=a.aggregate_hard_bytes, cores=a.cores,
                  timeout_s=a.timeout_s, **kw)


def phase_freeze(a, rep):
    G = M.G
    man = json.loads((ROOT / "qualification/synthetic/m2/perf/m2_workload_manifest.json").read_text(encoding="utf-8"))
    truth = pb.check_truth(G, man)
    t0 = time.perf_counter()
    store = M.build_store(SEED, 500)
    rows = rank_rows(store, 500)
    ref = rank_rows_ref(SEED, 500, drop=0)
    ref_amb4 = rank_rows_ref(SEED, 500, drop=5)
    truth["rank_truth_500"] = {
        "library_rows_equal_manifest_sha": hashlib.sha256(rows.encode()).hexdigest() == man["rank_truth"]["sha256"],
        "reference_without_amb4_equals_manifest_sha": hashlib.sha256(ref.encode()).hexdigest() == man["rank_truth"]["sha256"],
        "library_rows_equal_reference_with_amb4_drop": rows == ref_amb4,
        "finding": "the manifest rank truth ranks all 7,440 history values; the library drops the first W/60 = 5 grid points of every session (AMB-4, "
                   "ruled), so n is 7,340. The library equals the same reference computed with the drop; PO ruling requested on the fixture"}
    truth["rank_check_seconds"] = time.perf_counter() - t0
    if not truth["rank_truth_500"]["library_rows_equal_reference_with_amb4_drop"]:
        sys.exit("rank truth check failed (library store rows differ from the reference with the AMB-4 drop); no timing is accepted")
    per_unit = {k: G.unit_n(k) for k in (1, 7, 14, 21, 25)}
    rep["frozen"] = {"machine": mb.machine(), "label": LABEL, "seed": SEED, "truth": truth, "unit_print_totals": per_unit,
                     "workload": {"units_b12": 1950, "contracts_per_chain": 2000, "series_counts": [500, 2000, 6000], "history_sessions": 25,
                                  "store_records_at_2000": 2000 * 25 * 5, "manifest_sha256": hashlib.sha256((ROOT / "qualification/synthetic/m2/perf/m2_workload_manifest.json").read_bytes()).hexdigest()},
                     "runner": {"cap": R.worker_cap(a.cores, None, a.b9_peak_bytes, a.aggregate_hard_bytes), "N": a.n, "max_workers": a.max_workers},
                     "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(ROOT)).stdout.strip(),
                     "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(ROOT)).stdout.strip())}
    print(json.dumps(rep["frozen"], indent=1, sort_keys=True, default=str))


def rank_rows(store, n_series):
    """Rows of the manifest rank_truth form computed from the LIBRARY store: contracts metric, session 21, bin 200."""
    G = M.G
    from bisect import bisect_left
    out = []
    sid = M.session_date(21)
    for s in range(n_series):
        v = store.baseline("S%04d" % s, "contracts", 300, sid, 20, "stock")
        today = G.series_session(SEED, s, 21)[1]["contracts"]
        x, xt = today.get(200, 0), sum(today.values())
        n, le, ge = v.rank(x)
        tge = sum(1 for t in v.totals if t >= xt)
        med, mean = v.median(), v.mean()
        mr = "zd" if med == 0 else str(Fraction(x) / med)
        out.append("%d|%d|%d|%d|%d|%d|%s|%s|%s\n" % (s, x, n, le, ge, tge, med, mean, mr))
    return "".join(out)


def rank_rows_ref(seed, n_series, drop):
    """Tester-style reference (sorted list, Fraction) from the generator; drop = grid points dropped per session (AMB-4: 5)."""
    G = M.G
    from bisect import bisect_left, bisect_right
    out = []
    for s in range(n_series):
        hist, tots = [], []
        for k in range(1, 21):
            d = G.series_session(seed, s, k)[1]["contracts"]
            vals = [0] * G.minutes_of(k)
            for b, v in d.items():
                vals[b] = v
            hist.extend(vals[drop:])
            tots.append(sum(vals))
        today = G.series_session(seed, s, 21)[1]["contracts"]
        x, xt = today.get(200, 0), sum(today.values())
        hs = sorted(hist)
        n = len(hs)
        med = Fraction(hs[n // 2 - 1] + hs[n // 2], 2)
        mean = Fraction(sum(hs), n)
        ts = sorted(tots)
        mr = "zd" if med == 0 else str(Fraction(x) / med)
        out.append("%d|%d|%d|%d|%d|%d|%s|%s|%s" % (s, x, n, bisect_right(hs, x), n - bisect_left(hs, x), len(ts) - bisect_left(ts, xt), med, mean, mr))
    return "".join(r + chr(10) for r in out)


def phase_b16(a, rep):
    out = {"budget": budget("M2-B16"), "note": "start = send the snapshot, worker maps it read-only, verifies, compares content_hash(), gc.freeze(), acks; "
           "pool spawn and interpreter start reported apart; private bytes = working-set growth of the attach, shared = the mapped file"}
    rep["b16"] = out
    for series in (2000, 6000):
        spec = Spec(family="store", series_count=series, underlyings=("SYN1",), sessions=(21,), cutoffs=(0,))
        entry = out.setdefault(str(series), {})
        for n in sorted({4, a.n}):
            with make_runner(n, a) as r:
                gen = r._store_generation(spec)
                entry.setdefault("generation", {"build_s": gen["build_s"], "write_s": gen["write_s"], "file_bytes": gen["file_bytes"],
                                                 "records": gen["store"].stats()["records"], "est_bytes": gen["store"].stats()["est_bytes"],
                                                 "content_sha256": gen["content_hash"]})
                per_worker, spawn, priv, shared = [], [], [], gen["file_bytes"]
                over = 0
                for i in range(a.warmups + a.repeats):
                    t0 = time.perf_counter()
                    r.restart_pool()
                    t1 = time.perf_counter()
                    acks = r._setup_pool_store(spec, gen)
                    if i >= a.warmups:
                        spawn.append(t1 - t0)
                        per_worker += [x["total_s"] for x in acks]
                        priv += [x["private_bytes"] for x in acks]
                        over += sum(1 for x in acks if x["private_bytes"] > 512 * MIB)
                rss = [R.peak_rss_bytes()]
            hard = series == 6000
            entry["workers_%d" % n] = {"workers": n, "per_worker_start_s": stats(per_worker), "pool_spawn_s": stats(spawn),
                                       "private_bytes_per_worker": stats(priv), "shared_mapped_bytes": shared, "workers_over_512MB": over,
                                       "verdict_start_p95": verdict(pct(per_worker, 95), 15 if hard else 5, 15),
                                       "verdict_bytes_max": verdict(max(priv), 1 * GIB if hard else 512 * MIB, GIB)}
            print("B16 series %d workers %d: start p50 %.3f p95 %.3f max %.3f s; private max %.1f MiB; shared %.1f MiB" % (
                series, n, pct(per_worker, 50), pct(per_worker, 95), max(per_worker), max(priv) / MIB, shared / MIB), flush=True)
            mb.save(a.report, rep)


def verdict(v, budget_v, hard):
    return "within budget" if v <= budget_v else ("over budget, within hard" if v <= hard else "OVER HARD")


def phase_b17(a, rep):
    from option_features import flowstore
    out = {"budget": budget("M2-B17")}
    rep["b17"] = out
    store = M.build_store(SEED, 2000)
    cal = M.make_calendar()
    want = store.content_hash()
    tmp = tempfile.mkdtemp(prefix="m2-b17-")
    wr, rd = [], []
    try:
        path = os.path.join(tmp, "store.m2")
        for i in range(a.warmups + a.repeats):
            gc.collect()
            t0 = time.perf_counter()
            store.dump_to(path)
            t1 = time.perf_counter()
            loaded = flowstore.HistoryStore.load(Path(path), cal, k=M.STORE_SESSIONS)
            t2 = time.perf_counter()
            if loaded.content_hash() != want:
                sys.exit("round trip changed the content hash")
            if i >= a.warmups:
                wr.append(t1 - t0)
                rd.append(t2 - t1)
            print("  b17 repeat %d write %.2f s read %.2f s" % (i, t1 - t0, t2 - t1), flush=True) if i < 2 else None
        size = os.path.getsize(path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    rec = store.stats()["records"]
    wrate, rrate = [rec / x for x in wr], [rec / x for x in rd]
    out.update({"records": rec, "file_bytes": size, "content_sha256": want, "hash_identical_all_repeats": True, "write_s": stats(wr), "read_s": stats(rd),
                "write_records_per_s_p5": sorted(wrate)[max(1, math.ceil(0.05 * len(wrate))) - 1], "read_records_per_s_p5": sorted(rrate)[max(1, math.ceil(0.05 * len(rrate))) - 1],
                "write_records_per_s_p50": sorted(wrate)[len(wrate) // 2], "read_records_per_s_p50": sorted(rrate)[len(rrate) // 2]})
    out["verdict_write"] = rate_verdict(out["write_records_per_s_p5"], 25000, 5000)
    out["verdict_read"] = rate_verdict(out["read_records_per_s_p5"], 50000, 10000)
    print("B17 write p5 %.0f rec/s (p50 %.0f) -> %s; read p5 %.0f rec/s (p50 %.0f) -> %s" % (
        out["write_records_per_s_p5"], out["write_records_per_s_p50"], out["verdict_write"], out["read_records_per_s_p5"], out["read_records_per_s_p50"], out["verdict_read"]), flush=True)


def rate_verdict(v, floor, hard):
    return "within budget" if v >= floor else ("over budget, within hard" if v >= hard else "OVER HARD")


def phase_b18(a, rep):
    G = M.G
    out = {"budget": budget("M2-B18")}
    rep["b18"] = out
    man = json.loads((ROOT / "qualification/synthetic/m2/perf/m2_workload_manifest.json").read_text(encoding="utf-8"))
    inputs, total = [], 0
    for k in range(1, 26):
        prints = list(G.unit_prints(SEED, "SYN1", k))
        lane = G.lane("SYN1")
        cons = {}
        for p in prints:
            if p[0] not in cons:
                right, strike, exp = G.contract(p[0])
                cons[p[0]] = (right, strike, exp, lane)
        inputs.append((k, prints, cons, lane))
        total += len(prints)
    out["prints"], out["expected_prints"] = total, 23 * 40000 + 2 * 21538
    times, builds = [], None
    for i in range(a.warmups + a.repeats):
        gc.collect()
        t0 = time.perf_counter()
        builds = [M.build_grid(p, c, k, ln) for k, p, c, ln in inputs]
        t1 = time.perf_counter()
        if i >= a.warmups:
            times.append(t1 - t0)
        if i < 2:
            print("  b18 repeat %d %.2f s (%.0f prints/s)" % (i, t1 - t0, total / (t1 - t0)), flush=True)
    ok = all(M.grid_truth_check(p, c, k, ln, b) for (k, p, c, ln), b in zip(inputs, builds))
    series_ref = {t["unit"]: t["series_with_prints"] for t in man["trade_to_grid_truth"]}
    got = {"SYN1/21": len({r.series_id for r in builds[20].records if r.series_id != "NAME"}), "SYN1/01": len({r.series_id for r in builds[0].records if r.series_id != "NAME"})}
    rates = [total / t for t in times]
    out.update({"seconds": stats(times), "prints_per_s_p50": sorted(rates)[len(rates) // 2],
                "prints_per_s_p5": sorted(rates)[max(1, math.ceil(0.05 * len(rates))) - 1], "totals_truth_ok": ok,
                "series_with_prints_vs_manifest": {"library": got, "manifest": series_ref, "equal": all(got[k] == series_ref[k] for k in got)},
                "p1_t1_marker_records_per_s": pb.p1_t1_marker({"gates": {}}) if False else "663,933 at 1e6 (docs/p1/P1_T1_REPORT.json)"})
    out["verdict"] = rate_verdict(out["prints_per_s_p5"], 50000, 20000) if ok else "TRUTH CHECK FAILED"
    print("B18 %d prints: p5 %.0f prints/s (p50 %.0f) truth %s -> %s" % (total, out["prints_per_s_p5"], out["prints_per_s_p50"], ok, out["verdict"]), flush=True)


def unit_work_spec(family, cutoffs, a):
    return Spec(family=family, shape="M", underlyings=tuple(m1_runner.workload.gen.UNDERLYINGS), sessions=(21,), cutoffs=cutoffs, series_count=2000)


def phase_scaling(a, rep):
    out = {"s_rows": "S01 >= 2.0x at 4 workers (compute, 5 underlyings); S02 >= 1.8x (trade streams)"}
    rep["scaling"] = out
    cuts = tuple(range(0, 78, 10))
    for name, family in (("S01_family_all", "all"), ("S02_proxy_print_families", "prints")):
        spec = unit_work_spec(family, cuts, a)
        entry = out.setdefault(name, {"units": 5 * len(cuts), "family": family})
        walls = {}
        for n in (1, 2, 4, 8, a.n):
            if n in walls:
                continue
            with make_runner(n, a) as r:
                runs = []
                for _ in range(3 if n <= 4 else 2):
                    res = r.run(spec)
                    runs.append({"wall_s": res.log["wall_s"], "synthesis_s": sum(c["history_s"] for c in res.log["chunk_wall_s"]),
                                 "aggregate_peak_rss_bytes": res.log["aggregate_peak_rss_bytes"], "result_sha256": res.result_sha256,
                                 "store_setup_s": (res.log.get("store") or {}).get("setup_s")})
                walls[n] = pct([x["wall_s"] for x in runs], 50)
                entry["workers_%d" % n] = {"runs": runs, "p50_wall_s": walls[n], "hash_equal": len({x["result_sha256"] for x in runs}) == 1}
                print("%s workers %d p50 wall %.1f s" % (name, n, walls[n]), flush=True)
                mb.save(a.report, rep)
        hashes = {entry[k]["runs"][0]["result_sha256"] for k in entry if k.startswith("workers_")}
        entry["identical_across_workers"] = len(hashes) == 1
        for n in walls:
            entry["workers_%d" % n]["speedup"] = walls[1] / walls[n]
            entry["workers_%d" % n]["efficiency"] = walls[1] / walls[n] / n
        floor = 2.0 if family == "all" else 1.8
        entry["meets_floor_at_4"] = entry["workers_4"]["speedup"] >= floor
        entry["floor_at_4"] = floor


def phase_b12(a, rep):
    out = {"budget": budget("M2-B12")}
    rep["b12"] = out
    cuts = tuple(range(0, 78, a.subset))
    spec = Spec(family="all", shape="M", sessions=(21, 22, 23, 24, 25), cutoffs=cuts, series_count=2000)
    with make_runner(a.n, a) as r:
        res = r.run(spec)
    lg = res.log
    chunks = lg["chunk_wall_s"]
    synth, cpu = sum(c["history_s"] for c in chunks), sum(c["cpu_s"] for c in chunks)
    out.update({"units": res.unit_count, "workers_used": lg["workers_used"], "wall_s": lg["wall_s"], "wall_min": lg["wall_s"] / 60,
                "units_per_s": lg["units_per_s"], "cpu_s_sum": cpu, "input_synthesis_s_sum": synth, "synthesis_share_of_cpu": synth / cpu,
                "compute_only_wall_min_estimate": lg["wall_s"] / 60 * (1 - synth / cpu), "store": {k: v for k, v in lg["store"].items() if k != "attach"},
                "store_attach_private_bytes_max": max(x["private_bytes"] for x in lg["store"]["attach"]),
                "peak_rss_per_worker_bytes": lg["peak_rss_per_worker_bytes"], "aggregate_peak_rss_bytes": lg["aggregate_peak_rss_bytes"],
                "max_worker_rss_bytes": max(lg["peak_rss_per_worker_bytes"]), "result_sha256": res.result_sha256,
                "utilisation_cpu_over_workers_x_wall": cpu / (lg["workers_used"] * lg["wall_s"]), "clamp": lg["clamp"], "n_subset": a.subset})
    if a.subset > 1:
        out["extrapolated_full_wall_min"] = out["wall_min"] * 1950 / res.unit_count
        out["label"] = "extrapolated (every %d-th cutoff)" % a.subset
    print("B12 %d units, %d workers: wall %.1f s = %.2f min; synthesis %.1f%% of CPU; max worker RSS %.0f MiB; aggregate %.2f GiB; hash %s" % (
        res.unit_count, lg["workers_used"], lg["wall_s"], lg["wall_s"] / 60, 100 * synth / cpu, out["max_worker_rss_bytes"] / MIB,
        out["aggregate_peak_rss_bytes"] / GIB, res.result_sha256[:16]), flush=True)


PHASES = {"freeze": phase_freeze, "b16": phase_b16, "b17": phase_b17, "b18": phase_b18, "scaling": phase_scaling, "b12": phase_b12}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--phase", required=True, choices=sorted(PHASES))
    ap.add_argument("--n", type=int, default=0, help="N workers (0 = min(runner cap, --max-workers))")
    ap.add_argument("--max-workers", type=int, default=24)
    ap.add_argument("--repeats", type=int, default=30)
    ap.add_argument("--warmups", type=int, default=1)
    ap.add_argument("--b9-peak-bytes", type=int, default=R.B9_BUDGET_BYTES)
    ap.add_argument("--aggregate-hard-bytes", type=int, default=None)
    ap.add_argument("--cores", type=int, default=None)
    ap.add_argument("--timeout-s", type=float, default=3600.0)
    ap.add_argument("--subset", type=int, default=1)
    a = ap.parse_args()
    if a.n == 0:
        a.n = min(R.worker_cap(a.cores, None, a.b9_peak_bytes, a.aggregate_hard_bytes)["cap"], a.max_workers)
    a.n = min(a.n, a.max_workers)
    rep = mb.load(a.report)
    if a.phase != "freeze" and "frozen" not in rep:
        sys.exit("run --phase freeze first: machine, workload and truth checks are written before the first measured run")
    PHASES[a.phase](a, rep)
    rep.setdefault("phases_done", []).append(a.phase)
    mb.save(a.report, rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
