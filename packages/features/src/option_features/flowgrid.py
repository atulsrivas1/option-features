"""M2 shared helpers: calendar, contracts, print validation, eligible-print window totals and the trade-to-grid builder.

Pure and single-threaded; exact integer arithmetic only (premium = price ticks x size x multiplier, 1 tick = 10^-4).
Owned by story A and imported by story B (docs/m2/M2_STORE_API.md is the contract).

Eligible print (one definition for every M2 family): multiplier 100 and not condition_excluded, in the requested
lane. Coverage: `excluded_condition_count` counts every in-window print with an excluded condition (including those
that are also nonstandard); `nonstandard_count` counts non-excluded prints whose multiplier is not 100.

Grid: point i is at open_ns + 60 s x i, i in range(minutes); the value is the window-W value of the closed window
[t_i - W, t_i] (AMB-4, AMB-8). The builder is one pass over the prints with difference arrays: a print adds its
quantity at the first grid point that sees it and subtracts it after the last, so the work is O(prints + minutes)
per series and no per-point rescan; contract series exist only for contracts that have eligible prints.

Validation scope: `validate="full"` scans every print (build and store boundary); `validate="scanned"` checks only
what is read and assumes the documented precondition that prints are sorted by (time_ns, seq), which lets the
window be found by binary search (O(log n + window)).
"""
from array import array
from bisect import bisect_left, bisect_right
import re
from collections import namedtuple

from .flowresult import M2StructuralError

NS = 1000000000
GRID_NS = 60 * NS
STANDARD_MULTIPLIER = 100
TICK_DIGITS = 4
TICK = 10 ** TICK_DIGITS
_POW = tuple(10 ** i for i in range(TICK_DIGITS + 1))

Contract = namedtuple("Contract", "right strike expiry lane underlying")
WindowTotals = namedtuple("WindowTotals", "premium volume count put_volume call_volume eligible_count "
                                          "nonstandard_count excluded_condition_count")
GridRecord = namedtuple("GridRecord", "series_id metric window_s session_id minutes idx vals total")
SessionBuild = namedtuple("SessionBuild", "records eligible_count nonstandard_count excluded_condition_count")


class Calendar:
    """Ordered sessions [(session_id, minutes)], ascending civil-date strings; append-only (positions never change)."""
    __slots__ = ("ids", "minutes", "_pos")

    def __init__(self, sessions=()):
        self.ids, self.minutes, self._pos = [], [], {}
        self.extend(sessions)

    def extend(self, sessions):
        for sid, minutes in sessions:
            if self.ids and sid <= self.ids[-1]:
                raise ValueError("calendar sessions must be strictly ascending: %r" % (sid,))
            self._pos[sid] = len(self.ids)
            self.ids.append(sid)
            self.minutes.append(minutes)

    def position(self, session_id):
        return self._pos.get(session_id)

    def minutes_of(self, session_id):
        return self.minutes[self._pos[session_id]]

    def __len__(self):
        return len(self.ids)

    def __contains__(self, session_id):
        return session_id in self._pos


_PRICE = re.compile(r"(-?)([0-9]*)(?:\.([0-9]*))?\Z")


def _parse_price(price):
    """Ticks of a price, or None when malformed. An int (not bool) is ticks (dollars x 10^4); a text price follows the
    ASCII grammar -?(digits(.digits*)? | .digits) ('1.' and '.5' are valid, trailing zeros accepted) and a non-zero digit
    beyond the 4th decimal is malformed; float, bool and every other type are malformed."""
    kind = type(price)
    if kind is int:
        return price
    if kind is str:
        m = _PRICE.match(price)
        if m is None:
            return None
        sign, whole, frac = m.groups()
        if not whole and not frac:
            return None
        frac = frac or ""
        if len(frac) > TICK_DIGITS:
            if frac[TICK_DIGITS:].strip("0"):
                return None
            frac = frac[:TICK_DIGITS]
        ticks = int((whole or "0") + frac.ljust(TICK_DIGITS, "0"))
        return -ticks if sign else ticks
    return None


def price_ticks(price):
    """Integer ticks (price x 10^4): an int is already ticks, a decimal string follows the grammar of `_parse_price`;
    anything malformed raises ValueError (`check_prints` reports it as malformed_type first)."""
    ticks = _parse_price(price)
    if ticks is None:
        raise ValueError("malformed price: %r" % (price,))
    return ticks


