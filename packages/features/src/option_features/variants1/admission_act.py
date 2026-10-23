"""Admission (stages 5-7) for full-session activity records: targets, frames, bucket inputs, daily records."""
from option_feature_contracts.variants1.canonical import b2f, fail, f2b, record_digest
from . import numeric as N
from .admission import _in_interval, interval_contains, SNAP, REQ


RAW_FIELDS = ("definition_id", "reference_id", "reference_instant_ns", "event_day", "expiry_day", "strike", "spot",
              "calendar_id", "calendar_revision")


def selected(ctx):
    """Records selected by the request: targets, baseline slots, their observations and frames."""
    sel = getattr(ctx, "_sel", None)
    if sel is not None:
        return sel
    targets, slots = set(), set()
    for op in ctx.req["operations"]:
        if op["kind"] == "current_activity":
            targets.add(op["target_id"])
        elif op["kind"] == "baseline":
            slots.update(op["slot_ids"])
    dailies = set()
    for sid in slots:
        sl = ctx.slots.get(sid)
        if sl is not None:
            dailies.update(sl["observation_ids"])
    frames = set()
    for tid in targets:
        t = ctx.targets.get(tid)
        if t is not None:
            frames.add(t["session_frame_id"])
    for did in dailies:
        d = ctx.dailies.get(did)
        if d is not None:
            frames.add(d["session_frame_id"])
    ctx._sel = {"targets": targets, "slots": slots, "dailies": dailies, "frames": frames}
    return ctx._sel


def owners(ctx):
    """Selected bucket-input owners in snapshot declaration order: (kind, index, record)."""
    sel = selected(ctx)
    for i, o in enumerate(ctx.snap["daily_observations"]):
        if o["observation_id"] in sel["dailies"]:
            yield "daily_observations", i, o
    for i, t in enumerate(ctx.snap["activity_targets"]):
        if t["target_id"] in sel["targets"]:
            yield "activity_targets", i, t


def owner_a(kind, rec):
    return rec["observation_A_ns"] if kind == "daily_observations" else rec["reference_A_ns"]


def owner_id(kind, rec):
    return rec["observation_id"] if kind == "daily_observations" else rec["target_id"]


# ------------------------------------------------------------------ stage 5
def check_input_ids(ctx, binput, path):
    if binput["kind"] == "raw":
        if binput["definition_id"] not in ctx.defs:
            fail("missing_identity", path + "/definition_id", 5)
        if binput["reference_id"] not in ctx.refs:
            fail("missing_identity", path + "/reference_id", 5)
    elif binput["kind"] == "qualified":
        if binput["certificate_id"] not in ctx.bcerts:
            fail("missing_identity", path + "/certificate_id", 5)
    else:
        if binput["control_id"] not in ctx.controls:
            fail("missing_identity", path + "/control_id", 5)


