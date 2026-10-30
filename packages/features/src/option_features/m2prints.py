"""M2 print-window families on a `printtape.PrintTape`: F1 (M2-1), F4 (M2-4), F17 (M2-5), F7 (M2-6), F18 (M2-9).

Pure and single-threaded (D4 amended); exact integers only, no float. Result records follow
docs/m2/M2_IO_CONTRACT.md section 3 (canonical key order); ratios and shares are `Fraction`s in the record and
reduced "n/d" strings (integers plain) in `to_wire` / `canonical_line`.

Performance design
- A tape is built once per (underlying, session); every family then reads it: windows are bisects plus prefix
  sums (F1, F4, F18), so a cutoff costs O(log n) and a 78-cutoff sweep never rescans the prints (M2-B15).
- F17 and F7 aggregate per key, so their single evaluation scans only the prints inside the window; their
  `*_sweep` functions keep the aggregation incrementally (two pointers, each print added once and removed
  once) instead of rescanning every window.
- Decisions are integer cross-multiplications (`15 * p60 * N_den >= N_num * p900`): no Fraction is built on the
  decision path, and Fractions are built only for the reported values. There is no float, hence no float
  filter and no error bound to state.
- Batched and single paths share the same cores; equality is tested byte for byte.

Gate order (docs/m2/M2_CAPABILITY_MATRIX.md section 4): invalid_input (tape error, session_not_in_calendar,
window_not_allowed, threshold_required, delayed_feed_tag, in the ruled list order), then insufficient_window,
then zero_denominator. Windows are closed [T - W, T] and never look ahead of T. Lane and filter selection is
by construction: a contract of another lane or right is not in the selected groups, so shares never cross
lanes. Delayed-feed scope is F1 and F12 only (the `delayed` argument of F4, F7, F17 and F18 is accepted for a
uniform call shape and ignored).
"""
import re
from bisect import bisect_left, bisect_right
from collections import Counter
from fractions import Fraction

from .flowgrid import NS
from .flowresult import ALLOWED_WINDOWS, Result, canonical_line, show, to_wire   # shared (story A); re-exported

F17_WINDOW_S = 300
DEFAULT_THRESHOLD_TICKS = 1_000_000_000      # 100,000 USD
INSUFFICIENT_WINDOW_NS = 900 * NS


_RATIONAL = re.compile(r"-?\d+(/\d+)?|-?\d*\.\d+", re.ASCII)


def frac(x):
    """Exact Fraction of a rational given as a non-bool int, a Fraction, or text matching
    `-?\\d+(/\\d+)?|-?\\d*\\.\\d+` (ASCII; "1_0", " 3 " and "1e3" are not rationals); None for anything else
    (float, bool, None, unparsable text): such a parameter is malformed_type, never converted."""
    k = type(x)
    if k is Fraction:
        return x
    if k is int:
        return Fraction(x)
    if k is str and _RATIONAL.fullmatch(x):
        try:
            return Fraction(x)
        except ZeroDivisionError:
            return None
    return None


def is_int(x):
    return type(x) is int


def start_of(t_ns, width_ns, open_ns):
    """Window start, clipped at session open: prints before open are never counted. `open_ns` (the request
    session's open) is required by F4, F7, F17 and F18; without it they answer malformed_type."""
    if open_ns is not None and t_ns < open_ns:
        return t_ns + 1                       # cutoff before open: an empty window (start after end), never negative
    start = t_ns - width_ns
    return start if open_ns is None or start >= open_ns else open_ns


def cov(ne, nn, nx, unavailable=0):
    return {"eligible_count": ne, "nonstandard_count": nn, "excluded_condition_count": nx,
            "unavailable_points": unavailable}


def result(output_id, series_id, session_id, t_ns, status, reason, code, value, fired, params, coverage, label, lane,
           **extra):
    return Result(output_id, series_id, session_id, t_ns, status, reason, code, value, fired, params, coverage, label,
                  lane, ratio_reason=extra.get("ratio_reason"))


