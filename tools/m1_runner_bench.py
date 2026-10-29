#!/usr/bin/env python3
"""Heavy measurements for the opt-in process-pool runner (not a CI test). Label: synthetic workload, relative
engineering budget; no claim about recorded data. See docs/M1_RUNNER.md.

Phases (python tools/m1_runner_bench.py --report R.json --phase NAME [options]); each phase appends to the report:
  freeze   machine and workload facts, written BEFORE the first measured run (no changes between runs)
  matrix   identical-hash matrix: B12-style set (one underlying, one session, all cutoffs by default) at 1, 2, 4, N
           workers, 3 repeats each, plus batch sizes and unit orderings, all compared with the 1-worker reference
  scaling  speedup, efficiency, units/s, RSS at 1, 2, 4 (S01: 5 underlyings, one session) and a larger curve
  b6       one underlying, size M, one cutoff, valid-quote chains: 1 worker (>= 30 repeats, p50/p95) and N concurrent units
  b7       whole workload (5 underlyings x 5 sessions x 78 cutoffs, size M) ONCE at N workers; or --subset 10 for a
           stated proportional 1/10 subset, reported as 'extrapolated'
  arb      untimed counter run: arb enclosure calls per solve (counters stay outside results)
Budgets are printed verbatim from qualification/synthetic/perf/PERF_ACCEPTANCE.md.
"""
import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools")]
import m1_runner  # noqa: E402
from m1_runner import Runner, Spec  # noqa: E402
from m1_runner import runner as R  # noqa: E402

LABEL = "synthetic workload, relative engineering budget"
BUDGET = {"B6": "<= 5 s p95, hard 15 s (all outputs, 1 underlying, size M, 1 cutoff)",
          "B7": "<= 170 min, hard 240 min (5 x 5 x 78 cutoffs, size M, run once; under 10 min on 8 cores is reported, not promised)",
          "B9": "<= 2 GB per process, hard 4 GB per process; cap uses the 2 GB budget, aggregate limit 50 percent of host RAM (configurable)",
          "S01": "speedup at 4 workers >= 2.0x on multi-underlying work (5 underlyings)"}
GIB = 1 << 30


def pct(samples, p):
    s = sorted(samples)
    return s[max(1, math.ceil(p / 100 * len(s))) - 1]


def ps(cmd):
    try:
        return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception:
        return None


def machine():
    import flint
    info = {"platform": platform.platform(), "python": sys.version, "executable": sys.executable, "python_flint": flint.__version__,
            "logical_cores": os.cpu_count(), "ram_bytes": R.system_ram_bytes(), "label": LABEL}
    if os.name == "nt":
        info["cpu_name"] = ps("(Get-CimInstance Win32_Processor | Select -First 1).Name")
        info["physical_cores"] = R.physical_cores()
        info["sockets"] = ps("(Get-CimInstance Win32_Processor | Measure-Object).Count")
        info["power_plan"] = ps("powercfg /getactivescheme")
        info["cpu_load_percent_before"] = ps("(Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average")
        info["os_build"] = ps("(Get-CimInstance Win32_OperatingSystem).BuildNumber")
    info["pythonhashseed_in_workers"] = R.HASHSEED
    return info


def spread(n, last=77):
    return tuple(sorted({round(i * last / (n - 1)) for i in range(n)})) if n > 1 else (last // 2,)


def load(path):
    return json.loads(Path(path).read_text()) if Path(path).exists() else {}


def save(path, report):
    Path(path).write_text(json.dumps(report, indent=1, sort_keys=True, default=str), encoding="utf-8")


def summarize_run(res):
    lg = res.log
    return {"wall_s": lg["wall_s"], "units_per_s": lg["units_per_s"], "workers_used": lg["workers_used"], "batch_size": lg["batch_size"],
            "chunks": lg["chunks"], "peak_rss_per_worker_bytes": lg["peak_rss_per_worker_bytes"],
            "aggregate_peak_rss_bytes": lg["aggregate_peak_rss_bytes"], "result_sha256": res.result_sha256}


def make_runner(workers, a, **kw):
    return Runner(workers=workers, b9_peak_bytes=a.b9_peak_bytes, aggregate_hard_bytes=a.aggregate_hard_bytes,
                  cores=a.cores, timeout_s=a.timeout_s, **kw)


def phase_freeze(a, rep):
    spec = Spec(shape="M")
    manifest = (ROOT / "qualification/synthetic/perf/perf_manifest.json").read_bytes()
    rep["frozen"] = {"machine": machine(), "workload": {
        "label": LABEL, "perf_manifest_sha256": hashlib.sha256(manifest).hexdigest(), "seed": spec.seed, "shape": "M",
        "units_b7": len(m1_runner.workload.all_unit_keys(spec)), "contracts_per_chain": m1_runner.workload.chain_size("M"),
        "spec": spec._asdict()}, "runner": {"b9_peak_bytes_used_for_cap": a.b9_peak_bytes, "aggregate_hard_bytes": a.aggregate_hard_bytes,
                                           "N": a.n}, "budgets": BUDGET,
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=str(ROOT)).stdout.strip()}
    print(json.dumps(rep["frozen"], indent=1, sort_keys=True, default=str))


