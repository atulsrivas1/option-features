#!/usr/bin/env python3
"""M1 Stage 0/1 comparison, mutation and benchmark harness for the IV solver (Developer evidence only).

Label: synthetic workload, relative engineering budget. No claim about recorded data or live latency.

Each solver run happens in a fresh subprocess against one checkout's source trees. Sets: flat (10k) and
mixed (10k) from qualification/synthetic/perf/gen_m1_solver_sets.py, plus the adversarial list of
tools/m1_adversarial_sets.py (2800 contracts: dyadic-sigma near ties, roots, edges, extremes, out-of-domain).

  compare   --base-root BASE --changed-root CHANGED [--n 10000] [--adv 2400] [--mut 400]
            Captures every InverseResult and SolverEvidence field (exact-field hash) at BASE, at CHANGED
            with the float filter on (default), at CHANGED with float_filter=False and at CHANGED with the Stage 2
            conversion switch off (--conv legacy), and
            requires identical hashes everywhere. Exit non-zero on any difference.
  mutation  --base-root BASE --changed-root CHANGED [--n 1000]
            Acceptance test 3. Test-only hooks (tools/m1_filter_hooks.py) shrink the bound and inject a
            modelled float error. Control (bound_divisor 1) must show ZERO differences; the shrunk bound
            (bound_divisor 10) must show AT LEAST ONE, otherwise this command exits non-zero (the build
            fails). Also prints the plain divisor-10 run without injection (informational).
  count     per-solve certified-enclosure (arb) call counts, base vs changed, p50/p95/max.
  bench     >= 30 repeats after warm-up, base and changed interleaved, per-solve wall p50/p95, solves/s,
            peak working set, arb calls per solve, and the B6 PROXY arithmetic (not a measurement).
  worker    (internal)
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
CHAIN_M = 2000          # contracts in a size-M chain (B6 proxy arithmetic only)
INJECT_W = 5.0          # modelled worst-case float error, in units of u*SCALE (proof coefficient, rounded up)


def contracts(kind, n):
    sys.path[:0] = [str(PERF), str(HERE)]
    if kind in ("flat", "mixed"):
        import gen_m1_solver_sets as g
        return [dict(g.contract(SEED, kind, i), i=i) for i in range(n)]
    import m1_adversarial_sets as a
    if kind == "adv":
        return [dict(c, i=i) for i, c in enumerate(a.adversarial(n))]
    if kind == "mut":
        return [dict(c, i=i) for i, c in enumerate(a.mutation_ties(n))]
    raise ValueError(kind)


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
        T = Fraction(c["T"]) if "T" in c else Fraction(c["t_days"], 365)
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


def run_one(owner_cm, solve, prep, cfg, kw):
    ops, target, conv = prep
    with owner_cm() as o:
        return solve(ops, target, cfg, conv, o, **kw)


def peak_working_set():
    """Peak resident set of this process in bytes (Windows PeakWorkingSetSize, else ru_maxrss)."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        k32, ps = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        ps.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(PMC)
        ps.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return int(pmc.PeakWorkingSetSize)
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def worker(a):
    numerical_owner, solve, prepare, cfg, srcfile = setup(a.root)
    assert str(Path(a.root).resolve()).lower() in str(Path(srcfile).resolve()).lower(), "imported solver is not from --root"
    kw = {"float_filter": False} if a.filter == "off" else {}
    if a.conv == "legacy":   # Stage 2 switch: pre-Stage-2 endpoint conversion (arithmetic_legacy)
        import option_features.arithmetic as _ar
        _ar.set_fast_endpoints(False)
    hooks = None
    if a.hooks:
        from m1_filter_hooks import test_hooks
        d, inj = (float(x) for x in a.hooks.split(","))
        hooks = test_hooks(bound_divisor=d, inject=inj)
        hooks.__enter__()
    items = []
    for spec in a.sets.split(","):
        kind, _, cnt = spec.partition(":")
        items += [(kind, c) for c in contracts(kind, int(cnt) if cnt else a.n)]
    preps = [(k, c["i"], prepare(c)) for k, c in items]
    if a.wmode == "capture":
        out = {}
        for k, i, p in preps:
            try:
                r = run_one(numerical_owner, solve, p, cfg, kw)
                rep, st, rs = json.dumps(canon(r), sort_keys=True), r.status, r.reason
            except Exception as e:  # recorded, must match too
                rep, st, rs = "EXC:" + repr(e), "exception", type(e).__name__
            out["%s:%06d" % (k, i)] = [hashlib.sha256(rep.encode()).hexdigest(), st, rs]
        json.dump(out, open(a.out, "w"), sort_keys=True)
    elif a.wmode == "count":
        import option_features.model as model
        import option_features.inverse as inv
        calls = [0]
        real_eq, real_bounds = model.equation, inv.bounds

        def eq(*x, **y):
            calls[0] += 1
            return real_eq(*x, **y)

        def bd(*x, **y):
            calls[0] += 1
            return real_bounds(*x, **y)
        model.equation, inv.bounds = eq, bd
        # Stage 2: endpoint conversions (dyadic endpoint + outward_decimal calls) and Decimal materialisations
        import option_features.arithmetic as ar
        conv, dec = [0], [0]

        def wrap(mod, name, ctr):
            real = getattr(mod, name)

            def f(*x, **y):
                ctr[0] += 1
                return real(*x, **y)
            setattr(mod, name, f)
        for name in ("dyadic_endpoint", "dyadic_endpoint_parts", "outward_decimal"):
            if hasattr(ar, name) and not (name == "dyadic_endpoint" and hasattr(ar, "dyadic_endpoint_parts")):
                wrap(ar, name, conv)
        wrap(ar, "_decimal" if hasattr(ar, "_decimal") else "decimal_tuple", dec)
        per, per_conv, per_dec = [], [], []
        for k, i, p in preps:
            calls[0] = conv[0] = dec[0] = 0
            run_one(numerical_owner, solve, p, cfg, kw)
            per.append(calls[0])
            per_conv.append(conv[0])
            per_dec.append(dec[0])
        json.dump({"per_solve": per, "conversions": per_conv, "decimals": per_dec}, open(a.out, "w"))
    else:
        sub = [p for k, i, p in preps]
        for p in sub:
            run_one(numerical_owner, solve, p, cfg, kw)  # warm-up (not counted)
        samples = []
        for _ in range(a.repeats):
            rep = []
            for p in sub:
                t = time.perf_counter_ns()
                run_one(numerical_owner, solve, p, cfg, kw)
                rep.append(time.perf_counter_ns() - t)
            samples.append(rep)
        json.dump({"solves_per_repeat": len(sub), "samples_ns": samples, "peak_working_set_bytes": peak_working_set()}, open(a.out, "w"))
    if hooks:
        hooks.__exit__(None, None, None)


