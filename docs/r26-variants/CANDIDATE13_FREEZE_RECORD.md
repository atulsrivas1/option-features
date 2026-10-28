# R26 variants: candidate13 freeze record (public-safe)

Status: candidate13 is recorded as a post-release candidate for the next release (2026-10-28), superseding the candidate12 freeze record (PR 46) for the fixtures it covers. R26 was released as r26-variants1-prerelease on 2026-10-23; this record corrects fixtures after that release. The release label stays PRERELEASE. Coordinator rulings are "decided, pending PO review" unless the Product Owner ruled. Independent audit: approve (no defects). Independent source review: approve-with-conditions (applied). Independent controller review: approve-with-conditions (applied in the hardened rerun), partial (section 7). Independent freeze review of this record: done (approve-with-conditions, conditions applied). The reviewer did not verify the workers 96-row total and 58/38 split, the controller determinism rerun and its hashes, the audit approvals or the mutation proof; those rest on the records above. This PR is not final until merged. Row content and the private work folder are not published; this record carries hashes, counts, exclusions by id, flags, gaps and open items.

## 1. Census
| file | sha256 | bytes | in file | frozen | vs candidate12 |
|---|---|---|---|---|---|
| representative.jsonl | 1e7cadcce4ef3c717e2feeb74a3142c64db908b432c93a4e2061d501099860e0 | 6183840 | 25 | 25 | byte-identical |
| baseline.jsonl | 6066098b3470ff373c5b86e1ee97f1d5d7a22cfc641a8662dd0b32b5a2e85a1c | 44818801 | 153 | 153 | byte-identical |
| flow.jsonl | 14efa0af86b76e51ecf580e6e98f57dbb02906f6fb890c736bfcfed74cf9abea | 24815750 | 174 | 174 | byte-identical |
| flow-residual.jsonl | eddc4090a30703b5f1246ed364fafd1961e9c72a473de520d74d16b9b26164ed | 9534396 | 55 | 55 | byte-identical |
| wire.jsonl | e98d6850b02dc62739049d6f0f1fb514912dcb6386c016610550829a810452f3 | 46510253 | 1810 | 1810 | byte-identical |
| obligations.jsonl | f9f542dc78f55bda2300a53a1a5b33cfb385eaeb3961312a23ce4d6238f41e4e | 15578323 | 120 | 115 | +33 N5 rows (the 87 N4 rows are identical) |
| identity-graphs.jsonl | fc45131815038ae00c24124e71136619eff93f879f7a892ddce922ec9153aad6 | 57721593 | 310 | 310 | byte-identical (no N5 graphs) |
| index.json | 518539dd8d49fc9b2763644c295c9a141f68f53f3d96dce3f819e35704c4efac | 2202 | - | - | - |

Total bytes of the seven jsonl files: 205162956 (index.json not counted; candidate12: 203569173). 2647 rows in files (2337 non-graph + 310 graphs), case_ids unique. Against candidate12 by case_id (parsed from disk): 2614 identical, 0 changed, 33 added, 0 removed. **Frozen: 2642** = 2647 minus 5 excluded by id (2332 non-graph rows + 310 graphs). Candidate12's 2614 frozen rows are unchanged and byte-identical. Files are never edited. Verify whole-file sha256 first. The candidate root directory is named generated-completion-candidate5 (hardcoded by the pinned containment module) but holds candidate13 output: rely on the index.json hash, not the directory name.

