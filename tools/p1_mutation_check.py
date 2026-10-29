#!/usr/bin/env python3
"""Mutation check of the P1 implementation against the independent P1 rows.

Each mutant is a one-line change applied to a scratch copy of packages/features/src (the checkout is never
modified); the P1 row tests must fail for every mutant. Mutants follow the Tester's table
(qualification/synthetic/p1/AUTHORING_NOTES.md) where the mutated code exists in this implementation.
Usage: python tools/p1_mutation_check.py     (exit status 1 if any mutant survives)
Label: synthetic fixtures only; a surviving mutant would mean a row set that cannot see that defect.
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
MUTS = [
 ("M01 bid=0 valid for spread", "option_features/reference.py", "elif bid is not None and bid == 0:", "elif False:"),
 ("M03 locked gives available", "option_features/reference.py", "elif bid == ask:\n            faults.append((\"invalid_input\", \"locked_market\"))", "elif False:\n            faults.append((\"invalid_input\", \"locked_market\"))"),
 ("M05 locked withholds signing", "option_features/quotes.py", "    if p is None or p <= 0 or bid is None or ask is None or bid <= 0:\n        return S_INVALID\n    if bid > ask:", "    if p is None or p <= 0 or bid is None or ask is None or bid <= 0 or bid == ask:\n        return S_INVALID\n    if bid > ask:"),
 ("M06 inside-spread split at midpoint", "option_features/quotes.py", "return S_ASK if hit_ask else S_INSIDE", "return S_ASK if (hit_ask or p * 2 > bid + ask) else S_INSIDE"),
 ("M07 epsilon exclusive (ask)", "option_features/quotes.py", "hit_ask = p >= ask - eps", "hit_ask = p > ask - eps"),
 ("M07b epsilon exclusive (bid)", "option_features/quotes.py", "if p <= bid + eps:\n        return S_AMBIGUOUS", "if p < bid + eps:\n        return S_AMBIGUOUS"),
 ("M08 age 3s stale", "option_features/quotes.py", "    if age > max_age:\n        return S_STALE\n    return _touch_code", "    if age >= max_age:\n        return S_STALE\n    return _touch_code"),
 ("M09 age limit +1ns", "option_features/quotes.py", "    if age > max_age:\n        return S_STALE\n    return _touch_code", "    if age > max_age + 1:\n        return S_STALE\n    return _touch_code"),
 ("M10 window_end ignored", "option_features/windows.py", "        end = window_end_ns\n    start = end - window_ns\n    tk = to_ticks", "        end = max((t for t, _, _, _, m in prints if m == std), default=window_end_ns)\n    start = end - window_ns\n    tk = to_ticks"),
 ("M11 window excludes print at end", "option_features/windows.py", "        if start <= t <= end:\n            if mult == std:", "        if start <= t < end:\n            if mult == std:"),
 ("M13 window start exclusive", "option_features/windows.py", "        if start <= t <= end:\n            if mult == std:", "        if start < t <= end:\n            if mult == std:"),
 ("M19 coverage counts excluded", "option_features/windows.py", "if regular and start <= t <= t_eval_ns:", "if start <= t <= t_eval_ns:"),
 ("M20 coverage start exclusive", "option_features/windows.py", "if regular and start <= t <= t_eval_ns:", "if regular and start < t <= t_eval_ns:"),
 ("M21 coverage minimum 6", "option_features/windows.py", "if count < min_regular_updates:", "if count < min_regular_updates + 1:"),
 ("M25 share threshold exclusive", "option_features/shares.py", "fired = share >= threshold", "fired = share > threshold"),
 ("M27 OTM inclusive at the money", "option_features/shares.py", "otm = k > s if right == \"call\" else k < s", "otm = k >= s if right == \"call\" else k <= s"),
 ("M18 short limit off by one", "option_features/shares.py", "short = 0 <= dte <= max_days", "short = 0 <= dte < max_days"),
 ("M14 denominator = referenced premium", "option_features/shares.py", "share = Fraction(hit, total)", "share = Fraction(hit, ref)"),
 ("M22 unclassified counted as ask", "option_features/quotes.py", "        else:\n            unc += premium\n    m = STANDARD_MULTIPLIER", "        else:\n            unc += premium\n            ask += premium\n    m = STANDARD_MULTIPLIER"),
 ("M32 same-ns quote unusable", "option_features/quotes.py", "or qt > t:\n        return S_NO_QUOTE", "or qt >= t:\n        return S_NO_QUOTE"),
 ("M33 later quote usable", "option_features/quotes.py", "or qt > t:\n        return S_NO_QUOTE", ":\n        return S_NO_QUOTE"),
 ("M31 stale before validity", "option_features/quotes.py", "    if p is None or p <= 0 or bid is None or ask is None or bid <= 0:\n        return S_INVALID\n    if bid > ask:\n        return S_CROSSED\n    if age > max_age:\n        return S_STALE\n", "    if age > max_age:\n        return S_STALE\n    if p is None or p <= 0 or bid is None or ask is None or bid <= 0:\n        return S_INVALID\n    if bid > ask:\n        return S_CROSSED\n"),
]
survivors = 0
MUT = tempfile.mkdtemp(prefix="p1-mutants-")
for name, rel, a, b in MUTS:
    if os.path.exists(MUT):
        shutil.rmtree(MUT)
    shutil.copytree(ROOT / "packages" / "features" / "src", os.path.join(MUT, "f"), ignore=shutil.ignore_patterns("__pycache__"))
    p = os.path.join(MUT, "f", rel)
    s = open(p, encoding="utf-8", newline="").read().replace("\r\n", "\n")
    if a not in s:
        sys.exit("pattern missing for " + name)
    open(p, "w", encoding="utf-8", newline="").write(s.replace(a, b, 1))
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([os.path.join(MUT, "f"), str(ROOT / "packages" / "option-contracts" / "src"), str(ROOT / "tests" / "p1")]), PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([PY, "-B", "-m", "unittest", "discover", "-s", str(ROOT / "tests" / "p1"), "-p", "test_p1_rows.py", "-v"], capture_output=True, text=True, env=env, cwd=ROOT)
    failed = sorted(set(re.findall(r"^(?:FAIL|ERROR): test_row_(\w+)", r.stderr, re.M)))
    survivors += not failed
    print(("CAUGHT   " if failed else "SURVIVED ") + name + "  rows: " + " ".join(failed))
shutil.rmtree(MUT, ignore_errors=True)
print("%d mutants, %d survived" % (len(MUTS), survivors))
sys.exit(1 if survivors else 0)
