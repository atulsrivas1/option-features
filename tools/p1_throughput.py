#!/usr/bin/env python3
"""P1-T1 throughput benchmark: spread gate + touch-policy classification over the synthetic stream.

Label: synthetic workload, relative engineering budget. No claim about recorded data, live latency or
vendor feeds. The stream comes from qualification/synthetic/perf/gen_perf_workloads.py
(stream_record, seed 20261029); records are converted to tuples before the timer starts and the
timer wraps only option_features.quotes.classify_stream (monotonic ns clock, result serialization
excluded). Protocol from perf/PERF_ACCEPTANCE.md section 2: one warm-up run, then >= 30 timed
repeats, nearest-rank percentiles, all raw samples printed, budgets printed verbatim beside the
measurement, machine recorded. Single worker, single thread.

Gate P1-T1: records/s >= 100,000 (Budget, judged on the p95 repeat time) and >= 20,000 (Hard), for
streams of 1e5 and 1e6 records; time(1e6)/time(1e5) <= 12 (non-linearity).

Usage: python tools/p1_throughput.py [--repeats 30] [--sizes 100000,1000000] [--json out.json]
Imports the two package source trees of this checkout (no install needed).
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages" / "features" / "src"), str(ROOT / "packages" / "option-contracts" / "src")]
GEN = ROOT / "qualification" / "synthetic" / "perf" / "gen_perf_workloads.py"
SEED = 20261029
LABEL = "synthetic workload, relative engineering budget"
QUAL = "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12"
BUDGET_RATE, HARD_RATE, MAX_RATIO = 100_000, 20_000, 12


def load_generator():
    spec = importlib.util.spec_from_file_location("gen_perf_workloads", GEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stream_tuples(gen, n):
    """Record i as ('q', contract, t, bid, ask) or ('t', contract, t, price, size)."""
    out = []
    append = out.append
    record = gen.stream_record
    for i in range(n):
        r = record(SEED, n, i)
        if r["k"] == "q":
            append(("q", r["contract"], r["t_rel_ns"], r["bid"], r["ask"]))
        else:
            append(("t", r["contract"], r["t_rel_ns"], r["price"], r["size"]))
    return out


def nearest_rank(sorted_values, p):
    return sorted_values[max(1, math.ceil(p / 100 * len(sorted_values))) - 1]


def machine():
    info = {"cpu": platform.processor(), "logical_cores": os.cpu_count(), "python": sys.version, "os": platform.platform()}

    def run(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception as exc:
            return "n/a (%s)" % type(exc).__name__
    if os.name == "nt":
        info["cpu_detail"] = run(["powershell", "-NoProfile", "-Command",
                                  "Get-CimInstance Win32_Processor | Select-Object -First 1 Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json -Compress"])
        info["ram_bytes"] = run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
        info["power_plan"] = run(["powercfg", "/getactivescheme"])
        info["load_percent_now"] = run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average"])
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=30)
    ap.add_argument("--sizes", default="100000,1000000")
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    if args.repeats < 30:
        print("note: protocol asks for >= 30 timed repeats; %d is a smoke run, not a gate result" % args.repeats)
    from option_features import quotes
    gen = load_generator()
    report = {"qualification_label": QUAL, "label": LABEL, "gate": "P1-T1", "seed": SEED, "repeats": args.repeats, "machine": machine(), "sizes": {}}
    print(QUAL)
    print("P1-T1 (%s)" % LABEL)
    print("budget: >= %d records/s (p95 repeat), hard: >= %d records/s, ratio time(1e6)/time(1e5) <= %d" % (BUDGET_RATE, HARD_RATE, MAX_RATIO))
    medians = {}
    for n in (int(s) for s in args.sizes.split(",")):
        t0 = time.perf_counter()
        records = stream_tuples(gen, n)
        gen_s = time.perf_counter() - t0
        quotes.classify_stream(records)  # warm-up, not counted
        floor = []
        for _ in range(5):
            a = time.perf_counter_ns()
            for _r in records:
                pass
            floor.append(time.perf_counter_ns() - a)
        samples = []
        for _ in range(args.repeats):
            a = time.perf_counter_ns()
            result = quotes.classify_stream(records)
            samples.append(time.perf_counter_ns() - a)
        digest = hashlib.sha256(bytes(result.codes) + result.spread.tobytes() + result.mid2.tobytes()).hexdigest()
        ordered = sorted(samples)
        p50, p95, mx = nearest_rank(ordered, 50), nearest_rank(ordered, 95), ordered[-1]
        rate50, rate95 = n / (p50 / 1e9), n / (p95 / 1e9)
        medians[n] = p50
        verdict = "PASS" if rate95 >= BUDGET_RATE else ("BUDGET MISS (hard met)" if rate95 >= HARD_RATE else "HARD BREACH")
        report["sizes"][str(n)] = {
            "records": n, "quotes": result.quotes, "trades": result.trades, "generation_s_untimed": round(gen_s, 1),
            "p50_ns": p50, "p95_ns": p95, "max_ns": mx, "rate_p50": round(rate50), "rate_at_p95_time": round(rate95),
            "empty_loop_floor_ns_min": min(floor), "verdict": verdict, "result_sha256": digest, "samples_ns": samples,
            "codes_by_value": {str(c): result.count(c) for c in sorted(set(result.codes))},
        }
        print("n=%-8d p50 %.3f s  p95 %.3f s  max %.3f s  | %d rec/s at p50, %d rec/s at p95  | loop floor %.3f s | %s"
              % (n, p50 / 1e9, p95 / 1e9, mx / 1e9, rate50, rate95, min(floor) / 1e9, verdict))
        print("        result sha256 %s" % digest)
        del records
    if len(medians) == 2:
        small, large = sorted(medians)
        ratio = medians[large] / medians[small]
        report["time_ratio_large_over_small"] = ratio
        report["ratio_verdict"] = "PASS" if ratio <= MAX_RATIO else "FAIL"
        print("time(%d)/time(%d) = %.2f (budget <= %d): %s" % (large, small, ratio, MAX_RATIO, report["ratio_verdict"]))
    print("machine: %s" % json.dumps(report["machine"]))
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
