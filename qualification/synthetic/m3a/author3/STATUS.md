# author3 status (V4-V8, V10, V11, V21), 2026-10-30, after fix round 5 (PO rulings R-162..R-185)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12. Provenance SYNTHETIC. NOT committed; kept out of the repo. Checked against origin/main docs/m3a, docs/decisions (owner decisions 1-5, batch 2) and docs/WIRE_FIXTURE_AUTHORING.md (fetched copies in ../_ref).

## Row counts (406; was 398)
V4 80 (M3A-3), V5 40 (M3A-4), V6 34 (M3A-5), V7 44 (M3A-6), V8 66 (M3A-7), V10 64 (M3A-9), V11 38 (M3A-10), V21 40 (M3A-11). Non-gating (near-threshold) rows: 36 plus 3 new. Mutants: 54, each caught by at least 2 rows (mutants_result.txt, LF). Self-check (second implementation, quote text only): 406 rows, 0 failures; boundary rows now compared strictly on all families.

## Round 5 (R-162..R-185)
1. R-182: boundary-exact rows V6-D2, D3, V8-D1, D3, V21-D3, D4 (and their pair rows plus V5-D-2, V7-C1..4, V11-D1..4, V8/V21 siblings) re-quoted by whole 1e-8 ticks (`expected.boundary.quote_ticks`, tag quote-tuned); the quote-text value now rounds exactly to the threshold under round-once and round-annual-first, fired stays true; all landed, no fired=false sibling needed.
2. R-172: V4-S-08 (iv_form_not_allowed), V4-S-09 (malformed_type): selector 3+3. R-173: V8-Cv11, Cv12: forward rows 12. R-174: V4-Cx1, V5-Cx1, V6-Cx1 (bad string), V7-Cx1 (non-string): delta_convention ignored, not echoed, no code. R-185: bad-string direction row not authored (code not in the contract).
3. R-180: V4-A-15, A-16 labels = model label of the used expiry only. R-178 (V4-M02, V8-F1, F2, V10-H2, M2, V11-F1, V21-F3) and R-179 (V4-A-17, V5-H-1) confirmed, citation tags only.
4. Reproducibility: generators plus patch_round4.py reproduce the files byte-identically (run order in AUTHORING_NOTES.md; closed_reasons_used order fixed). Mutants M50 to M54 new (convention validated or echoed on V4-V7, labels from unused expiries, iv_form case-insensitive, non-string iv_form code). mutants_result.txt LF. Superseded below: the Gaps entries on selector counts, V8 forward 10 vs 12 and V4-V7 delta_convention are CLOSED by R-172..R-174.

## Fixes made in this pass
1. `no_eligible_contract` (R-106, closed set) had no rows and was missing from every header: added 24 rows, `<FAM>-NE1` empty chain, `NE2` every contract late_report, `NE3` every contract stale, in all 8 families (unavailable, reason no_eligible_contract, labels [], contract_reasons counted, never structural); header `closed_reasons_used` updated; mutant M49 (reported as low_surface_coverage) caught by all 24.
2. Superseded citations: R-81 on 77 V4 rows -> R-151..R-154; R-83 on V6 rows -> R-103, R-104. V8-O1 (was a "guess, PENDING-RULING D-08") now RULED by R-117, R-139.
3. R-153 atm_iv restored: V4 ATM-form rows use series XYZ/stock/atm_iv, 30d rows XYZ/stock/iv30 (no mixing); no row uses the dropped-metric wording. V10 skew25 / skew25_fwd per R-159, R-160 as before. Checked, no change needed: R-132 labels sorted, R-133 down, R-134 all priors, R-136, R-137, R-139, R-140 names, R-152 selector codes, R-155 selector codes, R-158 echo.
4. Scripts and notes: ref3, rowkit3, gen v4/v6/v8 constants, run_mutants, patch_round4.py (post-generator patch: regenerating with the gens alone does NOT recreate the NE rows or the citation changes; run patch_round4.py after them), AUTHORING_NOTES.md round-4 paragraph.

