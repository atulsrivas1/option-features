"""Mutation run: each mutant changes one rule of the second implementation (m3a_ref2); it must be caught (any asserted key
of the authored expected differs: status, reason, code, value, fired, params, labels) by at least 2 rows.
Usage: python m3a_mutants.py [datadir] [results_file]"""
import os
import sys

import m3a_selfcheck as S

MUTANTS = [
    ("rank_strict_gt", "upper_share counts strictly greater (ties dropped)"),
    ("fires_exclusive", "top X percent exclusive (< instead of <=)"),
    ("ties_split", "ties split half above, half below"),
    ("mean_rank", "mean-style rank (ge + n - le) / 2n"),
    ("accept_19", "19 sessions accepted (min_sessions - 1)"),
    ("incomplete_counted", "incomplete stored session counted"),
    ("missing_zero_padded", "missing days zero-padded into the baseline"),
    ("today_included", "today's stored record included"),
    ("lookahead_included", "records after the session included"),
    ("zero_range_skipped", "zero range history computed as a percentile"),
    ("zero_range_with_x", "zero range judged over history plus x"),
    ("retention_60", "ring retention 60 instead of 252"),
    ("cap_ignored", "max_sessions not applied"),
    ("cap_oldest", "max_sessions keeps the oldest sessions"),
    ("round_half_up", "half up instead of half to even"),
    ("round_trunc", "truncation instead of rounding"),
    ("round_parts_first", "skew parts rounded before subtracting"),
    ("bottom_uses_upper", "bottom X fires on upper_share"),
    ("top_uses_lower", "top X fires on lower_share"),
    ("delayed_ignored", "delayed tag not rejected on intraday forms"),
    ("delayed_close_rejected", "close forms rejected under a delayed tag"),
    ("complete_ignored", "session_not_complete not raised in close mode"),
    ("order_complete_first", "gate order: session_not_complete before insufficient_history"),
    ("upstream_last", "gate order: upstream reason after history reasons"),
    ("minute_off_by_one", "V3 and column read minute m+1"),
    ("minute_substituted", "a session lacking the minute substituted by its last minute"),
    ("halfday_zero", "a session lacking the minute counted as 0"),
    ("minute_range_inclusive", "minute equal to the grid length accepted"),
    ("negative_minute_ok", "negative minute accepted"),
    ("x_range_exclusive", "X = 0 and X = 100 rejected"),
    ("x_float_ok", "float X accepted"),
    ("x_decimal_ok", "Decimal X accepted"),
    ("min_default_10", "default min_sessions 10"),
    ("x_default_10", "default X 10"),
    ("negative_zero_text", "zero shown as -0.00000000"),
    ("share_unreduced", "shares not reduced"),
    ("integral_as_fraction", "integral shares shown as 1/1"),
    ("lane_ignored", "ring lane not compared with the request lane"),
    ("labels_no_delayed", "delayed label dropped"),
    ("min_sessions_zero_ok", "min_sessions 0 accepted"),
    ("x_before_sessions", "X checked before min_sessions and max_sessions"),
    ("form_swapped", "form label swapped"),
    ("iv_form_default_30d", "default iv_form 30d instead of atm"),
    ("iv_form_type_ok", "non-string iv_form accepted"),
    ("iv_form_invalid_ok", "unknown iv_form accepted"),
    ("form_mix_allowed", "series of the other IV form read"),
    ("iv_form_not_echoed", "iv_form missing from the params echo"),
    ("conv_default_forward", "default delta_convention forward"),
    ("conv_type_ok", "non-string delta_convention accepted"),
    ("conv_invalid_ok", "unknown delta_convention accepted"),
    ("conv_mismatch_ignored", "V9 ignores a stored convention of the other kind"),
    ("conv_not_echoed", "delta_convention missing from the echo"),
    ("conv_unchecked_at_read", "store read does not check the convention"),
    ("missing_conv_as_forward", "a record without a convention field read as forward"),
    ("selector_first", "iv_form and delta_convention checked before min_sessions and max_sessions"),
    ("mismatch_after_delayed", "convention_mismatch checked after delayed_feed_tag"),
    ("conv_before_threshold", "store read checks the convention before X"),
    ("store_x_unchecked", "store read does not range-check X"),
    ("retention_253", "store retention 253"),
    ("arrival_hashed", "arrival order in the hashed line"),
    ("complete_not_hashed", "complete flag always true in the line"),
    ("lane_unchecked", "lane_mismatch not raised"),
    ("oop_ignored", "out_of_order_append accepted"),
    ("dup_allowed", "duplicate_session accepted"),
    ("seal_ignored", "seal does not complete a record"),
    ("as_of_inclusive", "baseline includes as_of"),
    ("per_series_k_ignored", "per-series k ignored (default k used)"),
    ("dump_unsorted", "dump lines in arrival order of series"),
    ("calendar_unchecked", "session_not_in_calendar not raised"),
    ("length_unchecked", "record_length_mismatch not raised"),
    ("mem_copies_2", "memory formula with 2 copies"),
    ("mem_4_bytes", "memory formula with 4 bytes per value"),
    ("points_x1000", "points key scaled by 1000"),
]


def run(d, out=None):
    lines, bad = [], 0
    for name, desc in MUTANTS:
        n, fails = S.check(d, mut=name)
        ids = [f[0] for f in fails]
        ok = len(ids) >= 2
        bad += 0 if ok else 1
        lines.append("%s | %s | caught by %d rows%s | %s" % (name, desc, len(ids), "" if ok else " NOT ENOUGH", ",".join(ids[:4])))
    lines.append("mutants %d, caught by >= 2 rows: %d" % (len(MUTANTS), len(MUTANTS) - bad))
    text = "\n".join(lines) + "\n"
    if out:
        with open(out, "w", newline="\n") as f:
            f.write(text)
    return bad, text


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    out = sys.argv[2] if len(sys.argv) > 2 else None
    bad, text = run(d, out)
    print(text)
    sys.exit(1 if bad else 0)
