# M2 perf fixtures: authoring notes (Tester), rev 2

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Provenance: SYNTHETIC. Synthetic data only; nothing recorded or vendor-supplied.

## Revision history
- rev 1 reconstructed gate ids and budgets because the M2 docs were absent from a stale checkout. Superseded.
- rev 2 (this) is authored against the ruled docs after the checkout was fast-forwarded: all rev-1 gate ids, budgets, the print count, B13-B18/B15r/G0 meanings, M1 figures, F17 window (Q9: closed trailing [T-300, T]) and the runner CLI are replaced.

## Files read (only these)
- docs\m2\M2_GATE_BUDGETS.md, M2_FIXTURE_REQUIREMENTS.md, M2_IO_CONTRACT.md (in full); M2_CAPABILITY_MATRIX.md (grep of rows M2-1..M2-11 and rulings Q1, Q2, Q5, Q7-Q11, Q15, Q18, reasons section)
- docs\M1_RUNNER.md, docs\M1_CLOSE.md (in full)
- qualification\synthetic\perf\PERF_ACCEPTANCE.md, PERF_RUNNER_CONTRACT.md (v2), PERF_NOTES.md, head of gen_perf_workloads.py and gen_perf_resource_rows.py (rev 1)
- watchyourlist-design\docs\features\flow.md (grep excerpts)
- Not read: option-features packages, tests, tools (runner and workload internals), M2 family fixture authors' scratch output, docs\p1\P1_T1_REPORT.json (the 663,933 records/s figure is from the brief). Seen only by filename search: strategy-research M2_PLAN.md, M2A_* scratch files (other work, not opened).

## Independence statement
No implementation, developer note or library output informed any number or expected value. Budgets are copied from the ruled budgets doc; truth values (F4/F17 trailing counts, F7 shares, rank and median, episodes for quiet_gap 1 and 5, trade-to-grid digest) are computed by Tester reference code in the generator (stdlib, Fraction, bisect), never by the library.

## Regenerate and verify
`python gen_m2_workloads.py --out .` (seed 20261029, about 1 minute, stdlib; `--quick` gives a reduced smoke manifest) and `python gen_m2_resource_rows.py`. Two full runs gave identical manifest sha256. Manifest about 55 KB; full workloads regenerate from seed at run time.

## Rev 3 (PO rulings A1-A4)
A1 total-only frozen fact; A2 dense subset (s % 5 == 0, 20 percent, >= 300 prints per session; see defect in acceptance A2); A3 CLI/perf_sut accepted conditionally, no deviation found; A4 two half-day sessions (7 and 14, 210 minutes), P1-T1 alarm informational. Smoke output moved outside the deliverable (`..\q1-smoke`, not deleted).

## Rev 4 (review conditions)
Half-day unit counts fixed (lower half and base scaled by n; per_unit_total_ok asserts n == unit_n(k)); B3n ratio rule, 30 repeats for all gates, wording 'recorded-data', P1-T1 provenance and 0.8x value 531,146 (informational), B3 7,440 values, boundary prints 26-50 (mean about 40), A8 truth-section coverage, runner contract cutoff mapping and one disclosed extension. Dense minimum 300 accepted by the PO.

## Remaining ambiguities
See M2_PERF_ACCEPTANCE.md section 6 (A2 dense threshold 300 prints; others ruled), and in the runner contract: the M2 CLI option names and the perf_sut adapter binding are proposals for the Developer and PO.
