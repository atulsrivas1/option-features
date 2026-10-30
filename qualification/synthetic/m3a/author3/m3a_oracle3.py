"""M3a author-3 PRIMARY oracle (synthetic, stdlib only, Decimal 60 digits).

SYNTHETIC. Smile-driven: expected values come from a STATED true smile
sigma(K,T) = a + b k + c k^2, k = ln(K/F), F = S exp((r-q)T), never from a solver.
Written from the design text, the matrix, the contract and the ruled list only.
No library code is imported. The second implementation (chain driven, float
bisection) is m3a_ref3.py.
"""
from decimal import Decimal as D, getcontext, ROUND_HALF_EVEN
import json

getcontext().prec = 60

LABEL = ("mock-data qualification only: passed on independently authored "
         "synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12")
APPROX = "approximate: European model on an American-style contract"
EXACT = "exact-model"
CUT = 34200000000000
STALE_NS = 10_000_000_000
PI = D("3.14159265358979323846264338327950288419716939937510582097494459")
TARGET = D("0.25")
REASON_OF = {"excl": "excluded_condition", "cross": "crossed_market", "stale": "stale_quote"}


def quant(x, dp):
    return x.quantize(D(1).scaleb(-dp), rounding=ROUND_HALF_EVEN)


def r8(x):
    return quant(x, 8)


def fs(x):
    if x == 0:
        x = abs(x)
    return format(x, "f")


def ncdf(x):
    x = D(x)
    if x == 0:
        return D("0.5")
    phi = (-(x * x) / 2).exp() / (2 * PI).sqrt()
    s = x
    term = x
    n = 0
    x2 = x * x
    while True:
        n += 1
        term = term * x2 / (2 * n + 1)
        s += term
        if n > 5 and abs(term) < D(10) ** -57 * abs(s):
            break
    return D("0.5") + phi * s


def T_of(days):
    return D(days) / D(365)


def fwd(S, r, q, days):
    return S * ((r - q) * T_of(days)).exp()


def d1_of(S, K, T, r, q, sg):
    return ((S / K).ln() + (r - q + sg * sg / 2) * T) / (sg * T.sqrt())


def bsm(S, K, T, r, q, sg, right):
    d1 = d1_of(S, K, T, r, q, sg)
    d2 = d1 - sg * T.sqrt()
    if right == "call":
        return S * (-q * T).exp() * ncdf(d1) - K * (-r * T).exp() * ncdf(d2)
    return K * (-r * T).exp() * ncdf(-d2) - S * (-q * T).exp() * ncdf(-d1)


def vega_of(S, K, T, r, q, sg):
    d1 = d1_of(S, K, T, r, q, sg)
    phi = (-(d1 * d1) / 2).exp() / (2 * PI).sqrt()
    return S * (-q * T).exp() * phi * T.sqrt()


def abs_delta(S, K, T, r, q, sg, right, fwd=False):
    d1 = d1_of(S, K, T, r, q, sg)
    e = D(1) if fwd else (-q * T).exp()
    return e * ncdf(d1) if right == "call" else e * ncdf(-d1)


# ------------------------------------------------------------------ spec
def default_step(days, S):
    import math
    raw = 0.055 * math.sqrt(days / 365.0) * float(S) / 2.5
    return D(max(1, round(raw))) * D("2.5")


def ex(days, S, r, q, a=D("0.2"), b=D("-0.5"), c=D("1.5"), n=5, step=None, base=None,
       style="european", mods=None, over=None, atm=None, strikes=None, shift=False, trim=True):
    """Build an expiry spec. atm: target sigma at the strike nearest F (sets a)."""
    S, r, q = D(S), D(r), D(q)
    b, c, a = D(b), D(c), D(a)
    F = fwd(S, r, q, days)
    st = D(step) if step is not None else default_step(days, S)
    if strikes is None:
        if base is None:
            if shift:
                mid = (S + F) / 2
                base = quant(mid - st / 2, 4)
            else:
                base = (F / st).quantize(D(1), rounding=ROUND_HALF_EVEN) * st
        base = D(base)
        strikes = [quant(base + st * j, 4) for j in range(-n, n + 1)]
    strikes = [D(k) for k in strikes]
    if atm is not None:
        kn = min(strikes, key=lambda k: (abs(k - F), k))
        kk = (kn / F).ln()
        a = D(atm) - b * kk - c * kk * kk
    if trim:
        T = T_of(days)
        keep = []
        for k in strikes:
            sg = D(over[k]) if (over and k in over) else None
            if sg is None:
                kl = (k / F).ln()
                sg = a + b * kl + c * kl * kl
            if sg > 0 and vega_of(S, k, T, r, q, sg) >= 4:
                keep.append(k)
        strikes = keep
    return {"days": days, "a": a, "b": b, "c": c, "strikes": strikes, "style": style,
            "mods": dict(mods or {}), "over": dict(over or {})}


