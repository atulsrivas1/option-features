# R26 variants: candidate6 freeze record (public-safe)

Status: candidate6 is FROZEN as a post-release fixture correction (2026-10-27), superseding the candidate5 freeze record for the fixtures it covers. R26 was released as r26-variants1-prerelease on 2026-10-23; this freeze corrects fixtures after that release. Coordinator rulings are "decided, pending owner review". Independent freeze review: approve-with-conditions (no blocker; conditions applied in proposal rev 2). Independent audit: approve-with-conditions. Row content and the private work folder (r26-20261027) are not published; this record carries hashes, counts, exclusions by id, flags, masks, gaps and open items.

## 1. Census
| file | sha256 | bytes | in file | frozen |
|---|---|---|---|---|
| representative.jsonl | 1e7cadcce4ef3c717e2feeb74a3142c64db908b432c93a4e2061d501099860e0 | 6183840 | 25 | 16 |
| baseline.jsonl | 6066098b3470ff373c5b86e1ee97f1d5d7a22cfc641a8662dd0b32b5a2e85a1c | 44818801 | 153 | 153 |
| flow.jsonl | 14efa0af86b76e51ecf580e6e98f57dbb02906f6fb890c736bfcfed74cf9abea | 24815750 | 174 | 174 |
| flow-residual.jsonl | 260e5e15c1cafe757c9c48ab7720979fe44f73d23f85e961cb079b7d4c2616df | 7928432 | 45 | 43 |
| wire.jsonl | 983db76dc426b74fff4247cb01079627b9ffd6a8a08a0f9aaf684399c2294718 | 46431944 | 1803 | 1803 |
| obligations.jsonl | 3758210abddc5deac9a7093a587ffa9e823be549a5854aae96f4d17792738018 | 12749980 | 73 | 69 |
| identity-graphs.jsonl | b4a6f34ccc8559cd5e901d47a09408e8aa6f555da5ee9e267d71e2c22a5e6f6a | 56669603 | 300 | 294 |
| index.json | 398279d60d6358352465f516340186f0cfc7c3d17896ec7a868ad695d16723c1 | n/a | - | - |

Total bytes of the seven jsonl files: 199598350. 2573 rows in files (2273 non-graph + 300 graphs). **Frozen: 2552** (2258 non-graph rows + 294 graphs) = 2573 - 12 excluded (section 2) - 9 held rows (section 3). Against candidate5 by case_id: 2524 identical, 30 changed, 19 added, 0 removed. Files are never edited; exclusion is by id. Verify whole-file sha256 first; there is no filtered-file hash. The candidate root directory is named generated-completion-candidate5 (hardcoded by the pinned containment module) but holds candidate6 output: rely on the index.json hash, not the directory name.

Consumer filter: skip a row if `freeze_excluded` is true, or `contract_status == "UNDETERMINED_CONTRACT_GAP"`, or (obligations) `completeness != "complete"` (the 4 masked N4 rows have completeness "complete"; `freeze_excluded` catches them), or its id is in the section 3 list. Identity graphs: 296 of 300 carry `source_case_id`, always equal to the `IDENTITY4-` suffix and always mapping to a source row; the 4 mode graphs (IDENTITY4-batch, -chronological_cut_replay, -checkpoint_restore, -admission-extension) have neither the key nor a source row and are not excluded. Two equivalent methods, which agree on all 296: skip `IDENTITY4-<excluded case_id>` by prefix, or skip graphs whose `source_case_id` is excluded.

## 2. Exclusions in the files (12, tagged freeze_excluded and UNDETERMINED_CONTRACT_GAP)
- flow-residual: F4-parent-capture-domain-misses-tail, F4-span-inclusive-endpoint-not-captured. Masked (non_asserted_subfields): Evidence.excluded_ids, Evidence.dependencies concerning the excluded root, Evidence.available_at_ns. Asserted: the root is not a member, incomplete capture, no new error code, population incomplete.
- obligations: N4-roll-unresolved-below-lower-bound-with-known-r, N4-roll-unresolved-at-exclusive-lower-bound, N4-roll-unresolved-inside-window, N4-roll-unresolved-after-known-positive-endpoint. Masked: Evidence.excluded_ids, Evidence.available_at_ns.
- identity graphs of those 6 (IDENTITY4-<case_id>): 6 (graphs hash every field, including masked ones).
Masked values are still emitted but unvalidated; nothing may assert them. No other row or graph references an excluded id (reviewer full-text check). Frozen but not library-run: 2 E-checkpoint rows (workers-owned).

