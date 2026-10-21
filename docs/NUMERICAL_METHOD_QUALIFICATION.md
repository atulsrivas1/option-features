# Numerical method qualification witnesses

October 21, 2026. This document describes the independently authored tests in
[test_method_qualification.py](../tests/features/test_method_qualification.py).
They supplement the frozen [method](r25/NUMERICAL_METHOD.md),
[model](r25/MODEL_PROFILE.md) and [acceptance contract](r25/NUMERICAL_ACCEPTANCE.md).
They do not alter formulas, numerical limits or acceptance budgets.

## Independent rigorous rational witnesses

The expectation path uses only Python integers, `Fraction` and integer `isqrt`.
It does not call production conversion helpers, Arb, mpmath or binary64 maths to
generate its mathematical bounds. The production functions are the objects
under test. The following witnesses are reconstructed as exact rational bounds:

| Quantity | Construction and remainder |
| --- | --- |
| exp(1/3) | Positive Taylor sum through degree 449. The omitted positive tail is at most the first omitted term divided by `1-x`, because successive term ratios are at most `x=1/3`. |
| log(3/2) | `2*atanh(1/5)`, summing 540 positive odd-power terms. The remaining terms are bounded above by `2*z^(2N+1)/((2N+1)*(1-z*z))`. |
| sqrt(2) | For scale `10^740`, integer floor square root of `floor(2*scale^2)` gives adjacent enclosing rationals. Each endpoint's squared inequality is also checked exactly. |
| erfc(1/2), erfc(8) | Integrate the Taylor series of `exp(-t*t)` term by term; multiply the integral enclosure by an independent enclosure of `2/sqrt(pi)` and subtract from one with outward interval arithmetic. Use 400 and 1500 terms respectively. |

For erfc, pi is enclosed using Machin's identity
`pi=16*atan(1/5)-4*atan(1/239)`, with 540 and 170 alternating terms and the next
term as a remainder bound. Integer square roots enclose both pi endpoints.
The integrated erf series has term
`(-1)^k*x^(2k+1)/(k!*(2k+1))`. At either selected truncation, its subsequent
magnitudes decrease to zero: the next-term ratio is
`x*x*(2k+1)/((k+1)*(2k+3)) < x*x/(k+1) < 1`.
For x=8 the early terms grow; the exact finite prefix is retained, and only the
decreasing alternating tail uses the remainder theorem. Exact rational
arithmetic avoids cancellation loss in that prefix and in `1-erf(8)`.

All five resulting witness intervals must have width below `10^-700`.
At each of the five production tiers, the tests independently extract exact
native lower/upper dyadics and require **both rational witness endpoints** to
lie inside them. They then require persisted Decimal bounds to enclose the raw
dyadics, and check coefficient/exponent limits. Thus these selected real values
have a rigorous independent enclosing witness contained in the native interval,
which is itself contained in the persisted certificate. This is stronger than
overlap with an empirical high-precision decimal answer. It remains a finite set
of method witnesses, not a proof of every transcendental implementation or every
admitted argument.

Separate rational conversion cases exercise non-dyadic positive/negative values,
a large numerator and a small positive decimal at every tier. Complementary
actual-backend properties check erfc reflection, exp inversion, put-call parity,
equal call/put Gamma and Vega, and strictly separated prices when volatility
increases. Such identities complement independent witnesses; identities alone
could share an implementation error and are not substituted for an oracle.

## Context ownership and bounded inverse decisions

Actual backend tests check saved precision/thread restoration after normal exit,
an injected body exception, a model range failure and an export failure. They
seed the supported prior thread count to 2 and precision to 96 under the owner
lock before each case, require the owner to pin threads to 1, and require both
prior settings to be restored. A final cleanup restores the original ambient
settings even if an assertion fails. This avoids a default-thread-count-1 test
passing when either pinning or restoration is absent.
They check explicit reentrancy rejection, recovery after an injected backend import
failure, and two real threads serialized around the actual numerical owner.
Thread waits have finite timeouts; this is correctness coverage, not a throughput
or scheduling-performance measurement. Native crashes or external concurrent
mutation of the global flint context are outside the admitted contract.

The `ControlledInverseDecisionTests` class supplies explicit synthetic forward
interval collaborators. These are **solver decision tests, not BSM fixtures or
backend numerical evidence**. The synthetic monotone function V(sigma)=sigma
places an exact root on a midpoint, forcing all five tiers and quarter-probe
rescue. Tests establish that its small residual cannot waive a wide bracket,
unresolved probes preserve the original bracket, cap overlap never invents an
exact root, strict cap shortfall reports bracket exceedance, failed forward
tiers stop finitely, and uncertain economic bounds never enter price solving.
A deliberately controlled midpoint conversion tests representability refusal;
it does not claim an independently generated real-market stagnation example.
Counts are checked against `15*(max_iterations+2)` and explicit expected tier
sequences. The separate real independent-fixture suite remains required for
actual BSM inverse root/bracket/residual and conditioning acceptance.

## Development execution and remaining acceptance

The author ran the focused test module in a newly created private development
environment on Windows 11 AMD64, CPython 3.12.10, with the pinned
`python-flint==0.9.0` wheel and `option-feature-contracts==0.1.0a1` wheel copied
by installation from the qualification attempt's read-only artifacts. Production
feature imports came explicitly from the current source tree. The command is:

```text
python -m unittest discover -s tests/features -p test_method_qualification.py -v
```

The development receipt records actual source hashes, Git base commit, import
origins, environment, command, results and log digest. It is source-development
evidence on a dirty working tree, not exact-final-commit installed-wheel proof.
No accepted qualification directory, study environment or global Python setting
was changed. A final reviewed source commit must be rebuilt, installed and tested
again by the release coordinator in each supported environment.

Still required independently: final source review of these derivations and test
assertions; the separately authored high-precision BSM wire-fixture suite;
native artifact/source/license inventory; installed artifact tests on actual
supported platforms; full direct/worker/stored parity and browser release demo.
Passing these focused tests alone does not accept R25 or claim exhaustive range,
native fault, performance or memory qualification.
