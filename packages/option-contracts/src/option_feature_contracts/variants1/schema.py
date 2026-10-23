"""Closed record inventory and stage 3 (shape) / stage 4 (scalar) validation.

Type tokens: id hash text currency u i pos day bool bits bp(positive finite bits)
bn(finite nonnegative bits) su/sp/si (canonical decimal integer strings: >=0, >0,
signed64); E:a|b enumeration; L:x literal; R:Name record; U:Name tagged union;
prefix ? nullable, prefix [] array.
"""
import re
import unicodedata
from .canonical import fail, bits_finite, is_bits, b2f, I64_MAX, I64_MIN

ENUMS = {
    "mode": "synthetic|licensed|public_permitted",
    "right": "call|put",
    "elig": "scalar_standard|nonstandard|unknown",
    "xkind": "new|replace|cancel",
    "exact": "exact|approximate|unknown",
    "cond": "regular|excluded",
    "ckind": "capture|lane_prefix|context_prefix|asof|frontier|reference_absence|eligibility|session_boundary|prior_slot|definition_absence|definition_ineligibility",
    "decision": "include|exclude|not_applicable",
    "creason": "captured|cancelled|condition_excluded|outside_scope|outside_interval|missing_reference|incomplete|prior_slot_present|prior_slot_absent|boundary|missing_definition|future_definition|ineffective_definition|nonstandard_definition|unknown_definition",
    "origin": "qualified_calculation|external_monetary_fact",
    "recipe": "integer-price-b64-products1|b64-price-products1|checked-integer-products1|qualified-supplied1",
    "brecipe": "integer-price-b64-products1|b64-price-products1",
    "order": "session-admission1|rolling-stable-event-admission1|event-id1",
    "profile": "b64-session-BD1|b64-rolling-BD1|i64-paired-call-put1",
    "ckey": "integer-price-quantity1|fixed-b64-price-quantity1|quantity-fixed-b64-premium1",
    "route": "contract-session1|pooled-divide-before-fold1|pooled-fold-before-divide1",
    "coverage": "observed_series|certified_expected_slots",
    "cmetric": "relative_contracts|relative_trades|premium_robust_z",
    "gkind": "parent|repeated_price|multi_venue",
    "signk": "epsilon|paired",
    "mkind": "present|missing",
    "mreason": "ok|metric_missing",
    "unavail": "missing_definition|future_definition|ineffective_definition|nonstandard_definition|unknown_definition",
    "buckreason": "missing_reference|future_reference",
    "axis": "dte|moneyness",
    "tag": "none|ITM|OTM",
    "admission": "raw-active-regular1|positive-derived-premium1",
    "mstatus": "available|undefined|unavailable|unsupported",
    "munit": "currency|currency_ticks|contracts|executions|ratio|mad_z|nanoseconds|venues|payoff_units",
    "mreasonfull": "ok|zero_denominator|incomplete_capture|incomplete_context|premium_unavailable|missing_definition|future_definition|ineffective_definition|nonstandard_definition|unknown_definition|future_reference|premium_overflow|missing_baseline|incomplete_baseline|empty_baseline|insufficient_history|missing_reference|unsupported_profile|source_witness_unqualified",
    "suppunit": "currency|currency_ticks",
    "mbranch": "ordinary|underflow_to_zero|finite_sentinel|nonpositive_baseline_zero|complete_empty|not_evaluated",
}

