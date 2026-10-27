# Handoff (keep under 60 lines; update after every merge)

Updated 2026-10-27. Read this, then STATUS.md, DECISIONS.md, the coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md).

## Where we are: R26 prerelease out (r26-variants1-prerelease); candidate6 frozen as a post-release candidate (2026-10-27)
- Freeze record: docs/r26-variants/CANDIDATE6_FREEZE_RECORD.md (supersedes the candidate5 record): 2573 rows in files, 12 excluded in the files, 9 held B rows tagged out by id, frozen 2552. Replay of record at ed3597d (PRs 30/31 merged): all layers pass, exit 0.
- Flagged frozen-subject-to-regeneration: 10 rows and 9 graphs (zero-price, tie variants, lane-by-interval, accepted-restore). Masked and excluded: 2 F4 rows and 4 N4-roll-unresolved rows plus 6 graphs.
- Gaps G1 to G8 are in the record; graph evidence is digest-level only. Rulings decided, pending owner review.
- R26 evidence: docs/r26-variants/R26_EVIDENCE.md; retro: docs/knowledge/RETRO_R26.md. Private work: Documents/ChatGPT/Equity Features/work/r26-20261027.

## Next
1. PO items P1 (-0.0 canonicalization or reject), P2 (F4 excluded_ids wording), P3 (N4 no-r envelope wording).
2. Private boundary text for the 9 held B rows (assumption 2); they stay tagged out until found.
3. Contract wording for excluded_ids so the 6 masked rows can be unmasked and regenerated.
4. Workers restore code gaps (missing-stream, CP3 temporal order, K-regression placement, suffix checks): fixtures now exist or need authoring.
5. Library field_set pointer code gap.
6. Windows qualification (backlog, not a gate).
7. Browser demo: stored-output DuckDB with provenance.
8. Release notes must list flags, exclusions and the controller's removed review gate.

## Owner items (parked)
- Release acceptance; review of decisions marked "pending owner review".
- Leftover worktrees under .claude/worktrees in the three repos can be removed (needs OK or manual cleanup).

## Gotchas
- Controller runs need absolute paths; contained run via python -I -B, never reuse a failed attempt dir.
- Add .gitignore for bytecode before any run; commit-then-remove leaks into branch history.
- Fixture-vs-contract triage before bending code; Sonnet (not Haiku) for storage/restore work.
