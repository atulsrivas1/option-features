#!/usr/bin/env python3
"""M2 story A benchmark: history store, grid builder, percentile and baseline reads.

Label: synthetic workload, relative engineering budget. No claim about recorded data, live latency or vendor feeds.
Developer evidence only; the independent Tester re-measures every gate. Workload is generated here from a fixed seed
(stdlib random) before any timer starts: one underlying, 2,000 contracts (size M), median about 20 and a heavy tail of
prints per contract per session, 390-minute sessions, 25 sessions (20 history + evaluated). Protocol: one warm-up,
then >= 30 timed repeats, nearest-rank p50/p95, raw samples kept in the JSON, budgets printed verbatim from
docs/m2/M2_GATE_BUDGETS.md beside each measurement, machine recorded, single thread, monotonic ns around the call only.
Gates covered: M2-B1, B2, B2c, B2n, B3, B3n, B4, B13 (store part), B15r (reads part), B16 (view transfer options),
B17, B18, and the story A part of B9 (fused reads); the P1-T1 regression marker is read from docs/p1/P1_T1_REPORT.json.
Usage: python tools/m2a_benchmark.py [--repeats 30] [--sessions 25] [--contracts 2000] [--json out.json]
"""
import argparse
import hashlib
import json
import math
import mmap
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages" / "features" / "src"), str(ROOT / "packages" / "option-contracts" / "src"), str(ROOT / "tools")]
from option_features import flowgrid, flowrank, flowstore  # noqa: E402

LABEL = "synthetic workload, relative engineering budget"
QUAL = ("mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, "
        "Windows x64, CPython 3.12")
NS = 10 ** 9
G = 60 * NS
MINUTES = 390
OPEN0 = 1790000000 * NS


def nearest_rank(ordered, p):
    return ordered[max(1, math.ceil(p / 100 * len(ordered))) - 1]


def budget_rows():
    text = (ROOT / "docs" / "m2" / "M2_GATE_BUDGETS.md").read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        m = re.match(r"\| (M2-B\w+) \|", line)
        if m:
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            if len(c) >= 6:
                rows[c[0]] = {"metric": c[2], "budget": c[3], "hard": c[4]}
    return rows


def rss_bytes():
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t)]
    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    ctypes.windll.kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), wintypes.DWORD]
    ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return int(c.WorkingSetSize), int(c.PeakWorkingSetSize)


def machine():
    info = {"python": sys.version.split()[0], "os": platform.platform(), "logical_cores": os.cpu_count(),
            "cpu": platform.processor()}
    try:
        info["cpu_detail"] = subprocess.run(["powershell", "-NoProfile", "-Command",
                                             "Get-CimInstance Win32_Processor | Select Name,NumberOfCores,NumberOfLogicalProcessors | ConvertTo-Json -Compress"],
                                            capture_output=True, text=True, timeout=60).stdout.strip()
        info["power_plan"] = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as exc:  # recorded, never fatal
        info["detail_error"] = str(exc)
    return info


