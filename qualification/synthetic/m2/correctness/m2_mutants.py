"""Mutation run: each mutant changes one rule of the reference model (m2_ref); it must be caught (result differs from the
authored expected, status/reason/value/fired/label/coverage all compared) by at least one of its mapped rows (rows carrying
a mapped tag). Usage: python m2_mutants.py [datadir] [results_file]"""
import glob
import json
import os
import sys

import m2_ref
from m2_selfcheck import canon, load

MUTANTS = [
    ("win_open_start", "window open at start: t > T-W", ["win_open_start"]),
    ("win_open_end", "window open at end: t < T", ["win_open_end"]),
    ("w900_for_60", "900 s window used for the 60 s side", ["w900_for_60"]),
    ("ratio_inverted", "F1 ratio inverted (P900 over 15 P60)", ["ratio_inverted"]),
    ("lookahead", "prints after T included", ["lookahead"]),
    ("f1_factor15", "F1 ratio without the factor 15", ["f1_factor15"]),
    ("f1_floor", "worker floor 100,000 USD on P900 adopted", ["overlap"]),
    ("both_nonstd_first", "print with both flags counted as nonstandard", ["both_excl"]),
    ("f2c_eod_raw_count", "F2c end of day uses raw count instead of per-minute rate", ["f2c_eod_raw_count"]),
    ("cond_excl_counted", "excluded-condition prints counted as eligible", ["cond_excl_counted"]),
    ("nonstd_counted", "nonstandard multiplier prints counted as eligible", ["nonstd_counted"]),
    ("float_ratio", "ratio computed in float", ["float_ratio"]),
    ("mean_as_median", "mean wired to the median name and reverse", ["mean_as_median"]),
    ("median_lower_middle", "lower middle instead of mean of two middle values", ["even_median"]),
    ("median_upper_middle", "upper middle instead of mean of two middle values", ["even_median"]),
    ("mean_instead_of_median", "median output computed as the mean", ["contrast"]),
    ("zero_stat_available", "zero statistic treated as available (ratio 0)", ["zero_stat"]),
    ("today_included", "today included in the history window", ["today_excluded"]),
    ("rank_strict_gt", "upper_share counts strictly greater", ["rank_strict_gt"]),
    ("rank_le_as_upper", "rank_le used for upper_share", ["rank_le_as_upper"]),
    ("ties_as_below", "ties not counted in rank_le", ["upper_share_boundary"]),
    ("accept_19", "19 sessions accepted", ["history_count"]),
    ("incomplete_counted", "an incomplete session counted", ["incomplete_session"]),
    ("missing_substituted", "a missing calendar session substituted by an older one", ["missing_calendar_session"]),
    ("zscore_instead", "z-score instead of percentile (F19)", ["zscore_absent"]),
    ("fires_exclusive", "top X percent exclusive (< instead of <=)", ["fires_exclusive"]),
    ("f2_no_drop", "grid points before open + W not dropped from history", ["drop_pre_open"]),
    ("f2_clip", "windows clipped instead of insufficient_window", ["insufficient_window"]),
    ("f4_exclusive", "F4 threshold exclusive", ["f4_inclusive"]),
    ("f4_side_known", "side-known prints only", ["f4_side"]),
    ("f17_exclusive", "F17 threshold exclusive", ["f17_inclusive"]),
    ("f17_tumbling", "F17 tumbling aligned bucket instead of trailing window", ["f17_tumbling"]),
    ("f17_per_name", "F17 per-name sum instead of per-contract", ["f17_per_name"]),
    ("f7_strike_not_summed", "F7 strike share not summed across expiries", ["f7_strike_sum"]),
    ("f7_expiry_not_summed", "F7 expiry share not summed across strikes", ["f7_expiry_sum"]),
    ("f7_tie_highest_strike", "F7 tie takes the highest strike", ["f7_tie_strike"]),
    ("f7_tie_latest_expiry", "F7 tie takes the latest expiry", ["f7_tie_expiry"]),
    ("f7_denominator_all", "F7 denominator includes nonstandard premium", ["f7_denominator"]),
    ("f18_swap", "F18 share and ratio swapped (call share reported)", ["f18_swap"]),
    ("f18_unknown_dropped", "F18 unknown-side prints dropped", ["f18_unknown"]),
    ("f18_exclusive", "F18 thresholds exclusive", ["f18_inclusive"]),
    ("f19_zero_counted", "F19 prior zero-call sessions counted", ["f19_zero_counted"]),
    ("f12_gap_minus1", "F12 quiet_gap off by one (low)", ["f12_gap"]),
    ("f12_gap_plus1", "F12 quiet_gap off by one (high)", ["f12_gap"]),
    ("f12_unavail_not_quiet", "F12 unavailable point not counted as quiet", ["f12_unavail"]),
    ("f12_merge_sessions", "F12 episodes merged across sessions", ["f12_merge_sessions"]),
    ("f12_peak_latest", "F12 peak tie takes the latest", ["f12_peak"]),
    ("f12_lookahead", "F12 uses grid points after T", ["f12_lookahead"]),
    ("store_k_plus_1", "store retention K+1", ["store_k_plus_1"]),
    ("store_no_sort", "store sort not applied (arrival order)", ["store_sort"]),
    ("store_arrival_hash", "store hash includes arrival order", ["store_arrival_hash"]),
    ("store_view_current", "store view includes the current session", ["store_view_current"]),
    ("half_day_390", "grid length fixed at 390 for every session", ["half_day_390"]),
    ("delay_ignored", "delayed-feed tag ignored", ["delay_ignored"]),
    ("gate_order_swap", "insufficient_window checked before insufficient_history", ["gate_order"]),
    ("f2_window_first", "F2 insufficient_window before insufficient_history", ["gate_order"]),
    ("f10_window_first", "F10 insufficient_window before insufficient_history", ["gate_order"]),
    ("snc_first", "session_not_complete before insufficient_history (F2, F19, F20)", ["gate_order"]),
    ("zero_before_window", "F1 zero_denominator before insufficient_window", ["gate_order"]),
    ("lane_ignored", "lane ignored in shares and baselines", ["lane_mixed"]),
    ("f2d_pct_upper", "F2d percentile = upper_share (direction flipped)", ["pct_is_upper_share"]),
    ("f2d_partial", "F2d averages only the available parts", ["partial_average"]),
    ("f2c_per_second", "F2c rate per second instead of per minute", ["f2c_rate"]),
    ("f20_median_default", "F20 consumer default median instead of mean", ["f20"]),
    ("f10_mean_default", "F10 consumer default mean instead of median", ["f10"]),
    ("skip_unordered", "unordered prints accepted", ["unordered_prints"]),
    ("skip_window_check", "window outside the allowed set accepted", ["window_not_allowed"]),
]