def spec_of(exps, S="1000", r="0.03", q="0.01"):
    return {"S": D(S), "r": D(r), "q": D(q), "expiries": exps}


def sigma_at(e, F, K):
    if K in e["over"]:
        return D(e["over"][K])
    k = (K / F).ln()
    return e["a"] + e["b"] * k + e["c"] * k * k


def build_chain(spec, dp=4, check_vega=True):
    S, r, q = spec["S"], spec["r"], spec["q"]
    contracts = []
    for e in spec["expiries"]:
        T = T_of(e["days"])
        F = fwd(S, r, q, e["days"])
        for K in e["strikes"]:
            sg = sigma_at(e, F, K)
            for right in ("call", "put"):
                kd = e["mods"].get((K, right)) or e["mods"].get((K, "both")) or "ok"
                if kd == "drop":
                    continue
                if check_vega:
                    assert vega_of(S, K, T, r, q, sg) >= 4, ("vega<4", e["days"], K)
                p = quant(bsm(S, K, T, r, q, sg, right), dp)
                assert p > D("0.0011"), ("price too small", e["days"], K, right)
                bid, ask = p - D("0.001"), p + D("0.001")
                if kd == "cross":
                    bid, ask = ask, bid
                ev = CUT - (20_000_000_000 if kd == "stale" else 2_000_000_000)
                contracts.append({
                    "contract_id": "%dd-%s-%s" % (e["days"], "C" if right == "call" else "P", fs(quant(K, 4))),
                    "expiry_days": e["days"], "right": right, "strike": fs(quant(K, 4)),
                    "bid": fs(quant(bid, dp)), "ask": fs(quant(ask, dp)),
                    "event_ns": ev, "known_at_ns": None, "style": e["style"],
                    "condition": "late_report" if kd == "excl" else "regular"})
    return {"contracts": contracts, "spot": fs(quant(S, 4)), "rate": fs(quant(r, 4)),
            "dividend_yield": fs(quant(q, 4)), "cutoff_ns": CUT}


def smile_record(spec):
    out = []
    for e in spec["expiries"]:
        rec = {"days": e["days"], "a": fs(quant(e["a"], 12)), "b": fs(e["b"]), "c": fs(e["c"]),
               "strikes": [fs(quant(k, 4)) for k in e["strikes"]], "style": e["style"]}
        if e["over"]:
            rec["sigma_override"] = {fs(quant(k, 4)): fs(v) for k, v in e["over"].items()}
        if e["mods"]:
            rec["mods"] = ["%s/%s=%s" % (fs(quant(k[0], 4)), k[1], v) for k, v in sorted(e["mods"].items(), key=lambda t: (t[0][0], t[0][1]))]
        out.append(rec)
    return out


