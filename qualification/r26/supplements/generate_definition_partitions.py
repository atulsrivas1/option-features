"""Reproduce the independent definition-partition fixture without production.

Uses only standard library and pinned independent reference helpers. Existing
artifacts and source files are preserved. The caller owns resource admission;
coordinate this CLI with other workloads before executing it.
"""
from pathlib import Path
from fractions import Fraction
import argparse
import hashlib
import importlib.util
import json
import sys

REFERENCE_LF_PINS = {
    "independent_full_rows.py": "1d137666e0fd867cf27e1008ff27f288f905ca4ffce14f56a83d76d489f0f699",
    "independent_reference_cases.py": "ea253804415d1f597071a996c9412ff1fa88b07fc67af54fd21bc589e82c26b2",
    "independent_reference.py": "d4bdce4898fb76eff30be89e201e2fb5b53762462470cdbfaa01729182295ec1",
}
BASE_ARTIFACT_SHA256 = "e0ab2065eaa62f3ac1b5442b0045f0e58a1c3c5a6ee45d20464f201a34316b51"
DEFINITION_FIELDS = ["underlying_id", "currency", "action_basis_id", "right",
                     "strike", "multiplier", "expiry_ordinal"]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def reference_identities(directory):
    return [{"file": name, "normalization": "UTF-8 LF; retain all other bytes",
             "sha256": hashlib.sha256((directory / name).read_text(encoding="utf-8").encode()).hexdigest()}
            for name in REFERENCE_LF_PINS]


def definition_key(reference):
    # Reference IDs and optional civil/spot inputs are not definition identity.
    # Semantic exact values, rather than decimal spelling, identify its scalars.
    return (reference["underlying_id"], reference["currency"], reference["action_basis_id"],
            reference["right"], Fraction(reference["strike"]),
            Fraction(reference["multiplier"]), reference["expiry_ordinal"])


def partitioner(snapshot, namespace):
    references = {r["reference_id"]: r for r in snapshot["references"]}

    def clusters(active, roots, witnesses, policy_sha256, policy):
        signs = {w["execution_id"]: w for w in witnesses}
        partitions = {}
        for execution in active:
            root = roots[execution["execution_id"]]
            basis = definition_key(references[root["reference_id"]])
            key = (root["contract_id"], root["session_id"], root["stream_id"],
                   basis, policy_sha256, signs[execution["execution_id"]]["method"])
            partitions.setdefault(key, []).append(execution)
        runs = []
        for members in partitions.values():
            ordered = sorted(members, key=lambda e: roots[e["execution_id"]]["position"])
            run = []
            previous = None
            for execution in ordered:
                root = roots[execution["execution_id"]]
                witness = signs[execution["execution_id"]]
                known = witness["sign"] != "unknown" and witness["quote_id"] is not None
                if not known:
                    if run:
                        runs.append(run)
                    run, previous = [], None
                    continue
                same_run = bool(previous and
                    witness["quote_id"] == previous[1]["quote_id"] and
                    witness["quote_revision_id"] == previous[1]["quote_revision_id"] and
                    witness["sign"] == previous[1]["sign"] and
                    root["event_ns"] - previous[0]["event_ns"] <= policy["cluster_max_adjacent_gap_ns"])
                if run and not same_run:
                    runs.append(run)
                    run = []
                run.append(execution)
                previous = root, witness
            if run:
                runs.append(run)
        result = []
        for members in runs:
            first = roots[members[0]["execution_id"]]
            last = roots[members[-1]["execution_id"]]
            witness = signs[members[0]["execution_id"]]
            ids = [e["execution_id"] for e in members]
            revisions = [e["revision_id"] for e in members]
            # FLOW_CONTRACT97 payload is unchanged. Definition is a partition
            # prerequisite, not a new cluster field or hash operand.
            identity = namespace.sha_domain("option-flow-cluster1", ["option-quote-cluster1",
                first["contract_id"], first["session_id"], policy_sha256,
                witness["quote_id"], witness["quote_revision_id"], witness["sign"], ids, revisions])
            record = dict(cluster_id=identity, profile="option-quote-cluster1",
                contract_id=first["contract_id"], session_id=first["session_id"],
                quote_id=witness["quote_id"], quote_revision_id=witness["quote_revision_id"],
                sign=witness["sign"], execution_ids=ids, execution_revision_ids=revisions,
                first_event_ns=first["event_ns"], last_event_ns=last["event_ns"],
                venue_ids=sorted({e["venue_id"] for e in members if e["venue_id"] is not None}),
                unknown_venue_count=sum(e["venue_id"] is None for e in members))
            result.append((record, members))
        return result

    return clusters


