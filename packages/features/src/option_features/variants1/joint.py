"""JointOp: observed short/OTM shares and joint-reference coverage."""
from option_feature_contracts.variants1.canonical import b2f, b64num, i64num, record_digest
from . import numeric as N
from . import premium as P
from . import signing as S
from .context import Deps, make_evidence
from .flow import (capture, order_members, premiums_for, eligibility_block, capture_deps, exclusion_deps,
                   sign_members)
from .results import metric, unavailable_metric, row as mkrow, receipt, aggregate

JOINT_IDS = [("total_premium", "currency"), ("joint_premium", "currency"), ("short_premium", "currency"),
             ("otm_premium", "currency"), ("unknown_premium", "currency"), ("unknown_count", "executions"),
             ("short_observed_share", "ratio"), ("otm_observed_share", "ratio"), ("joint_reference_coverage", "ratio")]


def civil_fact(ref):
    return {"calendar_id": ref["calendar_id"], "calendar_revision": ref["calendar_revision"],
            "civil_day": ref["civil_day"], "civil_instant_ns": ref["civil_instant_ns"],
            "contract_id": ref["contract_id"], "reference_id": ref["reference_id"], "stamp": ref["civil_stamp"]}


def spot_fact(ref):
    return {"contract_id": ref["contract_id"], "reference_id": ref["reference_id"], "spot": ref["spot"],
            "stamp": ref["spot_stamp"]}


def classify_reference(ctx, policy, res, deps, controls):
    """Consume A-visible reference components; returns (joint, short, otm) booleans (joint False = unknown)."""
    rev, new_rev = res["rev"], res["new_rev"]
    a_ns, t = new_rev["signing_A_ns"], new_rev["event_ns"]
    ref = ctx.refs.get(rev["reference_id"]) if rev["reference_id"] is not None else None
    d = res["definition"]
    if ref is None:
        return False, False, False
    civil_ok = ref["civil_stamp"] is not None and ctx.vis_A(ref["civil_stamp"], a_ns) and ref["civil_day"] is not None
    spot_ok = ref["spot"] is not None and ref["spot_stamp"] is not None and ctx.vis_A(ref["spot_stamp"], a_ns)
    if civil_ok:
        f = civil_fact(ref)
        _dep(ctx, deps, "variant_CivilFact", f)
    if spot_ok:
        f = spot_fact(ref)
        _dep(ctx, deps, "variant_SpotFact", f)
    if spot_ok and not (t - ref["spot_stamp"]["event_ns"] <= policy["max_spot_age_ns"] and ref["spot_stamp"]["event_ns"] <= t):
        spot_ok = False
    if not (civil_ok and spot_ok and d is not None and d["expiry_day"] is not None):
        for cid in ref["absence_control_ids"]:
            c = ctx.controls[cid]
            if ctx.vis_A(c["stamp"], a_ns):
                deps.add("variant_Control", cid, ctx.rd("variant_Control", c), "context", c["stamp"]["known_at_ns"])
                b = ctx.bindings[c["stamp"]["binding_id"]]
                deps.add("variant_Binding", b["binding_id"], ctx.rd("variant_Binding", b), "context", 0)
                controls.append(cid)
        return False, False, False
    dte = d["expiry_day"] - ref["civil_day"]
    z = N.div(b2f(d["strike"]), b2f(ref["spot"]))
    short = 0 <= dte <= policy["short_dte_max_days"]
    if d["right"] == "call":
        otm = z > 1.0
    else:
        otm = 0.0 < z < 1.0
    return True, short, otm


def _dep(ctx, deps, rtype, fact):
    h = record_digest(rtype, fact)
    deps.add(rtype, h, h, "context", fact["stamp"]["known_at_ns"])
    b = ctx.bindings[fact["stamp"]["binding_id"]]
    deps.add("variant_Binding", b["binding_id"], ctx.rd("variant_Binding", b), "context", 0)


