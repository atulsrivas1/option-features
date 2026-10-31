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
- Suite: `.github/run_suite.ps1 m3a` (the existing runner; as docs/CI.md: `python -B -m unittest discover -s tests/m3a -p 'test_*.py'` with `PYTHONPATH=packages/features/src;packages/option-contracts/src;tests/m3a;tests;.`). `tests/` has no `__init__.py`, so tests always run by discovery, never by dotted module name; one story's file runs as `python -B -m unittest discover -s tests/m3a -p test_<story>.py` (same PYTHONPATH). S01 adds the `m3a` suite line to `.github/workflows/ci.yml`.
- Failing-first: the first commit of every story adds its test file and a stub module whose functions raise `NotImplementedError`; the PR description shows the red run (`powershell .github/run_suite.ps1 m3a` output with the failing row ids) and then the green run. One test method per row id so a failing row is named (as tests/m2/test_m2b_rows.py).
- Ownership rule: every fixture row and perf row has exactly one FIRST OWNER (section 3a). The first owner adds the row's test method and makes it pass; every later story must keep it green (the full m3a suite runs on every PR). Rows whose first owner is not yet merged are skipped with that story id in the skip message (never silently filtered); the skip list shrinks to zero by S11. A story may also run item-level checks on rows it does not own (stated in section 3), which never count as ownership. The integrity test (S01) encodes the section 3a table and asserts it covers every row id exactly once.

## 3. Stories
Size: S = under a day, one sitting review; M = one to two days; L = split before pull (none is L). "Owns" = the only story that may create or edit these files.