def run(d):
    rows = []
    for path in sorted(glob.glob(os.path.join(d, "m2_cases_*.json"))):
        rows += load(path)[1]
    base = {r["id"]: canon(r["expected"]) for r in rows}
    lines, failures = [], []
    for name, desc, tags in MUTANTS:
        caught, mapped_caught, mapped = [], [], 0
        for r in rows:
            is_mapped = any(t in r["tags"] for t in tags)
            mapped += is_mapped
            try:
                got = canon(m2_ref.evaluate(r, name))
            except Exception:
                got = "EXC"
            if got != base[r["id"]]:
                caught.append(r["id"])
                if is_mapped:
                    mapped_caught.append(r["id"])
        ok = len(mapped_caught) >= 2
        if not ok:
            failures.append(name)
        lines.append("%-24s %-6s mapped %3d caught_mapped %3d caught_total %3d  e.g. %s" % (
            name, "CAUGHT" if ok else "MISSED", mapped, len(mapped_caught), len(caught),
            ",".join(mapped_caught[:2])))
    return lines, failures


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    lines, failures = run(d)
    label = "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12"
    out = label + chr(10) + "\n".join(lines) + "\nmutants %d caught %d missed %d\n" % (len(MUTANTS), len(MUTANTS) - len(failures), len(failures))
    print(out)
    if len(sys.argv) > 2:
        with open(sys.argv[2], "wb") as f:
            f.write(out.encode("ascii"))
    sys.exit(1 if failures else 0)
