# 2026-10-30: process rules and the M3, M4, M5 split (owner approved the meeting proposals; recorded by the Auditor on PO direction)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

## Decisions
1. Release split. M3, M4 and M5 of PO release plan V3 are split: M3a (surface, term structure, skew: V1, V3-V10, with history reuse from the M2 store for the percentile-of-history and change-since-prior-session rows V1, V3, V4, V7, V9, V10; entry gate includes the M2 store, merged in PR 80), M3b (realized-volatility join, daily-bar based, without history reuse: V11-V15), M3c (frame builder without presets: V16-V22; assignment proposed, V3 names no release for V16-V22), M4a (open-interest outputs), M4b (exposure and dealer-sign convention, labelled modeled), M5a (shadow scanner presets, D6), M5b (equity-side join, including F8 and F11). Order: M2, M3a, M3b, M3c, M4a, M4b, M5a, M5b, RQ. RQ stays last and unchanged. The split of PO rows between M4a and M4b (open-interest rows PO9, PO12-PO14, PO17-PO19 to M4a; exposure rows PO1-PO8, PO10, PO11, PO15, PO16 to M4b) is a proposal in docs/FEATURE_STATUS.md.
2. Review cap. Two review rounds per PR; a third round only for a correctness defect; everything else becomes a tracked follow-up. A bounded recheck lists exactly the items to be rechecked.
3. Design ambiguities are ruled in ONE batch (a ruling list with PO recommendations) BEFORE fixture authors start.
4. Fresh checkout. Authors and reviewers always work from a fresh origin/main checkout (git fetch, then a worktree) before starting.
5. Decision records. One file per PR under docs/decisions/ (see README.md there); DECISIONS.md is a frozen log through 2026-10-30 plus an index; HANDOFF.md keeps only current state, under 60 lines, edited only by the PO or the release closer; PRs do not edit HANDOFF.md or DECISIONS.md. tests/m2/test_feature_status.py was adapted: the open PR list moved into docs/FEATURE_STATUS.md (`Open PRs:` line), HANDOFF is checked only for PRs it claims as merged, and the test is a unittest.TestCase so that `unittest discover` and pytest both collect it.
6. Standing rules recorded earlier and unchanged: every release PR updates docs/FEATURE_STATUS.md (rule 7 of docs/RELEASE_NOTE_TEMPLATE.md); a fixtures PR whose rows need a code PR merges after it, or in the same PR, or its rows are tagged expected-fail with a ticket, and main is never red at a merge (rule 8).

PO ruling (same day, after the review of PR 100): history reuse moves into M3a; M3b is the realized-volatility join only; M3c is unchanged.

## Reason
Repeated review rounds and conflicts on DECISIONS.md and HANDOFF.md cost more than the changes themselves; M3 to M5 are too large to accept as single releases; fixtures authored before design rulings had to be redone.

## Effect on the tracker
docs/FEATURE_STATUS.md release column and release tables use M3a, M3b, M3c, M4a, M4b, M5a, M5b; row counts are unchanged (113 rows).
