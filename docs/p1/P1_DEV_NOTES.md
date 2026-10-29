# P1 developer notes: choices where the fixtures are silent, defect reports, rulings needed

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Author: Developer, 2026-10-29. Branch p1/parity-closure. These notes list every place where the independent P1 rows or the PO rulings did not fix the behaviour and a choice was made. None contradicts a row. The rows (qualification/synthetic/p1/p1_cases.json) are unedited; `tests/p1/test_p1_rows.py::RowIntegrity::test_rows_unedited` pins their sha256.

## Defect reports against the fixtures
None. No row contradicts the PO rulings or another row; all 121 pass and `selfcheck_p1.py` passes unchanged. Observations only: the rows assert `spread` and `midpoint`, which R25 did not output (added as outputs, see choice 1); the H-group rows pin legacy sides with an epsilon the Tester did not probe (0 used, as in the rows).

## Choices where the rows or rulings are silent (PO to confirm or rule)
1. `liquidity.spread` and `liquidity.midpoint` added as additive R25 outputs so the OC4 row values are asserted through the library, not recomputed in the test.
2. A quote with neither bid nor ask is represented as no quote record in the R25 adapter (design reason `no_quote`). The R25 library itself still answers `one_sided_quote` for such a record (unchanged bytes); in the batch classifier it reads `no_quote`.
3. Library reasons are not renamed to the design strings. `invalid_quote` is `negative_quote`, `nonpositive_bid` (new) or `one_sided_quote`; `crossed_market` is `crossed_quote`; `locked_market` is new. The map is docs/FLOW_NAMING_MAP.md. Renaming `negative_quote` and `crossed_quote` would change more R25 bytes than PO-P1-02 rules.
4. Only `bid <= 0` is invalid (as ruled). `ask <= 0` with `bid > 0` is crossed (R25 reason `crossed_quote`, unchanged).
5. Legacy window (no `window_end_ns`): the anchor is the latest standard (multiplier 100) print; a non-standard print never anchors and is counted only when it lies in the window. An empty legacy window returns zero amounts with window bounds None.
6. `single_reference_shares` with no prints, or a measure with no referenced print: `missing_reference` (the closed reason set has no `no_premium`); `fired` and `label` are None when the measure is unavailable even if a threshold is given. The OTM test is exact (strike versus spot); the legacy joint operation tests the binary64 ratio, which agrees for every price of at most 8 decimals below 1e8.
7. Trade price <= 0 or None is `invalid_quote` (legacy parity). A quote after the trade is `no_quote`; a quote at the same nanosecond is usable. In `classify_stream`, records at equal time apply in input order and an out-of-order stream raises ValueError. So a trade that precedes a same-nanosecond quote in the stream sees no quote, while `sign_trade` treats a quote at the same nanosecond as usable (the caller orders the input).
8. Legacy sign mode keeps the shipped order: stale before validity; crossed is `invalid_quote`. The touch policy uses the ruled order (no_quote, invalid, crossed, stale, touch).
9. Prices are held as integer ticks of 1e-8; more than 8 decimals raises ValueError instead of rounding. Premium assumes multiplier 100 for signed trades (`sign_aggregate`) as in the rows.

## Rulings needed
- Wire integration. The touch policy, window end and single-reference shares are pure modules beside the evaluator, not operations of the frozen variants1 wire schema. Adding a sign kind, a window end or new metrics to that schema changes Request/Policy/Operation records and the externally held frozen fixtures, so it is a candidate bump needing its own ruling and fixtures. Until then the design rows F3, F5, F6, F13-F16 are "match" in the P1 modules only (FLOW_NAMING_MAP.md says so).
- Modeled values. G1 and G2 gate the spread only; IV still accepts a bid of 0 and a locked quote (M1 scope).
- docs/r26/FEATURE_BINDINGS.json, FLOW_CONTRACT.md and MATHEMATICS.md notices still say the naming map is "planned and not yet published". They were not edited (history files); the PO may order a one-line follow-up.
- tools/demo: the 12 `version` fields in demo.html and in sample/demo-export.json are not package versions. They belong to the synthetic reference cohort "REFERENCE-full-fixtures2" (distributions option-flow-*, placeholder commits and hashes), which comes from frozen replay fixtures held outside this repository and is part of the cohort digest. They were left at 0.1.0a1 and the sample was not regenerated; changing them would break the digests the sample is checked against.

## Test coverage limits
`tests/p1/test_p1_version.py` checks the pyproject versions and pin, `__version__`, the embedded result strings, the living sources and API docs named in it, and the compatibility manifest. It does not grep `tools/demo` or the other docs (by decision the demo fields stay at 0.1.0a1, and history docs keep their versions).

## Environment facts
- python-flint is not installed in the default interpreter and nothing was downloaded. The suites that need it ran with the existing local environment `Documents/ChatGPT/Equity Features/work/r25-20261020/method-development-env` (CPython 3.12.10, python-flint 0.9.0), with this checkout's sources first on PYTHONPATH.
- The fixture consumer needs the LF bytes of qualification/fixtures/r25-independent-wire-fixtures.json: a Windows checkout with line-ending conversion hashes differently (3eae4f00... instead of 37f79537...). The run used `git show HEAD:...` output for the pinned file; the checked-in file is untouched.
- WSL (Ubuntu 24.04, CPython 3.12.3, no python-flint): contracts 14 and p1 140 tests pass as a process check, not a claim; the features and qualification suites need python-flint and were not run there (no installs).
