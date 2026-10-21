"""Reproduce independent selection-clock fixtures without production.

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

PINS = {
    "independent_full_rows.py": "1d137666e0fd867cf27e1008ff27f288f905ca4ffce14f56a83d76d489f0f699",
    "independent_reference_cases.py": "ea253804415d1f597071a996c9412ff1fa88b07fc67af54fd21bc589e82c26b2",
    "independent_reference.py": "d4bdce4898fb76eff30be89e201e2fb5b53762462470cdbfaa01729182295ec1",
}
OUTPUTS = ["flow.premium", "flow.signed_execution_premium", "flow.trade_count", "flow.unknown_premium"]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def identities(directory):
    return [{"file": name, "normalization": "UTF-8 LF; retain all other bytes",
             "sha256": hashlib.sha256((directory / name).read_text(encoding="utf-8").encode()).hexdigest()}
            for name in PINS]


def basis(reference):
    return (reference["underlying_id"], reference["currency"], reference["action_basis_id"],
            reference["right"], Fraction(reference["strike"]),
            Fraction(reference["multiplier"]), reference["expiry_ordinal"])


def selected_certificate(snapshot, root, kind, A):
    choices = [c for c in snapshot["context_certificates"] if c["kind"] == kind
        and c["contract_id"] == root["contract_id"] and c["session_id"] == root["session_id"]
        and c["stream_id"] == root["stream_id"] and c["through_position"] >= root["position"]
        and c["known_at_ns"] <= A]
    return min(choices, key=lambda c: (c["through_position"], c["certificate_id"])) if choices else None


def clock_signer(namespace):
    original_signer = namespace.sign_one

    def sign_one(snapshot, request, root, current, roots, refs, cursors, policy_sha256):
        method = request["policy"]["signing_profile"]
        A = root["signing_boundary_ns"]
        if method != "option-tick1":
            witness, certificate, admitted = original_signer(
                snapshot, request, root, current, roots, refs, cursors, policy_sha256)
            if method != "option-quote-midpoint1":
                return witness, certificate, admitted
            view = namespace.visible_view(snapshot["quotes"], "quote_id", A, cursors)
            complete = bool(certificate and certificate["complete"] and
                all(identity in view for identity in certificate["expected_root_ids"]))
            if complete:
                quote_roots = namespace.root_map(snapshot["quotes"], "quote_id")
                winner_position = (quote_roots[witness["quote_id"]]["position"]
                                   if witness["quote_id"] is not None else -1)
                for identity, revision in view.items():
                    original = quote_roots[identity]
                    # Only a removal above the surviving latest winner changes
                    # its selection proof. Older shadowed removals are ignored.
                    if (revision["kind"] == "cancel" and original["contract_id"] == root["contract_id"]
                            and original["stream_id"] == root["stream_id"]
                            and winner_position < original["position"] < root["position"]
                            and original["event_ns"] <= root["event_ns"]):
                        admitted.append(revision)
            # No cancellation is inserted into F43 minimal context operands.
            return witness, certificate, admitted

        reference = refs[root["reference_id"]]
        certificate = selected_certificate(snapshot, root, "execution_prefix", A)
        view = namespace.visible_view(snapshot["executions"], "execution_id", A, cursors)
        complete = bool(certificate and certificate["complete"] and
            all(identity in view for identity in certificate["expected_root_ids"]))
        witness = dict(execution_id=root["execution_id"], revision_id=current["revision_id"],
            sign="unknown", method=method, reason="tick_seed_unavailable", diagnostics=[],
            signing_boundary_ns=A, context_sha256="", context_certificate_id=certificate["certificate_id"] if certificate else None,
            quote_id=None, quote_revision_id=None, predecessor_execution_id=None, predecessor_revision_id=None)
        entries = [(root["position"], "flow_reference", reference)]
        admitted = [reference] + ([certificate] if certificate else [])
        predecessors = []
        if not complete:
            witness["diagnostics"] = ["incomplete_context", "tick_seed_unavailable"]
        else:
            for identity, revision in view.items():
                original = roots[identity]
                if (original["contract_id"] != root["contract_id"] or original["session_id"] != root["session_id"]
                        or original["stream_id"] != root["stream_id"] or original["position"] >= root["position"]
                        or basis(refs[original["reference_id"]]) != basis(reference)):
                    continue
                if revision["kind"] == "cancel" or revision["condition"] != "regular":
                    # The selected matching-prefix removal establishes why the
                    # previous-price/carry sweep omits this certified root.
                    admitted.append(revision)
                else:
                    predecessors.append((original, revision))
            predecessors.sort(key=lambda pair: pair[0]["position"])
            last_price = None
            carry = "unknown"
            for original, revision in predecessors:
                price = Fraction(revision["price"])
                if last_price is not None and price != last_price:
                    carry = "buy" if price > last_price else "sell"
                last_price = price
                entries.extend([(original["position"], "flow_execution", revision),
                    (original["position"], "flow_reference", refs[original["reference_id"]])])
                admitted.extend([revision, refs[original["reference_id"]]])
            target_price = Fraction(current["price"])
            if last_price is None:
                witness["reason"] = "tick_initial_unknown"
            elif target_price != last_price:
                witness["sign"] = "buy" if target_price > last_price else "sell"
                witness["reason"] = "tick_up" if target_price > last_price else "tick_down"
            elif carry != "unknown":
                witness.update(sign=carry, reason="tick_carried")
            else:
                witness["reason"] = "tick_initial_unknown"
            if predecessors:
                last = predecessors[-1][1]
                witness.update(predecessor_execution_id=last["execution_id"], predecessor_revision_id=last["revision_id"])
        ordered = namespace.record_context(entries)
        witness["context_sha256"] = namespace.sha_domain("option-flow-context1", [A, policy_sha256,
            [namespace.rd(kind, record) for position, kind, record in ordered],
            namespace.rd("flow_context_certificate", certificate) if certificate else None])
        return witness, certificate, admitted

    return sign_one


def quote_cases(namespace):
    p = namespace.prior
    cases = []
    for name, removal, known, cutoff, hidden in (
        ("quote-without-removal", None, None, 30, False),
        ("quote-latest-removal", "q2", 20, 30, False),
        ("quote-shadowed-older-removal", "q1", 20, 30, False),
        ("quote-no-survivor", "q2-only", 20, 30, False),
        ("quote-post-origin-removal", "q2", 31, 40, False),
        ("quote-cursor-hidden-removal", "q2", 20, 30, True),
    ):
        q1 = p.quote("q1", position=1, event=5, bid="1", ask="3")
        q2 = p.quote("q2", position=2, event=10, bid="3", ask="5")
        quotes = [q2] if removal == "q2-only" else [q1, q2]
        if removal:
            selected = q1 if removal == "q1" else q2
            cancelled = dict(selected, revision_id="v2", kind="cancel",
                target_quote_id=selected["quote_id"], target_revision_id="v1",
                position=4, known_at_ns=known, bid=None, ask=None, condition="excluded")
            quotes.append(cancelled)
        target = p.root("target", event=15, position=3, price="3", boundary=30)
        snapshot, request = p.make([target], outputs=OUTPUTS, quotes=quotes,
            profile="option-quote-midpoint1", start=15, end=16, cutoff=cutoff)
        for certificate in snapshot["context_certificates"]:
            certificate["known_at_ns"] = 0
        if hidden:
            request["cut_cursors"][0]["max_position"] = 3
        if name == "quote-latest-removal":
            sign, signed, unknown, clock, selected_id, reason = "buy", "300/1", "0/1", 20, "q1", "quote_above_midpoint"
        elif name == "quote-no-survivor":
            sign, signed, unknown, clock, selected_id, reason = "unknown", "0/1", "300/1", 20, None, "quote_missing"
        else:
            sign, signed, unknown, clock, selected_id, reason = "sell", "-300/1", "0/1", 15, "q2", "quote_below_midpoint"
        cases.append(dict(id=name, snapshot=snapshot, request=request,
            expected_available_at_ns=clock, expected_selected_quote_id=selected_id,
            expected_projection=dict(available={"flow.premium": "300/1", "flow.signed_execution_premium": signed,
                "flow.trade_count": "1/1", "flow.unknown_premium": unknown},
                signs={"target": sign}, sign_reasons={"target": reason}),
            hand_derivation="Target price3*quantity1*multiplier100=300; q1 midpoint2 versus q2 midpoint4. The latest cancelled eligible root changes selection only when admitted by A30/cursor and newer than the surviving winner."))
    return cases


def tick_cases(namespace):
    p = namespace.prior
    cases = []
    for mode in ("none", "cancel", "excluded", "other-definition", "other-session", "other-contract"):
        h1 = p.root("h1", event=5, position=1, price="100")
        h2 = p.root("h2", event=10, position=2, price="99")
        target = p.root("target", event=15, position=3, price="100", boundary=30)
        refs = [p.definition()]
        if mode == "other-definition":
            extra = dict(refs[0], reference_id="ref-other", strike="110")
            refs.append(extra)
            h2["reference_id"] = extra["reference_id"]
        elif mode == "other-session":
            h2["session_id"] = "S9"
        elif mode == "other-contract":
            h2 = p.root("h2", contract="B", event=10, position=1, price="99")
            refs.append(p.definition("B"))
            target["position"] = 2
        facts = [h1, h2, target]
        if mode != "none":
            revision = p.revision(h2, position=2 if mode == "other-contract" else 4,
                known=20, cancel=mode != "excluded")
            if mode == "excluded":
                revision["condition"] = "excluded"
            facts.append(revision)
        snapshot, request = p.make(facts, refs, OUTPUTS,
            profile="option-tick1", start=15, end=16, cutoff=30)
        for certificate in snapshot["context_certificates"]:
            certificate["known_at_ns"] = 0
        changed = mode in ("cancel", "excluded")
        sign = "buy" if mode == "none" else "unknown"
        cases.append(dict(id="tick-" + mode, snapshot=snapshot, request=request,
            expected_available_at_ns=20 if changed else 15,
            expected_predecessor_execution_id="h2" if mode == "none" else "h1",
            expected_projection=dict(available={"flow.premium": "10000/1", "flow.trade_count": "1/1",
                "flow.signed_execution_premium": "10000/1" if mode == "none" else "0/1",
                "flow.unknown_premium": "0/1" if mode == "none" else "10000/1"},
                signs={"target": sign}, sign_reasons={"target": "tick_up" if mode == "none" else "tick_initial_unknown"}),
            hand_derivation="Premium100*1*100=10000. Matching prefix100→99 then target100 gives buy; removing the99 seed leaves100→100 with no nonzero carry, unknown. Selected removal clock20 matters only inside the target definition/session/stream partition."))
    return cases


def construct(namespace):
    namespace.sign_one = clock_signer(namespace)
    result = quote_cases(namespace) + tick_cases(namespace)
    for item in result:
        snapshot, request = item["snapshot"], item["request"]
        rows = namespace.complete_rows(snapshot, request)
        namespace.assert_hand(rows, item["expected_projection"])
        if any(row["available_at_ns"] != item["expected_available_at_ns"] for row in rows):
            raise AssertionError("Independent availability contradicts literal witness: " + item["id"])
        witness = rows[0]["sign_witnesses"][0]
        for expected, field in (("expected_selected_quote_id", "quote_id"),
                                ("expected_predecessor_execution_id", "predecessor_execution_id")):
            if expected in item and witness[field] != item[expected]:
                raise AssertionError("Independent selected context identity mismatch: " + item["id"])
        wire = namespace.wire
        item.update(snapshot_wire=wire.envelope("flow_snapshot", snapshot), request_wire=wire.envelope("flow_request", request),
            snapshot_record_sha256=wire.record_digest("flow_snapshot", snapshot),
            request_record_sha256=wire.record_digest("flow_request", request),
            expected_results=rows, expected_results_record_sha256=wire.record_digest("flow_results", rows),
            expected_results_wire=wire.envelope("flow_results", rows))
    return dict(schema="r26-independent-selection-clock-fixtures1", cases=result,
        base_full_artifact_sha256="e0ab2065eaa62f3ac1b5442b0045f0e58a1c3c5a6ee45d20464f201a34316b51",
        independence="Original synthetic inputs, literal economic clocks/values, private independent namespace; no production source, tests, output or imports.",
        context_rule="Selection cause clocks do not insert cancellation/excluded records into F43 minimal context digest operands.",
        limitations=["Twelve bounded selected-cause controls, not every history/alignment variant.",
            "Source review, emitted-artifact independent review and actual installed conformance remain required.",
            "No performance, equity producer, browser, publication or full-release acceptance."])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.destination.exists():
        raise SystemExit("Preserve existing supplemental evidence")
    directory = Path(__file__).resolve().parents[1]
    before = identities(directory)
    if any(item["sha256"] != PINS[item["file"]] for item in before):
        raise AssertionError("Independent reference source changed")
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location("_r26_selection_clock_reference", directory / "independent_full_rows.py")
    namespace = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(namespace)
    normative = namespace.verify_reference_sources()
    payload = construct(namespace)
    if identities(directory) != before or namespace.verify_reference_sources() != normative:
        raise AssertionError("Independent/normative source changed during generation")
    payload["reference_source_identities"] = before
    payload["normative_source_identities"] = normative
    data = canonical(payload) + b"\n"
    if len(data) > 16777216:
        raise AssertionError("Supplement exceeds fixed16MiB cap")
    with args.destination.open("xb") as target:
        target.write(data)
    print(json.dumps(dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
        cases=len(payload["cases"]), expected_rows=sum(len(item["expected_results"]) for item in payload["cases"]))))


if __name__ == "__main__":
    main()
