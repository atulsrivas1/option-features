"""M2 F12 unusual episodes today (M2-11): an episode scan over the F1 series on the 60 s grid.

Pure and single-threaded (D4 amended); exact integers only. The F1 value at grid point k (time open + 60 s x k,
closed windows [T - 60, T] and [T - 900, T]) is "unusual" when 15 x P60 / P900 >= N, decided by an integer
cross-multiplication (`15 * p60 * N_den >= N_num * p900`): no Fraction and no float on the scan path.

Rules (matrix Q11, AMB-5, AMB-7, PR 76 conventions):
- grid points before open + 900 s are unavailable (insufficient window, not clipped); so is a point with P900 = 0
  or a missing point; an unavailable point counts as quiet (it cannot merge episodes across an outage);
- an episode starts at an unusual point and ends after `quiet_gap` consecutive quiet points (default 1, so
  episodes are rising edges; 5 is an optional hysteresis); `first_ns` and `last_ns` are the onsets of the first
  and last episode; the peak ratio is over the available points of the session to date (ties earliest), also
  with zero episodes; sessions are separate (no state crosses a session);
- no look-ahead: only grid points up to floor((T - open) / 60 s) are read;
- before 900 s since open the result is unavailable with insufficient_window; under a delayed-feed tag it is
  invalid_input with code delayed_feed_tag; fires at episode_count >= n_episodes.

Performance: one loop over the points (a few integer operations each; the peak is tracked by cross-multiplied
comparison). The F1 columns for a whole session come from `PrintTape.f1_columns` (C-speed bisect maps over the
prefix sums), so a session never rescans its prints per grid point.
"""
from fractions import Fraction

from .m2prints import cov, frac, invalid, result, structural_code
from .printtape import NS

GRID_NS = 60 * NS
FIRST_AVAILABLE_INDEX = 15            # 900 s / 60 s
GRID_S = 60


def scan_episodes(p60, p900, upto, thr_num, thr_den, quiet_gap):
    """Scan grid points 0..upto. Returns (episodes, first_idx, last_idx, peak_a, peak_b, peak_idx, unavailable);
    the peak ratio is 15 * peak_a / peak_b (None when no point is available)."""
    eps = 0
    first = last = None
    in_ep = False
    quiet = 0
    pk_a = pk_b = pk_k = None
    avail = 0
    c1 = 15 * thr_den
    m = min(len(p60), len(p900), upto + 1)
    for k in range(FIRST_AVAILABLE_INDEX, m):
        a = p60[k]
        b = p900[k]
        if a is None or b is None or b <= 0:
            if in_ep:
                quiet += 1
                if quiet >= quiet_gap:
                    in_ep = False
            continue
        avail += 1
        if pk_b is None or a * pk_b > pk_a * b:
            pk_a, pk_b, pk_k = a, b, k
        if a * c1 >= thr_num * b:
            if not in_ep:
                eps += 1
                in_ep = True
                if first is None:
                    first = k
                last = k
            quiet = 0
        elif in_ep:
            quiet += 1
            if quiet >= quiet_gap:
                in_ep = False
    return eps, first, last, pk_a, pk_b, pk_k, upto + 1 - avail


def _bad_params(nf, n_episodes, quiet_gap, grid_s):
    """True when a parameter is malformed (float or unparsable N, non-int or < 1 counts, grid other than 60 s)."""
    return (nf is None or type(quiet_gap) is not int or quiet_gap < 1 or type(n_episodes) is not int
            or n_episodes < 1)


