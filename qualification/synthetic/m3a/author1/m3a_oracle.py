"""M3a fixture oracle: G1 smile/term surface, G2 25-delta oracle, G3 tenor oracle.
SYNTHETIC. Python stdlib only (decimal 60+ digits, fractions). Never imports the library under test.
Expected values come from the TRUE sigma of each contract (stated, 6 decimals), not from any solver."""
import json, hashlib
from decimal import Decimal as D, getcontext, localcontext, ROUND_HALF_EVEN
from fractions import Fraction as Fr

getcontext().prec = 60
SEED = 20261030
LABEL = ("mock-data qualification only: passed on independently authored synthetic fixtures "
         "and synthetic workloads, Windows x64, CPython 3.12")
EXACT = "exact-model"
APPROX = "approximate: European model on an American-style contract"
CUT = 36000000000000          # cutoff_ns (non-negative int)
STALE = 10000000000           # stale_limit_ns (10 s, M1 Q4)
TOL = {"iv": "0.00003", "forward": "0.000001", "points": "0.005"}
Q4 = D("0.0001")
Q6 = D("0.000001")
Q8 = D("1e-8")


def _atan_inv(n):
    x = D(1) / n
    x2 = x * x
    term = x
    s = x
    k = 1
    while abs(term) > D(10) ** -70:
        term = -term * x2
        k += 2
        s += term / k
    return s


PI = 16 * _atan_inv(5) - 4 * _atan_inv(239)


def erf(z):
    with localcontext() as c:
        c.prec = 100
        z = D(z)
        z2 = z * z
        term = z
        s = z
        n = 0
        while True:
            n += 1
            term = -term * z2 / n
            t = term / (2 * n + 1)
            s += t
            if abs(t) < D(10) ** -85 and n > 5:
                break
        return 2 * s / PI.sqrt()


def ncdf(x):
    x = D(x)
    assert abs(x) < 9, x
    return (1 + erf(x / D(2).sqrt())) / 2


def phi(x):
    return (-(x * x) / 2).exp() / (2 * PI).sqrt()


def d1d2(S, K, T, r, q, s):
    sd = s * T.sqrt()
    d1 = ((S / K).ln() + (r - q + s * s / 2) * T) / sd
    return d1, d1 - sd


def bsm(S, K, T, r, q, s, right):
    d1, d2 = d1d2(S, K, T, r, q, s)
    if right == "call":
        return S * (-q * T).exp() * ncdf(d1) - K * (-r * T).exp() * ncdf(d2)
    return K * (-r * T).exp() * ncdf(-d2) - S * (-q * T).exp() * ncdf(-d1)


def vega(S, K, T, r, q, s):
    d1, _ = d1d2(S, K, T, r, q, s)
    return S * (-q * T).exp() * phi(d1) * T.sqrt()


def delta_abs(S, K, T, r, q, s, right, conv="spot"):
    d1, _ = d1d2(S, K, T, r, q, s)
    e = D(1) if conv == "forward" else (-q * T).exp()
    return e * ncdf(d1) if right == "call" else e * ncdf(-d1)


def fwd(S, r, q, N):
    return S * ((r - q) * D(N) / 365).exp()


def f8(x):
    return format(D(x).quantize(Q8, rounding=ROUND_HALF_EVEN), "f")


def f4(x):
    return format(D(x).quantize(Q4, rounding=ROUND_HALF_EVEN), "f")


def q6(x):
    return D(x).quantize(Q6, rounding=ROUND_HALF_EVEN)


def fK(K):
    return format(D(K), "f")


def cid(N, right, K):
    return "%dd-%s-%s" % (N, "C" if right == "call" else "P", fK(K))


def bounds(S, K, T, r, q, right):
    dq, dr = (-q * T).exp(), (-r * T).exp()
    if right == "call":
        return max(S * dq - K * dr, D(0)), S * dq
    return max(K * dr - S * dq, D(0)), K * dr


