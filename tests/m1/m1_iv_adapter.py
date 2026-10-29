"""Test adapter: maps the independently authored M1 IV rows (m1_iv_cases.json, 41 rows) onto the library API.

Rows are never edited. `run_row` returns the library answer reshaped into the row's `expected`
vocabulary and `compare` reports the first difference. Library statuses are "available" and
"unavailable"; the rows say "value" and "unavailable". A reason without a mapping is a failure.

Mapping: contract_iv rows -> option_features.chainiv.IVChain.contract_iv
         atm_iv rows      -> IVChain.atm_iv(request.expiry_days)
         iv_30d rows      -> IVChain.iv_30d(request.target_days)
Tolerances are the rows' own (IV 1e-4 absolute, forward 1e-6 absolute), fixed by the Tester.
"""
from decimal import Decimal
import json
from pathlib import Path

ROWS_PATH = Path(__file__).resolve().parents[2] / "qualification" / "synthetic" / "m1" / "m1_iv_cases.json"
STATUS = {"available": "value", "unavailable": "unavailable"}


def load():
    return json.loads(ROWS_PATH.read_text(encoding="utf-8"))


def build_chain(row, solver=None, chain_cls=None):
    from option_features import chainiv
    inp, req = row["inputs"], row["request"]
    contracts = [chainiv.ChainContract(c["id"], c["expiry_days"], c["right"], c["strike"], c["bid"], c["ask"],
                                       c["event_ns"], c["known_at_ns"], c["style"], c["condition"])
                 for c in inp["contracts"]]
    kw = {"stale_limit_ns": req["stale_limit_ns"]}
    if solver is not None:
        kw["solver"] = solver
    return (chain_cls or chainiv.IVChain)(contracts, inp["spot"], inp["rate"], inp["dividend_yield"], req["cutoff_ns"], **kw)


def _flt(x):
    return None if x is None else float(x)


def run_row(row, chain=None):
    chain = chain or build_chain(row)
    op, req = row["op"], row["request"]
    if op == "contract_iv":
        return {"contracts": {k: {"status": STATUS[v.status], "reason": v.reason, "iv": _flt(v.iv), "label": v.label}
                              for k, v in chain.contract_iv().items()}}
    if op == "atm_iv":
        a = chain.atm_iv(req["expiry_days"])
        return {"status": STATUS[a.status], "reason": a.reason,
                "strike": None if a.strike is None else float(a.strike), "forward": a.forward,
                "call_iv": a.call_iv, "put_iv": a.put_iv, "iv": a.iv, "label": a.label}
    if op == "iv_30d":
        t = chain.iv_30d(req["target_days"])
        return {"status": STATUS[t.status], "reason": t.reason, "iv": t.iv, "label": t.label,
                "expiries_used": list(t.expiries_used), "method": t.method}
    raise KeyError(op)


def _num_diff(name, got, want, tol):
    if want is None or got is None:
        return None if want is None and got is None else "%s: got %r want %r" % (name, got, want)
    if abs(float(got) - float(Decimal(want))) > tol:
        return "%s: got %r want %s (tol %g)" % (name, got, want, tol)
    return None


def compare(row, got):
    exp = row["expected"]
    tol_iv = float(row["expected"].get("tolerance_iv", "0.0001"))
    if row["op"] == "contract_iv":
        want = exp["contracts"]
        tol_iv = float(want.get("tolerance_iv", tol_iv)) if isinstance(want.get("tolerance_iv"), str) else tol_iv
        want = {k: v for k, v in want.items() if k != "tolerance_iv"}
        if set(got["contracts"]) != set(want):
            return "contract ids differ"
        for k, w in want.items():
            g = got["contracts"][k]
            for f in ("status", "reason", "label"):
                if g[f] != w[f]:
                    return "%s %s: got %r want %r" % (k, f, g[f], w[f])
            d = _num_diff(k + " iv", g["iv"], w["iv"], tol_iv)
            if d:
                return d
        return None
    fields = ("status", "reason", "label") + (("method",) if row["op"] == "iv_30d" else ())
    for f in fields:
        if got[f] != exp[f]:
            return "%s: got %r want %r" % (f, got[f], exp[f])
    if row["op"] == "atm_iv":
        for f, tol in (("strike", 1e-9), ("forward", float(exp["tolerance_forward"])), ("call_iv", tol_iv),
                       ("put_iv", tol_iv), ("iv", tol_iv)):
            d = _num_diff(f, got[f], exp[f], tol)
            if d:
                return d
    else:
        d = _num_diff("iv", got["iv"], exp["iv"], tol_iv)
        if d:
            return d
        if got["expiries_used"] != exp["expiries_used"]:
            return "expiries_used: got %r want %r" % (got["expiries_used"], exp["expiries_used"])
    return None
