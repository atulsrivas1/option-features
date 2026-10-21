# Option features

Pure option calculations and typed contracts for caller-supplied facts. Calculations do not fetch data, read files/databases, access credentials, schedule jobs or publish outputs.

**R25 / 0.1.0a1 is UNRELEASED and under qualification.** Implementation/source review does not establish release acceptance. Final numerical fixtures, rebuilt artifact qualification, integration and an inspected stored-output browser demo remain gates. See [release notes](docs/R25_RELEASE_NOTES.md) and [R25 acceptance](https://github.com/atulsrivas1/equity-features/issues/532). No PyPI publication is claimed.

## Calculations

R25 implements nine selected matrix outputs. Missing prerequisites produce explicit statuses rather than invented values.

| Output | Meaning |
| --- | --- |
| `contract.dte` | Expiry civil ordinal minus valuation ordinal under supplied bindings; not pricing time. |
| `contract.moneyness` | Strike / positive causal spot. |
| `contract.multiplier` | Supplied underlying units per contract; no default 100. |
| `liquidity.spread_bps` | `10000 * (ask - bid) / midpoint` for an eligible nonnegative, noncrossed quote with positive midpoint. |
| `quality.quote_coverage` | Distinct eligible observed slots / independently declared expected slots for one contract/window (`option-quote-count1`). |
| `chain.activity` | `100 * A / N`: active expected members / expected members (`option-chain-breadth1`). Active means an eligible positive-size trade in `[start,end)` and an eligible causal current quote. |
| `greeks.delta` | Absolute delta, not the signed derivative. |
| `greeks.gamma` | Second price derivative per underlying payoff unit, in inverse currency units. |
| `volatility.implied_volatility` | Annual decimal volatility from bounded midpoint-price inversion. |

Coverage/activity require explicit completeness evidence. Unknown is not zero; admitted empty populations have an undefined ratio with explicit empty coverage. These original count/breadth formulas claim no equivalence to private scores or continuous-time coverage.

Additional foundation outputs are `pricing.price`, `greeks.signed_delta`, `greeks.vega`, `greeks.rho` and `greeks.theta`; they do not increase the nine-feature matrix count. Price is per underlying payoff unit, vega/rho per unit annual volatility/rate and theta per ACT/365F year. No percentage-point, daily or per-contract rescaling is implicit. See [model and units](docs/r25/MODEL_PROFILE.md) and [feature bindings](docs/r25/FEATURE_BINDINGS.json).

## Typed API and supplied facts

`option-feature-contracts==0.1.0a1` provides immutable records and closed validation using only the standard library. `option-features==0.1.0a1` exposes:

```python
from option_feature_contracts import Request, Snapshot
from option_features import evaluate

def calculate(snapshot: Snapshot, request: Request):
    return evaluate(snapshot, request)
```

Callers supply definitions, distinct option/underlying IDs, exact economic Decimals, model facts, event/known-at clocks, civil dates and provenance/rights bindings. See [contracts](docs/CONTRACTS_API.md), [calculation API](docs/FEATURES_API.md) and the complete [typed synthetic scenario](https://github.com/atulsrivas1/option-feature-workers/blob/codex/r25-worker-implementation/examples/synthetic_scenario.py).

The computed model admits European vanilla on a scalar underlying, flat continuous rate/carry, ACT/365F time and coincident fixing/payment. American/Bermudan, adjusted/basket deliverables, discrete dividends, local/stochastic volatility and payment lags remain unsupported. Independently supplied metrics retain actual origin/model and are not relabelled computed BSM. Reference outputs may survive unavailable model inputs.

Only batch snapshots and replay of independent snapshots are supported; no incremental update/restore/merge. Supplied spot needs no equity calculation dependency: none is added. Future selected equity APIs require compatibility qualification; equity packages never import options.

## Local artifacts

CPython `>=3.12,<3.13` is required. Numerical dependencies are exactly `option-feature-contracts==0.1.0a1` and `python-flint==0.9.0`. Arb work has one numerical owner/native thread, bounded precision tiers and finite solver work. No speed or hard RSS claim is made.

Use reviewed locally qualified wheels, an exact platform lock and hashes. Replace placeholders with retained artifacts and a clean runtime interpreter:

```text
python -m pip --python <clean-runtime-python> install --no-index --find-links <qualified-wheelhouse> --require-hashes --no-compile -r <reviewed-platform-lock.txt>
```

This implies no registry availability. Source/editable installation alone does not create the controlled build identity required by workers. See the [qualification plan](docs/NUMERICAL_QUALIFICATION_PLAN.md) and [worker verification](https://github.com/atulsrivas1/option-feature-workers/blob/codex/r25-worker-implementation/docs/API.md). Worker runs require fresh `python -B`, no package bytecode caches and no alternate cache prefix.

Caller limits may lower fixed ceilings: 16 MiB wire envelopes, 100,000 snapshot rows, 1,000 requested contracts, 32 outputs, 32,001 result rows and 4,096 solver iterations. Scalar/string/Decimal and numerical-range limits also apply; see [boundary contracts](docs/r25/BOUNDARY_CONTRACT.md). Admission limits are not measured RSS bounds.

[Implementation PR](https://github.com/atulsrivas1/option-features/pull/3), [contracts PR](https://github.com/atulsrivas1/option-features/pull/2), [R25 epic](https://github.com/atulsrivas1/equity-features/issues/526), [releases](https://github.com/atulsrivas1/option-features/releases), [version policy](docs/VERSIONING.md), [handoff](docs/SESSION_HANDOFF.md), [work agreements](AGENTS.md).

Own code is [Apache-2.0](LICENSE). Python-flint/bundled native components retain separate licenses/notices requiring artifact-specific qualification. Apache-2.0 does not relicense dependencies or grant provider/private-data rights.
