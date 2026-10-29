#!/usr/bin/env python3
"""Adversarial contract sets for the M1 Stage 1 float filter (Developer-authored; stdlib only, seeded).

Label: synthetic workload, relative engineering budget. Independent of the library (own float pricer), so
the same list is produced for the base and the changed checkout. A contract is a dict with decimal-text
spot/strike/rate/div/price, exact time "T" as "p/q" and right "C"/"P".

Families (all deterministic for ADV_SEED):
  tie      price = float price at a dyadic sigma (hit exactly by a bisection midpoint) + offset in error
           units (u*SCALE, see docs/M1_STAGE1_FLOAT_FILTER_BOUND.md); offsets from -100 to +100 units, so
           the target sits inside and outside the filter bound at an iteration where only the sign decides
  root     price at a random sigma +- tiny relative offsets (near-converged ties at the tolerance)
  edge     price at the lower and upper admissible bounds +- small offsets, exact intrinsic, tiny prices
  extreme  extreme vol (0.001 .. 100 at the price), extreme moneyness, tiny and long T, negative rates,
           huge and tiny spot, 17-digit targets
  domain   outside the filter domain on purpose (spot 1e25, T = 1e-12, rate*T large): must fall back
"""
import math
import random

ADV_SEED = 20261030
U = 2.0 ** -40
OFFSETS = (-100.0, -10.0, -3.0, -1.0, -0.5, -0.1, 0.0, 0.1, 0.5, 1.0, 3.0, 10.0, 100.0)
MUTATION_OFFSETS = (0.2, 0.4, 0.6, 0.8)   # strictly between 0 and (injected 5 - shrunk bound 4) units


def _ncdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def fprice(S, K, T, r, q, sig, eta):
    """Plain float Black-Scholes and the error unit u*(A+B)*(1+Z) (same scale as the library filter)."""
    sT = math.sqrt(T)
    vs = sig * sT
    ln = math.log(S / K)
    d1 = (ln + (r - q + 0.5 * sig * sig) * T) / vs
    d2 = d1 - vs
    A, B = S * math.exp(-q * T), K * math.exp(-r * T)
    p = eta * (A * _ncdf(eta * d1) - B * _ncdf(eta * d2))
    z = (abs(ln) + (abs(r) + abs(q)) * T + sig * sig * T + 1.0) / vs
    return p, U * (A + B) * (1.0 + z)


def _txt(x):
    return format(x, ".17g")


def _fmt(v, places):
    return format(round(v, places), "f")


def _base(g, near_atm=False):
    S = 100.0
    mny = g.uniform(0.85, 1.15) if near_atm else math.exp(g.uniform(math.log(0.3), math.log(3.0)))
    K = round(S / mny, 2)
    T_num = g.choice((1, 2, 3, 5, 7, 14, 30, 91, 182, 365, 730, 1460))
    r = round(g.uniform(-0.02, 0.2), 4)
    q = round(g.uniform(0.0, 0.08), 4)
    return {"spot": _fmt(S, 4), "strike": _fmt(K, 2), "T": "%d/365" % T_num, "t_days": T_num,
            "rate": _fmt(r, 4), "div": _fmt(q, 4), "right": g.choice("CP")}


def _args(c):
    n, d = c["T"].split("/")
    return (float(c["spot"]), float(c["strike"]), int(n) / int(d), float(c["rate"]), float(c["div"]), 1 if c["right"] == "C" else -1)


def _with_price(c, price, family, tag):
    c = dict(c)
    c["price"] = _txt(price) if price > 0 else "0"
    c["family"], c["tag"] = family, tag
    return c


def dyadic_sigma(g, lo_bits, hi_bits):
    bits = g.randint(lo_bits, hi_bits)
    j = g.randrange(1, 2 ** bits)
    return 8.0 * j / 2 ** bits


def ties(n, offsets=OFFSETS, bits=(1, 12), seed=ADV_SEED, near_atm=False):
    g = random.Random(seed ^ 0x71E5)
    out = []
    while len(out) < n:
        c = _base(g, near_atm)
        sig = dyadic_sigma(g, *bits)
        S, K, T, r, q, eta = _args(c)
        try:
            p, unit = fprice(S, K, T, r, q, sig, eta)
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
        off = offsets[len(out) % len(offsets)]
        t = p + off * unit
        if not (p > 1e-6 and t > 0):
            continue
        out.append(_with_price(c, t, "tie", "sigma=%r off=%g" % (sig, off)))
    return out


