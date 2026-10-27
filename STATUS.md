# Status (newest first)

## 2026-10-27 - Candidate5 phase A frozen as a post-release candidate
- Candidate5 phase A frozen (2542 of 2554 rows, 12 excluded, post-release fixture correction; record docs/r26-variants/CANDIDATE5_FREEZE_RECORD.md). Product owner accepted with conditions; independent freeze review approve-with-conditions. Frozen-subject-to-regeneration watch list (13 ids), gaps G1 to G6 (17 phase-non-asserted rows, graph evidence digest-level only, N4 scripts exit 0 on failure) and the controller's removed source-review gate are recorded; release notes must repeat them. Coordinator rulings decided, pending owner review.

## 2026-10-27 - S1 hygiene and S2 clarifications merged; candidate5 phase A approved, freeze pending
- S1 hygiene (PR 25) and S2 post-R26 clarifications (PR 26) merged. Candidate5 phase A source (30 of 31 rows fixed, 2 F4 rows undetermined) approved by an independent reviewer (work folder review of 2026-10-27). Contained run passed attempt 1 (83 s, 2554 rows, 2521 byte-identical, 33 changed). Audit verdict: approve-with-conditions. Replay: library 393/393 (393 of 397 rows run; 2 F4 rows excluded, 2 checkpoint rows belong to the workers layer), I/O 1757/1757, workers 76/76. Harnesses unreviewed; freeze proposal pending.
- Code gaps remain in workers validate_restore (missing-stream, request immutability, CP3 temporal order, K-regression placement, suffix checks) and the library field_set pointer; fixtures needed first. Nothing released.

## 2026-10-23 - R26 variants1 released as unqualified prerelease (tag r26-variants1-prerelease in all three repos; owner chose to skip Windows qualification, browser demo and candidate5; 31 fixture-defect rows excluded (18 library + 13 I/O, incl. 3 joint-output; earlier "28" omitted those 3); contract gaps open)

## 2026-10-23 - R26 candidate4 (N4 obligation fixtures) materialized and audited (mechanical)
- New N4 fixtures (63 cases: BOM, restore, DailyCore scope, rolling, PR 12 amendments; 4 flagged undetermined) authored, reviewed twice (fixes applied), contained attempt 4 passed first run (85 s): 2,554 rows, completion3 rows unchanged. Auditor run: 176 checks, 4 failing, all triaged as auditor limits (sampled ids); no candidate defect. Still unfrozen: contract gaps listed in OBLIGATIONS4_STATUS.md, docs PR for edited clarifications, freeze, layer workers. Nothing released.

## 2026-10-23 - R26 independent fixture candidate materialized (mechanical only)
- Third contained run passed (70.9 s, lease released, empty child tree): 2,466 rows = representative 25, baseline 153, flow 174, flow-residual 45, wire 1,803, identity graphs 266; counts equal the hand census. Two earlier attempts failed safely and exposed real defects (W3 standalone inventory; identity-graph preimage regression), both fixed and re-reviewed. Index status unqualified_candidate; contract_frozen false.
- Next: independent content/wire/numerical/coverage audit of the generated candidate; PR 12 amendments need their own fixtures and review; remaining clarification reviews (UTF-8 BOM, restore pointer, DailyCore scope, rolling endpoint); freeze; three fresh layer workers. Nothing released or published.

## 2026-10-22 - R26 variant fixture source (B3, F3, F4) source-approved with open clarifications
- Three review rounds by fresh read-only reviewers (records in the old workspace, the old private workspace, work/r26-20261021). Final state: B3 (153 cases, SHA 745d9e2c...), F3 (174, d4d4f551...), F4 (45, 75a53a4d...) pass static name/signature sweeps and have no open blocking finding. W3 (1,803 cases) approved earlier. All source-only, nothing executed.
- Coordinator rulings (pending owner review) in work/r26-20261021/COORDINATOR_RULINGS_20261022.md: partition by complete definition; group reason stays premium_unavailable; rolling cases unfrozen until clarification review; observed_series incomplete-slot behaviour is a contract gap (no case).
- PR 12 (merged) proposes two amendments (partition key, group reason) and one clarification (definition-basis pointer); open before freeze: their independent fixtures/review, the observed_series incomplete-slot gap and 7 inferred B3 pointers; review of UTF-8 BOM, restore pointer, DailyCore multi-Scope and rolling-endpoint clarifications; root aggregator/controller; contained generation and independent audit; fresh layer workers. Nothing released or published.

## 2026-10-22 - earlier checkpoint (superseded above)
- Fresh read-only reviews of the private completion3 fixture source rejected B3 (1 blocking: a bucket-key-mismatch case that does not mismatch) and F3 (2 blocking: no strike/right/expiry partition cases under one contract_id; flow_residual_cases.py unsealed). Correction authors were started; results need a fresh re-review.
- Not done: W3 pending clarification reviews (UTF-8 BOM, restore pointer, DailyCore multi-Scope), root aggregator/controller, contained generation, independent audit, literal freeze, layer workers. Nothing released or published.
