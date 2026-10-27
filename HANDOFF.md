# Handoff (keep under 60 lines; update after every merge)

Updated 2026-10-27. Read this, then STATUS.md, DECISIONS.md, the coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md).

## Where we are: R26 prerelease out (r26-variants1-prerelease); S1 (PR 25) and S2 (PR 26) merged; candidate5 phase A awaiting freeze (2026-10-27)
- Candidate5 source approved by an independent reviewer (review of 2026-10-27; 30 of 31 rows fixed, 2 F4 undetermined); contained run passed (2554 rows, 2521 identical, 33 changed). Replay: library 393/393, I/O 1757/1757, workers 76/76. Audit verdict approve-with-conditions; harnesses unreviewed; freeze proposal pending.
- Open code gaps: workers validate_restore (missing-stream, request immutability, CP3 temporal order, K-regression placement, suffix checks), library field_set pointer; fixtures first. Nothing new released.
- R26 evidence: docs/r26-variants/R26_EVIDENCE.md; retro: docs/knowledge/RETRO_R26.md. Private work: owner's Documents/ChatGPT/Equity Features/work/r26-20261021 and r26-20261027 (candidate5).

## Next
1. Freeze review of candidate5.
2. Phase B fixtures for the S2 rulings.
3. Workers hardening (validate_restore, field_set pointer).
4. Windows qualification (backlog, not a gate).
5. Browser demo: stored-output DuckDB with provenance.

## Owner items (parked)
- Release acceptance.
- Review decisions marked "pending owner review" in DECISIONS.md and the coordinator rulings (work/.../COORDINATOR_RULINGS_20261022.md).
- Leftover worktrees under .claude/worktrees in the three repos can be removed (removal needs OK or manual cleanup).

## Gotchas
- Controller runs need absolute paths; contained run via python -I -B, never reuse a failed attempt dir.
- Add .gitignore for bytecode before any run; commit-then-remove leaks into branch history.
- Fixture-vs-contract triage before bending code; Sonnet (not Haiku) for storage/restore work.
