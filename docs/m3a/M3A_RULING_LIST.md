# M3a ruling list (one batch for the PO, revision 2)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Status: RULED 2026-10-30 (PO), interim pending design ratification where the design is silent, EXCEPT the items marked "owner-decided (final)" (R-01 V21, R-46, R-51, R-151 to R-161; FINAL OWNER DECISIONS 1 to 5 in docs/decisions/2026-10-30-m3a-ruling-batch-2.md; a design-session ratification may still amend them later); R-58 stays PO interim. All 102 recommended rulings (R-01 to R-102) are accepted as written by the PO pass of 2026-10-30; SETTLED rows are unchanged; the explicit decisions and the exceptions list are in docs/decisions/2026-10-30-m3a-ruling-pass.md. The text below keeps the original wording; "RECOMMENDED" now reads as RULED.

Author: Architect, 2026-10-30. Prepared for ONE PO pass BEFORE any fixture author starts (the pass is done, see the status line above). 161 ambiguities and design-silent edge cases (R-01 to R-161; R-103 to R-161 are the second batch found by the four fixture authors, RULED 2026-10-30 (PO second batch), interim pending design ratification where the design is silent), each with options and the Architect RECOMMENDED ruling. Rows marked SETTLED were ruled by the independent review of PR 101 (PO rulings) or follow directly from the M1 input record; they stay in the list so the ids are stable. Everything else is a proposal. Lesson of M2 applied: the precedence lists, type-first per field, trusted versus untrusted inputs and the canonical forms are decided here, once (R-66 to R-71). Where the design is silent an accepted ruling is interim pending design ratification. Companions: M3A_CAPABILITY_MATRIX.md, M3A_GATE_BUDGETS.md, M3A_FIXTURE_REQUIREMENTS.md, M3A_IO_CONTRACT.md. Sources: volatility-radar.md (VR), option-contracts.md (OC), workers audit (AUD), M1 code and M2 rulings.

## A. Scope
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-01 | M3a row list [owner-decided (final)] | V1, V3-V10 only; add V11; add V21 | SETTLED: V11 is a design row and JOINS M3a (same two 25-delta points; tracker moved by the Auditor); RULED 2026-10-30: V21 is INCLUDED (M3A-11) |
| R-02 | V2 (ATM IV, M1) points unit and threshold form | leave M1 annual decimal; add points and threshold output | add the points form and threshold rule as a thin wrapper in M3a; M1 bytes unchanged |
| R-03 | Rows left for later | V12-V15, V22 (M3b), V16-V19, V20, frame builder, presets | defer all; named as not built in the release note (history reuse is NOT deferred, see R-89) |
| R-04 | Delta definition used to place 25 delta | spot delta N(d1)e^{-qT}; forward delta; delta with ATM IV | (amended by R-155 to R-157: spot is the default of two conventions) spot delta of the BSM model at the contract OWN IV with e^{-qT}, absolute value for puts (R25 Greeks convention); target 0.25 inclusive |
| R-05 | Delta source and decision rule near the target | R25 certified delta; float delta with certified fallback | the existing certified delta; a float filter with a certified fallback only with identical bytes (Developer choice, gate unchanged) |
| R-06 | Which right defines each side | each right for its own side; OTM-only; mean of both | each side from its own right (V8 reads put side against call side); both rights must be eligible |

