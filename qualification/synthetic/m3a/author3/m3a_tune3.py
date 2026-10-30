"""R-182 tuner (SYNTHETIC): shift quotes by whole 1e-8 price ticks so the value computed FROM THE QUOTE TEXT
(second engine m3a_ref3 with intermediate rounding switched off, binary64 + bisection) lands on the threshold
within TOL points, so that both round-once (full precision, x100, round to 8 dp) and round-annual-first
give exactly the threshold text."""
import copy
import itertools
from decimal import Decimal as D
import m3a_ref3 as ref

TOL = D("0.000000002")
TICK = D("0.00000001")


def raw_x(fam, inputs):
    """unrounded rule value x (points for V4..V11, ratio for V21), as Decimal."""
    old = ref.r8
    ref.r8 = lambda x: D(x)
    try:
        o = ref.evaluate(fam, inputs)
    finally:
        ref.r8 = old
    assert o["status"] == "available", o
    return D(o["rule"]["x"]), o


def _shift(inputs, idx, n):
    c = inputs["chain"]["contracts"][idx]
    c["bid"] = format(D(c["bid"]) + TICK * n, "f")
    c["ask"] = format(D(c["ask"]) + TICK * n, "f")


def tune(fam, inputs, target, maxn=8, top=4):
    """returns (new_inputs, offsets dict contract_id->ticks, achieved raw x)."""
    target = D(target)
    base_x, _ = raw_x(fam, inputs)
    if abs(base_x - target) <= TOL:
        return inputs, {}, base_x
    jac = []
    cs = inputs["chain"]["contracts"]
    for i in range(len(cs)):
        t = copy.deepcopy(inputs)
        _shift(t, i, 1)
        try:
            x, _ = raw_x(fam, t)
        except AssertionError:
            continue
        j = x - base_x
        if abs(j) > D("1e-12"):
            jac.append((abs(j), i, j))
    jac.sort(reverse=True)
    pick = jac[:top]
    best = None
    rng = range(-maxn, maxn + 1)
    for combo in itertools.product(rng, repeat=len(pick)):
        pred = base_x + sum(n * p[2] for n, p in zip(combo, pick))
        err = abs(pred - target)
        if best is None or err < best[0]:
            best = (err, combo)
    err, combo = best
    out = copy.deepcopy(inputs)
    offs = {}
    for n, p in zip(combo, pick):
        if n:
            _shift(out, p[1], n)
            offs[cs[p[1]]["contract_id"]] = n
    x, _ = raw_x(fam, out)
    assert abs(x - target) <= TOL, (fam, x, target, offs)
    return out, offs, x
