# M3a performance acceptance (Tester, independent), rev 1

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Provenance: SYNTHETIC. Every number is a "synthetic workload, relative engineering budget"; no recorded-data, latency or live claim. Owner main goal: PERFORMANCE: use cores, memory and caches fully to calculate faster without changing a single result byte. Source of every budget: docs/m3a/M3A_GATE_BUDGETS.md section 5 (as of PR 104 head 1ec672f) (as of PR 104 head 1ec672f) (this table is a convenience copy; `check_gate_table.py BUDGETS_DOC THIS_FILE` diffs every row cell by cell and must print OK; the harness prints the budget text from the doc itself). Companions: gen_m3a_workloads.py, m3a_workload_manifest.json, gen_m3a_resource_rows.py, m3a_perf_resource_rows.json, M3A_PERF_RUNNER_CONTRACT.md.

## 1. Gates (pass = p95 within Budget; rates: p5 of the sample meets it; Hard = fail even if the PO rules otherwise; single worker unless stated; at least 30 repeats after one warm-up)
| Gate | Workload | Metric | Budget | Hard |
|---|---|---|---|---|
| M3A-B1 | (measured PER delta convention, spot and forward, each must meet the budget, R-157) surface increment, size M, one cutoff, contract IVs cached: bracketed delta search (at most 200 delta evaluations, M3A-B12), 25-delta put and call IV for every expiry, tenors 9, 30, 91 | wall | <= 0.1 s | 0.5 s |
| M3A-B2 | (per delta convention, R-157) one 25-delta point (one expiry, one side), IVs cached | per point | <= 2 ms | 10 ms |
| M3A-B3 | constant-maturity tenors 9, 30, 91 from cached ATM IVs, size M | wall | <= 0.1 s | 0.5 s |
| M3A-B4 | point outputs M3A-3 to M3A-7, 10, 11 per name; batch of 103 names | per name; batch | <= 1 ms; <= 110 ms | 5 ms; 550 ms |
| M3A-B5 | history ranks: V1 and V9 (session-close values, up to 252) per series; V3 same-minute across up to 252 sessions per series, measured for BOTH forms (`atm_iv` and `iv30` series) | per series | <= 50 us (V1, V9); <= 150 us (V3, each form) | 200 us; 600 us |
| M3A-B5n | the same for 103 names x 3 series at one cutoff (names fixed at 103, no series-count ratio), for each `iv_form` | wall | <= 20 ms (V1, V9); <= 50 ms (V3), each form | 80 ms; 200 ms |
| M3A-B6 | store append of the M3a series: 252 sessions x 103 names x 7 series (about 181,700 records: 2 minute series and 5 scalars incl. skew25_fwd; was 6 series, about 155,700) | records/s | >= 25,000 | 5,000 |
| M3A-B7 | store persistence round trip of the same set, canonical LF text and mmap snapshot | records/s write, read | >= 25,000, >= 50,000 | 5,000, 10,000 |
| M3A-B8 | memory: peak RSS per process; store bytes at retention 252 | peak RSS; store (private bytes) | <= 2 GB (B9); store <= 768 MiB | 4 GB; store 1 GiB per worker |
| M3A-B9 | determinism (extends B12) | result hashes | identical | identical |
| M3A-B10 | B7 with M3a: 5 x 5 x 78 cutoffs, size M, all outputs, run once | wall | <= 170 min | 240 min |
| M3A-B11 | cutoff sweep: 78 cutoffs of one session, one underlying, size M | sweep wall / (78 x single-cutoff wall) | <= 1.1 | 1.5 |
| M3A-B12 | (per delta convention, R-157) bracketed-search count: delta evaluations per chain, size M (enforces R-74) | count | <= 200 | 400 |
| M3A-B13 | scaling: 4 workers versus 1 on the 5-underlying compute phase | p50 wall ratio | >= 2.0x | none |
First task gate M3A-G0 (budgets doc section 4, not a row of the table above): full-output B6 with the M2-G0 set, the M2 flow outputs (M2-B9) and the M3a surface set, ONE timed unit, one underlying, size M, one cutoff (SYN1/03/045), all-valid-quote smile chain; budget 5 s p95, hard 15 s (nearest rank); gated at ONE worker, compute-only; 2, 4 and N workers informational with efficiency; with-synthesis figure printed beside it, not gated.
Correctness before timing: every timed output is first compared with the manifest truth (chain_truth: forward, ATM IV, 25-delta IV, tenor IV within IV 1e-4 and forward 1e-6 on vega >= 4 contracts; rank_truth and point_truth as exact rationals); a wrong result fails the gate regardless of speed. Informational: aggregate RSS at N workers, build-phase share, cache hit rates, history-view transfer cost per worker (mmap, M2-B16 hard limits 15 s and 1 GB), batch of 103 chains (B1).

