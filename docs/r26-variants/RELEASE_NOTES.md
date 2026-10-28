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
- Candidate13's record has had no independent freeze review. An audit (approve), a source review and a controller review (both approve-with-conditions, applied) exist.
- Consumer filter (structured keys only, never substring search): skip a row if `freeze_excluded` is true, or `contract_status == "UNDETERMINED_CONTRACT_GAP"`, or (obligations) `completeness != "complete"`. Rows with a non-empty `non_asserted_subfields` must not assert those subfields. `UNFROZEN_CANDIDATE` on most N4 and N5 rows is not an exclusion. Verify whole-file sha256 first; files are never edited.

### 3. Frozen subject to regeneration (flagged)
Consumers must expect these ids may change.
- **Total flagged: 89 rows and 30 graphs** (61 rows and 30 graphs carried from candidate12, plus 28 new N5 rows). No flag has been removed.
- **28 N5 rows** (19 wire, 9 restore; no graphs): authored from clarification text only; they depend on the INFERRED field_set parent pointer and the Q3 pointer. The 5 null-at-non-nullable rows rest on inferred non-nullability. They have no independent semantic adjudication beyond the audit (G27), no library-level evaluation and no graphs (G29).
- Other flagged groups, all carried: assumption 2 (9 B rows, 9 B3-integer-price rows, 9 graphs; assumption 2 is a PO product ruling, not contract text; encoding was confirmed, not regenerated, and the 9 graphs were not separately inspected); PR 34 rows (4 roll-unresolved + 4 F4 capture-domain, with graphs; `excluded_ids` is stored as a sorted literal and its order is compared literally by the replay harness); two-control F4 rows (4 rows and 4 graphs); root A after K rows (3); every other candidate12 flag per the candidate12 record, section 3.
- Two-control detail: the two expected-root rows (span, rolling) fail before the PR 42 fix and pass after; the two nonexpected-root rows pass both ways and do not discriminate (G30). The PO ruled them valid negative controls.

### 4. Excluded undetermined rows (5, all N5)
Excluded by id (`freeze_excluded` true, `UNDETERMINED_CONTRACT_GAP`):
- N5-nondict-plain-record-null
- N5-nondict-union-plain-null
- N5-nondict-union-array-element-null-index1
- N5-restore-q3-dropped-with-extra-stream-added
- N5-restore-q3-control-extra-stream-only-accepted

The first three: nullability of a record or union object is not declared in the contract text. The fourth depends on the unspecified admission of an extra stream. The fifth pins only "no checkpoint_cut_mismatch"; its expected results are masked. No graph is excluded.

### 5. Open contract gaps and held items
- Q4 (suffix checks): HELD, not asserted.
- Narrower-rollup clause: HELD. The F4 rollup-wider-than-capture-domain row was removed; **c-domain and c-completeness are untested**.
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

### 9. python-flint licence (review pending)
python-flint 0.9.0 (win_amd64 wheel, sha256 8f1059536b7393e48b1444894c3b54ce1b961e4aa4a356e19217b26690f20db0) is not MIT-only. Its licence expression is MIT AND LGPL-3.0-or-later AND others (with a GCC runtime exception); bundled licences cover libflint 3.6.0, gmp 6.3.0, mpfr 4.2.2, the gcc runtime and winpthreads. Wheel inspection is not a legal review. A licence review of LGPL-3.0-or-later redistribution obligations is still required before any release that ships or depends on it.

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

### 12. Before any "qualified" label
Next-release gate (PO, 2026-10-28): reviewed trust digest, real upstream commits, 111-case run, stored demo, written python-flint licence verdict, independent harness review, rulings or scoping for the 5 undetermined rows, regeneration of the 28 N5 rows, independent review of containment-helper internals, and owner acceptance.
