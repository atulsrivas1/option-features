# M3a gate budgets (synthetic-size stage)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Author: Architect, 2026-10-30. Status: PROPOSAL for PO ratification and independent review; budgets are set before any M3a code is measured. Every number is a "synthetic workload, relative engineering budget"; none is a measurement and none states a real-size or live claim. Extends B1-B12 and the M2 gates (docs/m2/M2_GATE_BUDGETS.md); B1-B12 stay hard acceptance gates as written. Companions: M3A_CAPABILITY_MATRIX.md, M3A_FIXTURE_REQUIREMENTS.md, M3A_RULING_LIST.md, M3A_IO_CONTRACT.md.

Owner main goal: PERFORMANCE. Use cores, memory and caches as fully as possible to calculate faster without breaking correctness. Design consequences: every contract IV is solved once per chain and cutoff and reused by every output; the 25-delta points are found by a bracketed search over strikes, not by computing delta for every contract (R-74); history is read through the M2 store with no new copies; batched, cached and parallel paths must equal the single-process reference exactly.

## 1. Two stages (V3 section 3)
| Stage | Where | Sizes | Status |
|---|---|---|---|
| Synthetic-size | every release, M3a included | generated workloads of the stated sizes | gated here |
| Real-size | RQ only | recorded chains and sessions | not measured, no claim; revised by PO ruling only |
The label "synthetic workload, relative engineering budget" and the budget value print beside every measurement. Windows x64, CPython 3.12; Linux is a process check, not claimed.

## 2. Measured baseline the numbers derive from (synthetic workload, relative engineering budget)
| Source | Measured | Used for |
|---|---|---|
| B4 chain ATM IV, size M / L | 0.063 s / 0.099 s p50 (budget 1 s / 4 s) | M3A-B3 |
| B5 30-day IV, size M | 0.021 s p50 (budget 1.5 s) | M3A-B3 |
| B6 IV part, size M, compute-only | 1.40 s p50, 1.53 s p95 (budget 5 s / 15 s) | M3A-G0, B1 |
| M2-G0 full output set (OC5, OC6, IV, ATM, 30d, P1 outputs), 1 worker | 2.41 s p50, 2.66 s p95 | M3A-G0 headroom |
| B2 OC5 one contract | 13 us p95 (budget 50 us) | per-series read gates |
| M2-B3 rank and M2-B2 read, per series | budget 50 us / 200 us, met at 2,000 series | M3A-B5 |
| M2-B1 store append, M2-B17 round trip | floors 25,000 records/s write, 50,000 read, met | M3A-B6, B7 |
| M2-B9 all M2 outputs (not yet measured), M2-B11 | budgets 1.2 s, 5 s | G0 sum of sub-budgets |
| B7 whole workload | 2.38 min at 24 workers, 1.78 min at 48 (budget 170 min) | M3A-B10 |
| Per-worker peak RSS | 142 to 495 MiB (budget 2 GB) | M3A-B8 |

## 3. Workload (fixed before measuring; frozen facts recorded by the Tester)
| Item | Value | Basis |
|---|---|---|
| Underlyings, evaluated sessions, cutoffs | 5, 5, 78 per session (B7 shape) | V3 stage rule |
| Chain size | S 500, M 2,000, L 6,000 contracts (smile surface generator, 8 expiries bracketing 9, 30 and 91 days for M) | as B4 to B6 |
| History | 252 prior complete sessions per underlying for the iv30, skew25 and term series (session-close values); the atm_iv and iv30 minute series on 252 sessions (R-126, R-153); generated values, not solved from chains | design 252-session look-back, 20 minimum |
| Universe for batch gates | 103 names (the covered universe) as series of values, not 103 solved chains | design |
| Grid | 60 s, 390 values per full session | M2 |
| Unit | underlying x session x cutoff (runner key SYN1/03/045); a unit reads an immutable history view | M1 runner |
Generators: Tester, seeded, deterministic, SYNTHETIC tag, LF, no absolute paths; the surface has known skew, curvature and term values.