def invalid(output_id, code, series_id, session_id, t_ns, params, lane):
    return result(output_id, series_id, session_id, t_ns, "invalid_input", None, code, None, None, params, None, None,
                  lane)


def structural_code(tape, *, calendar_ok=True, window_s=None, fixed_window_s=None, threshold_missing=False,
                    delayed=False, bad_param=False, bad_grid=False):
    """First failing structural code in the ruled order, or None: tape errors (unordered_prints,
    negative_size_or_price, bad_multiplier, unknown_contract, malformed_type), malformed_type (a float, bool or
    unparsable parameter), grid_not_60s (F12), session_not_in_calendar, window_not_allowed (also a non-int window),
    threshold_required, delayed_feed_tag (the single list of PR 81 section 9)."""
    if tape is not None and tape.error:
        return tape.error
    if bad_param:
        return "malformed_type"
    if bad_grid:
        return "grid_not_60s"
    if not calendar_ok:
        return "session_not_in_calendar"
    if window_s is not None:
        if type(window_s) is not int:
            return "window_not_allowed"
        if fixed_window_s is not None:
            if window_s != fixed_window_s:
                return "window_not_allowed"
        elif window_s not in ALLOWED_WINDOWS:
            return "window_not_allowed"
    if threshold_missing:
        return "threshold_required"
    if delayed:
        return "delayed_feed_tag"
    return None


# ======================================================================================== F1 (M2-1)
def _f1_prep(tape, n, flt, lane, delayed, series_id, session_id, session_in_calendar):
    nf = frac(n)
    params = {"N": n if nf is None else nf, "filter": flt}
    code = structural_code(tape, calendar_ok=session_in_calendar, delayed=delayed, bad_param=nf is None)
    groups = None if code else tape.select(lane, flt)
    return nf, params, code, groups


def _f1_at(tape, groups, nf, params, t_ns, open_ns, flt, lane, series_id, session_id):
    if t_ns - open_ns < INSUFFICIENT_WINDOW_NS:
        return result("M2-1", series_id, session_id, t_ns, "unavailable", "insufficient_window", None, None, None,
                      params, None, None, lane)
    p60, p900, ne, nn, nx = tape.f1_sums(groups, t_ns)
    coverage = cov(ne, nn, nx)
    if p900 == 0:
        return result("M2-1", series_id, session_id, t_ns, "unavailable", "zero_denominator", None, None, None, params,
                      coverage, flt, lane)
    fired = 15 * p60 * nf.denominator >= nf.numerator * p900
    return result("M2-1", series_id, session_id, t_ns, "available", None, None,
                  {"p60": p60, "p900": p900, "ratio": Fraction(15 * p60, p900)}, fired, params, coverage, flt, lane)


def f1_premium_surge(tape, t_ns, open_ns, *, n=3, flt="all", lane="stock", delayed=False, series_id=None,
                     session_id=None, session_in_calendar=True):
    """F1: ratio = 15 x P60 / P900 (premium of the last 60 s over premium of the last 900 s, per-second rates);
    fires at ratio >= N. Unavailable (insufficient_window) until 900 s after open; zero_denominator at P900 = 0.
    The 60 s window inside the 900 s window is deliberate."""
    nf, params, code, groups = _f1_prep(tape, n, flt, lane, delayed, series_id, session_id, session_in_calendar)
    if code:
        return invalid("M2-1", code, series_id, session_id, t_ns, params, lane)
    return _f1_at(tape, groups, nf, params, t_ns, open_ns, flt, lane, series_id, session_id)


def f1_sweep(tape, cutoffs, open_ns, *, n=3, flt="all", lane="stock", delayed=False, series_id=None,
             session_id=None, session_in_calendar=True):
    """F1 at many cutoffs of one session from one tape (bisects only; no print is revisited)."""
    nf, params, code, groups = _f1_prep(tape, n, flt, lane, delayed, series_id, session_id, session_in_calendar)
    if code:
        return [invalid("M2-1", code, series_id, session_id, t, params, lane) for t in cutoffs]
    return [_f1_at(tape, groups, nf, params, t, open_ns, flt, lane, series_id, session_id) for t in cutoffs]


