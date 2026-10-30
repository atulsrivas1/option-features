# M3a input and output contract (skeleton, revision 2)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Author: Architect, 2026-10-30. Status: SKELETON for the PO ruling pass; shapes only, value choices are RECOMMENDED rulings in M3A_RULING_LIST.md. Written once so that the structural codes and the precedence lists exist from the start (lesson of M2: precedence, type-first per field and trusted-versus-untrusted inputs were reworked four times after the fixtures). Baseline: docs/m2/M2_IO_CONTRACT.md and the M1 code interface (`chainiv.py`, `quotes.py`). Pure functions, no I/O, no clocks, single-threaded kernels.

## 1. Conventions (one convention per record type)
- Chain record type: follows M1 exactly. Strikes, bid, ask and spot: a text decimal with at most 8 decimal places, or a non-bool int meaning whole units (x 10^8 ticks internally); the M1 `to_ticks` rule. The M2 ticks rule (price x 10^4) applies ONLY to print families and is not used here. The price grammar `-?(\\d+(\\.\\d*)?|\\.\\d+)` (ASCII; "1." and ".5" valid) applies to chain text decimals with the M1 limit of 8 decimals; more than 8 decimals is `malformed_type`.
- Request scalars: `spot`, `rate`, `dividend_yield`: a non-bool int, an exact-rational string, or a finite binary64 float (as M1). Ranges (RULED): `rate` finite with |rate| <= 1; `dividend_yield` finite with 0 <= dividend_yield <= 1; `spot` finite and > 0. A rate or dividend_yield outside its range or non-finite is `bad_rate`; a non-positive or non-finite spot is `bad_spot`.
- History records and parameters: the M2 conventions (type-first per field; integers for sessions, minutes, K).
- Times: integer nanoseconds (UTC); `expiry_days` is an integer >= 1 supplied by the caller (M1: expiry N x 24 h after the cutoff, T = N/365). No civil-date conversion in M3a (an adapter duty, RQ item).
- IV: annual decimal as returned by M1 (binary64); thresholds and differences in points (1 point = 0.01 annual vol).
- Text: UTF-8, LF, canonical key order, no absolute paths; every dataset has `"provenance": "SYNTHETIC"`; non-JSON types in fixtures use the M2 tagged objects (R-65).

## 2. Inputs
| Record | Fields | Notes |
|---|---|---|
| Chain contract | EXACTLY the M1 `ChainContract`: `contract_id`, `expiry_days`, `right` ("call" or "put"), `strike`, `bid`, `ask`, `event_ns`, `known_at_ns` (None = event_ns), `style` ("european", "american"), `condition` ("regular" default) | no multiplier, no civil-date expiry, no lane on the chain record |
| Chain | `contracts`, `spot`, `rate`, `dividend_yield`, `cutoff_ns` | one chain at one cutoff |
| Request | `mode` in {"intraday", "close"}, `lane` in {"stock", "etf_index"}, `stale_limit_ns` (default 10 s), `feed_delay_tag` ("live" or "delayed"), `evaluation_ns`, `tenors`, `delta_target`, `direction`, thresholds, X, `min_sessions` (20), `max_sessions` (252), `minute`, `prior_sessions` (1), `min_strikes`, `min_coverage` | every parameter used is echoed in the result |
| Prior reading | `value`, `kind` ("frame" or "session"), `time_ns` or `session_id` | the reading time must be before the cutoff (`prior_not_before_cutoff`) |
| History record | M2 `HistoryRecord`, lane only here; scalar series: `window_s` 0, empty grid, `total` = integer in 10^-8 units; minute series: dense grid | read as an M2 view, `scalar_baseline` and `same_minute_column` (matrix section 6) |
| Calendar | ordered sessions with `minutes` (M2) | the prior sessions come from it |
Session-close frame = the frame evaluated at `close_ns` on the close chain, stored as a scalar (not as a grid minute).

## 3. Outputs
The M2 `Result` envelope: `output_id` (M3A-0 to M3A-11), `series_id`, `session_id`, `evaluation_ns`, `status`, `reason` (closed set, matrix section 5, or null), `code` (structural, or null), `value`, `fired`, `params`, `coverage`, `labels` (list), `lane`, `version`. An unavailable or invalid_input result carries `value` null and `fired` null.
Number forms (RULED): quote-derived exact values (counts, coverage ratios) are ints or reduced "n/d" strings; solver-derived values (IV, forward, derived series) are binary64 and are reported as decimal strings rounded half to even to 8 decimals; derived series (skew25, term_30_91) are the difference of the UNROUNDED floats rounded once to 8 decimals; all threshold and sign decisions use the rounded decimals; stored history values are integers in 10^-8 units. Canonical hashes of solver-derived values are Windows-only (no cross-platform byte claim).
`coverage`: `listed_strikes`, `eligible_strikes`, per-expiry counts, and `contract_reasons` = {M1 gate reason: count} (per-contract counts have their own field); `labels`: the M1 label of the model used ("exact-model" or "approximate: European model on an American-style contract"), plus "delayed".
| Output | `value` keys |
|---|---|
| M3A-0 | `expiries` list of {`expiry_days`, `forward`, `atm_iv`, `put25_iv`, `call25_iv`}, `tenors` {`9`, `30`, `91`: {`iv`, `method`, `expiries_used`}} |
| M3A-1 V1 | `x`, `n`, `rank_le`, `upper_share`, `lower_share`, `form` |
| M3A-2 V3 | `x`, `n`, `minute`, `rank_le`, `upper_share` |
| M3A-3 V4 | `now`, `prior`, `change_points`, `change_ratio`, `prior_kind` |
| M3A-4 V5 | `pairs` {`9_30`, `30_91`: {`longer`, `shorter`, `spread_points`}} (longer minus shorter) |
| M3A-5 V6 | `nearest_days`, `second_days`, `spread_points` (second minus nearest) |
| M3A-6 V7 | `now`, `priors` (list of {`session_id`, `gap`}), `gap_change_points` for the n-th prior; no slope key |
| M3A-7 V8 | `put25_iv`, `call25_iv`, `skew_points` (put minus call), `tenor` |
| M3A-8 V9 | as V1 for the skew series |
| M3A-9 V10 | `now`, `priors`, `change_points`, `sign_now`, `sign_prior`, `sign_changed` (sign of the rounded-once difference) |
| M3A-10 V11 | `wings_mid`, `atm_iv`, `curvature_points` |
| M3A-11 V21 (PROPOSED) | `put_distance`, `call_distance`, `ratio` |
Fire rules: comparisons inclusive ("at least X", "at most X") on the rounded decimals and the `direction` parameter (up, down, either); percentile rule as M2 for top X percent (upper_share <= X/100) and bottom X percent (lower_share <= X/100).

