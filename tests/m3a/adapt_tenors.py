"""Adapter for S04 (tenors): maps TEN rows (author1, read only) onto option_features.tenors. Item-level checks
only; S05 first-owns the whole TEN rows. No import of any author's reference code.

Per-expiry inputs: ATM IV from the certified M1 IVChain on the row's chain; the expiry status and reason from the
row's expected frame.expiries (coverage gates belong to S05, not S04).
Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12
"""
import json
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

from option_features.chainiv import ChainContract, IVChain
from option_features import tenors as T

ROOT = Path(__file__).resolve().parents[2]
TEN = ROOT / "qualification" / "synthetic" / "m3a" / "author1" / "m3a_cases_tenors.json"


def load_rows():
    return json.loads(TEN.read_bytes())["rows"]


def r8(x):
    """half-even 8 decimals of a binary64 (test-local; the shared helper is S01's)."""
    return str(Decimal(x).quantize(Decimal("1e-8"), rounding=ROUND_HALF_EVEN))


def chain_of(row):
    ch = row["inputs"]["chain"]
    contracts = [ChainContract(**c) for c in ch["contracts"]]
    return IVChain(contracts, ch["spot"], ch["rate"], ch["dividend_yield"], ch["cutoff_ns"],
                   row["params"]["stale_limit_ns"])


def expiry_inputs(row):
    atm = chain_of(row).atm_iv_all()
    out = []
    for d, e in sorted(row["expected"]["frame"]["expiries"].items(), key=lambda kv: int(kv[0])):
        d = int(d)
        if e["status"] == "available":
            out.append((d, "available", None, atm[d].iv))
        else:
            out.append((d, "unavailable", e["reason"], None))
    return out


def run_row(row):
    res = T.tenors(expiry_inputs(row), tuple(row["params"]["tenors"]))
    frame = {}
    for t, r in res.items():
        frame[str(t)] = {"status": r.status, "reason": r.reason, "iv": None if r.iv is None else r8(r.iv),
                         "method": r.method,
                         "expiries_used": None if r.expiries_used is None else list(r.expiries_used)}
    return frame
