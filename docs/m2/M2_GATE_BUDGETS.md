# M2 gate budgets (synthetic-size stage)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Author: Architect, 2026-10-29. Status: reviewed (PR 75, approve-with-conditions), PO rulings applied (RULED); remaining numbers are proposals for PO ratification; budgets are set before any M2 code is measured. Every number below is a "synthetic workload, relative engineering budget"; none is a measurement and none states a real-size or live claim. Extends B1-B12 (THROUGHPUT_BUDGET.md, PERF_ACCEPTANCE.md); B1-B12 stay hard acceptance gates as written. Companions: M2_CAPABILITY_MATRIX.md, M2_FIXTURE_REQUIREMENTS.md.

Owner main goal: PERFORMANCE. Use cores, memory and caches intelligently and as fully as possible to calculate faster without breaking correctness. Design consequences used below: one pass over the trade stream feeds every flow family; history is stored sorted once and read through cached immutable views; all outputs are exact (no float), so batched, cached and parallel paths must equal the single-process reference exactly.

## 1. Two stages (V3 section 3)
| Stage | Where | Sizes | Status |
|---|---|---|---|
| Synthetic-size | every release, M2 included | generated workloads of the stated sizes | gated here |
| Real-size | RQ only | recorded chains and sessions | not measured, no claim; may be revised by PO ruling only |
The label "synthetic workload, relative engineering budget" and the budget value print beside every measurement. Windows x64, CPython 3.12; Linux is a process check, not claimed.

## 2. Workload (fixed before measuring; frozen facts recorded by the Tester)
| Item | Value | Basis |
|---|---|---|
| Underlyings, evaluated sessions, cutoffs | 5, 5, 78 per session (B7 shape) | V3 stage rule |
| History | 20 complete prior sessions per underlying (25 sessions generated, 21 to 25 evaluated; session k reads the 20 before it) | request 9 interim, K = 20 |
| Chain size | S 500, M 2,000, L 6,000 contracts | as B4 to B6 |
| Series count N for per-series gates | 500, 2,000, 6,000 (contract-level worst case; name-level is 5 series) | PROPOSED worst case |
| Grid | 60 s, 390 values per session and series | matrix section 5 |
| Trades | median 20 and p99 1,000 prints per contract per session (proposal) with the print total of one size-M unit frozen at about 40,000 prints (2,000 x median 20; the generator scales the tail to the total); stream sizes 1e5 and 1e6 prints for rate gates | PROPOSED; measured median, p99 and unit total frozen in the manifest, rechecked within +/- 10 percent before every run |
Generators: Tester, seeded, deterministic, SYNTHETIC tag, LF, no absolute paths.

## 3. First task gate: M2-G0, full-output B6 as one measurement
Why first: docs/M1_CLOSE.md section 3 risk 3 and section 1: B6 for the full output set has never run as one measurement; the 1.53 s p95 is the IV part. It runs before any M2 code and again as M2-B11.
| Item | Rule |
|---|---|
| Output set | OC5, OC6, per-contract IV, chain ATM IV (all expiries), 30-day IV, plus the P1 outputs: spread and midpoint, `sign_aggregate` (touch policy), `window_premium`, single-reference shares (short-dated, OTM), `quote_count_coverage` |
| Workload | one underlying, size M (2,000 contracts), one cutoff, the all-valid-quote chain (every contract has a valid regular quote; the M1 gate chain), P1 trade stream per the section 2 trade facts |
| Measured as | ONE timed unit that computes every output on the chain; never a sum of separately timed parts. Timer: monotonic ns around the compute call only |
| Budget / hard | 5 s p95 / 15 s, B6 as written, p95 by nearest rank |
| Counts | M2-G0 is GATED at ONE worker only (in-process reference path, B6 as written). 2, 4 and N workers are informational: per-unit compute wall inside a worker while all workers run distinct units, with efficiency, plus the pool wall of N x 30 units. N = cap per the PR 72 ruling: min(physical cores, floor(aggregate / 2 GB)), aggregate default 50 percent of host RAM |
| Repeats | one warm-up, at least 30 timed repeats per count, unit set rotated; report p50, p95, max and all samples |
| Tool | tools/m1_runner and tools/m1_runner_bench.py (phase b6): `workload.py` is extended to call the P1 modules and to record P1 inputs (a tool change only; no library change; defaults unchanged: opt-in, default single-process) |
| Gate figure | compute-only (timer around the call after inputs are built). The figure with input synthesis (generator and ingest) is measured and printed beside it, not gated. M1 record for the IV part: 1.53 s compute-only p95; 5.0 s with input synthesis; 2.80 s p95 on the gate chain after Stage 2 (8.62 s before the stages). PROPOSED, PO to confirm (A2) |
| Machine | frozen and written before the first repeat: CPU model, physical and logical cores, clocks, RAM, OS build, Python build, power plan, other load idle (< 5 percent). M1 numbers came from 2x Xeon Platinum 8160, 48 physical cores, 254 GiB; a different machine is stated and M1 numbers are not compared across machines |
| Authorship | the independent Tester runs and signs; the Developer does not sign off its own run |
| A miss | reported as a miss. A p95 over budget with hard met needs a PO ruling before release; a hard breach blocks. A budget is never edited to fit. A miss also schedules the already-planned Newton bracket seed (M1 close, "not built by design") for a PO ruling; it does not change any budget |