# ------------------------------------------------------------------ analysis
class Surf:
    def __init__(self, spec, conv=None):
        self.spec = spec
        self.conv = conv or spec.get("conv", "spot")
        self.S, self.r, self.q = spec["S"], spec["r"], spec["q"]
        self.exps = {e["days"]: self._expiry(e) for e in spec["expiries"]}
        self.days = sorted(self.exps)
        self.american = any(e["style"] == "american" for e in spec["expiries"])

    def contract_reasons(self):
        tot = {}
        for x in self.exps.values():
            for k, v in x["reasons"].items():
                tot[k] = tot.get(k, 0) + v
        return dict(sorted(tot.items()))

    def _expiry(self, e):
        S, r, q = self.S, self.r, self.q
        days = e["days"]
        T = T_of(days)
        F = fwd(S, r, q, days)
        strikes = sorted(e["strikes"])
        sg = {K: sigma_at(e, F, K) for K in strikes}

        def kind(K, right):
            return e["mods"].get((K, right)) or e["mods"].get((K, "both")) or "ok"
        listed = [K for K in strikes if not (kind(K, "call") == "drop" and kind(K, "put") == "drop")]
        american = e["style"] == "american"
        near = min(listed, key=lambda K: (abs(K - F), K))
        elig, reasons = {}, {}
        for K in strikes:
            for right in ("call", "put"):
                kd = kind(K, right)
                if kd == "drop":
                    continue
                if kd != "ok":
                    rs = REASON_OF[kd]
                    reasons[rs] = reasons.get(rs, 0) + 1
                    continue
                if american and K != near:
                    itm = (right == "call" and K < F) or (right == "put" and K > F)
                    if itm:
                        reasons["american_itm"] = reasons.get("american_itm", 0) + 1
                        continue
                elig[(K, right)] = True
        either = [K for K in listed if (K, "call") in elig or (K, "put") in elig]
        both = [K for K in strikes if (K, "call") in elig and (K, "put") in elig]

        def near10(right):
            return sum(1 for K in strikes if (K, right) in elig and abs(K - F) <= D("0.1") * F)
        cov_ok = (len(either) >= 4 and 5 * len(either) >= 3 * len(listed)
                  and near10("call") >= 2 and near10("put") >= 2)
        atmK = min(both, key=lambda K: (abs(K - F), K)) if both else None
        out = {"days": days, "T": T, "F": F, "sg": sg, "elig": elig, "reasons": reasons,
               "cov_ok": cov_ok, "listed": len(listed), "eligible": len(either), "atmK": atmK,
               "atm_iv": sg[atmK] if atmK is not None else "no_atm_strike"}

        def dl(K, right):
            return abs_delta(S, K, T, r, q, sg[K], right, self.conv == "forward")

        def side(right):
            if atmK is None:
                return "no_delta_bracket"
            if right == "put":
                seq = sorted([K for K in strikes if K < atmK and (K, "put") in elig], reverse=True)
            else:
                seq = sorted([K for K in strikes if K > atmK and (K, "call") in elig])
            pk, pd = atmK, dl(atmK, right)
            if pd < TARGET:
                return "no_delta_bracket"
            for K in seq:
                dd = dl(K, right)
                if pd >= TARGET >= dd:
                    w = (TARGET - pd) / (dd - pd)
                    return sg[pk] + (sg[K] - sg[pk]) * w
                pk, pd = K, dd
            return "no_delta_bracket"
        out["p25"] = side("put")
        out["c25"] = side("call")
        return out

    def cm(self, target, key):
        """constant-maturity value of key (atm_iv / p25 / c25); D or reason string."""
        days = self.days
        if key == "atm_iv":
            miss_exact, miss_br = "no_atm_strike", "no_bracketing_expiry"
        else:
            miss_exact, miss_br = "no_delta_bracket", "no_delta_bracket"
        if target in days:
            x = self.exps[target]
            if key == "atm_iv" and isinstance(x[key], str):
                return x[key]
            if not x["cov_ok"]:
                return "low_surface_coverage"
            return x[key]
        lo = [d for d in days if d < target]
        hi = [d for d in days if d > target]
        if not lo or not hi:
            return "no_bracketing_expiry"
        d1, d2 = lo[-1], hi[0]
        x1, x2 = self.exps[d1], self.exps[d2]
        if not x1["cov_ok"] or not x2["cov_ok"]:
            return "no_bracketing_expiry"
        v1, v2 = x1[key], x2[key]
        for v in (v1, v2):
            if isinstance(v, str):
                return miss_br
        w1, w2 = v1 * v1 * d1, v2 * v2 * d2
        w = w1 + (w2 - w1) * D(target - d1) / D(d2 - d1)
        return (w / D(target)).sqrt()


def sgn(x):
    return (x > 0) - (x < 0)


def fire(direction, v, thr):
    if direction == "up":
        return v >= thr
    if direction == "down":
        return v <= -thr
    return abs(v) >= thr


def labels_of(sf, req):
    used = getattr(sf, "used_days", None)   # R-180: labels are output-level, only expiries the output uses
    L = {APPROX if e["style"] == "american" else EXACT for e in sf.spec["expiries"] if used is None or e["days"] in used}
    if req.get("feed_delay_tag") == "delayed":
        L.add("delayed")
    return sorted(L)


