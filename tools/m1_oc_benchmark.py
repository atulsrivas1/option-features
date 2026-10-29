#!/usr/bin/env python3
"""M1 story A benchmark: B2 (OC5, one contract) and B3 (OC6 window evaluation, linear in the window).

Label: synthetic workload, relative engineering budget. No claim about recorded data, live latency or vendor
feeds. Workload is generated here from a fixed seed (stdlib random); records are built before the timer starts.
Protocol (P1 style): one warm-up, then >= 30 timed repeats, nearest-rank p50/p95, all raw samples kept in the
JSON, budgets printed verbatim beside the measurement, machine recorded, single thread.

B2: OC5 for one contract (history of 10 updates + QuoteSize rows), budget p95 <= 50 us, hard <= 200 us.
    Measured two ways: (a) each call timed on its own (3000 calls per repeat set, p95 of calls),
    (b) per-contract time of the batched `oc5_many` (repeat time / contracts).
B3: OC6 for a 50-update window, budget p95 <= 200 us, hard <= 1 ms; also 500 and 5,000-update windows
    (hard <= 20 ms at 5,000), the 50-update window again with prices pre-converted to `Ticks` at ingest, and the linearity ratio time(5000)/time(500) (a linear algorithm gives about 10).

Usage: python tools/m1_oc_benchmark.py [--repeats 30] [--json out.json]
"""
import argparse
import json
import math
import os
import platform
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages" / "features" / "src"), str(ROOT / "packages" / "option-contracts" / "src")]
from option_features.imbalance import OC5Params, oc5, oc5_many  # noqa: E402
from option_features.quotehist import QuoteSize, QuoteUpdate, as_ticks  # noqa: E402
from option_features.spreadwin import OC6Params, oc6, oc6_many  # noqa: E402

LABEL = "synthetic workload, relative engineering budget"
QUAL = "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12"
NS = 10 ** 9
OPEN = -18000 * NS


def nearest_rank(ordered, p):
    return ordered[max(1, math.ceil(p / 100 * len(ordered))) - 1]