def solver_gate(rec, S, r, q):
    T = D(rec["expiry_days"]) / 365
    K = D(rec["strike"])
    mid = (D(rec["bid"]) + D(rec["ask"])) / 2
    lo, hi = bounds(S, K, T, r, q, rec["right"])
    if mid < lo or mid > hi:
        return "price_out_of_bounds"      # strictly outside (Q-13 ruled from the solver text)
    if mid == hi:
        return "upper_asymptote"          # exactly the upper bound
    return None                           # exactly the lower bound is available (IV 0.0), not a failure


def mk(S, r, q, N, K, right, sig, style="european", cond="regular", mode=None, cut=CUT, bound=None):
    """One ChainContract record (exactly the M1 field set) plus truth info."""
    T = D(N) / 365
    mid = bsm(S, K, T, r, q, sig, right)
    if bound:
        lo_, hi_ = bounds(S, K, T, r, q, right)
        mid = {"below": (lo_ / 2).quantize(Q4), "above": (hi_ * D("1.01")).quantize(Q4),
               "at_lower": lo_.quantize(Q4), "at_upper": hi_.quantize(Q4)}[bound]
    h = D("0.001")
    bid = (mid - h).quantize(Q4, rounding=ROUND_HALF_EVEN)
    ask = (mid + h).quantize(Q4, rounding=ROUND_HALF_EVEN)
    b, a = format(bid, "f"), format(ask, "f")
    ev = cut - 2 * 10 ** 9
    if mode == "stale":
        ev = cut - 60 * 10 ** 9
    elif mode == "crossed":
        b, a = a, b
    elif mode == "locked":
        b = a = format(mid.quantize(Q4, rounding=ROUND_HALF_EVEN), "f")
    elif mode == "neg":
        b = "-0.0100"
    elif mode == "zerobid":
        b = "0.0000"
    elif mode == "nobid":
        b = None
    elif mode == "noask":
        a = None
    elif mode == "noquote":
        ev = cut + 10 ** 9
    rec = {"contract_id": cid(N, right, K), "expiry_days": N, "right": right, "strike": fK(K),
           "bid": b, "ask": a, "event_ns": ev, "known_at_ns": None, "style": style, "condition": cond}
    info = {"sigma": sig, "mid": mid, "vega": vega(S, K, T, r, q, sig),
            "delta": delta_abs(S, K, T, r, q, sig, right), "N": N, "K": K, "right": right}
    return rec, info


def smile(F, a, b, c, put_shift=D(0)):
    """G1: sigma(k,T)=a+b k+c k^2, k=ln(K/F); stated to 6 decimals; put side shifted by put_shift."""
    def sig(K, right):
        k = (D(K) / F).ln()
        s = q6(a + b * k + c * k * k + (put_shift if right == "put" else D(0)))
        assert s >= D("0.03"), (K, s)
        return s
    return sig


def flat(a, put_shift=D(0)):
    def sig(K, right):
        return q6(a + (put_shift if right == "put" else D(0)))
    return sig


def grid(F, N, a, step, j_lo, j_hi, off=D(0), tick=D("0.01")):
    sd = a * (D(N) / 365).sqrt()
    out = []
    for j in range(j_lo, j_hi + 1):
        K = (F * ((D(j) + off) * step * sd).exp()).quantize(tick, rounding=ROUND_HALF_EVEN)
        if K not in out:
            out.append(K)
    return sorted(out)


def build(S, r, q, exps):
    """exps: list of dicts N, K (list of D), sig (callable), style, over {(Kstr,right): {...}}."""
    recs, truth = [], {}
    for e in exps:
        for K in e["K"]:
            for right in ("call", "put"):
                ov = e.get("over", {}).get((fK(K), right), {})
                if ov.get("drop"):
                    continue
                sg = ov.get("sigma") or e["sig"](K, right)
                st = ov["style"] if "style" in ov else e.get("style", "european")
                rec, info = mk(S, r, q, e["N"], K, right, sg, st, ov.get("cond", "regular"), ov.get("mode"), CUT, ov.get("bound"))
                recs.append(rec)
                truth[rec["contract_id"]] = info
    return recs, truth


