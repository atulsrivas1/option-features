# M3a build plan (stories, order, parallelism, close checklist)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Author: PO and Architect, 2026-10-30. Status: PLAN (decided by PO and Architect; no owner item). Inputs: docs/m3a/M3A_CAPABILITY_MATRIX.md, M3A_IO_CONTRACT.md, M3A_GATE_BUDGETS.md, M3A_FIXTURE_REQUIREMENTS.md, M3A_RULING_LIST.md, docs/decisions/2026-10-30-m3a-fixtures.md (R-162 to R-185), docs/FEATURE_STATUS.md, docs/M1_CLOSE.md, docs/m2/M2_STORE_API.md, docs/playbook/ADAPTATION.md and LIFECYCLE.md (story flow, Definition of Ready), fixtures under qualification/synthetic/m3a/author1..author4.

Owner goals applied: performance budgets are hard gates (every story names the gate it feeds; a story is not accepted while a Developer bench shows its sub-budget missed); synthetic data only; no adapter, vendor or network work (RQ).

## 1. Architecture rules every story follows
1. Pure modules beside `chainiv.py` in `packages/features/src/option_features/`, single-threaded kernels, no I/O, no clocks. Parallelism only through the existing runner (tools/m1_runner); no result byte depends on worker count.
2. IV is solved once per chain and cutoff by `chainiv.IVChain` (certified solver unchanged) and passed in; no M3a module solves IV. The 25-delta search is bracketed over strikes (R-74), never delta for every contract.
3. History is read through the M2 store only; no second copy of history. Sorted copies are lazy and skipped for scalar and same-minute reads (M3A-B8 duty).
4. No M1, M2, P1, R25 or R26 result byte changes; existing gates re-run unchanged (budgets section 6).
5. Every M3a value that is solver-derived is a binary64 float internally and a half-even 8-decimal string at the envelope (one rounding helper, story S01).
6. Interfaces between stories are plain records named here, so a story can be built and tested before its consumers exist. Each story writes its module docstring with the record shape it returns.

## 2. Shared test harness and failing-first rule
- `tests/m3a/m3a_harness.py` (owned by S01): loads the four author sets read-only, checks every `MANIFEST.sha256` (LF-normalised), decodes the tagged non-JSON types (R-65, R-125), and exposes `rows(set, file, where=...)`. It never imports an author's `m3a_ref*.py` or oracle; expectations come only from the row files.
- Each story owns ONE test file `tests/m3a/test_<story>.py` and, if it needs one, ONE adapter `tests/m3a/adapt_<story>.py` (maps row inputs to its own API). No story edits another story's test or adapter.
- Suite: `.github/run_suite.ps1 m3a` (the existing runner, `unittest discover -s tests/m3a`); S01 adds the `m3a` suite line to `.github/workflows/ci.yml`.
- Failing-first: the first commit of every story adds its test file and a stub module whose functions raise `NotImplementedError`; the PR description shows the red run (`powershell .github/run_suite.ps1 m3a` output with the failing row ids) and then the green run. One test method per row id so a failing row is named (as tests/m2/test_m2b_rows.py).
- Rows owned by a later story are skipped with the owning story id in the skip message (never silently filtered); the skip list shrinks to zero by S11. The integrity test (S01) counts all rows of all four sets so no row is dropped.

## 3. Stories
Size: S = under a day, one sitting review; M = one to two days; L = split before pull (none is L). "Owns" = the only story that may create or edit these files.

