# Clarification 4: integer-op incomplete capture; /checkpoint and /config missing-member order; Q4 held

> SUPERSEDED in part (2026-10-27): the statement that fixtures must not assert premiums or signs under incomplete capture for an integer op is superseded by PUBLIC_SAFE_INTEGER_INCOMPLETE_PREMIUMS_SIGNS_ADDENDUM5.md (the Result still lists the ordinary premium objects and signs of the retained roots; only metrics and weights change).

Status: **proposed, needs independent review and PO ratification.** Docs only, no code and no fixture change. Author: Architect, 2026-10-27. Directed by PO_DECISION_CANDIDATE11 decisions (1), (2), (3). The PO had not read the contract text and stated "if the contract says otherwise, the contract wins"; this document performs that check. Support labels: GROUNDED (stated in contract/clarification text or enforced by the schema), CONVENTION-ONLY (consistent with text, chosen by us), GUESS (no support).

Read for this check: docs/r26 (FLOW_CONTRACT, MATHEMATICS, FEATURE_BINDINGS), the variants schema (`option_feature_contracts/variants1/schema.py`), the library (`variants1/integer_flow.py`, `current.py`, `results.py`), REPLAY_V7, and the workers `checkpoint.py`, `execute.py`, `run.py` (variants1, read-only).

## 1. Integer directional op under incomplete capture

PO-directed sentence: "For an integer directional op whose capture is incomplete (incomplete_capture), integer_weights is [] and each of contracts, trade_count, unavailable_premium_count and premium has status incomplete_capture with no value."

### Finding: the PO sentence CONTRADICTS the schema in one word and is incomplete in scope
- The public docs/r26 flow contract does not define the integer-price (i64) profile at all: no occurrence of `integer_weights`, `i64` or `incomplete_capture` in FLOW_CONTRACT, MATHEMATICS or FEATURE_BINDINGS. For the content of the sentence the contract text is **silent**.
- The variants schema is not silent on the Metric shape: `mstatus` is the closed set `available|undefined|unavailable|unsupported`; `incomplete_capture` is a **reason**, not a status. `_rule_metric` requires value null iff status is not available, and branch `not_evaluated` for any non-available metric. So "status incomplete_capture" is not a legal Metric; the legal form is status `unavailable`, reason `incomplete_capture`, branch `not_evaluated`, value null. GROUNDED (schema); CONTRADICTS the PO wording.
- Scope: the library emits all ten i64 metric ids as unavailable/incomplete_capture (contracts, trade_count, premium, ask, bid, unknown, unavailable_premium_count, signed_call, signed_put, tide), keeping monetary_basis on currency_ticks metrics. The PO list names four. A sentence naming four invites a fixture to assert the other six as something else. `current.py` does the same all-metrics shape for the current-day op (CUR_IDS).
- Receipt: the status/reason aggregate is unavailable/incomplete_capture because incomplete_capture ranks first among unavailable reasons (results.py UNAVAIL_PRIORITY; the ranking text is also cited in PUBLIC_SAFE_FIXTURE_COMPLETION_CLARIFICATION1). Ranking GROUNDED; applying it here CONVENTION-ONLY.
- integer_weights `[]`: the schema permits any list for the i64 profile (`_rule_directional` only forbids non-empty weights for other profiles), and IntegerWeight requires a premium Metric (no "absent" form). So the alternative "one entry per contract/expiry/strike key with premium absent" is not legal; the only legal alternative is entries whose premium Metric is unavailable. That needs member keys, but under incomplete capture membership is not certified, so no key set is defined. `[]` is the only form needing no invented key set. Library behaviour: `[]`. CONVENTION-ONLY (consistent with schema and the uncertified-membership principle; no sentence states it).
- Failing row in REPLAY_V7: the removed fixture expected 3 weights (contract, expiry, strike) with premium not_evaluated/incomplete_capture/unavailable and the metrics ordinary/ok/available while capture is incomplete. The metrics half is wrong on any reading (available metrics under incomplete capture contradict the receipt reason); the weights half has no text support. The library output is the better-supported reading.

Support summary: weights `[]` CONVENTION-ONLY; Metric status/reason/branch/value GROUNDED by schema; "all ten metrics" CONVENTION-ONLY following current.py and the library; the PO's "status incomplete_capture" is unsupportable as worded.

### Proposed final wording
"For an integer directional op (profile i64-paired-call-put1) whose capture is incomplete (the receipt reason is incomplete_capture), DirectionalObject.integer_weights is the empty list, and every Metric of the object (contracts, trade_count, premium, ask, bid, unknown, unavailable_premium_count, signed_call, signed_put, tide) has status unavailable, reason incomplete_capture, branch not_evaluated and no value; currency_ticks metrics keep their monetary_basis."

