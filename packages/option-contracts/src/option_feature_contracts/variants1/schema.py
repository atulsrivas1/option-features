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
    # output / evidence / source record inventory
    "depuse": "economic|context|capture|exclusion|baseline|policy|numerical_eligibility",
    "side": "buy|sell",
    "sside": "buy|sell|unknown",
    "sreason": "classified|dead_band|inside_spread|missing_quote|stale_quote|invalid_quote|missing_pairing|incomplete_context",
    "iwkind": "contract|strike|expiry",
    "eoutcome": "positive|excluded_zero|unresolved_premium",
    "finality": "pending|final",
    "obsstate": "pending_horizon|bounded_asof_complete|incomplete_capture",
    "idstatus": "available|unavailable",
    "idreason": "ok|missing_reference|future_reference",
    "bdbranch": "negative_dte|ratio_rounded_zero",
    "statid": "contracts|trade_count|premium",
    "astatus": "available|unavailable",
    "areason": "ok|premium_unavailable",
    "role": "contracts|calculations|io|workers|dependency",
    "qptype": "variant_BucketCertificate|variant_DailyActivityCertificate|variant_SuppliedPremium",
    "xmode": "batch|chronological_cut_replay|checkpoint_restore",
    "coutcome": "committed|already_committed",
    "routcome": "computed|committed|already_committed|cancelled",
}

# Admitted Dependency.record_type -> allowed uses (contract section "Finite dependency identity").
DEPENDENCY_USES = {
    "variant_Binding": "economic|context|baseline",
    "variant_Scope": "policy",
    "variant_Policy": "policy",
    "variant_BucketPolicy": "policy",
    "variant_SessionFrame": "capture|baseline",
    "variant_Definition": "economic|context|baseline",
    "variant_Execution": "economic|context|exclusion",
    "variant_Quote": "context",
    "variant_Pairing": "context",
    "variant_Control": "capture|context|exclusion|baseline",
    "variant_SuppliedPremium": "economic",
    "variant_DailyObservation": "baseline",
    "variant_BaselineSlot": "baseline",
    "variant_ActivityTarget": "economic|baseline",
    "variant_BucketCertificate": "context|baseline",
    "variant_DailyActivityCertificate": "baseline",
    "variant_CivilFact": "context|baseline",
    "variant_SpotFact": "context|baseline",
    "variant_PremiumCore": "economic|numerical_eligibility",
    "variant_CurrentActivityObject": "economic",
    "variant_BaselineObject": "baseline",
}

