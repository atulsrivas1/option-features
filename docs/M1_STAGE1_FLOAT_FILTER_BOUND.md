# M1 Stage 1: float filter, error bound and certified fallback

Status: Developer evidence only. The independent Tester must review this proof, run the shrunk-bound mutation and the platform replays; the Developer does not sign off his own proof. Label for every number in this repository about this stage: synthetic workload, relative engineering budget (no real-data claim).

Code: `packages/features/src/option_features/floatfilter.py` (filter, constants, test-only hook) and `inverse.py` (`solve(..., float_filter=True)`). Everything below refers to those two files.

## 1. What the filter does, and what it never does

The certified solver (`_price` in `inverse.py`) bisects sigma on [0, max_sigma]. At each midpoint it evaluates a rigorous arb enclosure of the price, tier by tier (128 to 2048 bits), and uses it for two things: the ordering sign (enclosure entirely below or above the exact target) and the acceptance test `acceptable` (residual and width against the tolerances). The returned `InverseResult` and `SolverEvidence` contain the candidate and its enclosure.

The float layer computes a binary64 Black-Scholes price at the midpoint. It **never produces a value, an enclosure or an evidence field**. It may only replace a certified midpoint evaluation when all of the following hold (rule R):

1. the float price `p_f` differs from the float target `t_f` by more than the bound `E` (section 4): `|p_f - t_f| > E`, so the sign of `price - target` is known;
2. the base loop would **reject** the candidate both before and after the contraction (section 5): either `|p_f - t_f| > E + 2*price_tol` (the residual alone fails), or the bracket width after the contraction still exceeds the volatility tolerance;
3. the contract and sigma are inside the admitted domain (section 6).

If any condition fails, the unchanged certified path runs for that midpoint. The bracket update from the float sign is the same update the certified sign would have made. The candidate and its enclosure are only written to the evidence when the solve ends without acceptance (failure exits); in that case the deferred enclosure of the last skipped midpoint is computed by the same certified `_price` call (`pending` in `inverse.py`), so the bytes equal the base. The accepted midpoint, the terminal midpoint, the `sign == 0` handling, the bound admission (`bounds`), the conditioning (Vega) and all fractions are always certified.

Fallback switch: `solve(..., float_filter=False)` runs the pure certified path (no environment variable, no global state). It is also taken automatically when `floatfilter.make` returns `None` (domain), and by a whole-solve rerun if the deferred enclosure cannot be produced (`_FilterAbort`; defence in depth, proven unreachable in the domain by section 6). Counters are not stored in any result; the harness counts `model.equation` and `bounds` calls from outside.

The sigma-cap check before the loop uses the same rule with only condition 1 (its enclosure is unused when the sign is positive).

## 2. The float algorithm (all operations in order)

Inputs converted with `float(Fraction)` (CPython: correctly rounded, relative error at most e = 2^-53): S, K, T, target t; r, q and sigma are already binary64 values (exact). With eta = +1 call, -1 put:

```
A = S*exp(-q*T);  B = K*exp(-r*T);  ln = log(S/K);  sT = sqrt(T);  vs = sigma*sT
d1 = (ln + ((r-q) + 0.5*sigma*sigma)*T) / vs;  d2 = d1 - vs
N_i = 0.5*erfc(-eta*d_i*c)      with the constant c = 0.7071067811865476 (1/sqrt 2 rounded)
p_f = eta*(A*N_1 - B*N_2)
Z = (|ln| + (|r|+|q|)*T + sigma*sigma*T + 1) / vs
SCALE = (A + B)*(1 + Z),   E = C_BOUND * U * SCALE
```

Only +, -, *, /, sqrt (IEEE correctly rounded, identical on every platform; CPython never fuses multiply-add) and the libm functions exp, log, erfc. Constants: `U = 2^-40`, `W_COEFF = 5`, `C_BOUND = 40`, `Z_MAX = 1e5`, `D_MAX = 30` (all in `floatfilter.py`; fixed, argued here, not measured).

## 3. Assumptions (stated, not measured)

- A1 IEEE-754 binary64, round to nearest even, no extended precision, no fused multiply-add in the interpreter loop.
- A2 `float(Fraction)` is correctly rounded (CPython guarantees it).
- A3 libm `exp`, `log`, `erfc` return values with relative error at most `U = 2^-40` (about 4096 ulp of binary64) on every supported platform and libm (Windows UCRT, glibc, musl). Real libms are within a few ulp (about 2^-50 to 2^-52), so A3 leaves a factor of about 1000 for platform differences; the bound does **not** assume monotonicity or identical output across platforms, only A3.
- A4 arb: balls are rigorous (the true value is inside) and, at 2048 bits, the radius of the price enclosure inside the domain of section 6 is far below `2^-1000 * SCALE` (arb working precision is 2048 bits and the expression has a bounded number of operations on arguments of size at most `1e5`). This is only used for decisiveness (section 5, step 3), with a gap of more than 900 bits to spare.

## 4. Error model and the constant

