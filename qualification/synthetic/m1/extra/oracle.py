"""Independent oracle (float bisection, ACT/365) + my own adapter. Written from the spec only."""
import math
from fractions import Fraction as Fr
from decimal import Decimal as D


def N(x):
    return 0.5 * math.erfc(-x / math.sqrt(2))


def price(S, K, r, q, T, s, right):
    v = s * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + s * s / 2) * T) / v
    d2 = d1 - v
    if right == "call":
        return S * math.exp(-q * T) * N(d1) - K * math.exp(-r * T) * N(d2)
    return K * math.exp(-r * T) * N(-d2) - S * math.exp(-q * T) * N(-d1)


def bis_iv(S, K, r, q, T, mid, right):
    lo, hi = 1e-6, 8.0
    if mid <= price(S, K, r, q, T, lo, right) or mid >= price(S, K, r, q, T, hi, right):
        return None
    for _ in range(200):
        m = (lo + hi) / 2
        if price(S, K, r, q, T, m, right) < mid:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


def gate(c, cut, lim):
    bid = None if c["bid"] is None else Fr(D(c["bid"]))
    ask = None if c["ask"] is None else Fr(D(c["ask"]))
    known = c["known_at_ns"] if c.get("known_at_ns") is not None else c["event_ns"]
    if (bid is None and ask is None) or known > cut:
        return "no_quote"
    if c.get("condition", "regular") != "regular":
        return "excluded_condition"
    if bid is None or ask is None or bid <= 0:
        return "invalid_quote"
    if bid > ask:
        return "crossed_market"
    if bid == ask:
        return "locked_market"
    if cut - c["event_ns"] > lim:
        return "stale_quote"
    return None


class O:
    def __init__(s, inp, req):
        s.S = Fr(D(inp["spot"]))
        s.r = float(inp["rate"])
        s.q = float(inp["dividend_yield"])
        s.cut = req["cutoff_ns"]
        s.lim = req["stale_limit_ns"]
        s.cs = inp["contracts"]
        s.g = {c["id"]: gate(c, s.cut, s.lim) for c in s.cs}

    def Fw(s, d):
        return float(s.S) * math.exp((s.r - s.q) * d / 365)

    def near(s, ks, d):
        F = s.S if s.r == s.q else Fr(s.Fw(d))
        best = None
        for k in sorted(set(D(x) for x in ks)):
            dist = abs(Fr(k) - F)
            if best is None or dist < best[0]:
                best = (dist, k)
        return best[1] if best else None

    def iv(s, c):
        mid = float((Fr(D(c["bid"])) + Fr(D(c["ask"]))) / 2)
        return bis_iv(float(s.S), float(D(c["strike"])), s.r, s.q, c["expiry_days"] / 365, mid, c["right"])

    def contract(s, c):
        g = s.g[c["id"]]
        U = lambda r: dict(status="unavailable", reason=r, iv=None, label=None)
        if g:
            return U(g)
        st = c["style"]
        if st == "american":
            nk = s.near([x["strike"] for x in s.cs if x["expiry_days"] == c["expiry_days"]], c["expiry_days"])
            if D(c["strike"]) != nk:
                F = s.Fw(c["expiry_days"])
                K = float(D(c["strike"]))
                if (c["right"] == "call" and K < F) or (c["right"] == "put" and K > F):
                    return U("american_itm")
            lab = "approx"
        elif st == "european":
            lab = "exact"
        else:
            return U("style_unknown")
        v = s.iv(c)
        if v is None:
            return U("SOLVER")
        return dict(status="value", reason=None, iv=v, label=lab)

    def atm(s, d):
        byk = {}
        for c in s.cs:
            if c["expiry_days"] == d:
                byk.setdefault(D(c["strike"]), {})[c["right"]] = c
        el = [k for k, v in byk.items() if len(v) == 2 and all(s.g[x["id"]] is None for x in v.values())]
        if not el:
            return dict(status="unavailable", reason="no_atm_strike")
        k = s.near(el, d)
        legs = byk[k]
        if any(x["style"] not in ("european", "american") for x in legs.values()):
            return dict(status="unavailable", reason="style_unknown")
        ci, pi = s.iv(legs["call"]), s.iv(legs["put"])
        if ci is None or pi is None:
            return dict(status="unavailable", reason="SOLVER")
        lab = "approx" if any(x["style"] == "american" for x in legs.values()) else "exact"
        return dict(status="value", reason=None, strike=float(k), forward=s.Fw(d), call_iv=ci, put_iv=pi,
                    iv=(ci + pi) / 2, label=lab)

    def t30(s, t=30):
        ds = sorted({c["expiry_days"] for c in s.cs})
        if t in ds:
            a = s.atm(t)
            if a["status"] != "value":
                return dict(status="unavailable", reason=a["reason"], used=[])
            return dict(status="value", reason=None, iv=a["iv"], label=a["label"], used=[t], method="as_is")
        lo = [d for d in ds if d < t]
        hi = [d for d in ds if d > t]
        if not lo or not hi:
            return dict(status="unavailable", reason="no_bracketing_expiry", used=[])
        l, h = lo[-1], hi[0]
        al, ah = s.atm(l), s.atm(h)
        for a in (al, ah):
            if a["status"] != "value":
                return dict(status="unavailable", reason="no_bracketing_expiry" if a["reason"] == "no_atm_strike" else a["reason"], used=[l, h])
        wl, wh = al["iv"] ** 2 * l / 365, ah["iv"] ** 2 * h / 365
        w = wl + (wh - wl) * (t - l) / (h - l)
        return dict(status="value", reason=None, iv=math.sqrt(w / (t / 365)),
                    label="approx" if "approx" in (al["label"], ah["label"]) else "exact", used=[l, h], method="variance_interpolation")


