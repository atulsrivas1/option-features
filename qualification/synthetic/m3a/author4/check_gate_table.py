#!/usr/bin/env python3
"""Diffs the gate table of M3A_PERF_ACCEPTANCE.md against the gate table of docs/m3a/M3A_GATE_BUDGETS.md cell by cell
(Gate, Workload, Metric, Budget, Hard) and compares the sets of numbers. Usage: python check_gate_table.py BUDGETS.md ACCEPT.md"""
import re
import sys


def rows(path):
    out = {}
    for line in open(path, encoding="utf8"):
        if line.startswith("| M3A-B"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            out[cells[0]] = cells
    return out


def nums(s):
    return re.findall(r"\d[\d,]*\.?\d*", s)


def main(a, b):
    ra, rb = rows(a), rows(b)
    bad = []
    if set(ra) != set(rb):
        bad.append("gate sets differ: only budgets %s, only acceptance %s" % (sorted(set(ra) - set(rb)), sorted(set(rb) - set(ra))))
    names = ["Gate", "Workload", "Metric", "Budget", "Hard"]
    for g in sorted(set(ra) & set(rb)):
        for i, n in enumerate(names):
            if ra[g][i] != rb[g][i]:
                bad.append("%s %s differs:\n  budgets   : %s\n  acceptance: %s" % (g, n, ra[g][i], rb[g][i]))
        if nums(" ".join(ra[g][:5])) != nums(" ".join(rb[g][:5])):
            bad.append("%s numbers differ" % g)
    print("gates compared: %d" % len(set(ra) & set(rb)))
    print("OK" if not bad else "FAIL")
    for x in bad:
        print(x)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
