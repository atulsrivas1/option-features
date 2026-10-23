"""PremiumOp: raw premium recipes, qualified supplied pass-through and producer proofs."""
from option_feature_contracts.variants1.canonical import b2f, f2b, b64num, i64num, I64_MAX, I64_MIN, record_digest
from . import numeric as N
from .context import Deps
from .results import metric, unavailable_metric

FAMILY = "option-flow-variants-premium1"
PROFILE_B64 = "binary64-rne-each-op-no-fma1"
PROFILE_CHECKED = "checked-i64-each-op1"
PROFILE_PASS = "binary64-preserve-bits1"
RECIPE_FORMULA = {"integer-price-b64-products1": "integer-price-b64-products1",
                  "b64-price-products1": "b64-price-products1",
                  "checked-integer-products1": "checked-integer-products1",
                  "qualified-supplied1": "qualified-supplied-pass-through1"}


def basis_of(scope):
    return scope["monetary_basis"]


def definition_of(ctx, rev):
    du = rev["definition_use"]
    if du["kind"] == "available":
        return ctx.defs[du["definition_id"]]
    return None


def core_scale(recipe, price):
    if recipe in ("checked-integer-products1", "integer-price-b64-products1") and price["kind"] == "integer":
        return price["scale"]
    return None


def compute_premium(ctx, recipe, scope, rev, definition):
    """Returns (premium Metric, multiplier or None)."""
    du = rev["definition_use"]
    price = rev["price"]
    checked = recipe == "checked-integer-products1"
    unit = "currency_ticks" if checked else "currency"
    basis = basis_of(scope) if checked else None
    if definition is None:
        return unavailable_metric("premium", unit, du["reason"], basis=basis), None
    mult = definition["multiplier"]
    q = int(rev["quantity"])
    if checked:
        n = int(price["ticks"])
        try:
            u = N.cmul(n, q)
            p = N.cmul(u, int(mult["units"]))
        except N.NumericOverflow:
            return unavailable_metric("premium", unit, "premium_overflow", basis=basis), mult
        return metric("premium", unit, i64num(p), basis=basis), mult
    # B64 recipes
    if recipe == "integer-price-b64-products1":
        nf = N.rn_int(int(price["ticks"]))
        sf = N.rn_int(int(price["scale"]))
        p = N.div(nf, sf)
    else:
        p = b2f(price["bits"])
    qf = N.rn_int(q)
    m = b2f(mult["bits"])
    t = N.mul(p, qf)
    out = N.mul(t, m)
    branch = "underflow_to_zero" if out == 0 else "ordinary"
    return metric("premium", unit, b64num(out), branch=branch), mult


def core_dict(rev, recipe, mult, scale, prem):
    return {"definition_use": rev["definition_use"], "multiplier": mult, "premium": prem, "quantity": rev["quantity"],
            "raw_price": rev["price"], "recipe": recipe, "revision_id": rev["revision_id"], "root_id": rev["root_id"],
            "scale": scale}


def source_deps(ctx, rev, new_rev, definition, use="economic"):
    """Dependencies and proof input hashes for the raw execution revision and its definition context."""
    deps = Deps()
    hashes = set()
    for r in {id(x): x for x in (new_rev, rev)}.values():
        h = ctx.rd("variant_Execution", r)
        hashes.add(h)
        deps.add("variant_Execution", r["revision_id"], h, "economic", r["stamp"]["known_at_ns"])
        _binding(ctx, deps, r["stamp"]["binding_id"], "economic")
    du = rev["definition_use"]
    controls = []
    if du["kind"] == "available":
        d = ctx.defs[du["definition_id"]]
        h = ctx.rd("variant_Definition", d)
        hashes.add(h)
        deps.add("variant_Definition", d["definition_id"], h, "economic", d["stamp"]["known_at_ns"])
        _binding(ctx, deps, d["stamp"]["binding_id"], "economic")
    else:
        c = ctx.controls[du["control_id"]]
        h = ctx.rd("variant_Control", c)
        hashes.add(h)
        controls.append(c["control_id"])
        deps.add("variant_Control", c["control_id"], h, "context", c["stamp"]["known_at_ns"])
        _binding(ctx, deps, c["stamp"]["binding_id"], "economic")
        vid = du["visible_definition_id"]
        if vid is not None:
            d = ctx.defs[vid]
            hd = ctx.rd("variant_Definition", d)
            hashes.add(hd)
            deps.add("variant_Definition", vid, hd, "economic", d["stamp"]["known_at_ns"])
            _binding(ctx, deps, d["stamp"]["binding_id"], "economic")
    return deps, hashes, controls


def _binding(ctx, deps, binding_id, use):
    b = ctx.bindings[binding_id]
    deps.add("variant_Binding", binding_id, ctx.rd("variant_Binding", b), use, 0)


def policy_scope_deps(ctx, deps, hashes, op):
    scope = ctx.scopes[op["scope_id"]]
    pol = ctx.policies[op["policy_id"]]
    hs, hp = ctx.rd("variant_Scope", scope), ctx.rd("variant_Policy", pol)
    deps.add("variant_Scope", scope["scope_id"], hs, "policy", 0)
    deps.add("variant_Policy", pol["policy_id"], hp, "policy", 0)
    hashes.add(hs)
    hashes.add(hp)
    return hp


