"""Captured membership, eligibility evidence and the binary64 flow operations."""
from option_feature_contracts.variants1.canonical import b2f, b64num, i64num, record_digest
from . import numeric as N
from . import premium as P
from . import signing as S
from .admission import _in_interval, interval_contains
from .context import Deps, make_evidence
from .results import metric, unavailable_metric, row as mkrow, receipt, aggregate


class Cap:
    pass


def capture(ctx, op, oi, interval=None):
    """Resolve the op's capture controls into the raw member population.

    `interval` (checked-integer rollup) replaces the capture domain as member interval; every
    capture domain must then cover it for completeness."""
    cap = Cap()
    cap.controls = [ctx.controls[c] for c in op["capture_ids"]]
    cap.complete = bool(cap.controls)
    cap.domain = interval if interval is not None else (cap.controls[0]["event_domain"] if cap.controls else None)
    if interval is not None and not all(interval_contains(c["event_domain"], interval) for c in cap.controls):
        cap.complete = False
    expected, seen = [], set()
    for c in cap.controls:
        if not (c["complete"] and c["reason"] == "captured" and c["decision"] == "not_applicable" and
                ctx.vis_K(c["stamp"])):
            cap.complete = False
        for rid in c["expected_root_ids"]:
            if rid not in seen:
                seen.add(rid)
                expected.append(rid)
    cap.raw, cap.excluded, cap.excl_revs = [], [], []
    for rid in expected:
        sel = ctx.k_selected(rid)
        if sel is None:
            cap.complete = False
            continue
        if (sel["kind"] == "cancel" or sel["condition"] != "regular" or
                (cap.domain is not None and not _in_interval(cap.domain, ctx.new_rev(rid)["event_ns"]))):
            cap.excluded.append(rid)
            cap.excl_revs += [r for r in ctx.chain(rid) if ctx.vis_K(r["stamp"])]
            continue
        cap.raw.append(sel)
    if cap.domain is not None and "scope_id" in op:
        # F4 (clarification2 Q2a/Q2b): a visible regular root that is neither expected nor covered by the
        # capture domain is excluded (listed, exclusion dependency only; never a member).
        for rid in ctx.roots:
            if rid in seen:
                continue
            sel = ctx.k_selected(rid)
            if (sel is None or sel["kind"] == "cancel" or sel["condition"] != "regular" or
                    sel["scope_id"] != op["scope_id"] or _in_interval(cap.domain, ctx.new_rev(rid)["event_ns"])):
                continue
            cap.complete = False
            cap.excluded.append(rid)
            cap.excl_revs += [r for r in ctx.chain(rid) if ctx.vis_K(r["stamp"])]
    return cap


def exclusion_deps(ctx, cap, deps):
    """Exclusion-use dependencies on every K-visible revision of an excluded root."""
    for r in cap.excl_revs:
        deps.add("variant_Execution", r["revision_id"], ctx.rd("variant_Execution", r), "exclusion",
                 r["stamp"]["known_at_ns"])
        b = ctx.bindings[r["stamp"]["binding_id"]]
        deps.add("variant_Binding", b["binding_id"], ctx.rd("variant_Binding", b), "economic", 0)


def order_members(revs, order, ctx):
    if order == "session-admission1":
        return sorted(revs, key=lambda r: ctx.new_rev(r["root_id"])["admission_ordinal"])
    if order == "rolling-stable-event-admission1":
        return sorted(revs, key=lambda r: (ctx.new_rev(r["root_id"])["event_ns"], ctx.new_rev(r["root_id"])["admission_ordinal"]))
    return sorted(revs, key=lambda r: (ctx.new_rev(r["root_id"])["event_ns"], r["root_id"]))


class Elig:
    pass


def premiums_for(ctx, op, recipe, raw):
    """Native premium results for raw members plus eligibility outcomes."""
    out = []
    for rev in raw:
        res = P.native_premium(ctx, op, recipe, rev)
        prem = res["premium"]
        if prem["status"] != "available":
            res["outcome"] = "unresolved_premium"
        elif _is_zero(prem["value"]):
            res["outcome"] = "excluded_zero"
        else:
            res["outcome"] = "positive"
        out.append(res)
    return out


def _is_zero(v):
    if v["kind"] == "b64":
        return b2f(v["bits"]) == 0.0
    return int(v["integer"]) == 0


