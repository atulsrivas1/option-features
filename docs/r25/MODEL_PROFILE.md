# Mathematical contract: option-bsm1

Status: EQ182 freeze candidate, October 20, 2026. Selected R25 computed profile, not implementation, executed evidence or complete matrix coverage. Independent contract review and [numerical acceptance](NUMERICAL_ACCEPTANCE.md) remain required. R25 proceeds independently of R18; existing study/resource ownership remains protected.

## Admitted profile and operands

European vanilla call/put on one scalar underlying, supplied spot S and strike K in the same currency and action basis, flat continuously compounded rate r and carry q, annual decimal volatility sigma, ACT/365F time. S,K must convert to positive finite binary64; r,q are finite, including negative values; sigma is finite and nonnegative. Exact source decimals define mathematical S/K and quote price; binary64 model facts denote their exact represented real numbers and T its exact rational clock difference. Binary64 conversion/evaluation approximates these operands; it does not redefine an economic endpoint. Retain original facts and account for conversion in numerical error bounds. Conversion never silently rescales currency or adjusts a deliverable. Reject bool as numeric input. Calculations perform no clock reads, acquisition, storage or timezone lookup.

Admit scalar-underlying deliverables with explicit positive multiplier, European exercise and coincident fixing/payment instants. Cash/physical settlement describe the same scalar payoff-equivalent valuation; settlement workflows are not implemented. Last trade stays separate. American/Bermudan exercise, adjusted/composite/basket deliverables, discrete cash dividends, stochastic/local volatility and fixing/payment lags remain unsupported model profiles under EQ182, not fulfilled matrix requirements. Admitted supplied metrics retain actual producer model/units and are not labelled computed BSM.

Batch evaluates a frozen causal snapshot; replay independently evaluates a sequence of snapshots. Neither implies incremental update/restore/merge. Missing sigma does not suppress IV; missing pricing inputs do not suppress independently supplied metrics/reference outputs.

## Clocks and causal admission

T=(fixing_ns-valuation_ns)/(365*86400*10^9). Subtract bounded integer UTC nanoseconds exactly before numerical conversion. Do not substitute last-trade, payment, calendar DTE or date-only expiry. T<0 yields not_applicable/expired for model outputs before arithmetic; T=0 follows endpoints below. Calendar DTE is expiry_civil_ordinal minus valuation_civil_ordinal under a supplied certified civil-date/timezone binding. It can be negative; DTE0 can coexist with T>0. Missing/contradictory bindings cannot invent midnight or a calendar.

Required facts satisfy request effective/event and known-at cutoff rules; future-known/stale facts remain distinct from absent facts. Only selected-output dependencies govern readiness. Contract and underlying IDs stay distinct; contracts never become shares to fit equity records.

## Interior equations and units

For T>0,sigma>0, eta=+1 for call and -1 for put. Phi is standard normal CDF; phi(x)=exp(-x^2/2)/sqrt(2*pi).

- A=S exp(-qT), B=K exp(-rT).
- d1=[ln(S/K)+(r-q+sigma^2/2)T]/[sigma sqrt(T)]; d2=d1-sigma sqrt(T).
- V=eta[A Phi(eta d1)-B Phi(eta d2)].
- D=eta exp(-qT) Phi(eta d1).
- Gamma=exp(-qT) phi(d1)/[S sigma sqrt(T)].
- Vega=A phi(d1) sqrt(T).
- Rho=eta T B Phi(eta d2).
- Theta=-A phi(d1) sigma/[2 sqrt(T)]+eta q A Phi(eta d1)-eta r B Phi(eta d2).

