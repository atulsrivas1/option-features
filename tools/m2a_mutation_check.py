#!/usr/bin/env python3
"""Mutation check of the M2 story A implementation (store, grid builder, F2, F2d, F10, F20, F19).

Each mutant is a text change applied to a scratch copy of packages/features/src (the checkout is never modified).
Tier 1 runs the independently authored rows (tests/m2/test_m2_rows.py, 302 owned rows); a mutant that no row catches
is run through tier 2, the Developer property tests (tests/m2/test_m2_properties.py), and reported as such. The
first group maps the Tester's mutants (qualification/synthetic/m2/correctness/m2_mutants.py, AUTHORING_NOTES.md
section 4) for the families this story owns onto this implementation; the second group adds infrastructure mutants
(cache, batching, fusing) that the Tester lists for the performance rows. Mutants of story B families (F1, F4, F7,
F12, F17, F18) are not mapped here.
Usage: python tools/m2a_mutation_check.py [name-substring]     (exit status 1 if any mutant survives both tiers)
Developer evidence only; the independent Tester must run its own mutation list. Label: synthetic fixtures only.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
RK, ST, GR = "option_features/flowrank.py", "option_features/flowstore.py", "option_features/flowgrid.py"
RN = "option_features/flowresult.py"
# Mutants with no observable effect (reported, not counted as survivors).
EQUIVALENT = {"cache_not_cleared_on_seal": "a seal only completes an incomplete record, and a view is never built over an "
                                           "incomplete record (a missing baseline is not cached), so no cached view can be stale"}

WIN_FIRST_F2 = ('    view = store.baseline(series_id, metric, window_s, sid, K, lane)\n    if view is None or (intraday and view.n == 0):',
                '    if intraday and evaluation_ns - session.open_ns < window_s * NS:\n'
                '        return Result.unavailable("M2-2", series_id, sid, evaluation_ns, "insufficient_window", params, lane=lane)\n'
                '    view = store.baseline(series_id, metric, window_s, sid, K, lane)\n    if view is None or (intraday and view.n == 0):')
WIN_FIRST_F10 = ('    view = store.baseline(series_id, _F10_METRIC, window_s, sid, K, lane)\n    if view is None or view.n == 0:',
                 '    if evaluation_ns - session.open_ns < window_s * NS:\n'
                 '        return _na_stats("M2-7", series_id, sid, evaluation_ns, "insufficient_window", params, consumer_default, lane)\n'
                 '    view = store.baseline(series_id, _F10_METRIC, window_s, sid, K, lane)\n    if view is None or view.n == 0:')
SNC_F2 = ('    view = store.baseline(series_id, metric, window_s, sid, K, lane)\n    if view is None or (intraday and view.n == 0):',
          '    if not intraday and not session.complete:\n'
          '        return Result.unavailable("M2-2", series_id, sid, evaluation_ns, "session_not_complete", params, lane=lane)\n'
          '    view = store.baseline(series_id, metric, window_s, sid, K, lane)\n    if view is None or (intraday and view.n == 0):')
SNC_F20 = ('    view = store.baseline(series_id, metric, window_s, sid, K, lane)\n    if view is None:\n        return _na_stats("M2-8"',
           '    if not session.complete:\n'
           '        return _na_stats("M2-8", series_id, sid, evaluation_ns, "session_not_complete", params, consumer_default, lane)\n'
           '    view = store.baseline(series_id, metric, window_s, sid, K, lane)\n    if view is None:\n        return _na_stats("M2-8"')
SNC_F19 = ('    pv = store.baseline(series_id, "put_volume", window_s, sid, K, lane)\n',
           '    if not session.complete:\n'
           '        return Result.unavailable("M2-10", series_id, sid, evaluation_ns, "session_not_complete", params, lane=lane)\n'
           '    pv = store.baseline(series_id, "put_volume", window_s, sid, K, lane)\n')
SUBST = ('        for sid in cal.ids[pos - k:pos]:\n            r = recs.get(sid)\n            if r is None or not r.complete:\n                return None\n            got.append(r)\n',
         '        got = [r for s, r in recs.items() if r.complete and s < as_of][-k:]\n        if len(got) < k:\n            return None\n')
NONSTD_FIRST = ('        if p[5]:\n            excl += 1\n            continue\n        mult = p[4]\n        if mult != STANDARD_MULTIPLIER:\n            nonstd += 1\n            continue\n        size = p[3]\n        prem += price_ticks(p[2]) * size * mult\n        vol += size',
                '        mult = p[4]\n        if mult != STANDARD_MULTIPLIER:\n            nonstd += 1\n            continue\n        if p[5]:\n            excl += 1\n            continue\n        size = p[3]\n        prem += price_ticks(p[2]) * size * mult\n        vol += size')

# (name, tester mutant it maps, [(file, old, new)])
MUTS = [
    ("f2c_eod_raw_count", "f2c_eod_raw_count", [(RK, '        if metric == "prints":\n            mx = session.minutes', '        if False:\n            mx = session.minutes')]),
    ("mean_as_median", "mean_as_median", [(RK, '(("median", med), ("mean", mean))', '(("median", mean), ("mean", med))')]),
    ("median_lower_middle", "median_lower_middle", [(ST, "Fraction(self._kth(h - 1) + self._kth(h), 2)", "Fraction(self._kth(h - 1))"),
                                                    (RK, "Fraction(srt[h - 1] + srt[h], 2)", "Fraction(srt[h - 1])")]),
    ("median_upper_middle", "median_upper_middle", [(ST, "Fraction(self._kth(h - 1) + self._kth(h), 2)", "Fraction(self._kth(h))"),
                                                    (RK, "Fraction(srt[h - 1] + srt[h], 2)", "Fraction(srt[h])")]),
    ("mean_instead_of_median", "mean_instead_of_median", [(RK, "x, view.median(), view.mean(), N, consumer_default,", "x, view.mean(), view.mean(), N, consumer_default,"),
                                                           (RK, "    med = Fraction(srt[h]) if n % 2 else Fraction(srt[h - 1] + srt[h], 2)\n    mean = Fraction(sum(srt), n)\n",
                                                            "    mean = Fraction(sum(srt), n)\n    med = mean\n")]),
    ("zero_stat_available", "zero_stat_available", [(RK, '        if st == 0:\n            per[name]', '        if False:\n            per[name]'),
                                                    (RK, "r = Fraction(x) / st\n", "r = Fraction(x) / st if st else Fraction(0)\n")]),
    ("today_included", "today_included", [(ST, "cal.ids[pos - k:pos]:", "cal.ids[pos - k + 1:pos + 1]:"),
                                          (ST, "cal.minutes[pos - k:pos])", "cal.minutes[pos - k + 1:pos + 1])")]),
    ("rank_strict_gt", "rank_strict_gt", [(ST, "ge = self.n - (bisect_left(m, hi_x) + (z if hi_x > 0 else 0))", "ge = self.n - (bisect_right(m, hi_x) + (z if hi_x >= 0 else 0))"),
                                          (RK, "ge = n - bisect_left(srt, total)", "ge = n - bisect_right(srt, total)"),
                                          (RK, "                if lhs >= rhs:\n", "                if lhs > rhs:\n"),
                                          (RK, "        if rhs >= lhs:\n            ge += 1", "        if rhs > lhs:\n            ge += 1")]),
    ("rank_le_as_upper", "rank_le_as_upper", [(RK, '"upper_share": Fraction(ge, n), "form": form', '"upper_share": Fraction(le, n), "form": form'),
                                              (RK, "_fires(ge, n, X), params, coverage, label, lane)", "_fires(le, n, X), params, coverage, label, lane)")]),
    ("ties_as_below", "ties_as_below", [(ST, "le = bisect_right(m, lo_x) + (z if lo_x >= 0 else 0)", "le = bisect_left(m, lo_x) + (z if lo_x > 0 else 0)"),
                                        (RK, "le = bisect_right(srt, total)", "le = bisect_left(srt, total)"),
                                        (RK, "                if lhs <= rhs:\n", "                if lhs < rhs:\n"),
                                        (RK, "        if rhs <= lhs:\n            le += 1", "        if rhs < lhs:\n            le += 1")]),
    ("accept_19", "accept_19", [(ST, "        k = k or self.k\n        key = (as_of, k)", "        k = (k or self.k) - 1\n        key = (as_of, k)")]),
    ("incomplete_counted", "incomplete_counted", [(ST, "            if r is None or not r.complete:\n                return None\n            got.append(r)", "            if r is None:\n                return None\n            got.append(r)")]),
    ("missing_substituted", "missing_substituted", [(ST, "if pos is None or pos < k:\n            return None", "if pos is None:\n            return None"), (ST, *SUBST),
                                                   (ST, "cal.minutes[pos - k:pos])", "[r.minutes for r in got])")]),
    ("zscore_instead", "zscore_instead", [(RK, '"rank_le": Fraction(le, n), "upper_share": Fraction(ge, n)}\n    return Result.available("M2-10"', '"rank_le": Fraction(le, n), "upper_share": Fraction(le - ge, n)}\n    return Result.available("M2-10"')]),
    ("fires_exclusive", "fires_exclusive", [(RK, "return ge * 100 <= X * n", "return ge * 100 < X * n"),
                                            (RK, "return Fraction(ge, n) <= Fraction(X) / 100", "return Fraction(ge, n) < Fraction(X) / 100")]),
    ("f2_no_drop", "f2_no_drop", [(ST, "self.skip = skip = window_s // 60", "self.skip = skip = 0")]),
    ("f2_clip", "f2_clip", [(RK, "        if evaluation_ns - session.open_ns < window_s * NS:\n            return Result.unavailable", "        if False:\n            return Result.unavailable"),
                            (RK, "    if evaluation_ns - session.open_ns < window_s * NS:\n        return _na_stats", "    if False:\n        return _na_stats")]),
    ("half_day_390", "half_day_390", [(ST, "cal.minutes[pos - k:pos])", "[390] * k)")]),
    ("delay_ignored", "delay_ignored", [(RK, 'if gated_delay and session.feed_delay_tag == "delayed":', "if False:")]),
    ("gate_order_swap_f2", "gate_order_swap, f2_window_first", [(RK, *WIN_FIRST_F2)]),
    ("gate_order_swap_f10", "gate_order_swap, f10_window_first", [(RK, *WIN_FIRST_F10)]),
    ("snc_first_f2", "snc_first (F2)", [(RK, *SNC_F2)]),
    ("snc_first_f20", "snc_first (F20)", [(RK, *SNC_F20)]),
    ("snc_first_f19", "snc_first (F19)", [(RK, *SNC_F19)]),
    ("lane_ignored_store", "lane_ignored (history lane)", [(ST, "if ring is None or ring.lane != lane:", "if ring is None:")]),
    ("lane_ignored_prints", "lane_ignored (prints)", [(GR, "        if c.lane != lane or (want is not None and c.right != want):", "        if want is not None and c.right != want:")]),
    ("f2d_pct_upper", "f2d_pct_upper", [(RK, 'pc = 1 - p.value["upper_share"]', 'pc = p.value["upper_share"]')]),
    ("f2d_partial", "f2d_partial", [(RK, "    if first is not None:\n        return Result.unavailable(\"M2-3\"", "    if first is not None and not pcs:\n        return Result.unavailable(\"M2-3\""),
                                    (RK, "(pcs[0] + pcs[1] + pcs[2]) / 3", "sum(pcs) / len(pcs)")]),
    ("f2c_per_second", "f2c_per_second", [(RK, "Fraction(x, mins) if metric", "Fraction(x, window_s) if metric")]),
    ("f20_median_default", "f20_median_default", [(RK, '    params = {"N": N, "K": K, "metric": metric, "consumer_default": consumer_default}', '    consumer_default = "median"\n    params = {"N": N, "K": K, "metric": metric, "consumer_default": consumer_default}')]),
    ("f10_mean_default", "f10_mean_default", [(RK, '    params = {"N": N, "K": K, "window_s": window_s, "consumer_default": consumer_default}', '    consumer_default = "mean"\n    params = {"N": N, "K": K, "window_s": window_s, "consumer_default": consumer_default}')]),
    ("skip_unordered", "skip_unordered", [(GR, "if pt is not None and (t < pt or (t == pt and p[6] < ps)):", "if False:")]),
    ("skip_window_check", "skip_window_check", [(RK, "if windowed and window_s not in ALLOWED_WINDOWS:", "if False:")]),
    ("float_ratio", "float_ratio", [(RK, "r = Fraction(x) / st\n", "r = Fraction(float(x) / float(st))\n")]),
    ("f19_zero_counted", "f19_zero_counted", [(RK, "ratios = [(p, c) for p, c in zip(pv.totals, cv.totals) if c > 0]", "ratios = [(p, c) if c > 0 else (0, 1) for p, c in zip(pv.totals, cv.totals)]")]),
    ("store_k_plus_1", "store_k_plus_1", [(ST, "if len(recs) > self.k:\n            del recs[next(iter(recs))]\n\n    def seal", "if len(recs) > self.k + 1:\n            del recs[next(iter(recs))]\n\n    def seal")]),
    ("store_no_sort", "store_no_sort", [(ST, "        for key in sorted(self._rings):\n            ring = self._rings[key]\n            for sid in sorted(ring.recs):", "        for key in self._rings:\n            ring = self._rings[key]\n            for sid in ring.recs:")]),
    ("store_arrival_hash", "store_arrival_hash", [(ST, '"total", "complete", "sha", "txt")', '"total", "complete", "sha", "txt", "arr")'),
                                                   (ST, "self.total, self.complete, self.sha, self.txt = total, complete, None, txt", "self.total, self.complete, self.sha, self.txt = total, complete, None, txt\n        _ARR.append(0)\n        self.arr = len(_ARR)"),
                                                   (ST, "_VIEW_CACHE = 4\n", "_VIEW_CACHE = 4\n_ARR = []\n"),
                                                   (ST, """'%s%s,"window_s":%d,"grid":[%s],"total":%d,"complete":%s}' % (
        head, json.dumps(rec.session_id), window_s, _grid_text(rec), rec.total, "true" if rec.complete else "false")""",
                                                    """'%s%s,"window_s":%d,"grid":[%s],"total":%d,"complete":%s,"arr":%d}' % (
        head, json.dumps(rec.session_id), window_s, _grid_text(rec), rec.total, "true" if rec.complete else "false", rec.arr)""")]),
    ("store_view_current", "store_view_current", [(ST, "if r.complete and s < as_of]", "if r.complete and s <= as_of]")]),
    ("coverage_nonstd_first", "both_nonstd_first", [(GR, *NONSTD_FIRST)]),
    ("cond_excl_counted", "cond_excl_counted", [(GR, "        if p[5]:\n            excl += 1\n            continue\n        mult = p[4]\n        if mult != STANDARD_MULTIPLIER:\n            nonstd += 1\n            continue\n        size = p[3]\n        prem += price_ticks(p[2]) * size * mult\n        vol += size",
                                                 "        if p[5]:\n            excl += 1\n        mult = p[4]\n        if mult != STANDARD_MULTIPLIER:\n            nonstd += 1\n            continue\n        size = p[3]\n        prem += price_ticks(p[2]) * size * mult\n        vol += size")]),
    ("nonstd_counted", "nonstd_counted", [(GR, "        if mult != STANDARD_MULTIPLIER:\n            nonstd += 1\n            continue\n        size = p[3]\n        prem += price_ticks(p[2]) * size * mult\n        vol += size", "        if False:\n            nonstd += 1\n            continue\n        size = p[3]\n        prem += price_ticks(p[2]) * size * mult\n        vol += size")]),
    ("win_open_start", "win_open_start", [(GR, "        if t < lo or t > hi:\n            continue\n        c = contracts", "        if t <= lo or t > hi:\n            continue\n        c = contracts")]),
    ("win_open_end", "win_open_end", [(GR, "        if t < lo or t > hi:\n            continue\n        c = contracts", "        if t < lo or t >= hi:\n            continue\n        c = contracts")]),
    ("lookahead", "lookahead", [(GR, "        if t < lo or t > hi:\n            continue\n        c = contracts", "        if t < lo:\n            continue\n        c = contracts")]),
    # infrastructure mutants (the Tester lists them for the performance, cache and batching rows)
    ("cache_key_missing_k", "cache key missing one parameter", [(ST, "        key = (as_of, k)\n        view = ring.views.get(key)", "        key = (as_of,)\n        view = ring.views.get(key)"),
                                                                 (ST, "        ring.views[key] = view", "        ring.views[key] = view")]),
    ("cache_not_cleared_on_seal", "stale cache after seal", [(ST, "            rec.sha = None\n            ring.views.clear()", "            rec.sha = None")]),
    ("cache_not_cleared_on_append", "stale cache after append or eviction", [(ST, "        if ring.views:\n            ring.views.clear()\n        if len(recs)", "        if len(recs)")]),
    ("batched_drops_last", "batched path drops the last series", [(RK, "    return [flow_pack(store, s, session, evaluation_ns, window_s, p, v, c, X, N, K, consumer_default, lane, cov)\n            for s, p, v, c, cov in items]",
                                                                  "    items = list(items)[:-1]\n    return [flow_pack(store, s, session, evaluation_ns, window_s, p, v, c, X, N, K, consumer_default, lane, cov)\n            for s, p, v, c, cov in items]")]),
    ("fused_uses_wrong_volume", "fused path reads the wrong input", [(RK, '("contracts", volume), ("prints", count)):', '("contracts", count), ("prints", count)):')]),
    ("fused_f10_wrong_x", "fused F10 uses the wrong input", [(RK, "contracts_view.median(), contracts_view.mean(), N,", "contracts_view.median(), contracts_view.mean(), N,"),
                                                             (RK, "e = _finish_stats(\"M2-7\", series_id, sid, evaluation_ns, volume,", "e = _finish_stats(\"M2-7\", series_id, sid, evaluation_ns, count,")]),
    ("fused_ignores_window_gate", "fused path skips the window gate", [(RK, "window_ok = evaluation_ns - session.open_ns >= window_s * NS", "window_ok = True")]),
    ("lane_mismatch_dropped", "append accepts another lane", [(ST, 'if ring is not None and ring.lane != lane:', 'if False:')]),
    ("record_length_dropped", "record length not checked", [(ST, "if pos is not None and self.check_length and cal.minutes[pos] != minutes:", "if False:")]),
    ("trailer_not_verified", "load ignores the trailer", [(ST, 'if trailer.get("records") != len(rows) or', "if False and")]),
    ("trailer_not_required", "path load accepts a file without trailer", [(ST, "if need_trailer and trailer is None:", "if False:")]),
    ("snapshot_digest_skipped", "snapshot digest not verified", [(ST, "if verify and hashlib.sha256(mv[head + 40:]).digest()", "if False and hashlib.sha256(mv[head + 40:]).digest()")]),
    ("snapshot_length_skipped", "snapshot length not verified", [(ST, 'or int.from_bytes(mv[head:head + 8], "little") != len(mv):', "or False:")]),
    ("store_keeps_caller_arrays", "append_record keeps the caller's arrays", [(ST, "    if isinstance(x, memoryview):\n        a = array(x.format)", "    if True:\n        return x\n    if isinstance(x, memoryview):\n        a = array(x.format)")]),
    ("strict_calendar_default_off", "load defaults to non-strict", [(ST, "def load(cls, source, calendar, k=20, strict_calendar=True,", "def load(cls, source, calendar, k=20, strict_calendar=False,")]),
    ("lane_dropped_on_load", "load ignores the lane argument", [(ST, "ring = store._rings[key] = _Ring(lane_of(series_id), _head(series_id, metric))", "ring = store._rings[key] = _Ring(\"stock\", _head(series_id, metric))")]),
    ("stats_counts_rings_as_series", "stats series counts rings", [(ST, 'return {"series": len({k[0] for k in self._rings}),', 'return {"series": len(self._rings),')]),
    ("dump_not_atomic", "dump_to writes the target directly", [(ST, "os.replace(tmp, path)", "pass")]),
]


def run_tests(src, which):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(src), str(ROOT / "packages" / "option-contracts" / "src")]),
               M2A_DIFF_N="3000")
    r = subprocess.run([PY, "-B", "-m", "unittest", "discover", "-s", str(ROOT / "tests" / "m2"), "-p", which],
                       capture_output=True, text=True, env=env, cwd=ROOT)
    failed = sorted(set(re.findall(r"^(?:FAIL|ERROR): (?:test_row_)?(\w+)", r.stderr, re.M)))
    return failed, r.stderr


def main():
    pick = sys.argv[1] if len(sys.argv) > 1 else ""
    work = Path(tempfile.mkdtemp(prefix="m2a_mut_"))
    survivors = 0
    shown = 0
    try:
        for name, tester, edits in MUTS:
            if pick not in name:
                continue
            shown += 1
            src = work / name / "src"
            shutil.copytree(ROOT / "packages" / "features" / "src", src, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            for f, old, new in edits:
                p = src / f
                text = p.read_text(encoding="utf-8")
                if old not in text:
                    raise SystemExit("mutant %s: pattern not found in %s: %r" % (name, f, old[:70]))
                p.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
            failed, err = run_tests(src, "test_m2_rows.py")
            tier = "rows"
            if not failed:
                failed, err = run_tests(src, "test_m2_properties.py")
                tier = "properties"
            equiv = (not failed) and name in EQUIVALENT
            survivors += (not failed) and not equiv
            names = " ".join(x.replace("_", "-") for x in failed[:6]) + (" (+%d)" % (len(failed) - 6) if len(failed) > 6 else "")
            print(("CAUGHT   " if failed else ("EQUIVALENT " if equiv else "SURVIVED ")) + "%-28s [%s] by %s (%d): %s" % (name, tester, tier, len(failed), names + (EQUIVALENT[name] if equiv else "")), flush=True)
            shutil.rmtree(work / name, ignore_errors=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("%d mutants, %d survived" % (shown, survivors))
    sys.exit(1 if survivors else 0)


if __name__ == "__main__":
    main()
