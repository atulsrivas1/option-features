# Feature status (single live tracker)

> mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Owner of this file: the Auditor on creation (PO-directed, M2 F-row re-audit); afterwards every release PR updates it (rule in docs/RELEASE_NOTE_TEMPLATE.md). As of 2026-10-30 against origin/main f5580cc (PR 99). Merged and open PRs are in the machine-readable lines below; F2d stays partial (DR-M2-1).

How the statuses were checked: rows were derived from the design text (option-contracts, flow, volatility-radar, positioning), the baseline PARITY_CHECK (81 design rows) and PO_PARITY_RECONCILIATION, and then verified against the packages source, not the documents: exported functions were listed per module on main and on the PR 80 head (printtape, m2prints, episodes, imbalance, spreadwin, chainiv, windows, shares, quotes, quotehist; flowrank, flowstore, flowgrid, flowresult), fixture rows were recounted by loading the files (M2 correctness 570 rows in 14 files, additions 298 rows in 10 files (PR 82, 84, 90, 91 and 96; loaded and counted on main, MANIFEST_ADDITIONS.sha256 lists 31 files and was verified with sha256sum), P1 121, M1 OC 110, M1 IV 41 plus 28 extra), and the M2 test suites were run (tests/m2 on origin/main d3567af: 431 collected, 430 passed, 1 skipped (the PR 79 merge message says 431, the collected total); 817 passed, 1 skipped on the PR 80 head). Performance figures are copied from the records named in each row, not re-measured by the Auditor.

Legend. Status: done (built and passing its independently authored rows), partial (part of the row is built or a gate is open), pending (nothing built), dropped. Evidence applies to every row: synthetic fixtures only; Windows x64, CPython 3.12 only; not validated on recorded data. The Evidence column adds the surface (lib: library module only, not on the wire; wire: operation of the frozen evaluator or variants1 schema; doc) and whether an independent review took place. Interim design rulings (requests 1-3, 6, 8 and the M2 rulings Q1-Q18, AMB-1..19, GRID) are pending design ratification; a changed answer regenerates the dependent fixtures, so every row that depends on one lists it under pending reasons. "Done" never means wired: no P1, M1 or M2 output is on the wire (wire exposure is a candidate16 item).

## 1. Summary

Counts cover the five feature tables in section 3 (113 rows: 81 design rows plus 32 release items). Performance gates, accepted performance work and extras are tracked in their own sections and are not counted here.

By status:

| Status | Design rows (81) | All rows (113) |
|---|---|---|
| done | 28 | 40 |
| partial | 9 | 9 |
| pending | 44 | 63 |
| dropped | 0 | 1 |
| total | 81 | 113 |

Done and merged 40 (every done row is on main; PR 79 and PR 80 are merged). Partial rows are listed in the tables.

Merged PRs: 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 102

Open PRs: 100, 101

Additions rows: 298; files: 10; manifest files: 31

Done rows on the wire: 7; library-only: 31 (computed from the Evidence column; the remaining surface value is doc).

Design rows counted by the baseline audit: 81 (OC 6, G 8, presets 1, F 25 including tick fallback and crossing form, V 22, PO 19). Baseline classes were 5 match, 12 differs, 13 partial, 51 missing, which is not directly comparable: this tracker folds the baseline DIFFERS class into done or partial after the P1 changes.

By release (the release that delivers or is assigned the row; R25 and R26 are the pre-P1 releases):

| Release | done | partial | pending | dropped | total |
|---|---|---|---|---|---|
| R25 | 5 | 2 | 0 | 0 | 7 |
| R26 | 0 | 3 | 0 | 0 | 3 |
| P1 | 11 | 2 | 0 | 0 | 13 |
| M1 | 6 | 1 | 0 | 0 | 7 |
| M2 | 18 | 1 | 2 | 0 | 21 |
| M3a | 0 | 0 | 11 | 0 | 11 |
| M3b | 0 | 0 | 6 | 0 | 6 |
| M3c | 0 | 0 | 7 | 0 | 7 |
| M4a | 0 | 0 | 8 | 0 | 8 |
| M4b | 0 | 0 | 13 | 0 | 13 |
| M5a | 0 | 0 | 2 | 0 | 2 |
| M5b | 0 | 0 | 3 | 0 | 3 |
| RQ | 0 | 0 | 7 | 1 | 8 |
| later | 0 | 0 | 4 | 0 | 4 |
| all | 40 | 9 | 63 | 1 | 113 |

Process ruling (owner approved, docs/decisions/2026-10-30-process-and-m3-m5-split.md): M3, M4 and M5 are split into M3a, M3b, M3c, M4a, M4b, M5a, M5b. The V3 plan names the original M3, M4 and M5 only; the split of V-rows and PO-rows across the sub-releases beyond what the ruling lists (V1, V3-V10 to M3a; V11-V15 to M3b; V16-V22 to M3c) is marked proposed in the pending reasons.

