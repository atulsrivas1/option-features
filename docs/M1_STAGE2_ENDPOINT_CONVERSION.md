# M1 Stage 2: endpoint conversion, identical result bytes

Developer evidence only. An independent Tester must re-run it. Label for every number below: synthetic workload,
relative engineering budget (no claim about recorded data or live latency).

## What changed, and what did not

The certified solver converts each arb price enclosure (a ball) into outward decimal endpoints (`PriceEnclosure`
with `Decimal` bounds), and then converts the Decimals back into exact `Fraction`s to order the enclosure against
the target. Profiling the origin/main solver (cProfile, 300 flat and mixed contracts) put about 58 percent of solve
time in `outward_decimal`, `decimal_tuple`, `decimal_text` and `decimal_exact`: a 127-digit coefficient was built
as a `Fraction` division, a digit tuple, a joined string for the wire-text check, a `Decimal`, and then walked digit
by digit back into a `Fraction`, for every one of about 13 enclosures per solve.

Stage 2 keeps the arithmetic, the certified decisions, the tiers, the rounding rule and every returned field. It
changes only how the same integers are computed and when the `Decimal` objects are built:

1. Integer arithmetic. The endpoint is `floor` or `ceil` of `value / 10^x` computed on Python integers (a shift
   for dyadic values), with an exact `floor(log10)` search instead of `len(str(...))` on `Fraction` parts.
2. No digit tuple, no `decimal_text` string. The three admission rules (at most 128 digits, `|exponent| <= 1024`,
   projected wire text at most 1024 characters) are evaluated on the integers.
3. Lazy materialisation (`arithmetic.Ends`). An enclosure from a bisection step keeps its two endpoints as
   `(coefficient, exponent)` integers. Ordering against the target (`sign_vs`) and the residual test (`within`)
   are exact integer cross-multiplications; the exact `Fraction`s are built only for an accepted candidate; the
   `Decimal`s and the `PriceEnclosure` are built only for the enclosures the solver reports (the final candidate,
   the lower and upper bound enclosures). Intermediate bisection enclosures never become Decimals.
4. `decimal_exact` uses `Decimal.as_integer_ratio()` (exact, lowest terms, independent of the Decimal context).

`arithmetic_legacy.py` is the verbatim origin/main code (SHA-256 pinned by the test). It is the test oracle and the
fallback behind `arithmetic.set_fast_endpoints(False)`; the fast path is on by default. Library stays pure and
single-threaded (the only new module state is a memo of powers of ten, `_P10`, bounded to exponents of at most
4096; entries are deterministic, so a racing writer cannot change a value).

## Proof that the new path returns the same bytes

Let `v` be a nonzero rational (a dyadic `m * 2^e` for arb endpoints), `up` the direction, and
`k = floor(log10 |v|)`.

**Old.** `order` is `len(str(num)) - len(str(den))`, corrected once by the two comparisons against `10^order` and
`10^(order+1)`. For positive integers with `d1` and `d2` digits, `num/den` lies in `(10^(d1-d2-1), 10^(d1-d2+1))`, so
the estimate is `k` or `k+1`, and the correction yields exactly `k`. Then `x = max(-1024, k-126)`,
`c = ceil(v / 10^x)` if `up` else `floor(v / 10^x)` (exact rational, signed), and `decimal_tuple(c, x)`.

**New.** `_floor_log10` starts from a bit-length estimate and moves `k` down until `10^k <= |v|` and up until
`|v| < 10^(k+1)`; both tests are exact integer comparisons, so the result is `k` whatever the estimate was. `x` is
the same expression. `c` is the same exact quotient:

* general case: `n2 / d2` is `v / 10^x` with `n2 = num * 10^-x` (x < 0) or `d2 = den * 10^x` (x >= 0). Python `//`
  is floor division, and `-((-n2) // d2)` is the ceiling, the expression the old code used. Reduced and unreduced
  numerator/denominator pairs give the same floor and ceiling.
* dyadic case, `e < 0`, `x < 0`: `v / 10^x = m * 10^-x / 2^s` with `s = -e`. For every integer `n`,
  `n >> s == floor(n / 2^s)` (arithmetic shift, including negative `n`), and `-((-n) >> s)` is the ceiling.
* dyadic case, `e >= 0`: `v = m << e` is an integer; the general case applies with `den = 1`.

**Strip and admission.** For nonzero `c` the old loop `while c % 10 == 0` removes exactly the trailing `'0'`
characters of the decimal expansion of `|c|`, which is what `rstrip('0')` counts; the digit count is the stripped
length. The checks are identical: digits > 128 or `|exponent| > 1024` raise `NumericalFailure()`; then
`decimal_text` calls `scalar(value, "d")`, which (the Decimal being finite) rejects digits > 128, `|exponent| > 1024`,
and projected text length `L + sign > 1024` where `L = digits + exponent` for `exponent >= 0`, else `digits + 1` if
`digits + exponent > 0` else `2 - exponent`; `_finish` evaluates the same formula and raises the same
`NumericalFailure()`. `c == 0` returns `Decimal(0)` without any check in both. Therefore success and failure
coincide, and on success `(sign, digits, exponent)` coincide. `Decimal("%dE%d" % (c, x))` is an exact string
construction (the constructor never rounds to the context), so its `as_tuple()` equals the old
`Decimal((sign, digits, exponent))`.

**Arb endpoint rules.** `dyadic_endpoint_parts` keeps, in the same order, the finiteness check, the zero mantissa
case, the `> 4096` overflow, the `< -8192` tiny-grid clamp (which raises through the same text rule for the
`1E-1024` endpoint), and the exponent logic. `enclosure_ends` converts the lower endpoint rounded down and the upper
rounded up in the same order and raises on `low > high` with an exact comparison of the two `(c, e)` pairs.

**Lazy enclosures.** Every conversion failure is raised inside `price_interval`, exactly where the eager code raised
it, so the tier loop in `_price` takes the same branch. After construction, nothing can fail: `sign_vs` and `within`
are pure integer comparisons that equal the old `Fraction` comparisons (the denominator `td` is positive, so
`c * 10^e <?> tn / td` is `c * 10^e * td <?> tn` for `e >= 0` and `c * td <?> tn * 10^-e` for `e < 0`).
`residual > price_tolerance`, with `residual = max(|a-t|, |b-t|)`, holds iff an endpoint lies outside
`[t - tol, t + tol]` (`|x-t| <= tol <=> t-tol <= x <= t+tol`), which is what `within` tests; for an accepted
candidate the exact residual is then computed with `Fraction`s as before. Because the width test and the residual
test are pure, evaluating the residual test first changes no returned field. The reported enclosures are built
from the same integers and equal the old ones field by field. `certified_value` applies the unchanged
`certify` rule to the cached exact endpoints and discards the enclosure (only `.value` was used).

**Behaviour outside the solver's admitted domain.** `decimal_exact` falls back to the legacy function for any value
that is not exactly a `Decimal` or is NaN or an infinity (same exceptions). Conversions whose integers exceed 14000
bits (above 4214 decimal digits, where CPython's integer-to-string limit of 4300 digits can raise `ValueError` in the
old `len(str(...))`) are routed to the legacy code, so even that class is the old behaviour by construction.

## Evidence (reproduce with the commands in the PR)

See "Results" below; all counts come from the committed tools.

## Results

RESULTS_PLACEHOLDER