| Id | Title | Owns (files) | Fixtures it must pass (author set: file, families) | Depends on | Performance gate fed | Size | Ready |
|---|---|---|---|---|---|---|---|
| S01 | M3a common: reason and code sets, rounding, envelope, harness | `option_features/m3a_common.py` (closed reason set, structural code list, half-even 8-decimal rounding, 10^-8 integer storage form, labels sort R-132, M3a `Result` fields incl. `frame`, param echo R-154/R-158/R-184); `tests/m3a/m3a_harness.py`, `tests/m3a/test_m3a_common.py`, `tests/m3a/test_m3a_integrity.py`; ci.yml `m3a` suite line | author2 `m3a_cases_units.json` (21 rows, rounding and units); integrity: manifests of author1..4, total row counts | none | M3A-B9 (canonical bytes), B4 envelope overhead | S | Ready (frozen) |
| S02 | Store extension: per-series k up to 252 and the two read forms | `option_features/flowstore.py` (edit: `add_series(series_id, k)`, k cap 252 for scalar and minute series, M2 series keep cap 60, lazy sorted copy); new `option_features/m3a_history.py` (`scalar_baseline`, `same_minute_column` returning {values, sessions, n}; view-read codes order of IO contract section 4); `tests/m3a/test_m3a_history.py` | author2 `m3a_cases_history.json` (73 rows, H family: missing and incomplete days skipped, max 252, no zero-padding, k 252 and 60, scalar in total, lane in series id, content hash); author4 structural rows of the view-read list; author4 perf rows G7, R (store bytes) | S01 (rounding, codes) | M3A-B6 append >= 25,000 rec/s, B7 round trip, B8 store <= 768 MiB (1 GiB hard), B5 read share | M | Ready (frozen) |
| S03 | 25-delta point kernel (both conventions) | `option_features/delta25.py` (input: per expiry and right the eligible strikes with cached IVs, forward, T, rate, q, convention; output: {status, reason, value, strikes_used, evaluations}; bracketed search, first crossing, delta-linear interpolation R-09/R-10, no extrapolation); `tests/m3a/test_delta25.py`, `tests/m3a/adapt_delta25.py` | author1 `m3a_cases_delta25.json` (119 rows, per-side `put25_iv`/`call25_iv` items; spot and forward, target on strike, non-monotone, steep skew, no_delta_bracket, min strikes); unit rows with a stubbed solver for the four uncovered solver reasons (R-128 note) | none (uses `chainiv` read-only) | M3A-B1 (<= 0.1 s per convention), B2 (<= 2 ms per point), B12 (<= 200 evaluations per chain) | M | Ready (frozen) |
| S04 | Tenor kernel 9, 30, 91 days | `option_features/tenors.py` (input: per-expiry {days, status, reason, atm_iv}; output per tenor {status, reason, iv, method, expiries_used}; total-variance interpolation via the M1 `iv_30d(target_days)` rule, R-104, R-139, R-178); `tests/m3a/test_tenors.py`, `tests/m3a/adapt_tenors.py` | author1 `m3a_cases_tenors.json` (43 rows) | none | M3A-B3 (<= 0.1 s from cached ATM IVs) | S | Ready (frozen) |
| S05 | Surface frame M3A-0 (assembler) | `option_features/surfaceframe.py` (builds from an `IVChain`: per-expiry forward, ATM IV, coverage gates R-103/R-104, contract_reasons, labels R-105, calls S03 and S04, frame status and reason order R-141, `no_eligible_contract` R-106, solver failure exclusion R-109); `tests/m3a/test_surfaceframe.py` | author1 `m3a_cases_surface.json` (104), `m3a_cases_coverage.json` (37), `m3a_cases_american.json` (20), and the frame-level assertions of delta25 and tenors rows | S01, S03, S04 | M3A-G0 surface share, B1 end to end (frame increment over cached IVs) | M | Ready (frozen) |
| S06 | Chain point outputs V5, V6, V8, V11, V21 | `option_features/surface_points.py` (M3A-4, M3A-5, M3A-7, M3A-10, M3A-11 from a frame; fire rules, `direction`, inclusivity, failure precedence R-137, R-162); `tests/m3a/test_surface_points.py` | author3 `m3a_cases_v5.json` (40), `v6` (34), `v8` (66), `v11` (38), `v21` (40); near-threshold rows non-gating as tagged | S01, S05, S09 | M3A-B4 (<= 1 ms per name, <= 110 ms per 103 names), G0 point share | M | Ready (frozen) |
| S07 | Change outputs V4, V7, V10 (prior readings) | `option_features/surface_change.py` (M3A-3 both `iv_form`, M3A-6 n-th prior session, M3A-9 change and sign_change; empty store no_prior_reading, fewer than n insufficient_history R-136; no hidden state); `tests/m3a/test_surface_change.py` | author3 `m3a_cases_v4.json` (80), `v7` (44), `v10` (64); author3 `m3a_g5_priors.json` | S01, S02, S05, S09 | M3A-B4, G0 point share | M | Ready (frozen) |
| S08 | History rank outputs V1, V3, V9 | `option_features/surface_rank.py` (M3A-1, M3A-2 both forms on `atm_iv` and `iv30` minute series, M3A-8 on `skew25` or `skew25_fwd`; M2 Q2 tie rules, `x` and `tail`, zero_range_history, reason order R-131 item 7); `tests/m3a/test_surface_rank.py` | author2 `m3a_cases_V1.json` (52), `V3` (80), `V9` (69); `m3a_g4_histories.json` fingerprints | S01, S02, S09 | M3A-B5 (<= 50 us V1/V9, <= 150 us V3 per form), B5n | M | Ready (frozen) |
| S09 | Structural validation wrappers | `option_features/m3a_validate.py` (request list, 18 positions, type-first per field, M2 decimal grammar, spot representability, M1 ValueError mapped to codes; `validate="scanned"` default and `"full"`; positions applied per output R-120/R-168; convention ignored on V1 to V7 R-174); `tests/m3a/test_m3a_validate.py` | author4 `m3a_cases_structural.json` (157), `m3a_cases_structural_aux.json` (45), `m3a_cases_lane.json` (6); selector rows of author1/2/3 tagged structural | S01 | scanned validation inside G0 (O(contracts read)); B11 | M | Ready (stub) for the bad-direction code only: R-185 `invalid_direction` and R-175 D13 `invalid_param` are not yet in the IO contract list; the Architect docs PR (section 7, item 1) closes it before S09 merges; rows for it are added by author4 then |
| S10 | M3a series builder M3A-12 | `option_features/surface_series.py` (from a session-close frame and the minute frames: `atm_iv_close`, `iv30_close`, `skew25`, `skew25_fwd`, `term_30_91` scalars, `atm_iv` and `iv30` minute grids, rounded once to 10^-8 integers R-48, series_id "<UNDERLYING>/<lane>/<metric>"); `tests/m3a/test_surface_series.py` | author2 history rows on series content and naming (H family not owned by S02), units rows on storage form | S02, S05 | M3A-B6 records set (181,700), B8 | S | Ready (frozen) |
| S11 | Runner, G0 bench and gate tools | `tools/m1_runner/*` (M3a outputs in the unit, `delta_evaluations` in the response R-171; defaults unchanged), new `tools/m3a_g0_bench.py`, `tools/m3a_benchmark.py` (B1 to B13 from the author4 workload manifest and runner contract); `tests/m3a/test_m3a_runner.py` | author4 `m3a_perf_resource_rows.json` (71 rows: D, E, C, R, S, K, G0), `m3a_workload_manifest.json`, `M3A_PERF_RUNNER_CONTRACT.md`; removes the last skips | S01 to S10 | M3A-G0 (5 s p95 / 15 s, one worker, compute only), B9, B10, B11, B13 | M | Ready (frozen); pulled last |

