# M2 fixture requirements (independent Tester)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Author: Architect, 2026-10-29. Status: DRAFT, reviewed (PR 75), PO rulings applied (RULED; matrix section 8). This is the brief for the independent Tester; it fixes what must be authored, not the values. Inputs: docs/m2/M2_CAPABILITY_MATRIX.md (outputs, closed reason set, PROPOSED rulings), docs/m2/M2_GATE_BUDGETS.md (gates, workload), docs/m2/M2_IO_CONTRACT.md (input and output schema; the Tester authors inputs to it), PO release plan V3 section 4 (M2 generator row), docs/RELEASE_NOTE_TEMPLATE.md. Every ruling in the matrix (RULED interim, or PROPOSED) is encoded as the interim answer; a changed PO answer regenerates the dependent rows.

## 1. Independence and provenance
1. The Tester authors every fixture and every expected value from the design text, the matrix and the budgets, without reading any M2 implementation or the Developer tests (R26 circularity lesson).
2. Expected values come from hand derivation or from the Tester's own reference code (Python stdlib: `fractions.Fraction`, sorted lists, integer arithmetic) written from the text. The library under test is never used to derive an expectation. The library is imported only by the harness that runs it, never by a generator or by the reference code.
3. A second reviewer, independent of the author, re-derives a sample of at least 25 percent of the hand rows (and all boundary rows) without looking at the author derivations; differences must be zero or each ruled.
4. Every dataset carries a SYNTHETIC provenance tag. Generators are seeded and deterministic, write LF, take no absolute paths, and emit a manifest (seed, row counts, sha256 of every file, frozen workload facts). Committed fixtures are synthetic only.
5. Rows state the ruling they encode (matrix question number); rows for an unratified ruling carry the tag PENDING-RULING so a change finds them.

## 2. Allowed and forbidden sources
| Allowed | Forbidden |
|---|---|
| Design text (flow.md, option-contracts.md), the audit as read-only text | Any M2 module source under packages, the Developer branch, Developer tests or Developer notes |
| The M2 matrix, budgets and this document; DECISIONS.md; docs/FLOW_NAMING_MAP.md, docs/FEATURES_API.md (public ids and shapes) | Using the library under test to compute or "confirm" an expected value; importing it in a generator |
| P1 and M1 fixtures and generators under qualification/synthetic as format examples (read only) | Copying expected values from earlier fixtures unless re-derived for the M2 rule |
| tools/m1_runner CLI and docs/M1_RUNNER.md, driven as a black box | Reading runner or workload internals to decide an expectation |
| Python standard library, the Tester's own code | Any download, install, network call, vendor schema, vendor sample or recorded data; any non-synthetic input |
| gh/git for this repository only | Any wording or claim outside the label rules (docs/RELEASE_NOTE_TEMPLATE.md label rule 1 lists the forbidden terms; a docs reviewer greps as a gate) |

## 3. Generators (what must exist)
| Gen | Purpose | Must provide |
|---|---|---|
| G1 multi-session trade/premium generator | the base for every flow row | 25 sessions per underlying (20 history, 5 evaluated), 6.5 h sessions with the 60 s grid, contracts across strikes, expiries and both rights, standard and nonstandard multipliers, excluded-condition prints, ties at the same nanosecond, bursts and quiet periods, lane tag; per-contract print counts matching the budgets workload (median 20, p99 1,000) |
| G2 planted spikes | percentile and baseline cases | spike sessions and spike windows placed at known rank positions in the 20-session history (top 1, 5, 6, 50 percent, ties at the top, constant history); results derivable by hand |
| G3 median versus mean contrast | request 9 | both median_ratio and mean_ratio are asserted on every row; history sets where one outlier session moves the mean across the threshold N while the median does not, and the reverse; even count (20) so the median is the exact mean of two middle values; zero median; median equal to the value |
| G4 5-minute window cases | F1, F4, F17, F2/F10 inputs | prints exactly at T-300 s, T-300 s minus 1 ns, T, T plus 1 ns; the 60 s versus 900 s horizons; a block split into many prints that crosses the threshold only when summed; the same block split across the T-300 boundary |
| G5 volume-share cases | F18, F19 | put-only, call-only, zero volume, nonstandard-only, mixed standard and nonstandard, unknown-side prints, 20 prior put-call ratios with ties, prior sessions with zero call volume |
| G6 episode cases | F12 | grid sequences of F1 states with planted episodes, default quiet_gap 1 (rising edges): single, back-to-back separated by one quiet point (two episodes), and with the optional quiet_gap 5 (fewer than 5 quiet points: one episode; exactly 5: two); unavailable points inside and between episodes, episode open at the cutoff, episode spanning no session boundary (sessions are separate), peak ties (earliest time) |
| G7 concentration cases | F7 | shares at exactly 0.60, just below and above, strike share summed across expiries and rights, expiry share, ties at the top (lowest strike, earliest expiry), single print, zero eligible premium, nonstandard exclusion |
| G8 history-store workloads | store and gates | append of 1 to 25 sessions, retention past K, 60 series to 6,000 series, calendar gaps, an incomplete session, duplicate session, out-of-order session |
| G9 performance workloads | M2-G0 and M2-B1 to B14 | per the budgets doc section 2: size S, M, L chains, trade streams of 1e5 and 1e6, 5 x 25 sessions with all-valid-quote chain for M2-G0, manifest with frozen median and p99 facts |