def oracle(inp, req, op):
    o = O(inp, req)
    if op == "contract_iv":
        return {c["id"]: o.contract(c) for c in o.cs}
    if op == "atm_iv":
        return o.atm(req["expiry_days"])
    return o.t30(req.get("target_days", 30))


def impl(inp, req, op):
    from option_features import chainiv as C
    cs = [C.ChainContract(c["id"], c["expiry_days"], c["right"], c["strike"], c["bid"], c["ask"], c["event_ns"],
                          c.get("known_at_ns"), c["style"], c.get("condition", "regular")) for c in inp["contracts"]]
    ch = C.IVChain(cs, inp["spot"], inp["rate"], inp["dividend_yield"], req["cutoff_ns"], stale_limit_ns=req["stale_limit_ns"])
    L = lambda l: None if l is None else ("approx" if l == C.LABEL_APPROX else "exact")
    st = lambda s: "value" if s == "available" else s
    if op == "contract_iv":
        return {k: dict(status=st(v.status), reason=v.reason, iv=v.iv, label=L(v.label)) for k, v in ch.contract_iv().items()}
    if op == "atm_iv":
        a = ch.atm_iv(req["expiry_days"])
        return dict(status=st(a.status), reason=a.reason, strike=None if a.strike is None else float(a.strike),
                    forward=a.forward, call_iv=a.call_iv, put_iv=a.put_iv, iv=a.iv, label=L(a.label))
    t = ch.iv_30d(req.get("target_days", 30))
    return dict(status=st(t.status), reason=t.reason, iv=t.iv, label=L(t.label), used=list(t.expiries_used), method=t.method)


def cmp(a, b, tol=1e-4, path=""):
    """a = reference side (may hold reason 'SOLVER' = any solver reason); b = other side."""
    if isinstance(a, dict):
        for k in a:
            if k in b:
                r = cmp(a[k], b[k], tol, path + "/" + k)
                if r:
                    return r
        return None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return None if abs(a - b) <= (1e-6 if path.endswith("forward") else tol) else "%s %r vs %r" % (path, a, b)
    if a == "SOLVER":
        return None if b else "%s oracle solver-fail impl %r" % (path, b)
    return None if a == b else "%s %r vs %r" % (path, a, b)


def norm_expected(r):
    e = r["expected"]
    op = r["op"]
    lab = lambda l: None if l is None else ("approx" if l.startswith("approx") else "exact")
    f = lambda x: None if x is None else float(x)
    if op == "contract_iv":
        return {k: dict(status=v["status"], reason=v["reason"], iv=f(v["iv"]), label=lab(v["label"]))
                for k, v in e["contracts"].items() if k != "tolerance_iv"}
    d = dict(status=e["status"], reason=e["reason"], iv=f(e["iv"]), label=lab(e["label"]))
    if op == "atm_iv":
        d.update(strike=f(e["strike"]), forward=f(e["forward"]), call_iv=f(e["call_iv"]), put_iv=f(e["put_iv"]))
    else:
        d.update(used=e["expiries_used"], method=e["method"])
    return d


def check(row):
    """Return list of disagreement strings across oracle/impl/expected; and count of oracle numeric values."""
    inp, req, op = row["inputs"], row["request"], row["op"]
    o, i, e = oracle(inp, req, op), impl(inp, req, op), norm_expected(row)
    bad = []
    pairs = (("oracle~exp", o, e), ("impl~oracle", o, i), ("impl~exp", e, i))
    for name, a, b in pairs:
        if op == "contract_iv":
            for k in a:
                m = cmp(a[k], b[k])
                if m:
                    bad.append("%s %s %s" % (name, k, m))
        else:
            m = cmp(a, b)
            if m:
                bad.append("%s %s" % (name, m))
    allv = list(o.values()) if op == "contract_iv" else [o]
    n = sum(1 for y in allv for v in y.values() if isinstance(v, float))
    return bad, n
