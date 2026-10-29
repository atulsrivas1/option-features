"""Chain IV benchmark: B4 (chain ATM IV), B5 (30-day IV), B6 (per-contract IV for every contract + ATM + 30-day).

Label: synthetic workload, relative engineering budget (no claim about recorded data). Real measurements of
option_features.chainiv on synthetic chains; budgets are the Tester's proposals in
qualification/synthetic/perf/PERF_ACCEPTANCE.md (pass uses p95, nearest-rank percentiles, one warm-up run
not counted). One worker, library single-threaded. What is timed per repeat: IVChain construction from raw
contracts (parsing, gates, strike indexes) plus the call(s); nothing else. Not timed: workload generation.

Chain layouts are exactly gen_perf_workloads.CHAIN_SIZES / chain_contract (S 500, M 2000, L 6000 contracts).
Prices are Black-Scholes mids from a smooth smile (rounded to 4 places, +/-0.001), r = 0.03, q = 0.01,
spot 100, cutoff 0, quotes 2 s old. B6 here is the IV part of "all outputs" only (the other outputs are
other stories); see the report for what that means for the gate.

B4/B5 count only ATM and 30-day solves (PO ruling): ATM is solved for EVERY listed expiry (B4), the 30-day
value for the bracketing expiries only (B5). B6 includes per-contract IV for every contract.

Usage: python tools/m1_chain_benchmark.py [--repeats 30] [--sizes S,M,L] [--b6-sizes M] [--out report.json]
Counters (arb enclosure calls) come from a separate untimed run with call counting wrappers.
"""
import argparse
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "qualification" / "synthetic" / "perf")]
import gen_perf_workloads as gen  # noqa: E402
from option_features import chainiv, inverse  # noqa: E402

BUDGETS = {  # (budget s, hard s)
    ("B4", "M"): (1.0, 3.0), ("B4", "L"): (4.0, 10.0), ("B5", "M"): (1.5, 4.0), ("B6", "M"): (5.0, 15.0)}
SPOT, RATE, DIV = 100.0, 0.03, 0.01


