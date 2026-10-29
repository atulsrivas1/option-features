#!/usr/bin/env python3
"""Legacy byte status: evaluate the same R25 inputs with an old and a new source tree and diff the results.

    python tools/p1_legacy_diff.py OLD_ROOT NEW_ROOT [FIXTURE_JSON]

OLD_ROOT and NEW_ROOT are checkouts of this repository (for example the commit before P1 and the P1
branch). Each tree is imported in its own child interpreter (same python, which needs python-flint for
the model outputs). Inputs: (1) every case of the frozen R25 wire fixture (default
qualification/fixtures/r25-independent-wire-fixtures.json of NEW_ROOT, read as bytes), and (2) a seeded
grid of quotes for the spread outputs and the other quote consumers. A result is compared as its
canonical payload with the two embedded package-version fields masked; the report lists every result
that differs for another reason, which must be exactly the ruled P1 changes (bid <= 0 and locked spread).
Label: synthetic fixtures only; no claim beyond the compared inputs.
"""
import json
import subprocess
import sys
from pathlib import Path

CHILD = r'''
import json, sys, random
from decimal import Decimal
from dataclasses import replace
root, fixture = sys.argv[1], sys.argv[2]
sys.path[:0] = [root + "/packages/features/src", root + "/packages/option-contracts/src"]
from option_feature_contracts import (from_payload, to_payload, InputBinding, CivilDateBinding, Definition, Spot, ModelFact,
    Quote, Snapshot, Eligibility, SolverConfig, Request, R25_LIMITS, canonical_bytes)
from option_features import evaluate
import option_feature_contracts as C

def pay(r):
    d = to_payload(r)
    d["contracts_package_version"] = d["calculation_package_version"] = "MASKED"
    return json.dumps(d, sort_keys=True, separators=(",", ":"))

out = {}
data = json.loads(open(fixture, "rb").read())
for case in data["cases"]:
    s, q = from_payload("snapshot", case["snapshot_payload"]), from_payload("request", case["request_payload"])
    out["fixture:" + case["id"]] = [pay(r) for r in evaluate(s, q)]

YEAR = 31536000000000000
def base(quote, outputs, stale):
    d = Definition("c", "u", "call", Decimal("100"), "USD", Decimal("10"), "scalar_underlying", "basis", "european", "certified_vanilla_continuous_carry", "cash", YEAR, YEAR, YEAR, 719528, "UTC", "civil", "1", -1, None, 0, "b")
    snap = Snapshot("option-canonical1", (InputBinding("b", "synthetic-original", "1", "0" * 64, "synthetic", "original synthetic fixtures"),),
        (CivilDateBinding("civil", 0, 719163, "UTC", 0, "b"), CivilDateBinding("civil", YEAR, 719528, "UTC", 0, "b")),
        (d,), (Spot("u", Decimal("100"), "USD", "basis", 0, 0, "1", "b"),),
        tuple(ModelFact("u", None, k, v, "option-bsm1", "USD", "basis", -1, None, 0, "1", "b") for k, v in (("rate", 0.0), ("carry", 0.0), ("volatility", 0.3))),
        (quote,) if quote is not None else (), (), (), (), (), None)
    req = Request("option-request1", ("c",), tuple(outputs), "computed_only", "exact_only", 0, 0, 719163, "civil", "option-bsm1", "r25-formulas1", Eligibility(stale, YEAR, YEAR), SolverConfig("bisection1", "midpoint", 8.0, 256, 1e-10, 1e-10, 1e-10, 1e-10), R25_LIMITS)
    return snap, req

vals = [None, "-2", "-0.01", "0", "0.01", "0.05", "1", "2", "2.02", "3"]
n = 0
for bid in vals:
    for ask in vals:
        for age in (0, 5, 11):
            quote = Quote("c", None, None if bid is None else Decimal(bid), None if ask is None else Decimal(ask), "USD", "per_underlying_payoff_unit", -age, -age, 0, "1", "b")
            for outputs in (["liquidity.spread_bps"], ["volatility.implied_volatility"], ["greeks.delta", "contract.moneyness", "pricing.price"]):
                if "liquidity.spread_bps" not in outputs and age:
                    continue
                snap, req = base(quote, outputs, 10)
                out["grid:%s|%s|%d|%s" % (bid, ask, age, outputs[0])] = [pay(r) for r in evaluate(snap, req)]
                n += 1
json.dump(out, sys.stdout)
'''


def run(root, fixture):
    proc = subprocess.run([sys.executable, "-B", "-c", CHILD, str(root), str(fixture)], capture_output=True, text=True)
    if proc.returncode:
        sys.exit("child failed for %s:\n%s" % (root, proc.stderr[-2000:]))
    return json.loads(proc.stdout)


def main():
    old, new = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    fixture = Path(sys.argv[3]) if len(sys.argv) > 3 else new / "qualification" / "fixtures" / "r25-independent-wire-fixtures.json"
    a, b = run(old, fixture), run(new, fixture)
    same = sorted(k for k in a if a[k] == b[k])
    diff = sorted(k for k in a if a[k] != b[k])
    fixture_total = sum(1 for k in a if k.startswith("fixture:"))
    fixture_diff = [k for k in diff if k.startswith("fixture:")]
    grid_diff = [k for k in diff if k.startswith("grid:")]
    print("compared %d fixture cases and %d grid inputs (package-version fields masked)" % (fixture_total, len(a) - fixture_total))
    print("identical: %d; different: %d" % (len(same), len(diff)))
    print("fixture cases that differ (%d of %d): %s" % (len(fixture_diff), fixture_total, ", ".join(k[8:] for k in fixture_diff) or "none"))
    spread_only = all(k.endswith("|liquidity.spread_bps") for k in grid_diff)
    print("grid differences are all liquidity.spread_bps: %s (%d)" % (spread_only, len(grid_diff)))
    ruled = []
    for k in grid_diff:
        bid, ask = k[5:].split("|")[:2]
        is_ruled = (bid not in ("None",) and float(bid) <= 0) or (bid != "None" and ask != "None" and float(bid) == float(ask))
        if not is_ruled:
            ruled.append(k)
    print("grid differences outside the ruled set (bid <= 0, locked): %s" % (ruled or "none"))
    if "--list" in sys.argv:
        for k in diff:
            print("  differs:", k)


if __name__ == "__main__":
    main()
