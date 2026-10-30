"""G5 prior-reading generator (SYNTHETIC, stdlib only, seeded, deterministic).

Library part: builders for prior frame / prior session readings used by the V4, V7 and V10
generators (reading time at or after the cutoff, sign changes through zero, zero prior,
threshold exactly at X, unavailable prior). CLI part: writes a small sample dataset
m3a_g5_priors.json (readings with their validity classification).
"""
import json
import os
import sys
from decimal import Decimal as D, ROUND_HALF_EVEN
from m3a_oracle3 import LABEL, CUT, quant, fs

DAY_NS = 86_400_000_000_000


def frame_prior(value, before_ns=60_000_000_000):
    return {"kind": "frame", "value": value, "time_ns": CUT - before_ns}


def session_prior(value, sid="S-01", n=1):
    return {"kind": "session", "value": value, "time_ns": CUT - n * DAY_NS, "session_id": sid}


def at_cutoff(kind="frame", value="0.2"):
    p = frame_prior(value) if kind == "frame" else session_prior(value)
    p["time_ns"] = CUT
    return p


def after_cutoff(kind="frame", value="0.2", ns=1_000_000_000):
    p = frame_prior(value) if kind == "frame" else session_prior(value)
    p["time_ns"] = CUT + ns
    return p


def prior_for_ratio(now_r8, pct):
    """prior such that (now-prior)/prior = pct percent (8 decimals)."""
    return fs(quant(D(now_r8) / (1 + D(pct) / 100), 8))


def int8(x):
    """annual decimal -> integer 1e-8 units (round half even)."""
    return int(quant(D(x), 8) * D(10 ** 8))


def sign_pairs():
    """(now, prior) annual skew pairs: through zero both ways, zero prior, zero now."""
    return [("0.03", "-0.02"), ("-0.03", "0.02"), ("0.03", "0.02"), ("-0.03", "-0.02"),
            ("0.03", "0"), ("-0.03", "0"), ("0", "0.02"), ("0", "-0.02")]


def sample():
    rows = []
    for kind in ("frame", "session"):
        rows.append({"id": "G5-%s-before" % kind, "reading": (frame_prior("0.2") if kind == "frame" else session_prior("0.2")),
                     "cutoff_ns": CUT, "valid": True, "code": None})
        rows.append({"id": "G5-%s-at-cutoff" % kind, "reading": at_cutoff(kind), "cutoff_ns": CUT,
                     "valid": False, "code": "prior_not_before_cutoff"})
        rows.append({"id": "G5-%s-after" % kind, "reading": after_cutoff(kind), "cutoff_ns": CUT,
                     "valid": False, "code": "prior_not_before_cutoff"})
    rows.append({"id": "G5-zero-prior", "reading": frame_prior("0"), "cutoff_ns": CUT, "valid": True,
                 "code": None, "note": "denominator 0 gives zero_denominator for V4"})
    rows.append({"id": "G5-none", "reading": None, "cutoff_ns": CUT, "valid": True, "code": None,
                 "note": "no prior reading: unavailable no_prior_reading"})
    for i, (n, p) in enumerate(sign_pairs()):
        rows.append({"id": "G5-sign-%d" % (i + 1), "now_skew": n, "prior_skew": p,
                     "sign_changed": (D(n) != 0 and D(p) != 0 and (D(n) > 0) != (D(p) > 0))})
    for pct in ("10", "-10", "9.99999999", "10.00000001"):
        rows.append({"id": "G5-ratio-%s" % pct, "now": "0.22", "prior": prior_for_ratio("0.22", pct), "pct": pct})
    return rows


def main():
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
    os.makedirs(out, exist_ok=True)
    doc = {"provenance": "SYNTHETIC", "qualification_label": LABEL, "generator": "gen_m3a_g5.py",
           "seed": 20261030, "schema_version": 1, "cutoff_ns": CUT, "rows": sample()}
    with open(os.path.join(out, "m3a_g5_priors.json"), "w", newline="\n", encoding="ascii") as f:
        f.write(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
