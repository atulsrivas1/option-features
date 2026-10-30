"""M2 units for the opt-in process-pool runner (docs/M1_RUNNER.md, "M2 families").

Label: synthetic workload, relative engineering budget. Synthetic data only; no claim about recorded data.

A unit is (underlying, session, cutoff) with evaluated sessions 21 to 25 (unit key `SYN1/21/045`; the cutoff field is the
index 0..77, cutoff i + 1 is T = open + 300 s x (index + 1)). Inputs come from qualification/synthetic/m2/perf/gen_m2_workloads.py
(read only): unit prints per (underlying, session), history records per series S0000.. and session 1..25. Series S%04d is
contract id s of the unit (contract level, series_count up to 6,000 in the store, 2,000 contracts in a size-M unit).

One unit computes (family `m2`; `all` adds the M1 unit): F1, F4, F17 (print pass families), F7, F18, F12 from one print tape,
F2a-d and F10 for every series from the history store (fused `flow_pack_many`, or the one-at-a-time calls with path=single,
equal bytes), and at the last cutoff F2b end-of-day and F20. The history store is built once per run in the parent
(generation), transferred to workers as a binary M2BIN snapshot under a NEW file name per generation, attached read-only,
verified by content_hash() and frozen with gc.freeze(). Results never depend on the transfer form.
"""
import datetime
import gc
import hashlib
import json
import os
import sys
import time
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "qualification" / "synthetic" / "m2" / "perf")]
import gen_m2_workloads as G  # noqa: E402
from option_features import episodes, flowgrid, flowrank, flowresult, flowstore, m2prints, printtape  # noqa: E402

from . import workload  # noqa: E402

M2_FAMILIES = ("prints", "window", "volume", "concentration", "grid", "baseline", "history", "episodes", "store", "m2", "all")
STORE_SESSIONS = 25
WINDOW_S = 300
LAST_CUTOFF = G.CUTOFFS - 1
PATHS = ("batched", "single")
CACHES = ("warm", "cold", "off")
PARAM_NAMES = ("window_s", "premium_threshold", "n_large", "conc_threshold", "baseline_n", "k_history", "quiet_gap", "x_percent")
STORE_MUTATION_KINDS = ("history", "calendar")
MUTATION_KINDS = ("print", "contract", "param") + STORE_MUTATION_KINDS
SERIES_BYTES_BUDGET = 512 * (1 << 20)
SERIES_BYTES_HARD = 1 << 30


def is_m2(spec):
    return spec.family != "m1"


def uses_store(spec):
    return spec.family in ("history", "baseline", "store", "m2", "all")


def session_date(k):
    return (datetime.date(2026, 1, 1) + datetime.timedelta(days=k - 1)).isoformat()


def parse_mutation(text):
    if text is None:
        return None
    m = json.loads(text) if isinstance(text, str) else text
    if not isinstance(m, dict) or m.get("kind") not in MUTATION_KINDS:
        raise ValueError("mutation kind %r does not apply to an M2 run (expected one of %s)" % (m.get("kind") if isinstance(m, dict) else m, ", ".join(MUTATION_KINDS)))
    if m["kind"] == "param" and m.get("name") not in PARAM_NAMES:
        raise ValueError("mutation param name %r does not apply (expected one of %s)" % (m.get("name"), ", ".join(PARAM_NAMES)))
    return m


def validate_m2(spec):
    if spec.family not in M2_FAMILIES:
        raise ValueError("unknown family %r (expected m1 or one of %s)" % (spec.family, ", ".join(M2_FAMILIES)))
    for s in spec.sessions:
        if not 21 <= s <= 25:
            raise ValueError("M2 evaluated sessions are 21 to 25, got %r" % (s,))
    if spec.series_count not in range(1, 6001):
        raise ValueError("series_count must be 1..6000")
    if spec.history_sessions not in (20, 25):
        raise ValueError("history_sessions must be 20 or 25")
    if spec.path not in PATHS or spec.cache.split(":")[0] not in CACHES + ("limited",):
        raise ValueError("bad path or cache")
    if spec.unit_prints is not None and (type(spec.unit_prints) is not int or spec.unit_prints < 10):
        raise ValueError("unit_prints must be an int >= 10")
    parse_mutation(spec.mutation)
    params(spec)
    return spec


