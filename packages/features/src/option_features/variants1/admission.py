"""Stages 5-7 admission: identities, relationships and selected temporal coverage."""
from option_feature_contracts.variants1.canonical import fail, record_digest, b2f

SNAP = "/snapshot"
REQ = "/request"


def _in_interval(iv, t):
    lo = t > iv["start_ns"] or (t == iv["start_ns"] and iv["start_closed"])
    hi = t < iv["end_ns"] or (t == iv["end_ns"] and iv["end_closed"])
    return lo and hi


def interval_contains(outer, inner):
    """Every point of `inner` lies in `outer` (integer nanosecond domain)."""
    def lo(iv):
        return iv["start_ns"] if iv["start_closed"] else iv["start_ns"] + 1

    def hi(iv):
        return iv["end_ns"] if iv["end_closed"] else iv["end_ns"] - 1
    return lo(outer) <= lo(inner) and hi(inner) <= hi(outer)


def admission_hash(adm):
    return record_digest("variant_ProducerAdmission", adm)


# ---------------------------------------------------------------- stage 5
def stage5(ctx):
    s, r = ctx.snap, ctx.req
    # duplicate identities (collection declaration order)
    for coll, key in (("bindings", "binding_id"), ("scopes", "scope_id"), ("definitions", "definition_id"),
                      ("references", "reference_id"), ("executions", "revision_id"), ("quotes", "revision_id"),
                      ("pairings", "pairing_id"), ("controls", "control_id"), ("supplied_premiums", "premium_id"),
                      ("daily_observations", "observation_id"), ("baseline_slots", "slot_id"),
                      ("bucket_policies", "policy_id"), ("session_frames", "frame_id"),
                      ("activity_targets", "target_id"), ("bucket_certificates", "certificate_id"),
                      ("daily_activity_certificates", "certificate_id")):
        seen = set()
        for i, rec in enumerate(s[coll]):
            if rec[key] in seen:
                fail("identity_conflict", "%s/%s/%d/%s" % (SNAP, coll, i, key), 5)
            seen.add(rec[key])
    # stream position uniqueness across stamped records
    seen = {}
    for coll, stamps in _stamped(s):
        for i, st in stamps:
            k = (st["stream_id"], st["position"])
            if k in seen:
                fail("identity_conflict", "%s/%s/%d/stamp/position" % (SNAP, coll, i), 5)
            seen[k] = True
    # executions
    for e, ex in enumerate(s["executions"]):
        base = "%s/executions/%d" % (SNAP, e)
        du = ex["definition_use"]
        if du["kind"] == "available":
            if du["definition_id"] not in ctx.defs:
                fail("missing_identity", base + "/definition_use/definition_id", 5)
        else:
            if du["control_id"] not in ctx.controls:
                fail("missing_identity", base + "/definition_use/control_id", 5)
            if du["visible_definition_id"] is not None and du["visible_definition_id"] not in ctx.defs:
                fail("missing_identity", base + "/definition_use/visible_definition_id", 5)
        if ex["target_revision_id"] is not None and ex["target_revision_id"] not in ctx.execs:
            fail("missing_identity", base + "/target_revision_id", 5)
        if ex["reference_id"] is not None and ex["reference_id"] not in ctx.refs:
            fail("missing_identity", base + "/reference_id", 5)
        if ex["paired_quote_revision_id"] is not None and ex["paired_quote_revision_id"] not in ctx.quotes:
            fail("missing_identity", base + "/paired_quote_revision_id", 5)
    # pairings
    for p, pr in enumerate(s["pairings"]):
        base = "%s/pairings/%d" % (SNAP, p)
        if pr["root_id"] not in ctx.roots:
            fail("missing_identity", base + "/root_id", 5)
        if pr["original_revision_id"] not in ctx.execs:
            fail("missing_identity", base + "/original_revision_id", 5)
        if pr["quote_revision_id"] not in ctx.quotes:
            fail("missing_identity", base + "/quote_revision_id", 5)
    # request
    for o, op in enumerate(r["operations"]):
        base = "%s/operations/%d" % (REQ, o)
        if op["kind"] == "premium":
            for i, rid in enumerate(op["root_ids"]):
                if rid not in ctx.roots:
                    fail("missing_identity", "%s/root_ids/%d" % (base, i), 5)
        if op["kind"] == "span_at_anchor":
            for i, rid in enumerate(op["anchor_ids"]):
                if rid not in ctx.roots:
                    fail("missing_identity", "%s/anchor_ids/%d" % (base, i), 5)
        for fld in ("capture_ids", "context_ids", "lane_prefix_ids"):
            for i, cid in enumerate(op.get(fld, ())):
                if cid not in ctx.controls:
                    fail("missing_identity", "%s/%s/%d" % (base, fld, i), 5)
        for fld in ("session_endpoint_control_id", "frontier_control_id", "asof_control_id"):
            if op.get(fld) is not None and op[fld] not in ctx.controls:
                fail("missing_identity", "%s/%s" % (base, fld), 5)
    pa = r["producer_admission_sha256"]
    if pa is not None and ctx.admission is None:
        fail("missing_identity", REQ + "/producer_admission_sha256", 5)


