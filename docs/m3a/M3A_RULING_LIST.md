# M3a ruling list (one batch for the PO, revision 2)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Author: Architect, 2026-10-30. Status: for ONE PO pass BEFORE any fixture author starts. 102 ambiguities and design-silent edge cases (R-01 to R-102), each with options and the Architect RECOMMENDED ruling. Rows marked SETTLED were ruled by the independent review of PR 101 (PO rulings) or follow directly from the M1 input record; they stay in the list so the ids are stable. Everything else is a proposal. Lesson of M2 applied: the precedence lists, type-first per field, trusted versus untrusted inputs and the canonical forms are decided here, once (R-66 to R-71). Where the design is silent an accepted ruling is interim pending design ratification. Companions: M3A_CAPABILITY_MATRIX.md, M3A_GATE_BUDGETS.md, M3A_FIXTURE_REQUIREMENTS.md, M3A_IO_CONTRACT.md. Sources: volatility-radar.md (VR), option-contracts.md (OC), workers audit (AUD), M1 code and M2 rulings.

## A. Scope
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-01 | M3a row list | V1, V3-V10 only; add V11; add V21 | SETTLED: V11 is a design row and JOINS M3a (same two 25-delta points; tracker moved by the Auditor); V21 stays PROPOSED (derived from V8): accept it as M3A-11 or move it to M3b |
| R-02 | V2 (ATM IV, M1) points unit and threshold form | leave M1 annual decimal; add points and threshold output | add the points form and threshold rule as a thin wrapper in M3a; M1 bytes unchanged |
| R-03 | Rows left for later | V12-V15, V22 (M3b), V16-V19, V20, frame builder, presets | defer all; named as not built in the release note (history reuse is NOT deferred, see R-89) |
| R-04 | Delta definition used to place 25 delta | spot delta N(d1)e^{-qT}; forward delta; delta with ATM IV | spot delta of the BSM model at the contract OWN IV with e^{-qT}, absolute value for puts (R25 Greeks convention); target 0.25 inclusive |
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
| R-41 | V4 form | relative percent; absolute points; ATM or 30d; zero prior | constant 30-day IV only (R-81); change_points and change_ratio both output; fires on relative percent (10 default) per `direction`; prior 0 gives `zero_denominator` |
| R-42 | V1 history cadence | session-close value; same minute; all frames | session-close scalar of each prior session, in both modes |
| R-43 | V3 minute alignment | same minute index; nearest frame within a tolerance | the same grid minute index; a prior session without that minute is skipped (not substituted) |
| R-44 | Look-back and minimum | 252 and 20 (worker); 20 only | design-silent beyond "at least 20 prior sessions": `min_sessions` 20, `max_sessions` 252 (the worker V3 figure; extended to V1 and V9 as an interim ruling) |
| R-45 | Percentile form and bottom X | M2 upper_share; add lower_share | M2 forms: top X percent fires when upper_share <= X/100; bottom X percent when lower_share = count(history <= x)/n <= X/100; both always returned |
| R-46 | Zero-range history | percentile of a constant history; unavailable | unavailable `zero_range_history` (design VR P3); DELIBERATE exception to M2 Q2 (there a constant history is available and cannot fire) |
| R-47 | Completeness and "new" | partial sessions counted; only complete | only sealed complete sessions; below `min_sessions`: `insufficient_history` ("new") |
| R-48 | Stored value representation | float; rational; integer | integers in 10^-8 units (the rounded-once 8-decimal value); ranks on integers |
| R-49 | Rounding | at storage; at output; both | round once, half to even, from the binary64 value to 8 decimals; that decimal is the reported value, the stored integer and the basis of every comparison |
| R-50 | Ties at the percentile | at-or-above; split | M2 rule (ties count in upper_share and in rank_le) |
| R-51 | Days whose value is absent in history | skip; fail | `scalar_baseline` skips missing and incomplete days; n counts available sessions; below min_sessions: insufficient_history; DELIBERATE exception to M2 Q3 and AMB-17 (design: "at least 20 prior sessions") |
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
| R-69 | Chain structural codes | reuse M1 reasons; new | bad_cutoff, bad_spot, bad_rate, bad_expiry, unknown_right, duplicate_contract, bad_strike, malformed_type (M1 raises ValueError for these; M3a maps them to codes); no multiplier, civil-date or ordering codes |
| R-70 | History input validation | reuse; new | reuse the M2 store codes and order unchanged |
| R-71 | Empty chain or all excluded | structural; unavailable | unavailable with the M1 reasons counted in coverage; never structural |
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
| R-79 | Store budget at retention 252 | 512 MB / 1 GB (M2); lower | 512 MB budget, 1 GB hard per worker; bytes per series reported |
| R-80 | Runner and perf adapter | extend m1_runner; new | extend tools/m1_runner (opt-in, default single-process); perf_sut adapter deferred |

