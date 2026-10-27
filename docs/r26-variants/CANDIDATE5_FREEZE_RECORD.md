# R26 variants: candidate5 phase A freeze record (public-safe)

Status: candidate5 phase A is FROZEN as a post-release fixture correction (2026-10-27). R26 was released unqualified as r26-variants1-prerelease on 2026-10-23, skipping candidate5; this freeze corrects fixtures after that release. The coordinator rulings are "decided, pending owner review". Independent freeze review: approve-with-conditions (no blocker). Product owner: accepted with conditions (all recorded here). Independent audit: approve-with-conditions. Row content and the private work folder (r26-20261027) are not published; this record carries hashes, counts, exclusions, gaps and the regeneration watch list.

## 1. Census
| file | sha256 | bytes | in file | frozen |
|---|---|---|---|---|
| representative.jsonl | 6ce3233e92e98e0e43769da412bf2b9c4bd4d934240f27aaa8fbd4d1b5b519a1 | 6183832 | 25 | 25 |
| baseline.jsonl | 6066098b3470ff373c5b86e1ee97f1d5d7a22cfc641a8662dd0b32b5a2e85a1c | 44818801 | 153 | 153 |
| flow.jsonl | 14efa0af86b76e51ecf580e6e98f57dbb02906f6fb890c736bfcfed74cf9abea | 24815750 | 174 | 174 |
| flow-residual.jsonl | 491353e35ad8048027c9205ee39f3ddc1b9c382195c4ab6e5284d5aeeb50a1c6 | 8004140 | 45 | 43 |
| wire.jsonl | 436b51aaa09d80643d38ba50373316e82bebc0b5480e624c4d03e6e97f6a5f78 | 46431912 | 1803 | 1803 |
| obligations.jsonl | c20c7e7054abe89d663d013994dd4d74a0580bc8b9b38e4e928cdf2a688d601a | 10606232 | 63 | 59 |
| identity-graphs.jsonl | 94be1826f7e0c118ddd264e427d324a18d39f0720961f95b6cb3896531b38061 | 55495911 | 291 | 285 |
| index.json | 6e7facee9d76872370c77ef531eb8a0f7fa840f633bde9fecd66a5a6c1875dea | n/a | - | - |

2554 rows in files; 2542 frozen (2257 non-graph rows + 285 graphs); 12 excluded. Against candidate4: 2521 identical, 33 changed, none added or removed. Frozen rows are unchanged; files are never edited. Verify whole-file sha256 first; there is no filtered-file hash.

Consumer filter: skip a row if `freeze_excluded` is true, or `contract_status == "UNDETERMINED_CONTRACT_GAP"`, or (obligations) `completeness != "complete"`; for identity graphs skip `IDENTITY4-<excluded case_id>`.

## 2. Exclusions (12)
- flow-residual: F4-parent-capture-domain-misses-tail, F4-span-inclusive-endpoint-not-captured (UNDETERMINED_CONTRACT_GAP: membership of a visible root that is neither expected nor covered under incomplete capture is unstated).
- obligations: N4-roll-unresolved-below-lower-bound-with-known-r, N4-roll-unresolved-at-exclusive-lower-bound, N4-roll-unresolved-inside-window, N4-roll-unresolved-after-known-positive-endpoint (rolling envelope members and signs under uncertified r are unspecified).
- identity graphs of those 6 cases (IDENTITY4-<case_id>): 6.
No frozen row references an excluded id (full-text check by the reviewer; shared digests not checked). Frozen but not library-run: 2 E-checkpoint rows (workers-owned).

## 3. Frozen subject to regeneration (watch list)
Consumers must expect these ids may change in the next candidate.
| case_id | depends on |
|---|---|
| N4-roll-two-positive-rows-tied-at-r | POST_R26 section 2.4 (proposed): tie member order |
| IDENTITY4-N4-roll-two-positive-rows-tied-at-r | same ruling (graph of that row) |
| A-positive-current | Binding/context not added for bucket-proof rows; contract silent (assumption 1) |
| B-contract-session1-relative_contracts, B-contract-session1-relative_trades, B-contract-session1-premium_robust_z | assumption 1; prior-day source Result gets Definition/context (assumption 2) |
| B-pooled-divide-before-fold1-relative_contracts, B-pooled-divide-before-fold1-relative_trades, B-pooled-divide-before-fold1-premium_robust_z | assumptions 1 and 2 |
| B-pooled-fold-before-divide1-relative_contracts, B-pooled-fold-before-divide1-relative_trades, B-pooled-fold-before-divide1-premium_robust_z | assumptions 1 and 2 |
| N4-bom-fefff-inside-json-string-is-ordinary-character | FEFF: invalid_scalar, stage 4, pointer /envelope/payload/rights by analogy; no text states the pointer (assumption 3) |
13 ids. Also noted: the 9 W3-union unknown-tag rows cite POST_R26 section 8 (draft); contract section 13 independently gives stage 3.

