# M3a fixture requirements (independent Tester)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Author: Architect, 2026-10-30. Status: DRAFT; starts only AFTER the PO has ruled M3A_RULING_LIST.md (one pass). This is the brief for the independent Tester; it fixes what must be authored, not the values. Inputs: M3A_CAPABILITY_MATRIX.md (outputs, closed reason set), M3A_GATE_BUDGETS.md (gates, workload), M3A_IO_CONTRACT.md (schema, structural codes, the single precedence list), M3A_RULING_LIST.md (the ruled answers; rows state the R-number they encode), PO release plan V3 section 4 (M3 generator row), docs/RELEASE_NOTE_TEMPLATE.md. Rows for an unratified design-silent ruling carry the tag PENDING-RULING.

## 1. Independence and provenance
1. The Tester authors every fixture and expected value from the design text, the matrix, the contract and the ruled list, without reading any M3a module or the Developer tests (R26 circularity lesson).
2. Expected values come from hand derivation or from the Tester own reference code (Python stdlib: `fractions.Fraction`, `decimal` with at least 50 digits, integer arithmetic) written from the text. The library under test is never used to derive an expectation and is never imported by a generator or by the reference code; only the harness that runs it imports it. A BSM price, delta and implied vol oracle is authored by the Tester (Decimal series or bisection at 50 digits), independent of the M1 solver and of python-flint.
3. A second reviewer, independent of the author, re-derives at least 25 percent of the hand rows and all boundary rows without seeing the author derivations; differences must be zero or each ruled. Counts are recomputed by the reviewer from the tables, never trusted from a first run.
4. Every dataset carries `"provenance": "SYNTHETIC"`. Generators are seeded, deterministic, LF, no absolute paths, with a manifest (seed, row counts, sha256 of every file, frozen workload facts). Performance workloads are generated at run time; only samples and manifests are committed.
5. Fixtures use the M2 compact row format and tagged encodings for non-JSON types; the harness decodes them.

## 2. Allowed and forbidden sources
| Allowed | Forbidden |
|---|---|
| Design text (volatility-radar.md, option-contracts.md), the audit as read-only text | Any M3a module source under packages, the Developer branch, tests or notes |
| The M3a matrix, budgets, contract, ruling list and this document; DECISIONS.md; docs/FLOW_NAMING_MAP.md, docs/FEATURES_API.md, docs/m2 (public ids and shapes) | Using the library under test (or the M1 solver) to compute or confirm an expectation |
| M1 and M2 fixtures and generators under qualification/synthetic as format examples (read only) | Copying expected values from earlier fixtures unless re-derived for the M3a rule |
| tools/m1_runner CLI and docs/M1_RUNNER.md, driven as a black box | Reading runner or solver internals to decide an expectation |
| Python standard library, the Tester own code | Any download, install, network call, vendor schema or sample, recorded data, or any non-synthetic input |
| gh/git for this repository only | Wording or claims outside the label rules (docs/RELEASE_NOTE_TEMPLATE.md label rule 1; a docs reviewer greps as a gate) |

## 3. Generators (what must exist)
| Gen | Purpose | Must provide |
|---|---|---|
| G1 smile and term surface generator | the base for every row | parameterized true volatility sigma(k, T) = a(T) + b(T) k + c(T) k^2 (a smile with known ATM level, skew slope b and curvature c, a term structure in a(T)), listed strike grids around the forward, 8 expiries bracketing 9, 30 and 91 days (and variants without a bracket), both rights, quotes priced by BSM at the true sigma (midpoint, tight spread) so the IV at every listed strike is known; American and European style flags; tie strikes (forward exactly between two strikes); deep wings; missing and one-sided quotes; locked, crossed and stale quotes; nonstandard multiplier and excluded-condition contracts |
| G2 25-delta oracle | expected 25-delta points | exact delta of each listed strike at its true sigma (50-digit), the bracketing pair, the delta-linear interpolated IV as an exact rational, the non-monotone-delta case (steep skew), targets exactly on a listed strike, no-bracket cases (target outside the listed deltas) |
| G3 tenor oracle | expected 9, 30, 91 day IV | linear total variance between bracketing expiries as exact rationals; exact-expiry cases; one bracketing expiry lacking an ATM strike; no-bracket cases |
| G4 history generators | V1, V3, V9 | 20, 21, 252 sessions of session-close values and minute grids with planted rank positions (top 1, 5, 6, 50 percent; ties at the top; constant history; zero range); missing minutes in prior sessions; half-day sessions; incomplete sessions; calendar gaps; a missing CM value on some days; lane mismatch |
| G5 prior-reading generator | V4, V6, V7, V10 | prior frame and prior session readings, sign changes through zero, zero prior, thresholds exactly at X, unavailable prior |
| G6 structural generator | contract section 4 | one row per code, and for every adjacent pair of positions of the single precedence list one row with both errors present (the first listed code must be reported), type-first per field cases (float, Decimal, Fraction, bool, None, bytes in each typed field) with tagged encodings |
| G7 history-store workloads | store reuse | append and read of 252 sessions for 103 names x 4 series, retention at 252, persistence round trip, mmap snapshot attach, content hash stability under shuffled arrival |
| G8 performance workloads | M3A-G0 and M3A-B1 to B14 | size S, M, L smile chains, the all-valid-quote chain for M3A-G0, 103-name series batches, 5 x 5 x 78 unit grid, manifest with frozen facts (quote counts, expiry counts, strikes per expiry) |

