# Design row to repository id map (P1, 0.2.0a1)

Status: library-owned, published with P1. Provenance: synthetic fixtures only; "match" means the design rule is implemented and passes the independently authored P1 rows, not that it is validated on recorded data. Label for any release note quoting this map: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12.

Source rows: the design option-contracts (OC), gates (G) and flow (F) rows as audited in the parity check and the PO reconciliation (2026-10-29). Repository ids are the ids the code actually ships: R25 outputs (`option_features.evaluate`), the P1 modules (`option_features.quotes`, `.windows`, `.shares`) and the `variants1` operations (family called "span" where the design says F4 for large prints; the two are unrelated).

Classes: **match** (design rule implemented and fixture-tested), **partial** (a primitive exists, the design needs more, or only part of the row is covered), **missing** (nothing ships). A "since" of R25/R26 means unchanged by P1.

Wire note: the P1 modules are pure functions beside the R25 evaluator. They are not yet operations of the frozen `variants1` wire schema (adding a sign kind, a window end or a share output to that schema is a candidate bump with fixtures that live outside this repository; see DECISIONS.md, P1 entry). The variants1 flow metrics (`bullish`, `bearish`, `ask`, `bid`, `premium`, `call`, `put`, joint shares) keep their legacy semantics and bytes.

## Reason vocabulary (design reason to repository status/reason)

| Design reason | Repository (spread outputs) | P1 sign / aggregate / coverage modules |
|---|---|---|
| no_quote | missing_input / missing_quote (a quote with neither bid nor ask is represented as no quote record) | `no_quote` (also a quote after the trade) |
| invalid_quote | invalid_input / negative_quote, invalid_input / nonpositive_bid (new), ineligible_input / one_sided_quote | `invalid_quote` |
| crossed_market | invalid_input / crossed_quote | `crossed_market` |
| locked_market | invalid_input / locked_market (new) | not a gate for signing |
| stale_quote | ineligible_input / stale_quote (limit = request eligibility max_quote_age_ns) | `stale_quote` (max_quote_age_ns, default 3 s) |
| low_quote_coverage | not in the R25 evaluator | `windows.quote_count_coverage`, blocks OC6 only |
| missing_reference | not in the R25 evaluator | `shares.*` measure with no referenced print |
| inside_spread, ambiguous_touch | not applicable | unclassified reasons of `sign_trade(inside_spread="unknown")` |
| no_classified_premium | not applicable | `sign_aggregate` status unavailable (shares null, PO-P1-01) |

Gate precedence (PO-P1-02): no_quote, invalid_quote, crossed_market, locked_market, stale_quote. For signing, locked does not block and the order is no_quote, invalid_quote, crossed_market, stale_quote, then the touch rule.

## Option contracts and gates

| Design id | Design meaning (short) | Repository id | Mode and parameters | Class | Since |
|---|---|---|---|---|---|
| OC1 | Days to expiry | `contract.dte` | civil binding in the request | match | R25 |
| OC2 | Strike over price | `contract.moneyness` | spot staleness from eligibility | match | R25 |
| OC3 | Modeled absolute delta | `greeks.delta` | supplied sigma, rate, carry; European | match | R25 |
| OC4 | Spread in bps of midpoint | `liquidity.spread_bps` (also `liquidity.spread`, `liquidity.midpoint`) | gate above; stale limit = eligibility max_quote_age_ns | match | P1 (bytes change for bid <= 0 and locked) |
| OC5 | Bid/ask size imbalance | `option_features.imbalance.oc5`, `oc5_many` (inputs: `quotehist.QuoteUpdate`, `QuoteSize` keyed by quote revision) | (bid_size - ask_size) / (bid_size + ask_size) of the latest causal quote; |imbalance| >= `imbalance_threshold` (0.60, inclusive) fires bid or ask; gates no_quote, excluded_condition, not_consolidated, invalid_quote, crossed_market, stale_quote (event time, 10 s, exactly 10 s fresh), missing_size, zero_displayed_size; locked evaluates; low OC6 coverage never blocks | match (library modules only; not on the wire) | M1 |
| OC6 | Spread against own 5-minute average | `option_features.spreadwin.oc6`, `oc6_many` | current spread bps of midpoint over the time-weighted average of the closed window [T-300 s, T] (carry-in at the window start, current quote weighted to T, intervals start at known_at, valid regular quotes only, denominator = valid weighted time, clipped at session open); ratio <= 0.75 narrower, >= 1.50 wider (inclusive); gates no_quote, excluded_condition, invalid_quote, crossed_market, locked_market, stale_quote, low_quote_coverage (G5, min 5), no_window_spread | match (library modules only; not on the wire) | M1 |
| G1 | Invalid quote gate (bid <= 0) | `liquidity.spread_bps` / `.spread` / `.midpoint`: nonpositive_bid, negative_quote, one_sided_quote | modeled values (IV) still accept a bid of 0 until M1 | partial | P1 (spread) |
| G2 | Locked market blocks spread and modeled values | same outputs: locked_market | signing proceeds (request 1, interim option A); IV unchanged until M1 | partial | P1 (spread) |
| G3 | Crossed market withheld | crossed_quote (spread, IV) | | match | R25 |
| G4 | Stale quote | stale_quote | limit is supplied: eligibility.max_quote_age_ns (spread), `max_quote_age_ns` (signing, default 3 s) | partial | R25 |
| G5 | Fewer than 5 regular updates in 5 minutes | `option_features.windows.quote_count_coverage`, `QuoteUpdateIndex` | window_ns 300 s, closed [T-W, T], min_regular_updates 5, excluded-condition updates never count; blocks OC6 only | match (gate rule; blocks OC6 in `spreadwin.oc6`, not OC5) | P1, M1 |
| G5 extra | Slot ratio of declared sampling plan | `quality.quote_coverage` | unchanged; not the design rule | extra (renamed "slot coverage") | R25 |
| G6 | Unavailable with reason | status and reason on every result | | match | R25 |
| G7 | Baseline unavailable | variants1 `baseline` (empty_baseline, insufficient_history) | minimum samples is a request field | partial | R26 |
| G8 | Non-standard contract | `contract.multiplier`, variants1 nonstandard_definition; `windows.window_premium` counts multiplier != 100 prints as excluded_nonstandard_count | classification supplied, no root test | partial | R26/P1 |

