"""Bounded exact rational arithmetic with explicit intermediate admission."""
from decimal import Decimal
from fractions import Fraction
from functools import cmp_to_key
from math import gcd
from option_flow_contracts import FlowRational, FlowValidationError
from option_flow_contracts.codec import decimal_text

class ExactArithmetic:
    """Invocation-owned arithmetic honoring a lowered integer-digit ceiling."""
    __slots__ = ('maximum', 'digits')

    def __init__(self, digits):
        self.digits = digits
        self.maximum = 10**digits - 1

    def integer(self,value):
        if abs(value)>self.maximum:
            raise FlowValidationError('resource_limit','/arithmetic')
        return value

    def product(self,a,b):
        if b and abs(a)>self.maximum//abs(b):
            raise FlowValidationError('resource_limit','/arithmetic')
        return a*b

    def sum_integer(self,a,b):
        if (b>0 and a>self.maximum-b) or (b<0 and a < -self.maximum-b):
            raise FlowValidationError('resource_limit','/arithmetic')
        return a+b

    def exact(self,value):
        if type(value) is int:
            return Fraction(self.integer(value))
        if type(value) is Fraction or type(value) is FlowRational:
            self.integer(value.numerator);self.integer(value.denominator)
            return Fraction(value.numerator,value.denominator)
        if type(value) is Decimal:
            sign,digits,exponent=Decimal(decimal_text(value)).as_tuple()
            # Decimal profile prebounds these private coefficients to38 digits
            # and scale18. Only the reduced rational is a semantic intermediate.
            numerator=0
            for digit in digits:
                numerator=numerator*10+digit
            if sign:numerator=-numerator
            power=10**abs(exponent)
            result=Fraction(numerator*power) if exponent>=0 else Fraction(numerator,power)
            self.integer(result.numerator);self.integer(result.denominator)
            return result
        raise FlowValidationError('type_mismatch','/arithmetic')

    def add(self,a,b):
        a,b=self.exact(a),self.exact(b)
        common=gcd(a.denominator,b.denominator)
        left=a.denominator//common;right=b.denominator//common
        # Admitted operands statically bound each private cross-term to2*digits,
        # and their sum to2*digits+1; no unbounded temporary is allocated.
        numerator=a.numerator*right+b.numerator*left
        reduction=gcd(abs(numerator),common)
        result=Fraction(numerator//reduction,left*(b.denominator//reduction))
        self.integer(result.numerator);self.integer(result.denominator)
        return result

    def sub(self,a,b):
        b=self.exact(b)
        return self.add(a,Fraction(-b.numerator,b.denominator))

    def mul(self,a,b):
        a,b=self.exact(a),self.exact(b)
        first=gcd(abs(a.numerator),b.denominator)
        second=gcd(abs(b.numerator),a.denominator)
        return Fraction(self.product(a.numerator//first,b.numerator//second),
                        self.product(a.denominator//second,b.denominator//first))

    def div(self,a,b):
        b=self.exact(b)
        return self.mul(a,Fraction(b.denominator,b.numerator))

    def total(self,values):
        value=Fraction(0)
        for member in values:value=self.add(value,member)
        return value

    def wire(self,value):
        value=self.exact(value)
        return FlowRational(value.numerator,value.denominator)

    @staticmethod
    def compare(a,b):
        """Euclidean comparison avoids cross-products above the digit budget."""
        if a.numerator<0<=b.numerator:return -1
        if b.numerator<0<=a.numerator:return 1
        sign=-1 if a.numerator<0 else 1
        an,ad=abs(a.numerator),a.denominator
        bn,bd=abs(b.numerator),b.denominator
        orientation=1
        while True:
            aq,ar=divmod(an,ad);bq,br=divmod(bn,bd)
            if aq!=bq:return sign*orientation*(1 if aq>bq else -1)
            if not ar or not br:
                return 0 if ar==br else sign*orientation*(1 if ar else -1)
            an,ad=ad,ar;bn,bd=bd,br;orientation=-orientation

    def median(self,values):
        values=sorted(values,key=cmp_to_key(self.compare))
        middle=len(values)//2
        return values[middle] if len(values)%2 else self.div(self.add(values[middle-1],values[middle]),2)
