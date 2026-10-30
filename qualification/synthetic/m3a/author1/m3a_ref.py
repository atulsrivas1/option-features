"""Independent SECOND implementation of the M3A-0 rules (author 1). SYNTHETIC.
Works from the QUOTES only (like a library would): midpoints are inverted to IV by this file own bisection
(float, erfc based), then ATM / coverage / 25-delta / tenor are recomputed with float and Fraction arithmetic.
It shares no code with m3a_oracle.py (which works from the stated true sigma with 60-digit decimals).
Mutation switches (set M) turn single rules wrong; m3a_mutants.py runs them."""
import math
from fractions import Fraction as Fr

APPROX = "approximate: European model on an American-style contract"
EXACT = "exact-model"


def Nc(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def bs(S, K, T, r, q, s, right):
    sd = s * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * s * s) * T) / sd
    d2 = d1 - sd
    if right == "call":
        return S * math.exp(-q * T) * Nc(d1) - K * math.exp(-r * T) * Nc(d2)
    return K * math.exp(-r * T) * Nc(-d2) - S * math.exp(-q * T) * Nc(-d1)


def invert(S, K, T, r, q, price, right):
    lo, hi = 1e-6, 8.0
    for _ in range(100):
        m = 0.5 * (lo + hi)
        if bs(S, K, T, r, q, m, right) < price:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def vega_f(S, K, T, r, q, s):
    d1 = (math.log(S / K) + (r - q + 0.5 * s * s) * T) / (s * math.sqrt(T))
    return S * math.exp(-q * T) * math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi) * math.sqrt(T)


def dlt(S, K, T, r, q, s, right, M, conv="spot"):
    d1 = (math.log(S / K) + (r - q + 0.5 * s * s) * T) / (s * math.sqrt(T))
    eq = 1.0 if ("fwd_delta" in M or conv == "forward") else math.exp(-q * T)
    if right == "call":
        return eq * Nc(d1)
    if "put_from_call" in M:
        return 1.0 - eq * Nc(d1)
    return eq * Nc(-d1)


_IVC = {}


def parse(row):
    ch = row["inputs"]["chain"]
    out = []
    for c in ch["contracts"]:
        out.append(dict(c, K=Fr(c["strike"]), b=None if c["bid"] is None else Fr(c["bid"]),
                        a=None if c["ask"] is None else Fr(c["ask"])))
    return out


def ivs(row, cs, key="mid"):
    ck = (row["id"], key)
    if ck in _IVC:
        return _IVC[ck]
    ch = row["inputs"]["chain"]
    S, r, q = float(Fr(ch["spot"])), float(Fr(ch["rate"])), float(Fr(ch["dividend_yield"]))
    res = {}
    for c in cs:
        if c["b"] is None or c["a"] is None or c["a"] <= 0:
            continue
        px = float((c["b"] + c["a"]) / 2) if key == "mid" else float(c["a"])
        if px <= 0:
            continue
        T = c["expiry_days"] / 365.0
        res[c["contract_id"]] = invert(S, float(c["K"]), T, r, q, px, c["right"])
    _IVC[ck] = res
    return res


def run(row, M=frozenset()):
    try:
        return _run(row, M)
    except ZeroDivisionError:
        return {"invalid": None, "crash": True}


