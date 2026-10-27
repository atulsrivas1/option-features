# R26 variants: candidate9 freeze record (public-safe)

Status: candidate9 is recorded as a post-release candidate for the next release (2026-10-27), superseding the candidate8 freeze record for the fixtures it covers. R26 was released as r26-variants1-prerelease on 2026-10-23; this record corrects fixtures after that release. Coordinator rulings are "decided, pending owner review". Independent audit: approve-with-conditions (the earlier auditor tooling could not be re-run). An independent freeze review of the proposal is required before the freeze is final. Row content and the private work folder are not published; this record carries hashes, counts, exclusions by id, flags, gaps and open items.

## 1. Census
| file | sha256 | bytes | in file | frozen |
|---|---|---|---|---|
| representative.jsonl | 1e7cadcce4ef3c717e2feeb74a3142c64db908b432c93a4e2061d501099860e0 | 6183840 | 25 | 25 |
| baseline.jsonl | 6066098b3470ff373c5b86e1ee97f1d5d7a22cfc641a8662dd0b32b5a2e85a1c | 44818801 | 153 | 153 |
| flow.jsonl | 14efa0af86b76e51ecf580e6e98f57dbb02906f6fb890c736bfcfed74cf9abea | 24815750 | 174 | 174 |
| flow-residual.jsonl | 34a5ae8be360fb57446762692b4dc7452816d10eb6879845a94877e26c683d7a | 8255640 | 47 | 47 |
| wire.jsonl | e98d6850b02dc62739049d6f0f1fb514912dcb6386c016610550829a810452f3 | 46510253 | 1810 | 1810 |
| obligations.jsonl | 660eab9c850d837b25ab345f7e580f9e9b314f6730dde3f8104e658c3e481acb | 12960254 | 83 | 83 |
| identity-graphs.jsonl | c2784e78e0c1bc9efc932fc4c0b2d8fb3698c62570c4640139518d1450e94b5a | 56882798 | 302 | 302 |
| index.json | 1e64b4c0100c21b76601c8a1e5ea05ba7006b5ce50629ec382e9ad0f6913e77c | 2201 | - | - |

Total bytes of the seven jsonl files: 200427336 (index.json not counted; candidate8: 199810458). 2594 rows in files (2292 non-graph + 302 graphs), case_ids unique. **Frozen: 2594** (2292 non-graph rows + 302 graphs), no exclusions. Candidate8 was 2575; +19 = 7 added rows (5 N4 + 2 F4) + 2 added graphs + the former missing-stream row + the 9 returned held rows. Against candidate8 by case_id: 2584 identical, 1 changed, 9 added, 0 removed. The representative, baseline, flow and wire files are byte-identical to candidate8. Files are never edited. Verify whole-file sha256 first. The candidate root directory is named generated-completion-candidate5 (hardcoded by the pinned containment module) but holds candidate9 output: rely on the index.json hash, not the directory name.

N4 frozen 83 = bom 20, restore 14, roll 16, dailycore 8, pr12 19, zero 1, premium 1, fieldset 4.

## 2. Consumer filter and exclusions
Filter (rule unchanged): skip a row if `freeze_excluded` is true, or `contract_status == "UNDETERMINED_CONTRACT_GAP"`, or (obligations) `completeness != "complete"`. A row with a non-empty `non_asserted_subfields` must not assert those subfields. In candidate9 no row matches any of these (checked over all 7 files): nothing is excluded, no id list exists, no graph is skipped. Consumers that skipped the 9 held ids for candidate8 must not skip them for candidate9. The 4 mode graphs (IDENTITY4-batch, -chronological_cut_replay, -checkpoint_restore, -admission-extension) have no source row and are frozen.

Excluded: none. The former excluded row N4-restore-missing-stream-dropped-retained-stream is unmasked (checkpoint_cut_mismatch at /request/cut_cursors; pointer INFERRED, PO ratified) and frozen, flagged. The 9 held representative rows return to the freeze set under ratified assumption 2 (section 10) and are flagged: B-contract-session1-{relative_contracts, relative_trades, premium_robust_z}, B-pooled-divide-before-fold1-{same three}, B-pooled-fold-before-divide1-{same three}.

