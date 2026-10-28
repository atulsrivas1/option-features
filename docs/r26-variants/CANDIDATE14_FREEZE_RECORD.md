# R26 variants: candidate14 freeze record (public-safe)

Status: candidate14 is recorded as the post-release candidate (2026-10-28), superseding candidate13 (CANDIDATE13_FREEZE_RECORD.md) for the fixtures it covers. The release label stays PRERELEASE; nothing here is "qualified". Not final until this PR is merged and the review gates in section 11 are recorded. This record carries hashes, counts, ids, flags and limits only: no row content and no private paths.

## 0. Definition of "frozen" (verbatim)
Frozen means the 2665 rows are byte-reproducible from the manifested source, immutable except by a new candidate, and that the hashes above identify them. It does NOT mean every row is validated: flagged rows (N5 31, N6 21, W3 39) are frozen as-is, flagged, and consumers must treat them as provisional. Null rows are frozen without a flag. Unflagging does not change row content; any content change requires candidate15.

(The 3 null rows are frozen with no per-row flag key. See section 4 for how the group census counts them.)

## 1. Identity
| item | value |
|---|---|
| candidate | candidate14 (generated as candidate14b after a source-copy correction, section 1.1) |
| date | 2026-10-28 |
| code baseline (read-only exports used by replay) | option-features 8285cf70a0929ca5eb613e2d5e7618e77b1dc97c, option-feature-io e15696368eb9635e425b00c6455f4353f3b6e67a, option-feature-workers 8795f3e83333e5458e4e037e2441c4154fc664ec |
| controller (final, 14b) sha256 | 7afa68a1ce05dd1ebb95eed360d4770d6b55b077ec4993f576ca69f440b0f19a |
| manifest (COMPLETION14B_SOURCE_MANIFEST_A1) sha256 | 5233264ea38ff07613db957654cd079aea3c10445dc8624fd76fd56b65ea0153 |
| aggregator (completion_candidate5.py, chains N4, N5, N6) sha256 | 4002b6720420104f3d5c4b0cf41ade90fae72cf2042c62725351072e007b46fd |
| obligations5_cases.py sha256 | 53442d2ac97d3fb3b9fba064f940cfc24d55925ba29271f168ebfd62cf34c6ed |
| obligations6_cases.py sha256 (21 N6 rows) | f2940ae97dbb809b8ab7aa42b8618090c7e57a814251cb65570e494cad2c7056 |
| CANDIDATE13_AUTHORING.md (corrected copy) sha256 | effede0febd62a489c505badc28d41ab98e782cd320a94a60d6ddbfbb4ac329a |
| index.json sha256 | 11165e906a7e03c6e217847a980db6d949aea210ed47697c34838b7f13331203 |
| obligations.jsonl sha256 | cabb56fd9e38d48c6fed42736319e9897690762be8c45c824a8975b2162d21a1 |
| fixture tree sha256 (sorted relative path + file sha256, replay run_all algorithm) | 5bd656c4b5f2385eb3de318ac619c8e1c66715e3e51b51bb735eb260ceefd694 |
| contained interpreter and containment module | unchanged from candidate13 (interpreter pinned by path, version and hash) |

The 16-entry source tree is the candidate13b source with obligations5_cases.py (3 null rows corrected), the new obligations6_cases.py, the aggregator edit, and the CANDIDATE13_AUTHORING.md correction; the other 12 .py files and the second non-code file are byte-identical to candidate13b. Per-file hashes are in the manifest. N6 preimages were not added to the identity graphs.

