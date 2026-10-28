# Handoff (keep under 60 lines; update after every merge)

Updated 2026-10-27. Read this, then STATUS.md, DECISIONS.md, the coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md).

## Where we are: R26 prerelease out; candidate12 proposed as the post-release candidate (2026-10-27)
- Freeze record: docs/r26-variants/CANDIDATE12_FREEZE_RECORD.md (supersedes candidate11; its PR is not final until merged; independent freeze review done: approve-with-conditions, conditions applied, independent re-run of the five v9 harnesses matched; audit approve): 2614 rows in files (2304 + 310 graphs), nothing excluded, frozen 2614 (candidate11 + 6 = 4 rows + 2 graphs). index.json 4e2f6428...
- Replay v9 at option-features 0f37caa / io e156963 / workers 8795f3e: library 405/405 (+2 skipped), N4 49/49, graphs 306/306, I/O 1764/1764, workers 87/87 (32 partial); all exit 0, no expected-to-fail. Mutation proof for all five harnesses (first graph mutation redone).
- Integer-op incomplete capture and /checkpoint, /config shape order ratified (inferred); rollup rows and missing-member rows now authored. Two-control fix (PR 42) and demo (PR 41, synthetic-only) merged.
- Flagged frozen-subject-to-regeneration: 61 rows and 30 graphs. Gaps G1 to G26 in the record. Rulings decided, pending owner review.

- Windows qualification (2026-10-27): PO decision PRERELEASE, Windows x64 cp312 PARTIALLY qualified, not qualified (docs/r26-variants/WINDOWS_PARTIAL_QUALIFICATION_RECORD.md; must-fix list there; python-flint LGPL-3.0-or-later needs a licence review). Release notes must include the candidate12 flagged rows and gaps. Decided, pending owner review.

## Next
OWNER ITEMS first (parked until the owner returns):
1. PyPI wheel permission for Windows qualification: python-flint==0.9.0, duckdb==1.5.6, setuptools==80.9.0, win_amd64 cp312 (sizes unverified).
2. Qualification scope.
3. Release acceptance and the qualified-vs-prerelease label. Criteria: Windows qualification passes; demo works (merged, synthetic-only); two-control fix landed (done); /checkpoint and /config coverage (done) or scoped out; every flagged id disclosed; owner accepts.
4. Review of the "decided, pending owner review" decisions (assumption 2, Q3 and field_set inference, F4 ratifications, Clarification 4 and Addendum 5 inferences, controller no-review deviation, candidate12 supersession).
5. Worktree cleanup (.claude/worktrees in the three repos, including s24-freeze12 after merge).
Team items:
6. Independent freeze review of candidate12: DONE (approve-with-conditions, conditions applied). Next: coordinator freeze and merge of the record PR.
7. Q4 (suffix checks) and the narrower-rollup clause stay held (PO question needed to unhold).
8. Release notes finalization (record section 8 items; filter re-issued for candidate12; draft kept in the private work folder).
9. Regenerate the flagged rows, assumption-2 block first (18 rows/graphs plus the 9 held rows).

## Gotchas
- Controller runs need absolute paths; contained run via python -I -B, never reuse a failed attempt dir.
- Add .gitignore for bytecode before any run; commit-then-remove leaks into branch history.
- Fixture-vs-contract triage before bending code; Sonnet (not Haiku) for storage/restore work.
- Pinned counts learned from a first run (workers partial 32) must be recomputed by a reviewer.
- A mutation that does not trip proves nothing: confirm the mutated field is one the harness reads.
- Check gh auth (atulsrivas1) before every push.
