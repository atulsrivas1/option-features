# R26 variants: candidate12 freeze record (public-safe)

Status: candidate12 is recorded as a post-release candidate for the next release (2026-10-27), superseding the candidate11 freeze record for the fixtures it covers. R26 was released as r26-variants1-prerelease on 2026-10-23; this record corrects fixtures after that release. Coordinator rulings are "decided, pending owner review". Independent audit: candidate12 approve. Independent freeze review of candidate12: done (approve-with-conditions, conditions applied; an independent re-run of the five v9 harnesses matched). This PR is not final until merged. Row content and the private work folder are not published; this record carries hashes, counts, exclusions by id, flags, gaps and open items.

## 1. Census
| file | sha256 | bytes | in file | frozen |
|---|---|---|---|---|
| representative.jsonl | 1e7cadcce4ef3c717e2feeb74a3142c64db908b432c93a4e2061d501099860e0 | 6183840 | 25 | 25 |
| baseline.jsonl | 6066098b3470ff373c5b86e1ee97f1d5d7a22cfc641a8662dd0b32b5a2e85a1c | 44818801 | 153 | 153 |
| flow.jsonl | 14efa0af86b76e51ecf580e6e98f57dbb02906f6fb890c736bfcfed74cf9abea | 24815750 | 174 | 174 |
| flow-residual.jsonl | eddc4090a30703b5f1246ed364fafd1961e9c72a473de520d74d16b9b26164ed | 9534396 | 55 | 55 |
| wire.jsonl | e98d6850b02dc62739049d6f0f1fb514912dcb6386c016610550829a810452f3 | 46510253 | 1810 | 1810 |
| obligations.jsonl | 2fce5f5637d2e453357158e093b72b1a8d42e53d60f10ed7f6d0dcd268c4289f | 13984540 | 87 | 87 |
| identity-graphs.jsonl | fc45131815038ae00c24124e71136619eff93f879f7a892ddce922ec9153aad6 | 57721593 | 310 | 310 |
| index.json | 4e2f642851ff5107e9eb917cf92855fa6b630158f78eee8e6b761a0501744c02 | 2201 | - | - |

Total bytes of the seven jsonl files: 203569173 (index.json not counted; candidate11: 202586266). 2614 rows in files (2304 non-graph + 310 graphs), case_ids unique. **Frozen: 2614** (2304 non-graph rows + 310 graphs), no exclusions. Candidate11 was 2608; +6 = 4 added rows (2 F4, 2 N4) + 2 added graphs (candidate9 was 2594, +20). Against candidate11 by case_id (parsed from disk): 2608 identical, 0 changed, 6 added, 0 removed. The representative, baseline, flow and wire files are byte-identical to candidate11. Files are never edited. Verify whole-file sha256 first. The candidate root directory is named generated-completion-candidate5 (hardcoded by the pinned containment module) but holds candidate12 output: rely on the index.json hash, not the directory name.

Added ids: F4-rollup-wider-than-capture-domain-nonexpected-root-in-gap (re-authored; it was removed in candidate11 as UNDETERMINED) and F4-rollup-wider-than-capture-domain-no-gap-root-completeness-only, each with a graph IDENTITY4-<id>; N4-restore-direct-checkpoint-missing-member and N4-restore-direct-config-missing-member (2 rows, no graphs).

N4 frozen 87 = bom 20, restore 18, roll 16, dailycore 8, pr12 19, zero 1, premium 1, fieldset 4.

## 2. Consumer filter and exclusions
Structured keys only (freeze_excluded, non_asserted_subfields, contract_status), never substring search: the key 'mask' appears inside economic_literals on 55 rows and the string UNDETERMINED_CONTRACT_GAP appears in a provenance note.
Filter (rule unchanged): skip a row if `freeze_excluded` is true, or `contract_status == "UNDETERMINED_CONTRACT_GAP"`, or (obligations) `completeness != "complete"`. A row with a non-empty `non_asserted_subfields` must not assert those subfields. In candidate12 no row matches any of these (structured walk of all 2614 rows at any depth): nothing is excluded, no id list exists, no graph is skipped. The 4 mode graphs (IDENTITY4-batch, -chronological_cut_replay, -checkpoint_restore, -admission-extension) have no source row and are frozen. A runnable filter is part of the release notes (section 8).

Excluded: none.

