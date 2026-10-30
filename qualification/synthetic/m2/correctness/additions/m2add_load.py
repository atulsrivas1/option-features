"""Loader for the additions (stdlib only): wraps the merged m2_load (unchanged) and decodes tagged price objects of rows flagged
requires_decoding into Python types, as the dataset header states. assert_decoded() lets a harness prove it decoded."""
import decimal
import fractions
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import m2_load  # noqa: E402

TAGGED = {"Decimal": lambda d: decimal.Decimal(d["text"]), "Fraction": lambda d: fractions.Fraction(d["text"]),
          "bytes": lambda d: bytes.fromhex(d["hex"])}
PY_TYPES = {"Decimal": decimal.Decimal, "Fraction": fractions.Fraction, "bytes": bytes}


def decode_value(v):
    if isinstance(v, dict) and v.get("py_type") in TAGGED:
        return TAGGED[v["py_type"]](v)
    return v


def decode_row(row):
    if not row.get("requires_decoding"):
        return row
    row["inputs"]["prints"] = [[decode_value(x) for x in p] for p in row["inputs"]["prints"]]
    return row


def assert_decoded(row):
    """raises AssertionError when a row flagged requires_decoding still carries a tagged object or has no decoded Python-typed price"""
    prices = [x for p in row["inputs"].get("prints", []) for x in p]
    if row.get("requires_decoding"):
        assert not any(isinstance(p, dict) and "py_type" in p for p in prices), row["id"] + ": tagged object not decoded"
        assert any(isinstance(p, tuple(PY_TYPES.values())) for p in prices), row["id"] + ": no decoded Decimal, Fraction or bytes price"
    else:
        assert not any(isinstance(p, dict) and "py_type" in p for p in prices), row["id"] + ": tagged object in a row without requires_decoding"


def load_dataset(path):
    head, rows = m2_load.load_dataset(path)
    if head.get("decoding"):
        rows = [decode_row(r) for r in rows]
    for r in rows:
        assert_decoded(r)
    return head, rows