## Flow

| Design id | Design meaning (short) | Repository id | Mode and parameters | Class | Since |
|---|---|---|---|---|---|
| F1 | 1-minute premium rate vs 15-minute | variants1 `directional` b64-rolling-BD1 | two horizons composed by the consumer | partial | R26 |
| F2a, F2b, F2c | Premium, contracts or print rate in top X% of the last 20 sessions | `option_features.flowrank.f2_rank` (metric `premium`, `contracts`, `prints`; history `flowstore.HistoryStore`, window values from `flowgrid.window_totals`) | intraday form: 60 s grid values of 20 complete prior sessions after the first W/60 points; end-of-day form: 20 session totals; `upper_share = count(history >= x)/n`, fires at <= X/100 (X 5), `rank_le` also returned; gates insufficient_history, session_not_complete, insufficient_window; delayed tag gives invalid_input delayed_feed_tag intraday; no crossing form | match (library modules only; not on the wire) | M2 |
| F2d | Average of the F2a-c percentiles | `option_features.flowrank.f2d_combine` (`flow_pack` for one series) | percentile = 1 - upper_share, higher is more unusual, exact average, parts always shown, `fired` null (DR-M2-1), reason of the first unavailable part | match (library modules only; not on the wire) | M2 |
| F3 | Premium in window ending now, calls/puts | `option_features.windows.window_premium`, `WindowIndex` | `window_end_ns` = evaluation time (explicit end, closed [end-W, end]); `window_end_ns=None` is the legacy last-print anchor; call/put split; multiplier != 100 excluded and counted | match (library modules only; not on the wire) | P1 |
| F3 legacy | Rolling window ending at the last positive print | variants1 `directional` b64-rolling-BD1 | unchanged | (legacy mode) | R26 |
| F4 (design: large prints) | N prints of $100k or more | variants1 `premium` rows | no count, no threshold (the repository family called F4 is "span") | partial | R26 |
| F5 | At least X% of premium expiring within 2 days | `option_features.shares.single_reference_shares` -> `short_dte` | needs civil date and expiry only; 0 <= dte <= short_dte_max_days; total-premium denominator; coverage; `short_min_share` inclusive; label "at least X% of total eligible premium" | match (library modules only; not on the wire) | P1 |
| F6 | Out-of-the-money share | same -> `otm` | needs spot only; strict OTM (call K > S, put K < S); `otm_min_share` | match (library modules only; not on the wire) | P1 |
| F5/F6 joint | Both references | same -> `joint_short_dte`, `joint_otm`; `shares.joint_amounts` | kept; legacy variants1 joint op unchanged | match (library modules only; not on the wire) | P1 (legacy R26) |
| F7 | 60% in one strike or expiry | variants1 `directional` i64 per-strike/expiry totals | no share, no threshold | partial | R26 |
| F8 | Share of universe premium | none | | missing | |
| F9 | Repeated or multi-venue prints within a second | variants1 `parent_groups` | side-split lanes, exclusive first-unassigned windows (design wording to follow, request 7) | partial | R26 |
| F10, F20 | Contracts (window) or session total vs baseline | `option_features.flowrank.f10_baseline`, `f20_baseline` | both `median_ratio` and `mean_ratio` output; consumer default F10 median, F20 mean; median = mean of the two middle values; zero statistic gives zero_denominator for that ratio; fires at ratio >= N (2); legacy variants1 `baseline_consumer` and `baseline` unchanged | match (library modules only; not on the wire) | M2 |
| F11, F12 | Price response, episodes | none | | missing | |
| F13 | Call-ask plus put-bid premium | `option_features.quotes.sign_aggregate` -> `call_ask_plus_put_bid_premium` | `inside_spread="unknown"` (touch policy), epsilon, `max_quote_age_ns` 3 s; label "ask-side proxy" / "bid-side proxy" | match (library modules only; not on the wire) | P1 |
| F14 | Put-ask plus call-bid premium | same -> `put_ask_plus_call_bid_premium` | as F13 | match (library modules only; not on the wire) | P1 |
| F15 | Ask-side premium | same -> `ask_premium`, `ask_share_of_classified` | as F13 | match (library modules only; not on the wire) | P1 |
| F16 | Bid-side premium | same -> `bid_premium`, `bid_share_of_classified` | as F13 | match (library modules only; not on the wire) | P1 |
| F13-F16 legacy | Midpoint-split sides | variants1 `directional` metrics bullish, bearish, ask, bid; `quotes.sign_trade(inside_spread="split")` | the default; unchanged | (legacy mode) | R26 |
| F13-F16 unclassified | Premium inside the spread | `sign_aggregate` -> `unclassified_premium`, `unclassified_share_of_total` | inside_spread, ambiguous_touch and every unsignable trade; excluded from both shares | match (library modules only; not on the wire) | P1 |
| Tick fallback | Optional tick rule | none | later, optional | missing | |
| Crossing form | Crossing form for F2a-c | none | engine concern | missing | |
| F17 | One contract, 5 minutes, at least $X | variants1 `span_at_anchor` | anchors supplied | partial | R26 |
| F18 | Put share of volume | none | | missing | |
| F19 | Put/call volume ratio as percentile of 20 sessions | `option_features.flowrank.f19_percentile` | end of day only; prior sessions with zero call volume skipped, fewer than 20 usable gives insufficient_history; fires at upper_share <= X/100 (X 5) | match (library modules only; not on the wire) | M2 |