def phase_matrix(a, rep):
    spec = Spec(shape="M", underlyings=(a.underlying,), sessions=(1,), cutoffs=tuple(range(a.matrix_cutoffs)))
    out = {"spec": spec._asdict(), "units": len(m1_runner.workload.all_unit_keys(spec)), "runs": []}
    rep["matrix"] = out
    ref = None
    for n in [1, 2, 4, a.n]:
        with make_runner(n, a) as r:
            for rep_i in range(3):
                res = r.run(spec)
                row = dict(workers_requested=n, repeat=rep_i + 1, **summarize_run(res))
                if ref is None:
                    ref = res.result_sha256
                row["equals_single_process_reference"] = res.result_sha256 == ref
                out["runs"].append(row)
                print("matrix workers %d repeat %d wall %.1f s hash %s equal=%s" % (n, rep_i + 1, row["wall_s"], res.result_sha256[:16], row["equals_single_process_reference"]), flush=True)
                save(a.report, rep)
    out["reference_sha256"] = ref
    with make_runner(4, a) as r:  # batch sizes and unit orderings at 4 workers (one run each)
        out["batch_order_runs"] = []
        for batch, order in ((1, "natural"), (7, "reversed"), (16, "shuffle:11"), (1000, "shuffle:5")):
            res = r.run(spec, batch_size=batch, order=order)
            row = dict(batch_requested=batch, order=order, **summarize_run(res), equals_single_process_reference=res.result_sha256 == ref)
            out["batch_order_runs"].append(row)
            print("batch %s order %s equal=%s" % (batch, order, row["equals_single_process_reference"]), flush=True)
    spec2 = Spec(**{**spec._asdict(), "contract_order": "shuffle:3"})
    with make_runner(a.n, a) as r:
        res = r.run(spec2)
        out["shuffled_contract_order_equal"] = res.result_sha256 == ref
    out["all_identical"] = all(x["equals_single_process_reference"] for x in out["runs"] + out["batch_order_runs"]) and out["shuffled_contract_order_equal"]
    print("matrix all identical:", out["all_identical"])


def phase_scaling(a, rep):
    out = {"s01": {"budget": BUDGET["S01"]}, "curve": {}}
    rep["scaling"] = out
    s01 = Spec(shape="M", sessions=(1,), cutoffs=spread(8, 74))
    walls = {}
    for n in (1, 2, 4):
        with make_runner(n, a) as r:
            runs = [summarize_run(r.run(s01)) for _ in range(3)]
        walls[n] = [x["wall_s"] for x in runs]
        out["s01"][str(n)] = {"runs": runs, "p50_wall_s": pct(walls[n], 50)}
        print("S01 workers %d walls %s" % (n, [round(w, 1) for w in walls[n]]), flush=True)
        save(a.report, rep)
    out["s01"]["units"] = 40
    out["s01"]["speedup_4_vs_1"] = pct(walls[1], 50) / pct(walls[4], 50)
    out["s01"]["efficiency_4"] = out["s01"]["speedup_4_vs_1"] / 4
    out["s01"]["speedup_2_vs_1"] = pct(walls[1], 50) / pct(walls[2], 50)
    out["s01"]["meets_2_0x"] = out["s01"]["speedup_4_vs_1"] >= 2.0
    curve = Spec(shape="M", cutoffs=spread(6, 73))
    out["curve"]["units"] = 150
    cw = {}
    for n, repeats in [(1, 1)] + [(w, 2) for w in a.curve]:
        with make_runner(n, a, **({} if n <= a.n else {})) as r:
            runs = [summarize_run(r.run(curve)) for _ in range(repeats)]
        cw[n] = pct([x["wall_s"] for x in runs], 50)
        out["curve"][str(n)] = {"runs": runs, "p50_wall_s": cw[n]}
        print("curve workers %d wall %.1f s" % (n, cw[n]), flush=True)
        save(a.report, rep)
    for n in cw:
        out["curve"][str(n)]["speedup"] = cw[1] / cw[n]
        out["curve"][str(n)]["efficiency"] = cw[1] / cw[n] / n
        out["curve"][str(n)]["units_per_s_p50"] = 150 / cw[n]