## B. Surface construction
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-07 | Moneyness definition (labels, wings) | K/S; K/F; ln(K/F); delta | k = ln(K/F), F = S exp((r-q)T) per expiry (as M1 ATM); delta for the 25-delta points |
| R-08 | Strike grid | listed strikes only; fixed grids | listed strikes only; no synthetic grid in M3a |
| R-09 | Interpolation across strikes | linear IV in delta; linear IV in k; linear total variance in k; cubic; SVI | linear IV in delta between the two bracketing eligible strikes of the right (SVI skipped by the design) |
| R-10 | Bracket when delta is not monotone in strike | first crossing from ATM outward; any; lowest strike | first crossing scanning outward from the ATM strike; ties to the lower strike |
| R-11 | American-style labels | exact-model only; also approximate; also american_itm | exact-model and approximate (M1); american_itm and style_unknown excluded; labels are the M1 strings verbatim ("exact-model", "approximate: European model on an American-style contract") |
| R-12 | Contracts excluded | M1 gates only; more | M1 gates only (condition other than "regular" is excluded_condition, quote gates, stale); counted in coverage; the chain record has no multiplier |
| R-13 | Expiry set: minimum days | all; days >= 1; days >= 2 | SETTLED by the M1 input: `expiry_days` is an integer >= 1, otherwise structural `bad_expiry` (as M1 raises); no civil-date conversion in M3a (adapter duty, RQ item) |
| R-14 | Tenors | 9, 30, 91 (catalogue); 8 tenors 10d to 360d; expiry-based only | 9, 30, 91 days only; closed set, `tenor_not_allowed` otherwise; method `iv_30d(target_days)` of M1 |
| R-15 | Constant-maturity method for 9d and 91d | linear total variance; flat forward variance; interpolate IV | linear in total variance between bracketing expiries, as M1 |
| R-16 | Extrapolation | none; flat beyond the last expiry or strike | none anywhere; `no_bracketing_expiry`, `no_delta_bracket` |
| R-17 | Days-to-expiry counting | civil; M1 convention | SETTLED: the M1 convention (T = expiry_days/365, ACT/365) |
| R-18 | Expiry on the cutoff day or after expiry time | include with T = 0; exclude | SETTLED: `expiry_days` <= 0 is structural `bad_expiry` (as M1); the civil-day exclusion is dropped |
| R-19 | Longest expiry cap | none; cap | none; tenors above the longest expiry are unavailable |
| R-20 | Minimum coverage per expiry | 3/5 of listed strikes (worker 60 percent); fixed count; none | 3/5 of listed strikes and at least `min_strikes` 4; below: expiry unavailable, `low_surface_coverage`; parameters echoed; terms defined in R-83 |
| R-21 | Minimum strikes to interpolate | 2; 3; 4 | 2 bracketing eligible strikes of the right, else `no_delta_bracket` |
| R-22 | Deep wings | exclude beyond a bound; keep | keep; eligibility by M1 gates only |
| R-23 | Duplicate contracts | structural; keep one | SETTLED: same expiry, strike and right twice is structural `duplicate_contract` (as M1 raises) |
| R-24 | Rate and yield | one constant per chain (M1); term curve | one rate and one yield per chain (M1); a curve is a later ruling |
| R-25 | Spot | supplied; last trade | supplied spot as M1; spot staleness is the caller duty; `stale_limit_ns` (default 10 s, M1 Q4) applies to quotes |
| R-26 | Quote price | midpoint (M1); microprice | midpoint (M1 ruling retained) |

## C. Skew, term, derived outputs
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-27 | Which expiry carries the skew | each listed expiry; nearest; 30-day tenor | the 30-day constant-maturity tenor for V8 to V10 and V11; per-expiry points also in the surface frame |
| R-28 | Skew at a tenor | skew of the nearest expiry; 25d IVs per expiry then CM per side; CM of skew values | per-expiry 25d put and call IVs, then CM by linear total variance PER SIDE, then skew = put minus call |
| R-29 | V8 definition against the worker band | 25-delta risk reversal (design); pooled band 0.15 to 0.35 (AUD) | 25-delta (design contract); the worker band recorded as a known difference |
| R-30 | Term slope (V7) | 30d-91d gap; near-to-next slope; slope per year | SETTLED: the 30d-91d gap in points (longer minus shorter); slope is NOT offered; no `slope_change_points` |
| R-31 | V5 sign and pairs | shorter minus longer (worker); longer minus shorter | longer minus shorter, pairs 9-30 and 30-91; sign stated in the label |
| R-32 | V6 nearest and second expiry | nearest listed; nearest eligible; second = next eligible | nearest and second ELIGIBLE expiries after R-20; spread = second minus nearest; fewer than two gives `fewer_than_two_expiries` (R-91) |
| R-33 | V7 form | gap change; slope change; both | gap change only (R-30), against the n-th prior session close (R-82) |
| R-34 | V10 sign change | strict flip; zero as a side; dead band | sign in {-1, 0, +1} of the rounded-once difference (R-95); changed when the signs differ and neither is 0; 0 never counts as a flip |
| R-35 | Threshold inclusivity | at least X inclusive; strict | inclusive ("at least X", "at most X"), as M2 |
| R-36 | Defaults and units | worker placeholders in decimals; points | points: skew 5, skew change 2, term 3, term change 2, curvature 3, IV change 10 percent; all echoed; X default 5 |
| R-37 | V11 definition | (put25 + call25)/2 - ATM; sum minus 2 ATM; butterfly | (put25 + call25)/2 minus ATM in points; fires per `direction` (default up) by at least X |
| R-38 | V21 definition and zero denominator | (put25 - ATM)/(call25 - ATM); inverse; absolute | (put25 - ATM)/(call25 - ATM); call distance 0 gives `zero_denominator`; negative distances allowed and shown |
| R-39 | Wording of sides | direction words; neutral | "put-side" and "call-side" only; blocked words never appear in labels (design WL78, WL91) |

