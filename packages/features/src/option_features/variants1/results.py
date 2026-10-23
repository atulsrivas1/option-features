"""Result rows, operation receipts and status/reason aggregation."""
from .context import Deps, make_evidence

UNAVAIL_PRIORITY = [
    "incomplete_capture", "incomplete_context", "missing_definition", "future_definition", "ineffective_definition",
    "nonstandard_definition", "unknown_definition", "premium_overflow", "premium_unavailable", "missing_reference",
    "future_reference", "missing_baseline", "incomplete_baseline", "empty_baseline", "insufficient_history",
]
UNSUPPORTED_PRIORITY = ["unsupported_profile", "source_witness_unqualified"]


def metric(metric_id, unit, value, status="available", reason="ok", branch="ordinary", basis=None):
    return {"branch": branch, "metric_id": metric_id, "monetary_basis": basis, "reason": reason, "status": status,
            "unit": unit, "value": value}


def unavailable_metric(metric_id, unit, reason, status="unavailable", basis=None):
    return metric(metric_id, unit, None, status, reason, "not_evaluated", basis)


def aggregate(pairs):
    """Receipt status/reason from (status, reason) pairs: unsupported > unavailable > undefined > available."""
    for st, pri in (("unsupported", UNSUPPORTED_PRIORITY), ("unavailable", UNAVAIL_PRIORITY)):
        rs = [r for s, r in pairs if s == st]
        if rs:
            for p in pri:
                if p in rs:
                    return st, p
            return st, rs[0]
    if any(s == "undefined" for s, _ in pairs):
        return "undefined", "zero_denominator"
    return "available", "ok"


def diag(code, subject):
    return {"code": code, "subject_id": subject}


def sort_diag(ds):
    return sorted({(d[0], d[1]) if type(d) is tuple else (d["code"], d["subject_id"]) for d in ds})


def row(ctx, op, object_id, payload_kind, value, evidence, diagnostics, snapshot_hash, request_hash):
    return {
        "cohort_sha256": ctx.cohort,
        "diagnostics": [diag(c, s) for c, s in sort_diag(diagnostics)],
        "evidence": evidence,
        "formula_version": "option-flow-variants1",
        "input_checkpoint_sha256": ctx.input_checkpoint,
        "object_id": object_id,
        "op_id": op["op_id"],
        "payload": {"kind": payload_kind, "value": value},
        "policy_sha256": ctx.policy_hash(op["policy_id"]),
        "request_sha256": request_hash,
        "schema_version": "option-flow-variants-result1",
        "scope_id": op["scope_id"],
        "snapshot_sha256": snapshot_hash,
    }


def merge_evidence(rows_evidence, member_ids=None, member_revision_ids=None, extra_deps=None, **kw):
    """Receipt evidence as the union of row evidences (deduplicated dependencies)."""
    deps = Deps()
    controls, excl, usign, uref = [], [], [], []
    for e in rows_evidence:
        for d in e["dependencies"]:
            deps.add(d["record_type"], d["record_id"], d["record_sha256"], d["use"], d["known_at_ns"])
        controls += e["control_ids"]
        excl += e["excluded_ids"]
        usign += e["unknown_sign_ids"]
        uref += e["unknown_reference_ids"]
    if extra_deps:
        deps.update(extra_deps)
    return make_evidence(deps, member_ids or [], member_revision_ids or [], usign, uref, excl, controls, **kw)


def receipt(op, object_count, status, reason, evidence, anchor_readiness=()):
    return {"anchor_readiness": list(anchor_readiness), "evidence": evidence, "object_count": object_count,
            "op_id": op["op_id"], "reason": reason, "status": status}


def sort_rows(rows):
    return sorted(rows, key=lambda r: (r["op_id"], "" if r["object_id"] is None else r["object_id"], ))
