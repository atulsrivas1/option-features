# M3a ruling list (one batch for the PO)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Author: Architect, 2026-10-30. Status: for ONE PO pass BEFORE any fixture author starts. 80 ambiguities and design-silent edge cases (R-01 to R-80), each with options and the Architect RECOMMENDED ruling. Nothing is ruled; "RECOMMENDED" is a proposal. Lesson of M2 applied: the single precedence list, type-first per field, trusted versus untrusted inputs and the canonical forms are decided here, once (R-66 to R-71), instead of after the fixtures. Where the design is silent, an accepted ruling is interim pending design ratification. Companions: M3A_CAPABILITY_MATRIX.md, M3A_GATE_BUDGETS.md, M3A_FIXTURE_REQUIREMENTS.md, M3A_IO_CONTRACT.md. Sources: volatility-radar.md (VR), option-contracts.md (OC), workers audit (AUD), M1 and M2 rulings.

## A. Scope
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-01 | M3a row list | V1, V3-V10 only; add V11 and V21 (same surface); add V2 re-audit | V1, V3-V10 plus V11 and V21 (they cost two derived outputs on the same points); V2 re-audit only |
| R-02 | V2 (ATM IV, M1) points unit and threshold form | leave M1 annual decimal; add points and at-least/at-most output | add the points form and threshold rule as a thin wrapper in M3a; M1 bytes unchanged |
| R-03 | Rows left for later | V12-V15, V22 (M3b with the realized-volatility join and 52-week generator), V16-V19, V20, frame builder, presets | defer all; named as not built in the release note |
| R-04 | Delta definition used to place 25 delta | spot delta N(d1)e^{-qT}; forward delta N(d1); delta with ATM IV | spot delta of the BSM model at the contract OWN IV with e^{-qT}, absolute value for puts (R25 Greeks convention); target 0.25 inclusive |
| R-05 | Delta source and decision rule near the target | R25 certified delta; float delta with certified fallback; closed form on floats | use the existing certified delta; a float filter with a certified fallback is allowed only with identical bytes (Developer choice, gate unchanged) |
| R-06 | Which right defines each side | put IVs for the put side and call IVs for the call side; OTM-only (puts below forward, calls above); mean of both rights | each side from its own right (V8 reads put side against call side); both rights must be eligible |

