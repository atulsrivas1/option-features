"""BaselineOp (three full-session routes, DailyCore, statistics) and the finite baseline consumers."""
import math
from option_feature_contracts.variants1.canonical import b2f, b64num, f2b, record_digest
from . import numeric as N
from . import buckets as B
from .context import Deps, make_evidence
from .results import metric, unavailable_metric, row as mkrow, receipt, aggregate

FAMILY = "option-flow-variants-baseline-daily1"
PROFILE = "binary64-rne-each-op-no-fma1"
METRICS = [("contracts", "contracts", "contracts"), ("trade_count", "trade_count", "executions"),
           ("premium", "premium", "currency")]   # (daily/statistic id, MetricInput field, unit)
REASON_ORDER = ["missing_reference", "future_reference", "incomplete_baseline"]


class Slot:
    pass


def _bind(ctx, deps, binding_id, use):
    b = ctx.bindings[binding_id]
    deps.add("variant_Binding", binding_id, ctx.rd("variant_Binding", b), use, 0)


def _dep(ctx, deps, rtype, rec, rid, use, known):
    h = ctx.rd(rtype, rec)
    deps.add(rtype, rid, h, use, known)
    return h


def slot_info(ctx, op, bp, sid):
    """Resolve one selected slot: observations, bucket witnesses, selection and readiness."""
    sl = ctx.slots[sid]
    s = Slot()
    s.slot = sl
    s.ctl = ctx.controls[sl["control_id"]]
    s.obs = [ctx.dailies[i] for i in sl["observation_ids"]]
    s.bk = {}
    s.selected, s.excluded = [], []
    s.missing = None            # reason when the slot cannot form a daily reduction
    s.diag = []
    s.domain = []
    for o in s.obs:
        bk = B.derive(ctx, o["observation_id"], o["observation_A_ns"], o["right"], bp, o["bucket_input"])
        s.bk[o["observation_id"]] = bk
        if bk.domain is not None:
            s.domain.append(bk.domain)
        if not bk.ok:
            if s.missing not in ("missing_reference", "future_reference") or bk.reason == "missing_reference":
                s.missing = bk.reason
            continue
        if o["right"] == op["right"] and bk.dte_key == op["dte_bucket"] and bk.mon_key == op["moneyness_bucket"]:
            s.selected.append(o)
        else:
            s.excluded.append(o)
    if s.missing is not None:
        return s
    exp = set(sl["expected_contract_ids"])
    have = {o["contract_id"] for o in s.selected}
    if not s.ctl["complete"] or s.ctl["reason"] != "prior_slot_present" or exp != have:
        s.missing = "incomplete_baseline"
        return s
    for o in s.selected:
        cid = o["admission"]["certificate_id"]
        if cid is None:
            s.missing = "incomplete_baseline"
            return s
        cert = ctx.dcerts[cid]
        if not cert["core"]["membership_complete"]:
            s.missing = "premium_unavailable"
            return s
    return s