## 4. First task gate: M3A-G0, full-output B6 with the M3a surface set, one measurement
Why first: the M3a outputs add work to a B6 that already carries the M2 outputs (M2-B9 and M2-B11 are still unmeasured); the sum of sub-budgets must be checked before M3a code is optimized. M3A-G0 supersedes any separate whole-B6 gate.
| Item | Rule |
|---|---|
| Output set | the M2-G0 set (OC5, OC6, per-contract IV, ATM IV for all expiries, 30-day IV, P1 outputs) plus the M2 flow outputs of M2-B9 (budget 1.2 s) plus the M3a set: surface frame (25-delta put and call IV per expiry, tenors 9, 30, 91 days) and the point outputs M3A-3 to M3A-7, M3A-10 and (if R-01 accepts V21) M3A-11 on that chain; history-free (history outputs are gated by M3A-B5). This is the single B6-with-M2-and-M3a gate; there is no separate B10 |
| Workload | one underlying, size M, one cutoff, the all-valid-quote smile chain |
| Measured as | ONE timed unit that computes every output; never a sum of separately timed parts; monotonic ns around the compute call only |
| Budget / hard | 5 s p95 / 15 s (B6 as written), nearest-rank p95 |
| Count | gated at ONE worker only (in-process reference path); 2, 4 and N workers informational with efficiency; N = cap per the PR 72 ruling (min(physical cores, floor(aggregate / 2 GB)), aggregate default 50 percent of host RAM) |
| Repeats | one warm-up, at least 30 timed repeats per count, unit set rotated; p50, p95, max and all samples |
| Tool | tools/m1_runner and the M2-G0 bench phase extended to call the M3a modules (tool change only; defaults unchanged) |
| Gate figure | compute-only; the figure with input synthesis is printed beside it, not gated |
| Sum check (reported, not a gate) | 2.66 s measured M2-G0 p95 plus the M2 flow budget 1.2 s (M2-B9) plus the M3a increment budget 0.1 s (M3A-B1) is 3.96 s, 1.04 s under 5 s (unchanged by owner decision 2: the ATM form reuses the per-expiry ATM IVs of the surface frame, so there is no extra solve and no extra G0 work beyond selecting the nearest eligible expiry; the G0 output set adds the V3 and V4 point outputs for both forms, O(1) each, inside the 1 ms per-name budget of M3A-B4); if the measured M2-G0 plus the sum of M3a measurements exceeds 5 s the PO rules before release |
| Machine, authorship | frozen and written before the first repeat (CPU, cores, RAM, OS build, Python build, power plan, idle load); independent Tester runs and signs |
| A miss | reported as a miss; over budget with hard met needs a PO ruling; hard breach blocks; never an edit of a budget |