def stage5(ctx):
    s = ctx.snap
    sel = selected(ctx)
    for i, o in enumerate(s["daily_observations"]):
        if o["observation_id"] not in sel["dailies"]:
            continue
        base = "%s/daily_observations/%d" % (SNAP, i)
        if o["scope_id"] not in ctx.scopes:
            fail("missing_identity", base + "/scope_id", 5)
        if o["session_frame_id"] not in ctx.frames:
            fail("missing_identity", base + "/session_frame_id", 5)
        check_input_ids(ctx, o["bucket_input"], base + "/bucket_input")
        cid = o["admission"]["certificate_id"]
        if cid is not None and cid not in ctx.dcerts:
            fail("missing_identity", base + "/admission/certificate_id", 5)
        for fld in ("eligibility_control_id", "slot_control_id"):
            if o[fld] not in ctx.controls:
                fail("missing_identity", "%s/%s" % (base, fld), 5)
    for i, b in enumerate(s["baseline_slots"]):
        if b["slot_id"] not in sel["slots"]:
            continue
        base = "%s/baseline_slots/%d" % (SNAP, i)
        if b["scope_id"] not in ctx.scopes:
            fail("missing_identity", base + "/scope_id", 5)
        for j, oid in enumerate(b["observation_ids"]):
            if oid not in ctx.dailies:
                fail("missing_identity", "%s/observation_ids/%d" % (base, j), 5)
        if b["control_id"] not in ctx.controls:
            fail("missing_identity", base + "/control_id", 5)
    for i, f in enumerate(s["session_frames"]):
        if f["frame_id"] not in sel["frames"]:
            continue
        base = "%s/session_frames/%d" % (SNAP, i)
        if f["scope_id"] not in ctx.scopes:
            fail("missing_identity", base + "/scope_id", 5)
        if f["boundary_control_id"] not in ctx.controls:
            fail("missing_identity", base + "/boundary_control_id", 5)
    for i, t in enumerate(s["activity_targets"]):
        if t["target_id"] not in sel["targets"]:
            continue
        base = "%s/activity_targets/%d" % (SNAP, i)
        if t["scope_id"] not in ctx.scopes:
            fail("missing_identity", base + "/scope_id", 5)
        if t["session_frame_id"] not in ctx.frames:
            fail("missing_identity", base + "/session_frame_id", 5)
        if t["bucket_policy_id"] not in ctx.bpolicies:
            fail("missing_identity", base + "/bucket_policy_id", 5)
        check_input_ids(ctx, t["bucket_input"], base + "/bucket_input")
    for kind, i, rec in owners(ctx):
        bi = rec["bucket_input"]
        if bi["kind"] == "qualified" and bi["certificate_id"] in ctx.bcerts:
            c = ctx.bcerts[bi["certificate_id"]]
            check_input_ids(ctx, c["core"]["raw"], "%s/bucket_certificates/%d/core/raw" % (
                SNAP, s["bucket_certificates"].index(c)))
    for i, c in enumerate(s["daily_activity_certificates"]):
        base = "%s/daily_activity_certificates/%d/core" % (SNAP, i)
        if c["core"]["observation_id"] not in ctx.dailies:
            pass


def stage5_request(ctx, o, op):
    base = "%s/operations/%d" % (REQ, o)
    if op["kind"] == "current_activity" and op["target_id"] not in ctx.targets:
        fail("missing_identity", base + "/target_id", 5)
    if op["kind"] == "baseline":
        if op["bucket_policy_id"] not in ctx.bpolicies:
            fail("missing_identity", base + "/bucket_policy_id", 5)
        for i, sid in enumerate(op["slot_ids"]):
            if sid not in ctx.slots:
                fail("missing_identity", "%s/slot_ids/%d" % (base, i), 5)
    if op["kind"] == "baseline_consumer":
        for fld in ("baseline_op_id", "current_op_id"):
            if op[fld] not in ctx.ops:
                fail("missing_identity", "%s/%s" % (base, fld), 5)


# ------------------------------------------------------------------ stage 6
def check_raw(ctx, kind, rec, raw, path, full_session=None):
    """Raw bucket operand relationships (first mismatch in declaration order)."""
    scope = ctx.scopes[rec["scope_id"]]
    d = ctx.defs[raw["definition_id"]]
    ref = ctx.refs[raw["reference_id"]]
    a_ns = owner_a(kind, rec)
    bad = None
    if (d["contract_id"] != rec["contract_id"] or d["underlying_id"] != scope["underlying_id"] or
            d["currency"] != scope["currency"] or d["action_basis_id"] != scope["action_basis_id"] or
            d["deliverable_basis_id"] != scope["deliverable_basis_id"] or
            d["definition_basis_id"] != scope["definition_basis_id"] or d["right"] != rec["right"] or
            d["eligibility"] != "scalar_standard" or d["expiry_day"] is None or
            not _in_interval(d["effective"], raw["reference_instant_ns"])):
        bad = "definition_id"
    elif ref["contract_id"] != rec["contract_id"] or ref["civil_day"] is None or ref["spot"] is None:
        bad = "reference_id"
    elif (raw["reference_instant_ns"] != ref["civil_instant_ns"] or raw["reference_instant_ns"] > a_ns or
          (kind == "activity_targets" and raw["reference_instant_ns"] != rec["reference_instant_ns"]) or
          (full_session is not None and not _in_interval(full_session, raw["reference_instant_ns"]))):
        bad = "reference_instant_ns"
    elif raw["event_day"] != ref["civil_day"] or raw["event_day"] != scope["session_day"]:
        bad = "event_day"
    elif raw["expiry_day"] != d["expiry_day"]:
        bad = "expiry_day"
    elif raw["strike"] != d["strike"]:
        bad = "strike"
    elif raw["spot"] != ref["spot"]:
        bad = "spot"
    elif raw["calendar_id"] != ref["calendar_id"]:
        bad = "calendar_id"
    elif raw["calendar_revision"] != ref["calendar_revision"]:
        bad = "calendar_revision"
    if bad is not None:
        fail("identity_mismatch", "%s/%s" % (path, bad), 6)


