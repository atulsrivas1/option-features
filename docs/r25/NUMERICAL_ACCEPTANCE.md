# R25 numerical acceptance contract

Status: EQ182 freeze candidate, October 20, 2026. Validation specification only; no generator, numerical kernel, fixture execution, build, benchmark or database operation has run for this document. Exact-commit local checks provide merge validation under owner policy; hosted CI is not a merge prerequisite. Platform support requires actual environment evidence.

The normative model is [option-bsm1](MODEL_PROFILE.md). Independent fixture authors work separately from production implementation. [CONFORMANCE_CASES.json](CONFORMANCE_CASES.json) remains declarative until executed.

## Independent oracle and evidence

Use a separately reviewed generator with at least 80 decimal digits. Pin generator source, arithmetic/CDF method, precision, exact inputs, dependency versions and eventual artifact hash. Never import/invoke production evaluation or transcribe its outputs as expectations. Crosscheck interior analytic Greeks using high-precision derivatives/finite differences away from kinks; differences support, rather than replace, the independent oracle. Endpoint statuses/values follow symbolic one-sided derivations in MODEL_PROFILE.

Retain decimal inputs, high-precision expectations, independently rounded binary64 expectations where applicable, statuses/reasons/quality and units. Recalled/published candidate numbers remain unverified until independently derived. Regeneration on failure requires a documented reviewed oracle/contract correction. A reviewer distinct from oracle author and production implementer inspects oracle evidence.

Executed checks record source commit/dirty state, command, exit/results, OS/architecture, Python/dependencies and applicable artifact hashes. Distinguish source checks from installed-wheel/runtime checks. Never infer platform results from another platform or an unexecuted workflow. Respect reserved resources; runtime work waits for actual availability.

## Numerical assertions

Ordinary interior prices/Greeks require abs(actual-expected)<=1e-10+1e-10*abs(expected), in canonical units. This initial maximum regression budget does not authorize persistence rounding. Analytic zero endpoints produce specified zero without NaN. Nonzero tails require explicit tighter allowances whenever the ordinary absolute allowance would admit a materially wrong zero. Each fixture states and justifies its allowance from oracle precision/representation before acceptance.

Finite outputs meet approved budgets; failure cases match independently expected reasons/null values. Unrepresentable requests require explicit numerical_failure, never successful infinity. A production limitation on representable oracle inputs remains a documented domain limitation, not an invented expected failure.

IV tests bind cap/tolerances and verify worst-case enclosed residual AND width, endpoint certification, bracket containment against independent root, deterministic iteration accounting and config identity. Independently review and qualify the production forward/bound enclosure method, including decimal/clock conversion and transcendental error; an ordinary regression tolerance is not a proven production error bound. Compare root error against certified interval/numerical budget instead of one arbitrary decimal root. Reject small residual with wide bracket. Distinguish cap exceedance, invalid price, nonidentifiable inverse, precision failure and iteration limit.

## Required families

| Family | Independent expectations |
| --- | --- |
| Interior | Call/put, nonzero q, negative r/q, unequal S/K, short/long T, ordinary/deep ITM/OTM, signed/absolute delta |
| Terminal | T0 with S<K/S>K/S=K, both rights, sigma0/positive, individual Greek statuses, right-time Theta, nonidentifiable IV |
| Zero volatility | H positive/negative/exact0, both rights, right-sigma Vega, spatial/rate kinks, zero/nonzero time slopes |
| Time | Exact ns subtraction, DTE0 with T>0, negative DTE/expired model, absent/contradictory civil binding, date-only expiry |
| IV bounds | Exact lower/asymptote, one representable price either side, capped root, root beyond cap, exhaustion/stagnation |
| Conditioning | Tiny Vega, nearly coincident bounds, representable tails, destructive overflow/underflow, no kink widening |
| Units | Multipliers 10/100/150, signed versus absolute delta, annual theta/unit r/sigma, no implicit position scaling |
| Readiness | Absent sigma with solvable IV, supplied Greek without computed dependencies, stale/future facts, structural versus semantic failure |
| Profile | European scalar; unsupported American/Bermudan/composite/adjusted/discrete-dividend/lag; true supplied provenance |
| Quotes | Locked, crossed, negative, one-sided, zero midpoint, stale/future; bound errors distinct from eligibility |

Construct exact H=0 through original operand identities, e.g. r=q,S=K. Lower/asymptote fixtures retain original decimal quotes and require analytic endpoint proof or qualified enclosures; binary64 equality is insufficient. Include r=q=0 analytically exact bounds, nonzero-rate/carry transcendental bounds whose converted quote rounds onto the bound from either side, collapsed rounded lower/upper bounds and uncertain cap/midpoint comparisons. Expect bound_precision when refinement cannot resolve them. Include safely interior nonzero-rate/carry cases to show conservative certification does not indiscriminately block ordinary inversion. No expectation may manufacture acceptance by clamping economically different prices.

## Complementary properties and integration

Put-call parity, equal call/put Gamma/Vega, price monotonicity in volatility, signed/absolute mapping and multiplier-once complement independent literals. IV forward prices come from independent oracle, not only production roundtrips. Verify output/config identity, causal exclusion and readiness independent of unrelated missing facts.

EQ185/EQ186/EQ187 qualify canonical bytes, typed roundtrip and direct -> worker -> stored full Result parity: value/null, status/reason, unit, quality, coverage, causal bindings, origin, model/formula/schema/config/package identities and digest. Value equality alone is insufficient. Qualify batch/replay, cancellation/publication and logical resource bounds without claiming incremental modes or hard RSS caps.

Actual local builds/installs and platform receipts apply once implementation exists; documentation freeze does not invent builds. Release requires integrated validation, accepted immutable artifacts and an actual browser demo of computed/stored synthetic outputs. Merged contracts/code alone are not release acceptance.
