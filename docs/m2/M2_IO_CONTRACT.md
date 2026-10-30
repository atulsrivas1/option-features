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
| HistoryRecord | `series_id` (contract id or name), `metric`, `session_id`, `window_s`, `grid`, `total`, `complete`, `content_sha256` | metrics: premium, contracts, prints, put_volume, call_volume |
| HistoryView | immutable, hashable; the K complete sessions strictly before a given session, per series | reads only; no look-ahead |
| Calendar | ordered list of session ids with `minutes` | the 20-session window is taken from this list |
| Request | `evaluation_ns` (T), `window_s` (60, 300, 900, 1800, 3600; F17 fixed 300), parameters of matrix section 3 (N, X, thresholds, K, minimum sessions, `quiet_gap` default 1), `filter` ("all", "calls", "puts"), `lane` | every parameter value used is echoed in the result |
Structural errors (status invalid_input, `code`): `unordered_prints`, `negative_size_or_price`, `bad_multiplier`, `duplicate_session`, `non_monotone_grid`, `session_not_in_calendar`, `window_not_allowed`, `threshold_required`, `out_of_order_append`, `delayed_feed_tag` (the single status word everywhere: invalid_input with this code; F1, F12, intraday F2 and intraday F10 under a delayed tag). Validation scope: full on build and at the store boundary, scanned on hot paths with an explicit `validate="full"` switch, as for OC5 and OC6.

## 3. Outputs
One result per (output id, series or name, evaluation). Fields in canonical order:
`output_id` (M2-1 to M2-11), `series_id`, `session_id`, `evaluation_ns`, `status` ("available", "unavailable", "invalid_input"), `reason` (closed set below, or null); an unavailable or invalid_input result carries `value` null and `fired` null, `code` (structural, or null), `value` (object of exact rationals as "n/d" strings or integers; per output below), `fired` (bool or null), `params` (every parameter used), `coverage` (counts: eligible_count, nonstandard_count, excluded_condition_count, unavailable_points), `label` (statistic or side name), `lane`, `version`.
| Output | `value` keys |
|---|---|
| M2-1 F1 | `p60`, `p900`, `ratio` |
| M2-2 F2a to F2c | `x`, `n`, `rank_le`, `upper_share`, `form` ("intraday" or "end_of_day"), metric name |
| M2-3 F2d | `parts` (three percentiles = 1 - upper_share), `average`, `direction` ("higher_is_more_unusual") |
| M2-4 F4 | `large_count`, `large_premium` (ticks), `threshold_ticks` (in `params`, 1000000000 for 100,000 USD) |
| M2-5 F17 | `window_premium` |
| M2-6 F7 | `top_strike`, `strike_share`, `top_expiry`, `expiry_share`, `total_premium` |
| M2-7, M2-8 F10, F20 | `x`, `median`, `mean`, `per_statistic` ({median, mean} each with status, reason, ratio), `consumer_default` ("median" or "mean"); top-level `value` is null when the default statistic is unavailable |
| M2-9 F18 (params `at_least`, `at_most`) | `put_volume`, `call_volume`, `put_share`, `put_call_ratio` |
| M2-10 F19 | `ratio`, `n`, `rank_le`, `upper_share` |
| M2-11 F12 | `episode_count`, `first_ns`, `last_ns`, `peak_ratio`, `peak_ns`, `quiet_gap` |
Reason closed set: `insufficient_history`, `session_not_complete`, `insufficient_window` (F1, F2, F10, F12: before session open + W), `zero_denominator`. Mapping to the existing vocabulary (no new synonyms): statistic equal to 0 -> `zero_denominator`; nothing stored or fewer sessions -> `insufficient_history`; `zero_mad` unused. Gate order: invalid_input, insufficient_history, session_not_complete, insufficient_window, zero_denominator.

## 4. Canonical serialization and hashing
- One JSON object per result, keys in the order of section 3, separators `,` and `:` (no spaces), rationals as reduced "n/d" strings (integers as plain integers), booleans and null as JSON, one object per line, LF.
- Results are ordered by (output_id, series_id, session_id, evaluation_ns) - never by completion order. Per-unit SHA-256 over the unit bytes; run hash over `unit key LF unit sha256 LF` in key order (as the M1 runner).
- The store serializes as one line per HistoryRecord in (series_id, metric, window_s, session_id) order, grids as integer lists; `content_sha256` covers the canonical line. Round trip must reproduce the same bytes (M2-B17).
- Worker count, timings, cache statistics and store hashes appear only in the run log, never in results.

