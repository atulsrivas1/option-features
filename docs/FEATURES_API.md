# Calculation API and qualification checkpoint

## Separate R26 flow API

`option-flow-features==0.1.0a1` exports `option_flow_features.evaluate_flow`, `replay_flow`, `make_flow_checkpoint` and `restore_flow`, using only the new `option-flow-contracts==0.1.0a1` and standard library. These support batch, genuine chronological cuts and bounded full-prefix restore; they do not alter the original API below. Flow results retain exact rational numerator/denominator, units, status/reason, causal availability and typed evidence/dependencies. Discover [scope/API](r26/README.md), [mathematics](r26/MATHEMATICS.md), [output/profile bindings](r26/FEATURE_BINDINGS.json), [closed signatures and codecs](r26/FLOW_CONTRACT.md), [compatibility/mode/resource gates](r26/COMPATIBILITY.json), [usable synthetic example](../examples/r26/README.md) and [completed versus pending qualification](r26/LOCAL_QUALIFICATION.md). Three reserved EQ190 outputs return unsupported/equity_integration_unqualified until actual equity integration is accepted. R26 remains UNRELEASED.

`option-features==0.1.0a1` exposes `option_features.evaluate(snapshot, request)` and returns ordered immutable results. Nine selected matrix outputs plus five foundation pricing/Greek outputs retain their frozen units, model, causal admission, status, provenance, coverage and solver-evidence contracts. Only batch snapshots and replay of independent snapshots are admitted; no fetching, file/database access, credentials, clock reads or scheduling occurs in kernels.

## Current evidence — October 21, 2026

The original runtime hold is released. Both exact-source supported-platform component suites and reviewed successor fixtures have now executed successfully against original-wheel and original-sdist-built-wheel forms. These replace earlier source-only/unexecuted descriptions as current component evidence. Both final-wheel tamper suites passed seven rejection cases after verified computation; each platform also passed 172 additional methods in six package-layer isolation environments. See [current local qualification](R25_LOCAL_QUALIFICATION.md) for source commits, 216 cohort methods plus 172 isolated-layer methods per platform, fixture identity, artifact admission and final documentation/publication steps. Source PRs are now merged with qualified source trees preserved. Four five-scenario integration harnesses passed; broad golden integration passed all four Windows/Linux original/rebuilt cohorts, including 111 batch/retry cases and 111 replay cases per cohort. Full direct/worker/stored canonical payloads for all 111 cases/378 rows match across all four cohorts. The stored browser demo and supplemental all-14-output price/IV round trip were actually inspected. Final four-cohort byte comparison and fresh independent static wrapper review passed. Technical validation is complete; final documentation publication, lifecycle reconciliation and owner release-publication approval remain. **R25 remains UNRELEASED.**

The API still uses supplied spot without an unused equity dependency, independently packaged contracts and exact `python-flint==0.9.0`. Numerical work has one exclusive owner and one native thread; foreign context/process mutation is outside the admitted runtime. Source review, independent expectations and rigorous production enclosures remain distinct kinds of evidence.

## Historical source-authoring and correction record

The dated development runs and source-authoring restrictions below are preserved. Their statements that tests/fixtures were not run or qualification remained pending describe those earlier snapshots; the current report above governs qualification status.

# Calculation source candidate

Independent Vega assertions may provide an `oracle_vega_interval` over all
contract-admitted candidate volatilities. Its exact fields are low, high,
uncertainty_kind and relative_padding. The consumer requires the empirical label
`empirical_two_precision_plus_outward_relative_padding` and reviewed padding1e-58;
these are not a rigorous enclosure claim. It checks ordered nonnegative bounds
and candidate Vega membership. The optional admissible_candidate_sigma_interval
has exact low/high fields and must contain the returned candidate within ordered
nonnegative bounds. This does not substitute oracle-root point Vega for the
returned candidate's Vega. Without a Vega interval the existing point comparison
and frozen tolerance caps remain unchanged. Seven focused consumer assertion tests
passed; full fixtures require a newly admitted reviewed artifact.

The independently reviewed October21 coverage clarification preserves complete
empty population metadata: after causal plan/population and required complete
certificates are admitted, an undefined empty ratio carries Coverage0/0 with its
declared ID, completeness=True and the actual sampling type. Missing/future/
incomplete prerequisites retain coverage=None. Three focused source-development
tests pass for empty quote plans, empty activity populations and unknown-versus-
absent completeness, including negative admission variants.