def _ncdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def bs(right, K, T, sigma):
    A, B = SPOT * math.exp(-DIV * T), K * math.exp(-RATE * T)
    d1 = (math.log(SPOT / K) + (RATE - DIV + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return A * _ncdf(d1) - B * _ncdf(d2) if right == "call" else B * _ncdf(-d2) - A * _ncdf(-d1)


def make_chain(size, all_european=False):
    rows = []
    for i in range(gen.chain_size(size)):
        m = gen.chain_contract(size, i)
        K, days, right = float(m["strike"]), m["expiry_days"], "call" if m["right"] == "C" else "put"
        sigma = 0.20 + 0.08 * math.log(K / SPOT) ** 2 * 10 + 0.02 * math.sqrt(days / 365.0) + (0.004 if right == "put" else 0.0)
        mid = round(bs(right, K, days / 365.0, sigma), 4)
        bid, ask = max(mid - 0.001, 0.0), mid + 0.001
        rows.append(chainiv.ChainContract("%dd-%s-%s" % (days, m["right"], m["strike"]), days, right, m["strike"],
                                          "%.4f" % bid, "%.4f" % ask, -2_000_000_000, -2_000_000_000,
                                          "european" if all_european else m["style"]))
    return rows


def run_b4(rows):
    return chainiv.IVChain(rows, "100.0000", "0.0300", "0.0100", 0).atm_iv_all()


def run_b5(rows):
    return chainiv.IVChain(rows, "100.0000", "0.0300", "0.0100", 0).iv_30d(30)


def run_b6(rows):
    chain = chainiv.IVChain(rows, "100.0000", "0.0300", "0.0100", 0)
    return chain.contract_iv(), chain.atm_iv_all(), chain.iv_30d(30)


def pct(sorted_samples, p):
    k = max(1, math.ceil(p / 100.0 * len(sorted_samples)))
    return sorted_samples[k - 1]


def measure(fn, rows, repeats, budget_total_s):
    fn(rows)  # warm-up, not counted
    samples, started = [], time.perf_counter()
    while len(samples) < repeats:
        t0 = time.perf_counter()
        fn(rows)
        samples.append(time.perf_counter() - t0)
        if len(samples) >= 5 and time.perf_counter() - started > budget_total_s:
            break
    s = sorted(samples)
    return {"repeats": len(samples), "p50_s": pct(s, 50), "p95_s": pct(s, 95), "max_s": s[-1], "min_s": s[0],
            "samples_s": [round(x, 5) for x in samples]}


def counters(fn, rows):
    """Untimed run counting arb enclosure work (price enclosures, forward/vega, bounds) and solves."""
    n = {"price_interval": 0, "forward": 0, "bounds": 0, "solves": 0}
    real = (inverse.price_interval, inverse.forward, inverse.bounds, inverse.solve)

    def wrap(name, f):
        def g(*a, **k):
            n[name] += 1
            return f(*a, **k)
        return g
    inverse.price_interval, inverse.forward, inverse.bounds = (wrap("price_interval", real[0]), wrap("forward", real[1]), wrap("bounds", real[2]))
    solves = {"n": 0}
    real_chain_solve = chainiv.solve

    def counted_solve(*a, **k):
        solves["n"] += 1
        return real_chain_solve(*a, **k)
    chainiv.solve = counted_solve
    try:
        fn(rows)
    finally:
        inverse.price_interval, inverse.forward, inverse.bounds = real[:3]
        chainiv.solve = real_chain_solve
    n["solves"] = solves["n"]
    n["arb_enclosure_calls"] = n["price_interval"] + n["forward"] + n["bounds"]
    n["arb_calls_per_solve"] = round(n["arb_enclosure_calls"] / n["solves"], 2) if n["solves"] else None
    return n


def machine():
    info = {"platform": platform.platform(), "python": platform.python_version(), "cpu_count": os.cpu_count(),
            "processor": platform.processor()}
    try:
        info["cpu_name"] = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"],
                                          capture_output=True, text=True, timeout=30).stdout.strip()
        info["power_plan"] = subprocess.run(["powershell", "-NoProfile", "-Command", "powercfg /getactivescheme"],
                                            capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        pass
    try:
        import flint
        info["python_flint"] = flint.__version__
    except Exception:
        pass
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=30)
    ap.add_argument("--sizes", default="M,L")
    ap.add_argument("--b6-sizes", default="M")
    ap.add_argument("--max-seconds", type=float, default=240.0, help="stop repeating one measurement after this long (min 5 repeats)")
    ap.add_argument("--all-european", action="store_true",
                    help="every contract european, so no american-ITM gate skips a solve (Stage 2 'valid quotes everywhere' chain)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    report = {"label": "synthetic workload, relative engineering budget (no claim about recorded data); single worker",
              "machine": machine(), "results": []}
    print(report["label"]); print(json.dumps(report["machine"]))
    plan = []
    for size in a.sizes.split(","):
        plan.append(("B4" if size == "M" else "B4" if size == "L" else "B4", size, run_b4))
        plan.append(("B5", size, run_b5))
    for size in a.b6_sizes.split(","):
        plan.append(("B6", size, run_b6))
    chains = {}
    for gate, size, fn in plan:
        rows = chains.setdefault(size, make_chain(size, a.all_european))
        r = measure(fn, rows, a.repeats, a.max_seconds)
        r.update(gate=gate, size=size, contracts=len(rows), counters=counters(fn, rows))
        budget = BUDGETS.get((gate, size))
        if budget:
            r["budget_s"], r["hard_s"] = budget
            r["verdict_p95"] = "within budget" if r["p95_s"] <= budget[0] else ("over budget, within hard limit" if r["p95_s"] <= budget[1] else "OVER HARD LIMIT")
        report["results"].append(r)
        print("%s size %s (%d contracts): p50 %.3f s  p95 %.3f s  max %.3f s  n=%d  budget %s  | %s | %s" % (
            gate, size, len(rows), r["p50_s"], r["p95_s"], r["max_s"], r["repeats"],
            "%s/%s s" % budget if budget else "none (not a gate at this size)", r.get("verdict_p95", ""), json.dumps(r["counters"])))
    if a.out:
        Path(a.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