Totals: 11 stories, 0 L. Fixture rows covered: author1 323, author2 295, author3 406, author4 208 plus 71 perf rows; every row has exactly one owning story.

## 4. Definition of Ready check (playbook LIFECYCLE section 4, Variant B: no UI)
| Item | Result |
|---|---|
| 1 Screen source | none by design: library modules, no UI; guarded by the m3a suite |
| 2 Contract | docs/m3a RULED (matrix, IO contract, budgets, R-01 to R-185); frozen for all stories except the S09 direction code (stub, above) |
| 3 Data line | synthetic chains and histories from qualification/synthetic/m3a; server-side per the capability matrix; no source mixing; adapters RQ |
| 4 Gate | release gate M3a; budgets in M3A_GATE_BUDGETS.md are hard acceptance gates |
| 5 No open build blocker | none for S01 to S08, S10, S11; S09 as stated; dependencies in the table |
| 6 Testable criteria | the row files plus the named gate; PO checks at pull |
| 7 Owner-pending wording | none |

## 5. Order and parallelism (at most 3 Developers)
| Wave | Dev A | Dev B | Dev C |
|---|---|---|---|
| 1 | S01 (S) then S04 (S) | S02 (M) | S03 (M) |
| 2 | S09 (M) | S10 (S, after S05) or S08 (after S09) | S05 (M, after S01, S03, S04) |
| 3 | S06 (after S05, S09) | S08 (after S02, S09) | S07 (after S02, S05, S09) |
| 4 | S11 (after all) | code and architecture reviews | Tester support (no build) |
Critical path: S03 -> S05 -> S07 -> S11. S01, S03, S04 have no M3a code dependency and start together; S02 starts against the S01 rounding helper (S01 is S, merges first). No two stories share a file. WIP: 1 story per Developer, at most 3 PRs in review, at most 3 waiting for the Architect, at most 2 for the Tester (LIFECYCLE section 3). Merge order follows the dependency column; main stays green (skips name the owner story).

