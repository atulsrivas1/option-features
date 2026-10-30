"""M3a story S03: the 25-delta point kernel (one expiry, one right), both delta conventions.

STUB (failing-first commit): the record shape is fixed here; the search is not implemented yet.
"""
from fractions import Fraction

CONVENTIONS = ("spot", "forward")
TARGET = Fraction(1, 4)


def delta25_point(strikes, ivs, atm_strike, spot, rate, carry, expiry_days, right, convention="spot",
                  owner=None, certified_only=False):
    raise NotImplementedError("S03 delta25_point")