## D. History and percentiles
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-40 | Clock of "prior reading" | previous frame (memory); stored frame; prior session close | `prior` is an INPUT (kind frame or session, with its time); caller or store supplies it; no hidden state; the reading time must be before the cutoff (R-92) |
| R-41 | V4 form | relative percent; absolute points; ATM or 30d; zero prior | the ATM form or the 30-day form per `iv_form` (R-151, R-152); change_points and change_ratio both output; fires on relative percent (10 default) per `direction`; prior 0 gives `zero_denominator` |
| R-42 | V1 history cadence | session-close value; same minute; all frames | session-close scalar of each prior session, in both modes |
| R-43 | V3 minute alignment | same minute index; nearest frame within a tolerance | the same grid minute index; a prior session without that minute is skipped (not substituted) |
| R-44 | Look-back and minimum | 252 and 20 (worker); 20 only | design-silent beyond "at least 20 prior sessions": `min_sessions` 20, `max_sessions` 252 (the worker V3 figure; extended to V1 and V9 as an interim ruling) |
| R-45 | Percentile form and bottom X | M2 upper_share; add lower_share | M2 forms: top X percent fires when upper_share <= X/100; bottom X percent when lower_share = count(history <= x)/n <= X/100; both always returned |
| R-46 | Zero-range history [owner-decided (final)] | percentile of a constant history; unavailable | unavailable `zero_range_history` (design VR P3); DELIBERATE exception to M2 Q2 (there a constant history is available and cannot fire) |
| R-47 | Completeness and "new" | partial sessions counted; only complete | only sealed complete sessions; below `min_sessions`: `insufficient_history` ("new") |
| R-48 | Stored value representation | float; rational; integer | integers in 10^-8 units (the rounded-once 8-decimal value); ranks on integers |
| R-49 | Rounding | at storage; at output; both | round once, half to even, from the binary64 value to 8 decimals; that decimal is the reported value, the stored integer and the basis of every comparison |
| R-50 | Ties at the percentile | at-or-above; split | M2 rule (ties count in upper_share and in rank_le) |
| R-51 | Days whose value is absent in history [owner-decided (final)] | skip; fail | `scalar_baseline` skips missing and incomplete days; n counts available sessions; below min_sessions: insufficient_history; DELIBERATE exception to M2 Q3 and AMB-17 (design: "at least 20 prior sessions") |
| R-52 | Retention and memory | raise the cap for all; per-series k | per-series `k` = 252 for the M3a series; the M2 store has k default 20 and a hard cap of 60 (k in 1 to 60), so 252 EXCEEDS it: M3a raises the hard cap for scalar series (per-series k up to 252) as a deliberate additive M2 store change, M2 series keep k <= 60; minute grid only for iv30 (R-81); scalar series elsewhere; budget 81 MB raw, 243 MB with the M2 layout |
| R-53 | Which series stores skew | 30d tenor skew; nearest; every expiry | 30d tenor skew (R-27, R-28) as `skew25` |
| R-54 | Minute index range for V3 | all 390; skip edges | any grid minute 0 to minutes-1; outside is structural `minute_out_of_range` |
| R-55 | Half-day sessions for V3 | by minute index; by fraction | by minute index from open; a half-day has fewer minutes and is skipped for later minutes |

## E. Frames, modes, feed
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-56 | Mode | flag; two functions | `mode` in {intraday, close}; close reads the close-chain frame and needs a sealed session (`session_not_complete`); invalid mode is `invalid_mode` |
| R-57 | Exact frame (VR3) | nearest; exact only | the library takes one chain at one cutoff: exact by construction; "no exact frame" is an engine reason |
| R-58 | Delayed feed | compute and label; unavailable | V3 and intraday V1, V4: invalid_input `delayed_feed_tag` (as F1 in M2); DELIBERATE exception to the design word "unavailable" (same interim choice as M2); close forms computed and labelled delayed |
| R-59 | Prior session and holidays | previous calendar day; calendar | previous session in the supplied calendar |

## F. Units, rounding, representation
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-60 | IV unit | annual decimal; points | annual decimal in `iv` keys; `_points` keys are x100 differences; thresholds in points |
| R-61 | Output number type | float; rational; decimal | quote-derived exact values: ints or "n/d"; solver-derived values (IV, forward, derived series): binary64 reported as decimal strings rounded half-even to 8 decimals |
| R-62 | Tolerances | exact; 1e-4 | solver tolerances are 1e-10 (`DEFAULT_SOLVER`); 1e-4 is the M1 FIXTURE comparison tolerance (4-decimal quote quantisation, vega >= 4); forward 1e-6; rows within a tolerance interval of a threshold are not asserted; canonical hashes of solver-derived values are Windows-only |
| R-63 | Labels | free text; closed | SETTLED: the M1 vocabulary verbatim; a `labels` list (model label, plus "delayed" when applicable); the three-label scheme is dropped |
| R-64 | Version and envelope | new; M2 Result | the M2 Result envelope and the library version string (no bump); unavailable carries value and fired null |
| R-65 | Tagged encodings of non-JSON types | none; M2 tagged objects | the M2 tagged objects (Decimal, Fraction, bytes); harnesses decode before calling |