## 2. Release order (PO release plan V3, 2026-10-29) and what each pending release contains

Every release carries the label sentence verbatim, stays PRERELEASE (D7), makes no recorded-data claim, and contains no vendor code or network work before RQ. Each of M2, M3a-c, M4a-b and M5a-b gets its own capability matrix and independently authored fixtures before code (V3 section 3 and 4).

| Release | State | Contents | Entry gate |
|---|---|---|---|
| R27 | done (candidate15, PR 59) | Frozen R26 variants1 candidate and release notes | - |
| P1 | done, PO accepted 2026-10-29 (PR 63, 0.2.0a1) | OC4/G1, G2 spread, F3 window end, F5/F6 single reference, F13-F16 touch policy, G5, naming map | R27 closed |
| M1 | done, closed 2026-10-29 (docs/M1_CLOSE.md) | OC5, OC6, chain ATM IV, 30-day IV, American labels, solver Stages 0-2, opt-in runner | P1 accepted, design requests 1, 2, 7 (interim rulings used) |
| M2 | in progress: stories A and B merged (PR 79, PR 80); Result type alignment merged (PR 88); F-row re-audit merged (PR 85); docs PR 89, 92, 94, 95 merged (print type, ordering and field rules); remaining M2 items: runner integration, performance follow-up, benchmark regeneration (PR 87 open); check_prints type-first merged (PR 93) | F1, F2a-d, F4, F7, F10, F20, F12, F17, F18, F19, history store; then re-audit every F row | M1 accepted; matrix and budgets (PR 75, 76, 81, 83), fixtures (PR 78, 82, 84), M2-G0 (PR 77) all merged |
| M3a | pending | Surface, term structure and skew builder (V1, V3-V10) with history reuse from the M2 store for the percentile-of-history and change-since-prior-session rows (V1, V3, V4, V7, V9, V10) | M2 accepted and the M2 store merged (PR 80); own matrix; synthetic surface generator with known smile and term values |
| M3b | pending | Realized-volatility join, daily-bar based, without history reuse (V11-V15) | M3a accepted; own matrix; daily-bar generator |
| M3c | pending | Frame builder without presets (V16-V22, proposed assignments; V20 aggregate, V21, V22) | M3b accepted; own matrix |
| M4a | pending | Open-interest outputs (PO9, PO12-PO14, PO17-PO19; proposed assignments) | M3c accepted; own matrix; chain generator with synthetic open interest |
| M4b | pending | Exposure outputs and dealer-sign convention, labelled modeled (PO1-PO8, PO10, PO11, PO15, PO16; proposed assignments) | M4a accepted; own matrix; hand-computable exposure totals |
| M5a | pending | Shadow, list-eligible scanner presets (D6) | M4b accepted; own matrix; universe generator with planted matches per preset; scanner authorization flag stays false |
| M5b | pending | Equity-side join, including F8 and F11 | M5a accepted; own matrix |
| RQ | pending, last | Vendor feed adapter, display-rights rules, recorded data (local), B1-B12 on real sizes, Linux x64 and Windows x64 evidence, D8 sources wired, divergence review; first release allowed to make recorded-data claims | M5b accepted, all earlier labels clean, owner items supplied (feed credential, first download permission and spend ceiling, display-rights table, Linux environment) |

Dropped: R28a as a separate release (adapter work moves wholly into RQ). Entry gates for M3a to M5b beyond "previous release accepted" and "own matrix and fixtures first" are not ruled in V3; they are listed here as the standing rule, not as new rulings. After M5b the RQ entry gate applies: all earlier labels clean and the owner items supplied.

## 3. Feature tables

### Option contracts and gates (design rows OC1-OC6, G1-G8, presets)

