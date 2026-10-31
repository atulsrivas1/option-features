"""S02d evidence tool: `bench` (scalar_baseline on a skew series, store attached from a binary snapshot, one fresh
process) and `digest` (a seeded random workload of stores and reads over the public API; the digest of every result is
compared between the old source and the new one). Run with PYTHONPATH selecting the source under test:

    python tools/m3a_s02d_check.py bench [repeats=30] [calls=400]
    python tools/m3a_s02d_check.py digest [trials=1100]

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12
"""
import gc
import hashlib
import json
import os
import random
import statistics
import sys
import tempfile
import time

from option_features import m3a_history as MH
from option_features.flowgrid import Calendar
from option_features.flowstore import HistoryStore


def bench(repeats=30, calls=400, names=30, sessions=260):
    cal = Calendar([("S%04d" % i, 390) for i in range(sessions)])
    st = HistoryStore(cal)
    rnd = random.Random(7)
    keys = []
    for n in range(names):
        for m, cv in (("skew25", "spot"), ("skew25_fwd", "forward")):
            sid = "N%03d/stock/%s" % (n, m)
            st.add_series(sid, 252)
            keys.append((sid, m))
            for i in range(sessions - 1):
                st.append(sid, m, 0, cal.ids[i], [], total=rnd.randint(-10 ** 7, 10 ** 7), delta_convention=cv)
    p = os.path.join(tempfile.mkdtemp(), "b.bin")
    st.binary_snapshot_to(p)
    del st
    gc.collect()
    att = HistoryStore.attach_binary(p, cal)
    att.build_m3a_layout()
    as_of = cal.ids[sessions - 1]
    cv_of = {"skew25": "spot", "skew25_fwd": "forward"}

    def one_pass():
        out = []
        for j in range(calls):
            sid, m = keys[j % len(keys)]
            t0 = time.perf_counter_ns()
            r = MH.scalar_baseline(att, sid, m, as_of, delta_convention=cv_of[m])
            out.append((time.perf_counter_ns() - t0) / 1000.0)
            assert r.status == "available" and r.value["n"] == 252
        return out
    one_pass()                                            # 1 warm-up
    p50s, p95s = [], []
    for _ in range(repeats):
        v = sorted(one_pass())
        p50s.append(v[len(v) // 2])
        p95s.append(v[int(len(v) * .95)])
    print(json.dumps({"p50_us_median": round(statistics.median(p50s), 2), "p95_us_median": round(statistics.median(p95s), 2),
                      "p95_us_min": round(min(p95s), 2), "p95_us_max": round(max(p95s), 2)}))
    p = None


def digest(trials=1100):
    rnd = random.Random(31102026)
    N = 70
    cal = Calendar([("S%04d" % i, 3) for i in range(N)])
    series = [("A/stock/skew25", "skew25"), ("A/stock/skew25_fwd", "skew25_fwd"), ("A/stock/term_30_91", "term_30_91")]
    tmp = tempfile.mkdtemp()
    h = hashlib.sha256()
    reads = 0
    for trial in range(trials):
        kind = rnd.choice(("pure", "mixed", "mixed", "none"))
        st = HistoryStore(cal)
        for sid, _ in series:
            st.add_series(sid, rnd.choice((3, 5, 8, 20, 40)))

        def conv_for(m):
            base = "forward" if m.endswith("_fwd") else "spot"
            if m == "term_30_91":
                return None
            clean = rnd.choice((base, None if base == "spot" else base))
            if kind == "pure":
                return base
            if kind == "none":
                return clean
            return rnd.choice((None, "spot", "forward")) if rnd.random() < .12 else clean

        def feed(s, lo, hi):
            for i in range(lo, hi):
                if rnd.random() < .12:
                    continue
                for sid, m in series:
                    s.append(sid, m, 0, cal.ids[i], [], total=rnd.randint(-5, 10 ** 6), complete=rnd.random() > .1,
                             delta_convention=conv_for(m))
                    if rnd.random() < .05:
                        s.seal(sid, m, 0, cal.ids[i])

        def reads_on(s):
            nonlocal reads
            for _ in range(rnd.randint(3, 6)):
                sid, m = rnd.choice(series)
                a = rnd.randrange(0, N)
                mn = rnd.randint(1, 6)
                mx = rnd.choice((mn, mn + rnd.randint(0, 5), 252))
                kw = {}
                c = rnd.random()
                if c < .4:
                    kw["delta_convention"] = "spot"
                elif c < .8:
                    kw["delta_convention"] = "forward"
                r = MH.scalar_baseline(s, sid, m, cal.ids[a], min_sessions=mn, max_sessions=mx,
                                       lane=rnd.choice(("stock", "stock", "index")), **kw)
                h.update(repr((r.status, r.reason, r.code, r.value)).encode())
                reads += 1

        cut = rnd.randint(2, N - 5)
        feed(st, 0, cut)
        reads_on(st)
        if rnd.random() < .3:
            for sid, _ in series:
                st.add_series(sid, rnd.choice((3, 8, 40)))
            reads_on(st)
        feed(st, cut, N)
        reads_on(st)
        sk = {sid: st.k_of(sid) for sid, _ in series}
        att = None
        x = rnd.random()
        if x < .25:
            other = HistoryStore.load(st.dump(), cal, series_k=sk)
        elif x < .5:
            other = HistoryStore.from_snapshot(st.snapshot(), cal, series_k=sk)
        elif x < .75:
            other = HistoryStore.from_binary_snapshot(st.binary_snapshot(), cal)
        else:
            p = os.path.join(tmp, "t%d.bin" % trial)
            st.binary_snapshot_to(p)
            other = att = HistoryStore.attach_binary(p, cal)
        reads_on(other)
        for sid, m in series:
            ring = other._rings.get((sid, m, 0))
            if ring is not None and ring.recs:
                i = cal.ids.index(max(ring.recs)) + 1
                if i < N:
                    other.append(sid, m, 0, cal.ids[i], [], total=1, delta_convention=conv_for(m))
        reads_on(other)
        ring = None
        h.update(other.content_hash().encode() if hasattr(other, "content_hash") else b"")
        if att is not None:
            att.close_mapping()
    print(json.dumps({"reads": reads, "digest": h.hexdigest()}))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "bench":
        bench(*[int(x) for x in a[1:]])
    else:
        digest(*[int(x) for x in a[1:]])