def default_params(**kw):
    p = {"mode": "intraday", "lane": "stock", "stale_limit_ns": STALE, "feed_delay_tag": "live",
         "evaluation_ns": CUT, "tenors": [9, 30, 91], "delta_target": "0.25",
         "min_strikes": 4, "min_coverage": "3/5", "delta_convention": "spot"}
    p.update(kw)
    return p


# ---------------------------------------------------------------- oracle
def gate(rec, F, nearest, cut, stale):
    if rec["event_ns"] > cut or (rec["known_at_ns"] is not None and rec["known_at_ns"] > cut):
        return "no_quote"
    if rec["condition"] != "regular":
        return "excluded_condition"
    b, a = rec["bid"], rec["ask"]
    if b is None or a is None:
        return "invalid_quote"
    b, a = D(b), D(a)
    if b <= 0 or a <= 0:
        return "invalid_quote"
    if b > a:
        return "crossed_market"
    if b == a:
        return "locked_market"
    if cut - rec["event_ns"] > stale:
        return "stale_quote"
    if rec["style"] not in ("european", "american"):
        return "style_unknown"
    K = D(rec["strike"])
    if rec["style"] == "american" and K != nearest and (
            (rec["right"] == "call" and K < F) or (rec["right"] == "put" and K > F)):
        return "american_itm"
    return None


def parse_frac(s):
    n, d = s.split("/")
    return int(n), int(d)


def _frs(x):
    x = Fr(x)
    return "%d/%d" % (x.numerator, x.denominator)