def joint(ctx, oi, op):
    policy = ctx.policies[op["policy_id"]]
    cap = capture(ctx, op, oi)
    raw = order_members(cap.raw, op["order"], ctx)
    results = premiums_for(ctx, op, op["recipe"], raw)
    elig = eligibility_block(ctx, cap, results)
    unresolved = bool(elig["unresolved_ids"])
    positive = [r for r in results if r["outcome"] == "positive"]
    signed = sign_members(ctx, op, policy, positive, op["recipe"])
    deps = Deps()
    capture_deps(ctx, cap, deps)
    exclusion_deps(ctx, cap, deps)
    controls = [c["control_id"] for c in cap.controls]
    for res in results:
        deps.update(res["deps"])
        deps.add("variant_PremiumCore", res["object_id"], res["object_id"], "numerical_eligibility", res["known"])
        controls += res["controls"]
    P.policy_scope_deps(ctx, deps, set(), op)
    unknown_sign, context_complete = [], True
    for res, sr, wit in signed:
        S.context_deps(ctx, sr, deps)
        if sr.control_id is not None:
            controls.append(sr.control_id)
        else:
            context_complete = False
        if sr.side == "unknown":
            unknown_sign.append(res["rev"]["root_id"])
    joint_ids, short_ids, otm_ids, unknown_ref = [], [], [], []
    T = Q = D = O = U = 0.0
    unk_count = 0
    reasons_ok = cap.complete and not unresolved
    for cid in op["context_ids"]:
        c = ctx.controls[cid]
        deps.add("variant_Control", cid, ctx.rd("variant_Control", c), "context", c["stamp"]["known_at_ns"])
        controls.append(cid)
    for res in positive:
        P_ = b2f(res["premium"]["value"]["bits"])
        j, sh, ot = classify_reference(ctx, policy, res, deps, controls)
        rid = res["rev"]["root_id"]
        if j:
            joint_ids.append(rid)
            if sh:
                short_ids.append(rid)
            if ot:
                otm_ids.append(rid)
        else:
            unknown_ref.append(rid)
        if reasons_ok:
            T = N.add(T, P_)
            if j:
                Q = N.add(Q, P_)
                if sh:
                    D = N.add(D, P_)
                if ot:
                    O = N.add(O, P_)
            else:
                U = N.add(U, P_)
                unk_count += 1
    if not cap.complete:
        metrics = [unavailable_metric(m, u, "incomplete_capture") for m, u in JOINT_IDS]
    elif unresolved:
        metrics = [unavailable_metric(m, u, "premium_unavailable") for m, u in JOINT_IDS]
    elif not positive:
        metrics = [metric(m, u, i64num(0) if m == "unknown_count" else b64num(0.0), branch="complete_empty")
                   for m, u in JOINT_IDS[:6]] + \
                  [unavailable_metric(m, u, "zero_denominator", status="undefined") for m, u in JOINT_IDS[6:]]
    else:
        vals = [b64num(T), b64num(Q), b64num(D), b64num(O), b64num(U), i64num(unk_count),
                b64num(N.div(D, T)), b64num(N.div(O, T)), b64num(N.div(Q, T))]
        metrics = [metric(m, u, v) for (m, u), v in zip(JOINT_IDS, vals)]
    ev = make_evidence(deps, [r["rev"]["root_id"] for r in positive], [r["rev"]["revision_id"] for r in positive],
                       unknown_sign, unknown_ref, list(elig["zero_excluded_ids"]) + list(cap.excluded), controls,
                       capture_complete=cap.complete, context_complete=context_complete, eligibility=elig)
    value = {"joint_ids": joint_ids, "metrics": metrics, "otm_ids": otm_ids,
             "premiums": [r["object"] for r in results], "short_ids": short_ids, "signs": [w for _, _, w in signed]}
    st, rs = aggregate([(m["status"], m["reason"]) for m in metrics])
    row = mkrow(ctx, op, None, "joint_reference", value, ev, [], ctx.snapshot_hash, ctx.request_hash)
    return receipt(op, 1, st, rs, ev), [row]
