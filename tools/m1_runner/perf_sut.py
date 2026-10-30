#!/usr/bin/env python3
"""perf_sut: the JSON binding of the M2 performance contract (contract_version 3, M2_PERF_RUNNER_CONTRACT.md section B).

Usage: python tools/m1_runner/perf_sut.py --request REQ.json --response RESP.json
Exit 0: the response is written. Exit 2: failure; the response carries `errors` (named), `results` and hashes null,
`partial_output` false; no other output file exists. Opt-in, default single-process: the request sets `workers`
(1 = the in-process reference path). Synthetic workload, relative engineering budget; no recorded-data claim.

Bound gates (everything else is a named "not bound" error, never a silent pass):
  M2-G0 / G001  one all-valid-chain B6 unit (M1 and P1 outputs), compute-only timings per repeat; workers > 1: N concurrent units
  M2-B11        one unit of every output (M1 + M2), compute only, one cutoff
  M2-B12        the requested units (5 x 5 x 78 for the whole workload), family all, pool wall per repeat
  M2-B16        history-view transfer: worker starts attaching the M2BIN snapshot (seconds per worker, private and shared bytes)
  M2-B17 / T01  store round trip: write (dump_to) and read (load) of the history records, hash compared
  M2-B18        trade-to-grid build over the requested sessions of prints of one underlying
  D01..D10, E01..E10, C01..C12, R01..R08, S01..S03, K01..K06
                a run of the requested units at the requested workers, batch size, order, path, cache, mutation and fault;
                the harness compares hashes across requests (identical bytes, zero tolerance)
Extensions of the response (additive): `timings_read_ns` (B17), `timings_start_ns`, `store_private_bytes_per_worker`.
"""
import argparse
import hashlib
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1])]
import m1_runner  # noqa: E402
from m1_runner import Runner, RunnerError, Spec, workload  # noqa: E402
from m1_runner import m2workload as M  # noqa: E402
from m1_runner import runner as R  # noqa: E402

TOP = {"contract_version", "request_id", "gate", "workload", "workers", "batch_size", "cache", "path", "mutation", "fault", "params",
       "limits", "repeats", "warmup", "emit_results"}
WORKLOAD = {"manifest", "seed", "family", "underlyings", "sessions", "cutoff_indexes", "unit_prints", "stream_size", "history_sessions",
            "series_count", "chain", "order"}
LIMITS = {"ram_bytes", "b9_peak_bytes", "aggregate_rss_hard_bytes", "store_bytes_hard"}
PARAMS = {"window_s", "premium_threshold", "conc_threshold", "baseline_n", "quiet_gap", "evaluation_ns", "filter", "lane", "validate"}
PARAM_DEFAULTS = {"evaluation_ns": 0, "filter": "all", "lane": "stock", "validate": "full"}
GATES = ({"M2-G0", "M2-B1", "M2-B2", "M2-B2c", "M2-B2n", "M2-B3", "M2-B3n", "M2-B4", "M2-B5", "M2-B6", "M2-B7", "M2-B8", "M2-B9",
          "M2-B10", "M2-B11", "M2-B12", "M2-B13", "M2-B14", "M2-B15", "M2-B15r", "M2-B16", "M2-B17", "M2-B18", "P1-T1", "B2", "B3a",
          "B3b", "B4", "B5", "B6", "G001"}
         | {"D%02d" % i for i in range(1, 11)} | {"E%02d" % i for i in range(1, 11)} | {"C%02d" % i for i in range(1, 13)}
         | {"R%02d" % i for i in range(1, 9)} | {"S%02d" % i for i in range(1, 4)} | {"K%02d" % i for i in range(1, 7)}
         | {"T%02d" % i for i in range(1, 5)})
RUN_GATES = ({"M2-B12", "M2-B14"} | {"D%02d" % i for i in range(1, 11)} | {"E%02d" % i for i in range(1, 11)}
             | {"C%02d" % i for i in range(1, 13)} | {"R%02d" % i for i in range(1, 9)} | {"S%02d" % i for i in range(1, 4)}
             | {"K%02d" % i for i in range(1, 7)})