# Record name -> field declaration order.
RECORDS = {
    "Binding": "binding_id:id source_id:id source_revision:id source_content_sha256:hash mode:E.mode rights:text",
    "Cursor": "stream_id:id position:u",
    "Stamp": "clock_id:id event_ns:u known_at_ns:u stream_id:id position:u binding_id:id",
    "Interval": "start_ns:u end_ns:u start_closed:bool end_closed:bool",
    "MoneyBasis": "unit:L.currency_ticks currency:currency scale:sp",
    "Scope": "scope_id:id population_universe_id:id underlying_id:id contract_ids:[]id session_id:id session_day:day currency:currency action_basis_id:id deliverable_basis_id:id definition_basis_id:id clock_id:id partition_start_ns:u monetary_basis:?R.MoneyBasis",
    "RawIntegerPrice": "kind:L.integer ticks:sp scale:sp",
    "RawBinary64Price": "kind:L.b64 bits:bp",
    "IntegerMultiplier": "kind:L.integer units:sp",
    "Binary64Multiplier": "kind:L.b64 bits:bp",
    "DefinitionAvailable": "kind:L.available definition_id:id",
    "DefinitionUnavailable": "kind:L.unavailable reason:E.unavail control_id:id visible_definition_id:?id",
    "Definition": "definition_id:id revision_id:id contract_id:id underlying_id:id currency:currency action_basis_id:id deliverable_basis_id:id definition_basis_id:id right:E.right strike:bp integer_strike:?R.RawIntegerPrice multiplier:U.Multiplier expiry_day:?day eligibility:E.elig effective:R.Interval stamp:R.Stamp",
    "Reference": "reference_id:id contract_id:id civil_day:?day civil_instant_ns:?u calendar_id:?id calendar_revision:?id civil_stamp:?R.Stamp spot:?bp spot_stamp:?R.Stamp absence_control_ids:[]id",
    "Execution": "root_id:id revision_id:id kind:E.xkind target_revision_id:?id scope_id:id contract_id:id event_ns:u signing_A_ns:u admission_ordinal:u price:?U.Price quantity:?sp definition_use:U.DefinitionUse reference_id:?id venue_id:?id exactness:E.exact condition:E.cond paired_quote_revision_id:?id stamp:R.Stamp",
    "QuoteIntegerPrice": "kind:L.integer ticks:si scale:sp",
    "QuoteBinary64Price": "kind:L.b64 bits:bits",
    "Quote": "quote_id:id revision_id:id kind:E.xkind target_revision_id:?id scope_id:id contract_id:id bid:?U.QuotePrice ask:?U.QuotePrice condition:E.cond pairing_id:?id stamp:R.Stamp",
    "Pairing": "pairing_id:id root_id:id original_revision_id:id quote_revision_id:id stamp:R.Stamp",
    "Control": "control_id:id kind:E.ckind scope_id:id event_domain:R.Interval through_cursors:[]R.Cursor expected_root_ids:[]id expected_contract_ids:[]id excluded_root_ids:[]id complete:bool decision:E.decision reason:E.creason stamp:R.Stamp",
    "ProducerProof": "producer_family:id formula_id:id numeric_profile:id policy_sha256:hash input_record_sha256s:[]hash producer_cohort_sha256:hash output_record_sha256:hash",
    "ProducerProofSupplied": "producer_family:L.option-flow-variants-premium1 formula_id:E.brecipe numeric_profile:L.binary64-rne-each-op-no-fma1 policy_sha256:hash input_record_sha256s:[]hash producer_cohort_sha256:hash output_record_sha256:hash",
    "ProducerProofBucket": "producer_family:L.option-flow-variants-bucket1 formula_id:L.civil-difference-strike-spot-rne1 numeric_profile:L.binary64-rne-each-op-no-fma1 policy_sha256:hash input_record_sha256s:[]hash producer_cohort_sha256:hash output_record_sha256:hash",
    "ProducerProofDaily": "producer_family:L.option-flow-variants-current-activity1 formula_id:L.full-session-positive-activity1 numeric_profile:L.binary64-rne-each-op-no-fma1 policy_sha256:hash input_record_sha256s:[]hash producer_cohort_sha256:hash output_record_sha256:hash",
    "B64Number": "kind:L.b64 bits:bits",
    "I64Number": "kind:L.i64 integer:si",
    "Metric": "metric_id:id monetary_basis:?R.MoneyBasis unit:E.munit value:?U.Number status:E.mstatus reason:E.mreasonfull branch:E.mbranch",
    "DefinitionUseAvailableRef": "kind:L.available definition_id:id",
    "PremiumCore": "root_id:id revision_id:id recipe:E.recipe raw_price:U.Price quantity:sp multiplier:?U.Multiplier definition_use:U.DefinitionUse scale:?sp premium:R.Metric",
    "SuppliedPremium": "premium_id:id root_id:id revision_id:id scope_id:id value:U.Number unit:E.suppunit origin:E.origin producer:?R.ProducerProofSupplied core:?R.PremiumCore external_binding_id:?id definition_id:id stamp:R.Stamp",
    "MetricInput": "kind:E.mkind value:?bn reason:E.mreason",
    "BucketRaw": "kind:L.raw definition_id:id reference_id:id reference_instant_ns:u event_day:day expiry_day:day strike:bp spot:bp calendar_id:id calendar_revision:id",
    "BucketDerived": "kind:L.qualified certificate_id:id dte_days:i moneyness:bp",
    "BucketUnavailable": "kind:L.unavailable reason:E.buckreason control_id:id",
    "ActivityBasis": "admission:E.admission count_conversion:L.checked-i64-then-rne-once1 premium_recipe:E.brecipe premium_order:L.event-id1",
    "DailyAdmission": "basis:R.ActivityBasis certificate_id:?id",
    "DailyObservation": "observation_id:id scope_id:id contract_id:id session_frame_id:id session_day:day session_interval:R.Interval observation_ordinal:u observation_A_ns:u right:E.right bucket_input:U.BucketInput admission:R.DailyAdmission contracts:R.MetricInput trade_count:R.MetricInput premium:R.MetricInput premium_producer:?R.ProducerProofDaily eligibility_control_id:id slot_control_id:id stamp:R.Stamp",
    "BaselineSlot": "slot_id:id scope_id:id session_day:day expected_contract_ids:[]id observation_ids:[]id control_id:id",
    "BucketPolicy": "policy_id:id dte_positive_upper_cutpoints:[]pos dte_zero_id:id dte_band_ids:[]id dte_overflow_id:id moneyness_distance_upper_cutpoints:[]bp atm_id:id moneyness_band_ids:[]id moneyness_overflow_id:id",
    "SessionFrame": "frame_id:id scope_id:id session_day:day full_session:R.Interval horizon_id:L.full-session1 boundary_control_id:id",
    "ActivityTarget": "target_id:id scope_id:id contract_id:id session_frame_id:id right:E.right bucket_policy_id:id bucket_input:U.BucketInput reference_instant_ns:u reference_A_ns:u stamp:R.Stamp",
    "BucketCore": "owner_id:id contract_id:id scope_id:id session_frame_id:id reference_A_ns:u right:E.right raw:R.BucketRaw dte_days:i moneyness:bp units:L.civil_days_and_strike_per_spot selection_profile:L.origin-A-common-clock1",
    "BucketCertificate": "certificate_id:id core:R.BucketCore producer:R.ProducerProofBucket stamp:R.Stamp",
    "DailyActivityCore": "observation_id:id scope_id:id contract_id:id session_frame_id:id session_day:day right:E.right observation_A_ns:u bucket_input:U.BucketInput basis:R.ActivityBasis raw_contracts:u raw_trade_count:u observed_positive_contracts:u observed_positive_trade_count:u membership_complete:bool contracts:R.MetricInput trade_count:R.MetricInput premium:R.MetricInput raw_population_sha256:hash eligible_population_sha256:hash zero_premium_core_sha256s:[]hash unresolved_ids:[]id",
    "DailyActivityCertificate": "certificate_id:id core:R.DailyActivityCore producer:R.ProducerProofDaily stamp:R.Stamp",
    "Snapshot": "schema_version:L.option-flow-variants-canonical1 bindings:[]R.Binding scopes:[]R.Scope definitions:[]R.Definition references:[]R.Reference executions:[]R.Execution quotes:[]R.Quote pairings:[]R.Pairing controls:[]R.Control supplied_premiums:[]R.SuppliedPremium daily_observations:[]R.DailyObservation baseline_slots:[]R.BaselineSlot bucket_policies:[]R.BucketPolicy session_frames:[]R.SessionFrame activity_targets:[]R.ActivityTarget bucket_certificates:[]R.BucketCertificate daily_activity_certificates:[]R.DailyActivityCertificate cursors:[]R.Cursor",
    # request side
    "Limits": "wire_bytes:u records:u depth:u roots:u quotes:u references:u streams:u scopes:u operations:u outputs:u prior_slots:u contracts:u quantiles:u format_digits:u",
    "SignPolicy": "kind:E.signk epsilon:?bp max_quote_age_ns:u",
    "Policy": "policy_id:id formula_version:L.option-flow-variants1 temporal_profile:L.origin-A-economics-K-common-clock1 numeric_profile:L.binary64-rne-each-op-no-fma1 sign:R.SignPolicy max_spot_age_ns:u short_dte_max_days:u window_ns:pos lateness_ns:u format_digits:u sentinel:bp mad_scale:bp",
    "BucketKey": "axis:E.axis band_id:id tag:E.tag",
    "PremiumOp": "op_id:id scope_id:id policy_id:id kind:L.premium recipe:E.recipe root_ids:[]id",
    "DirectionalOp": "op_id:id scope_id:id policy_id:id kind:L.directional profile:E.profile recipe:E.recipe capture_ids:[]id context_ids:[]id session_endpoint_control_id:?id horizon_ns:?pos rollup_interval:?R.Interval",
    "JointOp": "op_id:id scope_id:id policy_id:id kind:L.joint_reference recipe:E.recipe order:E.order capture_ids:[]id context_ids:[]id",
    "ConcentrationOp": "op_id:id scope_id:id policy_id:id kind:L.concentration key:E.ckey recipe:E.recipe order:E.order capture_ids:[]id",
    "BaselineOp": "op_id:id scope_id:id policy_id:id kind:L.baseline route:E.route coverage:E.coverage asof_day:day slot_ids:[]id bucket_policy_id:id dte_bucket:R.BucketKey moneyness_bucket:R.BucketKey right:E.right activity_basis:R.ActivityBasis horizon_id:L.full-session1 minimum_samples:pos quantiles:[]bits include_mean:bool",
    "ConsumerOp": "op_id:id scope_id:id policy_id:id kind:L.baseline_consumer metric:E.cmetric baseline_op_id:id current_op_id:id",
    "ParentOp": "op_id:id scope_id:id policy_id:id kind:L.parent_groups recipe:L.checked-integer-products1 capture_ids:[]id lane_prefix_ids:[]id context_ids:[]id frontier_control_id:?id kinds:[]E.gkind",
    "SpanOp": "op_id:id scope_id:id policy_id:id kind:L.span_at_anchor recipe:E.brecipe anchor_ids:[]id capture_ids:[]id context_ids:[]id asof_control_id:id",
    "CurrentActivityOp": "op_id:id scope_id:id policy_id:id kind:L.current_activity target_id:id recipe:E.brecipe capture_ids:[]id",
    "Request": "schema_version:L.option-flow-variants-request1 knowledge_K_ns:u clock_id:id emit:R.Interval cut_cursors:[]R.Cursor policies:[]R.Policy operations:[]U.Operation limits:R.Limits formula_version:L.option-flow-variants1 producer_admission_sha256:?hash",
}