# ======================================================================================== F4 (M2-4)
def _f4_prep(tape, window_s, threshold_ticks, n, flt, lane, series_id, session_id, session_in_calendar, open_ns):
    nf = frac(n)
    params = {"N": n if nf is None else nf, "threshold_ticks": threshold_ticks, "window_s": window_s}
    code = structural_code(tape, calendar_ok=session_in_calendar, window_s=window_s,
                           bad_param=nf is None or not is_int(threshold_ticks) or not is_int(open_ns))
    groups = None if code else tape.select(lane, flt)
    return nf, params, code, groups


def _f4_at(tape, groups, nf, params, t_ns, window_s, threshold_ticks, series_id, session_id, lane, open_ns):
    start = start_of(t_ns, window_s * NS, open_ns)
    count = large = 0
    for g in groups:
        lt, lpp = g.large(threshold_ticks)
        a, b = bisect_left(lt, start), bisect_right(lt, t_ns)
        count += b - a
        large += lpp[b] - lpp[a]
    _, _, ne, nn, nx = tape.stats(groups, start, t_ns)
    return result("M2-4", series_id, session_id, t_ns, "available", None, None,
                  {"large_count": count, "large_premium": large}, count * nf.denominator >= nf.numerator, params,
                  cov(ne, nn, nx), None, lane)


def f4_large_prints(tape, t_ns, *, window_s=300, threshold_ticks=DEFAULT_THRESHOLD_TICKS, n=1, flt="all",
                    lane="stock", delayed=False, series_id=None, session_id=None, session_in_calendar=True, open_ns=None):
    """F4 (repository name flow.large_print_count): count of eligible prints with premium >= threshold ticks in
    the window, side-agnostic (unknown side counts); fires at count >= N. An empty window is available, count 0."""
    nf, params, code, groups = _f4_prep(tape, window_s, threshold_ticks, n, flt, lane, series_id, session_id,
                                        session_in_calendar, open_ns)
    if code:
        return invalid("M2-4", code, series_id, session_id, t_ns, params, lane)
    return _f4_at(tape, groups, nf, params, t_ns, window_s, threshold_ticks, series_id, session_id, lane, open_ns)


def f4_sweep(tape, cutoffs, *, window_s=300, threshold_ticks=DEFAULT_THRESHOLD_TICKS, n=1, flt="all", lane="stock",
             delayed=False, series_id=None, session_id=None, session_in_calendar=True, open_ns=None):
    nf, params, code, groups = _f4_prep(tape, window_s, threshold_ticks, n, flt, lane, series_id, session_id,
                                        session_in_calendar, open_ns)
    if code:
        return [invalid("M2-4", code, series_id, session_id, t, params, lane) for t in cutoffs]
    return [_f4_at(tape, groups, nf, params, t, window_s, threshold_ticks, series_id, session_id, lane, open_ns)
            for t in cutoffs]


# ======================================================================================= F17 (M2-5)
def _f17_prep(tape, window_s, threshold_ticks, flt, lane, session_in_calendar, open_ns):
    params = {"threshold_ticks": threshold_ticks, "window_s": F17_WINDOW_S}
    code = structural_code(tape, calendar_ok=session_in_calendar, window_s=window_s, fixed_window_s=F17_WINDOW_S,
                           bad_param=not is_int(threshold_ticks) or not is_int(open_ns))
    groups = None if code else tape.select(lane, flt)
    return params, code, groups


def _rare_counts(tape, gset, start, end):
    """Per contract index: [nonstandard-only count, excluded-condition count] in [start, end]."""
    counts = {}
    rare, rare_t, c_group = tape.rare, tape.rare_t, tape.c_group
    a, b = bisect_left(rare_t, start), bisect_right(rare_t, end)
    for i in range(a, b):
        _, ci, kind = rare[i]
        if c_group[ci] in gset:
            c = counts.get(ci)
            if c is None:
                c = counts[ci] = [0, 0]
            c[kind - 1] += 1
    return counts