class _Scan:
    """Incremental form of `scan_episodes`: `advance` consumes grid points up to a later index, append-only
    (no rebuild from open); `snapshot` equals `scan_episodes` over the same prefix."""
    __slots__ = ("k", "eps", "first", "last", "in_ep", "quiet", "pk_a", "pk_b", "pk_k", "avail", "c1", "tn", "gap")

    def __init__(self, thr_num, thr_den, quiet_gap):
        self.k = FIRST_AVAILABLE_INDEX
        self.eps = self.quiet = self.avail = 0
        self.first = self.last = self.pk_a = self.pk_b = self.pk_k = None
        self.in_ep = False
        self.c1, self.tn, self.gap = 15 * thr_den, thr_num, quiet_gap

    def advance(self, p60, p900, upto):
        eps, first, last, in_ep, quiet = self.eps, self.first, self.last, self.in_ep, self.quiet
        pk_a, pk_b, pk_k, avail = self.pk_a, self.pk_b, self.pk_k, self.avail
        c1, tn, gap = self.c1, self.tn, self.gap
        for k in range(self.k, upto + 1):
            a = p60[k]
            b = p900[k]
            if a is None or b is None or b <= 0:
                if in_ep:
                    quiet += 1
                    if quiet >= gap:
                        in_ep = False
                continue
            avail += 1
            if pk_b is None or a * pk_b > pk_a * b:
                pk_a, pk_b, pk_k = a, b, k
            if a * c1 >= tn * b:
                if not in_ep:
                    eps += 1
                    in_ep = True
                    if first is None:
                        first = k
                    last = k
                quiet = 0
            elif in_ep:
                quiet += 1
                if quiet >= gap:
                    in_ep = False
        if upto + 1 > self.k:
            self.k = upto + 1
        self.eps, self.first, self.last, self.in_ep, self.quiet = eps, first, last, in_ep, quiet
        self.pk_a, self.pk_b, self.pk_k, self.avail = pk_a, pk_b, pk_k, avail

    def snapshot(self, upto):
        return (self.eps, self.first, self.last, self.pk_a, self.pk_b, self.pk_k, upto + 1 - self.avail)


def _emit(scan, open_ns, nf, n_episodes, quiet_gap, params, t_ns, series_id, session_id, lane, counts=(0, 0, 0)):
    eps, first, last, pk_a, pk_b, pk_k, unav = scan
    value = {"episode_count": eps,
             "first_ns": None if first is None else open_ns + first * GRID_NS,
             "last_ns": None if last is None else open_ns + last * GRID_NS,
             "peak_ratio": None if pk_b is None else Fraction(15 * pk_a, pk_b),
             "peak_ns": None if pk_k is None else open_ns + pk_k * GRID_NS,
             "unavailable_points": unav, "quiet_gap": quiet_gap}
    return result("M2-11", series_id, session_id, t_ns, "available", None, None, value, eps >= n_episodes, params,
                  cov(counts[0], counts[1], counts[2], unav), None, lane)


