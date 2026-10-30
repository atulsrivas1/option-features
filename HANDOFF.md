# Handoff (keep under 60 lines; update after every merge)
Updated 2026-10-29 (M1 CLOSED, see docs/M1_CLOSE.md; P1 DONE, 0.2.0a1 on main, merge 62a178c; candidate15 frozen, CANDIDATE15_FREEZE_RECORD.md: 2666 of 2668; R27 evidence recorded in RELEASE_NOTES section 16 (T8 draft, docs review and PO accept pending): harness v15.1 is the gate harness, label extended to candidate15 on Windows, Linux evidence on WSL2 is not a label; PRERELEASE). Read this, then STATUS.md, DECISIONS.md, the coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md).

## PO release plan V3 (2026-10-29, authoritative; DECISIONS.md has the entries)
- Main goal (owner): performance. Use cores, memory and caches fully to calculate faster without breaking correctness. B1-B12 are hard acceptance gates (synthetic-size stage until RQ; label "synthetic workload, relative engineering budget"). Developer designs for multi-core, vectorised/batched calculation, caching, minimal allocation; Tester authors independent perf, parallelism-determinism, batched-vs-single, cache and memory fixtures.
- Order: R27 done, P1 (0.2.0a1), M1 (was R28b, OC5/OC6/ATM IV/30-day IV), M2 flow, M3 surface, M4 positioning, M5 scanners, RQ last. R28a is DROPPED; ALL adapter/Databento/network work only in the final RQ release.
- Label through M5, verbatim in every release note: "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12". Rules: docs/RELEASE_NOTE_TEMPLATE.md; docs reviewer greps the forbidden list as a gate. Stays PRERELEASE.
- Performance rulings (DECISIONS.md, D4 amended): opt-in process-pool runner (opt-in, default single-process) = LAST M1 story (workers <= min(cores, RAM/B9), merge by unit key); solver stages: Fraction hoist, float-filtered bisection with certified fallback and proven bound, Stage 0 then Stage 1 both in M1; Newton only as verified bracket seed; true-value change = separate PO ruling and candidate bump; governing B7 = 170/240 min; Linux process check, not claimed; eight acceptance tests authored by the independent Tester. Owner-only: python-flint scratch venv approval, B7 machine cores/RAM.
- P1 and M1 fixtures authored independently (Tester, no implementation read), reviewed by an independent reviewer; interim rulings on design requests 1-3 (option A each) are pending design ratification; a changed answer redoes fixtures. M1 code starts when P1 is accepted. P1 bump plan: docs/P1_VERSION_BUMP_PLAN.md.

## M1 status (2026-10-29): CLOSED; Stage 0, 1, 2, stories A and B, runner PR 72 all merged
- M2-G0 (PR m2/g0-full-output-b6, Developer evidence only, Tester must re-run): full-output B6 1 worker compute-only p50 2.41 / p95 2.66 s (with sign_aggregate) vs 5 s budget (met); IV 57 percent, signing 27 percent; matrix identical at 1/2/4/24 workers; data docs/m2/M2_G0_BENCH.json, DECISIONS.md last entry.
- Runner (m1/process-pool-runner, Developer evidence only; Tester re-runs determinism, kill, scaling, platform replays; PO accepts): tools/m1_runner/ (opt-in, default single-process; 1 worker = in-process reference), tools/m1_runner_bench.py, docs/M1_RUNNER.md, docs/m1/M1_RUNNER_BENCH.json, tests/m1/test_runner.py (29 tests, ~41 s).
- Measured post-Stage-2 (synthetic workload, relative engineering budget; 2x Xeon 8160, 48 physical / 96 logical, 254 GiB; cap min(physical cores, 0.5 x RAM / 2 GB) = 48): identical hashes at 1, 2, 4, 48 workers x 3, batches, orders; B6 compute p95 1.53 s (1 worker), 1.63 s per unit at 48; B7 1.78 min at 48 workers, 2.38 min at 24 (budget 170 min). Details in DECISIONS.md.
- Older story A/B/history lines were moved verbatim to DECISIONS.md (entry "Restored verbatim from HANDOFF.md", runner PR). PO rulings on PR 72 applied (cap, B9 fact, perf_sut deferred); Tester drives the CLI.

## P1 (0.2.0a1): DONE, PO accepted 2026-10-29 (PR 63, merge 62a178c on main)
- Accepted after independent code review (approve-with-conditions, then delta re-check approve) and an independent Tester re-run with python-flint 0.9.0 (DECISIONS.md, last entries). Interim design rulings stay pending ratification; wire exposure of quotes/windows/shares is a candidate16 item.
- M1 CLOSED 2026-10-29 (accepted as built, prerelease, synthetic data; docs/M1_CLOSE.md has built-vs-scope, B2-B7 numbers, risks, M2 proposal): Stage 0/1/2, OC5/OC6, chain IV, opt-in, default single-process runner all merged. Risks: thin B2/B3 margin on string path, input synthesis 23% CPU at 48 workers (idea candidate), full-output B6 run still to do. NEXT: M2 flow completion (capability matrix and gate budgets first, then independent fixtures, then code). Owner goal: performance. Open: tag and wheel rebuild, owner items (python-flint scratch venv, B7 machine).

## R26: stays PRERELEASE (Windows x64 cp312); notes docs/r26-variants/RELEASE_NOTES.md, scoped label in RELEASE_NOTES section 15

## M1 Stage 2 (PR 71): merged; independent Tester re-run done (details in DECISIONS.md). B6 IV part about 1.4 s p50 compute-only.

- M2 (2026-10-29): docs/m2 merged (PR 75); PO-M2-AMB rulings (19 ambiguities) in docs PR on branch docs/m2-amb-rulings (not merged). Next: Tester fixtures, M2-G0 first task gate, then code.

- M2-GRID rulings (2026-10-30): docs PR on branch docs/m2-grid-rulings (not merged); IO contract section 9. PR 79 adds section 8.

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
