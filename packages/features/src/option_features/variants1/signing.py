"""Origin-A quote context selection and sign witnesses (epsilon and paired profiles)."""
from option_feature_contracts.variants1.canonical import b2f, context_digest
from . import numeric as N
from .context import Deps
from .admission import interval_contains


def _chain_a(ctx, revs, a_ns):
    """A-visible chain prefix of a quote root (revisions linked by target_revision_id)."""
    by_target = {}
    for r in revs:
        by_target.setdefault(r["target_revision_id"], []).append(r)
    out, cur = [], by_target.get(None, [])
    while cur:
        r = cur[0]
        if not ctx.vis_A(r["stamp"], a_ns):
            break
        out.append(r)
        cur = by_target.get(r["revision_id"], [])
    return out


class SignResult:
    def __init__(self):
        self.side = "unknown"
        self.reason = "incomplete_context"
        self.quote_revision_id = None
        self.pairing_id = None
        self.records = []        # (record_type, record, stamp) selected context records
        self.control_id = None   # selected context_prefix control
        self.witness = None


def select_context_control(ctx, op, ex, new_rev, scope, a_ns):
    t = new_rev["event_ns"]
    cands = []
    for cid in op["context_ids"]:
        c = ctx.controls[cid]
        if not ctx.vis_A(c["stamp"], a_ns):
            continue
        if (c["kind"] != "context_prefix" or c["scope_id"] != ex["scope_id"] or not c["complete"] or
                c["decision"] != "not_applicable" or c["reason"] != "captured" or
                ex["contract_id"] not in c["expected_contract_ids"]):
            continue
        need = {"start_ns": scope["partition_start_ns"], "end_ns": t, "start_closed": True, "end_closed": True}
        if not interval_contains(c["event_domain"], need):
            continue
        cands.append(c)
    if not cands:
        return None
    cands.sort(key=lambda c: (c["stamp"]["known_at_ns"], c["stamp"]["stream_id"], c["stamp"]["position"], c["control_id"]))
    return cands[0]


def epsilon_side(p, b, h, e):
    """Ask-first epsilon rule on finite p>0, b>0, h>=b; returns (side, reason)."""
    if p >= N.sub(h, e):
        return "buy", "classified"
    if p <= N.add(b, e):
        return "sell", "classified"
    z = N.div(N.add(b, h), 2.0)
    if p > N.add(z, e):
        return "buy", "classified"
    if p < N.sub(z, e):
        return "sell", "classified"
    return "unknown", "dead_band"


def sign_root(ctx, op, policy, new_rev, scope, definition_rec_pairs, price_float, integer_trade=None):
    """Sign one root at its immutable A. `definition_rec_pairs` are the (type, record) DefinitionUse records."""
    a_ns = new_rev["signing_A_ns"]
    res = SignResult()
    res.records = [("variant_Execution", new_rev)] + list(definition_rec_pairs)
    ctl = select_context_control(ctx, op, new_rev, new_rev, scope, a_ns)
    if ctl is None:
        return res
    res.control_id = ctl["control_id"]
    res.records.append(("variant_Control", ctl))
    if policy["sign"]["kind"] == "paired":
        return _paired(ctx, policy, new_rev, scope, ctl, res, a_ns, integer_trade)
    return _epsilon(ctx, policy, new_rev, scope, ctl, res, a_ns, price_float)


def _matching_roots(ctx, ctl, ex, a_ns, t):
    """Per matching quote root: (quote_id, chain_a, terminal_active_or_None, immutable_event)."""
    out = []
    for qid in ctl["expected_root_ids"]:
        revs = ctx.qroots.get(qid, [])
        chain = _chain_a(ctx, revs, a_ns)
        if not chain:
            continue
        first = chain[0]
        if first["scope_id"] != ex["scope_id"] or first["contract_id"] != ex["contract_id"] or first["stamp"]["event_ns"] > t:
            continue
        term = chain[-1]
        active = None if term["kind"] == "cancel" else term
        out.append((qid, chain, active, first["stamp"]["event_ns"]))
    return out


def _epsilon(ctx, policy, ex, scope, ctl, res, a_ns, p):
    t = ex["event_ns"]
    roots = _matching_roots(ctx, ctl, ex, a_ns, t)
    actives = [r for r in roots if r[2] is not None]
    cancelled = [r for r in roots if r[2] is None]
    if not actives:
        res.side, res.reason = "unknown", "missing_quote"
        for qid, chain, _, _ in cancelled:
            res.records += [("variant_Quote", q) for q in chain]
        return res
    sel = max(actives, key=lambda r: (r[3], r[0]))
    for qid, chain, _, ev in cancelled:
        if (ev, qid) > (sel[3], sel[0]):
            res.records += [("variant_Quote", q) for q in chain]
    res.records += [("variant_Quote", q) for q in sel[1]]
    q = sel[2]
    res.quote_revision_id = q["revision_id"]
    age = t - sel[3]
    if age > policy["sign"]["max_quote_age_ns"]:
        res.side, res.reason = "unknown", "stale_quote"
        return res
    bid, ask = q["bid"], q["ask"]
    if q["condition"] != "regular" or bid is None or ask is None or bid["kind"] != "b64" or ask["kind"] != "b64" or p is None:
        res.side, res.reason = "unknown", "invalid_quote"
        return res
    b, h = b2f(bid["bits"]), b2f(ask["bits"])
    if not (p > 0 and b > 0 and h >= b):
        res.side, res.reason = "unknown", "invalid_quote"
        return res
    res.side, res.reason = epsilon_side(p, b, h, b2f(policy["sign"]["epsilon"]))
    return res