def params(spec):
    base = {"window_s": WINDOW_S, "premium_threshold": G.LARGE_PREM, "n_large": 1, "conc_threshold": "3/5", "baseline_n": 2,
            "k_history": spec.history_sessions, "quiet_gap": 1, "x_percent": 5}
    if spec.params:
        base.update(json.loads(spec.params) if isinstance(spec.params, str) else spec.params)
    m = parse_mutation(spec.mutation)
    if m and m["kind"] == "param":
        v = m["value"]
        base[m["name"]] = v if m["name"] == "conc_threshold" else int(v)
    return base


# ------------------------------------------------------------------------------------------------ history store
def calendar_sessions(mutation=None):
    sessions = [(session_date(k), G.minutes_of(k)) for k in range(1, STORE_SESSIONS + 1)]
    m = mutation if mutation and mutation["kind"] == "calendar" else None
    if m:
        sid = session_date(int(m["session_id"]))
        if m["field"] == "minutes":
            sessions = [(s, int(m["value"]) if s == sid else mins) for s, mins in sessions]
        elif m["field"] == "drop":
            sessions = [(s, mins) for s, mins in sessions if s != sid]
        else:
            raise ValueError("calendar mutation field must be minutes or drop")
    return sessions


def make_calendar(mutation=None):
    return flowgrid.Calendar(calendar_sessions(mutation))


def build_store(seed, series_count, mutation=None):
    """Parent-side generation: the store of S0000..S{n-1}, sessions 1..25, five metrics, window 300 s, ring 25."""
    mutation = parse_mutation(mutation) if not isinstance(mutation, (dict, type(None))) else mutation
    cal = make_calendar(mutation)
    store = flowstore.HistoryStore(cal, k=STORE_SESSIONS)
    hm = mutation if mutation and mutation["kind"] == "history" else None
    in_cal = set(cal.ids)
    for s in range(series_count):
        sid = "S%04d" % s
        for k in range(1, STORE_SESSIONS + 1):
            date = session_date(k)
            if date not in in_cal:
                continue
            _c, d = G.series_session(seed, s, k)
            for m in G.METRICS:
                nz = sorted(d[m].items())
                idx, vals = [b for b, _ in nz], [v for _, v in nz]
                total, complete = sum(vals), True
                if hm and hm["series_id"] == sid and hm["metric"] == m and int(hm["session_id"]) == k:
                    val = json.loads(hm["value"]) if isinstance(hm["value"], str) else hm["value"]
                    if hm["field"] == "grid":
                        idx, vals = [int(i) for i, _ in val], [int(v) for _, v in val]
                    elif hm["field"] == "total":
                        total = int(val)
                    elif hm["field"] == "complete":
                        complete = bool(val)
                    else:
                        raise ValueError("history mutation field must be grid, total or complete")
                store.append(sid, m, WINDOW_S, date, vals, total=total, grid_idx=idx, complete=complete)
    return store


# ------------------------------------------------------------------------------------------------ per-process context
class Context:
    """Per-process derived data: the attached or built store and a bounded cache of print tapes (never shared,
    never part of a result)."""

    def __init__(self):
        self.store = None
        self.store_id = None        # (path, content hash) of the attached snapshot, or the built store's hash
        self.tapes = {}
        self.timing = {}
        self.facts = {}