Write `p` for the exact price at the exact binary64 sigma. Notation: e = 2^-53 <= 1.2e-16, U = 2^-40 = 9.1e-13, so e*1000 < U/9.

1. **A and B.** The exponent argument has absolute error at most `|qT| * 3e` (rounding of q*T and of the converted T), with `|qT| <= 64` (domain) that is `<= 2.1e-14 = 0.023U`; exp adds relative `U`; S adds `e`. Hence `A_f = A(1+t_A)`, `|t_A| <= 1.1U`, same for B. Use 2U.
2. **Numerator.** `ln(S/K)`: S/K has relative error 3e, so absolute error 3.1e plus relative `U` from libm. The drift term `((r-q)+0.5*sigma^2)*T` accumulates at most 6e relative to `(|r|+|q|+sigma^2)*T`. With `W = |ln| + (|r|+|q|+sigma^2)T`: `|d num| <= (U+6e) W + 3.1e <= 1.001 U (W+1)`.
3. **d1, d2.** `vs` has relative error 2.5e; the division adds e. Since `|d1| <= W/vs <= Z`: `|d d1| <= 1.001 U Z + 3.6 e Z <= 1.02 U Z`. For d2 = d1 - vs (note `vs <= Z`, `|d2| <= 2Z`): `|d d2| <= 1.02 U Z + 5.5 e Z`. Round up: **`|d d_i| <= 3 U Z`**.
4. **N.** The argument `x = -eta d c` has error at most `3UZ/sqrt2 + 2e|d|/sqrt2 <= 2.2 U Z`. Mean value theorem for the exact function erfc (derivative at most `2/sqrt(pi) < 1.13`) gives an N error `<= 0.5642 * 2.2 U Z = 1.25 U Z`; libm adds relative `U`, and `N <= 1`. So `|N_f - N| <= 1.25 U Z + U`.
5. **Products and difference.** `|A_f N1_f - A N1| <= A (1.25 U Z + U + 2U(1+U)) <= A (1.25 U Z + 3.1 U)`; same for B; the two product roundings and the subtraction add at most `3e (A+B) < 0.001 U (A+B)`. Total: `|p_f - p| <= (A+B)(1.25 U Z + 3.2 U) <= 3.2 U (A+B)(1+Z) = 3.2 U SCALE` (SCALE uses the float A, B, Z; the difference to the exact ones is below 1e-14 relative). The error is absolute in units of A+B, which is what covers cancellation in `A*N1 - B*N2` (deep ITM/OTM): the bound never divides by the price.
6. **Constants.** `W_COEFF = 5` (rounded up from 3.2, factor 1.56) is the proven worst-case float error in units of `U*SCALE`. `C_BOUND = 40` gives `E = 40 U SCALE`: **safety factor 8 over the rounded-up worst case, 12.5 over the derived coefficient**, on top of the factor of about 1000 already inside U (A3). Information only, not used to set any constant: over 16,149 (contract, sigma) points (flat, mixed, adversarial) the observed maximum of `|p_f - p| / (U*SCALE)` against a 256-bit enclosure was 7.4e-5 (`tests/features/test_stage1_float_filter.py` re-checks `<= W_COEFF` on a sample every run).
7. **Target.** `|t_f - t| <= e t`. The loop is reached only after the certified admission `t < ` (certified upper price bound), and that bound is A (call) or B (put) up to its enclosure width, so `t <= 1.0001 SCALE`.

**Lemma D (sign).** If `|p_f - t_f| > E` then `sign(p - t) = sign(p_f - t_f)` and `|p - t| >= (40 - 3.2 - 0.01) U SCALE > 36 U SCALE`. Proof: `|p - t| >= |p_f - t_f| - |p_f - p| - |t_f - t| > 40U SCALE - 3.2U SCALE - 1.0001 e SCALE`. QED.

## 5. Why the certified path would take the same branch and produce the same bytes