def _f17_emit(tape, gset, ids, sums, cnts, rare, thr, params, t_ns, session_id, lane):
    out = []
    cidx, c_group = tape.cidx, tape.c_group
    for cid in ids:
        ci = cidx.get(cid)
        if ci is None or c_group[ci] not in gset:
            s = ne = nn = nx = 0
        else:
            s, ne = sums.get(ci, 0), cnts.get(ci, 0)
            rc = rare.get(ci)
            nn, nx = (rc[0], rc[1]) if rc else (0, 0)
        out.append(result("M2-5", cid, session_id, t_ns, "available", None, None, {"window_premium": s}, s >= thr,
                          params, cov(ne, nn, nx), None, lane))
    return out


def _f17_scan(groups, start, end):
    """Per contract index: premium sum and eligible count over the prints inside [start, end] (one scan)."""
    sums, cnts = {}, Counter()
    for g in groups:
        t = g.t
        a, b = bisect_left(t, start), bisect_right(t, end)
        if b > a:
            cs = g.ci[a:b]
            cnts.update(cs)
            for c, p in zip(cs, g.p[a:b]):
                sums[c] = sums.get(c, 0) + p
    return sums, cnts


def _f17_slide(groups, cutoffs, open_ns=None):
    """Yield (input index, T, window start, sums, cnts) in ascending T; the dicts are updated in place with two
    pointers per group (each print is added once and removed once) and are valid until the next yield."""
    sums, cnts = {}, {}
    state = [[0, 0] for _ in groups]
    width = F17_WINDOW_S * NS
    for idx in sorted(range(len(cutoffs)), key=cutoffs.__getitem__):
        t_ns = cutoffs[idx]
        start = start_of(t_ns, width, open_ns)
        for g, st in zip(groups, state):
            t, ci, p = g.t, g.ci, g.p
            hi, lo, n = st[1], st[0], len(t)
            while lo < hi and t[lo] < start:
                c = ci[lo]
                sums[c] -= p[lo]
                cnts[c] -= 1
                lo += 1
            if lo == hi and hi < n and t[hi] < start:       # nothing live: jump to the window, skip older prints
                lo = hi = bisect_left(t, start, hi)
            while hi < n and t[hi] <= t_ns:
                c = ci[hi]
                sums[c] = sums.get(c, 0) + p[hi]
                cnts[c] = cnts.get(c, 0) + 1
                hi += 1
            st[0], st[1] = lo, hi
        yield idx, t_ns, start, sums, cnts


def f17_many(tape, t_ns, contract_ids=None, *, window_s=300, threshold_ticks=DEFAULT_THRESHOLD_TICKS, flt="all",
             lane="stock", delayed=False, session_id=None, session_in_calendar=True, open_ns=None):
    """F17 for many contracts in ONE scan of the window's prints (per-contract sum of eligible premium over the
    fixed trailing [T - 300 s, T]; fires at sum >= threshold; a contract with no prints is available with 0).
    `contract_ids` defaults to the contracts seen on the tape in first-seen order."""
    ids = tape.c_id if contract_ids is None else contract_ids
    params, code, groups = _f17_prep(tape, window_s, threshold_ticks, flt, lane, session_in_calendar, open_ns)
    if code:
        return [invalid("M2-5", code, cid, session_id, t_ns, params, lane) for cid in ids]
    start = start_of(t_ns, F17_WINDOW_S * NS, open_ns)
    sums, cnts = _f17_scan(groups, start, t_ns)
    gset = set(groups)
    return _f17_emit(tape, gset, ids, sums, cnts, _rare_counts(tape, gset, start, t_ns), threshold_ticks, params,
                     t_ns, session_id, lane)


def f17_window_premium(tape, t_ns, contract_id, *, window_s=300, threshold_ticks=DEFAULT_THRESHOLD_TICKS, flt="all",
                       lane="stock", delayed=False, session_id=None, session_in_calendar=True, open_ns=None):
    return f17_many(tape, t_ns, [contract_id], window_s=window_s, threshold_ticks=threshold_ticks, flt=flt, lane=lane,
                    session_id=session_id, session_in_calendar=session_in_calendar, open_ns=open_ns)[0]


