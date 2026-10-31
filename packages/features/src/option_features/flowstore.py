"""M2 history store: array-backed per-series grid history, retention ring, immutable cached views, canonical text.

Pure and single-threaded; exact integers only (`Fraction` appears in view statistics at the output boundary).

Key = (series_id, metric, window_s); one ring per key, append-only in session order, retention `k` (default 20, hard
cap 60) counting every stored record, complete or not. M3a (story S02, R-52, R-114): `add_series(series_id, k)` declares
a per-series k up to 252 for the M3a series (M3A_METRICS and skew-type `skew*_fwd`); M2 series keep k <= 60. An M3a
record may carry `delta_convention` (R-160), written in its canonical line only when given (no M2 line changes). A
record is a sparse grid (ascending `array('H')` indexes of the nonzero points, `array('q')` values, or a plain
list when a value exceeds 64 bits), the session total, a complete flag; zeros are implicit. Series are created lazily by the first append, so a contract without prints costs
nothing. Sealed records never change; completing an incomplete record (`seal`) is the only mutation.

Reads go through `baseline()`: the K calendar sessions right before `as_of`, all stored and complete, same lane (no
substitution, no look-ahead). The returned `HistoryView` is immutable and cached on the ring until the ring changes
(append, seal or eviction clear it: correct invalidation by construction, bounded to a few entries per ring). A
view stores the sorted nonzero counted values once (built on first rank or median read: concatenate the K slices
after the first W/60 points of each session, sort once) and the number of zeros, so rank is two bisects and the
median is an index into the implicit sorted array; mean is the cached exact sum over n.

Canonical text (docs/m2/M2_IO_CONTRACT.md sections 4 and 6): one line per record in (series_id, metric, window_s,
session_id) order, keys `series_id, metric, session_id, window_s, grid, total, complete, content_sha256`, LF;
content_sha256 = SHA-256 of the line without that field followed by LF. `load` reads the same bytes back, verifies each
hash from the raw bytes and parses a grid lazily on first use.
"""
import gc
import hashlib
import json
import os
import re
import sys
from array import array
from bisect import bisect_left, bisect_right
from fractions import Fraction
from functools import wraps

from .flowgrid import _pack_q, narrow
from .flowresult import M2StructuralError

MAX_K = 60
MAX_SERIES_K = 252      # M3a (R-52, R-114): per-series k via add_series, M3a series only; M2 series keep MAX_K
# M3a series metrics (series_id "<UNDERLYING>/<lane>/<metric>", R-153, R-159); skew-type `<metric>_fwd` included
M3A_METRICS = frozenset(("atm_iv", "atm_iv_close", "iv30", "iv30_close", "skew25", "skew25_fwd", "term_30_91"))
CONVENTIONS = ("spot", "forward")
_SNAP_MAGIC = b"M2SNAP1"
_BIN_NAME = b"M2BIN"
_BIN_VERSION = (1).to_bytes(2, "little")
_BIN_MAGIC = _BIN_NAME + _BIN_VERSION          # 7 bytes: name and little-endian version
_BIN_HEADER = len(_BIN_MAGIC) + 8 + 32 + 8     # magic, total length, SHA-256, table length: the smallest valid file
_TRAILER = re.compile(r"#END records=(\d+) content_sha256=([0-9a-f]{64})\Z")
_VIEW_CACHE = 4
_SIZE = {"B": 1, "H": 2, "I": 4, "L": 4, "Q": 8, "q": 8}

_LINE = re.compile(r'\{"series_id":(".*?"),"metric":(".*?"),"session_id":(".*?"),"window_s":(\d+),"grid":\[')


class _Rec:
    __slots__ = ("session_id", "minutes", "idx", "vals", "total", "complete", "sha", "txt", "sparse", "itxt", "conv")

    def __init__(self, session_id, minutes, idx, vals, total, complete, txt=None, sparse=False, itxt=None, conv=None):
        self.session_id, self.minutes, self.idx, self.vals = session_id, minutes, idx, vals
        self.total, self.complete, self.sha, self.txt = total, complete, None, txt
        self.sparse, self.itxt, self.conv = sparse, itxt, conv


_FULL_IDX = {}
_INT_ONLY = frozenset((int,))
_FITS_Q = frozenset("bBhHiIlq")      # array formats whose every value fits int64


def _full_idx(n):
    """Shared index array 0..n-1 for dense grids without a zero point (the M3a minute series): one copy per grid
    length instead of one per record (the store never mutates a stored array)."""
    a = _FULL_IDX.get(n)
    if a is None:
        a = _FULL_IDX[n] = array("H", range(n))
    return a


def _is_m3a_series(series_id):
    """True for an M3a series id. A str subclass is refused (TypeError): it could lie to rsplit, ==, hash or str and
    pass an M3a-named id off as an M2 one, bypassing the exact-integer rules."""
    if type(series_id) is not str and isinstance(series_id, str):
        raise TypeError("series_id must be an exact str")
    metric = str.rsplit(series_id, "/", 1)[-1] if type(series_id) is str else None
    return metric is not None and (metric in M3A_METRICS or (metric.startswith("skew") and metric.endswith("_fwd")))


def _sparse(rec):
    """Materialise a lazily loaded record (parse its grid text once). A record supplied dense keeps only its nonzero
    points; a record supplied sparse keeps exactly the supplied indexes and values."""
    if rec.idx is None:
        idx = array("H")
        if rec.sparse:
            if rec.itxt:
                idx.extend([int(t) for t in rec.itxt.split(",")])
            vals = [int(t) for t in rec.txt.split(",")] if rec.txt else []
        else:
            vals = []
            if rec.txt:
                i = 0
                for tok in rec.txt.split(","):
                    if tok != "0":
                        idx.append(i)
                        vals.append(int(tok))
                    i += 1
        rec.idx, rec.vals, rec.txt, rec.itxt = idx, narrow(vals), None, None
    return rec


