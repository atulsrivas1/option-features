"""ConcentrationOp: three key families over the strict positive-premium population."""
from option_feature_contracts.variants1.canonical import b2f, b64num, canonical_json, record_digest
from . import numeric as N
from . import premium as P
from .context import Deps, make_evidence
from .flow import capture, order_members, premiums_for, eligibility_block, capture_deps, exclusion_deps
from .results import metric, unavailable_metric, row as mkrow, receipt, aggregate


def _price_float(rev):
    price = rev["price"]
    if price["kind"] == "b64":
        return b2f(price["bits"])
    return N.div(N.rn_int(int(price["ticks"])), N.rn_int(int(price["scale"])))


def _key(op, policy, res):
    rev = res["rev"]
    kind = op["key"]
    q = rev["quantity"]
    if kind == "integer-price-quantity1":
        p = rev["price"]
        return {"digits": None, "fixed_text": None, "kind": kind, "price_scale": p["scale"], "quantity": q,
                "raw_price_ticks": p["ticks"]}
    d = policy["format_digits"]
    x = _price_float(rev) if kind == "fixed-b64-price-quantity1" else b2f(res["premium"]["value"]["bits"])
    return {"digits": d, "fixed_text": N.fixed(x, d), "kind": kind, "price_scale": None, "quantity": q,
            "raw_price_ticks": None}


def concentration(ctx, oi, op):
    policy = ctx.policies[op["policy_id"]]
    cap = capture(ctx, op, oi)
    raw = order_members(cap.raw, op["order"], ctx)
    results = premiums_for(ctx, op, op["recipe"], raw)
    elig = eligibility_block(ctx, cap, results)
    unresolved = bool(elig["unresolved_ids"])
    positive = [r for r in results if r["outcome"] == "positive"]
    deps = Deps()
    capture_deps(ctx, cap, deps)
    exclusion_deps(ctx, cap, deps)
    controls = [c["control_id"] for c in cap.controls]
    for res in results:
        deps.update(res["deps"])
        deps.add("variant_PremiumCore", res["object_id"], res["object_id"], "numerical_eligibility", res["known"])
        controls += res["controls"]
    P.policy_scope_deps(ctx, deps, set(), op)
    groups = {}
    order = []
    for res in positive:
        key = _key(op, policy, res)
        kb = canonical_json(key)
        if kb not in groups:
            groups[kb] = {"key": key, "members": []}
            order.append(kb)
        groups[kb]["members"].append(res)
    reason = "incomplete_capture" if not cap.complete else ("premium_unavailable" if unresolved else None)
    buckets = []
    tied = []
    latest = max((ctx.new_rev(r["rev"]["root_id"])["event_ns"] for r in positive), default=None)
    if reason is not None:
        for kb in sorted(groups):
            g = groups[kb]
            buckets.append({"key": g["key"], "member_ids": [m["rev"]["root_id"] for m in g["members"]],
                            "premium": unavailable_metric("premium", "currency", reason),
                            "share": unavailable_metric("share", "ratio", reason)})
        total = unavailable_metric("total", "currency", reason)
        maxshare = unavailable_metric("maximum_share", "ratio", reason)
    elif not positive:
        total = metric("total", "currency", b64num(0.0), branch="complete_empty")
        maxshare = metric("maximum_share", "ratio", b64num(0.0), branch="complete_empty")
    else:
        T = 0.0
        for res in positive:
            T = N.add(T, b2f(res["premium"]["value"]["bits"]))
        best = 0.0
        shares = []
        for kb in sorted(groups):
            g = groups[kb]
            B = 0.0
            for m in g["members"]:
                B = N.add(B, b2f(m["premium"]["value"]["bits"]))
            sh = N.div(B, T)
            shares.append((kb, g, B, sh))
            if sh > best:
                best = sh
        for kb, g, B, sh in shares:
            buckets.append({"key": g["key"], "member_ids": [m["rev"]["root_id"] for m in g["members"]],
                            "premium": metric("premium", "currency", b64num(B)),
                            "share": metric("share", "ratio", b64num(sh))})
            if sh == best:
                tied.append(record_digest("variant_ConcentrationKey", g["key"]))
        total = metric("total", "currency", b64num(T))
        maxshare = metric("maximum_share", "ratio", b64num(best))
    ev = make_evidence(deps, [r["rev"]["root_id"] for r in positive], [r["rev"]["revision_id"] for r in positive], [], [],
                       list(elig["zero_excluded_ids"]) + list(cap.excluded), controls,
                       capture_complete=cap.complete, context_complete=False, eligibility=elig)
    value = {"buckets": buckets, "latest_event_ns": latest, "maximum_share": maxshare, "order": op["order"],
             "tied_key_sha256s": tied, "total": total}
    st, rs = aggregate([(total["status"], total["reason"]), (maxshare["status"], maxshare["reason"])])
    row = mkrow(ctx, op, None, "concentration", value, ev, [], ctx.snapshot_hash, ctx.request_hash)
    return receipt(op, 1, st, rs, ev), [row]