## 3. Held rows tagged out of the freeze by id (9; coordinator ruling, record only, fixtures unchanged)
UNDETERMINED_CONTRACT_GAP, resting on assumption 2 (a prior-day source Result gets Definition/context), which the product owner HELD; the private boundary text was not located. All in representative.jsonl; none has an identity graph (so 9 rows, 0 graphs):
B-contract-session1-relative_contracts, B-contract-session1-relative_trades, B-contract-session1-premium_robust_z, B-pooled-divide-before-fold1-relative_contracts, B-pooled-divide-before-fold1-relative_trades, B-pooled-divide-before-fold1-premium_robust_z, B-pooled-fold-before-divide1-relative_contracts, B-pooled-fold-before-divide1-relative_trades, B-pooled-fold-before-divide1-premium_robust_z.
They return by a later candidate or an explicit coordinator note if the text is found. The similarly named baseline rows (B3-integer-price-<same stems>, 9 rows with 9 graphs) are not tagged by this ruling and stay frozen.

## 4. Frozen subject to regeneration (flagged; consumers must expect these ids may change)
| case_id (graph IDENTITY4-<id> unless noted) | depends on |
|---|---|
| N4-restore-accepted-nonK-nonCursor-request-field-changed (no graph) | ruling 6 (Request immutability rejected); the field choice limits.records is a fixture-author choice |
| N4-pr12-lane-interval-closed-end-at-anchor-covers-both-partitions, N4-pr12-lane-interval-ends-before-both-anchors, N4-pr12-lane-interval-open-end-at-anchor-does-not-cover | ruling 8 (per-partition lane binding deferred; interval coverage only); regenerate if binding lands |
| N4-roll-tie-three-way-ordinals-reverse-of-ids, N4-roll-tie-with-older-positive-below-lower-bound | ruling 1 (tie order by event_ns, admission_ordinal) |
| N4-zero-price-session-known-zero-root, N4-roll-zero-price-known-zero-inside-window, N4-roll-zero-price-complete-empty-all-known-zero, N4-roll-tie-with-known-zero-at-same-event-ns | ruling 7 and PRs 30/31 (+0.0 admitted via bz, exact zero gives branch ordinary); -0.0 stays rejected, P1 open |

10 rows and 9 graphs (19), none excluded. None of the 10 has independent semantic adjudication. Settled and off the list: N4-roll-two-positive-rows-tied-at-r (and graph), N4-bom-fefff-inside-json-string-is-ordinary-character, A-positive-current. The 9 W3-union unknown-tag rows still cite POST_R26 section 8 (draft); contract section 13 independently gives stage 3.

## 5. Partial rows and masks
17 doc_phase / doc_checkpoint_phase rows (E-checkpoint 2, W3-restore 5, W3-admission 3, N4-restore 7) and 10 W3-storage-nullability rows: 27 partial in the workers layer; nothing may assert doc_phase. Rows with a non-empty non_asserted_subfields must not be asserted on those subfields (6 rows, all excluded). FEFF additive fields id_note and candidate6_check are documentation only.

## 6. Evidence (replay of record at option-features ed3597d; option-feature-io 9f7b468; option-feature-workers 5f8b4d0; v3 harnesses, python -I -B, fresh output dirs, all exit 0)
| layer | rows | run | passed | failed | skipped | partial |
|---|---|---|---|---|---|---|
| library (4 files) | 397 | 393 | 393 | 0 | 4 | 0 |
| I/O (1737 wire + 20 N4-bom) | 1757 | 1757 | 1757 | 0 | 4 | 0 |
| workers | 77 | 77 | 77 | 0 | 0 | 27 |
| N4 library rows | 44 | 40 | 40 | 0 | 4 | - |
| N4 graph digests | 300 | 290 | 290 | 0 | 10 (6 excluded, 4 mode) | - |