# Fixed ProducerProof tuples for PremiumObject by recipe (formula_id, numeric_profile).
PREMIUM_PROOF = {
    "integer-price-b64-products1": ("integer-price-b64-products1", "binary64-rne-each-op-no-fma1"),
    "b64-price-products1": ("b64-price-products1", "binary64-rne-each-op-no-fma1"),
    "checked-integer-products1": ("checked-integer-products1", "checked-i64-each-op1"),
    "qualified-supplied1": ("qualified-supplied-pass-through1", "binary64-preserve-bits1"),
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
    "RawBinary64Price": "kind:L.b64 bits:bn",
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
    # consumed-field projections (contract: dependency identity, consumed-field projections)
    "CivilFact": "reference_id:id contract_id:id civil_day:day civil_instant_ns:u calendar_id:id calendar_revision:id stamp:R.Stamp",
    "SpotFact": "reference_id:id contract_id:id spot:bits stamp:R.Stamp",
    "ActivityKey": "underlying_id:id contract_id:?id right:E.right activity_basis:R.ActivityBasis bucket_policy_sha256:hash dte_bucket:R.BucketKey moneyness_bucket:R.BucketKey currency:currency action_basis_id:id deliverable_basis_id:id definition_basis_id:id population_universe_id:id horizon_id:L.full-session1",
    # result side: evidence
    "Dependency": "record_type:id record_id:id record_sha256:hash use:E.depuse known_at_ns:u",
    "Evidence": "dependencies:[]R.Dependency member_ids:[]id member_revision_ids:[]id unknown_sign_ids:[]id unknown_reference_ids:[]id excluded_ids:[]id control_ids:[]id capture_complete:bool context_complete:bool eligibility:?R.EligibilityEvidence bucket_domain_evidence:[]R.BucketDomainEvidence available_at_ns:u",
    "Diagnostic": "code:E.mreasonfull subject_id:id",
    "EligibilityWitness": "root_id:id revision_id:id premium_core:R.PremiumCore premium_core_sha256:hash outcome:E.eoutcome available_at_ns:u",
    "EligibilityEvidence": "raw_contracts:R.Metric raw_trade_count:R.Metric observed_positive_contracts:u observed_positive_trade_count:u zero_excluded_ids:[]id unresolved_ids:[]id positive_complete:bool witnesses:[]R.EligibilityWitness",
    "BucketDomainEvidence": "owner_id:id raw:R.BucketRaw reference_A_ns:u dte_days:i moneyness:?bits branch:E.bdbranch",
    "SignWitness": "root_id:id revision_id:id side:E.sside profile:E.signk reason:E.sreason quote_revision_id:?id pairing_id:?id signing_A_ns:u context_sha256:hash",
    # result side: payload objects
    "PremiumObject": "root_id:id revision_id:id recipe:E.recipe raw_price:U.Price quantity:sp multiplier:?U.Multiplier definition_use:U.DefinitionUse scale:?sp premium:R.Metric producer:R.ProducerProof",
    "IntegerWeight": "kind:E.iwkind contract_id:?id strike:?R.RawIntegerPrice expiry_day:?day premium:R.Metric",
    "DirectionalObject": "profile:E.profile order:E.order member_interval:R.Interval premiums:[]R.PremiumObject signs:[]R.SignWitness integer_weights:[]R.IntegerWeight metrics:[]R.Metric",
    "JointObject": "premiums:[]R.PremiumObject signs:[]R.SignWitness joint_ids:[]id short_ids:[]id otm_ids:[]id metrics:[]R.Metric",
    "ConcentrationKey": "kind:E.ckey quantity:sp raw_price_ticks:?sp price_scale:?sp fixed_text:?text digits:?u",
    "Bucket": "key:R.ConcentrationKey member_ids:[]id premium:R.Metric share:R.Metric",
    "ConcentrationObject": "order:E.order buckets:[]R.Bucket tied_key_sha256s:[]hash total:R.Metric maximum_share:R.Metric latest_event_ns:?u",
    "BucketWitness": "observation_id:id input:U.BucketInput observation_A_ns:u dte_days:i moneyness:bp distance:bits dte_index:u moneyness_index:u dte_equal_cutpoint:bool moneyness_equal_cutpoint:bool dte_bucket:R.BucketKey moneyness_bucket:R.BucketKey",
    "ProducerProofBaselineDaily": "producer_family:L.option-flow-variants-baseline-daily1 formula_id:E.route numeric_profile:L.binary64-rne-each-op-no-fma1 policy_sha256:hash input_record_sha256s:[]hash producer_cohort_sha256:hash output_record_sha256:hash",
    "DailyCore": "slot_id:id session_day:day contract_ids:[]id observation_ids:[]id route:E.route bucket_witnesses:[]R.BucketWitness dte_bucket:R.BucketKey moneyness_bucket:R.BucketKey eligible_count:u contracts:R.Metric trade_count:R.Metric premium:R.Metric",
    "DailyReduction": "slot_id:id session_day:day contract_ids:[]id observation_ids:[]id route:E.route bucket_witnesses:[]R.BucketWitness dte_bucket:R.BucketKey moneyness_bucket:R.BucketKey eligible_count:u contracts:R.Metric trade_count:R.Metric premium:R.Metric producer:R.ProducerProofBaselineDaily",
    "Quantile": "probability:bits value:R.Metric",
    "Statistic": "metric_id:E.statid sample_slot_ids:[]id sorted_sample_bits:[]bits samples:u median:R.Metric mad:R.Metric mean:?R.Metric quantiles:[]R.Quantile",
    "BaselineObject": "route:E.route coverage:E.coverage activity_key:?R.ActivityKey asof_day:day slot_ids:[]id missing_slot_ids:[]id daily:[]R.DailyReduction statistics:[]R.Statistic",
    "CurrentActivityObject": "target_id:id session_frame_id:id full_session:R.Interval reference_A_ns:u bucket_witness:?R.BucketWitness activity_key:?R.ActivityKey identity_status:E.idstatus identity_reason:E.idreason premiums:[]R.PremiumObject metrics:[]R.Metric",
    "ConsumerObject": "baseline_op_id:id current_op_id:id current_raw:R.Metric current_b64:R.Metric median:R.Metric mad:?R.Metric scale:?bp sentinel:bp result:R.Metric",
    "VenueEvidence": "known_venue_ids:[]id unknown_member_ids:[]id",
    "ExactnessEvidence": "exact_ids:[]id approximate_ids:[]id unknown_ids:[]id",
    "GroupObject": "group_id:hash monetary_basis:R.MoneyBasis kind:E.gkind parent_anchor_id:id parent_anchor_ns:u subset_start_id:id subset_start_ns:u member_interval:R.Interval member_ids:[]id member_revision_ids:[]id exact_price_ticks:?sp price_scale:?sp side:E.side membership_complete:bool finality:E.finality frontier_control_id:?id venues:R.VenueEvidence exactness:R.ExactnessEvidence count:u contracts:u premium:R.Metric",
    "SpanObject": "candidate_id:hash anchor_id:id anchor_event_ns:u asof_control_id:id member_interval:R.Interval member_ids:[]id member_revision_ids:[]id membership_complete:bool horizon_reached:bool observation_state:E.obsstate venues:R.VenueEvidence exactness:R.ExactnessEvidence count:u premium:R.Metric latest_event_ns:u",
    # result envelope
    "ResultPayloadPremium": "kind:L.premium value:R.PremiumObject",
    "ResultPayloadDirectional": "kind:L.directional value:R.DirectionalObject",
    "ResultPayloadJoint": "kind:L.joint_reference value:R.JointObject",
    "ResultPayloadConcentration": "kind:L.concentration value:R.ConcentrationObject",
    "ResultPayloadBaseline": "kind:L.baseline value:R.BaselineObject",
    "ResultPayloadCurrentActivity": "kind:L.current_activity value:R.CurrentActivityObject",
    "ResultPayloadConsumer": "kind:L.baseline_consumer value:R.ConsumerObject",
    "ResultPayloadGroup": "kind:L.group value:R.GroupObject",
    "ResultPayloadSpan": "kind:L.span value:R.SpanObject",
    "Result": "schema_version:L.option-flow-variants-result1 op_id:id scope_id:id object_id:?hash formula_version:L.option-flow-variants1 policy_sha256:hash snapshot_sha256:hash request_sha256:hash cohort_sha256:hash input_checkpoint_sha256:?hash evidence:R.Evidence diagnostics:[]R.Diagnostic payload:U.ResultPayload",
    "AnchorReadiness": "anchor_id:id status:E.astatus reason:E.areason premium_core:?R.PremiumCore evidence:R.Evidence",
    "OperationReceipt": "op_id:id object_count:u status:E.mstatus reason:E.mreasonfull anchor_readiness:[]R.AnchorReadiness evidence:R.Evidence",
    "Results": "schema_version:L.option-flow-variants-result1 operations:[]R.OperationReceipt rows:[]R.Result",
    # checkpoint, cohort, producer admission, publication and receipts
    "QualifiedProducerInput": "record_type:E.qptype record_sha256:hash output_core_sha256:hash input_record_sha256s:[]hash qualification_receipt_sha256:hash",
    "ProducerAdmission": "schema_version:L.option-flow-variants-producers1 producer_selector:L.current-evaluator1 qualified_inputs:[]R.QualifiedProducerInput",
    "Checkpoint": "schema_version:L.option-flow-variants-checkpoint1 history:R.Snapshot prior_request:R.Request history_sha256:hash prior_request_sha256:hash policy_sha256s:[]hash evaluator_cohort_sha256:hash producer_admission:?R.ProducerAdmission formula_version:L.option-flow-variants1",
    "ConversionReceipt": "snapshot_sha256:hash raw_binding_ids:[]id duplicate_identical_count:u excluded_source_count:u limitations:[]text",
    "Artifact": "distribution:id version:id source_commit:id wheel_sha256:hash role:E.role",
    "Cohort": "schema_version:L.option-flow-variants-cohort1 candidate_id:id python_version:id platform_id:id contract_manifest_sha256:hash artifacts:[]R.Artifact",
    "ExecutionConfig": "mode:E.xmode max_workers:u max_inflight:u io_slots:u backend_threads:u memory_budget_bytes:u logical_task_bytes:u producer_admission_sha256:?hash producer_qualification_receipt_sha256s:[]hash",
    "Publication": "schema_version:L.option-flow-variants-generation1 run_key:id work_sha256:hash request:R.Request snapshot_sha256:hash request_sha256:hash cohort:R.Cohort cohort_sha256:hash producer_admission:?R.ProducerAdmission input_checkpoint_sha256:?hash results:R.Results bindings:[]R.Binding output_checkpoint:?R.Checkpoint",
    "CommitReceipt": "run_key:id work_sha256:hash publication_sha256:hash results_sha256:hash output_checkpoint_sha256:?hash object_count:u outcome:E.coutcome verified_readback:bool",
    "RunReceipt": "run_key:id work_sha256:hash outcome:E.routcome results:?R.Results output_checkpoint:?R.Checkpoint commit_receipt:?R.CommitReceipt cancellation_observed:bool",
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
    # Each payload is exactly {kind, value}; the wrapper record carries the object under `value`.
    "ResultPayload": {"premium": "ResultPayloadPremium", "directional": "ResultPayloadDirectional",
                      "joint_reference": "ResultPayloadJoint", "concentration": "ResultPayloadConcentration",
                      "baseline": "ResultPayloadBaseline", "current_activity": "ResultPayloadCurrentActivity",
                      "baseline_consumer": "ResultPayloadConsumer", "group": "ResultPayloadGroup",
                      "span": "ResultPayloadSpan"},
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
    elif stage == 9:
        _coherence_rules(value, name, path)


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
    else:
        rule = _OUTPUT_RULES.get(name)
        if rule is not None:
            rule(value, path)


_REASON_BY_STATUS = {"available": ("ok",), "undefined": ("zero_denominator",),
                     "unsupported": ("unsupported_profile", "source_witness_unqualified")}
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _bad(path, key):
    fail("invalid_scalar", _ptr(path, key), 4)


def _status_reason(value, path):
    """Available/ok, undefined/zero_denominator, unsupported/{profile,witness}; the rest unavailable."""
    status, reason = value["status"], value["reason"]
    allowed = _REASON_BY_STATUS.get(status)
    if allowed is not None:
        if reason not in allowed:
            _bad(path, "reason")
    elif reason == "ok" or reason == "zero_denominator" or reason in _REASON_BY_STATUS["unsupported"]:
        _bad(path, "reason")


def _rule_metric(value, path):
    _status_reason(value, path)
    available = value["status"] == "available"
    if (value["value"] is not None) != available:
        _bad(path, "value")
    if not available and value["branch"] != "not_evaluated":
        _bad(path, "branch")
    if (value["unit"] == "currency_ticks") != (value["monetary_basis"] is not None):
        _bad(path, "monetary_basis")


def _rule_dependency(value, path):
    uses = DEPENDENCY_USES.get(value["record_type"])
    if uses is None:
        _bad(path, "record_type")
    if value["use"] not in uses.split("|"):
        _bad(path, "use")


def _rule_bucket_domain(value, path):
    if value["branch"] == "negative_dte":
        if value["dte_days"] >= 0:
            _bad(path, "dte_days")
        if value["moneyness"] is not None:
            _bad(path, "moneyness")
    else:
        if value["dte_days"] < 0:
            _bad(path, "dte_days")
        if value["moneyness"] != "0000000000000000":
            _bad(path, "moneyness")


def _rule_proof_premium(value, path):
    formula, profile = PREMIUM_PROOF[value["recipe"]]
    producer = value["producer"]
    base = _ptr(path, "producer")
    if producer["producer_family"] != "option-flow-variants-premium1":
        _bad(base, "producer_family")
    if producer["formula_id"] != formula:
        _bad(base, "formula_id")
    if producer["numeric_profile"] != profile:
        _bad(base, "numeric_profile")


def _rule_integer_weight(value, path):
    want = {"contract": "contract_id", "strike": "strike", "expiry": "expiry_day"}[value["kind"]]
    for key in ("contract_id", "strike", "expiry_day"):
        if (value[key] is not None) != (key == want):
            _bad(path, key)


def _rule_directional(value, path):
    if value["profile"] != "i64-paired-call-put1" and value["integer_weights"]:
        _bad(path, "integer_weights")


def _rule_concentration_key(value, path):
    if value["kind"] == "integer-price-quantity1":
        for key in ("raw_price_ticks", "price_scale"):
            if value[key] is None:
                _bad(path, key)
        for key in ("fixed_text", "digits"):
            if value[key] is not None:
                _bad(path, key)
        return
    for key in ("raw_price_ticks", "price_scale"):
        if value[key] is not None:
            _bad(path, key)
    for key in ("fixed_text", "digits"):
        if value[key] is None:
            _bad(path, key)
    digits, text = value["digits"], value["fixed_text"]
    if digits > 18:
        _bad(path, "digits")
    # Fixed_d: exact d fractional digits, dot separator, no exponent/plus/grouping, ASCII only.
    body = text[1:] if text.startswith("-") else text
    whole, dot, frac = body.partition(".")
    if not (text.isascii() and whole.isdigit() and len(frac) == digits and (frac.isdigit() or not frac)
            and bool(dot) == (digits > 0)):
        _bad(path, "fixed_text")


def _rule_quantile(value, path):
    if not 0.0 <= b2f(value["probability"]) <= 1.0:
        _bad(path, "probability")


def _rule_statistic(value, path):
    if len(value["sample_slot_ids"]) != len(value["sorted_sample_bits"]):
        _bad(path, "sample_slot_ids")


def _rule_daily_reduction(value, path):
    if value["producer"]["formula_id"] != value["route"]:
        _bad(_ptr(path, "producer"), "formula_id")


def _rule_current_activity(value, path):
    ready = value["identity_status"] == "available"
    if ready != (value["identity_reason"] == "ok"):
        _bad(path, "identity_reason")
    if ready != (value["activity_key"] is not None):
        _bad(path, "activity_key")
    if ready != (value["bucket_witness"] is not None):
        _bad(path, "bucket_witness")


def _rule_group(value, path):
    repeated = value["kind"] == "repeated_price"
    for key in ("exact_price_ticks", "price_scale"):
        if (value[key] is not None) != repeated:
            _bad(path, key)
    if value["finality"] == "final":
        if not value["membership_complete"]:
            _bad(path, "finality")
        if value["frontier_control_id"] is None:
            _bad(path, "frontier_control_id")


def _rule_span(value, path):
    if value["count"] < 1:
        _bad(path, "count")


def _rule_anchor(value, path):
    if (value["status"] == "available") != (value["reason"] == "ok"):
        _bad(path, "reason")


def _rule_eligibility_evidence(value, path):
    for key, unit in (("raw_contracts", "contracts"), ("raw_trade_count", "executions")):
        metric = value[key]
        if metric["metric_id"] != key:
            _bad(_ptr(path, key), "metric_id")
        if metric["unit"] != unit:
            _bad(_ptr(path, key), "unit")
        if metric["value"] is not None and metric["value"]["kind"] != "i64":
            _bad(_ptr(path, key), "value")
        if metric["status"] == "unavailable" and metric["reason"] != "incomplete_capture":
            _bad(_ptr(path, key), "reason")


def _rule_artifact(value, path):
    if _COMMIT.match(value["source_commit"]) is None:
        _bad(path, "source_commit")


def _rule_admission(value, path):
    if not value["qualified_inputs"]:
        _bad(path, "qualified_inputs")


def _rule_exec_config(value, path):
    for key in ("max_workers", "max_inflight", "io_slots", "backend_threads"):
        if value[key] != 1:
            _bad(path, key)
    if value["logical_task_bytes"] < 268435456:
        _bad(path, "logical_task_bytes")
    if value["logical_task_bytes"] > value["memory_budget_bytes"]:
        _bad(path, "logical_task_bytes")


def _rule_commit_receipt(value, path):
    if value["verified_readback"] is not True:
        _bad(path, "verified_readback")


def _rule_run_receipt(value, path):
    outcome = value["outcome"]
    if outcome == "cancelled":
        for key in ("results", "output_checkpoint", "commit_receipt"):
            if value[key] is not None:
                _bad(path, key)
        return
    if value["results"] is None:
        _bad(path, "results")
    if (outcome == "computed") != (value["commit_receipt"] is None):
        _bad(path, "commit_receipt")
    if outcome != "computed" and value["commit_receipt"]["outcome"] != outcome:
        _bad(path, "outcome")


_OUTPUT_RULES = {
    "Metric": _rule_metric,
    "Dependency": _rule_dependency,
    "BucketDomainEvidence": _rule_bucket_domain,
    "PremiumObject": _rule_proof_premium,
    "IntegerWeight": _rule_integer_weight,
    "DirectionalObject": _rule_directional,
    "ConcentrationKey": _rule_concentration_key,
    "Quantile": _rule_quantile,
    "Statistic": _rule_statistic,
    "DailyReduction": _rule_daily_reduction,
    "CurrentActivityObject": _rule_current_activity,
    "GroupObject": _rule_group,
    "SpanObject": _rule_span,
    "AnchorReadiness": _rule_anchor,
    "OperationReceipt": _status_reason,
    "EligibilityEvidence": _rule_eligibility_evidence,
    "Artifact": _rule_artifact,
    "ProducerAdmission": _rule_admission,
    "ExecutionConfig": _rule_exec_config,
    "CommitReceipt": _rule_commit_receipt,
    "RunReceipt": _rule_run_receipt,
}


def _check_scalar(value, kind, path, stage):
    if stage == 9:
        return
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
        if stage != 9:
            fail("type_mismatch" if stage == 3 else "invalid_scalar", path, stage)
        return
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
        elif stage == 4 and value not in ENUMS[base[2:]].split("|"):
            fail("invalid_scalar", path, 4)
    elif base.startswith("L."):
        if stage == 3:
            if type(value) is not str:
                fail("type_mismatch", path, 3)
        elif stage == 4 and value != base[2:]:
            fail("invalid_scalar", path, 4)
    else:
        _check_scalar(value, base, path, stage)


def validate_shape(value, name, root):
    """Stage 3 then stage 4 over one record tree rooted at `root` (e.g. '/snapshot')."""
    _check_record(value, name, root, 3)


def validate_scalars(value, name, root):
    _check_record(value, name, root, 4)


_SHARE_IDS = ("short_observed_share", "otm_observed_share", "joint_reference_coverage")


def _share_bound(metric, path):
    """Available share values are in [0,1]; the next representable value above 1 is a coherence failure."""
    number = metric["value"]
    if number is not None and number["kind"] == "b64" and b2f(number["bits"]) > 1.0:
        fail("identity_mismatch", "%s/value/bits" % path, 9)


def _coherence_rules(value, name, path):
    """Stage 9 result-coherence rules that need only the output record itself."""
    if name == "JointObject":
        for i, metric in enumerate(value["metrics"]):
            if metric["metric_id"] in _SHARE_IDS:
                _share_bound(metric, "%s/metrics/%d" % (path, i))
    elif name == "Bucket":
        _share_bound(value["share"], _ptr(path, "share"))
    elif name == "ConcentrationObject":
        _share_bound(value["maximum_share"], _ptr(path, "maximum_share"))


def validate_coherence(value, name, root):
    """Stage 9 output coherence over an already stage 3/4 valid record tree (e.g. root '/results')."""
    _check_record(value, name, root, 9)
