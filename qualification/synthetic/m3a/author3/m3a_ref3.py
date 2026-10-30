"""M3a author-3 SECOND implementation (chain driven, float bisection) with mutation hooks.

SYNTHETIC. Independent of m3a_oracle3.py (different input: quote text, different arithmetic:
binary64 + math.erf + bisection, different code). It is a test reference, not library code.
evaluate(fam, inputs, mut) takes the row inputs exactly as stored (chain, prior, priors_store,
request) and returns {status, reason, code, value, fired, labels, contract_reasons, rule}.
`mut` is a frozenset of mutant ids (M01..M49); empty = the honest reference.
"""
import math
from decimal import Decimal as D, ROUND_HALF_EVEN

APPROX = "approximate: European model on an American-style contract"
EXACT = "exact-model"
DEFAULTS = {
    "V4": ("up", "10"), "V5": ("up", "3"), "V6": ("up", "3"), "V7": ("either", "2"),
    "V8": ("up", "5"), "V10": ("either", "2"), "V11": ("up", "3"), "V21": ("up", None),
}
STATE = {"last_now": None}
REASON_FOR = {"crossed": "crossed_market", "stale": "stale_quote", "excl": "excluded_condition"}


def r8(x):
    return D(x).quantize(D("0.00000001"), rounding=ROUND_HALF_EVEN)


def ncdf(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def bsm(S, K, T, r, q, s, right):
    sq = s * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * s * s) * T) / sq
    d2 = d1 - sq
    if right == "call":
        return S * math.exp(-q * T) * ncdf(d1) - K * math.exp(-r * T) * ncdf(d2)
    return K * math.exp(-r * T) * ncdf(-d2) - S * math.exp(-q * T) * ncdf(-d1)


def solve_iv(mid, S, K, T, r, q, right):
    lo, hi = 1e-6, 8.0
    if not (bsm(S, K, T, r, q, lo, right) <= mid <= bsm(S, K, T, r, q, hi, right)):
        return None
    for _ in range(220):
        m = 0.5 * (lo + hi)
        if bsm(S, K, T, r, q, m, right) < mid:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def sgn(x):
    return (x > 0) - (x < 0)


def fire(direction, v, thr, mut):
    if "M23" in mut:
        direction = "either"
    if "M24" in mut:
        if direction == "up":
            return v > thr
        if direction == "down":
            return v < -thr
        return abs(v) > thr
    if direction == "up":
        return v >= thr
    if direction == "down":
        return v <= -thr
    return abs(v) >= thr


