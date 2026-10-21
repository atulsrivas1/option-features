# Candidate mathematical profile: option-bsm1

Status: draft before EQ182 admission. Owner approved independent R25 progression without blanket R18/EQ146 or EQ143/EQ144 acceptance; no implementation, numerical fixture execution or legacy parity is claimed. R25 contract/compatibility, executor/resource and numerical/integrated qualification remain required. The coordinator must resolve the listed open contracts and obtain independent contract/fixture review before freezing this profile.

## Scope and operands

Candidate computed model: European vanilla call/put on one scalar underlying, supplied spot/strike in the same currency and adjustment basis, flat continuously compounded r/q, annual decimal volatility and ACT/365F. Require finite positive S/K, finite r/q and nonnegative sigma. Negative finite rates/carry are allowed; numerical overflow has an explicit failure state. Contract definition, fixing/expiry, deliverable/multiplier, model and underlying source identity are explicit supplied facts.

American/Bermudan exercise, baskets/composite or adjusted deliverables, discrete cash dividends, stochastic/local volatility and fixing/payment-lag valuation are not covered by applying this profile. Keep their matrix requirements visible as unsupported/unqualified scope with ownership under EQ182; initial support does not establish full option-matrix coverage. Supplied Greek/IV facts may be admitted independently with their actual model/units/provenance and supported producer contract; never label them computed BSM.

## Price and derivatives

For T>0 and sigma>0, define A=S exp(-qT), B=K exp(-rT), d1=[ln(S/K)+(r-q+sigma^2/2)T]/(sigma sqrt(T)), d2=d1-sigma sqrt(T). With eta=1 for call and -1 for put, V=eta[A Phi(eta d1)-B Phi(eta d2)]. Phi is the standard normal CDF. This is an original specification of public mathematical relationships; no external implementation code is copied.

Canonical outputs are per underlying payoff unit: signed delta=dV/dS; gamma=d2V/dS2; vega=dV/dsigma; rho=dV/dr holding q fixed; calendar theta=-dV/dT holding S/r/q/sigma fixed. Rates/volatility use unit changes and theta is per year. Explicit per-percentage-point/per-basis-point/per-day projections have separately named units and scales. Absolute delta is an explicit abs(signed_delta) projection; it cannot replace signed delta. A multiplier is applied once only in explicitly named per-contract projections.

Public crosscheck: [OpenGamma Strata's official implementation](https://raw.githubusercontent.com/OpenGamma/Strata/main/modules/pricer/src/main/java/com/opengamma/strata/pricer/impl/option/BlackScholesFormulaRepository.java). The implementation uses the half-variance term above; its class-level explanatory expression omits that factor. This project does not adopt arbitrary finite reference values for ambiguous model limits.

## Clocks and limiting cases

Model T=(fixing_or_exercise_ns-valuation_ns)/(365*86400*10^9) with exact integer instants before final numeric conversion. Separate fixing, last-trading and payment instants. Unsupported lag conventions are unavailable/unsupported; do not choose midnight from a date-only expiry.

Calendar DTE is expiry_civil_ordinal-valuation_civil_ordinal under an explicitly supplied admitted civil-date/timezone binding, not ceil(T*365). I/O supplies and certifies that binding; kernels do not read wall time or timezone files. Same-day DTE0 may have positive T. Missing/contradictory bindings must not invent a calendar.

At T=0 price is max(eta*(S-K),0); IV is nonidentifiable. At sigma=0,T>0 price is max(eta*(A-B),0). Freeze per-Greek limiting values and nondifferentiability independently before Ready; a valid price need not make every Greek available. Negative T is expired/not-applicable rather than a numerical IV problem. Do not force an undefined kink to a conventional half-delta.

## IV contract

Select the exact quote basis, model/currency/expiry frame and eligibility policy in the request. For T>0, call lower=max(A-B,0), upper=A; put lower=max(B-A,0), upper=B. The lower bound can represent sigma0; the upper bound is an asymptote without a finite root. Outside-bound prices are invalid, not solver nonconvergence. At expiry the inverse is nonidentifiable.

Candidate bounded monotonic bracketed search: request binds max_sigma, iteration budget, price absolute/relative tolerances and volatility-width tolerance. Require positive finite tolerances and a declared finite cap; no implicit unbounded doubling. Both price residual and bracket width must meet the declared acceptance, with exact convergence metadata. A root beyond max_sigma is bracket_exceeded, not proof of no mathematical root. Tiny-vega cases need uncertainty/conditioning evidence; residual alone is insufficient. These numeric bounds/error budgets remain a named admission decision, not an implemented default.

## Reference, liquidity and chain contracts

Moneyness candidate is K/S as a named strike/spot ratio, with call/put OTM interpretation separately specified. Preserve exact supplied multiplier and scalar deliverable/action identity; never assume 100. Spread candidate is (ask-bid)/((ask+bid)/2)*10000 basis points for eligible nonnegative bid/ask and positive midpoint. Locked quotes may produce observed zero; crossed, one-sided, stale and zero-mid cases retain distinct ineligible/unavailable reasons.

Quote coverage candidate is eligible observed members / declared expected members of a frozen population/window. Empty denominator is undefined, not zero coverage; event-count coverage is not time coverage. Missing/partial chains remain distinguishable from observed zero activity. Raw chain sums/counts do not deliver the inventory's activity score. EQ214/EQ182 must resolve a permitted versioned score or leave the named score blocked; liquidity-score policy remains R29/EQ207.

## Required decisions before freeze

Exact model/deliverable admission; civil-date binding; Greek limits/error budgets and finite numeric domains; IV quote basis/bracket/tolerances/budget; chain-score contract; common precision/rounding and canonical units; native option transport and worker admission; independent expected fixtures and package/artifact compatibility. Unsupported or unresolved records do not count as delivered matrix coverage.
