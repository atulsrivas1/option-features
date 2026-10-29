#!/usr/bin/env python3
"""Command line of the opt-in process-pool runner (opt-in, default single-process; see docs/M1_RUNNER.md).

Usage: python tools/m1_runner/cli.py [--workers N] [--shape T|S|M|L] [--underlyings SYN1,SYN2] [--sessions 1-5]
       [--cutoffs 0-77] [--batch-size N] [--order natural|reversed|shuffle:K] [--contract-order ...]
       [--out DIR] [--emit digest|full] [--log FILE] [--b9-peak-bytes N] [--aggregate-hard-bytes N]
       [--cores N] [--ram-bytes N] [--timeout-s S] [--count-arb] [--fault KIND:ARGS]
Exit 0: success (stdout: result_sha256 and unit count only). Exit 2: named runner failure on stderr, no output files.
Synthetic workload, relative engineering budget.
"""
import argparse
import os
import sys

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]


def ints(text):
    out = []
    for part in text.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return tuple(out)


def parse_fault(text):
    if not text:
        return None
    kind, *args = text.split(":")
    if kind == "kill_worker" and len(args) == 2:
        return {"kind": kind, "worker": int(args[0]), "after_units": int(args[1])}
    if kind == "hang_worker" and len(args) == 1:
        return {"kind": kind, "worker": int(args[0])}
    if kind == "drop_unit" and len(args) == 1:
        return {"kind": kind, "unit_key": args[0]}
    raise SystemExit("bad --fault %r (kill_worker:W:N | hang_worker:W | drop_unit:KEY)" % text)


def main(argv=None):
    import m1_runner
    from m1_runner import runner as R
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--workers", type=int, default=m1_runner.DEFAULT_WORKERS, help="default 1 = in-process reference path")
    ap.add_argument("--shape", default="M")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--underlyings", default="SYN1,SYN2,SYN3,SYN4,SYN5")
    ap.add_argument("--sessions", default="1-5")
    ap.add_argument("--cutoffs", default="0-77")
    ap.add_argument("--contract-order", default="natural")
    ap.add_argument("--batch-size", type=int, default=None)
    ap.add_argument("--order", default="natural")
    ap.add_argument("--out", default=None)
    ap.add_argument("--emit", default="digest", choices=("digest", "full"))
    ap.add_argument("--log", default=None)
    ap.add_argument("--b9-peak-bytes", type=int, default=R.B9_BUDGET_BYTES)
    ap.add_argument("--aggregate-hard-bytes", type=int, default=None, help="default 50 percent of host RAM")
    ap.add_argument("--cores", type=int, default=None, help="physical cores (default detected)")
    ap.add_argument("--ram-bytes", type=int, default=None)
    ap.add_argument("--timeout-s", type=float, default=7200.0)
    ap.add_argument("--count-arb", action="store_true")
    ap.add_argument("--fault", default=None)
    a = ap.parse_args(argv)
    extra = {} if a.seed is None else {"seed": a.seed}
    spec = m1_runner.Spec(shape=a.shape, underlyings=tuple(a.underlyings.split(",")), sessions=ints(a.sessions),
                          cutoffs=ints(a.cutoffs), contract_order=a.contract_order, **extra)
    try:
        with m1_runner.Runner(workers=a.workers, b9_peak_bytes=a.b9_peak_bytes, aggregate_hard_bytes=a.aggregate_hard_bytes,
                              cores=a.cores, ram_bytes=a.ram_bytes, timeout_s=a.timeout_s, fault=parse_fault(a.fault),
                              count_arb=a.count_arb, log=a.log) as r:
            res = r.run(spec, batch_size=a.batch_size, order=a.order, emit=a.emit, out_dir=a.out)
    except m1_runner.RunnerError as e:
        print("%s: %s" % (type(e).__name__, e), file=sys.stderr)
        return 2
    print("result_sha256 %s units %d" % (res.result_sha256, res.unit_count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