At the earlier commit a48ef1c (PR 30 only) the N4 rows were 36/40 and graphs 286/290: four exact-zero-price rows failed, fixed by PR 31. Graph evidence is DIGEST-LEVEL only; edge structure, frozen_guard, receipt selectors and reference_cohort are not evidenced and the 4 mode graphs are unevidenced. Mutation checks (one altered value per harness, each exit 1) show each harness can fail; they do not prove coverage. Mandatory non-claim stays: numeric, wire and earliest-error correctness is not claimed beyond the audit and these replays; the 10 new rows come from rulings and independent helpers, not from implementation code.

Harness sha256: replay5_library_v3.py 8d28cba4e4c20e183e1dbd6fa29f8a1fb8bdb93e9a4993504bf5546e96dbaffc; replay5_library_n4_v3.py 6ad8e276494392d81929d86f5b08d1a50eadd9da155bc1b4e6b1c066289eeeed; replay5_library_n4_graphs_v3.py 976b457eeef327f10bee3623eb981841289face3ccfc0e320c844219ca668847; replay_io_c5_v3.py 8e24694f8891a756a63254b428de34d09eb74e18e6f3beaded04855c12515d53; replay_workers_c5_v3.py 6c721244b83c99a59154387b6f84722c5f4d2e12d61cc16c22a0ca7a6d3def73.

## 7. Code commits
PR 30 (bz token: +0.0 admitted, -0.0 rejected invalid_scalar stage 4), main a48ef1c. PR 31 (exact zero price gives PremiumCore branch ordinary; underflow_to_zero only when a positive product rounds to zero), commit 6e69ba4, merge ed3597d, 2026-10-27. Version stays 0.1.0a1; no R25 identity change.

## 8. Controller and provenance
Controller run_completion_candidate6.py sha256 4815289a87140ccaa4673277ebb4bc3df53b461c551ef676c4ae6613d81b9390; manifest 3038401b5da7705fea8f44c54741f926748cec8ba2c903bd70d5f6786e2f044f; attempt 1 passed (85 s). Deviations from the original controller (unchanged from candidate5, accepted by the coordinator): source-review approval gate removed (no independent controller review), 6 source receipts removed, contract path restriction removed, manifest-name check relaxed to "beside controller", second in-validate scheduling-lock check removed, check added that local *.py equal the 12-module set. Candidate6 differs from the candidate5 controller only in docstring, containment module name, source dir and operation labels. Accepted risk: no independent controller review; release notes must disclose it. Stale-copy move: candidate6-source was copied from candidate5-source and carried a stale copy of the candidate5 output; to pass the never-overwrite check it was moved (not deleted) to a private stale folder; it is byte-identical to candidate5's own output. candidate5-source is untouched.

## 9. Gaps and accepted risks
G1: 17 rows carry doc_phase / doc_checkpoint_phase, never asserted (closed by design, ruling 5); partial everywhere. G2: W3-admission-monotone-extension and W3-admission-null-to-nonempty have no expected receipt. G3: 10 storage-nullability rows partial. G4: graph evidence digest-level only; 4 mode graphs unevidenced. G5: I/O total 1757 is harness scope, asserted not derived. G6: closed; N4 scripts exit non-zero on failure and were rerun at ed3597d. G7: closed; zero-price fix covered on all layers (workers exercise no exact-zero prices). G8: masked content (6 rows) is emitted but unvalidated; unmasking needs P2 and P3 and regeneration of 6 rows and 6 graphs.

## 10. Open product-owner items (post-R26)
- P1: -0.0: admit with canonicalization to +0.0 (needs a code change in f2b/canonical.py) or keep rejecting. Today it is rejected; no fixture authors -0.0.
- P2: wording for F4 Evidence.excluded_ids, the exclusion dependency and available_at_ns.
- P3: wording for the N4 no-r envelope excluded_ids (known-zero roots only or every full-session root) and available_at_ns (maximum over all dependencies or a named subset).

Neither blocks the freeze; they block unmasking.

## 11. Rulings (decided, pending owner review)
Controller deviations accepted; 2552 rows frozen; 9 held B rows tagged out by id; 19 flagged rows and graphs frozen subject to regeneration; -0.0 stays rejected pending P1; masks used instead of hardening guesses on 6 rows; graph evidence digest-level; post-release status as above.

## 12. Next
P1 to P3; private boundary text for the 9 held rows; contract wording for excluded_ids; workers restore code gaps (missing-stream, CP3 temporal order, K-regression placement, suffix checks) now that fixtures exist or need authoring; field_set pointer code gap; Windows qualification; browser demo.
