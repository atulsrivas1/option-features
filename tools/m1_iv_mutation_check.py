"""Mutation check for option_features.chainiv against the 41 independently authored IV rows.

Each mutant is the real chainiv source with one textual change (the change must match exactly once),
executed as a separate module and run over every row through tests/m1/m1_iv_adapter.py. A mutant is
CAUGHT when at least one row differs or raises. V-ids are the Tester's list in AUTHORING_NOTES.md
(V1-V10, V12, V13, V14; V11 does not exist). X-ids are Developer additions; an X mutant that survives is
reported as a coverage gap, not hidden. Usage: python tools/m1_iv_mutation_check.py  (PYTHONPATH = both src dirs)
Developer evidence only; the Tester re-runs its own mutation check.
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tests" / "m1")]
import m1_iv_adapter as A  # noqa: E402

SRC = (ROOT / "packages" / "features" / "src" / "option_features" / "chainiv.py").read_text(encoding="utf-8")

M = []  # (id, description, old, new)


def mut(mid, desc, old, new):
    M.append((mid, desc, old, new))


mut("V1", "ATM picks the strike nearest spot, not forward",
    "self._prepare(e).fwd.nearest(both)", "_Forward(self._spot_ticks, Fraction(0)).nearest(both)")
mut("V2", "tie goes to the upper strike", "self.cmp(lo + hi, 2) >= 0", "self.cmp(lo + hi, 2) > 0")
mut("V3", "ATM IV is the call IV only", "(call_iv + put_iv) / 2, label)", "call_iv, label)")
mut("V4", "30-day interpolates linearly in IV",
    "sqrt(variance / target)", "a_lo.iv + (a_hi.iv - a_lo.iv) * (target - lo) / (hi - lo)")
mut("V5", "approximate label dropped for American",
    '            label = LABEL_APPROX\n        else:\n            return ContractIV("unavailable", "style_unknown"',
    '            label = LABEL_EXACT\n        else:\n            return ContractIV("unavailable", "style_unknown"')
mut("V6", "american_itm dropped", 'return ContractIV("unavailable", "american_itm", None, None)', "pass")
mut("V7", "extrapolation: flat IV from the nearest listed expiry when no bracket",
    '        if not lower or not upper:\n            return IV30("unavailable", "no_bracketing_expiry", None, None, (), None)',
    '        if not lower or not upper:\n            n = min(self._expiries, key=lambda d: abs(d - target))\n            a = self._atm_iv(n)\n'
    '            return IV30("available", None, a.iv, a.label, (n,), "extrapolated") if a.status == "available" else IV30("unavailable", a.reason, None, None, (), None)')
mut("V8", "exact 30-day expiry ignored (always interpolate)", "if target in self._expiries:", "if False:")
mut("V9", "strikes with one right are eligible for ATM",
    "ci is not None and pi is not None and items[ci][3] == G_OK and items[pi][3] == G_OK",
    "(ci is not None and items[ci][3] == G_OK) or (pi is not None and items[pi][3] == G_OK)")
mut("V10", "quote gates ignored when both sides are present",
    "gate = _spread_gate(bid, ask, cutoff_ns - c.event_ns, stale_limit_ns)",
    "gate = G_OK if (bid is not None and ask is not None) else _spread_gate(bid, ask, cutoff_ns - c.event_ns, stale_limit_ns)")
mut("V12", "unknown style treated as American (contract)", 'elif style == "american":', 'elif style != "european":')
mut("V13", "American nearest strike taken among both-right strikes only",
    "e._nearest = self._prepare(e).fwd.nearest(self._all_strikes(e))",
    "e._nearest = self._prepare(e).fwd.nearest(sorted(k for k, v in e.legs.items() if v[0] is not None and v[1] is not None) or self._all_strikes(e))")
mut("V14", "ineligible bracketing expiries skipped (next expiry used)",
    "lower = [d for d in self._expiries if d < target]\n        upper = [d for d in self._expiries if d > target]",
    "lower = [d for d in self._expiries if d < target and self._atm_iv(d).status == 'available']\n"
    "        upper = [d for d in self._expiries if d > target and self._atm_iv(d).status == 'available']")
# Developer additions
mut("X1", "ATM style_unknown check removed", 'if any(c.style not in ("european", "american") for c in legs):', "if False:")
mut("X2", "ATM label always exact", 'label = LABEL_APPROX if any(c.style == "american" for c in legs) else LABEL_EXACT', "label = LABEL_EXACT")
mut("X3", "30-day label always exact", "label = LABEL_APPROX if LABEL_APPROX in (a_lo.label, a_hi.label) else LABEL_EXACT", "label = LABEL_EXACT")
mut("X4", "stale limit inclusive (age == limit is stale)", "cutoff_ns - c.event_ns, stale_limit_ns", "cutoff_ns - c.event_ns, stale_limit_ns - 1")
mut("X5", "call ITM test inverted", '(c.right == "call" and sign < 0) or (c.right == "put" and sign > 0)',
    '(c.right == "call" and sign > 0) or (c.right == "put" and sign < 0)')
mut("X6", "time basis 360", "e.T = Fraction(e.days, 365)", "e.T = Fraction(e.days, 360)")
mut("X7", "forward ignores the dividend yield", "(self._rate - self._carry) * e.T", "self._rate * e.T")
mut("X8", "variance weights use the wrong end", "(target - lo) / (hi - lo)", "(hi - target) / (hi - lo)")
mut("X9", "ATM ignores quote gates in the strike pool", "items[ci][3] == G_OK and items[pi][3] == G_OK", "True")
mut("X10", "excluded_condition not applied", 'elif c.condition != "regular":', "elif False:")
mut("X11", "known_at after the cutoff still visible", "if known > cutoff_ns or (bid is None and ask is None):", "if (bid is None and ask is None):")
mut("X12", "contract IV midpoint uses the bid only", "(bid + ask) if gate == eligible_gate", "(bid + bid) if gate == eligible_gate")
mut("X13", "exact-expiry no_atm_strike reported as no_bracketing_expiry",
    'return IV30("unavailable", a.reason, None, None, (), None)\n            return IV30("available", None, a.iv, a.label, (target,), "as_is")',
    'return IV30("unavailable", "no_bracketing_expiry", None, None, (), None)\n            return IV30("available", None, a.iv, a.label, (target,), "as_is")')
mut("X14", "tie rule decided on the float forward only", "return lo if self.cmp(lo + hi, 2) >= 0 else hi",
    "return lo if (lo + hi) - 2 * (self.f if self.f is not None else 0.0) > 0 else hi")


def build(old, new):
    if SRC.count(old) != 1:
        raise SystemExit("mutation anchor not unique (%d): %r" % (SRC.count(old), old[:70]))
    mod = types.ModuleType("option_features._mutant")
    mod.__package__ = "option_features"
    exec(compile(SRC.replace(old, new), "chainiv_mutant", "exec"), mod.__dict__)
    return mod


def catching_rows(mod, rows):
    hit = []
    for row in rows:
        try:
            diff = A.compare(row, A.run_row(row, A.build_chain(row, chain_cls=mod.IVChain)))
        except Exception as exc:  # a crash is a detection
            diff = "raised %s" % type(exc).__name__
        if diff:
            hit.append(row["id"])
    return hit


def caught_by_extra_tests(mod):
    """Run tests/m1/test_chainiv_extra.py against the mutant (survivors of the rows only). True if any test fails."""
    import importlib
    import io
    import unittest
    import option_features
    real = sys.modules.get("option_features.chainiv"), option_features.chainiv
    sys.modules["option_features.chainiv"] = option_features.chainiv = mod
    sys.modules.pop("test_chainiv_extra", None)
    try:
        suite = unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module("test_chainiv_extra"))
        result = unittest.TextTestRunner(stream=io.StringIO()).run(suite)
        return not result.wasSuccessful()
    finally:
        sys.modules["option_features.chainiv"], option_features.chainiv = real
        sys.modules.pop("test_chainiv_extra", None)


def main():
    rows = A.load()["rows"]
    control = catching_rows(build("LABEL_EXACT = ", "LABEL_EXACT = "), rows)
    print("control (unmutated): %d rows differ (must be 0)" % len(control))
    survivors, missed_v = [], []
    for mid, desc, old, new in M:
        hit = catching_rows(build(old, new), rows)
        more = " (+%d)" % (len(hit) - 6) if len(hit) > 6 else ""
        print("%-4s %-8s %2d rows: %s%s  | %s" % (mid, "CAUGHT" if hit else "SURVIVED", len(hit), ", ".join(hit[:6]), more, desc))
        if not hit:
            extra = mid.startswith("X") and caught_by_extra_tests(build(old, new))
            print("       %s by tests/m1/test_chainiv_extra.py" % ("CAUGHT" if extra else "NOT caught"))
            if not extra:
                (missed_v if mid.startswith("V") else survivors).append(mid)
    x_total = sum(1 for m in M if m[0].startswith("X"))
    print("V mutants (Tester list, 13): %s" % ("all caught" if not missed_v else "SURVIVED " + ", ".join(missed_v)))
    print("X mutants (Developer additions; rows plus extra tests): %d of %d caught; survivors: %s" % (x_total - len(survivors), x_total, ", ".join(survivors) or "none"))
    return 1 if control or missed_v else 0


if __name__ == "__main__":
    sys.exit(main())