## 4. Rows per family (minimum counts; every row states status, reason, value and the R-number it encodes)
| Family | Output | Minimum rows | Must include |
|---|---|---|---|
| Surface frame | M3A-0 | 80 | forward, T, ATM IV per expiry, coverage counts, labels, delayed tag, all-excluded chain, one expiry per coverage gate, American-style labels |
| 25-delta bracket | M3A-0 | 60 | G2 list, put and call sides, target on a strike, steep skew non-monotone case, no_delta_bracket both sides, minimum strikes |
| Tenors | M3A-0 | 40 | G3 list, exact 30-day expiry, 9 and 91 day brackets, no extrapolation |
| Coverage gates | M3A-0 | 24 | strikes eligible exactly at 3/5, just below, min_strikes, low_surface_coverage, expiry_min_days boundary (R-13) |
| American labels | M3A-0 | 20 | exact-model, approximate, american_itm excluded, style_unknown excluded, label text |
| V1 | M3A-1 | 40 | top and bottom X, upper_share and lower_share boundaries, 19, 20, 252 sessions, zero range, session_not_complete, delayed end-of-day form |
| V3 | M3A-2 | 40 | same-minute alignment, missing minutes skipped, half-day sessions, insufficient_window, delayed_feed_tag, 252 look-back |
| V4 | M3A-3 | 40 | ATM and 30d basis, frame and session prior, relative and absolute outputs, zero prior, no_prior_reading, threshold exactly 10 percent |
| V5 | M3A-4 | 36 | both pairs, longer minus shorter sign, missing tenor, threshold boundary |
| V6 | M3A-5 | 30 | nearest and second eligible, only one expiry, coverage-excluded nearest |
| V7 | M3A-6 | 36 | gap change and slope change, prior session from the store, threshold boundary |
| V8 | M3A-7 | 48 | skew sign and size, 30-day tenor from per-side CM, threshold exactly 5 points, each side missing |
| V9 | M3A-8 | 40 | as V1 for skew |
| V10 | M3A-9 | 48 | change in points, sign change through 0, 0 never a flip, prior frame versus prior session |
| V11 | M3A-10 | 24 | (if R-01 accepted) both signs, boundary |
| V21 | M3A-11 | 24 | (if R-01 accepted) negative distances, zero call distance |
| Units and rounding | all | 20 | micro-vol rounding half to even at the storage boundary, points keys, rational output form |
| History reuse | M3A-12 | 24 | retention at 252, series cap, content hash, lane mismatch, store codes inherited |
| Structural | all | 60 | 40 codes and type cases plus 20 precedence pair rows (section 3 G6) |
| Lane | all | 6 | lane isolation |
Total at least 692 hand-derivable rows without V11 and V21 (740 with), recomputed by the reviewer. Differential: at least 20,000 randomized cases each for the 25-delta interpolation, the tenor interpolation, the rank forms and the sign-change rule, expected values from the Tester reference; zero differences allowed. Rows within the solver tolerance (1e-4) of a threshold are not asserted; near-threshold attack rows state the ruling that decides them (R-62).

