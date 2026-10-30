# Variants: adapting the playbook to your project

> Working document, not a decision. Part of the portable playbook (`playbook/README.md`). Everything here is a **Suggested default (not an owner agreement)** unless it says otherwise: WatchYourList had one owner, no tests or CI in its app repo, and a design repo with boards.

## A. A code project WITH tests and CI

| Playbook item | Change |
|---|---|
| Merge precondition | CI green is required before the coordinator merges, in addition to the three reviews and PO acceptance |
| Branch protection | Turn it on: require a pull request, the CI checks, and the Review table (a required status check that fails when a Review row is empty, or a required reviewer); no direct push to main; this enforces the gate that a separate session once bypassed |
| Definition of Done 1 and 3 | Acceptance criteria are covered by automated tests that run in CI; the repo's local checks are the same commands as CI |
| Tester | Keeps a manual pass for UI behaviour, exploratory use and states CI cannot reach; no longer repeats what tests prove. Results table stays in the PR |
| Developer prompt | Replace the tests line with: write tests for each acceptance criterion; run the full suite locally before opening the PR; never skip or delete a failing test |
| PR template | Add a "CI" line under Checks run; keep the Review table |
| Pre-merge checklist | Add: CI green on the merge commit; no skipped tests added |

## B. A project with no UI

- Drop the Designer role and Definition of Done items 4 to 6 and 8 where they do not apply.
- In the Review table write "UI design: N/A: no UI" once in the working agreement and do not repeat the reason in every PR if the project says so in its charter (decide that by a decision row); otherwise keep the reason, it is cheap.
- Architecture and code reviews stay. The Tester verifies through the API, CLI or a harness.

## C. Solo or small team (minimum viable team)

| Hats | Who |
|---|---|
| Owner | You |
| Coordinator, PO, Architect | One AI session each, or one session wearing each hat in turn |
| Developer | One |
| Reviewers | Always a fresh agent that did not write the work; this is the one rule you must not collapse |
| Tester | You, or an agent in a browser |

Keep: the decision log, the Review table (code and architecture reviews by fresh agents), Verified and Not verified, worktrees, the checks. Drop: WIP limits, the Designer, the Researcher, release folders until a second release exists. Start the second Developer when you have more than a few Ready stories that share no files.

## D. Several repositories

Name per repo who may write it and which repos are reference-only; the design or contracts repo is the source of truth and implementation repos request changes by a note citing story, board and contract. Each repo has its own AGENTS.md; where two repos differ (for example commit attribution or tests), say which rule applies where in the charter and record the Architect's override.

## E. How sessions are started and trusted

Settle at the start: how a session is launched (desktop app, terminal, scheduled), whether each repo has to be trusted once, which tools subagents may use, and who runs which role (`TEAM.md`). Record the answers in the working agreement and in each prompt's standing lines.
