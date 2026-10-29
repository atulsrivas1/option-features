"""Opt-in process-pool runner over independent units (underlying x session x cutoff). See docs/M1_RUNNER.md.

The runner is opt-in, default single-process: workers=1 runs in this process and is the reference path. The
pool is a thin driver; every number is computed by the pure modules via workload.compute_unit. It adds no
result field and changes no result byte: workers return (unit key, result bytes), the parent merges by unit key
and hashes in key order, never in completion order. Worker count, ids, timings and counters go only to the
run log (RunResult.log, and the log file when given), never into results or output files.

Failure semantics: a worker crash, a chunk timeout, a missing or duplicate unit, a worker exception, a
mismatching interpreter or an aggregate worker RSS above the hard limit raises a named RunnerError, the pool is
terminated and NO output file is written (outputs are written only after every unit is merged, temp file then
rename).

Synthetic workload, relative engineering budget.
"""
import hashlib
import json
import multiprocessing as mp
import os
import platform
import sys
import time
import traceback
from collections import deque
from multiprocessing.connection import wait

from . import workload
from .workload import Spec, apply_order, parse_key  # noqa: F401  (Spec re-exported)

GIB = 1 << 30
DEFAULT_WORKERS = 1
PLACEHOLDER_B9_PEAK_BYTES = 2 * GIB    # until the first B7 run measures the per-process peak
AGGREGATE_HARD_BYTES = 8 * GIB         # aggregate worker RSS hard limit
HASHSEED = "0"
HELLO_TIMEOUT_S = 180.0


class RunnerError(RuntimeError):
    """Base of every named runner failure."""


class WorkerCrashedError(RunnerError):
    pass


class WorkerTimeoutError(RunnerError):
    pass


class MissingUnitError(RunnerError):
    pass


class DuplicateUnitError(RunnerError):
    pass


class MemoryLimitError(RunnerError):
    pass


class InterpreterMismatchError(RunnerError):
    pass


class WorkerFailedError(RunnerError):
    pass


# ----------------------------------------------------------------------------- caps (pure, injectable)
def system_cores():
    try:
        return len(os.sched_getaffinity(0))
    except AttributeError:
        return os.cpu_count() or 1


