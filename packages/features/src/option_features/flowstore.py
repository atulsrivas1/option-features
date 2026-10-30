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

from .flowgrid import GridRecord, _pack_q
from .flowresult import M2StructuralError

MAX_K = 60
_SNAP_MAGIC = b"M2HISTSNAP1\n"
_VIEW_CACHE = 4

_LINE = re.compile(r'\{"series_id":(".*?"),"metric":(".*?"),"session_id":(".*?"),"window_s":(\d+),"grid":\[')


class _Rec:
    __slots__ = ("session_id", "minutes", "idx", "vals", "total", "complete", "sha", "txt")

    def __init__(self, session_id, minutes, idx, vals, total, complete, txt=None):
        self.session_id, self.minutes, self.idx, self.vals = session_id, minutes, idx, vals
        self.total, self.complete, self.sha, self.txt = total, complete, None, txt


def _sparse(rec):
    """Materialise a lazily loaded record (parse its grid text once)."""
    if rec.idx is None:
        idx, vals = array("H"), []
        txt = rec.txt
        if txt:
            i = 0
            for tok in txt.split(","):
                if tok != "0":
                    idx.append(i)
                    vals.append(int(tok))
                i += 1
        rec.idx, rec.vals, rec.txt = idx, _pack_q(vals), None
    return rec


def _grid_text(rec):
    _sparse(rec)
    tokens = ["0"] * rec.minutes
    idx, vals = rec.idx, rec.vals
    for i, v in zip(idx.tolist() if type(idx) is array else idx, vals.tolist() if type(vals) is array else vals):
        tokens[i] = str(v)
    return ",".join(tokens)


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


def _body(head, window_s, rec):
    return '%s%s,"window_s":%d,"grid":[%s],"total":%d,"complete":%s}' % (
        head, json.dumps(rec.session_id), window_s, _grid_text(rec), rec.total, "true" if rec.complete else "false")


def _rec_sha(series_id, metric, window_s, rec):
    if rec.sha is None:
        rec.sha = hashlib.sha256((_body(_head(series_id, metric), window_s, rec) + "\n").encode("ascii")).hexdigest()
    return rec.sha


