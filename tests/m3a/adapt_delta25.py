"""S03 adapter: maps author1 delta25 rows and the author4 size S/M/L workload chains to `delta25.delta25_point`.

Read only on qualification/synthetic/m3a. Never imports an author's reference or oracle; the author4 workload
GENERATOR (gen_m3a_workloads.chain / chain_truth) is imported to rebuild the frozen workload chains, as its
docstring prescribes, and its digest is checked against the manifest. Until S01's `m3a_harness` lands on main
this file reads the row files itself (plain JSON; author1 delta25 needs no tagged type, its `encoding` says so).
"""
import hashlib
import importlib
import json
import sys
from fractions import Fraction
from pathlib import Path

from option_features.chainiv import ChainContract, IVChain
from option_features.delta25 import delta25_point

ROOT = Path(__file__).resolve().parents[2]
M3A = ROOT / "qualification" / "synthetic" / "m3a"
AUTHOR1, AUTHOR4 = M3A / "author1", M3A / "author4"
SIDES = (("put", "put25_iv"), ("call", "call25_iv"))


def manifest_ok(folder, name):
    pinned = {}
    for line in (folder / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, fname = line.split(None, 1)
            pinned[fname.strip().lstrip("*")] = digest
    data = (folder / name).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest() == pinned.get(name)


def d25_rows():
    return json.loads((AUTHOR1 / "m3a_cases_delta25.json").read_text(encoding="utf-8"))["rows"]


def _contracts(raw):
    return [ChainContract(c["contract_id"], c["expiry_days"], c["right"], c["strike"], c["bid"], c["ask"],
                          c["event_ns"], c["known_at_ns"], c["style"], c["condition"]) for c in raw]


class Prepared:
    """One chain with its contract IVs solved once (cached) and the per-expiry, per-right eligible lists."""

    def __init__(self, contracts, spot, rate, dividend_yield, cutoff_ns):
        self.chain = IVChain(contracts, spot, rate, dividend_yield, cutoff_ns)
        self.ivs = self.chain.contract_iv()
        self.atm = self.chain.atm_iv_all()
        self.spot = Fraction(spot)
        self.rate = Fraction.from_float(float(rate))
        self.carry = Fraction.from_float(float(dividend_yield))
        self.legs = {}
        for c in contracts:
            got = self.ivs[c.contract_id]
            self.legs.setdefault((c.expiry_days, c.right), []).append(
                (Fraction(c.strike), got.iv if got.status == "available" else None))
        for v in self.legs.values():
            v.sort(key=lambda x: x[0])

    def point(self, days, right, convention="spot", **kw):
        atm = self.atm[days]
        if atm.status != "available":
            return None
        legs = self.legs.get((days, right), [])
        return delta25_point([k for k, _ in legs], [s for _, s in legs], atm.strike, self.spot, self.rate,
                             self.carry, days, right, convention, **kw)


def prepare_row(row):
    ch = row["inputs"]["chain"]
    return Prepared(_contracts(ch["contracts"]), ch["spot"], ch["rate"], ch["dividend_yield"], ch["cutoff_ns"])


def row_items(row):
    """(expiry_days, right, expected {status, reason, value}) for every 25-delta side the row lists on an
    AVAILABLE expiry (item-level check; the frame, coverage and reason order belong to S05)."""
    out = []
    for n, ex in sorted(((row["expected"].get("frame") or {}).get("expiries") or {}).items(), key=lambda x: int(x[0])):
        if ex.get("status") != "available":
            continue
        for right, key in SIDES:
            if key in ex:
                out.append((int(n), right, ex[key]))
    return out


def row_convention(row):
    params = row.get("params") or row["inputs"].get("params") or {}
    return params.get("delta_convention", "spot")


# ---------------------------------------------------------------- author4 workload chains (W03, W14)
def workload_module():
    """Import author4's generator by path; its sibling `m3a_common` is dropped from sys.modules afterwards so
    no other suite sees an author module under that top-level name."""
    sys.path.insert(0, str(AUTHOR4))
    saved = sys.modules.pop("m3a_common", None)
    try:
        return importlib.import_module("gen_m3a_workloads")
    finally:
        sys.path.remove(str(AUTHOR4))
        sys.modules.pop("m3a_common", None)
        if saved is not None:
            sys.modules["m3a_common"] = saved


def workload(size):
    gen = workload_module()
    ch = gen.chain(size)
    manifest = json.loads((AUTHOR4 / "m3a_workload_manifest.json").read_text(encoding="utf-8"))["chains"][size]
    digest = hashlib.sha256(gen.chain_bytes(ch)).hexdigest()
    if digest != manifest["facts"]["chain_sha256"]:
        raise AssertionError("workload chain %s digest %s differs from the manifest" % (size, digest))
    prepared = Prepared(_contracts(ch["contracts"]), ch["spot"], ch["rate"], ch["dividend_yield"], ch["cutoff_ns"])
    return prepared, gen.chain_truth(ch), manifest
