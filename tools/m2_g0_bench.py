#!/usr/bin/env python3
"""M2-G0 measurement: B6 for the FULL output set as one measurement (not a CI test).

Label: synthetic workload, relative engineering budget; no claim about recorded data.
Developer evidence only: the independent Tester must re-run this.

B6 as written (PERF_ACCEPTANCE.md): all outputs, one underlying, size M, one cutoff <= 5 s p95 (15 s hard).
One unit = tools/m1_runner/workload.py compute_unit: OC5, OC6 for every contract, per-contract IV, ATM IV (all
expiries), 30-day IV, and the P1 outputs (spread/locked/coverage gates, touch-policy signing, window_end premium
windows, single-reference F5/F6 shares) over the unit's synthetic quote and trade streams.

Phases (python tools/m2_g0_bench.py --report R.json --phase NAME), each appends to the report:
  freeze   machine and workload facts, printed and written BEFORE the first measured run
  g0       single worker, size M, all-valid-quote chain, one cutoff: warm-up, then >= 30 timed compute-only repeats
           (input synthesis excluded, reported separately): p50/p95/max, per-family breakdown, peak memory
  scale    2, 4 and N workers, informational: one unit per worker, >= 30 repeats; efficiency vs the 1-worker p50
  matrix   identical-hash matrix (delegates to tools/m1_runner_bench.py): 1, 2, 4, N workers x 3 repeats, batch sizes,
           unit orders, contract order; compared with the single-process reference
  arb      untimed counter run (counters stay outside results)
N is capped: min(runner cap, --max-workers 24).
"""
import argparse
import gc
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools")]
import m1_runner  # noqa: E402
import m1_runner_bench as mb  # noqa: E402
from m1_runner import Spec, workload  # noqa: E402
from m1_runner import runner as R  # noqa: E402

LABEL = mb.LABEL
BUDGET = {"B6": "all outputs, 1 underlying, size M, 1 cutoff: <= 5 s p95, hard 15 s (PERF_ACCEPTANCE.md; a miss is reported as a miss, never a budget edit)",
          "B9": mb.BUDGET["B9"]}
CUTOFF = 39
KEY = "SYN1/01/%03d" % CUTOFF
GIB = 1 << 30


def b6_spec():
    return Spec(shape="M", underlyings=("SYN1",), sessions=(1,), cutoffs=(CUTOFF,), gating="valid")


def verdict(p95):
    return "within budget" if p95 <= 5 else ("MISS: over budget, within hard" if p95 <= 15 else "MISS: OVER HARD")


def phase_freeze(a, rep):
    spec = b6_spec()
    inp = workload.build_inputs(spec, KEY)
    quotes_n = sum(inp.cut)
    prints_n = sum(len(p) for p in inp.prints)
    fingerprint = hashlib.sha256(repr((inp.records, inp.prints, inp.share_prints, inp.spot)).encode()).hexdigest()
    manifest = (ROOT / "qualification/synthetic/perf/perf_manifest.json").read_bytes()
    frozen = {
        "machine": mb.machine(),
        "workload": {
            "label": LABEL, "perf_manifest_sha256": hashlib.sha256(manifest).hexdigest(), "seed": spec.seed, "shape": "M",
            "contracts_per_chain": workload.chain_size("M"), "unit": KEY, "gating": "valid (all chain quotes valid for IV)",
            "cutoff_index": CUTOFF, "cutoff_ns": inp.cutoff_ns,
            "prints_per_contract": spec.prints, "prints_per_unit": prints_n,
            "quote_updates_in_unit_stream": quotes_n, "classify_stream_records": len(inp.records),
            "print_windows_ns": list(workload.PRINT_WINDOWS_NS), "print_mix": "70% within 4 s after a quote update, 30% uniform in trailing hour; "
            "price 35% ask, 35% bid, 15% inside, 7% one tick beyond touch, 8% near mid; size 1..100; 2% multiplier 10",
            "short_dte_max_days": workload.SHORT_DTE_MAX_DAYS, "input_fingerprint_sha256": fingerprint, "spec": spec._asdict(),
            "families": list(workload.FAMILIES)},
        "budgets": BUDGET, "protocol": "single worker in-process, warm-up %d, repeats %d, compute-only (inputs prebuilt and excluded), nearest-rank percentiles" % (a.warmups, a.repeats),
        "max_workers": a.max_workers,
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(ROOT)).stdout.strip(),
        "git_dirty": bool(subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(ROOT)).stdout.strip())}
    rep["frozen"] = frozen
    print(json.dumps(frozen, indent=1, sort_keys=True, default=str))