### 1.1 Post-rerun marker and superseded hashes
First run ("candidate14", 2 runs): the source tree carried the stale CANDIDATE13_AUTHORING.md (sha256 34febce26b7f3cbbe31831de92d93399b38962399c4be1a92d1672e8ff344c6e), which still listed the 3 null rows as undetermined and contradicted the generated targets. PO decision: adopt the corrected copy (hash above), update the manifest, rerun. Rule applied: any output row hash change on rerun would stop the freeze.
Result of the rerun ("candidate14b", 2 runs): all 8 output files (7 jsonl + index.json) are byte-identical to the first run, so index.json and every row-file hash are unchanged. Only the manifest and controller identities moved.
**Superseded (traceability only; do not use):** manifest sha256 f5bc80b9fbf6b1caa562b3a8148f847c253d9f76ca2d676e2d9bf1995ea3780d; controller sha256 d4e2986146dae944fa17647227be6e9b81d5451de2ea5afe7a6f286af06e5a32; stale authoring file hash above. The hashes in the table in section 1 are the post-rerun values.
Controller 14b differs from the first controller only by source directory name and text/module-name renames. Against candidate13b the controller change is: obligations6_cases.py added to the module allowlist, "fourteen-module" text, renames. Interpreter pin, lock name, output-must-be-new and output-parent refusals are unchanged.
Determinism: 4 generations (2 first-run, 2 rerun), all 8 files byte-identical (cmp), exit 0, lease released. Re-verified from disk for this record: whole-set sha256 identical across all four output directories.

## 2. Census
| file | sha256 | bytes | in file | frozen | vs candidate13 |
|---|---|---|---|---|---|
| representative.jsonl | 1e7cadcce4ef3c717e2feeb74a3142c64db908b432c93a4e2061d501099860e0 | 6183840 | 25 | 25 | byte-identical |
| baseline.jsonl | 6066098b3470ff373c5b86e1ee97f1d5d7a22cfc641a8662dd0b32b5a2e85a1c | 44818801 | 153 | 153 | byte-identical |
| flow.jsonl | 14efa0af86b76e51ecf580e6e98f57dbb02906f6fb890c736bfcfed74cf9abea | 24815750 | 174 | 174 | byte-identical |
| flow-residual.jsonl | eddc4090a30703b5f1246ed364fafd1961e9c72a473de520d74d16b9b26164ed | 9534396 | 55 | 55 | byte-identical |
| wire.jsonl | e98d6850b02dc62739049d6f0f1fb514912dcb6386c016610550829a810452f3 | 46510253 | 1810 | 1810 | byte-identical |
| obligations.jsonl | cabb56fd9e38d48c6fed42736319e9897690762be8c45c824a8975b2162d21a1 | 16563064 | 141 | 138 | 0 removed, 3 changed (null rows), 21 added (N6) |
| identity-graphs.jsonl | fc45131815038ae00c24124e71136619eff93f879f7a892ddce922ec9153aad6 | 57721593 | 310 | 310 | byte-identical |
| index.json | 11165e906a7e03c6e217847a980db6d949aea210ed47697c34838b7f13331203 | - | - | - | candidate13: 518539dd8d49fc9b2763644c295c9a141f68f53f3d96dce3f819e35704c4efac |

Total bytes of the seven jsonl files: 206147697. **2668 rows in files** (2358 non-graph + 310 graphs); case_ids unique. Against candidate13 by case_id (parsed from disk): 2644 identical, 3 changed, 21 added, 0 removed. **Frozen: 2665** = 2668 minus 3 excluded by id (2355 non-graph + 310 graphs). Obligations frozen 138 = 87 N4 + 31 N5 + 20 N6. Candidate13's frozen rows are byte-identical except the 3 null rows. Files are never edited; verify whole-file sha256 first. The candidate root directory is named generated-completion-candidate5 (hardcoded by the pinned containment module); rely on the index.json hash, not the directory name.

## 3. Exclusions by id (3, structured keys: freeze_excluded true and UNDETERMINED_CONTRACT_GAP; a walk of all 2668 rows finds no other)
- N5-restore-q3-dropped-with-extra-stream-added: the outcome depends on the unspecified admission of an extra stream; scoped out by PO R27 ruling and not asserted.
- N5-restore-q3-control-extra-stream-only-accepted: only "no checkpoint_cut_mismatch" is pinned; expected results are masked; stays excluded until a harness can assert that negative.
- N6-restore-q3-with-knowledge-regression: the order between the Q3 stream-omission check and a knowledge regression is unspecified (Q2 combined-defect order); nothing is asserted.
Candidate13 excluded 5; the other 3 (the null rows) are adopted in candidate14 (section 4). No graph is excluded. The consumer filter is unchanged: skip a row if `freeze_excluded` is true, or `contract_status == "UNDETERMINED_CONTRACT_GAP"`, or (obligations) `completeness != "complete"`; rows with non-empty `non_asserted_subfields` must not assert those subfields; `UNFROZEN_CANDIDATE` is not an exclusion. Re-issue it with this record's hashes and the 3 ids above.

