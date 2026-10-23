# Fixture-completion clarifications

2026-10-23. Coordinator-authored narrow proposal for fresh independent review. These clarifications resolve ambiguities found while authoring independent fixtures for the R26 variant contracts. They change no mathematics, record shape or readiness policy beyond the readings below. All earlier sealed R26 documents and the merged variant proposal (equity-features PR 629 and its clarifications) remain unchanged. No freeze, implementation or runtime approval follows.

## 1. Group and span partition key

A flow group or span partition is one underlying and basis group within one Scope, one contract, and the complete admitted economic definition of its executions: right, strike, expiry and multiplier. Executions that share a `contract_id` but differ in any of those definition fields are different partitions: they are not members of each other's parent window, repeated-price or multi-venue subset, or span population. A Snapshot may therefore hold several definitions under one `contract_id`. This reads "one contract per partition" together with the sealed original's definition partition and the accepted cluster-partition correction (equity-features issue 533); it does not relax any identity check.

## 2. Group reason when a member premium is overflow

A group that has any member whose premium is unavailable, including a member whose own reason is `premium_overflow`, reports the group reason `premium_unavailable`. A `GroupObject` carries no member Core, so the member's own reason is not re-expressed at group level. A group whose summed premium itself overflows still reports `premium_overflow`. Receipt-level priority (`premium_overflow` before `premium_unavailable`) is unchanged.

## 3. Definition-basis mismatch pointer

An execution whose available Definition does not match the root's contract, scope, underlying, currency or bases, including `definition_basis_id`, is `identity_mismatch` at stage 6 at `/snapshot/executions/{e}/definition_use/definition_id`, where `{e}` is the actual execution index, using the first offending execution in declaration order.

## 4. Baseline frame horizon mismatch pointer

A historical or Current SessionFrame whose `horizon_id` differs from the BaselineOp's known `horizon_id` is `identity_mismatch` at stage 6 at `/request/operations/{o}/baseline_op_id`, where `{o}` is the actual operation index. A non-literal BaselineOp horizon keeps its existing malformed-horizon error.

## Not resolved here

The `observed_series` treatment of an incomplete selected common slot, and seven B3 snapshot pointers still marked inferred in the private fixture packet, remain open contract gaps. Fixtures carry no expectation for them until a reviewed clarification exists. Independent valid-parent and compound-error fixtures plus fresh independent review are required before these readings enter a frozen implementation handoff.