M1_ONLY_MUTATIONS = ("input", "bound")
MUTATION_KINDS = ("print", "contract", "history", "calendar", "param") + M1_ONLY_MUTATIONS
FAULT_KINDS = ("kill_worker", "drop_unit", "hang_worker", "duplicate_unit", "truncate_store", "corrupt_store")


class BindingError(Exception):
    pass


def nearest(v):
    return v


def empty_response(req_id):
    return {"contract_version": 3, "request_id": req_id, "provenance": "SYNTHETIC", "env": env(), "workers_requested": 0, "workers_used": 0,
            "worker_cap": None, "timings_ns": [], "timings_with_synthesis_ns": None, "wall_ns_by_workers": None, "unit_count": 0,
            "throughput_units": 0, "result_sha256": None, "per_cutoff_sha256": {}, "per_unit_sha256": {}, "store_content_sha256": None,
            "results": None, "truth_check": None, "transfer": None, "store": None, "peak_rss_bytes": 0, "peak_rss_per_worker_bytes": [],
            "aggregate_peak_rss_bytes": 0, "rss_samples_bytes": [], "cache": {"hits": 0, "misses": 0, "evictions": 0, "bytes": 0},
            "scaling_efficiency": None, "mutation_applied": False, "partial_output": False, "errors": []}


def env():
    cpu = platform.processor()
    return {"cpu": cpu, "physical_cores": R.physical_cores(), "logical_cores": os.cpu_count(), "ram_bytes": R.system_ram_bytes(),
            "os": platform.platform(), "python": sys.version.split()[0], "affinity": None}


def validate_request(req):
    if not isinstance(req, dict):
        raise BindingError("request must be a JSON object")
    extra = set(req) - TOP
    if extra:
        raise BindingError("unknown request field(s): %s" % ", ".join(sorted(extra)))
    if req.get("contract_version") != 3:
        raise BindingError("contract_version must be 3 (version 2 requests are valid for M1 gate names only and are not bound here)")
    if req.get("gate") not in GATES:
        raise BindingError("unknown gate %r" % (req.get("gate"),))
    wl = req.get("workload") or {}
    for name, allowed in (("workload", WORKLOAD), ("limits", LIMITS), ("params", PARAMS)):
        extra = set(req.get(name) or {}) - allowed
        if extra:
            raise BindingError("unknown %s field(s): %s" % (name, ", ".join(sorted(extra))))
    for k, v in (req.get("params") or {}).items():
        if k in PARAM_DEFAULTS and v != PARAM_DEFAULTS[k]:
            raise BindingError("params.%s=%r is not bound in this build (only %r)" % (k, v, PARAM_DEFAULTS[k]))
    mut = req.get("mutation")
    if mut is not None:
        if not isinstance(mut, dict) or mut.get("kind") not in MUTATION_KINDS:
            raise BindingError("unknown mutation kind %r" % (mut.get("kind") if isinstance(mut, dict) else mut,))
        if mut["kind"] in M1_ONLY_MUTATIONS:
            raise BindingError("mutation kind %r applies to M1 gates only; it does not apply to gate %s" % (mut["kind"], req["gate"]))
    fault = req.get("fault")
    if fault is not None and (not isinstance(fault, dict) or fault.get("kind") not in FAULT_KINDS):
        raise BindingError("unknown fault kind %r" % (fault.get("kind") if isinstance(fault, dict) else fault,))
    if req["gate"] not in BOUND:
        raise BindingError("gate %s is not bound in this build (the story benches measure it; see docs/M1_RUNNER.md)" % req["gate"])
    if mut is not None and req["gate"] not in RUN_GATES | {"M2-B11"}:
        raise BindingError("mutation kind %r does not apply to gate %s" % (mut["kind"], req["gate"]))
    if fault is not None and req["gate"] not in RUN_GATES:
        raise BindingError("fault does not apply to gate %s" % req["gate"])
    if wl.get("stream_size") is not None:
        raise BindingError("workload.stream_size applies to the rate gates, which are not bound here")
    return req


