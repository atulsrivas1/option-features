"""Independent literal reduction and true-overflow boundary witnesses."""
from decimal import Decimal
from fractions import Fraction
import unittest

from option_flow_contracts import FlowValidationError
from option_flow_features.arithmetic import ExactArithmetic


class ArithmeticTests(unittest.TestCase):
    def test_cross_cancellation_before_multiply_and_divide(self):
        arithmetic=ExactArithmetic(3)
        self.assertEqual(arithmetic.mul(Fraction(99,100),Fraction(100,99)),Fraction(1))
        self.assertEqual(arithmetic.div(Fraction(99,100),Fraction(99,100)),Fraction(1))

    def test_denominator_gcd_and_opposite_terms_are_reduced_before_cap(self):
        arithmetic=ExactArithmetic(3)
        self.assertEqual(arithmetic.add(Fraction(499,500),Fraction(1,500)),Fraction(1))
        self.assertEqual(arithmetic.add(Fraction(997,2),Fraction(-998,3)),Fraction(995,6))
        self.assertEqual(arithmetic.add(Fraction(999,998),Fraction(999,998)),Fraction(999,499))
        self.assertEqual(arithmetic.add(Fraction(999,998),Fraction(-999,998)),Fraction(0))

    def test_decimal_coefficient_is_reduced_before_lowered_cap(self):
        self.assertEqual(ExactArithmetic(2).exact(Decimal('1.25')),Fraction(5,4))

    def test_true_reduced_result_overflow_is_resource_error(self):
        with self.assertRaises(FlowValidationError) as caught:ExactArithmetic(3).mul(999,2)
        self.assertEqual(caught.exception.code,'resource_limit')
        with self.assertRaises(FlowValidationError):ExactArithmetic(3).add(999,2)
        with self.assertRaises(FlowValidationError):ExactArithmetic(3).sum_integer(999,2)
