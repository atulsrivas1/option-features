# M2 performance acceptance (Tester, independent), rev 2

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Provenance: SYNTHETIC. Every number is a "synthetic workload, relative engineering budget"; no recorded-data, latency or live claim. Owner main goal: PERFORMANCE: use cores, memory and caches fully to calculate faster without changing a single result byte. Source of every budget: docs/m2/M2_GATE_BUDGETS.md section 4 (RULED); this table is a convenience copy, the harness prints the budget text from that file beside each measurement (same text, not retyped). Workload: `gen_m2_workloads.py`, seed 20261029, manifest `m2_workload_manifest.json`; unit = underlying x session, size M (2,000 contracts, frozen total 40,000 prints).

## 1. Gates (pass = p95 within Budget; rates: p5 of the sample meets it; Hard = fail even if PO rules otherwise; 1 worker unless stated; B1-B12 stay hard acceptance gates as written)
| Gate | Workload (fixture) | Metric | Budget | Hard |
|---|---|---|---|---|
| M2-G0 | full-output B6 as ONE timed unit, size M, all-valid chain, 1 cutoff (first task) | wall, compute-only | 5 s p95 | 15 s |
| M2-B1 | seal 25 sessions x 2,000 series x 5 metrics = 250,000 records (`history_records`) | records/s | >= 25,000 | 5,000 |
| M2-B2 / B2c | history view, 20 sessions, warm / cold | per series | <= 50 us / <= 2 ms | 200 us / 10 ms |
| M2-B2n | batch of N views, warm, N = 500 / 2,000 / 6,000 | wall | 25 / 100 / 300 ms; time(6,000)/time(2,000) <= 3.6 | 100 / 400 / 1,200 ms |
| M2-B3 / B3n | percentile rank intraday (7,440 values; 7,800 for an all-full-day history) and end-of-day (20); N series at one cutoff (`rank_truth`) | per series; N batch | <= 50 us; 25 / 100 / 300 ms; time(6,000)/time(2,000) <= 3.6 | 200 us; 100 / 400 / 1,200 ms |
| M2-B4 | F10/F20 median baseline ratio, N = 2,000 batch | per series; batch | <= 50 us; <= 100 ms | 200 us; 400 ms |
| M2-B5 | F1, F4, F17 alone over `rate_streams` 1e5 and 1e6 prints | prints/s | >= 100,000; time(1e6)/time(1e5) <= 12 | 20,000 |
| M2-B6 | F7 strike and expiry concentration over 1e5, 1e6 prints | prints/s | >= 100,000; ratio <= 12 | 20,000 |
| M2-B7 | F18/F19 volume aggregation over 1e5, 1e6 prints | prints/s | >= 200,000 | 40,000 |
| M2-B8 | F12 scan: 390 points per name; 1e6 points (`episode_stream`, `episodes`) | points/s | >= 500,000 | 100,000 |
| M2-B9 | all M2 outputs, one underlying, size M, 1 cutoff, history warm, compute-only | wall | <= 1.2 s | 3 s |
| M2-B10 | one shared pass F1, F4, F17, F7, F18 + F2/F10/F12 inputs, 1e5 and 1e6 prints | prints/s | >= 50,000; shared vs six separate passes ratio reported | 20,000 |
| M2-B11 | B6 with M2: M2-G0 set plus every M2 output, size M, 1 cutoff, compute-only | wall | <= 5 s | 15 s |
| M2-B12 | B7 with M2: 5 x 5 x 78 cutoffs, size M, offline replay, run once | wall | <= 170 min (60 min owner target at N workers, reported) | 240 min |
| M2-B13 | memory: peak RSS per process on B12 and B11 workloads; history store bytes | RSS; store | <= 2 GB; store <= 64 KB per contract series at median count and <= 512 MB | 4 GB; store 1 GB per worker |
| M2-B14 | determinism (extends B12), D/E/C rows | result hashes | identical | identical |
| M2-B15 | cutoff sweep print pass, 78 cutoffs, incremental | sweep / (78 x single) | <= 0.25 | 0.5 |
| M2-B15r | cutoff sweep reads: 78 x 8,000 = 624,000 reads, gated apart | wall | <= 32 s | 125 s |
| M2-B16 | history-view transfer to workers (shared memory, mmap or store load; rebuild of one session allowed, full rebuild not) | s per worker start; bytes per worker | <= 5 s; <= 512 MB | 15 s; 1 GB |
| M2-B17 | store round trip, 250,000 records, canonical LF | records/s write, read | >= 25,000, >= 50,000; hash identical | 5,000, 10,000 |
| M2-B18 | trade-to-grid, 25 sessions of prints (963,076 = 23 x 40,000 + 2 x 21,538 half-day), one underlying (`trade_to_grid_truth`) | prints/s | >= 50,000 | 20,000 |
Correctness before timing: every timed output is first compared with the manifest truth (F4/F17 per-cutoff truth, F7 reference, rank/median reference, episode totals gap 1 and 5, trade-to-grid digest); a wrong result fails the gate regardless of speed. Informational: aggregate RSS at N workers, build-phase share, cache hit rates, memory per worker.