class Chain:
    def __init__(self, inp, mut):
        ch = inp["chain"]
        self.mut = mut
        self.S = float(D(ch["spot"]))
        self.r = float(D(ch["rate"]))
        self.q = float(D(ch["dividend_yield"]))
        self.cut = ch["cutoff_ns"]
        req = inp["request"]
        self.stale = req.get("stale_limit_ns", 10_000_000_000)
        cv = req.get("delta_convention", "spot")
        cv = cv if cv in ("spot", "forward") else "spot"
        if "M46" in mut:
            cv = "spot"
        self.fwd = (cv == "forward") != ("M45" in mut)
        self.reasons = {}
        self.american = False
        self.styles = set()
        ex = {}
        for c in ch["contracts"]:
            d = c["expiry_days"]
            e = ex.setdefault(d, {"T": d / 365.0, "rows": {}, "listed": set()})
            K = float(D(c["strike"]))
            e["listed"].add(K)
            bid, ask = D(c["bid"]), D(c["ask"])
            ev = c["event_ns"] if c["known_at_ns"] is None else c["known_at_ns"]
            why = None
            if c["condition"] != "regular" and "M33" not in mut:
                why = "excluded_condition"
            elif bid > ask and "M34" not in mut:
                why = "crossed_market"
            elif (self.cut - ev) > self.stale and "M35" not in mut:
                why = "stale_quote"
            self.styles.add(c["style"])
            e["rows"][(K, c["right"])] = {"why": why, "bid": bid, "ask": ask, "style": c["style"]}
            e.setdefault("styles", set()).add(c["style"])
        for d, e in ex.items():
            e["F"] = self.S * math.exp((self.r - self.q) * e["T"])
            if "M01" in mut:
                e["F"] = self.S
            near = min(e["listed"], key=lambda K: (abs(K - e["F"]), K))
            for (K, right), row in e["rows"].items():
                if row["style"] == "american":
                    self.american = True
                    if row["why"] is None and K != near:
                        itm = (right == "call" and K < e["F"]) or (right == "put" and K > e["F"])
                        if itm:
                            row["why"] = "american_itm"
                if row["why"] is not None:
                    self.reasons[row["why"]] = self.reasons.get(row["why"], 0) + 1
        self.ex = ex
        self.used = None   # R-180: expiries the output uses (None = all, mutant M52 keeps all)
        self.used_american = False

    def iv(self, d, K, right):
        e = self.ex[d]
        row = e["rows"][(K, right)]
        if "iv" not in row:
            mid = float((row["bid"] + row["ask"]) / 2)
            row["iv"] = solve_iv(mid, self.S, K, e["T"], self.r, self.q, right)
        v = row["iv"]
        if "M11" in self.mut and v is not None:
            v = round(v, 3)
        return v

    def ok(self, d, K, right):
        row = self.ex[d]["rows"].get((K, right))
        return row is not None and row["why"] is None

    def delta(self, d, K, right, ivk, atm):
        e = self.ex[d]
        T = e["T"]
        s = atm if "M03" in self.mut else ivk
        drift = (self.r - self.q) if "M01" not in self.mut else 0.0
        d1 = (math.log(self.S / K) + (drift + 0.5 * s * s) * T) / (s * math.sqrt(T))
        disc = 1.0 if ("M04" in self.mut or self.fwd) else math.exp(-self.q * T)
        if right == "call" or "M36" in self.mut:
            return disc * ncdf(d1)
        return disc * ncdf(-d1)

    def cov_ok(self, d):
        e = self.ex[d]
        strikes = sorted(e["listed"])
        elig = [K for K in strikes if self.ok(d, K, "call") or self.ok(d, K, "put")]
        need = 3 if "M32" in self.mut else 4
        if len(elig) < need or 5 * len(elig) < 3 * len(strikes):
            return False
        for right in ("call", "put"):
            if sum(1 for K in strikes if self.ok(d, K, right) and abs(K - e["F"]) <= 0.1 * e["F"]) < 2:
                return False
        return True

    def atm(self, d):
        """(strike, iv) or None."""
        e = self.ex[d]
        both = [K for K in e["listed"] if self.ok(d, K, "call") and self.ok(d, K, "put")]
        if not both:
            return None
        ref = self.S if "M02" in self.mut else e["F"]
        if "M06" in self.mut:
            K = min(both, key=lambda K: (abs(K - ref), -K))
        else:
            K = min(both, key=lambda K: (abs(K - ref), K))
        a, b = self.iv(d, K, "call"), self.iv(d, K, "put")
        if "M48" in self.mut:
            pass
        return K, 0.5 * (a + b)

    def side(self, d, right):
        """25-delta IV on one side of one expiry, or None."""
        a = self.atm(d)
        if a is None:
            return None
        Katm, atm_iv = a
        e = self.ex[d]
        if right == "put":
            ks = sorted([K for K in e["listed"] if K < Katm and self.ok(d, K, "put")], reverse=True)
        else:
            ks = sorted([K for K in e["listed"] if K > Katm and self.ok(d, K, "call")])
        pts = [(Katm, self.iv(d, Katm, right), self.delta(d, Katm, right, self.iv(d, Katm, right), atm_iv))]
        for K in ks:
            v = self.iv(d, K, right)
            pts.append((K, v, self.delta(d, K, right, v, atm_iv)))
        tgt = 0.25
        if pts[0][2] < tgt:
            return None
        cands = [i for i in range(1, len(pts)) if pts[i - 1][2] >= tgt >= pts[i][2]]
        if "M05" in self.mut:
            rev = pts[::-1]
            cands = [i for i in range(1, len(rev)) if rev[i][2] >= tgt >= rev[i - 1][2]]
            if cands:
                i = cands[0]
                lo, hi = rev[i - 1], rev[i]
                return self._interp(lo, hi, tgt, d, right)
        elif cands:
            i = cands[-1] if "M07" in self.mut else cands[0]
            return self._interp(pts[i - 1], pts[i], tgt, d, right)
        if "M08" in self.mut:
            best = min(pts, key=lambda t: abs(t[2] - tgt))
            return best[1]
        return None

    def _interp(self, p0, p1, tgt, d, right):
        K0, v0, d0 = p0
        K1, v1, d1 = p1
        if "M09" in self.mut:
            e = self.ex[d]
            F, T = e["F"], e["T"]
            z = _ninv(tgt / math.exp(-self.q * T))
            d1s = z if right == "call" else -z
            kt = 0.5 * v0 * v0 * T - d1s * v0 * math.sqrt(T)
            k0, k1 = math.log(K0 / F), math.log(K1 / F)
            return v0 + (v1 - v0) * (kt - k0) / (k1 - k0)
        w = (tgt - d0) / (d1 - d0)
        if "M10" in self.mut:
            t = self.ex[d]["T"]
            va, vb = v0 * v0 * t, v1 * v1 * t
            return math.sqrt((va + (vb - va) * w) / t)
        return v0 + (v1 - v0) * w


