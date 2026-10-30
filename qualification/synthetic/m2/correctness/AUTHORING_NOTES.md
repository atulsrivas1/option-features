# M2 synthetic fixtures: authoring notes (independent Tester)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Status: authored, not run against any implementation. Every dataset carries provenance SYNTHETIC. Seed 20261029, Python 3.12 stdlib only.

## 1. Scope
570 correctness rows in 14 files m2_cases_<name>.json (family minimums met: F1 44, F2 105 (F2a-c, F2d, F2d direction, F2c rate, F2c end of day),
F4 34, F7 38, F10F20 80, F17 32, F18F19 66, F12 54, lane 8, structural 31, delayed 9, sessionopen 12, halfday 10, store 47). The original table summed to 498;
PO rulings (AMB minimums, review conditions, convention rows) raised the target to 558; the set is 570 after the contract-conformance round (MANIFEST.json has counts per file and output id).
File format: header line (provenance, label, seed, interned calendars and contracts) then one canonical JSON row per line, LF, ASCII. Compact: histories are
base-plus-override session payloads (deduplicated) and store ops are compact lists; m2_load.py restores them and verifies expansion_sha256 and ops_sha256.
Row = id, family, output_id, design_ref, ruling, tags (incl. amb-n), pending, inputs, params, expected, derivation. Times are integer ns relative to T.
Prints: [contract_id, time_rel_ns, price, size, multiplier, condition_excluded, seq, side(optional ask/bid/unknown)]. Generators gen_m2_<name>.py (seeded, LF, no
absolute paths, --out relative) share m2common.py (oracle A) and f2lib.py. m2_ref.py is the independent second implementation (exact Fractions, no shared code).
m2_selfcheck.py, m2_mutants.py, gen_m2_diff.py with m2_diff_check.py (differential), gen_m2_manifest.py (MANIFEST.json). pending: 0 PENDING-RULING, 287 RULED rows.

## 2. Closed sets
Reasons: insufficient_history, session_not_complete, insufficient_window, zero_denominator. Gate order: invalid_input, insufficient_history, session_not_complete,
insufficient_window, zero_denominator (self-check asserts: each listed reason has at least 3 rows per output that lists it, none appears elsewhere, 22 rows hold two
conditions at once). Codes: unordered_prints, negative_size_or_price, bad_multiplier, duplicate_session, non_monotone_grid, session_not_in_calendar,
window_not_allowed, delayed_feed_tag, threshold_required (AMB-6, PO), out_of_order_append (AMB-13, PO). Two rows each in the structural file and in F18/store.