def _stamped(s):
    for coll in ("definitions", "executions", "quotes", "pairings", "controls", "supplied_premiums",
                 "daily_observations", "activity_targets", "bucket_certificates", "daily_activity_certificates"):
        yield coll, [(i, rec["stamp"]) for i, rec in enumerate(s[coll])]


# ---------------------------------------------------------------- stage 6
def definition_ok(ctx, ex, d):
    """Available Definition resolves for the execution's context at its immutable A."""
    sc = ctx.scopes.get(ex["scope_id"])
    root_new = ctx.new_rev(ex["root_id"]) or ex
    a_ns = root_new["signing_A_ns"]
    if sc is None:
        return False
    return (d["contract_id"] == ex["contract_id"] and d["underlying_id"] == sc["underlying_id"] and
            d["currency"] == sc["currency"] and d["action_basis_id"] == sc["action_basis_id"] and
            d["deliverable_basis_id"] == sc["deliverable_basis_id"] and
            d["definition_basis_id"] == sc["definition_basis_id"] and
            ctx.vis_A(d["stamp"], a_ns) and _in_interval(d["effective"], root_new["event_ns"]) and
            d["eligibility"] == "scalar_standard")


def check_money(ctx, op):
    """Checked-integer operations need one monetary basis; every selected raw integer scale must equal it."""
    sc = ctx.scopes[op["scope_id"]]
    if sc["monetary_basis"] is None:
        fail("identity_mismatch", "%s/scopes/%d/monetary_basis" % (SNAP, ctx.snap["scopes"].index(sc)), 6)
    roots = set()
    if op["kind"] == "premium":
        roots = set(op["root_ids"])
    else:
        for cid in op.get("capture_ids", ()):
            roots.update(ctx.controls[cid]["expected_root_ids"])
    want = sc["monetary_basis"]["scale"]
    for e, ex in enumerate(ctx.snap["executions"]):
        if ex["root_id"] in roots and ex["price"] is not None and ex["price"]["kind"] == "integer" and \
                ex["price"]["scale"] != want:
            fail("identity_mismatch", "%s/executions/%d/price/scale" % (SNAP, e), 6)


def visible_justifies(ctx, ex, root_new, d, reason):
    sc = ctx.scopes.get(ex["scope_id"])
    if d["contract_id"] != ex["contract_id"] or sc is None or not ctx.vis_A(d["stamp"], root_new["signing_A_ns"]):
        return False
    inside = _in_interval(d["effective"], root_new["event_ns"])
    if reason == "ineffective_definition":
        return not inside and d["eligibility"] == "scalar_standard"
    if reason == "nonstandard_definition":
        return d["eligibility"] == "nonstandard"
    if reason == "unknown_definition":
        return d["eligibility"] == "unknown"
    return False