## 2. Measurement protocol
1. One warm-up, then >= 30 timed repeats per gate and per worker count (M2-B12 once, as ruled; B1, B17 and B15r also >= 30 repeats). Report p50, p95, max and all samples; nearest rank. Unit set rotated.
2. Timer: monotonic ns around the compute call only; inputs built before the timer; compute and with-input-synthesis reported separately; serialization measured apart.
3. Machine frozen and written before the first repeat: CPU model, physical/logical cores, clocks, RAM, OS build, Python build, power plan, idle < 5 percent. A different machine is stated; M1 numbers are not compared across machines (M1: 2x Xeon Platinum 8160, 48 cores, 254 GiB).
4. Single-worker figures are the pass/fail gates. M2-G0 is gated at ONE worker; 2, 4, N workers are informational (per-unit compute wall inside a worker, efficiency, pool wall of N x 30 units). N = min(physical cores, floor(aggregate / 2 GB)), aggregate default 50 percent of host RAM (PR 72). Scaling S rows: >= 2.0x at 4 workers (compute), >= 1.8x (trade streams); N/A under 4 cores.
5. The frozen workload fact is the print total per size-M unit (<= 40,000 for a full day, prorated for half-days; PO ruling A1), rechecked before every run. Per-contract median and p99 are informational measured facts, no tolerance check. Timing gates are stated on the mixed series set; dense (s % 5 == 0, 20 percent) and sparse are reported separately.
6. A miss is reported; a p95 over budget with hard met needs a PO ruling; a hard breach blocks; a miss of M2-G0 schedules the Newton bracket seed for a ruling, never a budget edit. The Tester runs and signs; the Developer does not sign its own run.
7. Not measured: network, live latency, recorded sizes, adapter ingest, real-size history. Linux, if run: "Linux run as process check, not claimed".

## 3. Regression markers (printed beside every rate floor; M1 gates re-run unchanged on the M2 build, same budgets)
| Marker | M1 / P1 value (synthetic workload, relative engineering budget) | Rule |
|---|---|---|
| P1-T1 spread + touch | 663,933 records/s at 1e6 (p95 1.506 s) and 695,324 records/s at 1e5 (p95 0.144 s); source docs/p1/P1_T1_REPORT.json and DECISIONS.md (verified against docs/p1/P1_T1_REPORT.json and DECISIONS.md) | printed with M2-B5..B8, B10, B18; a measured regression is reported; informational alarm below 0.8 x = 531,146 records/s at 1e6 (not a gate, PO ruling A4) |
| B2 OC5 | 13 us p95 vs 50 / 200 us | unchanged budget; > 50 us is a failure or ruling |
| B3 OC6 50 / 5,000 updates | 114-127 us (ticks), 175-181 us (strings) / 10-14 ms vs 200 us / 1 ms / hard 20 ms | unchanged; strings margin thin (M1 risk 1) |
| B4 / B5 / B6 IV part | 0.063 s (M), 0.099 s (L) p50 / 0.021 s p50 / 1.53 s p95 (1.40 s p50; the repo-record figure); 2.80 s p95 is the gate-chain figure after Stage 2; 5.0 s with synthesis | unchanged budgets 1 s, 4 s / 1.5 s / 5 s |
| B7, scaling, RSS | 1.78 min at 48 workers; 3.78x at 4 workers; 142-495 MiB per worker | unchanged 170/240 min, >= 2.0x, 2 GB; the B7 and B9 regression names are covered through M2-B12 and M2-B13 |