## 5. Closed reason set coverage
Each reason of the matrix section 5 has at least 3 rows in every family where the matrix lists it and at least one row proves it never appears elsewhere. The closed set: no_atm_strike, no_bracketing_expiry, insufficient_history, insufficient_window, session_not_complete, zero_denominator, no_delta_bracket, low_surface_coverage, no_prior_reading, zero_range_history. A reason outside the set in any result is a failure. Rows with two simultaneous conditions (at least 10) fix the gate order. The harness asserts reason and status, never only the value.

## 6. Mutation requirements
The Tester authors a mutation list and runs it (the Developer does not sign off its own proof). Each mutant must be caught by at least one row, and the Tester confirms the mutated field is one the harness reads. At least 40 mutants, at least these:
1. Surface: wrong forward (no carry), K/S instead of K/F, delta of the ATM IV instead of the contract IV, forward delta, strike order reversed, tie to the higher strike, first crossing replaced by the last, extrapolation allowed, american_itm included, nonstandard counted.
2. Interpolation: IV linear in k, total variance used for the 25-delta step, rounding before interpolation, tenor interpolation linear in IV.
3. Coverage: 3/5 replaced by 1/2, inclusive/exclusive swapped at the boundary, expiry_min_days off by one.
4. Derived: skew sign swapped, term sign swapped (shorter minus longer), V6 uses nearest listed instead of eligible, curvature without the half, V21 inverted, zero call distance treated as available.
5. History: mean-style rank, strict greater instead of at-or-above, ties split, 19 sessions accepted, incomplete session counted, minute alignment off by one, missing minute substituted, today included, zero range computed, retention 60.
6. Prior reading: hidden in-memory state used, prior session replaced by prior frame, zero prior divided, sign change through 0 counted.
7. Structural: precedence pair swapped, type check after value check, scanned validation skips a full-only code, a code outside the closed set.
8. Infrastructure: cache key missing a field, hit across cutoffs, batched path drops a name, worker count or completion order in a result, float used in an output.
Mutants of groups 7 and 8 also run through the performance, parallelism and cache rows, which must fail on them.

## 7. Performance, parallelism, cache and memory fixtures
Authored from M3A_GATE_BUDGETS.md in the PERF_ACCEPTANCE structure (workload generator, manifest, rows file, runner contract). Budgets print verbatim beside measurements.
| Group | Rows (minimum) | Requirement |
|---|---|---|
| Workloads | one per gate M3A-G0 and M3A-B1 to B14 | sizes S, M, L; 103-name batches; frozen facts rechecked within +/- 10 percent before each run |
| D determinism | 12 | identical hashes at 1, 2, 4, N workers x 3 repeats, batch sizes 1, 7, 64, all, shuffled unit, name, expiry and contract order, identical store content hash |
| E batched versus single | 12 | exact equality for every output, status and reason, no tolerance; equality with the Tester reference |
| C cache | 14 | cold equals warm; each input field and parameter changes the key; no hit across chains, cutoffs, underlyings or lanes; bounded size; eviction does not change bytes |
| R memory | 8 | peak RSS per process and aggregate; leak slope <= 1 MB per repeat; last-10 mean within 5 percent of first-10; store bytes at retention 252 against the budgets doc formula |
| S scaling | 3 | >= 2.0x at 4 workers on the 5-underlying compute phase; N/A reported under 4 physical cores |
| K runner | 6 | kill, missing and duplicate unit, interpreter mismatch, no partial output with M3a outputs in the unit; only own process ids terminated |
| G0 first task gate | 1 plus protocol | per the budgets doc section 4: one worker, at least 30 repeats, machine frozen, compute-only gated, with-synthesis printed |
Verdict rules: any D, E, C or determinism failure blocks acceptance regardless of speed; a Hard breach blocks; a Budget miss with Hard met needs a PO ruling; a miss is reported, never edited.

## 8. Deliverables and acceptance
- Location qualification/synthetic/m3a/ (generators, fixtures, manifest with sha256, rows files, reference code, mutation list and results).
- Independent reviewer (not author, not Developer): re-derivation per section 1, closed-set and count recomputation, forbidden-term grep, LF and ASCII check, no absolute paths, SYNTHETIC tag everywhere.
- The PO accepts the fixture set before M3a code starts; the Developer first runs must fail on an empty implementation.
- Every report header carries the label sentence verbatim; every performance number carries "synthetic workload, relative engineering budget"; Linux, if run, is "Linux run as process check, not claimed".
- The Tester records any ambiguity found as a numbered question to the PO; the row stays PENDING-RULING.
