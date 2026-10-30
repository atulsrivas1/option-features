#!/usr/bin/env python3
"""SHA-256 of every output of the story B families over fixed inputs, to prove an alignment changed no output byte:
(1) every merged correctness row and additions row of the print families (full wire of the library answer),
(2) the random property scenarios (single, batched and sweep paths, lanes, filters, thresholds, F12 grids),
(3) the benchmark workloads (unit SYN1/21 78-cutoff sweeps of F1, F4, F17, F7, F18 and F12; the 1e5 rate stream shared pass).
Run it before and after a change with the same arguments; the digests must be identical.

Usage: python tools/m2b_output_hash.py [--json FILE]      (imports option_features from PYTHONPATH)
Label: synthetic workload, relative engineering budget. Synthetic fixtures only.
"""
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "m2"))
sys.path.insert(0, str(ROOT / "qualification" / "synthetic" / "m2" / "perf"))

from option_features import episodes as E, m2prints as M, printtape as PT  # noqa: E402
import m2b_adapter as A  # noqa: E402

NS = 10 ** 9
OPEN = 1_790_000_000 * NS


def wire(r):
    if isinstance(r, dict):
        w = M.to_wire(r)
    else:
        from option_features import flowresult
        w = flowresult.to_wire(r)
        if getattr(r, "ratio_reason", None):
            w["ratio_reason"] = r.ratio_reason
    return json.dumps(w, separators=(",", ":"), sort_keys=False)


class Digest:
    def __init__(self):
        self.h, self.n = hashlib.sha256(), 0

    def add(self, r):
        self.h.update((wire(r) + "\n").encode())
        self.n += 1

    def addj(self, o):
        self.h.update((json.dumps(o, sort_keys=True, separators=(",", ":")) + "\n").encode())
        self.n += 1

    def result(self):
        return {"outputs": self.n, "sha256": self.h.hexdigest()}


def rows():
    d = Digest()
    for _f, row in A.load_rows():
        d.addj({"id": row["id"], "got": A.run_row(row)})
    return d.result()


def campaigns():
    from test_m2b_properties import LANES, Scenario
    d = Digest()
    for seed in range(1, 25):
        sc = Scenario(seed)
        for lane in LANES:
            for flt in ("all", "calls", "puts"):
                for r in M.f1_sweep(sc.tape, sc.cuts, OPEN, n="3/2", flt=flt, lane=lane):
                    d.add(r)
            for r in M.f4_sweep(sc.tape, sc.cuts, window_s=900, threshold_ticks=5_000_000, n=2, lane=lane, open_ns=OPEN):
                d.add(r)
            for r in M.f7_sweep(sc.tape, sc.cuts, window_s=3600, lane=lane, open_ns=OPEN):
                d.add(r)
            for r in M.f18_sweep(sc.tape, sc.cuts, window_s=300, at_least="1/2", at_most="1/4", lane=lane, open_ns=OPEN):
                d.add(r)
            for row in M.f17_sweep(sc.tape, sc.cuts, sorted(sc.cons), lane=lane, open_ns=OPEN):
                for r in row:
                    d.add(r)
            d.addj(M.f17_sweep_columns(sc.tape, sc.cuts, sorted(sc.cons), lane=lane, open_ns=OPEN))
            for T in sc.cuts[:6]:
                d.add(M.f7_concentration(sc.tape, T, lane=lane, open_ns=OPEN))
                d.add(M.f4_large_prints(sc.tape, T, lane=lane, open_ns=OPEN, threshold_ticks=1))
                d.add(M.f18_put_share(sc.tape, T, lane=lane, open_ns=OPEN, at_least="0"))
        if seed <= 8:
            for lane in LANES:
                for r in E.f12_sweep(sc.tape, sc.cuts, OPEN, n=2, n_episodes=2, quiet_gap=3, lane=lane):
                    d.add(r)
    return d.result()


def workloads():
    import gen_m2_workloads as G
    d = Digest()
    prints = list(G.unit_prints(20261029, "SYN1", 21))
    lane = G.lane("SYN1")
    cons = {}
    for p in prints:
        if p[0] not in cons:
            r, s, e = G.contract(p[0])
            cons[p[0]] = (r, s, e, lane)
    tape = PT.build_tape(prints, cons)
    op = G.session_open_ns(21)
    cuts = [op + i * G.B_NS for i in range(1, 79)]
    for r in M.f1_sweep(tape, cuts, op, lane=lane):
        d.add(r)
    for r in M.f4_sweep(tape, cuts, threshold_ticks=G.LARGE_PREM, lane=lane, open_ns=op):
        d.add(r)
    for row in M.f17_sweep(tape, cuts, threshold_ticks=G.LARGE_PREM, lane=lane, open_ns=op):
        for r in row:
            d.add(r)
    for r in M.f7_sweep(tape, cuts, lane=lane, open_ns=op):
        d.add(r)
    for r in M.f18_sweep(tape, cuts, at_least="1/2", lane=lane, open_ns=op):
        d.add(r)
    for r in E.f12_sweep(tape, cuts, op, lane=lane):
        d.add(r)
    stream = list(G.stream_prints(20261029, 100_000))
    cons2 = {}
    for p in stream:
        if p[0] not in cons2:
            r, s, e = G.contract(p[0])
            cons2[p[0]] = (r, s, e, "stock")
    t2 = PT.build_tape(stream, cons2)
    sop = G.session_open_ns(1)
    T = sop + 21_600 * NS
    for r in (M.f1_premium_surge(t2, T, sop), M.f4_large_prints(t2, T, open_ns=sop), M.f7_concentration(t2, T, open_ns=sop),
              M.f18_put_share(t2, T, at_least="1/2", at_most="1/4", open_ns=sop), E.f12_from_tape(t2, T, sop)):
        d.add(r)
    for r in M.f17_many(t2, T, open_ns=sop):
        d.add(r)
    return d.result()


def main():
    out = {"rows": rows(), "campaigns": campaigns(), "workloads": workloads()}
    total = hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()
    out["overall_sha256"] = total
    print(json.dumps(out, indent=1, sort_keys=True))
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", newline="\n")


if __name__ == "__main__":
    main()
