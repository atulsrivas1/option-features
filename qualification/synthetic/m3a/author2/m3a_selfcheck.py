"""Self-check: every row's expected value is re-derived with the second implementation (m3a_ref2, exact Fractions) and
compared on every asserted key; structure checks (provenance, label sentence, counts, LF, ASCII, no absolute paths).
Usage: python m3a_selfcheck.py [datadir]"""
import glob
import os
import re
import sys

import m3a_common as C
import m3a_ref2 as R2

FILES = {"V1": "m3a_cases_V1.json", "V3": "m3a_cases_V3.json", "V9": "m3a_cases_V9.json", "history": "m3a_cases_history.json",
         "units": "m3a_cases_units.json"}
MIN_ROWS = {"V1": 40, "V3": 40, "V9": 40, "history": 36, "units": 20}
FORBIDDEN = ["real-data", "market data", "production", "validated against vendor", "Databento", "Linux parity", "byte-identical"]


def load_all(d):
    out = {}
    for fam, fn in FILES.items():
        h, rows = C.read_dataset(os.path.join(d, fn))
        out[fam] = (h, rows)
    return out


def cals_of(h):
    return h["calendars"]


def same(exp, got):
    """Every asserted key of exp must equal got; None values compare as given."""
    bad = []
    for k, v in exp.items():
        if got is None or k not in got or C.canon(got[k]) != C.canon(v):
            bad.append(k)
    return bad


def check(d, mut=None, quiet=False):
    data = load_all(d)
    failures, n = [], 0
    for fam, (h, rows) in data.items():
        for r in rows:
            n += 1
            try:
                got = R2.evaluate(r, cals_of(h), mut)
            except Exception:  # a crash under a mutant counts as detected
                got = None
            bad = same(r["expected"], got)
            if bad:
                failures.append((r["id"], bad))
    return n, failures


def structure(d):
    msgs = []
    data = load_all(d)
    for fam, (h, rows) in data.items():
        if h.get("provenance") != "SYNTHETIC" or h.get("label") != C.LABEL:
            msgs.append("%s: header provenance or label" % fam)
        if h["row_count"] != len(rows) or len(rows) < MIN_ROWS[fam]:
            msgs.append("%s: row count %d (min %d)" % (fam, len(rows), MIN_ROWS[fam]))
        ids = [r["id"] for r in rows]
        if len(set(ids)) != len(ids):
            msgs.append("%s: duplicate ids" % fam)
        for r in rows:
            for k in ("id", "family", "design_ref", "ruling", "inputs", "params", "expected", "derivation", "pending", "tags"):
                if k not in r:
                    msgs.append("%s: missing %s" % (r["id"], k))
            if not r["ruling"]:
                msgs.append("%s: no R-number" % r["id"])
    for fn in list(FILES.values()) + ["m3a_g4_histories.json"]:
        b = open(os.path.join(d, fn), "rb").read()
        if b"\r" in b:
            msgs.append("%s: CR found" % fn)
        try:
            b.decode("ascii")
        except UnicodeDecodeError:
            msgs.append("%s: non-ascii" % fn)
        t = b.decode("ascii", "replace")
        if re.search(r"[A-Za-z]:[\/]|/Users/|/home/", t):
            msgs.append("%s: absolute path" % fn)
        body = t.replace(C.LABEL, "")
        for term in FORBIDDEN:
            if term.lower() in body.lower():
                msgs.append("%s: forbidden term %s" % (fn, term))
    return msgs


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    n, fails = check(d)
    msgs = structure(d)
    data = load_all(d)
    counts = {f: len(v[1]) for f, v in data.items()}
    pend = sum(1 for _, rows in data.values() for r in rows if r["pending"] != "RULED")
    print("rows", n, counts, "pending", pend)
    for f in fails:
        print("MISMATCH", f)
    for m in msgs:
        print("STRUCT", m)
    if fails or msgs:
        sys.exit(1)
    print("selfcheck OK")


if __name__ == "__main__":
    main()
