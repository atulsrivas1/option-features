"""Additional original R26 fixture materialization, independent of production.

Source authoring only until coordinator grants the serialized execution lease.
Uses only the independently reviewed reference writer and standard library.
Expected numerical projections below are literal hand witnesses, never production
outputs. Full result goldens are deliberately identified case by case.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from fractions import Fraction

import independent_reference as ref

SCENARIOS_SHA256 = "a0cdaaa6abc8441f3cf8ecb069fae2c89477979a7543e2cc96649f13dc4bfa1c"
REFERENCE_SOURCE_SHA256 = "d4bdce4898fb76eff30be89e201e2fb5b53762462470cdbfaa01729182295ec1"
REVIEWED_CONTRACT_COMMIT = "d19d84bbc6f9afbb2deb03b5aad768cb4cacf51f"
FROZEN_CONTRACT_TREE = "1b982b8004062ff6198ed461beccaffc5b508604"
PRIOR_MERGED_CONTRACT_COMMIT = "23194707c844413ed9e8fdb018715647b0b30aa8"
FROZEN_AMENDMENT_SCENARIOS = ["F43-context-members-and-dimensional-operands",
                             "F44-reduced-rational-limit-vs-bounded-scratch"]

BASE_OUTPUTS = ["flow.trade_count", "flow.contracts", "flow.premium",
                "flow.signed_execution_premium", "flow.contract_hhi"]
CLUSTER_OUTPUTS = ["execution.cluster_premium", "execution.cluster_trade_count",
                   "execution.cluster_contracts", "execution.cluster_span_ns",
                   "execution.cluster_venue_count", "execution.cluster_coverage"]
ACTIVITY_OUTPUTS = ["activity.contracts_median", "activity.trade_count_median",
                    "activity.premium_median", "activity.premium_mad",
                    "activity.relative_volume", "activity.relative_trade_count",
                    "activity.premium_robust_z"]
REFERENCE_OUTPUTS = ["flow.short_dte_premium_share", "flow.dte_reference_coverage",
                     "flow.short_dte_known_reference_share", "flow.short_dte_observed_lower_share",
                     "flow.otm_premium_share", "flow.otm_reference_coverage",
                     "flow.otm_known_reference_share", "flow.otm_observed_lower_share"]


def clone(value):
    return copy.deepcopy(value)


def digest(domain, payload):
    return hashlib.sha256(domain.encode("utf-8") + b"\n" + ref.canonical(payload)).hexdigest()


def rational(text):
    numerator, denominator = text.split("/")
    return dict(numerator=numerator, denominator=denominator)


def root(identity="a", *, contract="A", position=1, event=11,
         price="2", quantity="1", side="buy", known=None, boundary=None):
    return ref.execution(identity, contract, position, event, price, quantity,
                         side, known=known, boundary=boundary)


def definition(contract="A", *, right="call", multiplier="100", expiry=20):
    return ref.reference(contract, right, multiplier, expiry)


def revision(original, *, position, known, price=None, quantity=None, cancel=False,
             revision_id="v2", target_revision_id="v1"):
    item = clone(original)
    item.update(revision_id=revision_id, kind="cancel" if cancel else "replace",
                target_execution_id=original["execution_id"],
                target_revision_id=target_revision_id, position=position, known_at_ns=known)
    if cancel:
        item.update(price=None, quantity=None, condition="excluded", observed_side="unknown",
                    observed_side_semantics_id=None, observed_side_known_at_ns=None)
    else:
        if price is not None:
            item["price"] = price
        if quantity is not None:
            item["quantity"] = quantity
    return item


def quote(identity="q", *, contract="A", position=1, event=10, known=None,
          bid="1", ask="3"):
    return dict(quote_id=identity, revision_id="v1", kind="new",
                target_quote_id=None, target_revision_id=None, contract_id=contract,
                stream_id="stream-" + contract, position=position, event_ns=event,
                known_at_ns=event if known is None else known,
                bid=bid, ask=ask, condition="regular", input_binding_id="synthetic1")


def quote_revision(original, *, position, known, bid, ask):
    item = clone(original)
    item.update(revision_id="v2", kind="replace", target_quote_id=original["quote_id"],
                target_revision_id="v1", position=position, known_at_ns=known,
                bid=bid, ask=ask)
    return item


def canonical_order(snapshot):
    keys = {"bindings": lambda x: x["binding_id"],
            "references": lambda x: x["reference_id"],
            "executions": lambda x: (x["execution_id"], x["revision_id"]),
            "quotes": lambda x: (x["quote_id"], x["revision_id"]),
            "groups": lambda x: x["group_id"],
            "populations": lambda x: x["population_id"],
            "context_certificates": lambda x: x["certificate_id"],
            "baselines": lambda x: x["baseline_id"],
            "cursors": lambda x: x["stream_id"]}
    for name, key in keys.items():
        snapshot[name].sort(key=key)
    return snapshot


def make(executions=None, references=None, outputs=None, *, start=10, end=20,
         cutoff=20, complete=True, profile="option-observed-side1", quotes=None,
         context=True, members=None):
    executions = [root()] if executions is None else clone(executions)
    references = [definition()] if references is None else clone(references)
    snapshot, request = ref.inputs(executions, references, outputs or BASE_OUTPUTS,
                                  start=start, end=end, cutoff=cutoff, complete=complete,
                                  members=members or sorted({e["execution_id"] for e in executions}))
    snapshot["quotes"] = clone(quotes or [])
    for cursor in snapshot["cursors"]:
        positions = [x["position"] for x in executions + snapshot["quotes"]
                     if x["stream_id"] == cursor["stream_id"]]
        cursor["max_position"] = max(positions or [0])
    request["cut_cursors"] = clone(snapshot["cursors"])
    snapshot["populations"][0]["expected_quote_ids"] = sorted({q["quote_id"] for q in snapshot["quotes"]})
    request["policy"]["signing_profile"] = profile
    request["policy"]["short_dte_max_days"] = 2
    if context and profile != "option-observed-side1":
        for target in [e for e in executions if e["kind"] == "new"]:
            kind = "quote_prefix" if profile == "option-quote-midpoint1" else "execution_prefix"
            source = snapshot["quotes"] if kind == "quote_prefix" else executions
            ids = sorted({item["quote_id" if kind == "quote_prefix" else "execution_id"]
                          for item in source if item["kind"] == "new"
                          and item["stream_id"] == target["stream_id"]
                          and item["position"] <= target["position"]
                          and item.get("session_id", target["session_id"]) == target["session_id"]})
            snapshot["context_certificates"].append(dict(
                certificate_id="ctx-" + target["execution_id"], kind=kind,
                contract_id=target["contract_id"], session_id=target["session_id"],
                stream_id=target["stream_id"], session_start_ns=0,
                through_position=target["position"], expected_root_ids=ids, complete=True,
                known_at_ns=target["signing_boundary_ns"], input_binding_id="synthetic1"))
    return canonical_order(snapshot), request


def add(cases, identity, snapshot, request, expected, *, scenario=None,
        operation="evaluate", extra=None):
    value = ref.case(identity, canonical_order(snapshot), request, clone(expected))
    value["scenario_id"] = scenario or identity.split("-")[0]
    value["operation"] = operation
    value["expected_projection_scope"] = "Only explicitly listed fields; not a full-row oracle."
    value["full_result_goldens"] = False
    if extra:
        value.update(extra)
    cases.append(value)
    return value


def available(**values):
    return dict(available=values)


def sign_projection(signs, reasons=None):
    result = dict(signs=signs)
    if reasons:
        result["sign_reasons"] = reasons
    return result


def baseline_inputs(values=("2", "4", "6", "8"), *, current="11", minimum=4):
    e = root(price="1" if current != "0" else "0",
             quantity=current if current != "0" else "1", event=51)
    snapshot, request = make([e], [definition(multiplier="1")], ACTIVITY_OUTPUTS,
                             start=50, end=60, cutoff=60)
    request["policy"]["minimum_matched_prior_windows"] = minimum
    policy_sha = ref.record_digest("flow_policy", request["policy"])
    slots = []
    # Original synthetic integer tapes have v distinct price1/quantity1/
    # multiplier1 observations: premium, quantity and count all equal v.
    for index, value in enumerate(values):
        sid = "slot" + str(index + 1)
        slots.append(sid)
        prior_start = index * 10
        literal_history = dict(slot_id=sid, window_start_ns=prior_start,
                               window_end_ns=prior_start + 10,
                               contracts=value, trade_count=value, premium=value,
                               construction="v quantity1 price1 multiplier1 original synthetic executions")
        member_hashes = [digest("independent-r26-history1", [sid, n, "1", "1", "1"])
                         for n in range(int(value))]
        snapshot["baselines"].append(dict(
            baseline_id="baseline" + str(index + 1), group_id="all", slot_id=sid,
            session_ordinal=index + 1, horizon_id=request["policy"]["horizon_id"],
            window_start_ns=prior_start, window_end_ns=prior_start + 10, known_at_ns=prior_start + 10,
            policy_sha256=policy_sha,
            population_sha256=digest("independent-r26-history-population1", literal_history),
            currency="XTS", action_basis_id="synthetic-unadjusted1",
            contracts=rational(value + "/1"), trade_count=rational(value + "/1"),
            premium=rational(value + "/1"), member_record_sha256s=sorted(member_hashes),
            complete=True, input_binding_id="synthetic1"))
    request["baseline_targets"] = [dict(group_id="all", slot_ids=slots)]
    return canonical_order(snapshot), request


def reference_for_execution(execution, *, right="call", multiplier="100", expiry=12,
                            civil=10, strike="110", spot="100", spot_event=None,
                            spot_known=None, civil_known=None):
    value = definition(execution["contract_id"], right=right, multiplier=multiplier, expiry=expiry)
    value["reference_id"] = "ref-" + execution["execution_id"]
    value["strike"] = strike
    if civil is not None:
        value.update(civil_ordinal=civil, civil_instant_ns=execution["event_ns"],
                     civil_known_at_ns=execution["event_ns"] if civil_known is None else civil_known,
                     calendar_id="SYNTH-CAL", calendar_revision="1")
    if spot is not None:
        value.update(spot=spot,
                     spot_event_ns=max(0, execution["event_ns"] - 1) if spot_event is None else spot_event,
                     spot_known_at_ns=max(0, execution["event_ns"] - 1) if spot_known is None else spot_known,
                     spot_stream_id=execution["stream_id"], spot_position=0)
    execution["reference_id"] = value["reference_id"]
    return value


def exact(value):
    """Independent exact finite-decimal/integer interpretation, no Decimal context."""
    return Fraction(value)


def pair(value):
    value = Fraction(value)
    return dict(numerator=str(value.numerator), denominator=str(value.denominator))


def observed_full_rows(item):
    """Complete independent rows for bounded simple observed-side scenarios.

    Deliberately rejects revisions, quotes, activity/reference outputs and context
    certificates rather than silently approximating those metadata dependencies.
    Minimal context/operand-unit amendment is frozen at REVIEWED_CONTRACT_COMMIT.
    This independent writer still requires its own review and execution lease.
    """
    snapshot, request = item["snapshot"], item["request"]
    if request["policy"]["signing_profile"] != "option-observed-side1":
        return None
    if snapshot["quotes"] or snapshot["context_certificates"] or snapshot["baselines"]:
        return None
    if any(e["kind"] != "new" for e in snapshot["executions"]):
        return None
    if len(snapshot["groups"]) != 1 or request["group_ids"] != ["all"]:
        return None
    if not set(request["output_ids"]).issubset(ref.F01_VALUES):
        return None
    # This oracle covers missing civil/spot reference inputs only. Rich reference
    # membership has literal projections elsewhere, never false full-row claims.
    if any(a["civil_ordinal"] is not None or a["spot"] is not None for a in snapshot["references"]):
        return None
    if "error" in item["expected_projection"]:
        return None
    group = snapshot["groups"][0]
    refs = {a["reference_id"]:a for a in snapshot["references"]}
    cuts = {c["stream_id"]:c["max_position"] for c in request["cut_cursors"]}
    K = request["knowledge_cutoff_ns"]
    roots = snapshot["executions"]
    visible = {e["execution_id"]:e for e in roots
               if e["known_at_ns"] <= K and e["position"] <= cuts[e["stream_id"]]}
    active = sorted([e for e in visible.values() if e["condition"] == "regular"
                     and request["window_start_ns"] <= e["event_ns"] < request["window_end_ns"]],
                    key=lambda e:e["execution_id"])
    if any(e["signing_boundary_ns"] > K for e in active):
        return None
    populations = [p for p in snapshot["populations"] if p["group_id"]=="all"
                   and p["window_start_ns"]==request["window_start_ns"]
                   and p["window_end_ns"]==request["window_end_ns"]]
    if len(populations)>1:
        return None
    population = populations[0] if populations else None
    complete = bool(population and population["complete"] and population["known_at_ns"]<=K
                    and all(identity in visible for identity in population["expected_execution_ids"]))
    policy_hash = ref.record_digest("flow_policy", request["policy"])
    witnesses=[]
    for e in active:
        side=e["observed_side"]
        if e["observed_side_semantics_id"] is None:
            side, reason = "unknown", "observed_missing"
        elif e["observed_side_known_at_ns"] > e["signing_boundary_ns"]:
            side, reason = "unknown", "observed_future"
        else:
            reason={"buy":"observed_buy","sell":"observed_sell","unknown":"observed_unknown"}[side]
        context=[ref.record_digest("flow_execution",e),ref.record_digest("flow_reference",refs[e["reference_id"]])]
        witnesses.append(dict(execution_id=e["execution_id"],revision_id=e["revision_id"],
            sign=side,method="option-observed-side1",reason=reason,diagnostics=[],
            signing_boundary_ns=e["signing_boundary_ns"],
            context_sha256=digest("option-flow-context1",[e["signing_boundary_ns"],policy_hash,context,None]),
            context_certificate_id=None,quote_id=None,quote_revision_id=None,
            predecessor_execution_id=None,predecessor_revision_id=None))
    signs={w["execution_id"]:w["sign"] for w in witnesses}
    premiums={e["execution_id"]:exact(e["price"])*exact(e["quantity"])*exact(refs[e["reference_id"]]["multiplier"]) for e in active}
    N=Fraction(len(active)); C=sum((exact(e["quantity"]) for e in active),Fraction())
    U=sum((exact(e["quantity"])*exact(refs[e["reference_id"]]["multiplier"]) for e in active),Fraction())
    T=sum(premiums.values(),Fraction())
    A=sum((premiums[k] for k in premiums if signs[k]=="buy"),Fraction())
    B=sum((premiums[k] for k in premiums if signs[k]=="sell"),Fraction())
    Z=T-A-B; signed=sum(w["sign"]!="unknown" for w in witnesses)
    calls=sum((premiums[e["execution_id"]] for e in active if refs[e["reference_id"]]["right"]=="call"),Fraction())
    puts=T-calls
    positive=sum((premiums[e["execution_id"]] for e in active
        if (refs[e["reference_id"]]["right"],signs[e["execution_id"]]) in (("call","buy"),("put","sell"))),Fraction())
    negative=T-Z-positive
    weights={"contract":{c:Fraction() for c in group["contract_ids"]},
             "expiry":{str(a["expiry_ordinal"]):Fraction() for a in refs.values()}}
    for e in active:
        weights["contract"][e["contract_id"]]+=premiums[e["execution_id"]]
        weights["expiry"][str(refs[e["reference_id"]]["expiry_ordinal"])]+=premiums[e["execution_id"]]
    base=dict(count=N,contracts=C,share_equivalent=U,premium=T,buy_premium=A,sell_premium=B,
              unknown_premium=Z,signed_premium=A-B,call_premium=calls,put_premium=puts)
    operand_units=dict(count="executions",contracts="contracts",share_equivalent="payoff_units",
        premium="group_currency",buy_premium="group_currency",sell_premium="group_currency",
        unknown_premium="group_currency",signed_premium="group_currency",call_premium="group_currency",put_premium="group_currency")
    values={"flow.trade_count":N,"flow.contracts":C,"flow.share_equivalent":U,"flow.premium":T,
        "flow.buy_proxy_premium":A,"flow.sell_proxy_premium":B,"flow.unknown_premium":Z,
        "flow.signed_execution_premium":A-B,"flow.right_positive_premium":positive,
        "flow.right_negative_premium":negative,"flow.net_directional_premium":positive-negative,
        "flow.call_premium":calls,"flow.put_premium":puts}
    ratios={"flow.known_sign_imbalance":(A-B,A+B,"group_currency"),
        "flow.total_premium_imbalance":(A-B,T,"group_currency"),"flow.unknown_premium_share":(Z,T,"group_currency"),
        "flow.sign_event_coverage":(Fraction(signed),N,"executions"),
        "flow.sign_premium_coverage":(A+B,T,"group_currency"),"flow.put_call_premium_ratio":(puts,calls,"group_currency")}
    for partition in ("contract","expiry"):
        ratios["flow."+partition+"_hhi"]=(sum((v*v for v in weights[partition].values()),Fraction()),T*T,"group_currency_squared")
        ratios["flow."+partition+"_top_share"]=(max(weights[partition].values(),default=Fraction()),T,"group_currency")
    flags=[]
    if signed<len(active):flags.append("partial_sign_coverage")
    if active:flags.extend(["partial_dte_coverage","partial_otm_coverage"])
    if complete and not active:flags.append("complete_empty")
    flags.sort()
    coverage=dict(population_id=population["population_id"] if population else None,
        population_complete=complete,expected_count=len(active) if complete else None,
        observed_count=len(active),eligible_count=len(active),signed_count=signed,
        unknown_sign_count=len(active)-signed,dte_eligible_count=0,otm_eligible_count=0)
    exclusions=[]
    for e in roots:
        identity=e["execution_id"]
        if identity not in visible:reason="future_known"
        elif not request["window_start_ns"]<=e["event_ns"]<request["window_end_ns"]:reason="outside_window"
        elif e["condition"]!="regular":reason="excluded"
        else:continue
        exclusions.append(dict(execution_id=identity,revision_id=e["revision_id"],reason=reason))
    dependencies=[("flow_execution",e) for e in roots]
    needed_refs=sorted({e["reference_id"] for e in roots})
    dependencies.extend(("flow_reference",refs[key]) for key in needed_refs)
    dependencies.append(("flow_group",group))
    if population:dependencies.append(("flow_population",population))
    dependency_hashes=sorted({ref.record_digest(kind,value) for kind,value in dependencies})
    dependency_bindings=sorted({value["input_binding_id"] for kind,value in dependencies if "input_binding_id" in value})
    availability=max([0]+[e["known_at_ns"] for e in active]+[refs[e["reference_id"]]["known_at_ns"] for e in active]
        +([population["known_at_ns"]] if population and population["known_at_ns"]<=K else [])
        +[e["observed_side_known_at_ns"] for e in active if e["observed_side_known_at_ns"] is not None
          and e["observed_side_known_at_ns"]<=e["signing_boundary_ns"]])
    rows=[]
    for output in request["output_ids"]:
        numerator=denominator=None
        operands=clone(base); units=clone(operand_units)
        if output in ratios:
            numerator,denominator,ratio_unit=ratios[output]
            operands.update(numerator=numerator,denominator=denominator)
            units.update(numerator=ratio_unit,denominator=ratio_unit)
        if not complete:
            value,status,reason=None,"unavailable","incomplete_population"
        elif output in ratios and denominator==0:
            value,status,reason=None,"undefined","zero_denominator"
        else:
            value=values[output] if output in values else numerator/denominator
            status,reason="available","ok"
        unit={"flow.trade_count":"executions","flow.contracts":"contracts","flow.share_equivalent":"payoff_units"}.get(output,
            "ratio" if output in ratios else "group_currency")
        tops=[]
        if output.endswith("_top_share") and T:
            partition="contract" if output=="flow.contract_top_share" else "expiry"
            tops=sorted(k for k,v in weights[partition].items() if v==max(weights[partition].values()))
        diagnostics=sorted(set(flags+[w["reason"] for w in witnesses]+([] if reason=="ok" else [reason])
            +(["missing_dte_reference","missing_spot_reference"] if active else [])))
        evidence=dict(active_execution_ids=[e["execution_id"] for e in active],
            active_revision_ids=[e["revision_id"] for e in active],exclusions=exclusions,
            operands=[dict(name=name,value=pair(operands[name]),unit=units[name]) for name in sorted(operands)],
            partition_weights=[dict(partition_kind=kind,partition_id=identity,premium=pair(v))
                for kind in sorted(weights) for identity,v in sorted(weights[kind].items())],
            tied_top_ids=tops,cluster=None,baseline_slot_ids=[],baseline_record_sha256s=[],
            required_producer_ids=[],diagnostics=diagnostics)
        rows.append(dict(schema_version="option-flow-result1",group_id="all",output_id=output,cluster_id=None,
            window_start_ns=request["window_start_ns"],window_end_ns=request["window_end_ns"],
            knowledge_cutoff_ns=K,available_at_ns=availability,temporal_profile="option-origin-context1",
            currency="XTS",action_basis_id="synthetic-unadjusted1",origin="computed",
            value=None if value is None else pair(value),unit=unit,status=status,reason=reason,
            quality_flags=clone(flags),coverage=clone(coverage),sign_witnesses=clone(witnesses),evidence=evidence,
            numerator=None if numerator is None else pair(numerator),denominator=None if denominator is None else pair(denominator),
            baseline_ids=[],dependency_binding_ids=dependency_bindings,dependency_record_sha256s=dependency_hashes,
            policy_sha256=policy_hash,request_sha256=item["request_record_sha256"],snapshot_sha256=item["snapshot_record_sha256"],
            checkpoint_sha256=None,formula_version="option-flow-formulas1",contracts_package_version="0.1.0a1",
            calculation_package_version="0.1.0a1"))
    return rows


def projected_cases():
    """Source-only construction. No production import/evaluation is performed."""
    cases = []
    inherited = ref.construct()["cases"]
    for inherited_case in inherited:
        inherited_case["scenario_id"] = inherited_case["id"].split("-")[0]
        inherited_case["operation"] = "evaluate"
        inherited_case["full_result_goldens"] = False
        inherited_case["expected_projection_scope"] = "Listed literal fields only."
        cases.append(inherited_case)

    s, r = make(complete=False)
    add(cases, "F03-incomplete", s, r, dict(
        unavailable={name: "incomplete_population" for name in r["output_ids"]},
        coverage=dict(population_complete=False, expected_count=None, observed_count=1, eligible_count=1),
        evidence_operands={"premium": "200/1"}))
    s, r = make(); s["populations"] = []
    add(cases, "F04-population-absent", s, r, dict(
        unavailable={name: "incomplete_population" for name in r["output_ids"]},
        coverage=dict(population_complete=False, expected_count=None)))
    s, r = make([root(side="unknown")], [definition(multiplier="50")],
                ["flow.premium", "flow.unknown_premium", "flow.signed_execution_premium",
                 "flow.sign_event_coverage", "flow.sign_premium_coverage", "flow.unknown_premium_share",
                 "flow.total_premium_imbalance", "flow.contract_hhi", "flow.known_sign_imbalance"])
    add(cases, "F05-unknown-side", s, r, dict(available={
        "flow.premium":"100/1", "flow.unknown_premium":"100/1", "flow.signed_execution_premium":"0/1",
        "flow.sign_event_coverage":"0/1", "flow.sign_premium_coverage":"0/1",
        "flow.unknown_premium_share":"1/1", "flow.total_premium_imbalance":"0/1", "flow.contract_hhi":"1/1"},
        undefined={"flow.known_sign_imbalance":"zero_denominator"}, signs={"a": "unknown"}))
    s, r = make([root(price="0", quantity="2")], [definition(multiplier="50")],
                ["flow.trade_count", "flow.contracts", "flow.share_equivalent", "flow.premium",
                 "flow.sign_event_coverage", "flow.sign_premium_coverage", "flow.contract_hhi",
                 "flow.put_call_premium_ratio"])
    add(cases, "F06-zero-price", s, r, dict(available={"flow.trade_count":"1/1", "flow.contracts":"2/1",
        "flow.share_equivalent":"100/1", "flow.premium":"0/1", "flow.sign_event_coverage":"1/1"},
        undefined={"flow.sign_premium_coverage":"zero_denominator", "flow.contract_hhi":"zero_denominator",
                   "flow.put_call_premium_ratio":"zero_denominator"}))
    e = [root("before", event=9, position=1, price="1"), root("start", event=10, position=2),
         root("inside", event=19, position=3, price="3"), root("end", event=20, position=4, price="4")]
    s, r = make(e)
    add(cases, "F08-half-open", s, r, dict(available={"flow.trade_count":"2/1", "flow.premium":"500/1"},
        active_execution_ids=["inside", "start"], exclusions={"before":"outside_window", "end":"outside_window"}))
    e = [root("a", contract="A"), root("b", contract="B"), root("c", contract="C", price="1")]
    s, r = make(e, [definition(c) for c in ("A", "B", "C")],
                ["flow.premium", "flow.contract_hhi", "flow.contract_top_share"])
    add(cases, "F09-top-ties", s, r, dict(available={"flow.premium":"500/1", "flow.contract_hhi":"9/25",
        "flow.contract_top_share":"2/5"}, tied_top_ids={"flow.contract_top_share":["A", "B"]}))

    for index, (price, sign, reason) in enumerate([
        ("2", "unknown", "quote_midpoint"), ("2.5", "buy", "quote_above_midpoint"),
        ("1.5", "sell", "quote_below_midpoint"), ("2.0000005", "buy", "quote_above_midpoint"),
        ("3.5", "buy", "quote_above_midpoint")]):
        s, r = make([root(position=2, event=15, price=price)], profile="option-quote-midpoint1",
                    quotes=[quote(event=12)])
        expectation = sign_projection({"a":sign}, {"a":reason})
        if index == 4:
            expectation["sign_diagnostics_include"] = {"a":["outside_spread"]}
        add(cases, "F10-midpoint-" + str(index), s, r, expectation)
    for name, bid, ask, reason in [("locked", "2", "2", "quote_locked"),
                                   ("crossed", "3", "2", "quote_crossed"),
                                   ("one-sided", "1", None, "quote_one_sided")]:
        qs = [quote("old", event=11, position=1), quote("latest", event=14, position=2, bid=bid, ask=ask)]
        s, r = make([root(position=3, event=15, price="2.5")], profile="option-quote-midpoint1", quotes=qs)
        add(cases, "F11-latest-" + name, s, r, dict(signs={"a":"unknown"}, sign_reasons={"a":reason},
            selected_quotes={"a":["latest", "v1"]}))
    for label, event, known, position, reason in [
        ("age-equal", 12, 12, 1, "quote_above_midpoint"),
        ("stale", 11, 11, 1, "quote_stale"),
        ("same-time-before", 15, 15, 1, "quote_above_midpoint")]:
        s, r = make([root(position=2, event=15, price="2.5")], profile="option-quote-midpoint1",
                    quotes=[quote(event=event, known=known, position=position)])
        r["policy"]["max_quote_age_ns"] = 3
        add(cases, "F12-" + label, s, r, dict(signs={"a":"buy" if reason == "quote_above_midpoint" else "unknown"},
            sign_reasons={"a":reason}))
    # A future quote cannot be hidden from expected-context closure. Its root is
    # retained in the certificate, so the primary unknown is missing context,
    # not a fabricated valid quote or an older fallback.
    s, r = make([root(position=2, event=15, price="2")], profile="option-quote-midpoint1",
                quotes=[quote(event=14, known=16)])
    add(cases, "F12-future-context-member", s, r, dict(signs={"a":"unknown"},
        sign_diagnostics_include={"a":["incomplete_context"]}))

    prices = ["100", "100", "101", "101", "99", "99"]
    e = [root("t" + str(i), position=i, event=10+i, price=p) for i, p in enumerate(prices, 1)]
    e.append(root("other", contract="B", event=13, price="102"))
    s, r = make(e, [definition(), definition("B")], profile="option-tick1", end=18)
    add(cases, "F13-tick-partitions", s, r, sign_projection(dict(
        t1="unknown", t2="unknown", t3="buy", t4="buy", t5="sell", t6="sell", other="unknown")))
    e = [root("h1", event=8, position=1, price="101"),
         root("h2", event=9, position=2, price="100"), root("a", event=10, position=3, price="100")]
    s, r = make(e, profile="option-tick1")
    add(cases, "F14-historical-prefix", s, r, dict(signs={"a":"sell"}, sign_reasons={"a":"tick_carried"}))
    s2 = clone(s)
    for certificate in s2["context_certificates"]:
        if certificate["certificate_id"] == "ctx-a":
            certificate["known_at_ns"] = 11
    add(cases, "F14-prefix-certificate-future", s2, r, dict(signs={"a":"unknown"},
        sign_reasons={"a":"tick_seed_unavailable"}))

    for identity, corrected_price, known, expected_signs in [
        ("F15-correction-equal", "100", 25, dict(a="unknown", b="unknown", c="buy")),
        ("F16-correction-flips", "102", 25, dict(a="unknown", b="buy", c="sell")),
        ("F17-late-correction-denied", "102", 35, dict(a="unknown", b="buy", c="buy"))]:
        a = root("a", event=10, position=1, price="100")
        b = root("b", event=20, position=2, price="101")
        replacement_position = 3 if known == 25 else 4
        c = root("c", event=30, position=4 if known == 25 else 3, price="101")
        change = revision(b, position=replacement_position, known=known, price=corrected_price)
        s, r = make([a, b, change, c], profile="option-tick1", start=0, end=31, cutoff=40)
        add(cases, identity, s, r, dict(signs=expected_signs, available_at_at_least=known))

    a = root("a", event=10, position=1, price="100")
    b = root("b", event=20, position=2, price="101")
    cancellation = revision(a, position=3, known=30, cancel=True)
    c = root("c", event=40, position=4, price="101")
    s, final_request = make([a, b, cancellation, c], profile="option-tick1", start=0, end=41, cutoff=45)
    # Each cut has a distinct immutable population certificate; target window is
    # part of certificate selection. Both early cuts share [0,21).
    early_population = clone(s["populations"][0])
    early_population.update(population_id="population-early", window_end_ns=21,
                            expected_execution_ids=["a", "b"])
    s["populations"].append(early_population)
    cut_requests = []
    for cutoff, end, cursor, signs in [(25,21,2,dict(a="unknown", b="buy")),
                                      (35,21,3,dict(b="buy")), (45,41,4,dict(b="buy",c="unknown"))]:
        request = clone(final_request)
        request.update(knowledge_cutoff_ns=cutoff, window_end_ns=end)
        request["cut_cursors"][0]["max_position"] = cursor
        cut_requests.append(request)
        add(cases, "F18-cancel-origin-K" + str(cutoff), clone(s), request, dict(signs=signs))
    add(cases, "F32-chronological-cuts", clone(s), final_request,
        dict(cut_signs=[dict(a="unknown",b="buy"),dict(b="buy"),dict(b="buy",c="unknown")]),
        operation="replay", extra=dict(requests=cut_requests))

    q = quote(event=12, position=1)
    e = root(position=2, event=15, price="2")
    qr = quote_revision(q, position=3, known=16, bid="2", ask="4")
    er = revision(e, position=4, known=17, price="2.5")
    for corrected in (False, True):
        s, r = make([e, er] if corrected else [e], profile="option-quote-midpoint1",
                    quotes=[q, qr], end=16, cutoff=18)
        add(cases, "F19-quote-correction-" + ("price-replaced" if corrected else "original"), s, r,
            dict(signs={"a":"buy" if corrected else "unknown"},
                 selected_quotes={"a":["q","v1"]}, available_at_at_least=17 if corrected else 15))

    s, r = make(); duplicated = clone(s)
    duplicated["executions"].append(clone(duplicated["executions"][0]))
    add(cases, "F20-typed-duplicate", duplicated, r,
        dict(error=dict(code="identity_conflict")))
    for label, mutate in [
        ("missing-target", lambda e: e.update(target_execution_id="a",target_revision_id="absent")),
        ("changed-root-time", lambda e: e.update(event_ns=10)),
        ("known-regression", lambda e: e.update(known_at_ns=10))]:
        a = root(); change = revision(a, position=2, known=15, price="3"); mutate(change)
        s, r = make([a, change])
        add(cases, "F20-" + label, s, r, dict(error=dict(
            code="missing_identity" if label == "missing-target" else "invalid_correction")))

    qs = [quote(event=9, position=1, bid="0", ask="1")]
    es = [root("e10", position=2, event=10, price="1", quantity="1"),
          root("e15", position=3, event=15, price="1", quantity="2"),
          root("e20", position=4, event=20, price="1", quantity="3")]
    for e, venue in zip(es, ("V1", "V2", "V1")):
        e["venue_id"] = venue
    s, r = make(es, quotes=qs, profile="option-quote-midpoint1", outputs=CLUSTER_OUTPUTS,
                start=10, end=21, cutoff=21)
    add(cases, "F21-adjacent-gap", s, r, dict(cluster_members=[["e10","e15","e20"]],
        cluster_values={"execution.cluster_premium":["600/1"],"execution.cluster_trade_count":["3/1"],
        "execution.cluster_contracts":["6/1"],"execution.cluster_span_ns":["10/1"],
        "execution.cluster_venue_count":["2/1"]},available={"execution.cluster_coverage":"1/1"}))
    # q1 midpoint1, q2 midpoint2; selected prices create +,unknown,+,+,-,-.
    qs = [quote("q1", position=1,event=9,bid="0",ask="2"),
          quote("q2", position=5,event=13,bid="2",ask="4")]
    es = [root("a",position=2,event=10,price="2",quantity="1"),
          root("b",position=3,event=11,price="1",quantity="2"),
          root("c",position=4,event=12,price="2",quantity="2"),
          root("d",position=6,event=13,price="4",quantity="1"),
          root("e",position=7,event=14,price="2",quantity="3"),
          root("f",position=8,event=20,price="2",quantity="1")]
    # Same-contract multiplier50 gives exactly the original shorthand premiums.
    s, r = make(es, [definition(multiplier="50")], quotes=qs, profile="option-quote-midpoint1", outputs=CLUSTER_OUTPUTS,
                end=21,cutoff=21)
    add(cases, "F22-cluster-breaks", s, r, dict(cluster_members=[["a"],["c"],["d"],["e"],["f"]],
        cluster_values={"execution.cluster_premium":["100/1","200/1","200/1","300/1","100/1"]},
        available={"execution.cluster_coverage":"9/10"}, signs=dict(a="buy",b="unknown",c="buy",d="buy",e="sell",f="sell")))
    for profile in ("option-tick1", "option-observed-side1"):
        s, r = make(profile=profile,outputs=CLUSTER_OUTPUTS)
        add(cases, "F23-unsupported-" + profile, s, r, dict(
            unsupported={name:"unsupported_profile" for name in CLUSTER_OUTPUTS}))
    s2, r2 = make([root(position=2)], quotes=[quote(event=10)], profile="option-quote-midpoint1",
                  outputs=["execution.cluster_premium", "execution.cluster_venue_count"])
    s2["executions"][0]["price"] = "3"
    add(cases, "F23-missing-venue", s2, r2, dict(cluster_values={"execution.cluster_premium":["300/1"]},
        cluster_statuses={"execution.cluster_venue_count":[["unavailable","missing_venue_reference"]]}))

    s, r = baseline_inputs()
    add(cases, "F24-median-mad", s, r, dict(available={"activity.contracts_median":"5/1",
        "activity.trade_count_median":"5/1", "activity.premium_median":"5/1", "activity.premium_mad":"2/1",
        "activity.relative_volume":"11/5", "activity.relative_trade_count":"1/5",
        "activity.premium_robust_z":"5000/2471"}))
    for label, values, current, expected in [
        ("constant", ("5","5","5","5"), "10", dict(available={"activity.relative_volume":"2/1"},
            undefined={"activity.premium_robust_z":"zero_mad"})),
        ("zero", ("0","0","0","0"), "0", dict(undefined={"activity.relative_volume":"zero_denominator",
            "activity.premium_robust_z":"zero_mad"})),
        ("zero-current", ("2","4","6","8"), "0", dict(available={"activity.premium_robust_z":"-12500/7413"}))]:
        s, r = baseline_inputs(values,current=current)
        s["executions"][0].update(price="0" if current == "0" else "1",
                                  quantity="1" if current == "0" else current)
        add(cases, "F25-" + label, s, r, expected)
    for label in ("missing", "incomplete", "future", "minimum", "wrong-horizon", "current-session", "premium-null"):
        s, r = baseline_inputs()
        expected = {}
        if label == "missing":
            del s["baselines"][2]; expected = dict(unavailable={n:"incomplete_baseline" for n in ACTIVITY_OUTPUTS})
        elif label == "incomplete":
            s["baselines"][2]["complete"] = False; expected = dict(unavailable={n:"incomplete_baseline" for n in ACTIVITY_OUTPUTS})
        elif label == "future":
            s["baselines"][2]["known_at_ns"] = 61; expected = dict(unavailable={n:"future_reference" for n in ACTIVITY_OUTPUTS})
        elif label == "minimum":
            r["policy"]["minimum_matched_prior_windows"] = 5
            for baseline in s["baselines"]:
                baseline["policy_sha256"] = ref.record_digest("flow_policy",r["policy"])
            expected = dict(unavailable={n:"insufficient_history" for n in ACTIVITY_OUTPUTS})
        elif label == "wrong-horizon":
            s["baselines"][2]["horizon_id"] = "wrong"
            expected = dict(error=dict(code="identity_mismatch"))
        elif label == "current-session":
            s["baselines"][2]["session_ordinal"] = 10
            expected = dict(error=dict(code="identity_mismatch"))
        else:
            s["baselines"][2]["premium"] = None
            expected = dict(unavailable={"activity.premium_median":"incomplete_baseline",
                "activity.premium_mad":"incomplete_baseline","activity.premium_robust_z":"incomplete_baseline"},
                available={"activity.contracts_median":"5/1","activity.relative_volume":"11/5"})
        # price1*q11 gives premium11, with count1.
        s["executions"][0]["price"] = "1"
        add(cases, "F26-"+label, s, r, expected)

    e = [root("a",position=1,event=11,quantity="3"), root("b",position=2,event=12,price="1.5",quantity="2",side="sell"),
         root("c",contract="B",event=13,price="4"), root("d",contract="C",event=14,side="unknown")]
    references = [reference_for_execution(e[0]),reference_for_execution(e[1]),
                  reference_for_execution(e[2],right="put",expiry=13,strike="90"),
                  reference_for_execution(e[3],right="put",multiplier="50",expiry=11,strike="90",spot=None)]
    s, r = make(e,references,REFERENCE_OUTPUTS)
    add(cases, "F27-separated-references", s, r, dict(available={
        "flow.short_dte_premium_share":"5/7", "flow.dte_reference_coverage":"1/1",
        "flow.short_dte_known_reference_share":"5/7", "flow.short_dte_observed_lower_share":"5/7",
        "flow.otm_reference_coverage":"13/14", "flow.otm_known_reference_share":"1/1",
        "flow.otm_observed_lower_share":"13/14"}, unavailable={"flow.otm_premium_share":"missing_spot_reference"},
        coverage=dict(dte_eligible_count=4,otm_eligible_count=3)))
    for max_days in (0,2,3):
        e = [root("d0",contract="A",event=11),root("d2",contract="B",event=12),root("d3",contract="C",event=13)]
        refs = [reference_for_execution(e[0],expiry=10,strike="100"),
                reference_for_execution(e[1],expiry=12,strike="100",right="put"),
                reference_for_execution(e[2],expiry=13,strike="101")]
        s,r = make(e,refs,REFERENCE_OUTPUTS);r["policy"]["short_dte_max_days"] = max_days
        add(cases,"F28-short-max-"+str(max_days),s,r,dict(available={
            "flow.short_dte_premium_share":{0:"1/3",2:"2/3",3:"1/1"}[max_days],
            "flow.otm_premium_share":"1/3"}))
    for label, event, known, good in [("age-equal",12,12,True),("stale",11,11,False),
                                    ("future-known",14,16,False),("future-event",16,16,False)]:
        e = root(event=15)
        a = reference_for_execution(e,spot_event=event,spot_known=known)
        s,r = make([e],[a],REFERENCE_OUTPUTS);r["policy"]["max_spot_age_ns"] = 3
        exp = dict(available={"flow.short_dte_premium_share":"1/1",
            "flow.otm_reference_coverage":"1/1" if good else "0/1"})
        if good: exp["available"]["flow.otm_premium_share"] = "1/1"
        else: exp["unavailable"]={"flow.otm_premium_share":"missing_spot_reference"}
        add(cases,"F29-spot-"+label,s,r,exp)

    # A full prefix checkpoint is independently constructed from the source
    # contract, not obtained from production make_flow_checkpoint.
    prefix_s, prefix_r = make([root("a",event=10,position=1,price="100"),
        root("b",event=20,position=2,price="101")], profile="option-tick1",start=0,end=21,cutoff=25)
    checkpoint = dict(schema_version="option-flow-checkpoint1",history=prefix_s,prior_request=prefix_r,
        history_sha256=ref.record_digest("flow_snapshot",prefix_s),
        prior_request_sha256=ref.record_digest("flow_request",prefix_r),
        policy_sha256=ref.record_digest("flow_policy",prefix_r["policy"]),formula_version="option-flow-formulas1")
    a = prefix_s["executions"][0]
    cancel = revision(a,position=3,known=30,cancel=True)
    c = root("c",event=40,position=4,price="101")
    suffix_s, restore_r = make([cancel,c],profile="option-tick1",start=0,end=41,cutoff=45,
                               members=["a","b","c"])
    suffix_s["populations"][0]["population_id"] = "population-restored"
    # Suffix context c must include retained b; root a remains in ledger for b's
    # originalA20 context but is cancelled in c's A40 predecessor sweep.
    suffix_s["context_certificates"][0]["expected_root_ids"] = ["a","b","c"]
    add(cases,"F30-full-prefix-restore",suffix_s,restore_r,dict(signs={"b":"buy","c":"unknown"}),
        operation="restore",extra=dict(checkpoint=checkpoint,
            input_checkpoint_sha256=ref.record_digest("flow_checkpoint",checkpoint),
            compare_rule="Full bytes against direct merged same checkpoint; economic projection against flat null-checkpoint batch."))
    for label in ("missing-ancestor","tampered-digest","changed-policy","cursor-regression"):
        cp=clone(checkpoint); rr=clone(restore_r)
        if label=="missing-ancestor":
            cp["history"]["executions"].pop(0)
            cp["history_sha256"]=ref.record_digest("flow_snapshot",cp["history"])
            error="missing_identity"
        elif label=="tampered-digest":
            cp["history"]["executions"][0]["price"]="99";error="digest_mismatch"
        elif label=="changed-policy":
            rr["policy"]["max_quote_age_ns"]=101;error="identity_mismatch"
        else:
            rr["cut_cursors"][0]["max_position"]=1;error="checkpoint_cut_mismatch"
        add(cases,"F31-"+label,clone(suffix_s),rr,dict(error=dict(code=error)),
            operation="restore",extra=dict(checkpoint=cp))

    for field, invalid, code in [("price","-1","invalid_scalar"),
                                ("quantity","0","invalid_scalar"),
                                ("quantity","1"*129,"resource_limit"),
                                ("price","0.0000000000000000001","resource_limit")]:
        s,r=make();s["executions"][0][field]=invalid
        add(cases,"F34-"+field+"-"+str(len(invalid)),s,r,dict(error=dict(code=code)))
    s,r=make();r["limits"]["max_records"]=1
    add(cases,"F34-lowered-record-limit",s,r,dict(error=dict(code="resource_limit")))
    s,r=make();s["references"][0]["multiplier"]="0"
    add(cases,"F34-zero-multiplier",s,r,dict(error=dict(code="invalid_scalar")))
    s,r=make(outputs=["cross.share_equivalent_participation","cross.premium_turnover_participation"])
    add(cases,"F36-unqualified-producers",s,r,dict(unsupported={n:"equity_integration_unqualified" for n in r["output_ids"]},
        required_producer_ids=["EQ153","EQ158"]))
    s,r=make(outputs=["cross.lag_correlation"])
    add(cases,"F37-unqualified-correlation",s,r,dict(unsupported={"cross.lag_correlation":"equity_integration_unqualified"},
        required_producer_ids=["EQ153","EQ158"]))

    # Cursor-only expected-member invisibility is distinct from knowledge-only.
    e=[root("a",event=12),root("b",position=2,event=14,known=15,boundary=15,price="1")]
    s,r=make(e);r["cut_cursors"][0]["max_position"]=1
    add(cases,"F39-cursor-hidden-member",s,r,dict(unavailable={n:"incomplete_population" for n in r["output_ids"]},
        coverage=dict(population_complete=False,expected_count=None,observed_count=1,eligible_count=1,
                      signed_count=1,unknown_sign_count=0),evidence_operands={"premium":"200/1"},
        exclusions={"b":"future_known"},output_checkpoint=None))
    e=root()
    a=reference_for_execution(e,expiry=9,civil=10,strike="100",spot="90")
    s,r=make([e],[a],REFERENCE_OUTPUTS+["flow.premium","flow.trade_count","flow.contracts"])
    add(cases,"F41-negative-DTE-reference-only",s,r,dict(available={"flow.premium":"200/1","flow.trade_count":"1/1",
        "flow.contracts":"1/1","flow.dte_reference_coverage":"0/1","flow.short_dte_observed_lower_share":"0/1",
        "flow.otm_premium_share":"1/1"},unavailable={"flow.short_dte_premium_share":"missing_dte_reference"},
        undefined={"flow.short_dte_known_reference_share":"zero_denominator"},
        coverage=dict(eligible_count=1,dte_eligible_count=0,otm_eligible_count=1),exclusions={},
        quality_flags_include=["partial_dte_coverage"]))
    for label,boundary in (("invalid",11),("control",12)):
        e=root(boundary=boundary);a=definition();a["known_at_ns"]=12
        s,r=make([e],[a],["flow.premium"])
        expected = dict(error=dict(code="identity_mismatch",path="/snapshot/executions/0/reference_id")) if label=="invalid" else dict(available={"flow.premium":"200/1"},available_at_at_least=12)
        add(cases,"F42-definition-"+label,s,r,expected)

    # Metadata witnesses follow the independently reviewed frozen amendment,
    # independently of any implementation context builder.
    original = inherited[0]
    add(cases,"F43-observed-full-metadata",clone(original["snapshot"]),clone(original["request"]),
        clone(original["expected_projection"]),extra=dict(
            expected_metadata_predicates=dict(contract_hhi_numerator="980000/1",
                contract_hhi_denominator="1960000/1",hhi_operand_unit="group_currency_squared",
                observed_context_records="Original root execution then original root reference at that root position.")))
    e=root(position=3,event=15,price="2.5")
    q0=quote("q0",position=1,event=10);q1=quote("q1",position=2,event=12)
    s,r=make([e],quotes=[q0,q1],profile="option-quote-midpoint1")
    context=[ref.record_digest("flow_quote",q1),ref.record_digest("flow_reference",s["references"][0])]
    certificate=next(c for c in s["context_certificates"] if c["certificate_id"]=="ctx-a")
    expected_context=digest("option-flow-context1",[15,ref.record_digest("flow_policy",r["policy"]),
        context,ref.record_digest("flow_context_certificate",certificate)])
    add(cases,"F43-quote-minimal-context",s,r,dict(signs={"a":"buy"},
        sign_context_sha256={"a":expected_context}),extra=dict(
            expected_metadata_predicates=dict(context_record_sha256s=context,excluded_q0_from_context=True)))
    predecessor=root("e0",position=1,event=10,price="1")
    target=root("e1",position=2,event=15,price="2")
    r0=definition();r0["reference_id"]="ref-r0";predecessor["reference_id"]="ref-r0"
    r1=definition();r1["reference_id"]="ref-r1";target["reference_id"]="ref-r1"
    s,r=make([predecessor,target],[r0,r1],profile="option-tick1")
    context=[ref.record_digest("flow_execution",predecessor),ref.record_digest("flow_reference",r0),
             ref.record_digest("flow_reference",r1)]
    certificate=next(c for c in s["context_certificates"] if c["certificate_id"]=="ctx-e1")
    expected_context=digest("option-flow-context1",[15,ref.record_digest("flow_policy",r["policy"]),
        context,ref.record_digest("flow_context_certificate",certificate)])
    add(cases,"F43-tick-minimal-context",s,r,dict(signs={"e0":"unknown","e1":"buy"},
        sign_context_sha256={"e1":expected_context}),extra=dict(
            expected_metadata_predicates=dict(context_record_sha256s=context)))
    s,r=make([root("a",quantity="999",price="0",position=1),
               root("b",quantity="2",price="0",position=2,event=12)],
              [definition(multiplier="1")],["flow.contracts"])
    r["limits"]["max_integer_digits"]=3
    add(cases,"F44-semantic-contract-accumulator-overflow",s,r,
        dict(error=dict(code="resource_limit")),extra=dict(
            expected_metadata_predicates=dict(mathematical_contracts="1001/1",published_result_forbidden=True)))
    return cases


def construct():
    # Universal-newline UTF-8 source bytes equal canonical Git-LF blobs.
    source_root=Path(__file__).resolve().parents[2]
    scenario_source=source_root/"docs/r26/INDEPENDENT_FIXTURE_CASES.json"
    helper_source=Path(__file__).with_name("independent_reference.py")
    for source, expected in ((scenario_source,SCENARIOS_SHA256),(helper_source,REFERENCE_SOURCE_SHA256)):
        normalized=source.read_text(encoding="utf-8").encode("utf-8")
        if hashlib.sha256(normalized).hexdigest()!=expected:
            raise ValueError("Independent source pin mismatch: "+source.name)
    cases = projected_cases()
    for item in cases:
        if item["operation"] != "evaluate":
            continue
        rows = observed_full_rows(item)
        if rows is None:
            continue
        for output, literal in item["expected_projection"].get("available",{}).items():
            actual=next(row for row in rows if row["output_id"]==output)
            if actual["status"]!="available" or actual["value"]!=rational(literal):
                raise AssertionError("Independent reference contradicts hand literal: "+item["id"]+"/"+output)
        item["expected_results"] = rows
        item["expected_results_record_sha256"] = ref.record_digest("flow_results",rows)
        item["expected_results_wire"] = ref.envelope("flow_results",rows)
        item["full_result_goldens"] = True
        item["expected_projection_scope"] = "Complete independent rows AND retained literal hand projection; independent materializer review and runtime lease remain required."
    return dict(schema="r26-independent-materialization-tranche2",
                materializer_revision=2,
                source_scenarios_sha256=SCENARIOS_SHA256,
                source_hash_framing="UTF-8 universal-newline Git-LF blobs including final newline",
                reference_helper_source_sha256=REFERENCE_SOURCE_SHA256,
                helper_historical_tranche1_scenario_pin=ref.SOURCE_SCENARIOS_SHA256,
                helper_historical_pin_scope="Original five-scenario tranche1 source, not current44-definition identity",
                reviewed_contract_commit=REVIEWED_CONTRACT_COMMIT,
                frozen_contract_tree=FROZEN_CONTRACT_TREE,
                prior_merged_contract_commit=PRIOR_MERGED_CONTRACT_COMMIT,
                frozen_amendment_scenarios=FROZEN_AMENDMENT_SCENARIOS,
                normative_scenario_definitions=44,
                independence="Standard library plus reviewed independent_reference helper only; no production imports or observations.",
                cases=cases,
                nonmaterialized_integration_scenarios={
                    "F33":"Requires actual worker cancellation/transaction/readback/retry harness; no numerical proxy counts as coverage.",
                    "F35":"Full result identity parity requires independently constructed complete rows plus actual direct/worker/store execution.",
                    "F38":"Unsupported worker modes and original R25 artifact regression require their actual separate environments."},
                reserved_equity_limitations={
                    "F36":"Unsupported admission is materialized; 13/2 and7/10 future accepted-equity arithmetic remain reserved.",
                    "F37":"Unsupported admission is materialized; actual correlation producer and numeric contract remain gated."},
                arithmetic_primitive_witnesses=[
                    dict(id="F44-cross-cancel-multiply",max_integer_digits=3,operation="multiply",
                         operands=[rational("99/100"),rational("100/99")],expected=rational("1/1")),
                    dict(id="F44-denominator-gcd-add",max_integer_digits=3,operation="add",
                         operands=[rational("999/998"),rational("999/998")],expected=rational("999/499")),
                    dict(id="F44-opposite-sign-cancel",max_integer_digits=3,operation="add",
                         operands=[rational("999/998"),rational("-999/998")],expected=rational("0/1")),
                    dict(id="F44-true-reduced-overflow",max_integer_digits=3,operation="add",
                         operands=[rational("999/1"),rational("2/1")],expected_error="resource_limit")],
                arithmetic_primitive_scope="Literal primitive witnesses, not feature-transport cases or claimed production primitive execution.",
                runtime_claimed=False,
                full_rows_metadata_amendment_state="Frozen exact reviewed contract; independent materializer review and runtime lease still required.",
                full_result_goldens_complete=False)


if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("destination",type=Path)
    args=parser.parse_args()
    payload=construct()
    wire=ref.canonical(payload)+b"\n"
    args.destination.write_bytes(wire)
    print(json.dumps(dict(bytes=len(wire),sha256=hashlib.sha256(wire).hexdigest(),
                         invocations=len(payload["cases"]),full_result_goldens_complete=False)))
