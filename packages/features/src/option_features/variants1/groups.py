"""ParentOp: first-unassigned exclusive windows, repeated-price and multi-venue subsets."""
from option_feature_contracts.variants1.canonical import canonical_json, group_id as group_digest, i64num
from . import numeric as N
from . import premium as P
from . import signing as S
from .admission import interval_contains
from .context import Deps, make_evidence
from .flow import capture, capture_deps, exclusion_deps, definition_records
from .results import metric, unavailable_metric, row as mkrow, receipt, aggregate


def partition_key(res, side):
    d = res["definition"]
    return (res["rev"]["contract_id"], d["right"], d["strike"], d["expiry_day"], canonical_json(d["multiplier"]), side)


def lane_covers(ctx, op, scope, anchor_ns):
    need = {"start_ns": scope["partition_start_ns"], "end_ns": anchor_ns, "start_closed": True, "end_closed": True}
    for cid in op["lane_prefix_ids"]:
        c = ctx.controls[cid]
        if c["complete"] and c["kind"] == "lane_prefix" and interval_contains(c["event_domain"], need):
            return True
    return False


def capture_covers(cap, lo, hi):
    need = {"start_ns": lo, "end_ns": hi, "start_closed": True, "end_closed": False}
    return any(c["complete"] and interval_contains(c["event_domain"], need) for c in cap.controls) and cap.roots_visible


def lane_windows(ctx, members, w):
    """First-unassigned exclusive windows over lane members sorted by (event_ns, root_id)."""
    out, i = [], 0
    while i < len(members):
        a = ctx.new_rev(members[i]["rev"]["root_id"])["event_ns"]
        j = i
        win = []
        while j < len(members) and ctx.new_rev(members[j]["rev"]["root_id"])["event_ns"] < a + w:
            win.append(members[j])
            j += 1
        out.append((a, win))
        i = j
    return out


def parent_groups(ctx, oi, op):
    policy = ctx.policies[op["policy_id"]]
    scope = ctx.scopes[op["scope_id"]]
    basis = scope["monetary_basis"]
    pol_hash = ctx.policy_hash(op["policy_id"])
    w, lateness = policy["window_ns"], policy["lateness_ns"]
    cap = capture(ctx, op, oi)
    cap.roots_visible = True
    results = []
    for rev in sorted(cap.raw, key=lambda r: (ctx.new_rev(r["root_id"])["event_ns"], r["root_id"])):
        res = P.native_premium(ctx, op, "checked-integer-products1", rev)
        price = rev["price"]
        sr = S.sign_root(ctx, op, policy, res["new_rev"], scope, definition_records(ctx, rev), None,
                         (int(price["ticks"]), price["scale"]))
        res["sign"] = sr
        results.append(res)
    deps = Deps()
    capture_deps(ctx, cap, deps)
    exclusion_deps(ctx, cap, deps)
    controls = [c["control_id"] for c in cap.controls] + list(op["lane_prefix_ids"])
    for cid in op["lane_prefix_ids"]:
        c = ctx.controls[cid]
        deps.add("variant_Control", cid, ctx.rd("variant_Control", c), "capture", c["stamp"]["known_at_ns"])
        b = ctx.bindings[c["stamp"]["binding_id"]]
        deps.add("variant_Binding", b["binding_id"], ctx.rd("variant_Binding", b), "economic", 0)
    frontier = None
    if op["frontier_control_id"] is not None:
        frontier = ctx.controls[op["frontier_control_id"]]
        deps.add("variant_Control", frontier["control_id"], ctx.rd("variant_Control", frontier), "capture",
                 frontier["stamp"]["known_at_ns"])
        controls.append(frontier["control_id"])
        b = ctx.bindings[frontier["stamp"]["binding_id"]]
        deps.add("variant_Binding", b["binding_id"], ctx.rd("variant_Binding", b), "economic", 0)
    context_complete = True
    unknown_sign = []
    for res in results:
        deps.update(res["deps"])
        controls += res["controls"]
        sr = res["sign"]
        S.context_deps(ctx, sr, deps)
        if sr.control_id is not None:
            controls.append(sr.control_id)
        else:
            context_complete = False
        if sr.side == "unknown":
            unknown_sign.append(res["rev"]["root_id"])
    P.policy_scope_deps(ctx, deps, set(), op)
    # lanes
    lanes = {}
    for res in results:
        if res["definition"] is None or res["sign"].side == "unknown" or res["rev"]["price"]["kind"] != "integer":
            continue
        lanes.setdefault(partition_key(res, res["sign"].side), []).append(res)
    emit = ctx.req["emit"]
    groups = []
    for key in sorted(lanes):
        side = key[-1]
        for a_ns, win in lane_windows(ctx, lanes[key], w):
            if not _emit_has(emit, a_ns):
                continue
            complete = cap.complete and capture_covers(cap, a_ns, a_ns + w) and lane_covers(ctx, op, scope, a_ns)
            anchor = win[0]
            parent = (a_ns, win, anchor)
            if "parent" in op["kinds"]:
                groups.append(_group(ctx, op, policy, pol_hash, scope, basis, frontier, "parent", a_ns, anchor, anchor,
                                     win, None, side, complete, w, lateness))
            if "repeated_price" in op["kinds"]:
                byp = {}
                for r in win:
                    p = r["rev"]["price"]
                    byp.setdefault((p["ticks"], p["scale"]), []).append(r)
                for pk in sorted(byp, key=lambda k: (int(k[0]), int(k[1]))):
                    sub = byp[pk]
                    if len(sub) >= 2:
                        groups.append(_group(ctx, op, policy, pol_hash, scope, basis, frontier, "repeated_price", a_ns,
                                             anchor, sub[0], sub, pk, side, complete, w, lateness))
            if "multi_venue" in op["kinds"]:
                venues = {r["rev"]["venue_id"] for r in win if r["rev"]["venue_id"] is not None}
                if len(venues) >= 2:
                    groups.append(_group(ctx, op, policy, pol_hash, scope, basis, frontier, "multi_venue", a_ns, anchor,
                                         anchor, win, None, side, complete, w, lateness))
    all_ids = [r["rev"]["root_id"] for r in results]
    all_revs = [r["rev"]["revision_id"] for r in results]
    rows, pairs = [], []
    for g in groups:
        ev = make_evidence(deps, g["_members"], g["_revs"], unknown_sign, [], list(cap.excluded), controls,
                           capture_complete=cap.complete, context_complete=context_complete, eligibility=None)
        value = {k: v for k, v in g.items() if not k.startswith("_")}
        rows.append(mkrow(ctx, op, value["group_id"], "group", value, ev, [], ctx.snapshot_hash, ctx.request_hash))
        pairs.append((value["premium"]["status"], value["premium"]["reason"]))
    if not cap.complete:
        pairs.append(("unavailable", "incomplete_capture"))
    ev_op = make_evidence(deps, all_ids, all_revs, unknown_sign, [], list(cap.excluded), controls,
                          capture_complete=cap.complete, context_complete=context_complete, eligibility=None)
    st, rs = aggregate(pairs)
    return receipt(op, len(rows), st, rs, ev_op), rows


