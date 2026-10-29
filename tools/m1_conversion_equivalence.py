#!/usr/bin/env python3
"""M1 Stage 2: randomized equivalence of the new endpoint conversion against the pre-Stage-2 oracle.

Developer evidence only. Label: synthetic workload, relative engineering budget (no claim about recorded data).

The oracle is option_features.arithmetic_legacy, a verbatim copy of the origin/main conversion (its SHA-256 is
pinned by tests/features/test_stage2_endpoint_conversion.py). Every input is run through the oracle and through
the library's current functions; the normalised outcome (Decimal tuple, Fraction numerator/denominator,
PriceEnclosure fields, or exception type and arguments) must be equal. Input classes (all seeded, reproducible):

  ball       real arb balls: all five precision tiers, mantissas up to tier bits, magnitudes -9000..+4200 binary
             exponent (boundaries 4096/4097/-8192/-8193 forced), both signs, radius zero / relative / tiny
             absolute, midpoint zero, non-finite balls, and balls computed by exp/sqrt/log/erfc at the tier
  bound      duck-typed endpoints with mantissas up to 3000 bits (beyond any tier) and the same exponents
  rational   Fractions: random num/den up to 3200 bits, exact powers of ten and neighbours, 10^+-k with huge k
  decimal    Decimals for decimal_exact: random digits/exponents, zeros of both signs, NaN, sNaN, Infinity
  tuple      decimal_tuple(coefficient, exponent) with random trailing zeros and exponents -1500..1500

For ball and bound inputs BOTH directed roundings are checked on BOTH endpoints (enclosure, dyadic_endpoint
down and up), the lazy Ends object (fractions, ordering against random targets, materialised enclosure) is
checked against decimal_exact of the oracle's Decimals, and certify_exact is checked on the rationals.

  python tools/m1_conversion_equivalence.py [--n 1000000] [--workers 24] [--seed 20261029]
Exit status is non-zero on any mismatch. Runs across processes; the library itself stays single-threaded.
"""
import argparse
import concurrent.futures
import json
import os
import random
import sys
import time
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL = "synthetic workload, relative engineering budget"
KINDS = (("ball", 0.55), ("bound", 0.10), ("rational", 0.20), ("decimal", 0.10), ("tuple", 0.05))


def _paths():
    for p in (ROOT / "packages" / "features" / "src", ROOT / "packages" / "option-contracts" / "src"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))


class Bound:
    """Duck-typed arb endpoint (man_exp, is_finite) with Python integers."""
    def __init__(self, mantissa, exponent, finite=True):
        self.m, self.e, self.f = mantissa, exponent, finite

    def man_exp(self):
        return self.m, self.e

    def is_finite(self):
        return self.f


def norm(v):
    from option_feature_contracts import PriceEnclosure
    if isinstance(v, Decimal):
        return ("D", tuple(v.as_tuple()))
    if isinstance(v, Fraction):
        return ("F", v.numerator, v.denominator)
    if isinstance(v, PriceEnclosure):
        return ("E", v.method_id, v.method_version, norm(v.value_low), norm(v.value_high))
    if isinstance(v, float):
        return ("f", v.hex())
    if isinstance(v, (tuple, list)):
        return tuple(norm(x) for x in v)
    if hasattr(v, "value") and hasattr(v, "low") and hasattr(v, "high"):   # Certified
        return ("C", norm(v.value), norm(v.enclosure), norm(v.low), norm(v.high))
    return v


def call(f, *args):
    try:
        return ("ok", norm(f(*args)))
    except Exception as exc:  # outcome (type and args) must match too
        return ("exc", type(exc).__name__, tuple(str(a) for a in exc.args))


def rbits(rng, hi):
    """Random integer with 1..hi bits (log-uniform bit length)."""
    n = rng.randint(1, hi)
    return rng.getrandbits(n) | (1 << (n - 1))


def rmagnitude(rng):
    r = rng.random()
    if r < 0.12:
        return rng.choice((4094, 4095, 4096, 4097, 4098, -8190, -8191, -8192, -8193, -8194, 0, 1, -1, -1024, -1025, 1024))
    if r < 0.25:
        return rng.randint(-8300, -2500)
    if r < 0.40:
        return rng.randint(-2500, -100)
    if r < 0.55:
        return rng.randint(2000, 4200)
    return rng.randint(-100, 2000)