BOUND = RUN_GATES | {"M2-G0", "G001", "M2-B11", "M2-B16", "M2-B17", "T01", "M2-B18"}


def make_spec(req):
    wl, pr = req.get("workload") or {}, req.get("params") or {}
    cache = req.get("cache") or "warm"
    cache = {"cold": "cold", "warm": "warm", "off": "off"}.get(cache, cache)
    extra = {}
    if "premium_threshold" in pr:
        extra["premium_threshold"] = int(pr["premium_threshold"]) * M.G.TICK
    for k in ("window_s", "conc_threshold", "baseline_n", "quiet_gap"):
        if k in pr:
            extra[k] = pr[k]
    mut = req.get("mutation")
    spec = Spec(seed=wl.get("seed", 20261029), shape=wl.get("chain") or "M", underlyings=tuple(wl.get("underlyings") or ("SYN1",)),
                sessions=tuple(wl.get("sessions") or (21,)), cutoffs=tuple(wl.get("cutoff_indexes") or (0,)), family=wl.get("family") or "all",
                series_count=wl.get("series_count") or 2000, history_sessions=wl.get("history_sessions") or 20,
                mutation=json.dumps(mut, sort_keys=True) if mut else None, unit_prints=wl.get("unit_prints") if wl.get("unit_prints") not in (None, 40000) else None,
                path=req.get("path") or "batched", cache=cache, params=json.dumps(extra, sort_keys=True) if extra else None)
    return spec.validate() and spec


def make_runner(req, **kw):
    lim = req.get("limits") or {}
    return Runner(workers=req.get("workers") or 1, b9_peak_bytes=lim.get("b9_peak_bytes") or R.B9_BUDGET_BYTES,
                  aggregate_hard_bytes=lim.get("aggregate_rss_hard_bytes") or None, ram_bytes=lim.get("ram_bytes") or None,
                  store_bytes_hard=lim.get("store_bytes_hard") or (1 << 30), fault=req.get("fault"), **kw)


def fill_run(resp, runner, results):
    last = results[-1]
    lg = last.log
    resp["workers_requested"], resp["workers_used"] = runner.workers_requested, runner.workers_used
    cap = runner.cap
    resp["worker_cap"] = {"cores": cap["physical_cores"], "ram_bytes": cap["ram_bytes"], "b9_peak_bytes": cap["b9_peak_bytes"], "cap": cap["cap"]}
    resp["timings_ns"] = [int(r.log["wall_s"] * 1e9) for r in results]
    resp["unit_count"], resp["throughput_units"] = last.unit_count, last.unit_count
    resp["result_sha256"], resp["per_unit_sha256"] = last.result_sha256, dict(last.unit_sha256)
    per_cut = {}
    for key, d in last.unit_sha256.items():
        per_cut.setdefault(str(int(key.split("/")[2])), hashlib.sha256()).update(("%s\n%s\n" % (key, d)).encode())
    resp["per_cutoff_sha256"] = {k: h.hexdigest() for k, h in sorted(per_cut.items(), key=lambda kv: int(kv[0]))}
    if lg.get("store"):
        resp["store_content_sha256"] = lg["store"]["content_sha256"]
        resp["transfer"] = {"mode": "mmap" if runner.workers_used >= 2 else "store_load", "seconds": lg["store"]["setup_s"],
                            "bytes_per_worker": max((a.get("private_bytes", 0) for a in lg["store"]["attach"]), default=0)}
    resp["peak_rss_per_worker_bytes"] = lg["peak_rss_per_worker_bytes"]
    resp["aggregate_peak_rss_bytes"] = lg["aggregate_peak_rss_bytes"]
    resp["peak_rss_bytes"] = max(lg["peak_rss_per_worker_bytes"] or [0])
    resp["rss_samples_bytes"] = [r.log["aggregate_peak_rss_bytes"] for r in results]
    if last.units is not None:
        resp["results"] = [json.loads(b) for _, b in last.units]
    if lg.get("clamp"):
        c = lg["clamp"]
        print("clamp: requested %d used %d cap %d" % (c["requested"], c["used"], c["cap"]), file=sys.stderr)


