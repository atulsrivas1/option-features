# Unexecuted numerical qualification work

This is an evidence backlog for EQ183/EQ184/EQ214, not a list of passed cases.
All source probes and the independent fixture consumer are authored but unexecuted.
The exact oracle source remains coordinator-owned. A separate fixture author and
reviewer must produce wire-identical inputs/expectations after runtime admission;
the production author cannot turn its results into expected outputs.

| Normative family | Authored source probes | Independent wire fixture work still required |
| --- | --- | --- |
| Interior | Original S=K100,sigma2,T1 normal-symmetry put derivation; signed/absolute mapping | Both rights, nonzero carry, negative rate/carry, unequal S/K, short/long T, deep ITM/OTM;80/140digit oracle with exact binary64 fact ratios |
| Terminal | Both rights,S90/100/110,sigma0/positive, all outputs under native-import trap; exact dyadic directional Theta | Independent typed fixtures, nonzero ITM/OTM time slopes, per-output missing-fact precedence and context/evidence parity |
| Zero volatility | Both rights,H negative/zero/positive at r=q0, right-sigma Vega, Delta/Gamma/Rho kinks | Nonzero equal-rate/carry kinks, nonzero slopes, near-equality without tolerance widening, tail discount certificates |
| Time |365civil days reference; terminal; valid extremal clock difference precision failure | Same-day DTE0 with positive exact ns time, negative civil DTE with expired model, absent/contradictory/date-only bindings, representable clock conversion |
| IV bounds | Exact lower, exact upper asymptote, outside bound from manual rational derivations | Original decimal prices one representable step either side, nonzero transcendental rounding onto each bound, collapsed rounded bounds, ordinary interior roots, cap/no-cap, rescue overlap, iteration/stagnation and residual-versus-width counterexample |
| Conditioning | Source bounded dyadic/Decimal export and relative certificate; mandatory external nonzero-tail budget rule | Tiny Vega, erfc tails, positive economic values underflowing binary64 preview, overflow/cancellation, range limits, persisted endpoint outwardness and exact residual limits |
| Units | Multiplier10, canonical unit registry, explicit signed-to-absolute supplied projection | Multipliers100/150, annual theta/unit rate/sigma, explicit no position scaling, source basis/currency correspondence |
| Readiness | Reference without model facts, terminal zeroes without spot/model, specific sigma priority and future-known exclusion | Missing sigma with independently solvable IV, supplied Gamma without pricing facts, all stale/future/effective cases, unrelated input invariance and selected excluded provenance |
| Profile | Frozen profile admission source and explicit reason registry | European accepted; American/Bermudan/adjusted/basket/discrete dividend/stochastic/unknown/lag rejected; supplied producer identities retained |
| Quotes | Locked/crossed/zero-midpoint/spread, per-contract3/4slots, four-member breadth25 | Negative/one-sided/stale/future quotes; missing/incomplete/future certificates, empty slot/population, causal cancellation/duplicates/window endpoints and member definitions |

Complement oracle literals with executed put-call parity, equal call/put Gamma/Vega,
volatility monotonicity and enclosure inclusion. They cannot replace independent
expected values. Conversion tests must exercise ties-to-even, compact extreme
native exponents, actual persisted Decimal bounds and exact-zero distinctions.
Context tests must prove restored precision/threads after all failure stages and
serialization of competing callers. Finite work accounting needs instrumented
evidence against the five-tier and solver-evaluation ceilings.

The independent empirical oracle band's overlap with a production enclosure is
only a consistency check. It does not prove rigorous inclusion. Separate authored
exact-rational and analytic exp0/log1/sqrt4/erfc0 probes test directed conversion
and export against known values; full backend/transcendental qualification remains
mandatory. Oracle uncertainty cannot be fabricated narrower to fit an enclosure.

The mandatory fixture consumer requires all ten family tags and actually evaluates
each typed request. Tags alone cannot establish meaningful coverage: independent
review must inspect this family matrix, cases, budgets and expected metadata before
recording acceptance. It fails when required fixture evidence is absent.

Build and install exact contracts/features wheels with their embedded original
Apache LICENSE files and controlled source markers. Record source hashes, clean
staging/environment, command and result, wheel SHA256 and verified installed
RECORD. Inspect the pinned python-flint wheel and bundled native libraries/notices;
the wheel is not Apache/MIT-only by association with this source. No source build,
registry publication or production data is admitted implicitly. Run Windows and
Linux qualification independently; no platform inference is allowed.

Remaining release gates include actual complete direct/worker/stored Result parity,
artifact cohort verification, resource/cancellation/publication checks and browser
demo from real computed/stored synthetic results. Source availability and merged
implementation are distinct from these gates.