def proof(ctx, recipe, policy_hash, input_hashes, core):
    return {
        "formula_id": RECIPE_FORMULA[recipe],
        "input_record_sha256s": sorted(set(input_hashes)),
        "numeric_profile": PROFILE_CHECKED if recipe == "checked-integer-products1" else
        (PROFILE_PASS if recipe == "qualified-supplied1" else PROFILE_B64),
        "output_record_sha256": record_digest("variant_PremiumCore", core),
        "policy_sha256": policy_hash,
        "producer_cohort_sha256": ctx.cohort,
        "producer_family": FAMILY,
    }


def native_premium(ctx, op, recipe, rev):
    """Native generated PremiumObject for the K-selected revision (premium kinds b64/checked).

    Returns dict(core, object, object_id, deps, hashes, controls, diag, status, reason, known)."""
    scope = ctx.scopes[op["scope_id"]]
    new_rev = ctx.new_rev(rev["root_id"])
    definition = definition_of(ctx, rev)
    prem, mult = compute_premium(ctx, recipe, scope, rev, definition)
    core = core_dict(rev, recipe, mult, core_scale(recipe, rev["price"]), prem)
    deps, hashes, controls = source_deps(ctx, rev, new_rev, definition)
    hp = policy_scope_deps(ctx, deps, hashes, op)
    pr = proof(ctx, recipe, hp, hashes, core)
    obj = dict(core)
    obj["producer"] = pr
    diags = []
    if prem["status"] != "available":
        diags.append((prem["reason"], rev["root_id"]))
    return {"core": core, "object": obj, "object_id": pr["output_record_sha256"], "deps": deps, "hashes": hashes,
            "controls": controls, "diag": diags, "status": prem["status"], "reason": prem["reason"],
            "rev": rev, "new_rev": new_rev, "premium": prem, "policy_hash": hp,
            "known": max(d["known_at_ns"] for d in deps.d.values() if d["record_type"] in
                         ("variant_Execution", "variant_Definition", "variant_Control"))}


def admitted(ctx, sp):
    adm = ctx.admission
    if adm is None or ctx.req["producer_admission_sha256"] is None:
        return False
    h = ctx.rd("variant_SuppliedPremium", sp)
    return any(q["record_type"] == "variant_SuppliedPremium" and q["record_sha256"] == h
               for q in adm["qualified_inputs"])


def supplied_premium(ctx, op, rev):
    """qualified-supplied1 pass-through (or unsupported wrapper) for one root."""
    scope = ctx.scopes[op["scope_id"]]
    new_rev = ctx.new_rev(rev["root_id"])
    definition = definition_of(ctx, rev)
    sp = None
    for cand in ctx.snap["supplied_premiums"]:
        if cand["root_id"] == rev["root_id"] and cand["revision_id"] == rev["revision_id"]:
            sp = cand
            break
    deps, hashes, controls = source_deps(ctx, rev, new_rev, definition)
    hp = policy_scope_deps(ctx, deps, hashes, op)
    diags = []
    native = None
    if sp is None:
        prem = unavailable_metric("premium", "currency", "source_witness_unqualified", status="unsupported")
        mult = definition["multiplier"] if definition else None
        scale = rev["price"]["scale"] if rev["price"]["kind"] == "integer" else None
    else:
        sh = ctx.rd("variant_SuppliedPremium", sp)
        hashes.add(sh)
        deps.add("variant_SuppliedPremium", sp["premium_id"], sh, "economic", sp["stamp"]["known_at_ns"])
        _binding(ctx, deps, sp["stamp"]["binding_id"], "economic")
        if sp["origin"] == "qualified_calculation" and sp["core"] is not None:
            native = sp["core"]
            nh = ctx.rd_core(native) if hasattr(ctx, "rd_core") else record_digest("variant_PremiumCore", native)
            hashes.add(nh)
            known = max(rev["stamp"]["known_at_ns"], new_rev["stamp"]["known_at_ns"],
                        max((d["known_at_ns"] for d in deps.d.values() if d["record_type"] in ("variant_Definition", "variant_Control")), default=0))
            deps.add("variant_PremiumCore", nh, nh, "economic", known)
        if native is not None and admitted(ctx, sp):
            prem = dict(native["premium"])
            mult = native["multiplier"]
            scale = native["scale"]
        else:
            prem = unavailable_metric("premium", "currency", "source_witness_unqualified", status="unsupported")
            mult = native["multiplier"] if native is not None else (definition["multiplier"] if definition else None)
            scale = native["scale"] if native is not None else (rev["price"]["scale"] if rev["price"]["kind"] == "integer" else None)
    core = core_dict(rev, "qualified-supplied1", mult, scale, prem)
    pr = proof(ctx, "qualified-supplied1", hp, hashes, core)
    obj = dict(core)
    obj["producer"] = pr
    if prem["status"] != "available":
        diags.append((prem["reason"], rev["root_id"]))
    return {"core": core, "object": obj, "object_id": pr["output_record_sha256"], "deps": deps, "hashes": hashes,
            "controls": controls, "diag": diags, "status": prem["status"], "reason": prem["reason"],
            "rev": rev, "new_rev": new_rev, "premium": prem, "policy_hash": hp}
