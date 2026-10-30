"""Mutation run for the additions: each mutant changes one rule of m2add_ref; it must be caught by at least 2 mapped rows."""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import m2_load  # noqa: E402
import m2add_ref  # noqa: E402
from m2add_selfcheck import canon  # noqa: E402

MUTANTS = [
    ("unknown_ignored", "unknown contract not rejected", ["unknown_contract"]),
    ("bool_price_ok", "bool price accepted", ["bool_price"]),
    ("float_price_ok", "float price accepted", ["float_price"]),
    ("over_precision_ok", "digit beyond the 4th decimal accepted", ["over_precision", "malformed_type"]),
    ("trailing_zero_rejected", "trailing zeros in a text price rejected", ["trailing_zero_price"]),
    ("float_window_ok", "float window_s accepted", ["float_window"]),
    ("float_size_ok", "non-int size accepted", ["float_size", "malformed_type"]),
    ("float_time_ok", "non-int time accepted", ["float_time", "malformed_type"]),
    ("bool_multiplier_ok", "bool multiplier accepted", ["bool_multiplier", "malformed_type"]),
    ("negative_before_unordered", "negative checked before unordered", ["prec_pair"]),
    ("multiplier_before_negative", "bad_multiplier checked before negative", ["prec_pair"]),
    ("malformed_before_unknown", "malformed_type checked before unknown_contract", ["prec_pair"]),
    ("window_before_malformed", "window_not_allowed checked before malformed_type", ["prec_pair"]),
    ("preopen_not_clipped", "prints before open counted in F4/F7/F17/F18", ["preopen_clip"]),
    ("n_truncated", "fractional N truncated to an integer", ["fractional_N"]),
    ("big_float", "premium above 2^53 computed in float", ["premium_gt_2_53"]),
    ("f12_p60_window900", "F12 from prints: 60 s side uses 900 s", ["f12_from_prints"]),
    ("f12_cov_all", "F12 coverage counts prints outside [open, T]", ["coverage_from_prints"]),
    ("f12_start_open", "F12 from prints: window open at start", ["f12_from_prints"]),
    ("g_preopen_included", "grid: prints before open included", ["grid_builder"]),
    ("g_postclose_included", "grid: prints after close included", ["grid_builder"]),
    ("g_window_open_start", "grid: window open at start", ["grid_builder"]),
    ("g_nonstd_counted", "grid: nonstandard prints counted", ["grid_builder"]),
    ("g_cond_counted", "grid: excluded-condition prints counted", ["grid_builder"]),
    ("g_lane_ignored", "grid: lane ignored", ["grid_builder"]),
    ("g_half_day_390", "grid: length fixed at 390", ["grid_builder"]),
    ("grammar_lenient", "decimal grammar not enforced (+1, 1e3, spaces, non-ASCII digits)", ["grammar_text"]),
    ("int_price_as_usd", "integer price read as USD instead of ticks", ["int_tick_price"]),
    ("int_price_rejected", "integer price rejected", ["int_tick_price"]),
    ("flag_any_ok", "any condition_excluded value accepted", ["flag_int"]),
    ("seq_bool_ok", "bool seq accepted", ["bool_seq"]),
    ("trailing_dot_rejected", "text price with a trailing dot rejected", ["dot_trailing"]),
    ("ratio_reason_null_present", "F18 ratio_reason key present as null when the ratio is available", ["ratio_reason_absent"]),
    ("store_lane_ignored", "store accepts a record whose lane differs from the ring lane", ["lane_mismatch"]),
    ("store_length_ignored", "store accepts a dense grid longer than the session", ["dense_too_long"]),
    ("store_sparse_range_ignored", "store accepts a sparse index outside the session", ["sparse_outside"]),
    ("g_valid_from_clipped", "grid valid_from clipped to the session length", ["valid_from_beyond"]),
    ("snap_magic_ignored", "snapshot magic not checked", ["snapshot_bad_magic"]),
    ("snap_length_ignored", "snapshot length not checked", ["snapshot_length_mismatch"]),
    ("snap_hash_ignored", "snapshot body hash not checked", ["snapshot_hash_mismatch"]),
    ("trailer_ignored", "missing trailer not rejected", ["trailer_missing"]),
    ("trailer_count_ignored", "trailer record count not checked", ["trailer_count_mismatch"]),
    ("trailer_hash_ignored", "trailer hash not checked", ["trailer_hash_mismatch"]),
    ("store_grid_idx_dropped", "canonical line without grid_idx", ["sparse_hash"]),
    ("store_hash_no_lf", "record hash without the LF", ["store", "snapshot_control"]),
    ("prec_calendar_first", "store order: calendar before lane", ["prec_pair_store"]),
    ("prec_length_after_mono", "store order: non_monotone before length", ["prec_pair_store"]),
    ("prec_dup_before_mono", "store order: duplicate before non_monotone", ["prec_pair_store"]),
    ("param_types_ignored", "parameter types not checked", ["param_malformed"]),
    ("grid_60_ignored", "grid step not checked", ["grid_not_60s"]),
    ("param_below_one_ok", "quiet_gap and n_episodes below 1 accepted", ["param_below_one"]),
    ("g_sparse_zero_wrong", "grid: sparse zero_count off by one", ["contract_series"]),
]


def run(d):
    rows = []
    for path in sorted(glob.glob(os.path.join(d, "m2_cases_add_*.json"))):
        rows += m2_load.load_dataset(path)[1]
    base = {r["id"]: canon(r["expected"]) for r in rows}
    lines, fail = [], []
    for name, desc, tags in MUTANTS:
        mapped = [r for r in rows if any(t in r["tags"] for t in tags)]
        caught = []
        for r in mapped:
            try:
                got = canon(m2add_ref.evaluate(r, name))
            except Exception:
                got = "EXC"
            if got != base[r["id"]]:
                caught.append(r["id"])
        ok = len(caught) >= 2
        if not ok:
            fail.append(name)
        lines.append("%-26s %-6s mapped %3d caught_mapped %3d  e.g. %s" % (name, "CAUGHT" if ok else "MISSED", len(mapped), len(caught), ",".join(caught[:2])))
    return lines, fail


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else HERE
    lines, fail = run(d)
    label = "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12"
    out = label + chr(10) + chr(10).join(lines) + chr(10) + "mutants %d caught %d missed %d" % (len(MUTANTS), len(MUTANTS) - len(fail), len(fail)) + chr(10)
    print(out)
    if len(sys.argv) > 2:
        open(sys.argv[2], "wb").write(out.encode("ascii"))
    sys.exit(1 if fail else 0)