def phase_b6(a, rep):
    out = {"budget": BUDGET["B6"], "note": "valid-quote chains (gating=valid), size M, one underlying, cutoff 39; wall includes building the quote history up to the cutoff and the OC5/OC6 pass"}
    rep["b6"] = out
    one = Spec(shape="M", underlyings=("SYN1",), sessions=(1,), cutoffs=(39,), gating="valid")
    with make_runner(1, a) as r:
        r.run(one)  # warm-up, not counted
        logs = [r.run(one).log for _ in range(a.b6_repeats)]
    walls = [lg["wall_s"] for lg in logs]
    comp = [lg["wall_s"] - sum(c["history_s"] for c in lg["chunk_wall_s"]) for lg in logs]
    out["one_worker"] = {"repeats": len(walls), "p50_s": pct(comp, 50), "p95_s": pct(comp, 95), "max_s": max(comp), "samples_s": comp,
                         "basis": "wall excluding input synthesis (the quote-history generator), the B6 compute: IV, ATM, 30-day, OC5, OC6 for 2000 contracts",
                         "with_input_synthesis": {"p50_s": pct(walls, 50), "p95_s": pct(walls, 95), "max_s": max(walls), "samples_s": walls},
                         "verdict_p95": "within budget" if pct(comp, 95) <= 5 else ("over budget, within hard" if pct(comp, 95) <= 15 else "OVER HARD")}
    print("B6 1 worker p50 %.2f p95 %.2f max %.2f (n=%d)" % (out["one_worker"]["p50_s"], out["one_worker"]["p95_s"], out["one_worker"]["max_s"], len(walls)), flush=True)
    save(a.report, rep)
    n = a.n
    conc = Spec(shape="M", underlyings=("SYN1", "SYN2", "SYN3", "SYN4", "SYN5"), sessions=(1, 2, 3, 4, 5), cutoffs=(39,), gating="valid")
    keys = m1_runner.workload.all_unit_keys(conc)[:n]
    conc = Spec(**{**conc._asdict(), "underlyings": tuple(sorted({k.split("/")[0] for k in keys}))})
    # n units, one per worker (25 distinct sessions; the first n by key order), all at cutoff 39
    with make_runner(n, a) as r:
        r.run(conc, batch_size=1)
        unit_walls, run_walls, rss = [], [], []
        for _ in range(a.b6_repeats):
            res = r.run(conc, batch_size=1)
            run_walls.append(res.log["wall_s"])
            unit_walls += [c["wall_s"] - c["history_s"] for c in res.log["chunk_wall_s"]]
            rss.append(res.log["aggregate_peak_rss_bytes"])
        out["n_workers"] = {"workers": n, "units_per_run": res.unit_count, "repeats": len(run_walls),
                            "per_unit_wall_p50_s": pct(unit_walls, 50), "per_unit_wall_p95_s": pct(unit_walls, 95), "per_unit_wall_max_s": max(unit_walls),
                            "run_wall_p50_s": pct(run_walls, 50), "run_wall_p95_s": pct(run_walls, 95), "run_wall_max_s": max(run_walls),
                            "aggregate_peak_rss_bytes": max(rss), "peak_rss_per_worker_bytes": res.log["peak_rss_per_worker_bytes"],
                            "verdict_unit_p95": "within budget" if pct(unit_walls, 95) <= 5 else ("over budget, within hard" if pct(unit_walls, 95) <= 15 else "OVER HARD"),
                            "note": "%d units run concurrently (one per worker); per-unit wall (excluding input synthesis) is the B6 wall under %d-way concurrency" % (res.unit_count, n)}
    print("B6 N=%d per-unit p50 %.2f p95 %.2f max %.2f; run wall p50 %.2f" % (n, out["n_workers"]["per_unit_wall_p50_s"], out["n_workers"]["per_unit_wall_p95_s"], out["n_workers"]["per_unit_wall_max_s"], out["n_workers"]["run_wall_p50_s"]), flush=True)


