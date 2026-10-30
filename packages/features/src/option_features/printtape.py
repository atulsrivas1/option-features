"""M2 print tape: one validating pass over a trade stream into columnar, prefix-summable form.

Pure and single-threaded (D4 amended): no I/O, clocks, threads or shared mutable state. All arithmetic is
exact integers: prices are integer ticks (price x 10**4, as in `quotehist.as_ticks`), premium is
price x size x multiplier in ticks. No float anywhere, so no float filter is needed.

Design (owner goal: performance)
- ONE pass over the prints (`build_tape`): ordering, sign and multiplier validation, decimal-to-tick
  conversion (only for text prices), classification and appends. A print costs one dict lookup, a handful
  of integer comparisons and four list appends; no per-print object is created.
- Eligible prints (multiplier 100 and not an excluded condition) are stored per group (lane, right) as
  parallel columns: time, premium, size, contract index. Windows are then two bisects plus a prefix-sum
  difference (O(log n)), never a rescan; a sweep of many cutoffs reuses the same tape.
- Nonstandard and excluded-condition prints are rare; they are kept as small sorted time lists for the
  coverage counters (`excluded_condition_count` counts every excluded print, also nonstandard ones;
  `nonstandard_count` only the non-excluded nonstandard ones, AMB-14).
- Prefix arrays and per-threshold large-print lists are built lazily and cached on the (immutable after
  build) tape, so a family that does not need them never pays for them.

Input rows are tuples `(contract_id, time_ns, price, size, multiplier, condition_excluded, seq[, side])`
sorted by (time_ns, seq); `side` is ignored (AMB-2). `contracts` maps a contract id to
`(right, strike_ticks, expiry, lane)` with right "C" or "P". Structural problems do not raise: the tape
carries `error` (the code of `stream_code`, the per-position classification of item 15; no input raises) and the family functions answer `invalid_input` with that code.
"""
from bisect import bisect_left, bisect_right
from itertools import accumulate

from .flowgrid import NS, STANDARD_MULTIPLIER, price_ticks   # shared constants and the one price parser (story A)

FILTERS = ("all", "calls", "puts")
_RIGHT_OF = {"all": ("C", "P"), "calls": ("C",), "puts": ("P",)}
K_NONSTD, K_EXCL = 1, 2
LARGE_CACHE_THRESHOLDS = 4


class Group:
    """Eligible prints of one (lane, right): sorted columns plus lazily built prefix arrays."""
    __slots__ = ("lane", "right", "t", "p", "s", "ci", "nt", "et", "_pp", "_sp", "_large")

    def __init__(self, lane, right):
        self.lane, self.right = lane, right
        self.t, self.p, self.s, self.ci = [], [], [], []
        self.nt, self.et = [], []          # nonstandard-only and excluded-condition times (rare)
        self._pp = self._sp = None
        self._large = {}

    def prem_prefix(self):
        pp = self._pp
        if pp is None:
            pp = self._pp = list(accumulate(self.p, initial=0))
        return pp

    def size_prefix(self):
        sp = self._sp
        if sp is None:
            sp = self._sp = list(accumulate(self.s, initial=0))
        return sp

    def large(self, threshold):
        """(times, premium prefix) of the eligible prints with premium >= threshold ticks (cached)."""
        got = self._large.get(threshold)
        if got is None:
            p = self.p
            idx = [i for i, v in enumerate(p) if v >= threshold]
            t = self.t
            got = ([t[i] for i in idx], list(accumulate((p[i] for i in idx), initial=0)))
            cache = self._large
            while len(cache) >= LARGE_CACHE_THRESHOLDS:       # bounded: keep the most recent thresholds only
                del cache[next(iter(cache))]
            cache[threshold] = got
        return got