## G. Malformed inputs and precedence (decided once)
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-66 | Precedence lists | one list; per entry point | one list PER ENTRY POINT as M2: request (18 positions), history append and load (6, M2 order), snapshot (3), text load (3), view read (4); the first failing code is reported (IO contract section 4) |
| R-67 | Type-first | value codes first; global; per field | per field at the position of that field value check (M2 ruling) |
| R-68 | Trusted versus untrusted inputs | validate always; scanned for trusted | untrusted validated in full; verified-store views and validated chains scanned on hot paths; `validate="full"` always available, same codes |
| R-69 | Chain structural codes | reuse M1 reasons; new | bad_cutoff, bad_spot (value code only: spot not finite or not > 0; a spot, strike or quote not representable in 8 decimals is malformed_type), bad_rate, bad_expiry, unknown_right, duplicate_contract, bad_strike, malformed_type (M1 raises ValueError for these; M3a maps them to codes); no multiplier, civil-date or ordering codes |
| R-70 | History input validation | reuse; new | reuse the M2 store codes and order unchanged |
| R-71 | Empty chain or all excluded (modified by R-106) | structural; unavailable | unavailable with the M1 reasons counted in coverage; never structural |
| R-72 | Parameter validation | clamp; reject | reject: tenor_not_allowed, delta_not_allowed; X outside 0 to 100 is the value code `threshold_out_of_range` (not malformed_type); min_sessions and max_sessions wrong type or below 1 is malformed_type |
| R-73 | Lane handling | one lane; mix | one lane per call; lane in {stock, etf_index} else `invalid_lane`; history lane mismatch is `lane_mismatch`; lanes never mixed (design OD9) |

## H. Performance and architecture
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-74 | 25-delta search | delta for every contract; bracketed search; fused scan | bracketed search by strike order, at most 200 delta evaluations per size-M chain (M3A-B12) |
| R-75 | IV and delta reuse | recompute; per-chain cache; cross-cutoff | per chain and cutoff only (spot changes each cutoff) |
| R-76 | Parallel unit and history dependency | per underlying; unit with immutable view | the M1 runner unit with an immutable M2 view; build phase ordered per underlying |
| R-77 | Module boundary | extend chainiv; new module | a new surface module beside chainiv (chainiv bytes and gates unchanged) |
| R-78 | First task gate | G0 as M2-G0 plus separate whole-B6 | single M3A-G0: one-worker B6 with the M2-G0 set, the M2 flow outputs (M2-B9) and the M3a outputs; no separate B10 |
| R-79 | Store budget at retention 252 | 512 MB / 1 GB (M2); lower | 768 MB budget, 1 GB hard per worker (amended 2026-10-30 by the PO after owner decisions 2 and 3: two minute series per name; hard limit unchanged); bytes per series reported; sorted copies lazy, not built for reads that do not need them; the gate measures private bytes |
| R-80 | Runner and perf adapter | extend m1_runner; new | extend tools/m1_runner (opt-in, default single-process); perf_sut adapter deferred |

