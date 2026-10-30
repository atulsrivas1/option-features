# 2026-10-30: M3a contract codes (invalid_direction), R-178 confirmation, MiB wording

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Author: Architect. Status: decided (coordinator decision for the MiB wording, pending owner review).

## 1. Codes (closes the R-185 follow-up; supersedes the `invalid_param` wording of R-165 and R-175)
- `invalid_direction`: request list position 15, after `threshold_out_of_range` (the threshold slot R-165 named). VALUE code: `direction` a string other than up, down, either. Type-first kept: a non-string `direction` is `malformed_type` at position 15. The request list becomes 18 positions, 23 codes, 22 adjacent pairs.
- `invalid_session_window`: view read list position 3, after `malformed_type` (min_sessions, max_sessions). VALUE code: max_sessions < min_sessions (D13). Type checks first in the same slot.
- `invalid_param` is not a code. Each new code appears in exactly one position of one entry point list. Reason: fixtures must assert only closed codes (R-185); placing each value code in the slot where its field is type-checked keeps the M2 type-first rule. Author4 may now add the bad-string direction row; author2 D13 rows use `invalid_session_window`.

## 2. R-178 confirmed against R-139
R-139 covers a coverage-excluded expiry that brackets the tenor from one side; interpolation then lacks that side, so `no_bracketing_expiry`. An expiry at exactly the target tenor needs no interpolation (degenerate bracket): the only failing condition is its coverage, so `low_surface_coverage` (R-20) is the more specific and correct reason. No conflict; R-178 confirmed, the author3 rows stand.

## 3. Units
M3A_GATE_BUDGETS.md store budget wording '768 MB'/'1 GB' becomes '768 MiB'/'1 GiB' (the bytes were already read as binary: 805,306,368 B and 1,073,741,824 B). The author4 M3A_PERF_ACCEPTANCE.md B8 cells are updated in the same change; `check_gate_table.py` prints OK. The M2-B16 limit and decimal derived figures are unchanged.

- Updated qualification/synthetic/m3a/author4/MANIFEST.sha256 line for M3A_PERF_ACCEPTANCE.md to its new SHA-256 (267c16c7...) after the PR edited that file.