## 5. Gates
Pass = p95 within Budget (rates: the slowest 5 percent still meets it); Hard = fail even if the PO rules otherwise. Single worker unless stated. At least 30 repeats after one warm-up. Inputs built before the timer; compute and with-input-synthesis reported separately.
| Gate | Workload | Metric | Budget | Hard | Rationale |
|---|---|---|---|---|---|
| M3A-B1 | (measured PER delta convention, spot and forward, each must meet the budget, R-157) surface increment, size M, one cutoff, contract IVs cached: bracketed delta search (at most 200 delta evaluations, M3A-B12), 25-delta put and call IV for every expiry, tenors 9, 30, 91 | wall | <= 0.1 s | 0.5 s | per-delta cost about 250 us implied by M3A-B2 (2 ms for about 8 deltas): 200 x 250 us = 50 ms; a naive delta for all 2,000 contracts would cost 0.5 s, so the gate forces the bracketed search; batch of 103 chains (informational) 103 x 0.1 s |
| M3A-B2 | (per delta convention, R-157) one 25-delta point (one expiry, one side), IVs cached | per point | <= 2 ms | 10 ms | about 8 delta evaluations plus one exact interpolation |
| M3A-B3 | constant-maturity tenors 9, 30, 91 from cached ATM IVs, size M | wall | <= 0.1 s | 0.5 s | B5 measured 0.021 s p50 including the solve |
| M3A-B4 | point outputs M3A-3 to M3A-7, 10, 11 per name; batch of 103 names | per name; batch | <= 1 ms; <= 110 ms | 5 ms; 550 ms | O(1) arithmetic per name; 103 x 1 ms plus 7 ms of batch overhead; hard = 5x |
| M3A-B5 | history ranks: V1 and V9 (session-close values, up to 252) per series; V3 same-minute across up to 252 sessions per series, measured for BOTH forms (`atm_iv` and `iv30` series) | per series | <= 50 us (V1, V9); <= 150 us (V3, each form) | 200 us; 600 us | M2-B3 class (50 us / 200 us at 20 values); V3 reads 252 grid entries without a sort; the form selector adds no work (one series is read per request) |
| M3A-B5n | the same for 103 names x 3 series at one cutoff (names fixed at 103, no series-count ratio), for each `iv_form` | wall | <= 20 ms (V1, V9); <= 50 ms (V3), each form | 80 ms; 200 ms | absolute times only; linear in names; a request reads one form per name, so a both-forms scan costs 2x the V3 time (informational) |
| M3A-B6 | store append of the M3a series: 252 sessions x 103 names x 7 series (about 181,700 records: 2 minute series and 5 scalars incl. skew25_fwd; was 6 series, about 155,700) | records/s | >= 25,000 | 5,000 | M2-B1 floor (met); 7.3 s at the floor |
| M3A-B7 | store persistence round trip of the same set, canonical LF text and mmap snapshot | records/s write, read | >= 25,000, >= 50,000 | 5,000, 10,000 | M2-B17 floors; identical content hash after the round trip |
| M3A-B8 | memory: peak RSS per process; store bytes at retention 252 | peak RSS; store (private bytes) | <= 2 GB (B9); store <= 768 MB | 4 GB; store 1 GB per worker | B9 as written. RULED 2026-10-30 (PO): the M3a store budget is 768 MB with the hard limit unchanged at 1 GB per worker; bytes per series are reported; sorted copies are built lazily and not for scalar or minute-series reads that do not need them (a Developer design duty); the gate measures private bytes. Store against the M2 formula (series x K x grid x 8 B x copies): two minute series per name (atm_iv, iv30) = 2 x 103 x 252 x 390 x 8 B = 162 MB raw and 486 MB with the M2 layout (raw, sorted copy, merged array), inside 768 MB; about 162 MB when sorted copies and merged arrays are skipped for these reads; scalar series (5 per name) about 1 MB. k = 252 exceeds the M2 hard cap of 60: deliberate additive store change (matrix section 6) |
| M3A-B9 | determinism (extends B12) | result hashes | identical | identical | section 7 |
| M3A-B10 | B7 with M3a: 5 x 5 x 78 cutoffs, size M, all outputs, run once | wall | <= 170 min | 240 min | governing B7; 60 min is an informational owner target at N workers |
| M3A-B11 | cutoff sweep: 78 cutoffs of one session, one underlying, size M | sweep wall / (78 x single-cutoff wall) | <= 1.1 | 1.5 | no growth with sweep length; every cutoff re-solves its own IVs (spot changes), so no reuse is claimed |
| M3A-B12 | (per delta convention, R-157) bracketed-search count: delta evaluations per chain, size M (enforces R-74) | count | <= 200 | 400 | 8 expiries x 2 sides x about 12 evaluations; a count near 2,000 means the search degenerated to all contracts |
| M3A-B13 | scaling: 4 workers versus 1 on the 5-underlying compute phase | p50 wall ratio | >= 2.0x | none | S01 rule; N/A under 4 physical cores; correctness rows must pass at every count |
Whole-run informational lines: aggregate RSS at N workers, history-view transfer cost per worker (mmap, M2-B16 hard limits 15 s and 1 GB), cache hit rates.