def attach_or_adopt(ctx, setup, built_store=None):
    """Worker start: attach the snapshot (or adopt a store built in this process), compare content_hash(), gc.freeze().
    Returns the facts for the run log (never a result)."""
    t0 = time.perf_counter()
    if ctx.store_id == (setup["path"], setup["content_hash"]) and ctx.store is not None:
        return dict(ctx.facts, reused=True, attach_s=0.0)
    cal = make_calendar(parse_mutation(setup["mutation"]) if setup.get("mutation") else None)
    if ctx.store is not None:
        ctx.store.close_mapping() if hasattr(ctx.store, "close_mapping") else None
        ctx.store = None
        gc.collect()
    priv0 = private_bytes()
    if built_store is not None:
        store = built_store
        t1 = time.perf_counter()
    else:
        store = flowstore.HistoryStore.attach_binary(setup["path"], cal, k=STORE_SESSIONS)
        t1 = time.perf_counter()
    h = store.content_hash()
    if h != setup["content_hash"]:
        raise flowresult.M2StructuralError("snapshot_hash_mismatch", "content_hash after attach differs from the generation hash")
    t2 = time.perf_counter()
    gc.collect()
    gc.freeze()
    t3 = time.perf_counter()
    ctx.store, ctx.store_id = store, (setup["path"], setup["content_hash"])
    priv1 = private_bytes()
    st = store.stats()
    ctx.facts = {"reused": False, "attach_s": t1 - t0, "content_hash_s": t2 - t1, "freeze_s": t3 - t2, "total_s": t3 - t0,
            "private_bytes": max(0, priv1 - priv0), "shared_mapped_bytes": setup.get("file_bytes") if built_store is None else 0, "frozen_objects": gc.get_freeze_count(),
            "est_bytes": st.get("est_bytes"), "records": st.get("records"), "series": st.get("series")}
    return dict(ctx.facts)


def private_bytes():
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return int(c.PrivateUsage)
    try:
        for line in open("/proc/self/status"):
            if line.startswith("RssAnon:"):
                return int(line.split()[1]) * 1024
    except OSError:
        pass
    return 0


# ------------------------------------------------------------------------------------------------ inputs
def unit_inputs(spec, u, k, ctx):
    """prints, contracts (tape form), tape for (underlying, session); cached per process unless cache is off/cold."""
    ck = (spec.seed, u, k, spec.unit_prints, spec.mutation if parse_mutation(spec.mutation) and parse_mutation(spec.mutation)["kind"] in ("print", "contract") else None)
    got = ctx.tapes.get(ck) if spec.cache == "warm" or spec.cache.startswith("limited") else None
    if got is not None:
        return got
    t0 = time.perf_counter()
    prints = list(G.unit_prints(spec.seed, u, k, spec.unit_prints))
    lane = G.lane(u)
    cons = {}
    for p in prints:
        c = p[0]
        if c not in cons:
            right, strike, exp = G.contract(c)
            cons[c] = (right, strike, exp, lane)
    m = parse_mutation(spec.mutation)
    if m and m["kind"] == "print":
        i, f = int(m["index"]), m["field"]
        pos = {"price": 2, "size": 3, "multiplier": 4, "condition_excluded": 5, "time_ns": 1, "seq": 6}[f]
        p = list(prints[i])
        p[pos] = bool(m["value"]) if f == "condition_excluded" else int(m["value"])
        prints[i] = tuple(p)
    if m and m["kind"] == "contract":
        cid = int(m["contract_id"])
        right, strike, exp, ln = cons.get(cid, (*G.contract(cid), lane))
        f, v = m["field"], m["value"]
        right, strike, exp, ln = (v if f == "right" else right, int(v) if f == "strike" else strike,
                                  v if f == "expiry" else exp, v if f == "lane" else ln)
        cons[cid] = (right, strike, exp, ln)
    ctx.timing["synthesis_s"] = ctx.timing.get("synthesis_s", 0.0) + time.perf_counter() - t0
    tape = printtape.build_tape(prints, cons)
    got = (prints, cons, tape, lane)
    if spec.cache == "warm" or spec.cache.startswith("limited"):
        limit = 1 if spec.cache.startswith("limited") else 4
        while len(ctx.tapes) >= limit:
            del ctx.tapes[next(iter(ctx.tapes))]
        ctx.tapes[ck] = got
    return got