## I. Added after the review of PR 101
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-81 | Series for V3 and V4 (SUPERSEDED by R-151, OWNER DECISION 2 (2026-10-30, overrides the earlier 30-day-only recommendation)) | ATM IV; M1 30-day IV | formerly: 30-day form only (deliberate exception); superseded: V3 and V4 implement BOTH forms (R-151 to R-154); no longer an exception |
| R-82 | Prior sessions for V7 and V10 | one; n | `prior_sessions` n (default 1): the n-th prior session close; the result carries the `priors` list |
| R-83 | Coverage terms (SUPERSEDED by R-103) | strikes with both rights; either right | listed strike = a strike with an eligible quote for either right; "two per right near the money" = at least 2 eligible strikes per right within +-10 percent of the forward |
| R-84 | Direction | fixed wording; parameter | a `direction` parameter (up, down, either) for V4 to V8, V10, V11, V21 with design-wording defaults (V4 up, V5 up, V6 up, V7 either, V8 up, V10 either, V11 up, V21 up); inclusive (R-35) |
| R-85 | Quote quantisation | gate all; tag | generator contracts with vega >= 4 gate; below that the rows are tagged non-gating |
| R-86 | Solver failures | map to one reason; reuse | reuse the M1 solver reasons verbatim as closed reasons: price_out_of_bounds, upper_asymptote, sigma_cap, precision_exhausted, bound_precision, iteration_budget |
| R-87 | Session-close frame | grid minute; scalar | the frame evaluated at `close_ns` on the close chain, stored as a scalar |
| R-88 | Request parameter sets | free; closed | mode in {intraday, close}; lane in {stock, etf_index}; `stale_limit_ns` default 10 s; min_sessions 20; max_sessions 252; codes invalid_mode, invalid_lane, minute_out_of_range |
| R-89 | History reuse and store changes | later release; M3a | INTO M3a (entry gate includes the M2 store, PR 80); scalar series with per-series k = 252 (above the M2 hard cap of 60: a deliberate additive store change), `total` scalar, `window_s` 0; read forms `scalar_baseline` and `same_minute_column`; lane in the series id; no zero-padding of scalar reads (matrix section 6) |
| R-90 | Per-contract counts | in coverage totals; own field | own field `coverage.contract_reasons` {M1 gate reason: count} |
| R-91 | V6 with fewer than two expiries | no_bracketing_expiry; new reason | new reason `fewer_than_two_expiries` |
| R-92 | Prior validity | accept any; reject | a prior reading time at or after the cutoff is structural `prior_not_before_cutoff` |
| R-93 | New structural codes | none; list | invalid_mode, invalid_lane, minute_out_of_range, prior_not_before_cutoff, threshold_out_of_range, tenor_not_allowed, delta_not_allowed, threshold_required (IO contract section 4) |
| R-94 | Assertions on solver-derived values | exact; intervals | intervals for solver-derived values (IV 1e-4, forward 1e-6); exact only for quote-derived values; no cross-platform byte claim |
| R-95 | Derived series | round parts then subtract; subtract then round | difference of the UNROUNDED floats, rounded once to 8 decimals (skew25, term_30_91); sign on that value |
| R-96 | Deliberate exceptions register | silent; stated | R-46, R-51 and R-58 are stated as the three DELIBERATE exceptions in the matrix section 5 with their sources and need reason rows (R-81 was removed by owner decision 2, R-151); R-52 is an additive store change needing no reason rows; V3 and V4 are match candidates, pending until built |
| R-97 | Entry and crossing forms | in scope; deferred | deferred by name (design 2.8), like M2; the comparison forms V4, V7, V10 stay in scope |
| R-98 | Chain input record | extend; exact M1 | EXACTLY the M1 `ChainContract` plus request-level cutoff_ns, spot, rate, dividend_yield; lane only on history records; one convention per record type: chain strikes and quotes follow M1 (text decimal up to 8 places, or non-bool int = whole units x 10^8), the M2 ticks rule applies to print families only |
| R-99 | Envelope extensions | silent; stated | RULED: M2 outputs keep their `label` field unchanged (no change to any M2 result); M3a results use `labels` (list); `coverage.contract_reasons` and the M3a coverage keys EXTEND the envelope, which supports both; additive |
| R-100 | `cutoff_ns` versus `evaluation_ns` | independent; equal | `evaluation_ns` equals the chain `cutoff_ns` for every M3a output; a request with different values is the new structural VALUE code `cutoff_mismatch` at position 10, after the type checks of that slot (M2 reserves malformed_type for wrong types) |
| R-101 | Scan order across contracts | contract-major; position-major | position-major: for each position of the request list in order, all contracts are scanned in input order; the reported code is the lowest failing position, ties by contract order; within one contract the fields of one position are checked in the order written |
| R-102 | Duplicate-contract worked examples | none; two | (a) two contracts share an id and the second also has a wrong-typed bid: `duplicate_contract` (position 8) is reported before `malformed_type` (position 10), whatever the contract order; (b) two contracts with different ids share expiry, strike and right and one has a wrong-typed bid: `malformed_type` (position 10) is reported before `duplicate_contract` (position 11) |
| R-103 | Coverage terms (supersedes R-83: its definition made the 3/5 gate unreachable) | listed = strike with eligible quote for either right; listed = any contract record | listed strike = a strike with ANY contract record in the chain; eligible strike = a strike with at least one eligible quote (either right); `min_strikes` counts strikes (not contracts); the near-the-money clause (at least 2 eligible strikes per right within +-10 percent of the forward, inclusive) is a coverage gate |
| R-104 | Gate order inside one expiry | coverage first; ATM first | `no_atm_strike` before `low_surface_coverage` (as M1: no_atm_strike first); a coverage-excluded expiry is treated like an expiry without an ATM strike in tenor interpolation |
| R-105 | Labels on mixed frames | one label; both | a result on a mixed European/American frame carries both model labels (a sorted list); an unavailable result carries `labels` = [] |
| R-106 | Empty chain (modifies R-71) | existing reason; new | frame unavailable with the new reason `no_eligible_contract` (no contract passes the M1 gates, including an empty chain); never structural |
| R-107 | Type-first for chain and request fields | value code; type code | a text or float `expiry_days` is `malformed_type` (type-first), a wrong value is `bad_expiry`; a wrong-typed cutoff_ns, expiry_days, mode, lane or right is `malformed_type`; wrong values use the value codes |
| R-108 | M3A-0 value shape (amended by R-141, R-142) | author choice; ratified | RATIFIED interim (I/O contract section 8): per-expiry status and reason, 25-delta sides each with status, reason and value, coverage per expiry with sums, method vocabulary `as_is` and `variance_interpolation`; frame status and the `frame` object as amended by R-141 and R-142 |
| R-109 | Solver failure on one contract | fail the expiry; exclude the contract | exclude that contract (reason from the closed solver set counted in `coverage.contract_reasons`); the expiry continues if coverage still holds |
| R-110 | `max_sessions` | first N; last N available | the last N available sessions before the evaluation session |
| R-111 | Simultaneous history reasons | arbitrary; ordered | order: upstream reason, `insufficient_history`, `session_not_complete`, `zero_range_history` |
| R-112 | History lane at read | lane_mismatch; insufficient_history | a history lane differing from the request lane at READ is `insufficient_history` (M2); `lane_mismatch` applies at append only |
| R-113 | `same_minute_column` and short grids | zero-pad; skip | skips a session whose grid is shorter than the minute index (M3a-specific, no zero-padding) |
| R-114 | Per-series k API | constructor k; per-series | the store declares per-series k with `store.add_series(series_id, k)` (k up to 252) |
| R-115 | Request fields V5 and V10 | implicit; explicit | V10 takes `prior_kind` in {frame, session} and a condition per `direction`; V5 takes `pair` in {9-30, 30-91} |
| R-116 | Units of derived outputs | percent; ratio | `change_ratio` is unitless (change/prior); V21 distance keys are in points (x100); V21 has no default threshold (`threshold_required` when none is given) |
| R-117 | Priors and brackets | partial priors; fail | fewer than n priors gives `insufficient_history`; a bracketing expiry lacking a 25-delta bracket gives `no_delta_bracket` for the tenor |
| R-118 | Gate order for two simultaneous conditions | unspecified; ordered | upstream and frame reasons, then prior-reading checks, then threshold |
| R-119 | Delta target set | free; closed | `delta_target` in {0.25} only; otherwise `delta_not_allowed` |
| R-120 | Threshold parameter names | free; closed | `at_least`, `at_most`, and `x` (percentile); positions 16 to 18 of the request list apply only to outputs that use that parameter |
| R-121 | Pair rows that cannot hold both errors | force; accept swaps | three precedence pair rows whose two errors cannot coexist in one input are equivalent swaps (accepted) |
| R-122 | `threshold_out_of_range` at view read | request only; also read | also applies at view read for `x` |
| R-123 | Structural code field | reason; code | the structural code field is `code`: results carry `code`, rows assert `code`; `reason` is for non-structural unavailability |
| R-124 | None bid or ask | structural; missing quote | None bid or ask is a missing quote (M1: `invalid_quote`), not structural |
| R-125 | Non-finite floats in JSON | omit; tagged object | encode as {"py_type": "float", "text": "nan" or "inf" or "-inf"} (tagged objects as M2); harnesses decode |
| R-126 | Performance series and unit keys | atm_iv grid; iv30 grid | the minute series is the iv30 minute series (not an atm_iv grid); the unit key follows the M1 runner unit_key "%s/%02d/%03d" (underlying/session/cutoff) (R-147), not the session ordinals 01 to 05 of the earlier wording |
| R-127 | Unit of "vega >= 4" | per 1 percent; per 1.00 | the M1 vega per 1.00 of volatility (price change per unit sigma) |
| R-128 | Boundary prices of the solver (Q-13, inverse.py; corrected by R-145) | boundary available; boundary unavailable | `price_out_of_bounds` = target < ll or target > uh (ll the low end of the lower arb enclosure, uh the high end of the upper); the exact-bound statements (exact lower bound gives available IV 0.0, exact upper bound gives `upper_asymptote`) hold only when the bound is exact (see R-145); the other four solver reasons are unit-tested with a stubbed solver, gap recorded |
| R-129 | Series metric names and read results (amended by R-146) | free; closed | series metrics: `iv30` (30-day IV MINUTE series), `iv30_close`, `skew25`, `term_30_91` (session-close scalars); `atm_iv` dropped (R-146); `series_id` = "<UNDERLYING>/<lane>/<metric>"; `scalar_baseline` and `same_minute_column` return {`values`, `sessions`, `n`} |
| R-130 | Fourth equivalent pair swap | force; accept | the pair (`minute_out_of_range`, `prior_not_before_cutoff`) cannot hold both errors in one input and is an equivalent swap (follows from Q03; with the three of R-121 there are four) |
| R-131 | Order of structural codes versus result reasons | mixed; structural first | structural request codes (including `threshold_required` at position 14 and `prior_not_before_cutoff` at position 17) are reported BEFORE any evaluation; the "upstream first" order of R-118 applies only among result-level reasons |
| R-132 | Labels sort | arbitrary; sorted | the `labels` list is the lexicographic ASCII sort of its members, including "delayed" |
| R-133 | `down` convention | mirror; sign | `down` fires at x <= -X for change forms; V21 `down` fires at ratio <= X |
| R-134 | Prior validity scope | first prior; all | `prior_not_before_cutoff` checks ALL supplied priors |
| R-135 | V10 condition | one; two | V10 `condition` in {change, sign_change}, default `change` |
| R-136 | Empty versus short prior store | one reason; two | an empty prior store gives `no_prior_reading`; fewer than n priors (non-empty) gives `insufficient_history`, for V7 and V10 alike |
| R-137 | V11 and V21 failure precedence | any; ordered | ATM tenor first, then the put side, then the call side |
| R-138 | Tolerances | R-62 bound; tighter | 3e-5 annual for IV-derived values, 0.005 points for 25-delta-derived points (R-62 is the upper bound); rows that cannot meet them are non-gating with the reason stated |
| R-139 | Coverage-excluded versus no-25-delta bracketing expiry | one reason; two | a coverage-excluded bracketing expiry gives `no_bracketing_expiry` for the tenor; a bracketing expiry lacking a 25-delta bracket gives `no_delta_bracket` |
| R-140 | Request vocabulary | free; closed | threshold names `at_least`, `at_most`, `x` only; V5 `pair` values "9-30" and "30-91"; `gating` = false on near-threshold rows |
| R-141 | Frame status and reason precedence (supersedes the R-108 frame rule) | available when one expiry is; available only when all are | the M3A-0 frame is available only when every listed expiry, every requested tenor and every 25-delta side is available; otherwise unavailable with the per-expiry, per-tenor and per-side values still shown; reason = the first failing item: expiries ascending (lowest failing expiry reason), then tenors ascending, then 25-delta sides (put then call); follows the rows (COV-17 against COV-31) |
| R-142 | Top-level value of M3A-0 | value; null | top-level `value` is null; the frame details live in the declared `frame` object |
| R-143 | Percentile parameter names | X; x | `x` (lower-case) and `tail` in {top, bottom} for percentile forms (author 2 `tail` ratified); `X` is `x`; V5 pair "9-30" and "30-91"; V10 `condition` (R-135) |
| R-144 | Null in expected rows | asserted; not asserted | a row with null for `labels` or `coverage` is a harness-only partial assertion: null means not asserted |
| R-145 | Exact bounds (corrects R-128 and contract item 9) | always exact; exact only when exact | `price_out_of_bounds` is target < ll or > uh (ll low end of the lower arb enclosure, uh high end of the upper); an exact lower bound gives available IV 0.0 and an exact upper bound `upper_asymptote` ONLY when the bound is exact: lower_exact when r = q = 0, or S = K and r = q, or an OTM forward where the lower bound is 0; upper_exact for a call with q = 0 and a put with r = 0; with non-zero rates a target inside the enclosure ends is `bound_precision` (no IV 0.0) |
| R-146 | Stored series | with atm_iv; without | iv30 minute series, iv30_close scalar, skew25, term_30_91; `atm_iv` dropped (no consumer; SUPERSEDED by R-153, which restores the `atm_iv` minute series); any iv30_minute leftovers fixed in the matrix section 6 |
| R-147 | Unit key | session ordinals 01-05; M1 runner format | the M1 runner `unit_key` format "%s/%02d/%03d" (underlying/session/cutoff); corrects R-126 |
| R-148 | History load scan order | position-major; record-major | RECORD-MAJOR as M2 (line by line, each record checked at its append against the list); the pair (`duplicate_session`, `out_of_order_append`) is a fifth equivalent swap |
| R-149 | Positions 14 and 15 of the request list | always; when the request carries the parameter | apply whenever the request carries the parameter and the output uses it; the rows for positions 14 and 15 move from M3A-0 to an output that uses thresholds |
| R-150 | Performance thresholds and workload facts | free; cited | the thresholds R03 (30 percent) and R07 (5 s and 512 MB) cite M2-B16 or are marked proposals; workload fact: 71 distinct spots across the 78 cutoffs, so a spot-keyed cache cannot pass M3A-B11 accidentally |
| R-151 | ATM form of V3 and V4 (OWNER DECISION 2) [owner-decided (final)] | 30-day only; both forms | V3 and V4 implement BOTH forms; ATM form = the M1 `atm_iv` of the NEAREST ELIGIBLE expiry (M1 definition: strike nearest the forward, ties to the lower strike, mean of call and put IV; eligible = expiry_days >= 1 and covered per R-20 and R-103; per-expiry ATM IVs stay in the frame); the design worker all-strike mean within 7 days is a recorded known difference; R-81 is superseded |
| R-152 | Selector `iv_form` [owner-decided (final)] | implicit; request parameter | request `iv_form` in {atm, 30d}, default atm (design wording order); value code `iv_form_not_allowed` for any other string, type-first `malformed_type` for a non-string; new structural code at position 13 of the request list (after `delta_not_allowed`, same slot) |
| R-153 | Series metrics (amends R-129 and R-146) [owner-decided (final)] | 30-day only; both forms | metrics: `atm_iv` (nearest-eligible-expiry ATM IV MINUTE series on the session grid), `atm_iv_close` (session-close scalar), `iv30` (30-day minute series), `iv30_close` (scalar), `skew25`, `term_30_91` (scalars); series_id "<UNDERLYING>/<lane>/<metric>"; "atm_iv has no consumer" is resolved; V4 priors and V3 history are read from the metric of the selected form; a record of the other form is a different series (no mixing) |
| R-154 | Echo of the form [owner-decided (final)] | silent; echo | the result echoes `iv_form` (V3 and V4) |
| R-155 | Delta convention parameter (OWNER DECISION 3) [owner-decided (final)] | spot only; both | request `delta_convention` in {"spot", "forward"}, DEFAULT "spot" (what brokers show); value code `convention_not_allowed` for any other string, `malformed_type` for a non-string (type-first), at position 13 of the request list after `delta_not_allowed` and `iv_form_not_allowed` (same slot, order written); read only by outputs that use delta (V8, V9, V10, V11, V21 and the 25-delta points of the surface frame); V1 to V7 do NOT take it (a request carrying it for those outputs is not validated, per R-149) |
| R-156 | Definitions of the two deltas [owner-decided (final)] | one; two | T = expiry_days/365, own IV at the contract, absolute value for puts, target 0.25 inclusive. Spot delta: call e^{-qT} N(d1), put e^{-qT} N(-d1). Forward delta (with respect to the forward, no e^{-qT} factor): call N(d1), put N(-d1). The bracketing and interpolation rules (R-09, R-10) are unchanged and apply to the absolute delta of the chosen convention; amends R-04 (spot delta is the default, not the only convention) |
| R-157 | Certified delta per request [owner-decided (final)] | both at once; one | the certified delta (R-05) is computed only for the requested convention; a request computing both is out of scope (no combined-request gate; a Developer may add one later); the 25-delta search gates (bracket count at most 200, M3A-B1, M3A-B2) apply per convention |
| R-158 | Echo [owner-decided (final)] | silent; echo | the result carries `delta_convention` (the convention used) next to `iv_form` where applicable; labels unchanged |
| R-159 | Series metrics carry the convention [owner-decided (final)] | one series; suffix | `skew25` (spot) and `skew25_fwd` (forward); derived scalars from delta points follow the same rule (skew-type metrics, for example the V11 curvature and V21 series if stored: `<metric>_fwd`); `atm_iv`, `atm_iv_close`, `iv30`, `iv30_close`, `term_30_91` are convention-free; series_id "<UNDERLYING>/<lane>/<metric>" |
| R-160 | Mixing conventions [owner-decided (final)] | silent mix; structural | a prior or history record carrying a `delta_convention` field different from the request, or a skew-type series of the other convention, is the structural code `convention_mismatch` (never silent): at position 17 of the request list in the same slot after `prior_not_before_cutoff`, and at view read for skew-type series (new last position of the view read list); a record without the field is treated as "spot" |
| R-161 | Term outputs take no convention [owner-decided (final)] | convention; none | V6 and V7 (term structure, ATM based) take no convention; V9 and V10 history reads use the series of the requested convention |

## Notes for the PO
- Ruling the whole list in one pass: accept all RECOMMENDED, or list exceptions by id. SETTLED rows need no decision. Largest fixture impact: R-04 and R-05 (delta), R-09 (interpolation), R-40 (prior reading), R-89 (store changes); R-01 changes only whether V21 is built.
- Every accepted ruling is interim pending design ratification where the design is silent (R-04, R-09, R-14, R-27 to R-30, R-40, R-42, R-44 are design-silent or open in volatility-radar.md section 2.9 and 12); a changed answer regenerates the dependent fixtures.