## 4. Null rows (3), adopted, no per-row flag
N5-nondict-plain-record-null, N5-nondict-union-plain-null, N5-nondict-union-array-element-null-index1. Rule (PO R27): a record or union object is never nullable unless the schema declares it; null is a non-dict value giving type_mismatch at the record or union pointer. The first attempt used Execution.price as the union target; the pinned schema declares price nullable, so the row was retargeted (same id) to Execution.definition_use, which is not nullable, and the ruling sentence now names Execution.stamp, Execution.definition_use and rows[i].payload. No codec defect. The expectation is derived from the schema and the ruling sentence, not from codec output.
These 3 rows carry **no per-row flag key**, exactly like every N4 and N5 row (only the 21 N6 rows carry `flagged: true`); absence is not an omission. Flags are a group register (section 5). The R27 census counted these 3 in the N5 group (31 = 28 + 3); the PO plan also states null rows are frozen without a flag. Both statements are recorded here as written; which wins for R27 unflag accounting is a PO question (see section 9).

## 5. Flagged groups (remain flagged at freeze; consumers treat them as provisional)
Carried from candidate13 (no flag removed, no evidence supports removal): 61 rows and 30 graphs (candidate12 list; see CANDIDATE12_FREEZE_RECORD.md section 3), including the W3 block below. New in candidate14: N5 31 (28 + 3 null) is the R27 census group, N6 21. Register total under that arithmetic: 61 + 31 + 21 = 113 rows and 30 graphs; the R27 pre-N6 expectation was 92 rows.
| group | count | reason | R27 unflag gate |
|---|---|---|---|
| N5 | 28 + 3 (31 frozen) | fixture-author derived from clarification text only; field_set parent pointer, Q3 pointer and non-nullability are inferred by ruling, not contract text; no independent semantic adjudication beyond the audit; wire rows have I/O evidence, restore rows workers evidence, no graphs | R27 must supply independent adjudication of N5 semantics; unflag only on a recorded adjudication matching the generated targets |
| N6 | 21 (20 frozen) | see section 6 | independent adjudication (section 6); unflag per row on agreement, route disagreements to a fix candidate |
| W3 | 39 ids, status NOT_REGENERATED | assumption-2 block (9 B rows, 9 B3-integer-price rows, 9 graphs) and PR 34 (section 7: 6 rows, 6 graphs); independent regeneration was attempted and found infeasible at byte level: each row is 250-430 KB of computed results and each graph about 350 KB of digests, so reproducing them from ruling text alone means a second implementation. No difference was found and none was disproven. These ids are not independently confirmed | see below |
**W3 disclosure (permanent for R26):** "39 ids (assumption-2: 9 B, 9 B3, 9 graphs; PR34: 6 rows, 6 graphs) are frozen subject to independent regeneration. An independent regeneration was attempted in candidate14 and found infeasible at byte level; no difference was found and none was disproven. These ids are not independently confirmed." W3 is recorded as NOT_REGENERATED 39/39, not as a pass.
**W3 unflag gate (R27), ALL must hold:** (1) a spec-writer who has never seen library or candidate13 row bytes writes an encoding spec from public ruling and schema text only, ambiguities returned as rulings, never settled by reading code; OR (2, preferred) a rulings-only author derives decision-bearing fields only (status, accepted or rejected, premium, sign, price acceptance, member lists, excluded_ids as a sorted literal, error codes and pointers) and a separate comparer diffs those fields from candidate13, all matching, any difference a finding and not a fix-up; (3) graphs are digest-only, so they stay flagged until a spec-based regeneration matches (a field-level pass never unflags a graph); (4) PO ratifies in writing per group. A field-level pass moves rows to "field-confirmed", a weaker named status, not "independently regenerated". Reading B pre/post for PR 34 is part of the R27 work.
**Unflag procedure:** one DECISIONS entry per group naming ids, evidence hash and reviewer; rows leave the flagged set only by that entry. No bulk unflag. Unflagging does not change row content; a content change needs candidate15.