def system_ram_bytes():
    if os.name == "nt":
        import ctypes

        class MEMSTAT(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MEMSTAT()
        m.dwLength = ctypes.sizeof(MEMSTAT)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return int(m.ullTotalPhys)
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")


def peak_rss_bytes():
    """OS-measured peak resident set of THIS process."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t)]
        k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return int(c.PeakWorkingSetSize)
    import resource
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * (1 if sys.platform == "darwin" else 1024)


def worker_cap(cores=None, ram_bytes=None, b9_peak_bytes=PLACEHOLDER_B9_PEAK_BYTES, aggregate_hard_bytes=AGGREGATE_HARD_BYTES):
    """cap = min(cores, RAM / B9 peak, aggregate hard limit / B9 peak), at least 1. Inputs are injectable."""
    cores = system_cores() if cores is None else cores
    ram_bytes = system_ram_bytes() if ram_bytes is None else ram_bytes
    if cores < 1 or ram_bytes < 1 or b9_peak_bytes < 1 or aggregate_hard_bytes < 1:
        raise ValueError("cores, ram_bytes, b9_peak_bytes and aggregate_hard_bytes must be positive")
    by_ram, by_agg = ram_bytes // b9_peak_bytes, aggregate_hard_bytes // b9_peak_bytes
    return {"cores": cores, "ram_bytes": ram_bytes, "b9_peak_bytes": b9_peak_bytes, "aggregate_hard_bytes": aggregate_hard_bytes,
            "cap_by_cores": cores, "cap_by_ram": by_ram, "cap_by_aggregate": by_agg,
            "cap": max(1, min(cores, by_ram, by_agg))}


def resolve_workers(requested, cap):
    """(workers used, clamp) ; clamp is None or {requested, used, cap}. A clamp is reported, never an error."""
    if type(requested) is not int or requested < 1:
        raise ValueError("workers must be an integer >= 1")
    if requested <= cap["cap"]:
        return requested, None
    return cap["cap"], {"requested": requested, "used": cap["cap"], "cap": cap["cap"]}


# ----------------------------------------------------------------------------- merge by unit key (pure)
def unit_digest(value):
    return value if isinstance(value, str) else hashlib.sha256(value).hexdigest()


def merge_units(pairs, expected_keys):
    """Sort (unit_key, value) pairs by unit key, never by arrival order; every expected key exactly once."""
    expected, seen = set(expected_keys), {}
    for key, value in pairs:
        if key in seen:
            raise DuplicateUnitError("unit %s was returned more than once" % key)
        if key not in expected:
            raise RunnerError("unexpected unit %s" % key)
        seen[key] = value
    missing = sorted(expected - set(seen))
    if missing:
        raise MissingUnitError("%d unit(s) missing, first: %s" % (len(missing), ", ".join(missing[:5])))
    return [(k, seen[k]) for k in sorted(seen)]


def result_hash(sorted_pairs):
    """sha256 over 'unit_key LF unit_sha256 LF' in unit-key order (values: bytes or a hex digest)."""
    h = hashlib.sha256()
    for key, value in sorted_pairs:
        h.update(("%s\n%s\n" % (key, unit_digest(value))).encode("ascii"))
    return h.hexdigest()


# ----------------------------------------------------------------------------- chunking
def make_chunks(keys, batch_size, order="natural"):
    """Chunks of one (underlying, session) and consecutive cutoffs, at most batch_size units; the chunk list and the
    units inside a chunk are permuted by `order` (a test lever: results must not depend on it)."""
    groups = {}
    for key in sorted(keys):
        u, s, c = parse_key(key)
        groups.setdefault((u, s), []).append(key)
    chunks = []
    for g in sorted(groups):
        ks = groups[g]
        size = len(ks) if batch_size is None else max(1, batch_size)
        part = [ks[i:i + size] for i in range(0, len(ks), size)]
        part.reverse()  # highest cutoff first: a worker that keeps the session history built for it serves the rest from cache
        chunks.extend(part)
    chunks = [apply_order(c, order) for c in chunks]
    return apply_order(chunks, order)


def auto_batch_size(unit_count, workers, group_size):
    if workers <= 1:
        return group_size
    return max(1, min(group_size, -(-unit_count // (6 * workers))))


def chunk_group(keys):
    u, s, _ = parse_key(keys[0])
    return (u, s)


def chunk_horizon(keys):
    return max(parse_key(k)[2] for k in keys)


def pick_chunk(pending, last, active):
    """Scheduling heuristic only (never affects result bytes): index into `pending` (a list of (cid, keys)) for an
    idle worker. last = (group, horizon) the worker holds in cache or None; active = groups other workers hold.
    Prefer a chunk the worker can serve from its cached session history; else the first chunk of a group no
    other worker is on; else the head."""
    if last is not None:
        for i, (_, keys) in enumerate(pending):
            if chunk_group(keys) == last[0] and chunk_horizon(keys) <= last[1]:
                return i
    for i, (_, keys) in enumerate(pending):
        if chunk_group(keys) not in active:
            return i
    return 0


# ----------------------------------------------------------------------------- the unit loop (shared by both paths)
def _compute_chunk(spec, keys, fault, state, emit, worker_id):
    """Compute the units of one chunk. state: {'history': SessionHistory|None, 'units': int} (per worker or per run)."""
    out = []
    u, s, _ = parse_key(keys[0])
    horizon = (max(parse_key(k)[2] for k in keys) + 1) * workload.gen.CUTOFF_STEP_NS
    hist = state.get("history")
    if hist is None or hist.key != (spec.seed, spec.shape, u, s) or hist.horizon_ns < horizon:
        state["history"] = hist = workload.SessionHistory(spec, u, s, horizon)
    for key in keys:
        if fault and fault["kind"] == "hang_worker" and fault["worker"] == worker_id:
            time.sleep(10 ** 6)
        data = workload.compute_unit(spec, key, hist)
        state["units"] += 1
        if fault and fault["kind"] == "kill_worker" and fault["worker"] == worker_id and state["units"] >= fault["after_units"]:
            os._exit(137)
        if fault and fault["kind"] == "drop_unit" and fault["unit_key"] == key:
            continue
        out.append((key, hashlib.sha256(data).hexdigest(), data if emit == "full" else None))
    return out


def _env_info():
    import flint
    import option_features
    return {"executable": sys.executable, "version": sys.version, "flint": flint.__version__, "platform": platform.platform(),
            "hashseed": os.environ.get("PYTHONHASHSEED"), "hash_randomization": sys.flags.hash_randomization,
            "option_features": os.path.dirname(os.path.abspath(option_features.__file__))}


_ENV_MUST_MATCH = ("executable", "version", "flint", "platform", "option_features")


def _worker_main(conn, wid):
    """Persistent worker: sets its own process-global switches, says hello, then serves chunks until told to stop."""
    try:
        from flint import ctx
        ctx.threads = 1                      # each worker sets the numerical switch itself (also set per call in the library)
        info = _env_info()
        info["pid"] = os.getpid()
        conn.send(("hello", wid, info))
        state = {"history": None, "units": 0}
        while True:
            try:
                msg = conn.recv()
            except (EOFError, OSError):
                return
            if msg[0] == "stop":
                return
            _, cid, spec, keys, emit, fault, count, run_no = msg
            if state.get("run") != run_no:   # no state is shared between runs: drop the cached session history
                state["run"], state["history"] = run_no, None
            t0, c0 = time.perf_counter(), time.process_time()
            try:
                counter = workload.ArbCounter() if count else None
                if counter:
                    counter.__enter__()
                try:
                    res = _compute_chunk(spec, keys, fault, state, emit, wid)
                finally:
                    if counter:
                        counter.__exit__()
                stats = {"wall_s": time.perf_counter() - t0, "cpu_s": time.process_time() - c0, "units": len(res),
                         "rss_peak": peak_rss_bytes(), "arb": counter.n if counter else None, "history_updates": state["history"].n_updates}
                conn.send(("done", cid, res, stats))
            except BaseException:  # noqa: BLE001 - reported to the parent, which fails the run with a named error
                conn.send(("error", cid, traceback.format_exc()))
                return
    except BaseException:  # noqa: BLE001
        try:
            conn.send(("error", None, traceback.format_exc()))
        except Exception:
            pass


# ----------------------------------------------------------------------------- results and outputs
class RunResult:
    def __init__(self, spec, pairs, emit, log):
        self.spec = spec
        self.unit_count = len(pairs)
        self.unit_sha256 = {k: unit_digest(v) for k, v in pairs}
        self.result_sha256 = result_hash(pairs)
        self.units = [(k, v) for k, v in pairs] if emit == "full" else None
        self.log = log

    def digests_bytes(self):
        doc = {"result_sha256": self.result_sha256, "unit_count": self.unit_count, "spec": dict(self.spec._asdict()),
               "units": self.unit_sha256}
        return (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def write_outputs(result, out_dir):
    """Write digests.json (and results.jsonl for emit=full) only now, after every unit is merged: temp then rename."""
    files = {"digests.json": result.digests_bytes()}
    if result.units is not None:
        files["results.jsonl"] = b"".join(v + b"\n" for _, v in result.units)
    os.makedirs(out_dir, exist_ok=True)
    temps = []
    try:
        for name, data in files.items():
            tmp = os.path.join(out_dir, ".%s.tmp" % name)
            temps.append(tmp)
            with open(tmp, "wb") as f:
                f.write(data)
        for name in files:
            os.replace(os.path.join(out_dir, ".%s.tmp" % name), os.path.join(out_dir, name))
    except BaseException:
        for t in temps:
            try:
                os.remove(t)
            except OSError:
                pass
        raise


def _check_fault(fault, workers_used):
    if fault is None:
        return None
    kinds = {"kill_worker": ("worker", "after_units"), "drop_unit": ("unit_key",), "hang_worker": ("worker",)}
    if not isinstance(fault, dict) or fault.get("kind") not in kinds:
        raise ValueError("unknown fault %r" % (fault,))
    if set(fault) != {"kind", *kinds[fault["kind"]]}:
        raise ValueError("fault fields must be exactly %s" % (("kind",) + kinds[fault["kind"]],))
    if fault["kind"] in ("kill_worker", "hang_worker") and workers_used < 2:
        raise ValueError("%s needs workers >= 2 (the in-process reference path has no worker to kill)" % fault["kind"])
    if fault["kind"] in ("kill_worker", "hang_worker") and not 0 <= fault["worker"] < workers_used:
        raise ValueError("fault worker %r is not one of the %d workers" % (fault["worker"], workers_used))
    return dict(fault)


def _exitcode(proc):
    proc.join(2)
    return proc.exitcode


class Runner:
    """workers=1: in-process reference path. workers>=2: persistent spawn pool (opt-in). Use as a context manager."""

    def __init__(self, workers=DEFAULT_WORKERS, b9_peak_bytes=PLACEHOLDER_B9_PEAK_BYTES, aggregate_hard_bytes=AGGREGATE_HARD_BYTES,
                 cores=None, ram_bytes=None, timeout_s=7200.0, fault=None, count_arb=False, log=None):
        self.cap = worker_cap(cores, ram_bytes, b9_peak_bytes, aggregate_hard_bytes)
        self.workers_requested = workers
        self.workers_used, self.clamp = resolve_workers(workers, self.cap)
        self.fault = _check_fault(fault, self.workers_used)
        self.aggregate_hard_bytes, self.timeout_s, self.count_arb, self.log_path = aggregate_hard_bytes, timeout_s, count_arb, log
        self._procs, self._conns, self._env, self._broken, self._rss = [], [], [], False, {}
        self._seq = 0

    # -- lifecycle
    def __enter__(self):
        if self.workers_used >= 2:
            self._start_pool()
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def _log(self, event, **kw):
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"event": event, **kw}, sort_keys=True, default=str) + "\n")

    def _start_pool(self):
        ctx = mp.get_context("spawn")
        previous = os.environ.get("PYTHONHASHSEED")
        os.environ["PYTHONHASHSEED"] = HASHSEED          # inherited by the spawned interpreters
        try:
            for wid in range(self.workers_used):
                parent, child = ctx.Pipe(duplex=True)
                p = ctx.Process(target=_worker_main, args=(child, wid), name="m1-runner-worker-%d" % wid, daemon=True)
                p.start()
                child.close()
                self._procs.append(p)
                self._conns.append(parent)
        finally:
            if previous is None:
                os.environ.pop("PYTHONHASHSEED", None)
            else:
                os.environ["PYTHONHASHSEED"] = previous
        mine = _env_info()
        self._env = [None] * self.workers_used
        deadline = time.monotonic() + HELLO_TIMEOUT_S
        try:
            while any(e is None for e in self._env):
                waiting = [i for i, e in enumerate(self._env) if e is None]
                ready = wait([self._conns[i] for i in waiting] + [self._procs[i].sentinel for i in waiting], timeout=1.0)
                for i in waiting:
                    if self._conns[i] in ready:
                        try:
                            msg = self._conns[i].recv()
                        except (EOFError, OSError):
                            raise WorkerCrashedError("worker %d exited during start (exit code %s)" % (i, _exitcode(self._procs[i])))
                        if msg[0] == "error":
                            raise WorkerFailedError("worker %d failed to start:\n%s" % (i, msg[2]))
                        self._env[i] = msg[2]
                    elif self._procs[i].sentinel in ready:
                        raise WorkerCrashedError("worker %d exited during start (exit code %s)" % (i, _exitcode(self._procs[i])))
                if time.monotonic() > deadline:
                    raise WorkerTimeoutError("workers did not start within %.0f s" % HELLO_TIMEOUT_S)
            for i, env in enumerate(self._env):
                for key in _ENV_MUST_MATCH:
                    if env[key] != mine[key]:
                        raise InterpreterMismatchError("worker %d differs from the parent in %s: %r vs %r" % (i, key, env[key], mine[key]))
                if i and env["hashseed"] != self._env[0]["hashseed"]:
                    raise InterpreterMismatchError("worker %d hash seed differs" % i)
        except BaseException:
            self._terminate()
            raise
        self._log("pool_started", workers=self.workers_used, env=self._env)

    def _terminate(self):
        self._broken = True
        for p in self._procs:
            if p.is_alive():
                p.kill()
        for p in self._procs:
            p.join(5)
        for c in self._conns:
            try:
                c.close()
            except OSError:
                pass

    def close(self):
        if self._procs and not self._broken:
            for c in self._conns:
                try:
                    c.send(("stop",))
                except (OSError, ValueError):
                    pass
            for p in self._procs:
                p.join(10)
            self._terminate()
        self._procs, self._conns = [], []

    # -- one run
    def run(self, spec, batch_size=None, order="natural", emit="digest", out_dir=None):
        spec.validate()
        if emit not in ("digest", "full"):
            raise ValueError("emit must be digest or full")
        if self.workers_used >= 2 and (self._broken or not self._procs):
            raise RunnerError("the worker pool is not running (use the Runner as a context manager; a failed run ends the pool)")
        self._seq += 1
        keys = workload.all_unit_keys(spec)
        group = len(spec.cutoffs)
        batch = batch_size if batch_size is not None else auto_batch_size(len(keys), self.workers_used, group)
        chunks = make_chunks(keys, batch, order)
        t0 = time.perf_counter()
        try:
            if self.workers_used == 1:
                pairs, stats = self._run_inline(spec, chunks, emit)
            else:
                pairs, stats = self._run_pool(spec, chunks, emit)
            merged = merge_units(pairs, keys)
        except RunnerError as e:
            self._log("run_failed", error=type(e).__name__, message=str(e))
            if self.workers_used >= 2:
                self._terminate()
            raise
        wall = time.perf_counter() - t0
        log = {"workers_requested": self.workers_requested, "workers_used": self.workers_used, "pool": self.workers_used >= 2,
               "clamp": self.clamp, "worker_cap": self.cap, "batch_size": batch, "chunks": len(chunks), "order": order,
               "wall_s": wall, "units_per_s": len(keys) / wall if wall else None, "worker_env": [dict(e) for e in self._env],
               **stats}
        result = RunResult(spec, merged, emit, log)
        if out_dir is not None:
            write_outputs(result, out_dir)
        self._log("run_done", result_sha256=result.result_sha256, **{k: v for k, v in log.items() if k != "worker_env"})
        return result

    def _summarise(self, rss_by_worker, arb, chunk_stats, parent_rss):
        per = [rss_by_worker.get(i, 0) for i in range(max(self.workers_used, 1))] if self.workers_used >= 2 else [parent_rss]
        out = {"peak_rss_per_worker_bytes": per, "aggregate_peak_rss_bytes": sum(per), "parent_peak_rss_bytes": parent_rss,
               "chunk_wall_s": chunk_stats}
        if arb:
            solves, total = arb["solves"], arb["price_interval"] + arb["forward"] + arb["bounds"]
            out["arb_calls_per_solve"] = {"solves": solves, "total": total, "mean": (total / solves) if solves else None, "counts": arb}
        return out

    def _run_inline(self, spec, chunks, emit):
        state, pairs, arb, walls = {"history": None, "units": 0}, [], {"price_interval": 0, "forward": 0, "bounds": 0, "solves": 0}, []
        counter = workload.ArbCounter() if self.count_arb else None
        if counter:
            counter.__enter__()
        try:
            for keys in chunks:
                t = time.perf_counter()
                pairs.extend(_compute_chunk(spec, keys, self.fault, state, emit, 0))
                walls.append(time.perf_counter() - t)
        finally:
            if counter:
                counter.__exit__()
                arb = counter.n
        return [(k, d if v is None else v) for k, d, v in pairs] if emit == "full" else [(k, d) for k, d, _ in pairs], \
            self._summarise({}, arb if counter else None, walls, peak_rss_bytes())

    def _run_pool(self, spec, chunks, emit):
        n = self.workers_used
        pending, inflight, pairs, rss, walls = list(enumerate(chunks)), {}, [], {}, []
        held = {}  # worker id -> (group, horizon) of the session history that worker holds
        arb = {"price_interval": 0, "forward": 0, "bounds": 0, "solves": 0}
        idle = deque(range(n))
        while pending or inflight:
            while pending and idle:
                wid = idle.popleft()
                active = {h[0] for w, h in held.items() if w != wid}
                cid, keys = pending.pop(pick_chunk(pending, held.get(wid), active))
                g, hz = chunk_group(keys), chunk_horizon(keys)
                held[wid] = (g, hz) if held.get(wid) is None or held[wid][0] != g or held[wid][1] < hz else held[wid]
                try:
                    self._conns[wid].send(("chunk", cid, spec, keys, emit, self.fault, self.count_arb, self._seq))
                except (OSError, ValueError):
                    raise WorkerCrashedError("worker %d is not reachable (exit code %s) while sending chunk %d" % (wid, _exitcode(self._procs[wid]), cid))
                inflight[wid] = (cid, keys, time.monotonic())
            if not inflight:
                break
            ready = set(wait([self._conns[w] for w in inflight] + [self._procs[w].sentinel for w in inflight], timeout=0.5))
            now = time.monotonic()
            for wid in list(inflight):
                cid, keys, started = inflight[wid]
                conn, proc = self._conns[wid], self._procs[wid]
                msg = None
                if conn in ready or proc.sentinel in ready:
                    try:
                        if conn.poll():
                            msg = conn.recv()
                    except (EOFError, OSError):
                        msg = None
                    if msg is None:
                        raise WorkerCrashedError("worker %d (pid %s) exited with code %s while processing chunk %d (units %s .. %s)" % (
                            wid, self._env[wid]["pid"], _exitcode(proc), cid, keys[0], keys[-1]))
                if msg is None:
                    if now - started > self.timeout_s:
                        raise WorkerTimeoutError("worker %d did not finish chunk %d (units %s .. %s) within %.1f s" % (
                            wid, cid, keys[0], keys[-1], self.timeout_s))
                    continue
                if msg[0] == "error":
                    raise WorkerFailedError("worker %d failed on chunk %d:\n%s" % (wid, cid, msg[2]))
                _, rcid, res, stats = msg
                del inflight[wid]
                idle.append(wid)
                pairs.extend((k, d if v is None else v) if emit == "full" else (k, d) for k, d, v in res)
                walls.append({"worker": wid, "chunk": rcid, "wall_s": stats["wall_s"], "cpu_s": stats["cpu_s"], "units": stats["units"]})
                rss[wid] = max(rss.get(wid, 0), stats["rss_peak"])
                if stats["arb"]:
                    for k, v in stats["arb"].items():
                        arb[k] += v
                total = sum(rss.values())
                if total > self.aggregate_hard_bytes:
                    raise MemoryLimitError("aggregate worker RSS %d bytes exceeds the hard limit %d bytes (worker %d just reported %d)" % (
                        total, self.aggregate_hard_bytes, wid, stats["rss_peak"]))
        for wid in range(n):  # a worker that died while idle after its last reply is still a failed run
            if not self._procs[wid].is_alive():
                raise WorkerCrashedError("worker %d exited with code %s before the run ended" % (wid, _exitcode(self._procs[wid])))
        return pairs, self._summarise(rss, arb if self.count_arb else None, walls, peak_rss_bytes())


def run(spec, workers=DEFAULT_WORKERS, **kw):
    """One-shot helper: build a Runner, run once, close it."""
    run_kw = {k: kw.pop(k) for k in ("batch_size", "order", "emit", "out_dir") if k in kw}
    with Runner(workers=workers, **kw) as r:
        return r.run(spec, **run_kw)