| Id | Name | Status | Release | PRs | Evidence | Pending reasons |
|---|---|---|---|---|---|---|
| OC1 | Days to expiry | done | R25 | R25 release | wire; independent review: yes | - |
| OC2 | Strike over price (moneyness) | done | R25 | R25 release | wire; independent review: yes | - |
| OC3 | Modeled absolute delta | done | R25 | R25 release | wire; independent review: yes | - |
| OC4 | Spread in bps of midpoint | done | P1 | 63 (fixtures 62, accept 64) | wire; independent review: yes | Request 1 and 2 ratification (interim A); R25 result bytes changed for bid <= 0 and locked |
| OC5 | Bid/ask size imbalance | done | M1 | 69 (fixtures 62) | lib; independent review: yes | Wire exposure (candidate16); request 10 and 11 ratification |
| OC6 | Spread against own 5-minute average | done | M1 | 69 (fixtures 62) | lib; independent review: yes | Wire exposure (candidate16); request 3 ratification |
| G1 | Invalid quote gate (bid <= 0) | partial | P1 | 63, 68 | wire (spread) + lib; independent review: yes | R25 evaluate IV outputs still accept bid = 0 (quote_faults unchanged; only the new chainiv gates it); request 2 ratification |
| G2 | Locked market blocks spread and modeled values | partial | P1 | 63, 68 | wire (spread) + lib; independent review: yes | R25 evaluate IV outputs do not gate locked; signing proceeds by interim ruling; request 1 ratification |
| G3 | Crossed market withheld | done | R25 | R25 release | wire; independent review: yes | - |
| G4 | Stale quote | partial | R25 | R25 release, 63, 68, 69 | wire + lib; independent review: yes | No single design limit: eligibility field (spread), 3 s (signing), 10 s (OC5, OC6, chainiv); design 10 s vs 5 s open (OC section 12); request 11 ratification |
| G5 | Fewer than 5 regular updates in 5 minutes | done | P1 | 63, 69 | lib; independent review: yes | Request 3 ratification; wire exposure (candidate16); blocks OC6 only |
| G6 | Unavailable with reason | done | R25 | R25 release | wire; independent review: yes | - |
| G7 | Activity baseline unavailable | partial | R26 | R26 release | wire; independent review: yes | variants1 minimum samples is a request field, no default 20; M2 modules use K = 20 with insufficient_history (PR 79, PR 80); request 5 ratification |
| G8 | Non-standard contract | partial | R26 | R26 release, 63 | wire + lib; independent review: yes | Classification is supplied, no computed root test; windows excludes and counts multiplier != 100 prints |
| Presets | option_v1 scanner presets (12 watchlists, 14 volatility presets) | pending | M5a | - | - | Shadow, list-eligible only (D6); no scanner code in any repo |

### Flow (design rows F1-F20, tick fallback, crossing form)

| Id | Name | Status | Release | PRs | Evidence | Pending reasons |
|---|---|---|---|---|---|---|
| F1 | 1-minute premium rate at least 3x the 15-minute rate | done | M2 | 79 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 9f6617b; PO accepted, PR 79 merge message) | Wire exposure (candidate16); Q7 ratification (no floor, insufficient_window) |
| F2a | Premium in top X% of the last 20 sessions | done | M2 | 80 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 0954d21; PO accepted, PR 80 merge message) | Q1-Q3 ratification (time-of-day alignment is a design gap, flow.md 2.7); no crossing form; wire exposure |
| F2b | Contracts in top X% of the last 20 sessions | done | M2 | 80 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 0954d21; PO accepted, PR 80 merge message) | As F2a |
| F2c | Print rate in top X% of the last 20 sessions | done | M2 | 80 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 0954d21; PO accepted, PR 80 merge message) | As F2a; Q18 rate definition (interim) |
| F2d | Average of the F2a-c percentiles | partial | M2 | 80 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 0954d21; PO accepted, PR 80 merge message) | DR-M2-1: design must give the F2d fire rule and default X, `fired` is null until then |
| F3 | Premium in window ending now, calls and puts | done | P1 | 63 | lib; independent review: yes | Wire exposure (candidate16) |
| F4 | N prints of $100k or more | done | M2 | 79 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 9f6617b; PO accepted, PR 79 merge message) | Wire exposure; Q8 ratification (N = 1 and $100k are placeholders) |
| F5 | At least X% of premium expiring within 2 days | done | P1 | 63 | lib; independent review: yes | Request 6 ratification; wire exposure |
| F6 | Out-of-the-money share of premium | done | P1 | 63 | lib; independent review: yes | Request 6 ratification; wire exposure |
| F7 | 60% of premium in one strike or expiry | done | M2 | 79 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 9f6617b; PO accepted, PR 79 merge message) | Wire exposure; Q10 ratification; performance candidate (F7 at 3x window overlap) |
| F8 | Share of universe premium | pending | M5b | - | - | Needs a universe: equity-side join (M5b); the matrix proposes the deferral, V3 text does not name the release |
| F9 | Repeated or multi-venue prints within a second | partial | R26 | R26 release | wire; independent review: yes | Request 7 (grouping wording); side-split lanes, exclusive first-unassigned windows as shipped |
| F10 | Contracts unusual against baseline | done | M2 | 80 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 0954d21; PO accepted, PR 80 merge message) | request 9 and Q4 ratification (median vs mean default); wire exposure |
| F11 | Price response | pending | M5b | - | - | Needs an underlying price series (equity-side join); proposed M5b, not in V3 text |
| F12 | N unusual episodes today | done | M2 | 79 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 9f6617b; PO accepted, PR 79 merge message) | Wire exposure; Q11 ratification; no cross-session state |
| F13 | Call-ask plus put-bid premium | done | P1 | 63 | lib; independent review: yes | Request 8 ratification; wire exposure; legacy midpoint-split mode stays on the wire (R26) |
| F14 | Put-ask plus call-bid premium | done | P1 | 63 | lib; independent review: yes | As F13 |
| F15 | Ask-side premium | done | P1 | 63 | lib; independent review: yes | As F13 |
| F16 | Bid-side premium | done | P1 | 63 | lib; independent review: yes | As F13 |
| F17 | One contract, 5 minutes, at least $X | done | M2 | 79 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 9f6617b; PO accepted, PR 79 merge message) | Wire exposure; Q9 ratification; performance candidate (sparse reads per cutoff) |
| F18 | Put share of option volume | done | M2 | 79 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 9f6617b; PO accepted, PR 79 merge message) | Wire exposure; Q12 ratification (thresholds not defaulted) |
| F19 | Put/call volume ratio percentile of 20 sessions | done | M2 | 80 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 0954d21; PO accepted, PR 80 merge message) | Q13 ratification; wire exposure |
| F20 | Session contracts or premium at least N x 20-session average | done | M2 | 80 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 0954d21; PO accepted, PR 80 merge message) | request 9 and Q4 ratification; wire exposure |
| Tick fallback | Optional tick-rule fallback for F13-F16 | pending | later | - | - | Optional; design flow.md 2.8 keeps it apart; no release assigned |
| Crossing form | Crossing form for F2a-c | pending | later | - | - | Engine concern: needs prior-evaluation state; deferred in M2 (matrix section 7) |

