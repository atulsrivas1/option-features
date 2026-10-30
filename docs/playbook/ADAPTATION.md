# Option-Features adaptation of the playbook

Read this first. Where it differs from the other files in this folder, this file wins. Files are copied verbatim from the WatchYourList playbook (2026-10-30); "Example from WatchYourList" boxes and WL ids are reference only.

## Not adopted (WatchYourList-specific)
- Counsel gates and the counsel-open-item template (removed). Legal items go to the owner.
- Stored-data-only rule, list-first rule, WL decision ids, DECISIONS-THIS-PROJECT.md (not copied).

## Variants chosen (decisions: docs/decisions/2026-10-30-playbook-adoption.md)
- A (tests and CI): adopted. Merge needs CI green on the merge commit, architecture review, code review, PO acceptance. Branch protection requiring CI and the Review table: to be enabled by the owner (settings change).
- B (no UI): UI design review is N/A on every PR (owner: pure N/A). Review table keeps the row marked "N/A: no UI". Two independent reviews (architecture, code) by fresh agents who did not write the work.
- C (team): multi-agent team already in use: PO, Architect, Developers, independent authors, reviewers, Testers, Coordinator. Reviewers are always fresh.
- D (repos): this repo only; scratch worktrees stay out of PRs.
- E (sessions): desktop app; own git worktree per agent; `gh auth switch --user atulsrivas1` and re-verify before every push or merge.
- Release gates: performance budgets met (hard), independent Tester re-run, release-readiness filled, PO accepts. Linux evidence before RQ.
- Test environment: Windows x64, CPython 3.12 (CI windows-2022).

## Project rules that stay (override the playbook)
Two review rounds max (third only for a correctness defect); one decision file per PR; merge-order rule (fixtures after the code they need, main never red); HANDOFF.md edited only by the PO or release closer; no deletions without the owner.

## Release 0
Not a redesign: adopted in place. Release 0 = audit of existing design against the playbook, then continue HANDOFF "Next".