def compute(S, r, q, recs, truth, params, cut=CUT):
    S, r, q = D(S), D(r), D(q)
    target = D(params["delta_target"])
    conv = params.get("delta_convention", "spot")
    mn, (cn, cd) = params["min_strikes"], parse_frac(params["min_coverage"])
    expn = sorted({c["expiry_days"] for c in recs})
    reasons = {}
    frame = {"expiries": {}, "tenors": {}, "coverage": {"per_expiry": {}}, "g2": {}, "diverge": False}
    atm_of = {}
    cb = {"atm": set(), "p25": set(), "c25": set(), "tenors": set()}
    styles = set()
    for N in expn:
        T = D(N) / 365
        F = fwd(S, r, q, N)
        cs = [c for c in recs if c["expiry_days"] == N]
        nearest = min({D(c["strike"]) for c in cs}, key=lambda K: (abs(K - F), K))
        elig = {}
        for c in cs:
            g = gate(c, F, nearest, cut, params["stale_limit_ns"]) or solver_gate(c, S, r, q)
            if g:
                reasons[g] = reasons.get(g, 0) + 1
            else:
                elig[(D(c["strike"]), c["right"])] = c
                styles.add(c["style"])
        L = len({D(c["strike"]) for c in cs})                  # listed: any record at that strike (Q-01 pick)
        E = len({K for (K, _) in elig})                        # eligible: >= 1 eligible quote, either right (Q-01 pick)
        both = sorted(K for K in {K for (K, _) in elig} if (K, "call") in elig and (K, "put") in elig)
        if E != len(both):
            frame["diverge"] = True
        frame["coverage"]["per_expiry"][str(N)] = {"listed_strikes": L, "eligible_strikes": E}
        ex = {"forward": f8(F)}
        if not both:
            ex.update(status="unavailable", reason="no_atm_strike")
            frame["expiries"][N] = ex
            continue
        near_ok = all(sum(1 for (K, rt) in elig if rt == side and abs(K - F) <= F / 10) >= 2
                      for side in ("call", "put"))
        if E < mn or E * cd < cn * L or not near_ok:
            ex.update(status="unavailable", reason="low_surface_coverage")
            frame["expiries"][N] = ex
            continue
        Ka = min(both, key=lambda K: (abs(K - F), K))
        cc, pc = elig[(Ka, "call")], elig[(Ka, "put")]
        sc, sp = truth[cc["contract_id"]]["sigma"], truth[pc["contract_id"]]["sigma"]
        atm = (sc + sp) / 2
        ex.update(status="available", reason=None, atm_iv=f8(atm), atm_strike=fK(Ka))
        lab = APPROX if "american" in (cc["style"], pc["style"]) else EXACT
        cb["atm"].update([cc["contract_id"], pc["contract_id"]])
        atm_of[N] = {"atm": atm, "label": lab, "legs": [cc["contract_id"], pc["contract_id"]]}
        for side in ("put", "call"):
            seq = sorted(K for (K, rt) in elig if rt == side)
            seq = [K for K in seq if K <= Ka][::-1] if side == "put" else [K for K in seq if K >= Ka]
            pts = []
            for K in seq:
                c = elig[(K, side)]
                tr = truth[c["contract_id"]]
                pts.append((K, tr["sigma"], delta_abs(S, K, T, r, q, tr["sigma"], side, conv), c["contract_id"]))
            frame["g2"].setdefault(str(N), {})[side] = [
                {"strike": fK(K), "sigma": str(sg), "delta": format(dl.quantize(D("1e-30")), "f")}
                for K, sg, dl, _ in pts]
            res = {"status": "unavailable", "reason": "no_delta_bracket", "value": None}
            for i in range(len(pts) - 1):
                fi, fj = pts[i][2] - target, pts[i + 1][2] - target
                if (fi <= 0 <= fj) or (fj <= 0 <= fi):
                    di, dj = pts[i][2], pts[i + 1][2]
                    w = D(0) if di == dj else (target - di) / (dj - di)
                    iv = pts[i][1] + w * (pts[i + 1][1] - pts[i][1])
                    if di != dj:
                        qd = D("1e-40")
                        a_, b_ = Fr(di.quantize(qd)), Fr(dj.quantize(qd))
                        fr = Fr(pts[i][1]) + (Fr(target) - a_) / (b_ - a_) * (Fr(pts[i + 1][1]) - Fr(pts[i][1]))
                    else:
                        fr = Fr(pts[i][1])
                    res = {"status": "available", "reason": None, "value": f8(iv),
                           "bracket": [fK(pts[i][0]), fK(pts[i + 1][0])], "weight": f8(w),
                           "iv_rational": _frs(fr), "legs": [pts[i][3], pts[i + 1][3]],
                           "on_strike": bool(fi == 0 or fj == 0)}
                    break
            ex[side + "25_iv"] = res
            if res["status"] == "available":
                cb[side[0] + "25"].update(res["legs"])
        frame["expiries"][N] = ex
    for t in params["tenors"]:
        res = {"status": "unavailable", "reason": "no_bracketing_expiry", "iv": None, "method": None,
               "expiries_used": None}
        if t in expn:
            ex = frame["expiries"][t]
            if ex["status"] == "available":
                a_ = atm_of[t]
                res = {"status": "available", "reason": None, "iv": ex["atm_iv"], "method": "as_is",
                       "expiries_used": [t], "legs": a_["legs"], "label": a_["label"],
                       "w_rational": _frs(Fr(a_["atm"]) ** 2 * t / 365), "iv2_rational": _frs(Fr(a_["atm"]) ** 2)}
            else:
                res["reason"] = ex["reason"]
        else:
            lo = [n for n in expn if n < t]
            hi = [n for n in expn if n > t]
            if lo and hi:
                n1, n2 = lo[-1], hi[0]
                if frame["expiries"][n1]["status"] == "available" and frame["expiries"][n2]["status"] == "available":
                    s1, s2 = atm_of[n1]["atm"], atm_of[n2]["atm"]
                    w1, w2 = Fr(s1) ** 2 * n1 / 365, Fr(s2) ** 2 * n2 / 365
                    wt = w1 + (w2 - w1) * Fr(t - n1, n2 - n1)
                    iv2 = wt * 365 / t
                    iv = (D(iv2.numerator) / D(iv2.denominator)).sqrt()
                    lab = APPROX if APPROX in (atm_of[n1]["label"], atm_of[n2]["label"]) else EXACT
                    res = {"status": "available", "reason": None, "iv": f8(iv), "method": "variance_interpolation",
                           "expiries_used": [n1, n2], "legs": atm_of[n1]["legs"] + atm_of[n2]["legs"],
                           "label": lab, "w_rational": _frs(wt), "iv2_rational": _frs(iv2)}
        frame["tenors"][t] = res
        if res["status"] == "available":
            cb["tenors"].update(res["legs"])
    avail = [N for N in expn if frame["expiries"][N]["status"] == "available"]
    # R-141: available only when every listed expiry, every requested tenor and every 25-delta side is available;
    # reason = first failing item: expiries ascending, tenors ascending, then sides (put, call) of available expiries.
    fr_reason = None
    for N in expn:
        if frame["expiries"][N]["status"] != "available":
            fr_reason = frame["expiries"][N]["reason"]; break
    if fr_reason is None:
        for t in sorted(params["tenors"]):
            if frame["tenors"][t]["status"] != "available":
                fr_reason = frame["tenors"][t]["reason"]; break
    if fr_reason is None:
        for N in expn:
            for sd in ("put", "call"):
                if frame["expiries"][N][sd + "25_iv"]["status"] != "available":
                    fr_reason = frame["expiries"][N][sd + "25_iv"]["reason"]; break
            if fr_reason:
                break
    if not expn:
        fr_reason = "no_eligible_contract"          # R-106
    frame["frame_status"] = "unavailable" if fr_reason else "available"
    frame["frame_reason"] = fr_reason
    frame["cb"] = {k: sorted(v) for k, v in cb.items()}
    frame["coverage"]["contract_reasons"] = dict(sorted(reasons.items()))
    cov = frame["coverage"]
    cov["listed_strikes"] = sum(v["listed_strikes"] for v in cov["per_expiry"].values())
    cov["eligible_strikes"] = sum(v["eligible_strikes"] for v in cov["per_expiry"].values())
    frame["styles"] = sorted(styles)
    return frame