## 6. N6 (21 rows, all `flagged: true`)
18 proof rows (fail before the corresponding fix, pass after), 2 NON-PROOF controls (pass both before and after), 1 excluded.
- Restore (workers, 4 proof): N6-restore-root-A-after-K-before-identity-conflict-quotes, -controls, -two-collections; N6-restore-q3-before-root-A-after-K.
- Wire (I/O, 5 proof): N6-wire-plain-nested-record-extra-member, N6-wire-extra-member-slash-key-plain-record, N6-wire-extra-member-slash-key-array-element, N6-wire-extra-member-slash-key-payload-root, N6-wire-union-plain-field-extra-member.
- Field-set direct (library, 5 proof): N6-fieldset-direct-execution-stamp-missing-member, -stamp-extra-member, -stamp-extra-member-slash-key, -price-union-missing-kind, -price-union-extra-member.
- F4 (library, 4 proof): N6-F4-parent-two-controls-expected-tail-root-outside-second-domain, N6-F4-parent-two-controls-expected-two-roots-outside-second-domain, N6-F4-span-two-controls-expected-tail-root-outside-second-domain, N6-F4-span-two-controls-expected-two-roots-outside-second-domain.
- NON-PROOF controls (2, I/O): N6-wire-plain-nested-record-missing-member-control, N6-wire-union-plain-field-missing-kind-control (the pre-fix pointer logic coincidentally gives the right pointer; they prove nothing about the fix).
- Excluded (1): N6-restore-q3-with-knowledge-regression (section 3).
Before/after evidence came from the comparer run on read-only exports (before: 9b workers 82aac59, 8b io 9f7b468 plus features 4e87bc6, 9d features e462cf0; after: the code baseline in section 1): 18 rows fail before and pass after, 2 controls pass both, 0 fail after. The "before" side was not re-run at the final freeze. One F4 parent row first failed after: the library correctly emitted a second legal group (a repeated-price group from two members with equal premium); the PO ruled it a fixture oversight, not a library defect, and the row now uses distinct premiums.
**Caveats (stated, not resolved):**
- N6 had no independent adjudication. Rows were authored from rulings and grounded row by row by the PO; they are generated and replay-consistent only. "Frozen" for N6 means reproducible, not validated.
- Two groundings are by precedent, not by text: (1) the worker `input_invalid` wrapper with cause code and path and zero sink calls on the 5 field-set direct rows follows the worker-translation paragraph of the field-set clarification and the existing N4 field-set-direct row format, not an explicit sentence; (2) the two-roots F4 rows rely on the capture event domain being half-open at its end, which the public text states for FlowReference intervals but not for event_domain; the frozen span-inclusive-endpoint row is the precedent.
- Pointers for Q3 and the field-set rows are "inferred by PO ruling"; rows carry contract_gaps saying so.
- Controller independently audited (section 10) but see the controller non-claims in the candidate13 record, section 7.

