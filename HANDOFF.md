# Handoff (keep under 60 lines; update after every merge)

Updated 2026-10-23. Read this, then STATUS.md, DECISIONS.md, the coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md).

## Where we are: R26 released 2026-10-23 as unqualified prerelease (tag r26-variants1-prerelease, three repos)
- Merged: option-features #12 #15 (clarifications) #16 #18 #20 #22 (decisions) #17 (skill) #19 #21 (library); option-feature-io #7 (codec, stages 1-4/9); option-feature-workers #7 (checkpoint/restore, DuckDB storage, replay). Evidence: docs/r26-variants/R26_EVIDENCE.md; retro: docs/knowledge/RETRO_R26.md (PR 23 pending until merged).
- Manual runs: owned frozen rows pass per layer (workers 76/76; I/O 0 mismatches); 28 fixture-defect rows excluded pending a corrected candidate5 (18 library triage, 10 I/O listed in DECISIONS; the 3 joint-output rows make it 13 for I/O).
- Private fixtures/evidence: owner's work folder Documents/ChatGPT/Equity Features/work/r26-20261021 (candidate4 in variant-full-fixtures-completion4; freeze proposal + Addendum 1; reviews).

## Next
1. Candidate5: regenerate the 28 excluded fixture rows (representative rows predate the quote-selector clarification) and replay all layers.
2. Contract clarifications still needed: field_set missing/extra pointer, rolling envelope member ids, DailyCore excluded-candidate Results and scope pointers, restore i>0, PR 12 lane control/overflow placement, A>K temporal_cut order; N4 schema notes (bp vs bits, monetary_basis reverse direction).
3. Close: Windows qualification, browser demo, owner acceptance; apply retro changes in the next release's first brief.

## Owner items (parked)
- Decide what the browser demo shows for a library release; when to run Windows qualification; release acceptance.
- Review decisions marked "pending owner review" in DECISIONS.md and the coordinator rulings (work/.../COORDINATOR_RULINGS_20261022.md).
- Leftover worktrees under .claude/worktrees in the three repos can be removed (removal needs OK or manual cleanup).

## Gotchas
- Controller runs need absolute paths; contained run via python -I -B, never reuse a failed attempt dir.
- Add .gitignore for bytecode before any run; commit-then-remove leaks into branch history.
- Fixture-vs-contract triage before bending code; Sonnet (not Haiku) for storage/restore work.