### Volatility radar (design rows V1-V22)

| Id | Name | Status | Release | PRs | Evidence | Pending reasons |
|---|---|---|---|---|---|---|
| V1 | 30-day IV in the top X% of its own history | pending | M3a | - | - | Needs IV history (M2 store reuse) and a surface; M3a; history reuse from the M2 store (PR 80 merged) |
| V2 | ATM IV at least or at most X points | partial | M1 | 68, 70 | lib; independent review: yes | Chain ATM IV built (annual decimal; library module, not on the wire); no points unit or threshold form; request 11 ratification |
| V3 | ATM IV in top X% of the same minute in earlier sessions | pending | M3a | - | - | M3a (history reuse) |
| V4 | IV change from the prior reading | pending | M3a | - | - | M3a; history reuse from the M2 store (PR 80 merged) |
| V5 | Longer tenor above or below shorter (term structure) | pending | M3a | - | - | M3a (term structure) |
| V6 | Second expiry above or below the nearest | pending | M3a | - | - | M3a |
| V7 | Term gap or slope change since prior session | pending | M3a | - | - | M3a; history reuse from the M2 store (PR 80 merged) |
| V8 | 25-delta put-side over call-side volatility | pending | M3a | - | - | M3a (skew) |
| V9 | 25-delta skew in top X% of own history | pending | M3a | - | - | M3a; history reuse from the M2 store (PR 80 merged) |
| V10 | 25-delta skew change or sign change | pending | M3a | - | - | M3a; history reuse from the M2 store (PR 80 merged) |
| V11 | Wings above or below the smile centre | pending | M3b | - | - | M3b |
| V12 | 30-day IV above or below 20-day realized | pending | M3b | - | - | M3b (realized-volatility join, daily bars) |
| V13 | Implied divided by realized volatility | pending | M3b | - | - | M3b |
| V14 | Implied-minus-realized gap in top X% of history | pending | M3b | - | - | M3b (252-session form needs the 52-week history generator) |
| V15 | Average volatility percentile of V1, V9, V14 | pending | M3b | - | - | M3b |
| V16 | Expected move over 5, 15 or 30 minutes | pending | M3c | - | - | Release not named in V3; proposed M3c |
| V17 | Expected move change | pending | M3c | - | - | Release not named in V3; proposed M3c |
| V18 | Price move reached X% of the expected move | pending | M3c | - | - | Release not named in V3; proposed M3c |
| V19 | Move since anchor against scale from prior 20 sessions | pending | M3c | - | - | Release not named in V3; proposed M3c |
| V20 | Gamma, vega, theta activity unusual against baseline | partial | R25 | R25 release | wire; independent review: yes | Per-contract greeks exist (R25); activity-weighted aggregate and baseline pending; release not named in V3 (proposed M3c) |
| V21 | Put-side over call-side distance from ATM, 25 delta | pending | M3c | - | - | Derived from V8; release not named in V3; proposed M3c |
| V22 | 30-day IV 52-week range position | pending | M3c | - | - | M3c (52-week history generator) |

### Positioning (design rows PO1-PO19)