## 3. Frozen subject to regeneration (flagged; consumers must expect these ids may change)
Total 49 rows and 22 graphs, none excluded (candidate8: 32 rows and 20 graphs; candidate9 adds 17 rows and 2 graphs).
| ids (graph IDENTITY4-<id> unless noted) | depends on |
|---|---|
| N4-restore-accepted-nonK-nonCursor-request-field-changed (no graph) | ruling 6 (Request immutability rejected); limits.records is a fixture-author choice |
| N4-pr12-lane-interval-{closed-end-at-anchor-covers-both-partitions, ends-before-both-anchors, open-end-at-anchor-does-not-cover} (3 + 3 graphs) | ruling 8, interval coverage only |
| N4-roll-tie-{three-way-ordinals-reverse-of-ids, with-older-positive-below-lower-bound} (2 + 2 graphs) | ruling 1 |
| B3-integer-price-{contract-session1, pooled-divide-before-fold1, pooled-fold-before-divide1}-{relative_contracts, relative_trades, premium_robust_z} (9 + 9 graphs) | assumption 2 (PO product ruling); not regenerated under it |
| the 9 returned B representative rows listed in section 2 (9 rows, no graphs) | assumption 2 (PO product ruling); rows unchanged since candidate6 |
| N4-roll-unresolved-{below-lower-bound-with-known-r, at-exclusive-lower-bound, inside-window, after-known-positive-endpoint} (4 + 4 graphs) | PR 34 Q1a reading B and Q1b |
| F4-parent-capture-domain-misses-tail, F4-span-inclusive-endpoint-not-captured (2 + 2 graphs) | PR 34 Q2a/Q2b/Q2c; PR 39 ratified items |
| F4-parent-two-roots-outside-capture-domain, F4-span-two-roots-outside-capture-domain (2 + 2 graphs) | Q2a/Q2b/Q2c per root; excluded_ids order not asserted; available_at_ns values are generator-computed |
| W3-fieldset-* (7 rows, no graphs) | field_set parent-pointer ruling, INFERRED |
| N4-fieldset-direct-{snapshot,request}-{missing,extra}-member (4 rows, no graphs) | the same INFERRED pointer at the /snapshot and /request roots |
| N4-restore-missing-stream-dropped-retained-stream (1 row, no graph) | Q3, ratified as INFERRED (PR 37) |
| N4-restore-root-A-after-K-temporal-cut, N4-restore-temporal-cut-before-cursor-regression | CP3 order A>K before regression (PR 37 Q1) |
| N4-restore-root-A-after-K-temporal-cut-before-identity-conflict (1 row, no graph) | PO decision: temporal_cut at /request/knowledge_K_ns wins over the later merge identity_conflict |
| N4-restore-regression-at-first-cursor-index-zero | existing rule; low risk |
| N4-premium-b64-negative-zero-price-rejected | P1 decided (-0.0 rejected, invalid_scalar stage 4); pointer by precedent |

None of the candidate9 rows has independent semantic adjudication beyond the audit's source review. Settled and off the list: the 4 zero-price rows and graphs (PRs 30/31). The 9 W3-union unknown-tag rows still cite a draft section; contract section 13 independently gives stage 3.

## 4. Partial rows and masks
- Workers partial 32 = 20 doc_phase + 2 doc_checkpoint_phase + 10 W3-storage-nullability (candidate8: 30; the 2 added doc_phase rows are the missing-stream row and the A>K-before-merge row). Nothing may assert doc_phase or doc_checkpoint_phase. The worker learned 32 on a first run (placeholder 0) and then pinned it. A substring search of the fixtures corroborates 20 doc_phase and 2 doc_checkpoint_phase rows; the 10 nullability rows were not recomputed. An independent recompute from the fixtures is owed.
- 2 admission rows without expected receipt (W3-admission-monotone-extension, W3-admission-null-to-nonempty): compared via expected_publication only.
- 0 masked rows, 0 freeze_excluded rows.
- Additive documentation-only fields (id_note, candidate6_check, candidate9_new, candidate9_unmasked) are not asserted.

## 5. Gaps
G1: doc_phase / doc_checkpoint_phase rows partial, never asserted (closed by design). G2: 2 admission rows without expected receipt. G3: 10 storage-nullability rows partial. G4: graph evidence digest-level only (record/work/result node digests); edge structure, frozen_guard, receipt selectors, reference_cohort not evidenced; 4 mode graphs unevidenced. G5: I/O total is harness scope, asserted not derived. G6, G7: closed. G8: closed (missing-stream unmasked, passing on workers PR 9). G9: partly closed: direct field_set rows exist for /snapshot and /request; /checkpoint and /config direct-root rows are NOT authored. G10: partly closed: two F4 two-roots rows added; no rows for an F4 root that is also unresolved, several capture Controls, or a rollup wider than the capture domain (all ratified in PR 39, not yet authored; the several-Controls rows need two-capture_ids builder support); excluded_ids order unasserted. G11: no independent semantic adjudication of the new, changed and returned rows; the earlier auditor tooling could not be re-run. G12: A>K before merge is now pinned by one row; other temporal orderings and K-regression placement are unspecified. G13: K-regression placement and suffix checks (Q4) open. G15: the 9 returned rows and 9 B3 rows are not regenerated under assumption 2. G16: two-control latent defect (flow.py:42 tests expected roots against control 0 only, span.py:68 skips the domain test) contradicts the ratified PR 39 sentence (b); fix pending two-control fixtures that must fail first, then a separate code PR that leaves every frozen row byte-identical. G17: held clause on a rollup_interval narrower than the capture domain (non-expected root): no row, sentence or code. G18: Q4 held. G19: the F4 available_at_ns values are generator-computed. G20: the 32 workers-partial count is pinned, not independently derived. G21: the v6 harnesses and the controller have no independent review.

Mandatory non-claim: numeric, wire and earliest-error correctness is not claimed beyond the audit and the replays; the new rows are fixture-author derived from clarification texts and rulings, not from implementation code.

