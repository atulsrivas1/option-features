# 2026-10-31: M3a unit-test perf asserts are smoke checks (best of up to 3)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Date: 2026-10-31. Decided by: PO ruling, 2026-10-31, this session (chore PR after PR 118).

Decision: the throughput and latency asserts in `tests/m3a/test_m3a_history.py` `PerfStore` (B6 append, W09 round trip, B5 read share per call and per series) take the best of up to 3 samples and stop at the first pass (`m3a_harness.best_of`, floors as shared constants). Floors and budgets are unchanged and identical to GATE_BUDGETS section 5; nothing is skipped.

Reason: a single-shot floor fails on loaded shared hosts. The S02 measurement (decision 2026-10-30-m3a-s02 item 10) had a minimum of 24,492 records/s against the 25,000 floor while the slowest 5 percent of repeats still ran at 33,317 records/s or better (the p5 rate).

Scope: the unit asserts in `PerfStore` only. The W02, W03 and W04 rows (surface frame, delta25, tenors) are out of scope and unchanged; `PerfRetention` has no timing assert. New unit perf asserts in S07, S08, S10 and S11 use the same smoke rule (`best_of`). A B6 retry rebuilds the full 103-name store. W09 and B5 merge per metric or row across samples, so the asserted values may come from different samples.

Release gates are not affected: they are GATE_BUDGETS section 5 (p95; for rates, the slowest 5 percent still meets the budget) over at least 30 repeats after one warm-up, run by the Tester. GATE_BUDGETS section 8 rule 7 and BUILD_PLAN section 7 item 2 now say that a unit smoke check is never gate evidence and does not replace the bench. No budget number is edited.

Out of scope as ruled: W02, W03 and W04. Also not covered by this ruling and left unchanged: `tests/m3a/test_m3a_validate.py` `ValidationCost::test_cost_per_contract` (S09, median of 15 samples under 20 us per contract), a single-shot unit assert. Open question for the PO.