## 7. PR 34 count check (against candidate13)
Method: count case_ids by structured id from the candidate13 generated rows (index 518539dd...efac) and from candidate14, on disk. PR 34 rows are N4-roll-unresolved-{below-lower-bound-with-known-r, at-exclusive-lower-bound, inside-window, after-known-positive-endpoint} (4) and F4-parent-capture-domain-misses-tail, F4-span-inclusive-endpoint-not-captured (2); graphs are the matching IDENTITY4-<id> entries.
| | candidate13 | candidate14 |
|---|---|---|
| PR 34 rows | 4 + 2 = 6 | 4 + 2 = 6 |
| PR 34 graphs | 4 + 2 = 6 | 4 + 2 = 6 |
Equal, no difference by id; the PO plan's 4 + 2 rows and 6 graphs is correct. **Erratum:** the candidate13 record and release notes say "roll-unresolved 4 + 4, F4 capture-domain 4 + 4". The true counts are roll-unresolved 4 rows + 4 graphs and F4 capture-domain 2 rows + 2 graphs. Release notes are corrected in this PR. The earlier W3 ids "9 B3-integer-price rows" are the 9 contract-session1 and pooled rows; the 3 other B3-integer-price rows (mask-000, mask-110, count-RNonce...) and their graphs are not in the assumption-2 block.

## 8. Replay (read-only exports at the baseline refs; python -I -B; fresh output dirs; all exit 0; no --expect override; harness-c14)
Fixture tree 5bd656c4...d694 (the candidate14 output; candidate14b is byte-identical, section 1.1).
| layer | candidate13 | rows | run | passed | failed | skipped |
|---|---|---|---|---|---|---|
| library | 405/405 | 407 | 405 | 405 | 0 | 2 (workers-owned E-checkpoint, representative) |
| N4 library | 49/49 | 58 | 58 | 58 | 0 | 0 (49 + 4 N6-F4 + 5 N6-fieldset-direct) |
| graphs | 306/306 | 310 | 306 | 306 | 0 | 4 mode graphs (no source row); N6 graphs not added |
| I/O | 1783/1783 | 1796 | 1793 | 1793 | 0 | 3 excluded by id (1783 + 3 null rows + 7 N6 wire) |
| workers (owned) | 96 (38 partial) | 103 | 100 | 100 (58 full, 42 partial) | 0 | 3 excluded by id; 2 GAPs (W3-admission-monotone-extension, W3-admission-null-to-nonempty) |
Workers: 42 partial = 38 carried + 4 N6 restore rows (all partial on doc_phase CP3); 58 full unchanged. Nothing may assert doc_phase or doc_checkpoint_phase. Library, N4, I/O: 0 partial.
Tamper: all cases rejected (TAMPER OK). Isolation: layer tests Ran 14 / 48 / 24, post-test check ok (ISOLATION OK). Tamper and isolation have no fixture dependence; isolation uses the existing installed-package wheels, not rebuilt at these refs; these two were not re-run against the 14b manifest.
Excluded-row probes (diagnostic, not asserted): N5-dropped-with-extra rejected input_invalid; N5-control accepted; N6-q3-with-knowledge-regression rejected checkpoint_cut_mismatch at /request/cut_cursors.
**Independent replay review:** the reviewer reproduced the numbers above, with one limit: of the 42 workers partial rows he could reproduce only 32 by his own mechanism count (doc_phase, doc_checkpoint_phase, non_asserted_subfields) and relied on the harness count for the other 10. The 42 therefore rests partly on the harness. The workers count of 42 is pinned (derivation 38 + 4).
Harness sha256 (harness-c14): replay5_library_c14.py e10b769f148678eff9aba80693cf687f384c8abb6c35e569e19665f883dcfb34; replay5_library_n4_c14.py 00741df1465a4e09c0a15b56150e8d10952f63b35160e2a210df93a846f454fd; replay5_library_n4_graphs_c14.py be67203a8ab563f0bac64a7bfaa31dd310b2c0ecc14fb39a36826e7aab7153b0; replay_io_c5_c14.py 986286946ebaac900185880d834e545f7f2927f77e5f59eb00d4aecf219903b3; replay_workers_c5_c14.py bbd2d13fa76ad8859c1eebed01b01f644eda3f15df3eda490d7df71c79f222e7; run_all_c14.sh c9a82b336cac3e61ee2e259c8bb115cf03b57cb5898eda0281250c28088657dc; derive_c14.py 201faa0162e455b1d767a5f81c44e036856c163ac840937624bd8f6d88fb6d13; tamper, isolation and stage are byte copies of v12.