def _emit_has(iv, t):
    lo = t > iv["start_ns"] or (t == iv["start_ns"] and iv["start_closed"])
    hi = t < iv["end_ns"] or (t == iv["end_ns"] and iv["end_closed"])
    return lo and hi


def _group(ctx, op, policy, pol_hash, scope, basis, frontier, kind, a_ns, anchor, start, members, price_key, side,
           complete, w, lateness):
    start_ns = ctx.new_rev(start["rev"]["root_id"])["event_ns"]
    qty = 0
    prem_sum = 0
    reason = None
    for r in members:
        qty = N.cadd(qty, int(r["rev"]["quantity"]))
    if not complete:
        reason = "incomplete_capture"
    elif any(r["premium"]["status"] != "available" for r in members):
        reason = "premium_unavailable"
    else:
        try:
            for r in members:
                prem_sum = N.cadd(prem_sum, int(r["premium"]["value"]["integer"]))
        except N.NumericOverflow:
            reason = "premium_overflow"
    if reason is None:
        prem = metric("premium", "currency_ticks", i64num(prem_sum), basis=basis)
    else:
        prem = unavailable_metric("premium", "currency_ticks", reason, basis=basis)
    final = False
    if complete and frontier is not None and ctx.vis_K(frontier["stamp"]):
        final = frontier["event_domain"]["start_ns"] >= N.cadd(N.cadd(start_ns, w), lateness)
    venues = sorted({r["rev"]["venue_id"] for r in members if r["rev"]["venue_id"] is not None})
    unknown_v = [r["rev"]["root_id"] for r in members if r["rev"]["venue_id"] is None]
    ex = {"approximate_ids": [], "exact_ids": [], "unknown_ids": []}
    for r in members:
        ex[{"exact": "exact_ids", "approximate": "approximate_ids", "unknown": "unknown_ids"}[r["rev"]["exactness"]]].append(
            r["rev"]["root_id"])
    for k in ex:
        ex[k] = sorted(ex[k])
    tick, scale = (price_key if price_key is not None else (None, None))
    anchor_id = anchor["rev"]["root_id"]
    gid = group_digest(op["op_id"], op["scope_id"], kind, anchor_id, start["rev"]["root_id"], tick, scale, side,
                       pol_hash, basis)
    return {
        "contracts": qty, "count": len(members), "exact_price_ticks": tick, "exactness": ex,
        "finality": "final" if final else "pending",
        "frontier_control_id": op["frontier_control_id"], "group_id": gid, "kind": kind,
        "member_ids": [r["rev"]["root_id"] for r in members],
        "member_interval": {"end_closed": False, "end_ns": a_ns + w, "start_closed": True, "start_ns": a_ns},
        "member_revision_ids": [r["rev"]["revision_id"] for r in members],
        "membership_complete": complete, "monetary_basis": basis, "parent_anchor_id": anchor_id,
        "parent_anchor_ns": a_ns, "premium": prem, "price_scale": scale, "side": side,
        "subset_start_id": start["rev"]["root_id"], "subset_start_ns": start_ns,
        "venues": {"known_venue_ids": venues, "unknown_member_ids": sorted(unknown_v)},
        "_members": [r["rev"]["root_id"] for r in members], "_revs": [r["rev"]["revision_id"] for r in members],
    }