def dec(t):
    return "%d.%04d" % (t // 10000, t % 10000)


def oc5_contract(rng):
    ups, sizes = [], []
    for i in range(10):
        e = -(10 - i) * NS // 2
        half = rng.choice((200, 250, 300, 500))
        mid = 10 * 10000 + rng.randint(0, 40)
        ups.append(QuoteUpdate(i + 1, e, e, dec(mid - half), dec(mid + half), True, None))
        sizes.append(QuoteSize(i + 1, rng.randint(1, 900), rng.randint(1, 900)))
    return (0, ups, sizes, True)


def oc6_window(rng, n):
    """n updates evenly over the last 300 s; a handful of distinct spreads, midpoints drift (many distinct sums)."""
    step = 300 * NS // n
    ups = []
    for i in range(n):
        e = -300 * NS + i * step
        half = rng.choice((200, 250, 300, 500))
        mid = 10 * 10000 + rng.randint(0, 400)
        ups.append(QuoteUpdate(i + 1, e, e, dec(mid - half), dec(mid + half), True, None))
    return ups


def to_tick_updates(ups):
    """Same updates with prices converted once to Ticks (the ingest-time conversion)."""
    return [u._replace(bid=as_ticks(u.bid), ask=as_ticks(u.ask)) for u in ups]


def machine():
    info = {"cpu": platform.processor(), "logical_cores": os.cpu_count(), "python": sys.version, "os": platform.platform()}
    if os.name == "nt":
        import subprocess
        try:
            info["cpu_detail"] = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-CimInstance Win32_Processor | Select-Object -First 1 Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json -Compress"],
                capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception as exc:
            info["cpu_detail"] = "n/a (%s)" % type(exc).__name__
    return info


def summarize(samples_ns):
    ordered = sorted(samples_ns)
    return {"p50_us": nearest_rank(ordered, 50) / 1e3, "p95_us": nearest_rank(ordered, 95) / 1e3, "max_us": ordered[-1] / 1e3}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=30)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()
    if args.repeats < 30:
        print("note: protocol asks for >= 30 timed repeats; %d is a smoke run, not a gate result" % args.repeats)
    rng = random.Random(20261029)
    report = {"qualification_label": QUAL, "label": LABEL, "repeats": args.repeats, "machine": machine()}
    print(QUAL)
    print("M1 story A benchmark (%s)" % LABEL)
    clock = time.perf_counter_ns

    # B2: OC5 one contract
    contracts = [oc5_contract(rng) for _ in range(1000)]
    params = OC5Params()
    for t, u, s, c in contracts:  # warm-up
        oc5(u, s, t, params, c)
    oc5_many(contracts, params)
    single = []
    for _ in range(args.repeats):
        for t, u, s, c in contracts[:100]:
            a = clock()
            oc5(u, s, t, params, c)
            single.append(clock() - a)
    batch = []
    for _ in range(args.repeats):
        a = clock()
        oc5_many(contracts, params)
        batch.append((clock() - a) // len(contracts))
    b2s, b2b = summarize(single), summarize(batch)
    print("B2 budget: OC5 one contract p95 <= 50 us, hard <= 200 us")
    print("  single calls (%d samples): p50 %.2f us  p95 %.2f us  max %.1f us | %s"
          % (len(single), b2s["p50_us"], b2s["p95_us"], b2s["max_us"], "PASS" if b2s["p95_us"] <= 50 else "BUDGET MISS"))
    print("  oc5_many per contract (%d repeats x %d): p50 %.2f us  p95 %.2f us" % (args.repeats, len(contracts), b2b["p50_us"], b2b["p95_us"]))
    report["B2"] = {"single_call": b2s, "oc5_many_per_contract": b2b, "budget_p95_us": 50, "hard_p95_us": 200,
                    "single_samples_ns": single, "batch_per_contract_samples_ns": batch}

    # B3: OC6 windows
    p6 = OC6Params()
    report["B3"] = {"budget_us": {"50": 200}, "hard_us": {"50": 1000, "5000": 20000}}
    print("B3 budget: OC6 50-update window p95 <= 200 us, hard <= 1 ms; 5,000-update window hard <= 20 ms")
    p50s = {}
    for n, reps_inner in ((50, 200), (500, 20), (5000, 3)):
        wins = [oc6_window(rng, n) for _ in range(reps_inner)]
        for u in wins:
            oc6(u, 0, OPEN, p6)  # warm-up
        samples = []
        for _ in range(args.repeats):
            for u in wins:
                a = clock()
                r = oc6(u, 0, OPEN, p6)
                samples.append(clock() - a)
        assert r.status in ("fired", "not_fired"), r
        s = summarize(samples)
        p50s[n] = s["p50_us"]
        lim = {50: (200, 1000), 500: (None, None), 5000: (None, 20000)}[n]
        verdict = ""
        if lim[0]:
            verdict = "PASS" if s["p95_us"] <= lim[0] else ("BUDGET MISS (hard met)" if s["p95_us"] <= lim[1] else "HARD BREACH")
        elif lim[1]:
            verdict = "hard met" if s["p95_us"] <= lim[1] else "HARD BREACH"
        print("  window %-5d: p50 %.1f us  p95 %.1f us  max %.1f us | %.3f us per update at p50 | %s"
              % (n, s["p50_us"], s["p95_us"], s["max_us"], s["p50_us"] / n, verdict))
        report["B3"][str(n)] = dict(s, samples_ns=samples)
    wins = [to_tick_updates(oc6_window(rng, 50)) for _ in range(200)]
    for u in wins:
        oc6(u, 0, OPEN, p6)
    samples = []
    for _ in range(args.repeats):
        for u in wins:
            a = clock()
            oc6(u, 0, OPEN, p6)
            samples.append(clock() - a)
    s = summarize(samples)
    print("  window 50 with prices pre-converted to Ticks at ingest: p50 %.1f us  p95 %.1f us  max %.1f us" % (s["p50_us"], s["p95_us"], s["max_us"]))
    report["B3"]["50_ticks_preconverted"] = dict(s, samples_ns=samples)
    ratio = p50s[5000] / p50s[500]
    report["B3"]["linearity_5000_over_500_p50"] = ratio
    print("  linearity time(5000)/time(500) at p50 = %.2f (linear gives about 10; budget: linear in the window)" % ratio)
    batch6 = [(0, oc6_window(rng, 50), OPEN) for _ in range(500)]
    oc6_many(batch6, p6)
    per = []
    for _ in range(args.repeats):
        a = clock()
        oc6_many(batch6, p6)
        per.append((clock() - a) // len(batch6))
    s = summarize(per)
    print("  oc6_many 50-update windows per contract: p50 %.1f us  p95 %.1f us" % (s["p50_us"], s["p95_us"]))
    report["B3"]["oc6_many_50_per_contract"] = s
    print("machine: %s" % json.dumps(report["machine"]))
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
