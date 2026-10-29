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

**Legacy routing thresholds and the dropped cause chain.** Two routes send an input to `arithmetic_legacy`:
(1) an arb endpoint whose mantissa exceeds 5000 bits (`_LEGACY_MANTISSA_BITS`; real endpoints carry at most the tier
precision, 2048 bits, so the solver never takes this route; with the magnitude limit `>= -8192` the largest shift is
then `8192 + 5000 = 13192` bits); (2) a rational whose numerator or denominator exceeds 14000 bits (`_LEGACY_BITS`).
CPython raises `ValueError` for `str()` of an integer with more than 4300 digits, that is from about 14284 bits
(10^4300 is about 2^14284.3); 14000 bits leaves a margin of about 284 bits (2^14000 is about 10^4214), so no input
that the old `len(str(...))` would reject is handled by the new code. Both routes are inside the equivalence grid
(mantissas of 5000, 5001, 9000 and 16000 bits; rationals of 13990 to 14010 bits; binary exponents -8194 to 4097).
One intentional difference: when the `decimal_text` check fails, the old code raised `NumericalFailure()` from the
`ContractValidationError`; the new `_finish` raises `NumericalFailure()` directly, so `__cause__` is `None`. Nothing
reads `__cause__` (the solver uses only `.reason`), it is no result field, and the tests compare type and arguments.

**Process-global switch.** `arithmetic.set_fast_endpoints` sets a module global of the current process. It is for
tests and diagnosis, not a runtime option: set it before solving, never while another thread is solving, and set it
again in every spawned worker (a `spawn` child imports a fresh module and ignores the parent's setting; a forked
child inherits the value at fork time). The default is on in every new process.

**Release gate (PO ruling 2026-10-29).** The in-suite equivalence test defaults to 150,000 inputs for CI speed. The full
1,000,000-input run (`python tools/m1_conversion_equivalence.py`, or `M1S2_EQUIV_N=1000000` with the unit test) is a
REQUIRED release-gate step, recorded as evidence per candidate. The B6 gate chain is the Tester's all-valid-quote chain.

## Results

Machine: Intel Xeon (Skylake-SP, 96 logical cores, Windows 11 x64, CPython 3.12.10, python-flint 0.9.0); one worker,
library single-threaded; benchmark processes run one at a time. Raw numbers: `docs/m1/M1_STAGE2_RESULTS.json`.

**Identity (changed versus origin/main, every InverseResult and SolverEvidence field, exact-field SHA-256).**

| Check | Inputs | Identical | Different |
|---|---|---|---|
| `m1_solver_compare.py compare`: flat 10000 + mixed 10000 + adversarial 2800 (22,800 contracts) | 22,800 | 22,800 | 0 |
| same plus the 400 mutation-tie contracts (23,200 contracts; 771 unsolvable, all identical) | 23,200 | 23,200 | 0 |
| same, float filter off (Stage 1 switch) | 23,200 | 23,200 | 0 |
| same, `--conv legacy` (Stage 2 switch off) | 23,200 | 23,200 | 0 |
| `m1_conversion_equivalence.py`: 1,000,000 random inputs (5 classes), 9,124,284 old-versus-new comparisons | 1,000,000 | 9,124,284 | 0 |
| `m1_solver_compare.py mutation` (Stage 1 acceptance test 3) | | controls identical, mutants detected | |

The equivalence run covers all five precision tiers, both directed roundings on both endpoints, zero, tiny
(`< 2^-8192` clamp), huge (`> 2^4096`, 4096 boundary), non-finite balls, balls computed by exp, sqrt, log and erfc,
rationals with up to 3200 bits and beyond the 4300-digit limit, Decimals including NaN, sNaN, infinities and wrong
types, and exceptions (type and arguments must match). Two deliberate mutants of `_outward_parts` are caught at once
(3,910 and 5,017 mismatches in 3,000 inputs). No input class differs, so the fast path ships enabled.