def f17_sweep(tape, cutoffs, contract_ids=None, *, window_s=300, threshold_ticks=DEFAULT_THRESHOLD_TICKS, flt="all",
              lane="stock", delayed=False, session_id=None, session_in_calendar=True, open_ns=None):
    """F17 at many cutoffs: one list of per-contract results per cutoff (input order). The per-contract sums
    are kept incrementally with two pointers per group, so each print is added once and removed once."""
    ids = tape.c_id if contract_ids is None else contract_ids
    params, code, groups = _f17_prep(tape, window_s, threshold_ticks, flt, lane, session_in_calendar, open_ns)
    if code:
        return [[invalid("M2-5", code, cid, session_id, t, params, lane) for cid in ids] for t in cutoffs]
    gset = set(groups)
    out = [None] * len(cutoffs)
    for idx, t_ns, start, sums, cnts in _f17_slide(groups, cutoffs, open_ns):
        out[idx] = _f17_emit(tape, gset, ids, sums, cnts, _rare_counts(tape, gset, start, t_ns), threshold_ticks,
                             params, t_ns, session_id, lane)
    return out


def f17_columns(tape, t_ns, contract_ids=None, *, flt="all", lane="stock", open_ns=None, sparse=False):
    """Columnar F17 print pass at one cutoff: window premium sums (ticks) aligned with `contract_ids`, from one
    scan of the window; the single-cutoff counterpart of `f17_sweep_columns`."""
    ids = tape.c_id if contract_ids is None else contract_ids
    if tape.error:
        raise ValueError(tape.error)
    if not is_int(open_ns):
        raise ValueError("malformed_type")
    groups = tape.select(lane, flt)
    gset = set(groups)
    sums, _ = _f17_scan(groups, start_of(t_ns, F17_WINDOW_S * NS, open_ns), t_ns)
    if sparse:                                            # {contract id: sum} of the contracts live in the window
        c_id = tape.c_id
        return {c_id[ci]: v for ci, v in sums.items()}
    get, cidx, c_group = sums.get, tape.cidx, tape.c_group
    return [0 if (ci := cidx.get(cid)) is None or c_group[ci] not in gset else get(ci, 0) for cid in ids]


def f17_sweep_columns(tape, cutoffs, contract_ids=None, *, flt="all", lane="stock", open_ns=None, sparse=False):
    """Columnar F17 print pass: per cutoff (input order) the list of window premium sums (ticks) aligned with
    `contract_ids`, no result record per contract. Same incremental state as `f17_sweep`; the reads (results)
    are built separately by `f17_sweep` (M2-B15 gates the print pass apart from the reads). Raises
    ValueError on a structural tape error."""
    ids = tape.c_id if contract_ids is None else contract_ids
    if tape.error:
        raise ValueError(tape.error)
    if not is_int(open_ns):
        raise ValueError("malformed_type")
    groups = tape.select(lane, flt)
    gset = set(groups)
    cis = [tape.cidx.get(cid) for cid in ids]
    ok = [ci is not None and tape.c_group[ci] in gset for ci in cis]
    out = [None] * len(cutoffs)
    c_id = tape.c_id
    for idx, _t, _start, sums, cnts in _f17_slide(groups, cutoffs, open_ns):
        if sparse:
            out[idx] = {c_id[ci]: v for ci, v in sums.items() if cnts[ci]}
            continue
        get = sums.get
        out[idx] = [get(ci, 0) if k else 0 for ci, k in zip(cis, ok)]
    return out


# ======================================================================================== F7 (M2-6)
def _f7_prep(tape, window_s, share_threshold, flt, lane, session_in_calendar, open_ns):
    th = frac(share_threshold)
    params = {"share_threshold": share_threshold if th is None else th, "window_s": window_s}
    code = structural_code(tape, calendar_ok=session_in_calendar, window_s=window_s, bad_param=th is None or not is_int(open_ns))
    groups = None if code else tape.select(lane, flt)
    return th, params, code, groups


