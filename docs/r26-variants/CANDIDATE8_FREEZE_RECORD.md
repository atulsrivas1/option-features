# R26 variants: candidate8 freeze record (public-safe)

Status: candidate8 is FROZEN as a post-release candidate for the next release (2026-10-27), superseding the candidate6 freeze record for the fixtures it covers. R26 was released as r26-variants1-prerelease on 2026-10-23; this freeze corrects fixtures after that release. Coordinator rulings are "decided, pending owner review". Independent freeze review: approve-with-conditions (no blocker; conditions applied in proposal rev 2). Independent audit: approve-with-conditions. Row content and the private work folder are not published; this record carries hashes, counts, exclusions by id, flags, masks, gaps and open items.

## 1. Census
| file | sha256 | bytes | in file | frozen |
|---|---|---|---|---|
| representative.jsonl | 1e7cadcce4ef3c717e2feeb74a3142c64db908b432c93a4e2061d501099860e0 | 6183840 | 25 | 16 |
| baseline.jsonl | 6066098b3470ff373c5b86e1ee97f1d5d7a22cfc641a8662dd0b32b5a2e85a1c | 44818801 | 153 | 153 |
| flow.jsonl | 14efa0af86b76e51ecf580e6e98f57dbb02906f6fb890c736bfcfed74cf9abea | 24815750 | 174 | 174 |
| flow-residual.jsonl | a6d349c7d9d91d3305386b833b997bed2c86a13eaeab3da55054eff9a02f1c3b | 7927798 | 45 | 45 |
| wire.jsonl | e98d6850b02dc62739049d6f0f1fb514912dcb6386c016610550829a810452f3 | 46510253 | 1810 | 1810 |
| obligations.jsonl | 4ae79faaa61455667f4c8b9aae5542fdb8e25242b755e86682f59b30561fe1b3 | 12884105 | 78 | 77 |
| identity-graphs.jsonl | 5899f3a704d5335b82cc1e41290c914cc37425305ef484459133b8cd23f96bed | 56669911 | 300 | 300 |
| index.json | c94afe1f2bb1824e22a1ece523b647c2fcda4d4815d933534e8dac41374e7d4f | 2201 | - | - |

Total bytes of the seven jsonl files: 199810458 (index.json not counted; candidate6: 199598350). 2585 rows in files (2285 non-graph + 300 graphs), case_ids unique. **Frozen: 2575** (2275 non-graph rows + 300 graphs) = 2585 - 1 excluded (section 2) - 9 held rows (section 3). Candidate6 was 2552; +23 = 11 frozen added rows + 12 formerly excluded items back (6 rows, 6 graphs). Against candidate6 by case_id: 2563 identical, 10 changed, 12 added, 0 removed. Files are never edited; exclusion is by id. Verify whole-file sha256 first; there is no filtered-file hash. The candidate root directory is named generated-completion-candidate5 (hardcoded by the pinned containment module) but holds candidate8 output (attempt 2): rely on the index.json hash, not the directory name.

N4 frozen 77 = bom 20, restore 12 (of 13), roll 16, dailycore 8, pr12 19, zero 1, premium 1.

## 2. Consumer filter and exclusions
Filter: skip a row if `freeze_excluded` is true, or `contract_status == "UNDETERMINED_CONTRACT_GAP"`, or (obligations) `completeness != "complete"`, or its id is in the section 3 list. Identity graphs: skip `IDENTITY4-<excluded case_id>` (by prefix) or any graph whose `source_case_id` is excluded; 296 of 300 graphs carry `source_case_id`, always equal to the suffix; the 4 mode graphs (IDENTITY4-batch, -chronological_cut_replay, -checkpoint_restore, -admission-extension) have neither and are frozen. A row with a non-empty `non_asserted_subfields` must not assert those subfields.

Excluded (1 row, 0 graphs): N4-restore-missing-stream-dropped-retained-stream (obligations). It is the only row with `freeze_excluded`, `UNDETERMINED_CONTRACT_GAP` and `non_asserted_subfields` (expected_error.code, expected_error.path, expected_worker_error.cause_code, expected_worker_error.cause_path). Reason: the rejection's error code and pointer are not ratified (open item Q3); current workers accept a dropped stream. It has no identity graph, so no graph is skipped today. The 6 rows masked in candidate6 (4 N4-roll-unresolved-*, F4-parent-capture-domain-misses-tail, F4-span-inclusive-endpoint-not-captured) and their 6 graphs are UNMASKED and FROZEN, flagged (section 4).