def phase_b7(a, rep):
    spec = Spec(shape="M")
    keys = m1_runner.workload.all_unit_keys(spec)
    if a.subset > 1:   # proportional subset: every subset-th cutoff of every underlying x session (all 25 groups kept)
        spec = Spec(shape="M", cutoffs=tuple(range(0, 78, a.subset)))
    out = {"budget": BUDGET["B7"], "workers_requested": a.n, "n_subset": a.subset}
    rep["b7_N%d" % a.n] = out
    with make_runner(a.n, a) as r:
        t0 = time.perf_counter()
        res = r.run(spec, emit="digest")
        wall = time.perf_counter() - t0
    lg = res.log
    out.update(summarize_run(res))
    out.update({"units": res.unit_count, "wall_s": lg["wall_s"], "wall_min": lg["wall_s"] / 60, "worker_cap": lg["worker_cap"],
                "clamp": lg["clamp"], "physical_cores": rep["frozen"]["machine"].get("physical_cores"), "workers_vs_physical": "%d of %s" % (a.n, rep["frozen"]["machine"].get("physical_cores")),
                "cpu_s_sum": sum(c["cpu_s"] for c in lg["chunk_wall_s"]), "history_s_sum": sum(c["history_s"] for c in lg["chunk_wall_s"]), "chunk_count": len(lg["chunk_wall_s"])})
    out["utilisation_cpu_over_workers_x_wall"] = out["cpu_s_sum"] / (a.n * lg["wall_s"])
    out["input_synthesis_share_of_cpu"] = out["history_s_sum"] / out["cpu_s_sum"]
    out["wall_min_excluding_input_synthesis_estimate"] = out["wall_min"] * (1 - out["input_synthesis_share_of_cpu"])
    if a.subset > 1:
        out["extrapolated_full_wall_min"] = out["wall_min"] * len(keys) / res.unit_count
        out["label"] = "extrapolated (1/%d subset)" % a.subset
    print("B7 units %d workers %d wall %.1f s = %.2f min; aggregate RSS %.2f GB; units/s %.2f; hash %s" % (
        res.unit_count, lg["workers_used"], lg["wall_s"], lg["wall_s"] / 60, lg["aggregate_peak_rss_bytes"] / GIB, lg["units_per_s"], res.result_sha256[:16]), flush=True)


def phase_arb(a, rep):
    spec = Spec(shape="M", underlyings=("SYN1",), sessions=(1,), cutoffs=(10, 39, 70), gating="valid")
    with make_runner(1, a, count_arb=True) as r:
        res = r.run(spec)
    rep["arb"] = {"spec": spec._asdict(), "arb_calls_per_solve": res.log["arb_calls_per_solve"], "note": "untimed counter run; counters are log-only"}
    print("arb calls per solve", res.log["arb_calls_per_solve"]["mean"], flush=True)


PHASES = {"freeze": phase_freeze, "matrix": phase_matrix, "scaling": phase_scaling, "b6": phase_b6, "b7": phase_b7, "arb": phase_arb}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--phase", required=True, choices=sorted(PHASES))
    ap.add_argument("--n", type=int, default=0, help="N workers for the N-worker runs (0 = the cap: min(physical cores, 0.5 x RAM / 2 GB))")
    ap.add_argument("--b9-peak-bytes", type=int, default=R.B9_BUDGET_BYTES, help="B9 value used in the cap (the 2 GB budget)")
    ap.add_argument("--aggregate-hard-bytes", type=int, default=None, help="default 50 percent of host RAM")
    ap.add_argument("--cores", type=int, default=None)
    ap.add_argument("--timeout-s", type=float, default=3600.0)
    ap.add_argument("--underlying", default="SYN1")
    ap.add_argument("--matrix-cutoffs", type=int, default=78)
    ap.add_argument("--curve", type=lambda t: [int(x) for x in t.split(",")], default=[8, 16, 24])
    ap.add_argument("--b6-repeats", type=int, default=30)
    ap.add_argument("--subset", type=int, default=1)
    a = ap.parse_args()
    if a.n == 0:
        a.n = R.worker_cap(a.cores, None, a.b9_peak_bytes, a.aggregate_hard_bytes)["cap"]
    rep = load(a.report)
    if a.phase != "freeze" and "frozen" not in rep:
        sys.exit("run --phase freeze first: machine and workload are frozen before the first measured run")
    PHASES[a.phase](a, rep)
    rep.setdefault("phases_done", []).append(a.phase)
    save(a.report, rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
