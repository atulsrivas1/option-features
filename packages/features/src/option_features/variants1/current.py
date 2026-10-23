"""CurrentActivityOp: one-contract full-session positive-eligible activity with explicit target identity."""
from option_feature_contracts.variants1.canonical import b2f, b64num, i64num
from . import numeric as N
from . import premium as P
from . import buckets as B
from .context import Deps, make_evidence
from .flow import capture, capture_deps, exclusion_deps, order_members, premiums_for, eligibility_block
from .results import metric, unavailable_metric, row as mkrow, receipt, aggregate

CUR_IDS = [("positive_eligible_contracts", "contracts"), ("positive_eligible_trade_count", "executions"),
           ("premium", "currency")]


def basis_of(op):
    return {"admission": "positive-derived-premium1", "count_conversion": "checked-i64-then-rne-once1",
            "premium_order": "event-id1", "premium_recipe": op["recipe"]}


def target_context(ctx, target):
    frame = ctx.frames[target["session_frame_id"]]
    scope = ctx.scopes[target["scope_id"]]
    bp = ctx.bpolicies[target["bucket_policy_id"]]
    return frame, scope, bp


def add_frame_deps(ctx, deps, frame):
    bc = ctx.controls[frame["boundary_control_id"]]
    deps.add("variant_Control", bc["control_id"], ctx.rd("variant_Control", bc), "capture", bc["stamp"]["known_at_ns"])
    deps.add("variant_SessionFrame", frame["frame_id"], ctx.rd("variant_SessionFrame", frame), "capture",
             bc["stamp"]["known_at_ns"])
    return bc


def compute_current(ctx, oi, op, target_id=None):
    """Shared by the operation and by consumers; returns the full result dict."""
    target = ctx.targets[op["target_id"]]
    frame, scope, bp = target_context(ctx, target)
    full = frame["full_session"]
    cap = capture(ctx, op, oi, interval=full)
    raw = order_members(cap.raw, "event-id1", ctx)
    results = premiums_for(ctx, op, op["recipe"], raw)
    elig = eligibility_block(ctx, cap, results)
    unresolved = bool(elig["unresolved_ids"])
    positive = [r for r in results if r["outcome"] == "positive"]
    bk = B.derive(ctx, target["target_id"], target["reference_A_ns"], target["right"], bp, target["bucket_input"])
    deps = Deps()
    capture_deps(ctx, cap, deps)
    exclusion_deps(ctx, cap, deps)
    bc = add_frame_deps(ctx, deps, frame)
    controls = [c["control_id"] for c in cap.controls] + [bc["control_id"]]
    for res in results:
        deps.update(res["deps"])
        deps.add("variant_PremiumCore", res["object_id"], res["object_id"], "numerical_eligibility", res["known"])
        controls += res["controls"]
    P.policy_scope_deps(ctx, deps, set(), op)
    deps.add("variant_BucketPolicy", bp["policy_id"], ctx.rd("variant_BucketPolicy", bp), "policy", 0)
    for rtype, rid, rh, use, known in bk.deps:
        deps.add(rtype, rid, rh, use, known)
    controls += bk.controls
    tk = max(target["stamp"]["known_at_ns"], bk.known)
    deps.add("variant_ActivityTarget", target["target_id"], ctx.rd("variant_ActivityTarget", target), "economic", tk)
    # metrics
    diags = []
    if not cap.complete:
        metrics = [unavailable_metric(m, u, "incomplete_capture") for m, u in CUR_IDS]
        diags.append(("incomplete_capture", op["op_id"]))
    elif unresolved:
        metrics = [unavailable_metric(m, u, "premium_unavailable") for m, u in CUR_IDS]
        for r in results:
            if r["outcome"] == "unresolved_premium":
                diags.append((r["premium"]["reason"], r["rev"]["root_id"]))
                diags.append(("premium_unavailable", r["rev"]["root_id"]))
    else:
        qty = 0
        total = 0.0
        for r in positive:
            qty = N.cadd(qty, int(r["rev"]["quantity"]))
            total = N.add(total, b2f(r["premium"]["value"]["bits"]))
        br = "complete_empty" if not positive else "ordinary"
        metrics = [metric("positive_eligible_contracts", "contracts", i64num(qty), branch=br),
                   metric("positive_eligible_trade_count", "executions", i64num(len(positive)), branch=br),
                   metric("premium", "currency", b64num(total), branch=br)]
    ident_status = "available" if bk.ok else "unavailable"
    ident_reason = "ok" if bk.ok else bk.reason
    if not bk.ok:
        diags.append((bk.reason, target["target_id"]))
    key = None
    if bk.ok:
        key = B.activity_key(ctx, scope, target["contract_id"], target["right"], basis_of(op), bp, bk.dte_key, bk.mon_key)
    ev = make_evidence(deps, [r["rev"]["root_id"] for r in positive], [r["rev"]["revision_id"] for r in positive], (), (),
                       list(elig["zero_excluded_ids"]) + list(cap.excluded), controls, capture_complete=cap.complete,
                       context_complete=False, eligibility=elig,
                       bucket_domain_evidence=[bk.domain] if bk.domain is not None else ())
    value = {"activity_key": key, "bucket_witness": bk.witness, "full_session": full, "identity_reason": ident_reason,
             "identity_status": ident_status, "metrics": metrics, "premiums": [r["object"] for r in results],
             "reference_A_ns": target["reference_A_ns"], "session_frame_id": frame["frame_id"],
             "target_id": target["target_id"]}
    pairs = [(m["status"], m["reason"]) for m in metrics]
    if not bk.ok:
        pairs.append(("unavailable", bk.reason))
    for r in results:
        if r["outcome"] == "unresolved_premium" and cap.complete:
            pairs.append(("unavailable", r["premium"]["reason"]))
    return {"value": value, "evidence": ev, "diags": diags, "pairs": pairs, "bucket": bk, "target": target,
            "results": results, "positive": positive, "metrics": metrics, "key": key, "elig": elig, "cap": cap}


def current_activity(ctx, oi, op):
    c = compute_current(ctx, oi, op)
    st, rs = aggregate(c["pairs"])
    row = mkrow(ctx, op, None, "current_activity", c["value"], c["evidence"], c["diags"], ctx.snapshot_hash,
                ctx.request_hash)
    return receipt(op, 1, st, rs, c["evidence"]), [row]