Measured M2-G0 workload facts (Developer, PR 77): the trade stream is a developer-authored construct with a uniform 20 prints per contract (40,000 per size-M unit); the median 20 / p99 1,000 tail of the section 2 proposal is NOT modelled, and the windowing cost is mostly insensitive to it (one index build and two bisect queries per contract). Beside the IV figure: of 2,000 contracts 985 solve (261 invalid_quote, 744 american_itm, 10 price_out_of_bounds), so the IV time is the cost of 985 certified solves plus the gating of the rest.

## 4. Gates
Pass = p95 within Budget (rates: p5 of the sample, i.e. the slowest 5 percent still meets it); Hard = fail even if the PO rules otherwise. Single worker unless stated. At least 30 repeats after one warm-up. Inputs built before the timer; compute and with-input-synthesis reported separately.
| Gate | Workload | Metric | Budget | Hard | Rationale |
|---|---|---|---|---|---|
| M2-B1 | history append. Gate unit = series-metric-session record (5 metrics per series, per M2-B13). Workload: seal 25 sessions x 2,000 contract series x 5 metrics = 250,000 records, each with 390 grid values (sparse for contract series) and a total | records/s | >= 25,000 (one session of 10,000 records in 0.4 s; the whole 250,000 in 10 s) | 5,000 | sort once per seal; the cost is paid once and repays every read |
| M2-B2 | history read, warm: rank-ready view of 20 sessions for one series | per series | <= 50 us | 200 us | B2 style (OC5 13 us p95 measured against 50 us budget): the read is bisect on 20 sorted arrays |
| M2-B2c | the same, cold (first read after seal builds the merged sorted array for median) | per series | <= 2 ms | 10 ms | built once per series and session; 7,800 values |
| M2-B2n | batch of N views, warm | N = 500 / 2,000 / 6,000 | 25 / 100 / 300 ms | 100 / 400 / 1,200 ms | 50 us x N, hard 4x; ratio gate on the same row: statistic = median of 30 paired ratios t(6,000)/t(2,000), Budget 3.6, Hard 4.0 (cache effect); the absolute times stay the gates |
| M2-B3 | F2/F19 percentile rank (upper_share and rank_le), 20-session history: intraday form (7,800 values) and end-of-day form (20 values) | per series | <= 50 us | 200 us | same family as B2; exact integer counts, Fraction only at output |
| M2-B3n | the same, N series at one cutoff | N = 500 / 2,000 / 6,000 | 25 / 100 / 300 ms | 100 / 400 / 1,200 ms | linear; ratio gate as M2-B2n (median of 30 paired ratios, Budget 3.6, Hard 4.0) |
| M2-B4 | F10/F20 median baseline ratio, N series, one cutoff (median from the cached view; end-of-day from 20 values) | per series; N = 2,000 batch | <= 50 us; <= 100 ms | 200 us; 400 ms | median is O(1) on the cached view, O(20 log 20) at end of day |
| M2-B5 | F1, F4, F17 window family over a trade stream of 1e5 and 1e6 prints (each family alone) | prints/s | >= 100,000 | 20,000 | P1-T1 rate (100,000 records/s, hard 20,000 = B1 hard); time(1e6)/time(1e5) <= 12 |
| M2-B6 | F7 strike and expiry concentration over 1e5 and 1e6 prints | prints/s | >= 100,000 | 20,000 | one dictionary update per print, same class as B5; same ratio rule |
| M2-B7 | F18/F19 volume aggregation over 1e5 and 1e6 prints | prints/s | >= 200,000 | 40,000 | two integer counters per print, no price multiply: half the work of B5 |
| M2-B8 | F12 episode scan over grid points: one session of 390 points per name, and 1e6 points in a stream | points/s | >= 500,000 | 100,000 | a comparison and a counter per point; a session in about 1 ms |
| M2-B9 | all M2 outputs for one underlying, size M, one cutoff, history warm, compute-only. Formula: one shared pass over the frozen unit total of about 40,000 prints (0.8 s at the M2-B10 floor of 50,000/s) plus 2,000 series x about 4 reads each (F2a, F2b, F2c, F10; F20 and F19 read at end of day only) = 8,000 reads x 50 us = 0.4 s, plus the F12 scan (about 1 ms per name); sum 1.2 s. A fused single read per series is an allowed optimization, not required by the gate | wall | <= 1.2 s | 3 s | leaves B6 (5 s) room; budget equals the formula sum and carries no margin (acceptable for a relative budget; a miss is a PO ruling) |
| M2-B10 | one shared pass producing F1, F4, F17, F7, F18 and the F2/F10/F12 inputs over 1e5 and 1e6 prints | prints/s | >= 50,000 | 20,000 | B1 ingest rate (50,000/s): all families together cost no more than ingest; shared pass must beat six separate passes (reported ratio) |
| M2-B11 | B6 with M2: all outputs (M2-G0 set plus every M2 output), one underlying, size M, one cutoff, compute-only | wall | <= 5 s | 15 s | B6 as written; M2 may not loosen it |
| M2-B12 | B7 with M2: 5 x 5 x 78 cutoffs, size M, all outputs, offline replay, run once | wall | <= 170 min | 240 min | governing B7 as amended; 60 min reported as an owner target at N workers, not a gate |
| M2-B13 | memory: peak RSS per process on the B7-with-M2 and M2-B11 workloads; history store bytes. Stored metrics per series and per window W (the gate workloads use a single W = 300 s; the formula is per W and multiplies by the number of Ws kept): 5 (premium, contracts, prints, put volume, call volume), array-backed (8 bytes per value), each with its sorted copy and, for the median, one merged sorted array; contract-level series are sparse (nonzero grid points plus a zero count) and created lazily only for contracts with prints; name-level series are dense (5 x 20 x 390 x 8 x 3 copies, about 0.9 MB each, 5 names) | peak RSS; store | <= 2 GB per process (B9); store <= 64 KB per contract-level series at the median print count; store <= 512 MB | 4 GB per process; store 1 GB per worker (PO ruling) | B9 as written; 6,000 series x 64 KB = 384 MB inside the store budget; contract-level series are capped by the store budget, and the number held and the bytes are reported |
| M2-B14 | determinism (extends B12) | result hashes | identical | identical | section 6 |
| M2-B15 | cutoff sweep, print-pass component: 78 cutoffs of one session, one underlying, size M, incremental state reused | sweep print-pass time / (78 x single-cutoff print-pass time) | <= 0.25 | 0.5 | 78 cutoffs must not cost 78 full rescans of the print stream (each print processed once per sweep); measured with and without the tape build; includes the overlapping-cutoff case (900 s windows, cutoffs 300 s apart, same state-reuse denominator, gate 0.25); the 3600 s windows with 10 s cutoffs case is informational; sparse F17 reads are informational, reads are gated by M2-B15r only |
| M2-B15r | cutoff sweep, reads component: the series reads of 78 cutoffs (78 x 8,000 = 624,000 reads) | wall | <= 32 s (formula 31.2 s: 624,000 x 50 us, rounded up) | 125 s | gated apart from the print pass; same per-read budget as M2-B2. N-dependence (RULED, PR 80): the gate scales linearly with the number of reads; at N = 2,000 series (624,000 reads) budget 32 s and hard 125 s as written, at N = 6,000 series (3x the reads) budget 96 s and hard 375 s |
| M2-B16 | history-view transfer to workers: allowed options: shared memory, mmap or store load; a per-worker rebuild is allowed only if it meets the 5 s budget at its own M2-B18 floor (25 sessions x about 40,000 prints = 1,000,000 prints at 50,000/s = 20 s, so a rebuild of the full history does NOT qualify at the floor; a rebuild of one session, 40,000 prints = 0.8 s, does) | seconds per worker start (GATED); bytes per worker (GATED) | <= 5 s; <= 512 MB (the store budget) | 15 s; 1 GB | cost reported separately and never hidden in compute; the view counts in that worker RSS |
| M2-B17 | store persistence round trip: write and read back the M2-B1 record set (25 sessions x 2,000 series x 5 metrics = 250,000 records), canonical LF serialization | records/s write, read | >= 25,000, >= 50,000 (250,000 records in 10 s and 5 s); identical content hash after the round trip and at every worker count | 5,000, 10,000 | same class as M2-B1 and B2; determinism of the serialized bytes is a correctness row |
| M2-B18 | trade-to-grid build: 25 sessions of prints turned into 60 s grids and session totals for one underlying, size M | prints/s | >= 50,000 | 20,000 | the B1 ingest rate; built once per session, reused by every cutoff |
Every rate floor (M2-B5 to B8, B10, B18) prints the measured P1-T1 value (docs/p1/P1_T1_REPORT.json) beside it as a regression marker; a measured P1-T1 regression is reported.
Whole-run informational lines (not gates): aggregate RSS at N workers (cap keeps it at 50 percent of host RAM); build-phase share of wall; cache hit rates; memory per worker as a fact.