def _f7_emit(tape, groups, by_s, by_e, th, params, t_ns, start, series_id, session_id, lane):
    _, _, ne, nn, nx = tape.stats(groups, start, t_ns)
    coverage = cov(ne, nn, nx)
    total = sum(by_s.values())
    if total == 0:
        return result("M2-6", series_id, session_id, t_ns, "unavailable", "zero_denominator", None, None, None, params,
                      coverage, None, lane)
    best_s = max(by_s.values())
    top_s = min(k for k, v in by_s.items() if v == best_s)
    best_e = max(by_e.values())
    top_e = min(k for k, v in by_e.items() if v == best_e)
    cut = th.numerator * total
    fired = best_s * th.denominator >= cut or best_e * th.denominator >= cut
    return result("M2-6", series_id, session_id, t_ns, "available", None, None,
                  {"top_strike": top_s, "strike_share": Fraction(best_s, total), "top_expiry": top_e,
                   "expiry_share": Fraction(best_e, total), "total_premium": total}, fired, params, coverage, None,
                  lane)


def f7_concentration(tape, t_ns, *, window_s=300, share_threshold="3/5", flt="all", lane="stock", delayed=False,
                     series_id=None, session_id=None, session_in_calendar=True, open_ns=None):
    """F7: largest share of the window's eligible premium in one strike (summed over expiries and rights) and in
    one expiry (summed over strikes and rights); fires when either share >= threshold (default 3/5). Ties: lowest
    strike, earliest expiry. Denominator is the total eligible premium (zero_denominator when 0)."""
    th, params, code, groups = _f7_prep(tape, window_s, share_threshold, flt, lane, session_in_calendar, open_ns)
    if code:
        return invalid("M2-6", code, series_id, session_id, t_ns, params, lane)
    start = start_of(t_ns, window_s * NS, open_ns)
    byc = {}
    for g in groups:
        t = g.t
        a, b = bisect_left(t, start), bisect_right(t, t_ns)
        if b > a:
            for c, p in zip(g.ci[a:b], g.p[a:b]):
                byc[c] = byc.get(c, 0) + p
    by_s, by_e = {}, {}
    c_strike, c_expiry = tape.c_strike, tape.c_expiry
    for c, p in byc.items():
        k = c_strike[c]
        by_s[k] = by_s.get(k, 0) + p
        k = c_expiry[c]
        by_e[k] = by_e.get(k, 0) + p
    return _f7_emit(tape, groups, by_s, by_e, th, params, t_ns, start, series_id, session_id, lane)


def f7_sweep(tape, cutoffs, *, window_s=300, share_threshold="3/5", flt="all", lane="stock", delayed=False,
             series_id=None, session_id=None, session_in_calendar=True, open_ns=None):
    """F7 at many cutoffs; the strike and expiry sums slide with two pointers per group (each print is added
    once and removed once), so overlapping windows are never rescanned. (A per-key prefix-sum index was tried and
    is slower: O(keys log n) per cutoff exceeds a window scan at these densities.)"""
    th, params, code, groups = _f7_prep(tape, window_s, share_threshold, flt, lane, session_in_calendar, open_ns)
    if code:
        return [invalid("M2-6", code, series_id, session_id, t, params, lane) for t in cutoffs]
    by_s, by_e = {}, {}
    c_strike, c_expiry = tape.c_strike, tape.c_expiry
    state = [[0, 0] for _ in groups]
    out = [None] * len(cutoffs)
    width = window_s * NS

    def fold(ci, p, a, b, sign):
        """Add (sign +1) or remove (-1) the prints a..b: one dict update per print, then one fold per contract."""
        d = {}
        for c, v in zip(ci[a:b], p[a:b]):
            d[c] = d.get(c, 0) + v
        for c, v in d.items():
            if sign < 0:
                v = -v
            k = c_strike[c]
            by_s[k] = by_s.get(k, 0) + v
            k = c_expiry[c]
            by_e[k] = by_e.get(k, 0) + v

    for idx in sorted(range(len(cutoffs)), key=cutoffs.__getitem__):
        t_ns = cutoffs[idx]
        start = start_of(t_ns, width, open_ns)
        for g, st in zip(groups, state):
            t, ci, p = g.t, g.ci, g.p
            lo, hi = st
            nl = bisect_left(t, start, lo, hi)
            if nl > lo:
                fold(ci, p, lo, nl, -1)
                lo = nl
            if lo == hi:                                   # nothing live: jump to the window, skip older prints
                lo = hi = bisect_left(t, start, hi)
            nh = bisect_right(t, t_ns, hi)
            if nh > hi:
                fold(ci, p, hi, nh, 1)
                hi = nh
            st[0], st[1] = lo, hi
        out[idx] = _f7_emit(tape, groups, by_s, by_e, th, params, t_ns, start, series_id, session_id, lane)
    return out