def _grid_text(rec, cache=None):
    """Grid as supplied: dense records list every point up to the supplied length (no padding); sparse records list
    the supplied values only (the indexes go in `_idx_text`). `cache` (one dump call) reuses the text of a value array
    shared by several records."""
    if rec.txt is not None:
        return rec.txt
    _sparse(rec)
    idx, vals = rec.idx, rec.vals
    if rec.sparse:
        if cache is not None:
            got = cache.get(id(vals))
            if got is not None:
                return got[1]
        text = ",".join(map(str, vals if type(vals) is tuple else vals.tolist()))
        if cache is not None:
            cache[id(vals)] = (vals, text)
        return text
    vals = vals if type(vals) is tuple else vals.tolist()
    if len(idx) == rec.minutes and (type(vals) is list or _INT_ONLY.issuperset(map(type, vals))):
        # no zero point and exact ints: the values, one C call
        return repr(vals if type(vals) is list else list(vals))[1:-1].replace(" ", "")
    tokens = ["0"] * rec.minutes
    for i, v in zip(idx if type(idx) is tuple else idx.tolist(), vals):
        tokens[i] = str(v)
    return ",".join(tokens)


def _idx_text(rec, cache=None):
    if rec.itxt is not None:
        return rec.itxt
    _sparse(rec)
    idx = rec.idx
    if cache is not None:
        got = cache.get(id(idx))
        if got is not None:
            return got[1]
    text = ",".join(map(str, idx if type(idx) is tuple else idx.tolist()))
    if cache is not None:
        cache[id(idx)] = (idx, text)
    return text


_INT_CODES = frozenset("bBhHiIlLqQ")


def _m3a_values(x, memo):
    """Validated private form of the values of an M3a record: an integer-typed array / memoryview is taken as is; a list
    or tuple is copied ONCE to a tuple and every element must be an exact int; anything else is a TypeError. One source
    object shared by several records of an append_many is validated once."""
    got = memo.get(("m3a", id(x))) if memo is not None else None
    if got is not None:
        return got[1]
    if isinstance(x, array):
        ok = x.typecode in _INT_CODES
        out = x
    elif isinstance(x, memoryview):
        ok = x.format in _INT_CODES and x.ndim == 1
        out = x
    elif type(x) in (list, tuple):
        out = tuple(x)
        ok = _INT_ONLY.issuperset(map(type, out))
    else:
        ok = False
    if not ok:
        raise TypeError("M3a values must be exact integers")
    if memo is not None:
        memo[("m3a", id(x))] = (x, out)
    return out


def _m3a_record(r):
    """True when a batch element names an M3a series (never raises: anything odd is left to append_record)."""
    sid = getattr(r, "series_id", None)
    return type(sid) is str and _is_m3a_series(sid)


def _own(x, memo):
    """Private copy of an index or value array (read-only memoryview, array or sequence): typed array or tuple. One
    source object shared by several records of an append_many is copied once."""
    if memo is not None:
        got = memo.get(id(x))
        if got is not None:
            return got[1]
    if isinstance(x, memoryview):
        a = array(x.format)
        a.frombytes(x.cast("B"))
    elif isinstance(x, array):
        a = array(x.typecode, x)
    else:
        a = narrow(x)
    if memo is not None:
        memo[id(x)] = (x, a)      # keeps the source alive so its id cannot be reused within the call
    return a


def _nogc(fn):
    """Run `fn` with the cyclic collector paused (restored on exit, even on error). Loads, attaches and dumps create or
    visit hundreds of thousands of acyclic objects; the generation scans they trigger were the larger part of their
    time. Nothing is changed but timing."""
    @wraps(fn)
    def run(*a, **kw):
        was = gc.isenabled()
        gc.disable()
        try:
            return fn(*a, **kw)
        finally:
            if was:
                gc.enable()
    return run


def _atomic_write(path, data):
    tmp = "%s.tmp%d" % (path, os.getpid())
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


class _Cols:
    """M3a store layout of one ring (story S02, R-193): session-ordered columns kept in step with the ring at append,
    seal and eviction, so an M3a read is bounds arithmetic plus slices, with no per-call loop over records.

    ids, recs, tot (record totals), done (complete flags), mins (grid lengths), conv (delta_convention), inb (grid held
    in the block) are lists in session order (oldest first). Minute grids that are dense, have no zero point, fit the
    stride and int64 live in ONE contiguous int64 block of cap x stride values (cap = the ring k, stride = the longest
    calendar session); a record's `vals` is then a read-only-by-convention memoryview of its row and its `idx` the shared
    full index, so there is no second copy. Rows are used circularly: the row of session j is (head + j) % cap, so
    the minute column of the whole ring is the strided slice block[minute::stride] rotated by head. A record evicted
    from the ring gets a private copy of its row before the row is reused. Other grids keep their own arrays
    (inb False) and are read record by record."""
    __slots__ = ("ids", "recs", "tot", "done", "mins", "conv", "inb", "cap", "head", "stride", "block", "mv")

    def __init__(self, cap, stride):
        self.ids, self.recs, self.tot, self.done, self.mins, self.conv, self.inb = [], [], [], [], [], [], []
        self.cap, self.head, self.stride = cap, 0, stride
        self.block = self.mv = None

    def push(self, rec):
        if len(self.ids) >= self.cap:
            self.evict()
        inb = self._place(rec, (self.head + len(self.ids)) % self.cap)
        self.ids.append(rec.session_id)
        self.recs.append(rec)
        self.tot.append(rec.total)
        self.done.append(rec.complete)
        self.mins.append(rec.minutes)
        self.conv.append(rec.conv)
        self.inb.append(inb)

    def evict(self):
        rec = self.recs[0]
        if self.inb[0]:
            rec.vals = array("q", rec.vals)          # detach: the row is reused next
        for col in (self.ids, self.recs, self.tot, self.done, self.mins, self.conv, self.inb):
            del col[0]
        self.head = (self.head + 1) % self.cap

    def seal(self, session_id):
        i = bisect_left(self.ids, session_id)
        if i < len(self.ids) and self.ids[i] == session_id:
            self.done[i] = True

    def _place(self, rec, row):
        m = rec.minutes
        if not m or m > self.stride or rec.sparse:
            return False
        if rec.idx is None:                          # loaded from text: parse straight into the block
            if not rec.txt:
                return False
            vals = [int(t) for t in rec.txt.split(",")]
            if len(vals) != m or 0 in vals:
                _sparse(rec)
                return False
        else:
            if len(rec.idx) != m:                    # zero points: sparse form, read record by record
                return False
            vals = rec.vals
        q = isinstance(vals, array) and vals.typecode == "q"
        fmt = vals.typecode if isinstance(vals, array) else getattr(vals, "format", None)
        if type(vals) is tuple:
            return False
        if fmt not in _FITS_Q and len(vals) and (min(vals) < -(1 << 63) or max(vals) >= (1 << 63)):
            return False
        if self.block is None:
            self.block = array("q", bytes(8 * self.cap * self.stride))
            self.mv = memoryview(self.block)
        off = row * self.stride
        self.mv[off:off + m] = vals if q else array("q", vals)
        rec.vals = self.mv[off:off + m]
        rec.idx = _full_idx(m)
        rec.txt = rec.itxt = None
        return True