UNIONS = {
    "Price": {"integer": "RawIntegerPrice", "b64": "RawBinary64Price"},
    "Multiplier": {"integer": "IntegerMultiplier", "b64": "Binary64Multiplier"},
    "QuotePrice": {"integer": "QuoteIntegerPrice", "b64": "QuoteBinary64Price"},
    "DefinitionUse": {"available": "DefinitionAvailable", "unavailable": "DefinitionUnavailable"},
    "Number": {"b64": "B64Number", "i64": "I64Number"},
    "BucketInput": {"raw": "BucketRaw", "qualified": "BucketDerived", "unavailable": "BucketUnavailable"},
    "Operation": {"premium": "PremiumOp", "directional": "DirectionalOp", "joint_reference": "JointOp",
                  "concentration": "ConcentrationOp", "baseline": "BaselineOp", "baseline_consumer": "ConsumerOp",
                  "parent_groups": "ParentOp", "span_at_anchor": "SpanOp", "current_activity": "CurrentActivityOp"},
}

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_HASH = re.compile(r"^[0-9a-f]{64}$")
_CUR = re.compile(r"^[A-Z]{3}$")
_UINT = re.compile(r"^(0|[1-9][0-9]{0,18})$")
_SINT = re.compile(r"^(0|-?[1-9][0-9]{0,18})$")
_JSON_TYPES = {"id": str, "hash": str, "text": str, "currency": str, "bits": str, "bp": str, "bn": str,
               "su": str, "sp": str, "si": str}