def daily_reduction(ctx, op, pol_hash, scope, s, bp, observed_order):
    sl = s.slot
    sel = s.selected
    route = op["route"]
    if route == "pooled-divide-before-fold1":
        order = sorted(sel, key=lambda o: (o["session_day"], o["contract_id"]))
    elif route == "pooled-fold-before-divide1":
        order = sorted(sel, key=lambda o: o["observation_ordinal"])
    else:
        order = list(sel)
    n = len(order)
    mets = {}
    diag = []
    for mid, fld, unit in METRICS:
        vals = [o[fld] for o in order]
        if any(v["kind"] != "present" for v in vals):
            mets[mid] = unavailable_metric(mid, unit, "incomplete_baseline")
            for o in order:
                if o[fld]["kind"] != "present":
                    diag.append(("incomplete_baseline", o["observation_id"]))
            continue
        xs = [b2f(v["value"]) for v in vals]
        if route == "contract-session1":
            val = xs[0]
        elif route == "pooled-divide-before-fold1":
            nf = N.rn_int(n)
            val = 0.0
            for x in xs:
                val = N.add(val, N.div(x, nf))
        else:
            val = 0.0
            for x in xs:
                val = N.add(val, x)
            val = N.div(val, N.rn_int(n))
        mets[mid] = metric(mid, unit, b64num(val), branch="complete_empty" if val == 0.0 else "ordinary")
    core = {
        "bucket_witnesses": [s.bk[o["observation_id"]].witness for o in order],
        "contract_ids": [o["contract_id"] for o in order],
        "contracts": mets["contracts"], "dte_bucket": op["dte_bucket"], "eligible_count": n,
        "moneyness_bucket": op["moneyness_bucket"], "observation_ids": [o["observation_id"] for o in order],
        "premium": mets["premium"], "route": route, "session_day": sl["session_day"], "slot_id": sl["slot_id"],
        "trade_count": mets["trade_count"],
    }
    hashes = {pol_hash}
    for sc in {op["scope_id"], sl["scope_id"]} | {o["scope_id"] for o in s.obs}:
        hashes.add(ctx.rd("variant_Scope", ctx.scopes[sc]))
    hashes.add(ctx.rd("variant_BaselineSlot", sl))
    hashes.add(ctx.rd("variant_Control", s.ctl))
    hashes.add(ctx.rd("variant_BucketPolicy", bp))
    for o in s.obs:
        hashes.add(ctx.rd("variant_DailyObservation", o))
        fr = ctx.frames[o["session_frame_id"]]
        hashes.add(ctx.rd("variant_SessionFrame", fr))
        hashes.add(ctx.rd("variant_Control", ctx.controls[fr["boundary_control_id"]]))
        for fld in ("eligibility_control_id", "slot_control_id"):
            hashes.add(ctx.rd("variant_Control", ctx.controls[o[fld]]))
        bk = s.bk[o["observation_id"]]
        for rtype, rid, rh, use, known in bk.deps:
            hashes.add(rh)
        cid = o["admission"]["certificate_id"]
        if cid is not None:
            hashes.add(ctx.rd("variant_DailyActivityCertificate", ctx.dcerts[cid]))
    prod = {"formula_id": route, "input_record_sha256s": sorted(hashes), "numeric_profile": PROFILE,
            "output_record_sha256": record_digest("variant_DailyCore", core), "policy_sha256": pol_hash,
            "producer_cohort_sha256": ctx.cohort, "producer_family": FAMILY}
    red = dict(core)
    red["producer"] = prod
    return red, diag


def sort_key(item):
    v, idx = item
    return (v, 0 if (v == 0.0 and math.copysign(1.0, v) < 0) else 1, idx)


def statistic(ctx, op, mid, unit, series, miss_reason, nslots):
    """series: list of (slot_id, value-or-None); miss_reason: closed reason when a selected slot/metric is missing."""
    qs = op["quantiles"]
    n_unavail = miss_reason is not None

    def unav(name, reason):
        return unavailable_metric(name, unit, reason)

    def mk(reason, samples=0, ids=(), bits=()):
        return {"mad": unav("mad", reason), "mean": unav("mean", reason) if op["include_mean"] else None,
                "median": unav("median", reason), "metric_id": mid,
                "quantiles": [{"probability": q, "value": unav("quantile", reason)} for q in qs],
                "sample_slot_ids": list(ids), "samples": samples, "sorted_sample_bits": list(bits)}
    if nslots == 0 and miss_reason is None:
        return mk("empty_baseline")
    items = sorted(((b2f(v), i, sid) for i, (sid, v) in enumerate(series)),
                   key=lambda t: (t[0], 0 if (t[0] == 0.0 and math.copysign(1.0, t[0]) < 0) else 1, t[1]))
    vals = [t[0] for t in items]
    ids = [t[2] for t in items]
    bits = [f2b(v) for v in vals]
    if miss_reason is not None:
        return mk(miss_reason, len(vals), ids, bits)
    if len(vals) < op["minimum_samples"]:
        return mk("insufficient_history", len(vals), ids, bits)
    half = 0.5
    med = N.quantile(vals, half)
    devs = sorted(((abs(N.sub(v, med)), i) for i, v in enumerate(vals)),
                  key=lambda t: (t[0], 0 if (t[0] == 0.0 and math.copysign(1.0, t[0]) < 0) else 1, t[1]))
    mad = N.quantile([d[0] for d in devs], half)
    out = {"mad": metric("mad", unit, b64num(mad)), "median": metric("median", unit, b64num(med)),
           "metric_id": mid,
           "quantiles": [{"probability": q, "value": metric("quantile", unit, b64num(N.quantile(vals, b2f(q))))}
                         for q in qs],
           "sample_slot_ids": ids, "samples": len(vals), "sorted_sample_bits": bits}
    if op["include_mean"]:
        tot = 0.0
        for v in vals:
            tot = N.add(tot, v)
        out["mean"] = metric("mean", unit, b64num(N.div(tot, N.rn_int(len(vals)))))
    else:
        out["mean"] = None
    return out