## 6. Story flow per PR
build -> code review (fresh agent, not the author) -> architecture review (Architect, fresh) -> UI review N/A: no UI -> Tester pass (independent re-run, below) -> PO accept -> merge by the coordinator after CI green on the merge commit. Two review rounds max (third only for a correctness defect). One decision file per PR in docs/decisions/. `gh auth switch --user atulsrivas1` and re-verify before every push or merge.

## 7. Tester re-run plan
1. Per story PR: an independent Tester (not an author of that fixture set where avoidable, never the Developer) checks out the PR head, runs `sha256sum -c MANIFEST.sha256` in each set, runs `.github/run_suite.ps1 m3a` and all existing suites (contracts, features, m1, m2, p1) and records a results table: rows passed per file, skips with owner story, M1/M2 output hashes unchanged (tools/m2b_output_hash.py).
2. Per story with a gate: the Tester runs the story's bench (S02 B6/B7/B8, S03 B1/B2/B12 per convention, S04 B3, S06/S07 B4, S08 B5/B5n) at least 30 repeats after one warm-up, budgets printed verbatim with "synthetic workload, relative engineering budget". Developer and Tester evidence labelled apart.
3. Differential (fixture requirements section 4): at least 20,000 randomized cases each for 25-delta interpolation, tenor interpolation, rank forms and sign change, expected from the Tester's own reference; run at S03, S04, S08 and S07 acceptance; zero differences.
4. Release run after S11: M3A-G0 first (machine frozen and written before the first repeat, one worker gated, 2/4/N informational), then B1 to B13 and the regression set (B2 to B7, P1-T1, every M2 gate) on the same build; D, E, C, R, S, K rows of author4; B10 run by the Tester (not developer-only as in M1, M1_CLOSE risk 4).