| Id | Name | Status | Release | PRs | Evidence | Pending reasons |
|---|---|---|---|---|---|---|
| PO1 | Largest-exposure strike across expiries | pending | M4b | - | - | M4b: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO2 | Price within X bps of an exposure level | pending | M4b | - | - | M4b: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO3 | Price crosses a named level | pending | M4b | - | - | M4b: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO4 | Exposure at a strike and expiry positive or negative | pending | M4b | - | - | M4b: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO5 | Exposure sign change since last update | pending | M4b | - | - | M4b: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO6 | Total modeled exposure sign, call and put parts | pending | M4b | - | - | M4b: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO7 | Price near or crossing the gamma-flip level | pending | M4b | - | - | M4b: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO8 | Price near the largest call-side or put-side exposure | pending | M4b | - | - | M4b: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO9 | Price near the max-pain strike | pending | M4a | - | - | M4a: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO10 | Share of exposure above and below price | pending | M4b | - | - | M4b: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO11 | Exposure concentration index | pending | M4b | - | - | M4b: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO12 | Open interest at a strike or in total | pending | M4a | - | - | M4a: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO13 | Open interest change above own history | pending | M4a | - | - | M4a: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO14 | Open interest concentration by strike or expiry | pending | M4a | - | - | M4a: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO15 | Exposure change split into open-interest and repricing parts | pending | M4b | - | - | M4b: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO16 | Expiry scope N days on level conditions | pending | M4b | - | - | M4b: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO17 | Max-pain strike for a chosen expiry, with width | pending | M4a | - | - | M4a: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO18 | Put/call open interest ratio and net change | pending | M4a | - | - | M4a: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |
| PO19 | Open-interest share by expiry bucket | pending | M4a | - | - | M4a: needs an open-interest field and an exposure model (none exists); dealer-sign convention labelled modeled |

### Release items beyond the design rows (P1, M1, M2, M3a-c, M4a-b, M5a-b, RQ, later)

| Id | Name | Status | Release | PRs | Evidence | Pending reasons |
|---|---|---|---|---|---|---|
| P1-1 | Version bump 0.2.0a1 and sibling pins | done | P1 | 63, 66 | wire; independent review: yes | Tag and wheel rebuild still open (HANDOFF) |
| P1-2 | Library-owned design-to-repository map (FLOW_NAMING_MAP) | done | P1 | 63, 85 (updated to M2) | doc; independent review: yes | - |
| M1-1 | QuoteSize record (additive, keyed by quote revision) | done | M1 | 69 | lib; independent review: yes | Wire exposure (candidate16) |
| M1-2 | Per-contract IV with American-style labels | done | M1 | 68, 70 | lib; independent review: yes | Request 12 ratification; wire exposure |
| M1-3 | Chain ATM IV | done | M1 | 68, 70 | lib; independent review: yes | Request 11 ratification; wire exposure |
| M1-4 | 30-day constant-maturity IV | done | M1 | 68, 70 | lib; independent review: yes | Request 11 ratification; wire exposure |
| M2-1 | Shared columnar print tape (printtape) | done | M2 | 79 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 9f6617b; PO accepted, PR 79 merge message) | - |
| M2-2 | History store: retention ring, sorted views, canonical text, snapshots (flowstore) | done | M2 | 80 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 0954d21; PO accepted, PR 80 merge message) | store byte cap above 512 MB reported, not enforced |
| M2-3 | Trade-to-grid builder, Result type, canonical lines (flowgrid, flowresult) | done | M2 | 80 (fixtures 78, 82, 84) | lib; independent review: yes (Tester approve at 0954d21; PO accepted, PR 80 merge message) | Tester re-run |
| M2-4 | M2-G0 full-output B6 measurement and runner full unit | done | M2 | 77 | lib; independent review: partial (Tester conditions applied; Tester re-run pending) | Tester re-run |
| M2-5 | Align story B (printtape, m2prints, episodes) to story A Result type | done | M2 | 88, 93 | lib; independent review: yes (merged after PO review; Developer states outputs identical on 392 rows; Tester review per PR 88 body) | - |
| M2-6 | Runner integration of M2 families (worker scaling, gc.freeze after store load, mmap attach) | pending | M2 | - | - | Not done: story B notes runner integration not done; the runner rules are ruled, not exercised |
| M2-7 | F-row re-audit and single live tracker (this document) | done | M2 | 85 | doc; independent review: yes (independent docs review, approve-with-conditions applied) | - |
| M2-8 | Performance follow-up story (F7 3x overlap, F17 sparse reads) | pending | M2 | - | - | Scheduled after the F-row re-audit (PO ruling 2026-10-30) |
| X-1 | Wire exposure of the P1, M1 and M2 pure modules (candidate16) | pending | later | - | - | Candidate bump with fixtures outside this repository; not tied to a numbered release |
| X-2 | Release tag and wheel rebuild | pending | later | - | - | HANDOFF open item |
| M3-1 | Surface, term structure and skew builder | pending | M3a | - | - | Own capability matrix and independently authored fixtures first (V3 rule) |
| M3-2 | Realized-volatility join (daily bars) | pending | M3b | - | - | As M3-1 |
| M3-3 | Frame builder without presets | pending | M3c | - | - | As M3-1 |
| M3-4 | History reuse from the M2 store (percentile-of-history and change-since-prior-session rows V1, V3, V4, V7, V9, V10) | pending | M3a | - | - | M2 store merged (PR 80); history reuse belongs to the surface release, PO ruling 2026-10-30 |
| M4-1 | Open-interest-based and exposure outputs | pending | M4a | - | - | Own matrix and fixtures first; chain generator with synthetic open interest |
| M4-2 | Dealer-sign convention, labelled modeled | pending | M4b | - | - | As M4-1 |
| M5-1 | Scanner presets, shadow and list-eligible only (D6) | pending | M5a | - | - | Own matrix and fixtures first; scanner authorization flag stays false |
| M5-2 | Equity-side join (also enables F8, F11) | pending | M5b | - | - | As M5-1 |
| RQ-1 | Vendor feed adapter to the frozen mapping | pending | RQ | - | - | RQ entry gate: M5b accepted, earlier labels clean, owner items supplied |
| RQ-2 | Display-rights-driven storage and display rules | pending | RQ | - | - | Owner-supplied rights table |
| RQ-3 | Recorded data (local, never committed) | pending | RQ | - | - | Owner permission, entitlement and spend ceiling |
| RQ-4 | B1-B12 measured on real sizes | pending | RQ | - | - | RQ only |
| RQ-5 | Linux x64 and Windows x64 evidence | pending | RQ | - | - | Linux run as process check, not claimed, until RQ |
| RQ-6 | Open-interest statistics and daily bar sources wired (D8) | pending | RQ | - | - | RQ only |
| RQ-7 | Synthetic-versus-recorded divergence review | pending | RQ | - | - | Any semantic surprise becomes a PO ruling |
| DROP-1 | R28a as a separate adapter release | dropped | RQ | V3 plan | - | Adapter work moved wholly into RQ (PO release plan V3, 2026-10-29) |

