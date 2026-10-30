"""M2 history store: array-backed per-series grid history, retention ring, immutable cached views, canonical text.

Pure and single-threaded; exact integers only (`Fraction` appears in view statistics at the output boundary).

Key = (series_id, metric, window_s); one ring per key, append-only in session order, retention `k` (default 20, hard
cap 60) counting every stored record, complete or not. A record is a sparse grid (ascending `array('H')` indexes of
the nonzero points, `array('q')` values, or a plain list when a value exceeds 64 bits), the session total, a
complete flag; zeros are implicit. Series are created lazily by the first append, so a contract without prints costs
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
from array import array
from bisect import bisect_left, bisect_right
from fractions import Fraction
import hashlib
import json
import os
import re
import sys

from .flowgrid import _pack_q, narrow
from .flowresult import M2StructuralError

MAX_K = 60
_SNAP_MAGIC = b"M2SNAP1"
_BIN_NAME = b"M2BIN"
_BIN_VERSION = (1).to_bytes(2, "little")
_BIN_MAGIC = _BIN_NAME + _BIN_VERSION          # 7 bytes: name and little-endian version
_TRAILER = re.compile(r"#END records=(\d+) content_sha256=([0-9a-f]{64})\Z")
_VIEW_CACHE = 4
_SIZE = {"B": 1, "H": 2, "I": 4, "L": 4, "Q": 8, "q": 8}

_LINE = re.compile(r'\{"series_id":(".*?"),"metric":(".*?"),"session_id":(".*?"),"window_s":(\d+),"grid":\[')


class _Rec:
    __slots__ = ("session_id", "minutes", "idx", "vals", "total", "complete", "sha", "txt", "sparse", "itxt")

    def __init__(self, session_id, minutes, idx, vals, total, complete, txt=None, sparse=False, itxt=None):
        self.session_id, self.minutes, self.idx, self.vals = session_id, minutes, idx, vals
        self.total, self.complete, self.sha, self.txt = total, complete, None, txt
        self.sparse, self.itxt = sparse, itxt


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


class _Ring:
    __slots__ = ("lane", "recs", "views", "head")

    def __init__(self, lane, head):
        self.lane, self.recs, self.views, self.head = lane, {}, {}, head

    def __getstate__(self):
        return (self.lane, self.recs, self.head)

    def __setstate__(self, state):
        self.lane, self.recs, self.head = state
        self.views = {}


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
        return '%s%s,"window_s":%d,"grid":[%s],"grid_idx":[%s],"total":%d,"complete":%s}' % (
            head, json.dumps(rec.session_id), window_s, _grid_text(rec, cache), _idx_text(rec, cache), rec.total,
            "true" if rec.complete else "false")
    return '%s%s,"window_s":%d,"grid":[%s],"total":%d,"complete":%s}' % (
        head, json.dumps(rec.session_id), window_s, _grid_text(rec), rec.total, "true" if rec.complete else "false")


def _rec_sha(series_id, metric, window_s, rec, body=None):
    """The one sha path: SHA-256 of the canonical line without its sha field, plus LF (cached on the record)."""
    if rec.sha is None:
        if body is None:
            body = _body(_head(series_id, metric), window_s, rec)
        rec.sha = hashlib.sha256((body + "\n").encode("ascii")).hexdigest()
    return rec.sha


class HistoryStore:
    def __init__(self, calendar, k=20, strict_calendar=True):
        if not 1 <= k <= MAX_K:
            raise ValueError("k must be in 1..%d" % MAX_K)
        self.calendar, self.k, self.strict_calendar = calendar, k, strict_calendar
        self._rings = {}
        self._hits = self._misses = 0
        self._buf = None
        self._chash = None          # content hash carried by a binary snapshot, valid until the store changes

    # ------------------------------------------------------------------ writes
    def append(self, series_id, metric, window_s, session_id, grid, total=None, complete=True, grid_idx=None,
               lane="stock", minutes=None):
        """Append one session record: a dense `grid` list (zero-padded to the session minutes at read time), or, with
        `grid_idx`, the values at those indexes (sparse; kept as supplied). Errors (M2StructuralError), RULED order:
        lane_mismatch (the ring lane is the lane of the first append), session_not_in_calendar (strict calendar),
        record_length_mismatch (dense grid longer than the session minutes, or a sparse index outside [0, minutes)),
        non_monotone_grid (sparse indexes not strictly ascending), duplicate_session (equal to the last appended session of
        the series), out_of_order_append (earlier). The store keeps its own typed copy."""
        if grid_idx is None:
            idx = None
            minutes = len(grid)
        else:
            idx = array("H", grid_idx) if (grid_idx and min(grid_idx) >= 0 and max(grid_idx) < 65536) else tuple(grid_idx)
            if len(grid_idx) != len(grid):
                raise ValueError("grid and grid_idx differ in length")
        sparse = grid_idx is not None
        minutes = self._prepare(series_id, metric, window_s, session_id, lane, minutes, idx, sparse, None)
        if not sparse:
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
        self._store(series_id, metric, window_s, _Rec(session_id, minutes, idx, narrow(vals), total, bool(complete),
                                                      None, sparse), lane)

    def append_record(self, record, complete=True, lane="stock", _memo=None):
        """Append a prebuilt sparse `GridRecord` (see flowgrid.build_session_records), same checks. The store copies
        the arrays into private typed arrays (a caller cannot mutate stored data); an index or value array shared by
        several records of one `append_many` is copied and validated once and shared."""
        idx = _own(record.idx, _memo)
        minutes = self._prepare(record.series_id, record.metric, record.window_s, record.session_id, lane, record.minutes,
                                idx, True, _memo)
        self._store(record.series_id, record.metric, record.window_s,
                    _Rec(record.session_id, minutes, idx, _own(record.vals, _memo), record.total, bool(complete),
                         None, True), lane)

    def append_many(self, records, complete=True, lane="stock"):
        memo = {}
        for r in records:
            self.append_record(r, complete, lane, memo)

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
        self._chash = None
        key = (series_id, metric, window_s)
        ring = self._rings.get(key)
        if ring is None:
            ring = self._rings[key] = _Ring(lane, _head(series_id, metric))
        recs = ring.recs
        recs[rec.session_id] = rec
        if ring.views:
            ring.views.clear()
        if len(recs) > self.k:
            del recs[next(iter(recs))]

    def seal(self, series_id, metric, window_s, session_id):
        """Mark a stored record complete (and immutable). False when there is no such record."""
        ring = self._rings.get((series_id, metric, window_s))
        rec = None if ring is None else ring.recs.get(session_id)
        if rec is None:
            return False
        if not rec.complete:
            rec.complete = True
            rec.sha = None
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
    def load(cls, source, calendar, k=20, strict_calendar=True, verify=True, lane="stock"):
        """Store from canonical text: `os.PathLike` is a path; `str`, `bytes`, `bytearray`, `memoryview` are the content
        itself; empty content gives an empty store; other types raise TypeError. Non-empty content must end with the
        trailer line: after the lines parse, `trailer_missing`, `trailer_count_mismatch` (N differs from the record
        count) or `trailer_hash_mismatch` (hex differs from the content hash of the loaded records) are raised as
        M2StructuralError; a malformed line or a wrong per-line content_sha256 raises ValueError. `lane` is a string or a
        series_id -> lane mapping that sets the lane of every loaded ring (default "stock")."""
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

    def _parse_rows(self, rows, lane, verify):
        """Parse canonical record lines into this (empty) store; returns the claimed per-record sha list in order."""
        match = _LINE.match
        calendar = self.calendar
        strict = self.strict_calendar
        prev_key = None
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
            prev_key = key
            if g0 >= 0:
                txt, itxt = ln[m.end():g0], ln[g0 + 14:g1]
                minutes = calendar.minutes[pos] if pos is not None else 0
                rec = _Rec(sid, minutes, None, None, int(tail[0]), tail[1][11:] == "true", txt, True, itxt)
            else:
                txt = ln[m.end():g1]
                rec = _Rec(sid, (txt.count(",") + 1) if txt else 0, None, None, int(tail[0]), tail[1][11:] == "true", txt)
                if pos is not None and rec.minutes > calendar.minutes[pos]:
                    raise M2StructuralError("record_length_mismatch")
            rec.sha = claimed
            ring.recs[sid] = rec
            if len(ring.recs) > self.k:
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
    def from_snapshot(cls, buffer, calendar, k=20, strict_calendar=True, lane="stock", verify=True):
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
        if body:
            rows = body.decode("ascii").split("\n")
            if rows[-1] == "":
                rows.pop()
            store._parse_rows(rows, lane, verify)
        return store

    def binary_snapshot(self):
        """Optional zero-copy transfer form (not the ruled snapshot): magic, total length, SHA-256 of the rest, the record
        table, then the raw typed arrays (8-byte aligned). `from_binary_snapshot` over bytes, an `mmap` or shared memory
        builds a store whose records are read-only views of that buffer (view transfer option of M2-B16)."""
        table, blobs, off = [], [], 0
        for key in sorted(self._rings):
            ring = self._rings[key]
            recs = []
            for sid in sorted(ring.recs):
                r = _sparse(ring.recs[sid])
                n = len(r.idx)
                head = [sid, r.minutes, r.total, 1 if r.complete else 0, n, off, "H", 1 if r.sparse else 0]
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
        meta = json.dumps({"k": self.k, "content_hash": self.content_hash(), "series": table},
                          separators=(",", ":")).encode("ascii")
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
    def _from_binary_view(cls, mv, buffer, calendar, k, strict_calendar, lane, verify):
        head = len(_BIN_MAGIC)
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
        return store

    def binary_snapshot_to(self, path):
        _atomic_write(os.fspath(path), self.binary_snapshot())

    @classmethod
    def attach_binary(cls, path, calendar, expected_content_hash=None, k=None, strict_calendar=True, lane=None, deep=False):
        """Worker start: map the binary snapshot file read-only (shared file-backed pages), verify magic, version, length and
        SHA-256, build the zero-copy store, and when `expected_content_hash` is given compare `content_hash()` after the
        attach (mismatch: `snapshot_hash_mismatch`); `deep=True` recomputes the hash from the records instead of reading
        the value the verified snapshot carries (as slow as a dump). The store keeps the mapping alive; `close_mapping()` releases it."""
        import mmap
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