def window_scan(tape, lane, start, end):
    """Per contract index: [premium, volume, count] of the eligible prints in [start, end] (one scan)."""
    from bisect import bisect_left, bisect_right
    out = {}
    for g in tape.select(lane, "all"):
        t = g.t
        a, b = bisect_left(t, start), bisect_right(t, end)
        if b > a:
            for ci, p, s in zip(g.ci[a:b], g.p[a:b], g.s[a:b]):
                e = out.get(ci)
                if e is None:
                    out[ci] = [p, s, 1]
                else:
                    e[0] += p
                    e[1] += s
                    e[2] += 1
    return out


def day_totals(tape, lane):
    out = {}
    for g in tape.select(lane, "all"):
        for ci, s in zip(g.ci, g.s):
            out[ci] = out.get(ci, 0) + s
    return out


def wire(x):
    if isinstance(x, flowresult.Result):
        return flowresult.to_wire(x)
    return m2prints.to_wire(x)


# ------------------------------------------------------------------------------------------------ the unit
def compute_m2_unit(spec, key, ctx, m1_bytes=None):
    u, k, c = workload.parse_key(key)
    fam = spec.family
    pr = params(spec)
    prints, cons, tape, lane = unit_inputs(spec, u, k, ctx)
    open_ns = G.session_open_ns(k)
    T = open_ns + (c + 1) * G.B_NS
    t0 = time.perf_counter()
    doc = {"unit": key}
    thr, win = pr["premium_threshold"], pr["window_s"]
    sid = session_date(k)
    kw = {"open_ns": open_ns, "lane": lane}
    if fam in ("prints", "m2", "all"):
        doc["f1"] = wire(m2prints.f1_premium_surge(tape, T, open_ns, lane=lane))
    if fam in ("prints", "window", "m2", "all"):
        doc["f4"] = wire(m2prints.f4_large_prints(tape, T, window_s=win, threshold_ticks=thr, n=pr["n_large"], **kw))
        doc["f17"] = [wire(r) for r in m2prints.f17_many(tape, T, window_s=win, threshold_ticks=thr, **kw)]
    if fam in ("concentration", "m2", "all"):
        doc["f7"] = wire(m2prints.f7_concentration(tape, T, window_s=win, share_threshold=pr["conc_threshold"], **kw))
    if fam in ("volume", "m2", "all"):
        doc["f18"] = wire(m2prints.f18_put_share(tape, T, window_s=win, at_least="1/2", at_most="1/4", **kw))
    if fam in ("episodes", "m2", "all"):
        doc["f12"] = wire(episodes.f12_from_tape(tape, T, open_ns, quiet_gap=pr["quiet_gap"], lane=lane))
    if fam == "grid":
        doc["grid"] = grid_digest(prints, cons, k, lane) if c == 0 else None
    if fam in ("history", "baseline", "store", "m2", "all"):
        store = ctx.store
        scan = window_scan(tape, lane, max(T - win * G.NS, open_ns), T)
        series = []
        for s in range(spec.series_count):
            ci = tape.cidx.get(s)
            e = scan.get(ci) if ci is not None else None
            series.append(("S%04d" % s, *(e if e else (0, 0, 0)), None))
        sess = flowrank.SessionInfo(sid, open_ns, open_ns + G.minutes_of(k) * 60 * G.NS, G.minutes_of(k), True, "live", None, None)
        K, X, N = pr["k_history"], pr["x_percent"], pr["baseline_n"]
        if fam == "store":
            doc["store"] = [[sr[0], (v.n if (v := store.baseline(sr[0], "contracts", WINDOW_S, sid, K, "stock")) else None)] for sr in series]
        elif spec.path == "batched":
            pack = flowrank.flow_pack_many(store, sess, T, win, series, X=X, N=N, K=K)
            if fam == "history":
                doc["history"] = [[wire(r) for r in p[:4]] for p in pack]
            elif fam == "baseline":
                doc["baseline"] = [wire(p[4]) for p in pack]
            else:
                doc["pack"] = [[wire(r) for r in p] for p in pack]
        else:
            pack = []
            for s_, p_, v_, c_, cov in series:
                a_ = flowrank.f2_rank(store, s_, "premium", p_, sess, T, win, "intraday", X, K)
                b_ = flowrank.f2_rank(store, s_, "contracts", v_, sess, T, win, "intraday", X, K)
                c2 = flowrank.f2_rank(store, s_, "prints", c_, sess, T, win, "intraday", X, K)
                pack.append((a_, b_, c2, flowrank.f2d_combine(a_, b_, c2, win, X),
                             flowrank.f10_baseline(store, s_, v_, sess, T, win, N, K)))
            if fam == "history":
                doc["history"] = [[wire(r) for r in p[:4]] for p in pack]
            elif fam == "baseline":
                doc["baseline"] = [wire(p[4]) for p in pack]
            else:
                doc["pack"] = [[wire(r) for r in p] for p in pack]
        if c == LAST_CUTOFF and fam in ("baseline", "m2", "all"):
            tots = day_totals(tape, lane)
            eod = []
            for s in range(spec.series_count):
                ci = tape.cidx.get(s)
                total = tots.get(ci, 0) if ci is not None else 0
                es = sess._replace(total=total, total_source="stream")
                sid_s = "S%04d" % s
                eod.append([wire(flowrank.f2_rank(store, sid_s, "contracts", None, es, T, win, "end_of_day", X, K)),
                            wire(flowrank.f20_baseline(store, sid_s, "contracts", es, T, win, N, K))])
            doc["eod"] = eod
    ctx.timing["compute_s"] = ctx.timing.get("compute_s", 0.0) + time.perf_counter() - t0
    ts = time.perf_counter()
    if m1_bytes is not None:
        doc["m1"] = json.loads(m1_bytes)
    out = json.dumps(doc, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ctx.timing["serialize_s"] = ctx.timing.get("serialize_s", 0.0) + time.perf_counter() - ts
    return out


def build_grid(prints, cons, k, lane):
    contracts = {c: flowgrid.Contract(v[0], v[1], v[2], v[3], "SYN") for c, v in cons.items()}
    open_ns = G.session_open_ns(k)
    return flowgrid.build_session_records(prints, contracts, session_date(k), open_ns, open_ns + G.minutes_of(k) * 60 * G.NS,
                                          G.minutes_of(k), (WINDOW_S,), lane, "NAME", True, "scanned")


def grid_digest(prints, cons, k, lane):
    """Compact trade-to-grid digest of one session (contract series: id, metric, session total, nonzero points)."""
    b = build_grid(prints, cons, k, lane)
    lines = sorted("%s,%s,%d,%d" % (r.series_id, r.metric, r.total, len(r.idx)) for r in b.records)
    return {"records": len(b.records), "eligible": b.eligible_count,
            "sha256": hashlib.sha256(chr(10).join(lines).encode()).hexdigest()}


def grid_truth_check(prints, cons, k, lane, build=None):
    """Truth check against the generator reference (G.trade_to_grid, bins of 60 s): every contract series total of
    premium, contracts and prints equals the sum of the reference bins, and the series set equals the reference set.
    (The library grid holds closed 300 s window values, so the manifest bin digest itself is not comparable; totals are.)"""
    b = build or build_grid(prints, cons, k, lane)
    ref = G.trade_to_grid(prints, G.session_open_ns(k), G.minutes_of(k))
    got = {}
    for r in b.records:
        if r.series_id != "NAME":
            got.setdefault(r.series_id, {})[r.metric] = r.total
    if set(got) != set(ref):
        return False
    for cid, d in ref.items():
        for m in ("premium", "contracts", "prints"):
            if got[cid][m] != sum(d[m].values()):
                return False
    return True