## 4. Evidence
| layer | rows | run | passed | failed | note |
|---|---|---|---|---|---|
| library | 397 | 393 | 393 | 0 | 4 skipped (2 E-checkpoint, 2 F4 undetermined) |
| I/O | 1757 | 1757 | 1757 | 0 | 1737 wire + 20 N4-bom |
| workers | 76 | 76 | 76 | 0 | 49 full, 27 partial (17 G1, 10 G3) |
Library-owned N4 31/31. Hardened v2 harnesses were each mutation-checked (one flipped expected value detected). Graphs: 281/281 pass a DIGEST-LEVEL check only; edge structure, frozen_guard, receipt selectors, reference_cohort and the 4 mode graphs are not evidenced, so graphs must not be read as validated. The mandatory non-claim stays: numeric, wire and earliest-error correctness is not claimed beyond the audit and these replays.
Harness sha256: replay5_library_v2.py d366e8e075631a1683a2e968262aab92100877fe36492d990e14650bb51f9b30; replay_io_c5_v2.py feed5fd4754516cedc10db79c7c6107c22ad2a66bf4b5952ba68520c694bb1b0; replay_workers_c5_v2.py 65f6f8484dacff856dd1a432761c4dcb9551b12d0faec3571847a7eb0ab77dc0; replay5_library_n4.py a7c7157945afb39bd1135265e1018de0d7aa580abb03df7b09069b5bca95ff4c; replay5_library_n4_graphs.py 534e0770ced30a6d6b7b4acb5fd3b1085cf69d6d510bf629981a44d6cf10daf9. v1 harness results are withdrawn.
Controller: run_completion_candidate5.py 4c2985588dabccd2eafbf44e9756b7ed3e3c7a65bbd44125c6c2d9cea30e18a3; manifest 719a8346e10177d266568a0bcdbc4ebd8676a56b4d24a335b09102ab427ed873.

## 5. Gaps and accepted risks
- G1: 17 rows (E-checkpoint 2, W3-restore 5, W3-admission 3, N4-restore 7) have phase/checkpoint_phase non-asserted (documentation only; the code exposes no phase). Nothing may assert on it; the rows count as partial.
- G2: two W3-admission rows have no expected receipt; compared via expected publication only.
- G3: 10 storage-nullability rows are partial (not constructible in DuckDB; error code checked, stored compare skipped).
- G4: graph evidence is digest-level only; 4 mode graphs unevidenced.
- G5: the I/O total 1757 is harness scope, asserted not derived.
- G6: the two N4 replay scripts exit 0 even when rows fail. They were mutation-checked (30/31, 29/31, graph 1 fail) but must not be used as exit-code gates until fixed; read the printed summary.
- Controller: the candidate5 controller dropped the source-review approval gate and has no independent controller review (also 6 source receipts, the contract path restriction, a second scheduling-lock check; the manifest name check was relaxed). The hash-pinned manifest and containment module compensate. Release notes must disclose this.

## 6. POST_R26 clarifications
docs/r26-variants/PUBLIC_SAFE_POST_R26_CLARIFICATIONS.md: git blob f01de71b11de1b1b494eb2f2b3cb648818a5633f, file sha256 2c68709f76d91d5984c7da0eb63f568915bf8738c50dc556914cea5b175a4957, merged in 4daa4ef67232299a1801a0fd33757752a7633c75 (PR 26). It is a draft proposed for independent review, not ratified.

## 7. Coordinator rulings (decided, pending owner review)
Controller deviations accepted; assumptions 1, 3, 5 accepted; G6 added and N4 scripts recorded as mutation-checked; the 2542 rows frozen unchanged; G1 rows partial everywhere; regeneration watch list kept by case_id; graph evidence digest-level only; storage-nullability rows partial.

## 8. Next
Contract clarifications for the watch-list rows, phase B fixtures for the S2 rulings, workers and N4 harness hardening, qualification, demo.