def recompute(raw):
    dte = raw["expiry_day"] - raw["event_day"]
    try:
        z = N.div(b2f(raw["strike"]), b2f(raw["spot"]))
    except N.NumericOverflow:
        z = None
    return dte, z


def check_cert(ctx, ci, cert, owner_kind, owner_rec, bi_path, binput):
    """BucketCertificate relationship to its owner (derived input first, then core, then producer)."""
    base = "%s/bucket_certificates/%d" % (SNAP, ci)
    core = cert["core"]
    raw = core["raw"]
    if core["owner_id"] != owner_id(owner_kind, owner_rec):
        fail("identity_mismatch", base + "/core/owner_id", 6)
    for fld in ("contract_id", "scope_id", "session_frame_id", "right"):
        want = owner_rec[fld if fld != "session_frame_id" else "session_frame_id"]
        if core[fld] != want:
            fail("identity_mismatch", "%s/core/%s" % (base, fld), 6)
    if core["reference_A_ns"] != owner_a(owner_kind, owner_rec):
        fail("identity_mismatch", base + "/core/reference_A_ns", 6)
    check_raw(ctx, owner_kind, owner_rec, raw, base + "/core/raw")
    dte, z = recompute(raw)
    if binput is not None:
        if binput["dte_days"] != dte:
            fail("identity_mismatch", bi_path + "/dte_days", 6)
        if z is not None and b2f(binput["moneyness"]) != z:
            fail("identity_mismatch", bi_path + "/moneyness", 6)
    if core["dte_days"] != dte:
        fail("identity_mismatch", base + "/core/dte_days", 6)
    if z is not None and b2f(core["moneyness"]) != z:
        fail("identity_mismatch", base + "/core/moneyness", 6)
    pr = cert["producer"]
    if pr["producer_cohort_sha256"] != ctx.cohort:
        fail("identity_mismatch", base + "/producer/producer_cohort_sha256", 6)
    if pr["output_record_sha256"] != ctx.rd("variant_BucketCore", core):
        fail("identity_mismatch", base + "/producer/output_record_sha256", 6)


def stage6(ctx):
    for kind, i, rec in owners(ctx):
        base = "%s/%s/%d" % (SNAP, kind, i)
        frame = ctx.frames[rec["session_frame_id"]]
        binput = rec["bucket_input"]
        if kind == "daily_observations":
            daily_compat(ctx, i, rec, frame)
        if binput["kind"] == "raw":
            check_raw(ctx, kind, rec, binput, base + "/bucket_input", frame["full_session"])
        elif binput["kind"] == "qualified":
            cert = ctx.bcerts[binput["certificate_id"]]
            ci = ctx.snap["bucket_certificates"].index(cert)
            check_cert(ctx, ci, cert, kind, rec, base + "/bucket_input", binput)
        else:
            c = ctx.controls[binput["control_id"]]
            if (c["kind"] != "reference_absence" or c["scope_id"] != rec["scope_id"] or
                    rec["contract_id"] not in c["expected_contract_ids"] or not c["complete"] or
                    c["event_domain"]["start_ns"] != c["event_domain"]["end_ns"]):
                fail("identity_mismatch", base + "/bucket_input/control_id", 6)
    for kind, i, rec in owners(ctx):
        if kind == "daily_observations":
            daily_admission(ctx, i, rec)
    slot_checks(ctx)
    for i, f in enumerate(ctx.snap["session_frames"]):
        if f["frame_id"] not in selected(ctx)["frames"]:
            continue
        base = "%s/session_frames/%d" % (SNAP, i)
        sc = ctx.scopes[f["scope_id"]]
        c = ctx.controls[f["boundary_control_id"]]
        if (sc["session_day"] != f["session_day"] or c["kind"] != "session_boundary" or c["scope_id"] != f["scope_id"] or
                c["event_domain"] != f["full_session"] or not c["complete"]):
            fail("identity_mismatch", base + "/boundary_control_id", 6)


