"""evaluate_variants: Snapshot + Request -> Results (pure, stages 3-9)."""
from option_feature_contracts.variants1.canonical import (
    fail, record_digest, work_digest, cohort_digest, FORMULA, SCHEMA_RESULT, SCHEMA_GENERATION,
)
from option_feature_contracts.variants1.schema import validate_shape, validate_scalars
from . import admission, premium as P
from .context import Ctx, Deps, make_evidence
from .numeric import NumericOverflow
from .results import row as mkrow, receipt, aggregate, merge_evidence, sort_rows


def validate_inputs(snapshot, request):
    validate_shape(snapshot, "Snapshot", "/snapshot")
    validate_shape(request, "Request", "/request")
    validate_scalars(snapshot, "Snapshot", "/snapshot")
    validate_scalars(request, "Request", "/request")


def evaluate_variants(snapshot, request, *, cohort_sha256, input_checkpoint_sha256=None, producer_admission=None):
    validate_inputs(snapshot, request)
    ctx = Ctx(snapshot, request, cohort_sha256, producer_admission, input_checkpoint_sha256)
    admission.stage5(ctx)
    admission.stage6(ctx)
    admission.stage7(ctx)
    snapshot_hash = record_digest("variant_Snapshot", snapshot)
    request_hash = record_digest("variant_Request", request)
    ctx.snapshot_hash, ctx.request_hash = snapshot_hash, request_hash
    receipts, rows = {}, []
    done = {}
    order = [(i, o) for i, o in enumerate(request["operations"]) if o["kind"] != "baseline_consumer"] + \
            [(i, o) for i, o in enumerate(request["operations"]) if o["kind"] == "baseline_consumer"]
    for oi, op in order:
        try:
            rc, rws = run_op(ctx, oi, op, done)
        except NumericOverflow:
            fail("numeric_overflow", "/request/operations/%d" % oi, 8)
        done[op["op_id"]] = (rc, rws)
        receipts[op["op_id"]] = rc
        rows += rws
    ops_sorted = [receipts[k] for k in sorted(receipts)]
    return {"operations": ops_sorted, "rows": sort_rows(rows), "schema_version": SCHEMA_RESULT}


def run_op(ctx, oi, op, done):
    kind = op["kind"]
    if kind == "premium":
        return run_premium(ctx, oi, op)
    raise NotImplementedError(kind)


def run_premium(ctx, oi, op):
    rows, evs = [], []
    ids, revs, controls = [], [], []
    pairs = []
    recipe = op["recipe"]
    for rid in op["root_ids"]:
        rev = ctx.k_selected(rid)
        if recipe == "qualified-supplied1":
            res = P.supplied_premium(ctx, op, rev)
        else:
            res = P.native_premium(ctx, op, recipe, rev)
        ev = make_evidence(res["deps"], [rid], [rev["revision_id"]], control_ids=res["controls"])
        rows.append(mkrow(ctx, op, res["object_id"], "premium", res["object"], ev, res["diag"],
                          ctx.snapshot_hash, ctx.request_hash))
        evs.append(ev)
        ids.append(rid)
        revs.append(rev["revision_id"])
        pairs.append((res["status"], res["reason"]))
    status, reason = aggregate(pairs)
    rev_ev = merge_evidence(evs, ids, revs)
    return receipt(op, len(rows), status, reason, rev_ev), rows


def build_publication(snapshot, request, results, *, run_key, cohort, cohort_sha256, producer_admission=None,
                      input_checkpoint_sha256=None, output_checkpoint=None):
    """Canonical Publication record for one invocation (bindings = binding dependencies of the results)."""
    if cohort_digest(cohort) != cohort_sha256:
        fail("digest_mismatch", "/results", 9)
    snap_h = record_digest("variant_Snapshot", snapshot)
    req_h = record_digest("variant_Request", request)
    ids = set()
    for rc in results["operations"]:
        for d in rc["evidence"]["dependencies"]:
            if d["record_type"] == "variant_Binding":
                ids.add(d["record_id"])
    for rw in results["rows"]:
        for d in rw["evidence"]["dependencies"]:
            if d["record_type"] == "variant_Binding":
                ids.add(d["record_id"])
    bindings = sorted((b for b in snapshot["bindings"] if b["binding_id"] in ids), key=lambda b: b["binding_id"])
    return {
        "bindings": bindings,
        "cohort": cohort,
        "cohort_sha256": cohort_sha256,
        "input_checkpoint_sha256": input_checkpoint_sha256,
        "output_checkpoint": output_checkpoint,
        "producer_admission": producer_admission,
        "request": request,
        "request_sha256": req_h,
        "results": results,
        "run_key": run_key,
        "schema_version": SCHEMA_GENERATION,
        "snapshot_sha256": snap_h,
        "work_sha256": work_digest(snap_h, req_h, cohort_sha256, input_checkpoint_sha256),
    }