## 6. Merged PRs and commits
option-features: PR 30 (bz token, a48ef1c), 31 (exact zero price, ed3597d), 33 (field_set pointer clarification, 747ae7f), 34 (rolling/F4 clarification, ca6e2ab), 35 (F4 exclusion dependency, 4e87bc6), 36 (field_set parent pointer, 9ecd68e), 37 (restore CP3 clarification 2, 29c0cb1), 38 (candidate8 freeze record, e9ae6e5), 39 (F4 capture-edge clarification 3, 6a81e65; merged text still reads "proposed"; PO ratified items a, b, c-domain, c-completeness, d; the c-held clause is HELD). option-feature-io: PR 8 (codec, e156963). option-feature-workers: PR 8 (restore CP3 A>K before regression, 82aac59), PR 9 (missing-stream first in CP3, A>K before merge, 8795f3e). Version stays 0.1.0a1.

## 7. Evidence (replay v6; replay of record on merged mains option-features 6a81e65, io e156963, workers 8795f3e; python -I -B, fresh output dirs, fixtures read-only, all exit 0, 0 failures)
| layer | rows | run | passed | failed | skipped | partial |
|---|---|---|---|---|---|---|
| library (4 files) | 399 | 397 | 397 | 0 | 2 (workers-owned E-checkpoint) | 0 |
| N4 library | 49 | 49 | 49 | 0 | 0 | - |
| graphs | 302 | 298 | 298 | 0 | 4 mode graphs | - |
| I/O | - | 1764 | 1764 | 0 | 0 | 0 |
| workers (83 owned) | 83 | 83 | 83 | 0 | 0 | 32 |

N4 families: roll 16, dailycore 8, pr12 19, zero 1, premium 1, fieldset 4. Graph passes: baseline 106, flow 143, flow-residual 15, obligations 34. Harness sha256: replay5_library_v6.py 6c0a72e2a0eb7f1757b0baf5d6fe0ba6cc41ff0a9dbffd855bca1b3aa21cf54f; replay5_library_n4_v6.py 16211e3c080f9d5a3df48d7207324b1f60d04dbc6efdb1c8e880047e9c759c83; replay5_library_n4_graphs_v6.py 6efec35212c315e03f44715da118df6ffdab0a4ce43f0bd376e4d27305b46d55; replay_io_c5_v6.py fe5bc69886df4520d0fc3ceda4fa90be64cb2671b698921458cb7ea5e627d8c1; replay_workers_c5_v6.py fa414dcfc0d4261597941d872d4c2ae207485218d23d1ba91c51281800fa286b. Mutation proof for all five v6 harnesses (one altered value each, each exit 1) shows each harness can fail, not coverage.

## 8. Controller and provenance
Controller run_completion_candidate9.py sha256 29787cb54f8c0bc56e4c6ebf3a4b4fb7e750d2d3d55b8c870cacf79136ad6460; manifest sha256 a8d23c273115b9182765f1af48685802405925e9592bf203761362f8edab300b. It is the candidate8 controller with only docstring, containment module name, source dir and operation labels changed (audit: no safeguard removed). Deviations carried from candidates 5, 6 and 8 and accepted by the coordinator: source-review approval gate removed (NO independent review of the controller), 6 source receipts removed, contract path restriction removed, manifest-name check relaxed, second in-validate scheduling-lock check removed, glob check of the 12-module set added. Attempt 1 passed. Accepted risk: no independent controller review; release notes must disclose it.

## 9. Release-notes items (to publish with the release)
1. The consumer filter as runnable code (section 2).
2. The 49 flagged rows and 22 graphs (section 3) with the ruling each depends on.
3. Controller disclosure: no independent review of the controller (section 8).
4. Plainly: the new, changed and returned rows have no independent semantic adjudication; the field_set parent pointer and the Q3 pointer are INFERRED.
5. The 9 B3-integer-price baseline rows and the 9 returned B representative rows share assumption 2, a product ruling not derived from the private boundary text.
6. Graph evidence is digest-level only; the 4 mode graphs are unevidenced.

## 10. Post-release status and rulings (decided, pending owner review)
Post-release fixture correction candidate for the next release. Coordinator: candidate9 is the post-release candidate; controller deviations are accepted as before; the 9 held B rows return to the freeze set under the ratified assumption 2 (Definition/context-only for bucket-proof prior-day source Results; a PO product ruling, not derived from the private boundary text; if reversed, the flagged B3 rows/graphs and the returned rows are regenerated); no row is excluded. Q4 is held; the PR 39 held clause is held.

## 11. Open PO items
Q4 (suffix checks) held; PR 39 held clause (narrower rollup) held; a docs edit to record the PR 39 ratification in its merged text; /checkpoint and /config root strings; the excluded_ids order claim in the docs; owner acceptance of decisions pending owner review; downloads for Windows qualification need owner permission.

## 12. Next
1. Two-control fixtures (must fail on current code), then the flow.py:42 / span.py:68 domain fix in a separate PR.
2. Direct-root /checkpoint and /config rows; F4 unresolved-root and rollup-wider rows.
3. Windows qualification (needs owner permission for downloads), browser demo, release notes (section 9).
4. Q4 stays held.