def original_cases(namespace):
    prior = namespace.prior
    cases = []
    # Eight hand witnesses. All known-price executions have price2, quantity1;
    # quote midpoint1 gives buy. Unknown executions have price1, hence midpoint.
    for field, value in (("strike", "110"), ("right", "put"),
                         ("multiplier", "2"), ("expiry_ordinal", 21)):
        premium_b = "4/1" if field == "multiplier" else "2/1"
        cases.append(dict(id="definition-split-" + field, variant={field: value},
            sequence=[("a", "A", "2"), ("b", "B", "2")],
            projection=dict(cluster_members=[["a"], ["b"]],
                cluster_values={"execution.cluster_premium": ["2/1", premium_b],
                    "execution.cluster_trade_count": ["1/1", "1/1"],
                    "execution.cluster_contracts": ["1/1", "1/1"],
                    "execution.cluster_span_ns": ["0/1", "0/1"],
                    "execution.cluster_venue_count": ["1/1", "1/1"]},
                available={"execution.cluster_coverage": "1/1"})))
    cases.append(dict(id="same-definition-different-reference-ids", variant={},
        sequence=[("a", "A", "2"), ("b", "B", "2")],
        projection=dict(cluster_members=[["a", "b"]], cluster_values={
            "execution.cluster_premium": ["4/1"], "execution.cluster_trade_count": ["2/1"],
            "execution.cluster_contracts": ["2/1"], "execution.cluster_span_ns": ["2/1"],
            "execution.cluster_venue_count": ["2/1"]}, available={"execution.cluster_coverage": "1/1"})))
    cases.append(dict(id="partition-first-A-B-A", variant={"strike": "110"},
        sequence=[("a", "A", "2"), ("b", "B", "2"), ("c", "A", "2")],
        projection=dict(cluster_members=[["a", "c"], ["b"]], cluster_values={
            "execution.cluster_premium": ["4/1", "2/1"], "execution.cluster_trade_count": ["2/1", "1/1"],
            "execution.cluster_contracts": ["2/1", "1/1"], "execution.cluster_span_ns": ["4/1", "0/1"],
            "execution.cluster_venue_count": ["1/1", "1/1"]}, available={"execution.cluster_coverage": "1/1"})))
    for other_definition in (False, True):
        members = [["a", "c"]] if other_definition else [["a"], ["c"]]
        values = ["4/1"] if other_definition else ["2/1", "2/1"]
        counts = ["2/1"] if other_definition else ["1/1", "1/1"]
        spans = ["4/1"] if other_definition else ["0/1", "0/1"]
        venues = ["1/1"] if other_definition else ["1/1", "1/1"]
        cases.append(dict(id="unknown-other-definition" if other_definition else "unknown-inside-definition",
            variant={"strike": "110"},
            sequence=[("a", "A", "2"), ("b", "B" if other_definition else "A", "1"), ("c", "A", "2")],
            projection=dict(cluster_members=members, cluster_values={
                "execution.cluster_premium": values, "execution.cluster_trade_count": counts,
                "execution.cluster_contracts": counts, "execution.cluster_span_ns": spans,
                "execution.cluster_venue_count": venues},
                available={"execution.cluster_coverage": "4/5"}, signs={"a": "buy", "b": "unknown", "c": "buy"})))
    result = []
    for item in cases:
        definitions = {label: prior.definition(multiplier="1") for label in ("A", "B")}
        for label, reference in definitions.items():
            reference["reference_id"] = "ref-" + label
        definitions["B"].update(item["variant"])
        executions = []
        for index, (identity, label, price) in enumerate(item["sequence"]):
            execution = prior.root(identity, position=index + 2, event=10 + index * 2, price=price)
            execution["reference_id"] = definitions[label]["reference_id"]
            execution["venue_id"] = "V2" if identity == "b" else "V1"
            executions.append(execution)
        snapshot, request = prior.make(executions, list(definitions.values()), prior.CLUSTER_OUTPUTS,
            quotes=[prior.quote(position=1, event=9, bid="0", ask="2")],
            profile="option-quote-midpoint1", start=10, end=16, cutoff=20)
        result.append(dict(id=item["id"], snapshot=snapshot, request=request,
            expected_projection=item["projection"],
            hand_basis=dict(definition_A={k: definitions["A"][k] for k in DEFINITION_FIELDS},
                definition_B={k: definitions["B"][k] for k in DEFINITION_FIELDS},
                event_sequence=[10 + index * 2 for index in range(len(executions))],
                adjacent_gap_limit_ns=5, midpoint="1", quantity_per_execution="1")))
    return result