| Id | Title | Owns (files) | Fixtures it must pass (author set: file, families) | Depends on | Performance gate fed | Size | Ready |
|---|---|---|---|---|---|---|---|
| S01 | M3a common: reason and code sets, rounding, envelope, harness | `option_features/m3a_common.py` (closed reason set, structural code list, half-even 8-decimal rounding, 10^-8 integer storage form, labels sort R-132, M3a `Result` fields incl. `frame`, param echo R-154/R-158/R-184); `tests/m3a/m3a_harness.py`, `tests/m3a/test_m3a_common.py`, `tests/m3a/test_m3a_integrity.py`; ci.yml `m3a` suite line | first owner of: author2 `m3a_cases_units.json` M3A-U-001..021 (21); integrity: manifests of author1..4 and the section 3a table | none | M3A-B9 (canonical bytes), B4 envelope overhead | S | Ready (frozen) |
| S02 | Store extension: per-series k up to 252 and the two read forms | `option_features/flowstore.py` (edit: `add_series(series_id, k)`, k cap 252 for scalar and minute series, M2 series keep cap 60, lazy sorted copy); new `option_features/m3a_history.py` (`scalar_baseline`, `same_minute_column` returning {values, sessions, n}; view-read codes order of IO contract section 4); `tests/m3a/test_m3a_history.py` | first owner of: author2 `m3a_cases_history.json` all 73 M3A-H rows (incl. view-read structural rows H-014, 015, 021, 022, 027, convention rows H-066..074, memory rows H-046..049, 075); perf W09, W10, R03, R04, D10 | S01 (rounding, codes); view-read order as PR 112 (position 3: `malformed_type`, then `invalid_session_window`) | M3A-B6 append >= 25,000 rec/s, B7 round trip, B8 store <= 768 MiB (1 GiB hard), B5 read share | M | Ready (frozen) |
| S03 | 25-delta point kernel (both conventions) | `option_features/delta25.py` (input: per expiry and right the eligible strikes with cached IVs, forward, T, rate, q, convention; output: {status, reason, value, strikes_used, evaluations}; bracketed search, first crossing, delta-linear interpolation R-09/R-10, no extrapolation); `tests/m3a/test_delta25.py`, `tests/m3a/adapt_delta25.py` | first owner of: perf W03 (B2), W14 (B12). Item-level checks only (rows first-owned by S05/S09): the `p25`/`c25` items of author1 delta25 rows; own unit tests with a stubbed solver for the four uncovered solver reasons (R-128 note) | none (uses `chainiv` read-only) | M3A-B1 (<= 0.1 s per convention), B2 (<= 2 ms per point), B12 (<= 200 evaluations per chain) | M | Ready (frozen) |
| S04 | Tenor kernel 9, 30, 91 days | `option_features/tenors.py` (input: per-expiry {days, status, reason, atm_iv}; output per tenor {status, reason, iv, method, expiries_used}; total-variance interpolation via the M1 `iv_30d(target_days)` rule, R-104, R-139, R-178); `tests/m3a/test_tenors.py`, `tests/m3a/adapt_tenors.py` | first owner of: perf W04 (B3). Item-level checks only (rows first-owned by S05): the `tenors` items of TEN-01..43 | none | M3A-B3 (<= 0.1 s from cached ATM IVs) | S | Ready (frozen) |
| S05 | Surface frame M3A-0 (assembler) | `option_features/surfaceframe.py` (builds from an `IVChain`: per-expiry forward, ATM IV, coverage gates R-103/R-104, contract_reasons, labels R-105, calls S03 and S04, frame status and reason order R-141, `no_eligible_contract` R-106, solver failure exclusion R-109); `tests/m3a/test_surfaceframe.py` | first owner of: author1 SUR-01..104 (104), COV-01..34 (34), AME-01..20 (20), all D25 rows except D25-V1..V7 (112), TEN-01..43 (43) = 313 whole rows; perf W02 (B1) | S01, S03, S04 | M3A-G0 surface share, B1 end to end (frame increment over cached IVs) | M | Ready (frozen) |
| S06 | Chain point outputs V5, V6, V8, V11, V21 | `option_features/surface_points.py` (M3A-4, M3A-5, M3A-7, M3A-10, M3A-11 from a frame; fire rules, `direction`, inclusivity, failure precedence R-137, R-162); `tests/m3a/test_surface_points.py` | first owner of: author3 all rows of `m3a_cases_v5.json` (40), `v6` (34), `v8` (66), `v11` (38), `v21` (40) = 218, incl. their structural-tagged rows; perf W05 (B4); near-threshold rows non-gating as tagged | S01, S05, S09 | M3A-B4 (<= 1 ms per name, <= 110 ms per 103 names), G0 point share | M | Ready (frozen) |
| S07 | Change outputs V4, V7, V10 (prior readings) | `option_features/surface_change.py` (M3A-3 both `iv_form`, M3A-6 n-th prior session, M3A-9 change and sign_change; empty store no_prior_reading, fewer than n insufficient_history R-136; no hidden state); `tests/m3a/test_surface_change.py` | first owner of: author3 all rows of `m3a_cases_v4.json` (80, incl. V4-S-01..09, V4-Cx1), `v7` (44), `v10` (64) = 188; uses author3 `m3a_g5_priors.json` | S01, S02, S05, S09 | M3A-B4, G0 point share | M | Ready (frozen) |
| S08 | History rank outputs V1, V3, V9 | `option_features/surface_rank.py` (M3A-1, M3A-2 both forms on `atm_iv` and `iv30` minute series, M3A-8 on `skew25` or `skew25_fwd`; M2 Q2 tie rules, `x` and `tail`, zero_range_history, reason order R-131 item 7); `tests/m3a/test_surface_rank.py` | first owner of: author2 all rows of `m3a_cases_V1.json` (52), `V3` (80), `V9` (69) = 201, incl. their structural-tagged rows; perf W06 (B5), W07 (B5n); uses `m3a_g4_histories.json` fingerprints | S01, S02, S09 | M3A-B5 (<= 50 us V1/V9, <= 150 us V3 per form), B5n | M | Ready (frozen) |
| S09 | Structural validation wrappers | `option_features/m3a_validate.py` (request list, 18 positions, type-first per field, M2 decimal grammar, spot representability, M1 ValueError mapped to codes; `validate="scanned"` default and `"full"`; positions applied per output R-120/R-168; convention ignored on V1 to V7 R-174); `tests/m3a/test_m3a_validate.py` | first owner of: author4 M3A-STRUCT-001..157, M3A-STRUCT-AUX-001..045, M3A-LANE-001..006; author1 COV-35..37 and D25-V1..V7 (frame request validation) = 218. Not the structural-tagged rows of author2/3 (their output stories own them) | S01; PR 112 merged | scanned validation inside G0 (O(contracts read)); B11 | M | Ready (frozen) on PR 112 (docs/m3a-contract-codes): request position 15 is `threshold_out_of_range`, then `invalid_direction` (R-185); `invalid_param` is not a code. S09 does not merge before PR 112; author4's `invalid_direction` rows are added then, first owner S09 |
| S10 | M3a series builder M3A-12 | `option_features/surface_series.py` (from a session-close frame and the minute frames: `atm_iv_close`, `iv30_close`, `skew25`, `skew25_fwd`, `term_30_91` scalars, `atm_iv` and `iv30` minute grids, rounded once to 10^-8 integers R-48, series_id "<UNDERLYING>/<lane>/<metric>"); `tests/m3a/test_surface_series.py` | first owner of: perf W08 (B6, 181,692 records of the workload manifest). Keeps S01 units and S02 history rows green; first-owns no fixture row | S02, S05 | M3A-B6 records set (181,700), B8 | S | Ready (frozen) |
| S11 | Runner, G0 bench and gate tools | `tools/m1_runner/*` (M3a outputs in the unit, `delta_evaluations` in the response R-171; defaults unchanged), new `tools/m3a_g0_bench.py`, `tools/m3a_benchmark.py` (B1 to B13 from the author4 workload manifest and runner contract); `tests/m3a/test_m3a_runner.py` | first owner of: perf G001, W01, W11, W12, W13, W15, D01..09, D11, D12, E01..12, C01..14, R01, R02, R05..08, S01..03, K01..06 (58); uses `m3a_workload_manifest.json`, `M3A_PERF_RUNNER_CONTRACT.md`; removes the last skips | S01 to S10 | M3A-G0 (5 s p95 / 15 s, one worker, compute only), B9, B10, B11, B13 | M | Ready (frozen); pulled last |