## 4. Rows per family (minimum counts; every row has a stated expected status, reason, value and the ruling it encodes)
| Family | Output | Minimum rows | Must include |
|---|---|---|---|
| F1 | M2-1 | 36 | ratio exactly N, just below, above; P900 zero; calls-only and puts-only filters; overlap of 60 s inside 900 s; empty window; nonstandard and excluded-condition prints |
| F2 | M2-2 | 60 | each of F2a, F2b, F2c; upper_share boundary (exactly X percent, just either side); constant history; ties at the top; today excluded; 19, 20, 21 sessions; an incomplete session; a missing calendar session; intraday and end-of-day forms; nothing stored (insufficient_history); session_not_complete |
| F2d | M2-3 | 12 | all three available; each part unavailable in turn; reason precedence |
| F4 | M2-4 | 30 | premium exactly 100,000 (inclusive), 99,999.99, N exactly, unknown-side prints counted, nonstandard excluded and counted, empty window |
| F7 | M2-6 | 36 | G7 list, both shares, fire by strike only, by expiry only, both |
| F10 | M2-7 | 40 | median and mean contrast (G3), both ratios, ratio exactly N, zero_denominator (statistic 0), insufficient_history (including none stored), window lengths 60 to 3600 s, window not in allowed set |
| F20 | M2-8 | 30 | session_not_complete, median and mean contrast (consumer default mean), premium and contracts forms, supplied end-of-day totals labelled degraded |
| F17 | M2-5 | 30 | sum exactly 100,000, 99,999.99, block split, boundary prints, per-contract isolation (two contracts do not add), contract with no prints |
| F18 | M2-9 | 30 | G5 list, share exactly at X and Y, ratio with zero call volume, at-least and at-most rules, neither set |
| F19 | M2-10 | 30 | percentile form, ties, prior zero call volume skipped, 19 usable sessions, session_not_complete, z-score absent |
| F12 | M2-11 | 48 | G6 list, N episodes threshold, quiet_gap 1 (default) and 5 (optional) boundaries, unavailable-as-quiet, no look-ahead (appending later points never changes earlier episodes), session to date |
| Store | M2-12 | 40 | append, seal, retention ring at K and K+1, content hash stable under shuffled series arrival, view as of a session, no look-ahead, structural errors |
| Lane | Q16 | 6 | lane isolation for shares and baselines |
| Session-open window rule | Q7 | 12 | F1, F2, F10 and F12 give insufficient_window before open + W (900 s for F1), exactly at W, after; windows are not clipped; F12 in the first 900 s; history n after exclusion (grid points before open + W dropped per session; n, rank and median asserted) |
| F2d direction | Q14 | 8 | percentile = 1 - upper_share, average exact, higher = more unusual, ties, one part unavailable |
| F2c definition | Q18 | 8 | prints per minute over the window, exact Fraction, window lengths 60 to 3600 s |
| Half-day sessions | Q1, Q3 | 10 | shorter grids, history mixing full and half days, counts use actual length, calendar supplies the length |
| Delayed-feed tag | M2-1 | 8 | F1, F12, intraday F2 and intraday F10 give invalid_input delayed_feed_tag; end-of-day forms computed and labelled delayed |
| Structural | all | 24 | one row per invalid_input code in matrix section 4 |
Total at least 558 hand-derivable rows including the convention rows of section 10 (538 = 498 before the AMB rulings plus 38 AMB rows plus 2 structural rows, section 9) (452 in the first fourteen lines of the table plus 46 in the five lines added after review: 12 + 8 + 8 + 10 + 8); the reviewer recomputes the sum. Differential: at least 20,000 randomized cases each for percentile rank (upper_share and rank_le), median baseline ratio and episode detection, expected values from the Tester reference; zero differences allowed. Row counts are minimums; the final counts are pinned in the manifest and recomputed by the reviewer (HANDOFF gotcha: pinned counts learned from a first run are never trusted).