## B. Surface construction
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-07 | Moneyness definition (for labels and wings) | K/S; K/F; ln(K/F); delta | k = ln(K/F), F = S exp((r-q)T) per expiry (as M1 ATM), as exact bracketing; delta for the 25-delta points |
| R-08 | Strike grid | listed strikes only; fixed moneyness grid; fixed delta grid | listed strikes only; no synthetic grid in M3a |
| R-09 | Interpolation across strikes | linear IV in delta; linear IV in k; linear total variance in k; cubic; SVI | linear IV in delta between the two bracketing eligible strikes of the right (SVI skipped by the design) |
| R-10 | Bracket when delta is not monotone in strike | first crossing from ATM outward; any crossing; lowest strike | first crossing scanning outward from the ATM strike; ties to the lower strike |
| R-11 | American-style labels in the surface | use only exact-model; also approximate; also american_itm | use exact-model and approximate (M1 labels); exclude american_itm and style_unknown; count labels in coverage and label the result "modeled, approximate: American-style" when any used |
| R-12 | Nonstandard contracts and excluded conditions | include; exclude and count | exclude (multiplier != 100, excluded condition) and count in coverage, as M1 and M2 |
| R-13 | Expiry set: minimum days | all listed; days >= 1; days >= 2 | days >= 1 (an expiry within one 24 h step of the cutoff is not a surface point); parameter `expiry_min_days` default 1 |
| R-14 | Tenors | 9, 30, 91 (catalogue); 8 tenors 10d to 360d (domain note); expiry-based only | 9, 30, 91 days only; set closed, `tenor_not_allowed` otherwise |
| R-15 | Constant-maturity method for 9d and 91d | linear total variance (M1 30d rule); flat forward variance; interpolate IV | linear in total variance between bracketing expiries, as M1 |
| R-16 | Extrapolation | none; flat beyond the last expiry or strike | none anywhere; `no_bracketing_expiry`, `no_delta_bracket` |
| R-17 | Days-to-expiry counting | civil days; M1 convention (expiry N x 24 h after the cutoff) | the M1 convention (T = days/365, ACT/365) |
| R-18 | Expiry on the cutoff day or after expiry time | include with T = 0; exclude | exclude (R-13) |
| R-19 | Longest expiry cap | none; cap at 400 days | none; tenors above the longest expiry are unavailable |
| R-20 | Minimum coverage per expiry | 3/5 of listed strikes eligible (worker 60 percent); fixed count; none | 3/5 of listed strikes and at least `min_strikes` 4 (two per right near the money); below: expiry unavailable, `low_surface_coverage`; parameters echoed |
| R-21 | Minimum strikes to interpolate | 2 bracketing; 3; 4 | 2 bracketing eligible strikes of the right, else `no_delta_bracket` |
| R-22 | Deep wings | exclude beyond a bound; keep | keep; eligibility is by M1 gates only |
| R-23 | Duplicate strikes (adjusted or split contracts) | reject chain; keep the standard; keep both | exclude the nonstandard one (R-12); two standard contracts with equal strike and right are `duplicate_contract` only if the id repeats, else the lower contract id wins and the other is counted excluded |
| R-24 | Rate and yield | one constant per chain (M1); term curve | one rate and one yield per chain (M1); a curve is a later ruling |
| R-25 | Spot at the cutoff | supplied spot with staleness gate; last trade | supplied spot as M1; staleness belongs to the caller in M3a (eligibility field as M1) |
| R-26 | Quote price | midpoint (M1); microprice | midpoint (M1 ruling retained) |

## C. Skew, term, derived outputs
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-27 | Which expiry carries the skew | each listed expiry; nearest; 30-day tenor | the 30-day constant-maturity tenor for V8-V10; per-expiry points also returned in the surface frame |
| R-28 | Skew at a tenor | skew of the nearest expiry; 25d IVs per expiry then CM per side; CM of skew values | per-expiry 25d put and call IVs, then CM by linear total variance PER SIDE, then skew = put minus call |
| R-29 | V8 definition against the worker band | 25-delta risk reversal (design OC); pooled delta band 0.15 to 0.35 (AUD) | 25-delta (design contract); the worker band recorded as a known difference |
| R-30 | Term slope definition (V7) | 30d to 91d gap; near to next expiry; slope per year | the 30d-91d gap in points (longer minus shorter); slope = gap / (91-30) days is not offered |
| R-31 | V5 sign and pairs | shorter minus longer (worker); longer minus shorter | longer minus shorter, pairs 9-30 and 30-91; sign convention stated in the label |
| R-32 | V6 nearest and second expiry | nearest listed; nearest eligible; second = next eligible | nearest and second ELIGIBLE expiries after R-13 and R-20; spread = second minus nearest |
| R-33 | V7 form | gap change since prior session; slope change; both | both outputs (gap change, slope change in points); fire on either at least X |
| R-34 | V10 sign change | strict sign flip; zero counts as a side; threshold dead band | sign of skew in {-1, 0, +1}; changed when the signs differ and neither is 0; 0 never counts as a flip |
| R-35 | Threshold inclusivity | at least X inclusive; strict | inclusive ("at least X", "at most X"), as M2 |
| R-36 | Defaults and units | worker placeholders in decimals (0.05) or points | points: skew 5, skew change 2, term 3, term change 2, curvature 3, IV change 10 percent; all echoed; X default 5 |
| R-37 | V11 definition | (put25 + call25)/2 - ATM; put25 + call25 - 2 ATM; butterfly vs strike | (put25 + call25)/2 minus ATM in points; fires when above (or below) by at least X |
| R-38 | V21 definition and zero denominator | (put25 - ATM)/(call25 - ATM); inverse; absolute values | (put25 - ATM)/(call25 - ATM); call distance 0 gives `zero_denominator`; negative distances allowed and shown |
| R-39 | Wording of sides | direction words; neutral | "put-side" and "call-side" only; blocked words never appear in labels (design WL78, WL91) |

