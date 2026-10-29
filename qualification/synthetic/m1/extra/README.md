# M1 extra IV rows (independent Tester)

Provenance: SYNTHETIC. Authored by the independent Tester during the PR 68 review; accepted as fixtures by the PO on 2026-10-29. Generators and the oracle are test code, not library code.

Label (verbatim): mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

## Files
- m1_iv_extra_cases.json: 28 rows (all gating), same row vocabulary as ../m1_iv_cases.json (ops contract_iv, atm_iv, iv_30d).
- gen_new_rows.py: deterministic generator (no clock, no randomness). `python gen_new_rows.py m1_iv_extra_cases.json`; two runs give identical bytes.
- oracle.py: independent oracle (float bisection on Black-Scholes, ACT/365, exact tie-break) plus a thin adapter to option_features.chainiv.
- run_rows.py: checks every row three ways (oracle vs row, implementation vs oracle, implementation vs row). PYTHONPATH must contain packages/features/src, packages/option-contracts/src and this directory. Expected output: `rows 28 oracle numeric values 74 disagreements 0`.
- MANIFEST.sha256: SHA-256 of every file here (LF).

## Tolerance
IV absolute 1e-4 (0.01 vol point); forward absolute 1e-6. Quotes are 4 dp mids with +/-0.0010. Expected IVs are the stated sigmas or exact functions of them, never solver output.

## Closed reason list
no_quote, excluded_condition, invalid_quote, crossed_market, locked_market, stale_quote, no_atm_strike, no_bracketing_expiry, american_itm, style_unknown, and the solver reason price_out_of_bounds (a mid outside the no-arbitrage bounds; reported as the solver gives it, no fallback to another strike).

## What the rows cover
Stale age equal to the limit and limit plus 1 ns (N-S); excluded_condition and gate precedence (N-X); known_at at and after the cutoff (N-K); mixed and unknown style on the ATM strike (N-M); American nearest-strike tie (N-A); solver failure on an ATM leg, per contract, exact 30-day and bracketing (N-F); binary64 rate and yield differences of +/-1e-9 and +/-1e-4 around a nearest-strike tie, and r = q (N-B); put-call parity chains with r != q (N-P); many-expiry chains (N-E).

## Notes
- expiry_days is an integer in the library API. The requested 29.99 and 30.01 day case is therefore N-E01 with expiries of 29 and 31 days. Fractional expiries need a real expiry time-of-day: an RQ-time item, not covered here.
- Rates and yields are decimal strings with up to 10 places (the other fixture uses 4); they enter the library as binary64 by ruling.
- Mutation evidence: these rows catch the developer-only mutants X4 (stale limit inclusive), X10 (excluded_condition not applied) and X11 (future known_at visible) of tools/m1_iv_mutation_check.py.
