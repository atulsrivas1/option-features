# R25 contract decisions for EQ182

Status: coordinator proposal for independent review, not frozen implementation admission. The owner started the first option release after GOV037 preparation was merged. R25 proceeds independently of R18; exact-commit local validation and independent review provide merge proof. Active release owners and resource reservations remain protected.

## Native option boundaries and actual dependencies

Select independently versioned option-native contracts, codec, new separate DuckDB generation storage and a bounded option worker. Existing shares-only equity batches, closed codecs and one-instrument admission are not extended or monkey-patched. Numerical libraries contain no data access, storage, credentials, clocks or scheduling.

R25 consumes supplied spot/rate/carry facts. No admitted R25 formula currently calls an equity calculation, so the initial contracts and kernel dependency set does not add an unused equity package. The equity source cohort is reference-only; it is not an installed lock. Options may later consume selected equity public APIs through exact qualified pins. Equity packages never import options. Strategies may depend on both. A real reused producer must bring its true prerequisites and compatibility evidence.

## Matrix identity decisions

[Feature bindings](FEATURE_BINDINGS.json) maps all nine selected identities to owner, scope, units and independent operands. `greeks.delta` is absolute delta; `greeks.signed_delta` is an additional explicit derivative, not an alias that changes the inventory unit. The underlying option and underlying equity retain separate identities. A multiplier is applied once only in explicitly named per-contract projections.

`quality.quote_coverage` uses the original named `option-quote-count1` contract-level sampling ratio: unique eligible observed slots divided by independently declared expected slots for the same contract and half-open window. Slot definitions and completeness proofs come from an admitted sampling plan. They cannot be derived from observed rows. Zero expected slots is undefined; lost observations and unknown ingestion completeness differ. This does not implement continuous-time quote coverage or claim equivalence to a different source algorithm.

`chain.activity` uses original `option-chain-breadth1`: `100*A/N`, with N frozen expected contracts and A distinct expected contracts having an eligible positive-size trade in the half-open window and a current eligible causal quote at valuation. Require complete admitted trade/quote coverage for the whole population/window. N=0 is undefined. Complete observed inactivity yields zero; unknown/partial coverage is unavailable. Duplicate events do not multiply participation; only the admitted latest causal revision counts. Locked positive-midpoint quotes can qualify, crossed/negative/one-sided/stale/future-known quotes cannot. The eligibility config is hashed. This is an activity breadth score, not raw totals, liquidity policy or an assertion of private algorithm parity.

These are new explicit formulas for the selected library contract. Source declarations, matching names and normalized units are not evidence of numerical or behavioral parity with an existing private producer. Such parity remains visible in the binding residual ledger. Independent contract review must assess definitions before they become frozen.

## Model and execution profile

Select European vanilla scalar-underlying BSM with explicit continuously compounded rates/carry and ACT365F instants. Keep fixing, payment and civil expiry distinct. Unsupported profiles remain explicit, not silently treated European. [Mathematical profile](MODEL_PROFILE.md), [numerical acceptance](NUMERICAL_ACCEPTANCE.md) and [boundary contract](BOUNDARY_CONTRACT.md) specify exact admission/limits and outcomes; independently reviewed fixture definitions must agree.

Initial execution is a pure frozen snapshot and independent-snapshot replay, with a bounded sequential worker baseline. Incremental state/update/restore/merge is unqualified; no capability claim comes from a source registry declaring both modes. Parallel modes require separate ordering/result/resource parity. One owner controls logical CPU/memory/I/O reservations; this is not a hard RSS cap. Whole-generation publication distinguishes calculated results from committed/readable output.

## Qualification and remaining gates

Exact packages/artifacts are built and qualified after implementation; they are not prerequisites for authoring the contract that defines them. Frozen interfaces, fixture definitions and qualification protocols precede fresh parallel implementation authors. Actual local numerical/build/installed/integration validation and independent PR review precede merge of the applicable implementation. Cross-platform claims require real platform-specific evidence. No hosted CI requirement is introduced.

The official EQ142 timing reservation still lacks a terminal exit receipt at this checkpoint. Contract source authoring and text/JSON/link checks proceed; numerical imports/tests/builds/benchmarks/database work do not run during that reservation. No performance, platform, artifact or numerical acceptance is claimed here. Every unresolved profile/mode/parity/data requirement stays with its named owner in the binding ledger, and no whole-release completion is inferred from these design choices.

## Concrete C04 selection and source-authoring gate

Select [option-arb-bsm1/version1](NUMERICAL_METHOD.md), exact python-flint==0.9.0 with bounded precision and explicit numerical range limits. The separate mpmath==1.3.0 [oracle source](ORACLE_IMPLEMENTATION.md) is an unexecuted independent expected-value tool. DuckDB==1.5.6 is the candidate storage dependency; no artifact is yet qualified. The coordinator may freeze reviewed source definitions and grant the three source-authoring tracks under [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md); consumer producer edges still gate actual integration, merge and release evidence. The source-authoring baseline can be the reviewed immutable candidate commit while source/oracle runtime validation holds its draft PR unmerged. No local runtime is admitted during the exclusive study window and no unexecuted tool is claimed tested.

## Explicit record-hash domains

Independent exact-wire fixture preparation found the hash formula named `record_type` without enumerating its individual-record literals. The coordinator clarification in BOUNDARY_CONTRACT explicitly freezes the existing schema names so independent producers need not infer them from implementation. Historical source freeze9403854 remains retained; the amended manifest records the changed boundary bytes. This is a source-contract clarification, not a numerical execution or artifact acceptance claim.

## Admitted empty coverage and computed model identity

Independent wire fixture review exposed optional-metadata ambiguity. The coordinator selects explicit complete zero/zero Coverage for an admitted empty sampling/population set while keeping the undefined value null; missing or unadmitted completeness retains null coverage. This preserves known population evidence without inventing observations. Branch dependencies stop at failed prerequisites and exclude members outside an empty population. Selected computed model facts identify option-bsm1; synthetic provenance remains in InputBinding, while supplied producer identities stay intact. These metadata/admission clarifications require independent contract review and matching source/tests, not numerical tolerance changes.
