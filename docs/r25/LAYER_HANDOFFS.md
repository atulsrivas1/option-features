# R25 layer handoffs before implementation

These handoffs prepare three fresh implementation workers; they do not launch runtime authoring. Coordinator resolves/amends contracts and pins their reviewed hashes before handing off. Read GOV037 and the current EQ146 acceptance evidence first.

## Libraries — option-features

Own proposed packages/option-contracts and packages/features. EQ182 owns canonical contracts, model/scope and matrix disposition; EQ183 pricing/Greeks; EQ184 IV; EQ214 reference/liquidity/chain. No I/O, credentials, scheduling, storage or source-dependent units inside kernels. Use the exact selected equity packages only when their public calculation is actually needed; supplied spot is a fact, not a forced equity computation. Distinct requested outputs have their own readiness. Do not copy accepted equity mathematics or count raw summaries as an activity score.

## I/O — option-feature-io

EQ185 owns option-input conversion and option-native serialization/sink contract. Keep separate option/underlying identities, quantities, clocks, multiplier/deliverable and supplied-versus-computed provenance. Qualify exact source schema/path/rights before any historical reads. Suitable DuckDB observations and labelled synthetic inputs are different provenance modes; neither fallback nor database existence establishes coverage/known-at.

Existing efio-json1/a4 exact codecs and efio-duckdb1 six-table schema do not admit new option records/tables. Design and review option-result1/option-generation1 transport/storage or an explicit backwards-compatible shared extension; preserve accepted equity behavior. Reuse supported public SDK capabilities only after conformance. Do not copy source code or insert option tables into an existing validated equity database. Output is a separate qualified destination with strict run/key/digest/version, repeat-write/conflict, ownership, atomic publication and full typed/readback parity contracts.

## Workers — option-feature-workers

EQ186 composes option-native requests, adapter inputs, selected library calls and sink commits. Existing WorkItem/TaskManifest admission, codec and core dispatcher are closed. The supplied path requires one instrument for every input row and cannot represent an option and distinct underlying by relabelling them. The calculate callback is a candidate seam, not proof that a new manifest/transport is accepted. EQ143/144/146 remain delivery prerequisites; exact reusable public extension versus option-owned execution shell is an unresolved coordinator decision before authoring.

One resource owner accounts for CPU/memory/I/O/backend threads and bounded in-flight work. Existing logical reservation limits are not hard RSS enforcement or fine IV cancellation. Preserve per-contract ordered events and exact populations; independent reference, supplied-Greek and price/IV branches do not wait for unrelated facts. Retry identity binds package/config/model/input/source and callback implementation, not just a task name. A changed result under the same key conflicts. Serialize sink ownership and distinguish calculation completion from published visibility; cancellation/recovery never fabricates success.

## Integration and release acceptance

EQ187 qualifies exact compatible package artifacts, all selected feature identities and supported modes on Windows/Linux, with independent direct/library-worker-stored result/status/quality/evidence parity. Small synthetic chain demo includes price/IV round-trip, supplied Greeks without solver inputs, missing/stale/future references, undefined Greeks and unavailable profile/partial chain states. Viewer shows actual stored output and provenance after implementation; no viewer, database or numerical demo is claimed here. API/SaaS is optional. Full R25 cannot close with unresolved activity-score/model/transport/residual ownership or unaccepted prerequisites.
