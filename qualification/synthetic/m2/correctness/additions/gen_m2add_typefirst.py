"""mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Additions: type-first per field (47 rows, F1/F4/F7/F17/F18). A wrong-typed field (float, Decimal, Fraction, bool, None, str, bytes, unhashable)
reports malformed_type at the slot of the single precedence list where that field's value check runs: time and seq at the ordering checks,
size at negative_size_or_price, multiplier at bad_multiplier, contract id at unknown_contract; price type and condition_excluded at the
malformed_type slot after unknown_contract. No exception escapes; a malformed print does not hide another print's error. The decoding rule
for tagged objects is in the dataset header (key decoding)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import m2add_oracle as A  # noqa: E402
from gen_m2add_types import DECODING  # noqa: E402
from m2common import *  # noqa: E402,F401,F403
import m2common as C  # noqa: E402

A.install()
DEC = lambda t: {"py_type": "Decimal", "text": t}
FRA = lambda t: {"py_type": "Fraction", "text": t}


def P(cid, dt, price, size, mult=100, excl=0, seq=0):
    return [cid, dt, price, size, mult, excl, seq]


def build(rng):
    R = Rows("addtypefirst", "M2A-TF")
    sess = session("2026-06-01", S(1800), 390)
    d = lambda s: -S(s)
    OUTS = ["M2-1", "M2-4", "M2-6", "M2-5", "M2-9"]
    PR = {"M2-1": {"filter": "all", "N": 3},
          "M2-4": {"window_s": 300, "N": 1, "threshold_ticks": 1000000000},
          "M2-6": {"window_s": 300},
          "M2-5": {"window_s": 300},
          "M2-9": {"window_s": 300, "at_least": "1/2", "at_most": None}}
    sid = {"M2-5": "C1"}
    T = ["structural", "additions", "type_first"]

    def row(out, prints, tags):
        r = R.add(out, "PO ruling: type first per field, at the slot of that field's value check", "Q6",
                  mkin(prints, sess=sess, series=sid.get(out, "SYN1"), raw=True), PR[out], tags=T + tags)
        if any(isinstance(x, dict) and "py_type" in x for p in prints for x in p):
            r["requires_decoding"] = True

    ok = lambda dt, seq=0, **kw: P("C1", dt, "1.0000", 5, seq=seq, **kw)
    # A. float size (-1.5, +1.5): malformed_type at the size slot
    for out, v in zip(OUTS, (-1.5, 1.5, -1.5, 1.5, -1.5)):
        row(out, [P("C1", d(10), "1.0000", v)], ["float_size", "malformed_type"])
    # B. float multiplier (0.0, 2.5): malformed_type at the multiplier slot (not bad_multiplier)
    for out, v in zip(OUTS, (0.0, 2.5, 0.0, 2.5, 0.0)):
        row(out, [P("C1", d(10), "1.0000", 5, mult=v)], ["float_multiplier", "malformed_type"])
    # C. negative Decimal and D. negative Fraction size, multiplier and time: type decides, not the sign
    cases = [("M2-1", "size"), ("M2-4", "mult"), ("M2-6", "time"), ("M2-5", "size"), ("M2-9", "mult"), ("M2-1", "time")]
    for make, tag, vals in ((DEC, "neg_decimal", {"size": "-1", "mult": "-100", "time": "-10000000000"}),
                            (FRA, "neg_fraction", {"size": "-1", "mult": "-100", "time": "-10000000000"})):
        for out, fld in cases:
            kw = {"size": 5, "mult": 100, "dt": d(10)}
            if fld == "size":
                kw["size"] = make(vals["size"])
            elif fld == "mult":
                kw["mult"] = make(vals["mult"])
            else:
                kw["dt"] = make(vals["time"])
            row(out, [P("C1", kw["dt"], "1.0000", kw["size"], mult=kw["mult"])], [tag, "malformed_type"])
    # E. str or None size or multiplier next to a genuine out-of-order pair elsewhere: unordered_prints is still reported
    def stream(defect_print):
        return [ok(d(40), 0), defect_print, ok(d(20), 0), ok(d(25), 1)]
    row("M2-1", stream(P("C1", d(30), "1.0000", "5", seq=1)), ["str_none_field", "pair_elsewhere", "unordered_prints"])
    row("M2-4", stream(P("C1", d(30), "1.0000", None, seq=1)), ["str_none_field", "pair_elsewhere", "unordered_prints"])
    row("M2-6", stream(P("C1", d(30), "1.0000", 5, mult="100", seq=1)), ["str_none_field", "pair_elsewhere", "unordered_prints"])
    row("M2-5", stream(P("C1", d(30), "1.0000", 5, mult=None, seq=1)), ["str_none_field", "pair_elsewhere", "unordered_prints"])
    row("M2-9", stream(P("C1", d(30), "1.0000", "5", seq=1)), ["str_none_field", "pair_elsewhere", "unordered_prints"])
    row("M2-1", [P("C1", d(10), "1.0000", "5")], ["str_none_field", "malformed_type"])
    row("M2-4", [P("C1", d(10), "1.0000", 5, mult=None)], ["str_none_field", "malformed_type"])
    # F. Decimal NaN as a price or a size
    for out, fld in zip(OUTS, ("price", "size", "price", "size", "price")):
        row(out, [P("C1", d(10), DEC("NaN") if fld == "price" else "1.0000", DEC("NaN") if fld == "size" else 5)], ["decimal_nan", "malformed_type"])
    # G. unhashable contract id (list, dict): malformed_type at the unknown_contract slot, no exception
    for out, cid in zip(OUTS, (["C1"], {"id": "C1"}, ["C1"], {"id": "C1"}, ["C1"])):
        row(out, [P(cid, d(10), "1.0000", 5)], ["unhashable_contract_id", "malformed_type"])
    # H. cross-field cases: the earlier slot decides
    row("M2-1", [P("ZZ9", d(10), "1.0000", 5, mult=1.5)], ["cross_field", "float_multiplier", "unknown_contract", "malformed_type"])     # multiplier slot first
    row("M2-5", [P("ZZ9", d(10), "1.0000", 5, mult=2.5)], ["cross_field", "float_multiplier", "unknown_contract", "malformed_type"])
    row("M2-4", [P("C1", d(10), "1.0000", 1.5, mult=0)], ["cross_field", "float_size", "bad_multiplier", "malformed_type"])           # size slot first
    row("M2-6", [P("C1", d(10), "1.0000", 2.5, mult=-100)], ["cross_field", "float_size", "bad_multiplier", "malformed_type"])
    row("M2-9", [P("ZZ9", d(10), 1.5, 5)], ["cross_field", "float_price", "unknown_contract"])                                          # price slot after unknown
    row("M2-4", [P("ZZ9", d(10), True, 5)], ["cross_field", "bool_price", "unknown_contract"])
    row("M2-1", [P("C1", d(10), "-1.0000", 1.5)], ["cross_field", "float_size", "negative_price", "malformed_type"])                    # size before price value
    row("M2-6", [P("C1", d(10), "-1.0000", 2.5)], ["cross_field", "float_size", "negative_price", "malformed_type"])
    assert len(R.rows) == 47, len(R.rows)
    return R.rows


def main():
    import argparse
    import json
    import random
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--seed", type=int, default=20261029)
    a = ap.parse_args()
    path = C.write_dataset(a.out, "add_typefirst", "addtypefirst", a.seed, build(random.Random(a.seed)))
    lines = open(path, "rb").read().decode("ascii").split("\n")
    head = json.loads(lines[0])
    head["decoding"] = DECODING
    lines[0] = C.dumps(head).rstrip("\n")
    open(path, "wb").write("\n".join(lines).encode("ascii"))
    print("m2_cases_add_typefirst.json", head["row_count"])


if __name__ == "__main__":
    main()