October 21 runtime correction candidate: exact lower-bound IV candidates now use
the same rigorous Vega/conditioning inequality as interior candidates. An ITM
sigma0 root has right-sigma Vega0 and is ill-conditioned under positive requested
tolerances; both `lower_boundary` and `ill_conditioned` are retained. Uncertified
Vega/conditioning remains unknown. A fresh Windows source-development environment
passed29 feature tests, including an independently derived both-rights boundary
regression, and4 fixture-consumer assertion tests. The changed feature source was
imported explicitly; these runs do not qualify a rebuilt/installed feature wheel.

The independent fixture consumer now checks full Coverage/null and explicit
solver-evidence presence/conditional/fixed assertions, independent Vega and
conditioning, bracket containment and both convergence criteria. Separate
structural exception cases run through decoding and evaluation, preserving exact
reason assertions only where independently fixed. The artifact's combined cases
and exception cases SHA is recomputed; the externally pinned whole-artifact SHA
remains the operator trust anchor. A digest-shaped review field alone does not
authenticate an independent reviewer. Full reviewed-fixture execution and new
exact-artifact qualification remain coordinator gates.

`option-features==0.1.0a1` exposes `option_features.evaluate(snapshot, request)`.
It returns ordered frozen Results and owns all nine R25 feature producers plus
the five named foundation outputs. Source has been authored; implementation
review and actual numerical acceptance remain open. No tests/builds/installs,
oracle generation, backend imports, benchmarks or platform qualification ran
during source authoring under the original EQ142 reservation.

Only the frozen European scalar continuous-carry model and batch snapshots are
implemented here. Worker replay evaluates independent snapshots through this same
pure API. Unsupported profiles, unknown bounds, precision/export limits and
unqualified execution modes never count as fulfilled feature coverage. There are
no fetching, filesystem/database, scheduling, credential, wall-clock or metadata
reads in kernels. Supplied spot is a fact, so no unused equity dependency is added.

Contracts are independently packaged. Numerical dependencies are exact alpha
`option-feature-contracts==0.1.0a1` and `python-flint==0.9.0`. The module imports
without loading flint; actual nonterminal model arithmetic acquires one exclusive
numerical owner and lazily imports the backend. It restores precision/thread state
on success and failure, rejects reentrancy and uses native threads1. Foreign flint
context mutation while evaluation runs is outside the admitted profile. Terminal
symbolic paths and pure reference/supplied outputs need no backend import.

Forward certificates use original exact Decimal spot/strike and exact rational
clock time, binary64 facts as exact dyadics, fixed128/256/512/1024/2048-bit tiers,
and outward persisted Decimal intervals. Point values require a relative error
certificate against the persisted endpoints. IV discards a side only after strict
certified ordering and requires both enclosed price residual and bracket width.
Residual export is exact and bounded. Bounds/precision failures are explicit.
Source review of formulas is not independent numerical or native-artifact proof.

Tagged backend APIs inspected as source include
[arb conversion and outward endpoints](https://raw.githubusercontent.com/flintlib/python-flint/0.9.0/src/flint/types/arb.pyx)
and [precision/thread context](https://raw.githubusercontent.com/flintlib/python-flint/0.9.0/src/flint/flint_base/flint_context.pyx).
No native code was imported. Installed wheel identities, native notices/licenses,
actual conversion inclusion, tail error, context and platform behavior still need
executed evidence and independent review.

Authored unit probes cover hand-derived reference formulas, causal revisions,
quote-slot coverage, population breadth, signed-to-absolute supplied projection,
terminal endpoints without native import, analytical normal-symmetry interior
checks, exact IV boundaries and context restoration. They are unexecuted. The
ordinary binary64 erfc probe is complementary to the independent80/140-digit
oracle and cannot replace it.

The mandatory separate suite
`tests/qualification/test_independent_wire_fixtures.py` fails clearly if a qualified
independent fixture artifact or its separately recorded SHA256 is missing. It
requires wire-identical decimal economics/binary64 ratios, independent author and
review identities, all ten normative fixture families, full selected provenance
checks, meaningful nonzero-tail budgets and IV residual/width/root containment.
It does not fabricate expectations or silently skip absent evidence. The current
documentary oracle examples have not been instantiated as these wire artifacts;
they cannot satisfy this gate merely by renaming their metadata.

After execution admission, use separately recorded installed artifacts and source
receipts to run contracts tests, feature unit probes and the qualification suite
in fresh Python3.12 interpreters against installed wheels. Qualification variables
are `R25_INDEPENDENT_WIRE_FIXTURES` and
`R25_INDEPENDENT_WIRE_FIXTURES_SHA256`. A purported artifact's metadata alone does
not prove independent review; the coordinator must retain the real review receipt.
Both supported platforms need their own evidence. Complete direct/worker/stored
parity, artifact/licensing inventory, resource/cancellation proof and actual stored
browser demo remain release gates.
