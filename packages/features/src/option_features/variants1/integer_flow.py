"""i64-paired-call-put1: checked signed64 rollup with conservative bucket prechecks."""
import json
from option_feature_contracts.variants1.canonical import i64num
from . import numeric as N
from . import premium as P
from . import signing as S
from .context import Deps, make_evidence
from .flow import capture, order_members, capture_deps, exclusion_deps, definition_records
from .results import metric, unavailable_metric, row as mkrow, receipt, aggregate

I64_IDS = [("contracts", "contracts"), ("trade_count", "executions"), ("premium", "currency_ticks"),
           ("ask", "currency_ticks"), ("bid", "currency_ticks"), ("unknown", "currency_ticks"),
           ("unavailable_premium_count", "executions"), ("signed_call", "currency_ticks"),
           ("signed_put", "currency_ticks"), ("tide", "currency_ticks")]
MONETARY = {"premium", "ask", "bid", "unknown", "signed_call", "signed_put", "tide"}


def directional_i64(ctx, oi, op):
    policy = ctx.policies[op["policy_id"]]
    scope = ctx.scopes[op["scope_id"]]
    basis = scope["monetary_basis"]
    cap = capture(ctx, op, oi, interval=op["rollup_interval"])
    raw = order_members(cap.raw, "event-id1", ctx)
    pol_hash = ctx.policy_hash(op["policy_id"])
    results, signed = [], []
    for rev in raw:
        res = P.native_premium(ctx, op, op["recipe"], rev)
        results.append(res)
        price = rev["price"]
        sr = S.sign_root(ctx, op, policy, res["new_rev"], scope, definition_records(ctx, rev), None,
                         (int(price["ticks"]), price["scale"]))
        signed.append((res, sr, S.sign_witness(ctx, sr, rev, res["new_rev"]["signing_A_ns"], policy, pol_hash, "paired")))
    deps = Deps()
    capture_deps(ctx, cap, deps)
    exclusion_deps(ctx, cap, deps)
    controls = [c["control_id"] for c in cap.controls]
    for res in results:
        deps.update(res["deps"])
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
    metrics, weights = i64_metrics(signed, cap, basis)
    member_ids = [r["rev"]["root_id"] for r in results]
    member_revs = [r["rev"]["revision_id"] for r in results]
    ev = make_evidence(deps, member_ids, member_revs, unknown_sign, [], list(cap.excluded), controls,
                       capture_complete=cap.complete, context_complete=context_complete, eligibility=None)
    value = {"integer_weights": weights, "member_interval": cap.domain, "metrics": metrics, "order": "event-id1",
             "premiums": [r["object"] for r in results], "profile": op["profile"],
             "signs": [w for _, _, w in signed]}
    st, rs = aggregate([(m["status"], m["reason"]) for m in metrics])
    row = mkrow(ctx, op, None, "directional", value, ev, [], ctx.snapshot_hash, ctx.request_hash)
    return receipt(op, 1, st, rs, ev), [row]


def _jkey(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def i64_metrics(signed, cap, basis):
    if not cap.complete:
        return [unavailable_metric(m, u, "incomplete_capture", basis=basis if u == "currency_ticks" else None)
                for m, u in I64_IDS], []
    qty = 0
    unavailable = 0
    ask = bid = unk = total = sc = sp = 0
    contract_tot, strike_tot, expiry_tot = {}, {}, {}
    keys = {}
    for res, sr, wit in signed:
        qty = N.cadd(qty, int(res["rev"]["quantity"]))
        d = res["definition"]
        ck = res["rev"]["contract_id"]
        sk = _jkey(d["integer_strike"]) if d is not None and d["integer_strike"] is not None else None
        ek = d["expiry_day"] if d is not None else None
        keys[("contract", ck)] = None
        if sk is not None:
            keys[("strike", sk)] = d["integer_strike"]
        if ek is not None:
            keys[("expiry", ek)] = None
        prem = res["premium"]
        if prem["status"] != "available":
            unavailable += 1
            continue
        pt = int(prem["value"]["integer"])
        for cur in (ask, bid, unk):
            N.cadd(cur, pt)
        N.cadd(contract_tot.get(ck, 0), pt)
        if sk is not None:
            N.cadd(strike_tot.get(sk, 0), pt)
        if ek is not None:
            N.cadd(expiry_tot.get(ek, 0), pt)
        side = sr.side
        if side == "buy":
            ask = N.cadd(ask, pt)
        elif side == "sell":
            bid = N.cadd(bid, pt)
        else:
            unk = N.cadd(unk, pt)
        total = N.cadd(total, pt)
        contract_tot[ck] = N.cadd(contract_tot.get(ck, 0), pt)
        if sk is not None:
            strike_tot[sk] = N.cadd(strike_tot.get(sk, 0), pt)
        if ek is not None:
            expiry_tot[ek] = N.cadd(expiry_tot.get(ek, 0), pt)
        sgn = 1 if side == "buy" else (-1 if side == "sell" else 0)
        if res["right"] == "call":
            sc = N.cadd(sc, N.cmul(pt, sgn))
        else:
            sp = N.cadd(sp, N.cmul(pt, sgn))
    tide = N.csub(sc, sp)
    branch = "complete_empty" if not signed else "ordinary"
    vals = {"contracts": qty, "trade_count": len(signed), "premium": total, "ask": ask, "bid": bid, "unknown": unk,
            "unavailable_premium_count": unavailable, "signed_call": sc, "signed_put": sp, "tide": tide}
    out = []
    for mid, unit in I64_IDS:
        b = basis if unit == "currency_ticks" else None
        if mid in MONETARY and unavailable:
            out.append(unavailable_metric(mid, unit, "premium_unavailable", basis=b))
        else:
            out.append(metric(mid, unit, i64num(vals[mid]), branch=branch, basis=b))
    weights = []
    for (kind, key), strike in sorted(keys.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        if unavailable:
            m = unavailable_metric("premium", "currency_ticks", "premium_unavailable", basis=basis)
        else:
            tot = {"contract": contract_tot, "strike": strike_tot, "expiry": expiry_tot}[kind].get(key, 0)
            m = metric("premium", "currency_ticks", i64num(tot), basis=basis)
        weights.append({"contract_id": key if kind == "contract" else None,
                        "expiry_day": key if kind == "expiry" else None, "kind": kind, "premium": m,
                        "strike": strike if kind == "strike" else None})
    return out, weights
