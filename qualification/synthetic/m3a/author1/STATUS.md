# M3a fixtures, author 1: STATUS (SYNTHETIC, not committed, not run against any implementation)
Base origin/main ce880c8. Rulings applied: R-01 to R-161 incl. R-103..R-161, owner decisions 1 to 5. Self-check, determinism (two runs identical) and 58-mutant run: PASS (every mutant caught by >= 2 gating rows).

Rows (323 total, 224 required; all RULED, all gating): surface 104 (min 80), delta25 119 (60), tenors 43 (40), coverage 37 (24), american 20 (20).

Coverage of requirements:
- Surface frame (forward, ATM, smile, labels, contract reasons, order, empty chain, all-excluded, mixed styles): SUR rows; Q-13 solver bounds: 16 rows (price_out_of_bounds 6 contracts, upper_asymptote 5, exact lower = IV 0.0), r = q = 0 so bounds are exact (R-145).
- 25-delta bracket (R-04, R-09, R-10, R-21): put/call, target on strike (6), non-monotone (11), steep skew (11), no_delta_bracket (10), min strikes (9), put shift (25), crossed/locked/stale (7).
- Both delta conventions (R-155..R-158): delta_convention on every row and echoed; 39 forward rows, spot-vs-forward divergence, q=0 equality, symmetry (6), default spot (2), selector 7 (convention_not_allowed 3 types of string, malformed_type for int/null/bool), 6 surface frame rows with 25-delta points in both conventions.
- Tenors: as_is, variance interpolation, no extrapolation, no_bracketing_expiry incl. coverage-excluded bracketing expiry (R-104, R-139).
- Coverage gates (R-103, R-104): ratio 10 isolating rows (5/9, 4/7, 7/12 flip under 1/2), min_strikes 7, near-the-money clause 3 (exact +-10 percent boundary), expiry_days >= 1 (12), structural-first (3); American labels and american_itm (R-63, R-105): 20 rows.
- Frame shape R-141/R-142: status/reason frame-level, value null, details in expected.frame.

Known gaps:
- convention_mismatch (position 17, view read), skew25 / skew25_fwd metrics, V8 to V11, V21 delta rows: not M3A-0 surface rows, belong to the structural and V8 to V11 authors; none here.
- Tenor-level no_delta_bracket (R-139 second half, per-side constant maturity) is V8, not here.
- Because R-141 makes the frame unavailable on any failed 25-delta side, rows on narrow chains (tenor, coverage) carry frame reason no_delta_bracket incidentally; item-level values stay asserted in expected.frame.
- Solver-internal reasons (sigma_cap, precision_exhausted, bound_precision, iteration_budget) are unit level; precedence of a convention_not_allowed against other slot-13 codes is one error per row.
- Reviewer re-derivation of boundary rows still to do; D-11 to D-17 of AUTHORING_NOTES stay open.