def daily_compat(ctx, i, o, frame):
    base = "%s/daily_observations/%d" % (SNAP, i)
    sc = ctx.scopes[o["scope_id"]]
    if o["contract_id"] not in sc["contract_ids"]:
        fail("identity_mismatch", base + "/contract_id", 6)
    if o["session_day"] != sc["session_day"]:
        fail("identity_mismatch", base + "/session_day", 6)
    if frame["scope_id"] != o["scope_id"] or frame["session_day"] != o["session_day"]:
        fail("identity_mismatch", base + "/session_frame_id", 6)
    if o["session_interval"] != frame["full_session"]:
        fail("identity_mismatch", base + "/session_interval", 6)


def daily_admission(ctx, i, o):
    base = "%s/daily_observations/%d" % (SNAP, i)
    ops = [op for op in ctx.req["operations"] if op["kind"] == "baseline" and
           any(o["observation_id"] in ctx.slots[sid]["observation_ids"] for sid in op["slot_ids"] if sid in ctx.slots)]
    for op in ops:
        if o["admission"]["basis"] != op["activity_basis"]:
            fail("identity_mismatch", base + "/admission/basis", 6)
    cid = o["admission"]["certificate_id"]
    if cid is None:
        return
    cert = ctx.dcerts[cid]
    ci = ctx.snap["daily_activity_certificates"].index(cert)
    cb = "%s/daily_activity_certificates/%d" % (SNAP, ci)
    core = cert["core"]
    for fld in ("observation_id", "scope_id", "contract_id", "session_frame_id", "session_day", "right",
                "observation_A_ns", "bucket_input"):
        if core[fld] != o[fld]:
            fail("identity_mismatch", "%s/core/%s" % (cb, fld), 6)
    if core["basis"] != o["admission"]["basis"]:
        fail("identity_mismatch", cb + "/core/basis", 6)
    pr = cert["producer"]
    if pr["producer_cohort_sha256"] != ctx.cohort:
        fail("identity_mismatch", cb + "/producer/producer_cohort_sha256", 6)
    if pr["output_record_sha256"] != ctx.rd("variant_DailyActivityCore", core):
        fail("identity_mismatch", cb + "/producer/output_record_sha256", 6)
    for fld in ("contracts", "trade_count", "premium"):
        for sub in ("kind", "value", "reason"):
            if core[fld][sub] != o[fld][sub]:
                fail("identity_mismatch", "%s/%s/%s" % (base, fld, sub), 6)
    if core["membership_complete"]:
        for fld, cnt in (("contracts", "observed_positive_contracts"), ("trade_count", "observed_positive_trade_count")):
            mi = o[fld]
            if mi["kind"] == "present" and mi["value"] != f2b(N.rn_int(core[cnt])):
                fail("identity_mismatch", "%s/%s/value" % (base, fld), 6)


def slot_checks(ctx):
    sel = selected(ctx)
    for b, sl in enumerate(ctx.snap["baseline_slots"]):
        if sl["slot_id"] not in sel["slots"]:
            continue
        if sl["session_day"] != ctx.scopes[sl["scope_id"]]["session_day"]:
            fail("identity_mismatch", "%s/baseline_slots/%d/session_day" % (SNAP, b), 6)
    seen = set()
    for op in ctx.req["operations"]:
        if op["kind"] != "baseline":
            continue
        for sid in op["slot_ids"]:
            sl = ctx.slots.get(sid)
            if sl is None:
                continue
            b = ctx.snap["baseline_slots"].index(sl)
            for j, oid in enumerate(sl["observation_ids"]):
                o = ctx.dailies[oid]
                key = (o["contract_id"], o["session_day"])
                if key in seen:
                    fail("identity_conflict", "%s/baseline_slots/%d/observation_ids/%d" % (SNAP, b, j), 6)
                seen.add(key)


