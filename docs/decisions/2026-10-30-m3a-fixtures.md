# 2026-10-30: M3a synthetic fixtures (4 independent sets) and fixture rulings R-162..R-185

Decided: coordinator (commit of PO-approved sets). Status: fixtures independent-reviewed, NOT yet run against any implementation. PO acceptance pending. Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

## 1. What was committed
Four independently authored sets under `qualification/synthetic/m3a/author1..author4/` (96 files, about 7.5 MB in total, largest file 0.9 MB), each with its own `MANIFEST.sha256` that lists explicit files (author1 19, author2 20, author3 32, author4 21, plus the manifest itself). No scratch, check or work directories were copied. Verify with `sha256sum -c MANIFEST.sha256` inside each set directory. All files are LF. Two author1 files (`m3a_ref.py`, `m3a_selfcheck.py`) arrived with CRLF line endings; they were converted to LF and their two manifest lines recomputed (content otherwise unchanged).

| Set | Scope | Rows | Mutants | Reviewers' verdict |
|---|---|---|---|---|
| author1 | surface frame, 25-delta bracket, tenors, coverage gates, American labels | 323 (224 required) | 58, each caught by at least 2 rows | APPROVE after round 2 |
| author2 | V1, V3, V9, history reuse, units and rounding, G4 history fingerprints | 295 (176 required) | 73, each caught by at least 2 rows | APPROVE after round 2 |
| author3 | V4-V8, V10, V11, V21 | 406 | 54, each caught by at least 2 rows | APPROVE after round 2 |
| author4 | structural (157 plus 45 aux), lane 6, perf and resource rows 71, workload manifest, perf acceptance and runner contract | 208 (+71 perf rows) | 56 (48 effective, 8 equivalent swaps) plus 10 infrastructure | APPROVE after round 2 |

Status: fixtures independent-reviewed, NOT yet run against any implementation. Expected values come from the rules, never from library output.

## 2. Coordinator unit decision (pending owner review)
768 MB means 768 MiB (805,306,368 B) and 1 GB means 1 GiB (1,073,741,824 B) in the M3a gates. `docs/m3a/M3A_GATE_BUDGETS.md` still says MB and GB: follow-up for the Architect to align the wording.

## 3. Tracked follow-ups
- Author2 D7, D10, D12, D13 rows (R-175).
- convention_mismatch x prior_not_before_cutoff pair rows (R-176; slot 17 ordering is covered by author2 V9-065..069 and H-071..074).
- Add the `invalid_direction` code to the IO contract and then author the bad-string direction row (R-185).
- STRUCT-110 uses `prior` on M3A-6, which takes `priors` (weak row).
- Author2 V3-068 and V3-069 carry ruling tag R-81; it should cite R-153.
- Author3 STATUS.md has stale per-requirement counts; V21-D1..D4 `boundary.note` is inaccurate for the round-annual-first order.
- Harness notes: author1 AME rows have no per_expiry; D25-T rows may bracket either side of 0.25.
- Architect to confirm R-178 (exact 30-day expiry failing coverage gives `low_surface_coverage`) against the R-139 wording.

## 4. Rulings R-162 to R-177 (m3a-fixture-rulings.md, copied)
### 1. V6 empty chain (R-162)
- R-162: V6 with an empty chain, or with no contract passing the M1 gates, is unavailable `no_eligible_contract`, not `fewer_than_two_expiries`. Reason: R-106 is a frame-level reason that precedes every output-level count; `fewer_than_two_expiries` (R-32, R-91) applies only when at least one contract is eligible but fewer than two expiries pass coverage. Author3 rows V6-NE1..3 stand as gating. Default for similar cases: frame-level reasons win over output-level counts.

### 2. Author4 open items
- R-163 (X3): sparse grid_idx on a minute series is allowed, so `non_monotone_grid` rows stand. Reason: M2 grids already carry explicit indices; forbidding gaps would make the code unreachable.
- R-164 (X5): strike text with more than 8 decimals is `malformed_type` at position 9; trailing zeros within 8 decimals ("1.00000000") are valid, beyond 8 ("1.000000000") are `malformed_type` (grammar is length-based, not value-based). Reason: one textual rule, no normalisation step in the library. Author4 adds 1 row for the trailing-zero case.
- R-165 (X8): `direction` outside {up, down, either} is `invalid_param` (the existing value code at the threshold slot); `known_at_ns` before `event_ns` and the rate text place limit stay M1 input rules and are not re-tested in M3a. Reason: M3a adds no new chain validation; direction needs one code. Author4 adds 2 rows (bad direction string; non-string direction = malformed_type).
- R-166 (X12): confirmed: rank_le and upper_share count the history only, today excluded (R-45). No change.
- R-167 (X13): confirmed: pair (14, 15) is an equivalent swap (no output takes both threshold keys and x), as R-121. No change.
- R-168 (X14): confirmed: delta_target and tenors positions apply to every chain-reading output (M3A-0, M3A-3..M3A-11), iv_form only to M3A-2 and M3A-3 (V3, V4), delta_convention only to M3A-0 and M3A-7..M3A-11. Reason: matches R-120 (positions apply only to outputs using that parameter) and owner decisions 2 and 3. No change.
- R-169 (P3): accepted: M3A-G0 reuses the M2 workload manifest for print and quote streams; G8 supplies chain and M3a inputs only. Reason: avoids two sources of truth for M2 load.
- R-170 (P5): accepted with a narrowing: keep the 0.03 floor, but chain_truth is asserted on contracts with vega >= 4 (R-127), which covers ATM and 25-delta regions; floored wings are throughput load only. Reason: performance is the main goal; floored quotes still exercise the solver path.
- R-171 (P7): accepted: the runner adds `delta_evaluations` to its response (tool change, deviation D4). Reason: delta count is the main M3a cost driver and no counter exists; Developer implements it in the runner, not the library.