Alternative the PO may prefer (schema-legal, not recommended): one IntegerWeight per contract, expiry and strike key of the raw population with an unavailable/incomplete_capture/not_evaluated premium Metric. Cost: it needs a key set from an uncertified population and changes library behaviour (a code change, not a clarification of current behaviour).

Unlocks: re-authoring the removed rollup-wider row after its known-at defect (30 > signing 24) is fixed, and fixture coverage for (c-domain) and (c-completeness). Needs ratification first because the sentence is CONVENTION-ONLY.

## 2. /checkpoint and /config missing-member rows

Checked against FLOW_CONTRACT line 39 (stage 3: extra/missing keys reported before scalar decoding), the field_set pointer clarification (a direct-API root string is the record pointer), and the workers code.

| PO sentence | Verdict | Basis |
|---|---|---|
| (a) Checkpoint failing the key-set check is field_set at /checkpoint before CP0, CP1a, CP1b and CP2 | **Needs rewording**; substance GROUNDED by code, CONVENTION-ONLY at contract level | In `validate_restore` the key-set check IS CP0 (first statement: `validate_shape(checkpoint, "Checkpoint", "/checkpoint")`, then scalars). Nothing precedes it, so "before CP0" is incoherent; it does precede CP1a, CP1b, CP2 and CP3. The contract text does not order the key-set check against CP0-CP3; the pointer table gives pointer, code and stage only. |
| (b) /config reports field_set before the mode, concurrency and later checks | GROUNDED by code, CONVENTION-ONLY at contract level | `execute._check_config` runs `validate_shape(config, "ExecutionConfig", "/config")` first, then mode (`unsupported_mode`), resource fields (`unsupported_resources`), logical_task_bytes (`resource_limit`), then scalars; it runs before the `cohort_unverified`, inventory and producer-admission checks in `execute_variants` and `replay_variants`. The mode is read with `config.get`, so a missing member cannot raise KeyError first. |
| (c) The worker applies the shape check to config with root /config | GROUNDED by code (execute.py `_check_config`); CONVENTION-ONLY for the contract (root string listed in the pointer table, evidenced by no row until the extra-member row) | N4-restore-direct-config-extra-member exercises it. |
| (d) The checkpoint shape check runs before validate_restore | **CONTRADICTED by code; reject as worded** | The check runs inside `validate_restore` as CP0. In `execute_variants` restore mode, `_check_config`, `cohort_unverified`, inventory and admission checks run before `run_restore`, so a config/cohort/admission error outranks a malformed checkpoint. `validate_restore` takes no config. What holds: among restore checks, key-set is first. |

Proposed final wording (replaces (a) and (d); keeps (b) and (c)):
1. "A Checkpoint record that fails the stage-3 key-set check is reported as field_set at /checkpoint; the check is the first restore check, so it is reported before any CP1a, CP1b, CP2 or CP3 check. The worker maps it to input_invalid with cause_code field_set and cause_path /checkpoint."
2. "An ExecutionConfig that fails the stage-3 key-set check is reported as field_set at /config before the mode, resource-field, logical_task_bytes, scalar, cohort-verification, inventory and producer-admission checks. The worker maps it to input_invalid with cause_code field_set and cause_path /config."
3. "The worker entry applies the key-set check to the config with root string /config."
4. "In checkpoint_restore mode the worker validates the config, cohort and producer admission before it reads the checkpoint, so a Checkpoint key-set failure is reported only for an otherwise accepted config and cohort."

Sentence 4 states what the code does and is CONVENTION-ONLY; if the PO prefers the checkpoint to outrank config errors, that is a code change, not a clarification. Caveat: worker code read at option-feature-workers main (8795f3e) and worktree s12-restore-cp3; the checks cited are identical in both.

Unlocks: 2 workers rows (N4-restore missing-member for /checkpoint and /config; with one member of an otherwise valid record removed, the order above fixes the expected value). The tests for (c-domain)/(c-completeness) and the rollup-wider row are unlocked by section 1 (plus the known-at fix), not by this section.

Ungroundable items: none is a pure GUESS. CONVENTION-ONLY: section 1 weights and all-ten-metrics; section 2 sentences 1-4 at the contract level. Not accepted as worded: "status incomplete_capture" (1) and "before validate_restore" (2d).

## 3. Q4 (suffix stamped-position rule): remains HELD
PO decision (3), restated: no code and no fixture for Q4; equal stamped positions in a suffix stay identity_conflict as they are today; no sentence is added here. Q4 stays in the candidate11 HELD list for the release notes.