def baseline(ctx, oi, op):
    scope = ctx.scopes[op["scope_id"]]
    bp = ctx.bpolicies[op["bucket_policy_id"]]
    pol_hash = ctx.policy_hash(op["policy_id"])
    infos = [slot_info(ctx, op, bp, sid) for sid in op["slot_ids"]]
    deps = Deps()
    controls = []
    all_cap = bool(infos)
    for s in infos:
        sl = s.slot
        ctl = s.ctl
        _dep(ctx, deps, "variant_BaselineSlot", sl, sl["slot_id"], "baseline", ctl["stamp"]["known_at_ns"])
        for c in [ctl] + [ctx.controls[ctx.frames[o["session_frame_id"]]["boundary_control_id"]] for o in s.obs] + \
                [ctx.controls[o["eligibility_control_id"]] for o in s.obs]:
            _dep(ctx, deps, "variant_Control", c, c["control_id"], "baseline", c["stamp"]["known_at_ns"])
            _bind(ctx, deps, c["stamp"]["binding_id"], "baseline")
            controls.append(c["control_id"])
        _bind(ctx, deps, ctl["stamp"]["binding_id"], "baseline")
        if not ctl["complete"]:
            all_cap = False
        for o in s.obs:
            fr = ctx.frames[o["session_frame_id"]]
            bc = ctx.controls[fr["boundary_control_id"]]
            _dep(ctx, deps, "variant_SessionFrame", fr, fr["frame_id"], "baseline", bc["stamp"]["known_at_ns"])
            _dep(ctx, deps, "variant_DailyObservation", o, o["observation_id"], "baseline", o["stamp"]["known_at_ns"])
            _bind(ctx, deps, o["stamp"]["binding_id"], "baseline")
            cid = o["admission"]["certificate_id"]
            if cid is not None:
                cert = ctx.dcerts[cid]
                _dep(ctx, deps, "variant_DailyActivityCertificate", cert, cid, "baseline", cert["stamp"]["known_at_ns"])
                _bind(ctx, deps, cert["stamp"]["binding_id"], "baseline")
            bk = s.bk[o["observation_id"]]
            for rtype, rid, rh, use, known in bk.deps:
                deps.add(rtype, rid, rh, "baseline", known)
                if rtype == "variant_Control":
                    controls.append(rid)
                    _bind(ctx, deps, ctx.controls[rid]["stamp"]["binding_id"], "baseline")
                elif rtype == "variant_Definition":
                    _bind(ctx, deps, ctx.defs[rid]["stamp"]["binding_id"], "baseline")
    if not any(d["record_type"] == "variant_Binding" for d in deps.d.values()):
        for b in ctx.snap["bindings"]:
            _bind(ctx, deps, b["binding_id"], "baseline")
    deps.add("variant_Scope", scope["scope_id"], ctx.rd("variant_Scope", scope), "policy", 0)
    for s in infos:
        sc = ctx.scopes[s.slot["scope_id"]]
        deps.add("variant_Scope", sc["scope_id"], ctx.rd("variant_Scope", sc), "policy", 0)
        for o in s.obs:
            sc = ctx.scopes[o["scope_id"]]
            deps.add("variant_Scope", sc["scope_id"], ctx.rd("variant_Scope", sc), "policy", 0)
    deps.add("variant_Policy", op["policy_id"], pol_hash, "policy", 0)
    deps.add("variant_BucketPolicy", bp["policy_id"], ctx.rd("variant_BucketPolicy", bp), "policy", 0)
    daily, diags, missing = [], [], []
    miss_reasons = []
    for s in infos:
        if s.missing is not None:
            missing.append(s.slot["slot_id"])
            miss_reasons.append(s.missing)
            diags.append((s.missing, s.slot["slot_id"]))
            continue
        red, d = daily_reduction(ctx, op, pol_hash, scope, s, bp, None)
        daily.append(red)
        diags += d
    key_unknown = any(m in ("missing_reference", "future_reference") for m in miss_reasons)
    key = None
    if not key_unknown:
        contract = scope["contract_ids"][0] if op["route"] == "contract-session1" else None
        key = B.activity_key(ctx, scope, contract, op["right"], op["activity_basis"], bp, op["dte_bucket"],
                             op["moneyness_bucket"])
    # statistics
    gap = None
    for r in REASON_ORDER:
        if r in miss_reasons or (r == "incomplete_baseline" and any(m == "premium_unavailable" for m in miss_reasons)):
            gap = r
            break
    stats = []
    for mid, fld, unit in METRICS:
        reason = gap
        series = []
        for red in daily:
            m = red[mid]
            if m["status"] != "available":
                reason = reason or "incomplete_baseline"
            else:
                series.append((red["slot_id"], b2f(m["value"]["bits"])))
        series = [(sid, f2b(v)) for sid, v in series]
        stats.append(statistic(ctx, op, mid, unit, series, reason, len(infos)))
    ev = make_evidence(deps, (), (), (), (), (), controls, capture_complete=all_cap, context_complete=False,
                       eligibility=None, bucket_domain_evidence=sorted(
                           [d for s in infos for d in s.domain], key=lambda d: d["owner_id"]))
    value = {"activity_key": key, "asof_day": op["asof_day"], "coverage": op["coverage"], "daily": daily,
             "missing_slot_ids": missing, "route": op["route"], "slot_ids": list(op["slot_ids"]),
             "statistics": stats}
    pairs = []
    for red in daily:
        for mid, _, _ in METRICS:
            pairs.append((red[mid]["status"], red[mid]["reason"]))
    for st in stats:
        for m in (st["median"], st["mad"], st["mean"]) + tuple(q["value"] for q in st["quantiles"]):
            if m is not None:
                pairs.append((m["status"], m["reason"]))
    st_, rs_ = aggregate(pairs)
    row = mkrow(ctx, op, None, "baseline", value, ev, diags, ctx.snapshot_hash, ctx.request_hash)
    return receipt(op, 1, st_, rs_, ev), [row]