## D. History and percentiles
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-40 | Clock of "prior reading" | previous frame (in memory); previous stored frame; prior session close | `prior` is an INPUT (kind frame or session, with its time); the caller or the store supplies it; no hidden in-memory state; evidence line states both times |
| R-41 | V4 form | relative percent; absolute points; ATM or 30d basis; zero prior | both change_points and change_ratio output; fire on relative percent (10 default); basis chosen by parameter; prior 0 gives `zero_denominator` |
| R-42 | V1 history cadence | session-close value; same minute; all frames | session-close value of each prior session, in both modes |
| R-43 | V3 minute alignment | same minute index of the 60 s grid; nearest frame within a tolerance | the same grid minute index; a prior session without that minute is skipped (not substituted) |
| R-44 | Look-back and minimum | 252 and 20 (design worker); 20 only | K = 252 sessions, minimum 20 complete sessions |
| R-45 | Percentile form and bottom X | M2 upper_share; add lower_share; interpolated percentile | M2 forms: top X percent fires when upper_share <= X/100; bottom X percent fires when lower_share = count(history <= x)/n <= X/100; both always returned |
| R-46 | Zero-range history | percentile of a constant history; unavailable | unavailable `zero_range_history` (design VR P3) |
| R-47 | Completeness and "new" | partial sessions counted; only complete | only sealed complete sessions; below minimum: `insufficient_history` ("new") |
| R-48 | Stored value representation | float; exact rational; integer micro-vol | integer micro-vol (annual vol x 10^6) rounded half to even from the solver value; all ranks on integers |
| R-49 | Rounding rules | round at storage only; round at output | round once at storage into the history series; outputs of the current frame are exact rationals of the solver value and are not rounded; the rank compares the rounded current value with rounded history |
| R-50 | Ties at the percentile | count ties as at-or-above; split | M2 rule (ties count in upper_share and in rank_le) |
| R-51 | Days whose CM IV is absent in history | skip (n shrinks); count as missing and fail | skip the day; n counts only present values; below minimum: insufficient_history |
| R-52 | Retention and memory | raise the M2 cap of 60 to 252 for all; per-series cap | raise the cap to 252 for the M3a series; the minute grid only for atm_iv, session-close values for iv30, skew25, term_30_91 (budget: 81 MB for 103 names) |
| R-53 | Which series stores skew | 30d tenor skew; nearest expiry; every expiry | 30d tenor skew (R-27, R-28) as `skew25` |
| R-54 | Minutes at the session edges for V3 | all 390; skip the first and last minute | every grid minute; the minute before the first usable frame gives `insufficient_window` |
| R-55 | Half-day sessions for V3 | align by minute index; by fraction of session | by minute index from open; a half-day session has fewer minutes and is skipped for later minutes |

## E. Frames, modes, feed
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-56 | Intraday versus end-of-day mode | one mode flag; two functions | `mode` parameter; end_of_day reads the last-close frame and needs a sealed session (`session_not_complete`) |
| R-57 | Exact frame rule (VR3) | nearest frame; exact only | the library takes one chain at one cutoff, so the frame is exact by construction; "no exact frame" is an engine reason, not a library reason |
| R-58 | Delayed feed | compute and label; unavailable | V3 and intraday V1, V4 give invalid_input `delayed_feed_tag` (as F1 in M2); end-of-day forms computed and labelled delayed |
| R-59 | Prior session and holidays | previous calendar day; previous session by calendar | previous session in the supplied calendar |

