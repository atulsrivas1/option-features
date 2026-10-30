# HANDOFF.md archive 2 (verbatim, as of 2026-10-30, before the post-M3a-fixtures rewrite)

Date: 2026-10-30. Archived verbatim. The live HANDOFF.md was rewritten after the M3a fixtures merge (PR 109 at 87992c6); this file keeps the previous text unchanged (the earlier one is docs/decisions/2026-10-30-handoff-archive.md). This file is also the decision record of the docs PR that rewrites HANDOFF.md and updates the Merged and Open PRs lines of docs/FEATURE_STATUS.md. Decided by the coordinator.

---

# Handoff (keep under 60 lines; edited only by the PO or the release closer)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Updated 2026-10-30 (session stop at the owner's request). Previous text is archived verbatim in docs/decisions/2026-10-30-handoff-archive.md. Read this, then docs/FEATURE_STATUS.md (live tracker), docs/decisions/ (README, newest first), DECISIONS.md (frozen log plus index), docs/TEAM_MEETING_2026-10-30.md. Rules: independent author, reviewer and Tester roles; two review rounds (a third only for a correctness defect); one ruling batch before fixtures; fresh origin/main checkouts for authors and reviewers; merge-order rule (fixtures after the code they need; main never red); run `gh auth switch --user atulsrivas1` and re-verify the active account before EVERY push or merge (it flips back); verify pushes with git ls-remote; kill only your own process ids; no deletions without the owner. Owner goals: performance (budgets are hard gates), all features first on synthetic data, adapter work last (RQ).

## State on main
- Done and accepted: R27, P1 (0.2.0a1), M1 (closed, docs/M1_CLOSE.md), M2 built (stories A and B, store, type-first rules, 570 + 298 fixture rows, M2-G0 2.3-2.7 s against 5 s), tracker (PR 85, 86, 100), CI (PR 105: windows-2022, CPython 3.12, six suites plus the tracker test, hash-pinned wheels, run 41083403896 green), M3a docs (matrix, budgets, fixture requirements, contract skeleton, ruling pass: PR 101, 103), python-flint scratch measurement (PR 102), team meeting (PR 99).
- M2 is not closed: the close record is not written and the runner integration is parked (below).

## Open PRs at stop (verify with gh pr list)
- PR 104 (docs/m3a-rulings-2, head b157db8b, mergeable): M3a rulings R-103..R-161, contract section 8 shapes, owner decisions 2-5, store budget 768 MB. The independent bounded review of the LATEST head was requested (reviewer a95725bae60b926a0) and NOT delivered at stop: obtain it (or redo) before merging. Items already ruled in R-141..R-150: frame status rule, null value for M3A-0, R-128/R-145 wording against inverse.py, metric names.
- PR 106 (docs/tracker-ci-m3a-decisions, head 58e88a5a, mergeable): tracker CI status and owner decisions 1-5 final. Needs a bounded review and merge, after PR 104.

## Owner decisions (FINAL, 2026-10-30)
1 V21 included in M3a. 2 V3 and V4 implement BOTH forms (iv_form atm|30d, default atm; ATM = M1 atm_iv of the nearest eligible expiry). 3 delta_convention spot|forward (default spot; metrics skew25 and skew25_fwd; convention_mismatch is structural). 4 a percentile over a constant history is unavailable (zero_range_history). 5 the scalar baseline allows partial history (missing days skipped, at least 20 sessions). Earlier approvals: M3-M5 split into M3a-c, M4a-b, M5a-b; two-round review cap; one decision file per PR; CI merged; python-flint scratch venv (measurement only).

## M3a fixture sets (scratchpad m3a-fixtures/author1..4; NOT committed; independent authors; no oracle recheck done; none run against code)
- Folder: C:\Users\MONIKA~1\AppData\Local\Temp\claude\C--Atul-Claude\0e5f6c2d-0322-4065-927e-a3702f72ac99\scratchpad\m3a-fixtures\ ; each set has a MANIFEST.sha256 listing explicit files; scratch files stay out of PRs.
- author1 (surface frame, 25-delta, tenors, coverage, American labels): about 250-260 rows; the update with Q-13 solver-bound rows, coverage-isolating rows and both delta conventions was IN FLIGHT at stop (agent a564ab1c1e27d96a7).
- author2 (V1, V3, V9, history reuse, units): 281 rows at last report; update for D17 positions and convention_mismatch only at request/view read (not at append) in flight (agent ac65429228ee51afc).
- author3 (V4-V8, V10, V11, V21): 374 rows, 48 mutants, owner decisions 2 and 3 applied; bounded oracle recheck not yet requested (agent a9afaae804a11428f; round 1 review by a0138db344f127028 closed).
- author4 (structural, lane, perf): 148 structural + 42 aux + 6 lane + 71 resource rows, 49 mutants; dropping the 4 DCP2 rows at stop (agent a24acc0ffe09b2bf4).

## Parked
- M2 runner integration: branch m2/runner-integration (pushed, no PR, ls-remote 265fb7e6); figures in docs/TEAM_MEETING_2026-10-30.md are unverified developer evidence; open rulings: rank fixture 7,340 versus 7,440 (library is right), S02 unit-sharded by default, N above 24 for B12 informational.
- Totality follow-ups: story A check_prints raises on hostile lists (tracked); contracts map trusted and adapter-validated; f17 column entry points internal.
- Performance candidates: F7 density-adaptive windows, F17 sparse reads, lazy ring/record creation, input synthesis sharing, Newton seed (deferred), perf_sut bindings B1-B10. CI follow-ups: pin actions by commit SHA, pip bootstrap unpinned, no Linux job (no recorded hash).
- Scratch worktrees (owner-only deletion): wt-ci (holds the CI branch), wt-v3, and many scratchpad folders.

## Pending owner questions
Linux evidence before RQ (WSL has no bash here); docs-only PR roles (full independence or relaxed); approval of a one-time scratch and worktree cleanup; B7 reference machine (2 x Xeon 8160, 48 physical cores, 254 GiB); design-session ratification of interim rulings (requests 1-3, 6, 8, DR-M2-1, the M2 AMB set, M3a design-silent rulings); go or no-go for the Developer M3a code after the fixtures merge.

## Next (in order)
1. Get the PR 104 verdict on the latest head, fix, merge; bounded review and merge PR 106.
2. Authors 1-4 finish the in-flight updates; bounded oracle recheck per set with fresh checkouts (different reviewers than the authors: Testers a628f204e8d54dbfc, a88a5239b25cb607a, a0138db344f127028, a3beda279317b791d; oracle reviewer a95725bae60b926a0); round 2 only for correctness defects.
3. Commit the fixtures to qualification/synthetic/m3a/ by explicit file lists (LF, MANIFEST), PO acceptance, merge; update docs/FEATURE_STATUS.md; run the tracker test.
4. Start M3a Developer code (pure modules beside chainiv: surface frame, 25-delta, tenors, V rows, history reuse via the M2 store with k up to 252, scalar_baseline, same_minute_column): failing-first fixtures, mutation tools, M3A-G0 and the single-worker gates, Tester re-runs, runner reuse. Then the M3a close record; M3b, M3c, M4a-b, M5a-b, RQ later.
