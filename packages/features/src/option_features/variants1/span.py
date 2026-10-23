"""SpanOp: explicit-anchor inclusive-span candidates with explicit AnchorReadiness."""
from option_feature_contracts.variants1.canonical import b2f, b64num, canonical_json, fail, span_id
from . import numeric as N
from . import premium as P
from . import signing as S
from .admission import interval_contains
from .context import Deps, make_evidence
from .flow import (Cap, capture_deps, definition_records, eligibility_block, exclusion_deps, sign_members)
from .results import metric, unavailable_metric, row as mkrow, receipt, aggregate


def partition_key(definition):
    return (definition["contract_id"], definition["right"], definition["strike"], definition["expiry_day"],
            canonical_json(definition["multiplier"]), definition["underlying_id"], definition["currency"])


def _emit_has(iv, t):
    lo = t > iv["start_ns"] or (t == iv["start_ns"] and iv["start_closed"])
    hi = t < iv["end_ns"] or (t == iv["end_ns"] and iv["end_closed"])
    return lo and hi


def _premiums(ctx, op, memo, rev):
    res = memo.get(rev["root_id"])
    if res is None:
        res = P.native_premium(ctx, op, op["recipe"], rev)
        prem = res["premium"]
        if prem["status"] != "available":
            res["outcome"] = "unresolved_premium"
        elif prem["value"]["kind"] == "b64" and b2f(prem["value"]["bits"]) == 0.0:
            res["outcome"] = "excluded_zero"
        else:
            res["outcome"] = "positive"
        memo[rev["root_id"]] = res
    return res


def _candidates(ctx, op, scope):
    """K-selected regular active roots of the op scope ordered (event_ns, root_id)."""
    out = []
    for rid in ctx.roots:
        sel = ctx.k_selected(rid)
        if sel is None or sel["kind"] == "cancel" or sel["condition"] != "regular":
            continue
        if sel["scope_id"] != op["scope_id"]:
            continue
        out.append(sel)
    out.sort(key=lambda r: (ctx.new_rev(r["root_id"])["event_ns"], r["root_id"]))
    return out


def _collect(ctx, op, scope, anchor_rev, asof_ns, w, cands, memo, expected):
    """Witness population (partition members at/after the anchor inside M) for one anchor."""
    anchor_new = ctx.new_rev(anchor_rev["root_id"])
    a_ns = anchor_new["event_ns"]
    hi = min(asof_ns, a_ns + w)
    adef = P.definition_of(ctx, anchor_rev)
    akey = partition_key(adef) if adef is not None else None
    wit = []
    for rev in cands:
        new = ctx.new_rev(rev["root_id"])
        if (new["event_ns"], rev["root_id"]) < (a_ns, anchor_rev["root_id"]) or new["event_ns"] > hi:
            continue
        if rev["root_id"] != anchor_rev["root_id"]:
            d = P.definition_of(ctx, rev)
            if d is not None and (akey is None or partition_key(d) != akey):
                continue
        wit.append(_premiums(ctx, op, memo, rev))
    return wit, a_ns, hi