def f12_episodes(p60, p900, t_ns, open_ns, *, n=3, n_episodes=1, quiet_gap=1, grid_s=GRID_S, delayed=False,
                 series_id=None, session_id=None, lane="stock", session_in_calendar=True):
    """F12 from F1 grid columns: p60[k] and p900[k] are the premium sums at grid point k (None = missing)."""
    nf = frac(n)
    params = {"N": n if nf is None else nf, "grid_s": grid_s, "n_episodes": n_episodes, "quiet_gap": quiet_gap}
    code = structural_code(None, calendar_ok=session_in_calendar, delayed=delayed,
                           bad_param=_bad_params(nf, n_episodes, quiet_gap, grid_s),
                           bad_grid=grid_s != GRID_S)
    if code:
        return invalid("M2-11", code, series_id, session_id, t_ns, params, lane)
    elapsed = t_ns - open_ns
    if elapsed < FIRST_AVAILABLE_INDEX * GRID_NS:
        return result("M2-11", series_id, session_id, t_ns, "unavailable", "insufficient_window", None, None, None,
                      params, None, None, lane)
    scan = scan_episodes(p60, p900, elapsed // GRID_NS, nf.numerator, nf.denominator, quiet_gap)
    return _emit(scan, open_ns, nf, n_episodes, quiet_gap, params, t_ns, series_id, session_id, lane)


def f1_grid_columns(tape, open_ns, upto, flt="all", lane="stock"):
    """(p60, p900) columns for grid points 0..upto of one session: None before open + 900 s, then the closed
    60 s and 900 s window premium sums at open + 60 s x k (F1 inputs; the internal grid helper of story B)."""
    pad = [None] * min(FIRST_AVAILABLE_INDEX, upto + 1)
    if upto < FIRST_AVAILABLE_INDEX:
        return pad, list(pad)
    times = [open_ns + k * GRID_NS for k in range(FIRST_AVAILABLE_INDEX, upto + 1)]
    c60, c900 = tape.f1_columns(tape.select(lane, flt), times)
    return pad + c60, pad + c900


def f12_from_tape(tape, t_ns, open_ns, *, n=3, n_episodes=1, quiet_gap=1, grid_s=GRID_S, flt="all", lane="stock",
                  delayed=False, series_id=None, session_id=None, session_in_calendar=True):
    """F12 straight from a print tape (session to date). The coverage counters are those of the lane's prints in
    [open, T] (the from-points form reports zeros; PO may rule one convention)."""
    nf = frac(n)
    params = {"N": n if nf is None else nf, "grid_s": grid_s, "n_episodes": n_episodes, "quiet_gap": quiet_gap}
    code = structural_code(tape, calendar_ok=session_in_calendar, delayed=delayed,
                           bad_param=_bad_params(nf, n_episodes, quiet_gap, grid_s),
                           bad_grid=grid_s != GRID_S)
    if code:
        return invalid("M2-11", code, series_id, session_id, t_ns, params, lane)
    elapsed = t_ns - open_ns
    if elapsed < FIRST_AVAILABLE_INDEX * GRID_NS:
        return result("M2-11", series_id, session_id, t_ns, "unavailable", "insufficient_window", None, None, None,
                      params, None, None, lane)
    upto = elapsed // GRID_NS
    p60, p900 = f1_grid_columns(tape, open_ns, upto, flt, lane)
    scan = scan_episodes(p60, p900, upto, nf.numerator, nf.denominator, quiet_gap)
    _, _, ne, nn, nx = tape.stats(tape.select(lane, flt), open_ns, t_ns)
    return _emit(scan, open_ns, nf, n_episodes, quiet_gap, params, t_ns, series_id, session_id, lane, (ne, nn, nx))


def f12_sweep(tape, cutoffs, open_ns, *, n=3, n_episodes=1, quiet_gap=1, grid_s=GRID_S, flt="all", lane="stock",
              delayed=False, series_id=None, session_id=None, session_in_calendar=True):
    """F12 at many cutoffs of one session, append-only: the F1 grid columns are built once up to the last
    cutoff and one `_Scan` state advances across the cutoffs (ascending internally, results in input order), so
    nothing is rebuilt from open per cutoff. Equal to `f12_from_tape` at every cutoff (tested)."""
    nf = frac(n)
    params = {"N": n if nf is None else nf, "grid_s": grid_s, "n_episodes": n_episodes, "quiet_gap": quiet_gap}
    code = structural_code(tape, calendar_ok=session_in_calendar, delayed=delayed,
                           bad_param=_bad_params(nf, n_episodes, quiet_gap, grid_s),
                           bad_grid=grid_s != GRID_S)
    if code:
        return [invalid("M2-11", code, series_id, session_id, t, params, lane) for t in cutoffs]
    out = [None] * len(cutoffs)
    order = sorted(range(len(cutoffs)), key=cutoffs.__getitem__)
    ready = [i for i in order if cutoffs[i] - open_ns >= FIRST_AVAILABLE_INDEX * GRID_NS]
    for i in order:
        if cutoffs[i] - open_ns < FIRST_AVAILABLE_INDEX * GRID_NS:
            out[i] = result("M2-11", series_id, session_id, cutoffs[i], "unavailable", "insufficient_window", None,
                            None, None, params, None, None, lane)
    if not ready:
        return out
    p60, p900 = f1_grid_columns(tape, open_ns, (cutoffs[ready[-1]] - open_ns) // GRID_NS, flt, lane)
    state = _Scan(nf.numerator, nf.denominator, quiet_gap)
    groups = tape.select(lane, flt)
    for i in ready:
        t_ns = cutoffs[i]
        upto = (t_ns - open_ns) // GRID_NS
        state.advance(p60, p900, upto)
        _, _, ne, nn, nx = tape.stats(groups, open_ns, t_ns)
        out[i] = _emit(state.snapshot(upto), open_ns, nf, n_episodes, quiet_gap, params, t_ns, series_id, session_id,
                       lane, (ne, nn, nx))
    return out
