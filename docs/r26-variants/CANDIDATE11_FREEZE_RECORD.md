# R26 variants: candidate11 freeze record (public-safe)

Status: candidate11 is recorded as a post-release candidate for the next release (2026-10-27), superseding the candidate9 freeze record for the fixtures it covers. R26 was released as r26-variants1-prerelease on 2026-10-23; this record corrects fixtures after that release. Coordinator rulings are "decided, pending owner review". Independent audits: candidate10 approve, candidate11 approve (the earlier auditor tooling could not be re-run). Independent freeze review: done (approve-with-conditions, conditions applied). This PR is not final until merged. Row content and the private work folder are not published; this record carries hashes, counts, exclusions by id, flags, gaps and open items.

## 1. Census
| file | sha256 | bytes | in file | frozen |
|---|---|---|---|---|
| representative.jsonl | 1e7cadcce4ef3c717e2feeb74a3142c64db908b432c93a4e2061d501099860e0 | 6183840 | 25 | 25 |
| baseline.jsonl | 6066098b3470ff373c5b86e1ee97f1d5d7a22cfc641a8662dd0b32b5a2e85a1c | 44818801 | 153 | 153 |
| flow.jsonl | 14efa0af86b76e51ecf580e6e98f57dbb02906f6fb890c736bfcfed74cf9abea | 24815750 | 174 | 174 |
| flow-residual.jsonl | 308cf98d20a662d2c833e5af7ae367d60743786d48ea0d0deeaf9d60b4ff7e52 | 9249713 | 53 | 53 |
| wire.jsonl | e98d6850b02dc62739049d6f0f1fb514912dcb6386c016610550829a810452f3 | 46510253 | 1810 | 1810 |
| obligations.jsonl | 4f0cee5234ae79e5aa42105372026934bc6a39440b4e4276f738a30af8070f15 | 13472247 | 85 | 85 |
| identity-graphs.jsonl | dd9051a2ce608807d4271db998ec3e014748a63884d546f26ea1a00563be4085 | 57535662 | 308 | 308 |
| index.json | 6f6e0f0ef22db02cd56674110a2a26f5916f36f98e1c75b9cb44d8e59b32f21b | 2201 | - | - |

Total bytes of the seven jsonl files: 202586266 (index.json not counted; candidate9: 200427336). 2608 rows in files (2300 non-graph + 308 graphs), case_ids unique. **Frozen: 2608** (2300 non-graph rows + 308 graphs), no exclusions. Candidate9 was 2594; +14 = 8 added rows (6 F4, 2 N4) + 6 added graphs. Against candidate9 by case_id (parsed from disk): 2594 identical, 0 changed, 14 added, 0 removed. The representative, baseline, flow and wire files are byte-identical to candidate9. Files are never edited. Verify whole-file sha256 first. The candidate root directory is named generated-completion-candidate5 (hardcoded by the pinned containment module) but holds candidate11 output: rely on the index.json hash, not the directory name.

Added ids: F4-parent-two-controls-{expected,nonexpected}-root-outside-second-domain, F4-span-two-controls-{expected,nonexpected}-root-outside-second-domain, F4-span-f4-root-also-unresolved-missing-definition, F4-rolling-f4-root-also-unresolved-missing-definition (6 rows plus 6 graphs IDENTITY4-<id>); N4-restore-direct-checkpoint-extra-member, N4-restore-direct-config-extra-member (2 rows, no graphs). Candidate10 (2610 rows, intermediate, not frozen) also held F4-rollup-wider-than-capture-domain-nonexpected-root-in-gap and its graph; candidate11 removed them (section 5, G10), so the net change from candidate9 is 16 - 2 = +14.

N4 frozen 85 = bom 20, restore 16, roll 16, dailycore 8, pr12 19, zero 1, premium 1, fieldset 4.

## 2. Consumer filter and exclusions
Structured keys only (freeze_excluded, non_asserted_subfields, contract_status), never substring search: the key 'mask' appears inside economic_literals on 55 rows and the string UNDETERMINED_CONTRACT_GAP appears in a provenance note.
Filter (rule unchanged): skip a row if `freeze_excluded` is true, or `contract_status == "UNDETERMINED_CONTRACT_GAP"`, or (obligations) `completeness != "complete"`. A row with a non-empty `non_asserted_subfields` must not assert those subfields. In candidate11 no row matches any of these (structured walk of all 2608 rows at any depth): freeze_excluded none, non_asserted_subfields none, status none; nothing is excluded, no id list exists, no graph is skipped. The 4 mode graphs (IDENTITY4-batch, -chronological_cut_replay, -checkpoint_restore, -admission-extension) have no source row and are frozen. A runnable filter is part of the release notes (section 8).

