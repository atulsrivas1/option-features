"""Shared builders for F2-family generators (stdlib only)."""
from m2common import *

XV = {"premium": usd(1000), "contracts": 40, "prints": 10}
BASEV = {"premium": usd(100), "contracts": 5, "prints": 2}
BIG = {"premium": usd(9000000), "contracts": 100000, "prints": 100000}


def x_prints(metric, cid="C1"):
    if metric == "premium":
        return [pp(cid, -S(10), 1000, size=10)]
    if metric == "contracts":
        return [pr(cid, -S(10), "1.0000", 40)]
    return [pr(cid, -S(10 + i), "1.0000", 1) for i in range(10)]


def make_hist(metric, k, W, minutes, *, hvf=1, nprior=20, nstore=20, incomplete_idx=None, cur_in_store=False,
              old_big=False, const=False, zero=False, spike0=True, extra_ids=()):
    cal, prior_ids, cur = mkcal([minutes] * nprior, minutes)
    use = prior_ids[-nstore:] if nstore else []
    drop = W // 60
    nplant = min(20, len(use))
    ov = spread(k, XV[metric] * hvf, drop, minutes, nsess=nplant) if (k and use) else [[] for _ in use]
    if len(use) > 20:
        ov = [[] for _ in range(len(use) - 20)] + ov
    base = XV[metric] if const else (0 if zero else BASEV[metric])
    recs = []
    for j, sid in enumerate(use):
        o = list(ov[j]) if j < len(ov) else []
        if spike0:
            o = [(0, BIG[metric])] + o
        b = base
        if old_big and j == 0 and len(use) > 20:
            b, o = BIG[metric], []
        recs.append(hs(sid, minutes, base=b, over=o,
                       complete=not (incomplete_idx is not None and j == incomplete_idx)))
    for sid in extra_ids:
        recs.insert(0, hs(sid, minutes, base=BIG[metric], over=[]))
    if cur_in_store:
        recs.append(hs(cur, minutes, base=BIG[metric], over=[], complete=True))
    return cal, cur, hist("SYN1", metric, recs, window_s=W)


def f2_intraday(R, metric, k, *, W=300, minutes=20, el=None, X=5, tags=(), pending=None, delay="live",
                ruling="Q1,Q2", ref="matrix M2-2; flow.md F2", minimal=False, hmod=None, **kw):
    cal, cur, h = make_hist(metric, k, W, minutes, **kw)
    if hmod:
        h.update(hmod)
    el = S(W + 900) if el is None else el
    sess = session(cur, el, minutes, delay=delay)
    inp = mkin(x_prints(metric), sess=sess, cal=cal, histo=h)
    prm = {"metric": metric} if minimal else {"form": "intraday", "metric": metric, "window_s": W, "X": X, "K": 20}
    return R.add("M2-2", ref, ruling, inp, prm, tags=list(tags) + (["default_omitted"] if minimal else []), pending=pending)


def f2_eod(R, metric, k, *, X=5, complete=True, nstore=20, hvf=1, tags=(), pending=None, delay="live",
           ruling="Q1,Q2,Q3", incomplete_idx=None, ref="matrix M2-2 end of day", minimal=False, extra=None):
    minutes = 3
    cal, prior_ids, cur = mkcal([minutes] * 20, minutes)
    xt = {"premium": 5000000, "contracts": 500, "prints": 50}[metric]
    bt = {"premium": 1000000, "contracts": 100, "prints": 10}[metric]
    use = prior_ids[-nstore:] if nstore else []
    recs = []
    for j, sid in enumerate(use):
        tot = xt * hvf if j < k else bt
        recs.append(hs(sid, minutes, base=0, over=[], total=tot,
                       complete=not (incomplete_idx is not None and j == incomplete_idx)))
    h = hist("SYN1", metric, recs)
    sess = session(cur, S(23400), minutes, complete=complete, delay=delay, total=xt)
    inp = mkin(None, contracts=CONTRACTS, sess=sess, cal=cal, histo=h)
    prm = {"form": "end_of_day", "metric": metric} if minimal else {"form": "end_of_day", "metric": metric, "X": X, "K": 20}
    prm.update(extra or {})
    return R.add("M2-2", ref, ruling, inp, prm, tags=list(tags) + (["default_omitted"] if minimal else []), pending=pending)


def part(metric, k, W, minutes, **kw):
    cal, cur, h = make_hist(metric, k, W, minutes, **kw)
    x = XV[metric] if metric != "prints" else Fr(XV[metric], W // 60)
    return cal, cur, {"x": fmt(x), "history": h}


def f2d(R, ks, *, W=300, minutes=20, el=None, missing=(), X=5, hvf=2, tags=(), ruling="Q14", pending=None,
        ref="matrix M2-3; flow.md F2d", mismatch=()):
    parts = {}
    cal = cur = None
    for pn, metric, k in zip(("F2a", "F2b", "F2c"), ("premium", "contracts", "prints"), ks):
        kw = {"hvf": hvf}
        if pn in missing:
            kw["nstore"] = 0
        cal, cur, pt = part(metric, k, W, minutes, **kw)
        if pn in mismatch:
            pt["history"]["window_s"] = 900
        parts[pn] = pt
    el = S(W + 900) if el is None else el
    sess = session(cur, el, minutes)
    inp = {"t_ns": T0, "series_id": "SYN1", "session": sess, "calendar": cal, "parts": parts}
    return R.add("M2-3", ref, ruling, inp, {"window_s": W, "X": X, "K": 20}, tags=list(tags) + ["f2d_fired_null"], pending=pending)
