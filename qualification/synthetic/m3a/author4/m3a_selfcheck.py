#!/usr/bin/env python3
"""Self-check of the M3a structural and lane fixtures (SYNTHETIC, stdlib only): the reference m3a_ref.py recomputes
every expected value; counts, closed sets, pair coverage, headers, ASCII/LF and encoding checks.
Usage: python m3a_selfcheck.py DIR"""
import os
import re
import sys

import m3a_ref as R
from m3a_common import QUAL, read_rows

fails = []


def ck(cond, msg):
    if not cond:
        fails.append(msg)


def main(d):
    files = {"structural": "m3a_cases_structural.json", "structural_aux": "m3a_cases_structural_aux.json",
             "lane": "m3a_cases_lane.json"}
    data = {}
    for k, f in files.items():
        raw = open(os.path.join(d, f), "rb").read()
        ck(b"\r" not in raw and all(b < 128 for b in raw), f + ": not LF-only ASCII")
        ck(not re.search(rb"[A-Za-z]:\\\\|/Users/|/home/", raw), f + ": absolute path")
        h, rows = read_rows(os.path.join(d, f))
        ck(h["provenance"] == "SYNTHETIC" and h["label"] == QUAL, f + ": header tag or label")
        ck(h["row_count"] == len(rows), f + ": row_count")
        ck(len({r["id"] for r in rows}) == len(rows), f + ": duplicate ids")
        data[k] = rows
    s, x, l = data["structural"], data["structural_aux"], data["lane"]

    def tagc(t):
        return sum(1 for r in s if t in r["tags"])
    ck(len(s) == 157, "structural count %d" % len(s))
    ck((tagc("code"), tagc("type"), tagc("cutoff"), tagc("spot"), tagc("pair"), tagc("typefirst"), tagc("typed"), tagc("nonfinite"), tagc("typed2"), tagc("quote_none"), tagc("ivform"), tagc("convention")) == (34, 6, 2, 3, 30, 12, 10, 4, 10, 2, 11, 20),
       "structural breakdown")
    ck(len(l) == 6 and len(x) == 45, "lane or aux count")
    ck((tagc("boundary"), tagc("loadscan"), tagc("typed3")) == (10, 1, 2), "fix round 2 breakdown")
    for k, rows in data.items():
        for r in rows:
            got = R.evaluate(r)
            ck(R.agrees(r, got), "%s %s: expected %s got %s" % (k, r["id"], r["expected"], got))
            ck(r["ruling"] in ("RULED", "PENDING-RULING") and (r["ruling"] == "RULED") == (not r["pending"]),
               r["id"] + ": ruling tag")
            ck(all(k2 in r for k2 in ("id", "family", "design_ref", "r_numbers", "inputs", "params", "expected",
                                      "derivation")), r["id"] + ": fields")
            c = r["expected"].get("code")
            ck(c is None or c in R.CLOSED, r["id"] + ": code outside the closed set")
    seen = {r["expected"]["code"] for r in s + l if r["expected"].get("code")}
    ck(not (R.CLOSED - {"bad_input"} - seen), "codes without a row: %s" % sorted(R.CLOSED - {"bad_input"} - seen))
    pairs = {t for r in s if "pair" in r["tags"] for t in r["tags"] if "+" in t}
    ck(len(pairs) == 18, "request pairs %d" % len(pairs))
    for fam, n in (("history", 5), ("snapshot", 2), ("text", 2), ("view", 3), ("request", 18)):
        ck(sum(1 for r in s if "pair" in r["tags"] and fam in r["tags"]) == n, "pair rows " + fam)
        ck(sum(1 for r in x if "pair" in r["tags"] and fam in r["tags"]) == n, "aux pair rows " + fam)
    flat = " ".join(str(r["inputs"]) for r in s)
    ck("'py_type': 'Decimal'" in flat and "'py_type': 'Fraction'" in flat and "'py_type': 'bytes'" in flat,
       "tagged objects")
    npend = sum(1 for r in s + l if r["ruling"] == "PENDING-RULING")
    print("rows: structural %d aux %d lane %d; pending-ruling rows (structural + lane) %d" % (len(s), len(x), len(l), npend))
    print("FAIL" if fails else "OK", len(fails))
    for f in fails[:40]:
        print(" ", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