def eligibility_block(ctx, cap, results):
    witnesses = []
    pos_c = pos_t = 0
    zero, unres = [], []
    raw_c = raw_t = 0
    for res in results:
        rev = res["rev"]
        q = int(rev["quantity"])
        raw_c = N.cadd(raw_c, q)
        raw_t += 1
        core_hash = res["object_id"]
        witnesses.append({"available_at_ns": res["known"], "outcome": res["outcome"], "premium_core": res["core"],
                          "premium_core_sha256": core_hash, "revision_id": rev["revision_id"], "root_id": rev["root_id"]})
        if res["outcome"] == "positive":
            pos_c = N.cadd(pos_c, q)
            pos_t += 1
        elif res["outcome"] == "excluded_zero":
            zero.append(rev["root_id"])
        else:
            unres.append(rev["root_id"])
    if cap.complete:
        rc = metric("raw_contracts", "contracts", i64num(raw_c))
        rt = metric("raw_trade_count", "executions", i64num(raw_t))
    else:
        rc = unavailable_metric("raw_contracts", "contracts", "incomplete_capture")
        rt = unavailable_metric("raw_trade_count", "executions", "incomplete_capture")
    return {"observed_positive_contracts": pos_c, "observed_positive_trade_count": pos_t,
            "positive_complete": bool(cap.complete and not unres), "raw_contracts": rc, "raw_trade_count": rt,
            "unresolved_ids": sorted(unres), "witnesses": witnesses, "zero_excluded_ids": sorted(zero)}


def capture_deps(ctx, cap, deps):
    for c in cap.controls:
        deps.add("variant_Control", c["control_id"], ctx.rd("variant_Control", c), "capture", c["stamp"]["known_at_ns"])
        b = ctx.bindings[c["stamp"]["binding_id"]]
        deps.add("variant_Binding", b["binding_id"], ctx.rd("variant_Binding", b), "economic", 0)


def definition_records(ctx, rev):
    du = rev["definition_use"]
    if du["kind"] == "available":
        return [("variant_Definition", ctx.defs[du["definition_id"]])]
    recs = [("variant_Control", ctx.controls[du["control_id"]])]
    if du["visible_definition_id"] is not None:
        recs.append(("variant_Definition", ctx.defs[du["visible_definition_id"]]))
    return recs


def sign_members(ctx, op, policy, results, recipe):
    """Sign every positive member; returns list of (res, SignResult, witness)."""
    scope = ctx.scopes[op["scope_id"]]
    pol_hash = ctx.policy_hash(op["policy_id"])
    out = []
    for res in results:
        if res["outcome"] != "positive":
            continue
        rev, new_rev = res["rev"], res["new_rev"]
        price = rev["price"]
        if price["kind"] == "b64":
            p = b2f(price["bits"])
        else:
            p = N.div(N.rn_int(int(price["ticks"])), N.rn_int(int(price["scale"])))
        sr = S.sign_root(ctx, op, policy, new_rev, scope, definition_records(ctx, rev), p)
        wit = S.sign_witness(ctx, sr, rev, new_rev["signing_A_ns"], policy, pol_hash, policy["sign"]["kind"])
        out.append((res, sr, wit))
    return out


def rolling_window(ctx, op, cap, results, unresolved):
    """Window interval and member results for b64-rolling-BD1 (clarified endpoint algorithm)."""
    bc = ctx.controls[op["session_endpoint_control_id"]]
    positives = [r for r in results if r["outcome"] == "positive"]
    if not cap.complete or unresolved or not positives:
        return bc["event_domain"], []
    r_ns = max(ctx.new_rev(r["rev"]["root_id"])["event_ns"] for r in positives)
    s_ns = r_ns - op["horizon_ns"]
    start = s_ns if s_ns > 0 else 0
    iv = {"end_closed": True, "end_ns": r_ns, "start_closed": False, "start_ns": start}
    win = [r for r in positives if _in_interval(iv, ctx.new_rev(r["rev"]["root_id"])["event_ns"])]
    return iv, win