def construct(namespace):
    result = []
    for item in original_cases(namespace):
        snapshot, request = item["snapshot"], item["request"]
        # Only this separately loaded, private namespace is changed. Never set
        # an attribute on an imported original independent reference module.
        namespace.cluster_partition = partitioner(snapshot, namespace)
        rows = namespace.complete_rows(snapshot, request)
        namespace.assert_hand(rows, item["expected_projection"])
        wire = namespace.wire
        item.update(snapshot_wire=wire.envelope("flow_snapshot", snapshot),
            request_wire=wire.envelope("flow_request", request),
            snapshot_record_sha256=wire.record_digest("flow_snapshot", snapshot),
            request_record_sha256=wire.record_digest("flow_request", request),
            expected_results=rows, expected_results_record_sha256=wire.record_digest("flow_results", rows),
            expected_results_wire=wire.envelope("flow_results", rows),
            expected_scope="Complete canonical independent row set plus original literal cluster witnesses.")
        result.append(item)
    return dict(schema="r26-independent-definition-partition-fixtures1",
        base_full_artifact_sha256=BASE_ARTIFACT_SHA256,
        semantic_definition_fields=DEFINITION_FIELDS, cases=result,
        independence="Original synthetic inputs and hand projections; original semantic partitioner in separately loaded reviewed independent row namespace; no production source/output/import.",
        preserved="Existing full artifact, reference modules, all44 normative scenarios and hash domains remain unchanged.",
        limitations=["Eight bounded supplemental definition-partition cases, not every cluster/feature/source variant.",
            "Source and emitted-artifact independent review plus actual installed conformance remain required.",
            "No performance, EQ190 integration, publication or full-release acceptance."])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        raise SystemExit("Existing supplemental artifact must be preserved")
    directory = Path(__file__).resolve().parents[1]
    before = reference_identities(directory)
    if any(item["sha256"] != REFERENCE_LF_PINS[item["file"]] for item in before):
        raise AssertionError("Reviewed independent reference source changed")
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location("_r26_definition_partition_reference", directory / "independent_full_rows.py")
    namespace = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(namespace)
    normative = namespace.verify_reference_sources()
    payload = construct(namespace)
    if reference_identities(directory) != before or namespace.verify_reference_sources() != normative:
        raise AssertionError("Independent/normative source changed during construction")
    payload["reference_source_identities"] = before
    payload["normative_source_identities"] = normative
    data = canonical(payload) + b"\n"
    if len(data) > 16777216:
        raise AssertionError("Supplemental fixture exceeds fixed16MiB transport cap")
    with args.destination.open("xb") as target:
        target.write(data)
    print(json.dumps(dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
        cases=len(payload["cases"]), expected_rows=sum(len(c["expected_results"]) for c in payload["cases"])) ))


if __name__ == "__main__":
    main()
