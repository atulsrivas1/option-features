# Handoff (keep under 60 lines; update after every merge)

Updated 2026-10-27. Read this, then STATUS.md, DECISIONS.md, the coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md).

## Where we are: R26 prerelease out (r26-variants1-prerelease); candidate5 phase A frozen as a post-release candidate (2026-10-27)
- Freeze record: docs/r26-variants/CANDIDATE5_FREEZE_RECORD.md (2542 of 2554 rows, 12 excluded, 13-id regeneration watch list, gaps G1 to G6). PO accepted with conditions; independent review approve-with-conditions. Rulings decided, pending owner review.
- Open code gaps: workers validate_restore (missing-stream, request immutability, CP3 temporal order, K-regression placement, suffix checks), library field_set pointer; fixtures first. Nothing new released.
- R26 evidence: docs/r26-variants/R26_EVIDENCE.md; retro: docs/knowledge/RETRO_R26.md. Private work: owner's Documents/ChatGPT/Equity Features/work/r26-20261021 and r26-20261027 (candidate5).

## Next
1. Contract clarifications for the regeneration-watch rows (POST_R26 2.4, Binding/context, FEFF pointer).
2. Phase B fixtures for the S2 rulings.
3. Workers and N4 harness hardening (G6 exit codes, phase exposure, nullability).
4. Windows qualification (backlog, not a gate).
5. Browser demo: stored-output DuckDB with provenance.
6. Release notes must list the watch list and the controller's removed review gate.

## Owner items (parked)
- Release acceptance.
- Review decisions marked "pending owner review" in DECISIONS.md and the coordinator rulings (work/.../COORDINATOR_RULINGS_20261022.md).
- Leftover worktrees under .claude/worktrees in the three repos can be removed (removal needs OK or manual cleanup).

## Gotchas
- Controller runs need absolute paths; contained run via python -I -B, never reuse a failed attempt dir.
- Add .gitignore for bytecode before any run; commit-then-remove leaks into branch history.
- Fixture-vs-contract triage before bending code; Sonnet (not Haiku) for storage/restore work.