def directional_b64(ctx, oi, op, rolling=False):
    policy = ctx.policies[op["policy_id"]]
    recipe = op["recipe"]
    cap = capture(ctx, op, oi)
    raw = order_members(cap.raw, "rolling-stable-event-admission1" if rolling else "session-admission1", ctx)
    results = premiums_for(ctx, op, recipe, raw)
    elig = eligibility_block(ctx, cap, results)
    unresolved = bool(elig["unresolved_ids"])
    if rolling:
        interval, window = rolling_window(ctx, op, cap, results, unresolved)
    else:
        interval, window = cap.domain, [r for r in results if r["outcome"] == "positive"]
    signed = sign_members(ctx, op, policy, window, recipe)
    deps = Deps()
    capture_deps(ctx, cap, deps)
    exclusion_deps(ctx, cap, deps)
    controls = [c["control_id"] for c in cap.controls]
    if rolling:
        bc = ctx.controls[op["session_endpoint_control_id"]]
        deps.add("variant_Control", bc["control_id"], ctx.rd("variant_Control", bc), "capture", bc["stamp"]["known_at_ns"])
        controls.append(bc["control_id"])
    for res in results:
        deps.update(res["deps"])
        deps.add("variant_PremiumCore", res["object_id"], res["object_id"], "numerical_eligibility", res["known"])
        controls += res["controls"]
    P.policy_scope_deps(ctx, deps, set(), op)
    unknown_sign = []
    context_complete = True
    for res, sr, wit in signed:
        S.context_deps(ctx, sr, deps)
        if sr.control_id is not None:
            controls.append(sr.control_id)
        else:
            context_complete = False
        if sr.side == "unknown":
            unknown_sign.append(res["rev"]["root_id"])
    metrics = flow_metrics(signed, cap, unresolved)
    member_ids = [r["rev"]["root_id"] for r in window]
    member_revs = [r["rev"]["revision_id"] for r in window]
    inside = set(member_ids)
    outside = [r["rev"]["root_id"] for r in results if r["rev"]["root_id"] not in inside]
    excluded = list(elig["zero_excluded_ids"]) + list(cap.excluded) + (outside if rolling else [])
    ev = make_evidence(deps, member_ids, member_revs, unknown_sign, [], excluded, controls,
                       capture_complete=cap.complete, context_complete=context_complete, eligibility=elig)
    value = {"integer_weights": [], "member_interval": interval, "metrics": metrics,
             "order": "rolling-stable-event-admission1" if rolling else "session-admission1",
             "premiums": [r["object"] for r in results],
             "profile": op["profile"], "signs": [w for _, _, w in signed]}
    st, rs = aggregate([(m["status"], m["reason"]) for m in metrics])
    row = mkrow(ctx, op, None, "directional", value, ev, [], ctx.snapshot_hash, ctx.request_hash)
    return receipt(op, 1, st, rs, ev), [row]


METRIC_IDS = [("positive_eligible_contracts", "contracts"), ("positive_eligible_trade_count", "executions"),
              ("premium", "currency"), ("bullish", "currency"), ("bearish", "currency"), ("unknown", "currency"),
              ("call", "currency"), ("put", "currency"), ("ask", "currency"), ("bid", "currency"),
              ("net", "currency"), ("classified", "currency")]


def flow_metrics(signed, cap, unresolved):
    if not cap.complete:
        return [unavailable_metric(m, u, "incomplete_capture") for m, u in METRIC_IDS]
    if unresolved:
        return [unavailable_metric(m, u, "premium_unavailable") for m, u in METRIC_IDS]
    empty = not signed
    branch = "complete_empty" if empty else "ordinary"
    B = D = U = CALL = PUT = ASK = BID = 0.0
    qty = 0
    for res, sr, wit in signed:
        P_ = b2f(res["premium"]["value"]["bits"])
        qty = N.cadd(qty, int(res["rev"]["quantity"]))
        right = ctx_right(res)
        side = sr.side
        if (right == "call" and side == "buy") or (right == "put" and side == "sell"):
            B = N.add(B, P_)
        elif (right == "put" and side == "buy") or (right == "call" and side == "sell"):
            D = N.add(D, P_)
        else:
            U = N.add(U, P_)
        if right == "call":
            CALL = N.add(CALL, P_)
        else:
            PUT = N.add(PUT, P_)
        if side == "buy":
            ASK = N.add(ASK, P_)
        elif side == "sell":
            BID = N.add(BID, P_)
    net = N.sub(B, D)
    classified = N.add(B, D)
    total = N.add(classified, U)
    vals = [i64num(qty), i64num(len(signed))] +         [b64num(x) for x in (total, B, D, U, CALL, PUT, ASK, BID, net, classified)]
    return [metric(mid, unit, v, branch=branch) for (mid, unit), v in zip(METRIC_IDS, vals)]


def ctx_right(res):
    return res["right"]