def make_ball(rng, arb, ctx, tiers):
    bits = rng.choice(tiers)
    ctx.prec = bits
    kind = rng.random()
    if kind < 0.04:
        return rng.choice((arb(float("inf")), arb(float("-inf")), arb(float("nan")), arb(0), arb("0 +/- 1e-9000")))
    if kind < 0.16:   # computed at the tier, as the solver does
        x = arb((rbits(rng, 40), rng.randint(-45, -3)))
        f = rng.choice(("exp", "sqrt", "log", "erfc", "mix"))
        if f == "mix":
            return (x * x + 1).log() * (-x).exp() / 3 + x.erfc() * arb(rbits(rng, 20)) / 7
        return getattr(x + (1 if f in ("sqrt", "log") else 0), f)()
    m = rbits(rng, bits + 12) * rng.choice((1, -1))
    mag = rmagnitude(rng)
    e = mag - abs(m).bit_length() + 1
    mid = arb((m, e))
    rk = rng.random()
    if rk < 0.15:
        rad = arb(0)
    elif rk < 0.75:
        rad = arb((rbits(rng, 30), mag - rng.randint(1, bits + 8)))
    else:
        rad = arb((rbits(rng, 30), rng.randint(-9000, 4100)))
    return arb(mid=mid, rad=rad)


def make_bound(rng):
    m = rbits(rng, rng.choice((53, 128, 512, 2048, 3000))) * rng.choice((1, -1, 1))
    if rng.random() < 0.05:
        m = 0
    mag = rmagnitude(rng)
    return Bound(m, mag - abs(m).bit_length() + 1 if m else rng.randint(-9000, 4200), rng.random() > 0.02)


def make_rational(rng):
    r = rng.random()
    s = rng.choice((1, -1))
    if r < 0.15:
        k = rng.choice((0, 1, 2, 5, 37, 126, 127, 128, 400, 1023, 1024, 1025, 1100, 1300, -1, -2, -37, -126, -127, -500, -1023, -1024, -1025, -1100, -1300, -3000, 3000))
        base = Fraction(10) ** k
        return s * (base + rng.choice((0, 0, 1, -1, 2)) * (Fraction(1, 10 ** 200) if k < 0 else Fraction(1, 7))) if rng.random() < 0.5 else s * base
    if r < 0.30:
        return Fraction(s * rbits(rng, 70), 10 ** rng.randint(0, 1100))
    if r < 0.45:
        return Fraction(s * rbits(rng, 3200), 1 << rng.randint(0, 3200))
    if r < 0.50:
        return Fraction(0)
    return Fraction(s * rbits(rng, 3200), rbits(rng, 3200))


def make_decimal(rng):
    r = rng.random()
    if r < 0.05:
        return rng.choice((Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal("-NaN")))
    if r < 0.12:
        return Decimal((rng.randint(0, 1), (0,) * rng.randint(1, 5), rng.randint(-50, 50)))
    digits = tuple(rng.randint(0, 9) for _ in range(rng.choice((1, 3, 17, 40, 127, 128, 129, 200))))
    return Decimal((rng.randint(0, 1), digits, rng.randint(-1100, 1100)))


def make_tuple(rng):
    c = rbits(rng, 440) * rng.choice((1, -1)) * 10 ** rng.choice((0, 0, 1, 3, 50, 300))
    if rng.random() < 0.05:
        c = 0
    return c, rng.randint(-1500, 1500)


def targets(rng, low_f, high_f):
    mid = (low_f + high_f) / 2
    pool = [low_f, high_f, mid, low_f - Fraction(1, 10 ** 30), high_f + Fraction(1, 10 ** 30), Fraction(0), Fraction(1), Fraction(-1),
            Fraction(rng.getrandbits(40), 1 << rng.randint(0, 40))]
    return pool