def check_prints(prints, contracts=None):
    """First structural code of a print list or None, RULED precedence: unordered_prints (order key (time_ns, seq)),
    negative_size_or_price, bad_multiplier (multiplier <= 0), unknown_contract (contract id not in `contracts`, when
    given), malformed_type (price, size, multiplier, time or seq of the wrong type, a bad price text, a
    condition_excluded flag other than bool, 0 or 1). The whole list is scanned."""
    unordered = neg = bad = unknown = malformed = False
    pt = ps = None
    for p in prints:
        cid, t, price, size, mult, excl, seq = p[0], p[1], p[2], p[3], p[4], p[5], p[6]
        if type(t) is not int or type(seq) is not int or type(size) is not int or type(mult) is not int:
            malformed = True
        ticks = _parse_price(price)
        if ticks is None:
            malformed = True
        elif ticks < 0:
            neg = True
        if type(excl) is not bool and not (type(excl) is int and excl in (0, 1)):
            malformed = True
        try:
            if size < 0:
                neg = True
            if mult <= 0:
                bad = True
            if pt is not None and (t < pt or (t == pt and seq < ps)):
                unordered = True
        except TypeError:
            malformed = True
        pt, ps = t, seq
        if contracts is not None and cid not in contracts:
            unknown = True
    if unordered:
        return "unordered_prints"
    if neg:
        return "negative_size_or_price"
    if bad:
        return "bad_multiplier"
    if unknown:
        return "unknown_contract"
    if malformed:
        return "malformed_type"
    return None


def _time_key(p):
    return p[1]


def window_totals(prints, contracts, evaluation_ns, window_s, lane="stock", side_filter="all", validate="full",
                  open_ns=None):
    """Totals over the eligible prints in the closed window [T - W, T] (see module doc); with `open_ns` the window is
    clipped at the session open (prints before it never count). `side_filter` is a plain right filter: "all", "calls"
    or "puts". Raises M2StructuralError for a bad print."""
    if validate == "full":
        code = check_prints(prints, contracts)
        if code:
            raise M2StructuralError(code)
        lo_i, hi_i = 0, len(prints)
    else:
        lo_i = bisect_left(prints, evaluation_ns - window_s * NS, key=_time_key)
        hi_i = bisect_right(prints, evaluation_ns, key=_time_key)
        code = check_prints(prints[lo_i:hi_i], contracts)
        if code:
            raise M2StructuralError(code)
    lo, hi = evaluation_ns - window_s * NS, evaluation_ns
    if open_ns is not None and open_ns > lo:
        lo = open_ns
    want = None if side_filter == "all" else ("C" if side_filter == "calls" else "P")
    prem = vol = cnt = put = call = nonstd = excl = 0
    for i in range(lo_i, hi_i):
        p = prints[i]
        t = p[1]
        if t < lo or t > hi:
            continue
        c = contracts[p[0]]
        if c.lane != lane or (want is not None and c.right != want):
            continue
        if p[5]:
            excl += 1
            continue
        mult = p[4]
        if mult != STANDARD_MULTIPLIER:
            nonstd += 1
            continue
        size = p[3]
        prem += price_ticks(p[2]) * size * mult
        vol += size
        cnt += 1
        if c.right == "P":
            put += size
        else:
            call += size
    return WindowTotals(prem, vol, cnt, put, call, cnt, nonstd, excl)


def _pack_q(values):
    try:
        return array("q", values)
    except OverflowError:
        return list(values)


_UNSIGNED = (("B", 255), ("H", 65535), ("I", 4294967295), ("Q", 18446744073709551615))


def narrow(values):
    """Smallest typed array that holds `values` exactly (unsigned B, H, I, Q; signed q when negative); a tuple when a
    value does not fit 64 bits."""
    if not len(values):
        return array("B")
    lo, hi = min(values), max(values)
    if lo >= 0:
        for tc, lim in _UNSIGNED:
            if hi <= lim:
                return array(tc, values)
    elif lo >= -(1 << 63) and hi < (1 << 63):
        return array("q", values)
    return tuple(values)


def freeze(x):
    """Read-only form of a narrowed array (memoryview, same item format) or a tuple."""
    return memoryview(x).toreadonly() if isinstance(x, array) else x


def _expand(events, minutes, slot):
    """Sparse (idx, vals) of the prefix sum of {grid index: [deltas]} for `slot`, zeros dropped (general path)."""
    idx, vals = array("H"), []
    cur = 0
    keys = sorted(events)
    last = len(keys) - 1
    for n, k in enumerate(keys):
        cur += events[k][slot]
        end = keys[n + 1] if n < last else minutes
        if cur and end > k:
            idx.extend(range(k, end))
            vals.extend([cur] * (end - k))
    return idx, _pack_q(vals)


def _expand3(events, minutes):
    """(idx, premium vals, size vals, count vals) for one contract: one pass, one shared idx array. Every quantity is
    nonnegative, so a point is active exactly when the count is positive; premium or size can still be 0 on an active
    point (zero price or size), which the general per-slot path handles."""
    idx = array("H")
    vp, vs, vc = array("q"), array("q"), array("q")
    cp = cs = cc = 0
    keys = sorted(events)
    last = len(keys) - 1
    try:
        for n, k in enumerate(keys):
            e = events[k]
            cp += e[0]
            cs += e[1]
            cc += e[2]
            end = keys[n + 1] if n < last else minutes
            if cc and end > k:
                if not (cp and cs):
                    raise ArithmeticError
                size = end - k
                idx.extend(range(k, end))
                if size == 1:
                    vp.append(cp)
                    vs.append(cs)
                    vc.append(cc)
                else:
                    vp.extend([cp] * size)
                    vs.extend([cs] * size)
                    vc.extend([cc] * size)
    except (ArithmeticError, OverflowError):
        out = []
        for slot in range(3):
            out.append(_expand(events, minutes, slot))
        return out[0][0], out[0][1], out[1][1], out[2][1], out[1][0], out[2][0]
    return idx, vp, vs, vc, idx, idx