def min_vega(frame, truth, want=None):
    toks = {"atm", "p25", "c25", "tenors"} if want is None else (set(want) & {"atm", "p25", "c25", "tenors"})
    ids = set()
    for t in toks:
        ids.update(frame["cb"][t])
    vs = [truth[c]["vega"] for c in ids]
    return min(vs) if vs else None


# ---------------------------------------------------------------- row assembly
def expected_items(frame, want):
    """want: set of tokens: fwd atm p25 c25 exp tenors cov labels."""
    items = {"expiries": {}, "tenors": {}}
    for N, ex in frame["expiries"].items():
        it = {}
        if want & {"exp", "atm", "fwd", "p25", "c25"}:
            it["status"], it["reason"] = ex["status"], ex["reason"]
        if ex["status"] == "available":
            if "fwd" in want:
                it["forward"] = ex["forward"]
            if "atm" in want:
                it["atm_iv"] = ex["atm_iv"]
            for tok, key in (("p25", "put25_iv"), ("c25", "call25_iv")):
                if tok in want:
                    it[key] = {"status": ex[key]["status"], "reason": ex[key]["reason"], "value": ex[key]["value"]}
        if it:
            items["expiries"][str(N)] = it
    if "tenors" in want:
        for t, tr in frame["tenors"].items():
            items["tenors"][str(t)] = {k: tr[k] for k in ("status", "reason", "iv", "method", "expiries_used")}
    for k in ("expiries", "tenors"):
        if not items[k]:
            del items[k]
    return items


def get_focus(items, focus):
    cur = items
    for part in focus.split("."):
        cur = cur[part]
    return cur


RATIFIED = {"Q-13", "Q-01", "Q-02", "Q-05", "Q-06", "Q-08", "Q-09", "Q-10", "Q-11", "Q-12"}   # PO ruling batch 2


def _rs(pending):
    return "RULED" if (not pending or pending["question"] in RATIFIED) else "PENDING-RULING"


