# Handoff (keep under 60 lines; update after every merge)

Updated 2026-10-27. Read this, then STATUS.md, DECISIONS.md, the coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md).

## Where we are: R26 prerelease out; candidate11 proposed as the post-release candidate (2026-10-27)
- Freeze record: docs/r26-variants/CANDIDATE11_FREEZE_RECORD.md (supersedes candidate9; its PR is not final until merged after the independent freeze review, NOT yet done): 2608 rows in files (2300 + 308 graphs), nothing excluded, frozen 2608 (candidate9 + 14 = 8 rows + 6 graphs). index.json 6f6e0f0e...
- Replay v8 at option-features 4e82136 / io e156963 / workers 8795f3e: library 403/403, N4 49/49, graphs 304/304, I/O 1764/1764, workers 85/85 (32 partial); all exit 0, no expected-to-fail. Audits candidate10 and candidate11: approve.
- Two-control latent defect fixed (PR 42); candidate9 rows unchanged. Demo merged (PR 41).
- Flagged frozen-subject-to-regeneration: 57 rows and 28 graphs. Gaps G1 to G24 in the record. Rulings decided, pending owner review.
- Private work: Documents/ChatGPT/Equity Features/work/r26-20261027 (FREEZE_PROPOSAL_CANDIDATE11.md).

## Next
1. Independent freeze review of FREEZE_PROPOSAL_CANDIDATE11, then coordinator freeze and merge of the record PR.
2. Ruling needed: integer-op incomplete-capture sentence (integer_weights and count Metrics statuses); then re-author the rollup-wider row (c-domain, c-completeness are untested until then).
3. Ruling needed: /checkpoint and /config missing-member sentences (stage-3 field_set before CP0-CP2 / config checks); then author missing-member rows.
4. Q4 (suffix checks) and the narrower-rollup clause stay held (PO question needed to unhold).
5. Release notes (record section 8 items; filter re-issued for candidate11); qualified-release criteria from PO_DECISION_CANDIDATE9: Windows qualification passes, demo works, two-control fix landed (done), /checkpoint and /config coverage or scoped out, no flagged id undisclosed, owner accepts. Stay a prerelease until then.
6. Regenerate the 18 assumption-2 flagged rows/graphs plus the 9 held rows (largest flagged block).

## Owner items (parked)
- Permission for PyPI downloads (python-flint, duckdb, setuptools wheels) for Windows qualification; qualification scope.
- Release acceptance and the qualified-vs-prerelease label.
- Review of decisions marked "pending owner review".
- Leftover worktrees under .claude/worktrees in the three repos can be removed (needs OK or manual cleanup).

## Gotchas
- Controller runs need absolute paths; contained run via python -I -B, never reuse a failed attempt dir.
- Add .gitignore for bytecode before any run; commit-then-remove leaks into branch history.
- Fixture-vs-contract triage before bending code; Sonnet (not Haiku) for storage/restore work.
- Pinned counts learned from a first run (workers partial 32) must be recomputed by a reviewer (done for 32 by the candidate9 freeze review).
- Check gh auth (atulsrivas1) before every push.
