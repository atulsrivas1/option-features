# M3a input and output contract (skeleton)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Author: Architect, 2026-10-30. Status: SKELETON for the PO ruling pass; shapes only, every value choice is a RECOMMENDED ruling in M3A_RULING_LIST.md. Written once so that the structural codes and ONE precedence list exist from the start (lesson of M2: the precedence list, type-first per field and the trusted-versus-untrusted input rule were reworked four times after the fixtures). Baseline: docs/m2/M2_IO_CONTRACT.md. Pure functions, no I/O, no clocks, single-threaded kernels. Exact arithmetic on the values returned by the M1 solver and the delta source; no float in any M3a output.

## 1. Conventions
- Times: integer nanoseconds since the Unix epoch (UTC); civil dates for expiries and sessions; windows closed [T-W, T] where a window exists.
- Strikes and prices: integer ticks (x 10^8 for strikes as in M1 `IVChain`, x 10^4 for prices as in M2), or text decimals converted once at ingest (grammar and type rules: R-65 to R-67, as M2 section 9 items 4 and 13 to 15).
- IV: annual decimal as returned by M1 (R-60); thresholds and differences in points (1 point = 0.01 annual vol); stored history values are integer micro-vol (R-48).
- Text: UTF-8, LF, canonical key order, no absolute paths. Every dataset has `"provenance": "SYNTHETIC"`. Non-JSON types in fixtures use the tagged objects of M2 section 9 item 14 (R-65).

## 2. Inputs
| Record | Fields | Notes |
|---|---|---|
| Chain | `contracts` list, `spot`, `rate`, `dividend_yield`, `cutoff_ns`, `lane`, `feed_delay_tag` ("live" or "delayed") | one chain at one cutoff; `contracts` exactly as the M1 `IVChain` input (right, strike, expiry, style, multiplier, quote with bid, ask, event_ns, known_at_ns, conditions); no change to that record |
| Contract id | string key, unique per chain | duplicates are structural |
| IV history | M2 `HistoryRecord` (series_id, metric, session_id, window_s, grid, total, complete, content_sha256) | metrics: `iv30`, `atm_iv`, `skew25`, `term_30_91` (session-close values or the minute grid, R-52); read only, as an M2 `HistoryView` |
| Prior reading | `prior` object: `value`, `kind` ("frame" or "session"), `time_ns` or `session_id` | supplied by the caller or read from the store (R-40) |
| Calendar | ordered sessions with `minutes` (M2) | the K-session window and the prior session come from it |
| Request | `evaluation_ns`, `tenors` (days), `delta_target`, `mode` ("intraday" or "end_of_day"), thresholds, X, K, `min_sessions`, `lane`, `expiry_min_days`, `min_strikes`, `min_coverage` | every parameter used is echoed in the result |

## 3. Outputs
One result per (output id, name, evaluation), the M2 `Result` envelope: `output_id` (M3A-0 to M3A-11), `series_id`, `session_id`, `evaluation_ns`, `status` ("available", "unavailable", "invalid_input"), `reason` (closed set of the matrix section 5, or null), `code` (structural, or null), `value`, `fired` (bool or null), `params`, `coverage`, `label`, `lane`, `version`. An unavailable or invalid_input result carries `value` null and `fired` null; `coverage` and `label` only for zero_denominator and the coverage reasons (M2 conventions, R-64).
| Output | `value` keys |
|---|---|
| M3A-0 surface frame | `expiries` list of {`expiry`, `days`, `forward`, `atm_iv`, `put25_iv`, `call25_iv`, `strikes_eligible`, `strikes_listed`, `labels`}, `tenors` map {`9`, `30`, `91`: {`iv`, `method`}} |
| M3A-1 V1 | `x`, `n`, `rank_le`, `upper_share`, `lower_share`, `form` |
| M3A-2 V3 | `x`, `n`, `minute`, `rank_le`, `upper_share` |
| M3A-3 V4 | `now`, `prior`, `change_points`, `change_ratio`, `basis` ("atm" or "iv30"), `prior_kind` |
| M3A-4 V5 | `pairs`: {`9_30`, `30_91`: {`longer`, `shorter`, `spread_points`}} (longer minus shorter) |
| M3A-5 V6 | `nearest`, `second`, `spread_points` (second minus nearest), `expiries` |
| M3A-6 V7 | `now`, `prior`, `gap_change_points`, `slope_change_points` |
| M3A-7 V8 | `put25_iv`, `call25_iv`, `skew_points` (put minus call), `tenor` |
| M3A-8 V9 | as V1 for the skew series |
| M3A-9 V10 | `now`, `prior`, `change_points`, `sign_now`, `sign_prior`, `sign_changed` |
| M3A-10 V11 | `wings_mid`, `atm_iv`, `curvature_points` |
| M3A-11 V21 | `put_distance`, `call_distance`, `ratio` |
Values are ints, reduced "n/d" strings of rationals, or null; never floats. Fired rules: threshold comparisons are inclusive ("at least X", "at most X"); percentile rule as M2 (upper_share <= X/100 for top X percent, lower_share for bottom X percent).

