# R26 variants1 release notes: known limitations and disclosures (public-safe)

Release: r26-variants1-prerelease (tag in all three repos, published 2026-10-23). Label: **PRERELEASE**. Product Owner decision (2026-10-28): R26 stays an accepted prerelease with partial Windows evidence (the PO's decision label, cited verbatim: "Windows x64 cp312 partially qualified"). It is not qualified, and no stronger label is claimed. A scoped qualified label is deferred to the next release as a gate.

This page carries counts, hashes, ids and limits only. It carries no fixture row content and no private paths. Sources: [CANDIDATE13_FREEZE_RECORD.md](CANDIDATE13_FREEZE_RECORD.md), [WINDOWS_PARTIAL_QUALIFICATION_RECORD.md](WINDOWS_PARTIAL_QUALIFICATION_RECORD.md), [CANDIDATE12_FREEZE_RECORD.md](CANDIDATE12_FREEZE_RECORD.md), DECISIONS.md. The fixture baseline described below is candidate13, a post-release correction candidate recorded after the tagged prerelease.

## Known limitations and disclosures

### 1. Label and platform scope
- Label: PRERELEASE. Platform scope: Windows x64, CPython 3.12.10 only, partial Windows evidence. Do not describe any R26 artifact as "qualified".
- No Linux parity. Package versions stay 0.1.0a1.
- The label does not claim sandbox confinement. It claims only: frozen fixtures replay on installed packages, a reproducible build, and the limits listed here.

### 2. Fixture baseline (candidate13)
- index.json sha256 518539dd8d49fc9b2763644c295c9a141f68f53f3d96dce3f819e35704c4efac. 2647 rows in files (2337 non-graph + 310 graphs). 5 excluded by id. **Frozen: 2642** (2332 non-graph + 310 graphs). Candidate12's 2614 rows are byte-identical; 33 N5 rows were added (28 frozen).
- Candidate13's record had an independent freeze review (approve-with-conditions, conditions applied; the reviewer did not verify the workers 96-row total and 58/38 split, the controller determinism rerun and hashes, the audit approvals or the mutation proof). An audit (approve), a source review and a controller review (both approve-with-conditions, applied) exist.
- Consumer filter (structured keys only, never substring search): skip a row if `freeze_excluded` is true, or `contract_status == "UNDETERMINED_CONTRACT_GAP"`, or (obligations) `completeness != "complete"`. Rows with a non-empty `non_asserted_subfields` must not assert those subfields. `UNFROZEN_CANDIDATE` on most N4 and N5 rows is not an exclusion. Verify whole-file sha256 first; files are never edited.

### 3. Frozen subject to regeneration (flagged)
Consumers must expect these ids may change.
- **Total flagged: 89 rows and 30 graphs** (arithmetic, 61 + 28, not a per-row flag count; 61 rows and 30 graphs carried from candidate12, plus 28 new N5 rows; superseded by the candidate14 register in section 13). No flag has been removed.
- **28 N5 rows** (19 wire, 9 restore; no graphs): authored from clarification text only; they depend on the INFERRED field_set parent pointer and the Q3 pointer. The 5 null-at-non-nullable rows rest on inferred non-nullability. They have no independent semantic adjudication beyond the audit (G27), no library-level evaluation and no graphs (G29).
- Other flagged groups, all carried: assumption 2 (9 B rows, 9 B3-integer-price rows, 9 graphs; assumption 2 is a PO product ruling, not contract text; encoding was confirmed, not regenerated, and the 9 graphs were not separately inspected); PR 34 rows (4 roll-unresolved + 2 F4 capture-domain rows, with 6 graphs; the earlier text "4 + 4" for F4 was imprecise, see the candidate14 record section 7; `excluded_ids` is stored as a sorted literal and its order is compared literally by the replay harness); two-control F4 rows (4 rows and 4 graphs); root A after K rows (3); every other candidate12 flag per the candidate12 record, section 3.
- Two-control detail: the two expected-root rows (span, rolling) fail before the PR 42 fix and pass after; the two nonexpected-root rows pass both ways and do not discriminate (G30). The PO ruled them valid negative controls.

### 4. Excluded undetermined rows (5, all N5; candidate13 baseline, superseded by section 13: candidate14 excludes 3)
Excluded by id (`freeze_excluded` true, `UNDETERMINED_CONTRACT_GAP`):
- N5-nondict-plain-record-null
- N5-nondict-union-plain-null
- N5-nondict-union-array-element-null-index1
- N5-restore-q3-dropped-with-extra-stream-added
- N5-restore-q3-control-extra-stream-only-accepted

The first three: nullability of a record or union object is not declared in the contract text. The fourth depends on the unspecified admission of an extra stream. The fifth pins only "no checkpoint_cut_mismatch"; its expected results are masked. No graph is excluded.

### 5. Open contract gaps and held items
- Q4 (suffix checks): scoped out by PO ruling R27 (see 11b), not asserted.
- Narrower-rollup clause: scoped out by PO ruling R27 (see 11b). The F4 rollup-wider-than-capture-domain row was removed; **c-domain and c-completeness are untested**.
- Gaps G1 to G26 (candidate12 record) and G27 to G31 (candidate13 record) remain open, including: partial rows (38 workers rows partial; nothing may assert doc_phase or doc_checkpoint_phase); 2 W3-admission rows without an expected receipt (compared via expected_publication only); Q3 combined with K regression, admission or root A after K not authored; Q2 combined-defect order unspecified and not asserted; no code or codec change is part of candidate13.
- Variants2 backlog: BOUNDARY_CONTRACT line 322 may mandate canonicalizing -0.0, while variants1 rejects -0.0 permanently (one pinning row exists).
- Numeric, wire and earliest-error correctness is not claimed beyond the audit and the replays.

### 6. Containment and confinement: non-claims
- Network confinement, file-system confinement (only pins and a post-run census check), environment and other-process isolation, and memory reservation are NOT verified. Nothing here claims sandboxing.
- The independent controller review is partial. Unreviewed: the containment helper internals (including the Windows job object) and the 15 contract hashes. The standard library and site packages are not hashed (the interpreter is pinned by path and hash).
- Earlier controller deviations (dropped independent source-review gate, dropped source receipts and others) were accepted by the coordinator and PO and are listed in DECISIONS.md.
- Whether this meets the PO condition of an independent controller review before a stronger label is not claimed.

### 7. Unreviewed worker-authored harness scripts
- The five replay v10 harnesses were worker-authored and have no independent review (G21). sha256: replay5_library_v10.py b018c0e556446f24d54c597fb7388957a77d3c0b032b5c39491985262c97676d; replay5_library_n4_v10.py abb4d8892caa6117a58adcbf5b80bb749b4a3650dcf65aa263ea3e8af1966800; replay5_library_n4_graphs_v10.py ef7cbe1aeaa3c8154451283cb0c61231535f18068afa742ce44a90571364e2f6; replay_io_c5_v10.py a39612e123fdd37b7ae809404cd8be83ed44e044c61de7894798cf25f5306be8; replay_workers_c5_v10.py 6bd42a791e4d93137fda09afc6197caabee11d1de0667c7a9bf319d6cb30a4eb.
- Mutation proof covers one I/O row and one workers row only (G31): it shows those paths can fail, not coverage. The earlier N4 replay scripts exit 0 on failure (G6); do not use them as exit-code gates.
- Replay v10 results (all exit 0): library 405/405 (2 skipped), N4 49/49, graphs 306/306 (4 mode graphs skipped), I/O 1783/1783, workers 96/96 (58 full, 38 partial).

### 8. Graph evidence is digest-level
Identity-graph evidence is compared at digest level only and was not recomputed. The 4 mode graphs (IDENTITY4 batch, chronological_cut_replay, checkpoint_restore, admission-extension) have no source row and are unevidenced.

### 9. python-flint licence notice
python-flint 0.9.0 (win_amd64 wheel, sha256 8f1059536b7393e48b1444894c3b54ce1b961e4aa4a356e19217b26690f20db0) is installed by pip, not vendored or shipped by us. Its Python bindings are MIT; the wheel bundles LGPL-3.0-or-later GMP 6.3.0, MPFR 4.2.2 and FLINT 3.6.0 (plus winpthreads and the gcc runtime under a GCC exception) as separate DLLs that the user may replace. Licence review verdict: acceptable as a pip dependency with this notice; no obligation falls on our MIT code. Vendoring or shipping a bundle (frozen exe, image, vendored wheel) needs a separate review (COPYING files, source offer, no relinking restriction). See the python-flint project for its licences. This is a coordinator review of wheel metadata, not legal advice.

### 10. Root A after K fixture (3 rows)
The three root-A-after-K rows are accepted by the PO (A>K temporal_cut wins) with this disclosure: the authorship of that fixture's provenance is unrecorded. A standing open condition remains: author a fixture that fails on current code and passes after a workers change, with no frozen row changed.

### 11. Partial Windows evidence items
Windows replay evidence used candidate12 (library 405/405, N4 49/49, I/O 1764/1764, workers 87/87 with 32 partial, 108 unit tests OK); candidate13 was replayed on read-only exports, not re-run on Windows.
- candidate13 replays ran against read-only exports of option-features 8951003, while the Windows build used option-features c0db18e.
- The 31 fixture-defect rows excluded in the 2026-10-23 tagged release (see STATUS 2026-10-23) predate candidate13 and are covered by the earlier candidate records; the tag itself carries them.
Deviations:
- No reviewed trust digest: the trusted digest was self-computed by a separate reimplementation. This shows self-consistency, not an external trust anchor.
- Stand-in upstream commits: third-party source_commit values are sha1 of the wheel bytes.
- No 111-case golden run (R25: 111 batch/retry plus 111 replay cases); only the 5-scenario integration harness ran.
- No stored demo or browser round trip was run on Windows.
- No Linux parity.
- The 7 tamper cases and the layer-isolation harness are reconstructions (86 test methods rather than the R25 172), not the original harnesses.
- Not yet tested: OneDrive-synced folders, antivirus lock contention, CRLF/BOM evidence files, long paths with system support disabled.
- Project and third-party wheel names, sizes and hashes: see the Windows record, sections 2 and 3.

### 11b. PO R27 rulings (effective in candidate14; candidate13 and this release unchanged)
- Adopted, needs candidate14: the three null-nondict rows (N5-nondict-plain-record-null, N5-nondict-union-plain-null, N5-nondict-union-array-element-null-index1) leave the excluded list. Rule: a record or union object is never nullable unless the schema declares it; null is a non-dict value giving type_mismatch at the record or union pointer (field-set clarification section 2 item 4; non-nullability inferred). Expected candidate14 census at that time: frozen N5 31, flagged 92; superseded by the PO ruling: the 3 null rows are frozen-unflagged, N5 flagged 28, register 110 (arithmetic).
- Narrow sentence adopted: an extra stream in the Request cut cursors is not an omission and never triggers the Q3 checkpoint_cut_mismatch at /request/cut_cursors. N5-restore-q3-control-extra-stream-only-accepted stays masked and excluded until the harness can assert 'not checkpoint_cut_mismatch at /request/cut_cursors'.
- Scoped out with disclosure: N5-restore-q3-dropped-with-extra-stream-added (a restore that both omits a retained stream and adds an unknown stream is unspecified and not asserted; the worker currently rejects the dropped-with-extra form with input_invalid and accepts the extra-stream-only control, diagnostic only; the probe output mislabels the dropped row as ACCEPTED); Q4 suffix checks (not part of the variants contract; equal stamped positions in a suffix are identity_conflict; a suffix position not above the retained cursor is not rejected by a dedicated check); the narrower-rollup clause (a non-expected root inside the capture domain but outside a narrower rollup_interval is neither listed in excluded_ids nor depended on; observed behaviour, not contract).

### 11c. Harness findings from the R27 review (disclosed, not yet fixed)
- The tamper and isolation scripts exit 0 regardless of case outcomes; summary.json is the only verdict. Do not use their exit codes as gates.
- The workers replay probe of skipped rows mislabels results (it prints ACCEPTED for any non-empty diff list, including a PARTIAL doc_phase note) and swallows exceptions; it is diagnostic only and never affects the exit code.
- Rows with only PARTIAL notes are counted as passing (partial).
- I/O non-wire N5 rows are skipped without an assertion that their count equals the workers-owned count.

### 12. Before any "qualified" label
Next-release gate (PO, 2026-10-28): reviewed trust digest, real upstream commits, 111-case run, stored demo, written python-flint licence verdict, independent harness review, rulings or scoping for the 5 undetermined rows, regeneration of the 28 N5 rows, independent review of containment-helper internals, and owner acceptance.

### 13. Candidate14 (post-release baseline, proposed; supersedes the candidate13 baseline in sections 2 to 4 once its PR merges)
Record: [CANDIDATE14_FREEZE_RECORD.md](CANDIDATE14_FREEZE_RECORD.md). Label stays PRERELEASE; nothing is "qualified". Counts and hashes only.
- index.json sha256 11165e906a7e03c6e217847a980db6d949aea210ed47697c34838b7f13331203. 2668 rows in files (2358 non-graph + 310 graphs). 3 excluded by id; **frozen 2665**. Candidate13's rows are byte-identical except the 3 null rows; 21 N6 rows added. Generated twice and again after a source-copy correction, byte-identical every time (controller 7afa68a1ce05dd1ebb95eed360d4770d6b55b077ec4993f576ca69f440b0f19a, manifest 5233264ea38ff07613db957654cd079aea3c10445dc8624fd76fd56b65ea0153; first-run manifest and controller hashes are superseded).
- Excluded by id: N5-restore-q3-dropped-with-extra-stream-added, N5-restore-q3-control-extra-stream-only-accepted, N6-restore-q3-with-knowledge-regression. The consumer filter in section 2 applies unchanged with these 3 ids. The three null-at-record rows (N5-nondict-plain-record-null, N5-nondict-union-plain-null, N5-nondict-union-array-element-null-index1) are now frozen, with no per-row flag (the union row targets Execution.definition_use because Execution.price is nullable).
- **Frozen means reproducible, not validated.** Provisional (flagged) groups: N5 28 rows (the 3 null rows are frozen-unflagged; frozen N5 census 31 = 28 + 3), N6 21 rows (18 proof rows, 2 NON-PROOF controls, 1 excluded; no independent adjudication; two groundings by precedent: the worker input_invalid wrapper and the half-open end of the capture domain), and 39 W3 ids (assumption-2: 9 B, 9 B3, 9 graphs; PR 34: 6 rows, 6 graphs). Carried flags from candidate13 (61 rows and 30 graphs) are unchanged. W3 disclosure: independent regeneration was attempted in candidate14 and found infeasible at byte level; no difference was found and none was disproven; these ids are not independently confirmed (NOT_REGENERATED 39/39).
- Replay (harness-c14, all exit 0): library 405/405, N4 58/58, graphs 306/306, I/O 1793/1793, workers 100 (58 full, 42 partial), tamper pass, isolation 14/48/24. The independent replay review reproduced 32 of the 42 partial rows by his own mechanism count and relied on the harness count for the other 10, so the 42 is partly harness-reported.
- Q4 and the narrower-rollup clause are scoped out by PO ruling (not held). Unreviewed harness scripts, controller non-claims, digest-level graph evidence and the python-flint notice (section 9) are unchanged.

### 14. Windows c14 evidence (recorded 2026-10-28; PO final ruling A3/A4)
Label: **Windows evidence recorded, not qualified.** Counts, hashes and limits only; no fixture values and no private paths. This section supersedes the Windows evidence wording of sections 1 and 11 for the c14 cohort (option-features a25c9d1, option-feature-io e156963, option-feature-workers 8795f3e); the release label remains PRERELEASE.

Final wording (PO):
> Windows evidence recorded, not qualified: on Windows 11 x64 with CPython 3.12, installed packages built from the pinned commits were checked offline: 108 unit tests, c14 replay (library 405, N4 58, graphs 306, I/O 1793, workers 100 with 2 disclosed gaps), tamper and isolation checks, a 5-scenario integration, a 111-case direct versus stored full-payload parity run (378 rows, passed), and a stored demo (exit 0, outputs hashed; read-only census after the run: 5 runs, 45 result rows, 4 tables, 56 rows). Limits: single run, synthetic data, Windows x64 cp312 only; atomic replace of an existing output file was not verified; demo page provenance text not verified; the trust digest was computed in-project and its independent re-review is pending; python-flint and duckdb receipt source commits are wheel-hash stand-ins; no production data, performance or other-platform proof.

#### 14a. A5 requalification result (CPython 3.12.10, cp312 win_amd64)
- Packages built offline from the pinned commits; all four wheels rebuilt byte-identically from the sdists. Wheel sha256: contracts 99c7d32ccc180a3767eceea90cc2d9fd33af4e70306675ca3e4c01f9a00a3b1f; features bff933e69ef9ab9f21b404ce76292fc35ae50290898f8f8c33b1dcc611c78c31; io 41fdd6534add0eebcdb1e4e2aa366387e3d83ad0e1445996b9359248b3f7eadd; workers 0cb39281ecb639aacd4b83779756b47d146f5ad6f5ffef378bfc2ebfe112ecf3. Third-party wheels matched recorded hashes (python-flint 0.9.0, duckdb 1.5.6).
- 108 unit tests OK (contracts 14, features 48, qualification 8, io 24, workers 14). The qualification suite needs both R25_INDEPENDENT_WIRE_FIXTURES and R25_INDEPENDENT_WIRE_FIXTURES_SHA256 set.
- c14 replay on installed packages: library 405/405, N4 58/58, graphs 306/306, I/O 1793/1793, workers 100 run (58 full, 42 partial, 0 failed) with 2 disclosed gaps (W3-admission-monotone-extension, W3-admission-null-to-nonempty). Equal to the candidate14 replay counts.
- Tamper: control accepted, T1 to T7 rejected, T8 and T9 rejected at verify. Isolation: 14, 48 and 24 tests, post-test check ok. Both are reconstructions, and their exit codes are not verdicts (see 11c).
- 5-scenario integration: full parity, retry verified, changed-source conflict rejected; 283 files verified.
- The trusted manifest digest ce4913556d48a46067b4fb61a82041a3170422f2349137ebc100879c6e834c15 was computed in-project and not independently reviewed; its independent re-review (A1) is pending.
- Harness changes were limited to replacing the source-path override with a module-origin assertion in the five replay scripts, one wheel-directory line in the isolation script, and a CRLF-to-LF conversion; expectations and the fixture pin were untouched.

#### 14b. A3: 111-case direct versus stored parity, pass
- integrate (state passed, 111 cases, 111 replayed) and compare (state passed, 111 cases, 378 result rows), both exit 0 with empty stderr, run on the installed c14 cohort with the R25 precedent runner, comparison helper and fixture. fixture-r25.json sha256 37f79537ebbf69cd0f39d4f52745954ab6e9e90a0f486dca7e7bacdc5945eb23; FOUR_COHORT_FULL_PAYLOAD_PARITY.json sha256 8e4f3d677bc60378dc38402aba724e48bcb7aeb2bb3d2db8ee7334fcf4946a9f.
- Counts recomputed independently: 111 cases, 378 expected rows, 378 rows in both reports, 111 stored result files, 111 replays.
- Output sha256: integration-report.json a4ddc869520238d6eee44d5bb2d9369e0d7b0a3f7d6e285abebd7f9933b8a540; DIRECT_WORKER_STORED_FULL_PARITY.json 3a3e46a4d829a4ab9d35f402c165b9324a39aca78979402faf60ddbcc4865aea; synthetic-results.duckdb 5b443571923d522e15f3faa89f4f6d65bd893bea960fa3246a6328232af542a4.
- Glue only: the candidate configuration was generated from the c14 cohort configuration; no R25 file was edited.

#### 14c. A4: stored demo, exit 0 with outputs hashed and a read-only census
- Demo exit 0, empty stderr. Outputs are hashed, not independently reviewed. synthetic-output.duckdb sha256 prefix 0b6c4912.
- Read-only census after the run, made by an independent script that reopened the database read-only (sha256 unchanged before and after): 5 runs, 45 result rows, 4 tables, 56 rows (generations 5, option_schema 1, result_rows 45, source_bindings 5). The earlier "5 tables, 45 rows" wording was a misstatement and is withdrawn.
- The read-only reopen was an independent census, not a feature of the demo.
- Known gaps, not run for R26: (1) atomic replace of an existing output file was not verified (the scratch swap used identical files and exercised neither a content change nor a failed replace); R26 makes no atomic-replace claim. (2) The demo page provenance text was not verified; the check string was a file hash prefix, not page text, so that check is dropped and not counted as passed.

#### 14d. Containment residual risk
Containment is process-tree kill plus hash pins; it does not restrict network, filesystem writes, memory or environment; hash checks are not atomic with use. The independent review of the helper (approve-with-conditions) found no network or filesystem confinement, no memory, CPU or process-count limit, an inherited environment, trusted but unpinned interpreter-side site code, an advisory lease and lock, and no protection against a hostile same-user process. It is not a sandbox. The 15 contract pins were recomputed from files and match.

#### 14e. Contract inputs held in private records (hashes only)
Fourteen of the fifteen contract inputs pinned by the controller are private-record inputs: they are not in this repository and not at a repo commit. The fifteenth, the fixture completion clarification, is in this repository. sha256 of the 14:
1. 9252fe9daddf996a64df7d4847f9f28cbf356287d7e4266717a9165a0491eabd
2. bbd0d64300073132224ab08cb21972d4791a70bbef075daf697308c540e7e500
3. 3f5b5e8d696ff468a7398f9e5c5fb2fbfabb49d436e9fbba5d81de944f549eee
4. e1e5b8801cd84268cf1187de56cbf9a3e2b36f54e248dd11afc8dc655016611c
5. f1560f234da478d12653281d5c93023379a44b6893f44b6793815e8f47716511
6. 49c1600c63ac5c84dfcd95a3e5774391fd13f72f96f8c22fb8dffa2d0557e120
7. f7fa65402ed467c0f316ca0ae471762aadd96f712c55a22fc3900e740aefae80
8. e8a007d11612ed36c8b745e6c7c3b910db4c078ffabb4274b2545bae7d30a573
9. 73a2e9a252c197f14d3885fccdc0dcf5c461ef6a6329d8b659cd74ec228a8363
10. 348e6ce7d042e80f1a9e1013f349fa445393c71eeea35497328e8cd216f1e520
11. 587cb0e13fb6648edf8356529529ef77dc3313b1adf057c1b987c2ba99be093e
12. e7a7e5aff68391123454ba0222185b8159c353c527909f65f9f5a424d244d76c
13. 461a3d136124d7f54ae38e975b1c89045389205d362496c5ecfab91ed44277a8
14. 755583c02ad975ad8dfe547170c8a2b2569047f6bf8cec5868a9ed6e7a9ff7b8

#### 14f. python-flint licence wording
python-flint 0.9.0 is installed by pip and is not vendored or shipped by us. Its Python bindings are MIT; the wheel bundles LGPL-3.0-or-later GMP, MPFR and FLINT as separate DLLs that the user may replace (plus winpthreads and the gcc runtime under a GCC exception); see the python-flint licences. Reviewed verdict: accepted for pip-dependency use with this notice; not accepted for vendoring or bundling (frozen executable, image, vendored wheel) without a separate review, which would require the COPYING files and a source offer.

#### 14g. Disclosed as pending or not done
- A1: independent re-review of the trust digest against the c14 hashes is pending; this section is updated when it lands. It does not block R26.
- A2: python-flint and duckdb receipt source commits remain wheel-hash stand-ins; no upstream fetch was done.
- Not run: a content-change or failed-replace check of the demo output (known gap in 14c).
- Evidence is a single run on synthetic data, Windows x64 cp312 only. No production data, performance or other-platform proof.
- The R27 harness findings in 11c remain open.