**Per-solve wall time** (`m1_solver_compare.py bench`, 200 contracts (flat 100 + mixed 100), 30 repeats after one
warm-up, base and changed interleaved as base, changed, base, changed, one process each, 6,000 samples each).

| Run | p50 us | p95 us | mean us | Peak working set |
|---|---|---|---|---|
| base | 2930 | 5071 | 3108 | 32.6 MB |
| changed | 958 | 1568 | 1009 | 32.5 MB |
| base (second) | 2854 | 4962 | 3017 | 32.7 MB |
| changed (second) | 1024 | 1699 | 1072 | 32.3 MB |

Speedup p50 3.06x and 2.79x, p95 3.23x and 2.92x (mean 3.08x and 2.81x). Memory is unchanged.

**Calls per solve** (flat + mixed, 200 solves, mean): arb enclosure calls 9.61 (p50 9, p95 16) in both versions,
unchanged: Stage 2 does not reduce arb work, it makes each enclosure cheap. Endpoint conversions (dyadic endpoints
and outward_decimal calls) 41.37 to 21.22 (p50 38 to 20, p95 66 to 34): each remaining conversion is the integer
version. Decimal materialisations 22.1 to 8.7 per solve (the remaining ones are the reported lower, upper and
candidate enclosures and the exact bounds).

**B6 proxy** (`tools/m1_chain_benchmark.py`, size M, 2000 contracts, B6 IV part: per-contract IV for every contract
plus all-expiry ATM IV plus 30-day IV; 6 alternating rounds of 5 repeats, 30 samples each, nearest-rank p95).
Label: synthetic workload, relative engineering budget. Budget 5 s, hard 15 s.

| Chain | Solves | base p50 / p95 | changed p50 / p95 | Speedup p50 / p95 |
|---|---|---|---|---|
| default chain (american ITM contracts are not solved) | 992 | 4.07 / 4.17 s | 1.27 / 1.35 s | 3.20x / 3.08x |
| `--all-european`: valid quotes everywhere, every contract reaches the solver (72 price_out_of_bounds, 1664 available) | 1736 | 7.19 / 7.38 s | 2.24 / 2.29 s | 3.21x / 3.22x |

About 4.1 ms per solve at base (4.1 s for 992, 7.2 s for 1736) and about 1.3 ms per solve changed. The all-valid
chain, which was over the 5 s budget at base (7.4 s p95, within the 15 s hard limit), is within it changed
(2.29 s p95), leaving 2.7 s for the other outputs of B6 (OC5, OC6 and the rest are other stories, so B6 as a whole is
still not measurable). Peak working set for one all-european B6 run: 33.5 MB base, 33.2 MB changed.
The Tester's own all-valid chain is not available to the Developer; the all-european variant above is the Developer's
stand-in, so the independent Tester must re-run on its chain.

## Reproduce

```
PYTHONPATH=<changed>/packages/features/src;<changed>/packages/option-contracts/src
python tools/m1_conversion_equivalence.py --n 1000000
python tools/m1_solver_compare.py compare  --base-root BASE --changed-root CHANGED --n 10000 --adv 2400 --mut 400
python tools/m1_solver_compare.py mutation --base-root BASE --changed-root CHANGED
python tools/m1_solver_compare.py bench    --base-root BASE --changed-root CHANGED --subset 100 --repeats 30
python tools/m1_chain_benchmark.py --sizes M --b6-sizes M --repeats 5 --all-european   # run per root, alternate
```

## Not done, and why

* Skipping the conversion of an endpoint the decision does not read (for example the lower endpoint when the upper
  is already below the target) would save about a quarter of the remaining conversions (about 3 percent of solve time),
  but a conversion can raise `NumericalFailure` for tiny or huge values, and the old code raised it before any
  decision. Deferring it needs a proof that the failure cannot occur, which holds only for values inside about
  1e-300..1e300; not worth the added proof surface for 3 percent.
* The 13 arb enclosure calls per solve are unchanged (the second lever; any change to how many are made must be
  argued separately, since each call is a certified decision).