def _run(row, M=frozenset()):
    ch, P = row["inputs"]["chain"], row["params"]
    cs = parse(row)
    for c in cs:
        e = c["expiry_days"]
        if isinstance(e, bool) or not isinstance(e, int):
            return {"invalid": "malformed_type"}
        if e < (2 if "min_days_2" in M else 1) and not ("allow_zero" in M and e == 0):
            if "struct_last" in M:
                cs = [x for x in cs if isinstance(x["expiry_days"], int) and x["expiry_days"] >= 1]
                break
            return {"invalid": "bad_expiry"}
    S, r, q = float(Fr(ch["spot"])), float(Fr(ch["rate"])), float(Fr(ch["dividend_yield"]))
    if "fwd_noq" in M:
        q_f = 0.0
    else:
        q_f = q
    cut, stale = ch["cutoff_ns"], P["stale_limit_ns"]
    mn = P["min_strikes"]
    cn, cd = [int(x) for x in P["min_coverage"].split("/")]
    if "cov_half" in M:
        cn, cd = 1, 2
    target = float(Fr(P["delta_target"]))
    conv = P.get("delta_convention", "spot")
    if "conv_default_forward" in M and "delta_convention" not in P:
        conv = "forward"
    if not isinstance(conv, str):
        if "conv_lenient" not in M:
            return {"invalid": "malformed_type"}
        conv = "spot"
    if conv not in ("spot", "forward"):
        if "conv_lenient" not in M:
            return {"invalid": "convention_not_allowed"}
        conv = "spot"
    if "conv_ignored_spot" in M:
        conv = "spot"
    elif "conv_ignored_forward" in M:
        conv = "forward"
    elif "conv_swapped" in M:
        conv = "forward" if conv == "spot" else "spot"
    iv = ivs(row, cs, "ask" if "price_ask" in M else "mid")
    exps = sorted({c["expiry_days"] for c in cs})
    reasons = {}
    R = {"invalid": None, "expiries": {}, "tenors": {}, "coverage": {"per_expiry": {}}}
    atm_of = {}
    styles = set()
    for N in exps:
        Tn = N / 365.0
        if "fwd_nocarry" in M:
            F = S
        elif "fwd_basis360" in M:
            F = S * math.exp((r - q_f) * N / 360.0)
        else:
            F = S * math.exp((r - q_f) * Tn)
        mine = [c for c in cs if c["expiry_days"] == N]
        allK = sorted({c["K"] for c in mine})
        nearest = min(allK, key=lambda K: (abs(float(K) - F), K))
        elig = {}
        for c in mine:
            why = None
            checks = [
                ("no_quote", lambda c=c: c["event_ns"] > cut and "noquote_counted" not in M),
                ("excluded_condition", lambda c=c: c["condition"] != "regular" and "cond_counted" not in M),
                ("invalid_quote", lambda c=c: c["b"] is None or c["a"] is None or c["b"] <= 0 or c["a"] <= 0),
                ("crossed_market", lambda c=c: c["b"] is not None and c["a"] is not None and c["b"] > c["a"] and "crossed_counted" not in M),
                ("locked_market", lambda c=c: c["b"] is not None and c["a"] is not None and c["b"] == c["a"] and "locked_counted" not in M),
                ("stale_quote", lambda c=c: cut - c["event_ns"] > stale and "stale_counted" not in M),
                ("style_unknown", lambda c=c: c["style"] not in ("european", "american") and "unknown_as_euro" not in M and "quote_gates_only" not in M),
                ("american_itm", lambda c=c: c["style"] == "american" and c["K"] != nearest and "itm_included" not in M and "quote_gates_only" not in M and
                    ((c["right"] == "call" and float(c["K"]) < F) or (c["right"] == "put" and float(c["K"]) > F))),
            ]
            def _solver(c=c):
                if "bounds_ignored" in M or "quote_gates_only" in M:
                    return False
                T_ = N / 365.0
                Kf = float(c["K"])
                mid_ = float((c["b"] + c["a"]) / 2)
                dq, dr = math.exp(-q * T_), math.exp(-r * T_)
                lo, hi = (max(S * dq - Kf * dr, 0.0), S * dq) if c["right"] == "call" else (max(Kf * dr - S * dq, 0.0), Kf * dr)
                why_ = None
                eps_ = 1e-9
                if mid_ < lo - eps_ or mid_ > hi + eps_:
                    why_ = "upper_asymptote" if ("above_is_asym" in M and mid_ > hi) else "price_out_of_bounds"
                elif abs(mid_ - hi) <= eps_:
                    why_ = "upper_asymptote"
                elif abs(mid_ - lo) <= eps_ and "lower_equal_fails" in M:
                    why_ = "price_out_of_bounds"
                if why_:
                    if "bounds_swap" in M:
                        why_ = "upper_asymptote" if why_ == "price_out_of_bounds" else "price_out_of_bounds"
                    c["_sr"] = why_
                    return True
                return False
            checks.append(("solver", _solver))
            if "reason_swap" in M:
                checks[1], checks[5] = checks[5], checks[1]
            for name, f in checks:
                if f():
                    why = c.get("_sr") if name == "solver" else name
                    break
            if why:
                reasons[why] = reasons.get(why, 0) + 1
            elif c["contract_id"] in iv:
                elig[(c["K"], c["right"])] = c
                styles.add(c["style"] if c["style"] in ("european", "american") else "european")
        Ks = {K for (K, _) in elig}
        both = sorted(K for K in Ks if (K, "call") in elig and (K, "put") in elig)
        L = len(allK)
        E = len(Ks)
        if "elig_both" in M:
            E = len(both)
        if "listed_eligible_only" in M:
            L = E
        R["coverage"]["per_expiry"][str(N)] = {"listed_strikes": L, "eligible_strikes": E}
        ex = {"forward": F}
        atm_pool = both
        if "atm_one_right" in M:
            atm_pool = sorted(Ks)
        if "coverage_first" in M and E < mn:
            ex.update(status="unavailable", reason="low_surface_coverage")
            R["expiries"][N] = ex
            continue
        if not atm_pool:
            ex.update(status="unavailable", reason="no_atm_strike")
            R["expiries"][N] = ex
            continue
        near = all(sum(1 for (K, rt) in elig if rt == side and abs(float(K) - F) <= F / 10.0 + 1e-12) >= 2
                   for side in ("call", "put"))
        if "near_off" in M:
            near = True
        ok_min = E >= (mn + 1 if "min_plus1" in M else mn) if "min_off" not in M else True
        ok_ratio = (E * cd > cn * L) if "cov_exclusive" in M else (E * cd >= cn * L)
        if not (ok_min and ok_ratio and near):
            ex.update(status="unavailable", reason="low_surface_coverage")
            R["expiries"][N] = ex
            continue
        if "spot_nearest" in M:
            key = lambda K: (abs(float(K) - S), K)
        elif "tie_high" in M:
            key = lambda K: (abs(float(K) - F), -K)
        else:
            key = lambda K: (abs(float(K) - F), K)
        Ka = min(atm_pool, key=key)
        cc = elig.get((Ka, "call"))
        pc = elig.get((Ka, "put"))
        sc = iv[cc["contract_id"]] if cc else iv[pc["contract_id"]]
        sp = iv[pc["contract_id"]] if pc else sc
        atm = {"call_only": sc, "put_only": sp}.get(next((m for m in ("call_only", "put_only") if m in M), ""), 0.5 * (sc + sp))
        lab = APPROX if "american" in [x["style"] for x in (cc, pc) if x] else EXACT
        atm_of[N] = (atm, lab)
        ex.update(status="available", reason=None, atm=atm)
        for side in ("put", "call"):
            seq = sorted(K for (K, rt) in elig if rt == side)
            seq = [K for K in seq if K <= Ka][::-1] if side == "put" else [K for K in seq if K >= Ka]
            if "scan_inward" in M:
                seq = seq[::-1]
            if "lowest_scan" in M:
                seq = sorted(K for (K, rt) in elig if rt == side)
            pts = []
            for K in seq:
                c = elig[(K, side)]
                s = iv[c["contract_id"]]
                if "delta_atm_iv" in M:
                    s_d = atm
                elif "mean_rights" in M and (K, "call") in elig and (K, "put") in elig:
                    s_d = 0.5 * (iv[elig[(K, "call")]["contract_id"]] + iv[elig[(K, "put")]["contract_id"]])
                    s = s_d
                else:
                    s_d = s
                d = dlt(S, float(K), Tn, r, q, s_d, side, M, conv)
                if "round2" in M:
                    d = round(d, 2)
                pts.append((float(K), s, d))
            found = []
            for i in range(len(pts) - 1):
                fi, fj = pts[i][2] - target, pts[i + 1][2] - target
                if (fi <= 0 <= fj) or (fj <= 0 <= fi):
                    found.append(i)
            res = ("unavailable", "no_delta_bracket", None)
            if found:
                i = found[-1] if "last_crossing" in M else found[0]
                (k1, s1, d1_), (k2, s2, d2_) = pts[i], pts[i + 1]
                w = 0.0 if d1_ == d2_ else (target - d1_) / (d2_ - d1_)
                if "midpoint_w" in M:
                    w = 0.5
                if "iv_linear_strike" in M:
                    Kst = k1 + w * (k2 - k1)
                    w2 = math.log(Kst / k1) / math.log(k2 / k1)
                    v = s1 + w2 * (s2 - s1)
                elif "tv_interp" in M:
                    v = math.sqrt(s1 * s1 + w * (s2 * s2 - s1 * s1))
                elif "nearest_strike" in M:
                    v = s1 if abs(d1_ - target) <= abs(d2_ - target) else s2
                else:
                    v = s1 + w * (s2 - s1)
                res = ("available", None, v)
            elif "extrap" in M and pts:
                best = min(pts, key=lambda p: abs(p[2] - target))
                res = ("available", None, best[1])
            ex[side + "25"] = res
        R["expiries"][N] = ex
    for t in P["tenors"]:
        res = ("unavailable", "no_bracketing_expiry", None, None, None)
        okE = lambda n: R["expiries"][n]["status"] == "available"
        if t in exps and "tenor_exact_ignored" not in M:
            if okE(t):
                res = ("available", None, atm_of[t][0], "as_is", [t])
            else:
                res = ("unavailable", R["expiries"][t]["reason"], None, None, None)
        else:
            lo = [n for n in exps if n < t]
            hi = [n for n in exps if n > t]
            if "tenor_skip_inelig" in M:
                lo = [n for n in lo if okE(n)]
                hi = [n for n in hi if okE(n)]
            if lo and hi:
                n1, n2 = lo[-1], hi[0]
                if okE(n1) and okE(n2):
                    s1, s2 = atm_of[n1][0], atm_of[n2][0]
                    if "tenor_linear_iv" in M:
                        v = s1 + (s2 - s1) * (t - n1) / (n2 - n1)
                    else:
                        w1, w2 = s1 * s1 * n1 / 365.0, s2 * s2 * n2 / 365.0
                        w = w1 + (w2 - w1) * (t - n1) / (n2 - n1)
                        v = math.sqrt(w * 365.0 / t)
                    res = ("available", None, v, "variance_interpolation", [n1, n2])
            elif "tenor_extrap" in M and (lo or hi):
                n1 = lo[-1] if lo else hi[0]
                if okE(n1):
                    res = ("available", None, atm_of[n1][0], "variance_interpolation", [n1])
        R["tenors"][t] = res
    avail = [N for N in exps if R["expiries"][N]["status"] == "available"]
    fr = None
    for n in exps:
        if R["expiries"][n]["status"] != "available":
            fr = R["expiries"][n]["reason"]; break
    if fr is None:
        for t in sorted(P["tenors"]):
            if R["tenors"][t][0] != "available":
                fr = R["tenors"][t][1]; break
    if fr is None:
        for n in exps:
            for sd in ("put25", "call25"):
                if R["expiries"][n][sd][0] != "available":
                    fr = R["expiries"][n][sd][1]; break
            if fr:
                break
    if not exps:
        fr = "no_eligible_contract"
    R["frame_status"] = "unavailable" if fr else "available"
    R["frame_reason"] = fr
    cov = R["coverage"]
    cov["contract_reasons"] = dict(sorted(reasons.items()))
    cov["listed_strikes"] = sum(v["listed_strikes"] for v in cov["per_expiry"].values())
    cov["eligible_strikes"] = sum(v["eligible_strikes"] for v in cov["per_expiry"].values())
    lab = []
    if R["frame_status"] == "available":
        if "label_exact_always" in M:
            ms = {EXACT}
        elif "label_approx_always" in M:
            ms = {APPROX}
        else:
            ms = {APPROX if x == "american" else EXACT for x in styles}
        if P["feed_delay_tag"] == "delayed" and "delayed_missing" not in M:
            ms = ms | {"delayed"}
        lab = sorted(ms)
    R["labels"] = lab
    R["echo"] = {"delta_convention": conv}
    return R