## 5. Runner interface (unchanged defaults)
Unit = underlying x session x cutoff (key `SYN1/03/045`); the unit reads an immutable HistoryView as of its session. Opt-in process pool, default single-process; `--workers 1` is the reference path; cap per the PR 72 ruling. The runner adds no calculation.

## 6. PO-M2-AMB rulings: shapes (interim pending design ratification where the design is silent)
1. Print is the wire encoding of the section 2 Print fields, `[contract_id, time_ns, price, size, multiplier, condition_excluded, seq]` plus an optional 8th element `side` (vocabulary "ask", "bid", "unknown"); kernels ignore it.
2. Premium values are integer ticks = price(ticks, 10^4) x size x multiplier. Thresholds are carried as `params.threshold_ticks` (100,000 USD = 1000000000); `value.large_premium` and `window_premium` are ticks.
3. F10 and F20 results: top-level `status`, `reason`, `fired` and `value` follow the consumer default statistic (F10 median, F20 mean); `value.per_statistic` = {"median": {status, reason, ratio}, "mean": {status, reason, ratio}}; `value` is null when the default is unavailable.
4. Grid: point i at open + 60 s x i (i from 0); for a window W the first W/60 points of each session are dropped before open + W; history n counts only the remaining points.
5. F12 `value`: `episode_count`, `first_ns` and `last_ns` (onsets of the first and last episode, null at count 0), `peak_ratio`, `peak_ns` (over the session to date, ties earliest), `unavailable_points` (every unavailable grid point), `quiet_gap`. Before 900 s since open: unavailable, insufficient_window.
6. Store record key (series_id, metric, session_id, window_s); each grid entry is the window-W value of that request window at that grid point. Canonical line key order: `series_id`, `metric`, `session_id`, `window_s`, `grid`, `total`, `complete`, `content_sha256`. `content_sha256` = SHA-256 of the canonical line without the `content_sha256` field, followed by LF. Sealing marks a record immutable and builds its sorted copies; an append whose session equals the series last appended session is structural `duplicate_session`; an earlier one is structural `out_of_order_append`. The retention ring counts every stored session, complete or not; history n counts only complete sessions.
7. `label` contents: F1 the filter name ("all", "calls", "puts"); F10 and F20 the consumer default statistic name; F18 "put"; F2 end-of-day under a delayed tag "delayed"; `coverage.degraded` true when F20 uses supplied end-of-day totals. `coverage.excluded_condition_count` counts every print with an excluded condition (including those also nonstandard); `coverage.nonstandard_count` counts only non-excluded nonstandard prints.
8. F2c intraday: x = count / (W/60), history counts divided by the same; F2c end-of-day: x = count / session minutes, history counts divided by the same, windowless for window_not_allowed. F2d: `fired` null, `parts` always shown, `reason` that of the first unavailable part (order F2a, F2b, F2c). F19: fires when upper_share <= X/100, X default 5, n = usable prior ratios (20).
9. Structural errors are checked in the order: unordered_prints, negative_size_or_price, bad_multiplier (multiplier <= 0), duplicate_session and non_monotone_grid (within a series record set), session_not_in_calendar, window_not_allowed, threshold_required, out_of_order_append, delayed_feed_tag; the first failing code is reported. A missing, incomplete or absent session is never structural: insufficient_history, no substitution.
10. `window_not_allowed` applies to F2 intraday, F2d, F4, F7, F10 and F18 (allowed set 60, 300, 900, 1800, 3600 s); F17 is fixed 300 s; F1 and F12 take no window. F18 with neither `at_least` nor `at_most`: `threshold_required`.
11. Defaults: F1 N = 3; F12 ratio N = 3 and n_episodes = 1; F4 N = 1; F10 and F20 N = 2; F2 and F19 X = 5; F7 share 3/5.

## 7. Conventions ruled after the PR 76 review (interim pending design ratification where the design is silent)
- An unavailable result carries `coverage` and `label` only for zero_denominator; for every other gate they are null. F10 and F20 unavailable results carry `label` and `per_statistic`.
- `unavailable_points` (F12) counts every unavailable grid point, including the first 15 before 900 s.
- A history lane differing from the request lane gives insufficient_history. session_not_in_calendar applies to the current session only.
- F12 `peak_ratio` and `peak_ns` are taken over the available points of the session to date even with zero episodes (ties earliest: peak 1 at the earliest available point when all ratios are 1).
- F2d `fired` is null in M2 (design request DR-M2-1, matrix section 11).

## 8. Story B output rules (PR 79)
See section 9 (single authoritative section) for: shapes, structural codes and precedence, price grammar, F18 `ratio_reason` and `version`, F12 coverage and early-grid rules, store I/O and runner rules. Nothing is restated here.