def _ninv(p):
    lo, hi = -10.0, 10.0
    for _ in range(200):
        m = 0.5 * (lo + hi)
        if ncdf(m) < p:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def cm_value(ch, target, getter, kind):
    """getter(d) -> float | None. kind: atm or side. returns float or reason string."""
    mut = ch.mut
    days = sorted(ch.ex)
    miss_exact = "no_atm_strike" if kind == "atm" else "no_delta_bracket"
    miss_br = "no_bracketing_expiry" if kind == "atm" else "no_delta_bracket"
    if "M38" in mut and kind != "atm":
        miss_br = miss_exact = "no_bracketing_expiry"
    if target in days:
        if kind == "atm" and getter(target) is None:
            return miss_exact
        if not ch.cov_ok(target):
            return "low_surface_coverage"
        v = getter(target)
        return miss_exact if v is None else v
    lo = [d for d in days if d < target]
    hi = [d for d in days if d > target]
    if not lo or not hi:
        if "M39" in mut and (lo or hi):
            d = lo[-1] if lo else hi[0]
            v = getter(d)
            if v is not None:
                return v
        return "no_bracketing_expiry"
    d1, d2 = lo[-1], hi[0]
    if not ch.cov_ok(d1) or not ch.cov_ok(d2):
        return "no_bracketing_expiry"
    v1, v2 = getter(d1), getter(d2)
    if v1 is None or v2 is None:
        return miss_br
    if "M12" in mut:
        w = (target - d1) / (d2 - d1)
        return v1 + (v2 - v1) * w
    t1, t2, tt = d1 / 365.0, d2 / 365.0, target / 365.0
    w1, w2 = v1 * v1 * t1, v2 * v2 * t2
    return math.sqrt((w1 + (w2 - w1) * (tt - t1) / (t2 - t1)) / tt)


def skew_parts(ch):
    mut = ch.mut
    if "M30" in mut:
        d = min(ch.ex, key=lambda d: (abs(d - 30), d))
        if not ch.cov_ok(d):
            return "low_surface_coverage"
        p, c = ch.side(d, "put"), ch.side(d, "call")
        if p is None or c is None:
            return "no_delta_bracket"
        return p, c
    p = cm_value(ch, 30, lambda d: ch.side(d, "put"), "side")
    if isinstance(p, str):
        return p
    c = cm_value(ch, 30, lambda d: ch.side(d, "call"), "side")
    if isinstance(c, str):
        return c
    if "M31" in mut and len(ch.ex) > 1 and 30 not in ch.ex:
        days = sorted(ch.ex)
        lo = [d for d in days if d < 30]
        hi = [d for d in days if d > 30]
        if lo and hi:
            d1, d2 = lo[-1], hi[0]
            s1 = ch.side(d1, "put") - ch.side(d1, "call")
            s2 = ch.side(d2, "put") - ch.side(d2, "call")
            sk = s1 + (s2 - s1) * (30 - d1) / (d2 - d1)
            return ("M31", sk, p, c)
    return p, c


