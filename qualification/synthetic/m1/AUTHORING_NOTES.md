# M1 fixture authoring notes (Tester)
Provenance: SYNTHETIC. Generators are test oracles, not library code. Date 2026-10-29.
Label (verbatim, also in both dataset headers): mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

## Scope and counts
- m1_oc_cases.json: 110 rows (110 gating, 0 non-gating). OC5 cases 1-19 and 24b, OC6 cases 20-34, plus carry-in, zero-weight current quote, no_window_spread, stale boundaries, M14 boundary rows, non-standard contract, bursty updating, structural rows. Cross cases 35-36 skipped (adapter work); no vendor content.
- m1_iv_cases.json: 41 rows (41 gating, 0 non-gating). Per-contract IV (IV-C), ATM IV (IV-A, incl. IV-A17 parity-consistent chain), 30-day IV (IV-T).
- Row fields: id, group, design_ref, case, op, inputs, request, expected, derivation, tags (IV rows also oracle.sigma). Times are integer ns relative to T=0; decimals are strings, at most 4 places; sizes are integers in a separate list keyed by quote revision (QuoteSize record). OC input has feed_kind (consolidated|single_venue), contract_style, contract_standard. Request has session_open_ns, stale_limit_ns (10 s), thresholds, window_ns (300 s), coverage_min (5).
- Status values: fired, not_fired, unavailable, structural_error. Values are exact rationals plus a 4dp decimal. Closed reasons now include excluded_condition. No row is pending: every former ambiguity row is gating under the PO rulings D1-D14 (ids OC6-B1.. keep their names).

## PO rulings applied (message of 2026-10-29)
D15 negative bid = invalid_quote (OC5-S03, OC6-S02); structural only for negative/non-integer size, non-monotone time, malformed type (OC5-S05), full ordering tie (OC5-18c). D1 current quote weighted event to T (OC6-B1). D2 average and ratio in bps of midpoint (OC6-B2; other gating rows hold the midpoint constant). D3 coverage counts regular-condition updates, validity ignored (OC6-B3). D4 coverage clipped at session open (OC6-B4 gives low_quote_coverage). D5 interval starts at known_at (OC6-B7). D6 gate order: validity, stale, coverage (OC5-B1, OC6-B9); excluded_condition reason (OC5-17a, OC6-EX); single_venue affects OC5 only (OC6-B11). D7 T before every quote = no_quote (OC5-16d, 16e). D8 vacuous stale branch dropped (row OC5-17b deleted). D9 order (event, seq, known_at), full tie structural. D10 stale on event time. D11 denominator = valid weighted time. D12 ACT/365, expiry N x 24 h after cutoff, midpoint, continuous r and q. D13 American nearest-to-forward = strike nearest F across all listed strikes, ties lower, K=F not ITM, any American ATM leg gives approximate (IV-C09, IV-A12). D14 bracketing expiry without ATM strike gives no_bracketing_expiry (IV-T12); exact-30d expiry without ATM strike gives no_atm_strike, no fallback (IV-T13).

## IV tolerance (fixed before any run)
IV (contract, ATM, 30-day): absolute 1e-4 (0.01 vol point). Forward: absolute 1e-6. Quotes are 4dp mids with +/-0.0010; every contract behind an expected value has vega >= 4, so quantisation costs under 1e-5 (measured max 7.6e-06, limit 2e-5). Expected IVs are the stated sigmas (30-day value is an exact function of them), never solver output. Real expiry time-of-day is deferred.

