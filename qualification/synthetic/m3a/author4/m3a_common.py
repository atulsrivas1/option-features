"""Shared plumbing for the Option Features M3a fixture author 4 (stdlib only, SYNTHETIC).
Nothing here computes an expected value; it only encodes, decodes, hashes and writes."""
import hashlib
import json
from datetime import date, timedelta
from fractions import Fraction
from decimal import Decimal

PROVENANCE = "SYNTHETIC"
QUAL = ("mock-data qualification only: passed on independently authored synthetic fixtures "
        "and synthetic workloads, Windows x64, CPython 3.12")
PERF_LABEL = "synthetic workload, relative engineering budget"
DEFAULT_SEED = 20261030
M64 = (1 << 64) - 1


def cj(o):
    """Canonical JSON: sorted keys, no spaces, ASCII."""
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha(b):
    return hashlib.sha256(b).hexdigest()


class SplitMix:
    def __init__(self, seed):
        self.s = seed & M64

    def next(self):
        self.s = (self.s + 0x9E3779B97F4A7C15) & M64
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M64
        return z ^ (z >> 31)

    def below(self, n):
        return self.next() % n


def tag(v):
    """Python value -> JSON-safe value with the M2 tagged objects (R-65)."""
    if isinstance(v, Decimal):
        return {"py_type": "Decimal", "text": str(v)}
    if isinstance(v, Fraction):
        return {"py_type": "Fraction", "text": "%d/%d" % (v.numerator, v.denominator)}
    if isinstance(v, (bytes, bytearray)):
        return {"py_type": "bytes", "hex": bytes(v).hex()}
    if isinstance(v, float) and (v != v or v in (float('inf'), float('-inf'))):
        return {'py_type': 'float', 'text': 'nan' if v != v else ('inf' if v > 0 else '-inf')}
    if isinstance(v, dict):
        return {k: tag(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [tag(x) for x in v]
    return v


def untag(v):
    if isinstance(v, dict):
        t = v.get("py_type")
        if t == "Decimal" and set(v) == {"py_type", "text"}:
            return Decimal(v["text"])
        if t == "Fraction" and set(v) == {"py_type", "text"}:
            n, d = v["text"].split("/")
            return Fraction(int(n), int(d))
        if t == "float" and set(v) == {"py_type", "text"}:
            return float(v["text"])
        if t == "bytes" and set(v) == {"py_type", "hex"}:
            return bytes.fromhex(v["hex"])
        return {k: untag(x) for k, x in v.items()}
    if isinstance(v, list):
        return [untag(x) for x in v]
    return v


def calendar(n=40, half_day_index=9):
    """n ISO weekdays from 2026-01-05; one half-day (210 minutes), others 390."""
    out, d = [], date(2026, 1, 5)
    while len(out) < n:
        if d.weekday() < 5:
            out.append([d.isoformat(), 210 if len(out) == half_day_index else 390])
        d += timedelta(days=1)
    return out


def header(family, seed, rows, extra=None):
    h = {"provenance": PROVENANCE, "label": QUAL, "dataset": "m3a_cases_" + family,
         "family": family, "seed": seed, "row_count": len(rows),
         "encoding": "header line, then one canonical JSON row per line, LF, ASCII; non-JSON types as M2 tagged objects"}
    if extra:
        h.update(extra)
    return h


def write_rows(path, family, seed, rows, extra=None):
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write(cj(header(family, seed, rows, extra)) + "\n")
        for r in rows:
            f.write(cj(r) + "\n")


def read_rows(path):
    with open(path, encoding="ascii", newline="") as f:
        lines = f.read().split("\n")
    assert lines[-1] == ""
    return json.loads(lines[0]), [json.loads(x) for x in lines[1:-1]]