Excluded: none.

## 3. Frozen subject to regeneration (flagged; consumers must expect these ids may change)
Total 57 rows and 28 graphs, none excluded (candidate9: 49 rows and 22 graphs; candidate11 adds 8 rows and 6 graphs). The candidate9 list is unchanged and carried in full:
| ids (graph IDENTITY4-<id> unless noted) | depends on |
|---|---|
| N4-restore-accepted-nonK-nonCursor-request-field-changed (no graph) | ruling 6; limits.records is a fixture-author choice |
| N4-pr12-lane-interval-{closed-end-at-anchor-covers-both-partitions, ends-before-both-anchors, open-end-at-anchor-does-not-cover} (3 + 3 graphs) | ruling 8 |
| N4-roll-tie-{three-way-ordinals-reverse-of-ids, with-older-positive-below-lower-bound} (2 + 2) | ruling 1 |
| B3-integer-price-{contract-session1, pooled-divide-before-fold1, pooled-fold-before-divide1}-{relative_contracts, relative_trades, premium_robust_z} (9 + 9) | assumption 2 (PO product ruling); not regenerated under it |
| B-{contract-session1, pooled-divide-before-fold1, pooled-fold-before-divide1}-{relative_contracts, relative_trades, premium_robust_z} (9 rows, no graphs) | assumption 2; unchanged since candidate6, not regenerated |
| N4-roll-unresolved-{below-lower-bound-with-known-r, at-exclusive-lower-bound, inside-window, after-known-positive-endpoint} (4 + 4) | PR 34 Q1a reading B and Q1b |
| F4-parent-capture-domain-misses-tail, F4-span-inclusive-endpoint-not-captured (2 + 2) | PR 34 Q2a/Q2b/Q2c; PR 39 ratified items |
| F4-parent-two-roots-outside-capture-domain, F4-span-two-roots-outside-capture-domain (2 + 2) | Q2a/Q2b/Q2c per root; excluded_ids order not asserted; available_at_ns generator-computed |
| W3-fieldset-* (7 rows) | field_set parent pointer, INFERRED |
| N4-fieldset-direct-{snapshot,request}-{missing,extra}-member (4) | same INFERRED pointer at /snapshot and /request |
| N4-restore-missing-stream-dropped-retained-stream (1) | Q3, ratified as INFERRED (PR 37) |
| N4-restore-root-A-after-K-temporal-cut, N4-restore-temporal-cut-before-cursor-regression | CP3 order A>K before regression (PR 37 Q1) |
| N4-restore-root-A-after-K-temporal-cut-before-identity-conflict (1) | PO decision: temporal_cut wins over merge identity_conflict |
| N4-restore-regression-at-first-cursor-index-zero | existing rule; low risk |
| N4-premium-b64-negative-zero-price-rejected | P1 decided; pointer by precedent |
New in candidate11 (8 rows, 6 graphs):
| ids | depends on |
|---|---|
| F4-parent-two-controls-{expected,nonexpected}-root-outside-second-domain, F4-span-two-controls-{expected,nonexpected}-root-outside-second-domain (4 + 4) | PR 39 (b) intersection sentence (ratified); the second capture Control is built by the fixture author; available_at_ns generator-computed. The two expected rows failed before PR 42 and pass after it |
| F4-span-f4-root-also-unresolved-missing-definition (1 + 1) | PR 39 (a), partition wording; available_at_ns generator-computed |
| F4-rolling-f4-root-also-unresolved-missing-definition (1 + 1) | PR 39 (a) plus a reading of Q1a's incomplete-capture clause as stated; excluded_ids order not asserted; available_at_ns generator-computed |
| N4-restore-direct-{checkpoint,config}-extra-member (2, no graphs) | the INFERRED field_set pointer at the /checkpoint and /config roots; worker-level result only |

None of the new rows has independent semantic adjudication beyond the audits' source review. Settled and off the list: the 4 zero-price rows and graphs (PRs 30/31). The 9 W3-union unknown-tag rows still cite a draft section; contract section 13 independently gives stage 3.

## 4. Partial rows and masks
- Workers partial 32 = 20 doc_phase + 2 doc_checkpoint_phase + 10 W3-storage-nullability (unchanged from candidate9; the 2 added workers-owned rows are full). Nothing may assert doc_phase or doc_checkpoint_phase. The 32 was independently recomputed from the fixtures by the candidate9 freeze reviewer (not circular).
- 2 admission rows without expected receipt (W3-admission-monotone-extension, W3-admission-null-to-nonempty): compared via expected_publication only.
- 0 masked rows, 0 freeze_excluded rows.