class PrintTape:
    """Immutable-after-build columnar tape. Use `build_tape`."""
    __slots__ = ("error", "n_prints", "n_eligible", "groups", "cidx", "c_id", "c_right", "c_strike", "c_expiry",
                 "c_lane", "c_group", "rare", "rare_t", "_sel")

    def select(self, lane, flt="all"):
        """Groups of the request lane (right per filter): lane isolation by construction."""
        key = (lane, flt)
        got = self._sel.get(key)
        if got is None:
            try:
                rights = _RIGHT_OF[flt]
            except KeyError:
                raise ValueError("filter must be one of %r, got %r" % (FILTERS, flt)) from None
            got = self._sel[key] = tuple(g for (ln, r), g in sorted(self.groups.items()) if ln == lane and r in rights)
        return got

    # ---- window primitives (closed windows [start, end]) -------------------------------------------------
    def stats(self, groups, start, end, want_size=False):
        """(premium, size or None, eligible, nonstandard, excluded) over [start, end] in `groups`."""
        prem = size = ne = nn = nx = 0
        for g in groups:
            t = g.t
            a, b = bisect_left(t, start), bisect_right(t, end)
            if b > a:
                pp = g.prem_prefix()
                prem += pp[b] - pp[a]
                ne += b - a
                if want_size:
                    sp = g.size_prefix()
                    size += sp[b] - sp[a]
            nt = g.nt
            if nt:
                nn += bisect_right(nt, end) - bisect_left(nt, start)
            et = g.et
            if et:
                nx += bisect_right(et, end) - bisect_left(et, start)
        return prem, size, ne, nn, nx

    def f1_sums(self, groups, t_ns):
        """(p60, p900, eligible, nonstandard, excluded): the 60 s and 900 s premium windows ending at T and
        the coverage counters of the 900 s window, from one bisect set per group."""
        s900, s60 = t_ns - 900 * NS, t_ns - 60 * NS
        p60 = p900 = ne = nn = nx = 0
        for g in groups:
            t = g.t
            b = bisect_right(t, t_ns)
            a9 = bisect_left(t, s900, 0, b)
            if b > a9:
                pp = g.prem_prefix()
                top = pp[b]
                p900 += top - pp[a9]
                p60 += top - pp[bisect_left(t, s60, a9, b)]
                ne += b - a9
            nt = g.nt
            if nt:
                nn += bisect_right(nt, t_ns) - bisect_left(nt, s900)
            et = g.et
            if et:
                nx += bisect_right(et, t_ns) - bisect_left(et, s900)
        return p60, p900, ne, nn, nx

    def f1_columns(self, groups, times):
        """Columnar (p60, p900) for ascending or arbitrary window-end `times`; C-speed maps, no per-point
        Python loop. Used for the F12 grid."""
        m = len(times)
        p60, p900 = [0] * m, [0] * m
        if not m:
            return p60, p900
        e60 = [t - 60 * NS for t in times]
        e900 = [t - 900 * NS for t in times]
        for g in groups:
            if not g.t:
                continue
            t = g.t
            pp = g.prem_prefix()
            hi = list(map(pp.__getitem__, map(bisect_right, [t] * m, times)))
            l60 = list(map(pp.__getitem__, map(bisect_left, [t] * m, e60)))
            l900 = list(map(pp.__getitem__, map(bisect_left, [t] * m, e900)))
            # a window start after its end contributes max(0, ...) only when start > end, never here
            p60 = [x + (h - l) for x, h, l in zip(p60, hi, l60)]
            p900 = [x + (h - l) for x, h, l in zip(p900, hi, l900)]
        return p60, p900


def _register(cid, contracts, cidx, c_id, c_right, c_strike, c_expiry, c_lane, c_group, app, groups):
    right, strike, expiry, lane = contracts[cid]
    ci = len(c_id)
    cidx[cid] = ci
    c_id.append(cid)
    c_right.append(right)
    c_strike.append(strike)
    c_expiry.append(expiry)
    c_lane.append(lane)
    g = groups.get((lane, right))
    if g is None:
        g = groups[(lane, right)] = Group(lane, right)
    c_group.append(g)
    app.append((g.t.append, g.p.append, g.s.append, g.ci.append))
    return ci


def stream_code(prints, contracts):
    """The structural code of a print list under the ruled per-field contract (IO contract section 9, items 5, 13, 15),
    or None; the same classification as `flowgrid.check_prints` (story A), but total: no exception escapes, whatever
    the objects in the list (unhashable contract ids, NaN, bytes, nested objects, huge ints, objects whose hash,
    comparison or arithmetic raises, short and non-sequence prints). Authoritative slow path: `build_tape` runs its
    fused fast loop and calls this only when the fast loop saw anything unusual.

    Positions, in order (a wrong-typed field reports `malformed_type` at the position where its value check would run;
    within a position a value code beats `malformed_type`; the whole list is scanned): (1) ordering: unordered_prints
    for a genuine adjacent out-of-order pair of prints whose time and seq are ints (bool excluded; a pair with a non-int
    time or seq is not compared), else malformed_type for a wrong-typed time or seq; (2) negative_size_or_price: a
    well-typed negative size, or a well-typed negative price on a print whose size is well-typed; else malformed_type for
    a wrong-typed size; (3) bad_multiplier: an int <= 0, else malformed_type for a wrong-typed multiplier; (4)
    unknown_contract: a hashable contract id absent from `contracts`; (5) malformed_type for the fields with no value
    code (price not an int or a valid decimal text, condition_excluded other than a bool, 0 or 1, an unhashable contract
    id, a print that is not a sequence of at least 7 items)."""
    ord_val = ord_mal = neg_val = neg_mal = bad_val = bad_mal = unknown = other = False
    pt = ps = None
    prev_ok = False
    try:
        it = iter(prints)
    except Exception:
        return "malformed_type"
    for p in it:
        try:
            cid, t, price, size, mult, excl, seq = p[0], p[1], p[2], p[3], p[4], p[5], p[6]
        except Exception:
            other = True
            prev_ok = False
            continue
        if type(t) is int and type(seq) is int:
            if prev_ok and (t < pt or (t == pt and seq < ps)):
                ord_val = True
            pt, ps, prev_ok = t, seq, True
        else:
            ord_mal = True
            prev_ok = False
        try:
            ticks = price_ticks(price)
        except Exception:
            ticks = None
            other = True
        if type(size) is not int:
            neg_mal = True
        elif size < 0 or (ticks is not None and ticks < 0):
            neg_val = True
        if type(mult) is not int:
            bad_mal = True
        elif mult <= 0:
            bad_val = True
        if type(excl) is not bool and not (type(excl) is int and excl in (0, 1)):
            other = True
        if contracts is not None:
            try:
                if cid not in contracts:
                    unknown = True
            except Exception:
                other = True
    if ord_val:
        return "unordered_prints"
    if ord_mal:
        return "malformed_type"
    if neg_val:
        return "negative_size_or_price"
    if neg_mal:
        return "malformed_type"
    if bad_val:
        return "bad_multiplier"
    if bad_mal:
        return "malformed_type"
    if unknown:
        return "unknown_contract"
    if other:
        return "malformed_type"
    return None


