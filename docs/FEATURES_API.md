# Calculation API and qualification checkpoint

`option-features==0.2.0a1` exposes `option_features.evaluate(snapshot, request)` and returns ordered immutable results. Nine selected matrix outputs plus five foundation pricing/Greek outputs retain their frozen units, model, causal admission, status, provenance, coverage and solver-evidence contracts. Only batch snapshots and replay of independent snapshots are admitted; no fetching, file/database access, credentials, clock reads or scheduling occurs in kernels.

## P1 parity closure (0.2.0a1)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Changed R25 results (the reason for the version bump): `liquidity.spread_bps` with a bid of 0 is now `invalid_input` / `nonpositive_bid` (was available, or `undefined` / `zero_midpoint` for 0/0), and a locked quote is `invalid_input` / `locked_market` (was available 0). Gate precedence for the spread outputs is no_quote, invalid, crossed, locked, stale. Results embed `0.2.0a1`. Nothing else in the R25 outputs changed: valid quotes, crossed, negative, one-sided and stale results, IV, quote coverage and chain activity keep their values.

Additive: outputs `liquidity.spread` and `liquidity.midpoint`; reasons `nonpositive_bid` and `locked_market`; and pure modules beside `evaluate` (no I/O, no clocks, single-threaded, exact integer and `Fraction` arithmetic, defaults reproduce the legacy behaviour):

| Module | Purpose | Legacy default |
|---|---|---|
| `option_features.quotes` | `spread_reason`, `quote_spread`, `sign_trade` (touch policy `inside_spread="unknown"`: inclusive epsilon, 3 s default quote age, `ambiguous_touch`, `inside_spread` unclassified), `sign_aggregate`, `classify_stream` (batched single pass) | `inside_spread="split"`: the shipped ask-first epsilon with midpoint split |
| `option_features.windows` | `window_premium`, `WindowIndex` (explicit `window_end_ns`, closed window), G5 `quote_count_coverage`, `QuoteUpdateIndex` | `window_end_ns=None`: window ends at the last standard print |
| `option_features.imbalance`, `spreadwin`, `quotehist` (M1 story A) | OC5 `oc5`/`oc5_many` with the additive `QuoteSize` record keyed by quote revision; OC6 `oc6`/`oc6_many`; `QuoteUpdate`, `Ticks`/`as_ticks` (prices converted once), `OCStructuralError` codes | library modules only; not on the wire; no R25 byte changes |
| `option_features.printtape`, `m2prints`, `episodes` (M2 story B) | `build_tape` (one validating pass into a columnar print tape), F1 `f1_premium_surge`/`f1_sweep`, F4 `f4_large_prints`, F17 `f17_window_premium`/`f17_many`/`f17_columns`, F7 `f7_concentration`, F18 `f18_put_share`, each with a `*_sweep`; F12 `f12_episodes`/`f12_from_tape`/`scan_episodes`; `to_wire`, `canonical_line` | library modules only; integer-only decisions, no float; the `contracts` map is trusted and adapter-validated, print data is never trusted (any object in any print field gets a code, no exception escapes); `f17_columns` and `f17_sweep_columns` are internal trusted entry points; results are the shared `flowresult.Result` (`canonical_line` has no trailing LF; `canonical_bytes` adds it), the price parser and constants are `flowgrid`'s; not on the wire; no R25, P1 or M1 byte changes |
| `option_features.shares` | `single_reference_shares` (short-dated share needs civil date and expiry, OTM share needs spot, joint measures kept, total-premium denominator, coverage), `joint_amounts` | joint measures as in the legacy joint operation |
| `option_features.chainiv` (M1 story B, not released until the M1 bump) | `IVChain(contracts, spot, rate, dividend_yield, cutoff_ns)` with `contract_iv()`, `atm_iv(expiry_days)`, `atm_iv_all()`, `iv_30d(target_days=30)`: per-contract IV with the American-style labels, chain ATM IV (nearest forward, mean of call and put), 30-day constant-maturity IV (linear in total variance, no extrapolation); batched, every contract solved at most once, certified solver unchanged | none (new) |

Validation scope of OC5/OC6 (M1 story A, PO-ruled performance trade for the owner goal): `oc5` and `oc6` default to `validate="scanned"`: the scanned portion (OC6: window, carry-in, boundary tie groups and one older update; OC5: the latest update, its tie group, one older update and later updates) is found by binary search on event time and only that portion is validated, so a call costs O(window), not O(history). Structural errors outside the scanned portion are NOT detected unless `validate="full"` is passed (whole history checked on every call) or the history went through `option_features.quotehist.validate_history` once at ingest (the documented one-time check); event order of the whole list is assumed. Documented fast path: convert prices once at ingest with `as_ticks` (`Ticks`), pass OC5 sizes as a dict rev -> `QuoteSize` (a list of `QuoteSize` is validated in full, O(rows)), validate the history once with `validate_history`. Cost statement: list-form `sizes` and `validate="full"` are O(history) (O(rows) for the list); the B2 hard limit (200 us) and the B3 hard limits (1 ms for a 50-update window, 20 ms for 5,000) hold only for dict sizes and scanned validation. Ticks ingest is the gated path; the string-price path has only about 10 percent margin on the 200 us B3 budget (measured p95 above it with older history, hard limit still met).

The design-to-repository id map, with the reason vocabulary and the match/partial/missing class of every touched row, is `docs/FLOW_NAMING_MAP.md`. The P1 modules are not operations of the frozen `variants1` wire schema. Compatibility: `docs/p1/COMPATIBILITY.json` (the 0.1.0a1 and R26 manifests stay as history). Throughput gate P1-T1 (synthetic workload, relative engineering budget): `tools/p1_throughput.py`, report in `docs/p1/P1_T1_REPORT.json`. The October 21 evidence below describes the 0.1.0a1 builds.

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

`option-features==0.2.0a1` exposes `option_features.evaluate(snapshot, request)`.
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
`option-feature-contracts==0.2.0a1` and `python-flint==0.9.0`. The module imports
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
