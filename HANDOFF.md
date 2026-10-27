# Handoff (keep under 60 lines; update after every merge)

Updated 2026-10-27. Read this, then STATUS.md, DECISIONS.md, the coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md).

## Where we are: R26 prerelease out; candidate9 recorded as a post-release candidate for the next release (2026-10-27)
- Freeze record: docs/r26-variants/CANDIDATE9_FREEZE_RECORD.md (supersedes candidate8): 2594 rows in files (2292 + 302 graphs), nothing excluded, frozen 2594. Missing-stream row unmasked (Q3 inferred); 9 held B rows returned under assumption 2 (PO product ruling). Replay v6 at option-features 6a81e65 / io e156963 / workers 8795f3e: all layers pass, exit 0; workers 32 partial pinned after a first run (independent recompute owed).
- Flagged frozen-subject-to-regeneration: 49 rows and 22 graphs. Gaps G1 to G21 in the record; graph evidence is digest-level only. Rulings decided, pending owner review.
- Merged: option-features PRs 30-31, 33-39, io PR 8, workers PRs 8-9. PR 39 text still reads "proposed" though PO ratified (docs edit pending).
- R26 evidence: docs/r26-variants/R26_EVIDENCE.md; retro: docs/knowledge/RETRO_R26.md. Private work: Documents/ChatGPT/Equity Features/work/r26-20261027 (FREEZE_PROPOSAL_CANDIDATE9.md).

## Next
1. Two-control fixtures (expected root in control 0 only; parent/flow and span; must fail on current code), then fix flow.py:42 and span.py:68 in a separate PR (frozen rows byte-identical).
2. Direct-root /checkpoint and /config rows (root strings need PO/workers confirmation); F4 unresolved-root and rollup-wider rows.
3. Windows qualification (needs owner permission for downloads), browser demo, release notes (record section 9).
4. Q4 and the narrower-rollup clause stay held.

## Owner items (parked)
- Release acceptance; review of decisions marked "pending owner review".
- Permission for downloads (Windows qualification).
- Leftover worktrees under .claude/worktrees in the three repos can be removed (needs OK or manual cleanup).

## Gotchas
- Controller runs need absolute paths; contained run via python -I -B, never reuse a failed attempt dir.
- Add .gitignore for bytecode before any run; commit-then-remove leaks into branch history.
- Fixture-vs-contract triage before bending code; Sonnet (not Haiku) for storage/restore work.
- Pinned counts learned from a first run (workers partial 32) must be recomputed from fixtures by a reviewer.