## I. Added after the review of PR 101
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-81 | Series for V3 and V4 | ATM IV; M1 30-day IV | SETTLED: V3 and the V4 comparison use the M1 30-day IV (`iv_30d`, design key constant_30d_iv_change); ATM-form variants out of scope |
| R-82 | Prior sessions for V7 and V10 | one; n | `prior_sessions` n (default 1): the n-th prior session close; the result carries the `priors` list |
| R-83 | Coverage terms | strikes with both rights; either right | listed strike = a strike with an eligible quote for either right; "two per right near the money" = at least 2 eligible strikes per right within +-10 percent of the forward |
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
| R-96 | Deliberate exceptions register | silent; stated | R-46, R-51, R-58 and R-81 are stated as DELIBERATE exceptions in the matrix section 5 with their sources; the re-audit records V3 and V4 as "partial: 30-day form only" |
| R-97 | Entry and crossing forms | in scope; deferred | deferred by name (design 2.8), like M2; the comparison forms V4, V7, V10 stay in scope |
| R-98 | Chain input record | extend; exact M1 | EXACTLY the M1 `ChainContract` plus request-level cutoff_ns, spot, rate, dividend_yield; lane only on history records; one convention per record type: chain strikes and quotes follow M1 (text decimal up to 8 places, or non-bool int = whole units x 10^8), the M2 ticks rule applies to print families only |
| R-99 | Envelope extensions | silent; stated | `labels` (list), `coverage.contract_reasons` and the M3a coverage keys EXTEND the M2 Result envelope (M2 `label` becomes `labels`); additive, M2 results unchanged |
| R-100 | `cutoff_ns` versus `evaluation_ns` | independent; equal | `evaluation_ns` equals the chain `cutoff_ns` for every M3a output; a request with different values is structural `malformed_type` at the malformed_type slot (position 10) |
| R-101 | Scan order across contracts | contract-major; position-major | position-major: for each position of the request list in order, all contracts are scanned in input order; the reported code is the lowest failing position, ties by contract order; within one contract the fields of one position are checked in the order written |
| R-102 | Duplicate-contract worked examples | none; two | (a) two contracts share an id and the second also has a wrong-typed bid: `duplicate_contract` (position 8) is reported before `malformed_type` (position 10), whatever the contract order; (b) two contracts with different ids share expiry, strike and right and one has a wrong-typed bid: `malformed_type` (position 10) is reported before `duplicate_contract` (position 11) |

## Notes for the PO
- Ruling the whole list in one pass: accept all RECOMMENDED, or list exceptions by id. SETTLED rows need no decision. Largest fixture impact: R-04 and R-05 (delta), R-09 (interpolation), R-40 (prior reading), R-89 (store changes); R-01 changes only whether V21 is built.
- Every accepted ruling is interim pending design ratification where the design is silent (R-04, R-09, R-14, R-27 to R-30, R-40, R-42, R-44 are design-silent or open in volatility-radar.md section 2.9 and 12); a changed answer regenerates the dependent fixtures.
