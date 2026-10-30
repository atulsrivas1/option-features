# STATUS: M3a fixture set author2 (SYNTHETIC, not committed)

Base: origin/main ce880c8 (R-103..R-161, owner decisions 1-5). Checks: `python m3a_selfcheck.py` (295 rows, two oracles agree, structure checks OK); `python m3a_mutants.py . m3a_mutation_results.txt` (73 mutants, each caught by >= 2 rows). All rows RULED; M3A-U-016 follows R-181 (skew_points x100 at full precision, rounded once: 0.19531250). R-184 echo check: iv_form and delta_convention appear in params only, no value-key rows. No library code used.

## Row counts
| Family | File | Rows | Required |
|---|---|---|---|
| V1 | m3a_cases_V1.json | 52 | 40 |
| V3 | m3a_cases_V3.json | 80 | 40 |
| V9 | m3a_cases_V9.json | 69 | 40 |
| history | m3a_cases_history.json | 73 | 36 |
| units | m3a_cases_units.json | 21 | 20 |
| G4 | m3a_g4_histories.json (gen_m3a_g4.py) | planted history fingerprints | G4 |

Total 295 rows (minimum 176).

## Coverage per requirement (row tags)
- V1: approximate 1, bottom 3, boundary 11, cap 2, close 6, d3 1, defaults 1, delayed 2, end_of_day 2, exact_boundary 5, extreme 2, gate_order 5, incomplete_day 2, insufficient 8, intraday 1, label 1, lane 1, lane_read 1, lookahead 1, max_sessions 1, min_sessions_param 2, missing_days 4, n19 1, n20 3, n21 1, n252 10, precedence_pair 1, r47 1, r51 3, rank 8, session_not_complete 1, session_not_in_calendar 1, structural 5, tagged_decimal 1, tagged_fraction 1, threshold 1, ties 5, ties_top 1, today_excluded 1, top 11, type_first 2, upstream_reason 2, x_differs 1, x_hundred 1, x_param 1, x_zero 1, zero_range 5, zero_range_near 1
- V3: 30d_form 2, alignment 3, atm_form 21, boundary 10, cap 2, d6 1, default_form 2, defaults 1, delayed 3, exact_boundary 8, first_missing_minute 2, gate_order 3, half_day 7, half_day_current 2, incomplete_day 3, insufficient 7, lane 1, lane_read 1, last_minute_of_halfday 1, lookahead 1, lookback 1, max_sessions 1, min_sessions 1, min_sessions_param 1, minute 3, minute_first 1, minute_last 1, minute_out_of_range 5, missing_sessions 2, n19 3, n20 3, n21 1, n252 11, no_mixing 2, precedence_pair 6, r47 1, r51 1, rank 10, selector 11, short_grid 1, skipped 2, structural 23, tagged_decimal 1, tagged_fraction 1, threshold 1, ties 5, ties_top 1, today_excluded 2, top 10, type_first 8, upstream_reason 4, x_differs 1, zero_range 4
- V9: approximate 1, bottom 3, boundary 9, cap 2, close 5, convention 19, convention_mismatch 5, d3 1, default_spot 1, defaults 1, delayed 5, end_of_day 2, exact_boundary 6, extreme 2, forward 5, gate_order 2, half_even 2, incomplete_day 1, insufficient 5, intraday 1, label 1, lane 1, lane_read 1, lookahead 1, max_sessions 1, missing_days 3, n19 1, n20 1, n21 1, n252 9, negative 1, negative_values 2, negative_zero 1, precedence_pair 6, r47 1, r51 2, rank 8, round_once 4, session_not_complete 1, session_not_in_calendar 1, sign 3, solver_reason 1, spot 1, structural 12, tagged_decimal 1, tagged_fraction 1, threshold 1, ties 11, ties_top 1, today_excluded 1, top 11, type_first 5, units 4, upstream_reason 4, x_differs 1, x_zero 1, zero_range 3, zero_range_near 1
- history: arrival 2, as_of_exclusive 2, atm_form 6, basic 2, cap 2, complete_flag 3, convention 9, convention_mismatch 4, d3 1, duplicate_session 2, forward 1, half_day 5, half_day_current 1, hash 8, incomplete_day 3, insufficient 3, available 1, isolation 1, k252 1, lane 3, lane_mismatch 1, lane_read 1, layout3 1, m2_cap60 1, m2_default 1, memory 4, min_sessions_param 1, missing_days 5, n20 1, n252 2, negative_total 1, no_field 1, no_lookahead 3, no_mixing 2, no_zero_padding 1, ordering 1, out_of_order_append 2, over_budget 1, pair 1, per_series_k 2, precedence 1, precedence_pair 3, r51 2, raw 1, record_length_mismatch 2, records 1, retention 8, same_minute_column 14, scalar_baseline 29, scalar_total 1, seal 2, session_not_in_calendar 2, spot 1, store_code 9, structural 5, twin 2, type_first 1
- units: derived 4, half_even 6, integral 1, kernel 6, large 1, near_tie 1, negative 1, negative_zero 1, points_key 4, rational_form 2, reduced 1, round_once 10, stored_integer 2, ties 13, units 21, zero 1

## Rulings reflected
R-110/111/112/113/114 (last N available, gate order, lane at read insufficient_history, short grid skipped, add_series k to 252); R-123 `code`; R-129 read shape; R-132 sorted labels; R-143 key `x` and `tail`; R-151..R-154 (V3 iv_form atm/30d, default atm, echoed, atm_iv series, no mixing); R-155..R-161 (V9 delta_convention, skew25/skew25_fwd, echo, mismatch); owner decisions 4 (zero_range_history) and 5 (partial history, min 20). D17: request position 13 (delta, iv_form, convention codes), 17 (prior_not_before_cutoff then convention_mismatch), view read 5 positions with convention_mismatch last; convention_mismatch only at request/view read, never at append.

## Gaps
- Entry point: rows supply `now` and history; chain-driven composition belongs to the surface fixtures (D1).
- Not covered: V1 and V9 under delayed intraday in combination with every pair; no row for max_sessions < min_sessions (no code, D13), V3 mode close (D7), position of iv_form_not_allowed relative to delta_not_allowed (only the rows in V3-077..080 use the written order).
- coverage is never asserted (D12); no hash rows on minute grids (D10); no performance rows.
- Independent re-derivation by a second reviewer (25 percent of hand rows and all boundary rows) still to be done.

## Fix round 2
V3-068/069 series_id is the requested form's series (R-153); V3-071..075, 077..080 no longer assert series_id; H-046..H-049 and new H-075 use the 768 MiB store budget (R-79, key within_768MiB; H-048 is 400 names over budget, H-075 is 300 names within, H-049 is 5 scalar series = 129,780 records); H-023 tagged available; U-016 left unchanged and PENDING (superseded by fix round 3).

## Fix round 3
R-181 applied to M3A-U-016 (expected 0.19531250, ruling R-181, PENDING and alt_expected dropped) and both oracles (m3a_ref.py, m3a_ref2.py) and the generator; U-014/015/017 unchanged (exact). R-184: no row puts iv_form or delta_convention in value keys. Selfcheck OK (295 rows, pending 0); 73 mutants each caught by >= 2 rows.
