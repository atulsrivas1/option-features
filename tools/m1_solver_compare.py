#!/usr/bin/env python3
"""M1 Stage 0 comparison and micro-benchmark harness for the IV solver (Developer evidence only).

Label: synthetic workload, relative engineering budget. No claim about recorded data or live latency.

Each solver run happens in a fresh subprocess against one checkout's source trees:
  compare  --base-root BASE --changed-root CHANGED [--n 10000]
           Generates the flat and mixed sets with qualification/synthetic/perf/gen_m1_solver_sets.py,
           runs option_features.inverse.solve at BASE (reference) and CHANGED for every contract, and
           asserts an identical sha256 of the full result (every InverseResult and SolverEvidence field)
           per contract, including status and closed reason of unsolvable contracts.
  bench    --base-root BASE --changed-root CHANGED [--subset 200] [--repeats 30]
           One warm-up pass, then >= 30 timed repeats of the solver over a fixed subset of the flat
           and mixed sets (sequential runs, never concurrent), nearest-rank p50/p95 per-contract time
           and solves/s, baseline vs changed (base and changed measured twice, interleaved).
  worker   (internal)
Usage: python tools/m1_solver_compare.py compare --base-root B --changed-root C
"""
import argparse
import dataclasses
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PERF = HERE.parent / "qualification" / "synthetic" / "perf"
LABEL = "synthetic workload, relative engineering budget"
SEED = 20261029


def contracts(kind, n):
    sys.path.insert(0, str(PERF))
    import gen_m1_solver_sets as g
    return [g.contract(SEED, kind, i) for i in range(n)]


def setup(root):
    sys.path[:0] = [str(Path(root) / "packages" / "features" / "src"), str(Path(root) / "packages" / "option-contracts" / "src")]
    from fractions import Fraction
    from decimal import Decimal
    from option_feature_contracts import SolverConfig, ConvertedOperands
    from option_features.arithmetic import numerical_owner, decimal_exact, nearest_binary64
    from option_features.model import Operands
    import option_features.inverse as inv
    cfg = SolverConfig("bisection1", "midpoint", 8.0, 256, 1e-10, 1e-10, 1e-10, 1e-10)

    def prepare(c):
        S, K = decimal_exact(Decimal(c["spot"])), decimal_exact(Decimal(c["strike"]))
        rate, carry = Fraction.from_float(float(c["rate"])), Fraction.from_float(float(c["div"]))
        T = Fraction(c["t_days"], 365)
        eta = 1 if c["right"] == "C" else -1
        ops = Operands(S, K, rate, carry, T, Fraction(0), eta)
        conv = ConvertedOperands(float(S), float(K), float(rate), float(carry), None, c["t_days"], nearest_binary64(T))
        return ops, decimal_exact(Decimal(c["price"])), conv
    return numerical_owner, inv.solve, prepare, cfg, inv.__file__


def canon(o):
    """Exact-field canonical form: floats via .hex(), Decimal/Fraction via str with type, arb balls via
    midpoint and radius at full precision (str(more=True) style), dataclasses field by field."""
    if dataclasses.is_dataclass(o):
        return [[f.name, canon(getattr(o, f.name))] for f in dataclasses.fields(o)]
    if isinstance(o, float):
        return o.hex()
    if isinstance(o, (list, tuple)):
        return [canon(x) for x in o]
    if isinstance(o, (bool, int, str)) or o is None:
        return o
    if type(o).__name__ in ("arb", "acb"):
        return [type(o).__name__, o.str(radius=True, more=True) if hasattr(o, "str") else str(o)]
    return [type(o).__name__, str(o)]


def run_one(owner_cm, solve, prep, cfg):
    ops, target, conv = prep
    with owner_cm() as o:
        return solve(ops, target, cfg, conv, o)


def worker(a):
    numerical_owner, solve, prepare, cfg, srcfile = setup(a.root)
    assert str(Path(a.root).resolve()).lower() in str(Path(srcfile).resolve()).lower(), "imported solver is not from --root"
    items = []
    for kind in ("flat", "mixed"):
        items += [(kind, c) for c in contracts(kind, a.n)]
    preps = [(k, c["i"], prepare(c)) for k, c in items]
    if a.wmode == "capture":
        out = {}
        for k, i, p in preps:
            try:
                r = run_one(numerical_owner, solve, p, cfg)
                rep, st, rs = json.dumps(canon(r), sort_keys=True), r.status, r.reason
            except Exception as e:  # recorded, must match too
                rep, st, rs = "EXC:" + repr(e), "exception", type(e).__name__
            out["%s:%06d" % (k, i)] = [hashlib.sha256(rep.encode()).hexdigest(), st, rs]
        json.dump(out, open(a.out, "w"), sort_keys=True)
    else:
        sub = [p for k, i, p in preps]
        for p in sub:
            run_one(numerical_owner, solve, p, cfg)  # warm-up (not counted)
        reps = []
        for _ in range(a.repeats):
            t = time.perf_counter_ns()
            for p in sub:
                run_one(numerical_owner, solve, p, cfg)
            reps.append(time.perf_counter_ns() - t)
        json.dump({"solves_per_repeat": len(sub), "repeat_ns": reps}, open(a.out, "w"))