Added: 33 N5 rows (22 wire-shaped, 11 restore-shaped), no graphs. Frozen N5 = 28 (19 wire + 9 restore). N4 frozen 87 unchanged (bom 20, restore 18, roll 16, dailycore 8, pr12 19, zero 1, premium 1, fieldset 4); obligations frozen 115 = 87 + 28.
N5 frozen ids, wire (19): nondict-plain-record-{list,string}, nondict-array-element-record-index1, nondict-union-plain-{list,string}, nondict-union-array-element-index1, null-nonnullable-{stamp-position, execution-root-id, execution-event-ns, request-knowledge-k, cursor-position-index1}, union-kind-{nonstring-int-plain, nonstring-null-plain, unknown-plain, nonstring-int-array-index1, nonstring-bool-array-index1, unknown-array-index1}, array-element-record-index1-{missing-member, extra-member}. Restore (9): restore-request-cursor-index2-{missing-member, extra-member}, restore-request-cursor-index1-nondict, restore-q3-{first-stream-dropped, middle-stream-dropped, two-streams-dropped, all-streams-dropped-empty-list, with-cursor-regression-q3-wins, with-request-shape-error-shape-wins} (all ids prefixed N5-). They cover non-dict records and unions, nulls at non-nullable members, union kind errors, plain-record array elements past index 0, request cursor shape, and omitted-stream (Q3) restore errors.

## 2. Consumer filter and exclusions
Structured keys only (freeze_excluded, non_asserted_subfields, contract_status, completeness), never substring search. Filter (rule unchanged): skip a row if `freeze_excluded` is true, or `contract_status == "UNDETERMINED_CONTRACT_GAP"`, or (obligations) `completeness != "complete"`. A row with a non-empty `non_asserted_subfields` must not assert those subfields. The value `UNFROZEN_CANDIDATE` on most N4 and N5 rows is not an exclusion.

**Excluded by id (5, all N5, each with freeze_excluded true and UNDETERMINED_CONTRACT_GAP; structured walk of all 2647 rows found no other):**
- N5-nondict-plain-record-null, N5-nondict-union-plain-null, N5-nondict-union-array-element-null-index1: null where a record or union object is expected; nullability is not declared in the contract text (inference only).
- N5-restore-q3-dropped-with-extra-stream-added: the outcome depends on the unspecified admission of an extra stream (admission precedes Q3). The workers replay probes show the worker accepts both excluded Q3 restore rows (this row and the extra-stream-only control); this supports leaving them undetermined and excluded (diagnostic only, not asserted).
- N5-restore-q3-control-extra-stream-only-accepted: only "no checkpoint_cut_mismatch" is pinned; expected results are masked.
No graph is excluded. The 4 mode graphs (IDENTITY4-batch, -chronological_cut_replay, -checkpoint_restore, -admission-extension) have no source row and are frozen. The runnable filter in the release notes must be re-issued with the candidate13 hashes, counts and these 5 ids.

## 3. Frozen subject to regeneration (flagged; consumers must expect these ids may change)
The candidate12 list is carried in full: 61 rows and 30 graphs (see CANDIDATE12_FREEZE_RECORD.md section 3). No flag was removed, because no evidence supports removal. Updates:
| group | state in candidate13 |
|---|---|
| assumption 2: 9 B rows, 9 B3-integer-price rows, 9 graphs | encoding of assumption 2 confirmed in the 18 rows and the 9 graphs; they were confirmed, not regenerated; assumption 2 is a PO product ruling, not contract text. STILL FLAGGED pending PO acceptance of the confirmation |
| PR 34 rows (roll-unresolved 4 + 4, F4 capture-domain 4 + 4) | STILL FLAGGED. PO ruling: excluded_ids is stored as a sorted literal; no regeneration under Reading B was authored |
| two-control F4 rows (4 + 4 graphs) | STILL FLAGGED. Compared on the parent of the PR 42 merge and on current main: the two expected-root rows (span, rolling) fail before the fix and pass after, with their graphs; the two nonexpected-root rows pass both before and after, so they do not discriminate. PO ruling: they are valid negative controls |
| root A after K rows (3) | STILL FLAGGED. PO ruling: accept, with release-notes disclosure that authorship of that fixture provenance is unrecorded |
| every other candidate12 flag | unchanged, STILL FLAGGED |
| 28 frozen N5 rows (new, no graphs) | proposed flagged (decided, pending PO review): fixture-author derived from clarification text only, depend on the INFERRED field_set parent pointer and the Q3 pointer; the 5 N5 null-nonnullable rows carry a note that non-nullability is inferred |
Flagged totals: carried 61 rows and 30 graphs; new 28 rows; total **89 rows and 30 graphs**; none excluded by flag.

