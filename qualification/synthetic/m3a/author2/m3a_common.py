"""Shared helpers for the author-2 M3a fixtures (stdlib only). SYNTHETIC data only."""
import datetime
import hashlib
import json
import random
import re
from fractions import Fraction

LABEL = ("mock-data qualification only: passed on independently authored synthetic fixtures and synthetic "
         "workloads, Windows x64, CPython 3.12")
SEED = 20261030
APPROX = "approximate: European model on an American-style contract"
EXACT = "exact-model"
NS = 10 ** 9


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def r8(x):
    """Round once, half to even, from the exact binary64 value to 8 decimals; returns integer 10^-8 units."""
    q = Fraction(x) * 10 ** 8
    fl = q.numerator // q.denominator
    rem = q - fl
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and fl % 2 == 1):
        fl += 1
    return fl


def text8(u):
    s = "-" if u < 0 else ""
    a = abs(u)
    return "%s%d.%08d" % (s, a // 10 ** 8, a % 10 ** 8)


def show(fr):
    fr = Fraction(fr)
    return fr.numerator if fr.denominator == 1 else "%d/%d" % (fr.numerator, fr.denominator)


def tag_fraction(t):
    return {"py_type": "Fraction", "text": t}


def tag_decimal(t):
    return {"py_type": "Decimal", "text": t}


def tag_bytes(h):
    return {"py_type": "bytes", "hex": h}


def decode(o):
    """Decode the M2 tagged objects (Decimal, Fraction, bytes) in a row, recursively."""
    from decimal import Decimal
    if isinstance(o, dict):
        if set(o) == {"py_type", "text"} and o["py_type"] in ("Decimal", "Fraction"):
            return Decimal(o["text"]) if o["py_type"] == "Decimal" else Fraction(o["text"])
        if set(o) == {"py_type", "hex"} and o["py_type"] == "bytes":
            return bytes.fromhex(o["hex"])
        return {k: decode(v) for k, v in o.items()}
    if isinstance(o, list):
        return [decode(v) for v in o]
    return o


def make_calendar(n, minutes=390, half=None, start="2024-01-02", holidays=()):
    """n sessions on weekdays, skipping the holiday dates (calendar gaps); half = {index: minutes}."""
    half = half or {}
    d = datetime.date.fromisoformat(start)
    out = []
    while len(out) < n:
        if d.weekday() < 5 and d.isoformat() not in holidays:
            out.append([d.isoformat(), half.get(len(out), minutes)])
        d += datetime.timedelta(days=1)
    return out


def cal_ref(cal):
    return "cal-" + sha(canon(cal))[:8]


def open_ns(session_id):
    d = datetime.date.fromisoformat(session_id)
    days = (d - datetime.date(1970, 1, 1)).days
    return days * 86400 * NS + (14 * 3600 + 30 * 60) * NS


def expand_gs(gs):
    g = [gs["base"]] * gs["len"]
    for i, v in gs["over"]:
        g[i] = v
    return g


def _rx(o):
    if isinstance(o, dict):
        return {("x" if k == "X" else k): _rx(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_rx(v) for v in o]
    return o


def write_dataset(path, header, rows):
    rows = [_rx(r) for r in rows]
    for r in rows:  # PO ruling batch 2 (2026-10-30): D3, D4, D5, D6, D9 settled as the primary readings
        if str(r.get("pending", "")).startswith("PENDING-RULING"):
            r["ruling"] = list(r["ruling"]) + ["PO-batch-2:" + r["pending"].split(":")[1]]
        if r.get("pending") != "PENDING-PO-RULING":
            r["pending"] = "RULED"
            r.pop("alt_expected", None)
    header = dict(header)
    header["row_count"] = len(rows)
    header["provenance"] = "SYNTHETIC"
    header["label"] = LABEL
    header["seed"] = SEED
    with open(path, "w", newline="\n", encoding="utf-8") as f:
        f.write(canon(header) + "\n")
        for r in rows:
            f.write(canon(r) + "\n")


def read_dataset(path):
    with open(path, encoding="utf-8") as f:
        lines = [json.loads(x) for x in f.read().split("\n") if x]
    return lines[0], lines[1:]
