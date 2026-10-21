"""Independent complete R26 result oracle over the unchanged RC2 inputs.

Only standard library and the two independent reference writers are imported.
No production code, tests, serialized production results or installed packages
are used to construct any expected value, sign, metadata field or digest.
This source requires independent review and a serialized runtime lease.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

import independent_reference as wire
import independent_reference_cases as prior

BASE_CONTRACT_COMMIT = "d19d84bbc6f9afbb2deb03b5aad768cb4cacf51f"
BASE_CONTRACT_TREE = "1b982b8004062ff6198ed461beccaffc5b508604"
CONTRACT_COMMIT = "388372c20a054aae273c20bffe862cbcbea042d3"
CLARIFICATION_RECEIPT = "https://github.com/atulsrivas1/equity-features/issues/534#issuecomment-6309740008"
DIAGNOSTIC_CLARIFICATION_COMMIT_PREFIX = "9c880a4"
DIAGNOSTIC_CLARIFICATION_RECEIPT = "https://github.com/atulsrivas1/equity-features/issues/534#issuecomment-6309764659"
PRIOR_WRITER_SHA256 = "ea253804415d1f597071a996c9412ff1fa88b07fc67af54fd21bc589e82c26b2"
REFERENCE_HELPER_SHA256 = "d4bdce4898fb76eff30be89e201e2fb5b53762462470cdbfaa01729182295ec1"
NORMATIVE_SHA256 = {
    "MATHEMATICS.md":"551b6a3bd5fc0c13f86fb89563e6c240481fb4432a4710170f59a9f84d9daf6a",
    "FLOW_CONTRACT.md":"5249b43bb70d57852a01e3f1faafb2ff0c78813b99f3a43b416fe26a09ab2b54",
    "COMPATIBILITY.json":"198cbba4e53c236b40bf26acc53185a2fab39f2bb4cb3ada3c5059e9e0a0c55b",
    "FEATURE_BINDINGS.json":"c599fef8bb9cf3dcc7358e248a55d1344afe07bcecd92a7442541802efdf9482",
    "INDEPENDENT_FIXTURE_CASES.json":"a0cdaaa6abc8441f3cf8ecb069fae2c89477979a7543e2cc96649f13dc4bfa1c",
    "FIXTURE_PROTOCOL.md":"8a4a4f32dd04dc93bd3c1df77582515a482253d88006dce8ab84cbf19cdc2a17"}
REFERENCE_REVIEW_STATE = "Source candidate; independent review and execution lease required."
UNKNOWN_CLASSIFICATION_DIAGNOSTICS = False

CLUSTER_PER_MEMBER = {
    "execution.cluster_premium", "execution.cluster_trade_count", "execution.cluster_contracts",
    "execution.cluster_span_ns", "execution.cluster_venue_count"}
ACTIVITY_METRICS = {
    "activity.contracts_median":"contracts", "activity.relative_volume":"contracts",
    "activity.trade_count_median":"trade_count", "activity.relative_trade_count":"trade_count",
    "activity.premium_median":"premium", "activity.premium_mad":"premium",
    "activity.premium_robust_z":"premium"}
OUTPUT_UNITS = {
    "flow.trade_count":"executions", "flow.contracts":"contracts", "flow.share_equivalent":"payoff_units",
    "flow.premium":"group_currency", "flow.buy_proxy_premium":"group_currency",
    "flow.sell_proxy_premium":"group_currency", "flow.unknown_premium":"group_currency",
    "flow.signed_execution_premium":"group_currency", "flow.right_positive_premium":"group_currency",
    "flow.right_negative_premium":"group_currency", "flow.net_directional_premium":"group_currency",
    "flow.call_premium":"group_currency", "flow.put_premium":"group_currency",
    "execution.cluster_premium":"group_currency", "execution.cluster_trade_count":"executions",
    "execution.cluster_contracts":"contracts", "execution.cluster_span_ns":"nanoseconds",
    "execution.cluster_venue_count":"venues", "activity.contracts_median":"contracts",
    "activity.trade_count_median":"executions", "activity.premium_median":"group_currency",
    "activity.premium_mad":"group_currency", "activity.premium_robust_z":"mad_z"}
BASE_UNITS = {
    "count":"executions", "contracts":"contracts", "share_equivalent":"payoff_units",
    "premium":"group_currency", "buy_premium":"group_currency", "sell_premium":"group_currency",
    "unknown_premium":"group_currency", "signed_premium":"group_currency",
    "call_premium":"group_currency", "put_premium":"group_currency"}


def verify_reference_sources():
    """Fail before construction if the admitted independent inputs changed."""
    receipt=[]
    for module,expected in ((wire,REFERENCE_HELPER_SHA256),(prior,PRIOR_WRITER_SHA256)):
        path=Path(module.__file__)
        normalized=path.read_text(encoding="utf-8").replace("\r\n","\n").replace("\r","\n").encode("utf-8")
        actual=hashlib.sha256(normalized).hexdigest()
        if actual!=expected:
            raise AssertionError("Independent reference source identity changed: "+path.name)
        receipt.append(dict(file=path.name,sha256=actual,normalization="UTF-8 LF; retain all other bytes"))
    docs=Path(__file__).resolve().parents[2]/"docs"/"r26"
    for name,expected in sorted(NORMATIVE_SHA256.items()):
        text=(docs/name).read_text(encoding="utf-8")
        normalized=text.replace("\r\n","\n").replace("\r","\n").encode("utf-8")
        actual=hashlib.sha256(normalized).hexdigest()
        if actual!=expected:
            raise AssertionError("Normative source identity changed: "+name)
        receipt.append(dict(file=name,sha256=actual,normalization="UTF-8 LF; retain all other bytes"))
    if prior.SCENARIOS_SHA256!=NORMATIVE_SHA256["INDEPENDENT_FIXTURE_CASES.json"]:
        raise AssertionError("Prior writer scenario identity does not match independently pinned normative scenario")
    return receipt


def q(value):
    if isinstance(value,dict):
        return Fraction(int(value["numerator"]),int(value["denominator"]))
    return Fraction(value)


def pair(value):
    value=q(value)
    return dict(numerator=str(value.numerator),denominator=str(value.denominator))


def rd(kind,value):
    return wire.record_digest(kind,value)


def sha_domain(domain,value):
    return hashlib.sha256(domain.encode()+b"\n"+wire.canonical(value)).hexdigest()


def median(values):
    values=sorted(values)
    size=len(values)
    if size%2:
        return values[size//2]
    return (values[size//2-1]+values[size//2])/2


def root_map(records,field):
    return {record[field]:record for record in records if record["kind"]=="new"}


def visible_view(records,field,knowledge,cursors):
    """Select revisions independently by certified publication position."""
    groups=defaultdict(list)
    for record in records:
        if record["known_at_ns"]<=knowledge and record["position"]<=cursors[record["stream_id"]]:
            groups[record[field]].append(record)
    return {identity:max(items,key=lambda record:record["position"]) for identity,items in groups.items()}


def matches(root,reference,group):
    return (root["contract_id"] in group["contract_ids"]
            and reference["underlying_id"]==group["underlying_id"]
            and reference["currency"]==group["currency"]
            and reference["action_basis_id"]==group["action_basis_id"]
            and (group["right"] is None or reference["right"]==group["right"])
            and (group["expiry_ordinal"] is None or reference["expiry_ordinal"]==group["expiry_ordinal"]))


def record_context(entries):
    """Distinct immutable records, anchored at minimum associated root position."""
    unique={}
    for position,kind,value in entries:
        identity=(kind,rd(kind,value))
        if identity not in unique or position<unique[identity][0]:
            unique[identity]=(position,kind,value)
    return sorted(unique.values(),key=lambda entry:(entry[0],entry[1],rd(entry[1],entry[2])))


def sign_one(snapshot,request,root,current,roots,refs,cursors,policy_sha):
    """Rebuild each target context independently at original A, never mutable K sweep."""
    A=root["signing_boundary_ns"]
    method=request["policy"]["signing_profile"]
    reference=refs[root["reference_id"]]
    witness=dict(execution_id=root["execution_id"],revision_id=current["revision_id"],
        sign="unknown",method=method,reason="observed_unknown",diagnostics=[],
        signing_boundary_ns=A,context_sha256="",context_certificate_id=None,
        quote_id=None,quote_revision_id=None,predecessor_execution_id=None,predecessor_revision_id=None)
    entries=[(root["position"],"flow_reference",reference)]
    admitted=[reference]
    chosen_certificate=None
    if method=="option-observed-side1":
        entries.append((root["position"],"flow_execution",root));admitted.append(root)
        if root["observed_side_semantics_id"] is None:
            witness["reason"]="observed_missing"
        elif root["observed_side_known_at_ns"]>A:
            witness["reason"]="observed_future"
        else:
            witness["sign"]=root["observed_side"]
            witness["reason"]={"buy":"observed_buy","sell":"observed_sell","unknown":"observed_unknown"}[root["observed_side"]]
    else:
        kind="quote_prefix" if method=="option-quote-midpoint1" else "execution_prefix"
        choices=[certificate for certificate in snapshot["context_certificates"]
            if certificate["kind"]==kind and certificate["contract_id"]==root["contract_id"]
            and certificate["session_id"]==root["session_id"] and certificate["stream_id"]==root["stream_id"]
            and certificate["through_position"]>=root["position"] and certificate["known_at_ns"]<=A]
        if choices:
            chosen_certificate=min(choices,key=lambda c:(c["through_position"],c["certificate_id"]))
            witness["context_certificate_id"]=chosen_certificate["certificate_id"]
            admitted.append(chosen_certificate)
        source=snapshot["quotes"] if kind=="quote_prefix" else snapshot["executions"]
        field="quote_id" if kind=="quote_prefix" else "execution_id"
        context_view=visible_view(source,field,A,cursors)
        complete=bool(chosen_certificate and chosen_certificate["complete"]
                      and all(identity in context_view for identity in chosen_certificate["expected_root_ids"]))
        if not complete:
            witness["reason"]="quote_missing" if kind=="quote_prefix" else "tick_seed_unavailable"
            witness["diagnostics"]=["incomplete_context"]
        elif kind=="quote_prefix":
            quote_roots=root_map(snapshot["quotes"],"quote_id")
            candidates=[(quote_roots[identity],record) for identity,record in context_view.items()
                if record["kind"]!="cancel" and record["contract_id"]==root["contract_id"]
                and record["stream_id"]==root["stream_id"]
                and quote_roots[identity]["position"]<root["position"]
                and quote_roots[identity]["event_ns"]<=root["event_ns"]]
            if not candidates:
                witness["reason"]="quote_missing"
            else:
                original,selected=max(candidates,key=lambda p:p[0]["position"])
                witness.update(quote_id=selected["quote_id"],quote_revision_id=selected["revision_id"])
                entries.append((original["position"],"flow_quote",selected));admitted.append(selected)
                age=root["event_ns"]-original["event_ns"]
                reasons=[]
                if selected["condition"]!="regular":
                    reasons.append("quote_missing");witness["diagnostics"].append("excluded_quote")
                if age>request["policy"]["max_quote_age_ns"]:reasons.append("quote_stale")
                if selected["bid"] is None or selected["ask"] is None:reasons.append("quote_one_sided")
                else:
                    bid,ask=q(selected["bid"]),q(selected["ask"])
                    if bid==ask:reasons.append("quote_locked")
                    elif bid>ask:reasons.append("quote_crossed")
                if reasons:
                    precedence=["quote_missing","quote_future","quote_order_unknown","quote_stale",
                                "quote_one_sided","quote_locked","quote_crossed","quote_midpoint"]
                    witness["reason"]=min(reasons,key=precedence.index)
                    # All discovered unknown causes, including the primary,
                    # are retained. Normal available sign reasons are not
                    # failures and do not enter witness diagnostics.
                    witness["diagnostics"].extend(reasons)
                else:
                    price=q(current["price"]); midpoint=(bid+ask)/2
                    witness["sign"]="buy" if price>midpoint else "sell" if price<midpoint else "unknown"
                    witness["reason"]="quote_above_midpoint" if price>midpoint else "quote_below_midpoint" if price<midpoint else "quote_midpoint"
                    if price<bid or price>ask:witness["diagnostics"].append("outside_spread")
        else:
            predecessors=[]
            for identity,selected in context_view.items():
                original=roots[identity]
                if (selected["kind"]!="cancel" and selected["condition"]=="regular"
                    and original["contract_id"]==root["contract_id"] and original["session_id"]==root["session_id"]
                    and original["stream_id"]==root["stream_id"] and original["position"]<root["position"]):
                    predecessors.append((original,selected))
            predecessors.sort(key=lambda p:p[0]["position"])
            last_price=None;last_sign="unknown"
            for original,selected in predecessors:
                selected_price=q(selected["price"])
                if last_price is not None:
                    if selected_price>last_price:last_sign="buy"
                    elif selected_price<last_price:last_sign="sell"
                last_price=selected_price
                entries.extend([(original["position"],"flow_execution",selected),
                    (original["position"],"flow_reference",refs[original["reference_id"]])])
                admitted.extend([selected,refs[original["reference_id"]]])
            price=q(current["price"])
            if last_price is None:witness["reason"]="tick_initial_unknown"
            elif price>last_price:witness.update(sign="buy",reason="tick_up")
            elif price<last_price:witness.update(sign="sell",reason="tick_down")
            elif last_sign!="unknown":witness.update(sign=last_sign,reason="tick_carried")
            else:witness["reason"]="tick_initial_unknown"
            if predecessors:
                selected=predecessors[-1][1]
                witness.update(predecessor_execution_id=selected["execution_id"],
                               predecessor_revision_id=selected["revision_id"])
    ordered=record_context(entries)
    if witness["sign"]=="unknown":
        classification=witness["reason"] in {"observed_unknown","quote_midpoint","tick_initial_unknown"}
        if classification and UNKNOWN_CLASSIFICATION_DIAGNOSTICS is None:
            raise RuntimeError("Coordinator unknown-classification diagnostic interpretation is not frozen")
        if not classification or UNKNOWN_CLASSIFICATION_DIAGNOSTICS:
            witness["diagnostics"].append(witness["reason"])
    witness["diagnostics"]=sorted(set(witness["diagnostics"]))
    witness["context_sha256"]=sha_domain("option-flow-context1",[A,policy_sha,
        [rd(kind,value) for position,kind,value in ordered],
        rd("flow_context_certificate",chosen_certificate) if chosen_certificate else None])
    return witness,chosen_certificate,admitted


def reference_membership(root,reference,policy):
    """Independent civil/spot membership and all actual closed failure causes."""
    causes=[]; dte=False;short=False;otm=False;otm_member=False;known=[]
    A=root["signing_boundary_ns"]
    if reference["civil_ordinal"] is None:
        causes.append("missing_dte_reference")
    elif reference["civil_known_at_ns"]>A:
        causes.extend(["missing_dte_reference","future_reference"])
    else:
        days=reference["expiry_ordinal"]-reference["civil_ordinal"]
        if days<0:causes.append("missing_dte_reference")
        else:
            dte=True;short=days<=policy["short_dte_max_days"]
            known.append(reference["civil_known_at_ns"])
    if reference["spot"] is None:
        causes.append("missing_spot_reference")
    elif reference["spot_known_at_ns"]>A or reference["spot_event_ns"]>root["event_ns"]:
        causes.extend(["missing_spot_reference","future_reference"])
    elif reference["spot_stream_id"]!=root["stream_id"] or reference["spot_position"]>=root["position"]:
        causes.append("missing_spot_reference")
    elif root["event_ns"]-reference["spot_event_ns"]>policy["max_spot_age_ns"]:
        causes.extend(["missing_spot_reference","stale_reference"])
    else:
        otm_member=True
        otm=(q(reference["strike"])>q(reference["spot"]) if reference["right"]=="call"
             else q(reference["strike"])<q(reference["spot"]))
        known.append(reference["spot_known_at_ns"])
    return dict(dte=dte,short=short,otm_member=otm_member,otm=otm,
                diagnostics=sorted(set(causes)),admitted_knowledge=known)


def cluster_partition(active,roots,witnesses,policy_sha,policy):
    """Maximal disjoint adjacent-gap runs, with unknown rows as hard breaks."""
    by_id={w["execution_id"]:w for w in witnesses}
    partitions=defaultdict(list)
    for current in active:
        original=roots[current["execution_id"]]
        partitions[(original["contract_id"],original["session_id"],original["stream_id"])].append(current)
    runs=[]
    for key,members in sorted(partitions.items()):
        members.sort(key=lambda e:roots[e["execution_id"]]["position"])
        run=[];previous=None
        for current in members:
            original=roots[current["execution_id"]]; sign=by_id[current["execution_id"]]
            known=sign["sign"]!="unknown" and sign["quote_id"] is not None
            compatible=bool(run and known and previous and
                sign["quote_id"]==previous[1]["quote_id"] and sign["quote_revision_id"]==previous[1]["quote_revision_id"]
                and sign["sign"]==previous[1]["sign"]
                and original["event_ns"]-previous[0]["event_ns"]<=policy["cluster_max_adjacent_gap_ns"])
            if run and not compatible:runs.append(run);run=[]
            if known:run.append(current)
            previous=(original,sign)
        if run:runs.append(run)
    result=[]
    for run in runs:
        first=roots[run[0]["execution_id"]];last=roots[run[-1]["execution_id"]]
        sign=by_id[run[0]["execution_id"]]
        ids=[e["execution_id"] for e in run];revisions=[e["revision_id"] for e in run]
        identity=sha_domain("option-flow-cluster1",["option-quote-cluster1",first["contract_id"],first["session_id"],
            policy_sha,sign["quote_id"],sign["quote_revision_id"],sign["sign"],ids,revisions])
        result.append((dict(cluster_id=identity,profile="option-quote-cluster1",contract_id=first["contract_id"],
            session_id=first["session_id"],quote_id=sign["quote_id"],quote_revision_id=sign["quote_revision_id"],
            sign=sign["sign"],execution_ids=ids,execution_revision_ids=revisions,
            first_event_ns=first["event_ns"],last_event_ns=last["event_ns"],
            venue_ids=sorted({e["venue_id"] for e in run if e["venue_id"] is not None}),
            unknown_venue_count=sum(e["venue_id"] is None for e in run)),run))
    return result


def baseline_for(snapshot,request,group,output):
    """Metric-specific prior-slot admission and exact descriptive statistics."""
    metric=ACTIVITY_METRICS[output]
    target=next((target for target in request["baseline_targets"] if target["group_id"]==group["group_id"]),None)
    slots=target["slot_ids"] if target else []
    mapping={b["slot_id"]:b for b in snapshot["baselines"] if b["group_id"]==group["group_id"]}
    present=[mapping[slot] for slot in slots if slot in mapping]
    causes=[]
    if not slots:causes.append("missing_baseline")
    if any(slot not in mapping for slot in slots):causes.append("incomplete_baseline")
    if any(not b["complete"] or b[metric] is None for b in present):causes.append("incomplete_baseline")
    if any(b["known_at_ns"]>request["knowledge_cutoff_ns"] for b in present):causes.append("future_reference")
    if not causes and len(present)<request["policy"]["minimum_matched_prior_windows"]:causes.append("insufficient_history")
    order=["missing_baseline","incomplete_baseline","future_reference","stale_reference","insufficient_history"]
    reason=min(causes,key=order.index) if causes else None
    admitted=[b for b in present if b["known_at_ns"]<=request["knowledge_cutoff_ns"]]
    counted=[b for b in admitted if b["complete"] and b[metric] is not None]
    result=dict(slots=slots,present=present,causes=sorted(set(causes)),reason=reason,metric=metric,
                median=None,mad=None,admitted_knowledge=[b["known_at_ns"] for b in admitted],
                baseline_count=len(counted))
    if reason is None:
        values=[q(b[metric]) for b in present]
        result["median"]=median(values)
        if output in ("activity.premium_mad","activity.premium_robust_z"):
            result["mad"]=median([abs(v-result["median"]) for v in values])
    return result


def complete_rows(snapshot,request,*,input_checkpoint_sha256=None):
    """Original dictionary-based independent reference; valid fixture inputs only."""
    refs={r["reference_id"]:r for r in snapshot["references"]}
    roots=root_map(snapshot["executions"],"execution_id")
    cursors={c["stream_id"]:c["max_position"] for c in request["cut_cursors"]}
    K=request["knowledge_cutoff_ns"];policy=request["policy"]
    policy_sha=rd("flow_policy",policy)
    current_view=visible_view(snapshot["executions"],"execution_id",K,cursors)
    snapshot_sha=rd("flow_snapshot",snapshot);request_sha=rd("flow_request",request)
    rows=[]
    for group in [g for g in snapshot["groups"] if g["group_id"] in request["group_ids"]]:
        group_roots={identity:r for identity,r in roots.items() if matches(r,refs[r["reference_id"]],group)}
        active=[];exclusions=[]
        for identity,original in sorted(group_roots.items()):
            selected=current_view.get(identity)
            if selected is None:reason="future_known"
            elif selected["kind"]=="cancel":reason="cancelled"
            elif not request["window_start_ns"]<=original["event_ns"]<request["window_end_ns"]:reason="outside_window"
            elif selected["condition"]!="regular":reason="excluded"
            else:
                active.append(selected);continue
            exclusions.append(dict(execution_id=identity,revision_id=(selected or original)["revision_id"],reason=reason))
        active.sort(key=lambda e:e["execution_id"])
        population=next((p for p in snapshot["populations"] if p["group_id"]==group["group_id"]
            and p["window_start_ns"]==request["window_start_ns"] and p["window_end_ns"]==request["window_end_ns"]),None)
        complete=bool(population and population["complete"] and population["known_at_ns"]<=K
            and all(identity in current_view for identity in population["expected_execution_ids"]))
        witnesses=[];certificates={};admitted=[]
        for selected in active:
            original=roots[selected["execution_id"]]
            witness,certificate,context_admitted=sign_one(snapshot,request,original,selected,roots,refs,cursors,policy_sha)
            witnesses.append(witness);admitted.extend(context_admitted+[selected,refs[original["reference_id"]]])
            if certificate:certificates[certificate["certificate_id"]]=certificate
        signs={w["execution_id"]:w for w in witnesses}
        reference_info={e["execution_id"]:reference_membership(roots[e["execution_id"]],refs[roots[e["execution_id"]]["reference_id"]],policy) for e in active}
        premiums={e["execution_id"]:q(e["price"])*q(e["quantity"])*q(refs[roots[e["execution_id"]]["reference_id"]]["multiplier"]) for e in active}
        total=sum(premiums.values(),Fraction()); count=len(active)
        contracts=sum((q(e["quantity"]) for e in active),Fraction())
        share=sum((q(e["quantity"])*q(refs[roots[e["execution_id"]]["reference_id"]]["multiplier"]) for e in active),Fraction())
        buy=sum((premiums[k] for k in premiums if signs[k]["sign"]=="buy"),Fraction())
        sell=sum((premiums[k] for k in premiums if signs[k]["sign"]=="sell"),Fraction())
        unknown=total-buy-sell
        call=sum((premiums[e["execution_id"]] for e in active if refs[roots[e["execution_id"]]["reference_id"]]["right"]=="call"),Fraction())
        put=total-call
        positive=sum((premiums[e["execution_id"]] for e in active if
            (refs[roots[e["execution_id"]]["reference_id"]]["right"],signs[e["execution_id"]]["sign"])
            in (("call","buy"),("put","sell"))),Fraction())
        negative=total-unknown-positive
        signed=sum(w["sign"]!="unknown" for w in witnesses)
        coverage=dict(population_id=population["population_id"] if population else None,
            population_complete=complete,expected_count=count if complete else None,
            observed_count=count,eligible_count=count,signed_count=signed,unknown_sign_count=count-signed,
            dte_eligible_count=sum(v["dte"] for v in reference_info.values()),
            otm_eligible_count=sum(v["otm_member"] for v in reference_info.values()))
        flags=[]
        if signed<count:flags.append("partial_sign_coverage")
        if coverage["dte_eligible_count"]<count:flags.append("partial_dte_coverage")
        if coverage["otm_eligible_count"]<count:flags.append("partial_otm_coverage")
        if policy["signing_profile"]!="option-observed-side1":flags.append("proxy_direction")
        if complete and not count:flags.append("complete_empty")
        relevant_execution=[e for e in snapshot["executions"] if e["contract_id"] in group["contract_ids"]]
        relevant_streams={roots[e["execution_id"]]["stream_id"] for e in relevant_execution}
        relevant_quotes=[item for item in snapshot["quotes"] if item["stream_id"] in relevant_streams]
        if any(item["kind"]!="new" and item["known_at_ns"]<=K and item["position"]<=cursors[item["stream_id"]]
               for item in relevant_execution+relevant_quotes):flags.append("corrected_history")
        partitions={"contract":{c:Fraction() for c in group["contract_ids"]},
            "expiry":{str(r["expiry_ordinal"]):Fraction() for r in refs.values() if r["contract_id"] in group["contract_ids"]}}
        for e in active:
            original=roots[e["execution_id"]]
            partitions["contract"][original["contract_id"]]+=premiums[e["execution_id"]]
            partitions["expiry"][str(refs[original["reference_id"]]["expiry_ordinal"])]+=premiums[e["execution_id"]]
        base=dict(count=Fraction(count),contracts=contracts,share_equivalent=share,premium=total,
            buy_premium=buy,sell_premium=sell,unknown_premium=unknown,signed_premium=buy-sell,call_premium=call,put_premium=put)
        scalar={"flow.trade_count":Fraction(count),"flow.contracts":contracts,"flow.share_equivalent":share,
            "flow.premium":total,"flow.buy_proxy_premium":buy,"flow.sell_proxy_premium":sell,
            "flow.unknown_premium":unknown,"flow.signed_execution_premium":buy-sell,
            "flow.right_positive_premium":positive,"flow.right_negative_premium":negative,
            "flow.net_directional_premium":positive-negative,"flow.call_premium":call,"flow.put_premium":put}
        ratio={"flow.known_sign_imbalance":(buy-sell,buy+sell,"group_currency"),
            "flow.total_premium_imbalance":(buy-sell,total,"group_currency"),"flow.unknown_premium_share":(unknown,total,"group_currency"),
            "flow.sign_event_coverage":(Fraction(signed),Fraction(count),"executions"),
            "flow.sign_premium_coverage":(buy+sell,total,"group_currency"),"flow.put_call_premium_ratio":(put,call,"group_currency")}
        for kind,weights in partitions.items():
            ratio["flow."+kind+"_hhi"]=(sum((v*v for v in weights.values()),Fraction()),total*total,"group_currency_squared")
            ratio["flow."+kind+"_top_share"]=(max(weights.values(),default=Fraction()),total,"group_currency")
        known_dte=sum((premiums[k] for k in premiums if reference_info[k]["dte"]),Fraction())
        short=sum((premiums[k] for k in premiums if reference_info[k]["short"]),Fraction())
        known_otm=sum((premiums[k] for k in premiums if reference_info[k]["otm_member"]),Fraction())
        otm=sum((premiums[k] for k in premiums if reference_info[k]["otm"]),Fraction())
        ratio.update({"flow.dte_reference_coverage":(known_dte,total,"group_currency"),
            "flow.short_dte_known_reference_share":(short,known_dte,"group_currency"),
            "flow.short_dte_observed_lower_share":(short,total,"group_currency"),
            "flow.short_dte_premium_share":(short,total,"group_currency"),
            "flow.otm_reference_coverage":(known_otm,total,"group_currency"),
            "flow.otm_known_reference_share":(otm,known_otm,"group_currency"),
            "flow.otm_observed_lower_share":(otm,total,"group_currency"),
            "flow.otm_premium_share":(otm,total,"group_currency")})
        needs_clusters=any(output.startswith("execution.cluster") for output in request["output_ids"])
        clusters=cluster_partition(active,roots,witnesses,policy_sha,policy) if needs_clusters and policy["signing_profile"]=="option-quote-midpoint1" else []
        clustered=sum((sum((premiums[e["execution_id"]] for e in members),Fraction()) for cluster,members in clusters),Fraction())
        ratio["execution.cluster_coverage"]=(clustered,total,"group_currency")
        dependency=[("flow_execution",e) for e in relevant_execution]+[("flow_quote",e) for e in relevant_quotes]
        ref_ids={roots[e["execution_id"]]["reference_id"] for e in relevant_execution}
        ref_ids.update(e["reference_id"] for e in current_view.values() if e["execution_id"] in group_roots)
        dependency.extend(("flow_reference",refs[identity]) for identity in sorted(ref_ids))
        dependency.extend(("flow_context_certificate",c) for c in certificates.values())
        dependency.append(("flow_group",group))
        if population:dependency.append(("flow_population",population))
        availability=[0]+[record["known_at_ns"] for record in admitted if record["known_at_ns"]<=K]
        if policy["signing_profile"]=="option-observed-side1":
            availability.extend(roots[e["execution_id"]]["observed_side_known_at_ns"] for e in active
                if roots[e["execution_id"]]["observed_side_known_at_ns"] is not None
                and roots[e["execution_id"]]["observed_side_known_at_ns"]<=roots[e["execution_id"]]["signing_boundary_ns"])
        # Cancellation/exclusion establishes selected-window membership and
        # contributes to economic/status knowledge even without a positive
        # premium. Future and outside-window roots do not advance this clock.
        for identity,selected in current_view.items():
            if identity in group_roots and request["window_start_ns"]<=roots[identity]["event_ns"]<request["window_end_ns"]:
                availability.extend([selected["known_at_ns"],refs[roots[identity]["reference_id"]]["known_at_ns"]])
        if population and population["known_at_ns"]<=K:availability.append(population["known_at_ns"])
        for info in reference_info.values():availability.extend(info["admitted_knowledge"])
        all_reference_diagnostics={cause for info in reference_info.values() for cause in info["diagnostics"]}

        for output in request["output_ids"]:
            per_cluster=output in CLUSTER_PER_MEMBER
            cluster_supported=policy["signing_profile"]=="option-quote-midpoint1"
            iteration=clusters if per_cluster and cluster_supported and complete else [(None,[])]
            for cluster,members in iteration:
                operands=copy.deepcopy(base);units=copy.deepcopy(BASE_UNITS)
                row_flags=list(flags); row_dependency=list(dependency); row_availability=list(availability)
                diagnostics=set(all_reference_diagnostics)
                status="available";reason="ok";value=None;numerator=None;denominator=None
                baseline_ids=[];baseline_slots=[];baseline_hashes=[];required=[];ties=[]
                if output in ratio:
                    numerator,denominator,dim=ratio[output]
                    operands.update(numerator=numerator,denominator=denominator)
                    units.update(numerator=dim,denominator=dim)
                    value=numerator/denominator if denominator else None
                    if denominator==0:status,reason="undefined","zero_denominator"
                elif output in scalar:value=scalar[output]
                if output.endswith("_top_share") and total:
                    kind="contract" if output=="flow.contract_top_share" else "expiry"
                    ties=sorted(identity for identity,weight in partitions[kind].items() if weight==max(partitions[kind].values()))
                if output in prior.REFERENCE_OUTPUTS:
                    is_dte="dte" in output
                    operands.update(known_reference_premium=known_dte if is_dte else known_otm,
                                    qualified_premium=short if is_dte else otm)
                    units.update(known_reference_premium="group_currency",qualified_premium="group_currency")
                    if output=="flow.short_dte_premium_share" and coverage["dte_eligible_count"]<count:
                        status,reason,value="unavailable","missing_dte_reference",None
                    if output=="flow.otm_premium_share" and coverage["otm_eligible_count"]<count:
                        status,reason,value="unavailable","missing_spot_reference",None
                if output in ACTIVITY_METRICS:
                    baseline=baseline_for(snapshot,request,group,output)
                    baseline_slots=baseline["slots"]
                    baseline_ids=[b["baseline_id"] for b in baseline["present"]]
                    baseline_hashes=[rd("flow_baseline",b) for b in baseline["present"]]
                    row_dependency.extend(("flow_baseline",b) for b in baseline["present"])
                    row_availability.extend(baseline["admitted_knowledge"])
                    diagnostics.update(baseline["causes"])
                    if baseline["present"]:row_flags.append("supplied_baseline")
                    metric=baseline["metric"]
                    dim={"contracts":"contracts","trade_count":"executions","premium":"group_currency"}[metric]
                    current={"contracts":contracts,"trade_count":Fraction(count),"premium":total}[metric]
                    operands["baseline_count"]=Fraction(baseline["baseline_count"])
                    units["baseline_count"]="executions"
                    if output in ("activity.relative_volume","activity.relative_trade_count","activity.premium_robust_z"):
                        operands["current"]=current;units["current"]=dim
                    if baseline["reason"]:
                        status,reason,value="unavailable",baseline["reason"],None
                    else:
                        med=baseline["median"]
                        operands["median"]=med;units["median"]=dim
                        if output.endswith("_median"):value=med
                        elif output=="activity.premium_mad":
                            value=baseline["mad"];operands["mad"]=value;units["mad"]=dim
                        elif output=="activity.premium_robust_z":
                            mad=baseline["mad"]
                            operands.update(mad=mad,mad_scale=Fraction(7413,5000))
                            units.update(mad=dim,mad_scale="ratio")
                            numerator,denominator=current-med,Fraction(7413,5000)*mad
                            operands.update(numerator=numerator,denominator=denominator)
                            units.update(numerator=dim,denominator=dim)
                            if mad==0:status,reason,value="undefined","zero_mad",None
                            else:value=numerator/denominator
                        else:
                            numerator,denominator=current,med
                            operands.update(numerator=numerator,denominator=denominator)
                            units.update(numerator=dim,denominator=dim)
                            if med==0:status,reason,value="undefined","zero_denominator",None
                            else:value=current/med
                if per_cluster and cluster is not None:
                    cluster_premium=sum((premiums[e["execution_id"]] for e in members),Fraction())
                    cluster_contracts=sum((q(e["quantity"]) for e in members),Fraction())
                    cluster_values={"execution.cluster_premium":cluster_premium,
                        "execution.cluster_trade_count":Fraction(len(members)),"execution.cluster_contracts":cluster_contracts,
                        "execution.cluster_span_ns":Fraction(cluster["last_event_ns"]-cluster["first_event_ns"]),
                        "execution.cluster_venue_count":Fraction(len(cluster["venue_ids"]))}
                    value=cluster_values[output]
                    operands.update(cluster_premium=cluster_premium,cluster_contracts=cluster_contracts,
                        cluster_count=Fraction(len(members)),cluster_span=cluster_values["execution.cluster_span_ns"],
                        known_venue_count=Fraction(len(cluster["venue_ids"])),unknown_venue_count=Fraction(cluster["unknown_venue_count"]))
                    units.update(cluster_premium="group_currency",cluster_contracts="contracts",cluster_count="executions",
                                 cluster_span="nanoseconds",known_venue_count="venues",unknown_venue_count="venues")
                    if output=="execution.cluster_venue_count" and cluster["unknown_venue_count"]:
                        status,reason,value="unavailable","missing_venue_reference",None
                if output.startswith("cross."):
                    status,reason,value="unsupported","equity_integration_unqualified",None
                    numerator=denominator=None;required=["EQ153","EQ158"]
                elif output.startswith("execution.cluster") and not cluster_supported:
                    status,reason,value="unsupported","unsupported_profile",None
                    numerator=denominator=None
                    for name in ("numerator","denominator"):
                        operands.pop(name,None);units.pop(name,None)
                    cluster=None
                elif not complete:
                    status,reason,value="unavailable","incomplete_population",None
                    cluster=None
                if reason!="ok":diagnostics.add(reason)
                diagnostics.update(row_flags)
                for witness in witnesses:
                    diagnostics.add(witness["reason"]);diagnostics.update(witness["diagnostics"])
                evidence=dict(active_execution_ids=[e["execution_id"] for e in active],
                    active_revision_ids=[e["revision_id"] for e in active],exclusions=copy.deepcopy(exclusions),
                    operands=[dict(name=name,value=pair(operands[name]),unit=units[name]) for name in sorted(operands)],
                    partition_weights=[dict(partition_kind=kind,partition_id=identity,premium=pair(weight))
                        for kind in sorted(partitions) for identity,weight in sorted(partitions[kind].items())],
                    tied_top_ids=ties,cluster=copy.deepcopy(cluster),baseline_slot_ids=baseline_slots,
                    baseline_record_sha256s=baseline_hashes,required_producer_ids=required,diagnostics=sorted(diagnostics))
                rows.append(dict(schema_version="option-flow-result1",group_id=group["group_id"],output_id=output,
                    cluster_id=cluster["cluster_id"] if cluster else None,window_start_ns=request["window_start_ns"],
                    window_end_ns=request["window_end_ns"],knowledge_cutoff_ns=K,available_at_ns=max(row_availability),
                    temporal_profile="option-origin-context1",currency=group["currency"],action_basis_id=group["action_basis_id"],
                    origin="computed",value=pair(value) if value is not None else None,unit=OUTPUT_UNITS.get(output,"ratio"),
                    status=status,reason=reason,quality_flags=sorted(set(row_flags)),coverage=copy.deepcopy(coverage),
                    sign_witnesses=copy.deepcopy(witnesses),evidence=evidence,numerator=pair(numerator) if numerator is not None else None,
                    denominator=pair(denominator) if denominator is not None else None,baseline_ids=baseline_ids,
                    dependency_binding_ids=sorted({record["input_binding_id"] for kind,record in row_dependency if "input_binding_id" in record}),
                    dependency_record_sha256s=sorted({rd(kind,record) for kind,record in row_dependency}),
                    policy_sha256=policy_sha,request_sha256=request_sha,snapshot_sha256=snapshot_sha,
                    checkpoint_sha256=input_checkpoint_sha256,formula_version="option-flow-formulas1",
                    contracts_package_version="0.1.0a1",calculation_package_version="0.1.0a1"))
    return sorted(rows,key=lambda row:(row["group_id"],row["output_id"],row["cluster_id"] or ""))


def merge_checkpoint(checkpoint,suffix):
    merged=copy.deepcopy(checkpoint["history"])
    fields={"bindings":("binding_id",),"references":("reference_id",),
            "executions":("execution_id","revision_id"),"quotes":("quote_id","revision_id"),
            "groups":("group_id",),"populations":("population_id",),
            "context_certificates":("certificate_id",),"baselines":("baseline_id",),"cursors":("stream_id",)}
    for family,key_fields in fields.items():
        index={tuple(record[k] for k in key_fields):record for record in merged[family]}
        for record in suffix[family]:
            identity=tuple(record[k] for k in key_fields)
            if family!="cursors" and identity in index and index[identity]!=record:
                raise AssertionError("Independent valid restore input has conflicting immutable identity")
            index[identity]=copy.deepcopy(record)
        merged[family]=list(index.values())
    return prior.canonical_order(merged)


def assert_hand(rows,projection):
    """Check independent full reconstruction against original literal witnesses."""
    scalar={row["output_id"]:row for row in rows if row["cluster_id"] is None}
    for state in ("available","undefined","unavailable","unsupported"):
        for output,expected in projection.get(state,{}).items():
            row=scalar[output]
            if row["status"]!=state:
                raise AssertionError((output,"hand status",state,row["status"]))
            if state=="available":
                if q(row["value"])!=q(expected):raise AssertionError((output,"hand value",expected,row["value"]))
            elif row["reason"]!=expected:raise AssertionError((output,"hand reason",expected,row["reason"]))
    if rows:
        for key,value in projection.get("coverage",{}).items():
            if rows[0]["coverage"][key]!=value:raise AssertionError(("hand coverage",key,value,rows[0]["coverage"][key]))
        witnesses={w["execution_id"]:w for w in rows[0]["sign_witnesses"]}
        for key,field in (("signs","sign"),("sign_reasons","reason"),("sign_context_sha256","context_sha256")):
            for identity,value in projection.get(key,{}).items():
                if witnesses[identity][field]!=value:raise AssertionError((key,identity,value,witnesses[identity][field]))
        for identity,values in projection.get("sign_diagnostics_include",{}).items():
            if not set(values)<=set(witnesses[identity]["diagnostics"]):raise AssertionError(("hand sign diagnostics",identity,values))
        if "active_execution_ids" in projection and rows[0]["evidence"]["active_execution_ids"]!=projection["active_execution_ids"]:
            raise AssertionError("Hand active membership mismatch")
        if "exclusions" in projection:
            actual={e["execution_id"]:e["reason"] for e in rows[0]["evidence"]["exclusions"]}
            if actual!=projection["exclusions"]:raise AssertionError(("Hand exclusions",actual,projection["exclusions"]))
        for name,expected in projection.get("evidence_operands",{}).items():
            actual=next(operand["value"] for operand in rows[0]["evidence"]["operands"] if operand["name"]==name)
            if q(actual)!=q(expected):raise AssertionError(("Hand operand",name,actual,expected))
    for output,values in projection.get("cluster_values",{}).items():
        chosen=sorted([row for row in rows if row["output_id"]==output],
            key=lambda row:row["evidence"]["cluster"]["first_event_ns"])
        if [q(row["value"]) for row in chosen]!=[q(value) for value in values]:raise AssertionError(("Hand cluster values",output))
    for output,values in projection.get("cluster_statuses",{}).items():
        chosen=sorted([row for row in rows if row["output_id"]==output],key=lambda row:row["evidence"]["cluster"]["first_event_ns"])
        if [[row["status"],row["reason"]] for row in chosen]!=values:raise AssertionError(("Hand cluster status",output))
    if "cluster_members" in projection:
        unique={row["cluster_id"]:row["evidence"]["cluster"] for row in rows if row["cluster_id"] is not None}
        chosen=sorted(unique.values(),key=lambda cluster:cluster["first_event_ns"])
        if [cluster["execution_ids"] for cluster in chosen]!=projection["cluster_members"]:raise AssertionError("Hand cluster membership mismatch")


def baseline_status_controls():
    """Original concrete controls for admitted count versus status knowledge.

    These are additional independent inputs, not alterations of any RC2 fact.
    Clarification is reviewed/frozen at CONTRACT_COMMIT; this reference still
    needs its own independent review and serialized generation lease.
    """
    cases=[]
    for label in ("absent","known-null","known-incomplete"):
        snapshot,request=prior.make([prior.root(event=10,price="1")],
            [prior.definition(multiplier="1")],["activity.relative_volume"],end=11,cutoff=20)
        request["policy"].update(horizon_id="unit-window1",minimum_matched_prior_windows=3)
        request["baseline_targets"]=[dict(group_id="all",slot_ids=["slot1","slot2","slot3"])]
        policy_sha=rd("flow_policy",request["policy"])
        for number,known in ((1,5),(3,30)):
            snapshot["baselines"].append(dict(baseline_id="control-baseline"+str(number),group_id="all",
                slot_id="slot"+str(number),session_ordinal=number,horizon_id="unit-window1",
                window_start_ns=number,window_end_ns=number+1,known_at_ns=known,policy_sha256=policy_sha,
                population_sha256=sha_domain("independent-control-population1",[number,"2"]),
                currency="XTS",action_basis_id="synthetic-unadjusted1",contracts=pair(2),trade_count=pair(2),premium=pair(2),
                member_record_sha256s=[sha_domain("independent-control-history1",[number,"2"])],
                complete=True,input_binding_id="synthetic1"))
        if label!="absent":
            baseline=copy.deepcopy(snapshot["baselines"][0])
            baseline.update(baseline_id="control-baseline2",slot_id="slot2",session_ordinal=2,
                window_start_ns=2,window_end_ns=3,known_at_ns=7,
                population_sha256=sha_domain("independent-control-population1",[2,"2"]),
                member_record_sha256s=[sha_domain("independent-control-history1",[2,"2"])])
            if label=="known-null":baseline["contracts"]=None
            else:baseline["complete"]=False
            snapshot["baselines"].append(baseline)
        prior.canonical_order(snapshot)
        cases.append(dict(id="baseline-status-"+label,snapshot=snapshot,request=request,
            expected_projection=dict(unavailable={"activity.relative_volume":"incomplete_baseline"}),
            expected_admitted_baseline_count=1,
            expected_baseline_status_clocks=[5] if label=="absent" else [5,7],
            expected_available_at_ns=10))
    return cases


def observed_side_clock_controls():
    """Literal distinction between root availability and separate side clock."""
    cases=[]
    for label,boundary,side,availability in (("admitted",15,"buy",14),("future-at-origin",12,"unknown",10)):
        execution=prior.root(event=10,known=10,boundary=boundary)
        execution["observed_side_known_at_ns"]=14
        snapshot,request=prior.make([execution],outputs=["flow.premium","flow.signed_execution_premium","flow.unknown_premium"])
        cases.append(dict(id="observed-side-clock-"+label,snapshot=snapshot,request=request,
            expected_projection=dict(available={"flow.premium":"200/1",
                "flow.signed_execution_premium":"200/1" if side=="buy" else "0/1",
                "flow.unknown_premium":"0/1" if side=="buy" else "200/1"},
                signs={"a":side},sign_reasons={"a":"observed_buy" if side=="buy" else "observed_future"}),
            expected_available_at_ns=availability))
    return cases


def construct():
    source_identity_receipt=verify_reference_sources()
    source=prior.construct()
    outputs=[];errors=[]
    for item in source["cases"]:
        if "error" in item["expected_projection"]:
            errors.append(dict(id=item["id"],expected_error=item["expected_projection"]["error"],
                               scope="Input error witness retained; no numeric rows asserted."))
            continue
        operation=item["operation"]
        requests=item["requests"] if operation=="replay" else [item["request"]]
        snapshot=merge_checkpoint(item["checkpoint"],item["snapshot"]) if operation=="restore" else item["snapshot"]
        checkpoint_sha=rd("flow_checkpoint",item["checkpoint"]) if operation=="restore" else None
        invocation_rows=[]
        for index,request in enumerate(requests):
            # Reconstruct all rows independently under the reviewed clarification.
            # RC2 historical full rows remain unchanged inside source_input.
            # Independently reconstruct them first and require byte equality;
            # never silently revise a previously accepted full golden.
            rows=complete_rows(snapshot,request,input_checkpoint_sha256=checkpoint_sha)
            if len(requests)==1 and item.get("full_result_goldens"):
                if wire.canonical(rows)!=wire.canonical(item["expected_results"]):
                    raise AssertionError("New independent oracle differs from preserved RC2 full golden: "+item["id"])
                rows=copy.deepcopy(item["expected_results"])
            projection=item["expected_projection"]
            if operation!="replay":assert_hand(rows,projection)
            else:
                assert_hand(rows,dict(signs=projection["cut_signs"][index]))
            invocation_rows.append(dict(cut_index=index,expected_results=rows,
                expected_results_record_sha256=rd("flow_results",rows),expected_results_wire=wire.envelope("flow_results",rows),
                snapshot_record_sha256=rd("flow_snapshot",snapshot),request_record_sha256=rd("flow_request",request),
                input_checkpoint_sha256=checkpoint_sha))
        outputs.append(dict(id=item["id"],operation=operation,source_input=copy.deepcopy(item),invocations=invocation_rows,
            expected_scope="Complete independent canonical rows for every actual selected output; no omitted metadata fields."))
    baseline_controls=[]
    for item in baseline_status_controls():
        baseline=baseline_for(item["snapshot"],item["request"],item["snapshot"]["groups"][0],"activity.relative_volume")
        if baseline["baseline_count"]!=item["expected_admitted_baseline_count"] or sorted(baseline["admitted_knowledge"])!=item["expected_baseline_status_clocks"]:
            raise AssertionError("Independent baseline control contradicts literal count/knowledge witness")
        rows=complete_rows(item["snapshot"],item["request"]);assert_hand(rows,item["expected_projection"])
        if rows[0]["available_at_ns"]!=item["expected_available_at_ns"]:
            raise AssertionError("Independent baseline control availability mismatch")
        baseline_controls.append(dict(source_input=item,expected_results=rows,
            expected_results_record_sha256=rd("flow_results",rows),expected_results_wire=wire.envelope("flow_results",rows)))
    side_controls=[]
    for item in observed_side_clock_controls():
        rows=complete_rows(item["snapshot"],item["request"]);assert_hand(rows,item["expected_projection"])
        if any(row["available_at_ns"]!=item["expected_available_at_ns"] for row in rows):
            raise AssertionError("Independent observed-side clock contradicts literal witness")
        side_controls.append(dict(source_input=item,expected_results=rows,
            expected_results_record_sha256=rd("flow_results",rows),expected_results_wire=wire.envelope("flow_results",rows)))
    return dict(schema="r26-independent-full-results1",contract_commit=CONTRACT_COMMIT,
        base_contract_commit=BASE_CONTRACT_COMMIT,base_contract_tree=BASE_CONTRACT_TREE,
        clarification_receipt=CLARIFICATION_RECEIPT,prior_writer_sha256=PRIOR_WRITER_SHA256,
        diagnostic_clarification_commit_prefix=DIAGNOSTIC_CLARIFICATION_COMMIT_PREFIX,
        diagnostic_clarification_receipt=DIAGNOSTIC_CLARIFICATION_RECEIPT,
        source_identity_receipt=source_identity_receipt,
        reference_review_state=REFERENCE_REVIEW_STATE,source_materialization=source,
        full_result_cases=outputs,input_error_cases=errors,independent_baseline_status_controls=baseline_controls,
        independent_observed_side_clock_controls=side_controls,
        limitations=["Not all44 scenario variants are materialized; preserves unchanged RC2 input corpus.",
                     "F33/F35/F38 require actual worker/storage/regression execution; no claim from reference generation.",
                     "Reserved cross outputs remain unsupported; no EQ190 producer arithmetic claimed."],
        production_imports=False,production_output_used=False,runtime_claimed=False)


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("destination",type=Path);args=parser.parse_args()
    output=construct();data=wire.canonical(output)+b"\n";args.destination.write_bytes(data)
    print(json.dumps(dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),
        full_result_cases=len(output["full_result_cases"]),input_error_cases=len(output["input_error_cases"]))))
