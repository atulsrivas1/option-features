# Handoff (keep under 60 lines; update after every merge)

Updated 2026-10-23. Read this, then STATUS.md, DECISIONS.md, the release coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md, owner-created).

## Where we are: R26 option flow (unreleased), fixture phase
- Canonical roadmap/stories: equity-features issue 533 (R26 epic); draft PRs option-features #9, option-feature-io #5, option-feature-workers #5 (native 44-output candidate; stale, being reworked). EQ188/EQ189/EQ215 In progress (variant rework), EQ191/EQ192 Test, EQ190/EQ193 gated on real EQ153/EQ158.
- Merged here: #10 (remove AGENTS/README), #11 (PROJECT-MEMORY/STATUS/DECISIONS), #12 (fixture-completion proposals: partition key, group reason, definition-basis pointer), #13 (status).
- Private fixture source and evidence live outside any repo, in the owner's old workspace folder (Documents/ChatGPT/Equity Features/work/r26-20261021 under the owner's home; confirm the location with the owner if it has moved): variant-full-fixtures-completion3 (B3 153, F3 174, F4 45, W3 1803 cases; all reviewed, source-only).
- Contained generation attempt 3 PASSED (2,466 rows, unqualified candidate); independent mechanical audit run, 9 failing checks all triaged as script limits/intentional (see COMPLETION3_AUDIT_ATTEMPT1.md and COMPLETION3_GENERATION_ATTEMPT1_FAILURE.md in work/r26-20261021).

## Done 2026-10-23 (this session)
- Steps 1-2 DONE: N4 fixtures (variant-full-fixtures-completion4/obligations4_cases.py, 63 cases, reviews INDEPENDENT_N4_FIXTURE_REVIEW_01/02), manifest COMPLETION4_SOURCE_MANIFEST1.json, controller review, contained attempt 4 PASSED (2,554 rows, candidate4), audit audit-completion4-attempt1: 176 checks, 4 failing = auditor limits (COMPLETION4_AUDIT_ATTEMPT1.md). Run controller with ABSOLUTE paths.
- Open contract gaps from N4 (OBLIGATIONS4_STATUS.md): rolling envelope member ids; DailyCore excluded candidate Results and incompatible-scope pointers; restore within-collection i>0; PR 12 lane control/overflow placement. These need contract text before freeze (4 N4 rolling cases stay unfrozen).

## Next (in order)
3. Public copies of the edited clarifications (private drafts in variant-boundary-draft3) need an option-features docs PR + fresh reviewer; PR 12 text is the template.
4. Coordinator freeze (after independent review; the owner may revise the pending rulings), then three fresh layer workers (library/I-O/workers) with path boundaries; R26 PRs #9/#5/#5 are stale.

## Owner items (parked)
- Coordinator rulings pending owner review (work/r26-20261021/COORDINATOR_RULINGS_20261022.md): partition by complete definition; group reason premium_unavailable; rolling cases unfrozen until clarification accepted; observed_series incomplete-slot is a contract gap.
- Evidence comment posted on equity-features#533 with owner OK (https://github.com/atulsrivas1/equity-features/issues/533#issuecomment-6360812355).

## Gotchas
- Controller: python -I -B, no PYTHONPATH, new output dir each attempt; after a failure move generated-completion-candidate3 aside before rerun. Lease file must read released.
- Authors/reviewers are static: no Python execution; real defects only surface in contained runs (found 2 so far).
- Source hashes pinned in COMPLETION3_SOURCE_MANIFEST1.json; any edit to fixture source or contracts requires re-pin and a new controller review JSON.
- The skill text mentions a root HANDOFF.md and no-CI manual runs; docs/SESSION_HANDOFF.md is the older long R25/R26 history (read only if needed).
