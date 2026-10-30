# M2 fixture additions (independent Tester)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Status: authored, not run against any implementation. Every dataset carries provenance SYNTHETIC. Seed 20261029, Python 3.12 stdlib only.
The merged files (parent folder, MANIFEST.sha256) are unchanged; this folder only adds files. Reuses m2common.py, m2_ref.py and m2_load.py read-only.

## 1. Scope (185 rows, 7 files)
- m2_cases_add_struct.json (60): unknown_contract 10 and malformed_type 10 (2 rows each for F1, F4, F7, F17, F18; bool price 3, float price 3, float size,
  float time 2, bool multiplier 2, over-precision text 3), precedence pairs 10 (2 rows each: unordered+negative, negative+bad_multiplier,
  bad_multiplier+unknown_contract, unknown_contract+malformed_type, malformed_type+window_not_allowed), F1 delayed with unknown contract 2, trailing-zero text
  price accepted 2, float window_s = window_not_allowed 2, integer-tick prices valid 2, text grammar 6 ('+1.0000', '1e3', ' 1.0000', a non-ASCII digit are
  malformed_type; '.8', '.2', '.5' valid), condition_excluded flag 4 (int 1 and bool true valid; 2 and 3 malformed_type), bool seq 2, plus 4 mutant-coverage rows.
- m2_cases_add_data.json (30): prints before open excluded from F4, F7, F17, F18 windows when the window reaches before open (8, incl. a print exactly at open),
  F12 built from prints (9, incl. coverage from prints, filter, nonstandard and excluded-condition counts, pre-open prints, off-grid T, burst at T),
  premium above 2^53 for F4 and F17 (4), fractional N = 3/2 for F1 (3, one sensitive to truncation) and F4 (2).
- m2_cases_add_store.json (24), m2_cases_add_snapshot.json (14), m2_cases_add_params.json (16): see section 6.
- m2_cases_add_grid.json (23): story A trade-to-grid builder, output id M2-GRID: premium, contracts, prints, put_volume, call_volume, windows 60 to 3600,
  prints before open and after close excluded, prints exactly at close (contracts and premium rows), the final minute (total only), half-day grid (6 minutes),
  nonstandard, excluded-condition and both-flag prints with coverage counts, lane tag, sparse contract series (3 rows), ties.
Rows follow the merged compact format (m2_load.py). Generators gen_m2add_<name>.py (seeded, LF, no absolute paths, --out relative) use m2add_oracle.py
(oracle A', wraps the merged oracle A). Independent second implementation: m2add_ref.py (wraps m2_ref, own validators and grammar scan, bisect prefix sums,
own grid builder). m2add_selfcheck.py recomputes all 185 rows (0 mismatches) and asserts the per-category minimums by tag; m2add_mutants.py runs 54 mutants,
each caught by at least 2 mapped rows (m2add_mutation_results.txt).

## 2. PO rulings encoded (extend the merged contract)
New structural codes after bad_multiplier: unknown_contract (print contract_id not in the contracts map) and malformed_type. Order: unordered_prints,
negative_size_or_price, bad_multiplier, unknown_contract, malformed_type, then the merged list (duplicate_session, non_monotone_grid, session_not_in_calendar,
window_not_allowed, threshold_required, out_of_order_append, delayed_feed_tag). Price: an integer (not bool) is integer ticks and valid; a text decimal must match
the ASCII grammar -?(digits(.digits*)? | .digits) with at most 4 decimals of value (trailing zeros accepted; a non-zero digit beyond the 4th decimal, '+1', '1e3',
spaces and non-ASCII digits are malformed_type; '.5' is valid); bool and float prices are malformed_type. Size, multiplier, time and seq must be int (bool excluded).
Float window_s is window_not_allowed. Prints before open are excluded from F4/F7/F17/F18 windows. Grid: points i = 0..minutes-1 at open + 60 s x i (AMB-4); the final
minute lies in no grid value and counts in the session total only; a print exactly at close counts in the total (closed [open, close]). M2-GRID shape ratified interim.

## 3. Ambiguities found (defect report; rows encode the interim reading)
- AMB-A1 M2-GRID shape (ratified interim): value {form dense, grid, total, valid_from = W/60} or, for a contract series (params.contract_id), {form sparse,
  sparse [[i, v]], zero_count, total, valid_from}; coverage eligible_count, nonstandard_count, excluded_condition_count over [open, close] for the lane and series.
- AMB-A3 F12 from prints: coverage counts prints in [open, T] (the merged coverage keys) and unavailable_points as before.
- AMB-A5 Interim reading used for the condition_excluded flag: 0 and 1 (int or bool) are valid, any other value is malformed_type (all merged rows use 0/1 ints).
  The contract text says bool; if ints must be rejected the merged rows would change. For the PO.
- AMB-A6 A float time equal to an integer (1.0) is malformed_type like any float.

