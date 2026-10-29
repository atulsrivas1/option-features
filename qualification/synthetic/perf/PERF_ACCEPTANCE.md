# P1/M1 performance acceptance (Tester, independent)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Provenance: SYNTHETIC. Every number is a "synthetic workload, relative engineering budget". No claim about recorded data, latency or live service is made. Source of numbers: THROUGHPUT_BUDGET.md section 2 (proposals) and PO_RELEASE_PLAN_V3 section 3 (two-stage rule). Workload: `gen_perf_workloads.py`, seed 20261029, manifest `perf_manifest.json`. Owner goal: use cores, memory and caches fully to compute faster without changing a single result byte.

## 1. Gate table (single worker unless stated; pass = p95 within Budget; Hard = fail even if PO rules otherwise)

| Gate | Workload | Metric | Budget (p95) | Hard | Label |
|---|---|---|---|---|---|
| B2 | OC5, 1 contract, single quote state | time/contract | <= 50 us | 200 us | synthetic workload, relative engineering budget |
| B3a | OC6, 1 contract, 50-update window | time/contract | <= 200 us | 1 ms | same |
| B3b | OC6, 1 contract, 5,000-update window | time/contract | report only | 20 ms | same |
| B4 | chain ATM IV, size M, 1 cutoff | wall | <= 1 s | 3 s | same |
| B4L | chain ATM IV, size L, 1 cutoff | wall | <= 4 s | 10 s | same |
| B5 | chain 30-day CM IV, size M, 1 cutoff | wall | <= 1.5 s | 4 s | same |
| B6 | all outputs, 1 underlying, size M, 1 cutoff | wall | <= 5 s | 15 s | same |
| B7 | 5 x 5 x 78 cutoffs, size M, offline replay, run once | wall | <= 170 min | 240 min | same (V3 amendment; see A1) |
| B9 | any one process, B7 and B6 workloads; aggregate of all workers | peak RSS | <= 2 GB per process; aggregate <= 8 GB | 4 GB per process | same; cap = min(cores, RAM / B9 peak), 2 GB placeholder until first B7 run |
| B12 | subset: one underlying, one session (PO_R28_DESIGN_RULINGS section 3 item 2), 3 repeats, Windows x64 | result bytes | identical | identical | same; wider coverage by D01-D08 and S01 |
| P1-T1 (new) | spread + touch-policy classification, stream 1e5 and 1e6 records, 1 worker | records/s | >= 100,000 | 20,000 | same |

P1-T1 rationale (proposal): B1 ingest budget is 50,000 records/s; the classifier sits behind ingest and is exact integer/rational arithmetic with no I/O, so it must cost at most half of the ingest stage (2x B1) and never be the bottleneck: 1e5 records <= 1 s, 1e6 <= 10 s. Hard 20,000/s equals the B1 hard limit (1e6 <= 50 s). Both stream sizes are measured to expose non-linear (superlinear) behaviour: time(1e6)/time(1e5) must be <= 12.
Owner performance target (informational, not a gate): B7 <= 60 min at N workers (the THROUGHPUT_BUDGET value), reported beside the gate.

## 2. Measurement protocol
1. One warm-up run (not counted), then >= 30 timed repeats for B2-B6 and P1-T1 (B7 and B12: as stated). Report p50, p95, max, and all raw samples. Pass uses p95. Percentile: nearest-rank.
2. Timers: monotonic ns clock around the call only; result serialization excluded from the timer and measured separately.
3. Machine record: CPU model, physical and logical cores, base/boost clock, RAM, OS build, Python build, power plan, other load (must be idle, < 5 percent). Frozen before the run, printed in the report.
4. Fixed core counts: every parallel gate is run at 1, 2, 4 and N workers (N = physical cores) with affinity pinned where the OS allows; the count actually used is recorded. Never compare runs at different counts.
5. Budgets are printed verbatim beside measurements. A miss is reported as a miss; relaxing needs a PO ruling and is never an edit to this file.
6. Not measured: network, live latency, real chain sizes. A WSL run is required each release as a process check and is not claimed. Cross-platform comparison: absolute equality for OC5/OC6 only; IV within 1e-4 until R27 T7.
7. B1, B8, B10, B11 are not gated in M1 here (B1/B10/B11 need adapter and sink; B8 is informational).
8. Quote-count distribution (median 50, p99 5,000) is accepted with tolerance +/- 10 percent; measured median and p99 are frozen workload facts in perf_manifest.json (frozen_fact_size_M_SYN1_s1) and are rechecked by the Tester before every run.