1. **The sign is the exact sign.** The certified `_price` returns -1 if the enclosure lies entirely below the target, +1 if entirely above (exact Fraction comparison of outward endpoints), else tries the next tier. Arb balls are rigorous (A4), so a decisive answer is the true sign.
2. **Decisiveness.** By Lemma D the gap is at least `36 U SCALE`, at least `3.3e-11 * SCALE`. By A4 the radius at 2048 bits is below `2^-1000 SCALE`. So some tier of `TIERS` is decisive and `_price` returns the true sign, which is the float sign. It never returns 0 and never raises (section 6, item 5). Precision escalation therefore cannot change the sign; it only changes which tier supplies the enclosure, and the enclosure is only needed on failure exits, where the identical `_price` call is made (the cache `Operands.cache` is deterministic).
3. **Rejection before and after contraction.** `acceptable` is evaluated with the midpoint candidate and its enclosure `[a, b]`, once with the bracket before and once after the contraction. It returns False whenever (a) `max(|a-t|,|b-t|) > price_tol` or (b) `width > vol_tol`. Since `p` lies in `[a, b]`, `max(|a-t|,|b-t|) >= |p-t| >= |p_f - t_f| - 3.21 U SCALE >= E + 2 price_tol - 3.21 U SCALE > price_tol` when `|p_f - t_f| > E + 2 price_tol` (rule R2a). Otherwise rule R2b requires the post-contraction width `w2` (new `hi-mid` or `mid-lo`) to exceed `vol_tol*(1+2^-30)` with a `(1-2^-30)` margin for the float comparison; `w2 <= width`, so both evaluations fail on (b). Nothing in `acceptable` that is visible outside happens when it returns False except `candidate` and `candidate_enclosure`, which are the deferred values.
4. **Bracket and midpoints.** `lo`, `hi` are binary64 values; the Fraction midpoint `nearest_binary64((lo+hi)/2)` equals `(lo+hi)/2` in binary64 for `1e-290 <= hi <= 1e300` (the sum is correctly rounded and halving is exact for normal numbers); outside that range the exact path is used (`tests/features/test_stage1_float_filter.py`, 20,000 random brackets including subnormal ones).
5. **Failure exits.** Every call of `result()` first materialises the deferred candidate and enclosure with the same `_price` call the base made, so `candidate_sigma` and `candidate_enclosure` equal the base; if that call ever raised, `_FilterAbort` reruns the whole solve with `float_filter=False`.

## 6. Domain: the filter is disabled automatically (certified path used) when

1. `eta` not +-1, `T <= 0` (terminal payoff), spot or strike not positive, any conversion raises or is not finite, `S` or `K` outside `[1e-20, 1e20]`, `T` outside `[2^-30, 1e3]`, target not positive.
2. `|r T| > 64` or `|q T| > 64` (the certified guard is 512).
3. `config.max_sigma > 100` (whole solve); a midpoint with `sigma` outside `(0, 100]`.
4. `Z > 1e5` (tiny `sigma*sqrt(T)` or extreme drift): conditioning of d.
5. `|d1| > 30` or `|d2| > 30`. This keeps the true price bounded below, so the certified enclosure never hits a failure of the enclosure text conversion (it fails for prices below about 1e-895, measured with `enclosure()`; `dyadic_endpoint` and `decimal_text`). Lemma P: write `h(x) = N(x)/phi(x)`; then `h'(x) = 1 + x h(x) >= 1/(1+x^2) >= 1/901` on `[-30, inf)`, and the price equals `A phi(d1) (h(d1) - h(d2))` (call) or `A phi(d1) (h(-d2) - h(-d1))` (put), because `B phi(d2) = A phi(d1)`; hence `price >= A phi(d1) vs / 901 >= 1.6e-48 * 1.1e-196 * 1e-5 / 901 > 1e-252`. All other `NumericalFailure` sources of the certified evaluation (`|rT|, |qT| <= 512`, `sigma <= 4096`, `|d| <= 1e6`, non-finite ball, endpoint magnitude above 2^4096) are excluded by items 1 to 5.

Nothing in the filter depends on environment variables or on the platform beyond A1 to A3. The Tester is asked to replay on Linux (process check, not claimed before RQ) and to try to falsify A3 by swapping in a reduced-accuracy erfc.

## 7. Test-only hook (acceptance test 3)

`floatfilter.test_hooks(bound_divisor, inject)` is a context manager used only by tests and the harness: `bound_divisor` divides `E`; `inject` adds `inject * U * SCALE` to `p_f` (models a float error of that size). Defaults are `1.0` and `0.0`; library code never sets them.

An honest finding: a plain divisor of 10 **cannot** be detected with the real libm, because the real float error is about 1e-4 units of `U*SCALE` while the shrunk bound is 4 units. The harness therefore runs the mutation with a modelled error of `W_COEFF = 5` units (the proven worst case, not larger) next to the shrunk bound (4 units): `bound_divisor 1` plus `inject 5` and `inject 30` (six times the proven worst case) must show zero byte differences against the certified solver; `bound_divisor 10` plus `inject 5` must show at least one, otherwise `tools/m1_solver_compare.py mutation` exits non-zero. The plain divisor 10 without injection is also printed (zero differences, informational). If the PO wants the literal divisor-10 mutation to be detectable without injection, the constant would have to be tightened until the safety factor over the real error is below 10, which contradicts the conservative ruling; this is a PO ruling item, not a Developer decision.

## 8. What the Tester should check

1. Steps 1 to 7 of section 4 and Lemma D (constants, A3 margin).
2. Lemma P and the domain list in section 6 (especially item 5 and the conversion limits).
3. Section 5 steps 3 and 5 against `inverse.py` (a skipped midpoint must be rejected both times; every `result()` path materialises).
4. Run: `python -m unittest discover -s tests/features -p "test_*.py"`; `python tools/m1_solver_compare.py compare --base-root BASE --changed-root CHANGED`; `... mutation ...`; platform replays; independent adversarial contracts built from the proof (the inequalities `|p_f - t_f| > E` with the true gap between 0 and 36 units are impossible by Lemma D; an attempt to construct one with real libm falsifies A3).