## 3. PO rulings applied (all 19 ambiguities RULED as PO-M2-AMB-n; rows tagged amb-n; rows per AMB: 1:95 2:26 3:171 4:57 5:47 6:2 7:4 8:10 9:165 10:27 11:22 12:35 13:24 14:28 15:7 16:16 17:58 18:13 19:11)
Accepted as authored: 1 (F10/F20 top-level follows consumer default, per_statistic both), 2 (optional side element; vocabulary ask/bid/unknown, twin rows with and without side),
3 integer ticks (params.threshold_ticks), 4 grid point i at open + 60 s x i, 5 F12 definitions, 7 F12 before 900 s is insufficient_window, 8 store has a window key (history with a
different window gives insufficient_history), 9 label content, 10 F2c (intraday history counts divided by W/60; end of day divided by session minutes, windowless), 11 F2d fired null,
12 F19 fires at upper_share <= X/100, 15 structural precedence = matrix list, 16 definitions, 17 calendar reading, 18 window set, 19 defaults (default-omitted rows).
Changed: 6 threshold_required (no result); 13 out_of_order_append, and the equal session append is duplicate_session; 14 a print both nonstandard and excluded-condition counts once
under excluded_condition (excluded_condition_count counts every such print, the nonstandard counter only non-excluded ones). Review rulings: F12 peak is the maximum ratio over the
available points of the session to date (ties earliest) even with zero episodes; store key and canonical line carry window_s (key series_id, metric, window_s, session_id;
content_sha256 over the line without that field and without LF; dump hash over lines each followed by LF); F20 degraded sits in coverage.degraded; unavailable results carry
coverage and label only for zero_denominator; F10/F20 unavailable results carry label and per_statistic; history lane differing gives insufficient_history; N is an integer when integral.
Contract round: store line key order series_id, metric, session_id, window_s, grid, total, complete; an append earlier than the last session is out_of_order_append, equal to the last is duplicate_session (STORE-021, 046, 047, STR-031); F4 threshold only in params.threshold_ticks.
Merged contract (PR 76) applied: content_sha256 = sha256(canonical line without that field, then LF); coverage keys eligible_count, nonstandard_count, excluded_condition_count, unavailable_points (degraded); F10/F20 value.per_statistic {median, mean} with status, reason, ratio (no ratio keys elsewhere); F12 value.unavailable_points.
AMB-1 combinations: default available with other unavailable (F20 zero median), default unavailable with other available (F10 zero median), both unavailable, both available; the fourth mixed case (F10 mean zero only) cannot occur since mean zero implies median zero.
Convention row counts (tag: rows): F2c end of day divisor 6; lane mismatch 3; calendar check current session only 3; F12 peak with zero episodes 2; coverage counter keys 4; out_of_order_append vs duplicate_session 5; unavailable_points first 15 1; F2d fired null 22; gate-order pairs 26; history window mismatch 6; side twin pairs 4; defaults omitted 11.