def span(ctx, oi, op):
    policy = ctx.policies[op["policy_id"]]
    scope = ctx.scopes[op["scope_id"]]
    pol_hash = ctx.policy_hash(op["policy_id"])
    w = policy["window_ns"]
    asofc = ctx.controls[op["asof_control_id"]]
    asof_ns = asofc["event_domain"]["start_ns"]
    ctls = [ctx.controls[c] for c in op["capture_ids"]]
    expected, seen = [], set()
    ctl_ok = bool(ctls)
    for c in ctls:
        if not (c["complete"] and c["reason"] == "captured" and c["decision"] == "not_applicable" and
                ctx.vis_K(c["stamp"])):
            ctl_ok = False
        for rid in c["expected_root_ids"]:
            if rid not in seen:
                seen.add(rid)
                expected.append(rid)
    for rid in expected:
        if ctx.k_selected(rid) is None:
            ctl_ok = False
    cands = _candidates(ctx, op, scope)
    memo = {}
    # stage 8, phase 1: premiums of every anchor's witness population (numeric failures first)
    anchors = []
    for rid in op["anchor_ids"]:
        arev = ctx.k_selected(rid)
        wit, a_ns, hi = _collect(ctx, op, scope, arev, asof_ns, w, cands, memo, expected)
        anchors.append((rid, arev, wit, a_ns, hi))
    # phase 2: anchor eligibility in anchor array order
    plan = []
    for ai, (rid, arev, wit, a_ns, hi) in enumerate(anchors):
        ares = memo[rid]
        path = "/request/operations/%d/anchor_ids/%d" % (oi, ai)
        side = None
        signed = []
        if ares["outcome"] == "excluded_zero":
            fail("ineligible_anchor", path, 8)
        if ares["outcome"] == "positive":
            signed = sign_members(ctx, op, policy, [r for r in wit if r["outcome"] == "positive"], op["recipe"])
            bysign = {r["rev"]["root_id"]: (r, sr, wt) for r, sr, wt in signed}
            side = bysign[rid][1].side
            if side not in ("buy", "sell"):
                fail("identity_mismatch", path, 8)
        plan.append((rid, arev, wit, a_ns, hi, ares, signed, side))
    rows, pairs, ars, evs = [], [], [], []
    union_wit, union_members, union_excl = {}, [], []
    any_incomplete = False
    all_ctx = True
    emit = ctx.req["emit"]
    for rid, arev, wit, a_ns, hi, ares, signed, side in plan:
        need = {"start_ns": a_ns, "end_ns": hi, "start_closed": True, "end_closed": True}
        complete = ctl_ok and all(interval_contains(c["event_domain"], need) for c in ctls)
        cap = Cap()
        cap.controls, cap.complete = ctls, complete
        wit_ids = {r["rev"]["root_id"] for r in wit}
        members = [(r, sr, wt) for r, sr, wt in signed if sr.side == side] if side is not None else []
        member_ids = [r["rev"]["root_id"] for r, _, _ in members]
        unres_ids = {r["rev"]["root_id"] for r in wit if r["outcome"] == "unresolved_premium"}
        excluded = [rid2 for rid2 in expected if rid2 not in set(member_ids) and rid2 not in unres_ids and
                    ctx.k_selected(rid2) is not None]
        cap.excl_revs = []
        for rid2 in excluded:
            cap.excl_revs += [r for r in ctx.chain(rid2) if ctx.vis_K(r["stamp"])]
        elig = eligibility_block(ctx, cap, wit)
        deps = Deps()
        capture_deps(ctx, cap, deps)
        exclusion_deps(ctx, cap, deps)
        deps.add("variant_Control", asofc["control_id"], ctx.rd("variant_Control", asofc), "capture",
                 asofc["stamp"]["known_at_ns"])
        b = ctx.bindings[asofc["stamp"]["binding_id"]]
        deps.add("variant_Binding", b["binding_id"], ctx.rd("variant_Binding", b), "economic", 0)
        controls = [c["control_id"] for c in ctls] + [asofc["control_id"]]
        for cid in op["context_ids"]:
            c = ctx.controls[cid]
            deps.add("variant_Control", cid, ctx.rd("variant_Control", c), "context", c["stamp"]["known_at_ns"])
            controls.append(cid)
        for res in wit:
            deps.update(res["deps"])
            deps.add("variant_PremiumCore", res["object_id"], res["object_id"], "numerical_eligibility", res["known"])
            controls += res["controls"]
        P.policy_scope_deps(ctx, deps, set(), op)
        unknown_sign, context_complete = [], True
        for r, sr, wt in signed:
            S.context_deps(ctx, sr, deps)
            if sr.control_id is not None:
                controls.append(sr.control_id)
            else:
                context_complete = False
            if sr.side == "unknown":
                unknown_sign.append(r["rev"]["root_id"])
        all_ctx = all_ctx and context_complete
        ev = make_evidence(deps, member_ids, [r["rev"]["revision_id"] for r, _, _ in members], unknown_sign, [],
                           list(elig["zero_excluded_ids"]) + excluded, controls, capture_complete=complete,
                           context_complete=context_complete, eligibility=elig)
        any_incomplete = any_incomplete or not complete
        evs.append(ev)
        for r in wit:
            union_wit.setdefault(r["rev"]["root_id"], r)
        for m in member_ids:
            if m not in union_members:
                union_members.append(m)
        union_excl += excluded
        if ares["outcome"] == "unresolved_premium":
            ars.append({"anchor_id": rid, "evidence": ev, "premium_core": ares["core"], "reason": "premium_unavailable",
                        "status": "unavailable"})
            pairs.append(("unavailable", "premium_unavailable"))
            continue
        ars.append({"anchor_id": rid, "evidence": ev, "premium_core": ares["core"], "reason": "ok",
                    "status": "available"})
        if not _emit_has(emit, a_ns):
            continue
        # SpanObject
        unresolved = [r for r in wit if r["outcome"] == "unresolved_premium"]
        if not complete:
            prem = unavailable_metric("premium", "currency", "incomplete_capture")
            state = "incomplete_capture"
        elif unresolved:
            prem = unavailable_metric("premium", "currency", "premium_unavailable")
            state = "bounded_asof_complete" if asof_ns >= a_ns + w else "pending_horizon"
        else:
            total = 0.0
            for r, _, _ in members:
                total = N.add(total, b2f(r["premium"]["value"]["bits"]))
            prem = metric("premium", "currency", b64num(total))
            state = "bounded_asof_complete" if asof_ns >= a_ns + w else "pending_horizon"
        reached = asof_ns >= a_ns + w
        if complete and not unresolved:
            state = "bounded_asof_complete" if reached else "pending_horizon"
        venues = sorted({r["rev"]["venue_id"] for r, _, _ in members if r["rev"]["venue_id"] is not None})
        unknown_v = sorted(r["rev"]["root_id"] for r, _, _ in members if r["rev"]["venue_id"] is None)
        exa = {"approximate_ids": [], "exact_ids": [], "unknown_ids": []}
        for r, _, _ in members:
            exa[{"exact": "exact_ids", "approximate": "approximate_ids", "unknown": "unknown_ids"}[
                r["rev"]["exactness"]]].append(r["rev"]["root_id"])
        for k in exa:
            exa[k] = sorted(exa[k])
        cid = span_id(op["op_id"], op["scope_id"], rid, op["asof_control_id"], pol_hash)
        value = {
            "anchor_event_ns": a_ns, "anchor_id": rid, "asof_control_id": op["asof_control_id"], "candidate_id": cid,
            "count": len(members), "exactness": exa, "horizon_reached": reached,
            "latest_event_ns": max(ctx.new_rev(m)["event_ns"] for m in member_ids),
            "member_ids": member_ids,
            "member_interval": {"end_closed": True, "end_ns": hi, "start_closed": True, "start_ns": a_ns},
            "member_revision_ids": [r["rev"]["revision_id"] for r, _, _ in members],
            "membership_complete": complete, "observation_state": state, "premium": prem,
            "venues": {"known_venue_ids": venues, "unknown_member_ids": unknown_v},
        }
        diags = [(r["premium"]["reason"], r["rev"]["root_id"]) for r in unresolved]
        rows.append(mkrow(ctx, op, cid, "span", value, ev, diags, ctx.snapshot_hash, ctx.request_hash))
        pairs.append((prem["status"], prem["reason"]))
    if any_incomplete:
        pairs.append(("unavailable", "incomplete_capture"))
    st, rs = aggregate(pairs)
    wit_all = sorted(union_wit.values(), key=lambda r: (ctx.new_rev(r["rev"]["root_id"])["event_ns"], r["rev"]["root_id"]))
    if len(evs) == 1:
        op_ev = evs[0]
    else:
        cap = Cap()
        cap.complete = not any_incomplete
        op_elig = eligibility_block(ctx, cap, wit_all)
        deps = Deps()
        for e in evs:
            for d in e["dependencies"]:
                deps.add(d["record_type"], d["record_id"], d["record_sha256"], d["use"], d["known_at_ns"])
        controls = [c for e in evs for c in e["control_ids"]]
        op_ev = make_evidence(deps, union_members,
                              [ctx.k_selected(m)["revision_id"] for m in union_members],
                              [x for e in evs for x in e["unknown_sign_ids"]], [], union_excl, controls,
                              capture_complete=not any_incomplete, context_complete=all_ctx, eligibility=op_elig)
    rc = receipt(op, len(rows), st, rs, op_ev, anchor_readiness=ars)
    return rc, rows