def _paired(ctx, policy, ex, scope, ctl, res, a_ns, trade):
    """Exact original pairing; no nearest/earlier fallback. `trade` = (ticks, scale) of the K-selected price."""
    t = ex["event_ns"]
    ptr = ex["paired_quote_revision_id"]
    res.side, res.reason = "unknown", "missing_pairing"
    if ptr is None:
        return res
    pair = None
    for cand in ctx.snap["pairings"]:
        if (cand["root_id"] == ex["root_id"] and cand["original_revision_id"] == ex["revision_id"] and
                cand["quote_revision_id"] == ptr):
            pair = cand
            break
    if pair is not None and ctx.vis_A(pair["stamp"], a_ns):
        res.records.append(("variant_Pairing", pair))
        res.pairing_id = pair["pairing_id"]
    else:
        pair = None
    q = ctx.quotes.get(ptr)
    if q is None or not ctx.vis_A(q["stamp"], a_ns):
        return res
    chain = _chain_a(ctx, ctx.qroots.get(q["quote_id"], []), a_ns)
    first = chain[0] if chain else q
    ev = first["stamp"]["event_ns"]
    if (pair is None or q["scope_id"] != ex["scope_id"] or q["contract_id"] != ex["contract_id"] or
            q["pairing_id"] != pair["pairing_id"] or ev > t or ev < scope["partition_start_ns"]):
        res.records += [("variant_Quote", c) for c in chain]
        res.quote_revision_id = q["revision_id"]
        return res
    res.records += [("variant_Quote", c) for c in chain]
    res.quote_revision_id = q["revision_id"]
    term = chain[-1]
    if term["revision_id"] != ptr or term["kind"] == "cancel":
        return res
    if t - ev > policy["sign"]["max_quote_age_ns"]:
        res.reason = "stale_quote"
        return res
    bid, ask = q["bid"], q["ask"]
    ticks, scale = trade
    if (q["condition"] != "regular" or bid is None or ask is None or bid["kind"] != "integer" or ask["kind"] != "integer" or
            bid["scale"] != scale or ask["scale"] != scale):
        res.reason = "invalid_quote"
        return res
    b, h = int(bid["ticks"]), int(ask["ticks"])
    if not (b > 0 and h > 0 and b < h):
        res.reason = "invalid_quote"
        return res
    if ticks <= b:
        res.side, res.reason = "sell", "classified"
    elif ticks >= h:
        res.side, res.reason = "buy", "classified"
    else:
        res.side, res.reason = "unknown", "inside_spread"
    return res


def context_hash(ctx, res, root_id, a_ns, policy_hash):
    seen, ordered = set(), []
    for rtype, rec in res.records:
        st = rec["stamp"]
        rid = _rid(rtype, rec)
        if (rtype, rid) in seen:
            continue
        seen.add((rtype, rid))
        ordered.append((st["stream_id"], st["position"], rtype, rid, ctx.rd(rtype, rec)))
    ordered.sort()
    return context_digest(root_id, a_ns, policy_hash, [o[4] for o in ordered])


ID_FIELD = {"variant_Execution": "revision_id", "variant_Quote": "revision_id", "variant_Control": "control_id",
            "variant_Definition": "definition_id", "variant_Pairing": "pairing_id"}


def _rid(rtype, rec):
    return rec[ID_FIELD[rtype]]


def sign_witness(ctx, res, rev, a_ns, policy, policy_hash, profile):
    return {"context_sha256": context_hash(ctx, res, rev["root_id"], a_ns, policy_hash),
            "pairing_id": res.pairing_id, "profile": profile, "quote_revision_id": res.quote_revision_id,
            "reason": res.reason, "revision_id": rev["revision_id"], "root_id": rev["root_id"], "side": res.side,
            "signing_A_ns": a_ns}


def context_deps(ctx, res, deps):
    """Add context-use dependencies (records and their bindings) to `deps`."""
    for rtype, rec in res.records:
        rid = _rid(rtype, rec)
        deps.add(rtype, rid, ctx.rd(rtype, rec), "context", rec["stamp"]["known_at_ns"])
        b = ctx.bindings[rec["stamp"]["binding_id"]]
        deps.add("variant_Binding", b["binding_id"], ctx.rd("variant_Binding", b), "context", 0)