## Coverage per requirement (M3A_FIXTURE_REQUIREMENTS section 4/5 families)
- V4 (req 60): 77; 30d form 47 (iv30), ATM form 27 (atm_iv series, incl. selector and NE rows); selector rows: iv_form_not_allowed 2 (req 3), malformed_type 2 (req 3). Both priors kinds, directions, zero prior, no_prior_reading, prior_not_before_cutoff 5, exact 10 percent, mixed labels, delayed.
- V5 (36): 39 (both pairs, sign, missing tenor, boundary). V6 (30): 33. V7 (36): 43 (n=1 and 3, store priors). V8 (60 plus 12 forward): 64 of which forward Cv 10. V10 (56 plus 8 forward): 64, forward 8 (mismatch 3, selector 2). V11 (30 plus 6): 38, forward 8. V21 (30 plus 6): 40, forward 7, threshold_required 4.
- Reasons present by family: see header closed_reasons_used; zero_range_history, session_not_complete, fewer_than_two_expiries (V6 only, 3 rows) as listed for other families (history family belongs to other authors).
- Two-condition rows (req at least 10): V4 M01/M02, V7 M1/M2, V10 M1/M2, V21 H1/H2, plus P-rows for structural beside upstream: 10+.
- Mutations: 49 (req at least 40); groups 1-6 covered; groups 7, 8 (structural pair swaps, infrastructure) not here.

## Gaps and interpretations (flagged, not hidden)
- Selector counts below the requirement per family: iv_form_not_allowed and malformed_type need 3 each across M3A-2/M3A-3; V3 (M3A-2) belongs to another author, V4 has 2+2. delta_convention: convention_not_allowed 1 and malformed_type 1 or 2 per family, requirement 3+3 across M3A-0, 7-11 (met in total, not per family).
- V8 has 10 forward rows against "12 forward-delta rows" in the requirements; V10 8 ok; V11 8, V21 7 ok.
- V6 with an empty chain: no_eligible_contract (R-106 "frame unavailable", takes precedence over fewer_than_two_expiries) is my reading; one reading of R-106 could keep fewer_than_two_expiries. V6-NE1..3 carry that interpretation (gating true; change to non-gating if the PO disagrees).
- NE rows are single-condition; "never appears elsewhere" is shown by the existing rows with few eligible contracts that expect low_surface_coverage/no_atm_strike/no_bracketing_expiry, no dedicated row. Position of no_eligible_contract against V4 structural codes (iv_form, delayed tag) is not exercised.
- R-149/R-155: V1-V7 requests carrying delta_convention are not validated: no V4-V7 row proves it (V4 to V7 take no convention); gap.
- R-160 slot order of convention_mismatch against prior_not_before_cutoff at position 17: no row combines them.
- Not covered here: V1, V3, V9, surface, tenor, coverage (3/5 vs 1/2, locked_market, near-the-money clause), units, history, structural, lane families, performance, 20,000-case differential, solver reasons beyond counting (R-128/R-145 stubbed at unit level).
- Tolerances per R-138 (3e-5 IV, 0.005 points); 8-decimal boundary rows land exactly on the threshold (R-182) but stay non-gating (R-138 tolerances).

## Stray work folders (not deleted)
`out`, `out_a`, `out_b`, `out_c`, `out_d`, `out_e`: scratch regeneration dumps written by the generators (--out) during earlier rounds, 4 to 9 files each (`m3a_cases_v*.json` datasets, `out_a`/`out_b` also the G5 priors), 1 to 2 MB each, dated 11:02 to 11:49. `out_e` (5 files: m3a_cases_v4, v8, v10, v11, v21 .json, 1.8 MB, 11:49) is the last, a determinism re-run of the five families touched by owner decision 3 on the 374-row set; it is STALE (pre round 4) and not part of the set. Not listed in MANIFEST.sha256. Safe to delete by the owner; nothing was removed.

## Manifest
MANIFEST.sha256: explicit file list (no directories, no show.py), LF line endings, sha256 of LF file bytes; includes STATUS.md and patch_round4.py; excludes itself.