def spawn(root, wmode, out, **kw):
    cmd = [sys.executable, str(Path(__file__).resolve()), "worker", "--root", str(root), "--wmode", wmode, "--out", str(out)]
    for k, v in kw.items():
        cmd += ["--" + k, str(v)]
    return subprocess.Popen(cmd, env={**os.environ, "PYTHONHASHSEED": "0"})


def capture_all(jobs, tmp):
    """jobs: {name: (root, kwargs)}; runs them concurrently, returns {name: capture}."""
    procs = {n: spawn(r, "capture", tmp / (n + ".json"), **kw) for n, (r, kw) in jobs.items()}
    for n, p in procs.items():
        if p.wait():
            sys.exit("worker %s failed" % n)
    return {n: json.load(open(tmp / (n + ".json"))) for n in jobs}


def diff_count(ref, other):
    assert ref.keys() == other.keys()
    return sorted(k for k in ref if ref[k][0] != other[k][0])


def compare(a):
    tmp = Path(a.tmpdir)
    tmp.mkdir(parents=True, exist_ok=True)
    sets = "flat:%d,mixed:%d,adv:%d,mut:%d" % (a.n, a.n, a.adv, a.mut)   # 10000+10000+2400+400 = 22,800 contracts
    caps = capture_all({"base": (a.base_root, {"sets": sets}), "changed": (a.changed_root, {"sets": sets}),
                        "changed_switch_off": (a.changed_root, {"sets": sets, "filter": "off"}),
                        "changed_legacy_conv": (a.changed_root, {"sets": sets, "conv": "legacy"})}, tmp)
    base = caps["base"]
    rep = {"label": LABEL, "evidence": "Developer evidence only", "contracts": len(base), "sets": sets, "runs": {}}
    bad = 0
    for name in ("changed", "changed_switch_off", "changed_legacy_conv"):
        d = diff_count(base, caps[name])
        reason_ident = sum(base[k][1:] == caps[name][k][1:] for k in base)
        unsolv = [k for k in base if base[k][1] != "available"]
        rep["runs"][name] = {"identical_result_hashes": len(base) - len(d), "different": d[:20], "identical_status_reason": reason_ident,
                             "unsolvable_contracts": len(unsolv), "unsolvable_identical": sum(base[k] == caps[name][k] for k in unsolv),
                             "by_set": {s: {"total": sum(k.startswith(s) for k in base),
                                            "identical": sum(base[k][0] == caps[name][k][0] for k in base if k.startswith(s))} for s in ("flat", "mixed", "adv", "mut")}}
        bad += len(d) + (len(base) - reason_ident)
    rep["status_counts"] = {}
    for k in base:
        key = base[k][1] + "/" + base[k][2]
        rep["status_counts"][key] = rep["status_counts"].get(key, 0) + 1
    print(json.dumps(rep, indent=1, sort_keys=True))
    if bad:
        sys.exit("MISMATCH between base and changed solver results")