def compare(row, R, tol_iv=3.0001e-5, tol_f=1.0001e-6):
    """Returns list of mismatch strings (empty = row passes)."""
    bad = []
    e = row["expected"]
    if e["status"] == "invalid_input":
        if R.get("invalid") != e["code"]:
            bad.append("code %s != %s" % (R.get("invalid"), e["code"]))
        return bad
    if R.get("invalid"):
        return ["invalid_input %s unexpected" % R["invalid"]]
    items = e["frame"] or {}
    for n, it in items.get("expiries", {}).items():
        ex = R["expiries"].get(int(n))
        if ex is None:
            bad.append("expiry %s missing" % n)
            continue
        if ex["status"] != it["status"] or ex["reason"] != it["reason"]:
            bad.append("expiry %s status %s/%s != %s/%s" % (n, ex["status"], ex["reason"], it["status"], it["reason"]))
            continue
        if "forward" in it and abs(ex["forward"] - float(Fr(it["forward"]))) > tol_f:
            bad.append("forward %s %r vs %s" % (n, ex["forward"], it["forward"]))
        if "atm_iv" in it and abs(ex["atm"] - float(Fr(it["atm_iv"]))) > tol_iv:
            bad.append("atm %s %r vs %s" % (n, ex["atm"], it["atm_iv"]))
        for k, key in (("put25_iv", "put25"), ("call25_iv", "call25")):
            if k in it:
                st, rs, v = ex[key]
                if st != it[k]["status"] or rs != it[k]["reason"]:
                    bad.append("%s %s status %s/%s != %s/%s" % (k, n, st, rs, it[k]["status"], it[k]["reason"]))
                elif it[k]["value"] is not None and abs(v - float(Fr(it[k]["value"]))) > tol_iv:
                    bad.append("%s %s %r vs %s" % (k, n, v, it[k]["value"]))
    for t, it in items.get("tenors", {}).items():
        st, rs, v, me, used = R["tenors"][int(t)]
        if st != it["status"] or rs != it["reason"]:
            bad.append("tenor %s status %s/%s != %s/%s" % (t, st, rs, it["status"], it["reason"]))
        elif st == "available":
            if abs(v - float(Fr(it["iv"]))) > tol_iv:
                bad.append("tenor %s iv %r vs %s" % (t, v, it["iv"]))
            if me != it["method"] or used != it["expiries_used"]:
                bad.append("tenor %s method %s %s" % (t, me, used))
    if e["coverage"] is not None:
        for k, v in e["coverage"].items():
            if R["coverage"][k] != v:
                bad.append("coverage.%s %s != %s" % (k, R["coverage"][k], v))
    if e["labels"] is not None and R["labels"] != e["labels"]:
        bad.append("labels %s != %s" % (R["labels"], e["labels"]))
    if e.get("echo") and R["echo"] != e["echo"]:
        bad.append("echo %s != %s" % (R["echo"], e["echo"]))
    if (e["status"], e["reason"]) != (R["frame_status"], R["frame_reason"]):
        bad.append("frame status %s/%s != %s/%s" % (R["frame_status"], R["frame_reason"], e["status"], e["reason"]))
    if e["value"] is not None:
        bad.append("top-level value must be null (R-142)")
    return bad