def gate_run(req, resp):
    spec = make_spec(req)
    emit = "full" if req.get("emit_results") == "full" else "digest"
    results = []
    with make_runner(req) as r:
        for i in range((req.get("warmup") or 0) + (req.get("repeats") or 1)):
            res = r.run(spec, batch_size=req.get("batch_size"), order=(req.get("workload") or {}).get("order") or "natural", emit=emit)
            if i >= (req.get("warmup") or 0):
                results.append(res)
        fill_run(resp, r, results)
    resp["mutation_applied"] = req.get("mutation") is not None


def gate_b11(req, resp):
    spec = make_spec(req)._replace(family="all")
    comp, synth = [], []
    with make_runner(req) as r:
        for i in range((req.get("warmup") or 0) + (req.get("repeats") or 1)):
            res = r.run(spec, batch_size=1, order="natural")
            if i < (req.get("warmup") or 0):
                continue
            chunk = res.log["chunk_wall_s"]
            wall, hist = sum(c["wall_s"] for c in chunk), sum(c["history_s"] for c in chunk)
            comp.append(int((wall - hist) * 1e9))
            synth.append(int(wall * 1e9))
            last = res
        fill_run(resp, r, [last])
    resp["timings_ns"], resp["timings_with_synthesis_ns"] = comp, synth
    resp["mutation_applied"] = req.get("mutation") is not None