def mutation(a):
    """Acceptance test 3: shrunk-bound mutation. The build fails if the mutant shows no byte difference."""
    tmp = Path(a.tmpdir)
    tmp.mkdir(parents=True, exist_ok=True)
    sets = "flat:%d,mixed:%d,adv:%d,mut:%d" % (a.n, a.n, a.adv, a.mut)
    w = INJECT_W
    runs = {"control_divisor1_inject5": (1, w), "headroom_divisor1_inject30": (1, 30.0),
            "mutant_divisor10_inject5": (10, w), "mutant_divisor10_inject30": (10, 30.0), "plain_divisor10_no_inject": (10, 0.0)}
    jobs = {"base": (a.base_root, {"sets": sets})}
    for n, (d, inj) in runs.items():
        jobs[n] = (a.changed_root, {"sets": sets, "hooks": "%g,%g" % (d, inj)})
    caps = capture_all(jobs, tmp)
    rep = {"label": LABEL, "evidence": "Developer evidence only", "contracts": len(caps["base"]), "sets": sets,
           "bound_used": {"default": "C_BOUND*U*SCALE = 40 * 2**-40 * SCALE", "shrunk": "default / 10 = 4 * 2**-40 * SCALE"},
           "mutation_applied": True, "inject_units": w, "runs": {}}
    for n in runs:
        d = diff_count(caps["base"], caps[n])
        rep["runs"][n] = {"different_contracts": len(d), "examples": d[:5]}
    print(json.dumps(rep, indent=1, sort_keys=True))
    fail = []
    for n in ("control_divisor1_inject5", "headroom_divisor1_inject30"):
        if rep["runs"][n]["different_contracts"]:
            fail.append("control %s differs from the certified solver" % n)
    for n in ("mutant_divisor10_inject5", "mutant_divisor10_inject30"):
        if not rep["runs"][n]["different_contracts"]:
            fail.append("MUTATION NOT DETECTED: %s shows zero byte differences, the build fails" % n)
    if fail:
        sys.exit("; ".join(fail))
    print("MUTATION DETECTED; controls identical")


def pct(xs, p):
    xs = sorted(xs)
    return xs[max(0, math.ceil(p / 100 * len(xs)) - 1)]


def count(a):
    tmp = Path(a.tmpdir)
    tmp.mkdir(parents=True, exist_ok=True)
    sets = "flat:%d,mixed:%d" % (a.n, a.n)
    out = {}
    for name, root, kw in (("base", a.base_root, {}), ("changed", a.changed_root, {}), ("changed_switch_off", a.changed_root, {"filter": "off"}),
                           ("changed_legacy_conv", a.changed_root, {"conv": "legacy"})):
        p = spawn(root, "count", tmp / (name + "_count.json"), sets=sets, **kw)
        if p.wait():
            sys.exit("count worker failed")
        cj = json.load(open(tmp / (name + "_count.json")))
        per = cj["per_solve"]
        out[name] = {"conversions_per_solve_p50": pct(cj["conversions"], 50), "conversions_per_solve_p95": pct(cj["conversions"], 95),
                     "conversions_per_solve_mean": sum(cj["conversions"]) / len(per), "decimal_materialisations_per_solve_mean": sum(cj["decimals"]) / len(per),
                     "solves": len(per), "arb_calls_per_solve_p50": pct(per, 50), "arb_calls_per_solve_p95": pct(per, 95),
                     "max": max(per), "total": sum(per), "mean": sum(per) / len(per)}
    out["label"] = LABEL
    print(json.dumps(out, indent=1, sort_keys=True))
    return out


