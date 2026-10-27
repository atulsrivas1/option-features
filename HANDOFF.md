# Handoff (keep under 60 lines; update after every merge)

Updated 2026-10-27. Read this, then STATUS.md, DECISIONS.md, the coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md).

## Where we are: R26 prerelease out (r26-variants1-prerelease); candidate6 frozen as a post-release candidate (2026-10-27)
- Freeze record: docs/r26-variants/CANDIDATE6_FREEZE_RECORD.md (supersedes the candidate5 record): 2573 rows in files, 12 excluded in the files, 9 held B rows tagged out by id, frozen 2552. Replay of record at ed3597d (PRs 30/31 merged): all layers pass, exit 0.
- Flagged frozen-subject-to-regeneration: 19 rows and 18 graphs (10 new rows with 9 graphs, plus 9 baseline B3 rows with 9 graphs). Masked and excluded: 2 F4 rows and 4 N4-roll-unresolved rows plus 6 graphs.
- Gaps G1 to G8 are in the record; graph evidence is digest-level only. Rulings decided, pending owner review.
- R26 evidence: docs/r26-variants/R26_EVIDENCE.md; retro: docs/knowledge/RETRO_R26.md. Private work: Documents/ChatGPT/Equity Features/work/r26-20261027.

## Next (PO priority)
1. Independent docs review of the P2/P3 ruling (PO_RULING_REPRESENTATION), then unmask and regenerate the 6 rows and 6 graphs.
2. Workers restore code gaps (missing-stream, CP3 temporal order, K-regression placement, suffix checks) plus one fixture row pinning -0.0 rejected (stage 4 invalid_scalar). P1 decided: -0.0 rejected permanently for variants1; line 322 conflict, if any, goes to the variants2 backlog.
3. field_set pointer: contract first, then code.
4. Private boundary text for the 9 held B rows by sprint end (9 baseline B3 rows share assumption 2, flagged).
5. Windows qualification, then browser demo (stored-output DuckDB with provenance).
6. Release notes: consumer filter as runnable code, the 19 flagged ids with rulings, controller's missing independent review.

## Owner items (parked)
- Release acceptance; review of decisions marked "pending owner review".
- Leftover worktrees under .claude/worktrees in the three repos can be removed (needs OK or manual cleanup).

## Gotchas
- Controller runs need absolute paths; contained run via python -I -B, never reuse a failed attempt dir.
- Add .gitignore for bytecode before any run; commit-then-remove leaks into branch history.
- Fixture-vs-contract triage before bending code; Sonnet (not Haiku) for storage/restore work.