# ------------------------------------------------------------------ evaluators
def _base(sf, status="available", reason=None, code=None, value=None, fired=None, req=None):
    return {"status": status, "reason": reason, "code": code, "value": value, "fired": fired,
            "labels": labels_of(sf, req) if status == "available" else [],
            "contract_reasons": sf.contract_reasons(), "rule": None, "margin": None, "near": False}


def _bad(sf, reason, req):
    return _base(sf, "unavailable", reason, None, None, None, req)


def _inv(sf, code, req):
    return _base(sf, "invalid_input", None, code, None, None, req)


def ev_v4(sf, req, prior):
    form = req["iv_form"]
    if not isinstance(form, str):
        return _inv(sf, "malformed_type", req)
    if form not in ("atm", "30d"):
        return _inv(sf, "iv_form_not_allowed", req)
    if prior is not None and prior["time_ns"] >= CUT:
        return _inv(sf, "prior_not_before_cutoff", req)
    if req["feed_delay_tag"] == "delayed" and req["mode"] == "intraday":
        return _inv(sf, "delayed_feed_tag", req)
    if form == "30d":
        now = sf.cm(30, "atm_iv")
    else:
        el = [d for d in sf.days if sf.exps[d]["cov_ok"]]
        now = sf.exps[el[0]]["atm_iv"] if el else "low_surface_coverage"
        if el:
            sf.used_days = {el[0]}
    if isinstance(now, str):
        return _bad(sf, now, req)
    now_r = r8(now)
    if prior is None:
        return _bad(sf, "no_prior_reading", req)
    pv = D(prior["value"])
    if pv == 0:
        return _bad(sf, "zero_denominator", req)
    chg = now_r - pv
    pts = chg * 100
    ratio = chg / pv
    pct = ratio * 100
    thr = D(req["threshold"])
    f = fire(req["direction"], pct, thr)
    out = _base(sf, value={"now": fs(now_r), "prior": fs(pv), "change_points": fs(pts),
                           "change_ratio": fs(r8(ratio)), "prior_kind": prior["kind"], "iv_form": form}, fired=f, req=req)
    out["rule"] = {"kind": "pct", "x": fs(pct), "thr": fs(thr), "dir": req["direction"]}
    out["margin"] = abs(abs(pct) - thr) if req["direction"] == "either" else abs(pct - (thr if req["direction"] == "up" else -thr))
    out["unrounded_pct"] = pct
    return out


def ev_v5(sf, req):
    t = {}
    for d in (9, 30, 91):
        t[d] = sf.cm(d, "atm_iv")
    pair = req["pair"]
    need = (9, 30) if pair == "9_30" else (30, 91)
    for d in need:
        if isinstance(t[d], str):
            return _bad(sf, t[d], req)
    for d in (9, 30, 91):
        if isinstance(t[d], str):
            raise AssertionError("other pair unavailable: shape ambiguous (row avoided)")
    pairs = {}
    spreads = {}
    for name, (s, l) in (("9_30", (9, 30)), ("30_91", (30, 91))):
        sp = r8(t[l] - t[s])
        spreads[name] = sp * 100
        pairs[name] = {"longer": fs(r8(t[l])), "shorter": fs(r8(t[s])), "spread_points": fs(sp * 100)}
    x = spreads[pair]
    thr = D(req["threshold"])
    out = _base(sf, value={"pairs": pairs}, fired=fire(req["direction"], x, thr), req=req)
    out["rule"] = {"kind": "pts", "x": fs(x), "thr": fs(thr), "dir": req["direction"]}
    out["margin"] = _margin(req["direction"], x, thr)
    return out


def _margin(direction, x, thr):
    if direction == "either":
        return abs(abs(x) - thr)
    return abs(x - (thr if direction == "up" else -thr))


def ev_v6(sf, req):
    el = [d for d in sf.days if sf.exps[d]["cov_ok"]]
    if len(el) < 2:
        return _bad(sf, "fewer_than_two_expiries", req)
    n1, n2 = el[0], el[1]
    a1, a2 = sf.exps[n1]["atm_iv"], sf.exps[n2]["atm_iv"]
    for v in (a1, a2):
        if isinstance(v, str):
            return _bad(sf, v, req)
    sp = r8(a2 - a1) * 100
    thr = D(req["threshold"])
    out = _base(sf, value={"nearest_days": n1, "second_days": n2, "spread_points": fs(sp)},
                fired=fire(req["direction"], sp, thr), req=req)
    out["rule"] = {"kind": "pts", "x": fs(sp), "thr": fs(thr), "dir": req["direction"]}
    out["margin"] = _margin(req["direction"], sp, thr)
    return out