## Volatility, positioning, presets

V1-V22 (V2 and V20 partial through `volatility.implied_volatility` and the Greeks, the rest missing), PO1-PO19 and the scanner presets are unchanged by P1: missing except where noted. M1 adds OC5 and OC6 (this table, story A), ATM IV and 30-day IV (later stories).

## M1 story B: contract IV, ATM IV, 30-day IV (`option_features.chainiv`; library module, not on the wire)

| Design id | Design meaning (short) | Repository id | Mode and parameters | Class | Since |
|---|---|---|---|---|---|
| V-contract IV | Per-contract IV with American-style label | `IVChain.contract_iv` | D12 ACT/365, midpoint, continuous r and q; European `exact-model`; American modeled for nearest-to-forward and OTM only (`approximate: European model on an American-style contract`), else `american_itm`; unknown style `style_unknown`; gates no_quote, excluded_condition, invalid_quote, crossed_market, locked_market, stale_quote | match (synthetic rows) | M1 B |
| V-ATM IV | Chain ATM IV | `IVChain.atm_iv`, `atm_iv_all` | strike nearest F = S exp((r-q)T) among strikes eligible for both rights, ties lower; mean of call and put IV; strike, forward, both IVs returned; reason `no_atm_strike` | match (synthetic rows) | M1 B |
| V-30d IV | 30-day constant-maturity IV | `IVChain.iv_30d` | exact 30-day expiry as is; else linear in total variance between the bracketing listed expiries; no extrapolation; reason `no_bracketing_expiry` (a bracketing expiry without an ATM strike); exact expiry without ATM strike gives `no_atm_strike` | match (synthetic rows) | M1 B |

## Shipped ids with no design row (extra)

`chain.activity` (0-100 score; design excludes a 0-100 score, ruling requested), `pricing.price`, `greeks.signed_delta`, `greeks.rho`, `quality.quote_coverage`, variants1 `net`, `classified`, `unknown`, raw counts and the checkpoint/restore family. P1 adds the helper outputs `liquidity.spread` and `liquidity.midpoint` (support for OC4) and the pure modules listed above.

## Labels and wording

Consumers label the P1 sides "ask-side proxy" and "bid-side proxy" (constants `quotes.ASK_LABEL`, `quotes.BID_LABEL`). The shipped ids keep their historical names (bullish, bearish, ask, bid); no direction wording is added by P1. The share label is the fixed phrase "at least X% of total eligible premium".