def spawn(root, wmode, out, **kw):
    cmd = [sys.executable, str(Path(__file__).resolve()), "worker", "--root", str(root), "--wmode", wmode, "--out", str(out)]
    for k, v in kw.items():
        cmd += ["--" + k, str(v)]
    return subprocess.Popen(cmd, env={**os.environ, "PYTHONHASHSEED": "0"})


def compare(a):
    tmp = Path(a.tmpdir)
    tmp.mkdir(parents=True, exist_ok=True)
    jobs = [spawn(r, "capture", tmp / (n + ".json"), n=a.n) for r, n in ((a.base_root, "base"), (a.changed_root, "changed"))]
    for p in jobs:
        if p.wait():
            sys.exit("worker failed")
    base, chg = (json.load(open(tmp / (n + ".json"))) for n in ("base", "changed"))
    assert base.keys() == chg.keys()
    ident = sum(base[k][0] == chg[k][0] for k in base)
    reason_ident = sum(base[k][1:] == chg[k][1:] for k in base)
    unsolv = [k for k in base if base[k][1] != "available"]
    rep = {"label": LABEL, "evidence": "Developer evidence only", "contracts": len(base),
           "identical_result_hashes": ident, "identical_status_reason": reason_ident,
           "unsolvable_contracts": len(unsolv), "unsolvable_identical": sum(base[k] == chg[k] for k in unsolv),
           "by_set": {s: {"total": sum(k.startswith(s) for k in base),
                          "identical": sum(base[k][0] == chg[k][0] for k in base if k.startswith(s))} for s in ("flat", "mixed")},
           "status_counts": {}}
    for k in base:
        key = base[k][1] + "/" + base[k][2]
        rep["status_counts"][key] = rep["status_counts"].get(key, 0) + 1
    print(json.dumps(rep, indent=1, sort_keys=True))
    if ident != len(base) or reason_ident != len(base):
        sys.exit("MISMATCH between base and changed solver results")


def pct(xs, p):
    xs = sorted(xs)
    return xs[max(0, math.ceil(p / 100 * len(xs)) - 1)]


def bench(a):
    tmp = Path(a.tmpdir)
    tmp.mkdir(parents=True, exist_ok=True)
    res = {}
    for name, root in (("base", a.base_root), ("changed", a.changed_root), ("base2", a.base_root), ("changed2", a.changed_root)):
        p = spawn(root, "bench", tmp / (name + "_bench.json"), n=a.subset, repeats=a.repeats)
        if p.wait():
            sys.exit("bench worker failed")  # sequential, never concurrent: no CPU contention
        d = json.load(open(tmp / (name + "_bench.json")))
        per = [x / d["solves_per_repeat"] for x in d["repeat_ns"]]
        res[name] = {"per_contract_us_p50": pct(per, 50) / 1e3, "per_contract_us_p95": pct(per, 95) / 1e3,
                     "solves_per_s_p50": 1e9 / pct(per, 50), "solves_per_s_at_p95": 1e9 / pct(per, 95),
                     "repeats": len(per), "solves_per_repeat": d["solves_per_repeat"]}
    for s in ("", "2"):
        res["speedup_p50" + s] = res["base" + s]["per_contract_us_p50"] / res["changed" + s]["per_contract_us_p50"]
        res["speedup_p95" + s] = res["base" + s]["per_contract_us_p95"] / res["changed" + s]["per_contract_us_p95"]
    res["label"] = LABEL
    res["evidence"] = "Developer evidence only"
    res["machine"] = {"cpu": platform.processor(), "python": platform.python_version(), "os": platform.platform()}
    print(json.dumps(res, indent=1, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["compare", "bench", "worker"])
    ap.add_argument("--base-root")
    ap.add_argument("--changed-root")
    ap.add_argument("--root")
    ap.add_argument("--wmode")
    ap.add_argument("--out")
    ap.add_argument("--n", type=int, default=10000)
    ap.add_argument("--subset", type=int, default=100, help="contracts per set in the benchmark (flat plus mixed)")
    ap.add_argument("--repeats", type=int, default=30)
    ap.add_argument("--tmpdir", default=str(Path(os.environ.get("TEMP", ".")) / "m1_solver_compare"))
    a = ap.parse_args()
    {"compare": compare, "bench": bench, "worker": worker}[a.cmd](a)


if __name__ == "__main__":
    main()