_INT_TOKENS = ("u", "i", "pos", "day")

LIMIT_CAPS = {"wire_bytes": 16777216, "records": 100000, "depth": 32, "roots": 4096, "quotes": 8192,
              "references": 8192, "streams": 128, "scopes": 128, "operations": 128, "outputs": 8192,
              "prior_slots": 3660, "contracts": 4096, "quantiles": 32, "format_digits": 18}


def _parse(spec):
    nullable = array = False
    if spec.startswith("?"):
        nullable, spec = True, spec[1:]
    if spec.startswith("[]"):
        array, spec = True, spec[2:]
    return nullable, array, spec


_FIELDS = {name: [tuple(tok.split(":", 1)) for tok in body.split()] for name, body in RECORDS.items()}


def _ptr(path, key):
    return "%s/%s" % (path, key)


def _check_record(value, name, path, stage):
    if type(value) is not dict:
        if stage == 3:
            fail("type_mismatch", path, 3)
        return
    fields = _FIELDS[name]
    if stage == 3:
        names = [f for f, _ in fields]
        for f in names:
            if f not in value:
                fail("field_set", _ptr(path, f), 3)
        for k in value:
            if k not in names:
                fail("field_set", _ptr(path, k), 3)
    for f, spec in fields:
        _check(value[f], spec, _ptr(path, f), stage)
    if stage == 4:
        _record_rules(value, name, path)


