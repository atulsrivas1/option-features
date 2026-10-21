# R25 source-authoring and integration gates

Scope: the already owner-adopted three-layer coordinator pattern for the selected R25 release. This plan does not waive a numerical, artifact, independent review or release gate. It separates interface-based source authoring from producer runtime acceptance so the three layers can actually progress in parallel.

## Contracts-based source admission

For the selected R25 release only, after independently reviewed EQ182 interfaces, mathematical methods and fixture definitions are frozen, scoped source authoring of EQ183/EQ184/EQ214, EQ185 and EQ186 may run as three fresh layer tracks under the coordinator agreement. EQ184's EQ183 edge and EQ186's EQ183/EQ184/EQ185/EQ214 edges remain producer runtime/integration prerequisites; they do not require producer Done before consumer source authoring against the frozen interface. EQ185 requires the real contracts-only bootstrap for runtime conformance. Consumers may reach integration Test, merge or acceptance only with actual compatible producers and required installed numerical evidence, never mocks. No predecessor is marked Done. EQ187 requires all actual producers and complete release evidence. Resource reservations remain independent execution gates; hosted CI is optional.

The coordinator records independent exact-source reviews, the contract manifest, source commit and per-track grant before starting the authors. The immutable reviewed candidate may be the pinned source-authoring baseline while its draft PR awaits execution validation; this does not merge unexecuted oracle tooling or declare EQ182 Done. Any dependent implementation PR is explicitly stacked on or linked to that candidate. No production/implementation merge bypasses exact local validation.

| Track | Stories | Source authoring inputs | Runtime/integration proof |
| --- | --- | --- | --- |
| Pure contracts/calculations | EQ183/EQ184/EQ214 | Reviewed frozen record/model/method/fixture interface | Contracts-only bootstrap first; actual independently checked pricing/Greeks before IV proof; six reference/liquidity/score outputs |
| Native I/O | EQ185 | Same frozen contracts and exact schemas | Real installed contracts; strict codec and separate DuckDB sink; actual numerical results for end-to-end proof |
| Bounded workers | EQ186 | Frozen evaluator/sink/cohort/execution protocols | Actual installed feature and I/O producers for numerical/integration proof; orchestration fakes prove only labelled orchestration behavior |
| Release integration | EQ187 | Coordinator may prepare harness/manifest | All actual producer artifacts and supported-platform numerical/direct-worker-stored/browser evidence |

The library track implements independently installable option-feature-contracts before numerical-package bootstrap. Neither I/O nor workers copy its types/hash rules. Proposed package versions are independently0.1.0a1; features -> contracts plus python-flint==0.9.0; I/O -> contracts plus duckdb==1.5.6; workers -> contracts/features/I/O. The independent oracle tool uses mpmath==1.3.0 and is not a production dependency. Exact alpha pins, source/artifact hashes and runtime closure must be qualified together before runtime acceptance. No source reference alone proves installation or registry availability. No equity package is added unless an actual selected public API is consumed.

The coordinator verified candidate DuckDB1.5.6 CPython3.12 Windowsx86-64 and Linuxx86-64 wheels on its [official PyPI page](https://pypi.org/project/duckdb/); no download/install or platform qualification is claimed. The numerical backend's artifact/license qualifications are in [NUMERICAL_METHOD.md](NUMERICAL_METHOD.md). Both dependencies need actual exact-artifact verification and local numerical/build/install evidence. Unsupported profiles/modes/private parity remain in [FEATURE_BINDINGS.json](FEATURE_BINDINGS.json).

## Worker and review boundaries

Fresh authors receive actual short-lived branches and private exact-path grants. Normative contract files remain coordinator-owned; authors report defects instead of redefining them. Each reports completion/blockers and actual checks to the coordinator, who continues review immediately rather than ending at a report. No push before coordinator review. Fresh independent read-only PR review, resolved findings and applicable exact-head local tests/builds/installs precede implementation merge. Current source-only validation is not numerical proof.

The exclusive official EQ142 reservation has no verified terminal exit receipt at this checkpoint. Source authoring, source AST/text/JSON/links/whitespace checks and read-only primary documentation research may proceed; numerical imports/tests/generators/builds/benchmarks/database operations remain held. All three authors must preserve this gate and unrelated release ownership. Source progress never silently releases the hold.

## Exact-source manifest

[CONTRACT_MANIFEST.json](CONTRACT_MANIFEST.json) binds normative files and independent fixture/oracle source definitions by SHA256, excluding itself. The final commit identity and independent approval/admission are recorded on EQ182 and the linked PR rather than placed self-referentially inside the manifest. Coordinator source-authoring freeze is not runtime/artifact/platform or whole-release acceptance. Native numerical methods/certificates remain implementation obligations, not guarantees inferred from a type declaration.