## 3. Frozen subject to regeneration (flagged; consumers must expect these ids may change)
Total 61 rows and 30 graphs, none excluded (candidate11: 57 rows and 28 graphs; candidate12 adds 4 rows and 2 graphs). The candidate11 list is carried in full (see CANDIDATE11_FREEZE_RECORD.md section 3: restore request-field row; pr12 lane-interval rows (3 + 3); roll-tie rows (2 + 2); B3-integer-price rows (9 + 9) and the 9 returned B rows under assumption 2; roll-unresolved rows (4 + 4); F4 capture-domain-misses-tail and span-inclusive-endpoint rows (2 + 2); F4 two-roots rows (2 + 2); W3-fieldset rows (7); N4-fieldset direct rows (4); missing-stream row (1); the CP3 A>K rows (3); restore regression-at-index-zero (1); the b64 negative-zero row (1); two-control rows (4 + 4); F4-root-also-unresolved rows (1 + 1 span, 1 + 1 rolling); restore direct extra-member rows (2)). New in candidate12:
| ids | depends on |
|---|---|
| F4-rollup-wider-than-capture-domain-nonexpected-root-in-gap, F4-rollup-wider-than-capture-domain-no-gap-root-completeness-only (2 + 2 graphs) | the ratified Clarification 4 item for an integer op under incomplete capture (integer_weights empty, ten metrics unavailable with reason incomplete_capture; ratified as INFERRED, convention-only) and Addendum 5 (premiums and signs of the retained root; ratified as an INFERRED convention whose only frozen precedent is a b64 row, not an integer-op row); the ratified F4 items (c-domain) and (c-completeness); available_at_ns generator-computed |
| N4-restore-direct-{checkpoint,config}-missing-member (2, no graphs) | Clarification 4 shape-order items (INFERRED, code-grounded): key-set check first at /checkpoint; /config field_set before the other config checks; config, cohort and admission validated before the checkpoint is read; worker-level result only |

None of the new rows has independent semantic adjudication beyond the audit, which checked them against their own provenance notes. Settled and off the list: the 4 zero-price rows and graphs (PRs 30/31).

## 4. Partial rows and masks
- Workers partial 32 = 20 doc_phase + 2 doc_checkpoint_phase + 10 W3-storage-nullability (unchanged; the 2 added workers-owned rows are full; workers full 55 of 87). Nothing may assert doc_phase or doc_checkpoint_phase.
- 2 admission rows without expected receipt (W3-admission-monotone-extension, W3-admission-null-to-nonempty): compared via expected_publication only.
- 0 masked rows, 0 freeze_excluded rows.

## 5. Gaps
G1: doc_phase / doc_checkpoint_phase rows partial, never asserted (closed by design). G2: 2 admission rows without expected receipt. G3: 10 storage-nullability rows partial. G4: graph evidence digest-level only (306 of 310); edge structure, frozen_guard, receipt selectors, reference_cohort not evidenced; 4 mode graphs unevidenced. G5: I/O total is harness scope, asserted not derived. G6 to G8: closed.
G9 and G15a: closed for coverage: extra-member and missing-member direct-root rows exist for /checkpoint and /config (worker-level result only); the sentences are ratified as inferred. G10: partly closed: (c-domain) and (c-completeness) are now tested by the two rollup rows; combinations, ties among excluded roots and excluded_ids order remain untested. G11: no independent semantic adjudication of the new rows; the earlier auditor tooling could not be re-run. G12: A>K before merge is pinned by one row; other temporal orderings and K-regression placement unspecified. G13: K-regression placement and suffix checks (Q4) open. G14: closed.
G15b: the 9 returned B rows and 9 B3-integer-price rows are not regenerated under assumption 2. G16: closed (PR 42). G17: held clause (narrower rollup_interval). G18: Q4 held. G19: F4 available_at_ns values are generator-computed, not quoted. G20: closed. G21: the v9 harnesses and the controller have no independent review. G22: closed in substance (the integer-op incomplete-capture sentence is ratified as inferred). G23: the rolling F4-also-unresolved row rests on a reading of Q1a. G24: the second capture Control of the two-control rows is fixture-author built.
G25: the two rollup rows rest on a ratified INFERRED convention; no integer-op row confirms it independently. G26: the two restore missing-member rows rest on inferred ordering sentences with no independent adjudication.
Remaining: Q4 held; narrower-rollup clause held; 2 W3-admission rows without expected receipt; no independent controller review; graph evidence digest-level with 4 mode graphs unevidenced; no direct-API roots beyond /snapshot, /request, /checkpoint and /config exist (not applicable).

Mandatory non-claim: numeric, wire and earliest-error correctness is not claimed beyond the audits and the replays; the new rows are fixture-author derived from clarification texts and rulings, not from implementation code.

## 6. Merged PRs and commits
option-features code: PR 30 (a48ef1c), 31 (ed3597d), 35 (4e87bc6), 36 (9ecd68e), 42 (4e82136). Docs: PR 37 (29c0cb1), 39 (6a81e65), 44 (Clarification 4, 601ddca), 45 (Addendum 5, 0f37caa); candidate11 record PR 43 (88c38ae). Demo: PR 41 (e462cf0). option-feature-io: PR 8 (e156963). option-feature-workers: PR 8 (82aac59), PR 9 (8795f3e). Version stays 0.1.0a1.