## 4. Partial rows and masks
- Workers partial 38 = 32 carried (20 doc_phase, 2 doc_checkpoint_phase, 10 W3-storage-nullability) + 6 N5 restore rows partial on doc_phase. Workers owned 96, full 58. Nothing may assert doc_phase or doc_checkpoint_phase. Library, N4 and I/O: 0 partial.
- 2 admission rows without expected receipt (W3-admission-monotone-extension, W3-admission-null-to-nonempty): compared via expected_publication only.
- 0 masked frozen rows (the one masked N5 row is excluded); 5 freeze_excluded rows.

## 5. Gaps
Carried G1 to G26 as in the candidate12 record, with updates: G10 (excluded_ids order is compared literally by the harness, see section 8), G15b (assumption-2 rows and graphs confirmed encoding, not regenerated), G21 (harnesses have no independent review; controller review is partial).
G27: the 28 N5 rows have no independent semantic adjudication beyond the audit; the field_set and Q3 pointers and the non-nullability are inferred. G28: 5 N5 rows are UNDETERMINED and excluded. G29: N5 has no graphs and no library-level evaluation; evidence is I/O (19 rows) and workers (9 rows, 6 partial). G30: the two nonexpected-root two-control rows do not discriminate before and after the fix. G31: mutation proof for the v10 harnesses covers one I/O row and one workers row only.
Remaining: Q4 held; narrower-rollup clause held; 2 W3-admission rows without expected receipt; Q3 plus K regression and Q3 plus admission or root A after K not authored; no code or codec change is part of this candidate; controller partly unconfined and partly unreviewed; graph evidence digest-level with 4 mode graphs unevidenced.

Mandatory non-claim: numeric, wire and earliest-error correctness is not claimed beyond the audit and the replays; the N5 rows are fixture-author derived from clarification texts, not from implementation code.

## 6. Evidence (replay v10; code = read-only exports of main: option-features 8951003, option-feature-io e156963, option-feature-workers 8795f3e; python -I -B, fresh output dirs, fixtures read-only, all exit 0, 0 failures)
| layer | candidate12 | rows | run | passed | failed | skipped |
|---|---|---|---|---|---|---|
| library | 405/405 | 407 | 405 | 405 | 0 | 2 (workers-owned E-checkpoint) |
| N4 library | 49/49 | 49 | 49 | 49 | 0 | 0 (N5 rows are not library-evaluable) |
| graphs | 306/306 | 310 | 306 | 306 | 0 | 4 mode graphs |
| I/O | 1764/1764 | 1783 | 1783 | 1783 | 0 | 5 N5 rows excluded by id |
| workers (owned) | 87 (32 partial) | 96 | 96 | 96 (58 full, 38 partial) | 0 | 2 N5 rows excluded by id |
N5 split: 19 I/O wire pass, 9 workers restore pass (3 full, 6 partial), 5 skipped by id with the skip asserted. Candidate12 rows replay identically. Harness sha256 (worker-authored, not independently reviewed): replay5_library_v10.py b018c0e556446f24d54c597fb7388957a77d3c0b032b5c39491985262c97676d; replay5_library_n4_v10.py abb4d8892caa6117a58adcbf5b80bb749b4a3650dcf65aa263ea3e8af1966800; replay5_library_n4_graphs_v10.py ef7cbe1aeaa3c8154451283cb0c61231535f18068afa742ce44a90571364e2f6; replay_io_c5_v10.py a39612e123fdd37b7ae809404cd8be83ed44e044c61de7894798cf25f5306be8; replay_workers_c5_v10.py 6bd42a791e4d93137fda09afc6197caabee11d1de0667c7a9bf319d6cb30a4eb. Mutation proof: one altered expected path in an I/O N5 row (1782/1783, exit 1) and one altered cause path in a workers N5 row (1 failure, exit 1); this shows those paths can fail, not coverage. Graph evidence stays digest-level.

