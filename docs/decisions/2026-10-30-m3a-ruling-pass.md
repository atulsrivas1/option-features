# 2026-10-30: M3a ruling pass (PO), exceptions list, owner product-decision batch, fixture-author brief

Decided: PO (ruling pass on docs/m3a/M3A_RULING_LIST.md, R-01 to R-102, after the independent review of PR 101). Status: RULED 2026-10-30 (PO), interim pending design ratification where the design is silent. Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

## 1. Decision
All recommended rulings R-01 to R-102 are accepted as written; SETTLED rows are unchanged. Explicit decisions:
- R-01: V21 is INCLUDED (M3A-11); the fixture total is 779 hand-derivable rows (docs/m3a/M3A_FIXTURE_REQUIREMENTS.md).
- R-99: M2 outputs keep their `label` field unchanged (no change to any M2 result); M3a results use `labels` (a list); the Result envelope supports both, additively.
- R-04 and R-05: spot delta (R25 convention, absolute value for puts, target 0.25 inclusive); certified delta (a float filter only with identical bytes).
- R-09: linear IV in delta. R-14: tenors 9, 30, 91 only. R-20: 3/5 of listed strikes and at least min_strikes 4. R-36: defaults (skew 5, skew change 2, term 3, term change 2, curvature 3, IV change 10 percent, X 5; points units).
- R-46: a constant history is unavailable `zero_range_history`. R-51: the `scalar_baseline` skip rule. R-52: per-series k up to 252 (additive store change). R-58: delayed feed is invalid_input `delayed_feed_tag`. R-81: V3 and V4 use the 30-day form only (partial). R-100: `cutoff_mismatch`.

## 2. Exceptions list (deliberate, with sources)
| Exception | Against | Source |
|---|---|---|
| R-46 constant history unavailable (`zero_range_history`) | M2 Q2 (a constant history is available and cannot fire) | design VR P3 |
| R-51 `scalar_baseline` skips missing and incomplete days, needs min_sessions available | M2 Q3 and AMB-17 (no substitution, no partial baseline) | design "at least 20 prior sessions" |
| R-58 delayed feed is invalid_input `delayed_feed_tag` | design wording "unavailable" | same interim choice as M2 |
| R-81 V3 and V4 on the 30-day IV only | design V3 "ATM IV ... same minute", V4 "ATM or constant 30-day" | design key constant_30d_iv_change; re-audit records "partial: 30-day form only" |
| R-52 per-series k up to 252 | M2 store hard cap 60 | additive store change; M2 series keep k <= 60 |

## 3. Interim list (pending design ratification where the design is silent)
R-04, R-09, R-14, R-27 to R-30, R-40, R-42, R-44, R-81. A changed design answer regenerates the dependent fixtures. All rulings are interim until then.

## 4. Owner product-decision batch (for the owner, facilitator only; none blocks the fixture author)
1. V21 included in M3a (put-side distance over call-side distance), or moved to M3b.
2. V3 and V4 on the 30-day IV only, against the design ATM wording.
3. Delta definition: spot delta of the BSM model at the contract own IV, absolute value for puts, target 0.25.
4. A constant history is unavailable (`zero_range_history`) against the M2 rule "available, cannot fire".
5. Scalar baseline with partial history: missing and incomplete days skipped, at least 20 available sessions.

## 5. Fixture-author brief (requirements; detail in docs/m3a/M3A_FIXTURE_REQUIREMENTS.md)
- Fresh checkout of origin/main; docs/m3a (matrix, budgets, fixtures, I/O contract, ruling list) and the M1 and M2 docs are the inputs.
- Owner goals in every deliverable: performance (budgets as hard gates, single-worker gates, two-stage synthetic then real, the opt-in default single-process runner reused, batched, memory and cache rules); all features and indicators first on synthetic data; adapter work last (RQ); the label sentence verbatim in every header and no forbidden term (docs/RELEASE_NOTE_TEMPLATE.md label rule 1).
- Independence: the Tester authors every fixture and expected value from the design text, the matrix, the contract and the ruled list, without reading any M3a module or the Developer tests, never using the library under test or the M1 solver to derive an expectation; a second reviewer re-derives at least 25 percent of the hand rows and all boundary rows.
- Rows per family: surface frame 80, 25-delta bracket 60, tenors 40, coverage gates 24, American labels 20, V1 40, V3 40, V4 40, V5 36, V6 30, V7 36, V8 48, V9 40, V10 48, V11 24, V21 24, units and rounding 20, history reuse 36, structural 87 (including 42 precedence rows and 2 cutoff_mismatch rows), lane 6: total 779; at least 20,000 randomized differential cases each for the 25-delta interpolation, the tenor interpolation, the rank forms and the sign-change rule; at least 40 mutants.
- Sources: allowed and forbidden lists as in the fixtures doc section 2; no download, network, vendor schema or recorded data; Python standard library; seeded, deterministic, LF generators with the SYNTHETIC tag; performance workloads generated at run time (samples and manifests committed only).
- Performance, determinism, batched-versus-single, cache and memory fixtures per M3A_GATE_BUDGETS.md, with the first task gate M3A-G0 at one worker.
- Rows with a design-silent ruling carry PENDING-RULING until the design ratifies it; an ambiguity found is recorded as a numbered question to the PO.
