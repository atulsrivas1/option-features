"""Test adapter (story A): maps the independently authored M2 correctness rows onto the library API.

Rows are never edited (qualification/synthetic/m2/correctness, read only; the loader verifies their hashes).
Owned outputs: M2-2 (F2a-c), M2-3 (F2d), M2-7 (F10), M2-8 (F20), M2-10 (F19), M2-12 (store). Rows of other
outputs (F1, F4, F7, F17, F18, F12: story B) are skipped here. `run_row` imports the library inside the call, so
on code without the modules every row fails individually instead of the suite failing at import.

Fixture payloads are raw (a history is a base value plus overrides per session, store ops are lists); this adapter
turns them into library objects. Fixture-level validation that belongs to the raw payload (duplicate session ids in
one history list, non-monotone override indexes) is done here in the structural precedence order of the contract:
print errors, duplicate_session, non_monotone_grid, then the library (calendar, window, threshold, delayed tag).

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12.
"""
import glob
import hashlib
import json
import os
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROWS_DIR = ROOT / "qualification" / "synthetic" / "m2" / "correctness"
ADD_DIR = ROWS_DIR / "additions"
OWNED = frozenset(("M2-2", "M2-3", "M2-7", "M2-8", "M2-10", "M2-12", "M2-GRID"))
NS = 1000000000


def _loader():
    if str(ROWS_DIR) not in sys.path:
        sys.path.insert(0, str(ROWS_DIR))
    import m2_load
    return m2_load


def load_rows(owned_only=True):
    """All rows (expanded by the fixture loader) of the owned outputs, in file order."""
    m2_load = _loader()
    rows = []
    for path in sorted(glob.glob(str(ROWS_DIR / "m2_cases_*.json"))) + sorted(glob.glob(str(ADD_DIR / "m2_cases_add_*.json"))):
        _, part = m2_load.load_dataset(path)
        rows.extend(r for r in part if (not owned_only) or r["output_id"] in OWNED)
    return rows


def manifest_hashes():
    pinned = {}
    for base, name in ((ROWS_DIR, "MANIFEST.sha256"), (ADD_DIR, "MANIFEST_ADDITIONS.sha256")):
        for line in (base / name).read_text(encoding="ascii").splitlines():
            parts = line.split()
            pinned[str((base / parts[-1].lstrip("*")).relative_to(ROWS_DIR)).replace(chr(92), "/")] = parts[0]
    return pinned