Totals: 11 stories, 0 L.

## 3a. First-owner table (by row id; verified)
| Story | Fixture rows (first owner) | Perf rows (first owner) |
|---|---|---|
| S01 | 21: M3A-U-001..021 | 0 |
| S02 | 73: M3A-H-* (all) | 5: W09, W10, R03, R04, D10 |
| S03 | 0 (item checks on D25 `p25`/`c25`) | 2: W03, W14 |
| S04 | 0 (item checks on TEN `tenors`) | 1: W04 |
| S05 | 313: SUR-*, COV-01..34, AME-*, D25-* except D25-V1..V7, TEN-* | 1: W02 |
| S06 | 218: V5-*, V6-*, V8-*, V11-*, V21-* | 1: W05 |
| S07 | 188: V4-*, V7-*, V10-* | 0 |
| S08 | 201: M3A-V1-*, M3A-V3-*, M3A-V9-* | 2: W06, W07 |
| S09 | 218: M3A-STRUCT-*, M3A-STRUCT-AUX-*, M3A-LANE-*, COV-35..37, D25-V1..V7 | 0 |
| S10 | 0 | 1: W08 |
| S11 | 0 | 58: G001, W01, W11, W12, W13, W15, D01..09, D11, D12, E01..12, C01..14, R01, R02, R05..08, S01..03, K01..06 |
| Total | 1,232 (author1 323, author2 295, author3 406, author4 208) | 71 (G 1, W 15, D 12, E 12, C 14, R 8, S 3, K 6) |