## 6. Regression (unchanged)
Original B2 to B5, B6, B7, P1-T1 and every M2 gate that exists on main are re-run unchanged on the M3a build with the same budgets; M1 and M2 outputs must keep their result hashes. Any change is a failure or a PO ruling.

## 7. Determinism, equivalence, cache, memory rules (hard; any failure blocks regardless of speed)
1. Determinism (M3A-B9): per-cutoff and whole-run SHA-256 of canonical result bytes identical at 1, 2, 4 and N workers, 3 repeats; across batch sizes 1, 7, 64, all; shuffled unit, name, expiry and contract order; shuffled arrival of quotes that share a timestamp (documented tie rules decide); history appended in canonical session order only; the store content hash identical at every worker count. Results are keyed and emitted in canonical order, never completion order.
2. Batched versus single: the batched path and the one-surface-at-a-time path give equal bytes for every M3a output, status and reason, with zero tolerance (all outputs are exact functions of the returned IV values and delta values); a status or reason flip is a failure. Interpolation and rank outputs also equal an independent Tester reference (exact rationals).
3. Cache rules: cold and warm give the same bytes. Changing any one input field or parameter (any contract field, quote field, spot, rate, yield, cutoff, tenor, delta target, thresholds, K, session, lane, history content) changes the key and recomputes. IV and delta caches are per chain and cutoff; a hit never crosses chains, cutoffs, underlyings or lanes. Caches are per process, bounded (size and eviction recorded), eviction does not change bytes, statistics go to the log only.
4. Memory: peak RSS per process within B9 including the store (store 768 MB budget, 1 GB hard per worker, RULED; cap per PR 72); allocation growth over 30 repeats: slope of post-GC RSS <= 1 MB per repeat, last-10 mean within 5 percent of first-10; retention bounded at the configured K.
5. Failure semantics unchanged: a crashed, missing or duplicate unit fails the run with no partial output.

## 8. Measurement rules
1. Budgets, workload and machine are frozen in the plan before the run; the report prints budgets verbatim beside measurements.
2. A missed budget is reported as missed; relaxing needs a PO ruling and is never an edit to this file.
3. Library, history store, runner and end-to-end are measured separately so a miss can be attributed.
4. Stress inputs (maximum chain, deep wings, sparse chains, 252-session histories with planted ranks) come from the Tester generators, independent of developer code.
5. Not measured: network, live latency, recorded chain sizes, adapter ingest, real-size history.
6. Developer and Tester evidence are labelled apart; the Developer does not sign off its own proof; the report carries the label sentence verbatim; a docs reviewer greps it against docs/RELEASE_NOTE_TEMPLATE.md label rule 1.

## 9. Assumptions for PO ruling (all PROPOSED)
- A1: the numbers are derived from the section 2 baseline; they are proposals, not measurements.
- A2: M3A-G0 gates the compute-only figure at one worker; with-synthesis is printed.
- A3: history is generated values, not solved chains (252 sessions of solves per series would dwarf every gate); a solved-history spot check belongs to RQ.
- A4: the 103-name universe is a batch size for the read and rank gates, not 103 solved chains.
- A5: M3A-B1 assumes delta from the existing certified path (R-05); if the PO rules a float delta with a certified fallback the gate stays and the structure is the Developer choice.
- Owner decision 3 (R-155 to R-161): two delta conventions. The certified delta is computed only for the requested convention (no combined-request gate); M3A-G0 is measured for the default (spot) and the forward run is reported against the same sub-budgets; M3A-B1, B2 and B12 apply per convention. Store: one more scalar series per name (skew25_fwd), negligible bytes (about 0.2 MB); M3A-B6 records 181,700. No budget changes are proposed; the G0 sub-budget sum is unchanged because only one convention is computed per request.