### 3. Gaps: required before merge versus tracked follow-up
Required before the fixtures merge:
- R-172 (author3, V4 selector 2+2 vs 3+3): required. Author3 adds 1 `iv_form_not_allowed` and 1 `malformed_type` row to V4 (author2 V3 already exceeds). Reason: the requirement is per selector family and cheap to meet.
- R-173 (author3, V8 forward rows 10 vs 12): required. Author3 adds 2 forward-delta V8 rows. Reason: stated minimum; V8 is the tenor-level 25-delta path with the most convention risk.
- R-174 (author3, V4-V7 ignore delta_convention): required, as stated in R-149/R-155. A delta_convention key on V4-V7 is ignored (not validated, not echoed). Author3 adds 1 row per output (4 rows, including an invalid value that must NOT give convention_not_allowed). Reason: a validator applied to the wrong outputs is a likely implementation defect and no row catches it.
Tracked follow-ups (merge allowed, issue opened):
- R-175 (author2, no rows for D7, D10, D12, D13): follow-up. D7 V3 is live only (mode close is `invalid_mode`, row optional); D10 minute-grid hash total = units of each minute, rows in the history follow-up; D12 coverage on supplied-value results is null (not asserted); D13 max_sessions < min_sessions is `invalid_param` at position 10, follow-up rows. Reason: none blocks a ruled code path in M3a release; each is a narrow edge.
- R-176 (author3, convention_mismatch x prior_not_before_cutoff pair): follow-up; order already ruled (position 17: prior_not_before_cutoff first). Author2 pair rows V9-065..069 and H-071..074 cover slot 17 ordering. Reason: order is ruled and covered by another family.
- R-177 (author1, incidental frame reasons): accepted as is. Rows on narrow chains keep frame reason no_delta_bracket by R-141; item values stay asserted in expected.frame. Reason: consequence of R-141, not a defect; no rework.

### 4. Owner-level items
None (no pricing, legal or new principle raised).

## 5. Rulings R-178 to R-185 (m3a-fixture-rulings-2.md, copied)
### 1. Exact 30-day expiry failing coverage (R-178)
- R-178: an expiry at exactly the target tenor that fails coverage gives `low_surface_coverage`, not `no_bracketing_expiry`. Reason: the expiry exists and brackets the target (exact match is a degenerate bracket); the failure is coverage, and the more specific reason helps users. R-104 gets a clarifying note. Change: spec note only; author3 rows V4-M02, V8-F1, V8-F2, V10-H2, V10-M2, V11-F1, V21-F3 stand.

### 2. Covered expiry with no both-right strike (R-179)
- R-179: no fallback; a covered selected expiry with no strike quoted on both rights gives `no_atm_strike`. Reason: R-151 selects the expiry first and the ATM step then works inside it; silent fallback to another expiry would change the tenor the user asked for. Change: none; V4-A-17, V5-H-1 stand.

### 3. Labels on expiries not feeding the ATM-form output (R-180)
- R-180: labels are output-level: only expiries actually used by the output appear. Reason: R-105 labels describe the value's provenance; listing unused expiries misleads. Change: rows V4-A-15, V4-A-16 drop the extra labels (frame-level detail stays in expected.frame).

### 4. skew_points rounding order (R-181)
- R-181: compute in full precision, multiply by 100, round once to 8 decimals: 0.19531250. Reason: single final rounding (round-once rule) avoids double-rounding error. Change: author2 U-016 expected value becomes 0.19531250.

### 5. Boundary-exact threshold rows (R-182)
- R-182: change the quotes, not the expected value: adjust each row's quotes so the round-once value equals the threshold exactly, keeping fired=true. Reason: the rows exist to test the inclusive boundary; fixing expected to false would lose that coverage. Change: author3 V6-D2, V6-D3, V8-D1, V8-D3, V21-D3, V21-D4 (quotes and recomputed truths); if no 8-decimal quote reaches the boundary exactly, keep the row with fired=false and add a sibling row that does.

### 6. Unavailable rows and echoes (R-183, R-184)
- R-183: on unavailable results `labels` is allowed to be omitted or []; tests treat omitted as []. Reason: R-144 already permits omission; requiring one form adds no user value. Change: none; author2 V1/V3/V9 rows stand.
- R-184: iv_form and delta_convention echo in `params` only, never in value keys (IO contract section 3). Change: author2 V3/V9 rows that put them in value keys move them to params.

### 7. Bad `direction` value (R-185, supersedes the code in R-165)
- R-185: `invalid_param` is not in the IO contract's closed list. Architect adds a new code `invalid_direction` to the contract as a tracked follow-up (issue opened). For now only the non-string direction row (`malformed_type`) is required; the bad-string row is deferred until the code is in the contract. Reason: fixtures must not assert a code the contract does not define.

### Owner-level items
None.
