"""P1 single-reference short-dated and OTM shares (F5/F6), exact and one pass.

Pure and single-threaded. Premium is price x size x 100 in integer ticks (see `quotes.to_ticks`);
every share, coverage and premium is a `Fraction`.

Design wording (request 6, interim option A): a share is "at least X% of total eligible premium".
Unreferenced premium stays in the denominator, so each share is a lower bound and cannot over-fire;
coverage (referenced premium over total premium) is reported with it. The short-dated share needs
only the civil date and the expiry, the OTM share needs only the spot; the joint measures need both
and are kept (as in the shipped joint operation). Short-dated: 0 <= days to expiry <= short_dte_max_days.
OTM is strict: call strike > spot, put strike < spot; at the money is not OTM. A threshold fires
with `share >= threshold` (inclusive).
"""
from collections import namedtuple
from fractions import Fraction

from .quotes import SCALE, STANDARD_MULTIPLIER, to_ticks

Measure = namedtuple("Measure", "status reason premium share coverage fired lower_bound label")
SingleReference = namedtuple("SingleReference", "status reason total_premium short_dte otm joint_short_dte joint_otm")
JointAmounts = namedtuple("JointAmounts", "joint_short_premium joint_otm_premium reference_premium")

_ZERO = Fraction(0)


def _accumulate(prints, civil_day, max_days):
    """One pass. prints: iterable of (right, strike, expiry_day, spot, price, size); days are integer ordinals."""
    tk = to_ticks
    total = exp_ref = exp_hit = spot_ref = spot_hit = joint_ref = joint_short = joint_otm = 0
    n_exp = n_spot = n_joint = 0
    have_day = civil_day is not None
    for right, strike, expiry, spot, price, size in prints:
        prem = tk(price) * size
        total += prem
        short = None
        if expiry is not None and have_day:
            n_exp += 1
            exp_ref += prem
            dte = expiry - civil_day
            short = 0 <= dte <= max_days
            if short:
                exp_hit += prem
        otm = None
        if spot is not None:
            n_spot += 1
            spot_ref += prem
            k, s = tk(strike), tk(spot)
            otm = k > s if right == "call" else k < s
            if otm:
                spot_hit += prem
        if short is not None and otm is not None:
            n_joint += 1
            joint_ref += prem
            if short:
                joint_short += prem
            if otm:
                joint_otm += prem
    return total, (n_exp, exp_ref, exp_hit), (n_spot, spot_ref, spot_hit), (n_joint, joint_ref, joint_short, joint_otm)


def _money(ticks):
    return Fraction(ticks * STANDARD_MULTIPLIER, SCALE)


def _exact_text(x):
    n, d = x.numerator, x.denominator
    t = d
    for p in (2, 5):
        while t % p == 0:
            t //= p
    if t != 1:
        return "%d/%d" % (n, d)
    k = 0
    while (10 ** k) % d:
        k += 1
    text = str(abs(n) * (10 ** k // d))
    if k:
        text = text.rjust(k + 1, "0")
        text = text[:-k] + "." + text[-k:]
    return ("-" if n < 0 else "") + text


def _threshold(value):
    if value is None:
        return None
    t = Fraction(value)
    if not 0 <= t <= 1:
        raise ValueError("a share threshold must lie in [0, 1]")
    return t


def _measure(total, n_ref, ref, hit, threshold):
    if n_ref == 0 or total == 0:
        return Measure("unavailable", "missing_reference", None, None, _ZERO, None, True, None)
    share = Fraction(hit, total)
    fired = label = None
    if threshold is not None:
        fired = share >= threshold
        label = "at least %s%% of total eligible premium" % _exact_text(threshold * 100)
    return Measure("available", None, _money(hit), share, Fraction(ref, total), fired, True, label)


def single_reference_shares(prints, civil_day, *, short_dte_max_days, short_min_share=None, otm_min_share=None):
    """F5/F6 shares of total eligible premium with single-reference and joint measures.

    prints: iterable of (right, strike, expiry_day, spot, price, size); expiry_day and civil_day are integer
    day ordinals (None when unknown), spot is None when unknown. short_min_share applies to short_dte and
    joint_short_dte, otm_min_share to otm and joint_otm; no threshold means fired and label are None.
    """
    short_t, otm_t = _threshold(short_min_share), _threshold(otm_min_share)
    total, (ne, er, eh), (ns, sr, sh), (nj, jr, js, jo) = _accumulate(prints, civil_day, short_dte_max_days)
    result = SingleReference(
        "available", None, _money(total),
        _measure(total, ne, er, eh, short_t), _measure(total, ns, sr, sh, otm_t),
        _measure(total, nj, jr, js, short_t), _measure(total, nj, jr, jo, otm_t))
    if total == 0:
        return result._replace(status="unavailable", reason="missing_reference")
    return result


def joint_amounts(prints, civil_day, *, short_dte_max_days):
    """Premium amounts of the jointly referenced prints (legacy joint operation vocabulary)."""
    _, _, _, (_, jr, js, jo) = _accumulate(prints, civil_day, short_dte_max_days)
    return JointAmounts(_money(js), _money(jo), _money(jr))