def _expand_dense(diff, minutes):
    idx, vals = array("H"), []
    cur = 0
    for i in range(minutes):
        cur += diff[i]
        if cur:
            idx.append(i)
            vals.append(cur)
    return idx, _pack_q(vals)


def build_session_records(prints, contracts, session_id, open_ns, close_ns, minutes, windows=(300,), lane="stock",
                          name_series_id=None, contract_series=True, validate="full"):
    """Turn one session of prints into sparse grid records for every window in `windows` (see module doc).

    Name-level series (id `name_series_id`, skipped when None) carry premium, contracts, prints, put_volume and
    call_volume; contract-level series (id = contract id) carry premium, contracts and prints, only for contracts
    with eligible prints. The session total of every record is the sum over eligible prints with
    open_ns <= time_ns <= close_ns."""
    if validate == "full":
        code = check_prints(prints, contracts)
        if code:
            raise M2StructuralError(code)
    nonstd = excl = elig = 0
    wins = tuple(windows)
    ev_ns = tuple(w * NS for w in wins)
    last = minutes - 1
    # name level: difference arrays per window and metric (premium, contracts, prints, put, call)
    name_diff = [[[0] * (minutes + 1) for _ in range(5)] for _ in wins] if name_series_id is not None else None
    name_tot = [0, 0, 0, 0, 0]
    cdiff = {}   # contract id -> per window dict idx -> [prem, size, count]
    ctot = {}    # contract id -> [prem, size, count]
    cinfo = {}
    for p in prints:
        t = p[1]
        if t < open_ns or t > close_ns:
            continue
        cid = p[0]
        c = cinfo.get(cid)
        if c is None:
            ct = contracts[cid]
            c = cinfo[cid] = (ct.lane == lane, ct.right == "P")
        if not c[0]:
            continue
        if p[5]:
            excl += 1
            continue
        mult = p[4]
        if mult != STANDARD_MULTIPLIER:
            nonstd += 1
            continue
        elig += 1
        size = p[3]
        prem = price_ticks(p[2]) * size * mult
        rel = t - open_ns
        lo = -(-rel // GRID_NS)
        is_put = c[1]
        if name_diff is not None:
            name_tot[0] += prem
            name_tot[1] += size
            name_tot[2] += 1
            name_tot[3 if is_put else 4] += size
        if contract_series:
            tot = ctot.get(cid)
            if tot is None:
                tot = ctot[cid] = [0, 0, 0]
                cdiff[cid] = [{} for _ in wins]
            tot[0] += prem
            tot[1] += size
            tot[2] += 1
        if lo > last:
            continue
        for wi, wns in enumerate(ev_ns):
            hi = (rel + wns) // GRID_NS
            if hi > last:
                hi = last
            end = hi + 1
            if name_diff is not None:
                nd = name_diff[wi]
                row = nd[0]
                row[lo] += prem
                row[end] -= prem
                row = nd[1]
                row[lo] += size
                row[end] -= size
                row = nd[2]
                row[lo] += 1
                row[end] -= 1
                row = nd[3 if is_put else 4]
                row[lo] += size
                row[end] -= size
            if contract_series:
                ev = cdiff[cid][wi]
                a = ev.get(lo)
                if a is None:
                    ev[lo] = [prem, size, 1]
                else:
                    a[0] += prem
                    a[1] += size
                    a[2] += 1
                if end <= last:
                    b = ev.get(end)
                    if b is None:
                        ev[end] = [-prem, -size, -1]
                    else:
                        b[0] -= prem
                        b[1] -= size
                        b[2] -= 1
    records = []
    if name_diff is not None:
        names = ("premium", "contracts", "prints", "put_volume", "call_volume")
        for wi, w in enumerate(wins):
            for m in range(5):
                idx, vals = _expand_dense(name_diff[wi][m], minutes)
                records.append(GridRecord(name_series_id, names[m], w, session_id, minutes, freeze(narrow(idx)),
                                          freeze(narrow(vals)), name_tot[m]))
    if contract_series:
        for cid in sorted(ctot):
            tot = ctot[cid]
            for wi, w in enumerate(wins):
                ip, vp, vs, vc, is_, ic = _expand3(cdiff[cid][wi], minutes)
                fi = freeze(ip)                      # one shared read-only index per (contract, session) when shared
                fs = fi if is_ is ip else freeze(is_)
                fc = fi if ic is ip else freeze(ic)
                records.append(GridRecord(cid, "premium", w, session_id, minutes, fi, freeze(narrow(vp)), tot[0]))
                records.append(GridRecord(cid, "contracts", w, session_id, minutes, fs, freeze(narrow(vs)), tot[1]))
                records.append(GridRecord(cid, "prints", w, session_id, minutes, fc, freeze(narrow(vc)), tot[2]))
    return SessionBuild(records, elig, nonstd, excl)
