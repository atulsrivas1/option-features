# 2026-10-31: M3a unit-test perf asserts are smoke checks (best of 3)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Status: PO ruling (chore PR after #118). The throughput and latency asserts in `tests/m3a/test_m3a_history.py` (PerfStore: B6 append, W09 round trip, B5 read share) are smoke checks that take the best of up to 3 samples and stop at the first pass; floors and budgets are unchanged and nothing is skipped; release gates stay p5 over at least 30 repeats.