def phase_g0(a, rep):
    spec = b6_spec()
    synth = {}
    rss0 = R.peak_rss_bytes()
    inp = workload.build_inputs(spec, KEY, None, synth)
    fp = hashlib.sha256(repr((inp.records, inp.prints, inp.share_prints, inp.spot)).encode()).hexdigest()
    if fp != rep["frozen"]["workload"]["input_fingerprint_sha256"]:
        sys.exit("workload changed since freeze (input fingerprint differs); re-freeze before measuring")
    rss_inputs = R.peak_rss_bytes()
    gc.collect()
    for _ in range(a.warmups):
        workload.compute_from_inputs(spec, inp)
    samples, fams, hashes = [], {f: [] for f in workload.FAMILIES}, set()
    for _ in range(a.repeats):
        tm = {}
        t0 = time.perf_counter()
        data = workload.compute_from_inputs(spec, inp, tm)
        samples.append(time.perf_counter() - t0)
        hashes.add(hashlib.sha256(data).hexdigest())
        for f in workload.FAMILIES:
            fams[f].append(tm[f])
    p50, p95, mx = mb.pct(samples, 50), mb.pct(samples, 95), max(samples)
    breakdown = {f: {"p50_s": mb.pct(v, 50), "p95_s": mb.pct(v, 95), "max_s": max(v), "share_of_total_p50": mb.pct(v, 50) / p50} for f, v in fams.items()}
    out = {"budget": BUDGET["B6"], "unit": KEY, "repeats": len(samples), "warmups": a.warmups, "compute_only": {
        "p50_s": p50, "p95_s": p95, "max_s": mx, "samples_s": samples, "verdict_p95": verdict(p95), "hard_ok": p95 <= 15},
        "result_bytes": len(data), "result_sha256_all_repeats_equal": len(hashes) == 1, "result_sha256": sorted(hashes)[0],
        "breakdown_s": breakdown, "breakdown_sum_p50_s": sum(b["p50_s"] for b in breakdown.values()),
        "input_synthesis_s_reported_separately": {**synth, "total_s": sum(synth.values()),
                                                  "note": "history = quote history of the session up to the cutoff (generator); chain = chain rows; prints = frozen trade stream; prep = conversion into library input shapes. Excluded from compute-only."},
        "peak_memory_bytes_single_worker": {"process_peak_working_set": R.peak_rss_bytes(), "before_inputs": rss0, "after_inputs": rss_inputs,
                                            "b9": "2 GB budget, 4 GB hard"}}
    # one wall figure including input synthesis, as one process would run a single fresh unit (informational)
    t0 = time.perf_counter()
    workload.compute_unit(spec, KEY)
    out["fresh_unit_wall_incl_synthesis_s_informational"] = time.perf_counter() - t0
    rep["g0"] = out
    print("M2-G0 compute-only 1 worker: p50 %.3f s  p95 %.3f s  max %.3f s (n=%d, warm-up %d) -> %s" % (p50, p95, mx, len(samples), a.warmups, out["compute_only"]["verdict_p95"]))
    for f, b in breakdown.items():
        print("  %-12s p50 %.4f s  p95 %.4f s  %5.1f%%" % (f, b["p50_s"], b["p95_s"], 100 * b["share_of_total_p50"]))
    print("  sum of family p50 %.3f s; input synthesis (excluded) %.2f s; peak working set %.0f MB; hashes equal across repeats: %s" % (
        out["breakdown_sum_p50_s"], sum(synth.values()), R.peak_rss_bytes() / 1e6, out["result_sha256_all_repeats_equal"]))