## 2. Measurement protocol
1. One warm-up, then >= 30 timed repeats per gate and per worker count (M3A-B10 once, as ruled in the budgets doc; B6, B7 also >= 30 repeats). Report p50, p95, max and all samples; nearest rank; unit set rotated.
2. Timer: monotonic ns around the compute call only; inputs built before the timer; compute and with-input-synthesis reported separately; serialization measured apart.
3. Machine frozen and written before the first repeat: CPU model, physical and logical cores, clocks, RAM, OS build, Python build, power plan, idle load below 5 percent. A different machine is stated; figures are never compared across machines.
4. Single-worker figures are the pass/fail gates. M3A-G0 is gated at ONE worker; 2, 4, N workers are informational (per-unit compute wall inside a worker, efficiency, pool wall of N x 30 units). N = min(physical cores, floor(aggregate / 2 GB)), aggregate default 50 percent of host RAM (PR 72). M3A-B13 (S01): >= 2.0x at 4 workers on the p50 wall of the 5-underlying compute phase; N/A (reported) under 4 physical cores.
5. Frozen workload facts (manifest `chains.*.facts`: contracts 500 / 2,000 / 6,000, expiries, strikes per expiry, quote counts, store records 181,692, units 1,950) are rechecked within +/- 10 percent before every run (`gen_m3a_workloads.py --recheck FACTS MANIFEST`). M3A-B11 fact: the manifest `sweep_B11` records 71 distinct spots across the 78 cutoffs and the repeated cutoff indexes, so a spot-keyed cache must not pass B11 by accident (the cutoff belongs in the key). The manifest also records the facts that are not frozen but informational: floored wing quotes, vega >= 4 counts.
6. A miss is reported; a p95 over budget with hard met needs a PO ruling; a hard breach blocks; a miss of M3A-G0 is reported and the PO rules; never a budget edit. The Tester runs and signs; the Developer does not sign its own run.
7. Not measured: network, live latency, recorded chain sizes, adapter ingest, real-size history. Linux, if run: "Linux run as process check, not claimed".
8. Library, history store, runner and end-to-end are measured separately so a miss can be attributed (budgets doc section 8, item 3).

## 3. Regression markers (printed beside every rate floor; the original gates and every M2 gate that exists on main are re-run unchanged on the M3a build, same budgets; M1 and M2 outputs must keep their result hashes)
Sources: docs/m3a/M3A_GATE_BUDGETS.md section 2 and qualification/synthetic/m2/perf/M2_PERF_ACCEPTANCE.md section 3 (copied by this author; the repo records docs/p1 and DECISIONS.md were outside the allowed source list and were NOT re-read, so the P1-T1 figures are carried as stated there, not re-verified here).
| Marker | M1 / M2 / P1 value (synthetic workload, relative engineering budget) | Rule |
|---|---|---|
| P1-T1 spread + touch | 663,933 records/s at 1e6 (p95 1.506 s) and 695,324 records/s at 1e5 (p95 0.144 s) | printed with every M3a rate floor; a measured regression is reported; informational alarm below 0.8 x = 531,146 records/s at 1e6 (not a gate) |
| B2 OC5 one contract | 13 us p95 vs 50 / 200 us | unchanged budget; > 50 us is a failure or ruling |
| B3 OC6 50 / 5,000 updates | 114-127 us (ticks), 175-181 us (strings) / 10-14 ms vs 200 us / 1 ms / hard 20 ms | unchanged; strings margin thin |
| B4 / B5 / B6 IV part | 0.063 s (size M), 0.099 s (size L) p50 / 0.021 s p50 / 1.40 s p50, 1.53 s p95 (compute-only) | unchanged budgets 1 s, 4 s / 1.5 s / 5 s |
| M2-G0 full output set, 1 worker | 2.41 s p50, 2.66 s p95 | M3A-G0 headroom; sum check 2.66 + 1.2 + 0.1 = 3.96 s printed, not a gate |
| B7, scaling, RSS | 1.78 min at 48 workers (2.38 min at 24); 3.78x at 4 workers; 142-495 MiB per worker | unchanged 170 / 240 min, >= 2.0x, 2 GB |
| M2 store | M2-B1 floor 25,000 records/s write, M2-B17 floors 25,000 write and 50,000 read, met; M2-B2 and M2-B3 budgets 50 us / 200 us, met at 2,000 series | M3A-B5, B6, B7 reuse these floors |