def roots(n, seed=ADV_SEED):
    g = random.Random(seed ^ 0x2007)
    out = []
    while len(out) < n:
        c = _base(g, True)
        sig = g.uniform(0.05, 3.0)
        S, K, T, r, q, eta = _args(c)
        p, unit = fprice(S, K, T, r, q, sig, eta)
        for rel in (0.0, 1e-13, -1e-13, 1e-11, -1e-11, 1e-9, -1e-9):
            if len(out) < n and p > 1e-6:
                out.append(_with_price(c, p * (1.0 + rel), "root", "sigma=%r rel=%g" % (sig, rel)))
    return out


def edges(n, seed=ADV_SEED):
    g = random.Random(seed ^ 0xED6E)
    out = []
    while len(out) < n:
        c = _base(g)
        S, K, T, r, q, eta = _args(c)
        A, B = S * math.exp(-q * T), K * math.exp(-r * T)
        lower = max(eta * (A - B), 0.0)
        upper = A if eta == 1 else B
        k = len(out) % 8
        if k == 0:
            price = lower + 1e-9 * (1 + g.random())
        elif k == 1:
            price = upper - 1e-9 * (1 + g.random())
        elif k == 2:
            price = lower + 1e-5
        elif k == 3:
            price = upper * (1 - 1e-6)
        elif k == 4:
            price = lower * (1 + 1e-12) + 1e-14
        elif k == 5:
            price = lower
        elif k == 6:
            price = upper
        else:
            price = (lower + upper) / 2
        if price > 0:
            out.append(_with_price(c, price, "edge", "k=%d" % k))
    return out


def extremes(n, seed=ADV_SEED):
    g = random.Random(seed ^ 0xE47E)
    out = []
    while len(out) < n:
        c = _base(g)
        k = len(out) % 10
        if k == 0:
            c["spot"], c["strike"] = _fmt(1e12, 2), _fmt(round(1e12 / g.uniform(0.8, 1.2), 2), 2)
        elif k == 1:
            c["spot"], c["strike"] = "0.0001", _fmt(round(0.0001 / g.uniform(0.8, 1.2), 6), 6)
        elif k == 2:
            c["strike"] = _fmt(round(100.0 / g.choice((0.01, 0.05, 20.0, 100.0)), 2), 2)
        elif k == 3:
            c["rate"], c["div"] = _fmt(g.uniform(-0.5, -0.1), 4), _fmt(g.uniform(0.2, 0.9), 4)
        elif k == 4:
            c["T"], c["t_days"] = "1/%d" % (365 * 24 * 60), 0
        elif k == 5:
            c["T"], c["t_days"] = "%d/365" % 36500, 36500
        S, K, T, r, q, eta = _args(c)
        sig = g.choice((0.001, 0.003, 0.01, 0.05, 0.3, 1.0, 3.0, 7.9, 12.0, 100.0)) * g.uniform(0.9, 1.1)
        try:
            p, unit = fprice(S, K, T, r, q, sig, eta)
        except (ValueError, ZeroDivisionError, OverflowError):
            continue
        if p > 0:
            out.append(_with_price(c, p, "extreme", "k=%d sigma=%g" % (k, sig)))
    return out


def domain(n, seed=ADV_SEED):
    """Outside the filter domain on purpose; the certified path must give the (identical) answer."""
    g = random.Random(seed ^ 0xD01A)
    out = []
    while len(out) < n:
        c = _base(g)
        k = len(out) % 5
        price = _txt(g.uniform(0.001, 5.0))
        if k == 0:
            c["spot"], c["strike"], price = "1" + "0" * 25, "1" + "0" * 25, "5" + "0" * 24
        elif k == 1:
            c["T"], c["t_days"] = "1/1000000000000", 0
        elif k == 2:
            c["rate"], c["T"], c["t_days"] = "0.9", "90000/365", 90000
        elif k == 3:
            c["spot"], c["strike"], price = "0.0000000000000000000000001", "0.0000000000000000000000002", "0.00000000000000000000000005"
        else:
            c["T"], c["t_days"] = "2000/1", 730000
        out.append(dict(c, price=price, family="domain", tag="k=%d" % k))
    return out


def adversarial(total=2400, seed=ADV_SEED):
    """The shipped adversarial list: ties 7k, roots 2k, edges 2k, extremes 2k, domain k (k = total // 12)."""
    k = max(total // 12, 1)
    return (ties(5 * k, seed=seed) + ties(2 * k, bits=(30, 42), seed=seed ^ 1) + roots(2 * k, seed=seed)
            + edges(2 * k, seed=seed) + extremes(2 * k, seed=seed) + domain(k, seed=seed))


def mutation_ties(n, seed=ADV_SEED):
    return ties(n, offsets=MUTATION_OFFSETS, bits=(1, 8), seed=seed ^ 0x3A7, near_atm=True)