class HistoryStore:
    def __init__(self, calendar, k=20, strict_calendar=True):
        if not 1 <= k <= MAX_K:
            raise ValueError("k must be in 1..%d" % MAX_K)
        self.calendar, self.k, self.strict_calendar = calendar, k, strict_calendar
        self._rings = {}
        self._hits = self._misses = 0
        self._buf = None

    # ------------------------------------------------------------------ writes
    def append(self, series_id, metric, window_s, session_id, grid, total=None, complete=True, grid_idx=None,
               lane="stock", minutes=None):
        """Append one session record. Dense `grid` list, or the nonzero values at `grid_idx` (strictly ascending,
        inside the grid). Errors: session_not_in_calendar (strict), duplicate_session, out_of_order_append,
        non_monotone_grid, checked in that order."""
        self._check_slot(series_id, metric, window_s, session_id, lane)
        if grid_idx is None:
            idx = array("H")
            vals = []
            i = 0
            for v in grid:
                if v:
                    idx.append(i)
                    vals.append(v)
                i += 1
            minutes = i
            if total is None:
                total = sum(grid)
        else:
            if minutes is None:
                pos = self.calendar.position(session_id)
                minutes = self.calendar.minutes[pos] if pos is not None else (grid_idx[-1] + 1 if grid_idx else 0)
            prev = -1
            for g in grid_idx:
                if g <= prev or g >= minutes:
                    raise M2StructuralError("non_monotone_grid")
                prev = g
            idx, vals = array("H", grid_idx), list(grid)
            if total is None:
                total = sum(vals)
        self._store(series_id, metric, window_s, _Rec(session_id, minutes, idx, _pack_q(vals), total, bool(complete)),
                    lane)

    def append_record(self, record, complete=True, lane="stock"):
        """Append a prebuilt sparse `GridRecord` (see flowgrid.build_session_records), same checks, no copy."""
        self._check_slot(record.series_id, record.metric, record.window_s, record.session_id, lane)
        self._store(record.series_id, record.metric, record.window_s,
                    _Rec(record.session_id, record.minutes, record.idx, record.vals, record.total, bool(complete)), lane)

    def append_many(self, records, complete=True, lane="stock"):
        for r in records:
            self.append_record(r, complete, lane)

    def _check_slot(self, series_id, metric, window_s, session_id, lane):
        if self.strict_calendar and session_id not in self.calendar:
            raise M2StructuralError("session_not_in_calendar")
        ring = self._rings.get((series_id, metric, window_s))
        if ring is not None:
            if ring.lane != lane:
                raise ValueError("lane of an existing series cannot change")
            if ring.recs:
                last = next(reversed(ring.recs))
                if session_id == last:
                    raise M2StructuralError("duplicate_session")
                if session_id < last:
                    raise M2StructuralError("out_of_order_append")

    def _store(self, series_id, metric, window_s, rec, lane):
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
        for (s, m, w), ring, r in self._records():
            body = _body(ring.head, w, r)
            if r.sha is None:
                r.sha = hashlib.sha256((body + "\n").encode("ascii")).hexdigest()
            yield body[:-1] + ',"content_sha256":"' + r.sha + '"}'

    def dump(self):
        return "".join([ln + "\n" for ln in self.lines()]).encode("ascii")

    def dump_to(self, path):
        with open(path, "wb") as fh:
            fh.write(self.dump())

    def content_hash(self):
        h = hashlib.sha256()
        for ln in self.lines():
            h.update(ln.encode("ascii"))
            h.update(b"\n")
        return h.hexdigest()

    @classmethod
    def load(cls, source, calendar, k=20, strict_calendar=False, verify=True):
        """Store from canonical bytes (or a path); verifies every content_sha256 and rejects non-canonical order."""
        if isinstance(source, (str, bytes, os.PathLike)) and not (isinstance(source, bytes) and source[:1] == b"{"):
            with open(source, "rb") as fh:
                source = fh.read()
        text = source.decode("ascii") if isinstance(source, bytes) else source
        store = cls(calendar, k, strict_calendar)
        match = _LINE.match
        prev_key = None
        for ln in text.split("\n"):
            if not ln:
                continue
            m = match(ln)
            if m is None:
                raise ValueError("not a canonical history line")
            g1 = ln.find('],"total":', m.end())
            tail = ln[g1 + 10:].split(",") if g1 >= 0 else ()
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
            if strict_calendar and sid not in calendar:
                raise M2StructuralError("session_not_in_calendar")
            ring = store._rings.get(key)
            if ring is None:
                if prev_key is not None and key < prev_key:
                    raise ValueError("lines are not in canonical order")
                ring = store._rings[key] = _Ring("stock", _head(series_id, metric))
            elif next(reversed(ring.recs)) >= sid:
                raise M2StructuralError("duplicate_session" if next(reversed(ring.recs)) == sid else "out_of_order_append")
            prev_key = key
            txt = ln[m.end():g1]
            rec = _Rec(sid, (txt.count(",") + 1) if txt else 0, None, None, int(tail[0]), tail[1][11:] == "true", txt)
            rec.sha = claimed
            ring.recs[sid] = rec
            if len(ring.recs) > store.k:
                del ring.recs[next(iter(ring.recs))]
        return store

    # ------------------------------------------------------------------ binary snapshot (shared memory / mmap transfer)
    def snapshot(self):
        """The whole store as one bytes object: a header with the record table, then the raw arrays (8-byte aligned).
        `from_snapshot` over a `bytes`, an `mmap` or a `multiprocessing.shared_memory` buffer builds a store whose
        records are zero-copy read-only views of that buffer (the view transfer option of M2-B16)."""
        table, blobs, off = [], [], 0
        for key in sorted(self._rings):
            ring = self._rings[key]
            recs = []
            for sid in sorted(ring.recs):
                r = _sparse(ring.recs[sid])
                n = len(r.idx)
                head = [sid, r.minutes, r.total, 1 if r.complete else 0, n, off]
                try:
                    vb = array("q", r.vals).tobytes() if not isinstance(r.vals, array) else r.vals.tobytes()
                    ib = array("H", r.idx).tobytes() if not isinstance(r.idx, array) else r.idx.tobytes()
                except OverflowError:
                    head.append([int(v) for v in r.vals])
                    vb, ib = b"", array("H", r.idx).tobytes()
                pad = (-len(ib)) % 8
                blobs.append(ib + bytes(pad) + vb)
                off += len(ib) + pad + len(vb)
                recs.append(head)
            table.append([key[0], key[1], key[2], ring.lane, recs])
        meta = json.dumps({"k": self.k, "series": table}, separators=(",", ":")).encode("ascii")
        pad = (-(len(_SNAP_MAGIC) + 8 + len(meta))) % 8
        return b"".join([_SNAP_MAGIC, len(meta).to_bytes(8, "little"), meta, b" " * pad] + blobs)

    def snapshot_to(self, path):
        with open(path, "wb") as fh:
            fh.write(self.snapshot())

    @classmethod
    def from_snapshot(cls, buffer, calendar, k=None, strict_calendar=False):
        """Store over a snapshot buffer (bytes, mmap or shared memory); nothing is copied, the caller keeps the buffer
        alive (the store holds a reference). Records are read-only."""
        mv = memoryview(buffer)
        if bytes(mv[:len(_SNAP_MAGIC)]) != _SNAP_MAGIC:
            raise ValueError("not a history snapshot")
        n = int.from_bytes(mv[len(_SNAP_MAGIC):len(_SNAP_MAGIC) + 8], "little")
        start = len(_SNAP_MAGIC) + 8
        meta = json.loads(bytes(mv[start:start + n]))
        base = start + n + ((-(start + n)) % 8)
        store = cls(calendar, k or meta["k"], strict_calendar)
        store._buf = buffer
        for series_id, metric, window_s, lane, recs in meta["series"]:
            ring = store._rings[(series_id, metric, window_s)] = _Ring(lane, _head(series_id, metric))
            out = ring.recs
            for row in recs:
                sid, minutes, total, complete, cnt, off = row[:6]
                a = base + off
                ib = (cnt * 2 + 7) // 8 * 8
                idx = mv[a:a + cnt * 2].cast("H")
                if len(row) > 6:
                    vals = row[6]
                else:
                    vals = mv[a + ib:a + ib + cnt * 8].cast("q")
                out[sid] = _Rec(sid, minutes, idx, vals, total, bool(complete))
        return store

    def drop_caches(self):
        """Forget every cached view (memory control; never changes a result)."""
        for ring in self._rings.values():
            ring.views.clear()

    # ------------------------------------------------------------------ log-only facts
    def stats(self):
        recs = nbytes = 0
        for ring in self._rings.values():
            for r in ring.recs.values():
                recs += 1
                nbytes += 200 + (len(r.txt) if r.txt is not None else 10 * len(r.vals))
        return {"series": len(self._rings), "records": recs, "est_bytes": nbytes, "view_hits": self._hits,
                "view_misses": self._misses}

    def __len__(self):
        return len(self._rings)
