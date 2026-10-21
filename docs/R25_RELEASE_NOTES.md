# R25 release notes — 0.1.0a1 candidate

**UNRELEASED; final qualification/acceptance pending.** No date/tag, registry publication or final platform pass is claimed. Final exact-artifact acceptance evidence is not yet published; follow [EQ187](https://github.com/atulsrivas1/equity-features/issues/532). Earlier cohort/component runs do not qualify later edits or rebuilt wheels.

## Scope and new APIs

The first alpha adds independently packaged `option-feature-contracts` and `option-features`, each `0.1.0a1`. Contracts expose immutable records, closed validation, bounded payload conversion and domain-separated digests. `option_features.evaluate(snapshot, request)` returns ordered typed results with explicit status, quality, coverage, provenance and applicable numerical evidence.

Nine matrix outputs: `contract.dte`, `contract.moneyness`, `contract.multiplier`, `liquidity.spread_bps`, `quality.quote_coverage`, `chain.activity`, `greeks.delta`, `greeks.gamma`, `volatility.implied_volatility`. Five foundation outputs: `pricing.price`, `greeks.signed_delta`, `greeks.vega`, `greeks.rho`, `greeks.theta`; these do not add matrix coverage. [Scope/units](../README.md#calculations) distinguish absolute delta, civil DTE and per-underlying price/Greek conventions.

`option-quote-count1` counts eligible declared slots per contract. Original `option-chain-breadth1` is `100*A/N`, where active expected members require an eligible positive trade in the window and an eligible causal current quote. Both require explicit completeness; unknown is not zero, admitted empty ratios remain undefined with explicit empty coverage. Neither claims private-algorithm parity or continuous-time coverage.

Pure calculations perform no fetching/storage/clock/credential access. Independently supplied metrics retain their actual origin/model. Initial computed scope is European scalar vanilla, flat continuous rate/carry, ACT/365F, coincident fixing/payment. American/Bermudan, adjusted/basket deliverables, discrete dividends, stochastic/local volatility and payment lags are unsupported. Endpoint nondifferentiability, nonidentifiable inversion and exhausted precision remain explicit outcomes. No tolerance clamp changes an economic endpoint. See [model](r25/MODEL_PROFILE.md), [boundary](r25/BOUNDARY_CONTRACT.md), [method](r25/NUMERICAL_METHOD.md).

## Compatibility and limits

CPython `>=3.12,<3.13`. Project cohort versions: `option-feature-contracts==0.1.0a1`, `option-features==0.1.0a1`, `option-feature-io==0.1.0a1`, `option-feature-workers==0.1.0a1`. Exact numerical/storage backends are `python-flint==0.9.0` and `duckdb==1.5.6`; individual package direct dependencies are listed in the [README](../README.md). This is a compatibility cohort, not a claim that every layer directly depends on every package. Exact source/wheel hashes, complete inventory, interpreter patch and platform require qualification. Alpha labels do not promise a stable API.

Only batch snapshots/replay of independent snapshots are admitted; no incremental update/restore/merge. Supplied spot introduces no unused equity dependency; equity packages never import options. Fixed count/byte/scalar/Decimal/range/solver ceilings apply and callers may lower them. There is no hard RSS guarantee, throughput claim, private-score parity, real/provider dataset acceptance or production-service qualification.

## Validation and publication

Remaining final evidence includes independently reviewed wire-identical fixtures, exact-source rebuilt wheels/sdists and clean installation on each supported platform, actual direct/batch/replay/stored semantic parity, resource/retry/cancellation/tamper checks, native-license inventory and an inspected stored-output browser demo. Windows and Linux require separate runs and canonical-output comparison. Source review and historical component checks do not replace final receipts. Local builds/tests provide merge evidence; hosted CI is optional.

Install only retained locally qualified wheels with reviewed hashes/platform locks. Controlled build identity is established before wheel creation, not inferred from a source install. Own code is [Apache-2.0](../LICENSE); dependencies/native components retain separate licenses/notices requiring artifact-specific inventory. No data rights are granted. Public registry/package publication retains owner approval.

[Implementation PR](https://github.com/atulsrivas1/option-features/pull/3), [R25 epic](https://github.com/atulsrivas1/equity-features/issues/526), [release page](https://github.com/atulsrivas1/option-features/releases), [version policy](VERSIONING.md).
