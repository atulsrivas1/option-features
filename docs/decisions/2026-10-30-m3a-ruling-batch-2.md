# 2026-10-30: M3a second ruling batch (25 ambiguities found by the four fixture authors)

Decided: PO (second ruling batch, relayed by the independent reviewer). Status: RULED 2026-10-30 (PO second batch), interim pending design ratification where the design is silent. Supersedes: the wording of R-83 (coverage terms) by R-103, and modifies R-71 (empty chain) by R-106; the first ruling pass is docs/decisions/2026-10-30-m3a-ruling-pass.md. Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

## Rulings
- Coverage (R-103, R-104): R-83 as written made the 3/5 gate unreachable. Listed strike = any contract record at the strike; eligible strike = at least one eligible quote (either right); min_strikes counts strikes; the near-the-money clause (at least 2 eligible strikes per right within +-10 percent of the forward, inclusive) is a coverage gate; no_atm_strike is checked before low_surface_coverage; a coverage-excluded expiry is treated like an expiry without an ATM strike in tenor interpolation.
- Labels and empty chain (R-105, R-106): a mixed frame carries both model labels (sorted); an unavailable result has labels []; an empty chain is unavailable with the new reason no_eligible_contract.
- Types (R-107, R-123, R-124, R-125): text or float expiry_days is malformed_type, a wrong value bad_expiry; wrong-typed cutoff_ns, expiry_days, mode, lane, right is malformed_type; the code field is `code`; None bid or ask is a missing quote (invalid_quote); non-finite floats use the tagged object {"py_type": "float", "text": "nan|inf|-inf"}.
- M3A-0 shape (R-108): the shape authored in author1 AUTHORING_NOTES D-10 is ratified interim and is in the I/O contract section 8.
- Solver failure (R-109): a failure on one contract excludes that contract (reason counted in coverage.contract_reasons) and the expiry continues if coverage holds.
- History (R-110 to R-114): max_sessions = last N available sessions; reason order upstream, insufficient_history, session_not_complete, zero_range_history; a history lane differing at read is insufficient_history, lane_mismatch at append only; same_minute_column skips short-grid sessions (no zero-padding); store.add_series(series_id, k), k up to 252.
- Prior and derived (R-115 to R-118): V10 prior_kind and condition per direction; V5 pair in {9-30, 30-91}; change_ratio unitless; V21 distances in points (x100) and no default threshold; fewer than n priors is insufficient_history; a bracketing expiry lacking a 25-delta bracket gives no_delta_bracket for the tenor; gate order: upstream and frame reasons, prior-reading checks, threshold.
- Structural (R-119 to R-122): delta_target {0.25} only; threshold names at_least, at_most, x; positions 16 to 18 apply only to outputs using that parameter; three pair rows that cannot hold both errors are equivalent swaps; threshold_out_of_range also at view read for x.
- Performance (R-126, R-127): iv30 minute series (not an atm_iv grid); unit-key session ordinals 01 to 05 (documented deviation from M2); "vega >= 4" is the M1 vega per 1.00 of volatility.

The ruling list now has 140 rows (R-01 to R-140); all rulings are interim pending design ratification where the design is silent.

## Appended rulings (R-128 to R-130)
- R-128 (Q-13, from inverse.py lines 130-150): price_out_of_bounds = target strictly below the lower bound or strictly above the upper bound (invalid_input); a target exactly at the lower bound is available with IV 0.0; exactly at the upper bound is upper_asymptote (nonidentifiable_inverse). sigma_cap, precision_exhausted, bound_precision and iteration_budget are not fixture-covered (solver internals needed); unit-tested with a stubbed solver in the Developer tests; the gap is recorded.
- R-129: series metrics iv30 (30-day IV minute series on the session grid), iv30_close, skew25, term_30_91 (session-close scalars), atm_iv; series_id "<UNDERLYING>/<lane>/<metric>"; scalar_baseline and same_minute_column return {values, sessions, n}.
- R-130: the fourth equivalent pair swap (minute_out_of_range, prior_not_before_cutoff), following from Q03.

## Appended rulings (R-131 to R-140, from the author-3 oracle review)
- R-131: structural request codes (including threshold_required at position 14 and prior_not_before_cutoff at 17) are reported before any evaluation; the upstream-first order applies only among result-level reasons.
- R-132 labels are lexicographic ASCII sorted including "delayed". R-133 down fires at x <= -X for change forms, V21 down at ratio <= X. R-134 prior_not_before_cutoff checks all supplied priors. R-135 V10 condition in {change, sign_change}, default change.
- R-136 empty prior store: no_prior_reading; fewer than n priors (non-empty): insufficient_history (V7 and V10). R-137 V11 and V21 failure precedence: ATM tenor, put side, call side. R-139 coverage-excluded bracketing expiry: no_bracketing_expiry; lacking a 25-delta bracket: no_delta_bracket.
- R-138 tolerances 3e-5 annual (IV-derived) and 0.005 points (25-delta-derived); R-62 is the upper bound; rows that cannot meet them are non-gating with the reason. R-140 request vocabulary: at_least, at_most, x only; V5 pair "9-30" and "30-91"; gating = false on near-threshold rows.