class _Ring:
    __slots__ = ("lane", "recs", "views", "head", "m3a")

    def __init__(self, lane, head):
        self.lane, self.recs, self.views, self.head, self.m3a = lane, {}, {}, head, None

    def __getstate__(self):
        return (self.lane, self.recs, self.head)

    def __setstate__(self, state):
        self.lane, self.recs, self.head = state
        self.views = {}
        self.m3a = None


class HistoryView:
    """Immutable, hashable view of the K complete sessions before `as_of` (see module doc)."""
    __slots__ = ("series_id", "metric", "window_s", "as_of", "sessions", "n", "totals", "minutes", "skip", "_recs",
                 "_merged", "_zeros", "_sum", "_eod", "_digest")

    def __init__(self, series_id, metric, window_s, as_of, recs, minutes):
        self.series_id, self.metric, self.window_s, self.as_of = series_id, metric, window_s, as_of
        self.sessions = tuple([r.session_id for r in recs])
        self.totals = tuple([r.total for r in recs])
        self.minutes = minutes
        self.skip = skip = window_s // 60
        self.n = sum([m - skip for m in minutes if m > skip])
        self._recs = tuple(recs)
        self._merged = None
        self._zeros = self._sum = 0
        self._eod = None
        self._digest = None

    def _build(self):
        skip = self.skip
        pool = []
        for r, m in zip(self._recs, self.minutes):
            _sparse(r)
            idx = r.idx
            lo = bisect_left(idx, skip) if skip else 0
            hi = bisect_left(idx, m) if r.minutes > m else len(idx)
            if hi > lo:
                pool.extend(r.vals[lo:hi])
        total = sum(pool)
        pool.sort()
        self._zeros = self.n - len(pool)
        self._sum = total
        self._merged = _pack_q(pool)

    def rank(self, x):
        """(n, le, ge): counts of grid values <= x and >= x among the n counted points (exact int or Fraction x)."""
        if self._merged is None:
            self._build()
        m, z = self._merged, self._zeros
        if type(x) is not int:
            lo_x = x.numerator // x.denominator          # floor
            hi_x = -((-x.numerator) // x.denominator)    # ceil
        else:
            lo_x = hi_x = x
        le = bisect_right(m, lo_x) + (z if lo_x >= 0 else 0)
        ge = self.n - (bisect_left(m, hi_x) + (z if hi_x > 0 else 0))
        return self.n, le, ge

    def _kth(self, i):
        z = self._zeros
        return 0 if i < z else self._merged[i - z]

    def median(self):
        """Exact median of the counted values: the mean of the two middle values when n is even."""
        if self._merged is None:
            self._build()
        n = self.n
        h = n // 2
        if n % 2:
            return Fraction(self._kth(h))
        return Fraction(self._kth(h - 1) + self._kth(h), 2)

    def mean(self):
        if self._merged is None:
            self._build()
        return Fraction(self._sum, self.n)

    def eod_sorted(self):
        """Sorted tuple of the K session totals (end-of-day forms)."""
        if self._eod is None:
            self._eod = tuple(sorted(self.totals))
        return self._eod

    def digest(self):
        if self._digest is None:
            h = hashlib.sha256(("%s|%s|%d|%s" % (self.series_id, self.metric, self.window_s, self.as_of)).encode())
            for r in self._recs:
                h.update(_rec_sha(self.series_id, self.metric, self.window_s, r).encode("ascii"))
            self._digest = h.hexdigest()
        return self._digest

    def __hash__(self):
        return hash((self.series_id, self.metric, self.window_s, self.as_of, self.sessions))

    def __eq__(self, other):
        return (isinstance(other, HistoryView) and (self.series_id, self.metric, self.window_s, self.as_of, self.sessions)
                == (other.series_id, other.metric, other.window_s, other.as_of, other.sessions)
                and self.digest() == other.digest())


def _head(series_id, metric):
    return '{"series_id":%s,"metric":%s,"session_id":' % (json.dumps(series_id), json.dumps(metric))


def _body(head, window_s, rec, cache=None):
    if rec.sparse:
        body = '%s%s,"window_s":%d,"grid":[%s],"grid_idx":[%s],"total":%d,"complete":%s}' % (
            head, json.dumps(rec.session_id), window_s, _grid_text(rec, cache), _idx_text(rec, cache), rec.total,
            "true" if rec.complete else "false")
    else:
        body = '%s%s,"window_s":%d,"grid":[%s],"total":%d,"complete":%s}' % (
            head, json.dumps(rec.session_id), window_s, _grid_text(rec), rec.total, "true" if rec.complete else "false")
    if rec.conv is not None:     # M3a record delta_convention (R-160); absent on every M2 record: M2 lines unchanged
        body = '%s,"delta_convention":"%s"}' % (body[:-1], rec.conv)
    return body


def _rec_sha(series_id, metric, window_s, rec, body=None):
    """The one sha path: SHA-256 of the canonical line without its sha field, plus LF (cached on the record)."""
    if rec.sha is None:
        if body is None:
            body = _body(_head(series_id, metric), window_s, rec)
        rec.sha = hashlib.sha256((body + "\n").encode("ascii")).hexdigest()
    return rec.sha


class HistoryStore:
    def __getstate__(self):
        # an M3a ring's layout holds memoryviews of its block, and the layout is built lazily: refuse by series, not by
        # state, so a store that pickles today does not fail only after its first read
        if any(_is_m3a_series(k[0]) for k in self._rings):
            raise TypeError("a store with M3a series cannot be pickled; transfer it with binary_snapshot() / "
                            "attach_binary() (mmap) or dump() / load()")
        return self.__dict__

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __init__(self, calendar, k=20, strict_calendar=True):
        if not 1 <= k <= MAX_K:
            raise ValueError("k must be in 1..%d" % MAX_K)
        self.calendar, self.k, self.strict_calendar = calendar, k, strict_calendar
        self._rings = {}
        self._hits = self._misses = 0
        self._buf = None
        self._chash = None          # content hash carried by a binary snapshot, valid until the store changes
        self._series_k = {}         # M3a per-series k (add_series); every other series uses self.k

    # ------------------------------------------------------------------ writes
    def add_series(self, series_id, k):
        """Declare the retention k of one series id (every metric and window of that id), R-114: k in 1..252 for an M3a
        series (metric in M3A_METRICS or a skew-type `<metric>_fwd`), 1..60 (MAX_K) for any other (M2) series.
        Lowering k evicts the oldest records at once; raising it keeps what is stored. ValueError otherwise."""
        cap = MAX_SERIES_K if _is_m3a_series(series_id) else MAX_K       # TypeError for a str subclass
        if type(k) is not int:
            raise ValueError("k must be an int")
        if not 1 <= k <= cap:
            raise ValueError("k must be in 1..%d for series %r" % (cap, series_id))
        rings = [r for key, r in self._rings.items() if key[0] == series_id]
        trimmed = [(r, dict(list(r.recs.items())[len(r.recs) - k:])) for r in rings if len(r.recs) > k]  # pure
        self._series_k[series_id] = k
        for r in rings:
            r.m3a = None                              # rebuilt on the next M3a read with the new k
        for r, kept in trimmed:
            r.recs = kept
            r.views.clear()
            self._chash = None

    def k_of(self, series_id):
        """Retention of a series id: its add_series k, else the store k."""
        return self._series_k.get(series_id, self.k)

    def append(self, series_id, metric, window_s, session_id, grid, total=None, complete=True, grid_idx=None,
               lane="stock", minutes=None, delta_convention=None):
        """Append one session record: a dense `grid` list (zero-padded to the session minutes at read time), or, with
        `grid_idx`, the values at those indexes (sparse; kept as supplied). Errors (M2StructuralError), RULED order:
        lane_mismatch (the ring lane is the lane of the first append), session_not_in_calendar (strict calendar),
        record_length_mismatch (dense grid longer than the session minutes, or a sparse index outside [0, minutes)),
        non_monotone_grid (sparse indexes not strictly ascending), duplicate_session (equal to the last appended session of
        the series), out_of_order_append (earlier). The store keeps its own typed copy.
        `delta_convention` (M3a, R-160): None (no field, read as "spot") or "spot" / "forward", stored as given and
        written in the canonical line only when given; any other value is ValueError (no append code, R-160)."""
        if delta_convention is not None and (type(delta_convention) is not str or delta_convention not in CONVENTIONS):
            raise ValueError("delta_convention must be None, 'spot' or 'forward'")
        m3a = _is_m3a_series(series_id)
        if m3a:
            # M3a: the grid is read ONCE into a private list (exactly a list or tuple is accepted; everything else is a
            # TypeError after the structural checks); the check and every later use see that copy only
            g = list(grid) if type(grid) in (list, tuple) else None
            if g is not None:
                grid = g
            if grid_idx is not None:
                grid_idx = tuple(grid_idx)             # one read: length, bounds and the stored copy agree
        if grid_idx is None:
            idx = None
            minutes = len(grid)
        else:
            idx = array("H", grid_idx) if (grid_idx and min(grid_idx) >= 0 and max(grid_idx) < 65536) else tuple(grid_idx)
            if len(grid_idx) != len(grid):
                raise ValueError("grid and grid_idx differ in length")
        sparse = grid_idx is not None
        minutes = self._prepare(series_id, metric, window_s, session_id, lane, minutes, idx, sparse, None)
        if m3a:                                # exact integers only (IO contract), checked before any mutation
            if g is None:
                raise TypeError("M3a grid must be a list or tuple of exact integers")
            if not _INT_ONLY.issuperset(map(type, grid)):
                raise TypeError("M3a grid values must be exact integers")
            if total is not None and type(total) is not int:
                raise TypeError("M3a total must be an exact integer")
        if not sparse:
            if m3a and minutes and minutes <= 65536 and 0 not in grid:
                idx = _full_idx(minutes)       # no zero point: every index, one shared array (same content)
                vals = grid
            else:
                idx = array("H")
                vals = []
                i = 0
                for v in grid:
                    if v:
                        idx.append(i)
                        vals.append(v)
                    i += 1
            if total is None:
                total = sum(grid)
        else:
            vals = list(grid)
            if total is None:
                total = sum(vals)
        if vals is grid and m3a:
            # an M3a full grid goes to the ring block: convert to int64 HERE, before any mutation, so a bad element
            # raises (TypeError, as narrow does on M2) and the append changes nothing (all-or-nothing)
            try:
                vals = array("q", grid)
            except OverflowError:
                vals = narrow(grid)
        else:
            vals = narrow(vals)
        self._store(series_id, metric, window_s, _Rec(session_id, minutes, idx, vals, total, bool(complete),
                                                      None, sparse, None, delta_convention), lane)

    def append_record(self, record, complete=True, lane="stock", _memo=None):
        """Append a prebuilt sparse `GridRecord` (see flowgrid.build_session_records), same checks. The store copies
        the arrays into private typed arrays (a caller cannot mutate stored data); an index or value array shared by
        several records of one `append_many` is copied and validated once and shared. On an M3a series the total and
        every value must be exact ints (checked after the structural checks, before any mutation). Each attribute of
        the record is read once."""
        idx = _own(record.idx, _memo)
        series_id, metric, window_s = record.series_id, record.metric, record.window_s
        session_id, rec_minutes = record.session_id, record.minutes
        m3a = _is_m3a_series(series_id)                  # TypeError for a str subclass
        minutes = self._prepare(series_id, metric, window_s, session_id, lane, rec_minutes, idx, True, _memo)
        vals, total = record.vals, record.total
        if m3a:
            vals = _m3a_values(vals, _memo)
            if type(total) is not int:
                raise TypeError("M3a total must be an exact integer")
        self._store(series_id, metric, window_s,
                    _Rec(session_id, minutes, idx, _own(vals, _memo), total, bool(complete), None, True), lane)

    def append_many(self, records, complete=True, lane="stock"):
        """Append records in order, sharing validated arrays. A batch that contains an M3a series is all-or-nothing: on
        any error every ring it touched is restored (a ring the batch created is removed). A batch with no M3a series
        is the plain loop (records before a failing one stay), exactly as before M3a."""
        memo = {}
        if isinstance(records, (list, tuple)) and not any(_m3a_record(r) for r in records):
            for r in records:
                self.append_record(r, complete, lane, memo)
            return
        saved, seen_m3a = {}, False
        try:
            for r in records:
                seen_m3a = seen_m3a or _m3a_record(r)
                key = (getattr(r, "series_id", None), getattr(r, "metric", None), getattr(r, "window_s", None))
                if key not in saved:
                    try:
                        ring = self._rings.get(key)
                    except TypeError:
                        ring = None
                    saved[key] = None if ring is None else (ring, dict(ring.recs))
                self.append_record(r, complete, lane, memo)
        except BaseException:
            if seen_m3a:
                for key, got in saved.items():
                    if got is None:
                        self._rings.pop(key, None)
                    else:
                        ring, recs = got
                        ring.recs = recs
                        ring.views.clear()
                        ring.m3a = None               # rebuilt from ring.recs on the next M3a read
                        self._rings[key] = ring
                self._chash = None
            raise

    def _prepare(self, series_id, metric, window_s, session_id, lane, minutes, idx, sparse, memo):
        """The append checks in the RULED order; returns the grid length (`minutes`) to store."""
        ring = self._rings.get((series_id, metric, window_s))
        if ring is not None and ring.lane != lane:
            raise M2StructuralError("lane_mismatch")
        cal = self.calendar
        pos = cal.position(session_id)
        if pos is None and self.strict_calendar:
            raise M2StructuralError("session_not_in_calendar")
        cal_minutes = None if pos is None else cal.minutes[pos]
        asc = True
        if sparse:
            if idx is None or not len(idx):
                lo = hi = None
            else:
                got = memo.get(("v", id(idx))) if memo is not None else None
                if got is None:
                    lst = idx.tolist() if isinstance(idx, array) else list(idx)
                    got = (min(lst), max(lst), all(a < b for a, b in zip(lst, lst[1:])))
                    if memo is not None:
                        memo[("v", id(idx))] = got
                lo, hi, asc = got
            if lo is not None and (lo < 0 or (cal_minutes is not None and hi >= cal_minutes)):
                raise M2StructuralError("record_length_mismatch")
            if not asc:
                raise M2StructuralError("non_monotone_grid")
            minutes = cal_minutes if cal_minutes is not None else (0 if hi is None else hi + 1)
        elif cal_minutes is not None and minutes > cal_minutes:
            raise M2StructuralError("record_length_mismatch")
        if ring is not None and ring.recs:
            last = next(reversed(ring.recs))
            if session_id == last:
                raise M2StructuralError("duplicate_session")
            if session_id < last:
                raise M2StructuralError("out_of_order_append")
        return minutes

    def _store(self, series_id, metric, window_s, rec, lane):
        """Insert a record. All-or-nothing: on any failure the ring holds exactly its previous records, the layout is
        dropped (rebuilt lazily from the records), and a ring created by this call is not left behind."""
        key = (series_id, metric, window_s)
        sid = rec.session_id
        hash(sid)                                       # fail before any state is touched
        ring = self._rings.get(key)
        new = ring is None
        if new:
            ring = _Ring(lane, _head(series_id, metric))
            if _is_m3a_series(series_id):
                ring.m3a = self._new_cols(series_id)
        recs = ring.recs
        evicted = None
        try:
            recs[sid] = rec
            if len(recs) > self._series_k.get(series_id, self.k):
                first = next(iter(recs))
                evicted = (first, recs.pop(first))
            if ring.m3a is not None:
                ring.m3a.push(rec)
        except BaseException:
            recs.pop(sid, None)
            if evicted is not None:
                ring.recs = {evicted[0]: evicted[1], **recs}
            ring.m3a = None                             # never half-updated: rebuilt from ring.recs on the next read
            ring.views.clear()
            self._chash = None
            raise
        self._chash = None
        if new:
            self._rings[key] = ring
        elif ring.views:
            ring.views.clear()

    def _new_cols(self, series_id):
        mins = self.calendar.minutes
        return _Cols(self._series_k.get(series_id, self.k), max(mins) if mins else 0)

    def m3a_cols(self, series_id, metric, window_s):
        """The M3a layout of a ring (built once on the first read of a loaded ring, then kept in step), or None."""
        ring = self._rings.get((series_id, metric, window_s))
        if ring is None:
            return None
        if ring.m3a is None:
            cols = self._new_cols(series_id)
            for rec in ring.recs.values():
                cols.push(rec)
            ring.m3a = cols
        return ring.m3a

    def build_m3a_layout(self):
        """Build the M3a layout of every M3a ring now (after a load or attach, before timed reads)."""
        for (s, m, w) in list(self._rings):
            if _is_m3a_series(s):
                self.m3a_cols(s, m, w)

    def seal(self, series_id, metric, window_s, session_id):
        """Mark a stored record complete (and immutable). False when there is no such record."""
        ring = self._rings.get((series_id, metric, window_s))
        rec = None if ring is None else ring.recs.get(session_id)
        if rec is None:
            return False
        if not rec.complete:
            try:
                if ring.m3a is not None:
                    ring.m3a.seal(session_id)
                rec.complete = True
                rec.sha = None
            except BaseException:
                rec.complete = False
                ring.m3a = None                       # rebuilt from ring.recs on the next read
                raise
            self._chash = None
            ring.views.clear()
        return True

    # ------------------------------------------------------------------ reads
    def complete_sessions_before(self, series_id, metric, window_s, as_of, k=None):
        """Last k complete stored sessions strictly before as_of (no look-ahead), ascending."""
        ring = self._rings.get((series_id, metric, window_s))
        if ring is None:
            return ()
        got = [s for s, r in ring.recs.items() if r.complete and s < as_of]
        return tuple(got[-(k or self.k):]) if got else ()

    def baseline(self, series_id, metric, window_s, as_of, k=None, lane="stock"):
        """HistoryView of the K calendar sessions right before `as_of`, or None (insufficient_history)."""
        ring = self._rings.get((series_id, metric, window_s))
        if ring is None or ring.lane != lane:
            return None
        k = k or self.k
        key = (as_of, k)
        view = ring.views.get(key)
        if view is not None:
            self._hits += 1
            return view
        self._misses += 1
        cal = self.calendar
        pos = cal.position(as_of)
        if pos is None or pos < k:
            return None
        recs = ring.recs
        got = []
        for sid in cal.ids[pos - k:pos]:
            r = recs.get(sid)
            if r is None or not r.complete:
                return None
            got.append(r)
        view = HistoryView(series_id, metric, window_s, as_of, got, cal.minutes[pos - k:pos])
        if len(ring.views) >= _VIEW_CACHE:
            del ring.views[next(iter(ring.views))]
        ring.views[key] = view
        return view

    def has(self, series_id, metric, window_s):
        return (series_id, metric, window_s) in self._rings

    # ------------------------------------------------------------------ canonical text
    def retained(self):
        out = {}
        for (s, m, w), ring in self._rings.items():
            out["%s|%s|%d" % (s, m, w)] = list(ring.recs)
        return {k: out[k] for k in sorted(out)}

    def _records(self):
        for key in sorted(self._rings):
            ring = self._rings[key]
            for sid in sorted(ring.recs):
                yield key, ring, ring.recs[sid]

    def record_hashes(self):
        return [_rec_sha(s, m, w, r) for (s, m, w), _, r in self._records()]

    def lines(self):
        cache = {}
        for (s, m, w), ring, r in self._records():
            body = _body(ring.head, w, r, cache)
            yield body[:-1] + ',"content_sha256":"' + _rec_sha(s, m, w, r, body) + '"}'

    def content_hash(self):
        """SHA-256 over the per-record content_sha256 values (lowercase hex) joined by LF in canonical order: the
        fixtures' `content_sha256_digest`, the value in the dump trailer. A store attached from a binary snapshot returns
        the (SHA-256 verified) value the snapshot carries until it changes; `recompute_content_hash()` ignores it."""
        if self._chash is not None:
            return self._chash
        return self.recompute_content_hash()

    def recompute_content_hash(self):
        return hashlib.sha256("\n".join(self.record_hashes()).encode("ascii")).hexdigest()

    @_nogc
    def dump(self, trailer=True):
        """Canonical text as bytes: one line per record, LF, then (default) the trailer line
        `#END records=N content_sha256=<content_hash()>`."""
        data = "".join([ln + "\n" for ln in self.lines()]).encode("ascii")
        if not trailer:
            return data
        return data + ("#END records=%d content_sha256=%s\n" % (data.count(b"\n"), self.content_hash())).encode("ascii")

    def dump_sha256(self):
        """SHA-256 of the dump text without its trailer line (every LF included)."""
        return hashlib.sha256(self.dump(False)).hexdigest()

    def dump_to(self, path):
        """Atomic file write (temporary file in the same directory, flush, os.replace) of `dump()`."""
        _atomic_write(os.fspath(path), self.dump())

    @classmethod
    @_nogc
    def load(cls, source, calendar, k=20, strict_calendar=True, verify=True, lane="stock", series_k=None):
        """Store from canonical text: `os.PathLike` is a path; `str`, `bytes`, `bytearray`, `memoryview` are the content
        itself; empty content gives an empty store; other types raise TypeError. Non-empty content must end with the
        trailer line: after the lines parse, `trailer_missing`, `trailer_count_mismatch` (N differs from the record
        count) or `trailer_hash_mismatch` (hex differs from the content hash of the loaded records) are raised as
        M2StructuralError; a malformed line or a wrong per-line content_sha256 raises ValueError. `lane` is a string or a
        series_id -> lane mapping that sets the lane of every loaded ring (default "stock"). `series_k` (M3a): a
        series_id -> k mapping applied with add_series before the lines are read (the text carries no k)."""
        if isinstance(source, os.PathLike):
            with open(source, "rb") as fh:
                source = fh.read()
        if isinstance(source, (bytes, bytearray, memoryview)):
            raw = bytes(source)
        elif isinstance(source, str):
            raw = source.encode("ascii")
        else:
            raise TypeError("load needs a path or canonical content")
        store = cls(calendar, k, strict_calendar)
        store._declare(series_k)
        if not raw:
            return store
        rows = raw.decode("ascii").split("\n")
        if rows[-1] == "":
            rows.pop()
        trailer = None
        if rows and rows[-1][:1] == "#":
            last = rows.pop()                       # a trailing "#..." line that is not "#END ..." is no trailer
            trailer = last if last[:5] == "#END " else None
        shas = store._parse_rows(rows, lane, verify)
        if trailer is None:
            raise M2StructuralError("trailer_missing")
        m = _TRAILER.match(trailer)
        if m is None:
            raise ValueError("bad trailer line")
        if int(m.group(1)) != len(rows):
            raise M2StructuralError("trailer_count_mismatch")
        if m.group(2) != hashlib.sha256("\n".join(shas).encode("ascii")).hexdigest():
            raise M2StructuralError("trailer_hash_mismatch")
        return store

    def _declare(self, series_k):
        if series_k:
            for sid in sorted(series_k):
                self.add_series(sid, series_k[sid])

    def _parse_rows(self, rows, lane, verify):
        """Parse canonical record lines into this (empty) store; returns the claimed per-record sha list in order."""
        match = _LINE.match
        calendar = self.calendar
        strict = self.strict_calendar
        prev_key = None
        kget, dk, kk = self._series_k.get, self.k, 0
        shas = []
        lane_of = (lambda s: lane.get(s, "stock")) if isinstance(lane, dict) else (lambda s: lane)
        for ln in rows:
            m = match(ln)
            if m is None:
                raise ValueError("not a canonical history line")
            g1 = ln.find('],"total":', m.end())
            if g1 < 0:
                raise ValueError("not a canonical history line")
            g0 = ln.find('],"grid_idx":[', m.end(), g1)
            tail = ln[g1 + 10:].split(",")
            conv = None
            if len(tail) == 4 and tail[2][:19] == '"delta_convention":':     # M3a record field (R-160)
                conv = tail.pop(2)[20:-1]
                if conv not in CONVENTIONS:
                    raise ValueError("not a canonical history line")
            if len(tail) != 3 or tail[1][:11] != '"complete":' or tail[2][:17] != '"content_sha256":' or tail[2][-2:] != '"}':
                raise ValueError("not a canonical history line")
            claimed = tail[2][18:-2]
            series_id, metric, sid, window_s = m.groups()
            series_id = json.loads(series_id) if "\\" in series_id else series_id[1:-1]
            metric = json.loads(metric) if "\\" in metric else metric[1:-1]
            sid = json.loads(sid) if "\\" in sid else sid[1:-1]
            window_s = int(window_s)
            if verify:
                body = ln[:ln.rindex(',"content_sha256"')] + "}\n"
                if hashlib.sha256(body.encode("ascii")).hexdigest() != claimed:
                    raise ValueError("content_sha256 mismatch")
            key = (series_id, metric, window_s)
            pos = calendar.position(sid)
            if pos is None and strict:
                raise M2StructuralError("session_not_in_calendar")
            ring = self._rings.get(key)
            if ring is None:
                if prev_key is not None and key < prev_key:
                    raise ValueError("lines are not in canonical order")
                ring = self._rings[key] = _Ring(lane_of(series_id), _head(series_id, metric))
            elif next(reversed(ring.recs)) >= sid:
                raise M2StructuralError("duplicate_session" if next(reversed(ring.recs)) == sid else "out_of_order_append")
            if key != prev_key:
                kk = kget(series_id, dk)
            prev_key = key
            if g0 >= 0:
                txt, itxt = ln[m.end():g0], ln[g0 + 14:g1]
                minutes = calendar.minutes[pos] if pos is not None else 0
                rec = _Rec(sid, minutes, None, None, int(tail[0]), tail[1][11:] == "true", txt, True, itxt, conv)
            else:
                txt = ln[m.end():g1]
                rec = _Rec(sid, (txt.count(",") + 1) if txt else 0, None, None, int(tail[0]), tail[1][11:] == "true", txt,
                           False, None, conv)
                if pos is not None and rec.minutes > calendar.minutes[pos]:
                    raise M2StructuralError("record_length_mismatch")
            rec.sha = claimed
            ring.recs[sid] = rec
            if len(ring.recs) > kk:
                del ring.recs[next(iter(ring.recs))]
            shas.append(claimed)
        return shas

    # ------------------------------------------------------------------ snapshot (RULED format) and binary transfer
    def snapshot(self):
        """RULED snapshot: magic "M2SNAP1" (7 bytes) + total length (8-byte little-endian: bytes of the whole snapshot) +
        SHA-256 of the body (32 bytes) + body, the body being the canonical record lines (the dump text without its
        trailer). The runner must compare `content_hash()` after attaching a store."""
        body = self.dump(False)
        return b"".join([_SNAP_MAGIC, (len(_SNAP_MAGIC) + 8 + 32 + len(body)).to_bytes(8, "little"),
                         hashlib.sha256(body).digest(), body])

    def snapshot_to(self, path):
        _atomic_write(os.fspath(path), self.snapshot())

    @classmethod
    @_nogc
    def from_snapshot(cls, buffer, calendar, k=20, strict_calendar=True, lane="stock", verify=True, series_k=None):
        """Store from a `snapshot()` buffer (bytes, mmap, shared memory, memoryview). Structural errors with closed codes,
        in this order: `snapshot_bad_magic`, `snapshot_length_mismatch` (including truncation), `snapshot_hash_mismatch`.
        The lines are then parsed as in `load` (per-line hashes verified; grids parsed on first use)."""
        mv = memoryview(buffer)
        head = len(_SNAP_MAGIC)
        if bytes(mv[:head]) != _SNAP_MAGIC:
            raise M2StructuralError("snapshot_bad_magic")
        if len(mv) < head + 40 or int.from_bytes(mv[head:head + 8], "little") != len(mv):
            raise M2StructuralError("snapshot_length_mismatch")
        body = bytes(mv[head + 40:])
        if hashlib.sha256(body).digest() != bytes(mv[head + 8:head + 40]):
            raise M2StructuralError("snapshot_hash_mismatch")
        store = cls(calendar, k, strict_calendar)
        store._declare(series_k)
        if body:
            rows = body.decode("ascii").split("\n")
            if rows[-1] == "":
                rows.pop()
            store._parse_rows(rows, lane, verify)
        return store

    def binary_snapshot(self):
        """Optional zero-copy transfer form (not the ruled snapshot): magic, total length, SHA-256 of the rest, the record
        table, then the raw typed arrays (8-byte aligned). `from_binary_snapshot` over bytes, an `mmap` or shared memory
        builds a store whose records are read-only views of that buffer (view transfer option of M2-B16). Little-endian
        hosts only (`snapshot_byteorder` otherwise)."""
        if sys.byteorder != "little":
            raise M2StructuralError("snapshot_byteorder")
        table, blobs, off, conv = [], [], 0, []
        for key in sorted(self._rings):
            ring = self._rings[key]
            recs = []
            for sid in sorted(ring.recs):
                r = _sparse(ring.recs[sid])
                n = len(r.idx)
                head = [sid, r.minutes, r.total, 1 if r.complete else 0, n, off, "H", 1 if r.sparse else 0]
                if r.conv is not None:
                    conv.append([key[0], key[1], key[2], sid, r.conv])
                ib = array("H", r.idx).tobytes()
                if isinstance(r.vals, tuple):
                    head.append([int(v) for v in r.vals])
                    vb = b""
                else:
                    head[6] = r.vals.typecode if isinstance(r.vals, array) else r.vals.format
                    vb = r.vals.tobytes()
                blob = ib + bytes((-len(ib)) % 8) + vb + bytes((-len(vb)) % 8)
                blobs.append(blob)
                off += len(blob)
                recs.append(head)
            table.append([key[0], key[1], key[2], ring.lane, recs])
        meta = {"k": self.k, "content_hash": self.content_hash(), "series": table}
        if self._series_k:                 # M3a keys only when used: an M2 store keeps its exact snapshot bytes
            meta["series_k"] = {s: self._series_k[s] for s in sorted(self._series_k)}
        if conv:
            meta["conv"] = conv
        meta = json.dumps(meta, separators=(",", ":")).encode("ascii")
        start = len(_BIN_MAGIC) + 8 + 32 + 8
        pad = (-(start + len(meta))) % 8
        rest = b"".join([len(meta).to_bytes(8, "little"), meta, b" " * pad] + blobs)
        total = len(_BIN_MAGIC) + 8 + 32 + len(rest)
        return b"".join([_BIN_MAGIC, total.to_bytes(8, "little"), hashlib.sha256(rest).digest(), rest])

    @classmethod
    def from_binary_snapshot(cls, buffer, calendar, k=None, strict_calendar=True, lane=None, verify=True):
        """Store over a `binary_snapshot()` buffer; nothing is copied, the store keeps a reference to the buffer.
        Layout (little-endian): bytes 0-4 name "M2BIN", 5-6 format version (1), 7-14 total length of the buffer, 15-46
        SHA-256 of every byte after offset 47, 47-54 length N of the record table, then the table (compact JSON: k and,
        per series, [series_id, metric, window_s, lane, [[session_id, minutes, total, complete, count, offset, typecode,
        sparse(, big values)]]]), padding to 8 bytes, then the blobs: per record the `count` indexes (uint16) padded to 8
        bytes, then the values (`typecode`, padded to 8). Offsets are relative to the first blob byte. Raises the closed
        snapshot codes: snapshot_bad_magic (name or version), snapshot_length_mismatch, snapshot_hash_mismatch.
        `lane`: None keeps the stored lanes. A failed attach releases its view of the buffer."""
        mv = memoryview(buffer).toreadonly()
        try:
            return cls._from_binary_view(mv, buffer, calendar, k, strict_calendar, lane, verify)
        except BaseException:
            try:
                mv.release()
            except BufferError:
                pass
            raise

    @classmethod
    @_nogc
    def _from_binary_view(cls, mv, buffer, calendar, k, strict_calendar, lane, verify):
        head = len(_BIN_MAGIC)
        if sys.byteorder != "little":                # the arrays are stored little-endian and mapped in place
            raise M2StructuralError("snapshot_byteorder")
        if len(mv) < _BIN_HEADER:                    # shorter than the header (including an empty buffer)
            raise M2StructuralError("snapshot_length_mismatch")
        if bytes(mv[:head]) != _BIN_MAGIC:           # wrong name or unsupported version
            raise M2StructuralError("snapshot_bad_magic")
        if len(mv) < head + 48 or int.from_bytes(mv[head:head + 8], "little") != len(mv):
            raise M2StructuralError("snapshot_length_mismatch")
        if verify and hashlib.sha256(mv[head + 40:]).digest() != bytes(mv[head + 8:head + 40]):
            raise M2StructuralError("snapshot_hash_mismatch")
        start = head + 40
        n = int.from_bytes(mv[start:start + 8], "little")
        start += 8
        meta = json.loads(bytes(mv[start:start + n]))
        base = start + n + ((-(start + n)) % 8)
        store = cls(calendar, k or meta["k"], strict_calendar)
        store._buf = buffer
        store._declare(meta.get("series_k"))
        store._chash = meta.get("content_hash")
        for series_id, metric, window_s, stored_lane, recs in meta["series"]:
            if lane is None:
                ln = stored_lane
            else:
                ln = lane.get(series_id, "stock") if isinstance(lane, dict) else lane
            ring = store._rings[(series_id, metric, window_s)] = _Ring(ln, _head(series_id, metric))
            out = ring.recs
            for row in recs:
                sid, minutes, total, complete, cnt, off, tc, sparse = row[:8]
                if strict_calendar and sid not in calendar:
                    raise M2StructuralError("session_not_in_calendar")
                a = base + off
                ib = (cnt * 2 + 7) // 8 * 8
                idx = mv[a:a + cnt * 2].cast("H")
                vals = tuple(row[8]) if len(row) > 8 else mv[a + ib:a + ib + cnt * _SIZE[tc]].cast(tc)
                out[sid] = _Rec(sid, minutes, idx, vals, total, bool(complete), None, bool(sparse))
        for series_id, metric, window_s, sid, cv in meta.get("conv", ()):
            store._rings[(series_id, metric, window_s)].recs[sid].conv = cv
        return store

    def binary_snapshot_to(self, path):
        _atomic_write(os.fspath(path), self.binary_snapshot())

    @classmethod
    def attach_binary(cls, path, calendar, expected_content_hash=None, k=None, strict_calendar=True, lane=None, deep=False):
        """Worker start: map the binary snapshot file read-only (shared file-backed pages), verify magic, version, length and
        SHA-256, build the zero-copy store, and when `expected_content_hash` is given compare `content_hash()` after the
        attach (mismatch: `snapshot_hash_mismatch`); `deep=True` recomputes the hash from the records instead of reading
        the value the verified snapshot carries (as slow as a dump). Without `deep`, the comparison covers the table hash
        only: the SHA-256 over the file guards against accidental corruption, not against a forged file with a matching
        table (accidental-corruption model). The store keeps the mapping alive; `close_mapping()` releases it. Runner rule:
        write every generation of a snapshot to a NEW file name (Windows cannot replace a file that is mapped)."""
        import mmap
        if os.path.getsize(os.fspath(path)) < _BIN_HEADER:        # an empty file cannot be mapped; report it structurally
            raise M2StructuralError("snapshot_length_mismatch")
        fh = open(os.fspath(path), "rb")
        try:
            mapped = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
        finally:
            fh.close()
        try:
            store = cls.from_binary_snapshot(mapped, calendar, k, strict_calendar, lane)
            if expected_content_hash is not None and (store.recompute_content_hash() if deep else store.content_hash()) != expected_content_hash:
                raise M2StructuralError("snapshot_hash_mismatch")
        except BaseException:
            store = None
            try:
                mapped.close()
            except BufferError:
                pass
            raise
        return store

    def close_mapping(self):
        """Drop every record (they are views of the mapping), then close the mapping of an attached store."""
        buf, self._buf, self._rings = self._buf, None, {}
        if buf is not None and hasattr(buf, "close"):
            buf.close()

    def drop_caches(self):
        """Forget every cached view (memory control; never changes a result)."""
        for ring in self._rings.values():
            ring.views.clear()

    # ------------------------------------------------------------------ log-only facts
    def stats(self):
        """Counts and a measured size estimate (sys.getsizeof of the record, its arrays and text; shared arrays counted
        once). `series` counts distinct series ids, `rings` the (series, metric, window) record sets."""
        seen = set()
        recs = nbytes = 0
        for ring in self._rings.values():
            if ring.m3a is not None and ring.m3a.block is not None:
                nbytes += sys.getsizeof(ring.m3a.block)
            for r in ring.recs.values():
                recs += 1
                nbytes += sys.getsizeof(r)
                for part in (r.idx, r.vals, r.txt, r.itxt):
                    if part is not None and id(part) not in seen:
                        seen.add(id(part))
                        nbytes += sys.getsizeof(part)
        return {"series": len({k[0] for k in self._rings}), "rings": len(self._rings), "records": recs,
                "est_bytes": nbytes, "view_hits": self._hits, "view_misses": self._misses}

    def __len__(self):
        return len(self._rings)