## 5. Gaps
G1: doc_phase / doc_checkpoint_phase rows partial, never asserted (closed by design). G2: 2 admission rows without expected receipt. G3: 10 storage-nullability rows partial. G4: graph evidence digest-level only; edge structure, frozen_guard, receipt selectors, reference_cohort not evidenced; 4 mode graphs unevidenced. G5: I/O total is harness scope, asserted not derived. G6 to G8: closed.
G9 and G15a: partly closed: direct field_set rows exist for /snapshot, /request (candidate9) and now extra-member rows for /checkpoint and /config. MISSING-member rows for /checkpoint and /config remain undetermined and are not authored: no ruled sentence says a Checkpoint or ExecutionConfig failing the stage-3 key-set check is reported as field_set, stage 3, at /checkpoint or /config before the other checks, nor that the worker entry applies that check to config at all.
G10: partly closed: F4 root also unresolved (span, rolling) and several capture Controls (parent, span) now have rows; combinations, ties among excluded roots and excluded_ids order remain untested. The rollup-wider-than-domain row was authored in candidate10 and removed in candidate11 as UNDETERMINED: it had a fixable fixture defect and a contract gap (no frozen or passing row has an integer op under incomplete capture, so no convention exists for integer_weights entries or the count Metrics statuses there). Consequence: ratified items (c-domain) (F4 tested against Control event_domain, never rollup_interval) and (c-completeness) (rollup_interval not contained in every Control domain gives incomplete_capture) are NOT tested by any fixture until the missing sentence is ruled. The clause for a rollup_interval narrower than the capture domain stays HELD.
G11: no independent semantic adjudication of the new, returned and earlier new rows; audits judged from fixture text. G12: A>K before merge is pinned by one row; other temporal orderings and K-regression placement are unspecified. G13: K-regression placement and suffix checks (Q4) open. G14: closed (no expected-to-fail tags remain).
G15b: the 9 returned B rows and 9 B3-integer-price rows are not regenerated under assumption 2. G16: CLOSED: the two-control latent defect (expected roots tested against control 0 only, domain test skipped for span) is fixed by PR 42 after two-control fixtures were authored; every candidate9 row is unchanged in candidate11. G17: held clause (narrower rollup_interval). G18: Q4 held. G19: F4 available_at_ns values are generator-computed, not quoted. G20: closed. G21: the v8 harnesses and the controller have no independent review.
G22: the integer-op incomplete-capture sentence is missing (what integer_weights holds and the statuses of contracts, trade_count, unavailable_premium_count). G23: the rolling F4-also-unresolved row rests on a reading of Q1a. G24: the second capture Control of the two-control rows is fixture-author built; no ratified text pins how two capture Controls on one op are admitted (rows pass on current code).

Mandatory non-claim: numeric, wire and earliest-error correctness is not claimed beyond the audits and the replays; the new rows are fixture-author derived from clarification texts and rulings, not from implementation code.