## 3. Held rows tagged out of the freeze by id (9; coordinator ruling, record only, fixtures unchanged)
Assumption 2 (a prior-day source Result gets Definition/context) is STILL HELD by the product owner. All in representative.jsonl, no identity graph:
B-contract-session1-relative_contracts, B-contract-session1-relative_trades, B-contract-session1-premium_robust_z, B-pooled-divide-before-fold1-relative_contracts, B-pooled-divide-before-fold1-relative_trades, B-pooled-divide-before-fold1-premium_robust_z, B-pooled-fold-before-divide1-relative_contracts, B-pooled-fold-before-divide1-relative_trades, B-pooled-fold-before-divide1-premium_robust_z.
They return by a later candidate or explicit coordinator note. The 9 baseline B3-integer-price-* rows share assumption 2 but stay frozen and flagged (section 4).

## 4. Frozen subject to regeneration (flagged; consumers must expect these ids may change)
Total 32 rows and 20 graphs, none excluded. None has independent semantic adjudication beyond source review.
| ids (graph IDENTITY4-<id> unless noted) | depends on |
|---|---|
| N4-restore-accepted-nonK-nonCursor-request-field-changed (no graph) | ruling 6 (Request immutability rejected); limits.records is a fixture-author choice |
| N4-pr12-lane-interval-{closed-end-at-anchor-covers-both-partitions, ends-before-both-anchors, open-end-at-anchor-does-not-cover} (3 + 3 graphs) | ruling 8, interval coverage only |
| N4-roll-tie-{three-way-ordinals-reverse-of-ids, with-older-positive-below-lower-bound} (2 + 2 graphs) | ruling 1 |
| B3-integer-price-{contract-session1, pooled-divide-before-fold1, pooled-fold-before-divide1}-{relative_contracts, relative_trades, premium_robust_z} (9 + 9 graphs) | assumption 2, held |
| N4-roll-unresolved-{below-lower-bound-with-known-r, at-exclusive-lower-bound, inside-window, after-known-positive-endpoint} (4 + 4 graphs) | PR 34 rulings: Q1a reading B (every full-session root in excluded_ids), Q1b (available_at_ns = max known_at_ns); decided, pending owner review |
| F4-parent-capture-domain-misses-tail, F4-span-inclusive-endpoint-not-captured (2 + 2 graphs) | PR 34 Q2a/Q2b/Q2c (exclusion dependency) |
| W3-fieldset-* (7 rows, no graphs) | field_set parent-pointer ruling, INFERRED (contract states no explicit rule); the slash/tilde row also depends on the pointer not being escaped or truncated |
| N4-restore-root-A-after-K-temporal-cut, N4-restore-temporal-cut-before-cursor-regression | CP3 order A>K before regression (PR 37, text still "proposed"). Caveat on the first: root A>K versus merge (identity_conflict) order is NOT pinned; the row must not be read as asserting it |
| N4-restore-regression-at-first-cursor-index-zero | existing rule; low risk |
| N4-premium-b64-negative-zero-price-rejected | P1 decided (-0.0 rejected, invalid_scalar stage 4); the pointer is by precedent |

Settled and off the list: the 4 zero-price rows and their graphs (PRs 30/31, exact zero gives branch ordinary). The 9 W3-union unknown-tag rows still cite POST_R26 section 8 (draft); contract section 13 independently gives stage 3.

## 5. Masks and partial rows
- 1 masked row (the missing-stream row), also freeze_excluded; no unskipped row carries a mask.
- Workers partial 30 = 18 doc_phase + 2 doc_checkpoint_phase + 10 W3-storage-nullability; nothing may assert doc_phase or doc_checkpoint_phase. Library and I/O: 0 partial.
- 2 admission rows without expected receipt (W3-admission-monotone-extension, W3-admission-null-to-nonempty): compared via expected_publication only.
- FEFF additive fields id_note and candidate6_check are documentation only.

## 6. Gaps
G1: doc_phase / doc_checkpoint_phase rows partial, never asserted (closed by design). G2: 2 admission rows without expected receipt. G3: 10 storage-nullability rows partial. G4: graph evidence digest-level only (record/work/result node digests); edge structure, frozen_guard, receipt selectors, reference_cohort not evidenced; 4 mode graphs unevidenced. G5: I/O total is harness scope, asserted not derived. G6: closed (N4 scripts exit non-zero on failure). G7: closed; workers do not exercise exact-zero prices. G8: masked content gap is 1 row (missing-stream), open pending Q3. G9: no direct-API field_set fixtures (the 7 W3-fieldset rows enter only through the codec, which cannot reach /snapshot, /request, /checkpoint, /config). G10: F4 and rolling edge cases untested beyond single shapes (no combinations, no ties among excluded roots; excluded_ids order unasserted). G11: no independent semantic adjudication of the new rows beyond source review. G12: restore coverage is carve-out only (root A>K before regression; other temporal orderings and K-regression ordering unspecified). G13: missing-stream, K-regression placement and suffix checks (Q4) open; the missing-stream row is excluded and unevidenced. G14: expected-to-fail tags of candidates 7/8 lived only in private change notes; all cleared by the replay; the slash/tilde outcome is evidenced by the replay only.