Check (PO and Architect, 2026-10-30, fixtures as on this branch): a script read every `m3a_cases_*.json` of author1..4 and `m3a_perf_resource_rows.json`, applied the id rules above per file and asserted each row id has exactly one first owner: 1,232 fixture rows and 71 perf rows, 0 unowned, 0 duplicates. S01's `test_m3a_integrity.py` encodes the same table and repeats the assertion in CI; a new row (for example the `invalid_direction` rows after PR 112) is added to this table in the same PR.

## 4. Definition of Ready check (playbook LIFECYCLE section 4, Variant B: no UI)
| Item | Result |
|---|---|
| 1 Screen source | none by design: library modules, no UI; guarded by the m3a suite |
| 2 Contract | docs/m3a RULED (matrix, IO contract, budgets, R-01 to R-185); frozen; S09 and the S02 view-read order take the PR 112 codes (`invalid_direction`, `invalid_session_window`; no `invalid_param`) |
| 3 Data line | synthetic chains and histories from qualification/synthetic/m3a; server-side per the capability matrix; no source mixing; adapters RQ |
| 4 Gate | release gate M3a; budgets in M3A_GATE_BUDGETS.md are hard acceptance gates |
| 5 No open build blocker | none for S01 to S08, S10, S11; S09 merges after PR 112; dependencies in the table |
| 6 Testable criteria | the row files plus the named gate; PO checks at pull |
| 7 Owner-pending wording | none |

## 5. Order and parallelism (at most 3 Developers)
| Wave | Dev A | Dev B | Dev C |
|---|---|---|---|
| 1 | S01 (S, no dependency) | S03 (M, no dependency) | S04 (S, no dependency) |
| 2 | S02 (M, after S01) | S05 (M, after S01, S03, S04) | S09 (M, after S01 and PR 112) |
| 3 | S07 (M, after S02, S05, S09) | S08 (M, after S02, S09) | S10 (S, after S02, S05) then S06 (M, after S05, S09) |
| 4 | S11 (M, after S01 to S10) | code and architecture reviews | Tester support (no build) |
Every story has one slot; a wave's stories depend only on stories merged in earlier waves (in wave 3 Dev C builds S10 then S06; both depend only on wave 2). Critical path: S03 (M) -> S05 (M) -> S10 (S) -> S06 (M) -> S11 (M); S07 and S08 run beside S10 and S06. No two stories share a file. WIP: 1 story per Developer, at most 3 PRs in review, at most 3 waiting for the Architect, at most 2 for the Tester (LIFECYCLE section 3). Merge order follows the dependency column; main stays green (skips name the owner story).

## 6. Story flow per PR
build -> code review (fresh agent, not the author) -> architecture review (Architect, fresh) -> UI review N/A: no UI -> Tester pass (independent re-run, below) -> PO accept -> merge by the coordinator after CI green on the merge commit. Two review rounds max (third only for a correctness defect). One decision file per PR in docs/decisions/. `gh auth switch --user atulsrivas1` and re-verify before every push or merge.

## 7. Tester re-run plan
1. Per story PR: an independent Tester (not an author of that fixture set where avoidable, never the Developer) checks out the PR head, runs `sha256sum -c MANIFEST.sha256` in each set, runs `.github/run_suite.ps1 m3a` and all existing suites (contracts, features, m1, m2, p1) and records a results table: rows passed per file, skips with owner story, M1/M2 output hashes unchanged (tools/m2b_output_hash.py).
2. Per story with a gate: the Tester runs the story's bench (S02 B6/B7/B8, S03 B1/B2/B12 per convention, S04 B3, S06/S07 B4, S08 B5/B5n) at least 30 repeats after one warm-up, budgets printed verbatim with "synthetic workload, relative engineering budget". Developer and Tester evidence labelled apart. Passing a unit smoke check does not replace the bench.
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
1. PR 112 (docs/m3a-contract-codes, open): adds `invalid_direction` at request position 15 and `invalid_session_window` at view-read position 3, and removes `invalid_param` (R-165/R-175 wording superseded); author4 then adds the rows (first owner S09, table 3a updated). S09 merges only after it.
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