def phase_scale(a, rep):
    if "g0" not in rep:
        sys.exit("run --phase g0 first (efficiency is relative to its p50)")
    base = rep["g0"]["compute_only"]["p50_s"]
    out = {"note": "informational, not a gate: n units (SYN1..5 x sessions, cutoff %d) run concurrently, one per worker; per-unit compute-only seconds from the worker timing, run wall includes input synthesis. efficiency = single-worker compute p50 / per-unit compute p50 at n workers" % CUTOFF, "workers": {}}
    rep["scale"] = out
    conc = Spec(shape="M", underlyings=("SYN1", "SYN2", "SYN3", "SYN4", "SYN5"), sessions=(1, 2, 3, 4, 5), cutoffs=(CUTOFF,), gating="valid")
    for n in (2, 4, a.n):
        keys = workload.all_unit_keys(conc)[:n]
        spec = Spec(**{**conc._asdict(), "underlyings": tuple(sorted({k.split("/")[0] for k in keys}))})
        with mb.make_runner(n, a) as r:
            ref = None
            r.run(spec, batch_size=1)  # warm-up
            unit_s, walls, rss, synth, shas = [], [], [], [], set()
            for _ in range(a.repeats):
                res = r.run(spec, batch_size=1)
                walls.append(res.log["wall_s"])
                for c in res.log["chunk_wall_s"]:
                    unit_s.append(c["timing"]["compute_s"])
                    synth.append(c["history_s"] + c["timing"]["synth_chain_s"] + c["timing"]["synth_prints_s"] + c["timing"]["synth_prep_s"])
                rss.append(res.log["peak_rss_per_worker_bytes"])
                shas.add(res.result_sha256)
            p50 = mb.pct(unit_s, 50)
            out["workers"][str(n)] = {
                "workers_used": res.log["workers_used"], "units_per_run": res.unit_count, "repeats": a.repeats, "per_unit_compute_p50_s": p50,
                "per_unit_compute_p95_s": mb.pct(unit_s, 95), "per_unit_compute_max_s": max(unit_s), "efficiency": base / p50,
                "run_wall_p50_s": mb.pct(walls, 50), "run_wall_p95_s": mb.pct(walls, 95), "run_wall_max_s": max(walls),
                "input_synthesis_per_unit_p50_s": mb.pct(synth, 50), "peak_rss_per_worker_bytes_max": max(max(x) for x in rss),
                "hash_stable_across_repeats": len(shas) == 1, "result_sha256": sorted(shas)[0],
                "verdict_unit_p95_informational": verdict(mb.pct(unit_s, 95))}
            print("scale n=%d per-unit compute p50 %.2f p95 %.2f max %.2f efficiency %.2f; run wall p50 %.1f s; peak RSS/worker %.0f MB; hash stable %s" % (
                n, p50, mb.pct(unit_s, 95), max(unit_s), base / p50, mb.pct(walls, 50), max(max(x) for x in rss) / 1e6, len(shas) == 1), flush=True)
            mb.save(a.report, rep)


def phase_matrix(a, rep):
    mb.phase_matrix(a, rep)


def phase_arb(a, rep):
    mb.phase_arb(a, rep)


PHASES = {"freeze": phase_freeze, "g0": phase_g0, "scale": phase_scale, "matrix": phase_matrix, "arb": phase_arb}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--phase", required=True, choices=sorted(PHASES))
    ap.add_argument("--n", type=int, default=0, help="N workers for the N-worker runs (0 = min(runner cap, --max-workers))")
    ap.add_argument("--max-workers", type=int, default=24)
    ap.add_argument("--repeats", type=int, default=30)
    ap.add_argument("--warmups", type=int, default=2)
    ap.add_argument("--b9-peak-bytes", type=int, default=R.B9_BUDGET_BYTES)
    ap.add_argument("--aggregate-hard-bytes", type=int, default=None)
    ap.add_argument("--cores", type=int, default=None)
    ap.add_argument("--timeout-s", type=float, default=3600.0)
    ap.add_argument("--underlying", default="SYN1")
    ap.add_argument("--matrix-cutoffs", type=int, default=78)
    a = ap.parse_args()
    if a.repeats < 30:
        print("note: protocol asks for >= 30 timed repeats; %d is a smoke run, not a gate result" % a.repeats)
    cap = R.worker_cap(a.cores, None, a.b9_peak_bytes, a.aggregate_hard_bytes)["cap"]
    if a.n == 0:
        a.n = min(cap, a.max_workers)
    a.n = min(a.n, a.max_workers)
    rep = mb.load(a.report)
    if a.phase != "freeze" and "frozen" not in rep:
        sys.exit("run --phase freeze first: machine and workload are frozen before the first measured run")
    PHASES[a.phase](a, rep)
    rep.setdefault("phases_done", []).append(a.phase)
    mb.save(a.report, rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