## 4. Mutation table (54 mutants; see m2add_mutation_results.txt)
Structural: unknown_ignored, bool_price_ok, float_price_ok, over_precision_ok, trailing_zero_rejected, float_window_ok, float_size_ok, float_time_ok,
bool_multiplier_ok, grammar_lenient, int_price_as_usd, int_price_rejected, flag_any_ok, seq_bool_ok; precedence: negative_before_unordered,
multiplier_before_negative, malformed_before_unknown, window_before_malformed. Data: preopen_not_clipped, n_truncated, big_float, f12_p60_window900,
f12_cov_all, f12_start_open. Grid: g_preopen_included, g_postclose_included, g_window_open_start, g_nonstd_counted, g_cond_counted, g_lane_ignored,
g_half_day_390, g_sparse_zero_wrong.

## 6. Round 3 (PO rulings: integer ticks, grammar, store records, version)
- m2_cases_add_store.json (8): lane_mismatch (ring lane stock then etf_index record, and the reverse), record_length_mismatch (dense grid longer than the calendar
  minutes, 2 rows; sparse index outside [0, minutes), 2 rows), controls: short dense grid zero-padded and sparse inside the session are valid. Records carry an optional
  lane (default stock); store rows use the key store_ops (verbose) instead of the compact ops. The code names lane_mismatch and record_length_mismatch are taken
  from the request; precedence among them and the merged store codes is not stated (rows carry one defect).
- struct: integer ticks vs text twins for F4 and F18 (4 rows, equal results; ticks = dollars x 10^4), trailing-dot text '1.' valid (2).
- data: F18 ratio_reason omitted when the ratio is available (2 rows) and present when it is null (1); one F1 row asserting result version '0.2.0a1'
  (params.expect_version; expected.version).
- grid: valid_from beyond the grid (W = 3600 on a 12-minute session, 3 rows in total with GRID-016).
- NOT authored (blocked): from_snapshot rows (bad magic, wrong total length, SHA mismatch) and text-dump trailer rows (record count mismatch, hash mismatch):
  the snapshot and dump formats (PR 79 section 8) are not in the merged docs. Please supply the format text; the rows follow in one pass.

## 7. Round 4 (PR 81 section 9, store I/O, parameter types)
- Store (24 rows): store_ops shape, lane optional (default stock), ring lane = lane of the first append; ruled append order lane_mismatch,
  session_not_in_calendar, record_length_mismatch, non_monotone_grid, duplicate_session, out_of_order_append with 2 rows per adjacent pair (10) plus 2 extras;
  duplicate vs out_of_order cannot hold for one record (equal to the last vs earlier), so swapping those two checks is an equivalent mutant and is not listed.
  Canonical line: series_id, metric, session_id, window_s, grid, [grid_idx for sparse records only], total, complete, content_sha256 (grid as supplied, no padding).
- Snapshot (14 rows): layout of section 9.7 (magic M2SNAP1, 8-byte LE total length, SHA-256 of the body, body = canonical lines); 2 rows each for
  snapshot_bad_magic, snapshot_length_mismatch (stored length +1; truncated), snapshot_hash_mismatch (flipped body byte; zeroed hash), trailer_missing (no trailer; a
  non-END last line), trailer_count_mismatch (N+1, N-1), trailer_hash_mismatch (one hex digit; all zeros); a valid snapshot and a valid dump as controls.
- Params (16 rows): parameter-level malformed_type (N, threshold_ticks, share_threshold, at_least/at_most, quiet_gap, n_episodes as float or bool; quiet_gap and
  n_episodes below 1) and grid_not_60s (grid_s 30 and 120).
- Revisions: no merged row changes. The canonical-line change (grid_idx for sparse records) touches no valid merged store row; all 47 merged store rows are
  reproduced under the new rules (revisions/check_merged_store.py, revisions/REVISIONS_NOTE.md). The additions row STORE-006 and every sparse hash were regenerated.
- DAT-030 (version '0.2.0a1'): the oracle and the second implementation both emit expected.version when params.expect_version is set; the row is also tagged harness_checked.

## 8. Round 5 (cutoff before session open)
- m2_cases_add_cutoff.json (18): a cutoff before open gives an EMPTY window for F4, F7, F17, F18 (counts and premiums zero, coverage zero, status available; F7 and F18 with a
  zero denominator give zero_denominator; never negative). Prints lie before open and between the cutoff and open (repro: prints at open-300, -90, -80, -70, -60 s,
  cutoff open-100 s; F4 threshold_ticks=1 expects zeros). F4 4 rows, F7 3, F17 8 (a sweep of cutoffs -100, -60, -30 s, -1 ns, 0, +1 ns, +30, +60 s straddling open),
  F18 3. The contract has no sweep output of its own, so a sweep is a series of single-cutoff rows over the same prints.
- Mutants: negative_counts (in-window minus pre-open) and cutoff_unavailable, each caught by at least 2 rows; preopen_not_clipped also covers these rows.

## 5. Files read and independence
Read: docs/m2 IO contract (merged, sections 6 and 7), fixture requirements, capability matrix (as earlier) and the PO rulings in the requests. Nothing under
packages, tests, tools or any p1 or m1 generator was opened; the library under test is not imported anywhere. Scratch files stay out of the manifest.
