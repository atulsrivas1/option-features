# Handoff (keep under 60 lines; update after every merge)

Updated 2026-10-27. Read this, then STATUS.md, DECISIONS.md, the coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md).

## Where we are: R26 prerelease out; candidate8 frozen as a post-release candidate for the next release (2026-10-27)
- Freeze record: docs/r26-variants/CANDIDATE8_FREEZE_RECORD.md (supersedes candidate6): 2585 rows in files, 1 excluded (missing-stream row), 9 held B rows tagged out by id, frozen 2575. Replay of record REPLAY_V5 at option-features 9ecd68e: all layers pass, exit 0.
- Flagged frozen-subject-to-regeneration: 32 rows and 20 graphs. Gaps G1 to G14 in the record; graph evidence is digest-level only. Rulings decided, pending owner review.
- Merged: PRs 30-31, 33-37 (PR 37 text still proposed; Q3/Q4 not ratified), io PR 8, workers PR 8.
- R26 evidence: docs/r26-variants/R26_EVIDENCE.md; retro: docs/knowledge/RETRO_R26.md. Private work: Documents/ChatGPT/Equity Features/work/r26-20261027.

## Next
1. Workers code: Q3 (checkpoint_cut_mismatch at /request/cut_cursors) and A>K before merge (in progress).
2. Fixtures: missing-stream unmask, A>K plus merge, the 9 held B rows (assumption 2 now a PO product ruling), direct-API field_set, F4/rolling combinations.
3. Replay v6 plus independent audit of the new rows.
4. Windows qualification, browser demo, release notes (items in record section 10).

## Owner items (parked)
- Release acceptance; review of decisions marked "pending owner review".
- Leftover worktrees under .claude/worktrees in the three repos can be removed (needs OK or manual cleanup).

## Gotchas
- Controller runs need absolute paths; contained run via python -I -B, never reuse a failed attempt dir.
- Add .gitignore for bytecode before any run; commit-then-remove leaks into branch history.
- Fixture-vs-contract triage before bending code; Sonnet (not Haiku) for storage/restore work.