## 4. Resource rows (`gen_m2_resource_rows.py` -> `m2_perf_resource_rows.json`, 54 rows)
| Group | Rows | Rule |
|---|---|---|
| G0 | G001 | M2-G0 protocol |
| D determinism | D01-D10 | identical per-cutoff and whole-run sha256 at 1, 2, 4, N workers x 3 repeats, across batch sizes 1, 7, 64, all, shuffled cutoff, underlying, contract and series order, same-ns arrival shuffles, canonical append only; identical store content hash |
| E equivalence | E01-E10 | batched = single, shared pass = separate passes, incremental = recompute, library = Tester reference; zero tolerance, status and reason equal |
| C cache | C01-C12 | cold = warm bytes; each input field and parameter changes the key; no hit across underlyings, sessions or lanes; a new sealed session invalidates exactly its series; bounded cache, eviction never changes bytes |
| R memory | R01-R08 | B13 limits, 30-repeat slope <= 1 MB/repeat and last-10 within 5 percent of first-10, store formula within 30 percent, retention K, transfer B16 |
| S scaling | S01-S03 | as section 2 item 4 |
| K runner | K01-K06 | kill, missing, duplicate unit, hang, interpreter mismatch: exit 2, no partial output; own PIDs only |
| T store, sweep | T01-T04 | B17, B15, B15r |

## 5. Verdict rules
- Any D, E, C, K or M2-B14 failure is a correctness failure and blocks regardless of speed. A Hard breach blocks. A Budget miss with Hard met needs a PO ruling recorded before release.
- Reports carry the label sentence in the header verbatim and "synthetic workload, relative engineering budget" beside numbers; forbidden-term grep per docs/RELEASE_NOTE_TEMPLATE.md label rule 1 applies.

## 6. Defects and ambiguities (for PO ruling; none silently resolved)
- A1 (RULED by PO): the frozen fact is the total print count per unit (<= 40,000); the median-20/p99-1,000 distribution is dropped as a frozen fact and the measured values are informational (`workload_facts_informational`).
- A2 (RULED by PO; dense minimum 300 prints per session ACCEPTED): sparsity stays for the worst-case series count; a dense subset (s % 5 == 0, 20 percent) is added so median_ratio, percentile and episode paths see non-zero baselines (episodes: fire probability 15 percent vs 4). DEFECT in the ruling text: 20 prints per session cannot give a non-zero median on the 60 s grid (about 20 of 390 bins nonzero, a median needs more than half of the 7,800 values nonzero, about 270 prints per session). Dense series use >= 300 prints per session (superset of the ruled minimum); `rank_truth.series_with_zero_median_by_class` shows dense 0 zero medians, sparse all zero. Confirm 300.
- A3: ratio fixtures: the time ratio check (3.6, 12) and "p5 for rates" are applied as written; M2-B2n budget for N = 500 is 25 ms but its Hard 100 ms.
- A4: M2-B9 formula (1.2 s) assumes 8,000 reads; the fixture's median series count of 2,000 x 4 reads matches; fused reads are allowed.
- A5: F7 fixtures place one print per (strike, expiry, right) cell; real concentration timing on a skewed stream is covered by M2-B6 streams only.
- A6: stream print order is (time_ns, seq) with about 1 percent same-ns ties and 26 to 50 (mean about 40) boundary prints at B-1 ns and B ns per full-day unit; half-day sessions: sessions 7 and 14 of the 25-session history have 210 minutes (PO ruling A4; unit print total prorated to 40,000 x 210 / 390 = 21,538, asserted n == unit_n(k) for every unit in `workload_facts_informational.per_unit_total_ok`, history grids 210 values, retention and rank counts use actual length: 20-session history over sessions 1-20 has 7,440 values); evaluated sessions 21-25 are full days (390).
- A8: truth sections in the manifest cover the stated sizes and units only (rank_truth N = 500, window_truth SYN1/21 and SYN2/21); other sizes and units are regenerated from the seed with the generator functions (rank_truth, window_truth, episode_facts, grid_truth, concentration_cases).
- A7 (RULED): the 0.8 x P1-T1 alarm is informational, not a gate.