## 4b. Mapping to the original gates and regression
| M2 gate | Original gate it extends |
|---|---|
| M2-G0, M2-B11 | B6 (5 s / 15 s as written) |
| M2-B12 | B7 (170 / 240 min, run once) |
| M2-B13 | B9 (2 GB / 4 GB per process; aggregate by the PR 72 cap rule, which supersedes the older 8 GB aggregate line of PERF_ACCEPTANCE; each worker store counts in that worker RSS) |
| M2-B14 | B12 (determinism) |
| M2-B1, B17, B18 | B10 and B11 in spirit (store write, checkpoint size), measured as library rates; B1 (ingest) stays an RQ item |
| M2-B2 to B4 | B2 style per-series budget |
| M2-B5 to B10 | P1-T1 and B1 rates |
Original B2 to B5 and the M1 gates (OC5, OC6, chain ATM IV, 30-day IV, P1-T1) are re-run unchanged on the M2 build as regression with the same budgets; any change is a failure or a PO ruling.

## 5. Parallelism expectation
The units reuse the opt-in, default single-process runner (tools/m1_runner): unit = underlying x session x cutoff; workers <= min(cores, RAM / B9); merge by unit key; worker count never enters a result; no change to the runner determinism rules.
| Phase | Parallel shape | Expectation |
|---|---|---|
| History build (M2-B1) | ordered per underlying, parallel across the 5 underlyings; series shards inside a session | at most 5-way on the 5-underlying workload; reported as serial share of wall (not hidden) |
| Compute (M2-B3, B4, B9, B11, B12) | independent units over immutable history views | scaling at 4 workers >= 2.0x p50 wall on the 5-underlying workload (PERF_ACCEPTANCE S01 rule); at N workers report efficiency |
| Trade-stream rate gates (M2-B5 to B8, B10) | sharded by contract id, merged in canonical order | >= 1.8x at 4 workers (S02 rule); skipped as N/A (reported) under 4 physical cores |
The history view a unit needs is passed read-only; a worker keeps the view it built for its underlying and session (derived data, dropped between runs; results never depend on it, tested). Input synthesis is reported separately from compute (M1 risk 2: 23 percent of CPU at 48 workers); caching or sharing synthesis per session across units is allowed in the tool, never in the library. A scaling miss is a PO ruling, never a budget edit; correctness rows must still pass at every count.