def check_supplied(ctx, op, rev):
    from . import premium as P
    sp = None
    si = None
    for i, cand in enumerate(ctx.snap["supplied_premiums"]):
        if cand["root_id"] == rev["root_id"] and cand["revision_id"] == rev["revision_id"]:
            sp, si = cand, i
            break
    if sp is None:
        return
    base = "%s/supplied_premiums/%d" % (SNAP, si)
    if sp["value"]["kind"] != "b64":
        fail("identity_mismatch", base + "/value/kind", 6)
    if sp["unit"] != "currency":
        fail("identity_mismatch", base + "/unit", 6)
    if sp["origin"] != "qualified_calculation" or sp["core"] is None:
        return
    core = sp["core"]
    pv = core["premium"]["value"]
    if pv is None or pv["kind"] != "b64" or pv["bits"] != sp["value"]["bits"]:
        fail("identity_mismatch", base + "/value/bits", 6)
    pr = sp["producer"]
    if pr["producer_cohort_sha256"] != ctx.cohort:
        fail("identity_mismatch", base + "/producer/producer_cohort_sha256", 6)
    deps, hashes, _ = P.source_deps(ctx, rev, ctx.new_rev(rev["root_id"]), P.definition_of(ctx, rev))
    P.policy_scope_deps(ctx, deps, hashes, op)
    if pr["input_record_sha256s"] != sorted(hashes):
        fail("identity_mismatch", base + "/producer/input_record_sha256s", 6)
    if pr["policy_sha256"] != ctx.policy_hash(op["policy_id"]):
        fail("identity_mismatch", base + "/producer/policy_sha256", 6)
    if pr["formula_id"] != core["recipe"]:
        fail("identity_mismatch", base + "/producer/formula_id", 6)
    if pr["output_record_sha256"] != ctx.rd("variant_PremiumCore", core):
        fail("identity_mismatch", base + "/producer/output_record_sha256", 6)
    for fld in ("bits", "kind", "scale", "ticks"):
        if fld in rev["price"] or fld in core["raw_price"]:
            if rev["price"].get(fld) != core["raw_price"].get(fld):
                fail("identity_mismatch", "%s/core/raw_price/%s" % (base, fld), 6)
    if core["quantity"] != rev["quantity"]:
        fail("identity_mismatch", base + "/core/quantity", 6)
    if core["root_id"] != rev["root_id"] or core["revision_id"] != rev["revision_id"]:
        fail("identity_mismatch", base + "/core/revision_id", 6)
    sh = ctx.rd("variant_SuppliedPremium", sp)
    adm = ctx.admission
    if adm is not None and ctx.req["producer_admission_sha256"] is not None:
        for qi, q in enumerate(adm["qualified_inputs"]):
            if q["record_type"] == "variant_SuppliedPremium" and q["record_sha256"] == sh:
                if q["output_core_sha256"] != pr["output_record_sha256"]:
                    fail("identity_mismatch", "/producer_admission/qualified_inputs/%d/output_core_sha256" % qi, 6)
                if q["input_record_sha256s"] != pr["input_record_sha256s"]:
                    fail("identity_mismatch", "/producer_admission/qualified_inputs/%d/input_record_sha256s" % qi, 6)


def stage6(ctx):
    s, r = ctx.snap, ctx.req
    for e, ex in enumerate(s["executions"]):
        base = "%s/executions/%d" % (SNAP, e)
        du = ex["definition_use"]
        if du["kind"] == "available":
            if not definition_ok(ctx, ex, ctx.defs[du["definition_id"]]):
                fail("identity_mismatch", base + "/definition_use/definition_id", 6)
        else:
            c = ctx.controls[du["control_id"]]
            want = "definition_absence" if du["reason"] in ("missing_definition", "future_definition") else "definition_ineligibility"
            root_new = ctx.new_rev(ex["root_id"]) or ex
            if (c["kind"] != want or c["scope_id"] != ex["scope_id"] or c["expected_contract_ids"] != [ex["contract_id"]] or
                    c["expected_root_ids"] != [ex["root_id"]] or not c["complete"] or c["decision"] != "not_applicable" or
                    c["reason"] != du["reason"] or not _in_interval(c["event_domain"], root_new["event_ns"])):
                fail("identity_mismatch", base + "/definition_use/control_id", 6)
            vid = du["visible_definition_id"]
            if want == "definition_ineligibility":
                if vid is None or not visible_justifies(ctx, ex, root_new, ctx.defs[vid], du["reason"]):
                    fail("identity_mismatch", base + "/definition_use/visible_definition_id", 6)
            elif vid is not None:
                fail("identity_mismatch", base + "/definition_use/visible_definition_id", 6)
    for p, pr in enumerate(s["pairings"]):
        orig = ctx.execs[pr["original_revision_id"]]
        if orig["root_id"] != pr["root_id"]:
            fail("identity_mismatch", "%s/pairings/%d/root_id" % (SNAP, p), 6)
        if orig["kind"] != "new":
            fail("identity_mismatch", "%s/pairings/%d/original_revision_id" % (SNAP, p), 6)
    for o, op in enumerate(r["operations"]):
        base = "%s/operations/%d" % (REQ, o)
        if op["kind"] == "premium":
            for i, rid in enumerate(op["root_ids"]):
                sel = ctx.k_selected(rid)
                if sel is None:
                    continue
                if sel["kind"] == "cancel" or sel["condition"] != "regular" or sel["scope_id"] != op["scope_id"]:
                    fail("identity_mismatch", "%s/root_ids/%d" % (base, i), 6)
            if op["recipe"] == "qualified-supplied1":
                for rid in op["root_ids"]:
                    check_supplied(ctx, op, ctx.k_selected(rid))
    for o, op in enumerate(r["operations"]):
        if op["kind"] == "span_at_anchor":
            base = "%s/operations/%d" % (REQ, o)
            for i, rid in enumerate(op["anchor_ids"]):
                sel = ctx.k_selected(rid)
                if sel is None:
                    continue
                if sel["kind"] == "cancel" or sel["condition"] != "regular" or sel["scope_id"] != op["scope_id"]:
                    fail("identity_mismatch", "%s/anchor_ids/%d" % (base, i), 6)
            ac = ctx.controls[op["asof_control_id"]]
            bad = ac["kind"] != "asof" or ac["scope_id"] != op["scope_id"]
            for rid in op["anchor_ids"]:
                sel = ctx.k_selected(rid)
                if sel is not None and ctx.new_rev(rid)["event_ns"] > ac["event_domain"]["start_ns"]:
                    bad = True
            if bad:
                fail("identity_mismatch", base + "/asof_control_id", 6)
    for o, op in enumerate(r["operations"]):
        if (op["kind"] == "directional" and op["profile"] == "i64-paired-call-put1") or \
                (op["kind"] == "parent_groups") or \
                (op["kind"] == "premium" and op["recipe"] == "checked-integer-products1"):
            check_money(ctx, op)
    pa = r["producer_admission_sha256"]
    if pa is not None and ctx.admission is not None and admission_hash(ctx.admission) != pa:
        fail("digest_mismatch", REQ + "/producer_admission_sha256", 6)