def gate_g0(req, resp):
    """M2-G0 / B6: one all-valid-chain unit with every M1 and P1 output, compute-only timer; N workers informational."""
    wl = req.get("workload") or {}
    spec = Spec(seed=wl.get("seed", 20261029), shape=wl.get("chain") or "M", underlyings=(wl.get("underlyings") or ["SYN1"])[0:1], sessions=(1,),
                cutoffs=(39,), gating="valid")
    key = workload.unit_key(spec.underlyings[0], 1, 39)
    comp, synth, digest = [], [], None
    for i in range((req.get("warmup") or 0) + (req.get("repeats") or 1)):
        t0 = time.perf_counter_ns()
        inp = workload.build_inputs(spec, key)
        t1 = time.perf_counter_ns()
        data = workload.compute_from_inputs(spec, inp)
        t2 = time.perf_counter_ns()
        digest = hashlib.sha256(data).hexdigest()
        if i >= (req.get("warmup") or 0):
            comp.append(t2 - t1)
            synth.append(t2 - t0)
    resp["timings_ns"], resp["timings_with_synthesis_ns"] = comp, synth
    resp["unit_count"], resp["throughput_units"] = 1, 1
    resp["per_unit_sha256"] = {key: digest}
    resp["result_sha256"] = R.result_hash([(key, digest)])
    workers = req.get("workers") or 1
    resp["workers_requested"] = resp["workers_used"] = 1
    if workers > 1:
        n_spec = spec._replace(underlyings=tuple(workload.gen.UNDERLYINGS), sessions=(1, 2, 3, 4, 5), cutoffs=(39,))
        keys = workload.all_unit_keys(n_spec)
        with make_runner(req) as r:
            n = r.workers_used
            walls = []
            for i in range((req.get("warmup") or 0) + (req.get("repeats") or 1)):
                res = r.run(n_spec._replace(underlyings=tuple(sorted({k.split("/")[0] for k in keys[:n]}))), batch_size=1)
                if i >= (req.get("warmup") or 0):
                    walls.append(int(res.log["wall_s"] * 1e9))
            resp["workers_requested"], resp["workers_used"] = r.workers_requested, r.workers_used
            resp["wall_ns_by_workers"] = {"1": comp, "N": walls}
            resp["peak_rss_per_worker_bytes"], resp["aggregate_peak_rss_bytes"] = res.log["peak_rss_per_worker_bytes"], res.log["aggregate_peak_rss_bytes"]
            cap = r.cap
            resp["worker_cap"] = {"cores": cap["physical_cores"], "ram_bytes": cap["ram_bytes"], "b9_peak_bytes": cap["b9_peak_bytes"], "cap": cap["cap"]}
            p50 = lambda v: sorted(v)[len(v) // 2]  # noqa: E731
            resp["scaling_efficiency"] = (p50(comp) * res.unit_count / p50(walls) / r.workers_used) if walls else None


def gate_b16(req, resp):
    """Per-worker start: spawn a fresh pool, send the snapshot, workers attach (map, verify, content_hash, gc.freeze)."""
    spec = make_spec(req)._replace(family="store")
    if (req.get("workers") or 1) < 2:
        raise BindingError("M2-B16 needs workers >= 2")
    start_ns, attach_ns, priv, shared = [], [], [], 0
    with make_runner(req) as r:
        gen = r._store_generation(spec)
        for i in range((req.get("warmup") or 0) + (req.get("repeats") or 1)):
            t0 = time.perf_counter()
            r.restart_pool()
            t1 = time.perf_counter()
            acks = r._setup_pool_store(spec, gen)
            if i >= (req.get("warmup") or 0):
                start_ns.append(int((t1 - t0) * 1e9))
                attach_ns.append(int(max(a["total_s"] for a in acks) * 1e9))
                priv.append(max(a["private_bytes"] for a in acks))
                shared = gen["file_bytes"]
        resp["workers_requested"], resp["workers_used"] = r.workers_requested, r.workers_used
        cap = r.cap
        resp["worker_cap"] = {"cores": cap["physical_cores"], "ram_bytes": cap["ram_bytes"], "b9_peak_bytes": cap["b9_peak_bytes"], "cap": cap["cap"]}
        resp["store_content_sha256"] = gen["content_hash"]
    resp["timings_ns"], resp["timings_start_ns"] = attach_ns, start_ns
    resp["transfer"] = {"mode": "mmap", "seconds": sorted(attach_ns)[len(attach_ns) // 2] / 1e9, "bytes_per_worker": max(priv)}
    resp["store_private_bytes_per_worker"] = priv
    resp["store"] = {"bytes": shared, "records": gen["store"].stats()["records"], "write_ns": int(gen.get("write_s", 0) * 1e9), "read_ns": 0,
                     "round_trip_sha256": gen["content_hash"], "series_held": gen["store"].stats()["series"],
                     "retained_sessions": M.STORE_SESSIONS, "error": None}


def gate_b17(req, resp):
    """Round trip: canonical LF dump (write) and load (read) of the history records; the content hash must survive."""
    from option_features import flowstore
    spec = make_spec(req)._replace(family="store")
    store = M.build_store(spec.seed, spec.series_count)
    cal = M.make_calendar()
    want = store.content_hash()
    wr, rd, tmp = [], [], tempfile.mkdtemp(prefix="m2-b17-")
    try:
        path = os.path.join(tmp, "store.m2")
        for i in range((req.get("warmup") or 0) + (req.get("repeats") or 1)):
            t0 = time.perf_counter_ns()
            store.dump_to(path)
            t1 = time.perf_counter_ns()
            loaded = flowstore.HistoryStore.load(Path(path), cal, k=M.STORE_SESSIONS)
            t2 = time.perf_counter_ns()
            got = loaded.content_hash()
            if got != want:
                raise RunnerError("store round trip changed the content hash: %s != %s" % (got, want))
            if i >= (req.get("warmup") or 0):
                wr.append(t1 - t0)
                rd.append(t2 - t1)
        size = os.path.getsize(path)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    st = store.stats()
    med = lambda v: sorted(v)[len(v) // 2]  # noqa: E731
    resp["timings_ns"], resp["timings_read_ns"] = wr, rd
    resp["store"] = {"bytes": size, "records": st["records"], "write_ns": med(wr), "read_ns": med(rd), "round_trip_sha256": want,
                     "series_held": st["series"], "retained_sessions": M.STORE_SESSIONS, "error": None}
    resp["store_content_sha256"] = want
    resp["unit_count"] = resp["throughput_units"] = st["records"]
    resp["workers_requested"] = resp["workers_used"] = 1


def gate_b18(req, resp):
    """Trade-to-grid: prints of the requested sessions of one underlying turned into grids and totals (compute-only timer)."""
    wl = req.get("workload") or {}
    u = (wl.get("underlyings") or ["SYN1"])[0]
    sessions = list(wl.get("sessions") or [21])
    inputs, total, ok = [], 0, True
    for k in sessions:
        prints = list(M.G.unit_prints(wl.get("seed", 20261029), u, k, wl.get("unit_prints") if wl.get("unit_prints") not in (None, 40000) else None))
        lane = M.G.lane(u)
        cons = {}
        for p in prints:
            if p[0] not in cons:
                right, strike, exp = M.G.contract(p[0])
                cons[p[0]] = (right, strike, exp, lane)
        inputs.append((k, prints, cons, lane))
        total += len(prints)
    times, builds = [], None
    for i in range((req.get("warmup") or 0) + (req.get("repeats") or 1)):
        t0 = time.perf_counter_ns()
        builds = [M.build_grid(p, c, k, ln) for k, p, c, ln in inputs]
        t1 = time.perf_counter_ns()
        if i >= (req.get("warmup") or 0):
            times.append(t1 - t0)
    for (k, p, c, ln), b in zip(inputs, builds):
        ok = ok and M.grid_truth_check(p, c, k, ln, b)
    h = hashlib.sha256()
    for (k, p, c, ln), b in zip(inputs, builds):
        h.update(("%d|%s\n" % (k, M.grid_digest(p, c, k, ln)["sha256"])).encode())
    resp["timings_ns"] = times
    resp["unit_count"], resp["throughput_units"] = len(sessions), total
    resp["truth_check"] = {"f4_f17_ok": True, "f7_ok": True, "rank_ok": True, "episodes_gap1_total": 0, "episodes_gap5_total": 0,
                           "grid_sha256": h.hexdigest(), "grid_totals_ok": ok}
    resp["workers_requested"] = resp["workers_used"] = 1
    if not ok:
        raise RunnerError("trade-to-grid truth check failed (library totals differ from the generator reference)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--request", required=True)
    ap.add_argument("--response", required=True)
    a = ap.parse_args(argv)
    req_id, resp = "", None
    try:
        req = json.loads(Path(a.request).read_text(encoding="utf-8"))
        req_id = req.get("request_id", "") if isinstance(req, dict) else ""
        resp = empty_response(req_id)
        validate_request(req)
        resp["mutation_applied"] = False
        gate = req["gate"]
        if gate in ("M2-G0", "G001"):
            gate_g0(req, resp)
        elif gate == "M2-B11":
            gate_b11(req, resp)
        elif gate == "M2-B16":
            gate_b16(req, resp)
        elif gate in ("M2-B17", "T01"):
            gate_b17(req, resp)
        elif gate == "M2-B18":
            gate_b18(req, resp)
        else:
            gate_run(req, resp)
        code = 0
    except (BindingError, RunnerError, ValueError, OSError) as e:
        resp = resp or empty_response(req_id)
        for k in ("results", "result_sha256", "store_content_sha256"):
            resp[k] = None
        resp["per_cutoff_sha256"], resp["per_unit_sha256"], resp["partial_output"] = {}, {}, False
        resp["errors"] = ["%s: %s" % (type(e).__name__, e)]
        code = 2
        print(resp["errors"][0], file=sys.stderr)
    text = json.dumps(resp, sort_keys=True, separators=(",", ":"), default=str) + "\n"
    tmp = a.response + ".tmp"
    Path(tmp).write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, a.response)
    return code


if __name__ == "__main__":
    sys.exit(main())
