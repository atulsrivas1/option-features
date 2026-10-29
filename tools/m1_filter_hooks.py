"""TEST-ONLY hooks for the M1 Stage 1 float filter (not part of the shipped package).

test_hooks(bound_divisor, inject) wraps option_features.floatfilter.make so that the filter built for each
solve inside the block uses E / bound_divisor and a modelled float error of inject * U * SCALE. The library
itself keeps no mutable state: make() receives the knobs as arguments, which is its snapshot per solve.
"""
from contextlib import contextmanager


@contextmanager
def test_hooks(bound_divisor=1.0, inject=0.0):
    import option_features.floatfilter as ff
    real = ff.make
    ff.make = lambda operands, target, config: real(operands, target, config, bound_divisor=float(bound_divisor), inject=float(inject))
    try:
        yield
    finally:
        ff.make = real