def make_world(contracts, sessions, seed):
    rng = random.Random(seed)
    cons = {"C%04d" % i: flowgrid.Contract("C" if i % 2 == 0 else "P", 1000000 + i * 10000, "2026-12-18", "stock", "SYN1")
            for i in range(contracts)}
    cal = flowgrid.Calendar([("2026-%02d-%02d" % (1 + i // 28, 1 + i % 28), MINUTES) for i in range(sessions + 1)])
    data = []
    for s in range(sessions):
        open_ns = OPEN0 + s * 86400 * NS
        ps = []
        for cid in cons:
            n = max(1, int(rng.lognormvariate(2.9, 0.9)))
            for _ in range(n):
                ps.append((cid, open_ns + rng.randrange(0, MINUTES * G), 10000 * rng.randrange(1, 50), rng.randrange(1, 50), 100, 0))
        ps.sort(key=lambda p: p[1])
        data.append((open_ns, [p + (i,) for i, p in enumerate(ps)]))
    return cons, cal, data


def five_metrics(build, cons):
    """Contract series carry premium, contracts, prints; add put_volume / call_volume so every series has the 5 metrics
    of M2-B1 (the volume of its own right, and an all-zero record for the other right)."""
    out = []
    for r in build.records:
        out.append(r)
        if r.metric == "contracts" and r.series_id in cons:
            right = cons[r.series_id].right
            empty = flowgrid.GridRecord(r.series_id, "put_volume" if right == "C" else "call_volume", r.window_s, r.session_id,
                                        r.minutes, r.idx[:0], r.vals[:0], 0)
            same = r._replace(metric="call_volume" if right == "C" else "put_volume")
            out.extend([same, empty])
    return out


def timed(fn, repeats, warm=1):
    for _ in range(warm):
        fn()
    s = []
    for _ in range(repeats):
        t = time.perf_counter_ns()
        fn()
        s.append((time.perf_counter_ns() - t) / 1e9)
    return s


def summary(samples):
    o = sorted(samples)
    return {"p50": nearest_rank(o, 50), "p95": nearest_rank(o, 95), "max": o[-1], "n": len(o)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=30)
    ap.add_argument("--sessions", type=int, default=25)
    ap.add_argument("--contracts", type=int, default=2000)
    ap.add_argument("--json")
    ap.add_argument("--no-gc-freeze", action="store_true", help="measure with the cyclic collector active over the stores")
    a = ap.parse_args()
    R = a.repeats
    budgets = budget_rows()
    out = {"label": LABEL, "qualification_label": QUAL, "machine": machine(), "repeats": R, "gates": {}}
    gates = out["gates"]

    def record(gate, name, value, unit, extra=None):
        gates.setdefault(gate, {"budget_text": budgets.get(gate, {}), "results": {}})["results"][name] = dict(value=value, unit=unit, **(extra or {}))
        b = budgets.get(gate, {})
        print("%-9s %-34s %s %s   | budget: %s | hard: %s" % (gate, name, value if isinstance(value, str) else json.dumps(value), unit,
                                                             b.get("budget"), b.get("hard")), flush=True)

    print("building workload ...", flush=True)
    cons, cal, data = make_world(a.contracts, a.sessions, 20261029)
    total_prints = sum(len(d[1]) for d in data)
    out["workload"] = {"contracts": a.contracts, "sessions": a.sessions, "prints_total": total_prints,
                       "prints_per_session": [len(d[1]) for d in data][:3], "seed": 20261029, "minutes": MINUTES}
    # ---------------------------------------------------------------- M2-B18 trade to grid
    builds = []
    rates = []
    for rep in range(max(2, R // 15)):
        builds = []
        for s, (open_ns, ps) in enumerate(data):
            t = time.perf_counter_ns()
            b = flowgrid.build_session_records(ps, cons, cal.ids[s], open_ns, open_ns + MINUTES * G, MINUTES, (300,), "stock", "SYN1", True, "scanned")
            dt = (time.perf_counter_ns() - t) / 1e9
            rates.append(len(ps) / dt)
            builds.append(b)
    o = sorted(rates)
    record("M2-B18", "per-session build, prints/s", {"p5_rate": nearest_rank(o, 5), "p50_rate": nearest_rank(o, 50), "samples": len(o)}, "prints/s (p5 judged)")
    # ---------------------------------------------------------------- M2-B1 append
    sessions_records = [five_metrics(b, cons) for b in builds]
    nrec = sum(len(r) for r in sessions_records)

    def build_store(k=a.sessions, complete=True):
        st = flowstore.HistoryStore(cal, k=k)
        for recs in sessions_records:
            st.append_many(recs, complete)
        return st
    s_app = timed(build_store, R)
    rate = [nrec / x for x in s_app]
    o = sorted(rate)
    record("M2-B1", "append %d records (k=%d)" % (nrec, a.sessions), {"p5_rate": nearest_rank(o, 5), "p50_rate": nearest_rank(o, 50), "time": summary(s_app)}, "records/s")

    def build_open():
        st = flowstore.HistoryStore(cal, k=a.sessions)
        for s, recs in enumerate(sessions_records):
            st.append_many(recs, False)
            for r in recs:
                st.seal(r.series_id, r.metric, r.window_s, r.session_id)
    s_seal = timed(build_open, max(3, R // 6))
    record("M2-B1", "append open then seal each", {"p50_rate": nrec / summary(s_seal)["p50"]}, "records/s (informational)")
    store = build_store(k=20)
    st25 = build_store(k=a.sessions)
    stats = store.stats()
    ser = stats["series"]
    import gc
    gc.collect()
    if not a.no_gc_freeze:
        gc.freeze()      # long-lived store objects leave the collector's scan (a runner does this after loading a store)
    out["gc_freeze"] = not a.no_gc_freeze
    # ---------------------------------------------------------------- reads
    series = sorted({r.series_id for r in sessions_records[0] if r.series_id in cons})[:]
    as_of = cal.ids[a.sessions]
    rng = random.Random(1)
    metrics = ("premium", "contracts", "prints")
    pick = [(s, rng.choice(metrics)) for s in series]
    first = as_of
    cold = []
    for rep in range(R):
        store.drop_caches()
        for s, m in pick[:200]:
            t = time.perf_counter_ns()
            v = store.baseline(s, m, 300, first, 20)
            if v is not None:
                v.rank(5)
            cold.append((time.perf_counter_ns() - t) / 1e9)
    o = sorted(cold)
    record("M2-B2c", "cold view + sorted build per series", {"p50_s": nearest_rank(o, 50), "p95_s": nearest_rank(o, 95), "samples": len(o)}, "s per series")
    warm = []
    for s, m in pick:
        store.baseline(s, m, 300, first, 20).rank(5)
    for rep in range(R):
        for s, m in pick[:200]:
            t = time.perf_counter_ns()
            v = store.baseline(s, m, 300, first, 20)
            v.rank(5)
            warm.append((time.perf_counter_ns() - t) / 1e9)
    o = sorted(warm)
    record("M2-B2", "warm rank-ready view per series", {"p50_s": nearest_rank(o, 50), "p95_s": nearest_rank(o, 95), "samples": len(o)}, "s per series")
    times = {}
    for n in (500, 2000, 6000):
        sel = [(pick[i % len(pick)][0], pick[i % len(pick)][1]) for i in range(n)]

        def batch():
            for s, m in sel:
                store.baseline(s, m, 300, first, 20)
        sm = summary(timed(batch, R))
        times[n] = sm
        record("M2-B2n", "N=%d warm views" % n, sm, "s")
    record("M2-B2n", "time(6000)/time(2000)", times[6000]["p50"] / times[2000]["p50"], "ratio (budget <= 3.6)")
    # ---------------------------------------------------------------- B3 / B4
    t_open = OPEN0 + a.sessions * 86400 * NS
    sess = flowrank.SessionInfo(as_of, t_open, t_open + MINUTES * G, MINUTES, True, "live", 12345, None)
    cut = t_open + 200 * G
    xs = {s: (1000000 + (hash(s) % 7) * 1000, 30, 3) for s in series}
    for s in series:   # warm-up: every view and sorted array built once before the timed calls
        for m in metrics:
            store.baseline(s, m, 300, as_of, 20).rank(5)
    lat = {"f2_intraday": [], "f2_eod": [], "f10": [], "f20": []}
    for rep in range(R):
        for s in series[:200]:
            p, v, c = xs[s]
            t = time.perf_counter_ns()
            flowrank.f2_rank(store, s, "premium", p, sess, cut, 300)
            lat["f2_intraday"].append(time.perf_counter_ns() - t)
            t = time.perf_counter_ns()
            flowrank.f2_rank(store, s, "contracts", 12345, sess, cut, 300, "end_of_day")
            lat["f2_eod"].append(time.perf_counter_ns() - t)
            t = time.perf_counter_ns()
            flowrank.f10_baseline(store, s, v, sess, cut, 300)
            lat["f10"].append(time.perf_counter_ns() - t)
            t = time.perf_counter_ns()
            flowrank.f20_baseline(store, s, "contracts", sess, cut, 300)
            lat["f20"].append(time.perf_counter_ns() - t)
    for k, g in (("f2_intraday", "M2-B3"), ("f2_eod", "M2-B3"), ("f10", "M2-B4"), ("f20", "M2-B4")):
        o = sorted(x / 1e9 for x in lat[k])
        record(g, k + " per series (warm)", {"p50_s": nearest_rank(o, 50), "p95_s": nearest_rank(o, 95), "samples": len(o)}, "s per series")
    t3 = {}
    for n in (500, 2000, 6000):
        items = [(series[i % len(series)], "premium", xs[series[i % len(series)]][0], None) for i in range(n)]
        sm = summary(timed(lambda: flowrank.f2_rank_many(store, items, sess, cut, 300), R))
        t3[n] = sm
        record("M2-B3n", "N=%d F2a batch" % n, sm, "s")
    record("M2-B3n", "time(6000)/time(2000)", t3[6000]["p50"] / t3[2000]["p50"], "ratio (budget <= 3.6)")
    items10 = [(s, xs[s][1], None) for s in series]
    record("M2-B4", "F10 batch N=%d" % len(items10), summary(timed(lambda: flowrank.f10_baseline_many(store, items10, sess, cut, 300), R)), "s")
    packs = [(s, xs[s][0], xs[s][1], xs[s][2], None) for s in series]
    sm = summary(timed(lambda: flowrank.flow_pack_many(store, sess, cut, 300, packs), R))
    record("M2-B9", "A part: fused F2a,b,c,d + F10, %d series" % len(packs), sm, "s (excludes the shared print pass and B stories)")
    sm78 = summary(timed(lambda: [flowrank.flow_pack_many(store, sess, cut + i * G // 4, 300, packs) for i in range(78)], max(3, R // 10), 0))
    record("M2-B15r", "A part: 78 cutoffs x %d series fused reads" % len(packs), sm78, "s (reads = 78 x 4 x %d = %d)" % (len(packs), 78 * 4 * len(packs)))
    # ---------------------------------------------------------------- B17 persistence, B16 transfer, B13 memory
    tmp = Path(tempfile.mkdtemp(prefix="m2a_bench_"))
    try:
        path = tmp / "store.lf"
        w = timed(lambda: st25.dump_to(path), max(3, R // 6))
        for st_ in (st25,):
            pass
        n25 = st25.stats()["records"]
        sm = summary(w)
        record("M2-B17", "write %d records" % n25, {"p5_rate": n25 / sm["max"], "p50_rate": n25 / sm["p50"], "time": sm, "bytes": path.stat().st_size}, "records/s")

        def rd():
            flowstore.HistoryStore.load(path, cal, k=a.sessions)
        r_ = timed(rd, max(3, R // 6))
        sm = summary(r_)
        record("M2-B17", "read %d records (verified, lazy grid)" % n25, {"p5_rate": n25 / sm["max"], "p50_rate": n25 / sm["p50"], "time": sm}, "records/s")
        h_a = flowstore.HistoryStore.load(path, cal, k=a.sessions).content_hash()
        record("M2-B17", "hash after round trip equals", h_a == st25.content_hash(), "bool")
        snap_path = tmp / "store.snap"
        st25.snapshot_to(snap_path)
        record("M2-B16", "snapshot bytes", snap_path.stat().st_size, "bytes (file, shared by all workers)")
        for label, fn in (("store load (text)", lambda: flowstore.HistoryStore.load(path, cal, k=a.sessions)),
                          ("snapshot bytes copy", lambda: flowstore.HistoryStore.from_snapshot(snap_path.read_bytes(), cal))):
            sm = summary(timed(fn, max(3, R // 6)))
            record("M2-B16", label + " seconds per worker start", sm, "s")

        def mm_load():
            with open(snap_path, "rb") as fh:
                m = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
                st = flowstore.HistoryStore.from_snapshot(m, cal)
            return st
        keep = []

        def mm_keep():
            keep.append(mm_load())
        sm = summary(timed(mm_keep, max(3, R // 6)))
        record("M2-B16", "mmap snapshot (zero copy) seconds per worker start", sm, "s")
        keep.clear()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # per-worker private bytes: fresh subprocess per option
    code = ("import sys,time;sys.path[:0]=%r;"
            "from option_features import flowstore,flowgrid;import json,mmap;sys.path.insert(0,%r);import m2a_benchmark as B;"
            "cal=flowgrid.Calendar([('2026-%%02d-%%02d'%%(1+i//28,1+i%%28),390) for i in range(%d)]);"
            "r0=B.rss_bytes()[0];t=time.perf_counter();%s;dt=time.perf_counter()-t;st.baseline('C0000','premium',300,cal.ids[-1],20);"
            "print(json.dumps({'seconds':dt,'rss_delta':B.rss_bytes()[0]-r0}))")
    tmp = Path(tempfile.mkdtemp(prefix="m2a_bench_"))
    try:
        path, snap_path = tmp / "store.lf", tmp / "store.snap"
        store.dump_to(path)
        store.snapshot_to(snap_path)
        base = [str(ROOT / "packages" / "features" / "src"), str(ROOT / "packages" / "option-contracts" / "src")]
        variants = {"store load (text)": "st=flowstore.HistoryStore.load(%r,cal,k=20)" % str(path),
                    "snapshot read into bytes": "st=flowstore.HistoryStore.from_snapshot(open(%r,'rb').read(),cal)" % str(snap_path),
                    "mmap snapshot": "f=open(%r,'rb');m=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ);st=flowstore.HistoryStore.from_snapshot(m,cal)" % str(snap_path)}
        for label, stmt in variants.items():
            res = subprocess.run([sys.executable, "-c", code % (base, str(ROOT / "tools"), a.sessions, stmt)], capture_output=True, text=True)
            try:
                record("M2-B16", "fresh worker, " + label, json.loads(res.stdout.strip().splitlines()[-1]), "seconds, private rss delta bytes")
            except Exception:
                print("worker variant failed:", label, res.stderr[-300:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    wset, peak = rss_bytes()
    stats = store.stats()
    record("M2-B13", "store (k=20) series, records, est bytes", {"series": stats["series"], "records": stats["records"], "est_bytes": stats["est_bytes"],
                                                              "est_bytes_per_contract_series": stats["est_bytes"] // max(1, stats["series"])}, "(contract-level series, 5 metrics each)")
    record("M2-B13", "process working set and peak (bench, includes all stores)", {"working_set": wset, "peak": peak}, "bytes")
    # P1-T1 marker
    try:
        p1 = json.loads((ROOT / "docs" / "p1" / "P1_T1_REPORT.json").read_text(encoding="utf-8"))
        out["p1_t1_marker"] = {k: p1[k] for k in ("sizes", "time_ratio_large_over_small") if k in p1}
        print("P1-T1 recorded marker:", json.dumps(out["p1_t1_marker"])[:300])
    except Exception as exc:
        print("P1-T1 marker unavailable:", exc)
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