## Mutations (each a mutated copy of my own oracle run over the rows; all caught)
| M | Mutation | Catching rows (all sub-variants unless a/b shown) |
|---|---|---|
| M1 | OC5 exclusive threshold | OC5-03, OC5-05a, OC5-08c |
| M2 | bid share instead of imbalance | OC5-01, OC5-04, OC5-02, OC5-03, OC5-05a (+20) |
| M3 | swap bid/ask labels | OC5-01, OC5-02, OC5-03, OC5-05a, OC5-07b (+16) |
| M4 | divide by bid only (a) / ask only (b) | a: OC5-01, OC5-02, OC5-03 (+19); b: OC5-01, OC5-02, OC5-03 (+20) |
| M5 | abs value, no side | OC5-02, OC5-05a, OC5-08c, OC5-09b, OC5-18a (+1) |
| M6 | stale dropped (a), limit +1ns (b), -1ns (c) | a: OC5-15a, OC5-15d, OC5-15f (+5); b: OC5-15d, OC5-15f, OC6-ST-b; c: OC5-15c, OC5-15e, OC6-ST-a |
| M7 | ignore known_at | OC5-16b, OC5-16e |
| M8 | fall back to older quote | OC5-17a, OC5-G2 |
| M9 | both-zero treated as 0 | OC5-10 |
| M10 | OC6 ratio inverted | OC6-20, OC6-21, OC6-23a, OC6-23b, OC6-23c (+26) |
| M11 | OC6 thresholds exclusive | OC6-23a, OC6-23b, OC6-25b, OC6-25c, OC6-31b (+2) |
| M12 | window 240 s (a) / 360 s (b) | a: OC6-26, OC6-27, OC6-28a (+8); b: OC6-24b, OC6-28b |
| M13 | coverage min 4 (a) / 6 (b) | a: OC6-24b, OC6-B4; b: OC6-24a, OC6-28a, OC6-28b (+8) |
| M14 | binary64 arithmetic | OC6-31b, OC6-31c, OC6-25c |
| M15 | OC6 evaluated on locked quote | OC6-30a |
| M16 | count includes excluded-condition | OC6-24c |
| M17 | simple mean not time-weighted | OC6-27, OC6-BURST, OC6-20, OC6-21, OC6-23a (+27) |
| M18 | window excludes update at exactly 300 s | OC6-28a, OC6-28c, OC6-31b, OC6-31c, OC6-33a (+2) |
| M19 | stale inclusive/exclusive swapped | OC5-15c, OC6-ST-a, OC5-15e |
| M20 | OC5 blocked by low coverage | OC5-24b, OC5-01, OC5-02, OC5-03, OC5-04 (+26) |
Extra OC mutants: X1: OC6-28b; X2: OC6-33a, OC6-33b; X3: OC6-26, OC6-33b (+1); X4: OC6-26, OC6-B3; X5: OC6-B2; X6: OC6-B3; X7: OC6-B4; X8: OC6-B7; X9: OC5-B1, OC6-G2; X10: OC6-B9; X11: OC6-B11; X12: OC5-NSTD, OC6-NSTD (X1 no carry-in, X2 previous session enters, X3 denominator = window length, X4 invalid intervals weighted, X5 price spread not bps, X6 coverage counts valid only, X7 coverage unclipped, X8 interval starts at event, X9 stale before validity, X10 coverage before stale, X11 single_venue blocks OC6, X12 non-standard blocks).
Extra IV mutants: V1: IV-A03, IV-A04, IV-A05 (+2); V2: IV-A02, IV-A15; V3: IV-A01, IV-A02, IV-A03 (+16); V4: IV-T01, IV-T07, IV-T08 (+2); V5: IV-C02, IV-C05, IV-C06 (+5); V6: IV-C02, IV-C05, IV-C06 (+1); V7: IV-T03, IV-T04; V8: IV-T02, IV-T14, IV-T16 (+1); V9: IV-A04, IV-A05, IV-A06 (+4); V10: IV-C04, IV-A05, IV-A08 (+1); V12: IV-C03, IV-A10, IV-T10b; V13: IV-C09; V14: IV-T09, IV-T12, IV-T13 (V1 nearest spot, V2 tie upper, V3 call-only IV, V4 linear-IV interpolation, V5 label dropped, V6 american_itm dropped, V7 extrapolation, V8 exact-30d ignored, V9 one-right strikes eligible, V10 quote gates ignored, V12 unknown style as American, V13 nearest among both-right strikes only, V14 ineligible expiries skipped).

## Pending-design tags
Tags name the design answer a row still depends on; they do not un-gate a row. pending:req3 on OC6 value, low_quote_coverage, no_window_spread rows; pending:req10 on OC5 value, zero_displayed_size and missing_size rows (OC5-11a/b/c explicit); pending:req11 on stale, not_consolidated, ATM, 30-day rows; pending:req12 on American, unknown-style and contract-IV rows; pending:req1 locked rows; pending:req2 bid-0 rows.

## Retired and deferred
Retired ids (not reused): IV-A11, IV-T15, OC5-17b. Deferred cross cases 35-36 (adapter work, not authored).

## Remaining assumptions to confirm (small)
A1 Gate order is ruled: no_quote, excluded_condition, not_consolidated (OC5 only), validity, stale, coverage; size reasons (zero_displayed_size, missing_size) after stale. Combined rows: OC5-G1..G7, OC6-G1, G2, OC5-B1, OC6-B9 (mutants X9, X10, X13, X14 catch swaps).
A2 The previous-session test (no carry across the open) uses event time; known_at-based interval start (D5) applies inside the window only.
A3 Forward strings are floats formatted to 8dp; compare within 1e-6, never byte-compare across platforms.

## Independence and files read
No implementation, existing fixture or developer note was read. Nothing under option-features packages, tests, qualification, tools, docs/r25, docs/r26 or docs/r26-variants was opened, listed or searched. Files read, all on the allowed list:
- watchyourlist-gap: PO_RELEASE_PLAN_V3.md, DESIGN_SESSION_REQUESTS.md, r28-design/OC5_OC6_FIXTURE_SPEC.md, r28-design/PO_R28_DESIGN_RULINGS.md, r28-design/R28A_B_CAPABILITY_MATRIX.md (whole files).
- watchyourlist-design docs/features/option-contracts.md lines 14-93 (slightly wider than 2.2, 2.3, 2.7) and 125-132, plus a heading grep.
- docs/features/volatility-radar.md: grep matches only (V2, V4 rows, 2.9 lines).
- docs/audits/workers-vs-conditions.md: grep matches for OC4-OC6 only (legacy statement).
- watchyourlist-design CLAUDE.md and AGENTS.md were attached by the harness. The PO rulings above arrived as an agent message.

## Regeneration
python gen_m1_oc.py --out <dir>; python gen_m1_iv.py --out <dir>. Each runs its mutation report and an independent self-check (second implementation; IV self-check prices from the stated sigma and inverts quotes with a separate bisection; IV-A17 also checks put-call parity). Two runs give identical hashes. MANIFEST.sha256 lists every file.