def labels(ch, req):
    sty = ch.styles
    if ch.used is not None and "M52" not in ch.mut:
        sty = set().union(*[ch.ex[d]["styles"] for d in ch.used])
    L = {EXACT} if "M37" in ch.mut else {APPROX if s == "american" else EXACT for s in sty}
    if req.get("feed_delay_tag") == "delayed" and "M41" not in ch.mut:
        L.add("delayed")
    return sorted(L)


def out(ch, req, status="available", reason=None, code=None, value=None, fired=None, rule=None, extra=None):
    o = {"status": status, "reason": reason, "code": code, "value": value, "fired": fired,
         "labels": labels(ch, req) if status == "available" else [],
         "contract_reasons": ({} if "M48" in ch.mut else dict(sorted(ch.reasons.items()))), "rule": rule}
    if extra:
        o.update(extra)
    return o


def evaluate(fam, inp, mut=frozenset()):
    ch = Chain(inp, mut)
    req = dict(inp["request"])
    dd, dt = DEFAULTS[fam]
    if "M28" in mut:
        dd = {"up": "either", "either": "up"}[dd]
    direction = req.get("direction", dd)
    thr_text = next((req[k] for k in ("at_least", "at_most", "x") if k in req), dt)
    thr = D(thr_text) if thr_text is not None else None
    cut = inp["chain"]["cutoff_ns"]
    prior, store = inp.get("prior"), inp.get("priors_store") or []
    n = int(req.get("prior_sessions", 1))
    if fam in ("V8", "V10", "V11", "V21") or ("M50" in mut and "delta_convention" in req):
        cvv = req.get("delta_convention", "spot")
        if not isinstance(cvv, str):
            return out(ch, req, "invalid_input", code="malformed_type")
        if cvv not in ("spot", "forward"):
            return out(ch, req, "invalid_input", code="convention_not_allowed")
        if fam == "V10" and "M47" not in mut:
            recs = ([prior] if prior is not None else []) + list(store)
            if any(x.get("delta_convention", "spot") != cvv for x in recs):
                return out(ch, req, "invalid_input", code="convention_mismatch")
    try:
        if fam == "V21" and thr is None:
            return out(ch, req, "invalid_input", code="threshold_required")
        if not any(row["why"] is None for e in ch.ex.values() for row in e["rows"].values()):
            # R-106: no contract passes the M1 gates (including an empty chain); M49 reports the coverage reason
            return out(ch, req, "unavailable", "low_surface_coverage" if "M49" in mut else "no_eligible_contract")
        o = _eval(fam, ch, req, direction, thr, prior, store, n, cut, mut)
        if (fam in ("V8", "V10", "V11", "V21") or ("M51" in mut and "delta_convention" in req)) and o["status"] == "available":
            o["value"]["delta_convention"] = req.get("delta_convention", "spot")
        return o
    except ZeroDivisionError:
        return out(ch, req, "unavailable", "zero_denominator")