## 9. Harness hardening and residual risks
- v11 (independent review approve-with-conditions; PO accepted): replay results matched, no check weakened, 3 negative tests exit nonzero. Conditions: CI pins every ref and fixture by sha; CI forbids --expect-override flags.
- v12 (PO accepted): stage and isolation no longer default to an unpinned origin/main (--ref and --ref-io mandatory); run_all takes its root as an argument and runs all seven checks, nonzero if any fails.
- c14 (copies of v12): fixture and exports are required arguments with no default; excluded ids are pinned in each script and skipping is by id only, with a startup check rejecting the fixture if the set of row-flagged excluded ids differs from the pinned set; N6 routing added (N6-F4 and N6-fieldset-direct in the N4/library script, N6-wire in the I/O script, N6-restore in workers).
Residual risks (disclosed, not fixed): direct script runs can still take --expect-* flags (the CI path refuses them); probe and GAP counts are diagnostic only (the 2 GAPs are asserted, nothing more); the N4 stray-row allowlist is prefix-based (variants2 backlog: exact match); a row with only partial notes counts as passed-partial by design; the c14 harness scripts are worker-authored and carry no independent review of their own; isolation reuses existing wheels; the mutation proof for harness-c14 was not repeated (the v10 proof covered one I/O row and one workers row only); graph evidence stays digest-level; the "before" side of the N6 table was not re-run.
Open questions for the PO (R27 accounting): whether the 3 null rows count in the flagged register (section 4). Q4 (suffix checks) and the narrower-rollup clause are scoped out by the PO R27 ruling, not held; c-domain and c-completeness remain untested.

## 10. Reviews and audit
- Independent audit of the candidate14 output: approve-with-conditions. Condition (a): the stale authoring file, resolved by section 1.1 with the corrected-file hash. Condition (b): state the null rows and the flagged groups, satisfied by sections 4 and 5. The short auditor addendum confirming (a) and (b) on the final record is NOT yet recorded.
- Controller (14b): independently audited; the independent controller review remains partial as in candidate13 (network, file-system confinement, environment and memory unconfined; containment helper internals and the 15 contract hashes unreviewed). Controller review and hardening are required before any release label stronger than PRERELEASE.
- Independent replay review: section 8.
- Not done: independent N6 adjudication; independent N5 adjudication; W3 regeneration.

## 11. Gates before merge (status when this record was written)
1. Controller rerun on the corrected source: DONE (rows and index byte-identical; 2 + 2 runs agree).
2. Replay layers on the post-rerun state: row layers hold because 14b output is byte-identical to the replayed output; tamper and isolation not re-run at the 14b manifest (no fixture dependence).
3. Independent replay review: done, with the 32-of-42 limit above.
4. Independent docs review of this record, STATUS, HANDOFF, DECISIONS, RELEASE_NOTES (cross-check against the run records by someone other than the author): PENDING.
5. PR 34 check: PASS (section 7).
6. Public-safety scan: to run on this PR.
7. Auditor addendum on conditions (a) and (b): PENDING.
8. CI green; PO acceptance recorded in DECISIONS; retro entry: PENDING.
Merge is blocked on any failed gate.

## 12. Known limitations and R27 backlog
- N5 and N6 adjudication (gates in sections 5 and 6); W3 regeneration (section 5); Reading B for PR 34 (excluded_ids is a sorted literal and its order is compared literally by the harness).
- Q4 and the narrower-rollup clause: scoped out; reopen only on owner-supplied contract text. N5-restore-q3-dropped-with-extra-stream-added scoped out. The extra-stream control row stays masked until a harness can assert "not checkpoint_cut_mismatch at /request/cut_cursors".
- 2 W3-admission rows without an expected receipt (compared via expected_publication only); Q3 combined with K regression, admission or root A after K not authored; gaps G1 to G31 remain open; the root-A-after-K fixture authorship is unrecorded.
- Mandatory non-claim: numeric, wire and earliest-error correctness is not claimed beyond the audit and the replays.