## 8. Mutation-tool use
- Tool: hand-written mutant scripts in the repo pattern (tools/*_mutation_check.py); no third-party mutation package (nothing downloaded). The Tester writes `tools/m3a_mutation_check.py` in its own Tester PR (not a Developer story file), applying each mutant of M3A_FIXTURE_REQUIREMENTS section 6 (at least 40; groups 1 to 8) to the LIBRARY modules in a scratch copy and running the m3a suite.
- Each mutant must be caught by at least one gating row that reads the mutated field; groups 7 and 8 also run through the perf, parallelism and cache rows (S11), which must fail. Results file committed beside the tool; uncaught mutants become a fix story or a new row via the PO.
- The authors' own mutant runs (author1 58, author2 73, author3 54, author4 56 plus 10) proved the rows against the reference code only; they do not replace the library mutation run.

## 9. M3a close-record checklist (docs/M3A_CLOSE.md, PO)
- [ ] Every story S01 to S11 merged with two reviews (architecture, code), Tester pass and PO accept recorded in the PR.
- [ ] m3a suite green with zero skips; all 1,232 rows of author1..4 plus 71 perf rows pass; manifests unchanged.
- [ ] Closed reason set: no reason outside matrix section 5 in any result; three deliberate exceptions (R-46, R-51, R-58) each with at least 4 passing rows.
- [ ] M3A-G0 measured by the independent Tester, machine frozen, compute-only p95 within 5 s (hard 15 s); sum check reported.
- [ ] M3A-B1 to B13 measured; B1, B2, B12 per delta convention; budgets printed verbatim beside measurements; misses reported, never edited; any over-budget-with-hard-met item has a PO ruling.
- [ ] Regression: B2 to B7, P1-T1 and every M2 gate re-run; M1 and M2 result hashes unchanged.
- [ ] Determinism, batched versus single, cache and memory rows (D, E, C, R) pass; store private bytes within 768 MiB, peak RSS within 2 GB.
- [ ] Differentials (4 x 20,000) zero differences; library mutation run results committed, every mutant caught.
- [ ] docs/FEATURE_STATUS.md: V1, V3 to V11, V21 moved to match candidates by the Auditor; V2 re-audited (R-02); label sentence verbatim; docs reviewer grep against docs/RELEASE_NOTE_TEMPLATE.md label rule 1.
- [ ] Follow-ups of docs/decisions/2026-10-30-m3a-fixtures.md section 3 closed or carried with a reason.
- [ ] Linux not claimed ("Linux run as process check, not claimed" if run); synthetic only; PRERELEASE.
- [ ] Retrospective written; HANDOFF.md updated by the PO; M3b readiness (own matrix and fixtures first) stated.

## 10. Prerequisite docs items (Architect, docs-only PRs, not stories)
1. Add `invalid_direction` (R-185) and the D13 `invalid_param` code (R-175) to M3A_IO_CONTRACT.md section 4 with their positions; author4 then adds the rows. Closes the S09 stub.
2. Align MB/GB wording to MiB/GiB in M3A_GATE_BUDGETS.md (coordinator unit decision, fixtures decision section 2).
3. R-178 confirmed by the Architect here: an exact-tenor expiry failing coverage gives `low_surface_coverage`; it is consistent with R-139 (which covers a coverage-excluded BRACKETING expiry at a non-exact tenor). Note added to R-104 in the same docs PR.

## 11. Risks
1. Store change (S02) touches M2 code: M2 hashes and gates must stay byte-identical; mitigated by the regression rerun in every S02 Tester pass.
2. M3A-B1/B12: the 25-delta search can degenerate toward all contracts on steep or non-monotone smiles; the evaluation counter (S03, runner field in S11) makes it visible early.
3. G0 headroom is 1.04 s on paper and M2-B9/B11 are still unmeasured; if the measured sum passes 5 s the PO rules before release (budgets section 4). Mitigation: S11 runs G0 as soon as S05 merges (informational) before the point outputs land.
4. Windows-only canonical hashes for solver-derived values; no cross-platform claim.
5. Tester and Architect are the bottleneck with 3 Developers; WIP limits pause pulls rather than relaxing reviews.
6. Interim design-silent rulings may change on design ratification; a changed answer regenerates the dependent fixtures and reopens the owning story only.

## 12. Owner-level items
None. (No pricing, legal or new principle; the two docs items of section 10 are Architect work.)