def make_row(rid, family, design_ref, rulings, case, S, r, q, recs, truth, params, want, focus,
             derivation, tags=(), pending=None, g2=False, labels="auto", gating=None, keep_cov=False):
    want = set(want)
    params = dict(params)
    if "tenors" not in want:      # R-141: a request whose tenors cannot be served makes the frame unavailable; serve the listed expiries
        params["tenors"] = sorted({c["expiry_days"] for c in recs}) or [30]
    frame = compute(S, r, q, recs, truth, params)
    tags = list(tags)
    if False:
        want.discard("cov")
        want.add("creasons")
        tags.append("cov_counts_not_asserted:Q-01")
    items = expected_items(frame, want)
    delayed = params["feed_delay_tag"] == "delayed"
    if labels == "auto":
        if frame["frame_status"] == "available":
            lab = sorted({APPROX if st == "american" else EXACT for st in frame["styles"]} | ({"delayed"} if delayed else set()))   # ASCII sort incl. delayed
        else:
            lab = []          # Q-05/Q-06 ruled: mixed frame carries both labels sorted; unavailable result labels = []
    else:
        lab = labels
    if "labels" not in want:
        lab = None
    status, reason, value = frame["frame_status"], frame["frame_reason"], None     # R-141, R-142: frame level, value null
    if focus == "frame":
        focus_item = {"status": status, "reason": reason}
    else:
        foc = get_focus(items, focus)
        if isinstance(foc, str):
            focus_item = {"status": "available", "reason": None, "value": foc}
        elif "iv" in foc:
            focus_item = {"status": foc["status"], "reason": foc["reason"], "value": foc["iv"]}
        elif "value" in foc:
            focus_item = {"status": foc["status"], "reason": foc["reason"], "value": foc["value"]}
        else:
            focus_item = {"status": foc["status"], "reason": foc["reason"], "value": foc.get("atm_iv") or foc.get("forward")}
    mv = min_vega(frame, truth, want)
    gate_ok = mv is None or mv >= 4
    if gating is not None:
        gate_ok = gating and gate_ok
    exp = {"output_id": "M3A-0", "status": status, "reason": reason, "code": None, "value": value,
           "tolerance": TOL, "frame": items, "focus_item": focus_item, "labels": lab, "echo": {"delta_convention": params.get("delta_convention", "spot")},
           "coverage": (frame["coverage"] if "cov" in want else
                        {"contract_reasons": frame["coverage"]["contract_reasons"]} if "creasons" in want else None)}
    row = {"id": rid, "family": family, "design_ref": design_ref, "rulings": list(rulings),
           "ruling_status": _rs(pending), "case": case,
           "inputs": {"chain": {"contracts": recs, "spot": format(S, "f"), "rate": format(r, "f"),
                                "dividend_yield": format(q, "f"), "cutoff_ns": CUT}},
           "params": params, "focus": focus, "expected": exp, "gating": bool(gate_ok), "asserted": sorted(want),
           "oracle": {"sigma": {k: str(v["sigma"]) for k, v in truth.items()},
                      "min_contrib_vega": None if mv is None else format(mv.quantize(D("0.01")), "f")},
           "derivation": derivation,
           "tags": sorted(set(tags) | ({"PENDING-RULING"} if _rs(pending) != "RULED" else set()) |
                          (set() if gate_ok else {"non-gating:vega<4"}))}
    if pending:
        row["ruling" if _rs(pending) == "RULED" else "pending"] = pending
    if g2:
        row["oracle"]["g2"] = frame["g2"]
        row["oracle"]["brackets"] = {
            str(N): {s: {k: ex[s + "25_iv"].get(k) for k in ("bracket", "weight", "iv_rational", "on_strike")}
                     for s in ("put", "call") if ex[s + "25_iv"]["status"] == "available"}
            for N, ex in frame["expiries"].items() if ex["status"] == "available"}
    if "tenors" in want:
        row["oracle"]["tenor_rationals"] = {
            str(t): {k: tr.get(k) for k in ("w_rational", "iv2_rational")}
            for t, tr in frame["tenors"].items() if tr["status"] == "available"}
    return row


