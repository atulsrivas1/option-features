# R26 native local qualification — October 21, 2026

**Native candidate, UNRELEASED; full R26 is not accepted.** This dated checkpoint records completed local evidence separately from the active qualification queue. EQ188/EQ189/EQ215/EQ191/EQ192 remain Test; actual EQ190 equity integration and EQ193 full acceptance remain gated. No registry, tag, package publication or Released/Done transition is authorized. See [canonical native scope](https://github.com/atulsrivas1/equity-features/issues/533), [independent admission](https://github.com/atulsrivas1/equity-features/issues/592), [source packet](README.md) and [public pipeline evidence](https://github.com/atulsrivas1/option-feature-workers/pull/5#issuecomment-6310760982).

## Exact sources and artifact admission

Four optional distributions at0.1.0a1 form the new family. `option-flow-contracts`/`option_flow_contracts` and `option-flow-features`/`option_flow_features` are the pure closure; `option-flow-io`/`option_flow_io` and `option-flow-workers`/`option_flow_workers`, plus DuckDB1.5.6, form the full five-distribution runtime. The original R25 packages and their separate six-distribution verifier remain unchanged.

| Built distribution | Exact source commit |
|---|---|
| option-flow-contracts, option-flow-features | `bd3b980bf90f0bbcaab9084dd11a3893665ac7b2` |
| option-flow-io | `8214c2252a62d25b2e18292524eec008c34fc4ac` |
| option-flow-workers | `d17ed52916149dd93ca3f8d3215e4313655dc82c` |

Actual local builds produced original wheels, original sdists and wheels rebuilt from those sdists on both supported platforms. Each platform's18 recorded build commands exited0. Independent artifact review checked source-export mappings (including explicitly audited Windows line-ending conversions), the sole staged build-marker overlay, sdist source contents, wheel RECORD/dependency pins, bundled notices and complete original/rebuilt wheel-member parity. Complete member bytes match within each platform; ZIP archive bytes need not match and cross-platform artifact equality is not claimed. Native DuckDB was checked against its admitted archive/notices and upstream source identity `802a345bb627435d2a05d63cb74454fa98b60b5e`; no upstream native reproducible-build claim is made.

The independently admitted qualification manifests bind the exact five wheel hashes, sources, build receipts and roles:

| Actual environment | Artifact form | External manifest digest |
|---|---|---|
| Windows11, CPython3.12.10 | original wheel | `b2b6928fc1cfedb9348ce6f98170ac2d2b2810abef381a49fd4bc56db65a06e2` |
| Windows11, CPython3.12.10 | original-sdist rebuilt wheel | `f1668f17bdd4d2f9596eb1031e88834b464fab57bd2cbe5db5c133f98449ea6e` |
| Ubuntu24.04/WSL, CPython3.12.3 | original wheel | `1054ec0bab76c1ebf77fc3e461c1497dd150dfb994ed1d65a41f18d9ab730af0` |
| Ubuntu24.04/WSL, CPython3.12.3 | original-sdist rebuilt wheel | `a4ea2d2e590249f8b87ef4203e1c6b8e2bea50034bb3e5b0797890ce8a5adc72` |

These are manifest-domain digests, not wheel archive hashes or public download instructions. The Windows native wheel SHA256 is `09ff51b230219f0d8b47fc8a1e17fb595ba9fab0c3d96a6de4d00b8ff86b3cf1`; the Linux native wheel SHA256 is `bc9619ed7d4ffa117b5155d84b44794366bb6635178d78ed5e13a6024845c757`.

Subsequent reviewed source heads were library `48ec370182afd0a057fc597e2c4cfd40b163af45`, I/O `145e03d4b2462f9d9938629c8145128825373286` and workers `fd564c04a33c2fa8342028fd6c6d463985a2f614`. Read-only Git comparisons against the exact build sources reported no changes in `packages/flow-contracts`, `packages/flow-features`, `packages/flow-io` or `packages/flow-workers`. Later documentation, independent tooling and the library example do not relabel the built sources or automatically qualify new execution paths. Fresh final-head review is still required after this documentation update.

## Completed component and independent numerical checks

All four installed platform/form cohorts passed126 component methods each,433 complete independently fixed result rows and19 expected structural/input errors. Each cohort contained exactly five admitted distributions; installed verification checked90 files before and after execution. Runs used actual installed `python -I -B` interpreters, no PYTHONPATH/source-tree substitution, one serialized process/inflight/I/O/backend thread and an explicitly granted256MiB logical reservation. This is not an enforced RSS/native-allocation ceiling. Test consumers and producers retained recorded before/after identities.

The independent full artifact SHA256 is `e0ab2065eaa62f3ac1b5442b0045f0e58a1c3c5a6ee45d20464f201a34316b51`. Its66 full case groups/68 invocations cover424 rows; five additional baseline/side controls cover nine rows, giving433 complete canonical payload/digest/wire comparisons. Nineteen input errors are separate. These row/case counts are not unique feature counts: the native API declares44 outputs, three additional reserved equity outputs remain unsupported, and44 scenario definitions are not themselves execution evidence. Genuine replay and full-prefix restore are included in the admitted independent cases.

The reference author/materializer and fresh independent fixture reviewers were separate from production authors; expected rows were not generated by calling the production evaluator. Actual separate Linux reference generation reproduced the same7,388,816-byte artifact and digest. Historical failed artifacts/attempts remain retained. In particular, the complete-row consumer initially hit five new-control KeyErrors; its repaired run matched431/433 rows and exposed a producer baseline-priority defect. Known null/incomplete baseline causes now precede future-reference causes, preserving all diagnostics/counts/clocks/dependencies. The unchanged independent artifact then passed all433 rows and19 errors. The development62-method result and installed126-method closure describe different checks, not interchangeable counts. [Library history](LIBRARY_IMPLEMENTATION.md) preserves the original receipts and limitations.

## Completed original-wheel integration and stored browser inspection

Actual original-wheel integrations passed on Windows and Linux. Each performed101 checks covering full independent result parity through direct→strict wire→worker→transactional storage/readback, genuine chronological replay and retained-prefix restore/corrections, retries, cancellation, commit acknowledgement/recovery seams, changed-key conflicts and selected schema/content corruption. Each compared all433 rows and19 expected errors. Source/fixture identity and fresh installed verification were retained. Normalized command structure was `python -I -B tools/flow_qualify_integration.py` with externally pinned artifact, manifest/provenance anchors, an explicit runtime lease and a new private output destination; actual absolute commands/interpreters and stdout/stderr are retained in coordinator evidence.

| Original-wheel run | Wall seconds | Process CPU seconds | Process-lifetime peak RSS bytes | Integration receipt SHA256 |
|---|---:|---:|---:|---|
| Windows | 1140.867952 | 1134.59375 | 94089216 | `46a2c5b220901122ff01a7404e35dc74bafd093e1ac0d5a15fab6b4239b1192a` |
| Linux | 1026.595728 | 1022.979941 | 109998080 | `d14707fc36bc7ac6abac47a9257529455b06e4f32b95152001d4cb88d3712e61` |

These timings describe instrumented qualification workloads, not representative performance or a speed comparison. RSS is the OS process-lifetime high-water measure, not per-case allocation or a promised ceiling. Simulated transaction faults are not an OS-crash/power-loss durability proof; cancellation preserves actual committed generations and prior replay cuts.

The coordinator also actually exported and inspected a browser view from fresh reads of the accepted Windows-original output databases. The whitelisted synthetic dataset digest was `7d04abd68f9af6932c8760dd751368bdce3d3bfd4b581bd7ece1a2b087dc86a1`; display/export identity and the source database bytes were checked, and the existing R25 display remained intact. This is stored-output inspection of that executed cohort, not a second independent numerical oracle or evidence for unexecuted forms. No server URL or private evidence path is a public dependency.

## Still pending at this snapshot

The remaining serialized native queue is active; do not relaunch its jobs or infer outcomes from source review. Linux rebuilt-wheel integration is the current queued integration step, followed by Windows rebuilt integration. Four-cohort tamper checks, twelve fresh layer-isolation closures, original-cohort R25 preservation regression and four balanced/hot resource measurements remain unproven here. Reviewed harnesses/plans and an independently generated/recomputed64-execution balanced/hot pack exist; expected-data qualification is not measured resource proof. No result from a future queued job is included in this report.

The [pure example](../../examples/r26/README.md) is independently source-reviewed at `48ec370182afd0a057fc597e2c4cfd40b163af45`, with original synthetic F01 wires, and is not yet executed. After the current queue releases resources, a fresh installed pure-closure run must compare its exact23-row canonical output against the independent F01 expected wire. Adding an example requires that execution evidence; unchanged package sources do not establish it.

Finish the queue and example, reconcile actual terminal receipts, obtain fresh independent final evidence/PR review, and merge eligible native source work under the local-proof agreement. Preserve the separately retained full-release gates: real accepted compatible EQ153/EQ158 equity producers, actual EQ190 cross-market integration and independent paired expectations, all-seven-story EQ193 acceptance, and owner publication approval followed by actual release/readback. Native admission does not remove these gates. Historical R25 publication approval applies only to R25.