# ------------------------------------------------------------------ consumer
CONSUMER_METRIC = {"relative_contracts": ("contracts", "positive_eligible_contracts", "contracts"),
                   "relative_trades": ("trade_count", "positive_eligible_trade_count", "executions"),
                   "premium_robust_z": ("premium", "premium", "currency")}


def rename(m, name, unit=None):
    if m is None:
        return None
    out = dict(m)
    out["metric_id"] = name
    return out


def consumer(ctx, oi, op, done):
    pol = ctx.policies[op["policy_id"]]
    brc, brows = done[op["baseline_op_id"]]
    crc, crows = done[op["current_op_id"]]
    bval = brows[0]["payload"]["value"]
    cval = crows[0]["payload"]["value"]
    sid, cmid, unit = CONSUMER_METRIC[op["metric"]]
    stat = next(s for s in bval["statistics"] if s["metric_id"] == sid)
    cm = next(m for m in cval["metrics"] if m["metric_id"] == cmid)
    # current operands
    ident_bad = cval["identity_status"] != "available" or bval["activity_key"] is None
    ident_reason = cval["identity_reason"] if cval["identity_status"] != "available" else "missing_reference"
    if cm["status"] == "available":
        if op["metric"] == "premium_robust_z":
            x = b2f(cm["value"]["bits"])
            raw = rename(cm, "current_raw")
            b64 = rename(cm, "current_b64")
        else:
            qf = N.rn_int(int(cm["value"]["integer"]))
            raw = rename(cm, "current_raw")
            b64 = metric("current_b64", unit, b64num(qf), branch="complete_empty" if cm["branch"] == "complete_empty" else "ordinary")
            x = qf
    else:
        raw = rename(cm, "current_raw")
        b64 = unavailable_metric("current_b64", unit, cm["reason"])
        x = None
    med = rename(stat["median"], "median")
    mad = rename(stat["mad"], "mad") if op["metric"] == "premium_robust_z" else None
    scale = pol["mad_scale"] if op["metric"] == "premium_robust_z" else None
    F = b2f(pol["sentinel"])
    rd = unit if op["metric"] != "premium_robust_z" else "mad_z"
    res_unit = "ratio" if op["metric"] != "premium_robust_z" else "mad_z"
    if med["status"] != "available" or (mad is not None and mad["status"] != "available"):
        bad = med if med["status"] != "available" else mad
        result = unavailable_metric("result", res_unit, bad["reason"])
    elif ident_bad:
        result = unavailable_metric("result", res_unit, ident_reason)
    elif x is None:
        result = unavailable_metric("result", res_unit, cm["reason"])
    else:
        m = b2f(med["value"]["bits"])
        if op["metric"] != "premium_robust_z":
            if m <= 0.0:
                if x > 0.0:
                    result = metric("result", res_unit, b64num(F), branch="finite_sentinel")
                else:
                    result = metric("result", res_unit, b64num(0.0), branch="nonpositive_baseline_zero")
            else:
                result = metric("result", res_unit, b64num(N.div(x, m)))
        else:
            a = b2f(mad["value"]["bits"])
            c = b2f(scale)
            if a <= 0.0:
                if x > m:
                    result = metric("result", res_unit, b64num(F), branch="finite_sentinel")
                else:
                    result = metric("result", res_unit, b64num(0.0), branch="nonpositive_baseline_zero")
            else:
                den = N.mul(c, a)
                result = metric("result", res_unit, b64num(N.div(N.sub(x, m), den)))
    deps = Deps()
    bev, cev = brows[0]["evidence"], crows[0]["evidence"]
    deps.add("variant_BaselineObject", op["baseline_op_id"], ctx.rd("variant_BaselineObject", bval), "baseline",
             bev["available_at_ns"])
    deps.add("variant_CurrentActivityObject", op["current_op_id"], ctx.rd("variant_CurrentActivityObject", cval),
             "economic", cev["available_at_ns"])
    scope = ctx.scopes[op["scope_id"]]
    deps.add("variant_Policy", op["policy_id"], ctx.policy_hash(op["policy_id"]), "policy", 0)
    deps.add("variant_Scope", scope["scope_id"], ctx.rd("variant_Scope", scope), "policy", 0)
    ev = make_evidence(deps, (), (), (), (), (), (), capture_complete=cev["capture_complete"], context_complete=False,
                       eligibility=None)
    value = {"baseline_op_id": op["baseline_op_id"], "current_b64": b64, "current_op_id": op["current_op_id"],
             "current_raw": raw, "mad": mad, "median": med, "result": result, "scale": scale,
             "sentinel": pol["sentinel"]}
    pairs = [(result["status"], result["reason"])]
    st, rs = aggregate(pairs)
    row = mkrow(ctx, op, None, "baseline_consumer", value, ev, [], ctx.snapshot_hash, ctx.request_hash)
    return receipt(op, 1, st, rs, ev), [row]
