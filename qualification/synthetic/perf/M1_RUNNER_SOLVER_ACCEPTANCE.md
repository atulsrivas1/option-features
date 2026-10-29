# M1 runner and solver acceptance (Tester, independent)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Provenance: SYNTHETIC. Authored from PO_BRAINSTORM_TOP2_RULINGS Part B and the design text only. Mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12. All numbers: synthetic workload, relative engineering budget.

## 0. Rules encoded
- Runner doc wording (test 8): the runner is "opt-in, default single-process". Not enabled by default anywhere. The library stays single-threaded and pure (D4 amended).
- Placement: the runner is the LAST M1 story, started only after OC5, OC6, ATM and 30-day work is accepted.
- Worker cap = min(cores, RAM / B9 peak), B9 peak = measured per-process peak of the B7 workload (2 GB placeholder until the first B7 run); aggregate worker RSS hard limit 8 GB. Requested workers above the cap are clamped and the clamp is reported, never an error.
- Results are merged by unit key only (unit key = set:zero-padded index, or cutoff/underlying/contract index). Completion order, worker count, worker id and timing never appear in the output bytes.
- Solver stage order: Stage 0 Fraction hoist; Stage 1 float-filtered bisection with the written rigorous bound and an always-available certified-fallback switch; Newton only as a bracket seed, accepted only if certified evaluation at BOTH ends of the seeded bracket confirms the root is enclosed. Newton never produces a value. Any identical-result failure rejects the stage.
- Wording: say "identical result bytes". The hyphenated forbidden term for this is reserved for the 111 parity files; also avoid the forbidden list in PO_RELEASE_PLAN_V3 section 5.2.

## 1. Sets (gen_m1_solver_sets.py, seed 20261029, manifest m1_solver_manifest.json)
Flat-vol 10,000 contracts (stated sigma 0.10-0.60, ordinary and near-ATM) and mixed-surface 10,000 contracts (about 10 percent extreme vol 0.01-0.05 or 2-5, 20 percent deep ITM/OTM, 25 percent short expiry 1-7 days, 10 percent long expiry, smile and term shape applied). Inputs only plus a stated sigma; some contracts are unsolvable by design (price rounded to 4 places) and must give the same closed reason in both solvers. Reference result = CURRENT solver output captured by the Tester at run time, stored with its sha256; never authored. Manifest digests pin the inputs.

## 2. The eight tests
| # | Test | Procedure | Pass |
|---|---|---|---|
| 1 | B12 workers | Gate B12 on the two sets and the B6 workload at 1, 2, 4, N workers, 3 repeats each, via the runner contract | all 12 runs per workload give one result_sha256 equal to the single-process run; per-unit rows equal. Platforms: Windows x64 run is the claim; any Linux run is "process check, not claimed" (see A1) |
| 2 | Hoist and filter equality | Run CURRENT solver (reference mode, `solver_mode=reference`) and candidate (`hoist`, then `filter`) on both sets; compare every returned field (value, status, reason, iteration/bracket fields if returned) | identical result bytes for all 20,000 units, per stage (0, 1, seeded-bracket) |
| 3 | Shrunk-bound mutation | Harness requests `solver_mode=filter` with `mutation={"kind": "bound", "bound_divisor": 10}` on the mixed set (and flat set) | at least one unit differs in result bytes from the reference; harness exits non-zero and FAILS THE BUILD if zero differences. The SUT must accept the mutation field and report `mutation_applied: true` and the bound used (default and divided) in the response. A SUT that ignores the mutation is a failure. Also run `bound_divisor: 1` as a control: must show zero differences |
| 4 | Reported metrics | Fields in section 3 | all present and non-null, else the row fails (reported, not budget-gated) |
| 5 | Re-measure | B4, B5, B6, B7 per section 4 | printed beside budgets verbatim |
| 6 | Worker kill | Request with workers >= 2 and `fault={"kind": "kill_worker", "worker": 1, "after_units": 100}` (SUT kills worker 1 hard); also a missing-unit variant `fault={"kind": "drop_unit", "unit_key": key}` | exit non-zero, `errors` non-empty with a message naming the failed worker or unit, and NO results file, no partial digest (results null, result_sha256 null); no stale temp file left in the output directory |
| 7 | Independence | Statement in PERF_NOTES.md | tests authored from this ruling and the design text, not implementation; Tester runs the mutation and platform replays; developer does not sign off the bound proof |
| 8 | Wording | grep runner doc and README for the phrase "opt-in, default single-process" and for the forbidden list | phrase present; no forbidden term |

## 3. Runner JSON contract additions (folded into PERF_RUNNER_CONTRACT.md, contract_version 2; that file is authoritative)
Request: `solver_mode` ("reference"|"hoist"|"filter"|"filter_newton_seed"), `certified_fallback` (bool, forces certified path), `mutation` (null or {"bound_divisor": number}), `fault` (null or as test 6), `set` ("flat"|"mixed"|null), `max_workers_cap` (RAM bytes and per-worker B9 peak used for the cap).
Response additions: `workers_requested`, `workers_used`, `worker_cap` {cores, ram_bytes, b9_peak_bytes, cap}, `arb_calls_per_solve` {p50, p95, max, solves, total}, `wall_ns_by_workers` {"1": [...], "N": [...]}, `peak_rss_per_worker_bytes` [..], `scaling_efficiency` (speedup(N)/N, p50 wall, same machine), `mutation_applied`, `bound_used` {default, applied}, `fallback_count` (units solved by certified fallback), `results_digest_inputs` (sha256 of the input set), `partial_output` (must be false).
Worker count, ids and timings must not influence `result_sha256` or `results`. Output file is written only after every unit is merged (write to temp, rename).

## 4. Re-measure protocol (B4, B5, B6, B7)
1. Machine (CPU, cores, RAM, OS, Python build, power plan) and workload (manifest digest, seed, chain size) frozen and written to the report BEFORE the first run; no changes between runs.
2. Budgets printed verbatim from PERF_ACCEPTANCE.md next to each measurement: B4 1 s/3 s, B5 1.5 s/4 s, B6 5 s/15 s, B7 170/240 min run once (the B7 amendment governs; the TOP2 test 5 figure of 60 min is superseded and only reported).
3. Protocol of PERF_ACCEPTANCE.md section 2 (warm-up, >= 30 repeats for B4-B6, p95). Same measurement for reference and each stage, at 1 and N workers.
4. B7 under 10 minutes on 8 cores is REPORTED, not promised: the report states elapsed time, worker count used, cap, and whether the machine had 8 physical cores. No pass or fail on it.
5. Stage 2 target ("5-20x" is not accepted) is set only after arb calls per solve are measured; until then B4/B5/B6 stay as written.

## 5. Ambiguities
- A1: Test 1 says "Windows and Linux", but PO_RELEASE_PLAN_V3 section 5.2 forbids any Linux claim beyond a process check before RQ. Treated as: Windows claimed, Linux run only as process check. PO to confirm.
- A2: Test 2 compares "every returned field"; the field list is whatever the current solver returns, captured at run time.
- A3: Float price generation may differ by one tick on another platform's math library; digests pin this machine, and the Tester regenerates reference per platform.