## 4. Structural codes and the ONE precedence list
Structural errors are status invalid_input with a closed `code`; the first failing code of the list is reported. Type-first per field (M2 ruling): a wrong-typed field (not an int or text as its grammar requires: float, Decimal, Fraction, bool, None, bytes) reports `malformed_type` at the list position where that field value check would run; a field with no value code reports it at the `malformed_type` slot. Within one position fields are checked in the order written.
| # | Code | Check |
|---|---|---|
| 1 | `bad_cutoff` | cutoff_ns not a non-negative int |
| 2 | `bad_spot` | spot not positive |
| 3 | `bad_rate` | rate or dividend_yield not finite or out of the ruled range |
| 4 | `duplicate_contract` | a contract id appears twice |
| 5 | `unknown_right` | right is neither call nor put |
| 6 | `bad_strike` | strike not positive |
| 7 | `bad_multiplier` | multiplier <= 0 |
| 8 | `bad_expiry` | expiry not a civil date, or not after the cutoff date |
| 9 | `unordered_quotes` | quote event times not monotone per contract |
| 10 | `malformed_type` | the type slot (price, size, flags and every field without a value code); includes `grid_not_60s` for a history grid |
| 11 | `lane_mismatch` | history lane differs from the request lane |
| 12 | `duplicate_session`, `non_monotone_grid`, `session_not_in_calendar`, `record_length_mismatch`, `out_of_order_append` | history record checks, M2 order (M2 section 9 item 5) |
| 13 | `tenor_not_allowed` | a tenor outside the allowed set |
| 14 | `delta_not_allowed` | delta target outside the ruled set |
| 15 | `threshold_required` | a fire rule asked with no threshold |
| 16 | `delayed_feed_tag` | V3 and intraday V1, V4 under a delayed tag |
Snapshot and trailer codes of the M2 store are inherited unchanged. An empty chain or a chain whose contracts are all excluded is not structural: unavailable with the M1 reasons counted in `coverage`.

## 5. Trusted versus untrusted inputs
- Untrusted (validated in full at the boundary): chains from a caller, history records at append and load, parameters. Every structural code of section 4 applies.
- Trusted (validated once, then scanned on hot paths): history views read from a store whose content hash was verified at attach, and chains already validated by `validate="full"`. `validate="scanned"` is the hot-path default; `validate="full"` is always available and gives the same codes (M2 convention). Cost statement: scanned validation is O(contracts read), full is O(chain).

## 6. Canonical serialization and hashing
As M2 section 4: one JSON object per result in the key order of section 3, separators `,` and `:`, rationals as reduced "n/d" strings, one object per line, LF; results ordered by (output_id, series_id, session_id, evaluation_ns); per-unit SHA-256 and the run hash over `unit key LF unit sha256 LF` in key order. Worker count, timings, cache statistics and store hashes appear only in the run log. Result `version` is the library version string (no bump proposed, R-64).

## 7. Runner interface (unchanged defaults)
Unit = underlying x session x cutoff; the unit reads an immutable history view; opt-in process pool, default single-process, `--workers 1` is the reference path; cap per PR 72; the runner adds no calculation; `gc.freeze()` after the store load and `content_hash()` compared after attach (M2 section 9 item 10).
