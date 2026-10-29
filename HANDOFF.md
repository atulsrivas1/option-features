# Handoff (keep under 60 lines; update after every merge)

Updated 2026-10-29 (M1 Stage 2 PR open, story B merged; P1 DONE, 0.2.0a1 on main, merge 62a178c; candidate15 frozen, CANDIDATE15_FREEZE_RECORD.md: 2666 of 2668; R27 evidence recorded in RELEASE_NOTES section 16 (T8 draft, docs review and PO accept pending): harness v15.1 is the gate harness, label extended to candidate15 on Windows, Linux evidence on WSL2 is not a label; PRERELEASE). Read this, then STATUS.md, DECISIONS.md, the coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md).

## PO release plan V3 (2026-10-29, authoritative; DECISIONS.md has the entries)
- Main goal (owner): performance. Use cores, memory and caches fully to calculate faster without breaking correctness. B1-B12 are hard acceptance gates (synthetic-size stage until RQ; label "synthetic workload, relative engineering budget"). Developer designs for multi-core, vectorised/batched calculation, caching, minimal allocation; Tester authors independent perf, parallelism-determinism, batched-vs-single, cache and memory fixtures.
- Order: R27 done, P1 (0.2.0a1), M1 (was R28b, OC5/OC6/ATM IV/30-day IV), M2 flow, M3 surface, M4 positioning, M5 scanners, RQ last. R28a is DROPPED; ALL adapter/Databento/network work only in the final RQ release.
- Label through M5, verbatim in every release note: "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12". Rules: docs/RELEASE_NOTE_TEMPLATE.md; docs reviewer greps the forbidden list as a gate. Stays PRERELEASE.
- Performance rulings (DECISIONS.md, D4 amended): opt-in process-pool runner (opt-in, default single-process) = LAST M1 story (workers <= min(cores, RAM/B9), merge by unit key); solver stages: Fraction hoist, float-filtered bisection with certified fallback and proven bound, Stage 0 then Stage 1 both in M1; Newton only as verified bracket seed; true-value change = separate PO ruling and candidate bump; governing B7 = 170/240 min; Linux process check, not claimed; eight acceptance tests authored by the independent Tester. Owner-only: python-flint scratch venv approval, B7 machine cores/RAM.
- P1 and M1 fixtures authored independently (Tester, no implementation read), reviewed by an independent reviewer; interim rulings on design requests 1-3 (option A each) are pending design ratification; a changed answer redoes fixtures. M1 code starts when P1 is accepted. P1 bump plan: docs/P1_VERSION_BUMP_PLAN.md.

## M1 story B (chain IV): merged (PR 68), awaiting independent Tester and PO acceptance (Developer evidence only)
- Done: option_features/chainiv.py (IVChain: contract_iv, atm_iv, atm_iv_all, iv_30d; American labels), tests/m1 (41 of 41 independent IV rows pass; 18 extra tests), tools/m1_iv_mutation_check.py (13 of 13 V mutants caught by rows; 14 of 14 X mutants caught by rows plus extra tests), tools/m1_chain_benchmark.py, docs/m1/M1B_CHAIN_BENCHMARK.json. Certified solver untouched; Stage 0/1 suites green.
- Measured (synthetic workload, relative engineering budget; Xeon 8160, one worker, 30 repeats, p95): B4 M 0.066 s, B4 L 0.107 s, B5 M 0.020 s, B6 IV part M 4.22 s (budget 5 s; other outputs are other stories, so B6 as a whole is not yet measurable). about 58 percent of solve time (cProfile) is outward-decimal endpoint conversion in arithmetic.py (next lever, identical bytes needed; PO ruling to schedule).
- Rulings used: D12 to D14 and the notes; PO rulings requested are listed in the DECISIONS.md entry (unknown-style ATM strike, solver-failure reasons, ATM no fallback).
- M1 Stage 1 (PR 67) is merged and accepted; Stage 0 merged (PR 65). Next: story A (OC5/OC6), Newton seed (optional), opt-in runner last.

## P1 (0.2.0a1): DONE, PO accepted 2026-10-29 (PR 63, merge 62a178c on main)
- Accepted after independent code review (approve-with-conditions, then delta re-check approve) and an independent Tester re-run with python-flint 0.9.0 (DECISIONS.md, last entries). Interim design rulings stay pending ratification; wire exposure of quotes/windows/shares is a candidate16 item.
- Next, in order: workers pin PR 11 (io PR 9 merged), then M1 Stage 0 (Fraction hoist), Stage 1 (float filter with proven bound), OC5/OC6/ATM/30-day IV, opt-in process-pool runner last. Owner goal: performance. Also still open: tag and wheel rebuild from the tag (no publication), Linux process check (not claimed).

## PO decision 2026-10-28: R26 stays PRERELEASE (Windows x64 cp312, partial Windows evidence)
- Release notes with full disclosures: docs/r26-variants/RELEASE_NOTES.md (see PR 51; Next item 8 is done once that PR merges). The scoped label was ratified 2026-10-29 (see below); candidate13 stays the baseline (history: the baseline is now candidate15, RELEASE_NOTES section 16).
- Windows c14 evidence: RELEASE_NOTES section 14 (PR 54; its label wording is superseded by section 15). A1 approve-with-conditions (independent reviewer); A2 done with limits (tags -> commits recorded in 14g; receipts keep placeholders; no wheel-to-commit provenance).