## 4. Resource rows (`gen_m3a_resource_rows.py` -> `m3a_perf_resource_rows.json`, 71 rows)
| Group | Rows | Rule |
|---|---|---|
| G0 | G001 | M3A-G0 protocol (section 1 note, budgets doc section 4) |
| W workloads | W01-W15 | one per gate M3A-G0, B1 to B13 and B5n; sizes S, M, L; 103-name batches; frozen facts rechecked |
| D determinism | D01-D12 | identical per-cutoff and whole-run sha256 at 1, 2, 4, N workers x 3 repeats, batch sizes 1, 7, 64, all, shuffled cutoff, underlying, contract, expiry and name order, same-ns quote arrival, canonical append only, identical store content hash; D12 must fail on mutants M-I05 to M-I07 |
| E equivalence | E01-E12 | batched = single for every output, status and reason, zero tolerance, equality with the Tester reference (at least 20,000 randomized cases each for 25-delta, tenor, rank and sign-change), validate full = scanned |
| C cache | C01-C14 | cold = warm bytes; each input field and parameter changes the key; no hit across chains, cutoffs, underlyings or lanes; bounded cache; eviction never changes bytes; statistics in the log only |
| R memory | R01-R08 | B9 limits, 30-repeat slope <= 1 MB per repeat and last-10 mean within 5 percent of first-10, store bytes at retention 252 against the formula, retention K, aggregate RSS, size L, B16-style worker start with the mmap snapshot (721 series, 181,692 records) |
| S scaling | S01-S03 | M3A-B13 and informational efficiency |
| K runner | K01-K06 | kill, missing, duplicate unit, interpreter mismatch, no partial output with M3a outputs in the unit, own PIDs only |
Infrastructure mutants (table `infrastructure_mutants` in the rows file, 10 mutants M-I01 to M-I10): each lists the rows that must fail on it; these are the performance-side counterpart of the structural mutants in m3a_mutation_results.txt.

## 5. Verdict rules
- Any D, E, C, K or M3A-B9 failure is a correctness failure and blocks regardless of speed. A Hard breach blocks. A Budget miss with Hard met needs a PO ruling recorded before release.
- Reports carry the label sentence in the header verbatim and "synthetic workload, relative engineering budget" beside numbers; the forbidden-term grep of docs/RELEASE_NOTE_TEMPLATE.md label rule 1 applies.

## 6. Defects and ambiguities (for PO ruling; none silently resolved)
- P1 (RULED, PO batch 2: iv30 minute series; owner decision 2 adds the atm_iv minute series): budgets doc section 3 says the history includes "the atm_iv minute grid on 252 sessions", while R-81, B8 and the matrix use the iv30 minute grid. This author built the iv30 minute grid (series `iv30_min`) as the fourth series (103 x 252 x 390 x 8 B = 80,982,720 B raw, matching the 81 MB of B8).
- P2 (RULED, PO batch 2: ordinals 01-05, documented deviation from M2): budgets doc section 3 gives the unit key example SYN1/03/045 while the M2 contract uses sessions 21-25. Here the session field is the evaluated-session ordinal 01-05 (calendar session 252 + ordinal, history sessions 1-256); a ruling may prefer 253-257.
- P3: M3A-G0 includes the M2-G0 and M2 flow outputs; the print and quote streams of that part are the runner's own M2 workload (m2_workload_manifest.json), not part of G8 here (G8 supplies the chain and the M3a inputs).
- P4 (RULED, PO batch 2: M1 vega per 1.00 of volatility): R-85 gives "vega >= 4" without a unit (per 1.00 vol or per point); the manifest tags vega per 1.00 vol (ATM vega about 4.7 for the 5-day expiry) and the 1e-4 truth checks apply only above it.
- P5: the "all-valid-quote" chain floors wing mids at 0.03 (about 21 percent of the size-M quotes); the floored contracts are valid quotes but their IV is not the true smile value, so chain_truth is asserted on the ATM and 25-delta region only. A ruling may prefer a narrower strike range.
- P6 (FLAG, owner decision 2): with atm_iv and atm_iv_close next to iv30 and iv30_close (owner decision 2) and skew25_fwd next to skew25 (owner decision 3) each name holds 7 series (5 scalar, 2 minute grids): 103 x 252 x 7 = 181,692 records, 721 series, two minute grids of 80,982,720 B raw (161,965,440 B), 485,896,320 B in the M2 layout = 60.34 percent of the 768 MiB budget of 805,306,368 B (RULED 2026-10-30; units binary per coordinator decision pending owner review; hard 1 GiB per worker); the budgets doc of PR 104 now carries 7 series, about 181,700 records and a store budget of 768 MiB and a hard 1 GiB per worker (gate-table cells kept verbatim; read as binary: 768 MiB = 805,306,368 B, 1 GiB = 1,073,741,824 B); this set matches it; the B8 text in section 5 for 6,000 series (M2-B16 hard limits) is carried as informational.
- P7: the runner counts delta evaluations itself (no counter exists in M1_RUNNER.md); the contract note adds `delta_evaluations` to the response (a tool change, deviation D4 in M3A_PERF_RUNNER_CONTRACT.md).