## 4. Accepted performance work (separate from the feature counts)

Owner main goal: performance. All figures are synthetic workload, relative engineering budget, on one Xeon Platinum 8160 host (48 physical cores, 254 GiB), Windows x64, CPython 3.12; Developer evidence unless a Tester measurement is named; no recorded-data claim.

| Item | Status | PRs | Result (synthetic workload) | Notes |
|---|---|---|---|---|
| Stage 0: Fraction conversions hoisted out of the IV solver loop | done | 65 | about 1.37x per solve | Identical result bytes; Tester differential |
| Stage 1: float-filtered bisection with written bound and certified switch | done | 67 | about 3.3x per solve | Tester approve-with-conditions, bound proof sound, 28,800 contracts identical |
| Stage 2: integer endpoint conversion with lazy enclosures | done | 71 | about 3x per solve; Stages 0-2 together 8.62 s to 2.80 s p95 on the B6 gate chain | 23,200 of 23,200 contracts identical; Tester re-run; full 1,000,000-input equivalence run is a PO-ruled periodic check |
| Opt-in process-pool runner (default single-process) | done | 72 | identical hashes at 1, 2, 4, 48 workers; 3.78x at 4 workers; B7 workload 1.78 min at 48 workers (developer run, once) | Tester re-ran determinism, kill and scaling; the B7 run was not re-run independently |
| M2-G0 full-output B6 | done | 77 | 1 worker compute-only p50 2.41 s, p95 2.66 s against the 5 s budget | Tester conditions applied, Tester re-run pending |
| M2 story B print-window families | done | 79 | at 1e6 prints F1/F4/F17 about 0.9-1.1M prints per s, shared pass 0.72-0.85M per s (floors 100k and 50k); B15 print-pass ratio 0.034 | Gates met; strict prebuilt ratio informational |
| M2 story A store, grid and rank gates | done | 80 | B18 build 70-85k prints/s, B2 warm 1.6 us p95, B3 8.3 us p95, B3n paired ratio 3.67 at 6,000 series against hard 4.0 (thin margin), B16 mmap start 4.37 s and 407 MB private at 6,000 series | Developer figures; Tester approved at 0954d21, PO accepted; the B3n margin is thin and a different machine decides it |
| Mmap store snapshot as the worker-start transfer form | done | 80 | see above | Ratified (PO 2026-10-30), optional beside the ruled M2SNAP1 text format |
| Newton as a verified bracket seed | deferred | - | - | Scheduled only if B6 on the full output set is missed; M2-G0 met B6, so no trigger today |
| Lazy ring and record creation per series (B16 worker start time and private bytes) | candidate, not scheduled | - | at 6,000 series the mmap start is 4.37 s with 407 MB private; text load 8.1 s and 651 MB private (synthetic workload) | Create rings and records only when a series is first read or written; recorded in DECISIONS 2026-10-30 |
| F7 density-adaptive window strategy (window scan versus two-pointer slide) | candidate, not scheduled | - | strict prebuilt F7 ratio 0.84-1.01 at 3x overlap (informational) | Recorded follow-up story after the F-row re-audit (task M2-8) |
| F17 sparse read per cutoff | candidate, not scheduled | - | strict prebuilt F17 ratio 0.72 (columns), 1.42 (full) (informational) | Same follow-up story (M2-8) |
| Input-synthesis sharing across units | candidate, not scheduled | - | about 23 percent of CPU at 48 workers (M1 close finding) | Idea candidate for the PO queue; B7 is far inside budget |
| Contract-v2 and contract-v3 perf_sut adapter | deferred | - | - | Deferred by PO ruling at the runner PR |
| Story A and story B alignment story | done (alignment), pending (runner integration) | 88 | - | Story B aligned to the story A Result type (PR 88 merged); runner integration of M2 families stays pending (M2-6) |
| Regenerate docs/m2/M2B_PRINT_BENCH.json | pending | - | - | Its strict prebuilt ratios predate the agreed 78-single-calls-versus-one-sweep method (DECISIONS 2026-10-30); regenerate with tools/m2_print_benchmark.py (PR 87 open: regenerated at 30 repeats with the agreed tool) |
| Tester re-run of B7 | pending | - | - | Only the developer ran B7 (once); disclosed in M1 close |

