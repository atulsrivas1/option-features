# Handoff (keep under 60 lines; edited only by the PO or the release closer)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Updated 2026-10-30 after the M3a fixtures merge. Previous text: docs/decisions/2026-10-30-handoff-archive-2.md (older: ...-handoff-archive.md). Read this, then docs/FEATURE_STATUS.md (live tracker), docs/playbook/ADAPTATION.md, docs/decisions/ (README, newest first), DECISIONS.md (frozen log plus index). Rules: independent author, reviewer and Tester roles; two review rounds (a third only for a correctness defect); one decision file per PR; fresh origin/main checkouts for authors and reviewers; merge-order rule (fixtures after the code they need; main never red); the gh account flips between SEPARATE tool calls, so `gh auth switch --user atulsrivas1`, `gh auth status` and the push/pr create/merge must be ONE command; verify pushes with git ls-remote; kill only your own process ids; no deletions without the owner. Owner goals: performance (budgets are hard gates), all features first on synthetic data, adapter work last (RQ).

## State on main (87992c6)
- PRs 99-109 merged: team meeting 99, tracker/process 100, M3a docs 101 and 103, flint scratch 102, rulings 104 (R-103..R-161), CI 105, tracker 106, previous handoff 107, playbook adoption 108, M3a fixtures 109.
- M3a fixtures (qualification/synthetic/m3a/): four independent sets, all APPROVE in round 2, PO accepted, rulings R-162..R-185. They have NOT been run against any implementation (no M3a code exists yet).
- Done earlier: R27, P1 (0.2.0a1), M1 closed, M2 built (close record not written, runner integration parked), CI green (windows-2022, CPython 3.12).
- Open PRs: none other than this handoff PR (verify with gh pr list).

## Playbook adopted in place (docs/playbook/ADAPTATION.md wins over the playbook text)
- Two reviews per PR (architecture and code); UI review N/A (no UI); gates are CI plus both reviews plus the PO gate. Platform Windows x64 CPython 3.12; Linux evidence before RQ.
- Variant decisions: docs/decisions/2026-10-30-playbook-adoption.md. Team size and licence were decided by the coordinator and are pending owner review.

## Decisions
- Owner decisions 1-5 FINAL: V21 in M3a; V3/V4 both forms (iv_form atm|30d, default atm); delta_convention spot|forward (default spot; skew25, skew25_fwd; convention_mismatch structural); percentile over constant history unavailable (zero_range_history); scalar baseline allows partial history (at least 20 sessions).
- Unit decision: 768 MB means 768 MiB (coordinator decision, pending owner review).

## Pending owner items (owner-level only)
- Branch protection settings on GitHub (required checks and reviews).
- Approval of a one-time scratch and worktree cleanup, including C:\Atul\Claude\wt-fix106 and many scratchpad worktrees (owner-only deletion).
- Linux evidence before RQ (no recorded hash; WSL has no bash here).
- B7 reference machine (2 x Xeon 8160, 48 physical cores, 254 GiB) confirmation.

## Team and architect follow-ups
- Rulings and docs: invalid_direction code (R-185); M3A_GATE_BUDGETS.md MB to MiB; confirm R-178 against R-139; D7, D10, D12, D13 rows; convention_mismatch pair; weak STRUCT-110; author3 STATUS stale counts.
- Parked from the old handoff: M2 runner integration (branch m2/runner-integration, pushed, no PR, 265fb7e6; figures in docs/TEAM_MEETING_2026-10-30.md are unverified developer evidence); totality follow-ups (check_prints on hostile lists, contracts map trusted, f17 column entry points internal); performance candidates (F7 density-adaptive windows, F17 sparse reads, lazy ring/record creation, input synthesis sharing, Newton seed, perf_sut B1-B10); CI follow-ups (pin actions by commit SHA, pip bootstrap unpinned, no Linux job).

## Next (in order)
1. M3a build plan: PO and Architect write the stories.
2. Developer M3a code in independent worktrees: failing-first fixtures, mutation tools, M3A-G0 and single-worker gates; Tester re-runs everything.
3. M3a close record.
4. M3b, M3c, M4a-b, M5a-b, then RQ.