def run_chunk(spec):
    """spec = (seed, count, kinds_weights). Returns counts and the first mismatches."""
    seed, count, tiers = spec
    _paths()
    from flint import arb, ctx
    from option_features import arithmetic as new
    from option_features import arithmetic_legacy as old
    assert new.fast_endpoints_enabled(), "fast endpoint conversion must be enabled"
    rng = random.Random(seed)
    counts, bad = {}, []

    def check(kind, label, a, b, info):
        counts[kind] = counts.get(kind, 0) + 1
        if a != b:
            bad.append({"kind": kind, "what": label, "old": repr(a)[:300], "new": repr(b)[:300], "input": info, "seed": seed})

    names, weights = zip(*KINDS)
    for _ in range(count):
        kind = rng.choices(names, weights)[0]
        if kind == "ball":
            ball = make_ball(rng, arb, ctx, tiers)
            info = ball.str(radius=True, more=True)[:200] if ball.is_finite() else "nonfinite"
            check(kind, "enclosure", call(old.enclosure, ball), call(new.enclosure, ball), info)
            try:
                lo_b, hi_b = ball.lower(), ball.upper()
            except Exception:
                lo_b = hi_b = None
            if lo_b is not None:
                for bound in (lo_b, hi_b):
                    for upper in (False, True):
                        check(kind, "dyadic_endpoint up=%s" % upper, call(old.dyadic_endpoint, bound, upper), call(new.dyadic_endpoint, bound, upper), info)
            oe = call(old.enclosure, ball)
            ne = call(lambda b: new.enclosure_ends(b).enclosure(), ball)
            check(kind, "ends.enclosure", oe, ne, info)
            if oe[0] == "ok":
                oenc = old.enclosure(ball)
                lof, hif = old.decimal_exact(oenc.value_low), old.decimal_exact(oenc.value_high)
                ends = new.enclosure_ends(ball)
                check(kind, "ends.fractions", ("ok", norm((lof, hif))), call(lambda: ends.fractions()), info)
                for t in targets(rng, lof, hif):
                    expect = -1 if hif < t else (1 if lof > t else 0)
                    check(kind, "ends.sign_vs", ("ok", expect), call(ends.sign_vs, t), (info, str(t)[:60]))
                cert_old = call(old.certify, oenc)
                cert_new = call(lambda: new.certified_value(ends))
                if cert_old[0] == "ok":
                    check(kind, "certified_value", ("ok", cert_old[1][1]), cert_new, info)
                else:
                    check(kind, "certified_value", ("exc", cert_old[1], cert_old[2]), cert_new, info)
            else:
                check(kind, "ends.exception", oe, call(new.enclosure_ends, ball), info)
        elif kind == "bound":
            bound = make_bound(rng)
            info = (bound.m.bit_length(), bound.e, bound.f)
            for upper in (False, True):
                check(kind, "dyadic_endpoint up=%s" % upper, call(old.dyadic_endpoint, bound, upper), call(new.dyadic_endpoint, bound, upper), info)
        elif kind == "rational":
            v = make_rational(rng)
            info = "%d bits / %d bits" % (v.numerator.bit_length(), v.denominator.bit_length())
            for upper in (False, True):
                check(kind, "outward_decimal up=%s" % upper, call(old.outward_decimal, v, upper), call(new.outward_decimal, v, upper), info)
            check(kind, "certify_exact", call(old.certify_exact, v), call(new.certify_exact, v), info)
            check(kind, "exact_decimal", call(old.exact_decimal, v), call(new.exact_decimal, v), info)
        elif kind == "decimal":
            d = make_decimal(rng)
            check(kind, "decimal_exact", call(old.decimal_exact, d), call(new.decimal_exact, d), repr(d)[:100])
        else:
            c, e = make_tuple(rng)
            check(kind, "decimal_tuple", call(old.decimal_tuple, c, e), call(new.decimal_tuple, c, e), (str(c)[:50], e))
    return counts, bad


def run(n, workers, seed, tiers=(128, 256, 512, 1024, 2048)):
    chunk = max(1, min(5000, n // max(workers * 4, 1)))
    specs, left, i = [], n, 0
    while left > 0:
        k = min(chunk, left)
        specs.append((seed * 1000003 + i, k, tiers))
        left -= k
        i += 1
    total, bad = {}, []
    t0 = time.time()
    if workers <= 1:
        results = map(run_chunk, specs)
    else:
        ex = concurrent.futures.ProcessPoolExecutor(max_workers=workers)
        results = ex.map(run_chunk, specs)
    for counts, b in results:
        for k, v in counts.items():
            total[k] = total.get(k, 0) + v
        bad += b
    return {"label": LABEL, "evidence": "Developer evidence only", "inputs": n, "comparisons_by_class": total,
            "comparisons": sum(total.values()), "mismatches": len(bad), "first_mismatches": bad[:5], "seed": seed,
            "workers": workers, "seconds": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1_000_000)
    ap.add_argument("--workers", type=int, default=min(24, os.cpu_count() or 1))
    ap.add_argument("--seed", type=int, default=20261029)
    a = ap.parse_args()
    rep = run(a.n, a.workers, a.seed)
    print(json.dumps(rep, indent=1, sort_keys=True))
    return 1 if rep["mismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
