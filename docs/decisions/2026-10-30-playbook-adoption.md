# Playbook adoption (2026-10-30)

Decided by the owner (answers in chat) unless noted. Supersedes nothing.

1. Adopt the team playbook in place under docs/playbook/ (copied from the WatchYourList playbook, read-only source); no Release 0 redesign, an audit instead. Reason: M1 closed, M2 built, M3a in flight.
2. Variant B: UI design review is N/A on every PR (owner chose pure N/A over a docs/API review). Two independent reviews (architecture, code) remain. Note: the session brief said three reviews; the owner's choice makes it two for this project.
3. Merge gate: CI green on merge commit + architecture review + code review + PO acceptance. Branch protection to be enabled by the owner.
4. Release gates: performance budgets met, independent Tester re-run, release-readiness filled, PO accepts.
5. Environment: Windows x64, CPython 3.12 only until RQ; Linux evidence before RQ.
6. Team size and licence: unchanged (existing multi-agent team; Apache-2.0 LICENSE). Decided by coordinator from the repo, pending owner review.
7. WatchYourList-specific rules (counsel gates, stored-data-only, list-first) not adopted.
