"""Independent R25 candidate oracle; never imports production calculations.

SOURCE ONLY until separately reviewed and explicitly executed in a free resource
window. Running this tool creates candidate evidence, not accepted wire fixtures.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import sys

VERSION = "r25-mpmath-oracle-1"
PRECISIONS = (80, 140)
RETAIN_DIGITS = 65
UNITS = {
    "pricing.price": "currency_per_underlying_payoff_unit",
    "greeks.signed_delta": "signed_delta",
    "greeks.delta": "absolute_delta",
    "greeks.gamma": "inverse_currency",
    "greeks.vega": "currency_per_unit_sigma",
    "greeks.rho": "currency_per_unit_rate",
    "greeks.theta": "currency_per_year",
}
# Original supplied synthetic examples. All operands are exact rational strings.
# Fixed bounded inventory; this is not a general arbitrary-input service.
INTERIORS = [
    ("ATM", "100", "100", "0", "0", "2", "1"),
    ("CARRY", "103", "97", "3/100", "1/100", "1/4", "3/2"),
    ("NEGATIVE", "91", "109", "-1/50", "-3/100", "2/5", "2"),
    ("SHORT", "101", "100", "1/100", "0", "3/10", "1/365"),
    ("LONG", "100", "102", "1/25", "1/50", "1/10", "10"),
    ("ITM", "150", "100", "0", "1/100", "1/4", "1"),
    ("OTM", "75", "120", "1/100", "0", "1/4", "1"),
]


def rational(ctx, text):
    """Convert rational text via integer components, never via binary float."""
    if not isinstance(text, str) or len(text) > 128:
        raise ValueError("bounded rational string required")
    value = Fraction(text)
    return ctx.mpf(value.numerator) / ctx.mpf(value.denominator)


def price(ctx, side, S, K, r, q, sigma, T):
    """Independent erfc pricing path; endpoint rules handled elsewhere."""
    eta = 1 if side == "call" else -1
    z = sigma * ctx.sqrt(T)
    d1 = (ctx.log(S / K) + (r - q + sigma * sigma / 2) * T) / z
    d2 = d1 - z
    cdf = lambda x: ctx.erfc(-x / ctx.sqrt(2)) / 2
    return eta * (S * ctx.exp(-q*T) * cdf(eta*d1)
                  - K * ctx.exp(-r*T) * cdf(eta*d2))


def interior(ctx, side, operands):
    S, K, r, q, sigma, T = [rational(ctx, x) for x in operands]
    eta = 1 if side == "call" else -1
    A, B = S * ctx.exp(-q*T), K * ctx.exp(-r*T)
    root = ctx.sqrt(T)
    d1 = (ctx.log(S/K) + (r-q+sigma*sigma/2)*T)/(sigma*root)
    d2 = d1 - sigma*root
    # Greek CDF uses erf, independently of the price path's erfc calls.
    cdf = lambda x: (1 + ctx.erf(x/ctx.sqrt(2)))/2
    density = ctx.exp(-d1*d1/2) / ctx.sqrt(2*ctx.pi)
    delta = eta * ctx.exp(-q*T) * cdf(eta*d1)
    result = {
        "pricing.price": price(ctx, side, S, K, r, q, sigma, T),
        "greeks.signed_delta": delta, "greeks.delta": abs(delta),
        "greeks.gamma": ctx.exp(-q*T)*density/(S*sigma*root),
        "greeks.vega": A*density*root,
        "greeks.rho": eta*T*B*cdf(eta*d2),
        "greeks.theta": -A*density*sigma/(2*root)
                         + eta*q*A*cdf(eta*d1)-eta*r*B*cdf(eta*d2),
    }
    fS = lambda s: price(ctx, side, s, K, r, q, sigma, T)
    derivatives = {
        "greeks.signed_delta": ctx.diff(fS, S),
        "greeks.gamma": ctx.diff(fS, S, 2),
        "greeks.vega": ctx.diff(lambda v: price(ctx, side, S, K, r, q, v, T), sigma),
        "greeks.rho": ctx.diff(lambda rate: price(ctx, side, S, K, rate, q, sigma, T), r),
        "greeks.theta": -ctx.diff(lambda t: price(ctx, side, S, K, r, q, sigma, t), T),
    }
    for key, value in derivatives.items():
        agree(ctx, value, result[key], "1e-50", "1e-80", key + " derivative")
    # Fixed-step central finite differences complement mpmath.diff. Execute at
    # high precision only; no adaptive convergence loop or kink approximation.
    if ctx.dps == 140:
        for step in ("1e-20", "1e-25"):
            h = rational(ctx, step) * S
            f0, fp, fm = fS(S), fS(S+h), fS(S-h)
            agree(ctx, (fp-fm)/(2*h), delta, "1e-35", "1e-65", "FD delta")
            agree(ctx, (fp-2*f0+fm)/(h*h), result["greeks.gamma"],
                  "1e-35", "1e-65", "FD gamma")
    other = "put" if side == "call" else "call"
    parity = result["pricing.price"] - price(ctx, other, S, K, r, q, sigma, T)
    agree(ctx, parity, eta*(A-B), "1e-60", "1e-90", "put-call parity")
    return result


def agree(ctx, a, b, relative, absolute, label):
    if not ctx.isfinite(a) or not ctx.isfinite(b):
        raise ArithmeticError(label + ": nonfinite oracle")
    if abs(a-b) > rational(ctx, absolute) + rational(ctx, relative)*max(abs(a), abs(b)):
        raise ArithmeticError(label + ": oracle agreement budget exceeded")


def endpoint(ctx, side, Stext, sigma_text, Ttext):
    """Separate symbolic endpoints: K=100,r=q=0; no smooth approximation."""
    S, K = rational(ctx, Stext), ctx.mpf(100)
    sigma, T = rational(ctx, sigma_text), rational(ctx, Ttext)
    eta = 1 if side == "call" else -1
    H = S-K
    itm = eta*H > 0
    values = {key: ctx.mpf(0) for key in UNITS}
    values["pricing.price"] = max(eta*H, ctx.mpf(0))
    statuses = {}
    if H:
        values["greeks.signed_delta"] = ctx.mpf(eta if itm else 0)
        values["greeks.delta"] = abs(values["greeks.signed_delta"])
        if T:
            values["greeks.rho"] = eta*T*K if itm else ctx.mpf(0)
    else:
        reason = "nondifferentiable_payoff" if T == 0 else "nondifferentiable_zero_volatility"
        for key in ("greeks.signed_delta", "greeks.delta", "greeks.gamma"):
            values.pop(key)
            statuses[key] = ("undefined", reason)
        if T:
            values.pop("greeks.rho")
            statuses["greeks.rho"] = ("undefined", reason)
            values["greeks.vega"] = S*ctx.sqrt(T)/ctx.sqrt(2*ctx.pi)
        elif sigma:
            values.pop("greeks.theta")
            statuses["greeks.theta"] = ("undefined", "nonfinite_terminal_time_derivative")
    return values, statuses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-commit", required=True, help="exact reviewed 40-hex source commit")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit):
        parser.error("source commit must be 40 lowercase hexadecimal characters")
    # Force reproducible pure-Python backend before the first numerical import.
    if "mpmath" in sys.modules:
        raise RuntimeError("run in a fresh interpreter; mpmath already imported")
    os.environ["MPMATH_NOGMPY"] = "1"
    os.environ["MPMATH_NOSAGE"] = "1"
    os.environ.pop("MPMATH_SAGE", None)
    if importlib.metadata.version("mpmath") != "1.3.0":
        raise RuntimeError("oracle requires exactly mpmath==1.3.0")
    import mpmath  # Deliberately deferred: source inspection needs no import.
    from mpmath.libmp.backend import BACKEND
    if BACKEND != "python":
        raise RuntimeError("oracle requires verified pure-Python backend")
    contexts = [mpmath.mp.clone() for _ in PRECISIONS]
    for ctx, digits in zip(contexts, PRECISIONS):
        ctx.dps = digits
    high = contexts[-1]
    cases = []

    def record(case_id, operands, results, statuses=None):
        low_values, high_values = results
        if low_values.keys() != high_values.keys():
            raise ArithmeticError("precision changed output inventory")
        outputs = []
        for key in sorted(high_values):
            hi = high_values[key]
            # String bridge preserves the low run's decimal value and avoids a
            # context-rounded conversion of its internal binary representation.
            lo = high.mpf(contexts[0].nstr(low_values[key], 82))
            # Pure relative budget preserves nonzero tails; exact zeros must
            # agree exactly. This agreement is empirical, not interval proof.
            agree(high, lo, hi, "1e-60", "0", case_id + "/" + key)
            literal = high.nstr(hi, RETAIN_DIGITS, strip_zeros=False)
            outputs.append({"output": key, "status": "available", "reason": "ok",
                            "unit": UNITS[key], "oracle_decimal": literal,
                            "error": {"kind": "empirical_two_precision_agreement",
                                      "relative_budget": "1e-60", "absolute_budget": "0",
                                      "rigorous_enclosure": False}})
        for key, (status, reason) in sorted((statuses or {}).items()):
            outputs.append({"output": key, "unit": UNITS[key], "status": status,
                            "reason": reason, "oracle_decimal": None,
                            "error": {"kind": "symbolic_endpoint_status"}})
        cases.append({"id": case_id, "state": "candidate_oracle_generated_not_accepted",
                      "operand_domain": "exact_rational_mathematical_example_not_wire_instantiated",
                      "operands_exact_rational": operands, "outputs": outputs})

    for name, *operands in INTERIORS:
        for side in ("call", "put"):
            record("ORACLE-"+name+"-"+side.upper(),
                   dict(zip(("S", "K", "r", "q", "sigma", "T"), operands), side=side),
                   [interior(ctx, side, operands) for ctx in contexts])
    for side in ("call", "put"):
        for S in ("90", "100", "110"):
            for sigma, T in (("0", "0"), ("1/4", "0"), ("0", "1")):
                evaluated = [endpoint(ctx, side, S, sigma, T) for ctx in contexts]
                if evaluated[0][1] != evaluated[1][1]:
                    raise ArithmeticError("endpoint statuses changed with precision")
                record("ORACLE-ENDPOINT-"+side+"-"+S+"-"+sigma.replace("/", "_")+"-"+T,
                       {"side": side, "S": S, "K": "100", "r": "0", "q": "0",
                        "sigma": sigma, "T": T}, [x[0] for x in evaluated], evaluated[1][1])
    root = Path(__file__).resolve().parents[1]
    design_path = root/"docs/r25/INDEPENDENT_FIXTURES.json"
    design = json.loads(design_path.read_text(encoding="utf-8"))
    designed = list(design["cases"]) + list(design["chain_score_proposal"]["cases"])
    # Never evaluate documentary expressions with eval or count copied statuses
    # as executed checks. Complete wire/semantic/IV fixture generation is later.
    not_generated = [{"id": c["id"], "state": "not_generated",
                      "reason": "design_template_requires_separate_wire_or_inverse_instantiation"}
                     for c in designed]
    payload = {
        "schema_version": 1, "state": "candidate_oracle_not_release_acceptance",
        "generator": {"id": VERSION, "source_commit": args.source_commit,
                      "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      "design_sha256": hashlib.sha256(design_path.read_bytes()).hexdigest(),
                      "dependency": "mpmath==1.3.0", "backend": "python_no_gmpy",
                      "precision_decimal_digits": list(PRECISIONS),
                      "retained_significant_digits": RETAIN_DIGITS,
                      "retention_note": "Last five retained digits are guard/display digits beyond the 1e-60 agreement budget; not all 65 digits are verified.",
                      "python": sys.version, "platform": platform.platform(),
                      "production_imports": False},
        "cases": cases, "design_cases_not_generated": not_generated,
        "limitations": ["Empirical precision agreement is not a rigorous interval bound.",
                        "Exact rational examples are not binary64 ModelFact wire targets.",
                        "No binary64 rounding certification or production IV error proof.",
                        "Independent source review and executed receipts remain necessary."]}
    content = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)+"\n").encode("utf-8")
    # Digest covers exact canonical payload bytes, separate from its envelope.
    envelope = {"payload_sha256": hashlib.sha256(content).hexdigest(), "payload": payload}
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(envelope, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