def bench(a):
    tmp = Path(a.tmpdir)
    tmp.mkdir(parents=True, exist_ok=True)
    res = {}
    sets = "flat:%d,mixed:%d" % (a.subset, a.subset)
    for name, root in (("base", a.base_root), ("changed", a.changed_root), ("base2", a.base_root), ("changed2", a.changed_root)):
        p = spawn(root, "bench", tmp / (name + "_bench.json"), sets=sets, repeats=a.repeats)
        if p.wait():
            sys.exit("bench worker failed")  # sequential, never concurrent: no CPU contention
        d = json.load(open(tmp / (name + "_bench.json")))
        per_solve = [x for rep in d["samples_ns"] for x in rep]
        per_repeat_mean = [sum(rep) / len(rep) for rep in d["samples_ns"]]
        res[name] = {"wall_us_per_solve_p50": pct(per_solve, 50) / 1e3, "wall_us_per_solve_p95": pct(per_solve, 95) / 1e3,
                     "solves_per_s_at_p50": 1e9 / pct(per_solve, 50), "solves_per_s_repeat_mean_p50": 1e9 / pct(per_repeat_mean, 50),
                     "mean_us_per_solve": sum(per_solve) / len(per_solve) / 1e3,
                     "repeats": len(d["samples_ns"]), "solves_per_repeat": d["solves_per_repeat"], "samples": len(per_solve),
                     "peak_working_set_mb": d["peak_working_set_bytes"] / 2 ** 20}
    for s in ("", "2"):
        res["speedup_p50" + s] = res["base" + s]["wall_us_per_solve_p50"] / res["changed" + s]["wall_us_per_solve_p50"]
        res["speedup_p95" + s] = res["base" + s]["wall_us_per_solve_p95"] / res["changed" + s]["wall_us_per_solve_p95"]
        res["speedup_mean" + s] = res["base" + s]["mean_us_per_solve"] / res["changed" + s]["mean_us_per_solve"]
    cnt = count(argparse.Namespace(tmpdir=a.tmpdir, base_root=a.base_root, changed_root=a.changed_root, n=a.subset))
    res["arb_calls"] = {k: v for k, v in cnt.items() if k != "label"}
    # PROXY arithmetic, NOT a measurement: B6 is all outputs for a size-M chain; this multiplies the mean
    # measured IV solve time by the chain size and ignores every other output and the evaluator overhead.
    res["b6_proxy"] = {"kind": "PROXY arithmetic, not a measurement", "chain_contracts": CHAIN_M,
                       "formula": "chain_contracts * mean_us_per_solve / 1e6 seconds (IV solve only; flat+mixed mean)",
                       "budget_verbatim": "B6 <= 5 s budget, 15 s hard (PERF_ACCEPTANCE.md)",
                       "base_s": CHAIN_M * (res["base"]["mean_us_per_solve"] + res["base2"]["mean_us_per_solve"]) / 2 / 1e6,
                       "changed_s": CHAIN_M * (res["changed"]["mean_us_per_solve"] + res["changed2"]["mean_us_per_solve"]) / 2 / 1e6}
    res["label"] = LABEL
    res["evidence"] = "Developer evidence only"
    res["machine"] = {"cpu": platform.processor(), "python": platform.python_version(), "os": platform.platform(), "cores": os.cpu_count()}
    print(json.dumps(res, indent=1, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["compare", "mutation", "count", "bench", "worker"])
    ap.add_argument("--base-root")
    ap.add_argument("--changed-root")
    ap.add_argument("--root")
    ap.add_argument("--wmode")
    ap.add_argument("--out")
    ap.add_argument("--sets", default="flat,mixed")
    ap.add_argument("--filter", default="default")
    ap.add_argument("--conv", default="default", help="legacy = pre-Stage-2 endpoint conversion (Stage 2 switch)")
    ap.add_argument("--hooks", default="")
    ap.add_argument("--n", type=int, default=10000)
    ap.add_argument("--adv", type=int, default=2400)
    ap.add_argument("--mut", type=int, default=400)
    ap.add_argument("--subset", type=int, default=100, help="contracts per set in the benchmark (flat plus mixed)")
    ap.add_argument("--repeats", type=int, default=30)
    ap.add_argument("--tmpdir", default=str(Path(os.environ.get("TEMP", ".")) / "m1_solver_compare"))
    a = ap.parse_args()
    {"compare": compare, "mutation": mutation, "count": count, "bench": bench, "worker": worker}[a.cmd](a)


if __name__ == "__main__":
    main()
