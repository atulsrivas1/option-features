# R26 variants: evidence of delivery and verification

Public-safe summary. No fixture-derived values are reproduced here.

## What R26 delivered

| Layer | Repository | PRs |
|---|---|---|
| Library | option-features | 19, 21 |
| I/O | option-feature-io | 7 |
| Workers | option-feature-workers | 7 |
| Docs (merged) | option-features | 12, 15 |

## Fixture phase

- N4 fixtures: 63 cases authored by a Sonnet worker, then two independent reviews. Blocking findings: incoherent Control events; an unflagged inferred pointer.
- Contained run (attempt 4) passed on its first run in 85 s, 2,554 rows.
- Audit: 176 checks, 4 failing; the 4 are auditor limits, not fixture defects.
- Freeze: 2,546 rows.
- Excluded after freeze, pending a regenerated candidate5: 18 library-triage and 10 I/O-triage fixture-defect rows.

## Per-layer manual-run results

- Library: B3 153/153, F3 174/174, F4 44/45, N4 30/31 library rows, representative 7 of 23 (16 excluded as fixture defects). An inventory follow-up added 43 record types (review: APPROVE).
- I/O: final 0 mismatches. Codec 104, field 1502, wire 79, union 27 (+9 excluded), stage 7, output 6 (+3 excluded, joint rows; see DECISIONS 2026-10-23 I/O triage), BOM 19 (+1 excluded).
- Workers: all 76 owned rows pass, with storage on DuckDB, after a Sonnet continuation and a second review whose conditions were applied.

## Exclusions and why

- Representative fixtures predated the quote-selector clarification and were never regenerated.
- One N4 selector tie error; one F4 row; one FEFF row.
- Nine unknown-tag stage rows.
- All are fixture-vs-contract triage outcomes, held out until candidate5 rather than bending code to match them.

## Deferred contract gaps

See option-feature-workers `docs/R26_VARIANTS_DEFERRED_CONTRACT_GAPS.md`.

## What is NOT claimed

- No numerical acceptance beyond the fixtures.
- No Windows qualification.
- No browser demo.
- No release acceptance.
- The contract is not formally frozen; owner review is pending.