## 5. Performance gates (short)

Every number is a synthetic workload, relative engineering budget; budgets are proposals until RQ. Sources: docs/M1_CLOSE.md section 2, qualification/synthetic/perf/PERF_ACCEPTANCE.md, docs/m2/M2_GATE_BUDGETS.md, DECISIONS.md.

| Gate | What | Budget / hard | State (synthetic workload) |
|---|---|---|---|
| B1 | Ingest rate | 50,000 records/s | Not gated before RQ (needs adapter and sink); M2-B1 is the library store append gate |
| B2 | OC5, one contract | 50 us / 200 us | met, 13 us p95 (Tester) |
| B3 | OC6, 50 updates; 5,000 updates | 200 us / 1 ms; hard 20 ms | met, 114-127 us p95 (Ticks ingest); 10-14 ms p95 at 5,000; thin margin on the string path |
| B4 | Chain ATM IV, size M / L | 1 s / 4 s | met, 0.063 s / 0.099 s p50 |
| B5 | 30-day IV, size M | 1.5 s | met, 0.021 s p50 |
| B6 | All outputs, one underlying, size M, compute-only | 5 s / 15 s | met, IV part 1.53 s p95; full output set 2.66 s p95 (M2-G0, PR 77, Tester re-run pending) |
| B7 | 5 x 5 x 78 cutoffs, size M, once | 170 min / 240 min | met, 2.38 min at 24 workers, 1.78 min at 48 (developer run, once; 60 min is an informational owner target) |
| B8 | Informational | - | not gated |
| B9 | Memory per process | 2 GB / 4 GB | met, 142-495 MiB per worker (repo record) |
| B10, B11 | Sink and checkpoint size | - | Not gated before RQ (adapter and sink) |
| B12 | Determinism, one underlying, one session | identical result bytes | met at every compared worker count and order |
| P1-T1 | Spread and touch-policy classification | >= 100,000 records/s | met, 663,933 records/s at 1e6 (marker; not re-measured since) |
| M2-B5 to B8, B10 | Print families, F7, F18, F12, shared pass (story B) | rate floors 100k, 100k, 200k, 500k, 50k | met (PR 79) |
| M2-B15 | Cutoff sweep, print-pass ratio | <= 0.25 | met under the ruled print-pass definition (0.034); strict prebuilt ratio informational |
| M2-B1, B2, B2c, B2n, B3, B3n, B4, B9 (story A part), B13, B15r, B16, B17, B18 | Store, rank, baseline, transfer, persistence, build | see M2_GATE_BUDGETS.md | measured, met at 2,000 series; at 6,000 series B3n 3.67 (hard 4.0, passes, thin) and B16 under the hard limits and inside budget with the mmap form|
| M2-B9 (all outputs together), B11, B12, B14 | Whole M2 output set, whole workload, M2 determinism under the runner | 1.2 s / 5 s / 170 min / identical | not measured: needs story A and B merged and the runner integration (M2-6) |

## 6. Open design requests

Source: DESIGN_SESSION_REQUESTS (baseline package), docs/m2 matrix section 8, 10, 11. No design-session ratification is recorded in this repository as of this audit; each interim ruling stays in force until the design session answers. A changed answer regenerates the dependent fixtures.