# ======================================================================================== F18 (M2-9)
def _f18_prep(tape, window_s, at_least, at_most, lane, session_in_calendar, open_ns):
    al = None if at_least is None else frac(at_least)
    am = None if at_most is None else frac(at_most)
    bad = ((at_least is not None and al is None) or (at_most is not None and am is None)
           or not is_int(open_ns))
    params = {"at_least": at_least if (bad and al is None) else al, "at_most": at_most if (bad and am is None) else am,
              "window_s": window_s}
    code = structural_code(tape, calendar_ok=session_in_calendar, window_s=window_s,
                           threshold_missing=at_least is None and at_most is None, bad_param=bad)
    groups = None if code else (tape.select(lane, "puts"), tape.select(lane, "calls"))
    return al, am, params, code, groups


def _f18_at(tape, groups, al, am, params, t_ns, window_s, series_id, session_id, lane, open_ns):
    start = start_of(t_ns, window_s * NS, open_ns)
    _, put, pe, pn, px = tape.stats(groups[0], start, t_ns, True)
    _, call, ce, cn, cx = tape.stats(groups[1], start, t_ns, True)
    coverage = cov(pe + ce, pn + cn, px + cx)
    total = put + call
    if total == 0:
        return result("M2-9", series_id, session_id, t_ns, "unavailable", "zero_denominator", None, None, None, params,
                      coverage, "put", lane)
    fired = False
    if al is not None and put * al.denominator >= al.numerator * total:
        fired = True
    if am is not None and put * am.denominator <= am.numerator * total:
        fired = True
    return result("M2-9", series_id, session_id, t_ns, "available", None, None,
                  {"put_volume": put, "call_volume": call, "put_share": Fraction(put, total),
                   "put_call_ratio": Fraction(put, call) if call else None}, fired, params, coverage, "put", lane,
                  **({} if call else {"ratio_reason": "zero_denominator"}))


def f18_put_share(tape, t_ns, *, window_s=300, at_least=None, at_most=None, lane="stock", delayed=False,
                  series_id=None, session_id=None, session_in_calendar=True, open_ns=None):
    """F18: put share of eligible option volume (sum of sizes) in the window, with put volume, call volume and
    the put-to-call ratio (unavailable with zero call volume: `ratio_reason` zero_denominator, share still
    available). Fires at share >= at_least or share <= at_most; neither set is invalid_input threshold_required.
    Side-agnostic; the calls/puts filter does not apply."""
    al, am, params, code, groups = _f18_prep(tape, window_s, at_least, at_most, lane, session_in_calendar, open_ns)
    if code:
        return invalid("M2-9", code, series_id, session_id, t_ns, params, lane)
    return _f18_at(tape, groups, al, am, params, t_ns, window_s, series_id, session_id, lane, open_ns)


def f18_sweep(tape, cutoffs, *, window_s=300, at_least=None, at_most=None, lane="stock", delayed=False,
              series_id=None, session_id=None, session_in_calendar=True, open_ns=None):
    al, am, params, code, groups = _f18_prep(tape, window_s, at_least, at_most, lane, session_in_calendar, open_ns)
    if code:
        return [invalid("M2-9", code, series_id, session_id, t, params, lane) for t in cutoffs]
    return [_f18_at(tape, groups, al, am, params, t, window_s, series_id, session_id, lane, open_ns) for t in cutoffs]