def build_tape(prints, contracts, validate="full"):
    """One pass over `prints`. validate "full" (default) checks order, sign and multiplier; "off" trusts a
    stream already validated by the caller (undefined results if it is not sorted).

    Fast path: the fused loop below handles well-formed prints. Anything unusual (a wrong type, an order or sign
    fault, an unknown or unhashable contract id, a short print, any exception) makes the loop note `suspect` and move
    on; the error code is then `stream_code(prints, contracts)`, the one authoritative classification, so the code
    never depends on the loop. No exception from a print field escapes; an exception that `stream_code` cannot
    explain (a malformed contract table, not a print) is re-raised."""
    tape = PrintTape()
    cidx, c_id, c_right, c_strike, c_expiry, c_lane, c_group, app, groups = {}, [], [], [], [], [], [], [], {}
    rare = []
    rare_add = rare.append
    suspect = False
    crashed = None
    pt, ps = -(1 << 127), 0
    full = validate != "off"
    get = cidx.get
    n = 0
    if not isinstance(prints, (list, tuple)):
        try:
            prints = list(prints)
        except Exception:
            prints = []
            suspect = True
    try:
        for p in prints:
            n += 1
            cid, t, price, size, mult, excl, seq = p[:7]
            if (t.__class__ is not int or size.__class__ is not int or mult.__class__ is not int
                    or seq.__class__ is not int
                    or (excl.__class__ is not bool and (excl.__class__ is not int or excl not in (0, 1)))):
                suspect = True
                continue
            if price.__class__ is not int:
                try:
                    price = price_ticks(price)
                except Exception:
                    suspect = True
                    continue
            if full:
                if t < pt or (t == pt and seq < ps) or size < 0 or price < 0 or mult <= 0:
                    suspect = True
                    continue
                pt, ps = t, seq
            ci = get(cid)
            if ci is None:
                if cid not in contracts:
                    suspect = True
                    continue
                ci = _register(cid, contracts, cidx, c_id, c_right, c_strike, c_expiry, c_lane, c_group, app, groups)
            if excl:
                rare_add((t, ci, K_EXCL))
            elif mult != 100:
                rare_add((t, ci, K_NONSTD))
            else:
                ta, pa, sa, ca = app[ci]
                ta(t)
                pa(price * size * 100)
                sa(size)
                ca(ci)
    except Exception as exc:                      # unhashable id, short or non-sequence print, odd objects
        suspect = True
        crashed = exc
    error = None
    if suspect:
        error = stream_code(prints, contracts)
        if error is None and crashed is not None:
            raise crashed
        if error is None:                         # cannot happen (every fast-path flag is a stream_code defect);
            error = "malformed_type"              # fail closed rather than keep a tape that skipped prints
    for t, ci, kind in rare:
        g = c_group[ci]
        (g.nt if kind == K_NONSTD else g.et).append(t)
    tape.error = error
    tape.n_prints = n
    tape.n_eligible = n - len(rare)
    tape.groups = groups
    tape.cidx, tape.c_id, tape.c_right, tape.c_strike = cidx, c_id, c_right, c_strike
    tape.c_expiry, tape.c_lane, tape.c_group = c_expiry, c_lane, c_group
    tape.rare = rare
    tape.rare_t = [r[0] for r in rare]
    tape._sel = {}
    return tape