## 4. Structural codes and precedence lists (one list PER ENTRY POINT, as M2)
Structural errors are status invalid_input with a closed `code`; the first failing code of the entry point list is reported. Type-first per field (M2 ruling): a wrong-typed field reports `malformed_type` at the position where that field value check would run; a field with no value code reports it at the `malformed_type` slot; within one position fields are checked in the order written. M1 raises ValueError for these conditions; the M3a wrapper maps them to codes.
**Request (chain and parameters), 18 positions:**
| # | Code | Check |
|---|---|---|
| 1 | `bad_cutoff` | cutoff_ns not a non-negative int |
| 2 | `bad_spot` | spot not finite or not > 0 (a wrong type is malformed_type here) |
| 3 | `bad_rate` | rate not finite or |rate| > 1; dividend_yield not finite or outside 0 to 1 |
| 4 | `invalid_mode` | mode not in {intraday, close} |
| 5 | `invalid_lane` | lane not in {stock, etf_index} |
| 6 | `bad_expiry` | expiry_days not an int >= 1 (as M1; per contract) |
| 7 | `unknown_right` | right not call or put |
| 8 | `duplicate_contract` | a contract id appears twice |
| 9 | `bad_strike` | strike not positive |
| 10 | `malformed_type` | quote fields, condition, style, event times and every field without a value code; more than 8 decimals |
| 11 | `duplicate_contract` | same expiry, strike and right twice |
| 12 | `tenor_not_allowed` | a tenor outside {9, 30, 91} |
| 13 | `delta_not_allowed` | delta target outside the ruled set |
| 14 | `threshold_required` | a fire rule asked without a threshold |
| 15 | `threshold_out_of_range` | X outside 0 to 100 (a value code) |
| 16 | `minute_out_of_range` | V3 minute outside the session grid |
| 17 | `prior_not_before_cutoff` | prior reading time at or after the cutoff |
| 18 | `delayed_feed_tag` | V3, intraday V1 and V4 under a delayed tag |
**History append and load (M2 order, unchanged):** lane_mismatch, session_not_in_calendar, record_length_mismatch, non_monotone_grid, duplicate_session, out_of_order_append (6 positions; this is where position 12 of the earlier skeleton lives).
**Snapshot:** snapshot_bad_magic, snapshot_length_mismatch, snapshot_hash_mismatch; **text load:** trailer_missing, trailer_count_mismatch, trailer_hash_mismatch (M2, unchanged).
**View read (`scalar_baseline`, `same_minute_column`):** session_not_in_calendar (current session), minute_out_of_range, malformed_type (min_sessions, max_sessions), threshold_out_of_range (4 positions).
An empty chain, a chain whose contracts are all excluded, or a missing history is not structural: unavailable with the reasons of the matrix.

## 5. Trusted versus untrusted inputs
- Untrusted (validated in full at the boundary): chains from a caller, history records at append and load, parameters. Every code of section 4 applies.
- Trusted (validated once, then scanned on hot paths): views of a store whose content hash was verified at attach, and chains already validated by `validate="full"`. `validate="scanned"` is the hot-path default; `validate="full"` is always available with the same codes (M2 convention). Cost: scanned is O(contracts read), full is O(chain).

## 6. Canonical serialization and hashing
As M2 section 4: one JSON object per result in the key order of section 3, separators `,` and `:`, one object per line, LF; ordered by (output_id, series_id, session_id, evaluation_ns); per-unit SHA-256 and the run hash over `unit key LF unit sha256 LF` in key order. Worker count, timings, cache statistics and store hashes appear only in the run log. Result `version` is the library version string (no bump proposed, R-64).

## 7. Runner interface (unchanged defaults)
Unit = underlying x session x cutoff; the unit reads an immutable history view; opt-in process pool, default single-process, `--workers 1` is the reference path; cap per PR 72; the runner adds no calculation; `gc.freeze()` after the store load and `content_hash()` compared after attach.
