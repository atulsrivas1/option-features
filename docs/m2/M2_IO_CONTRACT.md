# M2 input and output contract (draft)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Author: Architect, 2026-10-29. Status: DRAFT for the Tester and the Developer to author inputs and read outputs against; the exact module names and wire exposure stay open (candidate16 item). Shapes only; semantics are in M2_CAPABILITY_MATRIX.md. Pure functions, no I/O, no clocks, single-threaded kernels. All money and ratios are exact (integer ticks, `Fraction`); no float.

## 1. Conventions
- Times: integer nanoseconds since the Unix epoch (UTC) for prints; windows are closed [T-W, T]; session times are session-relative seconds on the grid.
- Prices: integer ticks (price x 10^4 as in `quotehist.as_ticks`) or decimal strings converted once at ingest; premium = ticks x size x multiplier, exact.
- Text files: UTF-8, LF, canonical key order, no absolute paths. Every dataset has `"provenance": "SYNTHETIC"`.

## 2. Inputs
| Record | Fields | Notes |
|---|---|---|
| Print | `contract_id`, `time_ns`, `price`, `size` (int >= 0), `multiplier` (int, 100 standard), `condition_excluded` (bool), `seq` (int tie breaker) | sorted by (time_ns, seq); `contract_id` resolves to Contract |
| Contract | `contract_id`, `underlying`, `right` ("C" or "P"), `strike` (ticks), `expiry` (civil date), `lane` ("stock" or "etf_index") | lane never mixed in shares or baselines |
| Session | `session_id` (civil date), `underlying`, `open_ns`, `close_ns`, `minutes` (grid length: 390 full, fewer for half-days), `complete` (bool), `feed_delay_tag` ("live" or "delayed") | calendar supplies `minutes`; delay is an input tag set by the adapter, never read by a kernel from a clock |
| Grid (derived) | per series, session, metric: array of `minutes` values at 60 s steps from open; session total | built from prints (M2-B18); sparse form for contract series: list of (index, value) plus zero count |
| HistoryRecord | `series_id` (contract id or name), `metric`, `session_id`, `grid`, `total`, `complete`, `content_sha256` | metrics: premium, contracts, prints, put_volume, call_volume |
| HistoryView | immutable, hashable; the K complete sessions strictly before a given session, per series | reads only; no look-ahead |
| Calendar | ordered list of session ids with `minutes` | the 20-session window is taken from this list |
| Request | `evaluation_ns` (T), `window_s` (60, 300, 900, 1800, 3600; F17 fixed 300), parameters of matrix section 3 (N, X, thresholds, K, minimum sessions, `quiet_gap` default 1), `filter` ("all", "calls", "puts"), `lane` | every parameter value used is echoed in the result |
Structural errors (status invalid_input, `code`): `unordered_prints`, `negative_size_or_price`, `bad_multiplier`, `duplicate_session`, `non_monotone_grid`, `session_not_in_calendar`, `window_not_allowed`, `delayed_feed_tag` (F1, F12, intraday F2 under a delayed tag). Validation scope: full on build and at the store boundary, scanned on hot paths with an explicit `validate="full"` switch, as for OC5 and OC6.

## 3. Outputs
One result per (output id, series or name, evaluation). Fields in canonical order:
`output_id` (M2-1 to M2-11), `series_id`, `session_id`, `evaluation_ns`, `status` ("available", "unavailable", "invalid_input"), `reason` (closed set below, or null), `code` (structural, or null), `value` (object of exact rationals as "n/d" strings or integers; per output below), `fired` (bool or null), `params` (every parameter used), `coverage` (counts: eligible prints, excluded_nonstandard_count, excluded_condition_count, unavailable_points), `label` (statistic or side name), `lane`, `version`.
| Output | `value` keys |
|---|---|
| M2-1 F1 | `p60`, `p900`, `ratio` |
| M2-2 F2a to F2c | `x`, `n`, `rank_le`, `upper_share`, `form` ("intraday" or "end_of_day"), metric name |
| M2-3 F2d | `parts` (three percentiles = 1 - upper_share), `average`, `direction` ("higher_is_more_unusual") |
| M2-4 F4 | `large_count`, `large_premium`, `premium_threshold` |
| M2-5 F17 | `window_premium` |
| M2-6 F7 | `top_strike`, `strike_share`, `top_expiry`, `expiry_share`, `total_premium` |
| M2-7, M2-8 F10, F20 | `x`, `median`, `mean`, `median_ratio`, `mean_ratio`, `consumer_default` ("median" or "mean") |
| M2-9 F18 | `put_volume`, `call_volume`, `put_share`, `put_call_ratio` |
| M2-10 F19 | `ratio`, `n`, `rank_le`, `upper_share` |
| M2-11 F12 | `episode_count`, `first_ns`, `last_ns`, `peak_ratio`, `peak_ns`, `quiet_gap` |
Reason closed set: `insufficient_history`, `session_not_complete`, `insufficient_window`, `zero_denominator`. Mapping to the existing vocabulary (no new synonyms): statistic equal to 0 -> `zero_denominator`; nothing stored or fewer sessions -> `insufficient_history`; `zero_mad` unused. Gate order: invalid_input, insufficient_history, session_not_complete, insufficient_window, zero_denominator.

## 4. Canonical serialization and hashing
- One JSON object per result, keys in the order of section 3, separators `,` and `:` (no spaces), rationals as reduced "n/d" strings (integers as plain integers), booleans and null as JSON, one object per line, LF.
- Results are ordered by (output_id, series_id, session_id, evaluation_ns) - never by completion order. Per-unit SHA-256 over the unit bytes; run hash over `unit key LF unit sha256 LF` in key order (as the M1 runner).
- The store serializes as one line per HistoryRecord in (series_id, metric, session_id) order, grids as integer lists; `content_sha256` covers the canonical line. Round trip must reproduce the same bytes (M2-B17).
- Worker count, timings, cache statistics and store hashes appear only in the run log, never in results.

## 5. Runner interface (unchanged defaults)
Unit = underlying x session x cutoff (key `SYN1/03/045`); the unit reads an immutable HistoryView as of its session. Opt-in process pool, default single-process; `--workers 1` is the reference path; cap per the PR 72 ruling. The runner adds no calculation.