def _eval(fam, ch, req, direction, thr, prior, store, n, cut, mut):
    if fam == "V4":
        form = req.get("iv_form", "30d" if "M43" in mut else "atm")
        if "M44" in mut and isinstance(form, str):
            form = "30d"
        if "M53" in mut and isinstance(form, str):
            form = form.strip().lower()
        if not isinstance(form, str):
            return out(ch, req, "invalid_input", code="iv_form_not_allowed" if "M54" in mut else "malformed_type")
        if form not in ("atm", "30d"):
            return out(ch, req, "invalid_input", code="iv_form_not_allowed")
        if prior is not None and prior["time_ns"] >= cut and "M26" not in mut:
            return out(ch, req, "invalid_input", code="prior_not_before_cutoff")
        if req["feed_delay_tag"] == "delayed" and req["mode"] == "intraday" and "M40" not in mut:
            return out(ch, req, "invalid_input", code="delayed_feed_tag")
        if form == "30d":
            now = cm_value(ch, 30, lambda d: (ch.atm(d) or (None, None))[1], "atm")
        else:
            el = sorted(ch.ex) if "M42" in mut else [d for d in sorted(ch.ex) if ch.cov_ok(d)]
            if not el:
                now = "low_surface_coverage"
            else:
                a_ = ch.atm(el[0])
                ch.used = {el[0]}
                now = "no_atm_strike" if a_ is None else a_[1]
        if isinstance(now, str):
            return out(ch, req, "unavailable", now)
        now_r = r8(now)
        pv_in = prior["value"] if prior else None
        if "M25" in mut and STATE["last_now"] is not None:
            pv_in = str(STATE["last_now"])
        STATE["last_now"] = now_r
        if pv_in is None:
            return out(ch, req, "unavailable", "no_prior_reading")
        pv = D(pv_in)
        if pv == 0 and "M19" not in mut:
            return out(ch, req, "unavailable", "zero_denominator")
        chg = now_r - pv
        ratio = chg / pv if pv != 0 else D(10 ** 6)
        pct = ratio * 100
        x = chg * 100 if "M27" in mut else pct
        f = fire(direction, x, thr, mut)
        return out(ch, req, value={"now": now_r, "prior": pv, "change_points": chg * 100, "change_ratio": r8(ratio),
                                   "prior_kind": prior["kind"], "iv_form": form}, fired=f,
                   rule={"kind": "pct", "x": x, "thr": thr, "dir": direction})
    if fam == "V5":
        t = {d: cm_value(ch, d, lambda e: (ch.atm(e) or (None, None))[1], "atm") for d in (9, 30, 91)}
        pair = req["pair"].replace("-", "_")
        need = (9, 30) if pair == "9_30" else (30, 91)
        for d in need:
            if isinstance(t[d], str):
                return out(ch, req, "unavailable", t[d])
        if "M29" in mut:
            need2 = {"9_30": (9, 30), "30_91": (9, 91)}[pair]
        else:
            need2 = need
        pairs = {}
        for name, (s, l) in (("9_30", (9, 30)), ("30_91", (30, 91))):
            sp = r8(t[l] - t[s])
            if "M14" in mut:
                sp = r8(t[s] - t[l])
            pairs[name] = {"longer": r8(t[l]), "shorter": r8(t[s]), "spread_points": sp * 100}
        if "M29" in mut:
            s, l = need2
            x = r8(t[l] - t[s]) * 100
        else:
            x = pairs[pair]["spread_points"]
        return out(ch, req, value={"pairs": pairs}, fired=fire(direction, x, thr, mut),
                   rule={"kind": "pts", "x": x, "thr": thr, "dir": direction})
    if fam == "V6":
        if "M15" in mut:
            el = sorted(ch.ex)
        else:
            el = [d for d in sorted(ch.ex) if ch.cov_ok(d)]
        if len(el) < 2:
            return out(ch, req, "unavailable", "fewer_than_two_expiries")
        a1, a2 = ch.atm(el[0]), ch.atm(el[1])
        if a1 is None or a2 is None:
            return out(ch, req, "unavailable", "no_atm_strike")
        sp = r8(a2[1] - a1[1]) * 100
        return out(ch, req, value={"nearest_days": el[0], "second_days": el[1], "spread_points": sp},
                   fired=fire(direction, sp, thr, mut), rule={"kind": "pts", "x": sp, "thr": thr, "dir": direction})
    if fam == "V7":
        if any(s["time_ns"] >= cut for s in store) and "M26" not in mut:
            return out(ch, req, "invalid_input", code="prior_not_before_cutoff")
        getter = lambda e: (ch.atm(e) or (None, None))[1]
        t30 = cm_value(ch, 30, getter, "atm")
        t91 = cm_value(ch, 91, getter, "atm")
        for v in (t30, t91):
            if isinstance(v, str):
                return out(ch, req, "unavailable", v)
        gap = r8(t91 - t30)
        if "M14" in mut:
            gap = r8(t30 - t91)
        if not store:
            return out(ch, req, "unavailable", "no_prior_reading")
        if len(store) < n:
            return out(ch, req, "unavailable", "insufficient_history")
        refi = store[0 if "M22" in mut else n - 1]["value_int"]
        ref = D(refi) / D(10 ** 8)
        chg = (gap - ref) * 100
        pri = [{"session_id": s["session_id"], "gap": D(s["value_int"]) / D(10 ** 8)} for s in store[:n]]
        return out(ch, req, value={"now": gap, "priors": pri, "gap_change_points": chg},
                   fired=fire(direction, chg, thr, mut), rule={"kind": "pts", "x": chg, "thr": thr, "dir": direction})
    # skew-based families
    if fam == "V10":
        kind = req.get("prior_kind", "frame")
        if "M21" in mut:
            kind = "session" if kind == "frame" else "frame"
        if ((prior is not None and prior["time_ns"] >= cut) or any(s["time_ns"] >= cut for s in store)) and "M26" not in mut:
            return out(ch, req, "invalid_input", code="prior_not_before_cutoff")
    atm_first = None
    if fam in ("V11", "V21"):
        atm_first = cm_value(ch, 30, lambda d: (ch.atm(d) or (None, None))[1], "atm")
        if isinstance(atm_first, str):
            return out(ch, req, "unavailable", atm_first)
    pc = skew_parts(ch)
    if isinstance(pc, str):
        return out(ch, req, "unavailable", pc)
    if isinstance(pc, tuple) and pc and pc[0] == "M31":
        _, sk, p, c = pc
    else:
        p, c = pc
        sk = None
    if "M13" in mut:
        skew = c - p
    else:
        skew = p - c
    if sk is not None:
        skew = sk
    if fam == "V8":
        sp = r8(skew) * 100
        return out(ch, req, value={"put25_iv": r8(p), "call25_iv": r8(c), "skew_points": sp, "tenor": 30},
                   fired=fire(direction, sp, thr, mut), rule={"kind": "pts", "x": sp, "thr": thr, "dir": direction})
    if fam == "V10":
        now = r8(skew)
        if kind == "frame":
            if prior is None:
                return out(ch, req, "unavailable", "no_prior_reading")
            ref = D(prior["value"])
            pri = []
        else:
            if not store:
                return out(ch, req, "unavailable", "no_prior_reading")
            if len(store) < n:
                return out(ch, req, "unavailable", "insufficient_history")
            pri = [{"session_id": s["session_id"], "gap": D(s["value_int"]) / D(10 ** 8)} for s in store[:n]]
            ref = D(store[0 if "M22" in mut else n - 1]["value_int"]) / D(10 ** 8)
        chg = (now - ref) * 100
        if "M20" in mut:
            sn = 1 if now >= 0 else -1
            sp_ = 1 if ref >= 0 else -1
            changed = sn != sp_
        else:
            sn, sp_ = sgn(now), sgn(ref)
            changed = sn != 0 and sp_ != 0 and sn != sp_
        if req.get("condition", "change") == "change":
            f = fire(direction, chg, thr, mut)
            rule = {"kind": "pts", "x": chg, "thr": thr, "dir": direction}
        else:
            f = changed
            rule = {"kind": "sign", "now": now, "ref": ref}
        return out(ch, req, value={"now": now, "priors": pri, "change_points": chg, "sign_now": sn, "sign_prior": sp_,
                                   "sign_changed": changed}, fired=f, rule=rule)
    atm = atm_first
    if fam == "V11":
        w = (p + c) if "M16" in mut else (p + c) / 2
        cur = r8(w - atm) * 100
        return out(ch, req, value={"wings_mid": r8((p + c) / 2), "atm_iv": r8(atm), "curvature_points": cur},
                   fired=fire(direction, cur, thr, mut), rule={"kind": "pts", "x": cur, "thr": thr, "dir": direction})
    if fam == "V21":
        pd_, cd_ = p - atm, c - atm
        if "M17" in mut:
            pd_, cd_ = cd_, pd_
        if r8(cd_) == 0 and "M18" not in mut:
            return out(ch, req, "unavailable", "zero_denominator")
        ratio = r8(pd_ / cd_) if cd_ != 0 else D(10 ** 6)
        f = ratio >= thr if direction == "up" else ratio <= thr
        if "M23" in mut:
            f = ratio >= thr
        if "M24" in mut:
            f = ratio > thr if direction == "up" else ratio < thr
        return out(ch, req, value={"put_distance": r8(p - atm) * 100, "call_distance": r8(c - atm) * 100, "ratio": ratio}, fired=f,
                   rule={"kind": "ratio", "x": ratio, "thr": thr, "dir": direction},
                   extra={"call_distance": D(r8(c - atm))})
    raise KeyError(fam)
