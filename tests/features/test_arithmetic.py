"""Independent exact inputs for conversion tests; authored, not executed."""
from decimal import Decimal, localcontext
from fractions import Fraction
import unittest
from option_features.arithmetic import (
    numerical_owner, decimal_exact, nearest_binary64, outward_decimal,
    exact_decimal, enclosure, certify, NumericalFailure, TIERS,
)
from option_feature_contracts import PriceEnclosure

class RationalConversionTests(unittest.TestCase):
    def test_original_decimal_conversion_ignores_ambient_context(self):
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(decimal_exact(Decimal("12345.6789")), Fraction(123456789, 10000))
            self.assertEqual(decimal_exact(Decimal("-0.000125")), Fraction(-1, 8000))

    def test_binary64_halfway_ties_are_even(self):
        self.assertEqual(nearest_binary64(Fraction(2**53+1, 2**53)), 1.0)
        self.assertEqual(nearest_binary64(Fraction(-(2**53+1), 2**53)), -1.0)
        self.assertEqual(nearest_binary64(Fraction(2**53+3, 2**53)), float.fromhex("0x1.0000000000002p0"))

    def test_directed_decimal_export_contains_exact_original_rationals(self):
        for value in (Fraction(1, 3), Fraction(-1, 3), Fraction(1, 7), Fraction(10**100+1, 10**50), Fraction(1, 10**900)):
            low, high = outward_decimal(value, False), outward_decimal(value, True)
            self.assertLessEqual(Fraction(low), value)
            self.assertGreaterEqual(Fraction(high), value)
            for bound in (low, high):
                self.assertLessEqual(len(bound.as_tuple().digits), 128)
                self.assertLessEqual(abs(bound.as_tuple().exponent), 1024)

    def test_exact_residual_export_never_rounds_repeating_rational(self):
        with self.assertRaises(NumericalFailure):
            exact_decimal(Fraction(1, 3))
        self.assertEqual(exact_decimal(Fraction(1, 8)), Decimal("0.125"))

class NativeInclusionTests(unittest.TestCase):
    def test_actual_arb_rational_conversion_and_export_inclusion(self):
        with numerical_owner() as (arb, fmpq, context):
            for bits in TIERS:
                context.prec = bits
                for numerator, denominator in ((1, 3), (-1, 7), (10**50+1, 97)):
                    original = Fraction(numerator, denominator)
                    bounds = enclosure(arb(fmpq(numerator, denominator)))
                    self.assertLessEqual(Fraction(bounds.value_low), original)
                    self.assertGreaterEqual(Fraction(bounds.value_high), original)

    def test_symbolically_known_transcendental_and_root_identities(self):
        with numerical_owner() as (arb, _, context):
            for bits in TIERS:
                context.prec = bits
                for ball, exact in ((arb(0).exp(), Fraction(1)), (arb(1).log(), Fraction(0)), (arb(4).sqrt(), Fraction(2)), (arb(0).erfc(), Fraction(1))):
                    bounds = enclosure(ball)
                    self.assertLessEqual(Fraction(bounds.value_low), exact)
                    self.assertGreaterEqual(Fraction(bounds.value_high), exact)

    def test_export_rejects_overflow_without_expansion(self):
        with numerical_owner() as (arb, _, _):
            with self.assertRaises(NumericalFailure):
                enclosure(arb((1, 5000)))

    def test_tiny_grid_rejected_by_wire_text_limit_intersection(self):
        # Tiny endpoint fallback grid1E-1024 itself expands to1026chars.
        # It is not persistable under the separately frozen1024string cap.
        with numerical_owner() as (arb, _, _):
            with self.assertRaises(NumericalFailure):
                enclosure(arb((1, -1000000)))

    def test_representable_nonzero_tail_cannot_certify_successful_zero(self):
        bounded = PriceEnclosure("option-arb-bsm1", "1", Decimal(0), Decimal("1E-1000"))
        with self.assertRaises(NumericalFailure):
            certify(bounded)

if __name__ == "__main__":
    unittest.main()