def _record_rules(value, name, path):
    if name == "Interval":
        s, e = value["start_ns"], value["end_ns"]
        if s > e or (s == e and not (value["start_closed"] and value["end_closed"])):
            fail("invalid_scalar", path, 4)
    elif name == "SignPolicy":
        if (value["kind"] == "epsilon") != (value["epsilon"] is not None):
            fail("invalid_scalar", _ptr(path, "epsilon"), 4)
    elif name == "Policy":
        if value["short_dte_max_days"] > 3652058 or value["format_digits"] > 18:
            fail("invalid_scalar", path, 4)
    elif name == "Limits":
        for k, cap in LIMIT_CAPS.items():
            v = value[k]
            if v > cap or (v == 0 and k != "format_digits"):
                fail("invalid_scalar", _ptr(path, k), 4)
    elif name == "BucketPolicy":
        cuts = value["dte_positive_upper_cutpoints"]
        if len(cuts) != len(value["dte_band_ids"]) or any(a >= b for a, b in zip(cuts, cuts[1:])):
            fail("invalid_scalar", _ptr(path, "dte_positive_upper_cutpoints"), 4)
        m = value["moneyness_distance_upper_cutpoints"]
        if len(m) != len(value["moneyness_band_ids"]) or any(b2f(a) >= b2f(b) for a, b in zip(m, m[1:])):
            fail("invalid_scalar", _ptr(path, "moneyness_distance_upper_cutpoints"), 4)
    elif name == "MetricInput":
        if (value["kind"] == "present") != (value["value"] is not None) or \
                (value["kind"] == "present") != (value["reason"] == "ok"):
            fail("invalid_scalar", path, 4)
    elif name == "Stamp":
        pass
    elif name in ("PremiumOp",):
        if not value["root_ids"]:
            fail("invalid_scalar", _ptr(path, "root_ids"), 4)
    elif name == "BaselineOp":
        q = value["quantiles"]
        if len(q) > 32 or any(not (0.0 <= b2f(x) <= 1.0) for x in q) or any(b2f(a) >= b2f(b) for a, b in zip(q, q[1:])):
            fail("invalid_scalar", _ptr(path, "quantiles"), 4)
        if value["minimum_samples"] > 3660:
            fail("invalid_scalar", _ptr(path, "minimum_samples"), 4)