## 7. Controller, determinism and review
Generation: controller sha256 97ffb6e52c1af1fe8c5271b767e539e935a08df84cdbc8a7ca98de5936584a70, manifest sha256 4a9b3e72eeff9439d9e04c5febbf488952bf0e4aa5533332eac3bef9c025be7a (13 modules; contract pins identical to candidate12), attempt 1 passed. The aggregator was edited so the obligations builder chains the N4 and N5 builders (still one obligations file; 7-file set kept). Containment module unchanged.
Determinism: a hardened-controller rerun (controller sha256 237dbe2a2bb5cd300d3934852c6e35adeb8d49abe3db62b423c2cdf4bfed97e0, manifest sha256 76c7546e1282199b420ce642ade96f41e680a81bdb4ccfb463baa4ca4e963c5e) produced all 7 files and index.json byte-identical to candidate13. Conditions applied there: source-directory allowlist (negative-tested); interpreter path, version and executable hash pinned; the scheduling lock name now matches the module's (the earlier name was a different file, so that check was ineffective); output directory must be new (negative-tested).
Independent controller review (approve-with-conditions, applied) is partial. Still unconfined: network, file-system confinement (only pins and a post-run census check), environment and other processes, memory reservation; the interpreter is pinned by path and hash but the standard library and site packages are not hashed. Unreviewed: the containment helper internals (including the Windows job object) and the 15 contract hashes. Whether this satisfies the PO condition of an independent controller review before any release with a stronger label is a PO question and is not claimed.

## 8. Open items and corrections
- Q4 (suffix checks) held; narrower-rollup clause held.
- Correction: earlier text said excluded_ids order is not asserted. The harness compares results literally, so the order IS compared; the library canonicalizes excluded_ids as sorted, so the stored literal is sorted. Known limitation for the PR 34 record and release notes. Graphs are digest-only and were not recomputed.
- Release-notes items (draft in the private work folder): the consumer filter re-issued with candidate13 hashes, counts and the 5 ids; the 89 flagged rows and 30 graphs; the unrecorded authorship of the root-A-after-K provenance; the controller review scope above; N5 rows have no independent semantic adjudication and rest on inferred pointers; assumption 2 is a PO product ruling; graph evidence is digest-level; Q4 and narrower-rollup held.
- Owner items unchanged (qualification scope, release acceptance and label, licence review of python-flint, worktree cleanup).

## 9. PO R27 rulings (effective in candidate14; candidate13 unchanged)
The PO ruled on the open candidate13 items on 2026-10-28 (see DECISIONS.md). Candidate13 stays exactly as recorded here; the adopted rulings take effect only in candidate14, a new candidate (no file is edited in place). Details are in DECISIONS.md and RELEASE_NOTES.md.

## 9b. Post-release status and rulings (decided, pending PO review)
Coordinator: candidate13 supersedes candidate12 as the post-release candidate (candidate12's 2614 rows unchanged; 28 N5 rows added; 5 N5 rows excluded by id); flagging of the N5 rows; the release label stays PRERELEASE and no stronger label is claimed. PO rulings referenced above (A>K accepted with disclosure; sorted-literal excluded_ids; nonexpected two-control rows valid negative controls) are recorded in DECISIONS.md.

## 10. Conditions to freeze
Met: hashes, counts and bytes re-read from disk; the structured walk finds exactly the 5 excluded ids; replay all exit 0; candidate12 rows byte-identical; determinism; audit approve; source and controller reviews approve-with-conditions, conditions applied. Partly met: v10 harness mutation proof (two rows). Independent freeze review of this record: done (approve-with-conditions, conditions applied); the reviewer did not verify the workers 96-row total and 58/38 split, the controller determinism rerun and hashes, the audit approvals or the mutation proof. Open, non-blocking: PO acceptance of the assumption-2 confirmation and of flagging the N5 rows; Q4 and narrower-rollup held. Candidate13 is not final until this PR is merged.