## 5. Closed reason set coverage
Each of insufficient_history, insufficient_window, session_not_complete, zero_denominator has at least 3 rows in every family where the matrix lists it, and at least one row proves it never appears where the matrix does not list it. Gate order (invalid_input, insufficient_history, session_not_complete, insufficient_window, zero_denominator) has at least 8 rows where two conditions hold at once. A reason outside the closed set in any result is a failure. The harness asserts reason and status, never only the value.

## 6. Mutation requirements
The Tester authors a mutation list and runs it (the Developer does not sign off its own proof). Each mutant must be caught by at least one row; a mutant that does not trip proves nothing, so for each mutant the Tester confirms the mutated field is one the harness reads. Minimum 30 mutants, at least these:
1. Windows: open at start; open at end; window 900 s used for the 60 s side; ratio inverted (P900 over P60); look-ahead past T.
2. Statistic: mean output wired to the median name (or the reverse); mean instead of median; lower middle instead of exact mean of the two middle values; zero statistic treated as available; today included in the history.
3. Rank: strict greater instead of at-or-above; rank_le used for upper_share; ties counted as below; 19 sessions accepted; an incomplete session counted; a missing calendar session substituted; z-score instead of percentile.
4. F4 and F17: exclusive threshold; side-known prints only; nonstandard counted; tumbling aligned buckets; per-name instead of per-contract sum.
5. F7: strike share not summed across expiries; wrong tie rule; denominator excludes nonstandard instead of eligible total.
6. F18 and F19: share and ratio swapped; unknown-side prints dropped; prior zero-call sessions counted.
7. F12: quiet_gap off by one (default 1 and optional 5); unavailable counted as not quiet; episodes merged across sessions; peak tie takes the latest.
8. Store: retention K+1; sort not applied at seal; append order dependent; hash includes arrival order.
9. Infrastructure: cache key missing one parameter; cache hit across underlyings or lanes; batched path drops the last series or reorders; worker count or completion order in a result; float used for a ratio.
Mutants in groups 8 and 9 are also run through the performance, parallelism and cache rows (section 7), which must fail on them.

## 7. Performance, parallelism, cache and memory fixtures
Authored by the Tester from M2_GATE_BUDGETS.md, in the PERF_ACCEPTANCE structure (workload generator, manifest, rows file, runner contract). Budgets are printed verbatim beside measurements.
| Group | Rows (minimum) | Requirement |
|---|---|---|
| Workloads | one per gate M2-G0, M2-B1 to M2-B18 | generated at run time from the seeded generators; only samples and manifests (seed, sizes, frozen facts, sha256 of the samples) are committed; sizes S, M, L; 1e5 and 1e6 prints; frozen median and p99 facts rechecked within +/- 10 percent before each run |
| D determinism | 10 | identical per-cutoff and whole-run hashes at 1, 2, 4, N workers x 3 repeats, batch sizes 1, 7, 64, all, shuffled cutoff, underlying, contract and series order; identical store content hash; history appended in canonical order only |
| E batched versus single | 10 | exact equality for every M2 output, status and reason (no tolerance); equality with the Tester reference; the shared pass (M2-B10) equals the separate passes |
| C cache | 12 | cold equals warm; each input field and parameter changes the key (window, threshold, N, X, K, multiplier, right, strike, expiry, session, lane, history content, calendar); no hit across underlyings, sessions or lanes; a new sealed session invalidates exactly its series; bounded size, eviction does not change bytes |
| R memory | 8 | peak RSS per process and aggregate per budgets; leak slope <= 1 MB per repeat; last-10 mean within 5 percent of first-10; store bytes within 30 percent of the formula; retention bounded at K |
| S scaling | 3 | >= 2.0x at 4 workers on the 5-underlying compute phase; >= 1.8x at 4 workers on the trade-stream gates; N/A reported under 4 physical cores |
| K runner | 6 | kill, missing and duplicate unit, interpreter mismatch and no partial output with M2 outputs in the unit; outputs of a previous run removed; only own process ids are ever terminated |
| G0 first task gate | 1 plus protocol | full-output B6 as one measurement, 1 worker and N workers, at least 30 repeats, machine frozen, compute-only gated and with-synthesis printed, per the budgets doc section 3 |
Timers: monotonic ns around the call only; serialization measured separately; percentile by nearest rank; machine record frozen before the first run and printed (CPU, cores, RAM, OS build, Python build, power plan, idle load).
Verdict rules: any D, E, C or determinism failure is a correctness failure and blocks acceptance regardless of speed; a Hard breach blocks; a Budget miss with Hard met needs a PO ruling recorded before release; a miss is reported, never edited.