def _store_ref(store, n):
    return store[n - 1]


def ev_v7(sf, req, store):
    n = int(req["prior_sessions"])
    if any(s["time_ns"] >= CUT for s in store):
        return _inv(sf, "prior_not_before_cutoff", req)
    t30 = sf.cm(30, "atm_iv")
    t91 = sf.cm(91, "atm_iv")
    for v in (t30, t91):
        if isinstance(v, str):
            return _bad(sf, v, req)
    now = r8(t91 - t30)
    if not store:
        return _bad(sf, "no_prior_reading", req)
    if len(store) < n:
        return _bad(sf, "insufficient_history", req)  # PENDING-RULING D-07
    pri = [{"session_id": s["session_id"], "gap": fs(D(s["value_int"]) / D(10 ** 8))} for s in store[:n]]
    ref = D(store[n - 1]["value_int"]) / D(10 ** 8)
    chg = (now - ref) * 100
    thr = D(req["threshold"])
    out = _base(sf, value={"now": fs(now), "priors": pri, "gap_change_points": fs(chg)},
                fired=fire(req["direction"], chg, thr), req=req)
    out["rule"] = {"kind": "pts", "x": fs(chg), "thr": fs(thr), "dir": req["direction"]}
    out["margin"] = _margin(req["direction"], chg, thr)
    return out


def _cv(sf, req):
    c = req["delta_convention"]
    if not isinstance(c, str):
        return _inv(sf, "malformed_type", req)
    if c not in ("spot", "forward"):
        return _inv(sf, "convention_not_allowed", req)
    return None


def skew_now(sf):
    p = sf.cm(30, "p25")
    c = sf.cm(30, "c25")
    for v in (p, c):
        if isinstance(v, str):
            return v
    return p, c


def ev_v8(sf, req):
    bad = _cv(sf, req)
    if bad:
        return bad
    pc = skew_now(sf)
    if isinstance(pc, str):
        return _bad(sf, pc, req)
    p, c = pc
    sk = r8(p - c) * 100
    thr = D(req["threshold"])
    out = _base(sf, value={"put25_iv": fs(r8(p)), "call25_iv": fs(r8(c)), "skew_points": fs(sk), "tenor": 30},
                fired=fire(req["direction"], sk, thr), req=req)
    out["rule"] = {"kind": "pts", "x": fs(sk), "thr": fs(thr), "dir": req["direction"]}
    out["margin"] = _margin(req["direction"], sk, thr)
    return out


def ev_v10(sf, req, prior, store):
    kind = req["prior_kind"]
    n = int(req["prior_sessions"])
    bad = _cv(sf, req)
    if bad:
        return bad
    recs = ([prior] if prior is not None else []) + list(store or [])
    if any(x.get("delta_convention", "spot") != req["delta_convention"] for x in recs):
        return _inv(sf, "convention_mismatch", req)
    if (prior is not None and prior["time_ns"] >= CUT) or any(s["time_ns"] >= CUT for s in (store or [])):
        return _inv(sf, "prior_not_before_cutoff", req)
    pc = skew_now(sf)
    if isinstance(pc, str):
        return _bad(sf, pc, req)
    p, c = pc
    now = r8(p - c)
    if kind == "frame":
        if prior is None:
            return _bad(sf, "no_prior_reading", req)
        ref = D(prior["value"])
        pri = []
    else:
        if not store:
            return _bad(sf, "no_prior_reading", req)
        if len(store) < n:
            return _bad(sf, "insufficient_history", req)
        pri = [{"session_id": s["session_id"], "gap": fs(D(s["value_int"]) / D(10 ** 8))} for s in store[:n]]
        ref = D(store[n - 1]["value_int"]) / D(10 ** 8)
    chg = (now - ref) * 100
    sn, sp_ = sgn(now), sgn(ref)
    changed = (sn != 0 and sp_ != 0 and sn != sp_)
    thr = D(req["threshold"])
    if req["condition"] == "change":
        f = fire(req["direction"], chg, thr)
        rule = {"kind": "pts", "x": fs(chg), "thr": fs(thr), "dir": req["direction"]}
        margin = _margin(req["direction"], chg, thr)
    else:
        f = changed
        rule = {"kind": "sign", "now": fs(now), "ref": fs(ref)}
        margin = min(abs(now), abs(ref)) * 100
    out = _base(sf, value={"now": fs(now), "priors": pri, "change_points": fs(chg), "sign_now": sn,
                           "sign_prior": sp_, "sign_changed": changed}, fired=f, req=req)
    out["rule"] = rule
    out["margin"] = margin
    return out