## 4. Mutation table (67 mutants; caught = mutated result differs in status, reason, value, fired, label, coverage; at least 2 mapped rows each)
Format: mutant [mapped tag] caught mapped rows, example id. All 67 caught (m2_mutation_results.txt). Infrastructure mutants (cache, workers, batching) are for the perf Tester.
| mutant | mutant |
|---|---|
| win_open_start [win_open_start] 7, M2-F1-011 | win_open_end [win_open_end] 5, M2-F1-013 |
| w900_for_60 [w900_for_60] 2, M2-F1-010 | ratio_inverted [ratio_inverted] 2, M2-F1-001 |
| lookahead [lookahead] 6, M2-F1-014 | f1_factor15 [f1_factor15] 3, M2-F1-001 |
| f1_floor [overlap] 2, M2-F1-009 | both_nonstd_first [both_excl] 5, M2-F1-037 |
| f2c_eod_raw_count [f2c_eod_raw_count] 2, M2-F2-095 | cond_excl_counted [cond_excl_counted] 14, M2-F1-018 |
| nonstd_counted [nonstd_counted] 15, M2-F1-017 | float_ratio [float_ratio] 11, M2-F1-002 |
| mean_as_median [mean_as_median] 4, M2-F10-004 | median_lower_middle [even_median] 6, M2-F10-006 |
| median_upper_middle [even_median] 6, M2-F10-006 | mean_instead_of_median [contrast] 6, M2-F10-004 |
| zero_stat_available [zero_stat] 8, M2-F10-009 | today_included [today_excluded] 4, M2-F10-016 |
| rank_strict_gt [rank_strict_gt] 16, M2-F19-002 | rank_le_as_upper [rank_le_as_upper] 2, M2-F2-019 |
| ties_as_below [upper_share_boundary] 38, M2-F19-002 | accept_19 [history_count] 7, M2-F10-014 |
| incomplete_counted [incomplete_session] 4, M2-F10-015 | missing_substituted [missing_calendar_session] 2, M2-F2-030 |
| zscore_instead [zscore_absent] 2, M2-F19-006 | fires_exclusive [fires_exclusive] 12, M2-F19-002 |
| f2_no_drop [drop_pre_open] 13, M2-F2-001 | f2_clip [insufficient_window] 18, M2-F1-025 |
| f4_exclusive [f4_inclusive] 2, M2-F4-001 | f4_side_known [f4_side] 4, M2-F4-007 |
| f17_exclusive [f17_inclusive] 13, M2-F17-001 | f17_tumbling [f17_tumbling] 3, M2-F17-015 |
| f17_per_name [f17_per_name] 4, M2-F17-009 | f7_strike_not_summed [f7_strike_sum] 8, M2-F7-001 |
| f7_expiry_not_summed [f7_expiry_sum] 5, M2-F7-006 | f7_tie_highest_strike [f7_tie_strike] 4, M2-F7-009 |
| f7_tie_latest_expiry [f7_tie_expiry] 2, M2-F7-010 | f7_denominator_all [f7_denominator] 3, M2-F7-014 |
| f18_swap [f18_swap] 5, M2-F18-001 | f18_unknown_dropped [f18_unknown] 3, M2-F18-006 |
| f18_exclusive [f18_inclusive] 6, M2-F18-006 | f19_zero_counted [f19_zero_counted] 2, M2-F19-011 |
| f12_gap_minus1 [f12_gap] 4, M2-F12-009 | f12_gap_plus1 [f12_gap] 5, M2-F12-003 |
| f12_unavail_not_quiet [f12_unavail] 4, M2-F12-016 | f12_merge_sessions [f12_merge_sessions] 2, M2-F12-031 |
| f12_peak_latest [f12_peak] 3, M2-F12-024 | f12_lookahead [f12_lookahead] 3, M2-F12-027 |
| store_k_plus_1 [store_k_plus_1] 5, M2-STORE-004 | store_no_sort [store_sort] 4, M2-STORE-010 |
| store_arrival_hash [store_arrival_hash] 5, M2-STORE-010 | store_view_current [store_view_current] 5, M2-STORE-014 |
| half_day_390 [half_day_390] 6, M2-HALF-001 | delay_ignored [delay_ignored] 7, M2-DLY-001 |
| gate_order_swap [gate_order] 6, M2-F10-026 | f2_window_first [gate_order] 4, M2-F2-050 |
| f10_window_first [gate_order] 2, M2-F10-026 | snc_first [gate_order] 6, M2-F20-015 |
| zero_before_window [gate_order] 3, M2-F1-026 | lane_ignored [lane_mixed] 6, M2-LANE-001 |
| f2d_pct_upper [pct_is_upper_share] 5, M2-F2-073 | f2d_partial [partial_average] 4, M2-F2-065 |
| f2c_per_second [f2c_rate] 7, M2-F2-081 | f20_median_default [f20] 34, M2-F20-001 |
| f10_mean_default [f10] 44, M2-F10-001 | skip_unordered [unordered_prints] 3, M2-STR-001 |
| skip_window_check [window_not_allowed] 5, M2-F10-022 |  |

## 5. Differential set, files read, independence, open points
Differential: gen_m2_diff.py makes 20,000 randomized cases each for percentile rank (rank_le, upper_share), median and mean ratio, and episode detection at run time;
only the generator and m2_diff_manifest.json (sha256 per kind) are committed; m2_diff_check.py (own algorithms) recomputes all 60,000 with 0 differences.
Read: docs/m2 IO contract, fixture requirements, capability matrix, RELEASE_NOTE_TEMPLATE (label rules). Not opened: GATE_BUDGETS, FLOW_NAMING_MAP, flow.md, option-contracts.md, audit,
PO plan, DESIGN_SESSION_REQUESTS, and the PR 76 document (git is outside this brief; the convention list was taken from the PO message, so the exact PR 76 convention list is unchecked).
Nothing under packages, tests, tools, or any p1 or m1 generator was opened; no implementation or developer note was read; the library under test is not imported anywhere.
Deviation: committed size is about 0.8 MB (target about 0.5 MB): expected, derivation and per-row session/print data dominate. Scratch files are not in MANIFEST.sha256.
Verification: generators run twice into two temp dirs gave identical sha256 for all 14 files; self-check 570 of 570 rows, 0 mismatches; 67 of 67 mutants caught.