Mandatory non-claim: numeric, wire and earliest-error correctness is not claimed beyond the audit and the replays; the new rows are fixture-author derived from clarification texts and rulings, not from implementation code.

## 7. Merged PRs and commits
option-features: PR 30 (bz token, a48ef1c), PR 31 (exact zero price, ed3597d), PR 33 (field_set pointer clarification, 747ae7f), PR 34 (rolling/F4 clarification, ca6e2ab), PR 35 (F4 exclusion dependency, 4e87bc6), PR 36 (field_set parent pointer, 9ecd68e), PR 37 (restore CP3 clarification 2, 29c0cb1; text still "proposed", Q3/Q4 not ratified). option-feature-io: PR 8 (codec, e156963). option-feature-workers: PR 8 (restore CP3 A>K before regression, 82aac59). Version stays 0.1.0a1.

## 8. Evidence (REPLAY_V5; replay of record on merged mains option-features 9ecd68e, io e156963, workers 82aac59; python -I -B, fresh output dirs, fixtures read-only, all exit 0)
| layer | rows | run | passed | failed | skipped | partial |
|---|---|---|---|---|---|---|
| library (4 files) | 397 | 395 | 395 | 0 | 2 (workers-owned E-checkpoint) | 0 |
| N4 library | 45 | 45 | 45 | 0 | 0 | - |
| graphs | 300 | 296 | 296 | 0 | 4 mode graphs | - |
| I/O | 1765 | 1764 | 1764 | 0 | 1 (missing-stream) | 0 |
| workers (82 owned) | 82 | 81 | 81 | 0 | 1 (missing-stream) | 30 |

I/O stage-3 field_set: 789 pass (751 W3-field, 27 W3-union, 4 W3-wire, 7 W3-fieldset). Harness sha256: replay5_library_v5.py 420bed967f635589e3b25b22987ece8f20b36289bbd9c43abebe65b1792f379c; replay5_library_n4_v5.py c286a8433f4b4e77967c121fb2b18215c87b24f3d8030decb46556bdb30ff80f; replay5_library_n4_graphs_v5.py 555d0350525278a66a7dae258c098837ef3cd75f820300264b122540a60d5626; replay_io_c5_v5.py 68dcd45a54e8694e11a2606e196c7d17ca1ec58e2fe25b7fbc1aa5b421319585; replay_workers_c5_v5.py 92e5b82026af5ecc506d67181202b78370141061197f42ed237c1d1bec99bc5c. Mutation checks (one altered value per harness, each exit 1) show each harness can fail; they do not prove coverage. Audit: 171 checks, 23 failing (known script limits, no genuine failure, no semantic validation).

## 9. Controller and provenance
Controller run_completion_candidate8.py sha256 603cab179e130157c41543400142930f3ae122fe56050a9adc81ae7b128775ca; manifest sha256 d4cf945cb239f3b6f2672f237f419feed092bfe06a01e79a84c23f7e5ce347e6. It is the candidate6 controller adapted: only docstring, containment module name, source dir and operation labels differ (the audit diff shows only name/path/hash changes). Deviations carried from candidates 5/6 and accepted by the coordinator: source-review approval gate removed (NO independent review of the controller), 6 source receipts removed, contract path restriction removed, manifest-name check relaxed, second in-validate scheduling-lock check removed, glob check of the 12-module set added. Attempt 1 failed on a defective row builder (partial output moved, not deleted, to a private stale folder); attempt 2 passed. Accepted risk: no independent controller review; release notes must disclose it.

## 10. Release-notes items
The consumer filter as runnable code; the flagged ids (32 rows, 20 graphs) with the ruling each depends on; the controller's missing independent review.

## 11. Post-release status and rulings (decided, pending owner review)
Post-release fixture correction candidate for the next release. Controller deviations accepted (as candidate6); 9 held B rows stay tagged out (assumption 2 held); the missing-stream row stays excluded; 2575 rows frozen; flagged list 32 rows and 20 graphs frozen subject to regeneration; graph evidence digest-level.

## 12. Open PO items
1. Q3: missing-stream rejection code and pointer (proposed checkpoint_cut_mismatch at /request/cut_cursors; not ratified); blocks unmasking the excluded row and needs a workers code change.
2. Q4: suffix-check rule (known-at half least supported); no row authored.
3. Assumption 2 boundary text for the 9 held B rows.
4. Next work: direct-API field_set fixture family, F4/rolling edge-case fixtures, Windows qualification, browser demo, release notes.