## 8. Deliverables and acceptance
- Location qualification/synthetic/m2/ (generators, fixtures, manifest with sha256, rows files, reference code, mutation list and results); PERF files under qualification/synthetic/perf style names for M2.
- Independent reviewer (not author, not Developer): re-derivation per section 1, closed-set and count recomputation, forbidden-term grep, LF and ASCII check, no absolute paths, SYNTHETIC tag in every dataset.
- The PO accepts the fixture set before M2 code starts (M1 pattern: fixtures accepted as authored, not yet run against any implementation; the Developer's first runs must fail on an empty implementation).
- Every report header carries the label sentence verbatim; every performance number carries "synthetic workload, relative engineering budget"; Linux, if run, is "Linux run as process check, not claimed".
- Open items the Tester must record, not decide: any ambiguity found in the matrix goes to the PO as a numbered question; the row stays PENDING-RULING.

## 9. PO-M2-AMB rows (interim pending design ratification where the design is silent)
At least 2 rows per ruling AMB-1 to AMB-19 of the matrix section 10 (at least 38 rows plus 2 structural rows, added to the total of section 4: at least 498 + 38 + 2 = 538). Required content: AMB-1 each of the four default-versus-other availability combinations for F10 and F20; AMB-2 a print with and without the 8th element (results equal); AMB-3 threshold_ticks and tick values; AMB-4 and AMB-8 grid index, dropped W/60 points, window dimension mismatch; AMB-5 onsets, peak ties, unavailable_points; AMB-6 threshold_required; AMB-7 F12 at 899 s, 900 s; AMB-9 each label; AMB-10 F2c end-of-day; AMB-11 F2d fired null; AMB-12 F19 boundary and n; AMB-13 out_of_order_append, content hash of the line without its own field, ring counting incomplete sessions; AMB-14 coverage keys: a print both nonstandard and excluded counts only in excluded_condition_count; nonstandard_count holds non-excluded nonstandard prints; AMB-15 pairs of simultaneous structural errors in list order; AMB-16 multiplier 0 and negative, duplicates and non-monotone grid within a series set; AMB-17 missing, incomplete and absent sessions; AMB-18 window_not_allowed per output, F17 fixed, F1 and F12 no window; AMB-19 each default. The structural family of section 4 gains one row each for threshold_required and out_of_order_append. Mutants: add one per AMB-1, AMB-6, AMB-13 and AMB-15 behaviour.

## 10. Rows for the PR 76 review rulings
At least 2 rows each: F12 unavailable_points including the first 15 (before 900 s); F2c end-of-day divides by session minutes and is windowless (window_not_allowed not raised); coverage counters (a print both nonstandard and excluded-condition counts only under excluded_condition_count); duplicate_session versus out_of_order_append at the store; unavailable results carrying coverage and label only for zero_denominator; F10 and F20 unavailable per_statistic and label; a history lane mismatch; session_not_in_calendar on the current session only; F12 peak with zero episodes (ties earliest); F2d fired null with parts shown. RULED: the total is at least 558 hand-derivable rows including these convention rows (538 plus about 20 rows from this section); the reviewer recomputes the sum.

## 11. Fixture additions (ratified interim, pending design ratification where the design is silent)
The Tester additions (at least 121 rows in total after the fixture author regeneration; first draft 83 rows: 40 structural, 25 data, 18 grid) encode M2_IO_CONTRACT.md section 9 (the only place the rulings are stated). The fixture author adds rows for lane_mismatch, record_length_mismatch (dense longer, sparse index outside range), a zero-padded short dense grid, snapshot and dump trailer verification, ratio_reason omission and the version string. The closing-print rows are RULED (section 9 item 2 ratifies them). Required: at least 2 rows for each of the six snapshot and trailer codes (snapshot_bad_magic, snapshot_length_mismatch, snapshot_hash_mismatch, trailer_missing, trailer_count_mismatch, trailer_hash_mismatch), added by the fixture author.

Update (RULED, pending design ratification where the design is silent): the additions now total 185 rows (add_cutoff, 18 rows, covers the empty window before open of M2_IO_CONTRACT.md section 9 item 11: zero counts and premiums, zero coverage, available status, zero_denominator for F7 and F18 shares, open_ns absent gives malformed_type). The "at least 121 rows" figure above is superseded by 185.
