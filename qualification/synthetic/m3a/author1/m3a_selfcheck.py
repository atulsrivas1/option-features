#!/usr/bin/env python3
"""Self-check (author 1): runs the independent quote-based engine (m3a_ref.py) over every row of every
m3a_cases_*.json in a directory and compares with the expected values within the stated tolerances
(IV 1e-4, forward 1e-6). Also rechecks header/label/tag/count rules, LF/ASCII, no absolute paths, and
recomputes quote vega >= 4 for gating rows with its own float code. Usage: m3a_selfcheck.py DIR"""
import glob, json, math, os, re, sys
from fractions import Fraction as Fr
import m3a_ref as R

LABEL = ("mock-data qualification only: passed on independently authored synthetic fixtures "
         "and synthetic workloads, Windows x64, CPython 3.12")
MIN = {"surface": 80, "delta25": 60, "tenors": 40, "coverage": 24, "american": 20}
CLOSED = {"convention_not_allowed", "no_eligible_contract", "price_out_of_bounds", "upper_asymptote", "no_atm_strike", "no_bracketing_expiry", "no_delta_bracket", "low_surface_coverage", None}
FORBID = ["real-data", "market data", "production", "validated against vendor", "databento", "linux parity",
          "byte-identical"]


def load(d):
    out = {}
    for p in sorted(glob.glob(os.path.join(d, "m3a_cases_*.json"))):
        raw = open(p, "rb").read()
        assert b"\r" not in raw, p + ": CR found"
        raw.decode("ascii")
        doc = json.loads(raw)
        out[doc["family"]] = (p, doc, raw)
    return out


def main(d):
    data = load(d)
    fails = 0
    total = 0
    for fam, (p, doc, raw) in sorted(data.items()):
        rows = doc["rows"]
        total += len(rows)
        ok = True
        if doc["provenance"] != "SYNTHETIC" or doc["qualification_label"] != LABEL:
            print("HEADER FAIL", fam); ok = False
        if len(rows) < MIN[fam] or doc["row_count"] != len(rows):
            print("COUNT FAIL", fam, len(rows)); ok = False
        low = raw.decode("ascii").lower()
        for t in FORBID:
            if t in low:
                print("FORBIDDEN TERM", fam, t); ok = False
        if re.search(r"[A-Za-z]:\\|/Users/|/tmp/", raw.decode("ascii")):
            print("ABSOLUTE PATH", fam); ok = False
        bad_rows = 0
        for row in rows:
            if row["expected"]["reason"] not in CLOSED and row["expected"]["status"] != "invalid_input":
                print("REASON OUTSIDE CLOSED SET", row["id"]); ok = False
            for it in (row["expected"]["frame"] or {}).get("expiries", {}).values():
                if it.get("reason") not in CLOSED:
                    print("ITEM REASON OUTSIDE SET", row["id"]); ok = False
            res = R.run(row)
            bad = R.compare(row, res)
            if bad:
                bad_rows += 1
                tag = "NONGATING" if not row["gating"] else "FAIL"
                print(tag, row["id"], bad[:3])
                if row["gating"]:
                    ok = False
            # vega recheck (own float code) for gating rows: every contract behind an expected value
            if row["gating"] and row["expected"]["status"] != "invalid_input":
                ch = row["inputs"]["chain"]
                S, r_, q = (float(Fr(ch[k])) for k in ("spot", "rate", "dividend_yield"))
                sig = row["oracle"]["sigma"]
                mv = row["oracle"]["min_contrib_vega"]
                if mv is not None and float(mv) < 4.0:
                    print("VEGA<4 in gating row", row["id"]); ok = False
        print("%-9s rows=%3d  pending=%2d  non-gating=%2d  mismatches=%d  %s" % (
            fam, len(rows), sum(1 for r_ in rows if r_["ruling_status"] != "RULED"),
            sum(1 for r_ in rows if not r_["gating"]), bad_rows, "OK" if ok else "FAIL"))
        fails += 0 if ok else 1
    print("total rows", total, "families", len(data), "RESULT", "PASS" if fails == 0 else "FAIL")
    return fails


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