def _check_scalar(value, kind, path, stage):
    if stage == 3:
        if kind in _INT_TOKENS:
            if type(value) is not int:
                fail("type_mismatch", path, 3)
        elif kind == "bool":
            if type(value) is not bool:
                fail("type_mismatch", path, 3)
        elif type(value) is not str:
            fail("type_mismatch", path, 3)
        return
    ok = True
    if kind == "id":
        ok = _ID.match(value) is not None
    elif kind == "hash":
        ok = _HASH.match(value) is not None
    elif kind == "text":
        ok = (unicodedata.normalize("NFC", value) == value and 1 <= len(value.encode("utf-8")) <= 1024 and
              all(unicodedata.category(c) not in ("Cc", "Cf", "Cs") for c in value))
    elif kind == "currency":
        ok = _CUR.match(value) is not None
    elif kind == "u":
        ok = 0 <= value <= I64_MAX
    elif kind == "i":
        ok = I64_MIN <= value <= I64_MAX
    elif kind == "pos":
        ok = 0 < value <= I64_MAX
    elif kind == "day":
        ok = 1 <= value <= 3652059
    elif kind in ("bits", "bp", "bn"):
        ok = is_bits(value) and bits_finite(value)
        if ok and kind == "bp":
            ok = b2f(value) > 0
        elif ok and kind == "bn":
            ok = b2f(value) >= 0
    elif kind == "su":
        ok = _UINT.match(value) is not None and int(value) <= I64_MAX
    elif kind == "sp":
        ok = _UINT.match(value) is not None and 0 < int(value) <= I64_MAX
    elif kind == "si":
        ok = _SINT.match(value) is not None and I64_MIN <= int(value) <= I64_MAX
    if not ok:
        fail("invalid_scalar", path, 4)


def _check(value, spec, path, stage):
    nullable, array, base = _parse(spec)
    if value is None:
        if nullable:
            return
        fail("type_mismatch" if stage == 3 else "invalid_scalar", path, stage)
    if array:
        if type(value) is not list:
            if stage == 3:
                fail("type_mismatch", path, 3)
            return
        for i, item in enumerate(value):
            _check_one(item, base, "%s/%d" % (path, i), stage)
        return
    _check_one(value, base, path, stage)


def _check_one(value, base, path, stage):
    if base.startswith("R."):
        _check_record(value, base[2:], path, stage)
    elif base.startswith("U."):
        table = UNIONS[base[2:]]
        if type(value) is not dict:
            if stage == 3:
                fail("type_mismatch", path, 3)
            return
        if "kind" not in value:
            if stage == 3:
                fail("field_set", _ptr(path, "kind"), 3)
            return
        k = value["kind"]
        if type(k) is not str:
            if stage == 3:
                fail("type_mismatch", _ptr(path, "kind"), 3)
            return
        if k not in table:
            if stage == 3:
                fail("invalid_scalar", _ptr(path, "kind"), 3)
            return
        _check_record(value, table[k], path, stage)
    elif base.startswith("E."):
        if stage == 3:
            if type(value) is not str:
                fail("type_mismatch", path, 3)
        elif value not in ENUMS[base[2:]].split("|"):
            fail("invalid_scalar", path, 4)
    elif base.startswith("L."):
        if stage == 3:
            if type(value) is not str:
                fail("type_mismatch", path, 3)
        elif value != base[2:]:
            fail("invalid_scalar", path, 4)
    else:
        _check_scalar(value, base, path, stage)


def validate_shape(value, name, root):
    """Stage 3 then stage 4 over one record tree rooted at `root` (e.g. '/snapshot')."""
    _check_record(value, name, root, 3)


def validate_scalars(value, name, root):
    _check_record(value, name, root, 4)