# ------------------------------------------------------------------ result to fixture form
def _show(x):
    if isinstance(x, Fraction):
        return int(x) if x.denominator == 1 else "%d/%d" % (x.numerator, x.denominator)
    if isinstance(x, dict):
        return {k: _show(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_show(v) for v in x]
    return x


def result_form(res):
    d = {"status": res.status, "reason": res.reason, "code": res.code, "value": _show(res.value), "fired": res.fired,
         "label": res.label, "coverage": res.coverage}
    if res.per_statistic is not None:
        d["per_statistic"] = _show(res.per_statistic)
    if res.parts_shown is not None:
        d["parts_shown"] = _show(res.parts_shown)
    return d


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


# ------------------------------------------------------------------ payload to objects
def _calendar(inp):
    from option_features.flowgrid import Calendar
    return Calendar([(c["session_id"], c["minutes"]) for c in inp["calendar"]])


def _session(inp):
    from option_features.flowrank import SessionInfo
    s = inp["session"]
    return SessionInfo(s["session_id"], s["open_ns"], s["close_ns"], s["minutes"], s["complete"], s["feed_delay_tag"],
                       s.get("total"), s.get("total_source"))


def _contracts(inp):
    from option_features.flowgrid import Contract
    return {cid: Contract(c["right"], c["strike"], c["expiry"], c["lane"], c["underlying"])
            for cid, c in (inp.get("contracts") or {}).items()}


def _abs_prints(inp):
    t = inp["t_ns"]
    out = []
    for p in inp.get("prints") or []:
        q = list(p)
        q[1] = t + p[1]
        out.append(tuple(q))
    return out


def _history_code(hist):
    """Payload-level structural codes of a raw history (fixture format), None if clean."""
    seen = set()
    for s in hist["sessions"]:
        if s["session_id"] in seen:
            return "duplicate_session"
        seen.add(s["session_id"])
    for s in hist["sessions"]:
        prev = None
        for idx, _ in s["gs"]["over"]:
            if idx < 0 or idx >= s["minutes"] or (prev is not None and idx <= prev):
                return "non_monotone_grid"
            prev = idx
    return None


def _dense(s):
    g = [s["gs"]["base"]] * s["minutes"]
    for idx, v in s["gs"]["over"]:
        g[idx] = v
    return g


def _store(inp, hist, k=20, metrics=None):
    """HistoryStore from a raw history payload (non-strict calendar: history may hold sessions outside it)."""
    from option_features.flowstore import HistoryStore
    # retention 60 (the hard cap): a raw fixture history may also hold today's own record or later sessions; a ring of
    # K would evict a needed prior session. Reads never use them (baseline = K calendar sessions before today).
    store = HistoryStore(_calendar(inp), k=60, strict_calendar=False)
    window = hist.get("window_s") or 300
    for s in sorted(hist["sessions"], key=lambda z: z["session_id"]):
        grid = _dense(s)
        if "put" in s:
            store.append(hist["series_id"], "put_volume", window, s["session_id"], grid, total=s["put"],
                         complete=s["complete"], lane=hist["lane"])
            store.append(hist["series_id"], "call_volume", window, s["session_id"], grid, total=s["call"],
                         complete=s["complete"], lane=hist["lane"])
        else:
            store.append(hist["series_id"], hist["metric"], window, s["session_id"], grid, total=s["total"],
                         complete=s["complete"], lane=hist["lane"])
    return store, window


def _coverage(w):
    return {"eligible_count": w.eligible_count, "nonstandard_count": w.nonstandard_count,
            "excluded_condition_count": w.excluded_condition_count, "unavailable_points": 0}


def _structural_prints(inp):
    from option_features.flowgrid import check_prints
    return check_prints(_abs_prints(inp), _contracts(inp))


def _invalid(output_id, code, inp):
    from option_features.flowresult import Result
    return Result.invalid(output_id, code, inp.get("series_id"), (inp.get("session") or {}).get("session_id"),
                          inp.get("t_ns"))


def _window_x(inp, prm, metric_key, w, side_filter="all"):
    from option_features.flowgrid import window_totals
    tot = window_totals(_abs_prints(inp), _contracts(inp), inp["t_ns"], w, lane=prm.get("lane", "stock"),
                        side_filter=side_filter, validate="full")
    return getattr(tot, metric_key), tot


_METRIC_KEY = {"premium": "premium", "contracts": "volume", "prints": "count"}


def _run_f2(row):
    from option_features.flowrank import f2_rank
    inp, prm = row["inputs"], row["params"]
    code = _structural_prints(inp) or _history_code(inp["history"])
    if code:
        return _invalid("M2-2", code, inp)
    form = prm.get("form", "intraday")
    w = prm.get("window_s", 300)
    metric = prm["metric"]
    store, hw = _store(inp, inp["history"], prm.get("K", 20))
    session = _session(inp)
    if form == "intraday":
        x, tot = _window_x(inp, prm, _METRIC_KEY[metric], w)
        cov = _coverage(tot)
    else:
        x, cov = session.total, None
    return f2_rank(store, inp["series_id"], metric, x, session, inp["t_ns"], window_s=hw if form != "intraday" else w,
                   form=form, X=prm.get("X", 5), K=prm.get("K", 20), lane=prm.get("lane", "stock"), coverage=cov)


def _run_f2d(row):
    from option_features.flowrank import f2d_combine, f2_rank
    inp, prm = row["inputs"], row["params"]
    w = prm.get("window_s", 300)
    parts = []
    session = _session(inp)
    for name, metric in (("F2a", "premium"), ("F2b", "contracts"), ("F2c", "prints")):
        pt = inp["parts"][name]
        code = _history_code(pt["history"])
        if code:
            return _invalid("M2-3", code, inp)
        store, _ = _store(inp, pt["history"], prm.get("K", 20))
        x = Fraction(pt["x"])
        if metric == "prints":
            x = x * (w // 60 if w % 60 == 0 and w > 0 else 1)
        if x.denominator == 1:
            x = int(x)
        parts.append(f2_rank(store, inp["series_id"], metric, x, session, inp["t_ns"], window_s=w, form="intraday",
                             X=prm.get("X", 5), K=prm.get("K", 20), lane=prm.get("lane", "stock")))
    return f2d_combine(parts[0], parts[1], parts[2], window_s=w, X=prm.get("X", 5))


def _run_f10(row):
    from option_features.flowrank import f10_baseline
    inp, prm = row["inputs"], row["params"]
    code = _structural_prints(inp) or _history_code(inp["history"])
    if code:
        return _invalid("M2-7", code, inp)
    w = prm.get("window_s", 300)
    flt = prm.get("filter", "all")
    x, tot = _window_x(inp, prm, "volume", w, {"all": "all", "calls": "calls", "puts": "puts"}[flt])
    store, hw = _store(inp, inp["history"], prm.get("K", 20))
    return f10_baseline(store, inp["series_id"], x, _session(inp), inp["t_ns"], window_s=w, N=prm.get("N", 2),
                        K=prm.get("K", 20), consumer_default=prm.get("consumer_default", "median"),
                        lane=prm.get("lane", "stock"), coverage=_coverage(tot))


def _run_f20(row):
    from option_features.flowrank import f20_baseline
    inp, prm = row["inputs"], row["params"]
    code = _history_code(inp["history"])
    if code:
        return _invalid("M2-8", code, inp)
    store, hw = _store(inp, inp["history"], prm.get("K", 20))
    return f20_baseline(store, inp["series_id"], prm["metric"], _session(inp), inp["t_ns"], window_s=hw,
                        N=prm.get("N", 2), K=prm.get("K", 20), consumer_default=prm.get("consumer_default", "mean"),
                        lane=prm.get("lane", "stock"))


def _run_f19(row):
    from option_features.flowrank import f19_percentile
    inp, prm = row["inputs"], row["params"]
    code = _history_code(inp["history"])
    if code:
        return _invalid("M2-10", code, inp)
    store, hw = _store(inp, inp["history"], prm.get("K", 20))
    s = inp["session"]
    return f19_percentile(store, inp["series_id"], s["put"], s["call"], _session(inp), inp["t_ns"], window_s=hw,
                          X=prm.get("X", 5), K=prm.get("K", 20), lane=prm.get("lane", "stock"))


def _store_value(store, inp):
    q = inp["query"]
    view = list(store.complete_sessions_before(q["series_id"], q["metric"], q["window_s"], q["as_of"], inp.get("k", 20)))
    hashes = store.record_hashes()
    return {"retained": store.retained(), "view": view, "dump_sha256": store.dump_sha256(), "n_lines": len(hashes),
            "content_sha256_digest": store.content_hash()}


def _run_store(row):
    from option_features.flowresult import M2StructuralError, Result
    from option_features.flowstore import HistoryStore
    inp = row["inputs"]
    try:
        if "snapshot_hex" in inp:
            store = HistoryStore.from_snapshot(bytes.fromhex(inp["snapshot_hex"]), _calendar(inp), k=inp.get("k", 20))
        elif "dump_text" in inp:
            store = HistoryStore.load(inp["dump_text"], _calendar(inp), k=inp.get("k", 20))
        else:
            store = HistoryStore(_calendar(inp), k=inp.get("k", 20))
            for op in inp.get("store_ops") or inp["ops"]:
                if op[0] == "append":
                    r = op[1]
                    store.append(r["series_id"], r["metric"], r["window_s"], r["session_id"], r["grid"], total=r["total"],
                                 complete=r["complete"], grid_idx=r.get("grid_idx"), lane=r.get("lane", "stock"))
                else:
                    store.seal(op[1], op[2], op[3], op[4])
    except M2StructuralError as exc:
        return Result.invalid("M2-12", exc.code, None, None, None)
    return Result.available("M2-12", None, None, None, _store_value(store, inp))


def _run_grid(row):
    from option_features.flowgrid import build_session_records
    from option_features.flowresult import M2StructuralError, Result
    inp, prm = row["inputs"], row["params"]
    s = inp["session"]
    w, metric, cid = prm["window_s"], prm["metric"], prm.get("contract_id")
    prints = _abs_prints(inp)
    if cid is not None:
        prints = [p for p in prints if p[0] == cid]
    try:
        b = build_session_records(prints, _contracts(inp), s["session_id"], s["open_ns"], s["close_ns"], s["minutes"], (w,),
                                  prm.get("lane", "stock"), None if cid is not None else inp["series_id"], cid is not None, "full")
    except M2StructuralError as exc:
        return Result.invalid("M2-GRID", exc.code, None, None, None)
    rec = next((r for r in b.records if r.metric == metric and (cid is None or r.series_id == cid)), None)
    minutes = s["minutes"]
    idx = [] if rec is None else list(rec.idx)
    vals = [] if rec is None else list(rec.vals)
    total = 0 if rec is None else rec.total
    if cid is not None:
        value = {"form": "sparse", "sparse": [[i, v] for i, v in zip(idx, vals)], "zero_count": minutes - len(idx),
                 "total": total, "valid_from": w // 60}
    else:
        grid = [0] * minutes
        for i, v in zip(idx, vals):
            grid[i] = v
        value = {"form": "dense", "grid": grid, "total": total, "valid_from": w // 60}
    cov = {"eligible_count": b.eligible_count, "nonstandard_count": b.nonstandard_count,
           "excluded_condition_count": b.excluded_condition_count, "unavailable_points": 0}
    return Result.available("M2-GRID", None, None, None, value, coverage=cov)


RUNNERS = {"M2-2": _run_f2, "M2-3": _run_f2d, "M2-7": _run_f10, "M2-8": _run_f20, "M2-10": _run_f19,
           "M2-12": _run_store, "M2-GRID": _run_grid}


def run_row(row):
    """Library result of one owned row (a `Result`)."""
    return RUNNERS[row["output_id"]](row)


def check_row(row):
    """None when the row matches its expected block exactly (status, reason, code, value, fired, label, coverage and
    the extra per_statistic / parts_shown blocks), else a short description of the first difference."""
    try:
        got = result_form(run_row(row))
    except Exception as exc:  # a failing row is a failure, never a crash of the suite
        return "%s: %s" % (type(exc).__name__, exc)
    exp = row["expected"]
    if canon(got) == canon(exp):
        return None
    for k in sorted(set(got) | set(exp)):
        if canon(got.get(k)) != canon(exp.get(k)):
            return "%s: got %s expected %s" % (k, canon(got.get(k))[:300], canon(exp.get(k))[:300])
    return "differs"