def clone_row(row, rid, conv, suffix, omit=False, tags=(), extra_rulings=("OD-3",)):
    """Same chain and quotes, other delta convention (or the key omitted = default spot); recomputed by the oracle."""
    ch = row["inputs"]["chain"]
    S, r, q = D(ch["spot"]), D(ch["rate"]), D(ch["dividend_yield"])
    recs = ch["contracts"]
    truth = {}
    for c in recs:
        sg = D(row["oracle"]["sigma"][c["contract_id"]])
        truth[c["contract_id"]] = {"sigma": sg, "vega": vega(S, D(c["strike"]), D(c["expiry_days"]) / 365, r, q, sg)}
    P = dict(row["params"])
    if omit:
        P.pop("delta_convention", None)
    else:
        P["delta_convention"] = conv
    return make_row(rid, row["family"], row["design_ref"], list(row["rulings"]) + list(extra_rulings), row["case"] + suffix, S, r, q, recs, truth, P,
                    set(row["asserted"]), row["focus"], row["derivation"] + " [convention %s]" % (conv if not omit else "omitted -> spot"),
                    tags=[t for t in row["tags"] if not t.startswith("near_threshold") and t != "target_on_strike"] + list(tags), g2="g2" in row["oracle"])


def invalid_row(rid, family, design_ref, rulings, case, S, r, q, recs, params, code, derivation,
                tags=(), pending=None):
    row = {"id": rid, "family": family, "design_ref": design_ref, "rulings": list(rulings),
           "ruling_status": _rs(pending), "case": case,
           "inputs": {"chain": {"contracts": recs, "spot": format(S, "f"), "rate": format(r, "f"),
                                "dividend_yield": format(q, "f"), "cutoff_ns": CUT}},
           "params": params, "focus": "frame",
           "expected": {"output_id": "M3A-0", "status": "invalid_input", "reason": None, "code": code,
                        "value": None, "tolerance": TOL, "frame": None, "focus_item": None, "labels": None, "coverage": None},
           "gating": True, "oracle": {}, "derivation": derivation,
           "tags": sorted(set(tags) | ({"PENDING-RULING"} if _rs(pending) != "RULED" else set()))}
    if pending:
        row["ruling" if _rs(pending) == "RULED" else "pending"] = pending
    return row


def header(family, rows, generator, note):
    return {"provenance": "SYNTHETIC", "qualification_label": LABEL, "generator": generator, "seed": SEED,
            "schema_version": 1, "family": family, "output_id": "M3A-0", "note": note,
            "tolerance": TOL, "model_labels": {"exact": EXACT, "approximate": APPROX},
            "encoding": "m2-tagged-v1: no non-JSON type is needed here (decimals are strings, times are integer ns)",
            "closed_reasons": ["no_eligible_contract", "no_atm_strike", "no_bracketing_expiry", "no_delta_bracket", "low_surface_coverage",
                               "price_out_of_bounds", "upper_asymptote", "sigma_cap", "precision_exhausted",
                               "bound_precision", "iteration_budget"],
            "contract_reasons": ["no_quote", "excluded_condition", "invalid_quote", "crossed_market",
                                 "locked_market", "stale_quote", "american_itm", "style_unknown"],
            "row_count": len(rows)}


def write_dataset(path, hdr, rows):
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate ids"
    lines = [json.dumps(r, sort_keys=True, separators=(",", ":"), ensure_ascii=True) for r in rows]
    h = json.dumps(hdr, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    body = h[:-1] + ',"rows":[\n' + ",\n".join(lines) + "\n]}\n"
    with open(path, "w", newline="\n", encoding="ascii") as f:
        f.write(body)
    return hashlib.sha256(body.encode("ascii")).hexdigest()


def out_dir(argv):
    return argv[argv.index("--out") + 1] if "--out" in argv else "."