## 6. Determinism, equivalence, cache, memory rules (hard; any failure blocks regardless of speed)
1. Determinism (M2-B14): per-cutoff and whole-run SHA-256 of canonical result bytes identical at 1, 2, 4 and N workers, 3 repeats; across batch sizes 1, 7, 64, all; shuffled cutoff, underlying, contract and series order; shuffled arrival order of prints that share a timestamp (the documented tie rules decide); history appended in canonical session order only. The store content hash is identical at every worker count. Results are keyed and emitted in canonical order, never completion order.
2. Batched versus single: the batched path and the one-series-at-a-time path give equal bytes for every M2 output, status and reason, with zero tolerance (all M2 outputs are exact; there is no IV tolerance here). A status or reason flip is a failure. Rank, median and episode outputs also equal an independent Tester reference (sorted list with Fraction arithmetic).
3. Cache rules: cold and warm give the same bytes. Changing any one input field or parameter (window, threshold, N, X, K, multiplier, right, strike, expiry, session, lane, history content, calendar) changes the key and recomputes; the expected bytes equal the cold result of the changed input. A hit never crosses underlyings, sessions or lanes. A new sealed session invalidates exactly the series it touches. Caches are per process, immutable views only, no shared mutable state between workers; bounded (size and eviction recorded); eviction does not change bytes; cache stats go to the log, never into a result.
4. Memory: peak RSS per process within B9 (2 GB budget, 4 GB hard) including the store (store 512 MB budget, 1 GB hard per worker, PO ruling; cap N per PR 72); allocation growth over 30 repeats: slope of post-GC RSS <= 1 MB per repeat and last-10 mean within 5 percent of first-10 mean; store bytes within 30 percent of the M2-B13 formula series x K x 390 x 8; the aggregate of worker RSS reported; size L at one worker within the hard limit; retention never exceeds K sessions (append past K evicts the oldest, tested).
5. Failure semantics unchanged: a crashed, missing or duplicate unit fails the run with no partial output.

