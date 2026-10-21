"""Independent synthetic fixture construction; never imports production code.

This first materialization tranche supplies closed literal requests/snapshots and
hand-authored economic expectations. It does not claim full-result goldens or
coverage of all forty frozen scenarios. Review before numerical-proof use.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

SOURCE_SCENARIOS_SHA256 = "d3f11434eacd45576c625ec50da83f19ab25c0d522e4770824074efc20cd48fc"
LIMITS = dict(max_wire_bytes=16777216, max_records=100000, max_groups=128,
              max_streams=128, max_baselines_per_group=32, max_outputs=64,
              max_result_rows=8192, max_replay_cuts=128, max_integer_digits=256)
F01_VALUES = {
    "flow.trade_count":"4/1", "flow.contracts":"7/1",
    "flow.share_equivalent":"650/1", "flow.premium":"1400/1",
    "flow.buy_proxy_premium":"1000/1", "flow.sell_proxy_premium":"300/1",
    "flow.unknown_premium":"100/1", "flow.signed_execution_premium":"700/1",
    "flow.known_sign_imbalance":"7/13", "flow.total_premium_imbalance":"1/2",
    "flow.unknown_premium_share":"1/14", "flow.sign_event_coverage":"3/4",
    "flow.sign_premium_coverage":"13/14", "flow.right_positive_premium":"600/1",
    "flow.right_negative_premium":"700/1", "flow.net_directional_premium":"-100/1",
    "flow.call_premium":"900/1", "flow.put_premium":"500/1",
    "flow.put_call_premium_ratio":"5/9", "flow.contract_hhi":"1/2",
    "flow.contract_top_share":"9/14", "flow.expiry_hhi":"85/98",
    "flow.expiry_top_share":"13/14",
}

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")

def record_digest(kind, value):
    return hashlib.sha256(("option-flow-record1\n"+kind+"\n").encode()+canonical(value)).hexdigest()

def envelope(kind, value):
    digest=hashlib.sha256(("option-flow-json1\n"+kind+"\n").encode()+canonical(value)).hexdigest()
    return canonical(dict(schema_version="option-flow-json1", record_type=kind,
                          content_sha256=digest, payload=value)).decode("utf-8")

def binding():
    return dict(binding_id="synthetic1", source_id="independent-r26",
                source_revision="literal1", source_content_sha256=hashlib.sha256(b"original synthetic R26 literals").hexdigest(),
                provenance_mode="synthetic", rights_reference="Original synthetic fixture; no market observations.")

def reference(contract, right, multiplier, expiry):
    return dict(reference_id="ref-"+contract, contract_id=contract,
                underlying_id="SYNTH-U", currency="XTS", action_basis_id="synthetic-unadjusted1",
                right=right, strike="100", multiplier=multiplier, expiry_ordinal=expiry,
                civil_ordinal=None, civil_instant_ns=None, civil_known_at_ns=None,
                calendar_id=None, calendar_revision=None, spot=None, spot_event_ns=None,
                spot_known_at_ns=None, spot_stream_id=None, spot_position=None,
                effective_from_ns=0, effective_to_ns=None, known_at_ns=0,
                revision_id="def1", input_binding_id="synthetic1")

def execution(identity, contract, position, event, price, quantity, side, *, known=None, boundary=None):
    return dict(execution_id=identity, revision_id="v1", kind="new",
                target_execution_id=None, target_revision_id=None, contract_id=contract,
                session_id="S10", stream_id="stream-"+contract, position=position,
                event_ns=event, signing_boundary_ns=event if boundary is None else boundary,
                known_at_ns=event if known is None else known, price=price, quantity=quantity,
                condition="regular", venue_id=None, observed_side=side,
                observed_side_semantics_id="supplied-side1",
                observed_side_known_at_ns=event if known is None else known,
                reference_id="ref-"+contract, input_binding_id="synthetic1")

def inputs(executions, references, outputs, *, complete=True, start=10, end=20, cutoff=20, members=None):
    contracts=sorted({r["contract_id"] for r in references})
    cursors=[dict(stream_id="stream-"+c, max_position=max([e["position"] for e in executions if e["contract_id"]==c] or [0])) for c in contracts]
    group=dict(group_id="all", kind="underlying", underlying_id="SYNTH-U",
               contract_ids=contracts, right=None, expiry_ordinal=None,
               currency="XTS", action_basis_id="synthetic-unadjusted1")
    population=dict(population_id="population1", group_id="all",
                    window_start_ns=start, window_end_ns=end,
                    expected_contract_ids=contracts,
                    expected_execution_ids=sorted(members if members is not None else [e["execution_id"] for e in executions]),
                    expected_quote_ids=[], complete=complete, known_at_ns=0, input_binding_id="synthetic1")
    snapshot=dict(schema_version="option-flow-canonical1", bindings=[binding()],
                  references=sorted(references,key=lambda r:r["reference_id"]),
                  executions=sorted(executions,key=lambda e:(e["execution_id"],e["revision_id"])),
                  quotes=[], groups=[group], populations=[population],
                  context_certificates=[], baselines=[], cursors=cursors)
    policy=dict(schema_version="r26-flow-policy1", temporal_profile="option-origin-context1",
                signing_profile="option-observed-side1", max_quote_age_ns=100, max_spot_age_ns=100,
                short_dte_max_days=7, cluster_max_adjacent_gap_ns=5, horizon_id="window10",
                minimum_matched_prior_windows=1)
    request=dict(schema_version="option-flow-request1", group_ids=["all"],
                 output_ids=sorted(outputs), window_start_ns=start, window_end_ns=end,
                 knowledge_cutoff_ns=cutoff, target_session_ordinal=10, policy=policy,
                 baseline_targets=[], cut_cursors=copy.deepcopy(cursors),
                 formula_version="option-flow-formulas1", limits=copy.deepcopy(LIMITS))
    return snapshot, request

def case(identity, snapshot, request, expected):
    return dict(id=identity, snapshot=snapshot, request=request, expected_projection=expected,
                snapshot_record_sha256=record_digest("flow_snapshot",snapshot),
                request_record_sha256=record_digest("flow_request",request),
                snapshot_wire=envelope("flow_snapshot",snapshot),
                request_wire=envelope("flow_request",request))

def construct():
    a=reference("A","call","100",20)
    b=reference("B","put","100",20)
    c=reference("C","put","50",21)
    executions=[execution("a","A",1,11,"2","3","buy"),
                execution("b","A",2,12,"1.5","2","sell"),
                execution("c","B",1,13,"4","1","buy"),
                execution("d","C",1,14,"2","1","unknown")]
    s,r=inputs(executions,[a,b,c],F01_VALUES)
    cases=[case("F01-mixed-multiplier-rollup",s,r,
                dict(available=F01_VALUES, coverage=dict(population_complete=True,
                     expected_count=4, observed_count=4, eligible_count=4,
                     signed_count=3, unknown_sign_count=1, dte_eligible_count=0, otm_eligible_count=0)))]
    s,r=inputs([], [a], ["flow.premium","flow.contract_hhi"])
    cases.append(case("F02-complete-empty",s,r,dict(
        available={"flow.premium":"0/1"}, undefined={"flow.contract_hhi":"zero_denominator"},
        coverage=dict(population_complete=True,expected_count=0,observed_count=0,eligible_count=0))))
    e=[execution("large","A",1,11,"9007199254740993","1","buy"),
       execution("tiny","A",2,12,"0.000000000000000001","1","buy")]
    s,r=inputs(e,[reference("A","call","1",20)],["flow.premium"])
    cases.append(case("F07-exact-tiny-large-premium",s,r,dict(available={
        "flow.premium":"9007199254740993000000000000000001/1000000000000000000"})))
    e=[execution("a","A",1,11,"2","1","buy"),
       execution("b","A",2,14,"1","1","buy",known=25,boundary=25)]
    s,r=inputs(e,[a],["flow.premium"])
    cases.append(case("F39-complete-certificate-future-member",s,r,dict(
        unavailable={"flow.premium":"incomplete_population"},
        coverage=dict(population_complete=False,expected_count=None,observed_count=1,eligible_count=1),
        evidence_operands={"premium":"200/1"})))
    e=[execution("a","A",1,10,"2","1","buy",boundary=30)]
    s,r=inputs(e,[a],["flow.premium"],start=0,end=15,cutoff=20)
    cases.append(case("F40-selected-origin-boundary-after-cutoff",s,r,dict(
        error=dict(code="identity_mismatch",path="/request/knowledge_cutoff_ns"))))
    r2=copy.deepcopy(r);r2["knowledge_cutoff_ns"]=30
    cases.append(case("F40-control-boundary-admitted",s,r2,dict(available={"flow.premium":"200/1"})))
    return dict(schema="r26-independent-materialization-tranche1", source_scenarios_sha256=SOURCE_SCENARIOS_SHA256,
                independence="No production imports; explicit synthetic facts and frozen hand expectations.",
                limitations=["Six invocations from five scenarios only; not forty-scenario coverage.",
                             "Economic projections and independent input bytes/hashes; no full result/evidence/hash oracle yet.",
                             "No executed production conformance or numerical acceptance implied."], cases=cases)

if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    output=canonical(construct())
    args.destination.write_bytes(output+b"\n")
    print(json.dumps(dict(bytes=len(output)+1, sha256=hashlib.sha256(output+b"\n").hexdigest(),
                          invocations=6, source_scenarios=5, full_result_goldens=False)))