# ---------------------------------------------------------------- stage 7
def stage7(ctx):
    s, r = ctx.snap, ctx.req
    for o, op in enumerate(r["operations"]):
        base = "%s/operations/%d" % (REQ, o)
        for fld in ("capture_ids", "context_ids", "lane_prefix_ids"):
            for i, cid in enumerate(op.get(fld, ())):
                if not ctx.vis_K(ctx.controls[cid]["stamp"]):
                    fail("temporal_cut", "%s/%s/%d" % (base, fld, i), 7)
        for fld in ("session_endpoint_control_id", "frontier_control_id", "asof_control_id"):
            if op.get(fld) is not None and not ctx.vis_K(ctx.controls[op[fld]]["stamp"]):
                fail("temporal_cut", "%s/%s" % (base, fld), 7)
        if op["kind"] == "joint_reference":
            for cid in op["capture_ids"]:
                for rid in ctx.controls[cid]["expected_root_ids"]:
                    sel = ctx.k_selected(rid)
                    if sel is None or sel["reference_id"] is None:
                        continue
                    a_ns = ctx.new_rev(rid)["signing_A_ns"]
                    ref = ctx.refs[sel["reference_id"]]
                    for ci, acid in enumerate(ref["absence_control_ids"]):
                        if not ctx.vis_A(ctx.controls[acid]["stamp"], a_ns):
                            fail("temporal_cut", "%s/references/%d/absence_control_ids/%d" % (
                                SNAP, s["references"].index(ref), ci), 7)
        if op["kind"] == "span_at_anchor":
            for i, rid in enumerate(op["anchor_ids"]):
                sel = ctx.k_selected(rid)
                if sel is None:
                    fail("temporal_cut", "%s/anchor_ids/%d" % (base, i), 7)
                if sel["signing_A_ns"] > ctx.K:
                    fail("temporal_cut", REQ + "/knowledge_K_ns", 7)
        if op["kind"] == "premium":
            for i, rid in enumerate(op["root_ids"]):
                sel = ctx.k_selected(rid)
                if sel is None:
                    fail("temporal_cut", "%s/root_ids/%d" % (base, i), 7)
                if sel["signing_A_ns"] > ctx.K:
                    fail("temporal_cut", REQ + "/knowledge_K_ns", 7)
                du = sel["definition_use"]
                if du["kind"] == "unavailable":
                    c = ctx.controls[du["control_id"]]
                    if not ctx.vis_A(c["stamp"], ctx.new_rev(rid)["signing_A_ns"]):
                        fail("temporal_cut", "%s/executions/%d/definition_use/control_id" % (
                            SNAP, s["executions"].index(sel)), 7)