def ev_v11(sf, req):
    bad = _cv(sf, req)
    if bad:
        return bad
    a = sf.cm(30, "atm_iv")
    if isinstance(a, str):
        return _bad(sf, a, req)
    pc = skew_now(sf)
    if isinstance(pc, str):
        return _bad(sf, pc, req)
    p, c = pc
    cur = r8((p + c) / 2 - a) * 100
    thr = D(req["threshold"])
    out = _base(sf, value={"wings_mid": fs(r8((p + c) / 2)), "atm_iv": fs(r8(a)), "curvature_points": fs(cur)},
                fired=fire(req["direction"], cur, thr), req=req)
    out["rule"] = {"kind": "pts", "x": fs(cur), "thr": fs(thr), "dir": req["direction"]}
    out["margin"] = _margin(req["direction"], cur, thr)
    return out


def ev_v21(sf, req):
    bad = _cv(sf, req)
    if bad:
        return bad
    if "threshold" not in req:
        return _inv(sf, "threshold_required", req)
    a = sf.cm(30, "atm_iv")
    if isinstance(a, str):
        return _bad(sf, a, req)
    pc = skew_now(sf)
    if isinstance(pc, str):
        return _bad(sf, pc, req)
    p, c = pc
    pd, cd = r8(p - a), r8(c - a)
    if cd == 0:
        return _bad(sf, "zero_denominator", req)
    ratio = r8((p - a) / (c - a))
    thr = D(req["threshold"])
    f = ratio >= thr if req["direction"] == "up" else ratio <= thr
    out = _base(sf, value={"put_distance": fs(pd * 100), "call_distance": fs(cd * 100), "ratio": fs(ratio)}, fired=f, req=req)
    out["rule"] = {"kind": "ratio", "x": fs(ratio), "thr": fs(thr), "dir": req["direction"]}
    out["margin"] = abs(ratio - thr)
    out["call_distance"] = cd
    return out


# ------------------------------------------------------------------ tuning
def bisect_param(fn, lo, hi, target, iters=90):
    """fn monotone in the parameter; returns parameter with fn(p) == target (60 digit)."""
    lo, hi = D(lo), D(hi)
    flo, fhi = fn(lo), fn(hi)
    assert (flo - target) * (fhi - target) <= 0, ("target not bracketed", flo, fhi, target)
    inc = fhi > flo
    for _ in range(iters):
        mid = (lo + hi) / 2
        fm = fn(mid)
        if (fm < target) == inc:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def request(mode="intraday", tag="live", direction=None, threshold=None, tenors=None, **kw):
    q = {"mode": mode, "lane": "stock", "stale_limit_ns": STALE_NS, "feed_delay_tag": tag,
         "evaluation_ns": CUT, "tenors": list(tenors or []), "delta_target": "0.25",
         "min_strikes": 4, "min_coverage": "3/5", "prior_sessions": 1}
    if direction is not None:
        q["direction"] = direction
    if threshold is not None:
        q["threshold"] = threshold
    q.update(kw)
    return q


def tol_for(res, fam):
    """absolute tolerances per row (IV 1e-4; derived annual differences 2e-4; ratios computed)."""
    t = {"iv": "0.00003", "diff_annual": "0.00006", "points": "0.005"}
    if fam == "V4":
        pr = D(res["value"]["prior"]) if res["status"] == "available" else D(1)
        t["change_ratio"] = fs(quant(D("0.00006") / abs(pr) * (1 + abs(D(res["value"]["change_ratio"]))) * 2, 6)) if res["status"] == "available" else "0"
    if fam == "V21" and res["status"] == "available":
        cd = abs(res["call_distance"])
        t["ratio"] = fs(quant(D("0.00006") * (1 + abs(D(res["value"]["ratio"]))) / cd * 2, 6))
    return t