## 7. Measurement rules
1. Budgets, workload and machine are frozen in the plan before the run; the report prints the budgets verbatim beside the measurements (same file text, not retyped).
2. A missed budget is reported as missed; relaxing needs a PO ruling with a reason and is never an edit to this file.
3. Library, history store, runner and end-to-end are measured separately so a miss can be attributed. The shared pass (M2-B10) is compared with separate passes.
4. Stress inputs (maximum chain, p99 trade counts, 20-session histories with planted spikes) come from the Tester generators, independent of developer code.
5. Not measured: network, live latency, recorded chain sizes, adapter ingest (B1 and B10 of the old list stay RQ items), real-size history.
6. Developer evidence and Tester evidence are labelled apart; the Tester runs or re-runs every gate here; the Developer does not sign off its own proof.
7. The report states what was not measured and carries the label sentence verbatim; a docs reviewer greps it against docs/RELEASE_NOTE_TEMPLATE.md label rule 1 as a gate.

## 8. Assumptions and ambiguities (A1 to A6 RULED)
- A1 (RULED as numbers): the numbers in section 4 are derived from M1 measured numbers (B2 13 us p95, B6 IV part 1.53 s p95, B7 1.78 min at 48 workers) and the P1-T1 and B1 rates; they are re-based only by a PO ruling after measurement.
- A2 (RULED): M2-G0 gates the compute-only figure; the figure with input synthesis is printed beside it, not gated.
- A3 (RULED, Q5): gates are measured at contract level, N up to 6,000, with name-level aggregation as a derived output.
- A4 (RULED as a number): trade counts per contract (median 20, p99 1,000) are a Tester-frozen fact, not a budget input.
- A5 (RULED as a number): M2-B1 to B4 numbers (50 us, 25,000 records/s) assume pure CPython bisect on array-backed sorted lists; if the Developer proposes another structure the gate stays and the structure is the Developer's choice.
- A6 (RULED as a number; B2n and B3n ratio gate: Budget 3.6, Hard 4.0, statistic median of 30 paired ratios t(6,000)/t(2,000)): 3.6 (time ratio for 3x size) and 12 (for 10x) are the P1-T1 style superlinear checks (1.2 x the size ratio).


## 9. Rulings after the story B and A measurements (RULED, pending design ratification where the design is silent)
- M2-B15: the gate is the print-pass ratio with the tape build counted (met). The strict prebuilt-tape ratio is informational. Performance candidates named: F7 at 3x overlap and F17 sparse reads (a density-adaptive window strategy).
- M2-B16: the store binary mmap snapshot is ratified as the worker-start transfer form (optional, alongside the canonical M2SNAP1 format). At N = 6,000 series the hard limits (15 s start, 1 GB per worker) are the gate; 5 s and 512 MB are gated at N = 2,000. Private bytes and shared mapped bytes are reported separately.
- Next M2 task: the re-audit of every F row.
