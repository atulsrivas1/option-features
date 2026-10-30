# 2026-10-30: tracker update for CI (PR 105) and the owner decisions on M3a (recorded by the Auditor on PO direction)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

## Decisions and facts recorded in docs/FEATURE_STATUS.md
1. CI: PR 105 is merged (GitHub Actions on windows-2022, CPython 3.12 x64, hash-pinned wheels; contracts, features, p1, qualification, m1, m2 with 963 tests and 2 skipped, plus the named tracker test; a manual-only benchmark workflow). First runs green: https://github.com/atulsrivas1/option-features/actions/runs/41083403896 . A CI status section (3b) and the Merged PRs line carry it; PR 103 is merged too; PR 104 (second M3a ruling batch) was still open when this was written. This closes the TODO in docs/decisions/2026-10-30-ci-workflow.md. No Linux job, so Linux stays a process check, not claimed.
2. Owner decisions on M3a, all five FINAL and owner-decided, not interim (a design-session ratification can still amend them): (1) V21 is included in M3a; (2) V3 and V4 implement BOTH forms (atm and 30d), so they are no longer "partial: 30-day form only" (the R-81 exception is withdrawn) but "match candidates, pending until built"; (3) the 25-delta outputs (V8-V11, V21) take a delta_convention parameter, spot or forward, default spot; (4) a constant (zero-range) history percentile is unavailable with reason zero_range_history, a deliberate exception to M2 Q2 (V1, V3, V9); (5) the scalar baseline allows partial history: missing days are skipped, at least 20 prior sessions are required, a deliberate difference from M2's strict rule (V1, V3, V4, V9). Pending reasons of V1, V3, V4, V9 say this; no row says an owner decision is pending.
3. Tracker effect: no row changes status or release; M3a still has 13 rows, all pending (counts unchanged: 113 rows, done 40, partial 9, pending 63, dropped 1).

## Reason
The tracker is the single live record; CI results and owner decisions change what a pending row will mean once built.
