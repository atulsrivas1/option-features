"""Pure bucket derivation (DTE, moneyness), BucketWitness, ActivityKey and bucket dependencies."""
from option_feature_contracts.variants1.canonical import b2f, f2b, record_digest
from . import numeric as N


def civil_fact(ref):
    return {"calendar_id": ref["calendar_id"], "calendar_revision": ref["calendar_revision"],
            "civil_day": ref["civil_day"], "civil_instant_ns": ref["civil_instant_ns"],
            "contract_id": ref["contract_id"], "reference_id": ref["reference_id"], "stamp": ref["civil_stamp"]}


def spot_fact(ref):
    return {"contract_id": ref["contract_id"], "reference_id": ref["reference_id"], "spot": ref["spot"],
            "stamp": ref["spot_stamp"]}


def dte_bucket(bp, d):
    if d == 0:
        return 0, False, {"axis": "dte", "band_id": bp["dte_zero_id"], "tag": "none"}
    cuts = bp["dte_positive_upper_cutpoints"]
    for j, u in enumerate(cuts, 1):
        if d <= u:
            return j, d == u, {"axis": "dte", "band_id": bp["dte_band_ids"][j - 1], "tag": "none"}
    return len(cuts) + 1, False, {"axis": "dte", "band_id": bp["dte_overflow_id"], "tag": "none"}


def moneyness_bucket(bp, right, v):
    dist = abs(N.sub(v, 1.0))
    cuts = [b2f(x) for x in bp["moneyness_distance_upper_cutpoints"]]
    for j, b in enumerate(cuts, 1):
        if dist <= b:
            band = bp["moneyness_band_ids"][j - 1]
            return j, dist == b, dist, {"axis": "moneyness", "band_id": band, "tag": _tag(j, right, v)}
    return len(cuts) + 1, False, dist, {"axis": "moneyness", "band_id": bp["moneyness_overflow_id"],
                                       "tag": _tag(len(cuts) + 1, right, v)}


def _tag(j, right, v):
    if j == 1:
        return "none"
    if right == "call":
        return "OTM" if v > 1.0 else "ITM"
    return "OTM" if v < 1.0 else "ITM"


class Bucket:
    """Outcome of bucket derivation for one owner (target or daily observation)."""

    def __init__(self):
        self.ok = False
        self.reason = "ok"            # ok | missing_reference | future_reference
        self.witness = None
        self.dte_key = None
        self.mon_key = None
        self.domain = None
        self.deps = []                # (rtype, rid, rhash, use, known)
        self.controls = []
        self.known = 0


def raw_of(ctx, binput):
    if binput["kind"] == "raw":
        return binput
    return ctx.bcerts[binput["certificate_id"]]["core"]["raw"]


def derive(ctx, owner_id, a_ns, right, bp, binput):
    out = Bucket()
    if binput["kind"] == "unavailable":
        out.reason = binput["reason"]
        c = ctx.controls[binput["control_id"]]
        out.deps.append(("variant_Control", c["control_id"], ctx.rd("variant_Control", c), "context",
                         c["stamp"]["known_at_ns"]))
        out.controls.append(c["control_id"])
        out.known = c["stamp"]["known_at_ns"]
        return out
    raw = raw_of(ctx, binput)
    d = ctx.defs[raw["definition_id"]]
    ref = ctx.refs[raw["reference_id"]]
    out.deps.append(("variant_Definition", d["definition_id"], ctx.rd("variant_Definition", d), "context",
                     d["stamp"]["known_at_ns"]))
    for rtype, fact in (("variant_CivilFact", civil_fact(ref)), ("variant_SpotFact", spot_fact(ref))):
        h = record_digest(rtype, fact)
        out.deps.append((rtype, h, h, "context", fact["stamp"]["known_at_ns"]))
    out.known = max(x[4] for x in out.deps)
    if binput["kind"] == "qualified":
        cert = ctx.bcerts[binput["certificate_id"]]
        out.deps.append(("variant_BucketCertificate", cert["certificate_id"], ctx.rd("variant_BucketCertificate", cert),
                         "context", cert["stamp"]["known_at_ns"]))
        out.known = max(out.known, cert["stamp"]["known_at_ns"])
        dte = binput["dte_days"]
        z = b2f(binput["moneyness"])
    else:
        dte = raw["expiry_day"] - raw["event_day"]
        z = None
    if dte < 0:
        out.reason = "missing_reference"
        out.domain = _domain(owner_id, raw, a_ns, dte, None, "negative_dte")
        return out
    if z is None:
        z = N.div(b2f(raw["strike"]), b2f(raw["spot"]))
    if z == 0.0:
        out.reason = "missing_reference"
        out.domain = _domain(owner_id, raw, a_ns, dte, 0.0, "ratio_rounded_zero")
        return out
    di, deq, dkey = dte_bucket(bp, dte)
    mi, meq, dist, mkey = moneyness_bucket(bp, right, z)
    out.ok = True
    out.dte_key, out.mon_key = dkey, mkey
    out.witness = {"distance": f2b(dist), "dte_bucket": dkey, "dte_days": dte, "dte_equal_cutpoint": deq,
                   "dte_index": di, "input": binput, "moneyness": f2b(z), "moneyness_bucket": mkey,
                   "moneyness_equal_cutpoint": meq, "moneyness_index": mi, "observation_A_ns": a_ns,
                   "observation_id": owner_id}
    return out


def _domain(owner_id, raw, a_ns, dte, z, branch):
    return {"branch": branch, "dte_days": dte, "moneyness": None if z is None else f2b(z), "owner_id": owner_id,
            "raw": raw, "reference_A_ns": a_ns}


def activity_key(ctx, scope, contract_id, right, basis, bp, dkey, mkey):
    return {"action_basis_id": scope["action_basis_id"], "activity_basis": basis,
            "bucket_policy_sha256": ctx.rd("variant_BucketPolicy", bp), "contract_id": contract_id,
            "currency": scope["currency"], "definition_basis_id": scope["definition_basis_id"],
            "deliverable_basis_id": scope["deliverable_basis_id"], "dte_bucket": dkey, "horizon_id": "full-session1",
            "moneyness_bucket": mkey, "population_universe_id": scope["population_universe_id"], "right": right,
            "underlying_id": scope["underlying_id"]}