## 6. Merged PRs and commits
option-features: PR 30 (bz token, a48ef1c), 31 (exact zero price, ed3597d), 33 (747ae7f), 34 (ca6e2ab), 35 (F4 exclusion dependency, 4e87bc6), 36 (field_set parent pointer, 9ecd68e), 37 (restore CP3 clarification 2, 29c0cb1), 38 (candidate8 record, e9ae6e5), 39 (F4 capture-edge clarification 3, 6a81e65; header now ratified, held clause HELD), 40 (candidate9 record, d03ab42), 41 (synthetic-only browser demo, e462cf0), 42 (every capture Control's event_domain, 4e82136). option-feature-io: PR 8 (codec, e156963). option-feature-workers: PR 8 (82aac59), PR 9 (8795f3e). Version stays 0.1.0a1.

## 7. Evidence (replay v8; replay of record on merged mains option-features 4e82136, io e156963, workers 8795f3e; python -I -B, fresh output dirs, fixtures read-only, all exit 0, 0 failures, no expected-to-fail list)
| layer | rows | run | passed | failed | skipped | partial |
|---|---|---|---|---|---|---|
| library (4 files) | 405 | 403 | 403 | 0 | 2 (workers-owned E-checkpoint) | 0 |
| N4 library | 49 | 49 | 49 | 0 | 0 | - |
| graphs | 308 | 304 | 304 | 0 | 4 mode graphs | - |
| I/O | 1764 | 1764 | 1764 | 0 | 0 | 0 |
| workers (85 owned) | 85 | 85 | 85 | 0 | 0 | 32 |

Graph passes: baseline 106, flow 143, flow-residual 21, obligations 34. Stage-3 field_set rows 795 of 795 (789 wire, 4 N4-fieldset, 2 N4-restore-direct); type_mismatch rows 756 of 756. Harness sha256: replay5_library_v8.py 94cc36e9bde59c86a6faef6bc4558e4c1cbf4658e608547945956d6784482220; replay5_library_n4_v8.py 5a11803bf058cdf431780df8de9513e40d772bbc8b60322341746a32ca15733d; replay5_library_n4_graphs_v8.py df28a10077648b8bbf9c36ab72d518e0eff0ba21d4b4fdc98adc05179fe42db5; replay_io_c5_v8.py 051898aebe8f523631e691204f6c8ab4abaf7c46f76061e6d5820f51db4ab53d; replay_workers_c5_v8.py 2c808c726d8436f4ff945eea5f14f2944eb3a45a1b8a2e577f841f3700cfe294. Provenance note: the v8 graph harness first run crashed on a trailing print after its results were computed; it was then edited and rerun clean with the same counts, so all harnesses exit 0 holds for the rerun. Mutation proof for all five v8 harnesses (one altered value each, each exit 1) shows each harness can fail, not coverage.

## 8. Controller, provenance and release-notes items
Controller sha256 fdc9945f938dbd5ec61631f976015ae4d9f62c785a457980e4db9a9c9e5c8681; manifest sha256 e98eb20a8869e75a1d2212b09c786222bc8a1173c75f4f46947299fb1c854de5. It is the candidate10 controller (461bc3fd7d8951beacd2c78d8efd339799bf262a29f8437192cb4a19e46e7156) with only docstring, names, source dir and description strings changed (both audits: no safeguard removed). Deviations carried from candidates 5, 6, 8 and 9 and accepted by the coordinator: source-review approval gate removed (NO independent review of the controller), 6 source receipts removed, contract path restriction removed, manifest-name check relaxed, second in-validate scheduling-lock check removed, glob check of the 12-module set added. Attempt 1 passed. Accepted risk: no independent controller review; release notes must disclose it.

Release-notes items (to publish with the release):
1. The consumer filter as runnable code (section 2), re-issued with the candidate11 hashes and counts.
2. The 57 flagged rows and 28 graphs (section 3) with the ruling each depends on.
3. Controller disclosure: no independent review of the controller.
4. Plainly: the new, changed and returned rows have no independent semantic adjudication; the field_set parent pointer and the Q3 pointer are INFERRED.
5. Assumption 2 is a product ruling not derived from the private boundary text; it covers the 9 B3-integer-price rows and the 9 returned B rows.
6. Graph evidence is digest-level only; the 4 mode graphs are unevidenced.
7. Coverage statement: /checkpoint and /config missing-member rows are absent; (c-domain) and (c-completeness) are ratified but untested; the held clause and Q4 are HELD; excluded_ids order is not asserted.

## 9. Post-release status and rulings (decided, pending owner review)
Post-release fixture correction candidate for the next release (target r26-variants2-prerelease, still a PRERELEASE). Coordinator: candidate11 supersedes candidate9 as the post-release candidate; the rollup-wider row is removed as UNDETERMINED (it needs a ruled sentence for integer ops under incomplete capture and had a fixable fixture defect); controller deviations are accepted as before; no row is excluded. Not qualified: the PO's qualified-release criteria (Windows qualification on python-flint, duckdb and setuptools wheels; demo works; two-control fix landed with frozen rows unchanged [done, PR 42]; /checkpoint and /config coverage present or scoped out in the notes; no flagged id undisclosed; owner accepts) are not all met, and the word "qualified" must not be used.

## 10. Open PO items
Q4 (suffix checks) held; narrower-rollup clause held; ruling for the integer-op incomplete-capture sentence; rulings for the /checkpoint and /config missing-member sentences; owner items: PyPI download permission for Windows qualification, qualification scope, release acceptance and label, review of decisions pending owner review, worktree cleanup.

## 11. Conditions to freeze
Met: hashes, counts, bytes re-read from disk; no structured exclusion key; replay of record on merged mains; harness hashes and mutation proof; controller deviations accepted; audits approve. Independent freeze review: done (approve-with-conditions, conditions applied); condition 6 met. Candidate11 is not final until this PR is merged.
