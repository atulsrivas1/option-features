# M1 close record and M2 proposal

Author: Product Owner, 2026-10-29. Decided by PO.

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

## 1. Built versus M1 scope (V3 section 1)
| M1 scope item | Status | Evidence |
|---|---|---|
| OC5 (QuoteSize record, additive) | Built, pure module | PR 69; 57 rows, 75,000-case differential, Tester approve |
| OC6 (time-weighted, count coverage) | Built, pure module | PR 69; 53 rows, near-threshold attack, exact fallback |
| Chain ATM IV, 30-day IV, American labels | Built | PR 68; 41 rows plus 28 extra rows (PR 70), Tester approve |
| Solver speed, identical result bytes | Stage 0 (PR 65), Stage 1 float filter (PR 67), Stage 2 integer endpoints (PR 71) | Stage 0 about 1.37x, Stage 1 about 3.3x, Stage 2 about 3x per solve; Stage 0 to 2 together 3.1x on the B6 gate chain (8.62 s to 2.80 s p95); synthetic workload; identical result hashes on every compared contract (Tester differential reports to the PO) |
| Opt-in process-pool runner | Built (PR 72), opt-in, default single-process | determinism at 1, 2, 4, cap workers; kill and stale-output tests; six mutants caught |
Not built by design: Newton as a bracket seed (scheduled only if B6 on the full output set is missed), contract-v2 perf_sut adapter (deferred), wire exposure of the pure modules (candidate16 item), cross cases 35-36 (adapter work, RQ).

## 2. Measured numbers (synthetic workload, relative engineering budget; Xeon Platinum 8160 host, 48 physical cores, 254 GiB; independent Tester measurements unless noted)
| Gate | Budget / hard | Measured |
|---|---|---|
| B2 OC5 one contract | 50 us / 200 us | 13 us p95 |
| B3 OC6 50 updates | 200 us / 1 ms | 114-127 us p95 (Ticks ingest), 175-181 us (strings) |
| B3 OC6 5,000 updates | hard 20 ms | 10-14 ms p95 |
| B4 chain ATM IV, size M / L | 1 s / 4 s | 0.063 s / 0.099 s p50 |
| B5 30-day IV, size M | 1.5 s | 0.021 s p50 |
| B6 per-contract IV part, size M, all-valid chain, one worker, compute only | 5 s / 15 s | 1.40 s p50, 1.53 s p95 in the repo record (the Tester measured 1.35 s and 1.42 s in its report to the PO) (base before Stages: 8.62 s p95); with input synthesis 5.0 s |
| B7 whole workload (5 x 5 x 78 cutoffs, size M), developer run, once | 170 min budget / 240 min hard governs | 2.38 min at 24 workers, 1.78 min at 48 workers (developer evidence; Tester re-ran scaling and B6 only) |
| Scaling at 4 workers | at least 2.0x | 3.78x (developer, repo record); 3.90x in the Tester report to the PO |
| Determinism | identical result hashes | all worker counts and orders equal the single-process reference |
Per-worker peak RSS 142-495 MiB (repo record) (B9 budget 2 GB). Linux was not run: no Linux claim.

## 3. Risks and findings
1. B2/B3 margin is thin on the string path (about 10 percent); Ticks ingest is the gated path. A host about 1.2x slower misses 200 us on strings.
2. Input synthesis is about 23 percent of CPU at 48 workers and is now the largest overhead in the runner. New idea candidate for the Researcher/PO queue: cache or share quote-history synthesis per session across units (same session, different cutoffs), precompute once per worker, and report compute-only separately. Not scheduled; B7 is about 70 to 95 times inside budget.
3. B6 for the full output set (OC5, OC6, IV together) has not been run as one measurement. The runner computes all three; the B6 figure above is the IV part. A full-output B6 run is the first M2 task.
4. B7 was run once by the developer; the independent Tester did not re-run it (scaling and B6 only). Disclosed.
5. Aggregate memory at 48 workers 15.5 GiB; cap formula keeps it at 50 percent of host RAM.
6. All design-request rulings (1-3 and the rest) are interim and pending ratification; changed answers redo the dependent fixtures.
7. A broad process-kill filter used once by a developer may have killed another session's workers; effect unknown; rule: only kill own PIDs.

## 4. Verdict
M1 is ACCEPTED as built, as prerelease (D7), synthetic data only, Windows x64, CPython 3.12. No claim is made beyond synthetic fixtures and workloads.

## 5. Proposal: M2 flow completion (V3 section 1 and 4)
Scope per V3: F1 ratio, F2 percentile rank (history store), F4 count and threshold, F7 strike/expiry share, F10/F20 vs median baseline (request 9 interim: median), F17 fixed 5-minute window, F18/F19 volume outputs, F12 episodes; then re-audit every F row.
Steps, in order:
1. Capability matrix for M2 (data needed, client/server, per source) and the gate performance budget table (extend B1-B12 with M2 gates: history-store read/write rates, percentile rank at 20-session history, episode scan, synthetic-size stage; real-size stage deferred to RQ), authored by the PO with the Architect; independent review.
2. Independent Tester fixtures from the V3 M2 generator row (multi-session trade/premium generator with planted spikes, 20-session history, median versus mean contrast, 5-minute window cases, volume-share cases, F12 episodes, strike/expiry concentration), plus performance, parallelism-determinism, batched-versus-single, cache and memory fixtures for the new outputs; independent reviewer.
3. Developer implements as pure modules, batched, single-threaded, reusing the runner for parallelism; history store designed for append and bounded memory; Tester re-runs.
4. Re-audit every F row; label sentence verbatim; Linux process check only.
Owner-only items: none now (python-flint scratch venv and B7 machine confirmation remain optional measurement helps).