## F. Units, rounding, representation
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-60 | IV unit | annual decimal; points | annual decimal in `iv` keys; `_points` keys are x100 differences; thresholds are in points |
| R-61 | Output number type | float; rational | reduced "n/d" rationals or ints; no float in any output |
| R-62 | Solver tolerance versus exact output | assert closed forms exactly; with 1e-4 | outputs are exact functions of returned IV; closed-form expectations carry the M1 tolerance 1e-4; rows within the tolerance of a threshold are not asserted (near-threshold attack rows state the ruling instead) |
| R-63 | Labels | free text; closed list | closed labels: modeled, modeled approximate (American-style), delayed |
| R-64 | Version and envelope | new envelope; M2 Result | the M2 Result envelope and the library version string (no bump); unavailable carries value and fired null |
| R-65 | Tagged encodings of non-JSON types | none; M2 tagged objects | the M2 tagged objects (Decimal, Fraction, bytes); harnesses decode before calling |

## G. Malformed inputs and precedence (decided once)
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-66 | Precedence list | per area; ONE list | the single list of M3A_IO_CONTRACT.md section 4 (16 positions); the first failing code is reported; one worked example per adjacent pair is a fixture requirement |
| R-67 | Type-first | value codes first; type first globally; per field | per field at the position of that field value check (M2 ruling), including price grammar and integer-tick rules as M2 section 9 |
| R-68 | Trusted versus untrusted inputs | validate always; scanned for trusted | untrusted inputs validated in full; views of a verified store and a validated chain are scanned on hot paths; `validate="full"` always available, same codes |
| R-69 | Chain structural codes | reuse M1 reasons; new codes | the codes of section 4 (bad_cutoff, bad_spot, bad_rate, duplicate_contract, unknown_right, bad_strike, bad_multiplier, bad_expiry, unordered_quotes) |
| R-70 | History input validation | reuse store codes; new | reuse the M2 store codes and order unchanged |
| R-71 | Empty chain or all excluded | structural; unavailable | unavailable with the M1 reasons counted in coverage; never structural |
| R-72 | Parameter validation | clamp; reject | reject: tenor_not_allowed, delta_not_allowed, X outside 0 to 100 as malformed_type, K and min_sessions below 1 as malformed_type |
| R-73 | Lane handling | one lane per call; mix | one lane per call; history lane mismatch is `lane_mismatch`; ETF and index lane never mixed (design OD9) |

## H. Performance and architecture
| ID | Topic | Options | RECOMMENDED |
|---|---|---|---|
| R-74 | 25-delta search strategy | delta for every contract; bracketed bisection over strikes; fused scan | bracketed search by strike order with at most one delta per contract; count gated by M3A-B13 |
| R-75 | IV and delta reuse | recompute; per-chain cache; cross-cutoff cache | per chain and cutoff cache only (spot changes each cutoff; no cross-cutoff reuse claimed) |
| R-76 | Parallel unit and history dependency | per underlying; unit with immutable view | the M1 runner unit with an immutable M2 view; build phase ordered per underlying |
| R-77 | Module boundary | extend chainiv; new module | a new surface module beside chainiv (chainiv bytes and gates unchanged) |
| R-78 | First task gate | G0 as M2-G0; per-output gates only | M3A-G0 one-worker full-output B6 with M2 and M3a outputs (budgets doc section 4) |
| R-79 | Store budget at retention 252 | per worker 512 MB / 1 GB as M2; lower | 512 MB budget and 1 GB hard per worker (M2 ruling); report bytes per series |
| R-80 | Runner and perf adapter | extend m1_runner; new runner | extend tools/m1_runner (opt-in, default single-process); perf_sut contract-v2 adapter stays deferred |

## Notes for the PO
- Ruling the whole list in one pass: accept all RECOMMENDED, or list exceptions by id. The three decisions with the largest fixture impact are R-04 and R-05 (delta), R-09 (interpolation) and R-40 (prior reading); R-01 changes the row count.
- Every accepted ruling is interim pending design ratification where the design is silent (R-04, R-09, R-14, R-28 to R-30, R-40 and R-42 are design-silent or design-open in volatility-radar.md section 2.9 and 12); a changed answer regenerates the dependent fixtures.