## 3. Parallelism and resource-use rows (full rows: `perf_resource_rows.json`)

| Group | Rows | Rule |
|---|---|---|
| D determinism under parallelism | D01-D08 | Result bytes (canonical serialization, per-cutoff and whole-run SHA-256) identical at 1, 2, 4, N workers; identical across batch sizes (1, 7, 64, all), shuffled cutoff order, shuffled underlying order, shuffled contract order within a chain; repeated 3 times. Results are keyed and emitted in canonical order, never completion order. |
| E batched vs single | E01-E06 | Batched or vectorised path vs one-at-a-time path: exact-arithmetic outputs (spread, midpoint, spread_bps, OC5, OC6, premium, touch side) bytes equal; IV: abs difference <= 1e-4 per contract and the same closed reason / status on every contract (a status flip is a failure even if values are close). |
| C cache correctness | C01-C07 | Cold vs warm cache: same bytes. Changing any one input field (each of bid, ask, sizes, times, strike, expiry, right, style, spot, rate, dividend, window, stale limit, params) must change the cache key and recompute: expected bytes equal the cold result of the changed input. Cache hit never crosses underlyings or sessions. Cache bounded: size and eviction recorded; eviction does not change bytes. |
| R memory | R01-R05 | Peak RSS at B9 limits per process (and sum of worker RSS reported); allocation growth over 30 repeats: linear regression slope of post-GC RSS per repeat <= 1 MB/repeat and last-10 mean within 5 percent of first-10 mean (no leak); chain L at 1 worker within hard limit. |
| S scaling | S01-S03 | Speedup at 4 workers vs 1 worker (same machine, same workload, p50 wall): >= 2.0x on B6-style multi-underlying work (5 underlyings) and >= 1.8x on P1-T1 sharded by contract. Rationale: with ~15 percent serial share (ingest, merge, ordered emit) Amdahl allows 2.76x; 2.0x allows spawn/serialization overhead (~50 percent efficiency). Skipped as N/A (reported, not passed) if fewer than 4 physical cores. A miss triggers a PO ruling, never a budget edit; correctness rows D/E must still pass at every count. |

## 4. Verdict rules
- Any D, E, C or B12 failure is a correctness failure: blocks acceptance regardless of speed.
- A Hard breach blocks. A Budget miss with Hard met needs a PO ruling recorded before release.
- All results carry the label sentence from PO_RELEASE_PLAN_V3 section 5.1 verbatim; forbidden-word grep applies to the report.

## 5. Assumptions and ambiguities (for PO ruling)
- A1: V3 cites "B7 amendment (170/240 min, run once)"; THROUGHPUT_BUDGET says 60/120. Gate uses 170/240 (later document); 60 kept as informational target. Confirm. TOP2 test 5 '60 min' is superseded by the B7 amendment: 170/240 governs, 60 is reported.
- A2: B3b has only a hard limit (20 ms); budget left as report-only. Aggregate 8 GB worker RSS limit adopted by PO.
- A3: Chain layouts S/M/L (5x50, 8x125, 12x250 expiries x strikes x 2) are the Tester's choice reaching 500/2000/6000; expiries bracket 30 days.
- A4: P1-T1 numbers, speedup factors 2.0x/1.8x, leak slope 1 MB/repeat and the 12x scaling ratio are Tester proposals.
- A5: Cache-key policy and cache size are implementation decisions; rows assert behaviour only.