| # | Topic | Interim ruling in force | Status | Rows affected |
|---|---|---|---|---|
| 1 | Locked market scope (OC 2.3) | Option A: gate withholds spread and modeled values; signing proceeds | interim, implemented in P1, pending ratification | OC4, G2, OC6, F13-F16 |
| 2 | Bid of 0 is invalid (OC 2.3) | Option A: invalid for spread and signing | interim, implemented in P1, pending ratification | OC4, G1 |
| 3 | Coverage rule and time-weighted average (G5, OC6) | Option A: time-weighted, closed window, count coverage min 5, blocks OC6 only | interim, implemented in P1 and M1, pending ratification | G5, OC6 |
| 4 | Anchor readiness under incomplete capture (span family) | Current behaviour; two masked rows and disclosure kept | open | R26 variants1 span rows (not a design row) |
| 5 | Zero-MAD and zero-median policy | Finite sentinel kept in variants1; M2 reuses the closed vocabulary (zero_denominator, insufficient_history) | open | G7, F10, F20 |
| 6 | F5/F6 denominator and coupling | Option A: share of total eligible premium, single-reference outputs | interim, implemented in P1, pending ratification | F5, F6 |
| 7 | F9 grouping mechanics | Library mechanics (side-split lanes, exclusive first-unassigned windows) | open | F9 stays partial |
| 8 | F13-F16 side rule, quote age, labels | Option A: touch rule, 3 s age, unclassified inside the spread, proxy labels; tick fallback not built | interim, implemented in P1, pending ratification | F13-F16, tick fallback |
| 9 | F10/F20 baseline statistic | Both median_ratio and mean_ratio output; consumer default F10 median, F20 mean | interim, built in PR 80 (merged), pending ratification | F10, F20 |
| 10 | OC5 formula, threshold, zero size | Ruled and implemented in M1 | interim, pending ratification | OC5 |
| 11 | Stale limit, ATM, constant maturity, consolidated feed | Ruled and implemented in M1 (feed kind is a synthetic field) | interim, pending ratification | G4, V2, M1-3, M1-4, OC5 |
| 12 | American-style option labels | Ruled and implemented in M1 | interim, pending ratification | M1-2, V2 |
| 13 | Shipped 0-100 chain.activity score | Shipped, used by no preset | open, low | extra |
| 14 | Cite repo ids through the naming map | Mapping stays library-side | open, low | docs |
| 15 | Persistent items OD11, OD12 | Stay with the design session | open, no library action | none |
| DR-M2-1 | F2d fire rule, default X, all-parts requirement, crossing form | F2d `fired` is null; parts and average shown | open, blocks a firing F2d | F2d |
| M2 rulings | Q1-Q18, AMB-1..19, GRID: F2 reference distribution and time-of-day alignment (flow.md 2.7), cadence (VR 2.9), product lane (OD9), F10 median versus F20 mean, placeholders X = 5, N = 2, share 0.60, $100k | Interim where the design is silent | pending ratification | F1, F2, F4, F7, F10, F12, F17-F20 |

## 7. Shipped ids with no design row (extra, not counted)

chain.activity (0-100 score; request 13), pricing.price, greeks.signed_delta, greeks.rho, quality.quote_coverage (slot ratio, not G5), variants1 net, classified, unknown, raw counts, parent-group and span families, concentration, joint_reference, checkpoint and restore family. Detail: docs/FLOW_NAMING_MAP.md.

## 8. Statuses the Auditor could not verify

- R25 and R26 rows cite the release, not PR numbers (the early PRs were not traced). The R25 and R26 behaviour was taken from the baseline parity audit and the shipped naming map, and the P1 changes from the merged P1 modules; the R25 evaluator was not re-run here.
- Retro process items of P1 (WSL pass of every harness, hash-record generator, wording grep gate) were not traced to artifacts, so they are not rows.
- Whether the design session has answered any request is not recorded in this repository; the design repository was not searched for replies.
- Story B review and acceptance: see the independent-review cell of its rows (Tester approve at 9f6617b; PO accepted in the PR 79 merge message).
- Story A (PR 80): the 817-test pass was run by the Auditor on the pre-merge head, not re-run on the merged tree; the mutation result (75 of 76 mutants caught, 1 equivalent) and benchmark figures are Developer records.
- All performance figures are copied from DECISIONS, M1_CLOSE and the benchmark JSON files; none was re-measured. The Auditor ran no benchmark and no python-flint suite (python-flint is not installed in this session).
- V16-V22, F8, F11 release assignments are proposals, not V3 text.

## 9. Maintenance

Every release PR updates this file (rows touched, counts, PR numbers, pending reasons, gates) and says so in its release note (docs/RELEASE_NOTE_TEMPLATE.md). The counts in section 1 are recomputed from the tables, not edited by hand. A row is never marked done on documents alone: name the module and the fixture rows or tests that pass.