## 7. Evidence (replay v9; replay of record on merged mains option-features 0f37caa, io e156963, workers 8795f3e; python -I -B, fresh output dirs, fixtures read-only, all exit 0, 0 failures, no expected-to-fail list)
| layer | rows | run | passed | failed | skipped | partial |
|---|---|---|---|---|---|---|
| library | 407 | 405 | 405 | 0 | 2 (workers-owned E-checkpoint) | 0 |
| N4 library | 49 | 49 | 49 | 0 | 0 | - |
| graphs | 310 | 306 | 306 | 0 | 4 mode graphs | - |
| I/O | 1764 | 1764 | 1764 | 0 | 0 | 0 |
| workers (87 owned) | 87 | 87 | 87 | 0 | 0 | 32 |

Graph passes: baseline 106, flow 143, flow-residual 23, obligations 34. Stage-3 field_set rows 797 of 797 (789 wire/I/O, 4 N4-fieldset, 4 N4-restore-direct); type_mismatch rows 756 of 756. Harness sha256: replay5_library_v9.py 315639062237637eb064babc4a9f4d296d3858d821c609a843e55ae095ba19e4; replay5_library_n4_v9.py fa20c127976de82aa49a42f10021c64ea802953728cee52ef82557072fd583d8; replay5_library_n4_graphs_v9.py 28a849596ea0ac01dc709b2466bda1ca82df7fdd64d06d52d04caf33bd4ec025; replay_io_c5_v9.py bf76c0295873c9d174a8a48a7939e74d23d2b8d7ff2e3452e327a0cb6842e9c1; replay_workers_c5_v9.py bad46bf43a2b2f4f618977f240cf0958d3503cfd569f23ef3df84970a63f77aa. Provenance notes: no v9 harness crashed (the v8 graph harness first-run crash on a trailing print, rerun clean with the same counts, is carried from candidate11). Mutation proof for all five v9 harnesses (one altered value each, each exit 1); the first graph mutation (renaming record name and values, not graph keys) did not trip and was redone as a node-key rename, which trips. Mutation checks show each harness can fail, not coverage.

## 8. Controller, provenance and release-notes items
Controller sha256 0ccd284290e93f76328578933cdbeb2629cb98be3fff77f5e7b2ecdf92ba3763; manifest sha256 ea0a8dc1b8da4cd3bf4f966d453fffe894acc163ccc2006baadb6d591e700b0c. It is the candidate11 controller (fdc9945f938dbd5ec61631f976015ae4d9f62c785a457980e4db9a9c9e5c8681) with only docstring, names, source dir and description strings changed (audit: no safeguard removed). Deviations carried from earlier candidates and accepted by the coordinator: source-review approval gate removed (NO independent review of the controller), 6 source receipts removed, contract path restriction removed, manifest-name check relaxed, second in-validate scheduling-lock check removed, glob check of the 12-module set added. Attempt 1 passed. Accepted risk: no independent controller review; release notes must disclose it.

Release-notes items (to publish with the release; the draft is in the private work folder):
1. The consumer filter as runnable code (section 2), re-issued with the candidate12 hashes and counts.
2. The 61 flagged rows and 30 graphs (section 3) with the ruling each depends on.
3. Controller disclosure: no independent review of the controller.
4. Plainly: the new, changed and returned rows have no independent semantic adjudication; the field_set parent pointer, the Q3 pointer, the integer-op incomplete-capture shape, the premiums and signs convention and the restore shape-order sentences are INFERRED.
5. Assumption 2 is a product ruling not derived from the private boundary text; it covers the 9 B3-integer-price rows and the 9 returned B rows.
6. Graph evidence is digest-level only; the 4 mode graphs are unevidenced.
7. Coverage statement: Q4 and the narrower-rollup clause are HELD; excluded_ids order is not asserted.

## 9. Post-release status and rulings (decided, pending owner review)
Post-release fixture correction candidate for the next release (target r26-variants2-prerelease, still a PRERELEASE). Coordinator: candidate12 supersedes candidate11 as the post-release candidate (the rollup-wider row is re-authored under the ratified integer-op sentence; the /checkpoint and /config missing-member rows are authored); controller deviations are accepted as before; no row is excluded. Not qualified: the PO's qualified-release criteria are Windows qualification passes; demo works (merged, synthetic-only); two-control fix landed (done); /checkpoint and /config coverage present (done) or scoped out; every flagged id disclosed; owner accepts. Windows qualification and owner acceptance are not met, so the word "qualified" must not be used.

## 10. Open PO items
Q4 (suffix checks) held; narrower-rollup clause held. Owner items: PyPI wheel permission for Windows qualification (python-flint==0.9.0, duckdb==1.5.6, setuptools==80.9.0, win_amd64 cp312; sizes unverified), qualification scope, release acceptance and label, review of decisions pending owner review, worktree cleanup.

## 11. Conditions to freeze
Met: hashes, counts, bytes re-read from disk; no structured exclusion key; replay of record on merged mains; harness hashes and mutation proof; controller deviations accepted; audit approve. Independent freeze review: done (approve-with-conditions, conditions applied), condition 6 met. Non-blocking: earlier auditor tooling not re-run; Q4 and the narrower-rollup clause open. Candidate12 is not final until this PR is merged.