def stage6_request(ctx, o, op):
    base = "%s/operations/%d" % (REQ, o)
    if op["kind"] == "baseline":
        for j, sid in enumerate(op["slot_ids"]):
            if ctx.slots[sid]["session_day"] >= op["asof_day"]:
                fail("identity_mismatch", "%s/slot_ids/%d" % (base, j), 6)
    if op["kind"] == "baseline_consumer":
        bop, cop = ctx.ops[op["baseline_op_id"]], ctx.ops[op["current_op_id"]]
        if bop["kind"] != "baseline":
            fail("identity_mismatch", base + "/baseline_op_id", 6)
        if cop["kind"] != "current_activity":
            fail("identity_mismatch", base + "/current_op_id", 6)
        if not keys_compatible(ctx, bop, cop):
            fail("identity_mismatch", base + "/baseline_op_id", 6)


def keys_compatible(ctx, bop, cop):
    from . import buckets as B
    from .current import basis_of
    bscope = ctx.scopes[bop["scope_id"]]
    target = ctx.targets[cop["target_id"]]
    cscope = ctx.scopes[target["scope_id"]]
    bp = ctx.bpolicies[bop["bucket_policy_id"]]
    tbp = ctx.bpolicies[target["bucket_policy_id"]]
    if ctx.rd("variant_BucketPolicy", bp) != ctx.rd("variant_BucketPolicy", tbp):
        return False
    if bop["activity_basis"] != basis_of(cop) or bop["right"] != target["right"]:
        return False
    for fld in ("underlying_id", "currency", "action_basis_id", "deliverable_basis_id", "definition_basis_id",
                "population_universe_id"):
        if bscope[fld] != cscope[fld]:
            return False
    if bop["route"] == "contract-session1" and bscope["contract_ids"][0] != target["contract_id"]:
        return False
    if bop["asof_day"] > cscope["session_day"]:
        return False
    try:
        bk = B.derive(ctx, target["target_id"], target["reference_A_ns"], target["right"], tbp, target["bucket_input"])
    except N.NumericOverflow:
        return True
    if bk.ok and (bk.dte_key != bop["dte_bucket"] or bk.mon_key != bop["moneyness_bucket"]):
        return False
    return True


# ------------------------------------------------------------------ stage 7
def stage7(ctx):
    for kind, i, rec in owners(ctx):
        base = "%s/%s/%d/bucket_input" % (SNAP, kind, i)
        binput = rec["bucket_input"]
        a_ns = owner_a(kind, rec)
        if binput["kind"] == "raw":
            _raw7(ctx, binput, a_ns, base)
        elif binput["kind"] == "qualified":
            cert = ctx.bcerts[binput["certificate_id"]]
            if not ctx.vis_A(cert["stamp"], a_ns):
                fail("temporal_cut", base + "/certificate_id", 7)
        else:
            c = ctx.controls[binput["control_id"]]
            if not ctx.vis_A(c["stamp"], a_ns):
                fail("temporal_cut", base + "/control_id", 7)
    for kind, i, rec in owners(ctx):
        if kind == "daily_observations":
            cid = rec["admission"]["certificate_id"]
            if cid is not None and not ctx.vis_K(ctx.dcerts[cid]["stamp"]):
                fail("temporal_cut", "%s/daily_observations/%d/admission/certificate_id" % (SNAP, i), 7)
    for i, f in enumerate(ctx.snap["session_frames"]):
        if f["frame_id"] not in selected(ctx)["frames"]:
            continue
        c = ctx.controls[f["boundary_control_id"]]
        if not ctx.vis_K(c["stamp"]):
            fail("temporal_cut", "%s/session_frames/%d/boundary_control_id" % (SNAP, i), 7)


def _raw7(ctx, raw, a_ns, base):
    d = ctx.defs[raw["definition_id"]]
    ref = ctx.refs[raw["reference_id"]]
    if not ctx.vis_A(d["stamp"], a_ns):
        fail("temporal_cut", base + "/definition_id", 7)
    for stamp in (ref["civil_stamp"], ref["spot_stamp"]):
        if stamp is not None and not ctx.vis_A(stamp, a_ns):
            fail("temporal_cut", base + "/reference_id", 7)
