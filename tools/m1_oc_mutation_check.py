#!/usr/bin/env python3
"""Mutation check of the OC5/OC6 implementation against the independent M1 OC rows.

Each mutant is a text change applied to a scratch copy of packages/features/src (the checkout is never
modified); the row tests (tests/m1/test_m1_oc_rows.py) must fail for every mutant. The mutants follow the Tester's
table (qualification/synthetic/m1/AUTHORING_NOTES.md, M1-M20 and X1-X12) mapped onto this implementation; the
Tester's own catching rows are listed there, this tool reports the rows that catch each mutant here.
Usage: python tools/m1_oc_mutation_check.py     (exit status 1 if any mutant survives)
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
IMB, SPR, HIST = "option_features/imbalance.py", "option_features/spreadwin.py", "option_features/quotehist.py"

STALE5 = "    if t_ns - ev > limit:\n        return _UNAVAILABLE[\"stale_quote\"]\n"
STALE6 = "    if t_ns - ev > limit:\n        return _unavailable(\"stale_quote\", 0)\n"
FAULT5 = ("    fault = quote_fault(price_ticks(bid), price_ticks(ask))\n"
          "    if fault is not None and fault != \"locked_market\":  # a locked quote still evaluates (ruling Q8)\n"
          "        return _UNAVAILABLE[fault]\n")
FAULT6 = "    fault = quote_fault(b, a)\n    if fault is not None:\n        return _unavailable(fault, 0)\n"
COVER6 = "    if count < cov_min:\n        return _unavailable(\"low_quote_coverage\", count)\n"
COUNT = "        if u[5]:\n            if e >= wstart:\n                count += 1\n        else:\n            st = None\n"

MUTS = [
    ("M1 OC5 exclusive threshold", [(IMB, ">= p * total", "> p * total")]),
    ("M2 bid share instead of imbalance", [(IMB, "    diff = b - a\n", "    diff = b\n")]),
    ("M3 swap bid/ask labels", [(IMB, '"bid" if diff > 0 else "ask"', '"ask" if diff > 0 else "bid"')]),
    ("M4a divide by bid only", [(IMB, "    total = b + a\n", "    total = b\n")]),
    ("M4b divide by ask only", [(IMB, "    total = b + a\n", "    total = a\n")]),
    ("M5 abs value, no side", [(IMB, "    diff = b - a\n", "    diff = abs(b - a)\n")]),
    ("M6a OC5 stale dropped", [(IMB, STALE5, "")]),
    ("M6b OC5 stale limit +1ns", [(IMB, "t_ns - ev > limit:", "t_ns - ev > limit + 1:")]),
    ("M6c OC5 stale limit -1ns", [(IMB, "t_ns - ev > limit:", "t_ns - ev > limit - 1:")]),
    ("M6a' OC6 stale dropped", [(SPR, STALE6, "")]),
    ("M6b' OC6 stale limit +1ns", [(SPR, "t_ns - ev > limit:", "t_ns - ev > limit + 1:")]),
    ("M6c' OC6 stale limit -1ns", [(SPR, "t_ns - ev > limit:", "t_ns - ev > limit - 1:")]),
    ("M7 ignore known_at", [(HIST, "if u[1] <= t_ns and u[2] <= t_ns:", "if u[1] <= t_ns:")]),
    ("M8 fall back to older quote", [(HIST, "if u[1] <= t_ns and u[2] <= t_ns:", "if u[1] <= t_ns and u[2] <= t_ns and u[5]:")]),
    ("M9 both-zero treated as 0", [(IMB, "    if total == 0:\n        return _UNAVAILABLE[\"zero_displayed_size\"]\n",
                                    "    if total == 0:\n        return OC5Result(\"not_fired\", None, None, 0, 1)\n")]),
    ("M10 OC6 ratio inverted", [(SPR, "r = dc * wtot / (sc * tot)", "r = (sc * tot) / (dc * wtot)"),
                                (SPR, "left = dc * den * wtot", "left = sc * num"),
                                (SPR, "right = sc * num", "right = dc * den * wtot")]),
    ("M11 OC6 thresholds exclusive", [(SPR, "left * nq <= np_ * right", "left * nq < np_ * right"),
                                      (SPR, "left * wq >= wp * right", "left * wq > wp * right")]),
    ("M12a window 240 s", [(SPR, "    wstart = t_ns - window_ns\n", "    wstart = t_ns - window_ns * 4 // 5\n")]),
    ("M12b window 360 s", [(SPR, "    wstart = t_ns - window_ns\n", "    wstart = t_ns - window_ns * 6 // 5\n")]),
    ("M13a coverage minimum 4", [(SPR, "if count < cov_min:", "if count < cov_min - 1:")]),
    ("M13b coverage minimum 6", [(SPR, "if count < cov_min:", "if count < cov_min + 1:")]),
    ("M14 binary64 decision only", [(SPR, "        if r < n_lo:", "        if r <= 0.75:"), (SPR, "        elif r > w_hi:", "        elif r >= 1.5:"),
                                    (SPR, "        elif n_hi < r < w_lo:", "        elif True:")]),
    ("M15 OC6 evaluated on locked quote", [(SPR, FAULT6, FAULT6.replace("if fault is not None:", "if fault is not None and fault != \"locked_market\":"))]),
    ("M16 count includes excluded-condition", [(SPR, COUNT, "        if u[5]:\n            if e >= wstart:\n                count += 1\n        else:\n            st = None\n            if e >= wstart:\n                count += 1\n")]),
    ("M17 simple mean, not time-weighted", [(SPR, "            w = nxt - s\n", "            w = 1\n")]),
    ("M18 window excludes update at exactly 300 s", [(SPR, "            if e >= wstart:\n                count += 1\n        else:\n            st = None\n",
                                                      "            if e > wstart:\n                count += 1\n        else:\n            st = None\n")]),
    ("M19a OC5 stale inclusive", [(IMB, "t_ns - ev > limit:", "t_ns - ev >= limit:")]),
    ("M19b OC6 stale inclusive", [(SPR, "t_ns - ev > limit:", "t_ns - ev >= limit:")]),
    ("M20 OC5 blocked by low coverage", [(IMB, "    sz = smap.get(rev)\n",
                                          "    if sum(1 for x in ups if x[5] and t_ns - 300000000000 <= x[1] <= t_ns) < 5:\n"
                                          "        return OC5Result(\"unavailable\", \"low_quote_coverage\", None, 0, None)\n    sz = smap.get(rev)\n")]),
    ("X1 no carry-in", [(SPR, "        if e < open_ns:\n            break\n        key = (u[3], u[4])\n        st = cache.get(key, 0)\n        if st == 0:\n            st = _state(key, cache)\n        if u[5]:\n            if e >= wstart:",
                         "        if e < wstart:\n            break\n        key = (u[3], u[4])\n        st = cache.get(key, 0)\n        if st == 0:\n            st = _state(key, cache)\n        if u[5]:\n            if e >= wstart:")]),
    ("X2 previous session enters", [(SPR, "        if e < open_ns:\n            break\n        key = (u[3], u[4])\n        st = cache.get(key, 0)\n        if st == 0:\n            st = _state(key, cache)\n        if u[5]:\n            if e >= wstart:",
                                     "        key = (u[3], u[4])\n        st = cache.get(key, 0)\n        if st == 0:\n            st = _state(key, cache)\n        if u[5]:\n            if e >= wstart:")]),
    ("X3 denominator = window length", [(SPR, "    acc, wtot, count = scan\n", "    acc, wtot, count = scan\n    wtot = t_ns - wstart if wtot else 0\n")]),
    ("X4 invalid intervals weighted", [(SPR, "and 0 < ub < ua else None", "and 0 < ub and 0 < ua else None")]),
    ("X5 price spread, not bps", [(SPR, "st = (ua - ub, ua + ub) if", "st = (ua - ub, 2 * 10 ** 8) if"), (SPR, "dc, sc = a - b, a + b", "dc, sc = a - b, 2 * 10 ** 8")]),
    ("X6 coverage counts valid only", [(SPR, "        if u[5]:\n            if e >= wstart:\n                count += 1\n        else:\n            st = None\n",
                                        "        if u[5]:\n            if e >= wstart and st is not None:\n                count += 1\n        else:\n            st = None\n")]),
    ("X7 coverage unclipped at session open", [(SPR, "        if e < open_ns:\n            break\n        key = (u[3], u[4])\n        st = cache.get(key, 0)\n        if st == 0:\n            st = _state(key, cache)\n        if u[5]:\n            if e >= wstart:",
                                                "        if e < open_ns:\n            if u[5] and e >= t_ns - window_ns:\n                count += 1\n            continue\n        key = (u[3], u[4])\n        st = cache.get(key, 0)\n        if st == 0:\n            st = _state(key, cache)\n        if u[5]:\n            if e >= wstart:")]),
    ("X8 interval starts at event time", [(SPR, "        s = ka if ka > wstart else wstart\n        if s > nxt:", "        s = e if e > wstart else wstart\n        if s > nxt:")]),
    ("X9a stale before validity (OC5)", [(IMB, FAULT5 + STALE5, STALE5 + FAULT5)]),
    ("X9b stale before validity (OC6)", [(SPR, FAULT6 + STALE6, STALE6 + FAULT6)]),
    ("X10 coverage before stale", [(SPR, STALE6, ""), (SPR, COVER6, COVER6 + STALE6)]),
    ("X11 single_venue blocks OC6", [(SPR, "    p = params or OC6Params()\n    return _oc6", "    p = params or OC6Params()\n    if not consolidated:\n        return _unavailable(\"not_consolidated\", 0)\n    return _oc6")]),
    ("X12a non-standard blocks OC5", [(IMB, "    params = params or OC5Params()\n    return _oc5", "    params = params or OC5Params()\n    if not standard:\n        return _UNAVAILABLE[\"invalid_quote\"]\n    return _oc5")]),
    ("X12b non-standard blocks OC6", [(SPR, "    p = params or OC6Params()\n    return _oc6", "    p = params or OC6Params()\n    if not standard:\n        return _unavailable(\"invalid_quote\", 0)\n    return _oc6")]),
]


def main():
    survivors = 0
    work = tempfile.mkdtemp(prefix="m1-oc-mutants-")
    try:
        for name, edits in MUTS:
            dst = os.path.join(work, "f")
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(ROOT / "packages" / "features" / "src", dst, ignore=shutil.ignore_patterns("__pycache__"))
            for rel, old, new in edits:
                p = os.path.join(dst, rel)
                text = open(p, encoding="utf-8", newline="").read().replace("\r\n", "\n")
                if old not in text:
                    sys.exit("pattern missing for %s: %r" % (name, old[:60]))
                open(p, "w", encoding="utf-8", newline="").write(text.replace(old, new, 1))
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join(
                [dst, str(ROOT / "packages" / "option-contracts" / "src"), str(ROOT / "tests" / "m1")]))
            r = subprocess.run([PY, "-B", "-m", "unittest", "discover", "-s", str(ROOT / "tests" / "m1"), "-p", "test_m1_oc_rows.py", "-v"],
                               capture_output=True, text=True, env=env, cwd=ROOT)
            failed = sorted(set(re.findall(r"^(?:FAIL|ERROR): test_row_(\w+)", r.stderr, re.M)))
            survivors += not failed
            shown = " ".join(x.replace("_", "-") for x in failed[:8]) + (" (+%d)" % (len(failed) - 8) if len(failed) > 8 else "")
            print(("CAUGHT   " if failed else "SURVIVED ") + name + "  rows: " + shown)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("%d mutants, %d survived" % (len(MUTS), survivors))
    sys.exit(1 if survivors else 0)


if __name__ == "__main__":
    main()
