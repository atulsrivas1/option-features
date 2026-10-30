"""mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Additions: field-type rows for F1/F4/F7/F17/F18 (40 rows): bool seq (including where it would invent or hide an ordering fault),
float condition_excluded 1.0, Decimal and Fraction prices, None and bytes prices, float and bool prices in multi-fault records where
precedence decides the code, malformed fields combined with an ordering fault. Prices of non-JSON types are tagged objects; the
decoding rule is in the dataset header (key decoding) and rows needing it carry requires_decoding."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import m2add_oracle as A  # noqa: E402
from m2common import *  # noqa: E402,F401,F403
import m2common as C  # noqa: E402

A.install()
DEC = {"py_type": "Decimal", "text": "1.0000"}
FRA = {"py_type": "Fraction", "text": "1/1"}
BYT = {"py_type": "bytes", "hex": "312e30"}
BYT2 = {"py_type": "bytes", "hex": "00ff"}
DECODING = ("a price given as an object with py_type is decoded by the harness before use: Decimal and Fraction carry text, "
            "bytes carries hex; the harness builds Decimal(text), Fraction(text) or bytes.fromhex(hex); rows needing this carry requires_decoding true")


def P(cid, dt, price, size, mult=100, excl=0, seq=0):
    return [cid, dt, price, size, mult, excl, seq]


def build(rng):
    R = Rows("addtypes", "M2A-TYP")
    sess = session("2026-06-01", S(1800), 390)
    d = lambda s: -S(s)
    PR = {"M2-1": {"filter": "all", "N": 3},
          "M2-4": {"window_s": 300, "N": 1, "threshold_ticks": 1000000000},
          "M2-6": {"window_s": 300},
          "M2-5": {"window_s": 300},
          "M2-9": {"window_s": 300, "at_least": "1/2", "at_most": None}}
    sid = {"M2-5": "C1"}
    T = ["structural", "additions", "field_types"]

    def row(out, prints, tags):
        r = R.add(out, "PO ruling: price, flag and seq types; first applicable check in the section 9 list", "Q6",
                  mkin(prints, sess=sess, series=sid.get(out, "SYN1"), raw=True), PR[out], tags=T + tags)
        if any(isinstance(p[2], dict) for p in prints):
            r["requires_decoding"] = True

    for out in PR:
        row(out, [P("C1", d(10), "1.0000", 5, excl=1.0)], ["flag_float", "malformed_type"])
        row(out, [P("C1", d(10), DEC, 5)], ["price_decimal", "malformed_type"])
        row(out, [P("C1", d(10), FRA, 5)], ["price_fraction", "malformed_type"])
        row(out, [P("C1", d(10), "1.0000", 5, seq=True)], ["bool_seq_types", "malformed_type"])
    # float and bool prices in a multi-fault record: the earlier check in the list decides the reported code
    row("M2-1", [P("C1", d(10), 1.5, -3)], ["prec_multi", "negative_size_or_price", "float_price"])
    row("M2-4", [P("C1", d(10), True, 5, mult=0)], ["prec_multi", "bad_multiplier", "bool_price"])
    row("M2-6", [P("ZZ9", d(10), 1.5, 5)], ["prec_multi", "unknown_contract", "float_price"])
    row("M2-5", [P("C1", d(10), True, -3)], ["prec_multi", "negative_size_or_price", "bool_price"])
    row("M2-9", [P("C1", d(10), 1.5, 5, mult=-100)], ["prec_multi", "bad_multiplier", "float_price"])
    row("M2-1", [P("ZZ9", d(10), True, 5)], ["prec_multi", "unknown_contract", "bool_price"])
    # a malformed field together with an ordering fault: unordered_prints comes first
    row("M2-4", [P("C1", d(20), "1.0000", 5, seq=0), P("C1", d(30), 1.5, 5, seq=1)], ["prec_multi", "unordered_prints", "float_price"])
    row("M2-6", [P("C1", d(10), True, 5, seq=1), P("C1", d(10), "1.0000", 5, seq=0)], ["prec_multi", "unordered_prints", "bool_price"])
    row("M2-1", [P("C1", d(20), DEC, 5, seq=0), P("C1", d(30), "1.0000", 5, seq=1)], ["prec_multi", "unordered_prints", "price_decimal"])
    row("M2-9", [P("C1", d(10), "1.0000", 5, excl=1.0, seq=2), P("C1", d(10), "1.0000", 5, seq=1)], ["prec_multi", "unordered_prints", "flag_float"])
    # a bool seq must neither invent nor hide an ordering fault: a pair with a bool seq is not judged, the record is malformed_type
    row("M2-1", [P("C1", d(10), "1.0000", 5, seq=True), P("C1", d(10), "1.0000", 5, seq=0)], ["seq_invented", "bool_seq_types", "malformed_type"])
    row("M2-4", [P("C1", d(10), "1.0000", 5, seq=True), P("C1", d(10), "1.0000", 5, seq=0)], ["seq_invented", "bool_seq_types", "malformed_type"])
    row("M2-6", [P("C1", d(10), "1.0000", 5, seq=5), P("C1", d(10), "1.0000", 5, seq=False), P("C1", d(10), "1.0000", 5, seq=2)],
        ["seq_hidden", "bool_seq_types", "malformed_type"])
    row("M2-5", [P("C1", d(10), "1.0000", 5, seq=5), P("C1", d(10), "1.0000", 5, seq=False), P("C1", d(10), "1.0000", 5, seq=7)],
        ["seq_hidden", "bool_seq_types", "malformed_type"])
    # a real ordering fault between int-seq prints is reported first even when another print has a bool seq
    row("M2-9", [P("C1", d(10), "1.0000", 5, seq=3), P("C1", d(10), "1.0000", 5, seq=1), P("C1", d(9), "1.0000", 5, seq=True)],
        ["prec_multi", "unordered_prints", "bool_seq_types"])
    row("M2-1", [P("C1", d(10), "1.0000", 5, seq=3), P("C1", d(10), "1.0000", 5, seq=1), P("C1", d(9), "1.0000", 5, seq=False)],
        ["prec_multi", "unordered_prints", "bool_seq_types"])
    # None and bytes prices are malformed_type
    row("M2-1", [P("C1", d(10), None, 5)], ["price_none", "malformed_type"])
    row("M2-4", [P("C1", d(10), BYT, 5)], ["price_bytes", "malformed_type"])
    row("M2-6", [P("C1", d(10), None, 5)], ["price_none", "malformed_type"])
    row("M2-6", [P("C1", d(10), BYT2, 5)], ["price_bytes", "malformed_type"])
    assert len(R.rows) == 40, len(R.rows)
    return R.rows


def main():
    import argparse
    import json
    import random
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=".")
    ap.add_argument("--seed", type=int, default=20261029)
    a = ap.parse_args()
    path = C.write_dataset(a.out, "add_types", "addtypes", a.seed, build(random.Random(a.seed)))
    lines = open(path, "rb").read().decode("ascii").split("\n")
    head = json.loads(lines[0])
    head["decoding"] = DECODING
    lines[0] = C.dumps(head).rstrip("\n")
    open(path, "wb").write("\n".join(lines).encode("ascii"))
    print("m2_cases_add_types.json", head["row_count"])


if __name__ == "__main__":
    main()