D=dV/dS, Gamma=d^2V/dS^2, Vega=dV/dsigma, Rho=dV/dr holding q fixed, Theta=-dV/dT holding S,r,q,sigma fixed. These are original specifications of public mathematical relationships. The [official OpenGamma implementation](https://raw.githubusercontent.com/OpenGamma/Strata/main/modules/pricer/src/main/java/com/opengamma/strata/pricer/impl/option/BlackScholesFormulaRepository.java) is a crosscheck, not copied code. Its class-level explanatory expression omits the half-variance factor used by implementation; arbitrary finite endpoint fallback conventions are not adopted.

| Output ID | Meaning and canonical unit |
| --- | --- |
| pricing.price | V, currency per underlying payoff unit |
| greeks.delta | abs(D), absolute underlying-unit delta; matrix absolute_delta identity |
| greeks.signed_delta | D, signed underlying-unit delta; additional foundation output |
| greeks.gamma | Gamma, inverse underlying spot-price unit |
| greeks.vega | Vega, currency per payoff unit per unit annual decimal volatility |
| greeks.rho | Rho, currency per payoff unit per unit continuously compounded annual rate |
| greeks.theta | Theta, currency per payoff unit per ACT/365F year |
| volatility.implied_volatility | annual decimal volatility |

Unavailable D makes abs(D) unavailable. Do not interchange greeks.delta and greeks.signed_delta. Price/signed delta/vega/rho/theta are foundation outputs, not additional inventory coverage. Per-percentage-point vega/rho multiply by 0.01; per-basis-point rho by 0.0001; per-day theta divides 365. Projections require separately named IDs/units before implementation; none is implicit. Per-contract projections multiply by supplied multiplier once. Position quantity is separate. Persist unrounded values; display rounding is separate.

## Exact endpoints

Endpoint equality must be established from original operands analytically or with qualified numerical enclosure, without tolerance-based kink widening. For example S=K,r=q establishes H=0 symbolically. Rounded binary64 equality alone does not prove a spatial/time/zero-volatility kink; unresolved ordering yields numerical_failure/bound_precision for affected outputs. Never return conventional half-delta.

At T=0, V=max(eta*(S-K),0). If S!=K: D=eta when in the money, else 0; Gamma=Vega=Rho=0; Theta=eta*(q*S-r*K) when in the money, else 0. This Theta is the negative right-time derivative. At S=K: D/Gamma are undefined/nondifferentiable_payoff; Vega=Rho=0 because terminal price is parameter-independent. Theta at S=K,sigma>0 is undefined/nonfinite_terminal_time_derivative. At S=K,sigma=0, Theta=-max(eta*(r-q)*S,0), explicitly the negative right-time derivative; evidence identifies this directional convention. Terminal IV is nonidentifiable_inverse/terminal_price.

At T>0,sigma=0, H=A-B and V=max(eta*H,0). For H!=0: D=eta*exp(-qT) when in the money, else 0; Gamma=Vega=0; Rho=eta*T*B when in the money, else 0; Theta=eta*(q*A-r*B) when in the money, else 0. Vega is the right-sigma derivative.

At T>0,sigma=0,H=0: D/Gamma/Rho are undefined/nondifferentiable_zero_volatility; Vega=A*sqrt(T)/sqrt(2*pi), a right-sigma derivative. Theta is undefined/nondifferentiable_zero_volatility unless q*A-r*B is exactly 0, when Theta=0. Each output retains its own status; valid price/directional Vega does not make all Greeks available. Abs(D) is not an invented derivative at a kink.

## IV inversion

R25 computed IV explicitly selects midpoint: eligible nonnegative bid/ask, bid<=ask, positive midpoint, causal facts, caller-selected quote/spot age limits. Locked positive quotes are eligible. Crossed/negative quotes are invalid; one-sided/stale/future-known retain their reasons. Other quote bases are unsupported until qualified. Inversion takes p,S,K,r,q,T, never supplied sigma.

For T>0, call L=max(A-B,0), U=A; put L=max(B-A,0), U=B. These are mathematical bounds on original operands. Certified p<L or p>U is invalid_input/price_out_of_bounds, not exhaustion. Certified p=L returns sigma 0, zero residual/width/iterations and lower_boundary evidence. Certified p=U is nonidentifiable_inverse/upper_asymptote, never infinity or a fabricated cap root. Rounded equality of converted p with an evaluated bound certifies neither endpoint. No epsilon clamp changes economic price.

Implementations must bind an independently reviewed forward/bound error method, accounting for original-decimal conversion, exact rational T conversion, arithmetic, exp/CDF and cancellation. One permissible policy encloses L,U in [Llo,Lhi],[Ulo,Uhi]. Exact decimal p<Llo or p>Uhi proves invalidity; p>Lhi and p<Ulo proves interior admission. An overlap requires analytic endpoint proof or a tighter qualified enclosure; otherwise numerical_failure/bound_precision. Analytically exact cases include r=q=0 bounds derived directly from original decimal S/K, or L=0 after a certified sign of A-B. Nonzero transcendental bounds cannot be called exact merely because they round to the quote. If distinct true bounds become indistinguishable, do not choose lower versus upper by branch order. Keep ordinary inversion admitted when independent error bounds establish strict interior ordering. Record enclosure/error-method identity and original/converted target in evidence. The ordinary regression tolerance below is not itself a bound on production error.

Bounded deterministic bisection defaults: max_sigma=8.0; max_iterations=256; price_abs_tol=1e-10; price_rel_tol=1e-10; vol_abs_tol=1e-10; vol_rel_tol=1e-10. Tolerances/max_sigma are finite positive; iterations a positive integer no greater than the initial 4096-iteration admission cap (default 256). Price tolerances are currency per payoff unit, volatility tolerances annual decimal volatility. Config changes change identity. Defaults describe numerical operations, not tick size/economic uncertainty.

Start [lo,hi]=[0,max_sigma]. A qualified upper enclosure for V(hi) strictly below exact p proves bracket_exceeded with endpoint evidence, not absence of a root beyond cap. An analytically certified exact cap root can be returned as such. Rounded equality V(hi)=p cannot certify it: refine price enclosure/bracket or return numerical_failure/bound_precision. Evaluate midpoints using the qualified forward-price error method; discard a half-interval only when its price ordering is certified. If price uncertainty overlaps target, refine the price enclosure or preserve enough volatility interval to contain all admissible roots. Accept c only when BOTH the worst-case enclosed abs(V(c)-p)<=price_abs_tol+price_rel_tol*abs(p) AND hi-lo<=vol_abs_tol+vol_rel_tol*abs(c), with c inside a certified root-containing bracket. Small residual or rounded equality cannot synthesize zero-width uncertainty. Precision unable to establish required ordering/convergence yields bound_precision or precision_exhausted, not an invented root.

Record candidate price/residual, lo/hi, iterations, tolerances, boundary flag and Vega. Exhaustion is iteration_limit. Finite-precision stagnation yields numerical_failure/precision_exhausted unless both acceptance criteria hold. Mark ill_conditioned when abs(Vega)*(vol_abs_tol+vol_rel_tol*abs(c))<=price_abs_tol+price_rel_tol*abs(p). Tiny Vega does not invalidate otherwise certified interval. Interval describes numerical inversion, not market-price uncertainty. Initial cancellation is between solves; per-iteration cancellation requires separately reviewed pure interface.

## Numerical behavior and remaining scope

Use stable logarithm/CDF/tail formulations and cancellation-aware pricing; expected fixtures use independent path. Finite negative r/q have no arbitrary prohibition. Overflow, destructive underflow, unresolved bound ordering or nonfinite required outputs produce numerical_failure, never caps or published NaN/Infinity. Tail probabilities may round to 0/1 only within independent case budgets. Finite output alone is not accuracy evidence. See [NUMERICAL_ACCEPTANCE.md](NUMERICAL_ACCEPTANCE.md).

Reference/liquidity/chain identities and activity-score policy are governed by canonical records/EQ214, not redefined here. European computation does not qualify unsupported models, time-weighted coverage, private chain-algorithm parity or another producer's supplied model. Residuals remain visible under EQ182; this freeze candidate claims no complete release coverage.