## M1 Stage 2 (endpoint conversion, identical bytes): PR 71 open, Tester approve-with-conditions applied (Developer evidence only)
- Done: integer endpoint conversion, lazy Ends (Decimals only for reported enclosures), exact integer ordering and residual tests; arithmetic_legacy.py is the pinned verbatim oracle and the switch fallback (arithmetic.set_fast_endpoints(False)). Proofs: docs/M1_STAGE2_ENDPOINT_CONVERSION.md; raw numbers docs/m1/M1_STAGE2_RESULTS.json.
- Identity: 23,200 of 23,200 contracts hash-identical (22,800 flat+mixed+adversarial plus 400 mutation ties) with the fast path, the Stage 1 switch off and the Stage 2 switch off; 1,000,000 random inputs, 9.1 million old-versus-new comparisons, 0 differences. No input class differs; fast path ships on.
- Measured (synthetic workload, relative engineering budget; one worker, 30 repeats, interleaved): per solve p50 2.93 to 0.96 ms (about 3x), p95 5.07 to 1.57 ms; B6 IV part size M default chain (992 solves) 4.17 to 1.35 s p95, all-european chain with valid quotes (1736 solves) 7.38 to 2.29 s p95. Arb calls per solve unchanged (about 13); memory unchanged (33 MB).
- Next: independent Tester re-run on its own all-valid chain; PO rulings listed in the DECISIONS.md entry; then story A (OC5/OC6), Newton seed (optional), opt-in runner last.

## Next
0. Independent freeze review of CANDIDATE13_FREEZE_RECORD: DONE (approve-with-conditions, applied); next coordinator freeze and merge. Then candidate14 (PO R27 rulings): lift exclusion of the 3 null-nondict rows, harness assertion for the extra-stream control row, re-issue filter, hashes, counts and release notes. PO to review: N5 rows flagged (proposed), assumption-2 confirmation, A>K disclosure, sorted-literal excluded_ids, nonexpected two-control rows as negative controls (the last three already PO-ruled; see DECISIONS.md).
OWNER ITEMS first (parked until the owner returns):
1. PyPI wheel permission for Windows qualification: APPROVED by the owner and done; python-flint 0.9.0, duckdb 1.5.6, setuptools 80.9.0 (win_amd64 cp312) downloaded, sizes and sha256 verified against PyPI (see docs/r26-variants/WINDOWS_PARTIAL_QUALIFICATION_RECORD.md).
2. Qualification scope.
3. Release acceptance and the qualified-vs-prerelease label. Criteria: Windows qualification passes; demo works (merged, synthetic-only); two-control fix landed (done); /checkpoint and /config coverage (done) or scoped out; every flagged id disclosed; owner accepts.
4. DONE: the pending-decision review is complete; all decisions are now PO-ruled (see DECISIONS.md, "PO ratification of pending decisions" and "PO rulings on the six items"); some rulings carry open conditions (items 9b-9e). No review items remain for the owner.
5. Worktree cleanup (.claude/worktrees in the three repos, including s24-freeze12 after merge).
Team items:
6. Independent freeze review of candidate12: DONE (approve-with-conditions, conditions applied). Next: coordinator freeze and merge of the record PR. Candidate13 supersedes it once its record PR is reviewed and merged.
7. Q4 and the narrower-rollup clause are SCOPED OUT with disclosure (PO R27 ruling, 2026-10-28); N5-restore-q3-dropped-with-extra-stream-added also scoped out. Reopen only on owner-supplied contract text.
8. Release notes finalization (record section 8 items; filter re-issued for candidate13 hashes, counts and the 5 excluded ids; draft kept in the private work folder).
8b. New fixtures for uncovered Q3 / field_set positions; code and codec changes land together (PO condition).
9. Regenerate the flagged rows, assumption-2 block first (18 rows/graphs plus the 9 held rows).
9b-9g. Open conditions (full text in DECISIONS.md): A>K merge identity_conflict fixture first; PR 34 six rows under Reading B; two-control F4 fix with frozen rows unchanged per the v9 replay; release notes disclose c-domain/c-completeness untested; CP3 Q2 order not asserted and Q4 held; assumption 2 already encoded in the 9 B and 9 B3 rows (PO acceptance pending via PR 49).

## variants2 backlog
- Contract-versus-code conflict: BOUNDARY_CONTRACT line 322 may mandate canonicalizing -0.0, while variants1 rejects -0.0 permanently. Resolve in variants2.
- -0.0 pinning row already exists: N4-premium-b64-negative-zero-price-rejected (invalid_scalar, stage 4); no new row needed, only the pointer flag remains (analysis finding, PO acceptance pending via PR 49 review).
- Before any "qualified" release: independent controller review.

## Gotchas
- Controller runs need absolute paths; contained run via python -I -B, never reuse a failed attempt dir.
- Add .gitignore for bytecode before any run; commit-then-remove leaks into branch history.
- Fixture-vs-contract triage before bending code; Sonnet (not Haiku) for storage/restore work.
- Pinned counts learned from a first run (workers partial 32) must be recomputed by a reviewer.
- A mutation that does not trip proves nothing: confirm the mutated field is one the harness reads.
- Check gh auth (atulsrivas1) before every push.
