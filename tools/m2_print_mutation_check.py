#!/usr/bin/env python3
"""Mutation check of the M2 story B implementation (printtape, m2prints, episodes) against the independent rows.

Maps the fixture mutants of qualification/synthetic/m2/correctness/m2_mutants.py that touch the print-window
families (F1, F4, F17, F7, F18, F12, lane, structural, delayed, session open) onto one-edit changes of a scratch
copy of packages/features/src (the checkout is never modified). Each mutant must be caught: at least one test of
tests/m2/test_m2b_rows.py or test_m2b_properties.py fails, and for a fixture mutant at least one failing row
must carry one of the tags the fixture author mapped to it (a mutant caught only by an unrelated row proves
nothing about its mapped rows). Extra mutants cover the sweep, batched and coverage paths.

Usage: python tools/m2_print_mutation_check.py [--rows-only] [--out FILE]   (exit status 1 if any mutant survives)
Developer evidence only; the independent Tester must run its own mutation list. Synthetic fixtures only.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "m2"))
sys.path.insert(0, str(ROOT / "qualification" / "synthetic" / "m2" / "correctness"))
PT = "option_features/printtape.py"
MP = "option_features/m2prints.py"
EP = "option_features/episodes.py"

# (name, fixture mutant names it realises, file, [(old, new, expected occurrences)], note)
MUTS = [
    ("win_start_exclusive", ["win_open_start"], PT,
     [("a, b = bisect_left(t, start), bisect_right(t, end)", "a, b = bisect_right(t, start), bisect_right(t, end)", 1)], ""),
    ("win_end_exclusive", ["win_open_end"], PT,
     [("a, b = bisect_left(t, start), bisect_right(t, end)", "a, b = bisect_left(t, start), bisect_left(t, end)", 1)], ""),
    ("win_lookahead", ["lookahead"], PT,
     [("a, b = bisect_left(t, start), bisect_right(t, end)", "a, b = bisect_left(t, start), len(t)", 1)], ""),
    ("f1_60_start_exclusive", ["win_open_start"], PT,
     [("p60 += top - pp[bisect_left(t, s60, a9, b)]", "p60 += top - pp[bisect_right(t, s60, a9, b)]", 1)], ""),
    ("f1_900_start_exclusive", ["win_open_start"], PT,
     [("a9 = bisect_left(t, s900, 0, b)", "a9 = bisect_right(t, s900, 0, b)", 1)], ""),
    ("f1_end_exclusive", ["win_open_end"], PT,
     [("b = bisect_right(t, t_ns)\n            a9", "b = bisect_left(t, t_ns)\n            a9", 1)], ""),
    ("f1_lookahead", ["lookahead"], PT,
     [("b = bisect_right(t, t_ns)\n            a9", "b = len(t)\n            a9", 1)], ""),
    ("f1_900_for_60", ["w900_for_60"], PT,
     [("s900, s60 = t_ns - 900 * NS, t_ns - 60 * NS", "s900, s60 = t_ns - 900 * NS, t_ns - 900 * NS", 1)], ""),
    ("f1_ratio_inverted", ["ratio_inverted"], MP,
     [('"ratio": Fraction(15 * p60, p900)}', '"ratio": Fraction(p900, 15 * p60 or 1)}', 1)], ""),
    ("f1_ratio_no_factor", ["f1_factor15"], MP,
     [('"ratio": Fraction(15 * p60, p900)}', '"ratio": Fraction(p60, p900)}', 1)], ""),
    ("f1_fire_no_factor", ["f1_factor15"], MP,
     [("fired = 15 * p60 * nf.denominator >= nf.numerator * p900", "fired = p60 * nf.denominator >= nf.numerator * p900", 1)], ""),
    ("f1_fire_exclusive", [], MP,
     [("fired = 15 * p60 * nf.denominator >= nf.numerator * p900", "fired = 15 * p60 * nf.denominator > nf.numerator * p900", 1)], "N exactly"),
    ("f1_float_ratio", ["float_ratio"], MP,
     [('"ratio": Fraction(15 * p60, p900)}', '"ratio": Fraction(15 * p60 / p900)}', 1)], ""),
    ("f1_floor_100k", ["f1_floor"], MP,
     [("    if p900 == 0:\n        return result(\"M2-1\"", "    if p900 < 10 ** 9:\n        return result(\"M2-1\"", 1)], ""),
    ("f1_clip_not_unavailable", ["f2_clip"], MP,
     [("    if t_ns - open_ns < INSUFFICIENT_WINDOW_NS:\n        return result(\"M2-1\"", "    if False:\n        return result(\"M2-1\"", 1)], ""),
    ("f1_zero_before_window", ["zero_before_window"], MP,
     [("    if t_ns - open_ns < INSUFFICIENT_WINDOW_NS:\n        return result(\"M2-1\"",
       "    if t_ns - open_ns < INSUFFICIENT_WINDOW_NS and tape.f1_sums(groups, t_ns)[1] != 0:\n        return result(\"M2-1\"", 1)], ""),
    ("f1_window_before_structural", ["gate_order_swap"], MP,
     [("    if code:\n        return invalid(\"M2-1\", code, series_id, session_id, t_ns, params, lane)\n    return _f1_at",
       "    if code and t_ns - open_ns >= INSUFFICIENT_WINDOW_NS:\n        return invalid(\"M2-1\", code, series_id, session_id, t_ns, params, lane)\n    return _f1_at", 1)], "delayed row at < 900 s"),
    ("delay_ignored", ["delay_ignored"], MP, [("    if delayed:\n        return \"delayed_feed_tag\"", "    if False:\n        return \"delayed_feed_tag\"", 1)], ""),
    ("skip_window_check", ["skip_window_check"], MP, [("        elif window_s not in ALLOWED_WINDOWS:", "        elif False:", 1)], ""),
    ("f17_window_any", ["skip_window_check"], MP, [("            if window_s != fixed_window_s:", "            if False:", 1)], ""),
    ("threshold_not_required", [], MP, [("threshold_missing=al is None and am is None", "threshold_missing=False", 1)], ""),
    ("skip_unordered", ["skip_unordered"], PT, [("            if t < pt or (t == pt and seq < ps):", "            if False:", 1)], ""),
    ("unordered_seq_ties_ignored", [], PT, [("(t == pt and seq < ps)", "False", 1)], "same time, lower seq"),
    ("negative_price_allowed", [], PT, [("if size < 0 or price < 0:", "if size < 0:", 1)], ""),
    ("negative_size_allowed", [], PT, [("if size < 0 or price < 0:", "if price < 0:", 1)], ""),
    ("zero_multiplier_allowed", [], PT, [("if mult <= 0:", "if mult < 0:", 1)], ""),
    ("lane_ignored", ["lane_ignored"], PT,
     [("if ln == lane and r in rights)", "if r in rights)", 1)], ""),
    ("filter_ignored", [], PT, [("if ln == lane and r in rights)", "if ln == lane)", 1)], "calls/puts filter ignored"),
    ("excluded_counted_eligible", ["cond_excl_counted"], PT, [("        if excl:\n            rare_add((t, ci, K_EXCL))", "        if False:\n            rare_add((t, ci, K_EXCL))", 1)], ""),
    ("nonstandard_counted_eligible", ["nonstd_counted", "f7_denominator_all"], PT, [("        elif mult != 100:", "        elif False:", 1)], "also the F7 denominator mutant"),
    ("both_flags_as_nonstandard", ["both_nonstd_first"], PT,
     [("        if excl:\n            rare_add((t, ci, K_EXCL))", "        if excl and mult == 100:\n            rare_add((t, ci, K_EXCL))", 1)], ""),
    ("both_flags_counted_twice", [], PT,
     [("        if excl:\n            rare_add((t, ci, K_EXCL))", "        if excl:\n            rare_add((t, ci, K_EXCL))\n            if mult != 100:\n                rare_add((t, ci, K_NONSTD))", 1)], "AMB-14"),
    ("unknown_side_dropped", ["f4_side_known", "f18_unknown_dropped"], PT,
     [("        n += 1\n", "        n += 1\n        if len(p) > 7 and p[7] == \"unknown\":\n            continue\n", 1)], ""),
    ("nonstd_coverage_start_exclusive", [], PT,
     [("nn += bisect_right(nt, end) - bisect_left(nt, start)", "nn += bisect_right(nt, end) - bisect_right(nt, start)", 1)], ""),
    ("excl_coverage_start_exclusive", [], PT,
     [("nx += bisect_right(et, end) - bisect_left(et, start)", "nx += bisect_right(et, end) - bisect_right(et, start)", 1)], ""),
    ("f4_exclusive", ["f4_exclusive"], PT, [("idx = [i for i, v in enumerate(p) if v >= threshold]", "idx = [i for i, v in enumerate(p) if v > threshold]", 1)], ""),
    ("f4_count_exclusive", [], MP, [("count * nf.denominator >= nf.numerator", "count * nf.denominator > nf.numerator", 1)], "N exactly"),
    ("f4_large_premium_all", [], MP, [("large += lpp[b] - lpp[a]", "large += lpp[-1]", 1)], ""),
    ("f17_exclusive", ["f17_exclusive"], MP, [('{"window_premium": s}, s >= thr,', '{"window_premium": s}, s > thr,', 1)], ""),
    ("f17_tumbling", ["f17_tumbling"], MP, [("    start = t_ns - F17_WINDOW_S * NS\n    sums, cnts", "    start = t_ns - (t_ns % (F17_WINDOW_S * NS))\n    sums, cnts", 1)], ""),
    ("f17_per_name", ["f17_per_name"], MP, [("s, ne = sums.get(ci, 0), cnts.get(ci, 0)", "s, ne = sum(sums.values()), sum(cnts.values())", 1)], ""),
    ("f17_sweep_no_removal", [], MP, [("                sums[c] -= p[lo]\n", "                sums[c] -= 0\n", 1)], "sweep path"),
    ("f17_sweep_start_exclusive", [], MP, [("while lo < hi and t[lo] < start:\n                c = ci[lo]\n                sums[c] -= p[lo]", "while lo < hi and t[lo] <= start:\n                c = ci[lo]\n                sums[c] -= p[lo]", 1)], "sweep path"),
    ("f7_strike_not_summed", ["f7_strike_not_summed"], MP,
     [("    for c, p in byc.items():\n        k = c_strike[c]", "    for c, p in byc.items():\n        k = (c_strike[c], c_expiry[c])", 1)], ""),
    ("f7_expiry_not_summed", ["f7_expiry_not_summed"], MP,
     [("        k = c_expiry[c]\n        by_e[k] = by_e.get(k, 0) + p\n", "        k = (c_expiry[c], c_strike[c])\n        by_e[k] = by_e.get(k, 0) + p\n", 1)], ""),
    ("f7_tie_highest_strike", ["f7_tie_highest_strike"], MP, [("top_s = min(k for k, v in by_s.items() if v == best_s)", "top_s = max(k for k, v in by_s.items() if v == best_s)", 1)], ""),
    ("f7_tie_latest_expiry", ["f7_tie_latest_expiry"], MP, [("top_e = min(k for k, v in by_e.items() if v == best_e)", "top_e = max(k for k, v in by_e.items() if v == best_e)", 1)], ""),
    ("f7_fire_exclusive", [], MP, [("fired = best_s * th.denominator >= cut or best_e * th.denominator >= cut", "fired = best_s * th.denominator > cut or best_e * th.denominator > cut", 1)], "share exactly 3/5"),
    ("f7_fire_strike_only", [], MP, [("fired = best_s * th.denominator >= cut or best_e * th.denominator >= cut", "fired = best_s * th.denominator >= cut", 1)], ""),
    ("f7_zero_total_available", [], MP, [("    if total == 0:\n        return result(\"M2-6\"", "    if total < 0:\n        return result(\"M2-6\"", 1)], ""),
    ("f7_sweep_no_removal", [], MP, [("                by_s[c_strike[c]] -= v\n", "                by_s[c_strike[c]] -= 0\n", 1)], "sweep path"),
    ("f18_share_swapped", ["f18_swap"], MP, [('"put_share": Fraction(put, total)', '"put_share": Fraction(call, total)', 1)], ""),
    ("f18_exclusive", ["f18_exclusive"], MP,
     [("put * al.denominator >= al.numerator * total", "put * al.denominator > al.numerator * total", 1),
      ("put * am.denominator <= am.numerator * total", "put * am.denominator < am.numerator * total", 1)], ""),
    ("f18_ratio_zero_call_zero", [], MP, [('Fraction(put, call) if call else None', 'Fraction(put, call) if call else 0', 1)], ""),
    ("f18_filter_applied", [], MP, [('tape.select(lane, "puts"), tape.select(lane, "calls")', 'tape.select(lane, "puts"), tape.select(lane, "puts")', 1)], ""),
    ("f12_gap_minus1", ["f12_gap_minus1"], EP, [("if quiet >= quiet_gap:", "if quiet >= quiet_gap - 1:", 2)], ""),
    ("f12_gap_plus1", ["f12_gap_plus1"], EP, [("if quiet >= quiet_gap:", "if quiet >= quiet_gap + 1:", 2)], ""),
    ("f12_unavailable_not_quiet", ["f12_unavail_not_quiet"], EP, [("        if a is None or b is None or b <= 0:\n            if in_ep:", "        if a is None or b is None or b <= 0:\n            if False:", 1)], ""),
    ("f12_peak_latest", ["f12_peak_latest"], EP, [("a * pk_b > pk_a * b", "a * pk_b >= pk_a * b", 1)], ""),
    ("f12_lookahead", ["f12_lookahead"], EP, [("m = min(len(p60), len(p900), upto + 1)", "m = min(len(p60), len(p900))", 1)], ""),
    ("f12_clip_not_unavailable", ["f2_clip"], EP, [("    if elapsed < FIRST_AVAILABLE_INDEX * GRID_NS:", "    if False:", 2)], ""),
    ("f12_first_15_available", [], EP, [("for k in range(FIRST_AVAILABLE_INDEX, m):", "for k in range(0, m):", 1)], "points before 900 s"),
    ("f12_unavailable_points_short", [], EP, [("pk_k, upto + 1 - avail", "pk_k, m - avail", 1)], "unavailable_points count"),
    ("f12_fire_exclusive", [], EP, [("if a * c1 >= thr_num * b:", "if a * c1 > thr_num * b:", 1)], "ratio exactly N"),
    ("f12_peak_not_exact", [], EP, [("pk_a, pk_b, pk_k = a, b, k", "pk_a, pk_b, pk_k = a, b, k if pk_k is None else pk_k", 1)], "peak time sticks to the first point"),
]


def fixture_tags():
    import m2_mutants
    return {name: set(tags) for name, _desc, tags in m2_mutants.MUTANTS}


def run_tests(src_a, src_b, modules, timeout=240):
    env = dict(os.environ)
    env["M2B_SEEDS"] = "6"
    env["PYTHONPATH"] = os.pathsep.join([str(src_a), str(src_b)])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("R25_INDEPENDENT_WIRE_FIXTURES", None)
    p = subprocess.run([sys.executable, "-m", "unittest", "-v"] + modules, cwd=str(ROOT / "tests" / "m2"), env=env,
                       capture_output=True, text=True, timeout=timeout)
    bad = set(re.findall(r"^(test_\S+) \([^)]*\) \.\.\. (?:FAIL|ERROR)", p.stdout + p.stderr, re.M))
    return bad, p.returncode


def main(argv):
    rows_only = "--rows-only" in argv
    out_path = argv[argv.index("--out") + 1] if "--out" in argv else None
    import m2b_adapter as A
    tags_of = {"test_" + r["id"].replace("-", "_"): set(r["tags"]) for _f, r in A.load_rows()}
    fx = fixture_tags()
    modules = ["test_m2b_rows"]
    tmp = Path(tempfile.mkdtemp(prefix="m2b_mut_"))
    survivors, lines = [], []
    try:
        src = tmp / "features_src"
        shutil.copytree(ROOT / "packages" / "features" / "src", src)
        contracts = ROOT / "packages" / "option-contracts" / "src"
        base_bad, rc = run_tests(src, contracts, modules)
        assert not base_bad and rc == 0, "baseline must pass: %s" % sorted(base_bad)[:5]
        covered_fixture = set()
        for name, fmuts, rel, edits, note in MUTS:
            path = src / rel
            original = path.read_text(encoding="utf-8")
            text = original
            for old, new, count in edits:
                assert text.count(old) == count, "%s: target occurs %d times, expected %d: %r" % (name, text.count(old), count, old)
                text = text.replace(old, new)
            path.write_text(text, encoding="utf-8", newline="\n")
            try:
                bad, rc = run_tests(src, contracts, modules)
                mapped = set().union(*(fx[f] for f in fmuts)) if fmuts else set()
                if not rows_only and not (bad and (not mapped or any(tags_of.get(b, set()) & mapped for b in bad))):
                    bad2, rc = run_tests(src, contracts, ["test_m2b_properties"])       # rows did not decide: properties
                    bad |= {"properties:" + b for b in bad2}
            except subprocess.TimeoutExpired:
                bad, rc = {"<timeout>"}, 1
            finally:
                path.write_text(original, encoding="utf-8", newline="\n")
            row_hits = sorted(b for b in bad if b in tags_of)
            mapped = set().union(*(fx[f] for f in fmuts)) if fmuts else set()
            mapped_hit = [b for b in row_hits if tags_of[b] & mapped] if mapped else None
            ok = bool(bad) and (mapped_hit is None or bool(mapped_hit) or not mapped)
            if fmuts and mapped:
                covered_fixture.update(fmuts) if mapped_hit else None
            status = "caught" if ok else "SURVIVED"
            if not ok:
                survivors.append(name)
            line = "%-34s %-9s failing tests %3d (rows %3d%s) fixture mutants %s%s" % (
                name, status, len(bad), len(row_hits), "" if mapped_hit is None else ", mapped rows %d" % len(mapped_hit),
                ",".join(fmuts) or "-", ("  [" + note + "]") if note else "")
            lines.append(line)
            print(line, flush=True)
        summary = "mutants %d, caught %d, survived %d; fixture mutants realised and caught on mapped rows: %s" % (
            len(MUTS), len(MUTS) - len(survivors), len(survivors), ", ".join(sorted(covered_fixture)))
        summary += ("; not representable: f12_merge_sessions (the F12 API takes one session's grid and has no cross-session "
                    "state; prior_session_points is not an input, so a merge cannot exist and row M2-F12-031 pins that); "
                    "other fixture mutants (F2, F10, F19, F20, store, infrastructure) belong to story A and the Tester")
        print(summary)
        lines.append(summary)
        if out_path:
            Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
