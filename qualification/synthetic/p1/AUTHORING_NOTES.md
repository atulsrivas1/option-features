# P1 fixtures: authoring notes (Tester)
Provenance: SYNTHETIC. Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12
Regenerate: `python gen_p1.py --out p1_cases.json` (seed 20261029, LF, no absolute paths).
Check: `python selfcheck_p1.py p1_cases.json` (separate reference model plus mutation run).
## Independence statement
Files read, only these: option-contracts.md and flow.md (in full), workers-vs-conditions.md
(grep of lines on F3-F6, F13-F16, G1/G2/G5 and the conflicts list; legacy description only),
PO_RELEASE_PLAN_V2.md, PO_RELEASE_PLAN_V3.md, DESIGN_SESSION_REQUESTS.md,
r28-design/PO_R28_DESIGN_RULINGS.md, plus the PO rulings PO-P1-02 (DECISIONS.md, 2026-10-29).
No implementation, test, existing fixture, qualification output, docs/r25, r26,
r26-variants, tools or developer note was read. No expected value derives from library output.
Generator and self-check are separate code paths by one author: they prove internal
consistency, not design correctness.
## Conventions
- Times: integer ns relative to T (evaluation time = 0). Decimals: strings, <= 4 places.
- Results: exact decimal string if terminating, else reduced rational p/q.
- Premium = price x size x 100, standard contracts only (multiplier 10 print excluded).
- Statuses: available, unavailable, unclassified (signing, no side), not_asserted.
- Gate precedence (PO ruling): no_quote, invalid_quote, crossed_market, locked_market, stale_quote.
  Locked does not block signing. Both fields null = no_quote; one-sided = invalid_quote.
- Signing: quote must be strictly before the trade, else no_quote. Stale if age > 3 s
  (spread: > 10 s). Touch: ask if price >= ask - eps, bid if price <= bid + eps (inclusive),
  both = ambiguous_touch, neither = inside_spread. Window = [end-W, end], closed both ends.
- pending_design_request is a list of request numbers or null.
## Closed reason set
invalid_quote, locked_market, crossed_market, stale_quote, low_quote_coverage, no_quote, missing_reference, inside_spread, no_classified_premium, ambiguous_touch.
## Pending design ratification
1 (locked: spread locked_market, signing proceeds): B01, B02, B03, B04, B05, B06, R03, R06
2 (bid <= 0 invalid for spread and signing): A07, A08, A13, A14, E15, E16, S03
3 (count coverage gate; time-weighted average is M1, not P1): G01, G02, G03, G04, G05, G06, G07, G08, G09, G10
6 (F5/F6 wording): D01, D02, D03, D04, D05, D06, D07, D08, D09
8 (F13-F16 touch rule, 3 s, labels): B04, B05, B06, E01, E02, E03, E04, E05, E06, E07, E08, E09, E10, E11, E12, E13, E14, E15, E16, E17, E18, E19, E20, Q01, Q02, Q03, Q04, Q05, Q06, Q07, Q08, S01, S02, S03, R04, R05, R06, T01, T02, E21, E22, E23, L01, L02
## Open items still needing a ruling or later mapping
- legacy_midpoint_epsilon_not_probed: H01, H02, H03, H04, H05, H06
- legacy_midpoint_tie_side_unknown: H10
- window_closed_both_ends: C03, C05, C07
PO-ruled this session (no longer open): epsilon inclusive, empty window = 0, precedence,
crossed signing, spread stale gate, ambiguous_touch.
## Mutations (each must fail every mapped row; verified by selfcheck_p1.py)
- M01 spread treats bid = 0 as valid -> A07, A13
- M02 spread_bps divides by ask instead of midpoint -> A01, A02
- M03 locked quote gives spread 0 available -> B01, B02, B03
- M04 crossed quote returns an absolute-value spread -> A12
- M05 locked gate also withholds signing (request 1 option B) -> B04, B05
- M06 inside-spread price split at midpoint instead of unclassified -> E05, E09, E10, S01, S02
- M07 epsilon comparison exclusive at the boundary -> E04, E08
- M08 quote age 3 s treated as stale (exclusive limit) -> Q02, Q07
- M09 quote age limit off by one ns (3 s + 1 ns passes) -> Q03, Q08
- M10 window_end ignored, last-print anchor always used -> C01, C05
- M11 window excludes a print exactly at window_end -> C03
- M12 window includes a print after window_end -> C05
- M13 window start boundary exclusive -> C07
- M14 share denominator is referenced premium only -> D02, D01
- M15 short share also requires spot (joint coupling) -> D06, D01
- M16 OTM share also requires expiry -> D07, D09
- M17 joint output needs only one of civil date and spot -> D01, D10
- M18 short-dated limit off by one day (dte <= 3) -> D08
- M19 coverage counts excluded-condition updates -> G03, G10
- M20 coverage window excludes update at exactly -300 s -> G04
- M21 coverage minimum is 6 instead of 5 -> G02
- M22 unclassified premium added to ask side -> S01, S02
- M23 signing accepts bid = 0 -> E15, E16, S03
- M24 ask-side label reads 'bullish-side proxy' -> E01, E02
- M25 share threshold exclusive (> instead of >=) -> D04
- M26 window_end hard-coded to T instead of the request value -> C10
- M27 OTM test inclusive at the money -> D01, D09
- M29 joint short amount needs expiry only -> D10
- M30 double touch (locked or wide epsilon) resolved as ask -> B06, E21
- M31 stale checked before validity gates -> R01, R02, R04, R05
- M32 quote at the same ns as the trade is unusable -> T01
- M33 quote after the trade is usable -> T02
- M28 coverage gate also blocks nothing (blocks list empty) -> G01
## Legacy-mode rows (tag legacy_mode, needs_byte_mapping true)
Rows: A01, A02, A03, C02, C04, C06, D10, H01, H02, H03, H04, H05, H06, H07, H08, H09, H10.
Developer/PO map each to R25/R26 tag bytes later. H10 (midpoint tie) is not_asserted.
Not asserted: legacy epsilon, age limit, spot age, empty-window result.

Convention PO-P1-01 (PO-ruled): when no premium is classified, ask_share_of_classified and bid_share_of_classified are null with reason no_classified_premium (rows S02 and related).
