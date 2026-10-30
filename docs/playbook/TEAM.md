# Team: roles, decision rights, size, sessions

> Working document, not a decision. Part of the portable playbook (`playbook/README.md`).

## Principle

Every decision has one owner. A reviewer is never the author. A role fills a gap only when the gap is named, and never reviews its own work. The owner is the facilitator and is not asked to be "informed" of routine things.

## Roles

| Role | Responsibilities | Decides | Must NOT |
|---|---|---|---|
| **Owner (facilitator)** | Sets principles; answers owner-level items (money, legal, new principles, real conflicts between owner rules, scope across gates); reviews Release 0 once; may veto at a demo; supplies human-only things (accounts, licences, people) | Owner-level items only | Be asked routine product, technical, ordering or wording questions; be asked to approve each PR |
| **Coordinator** | Runs the loop: assigns Ready stories, WIP, session rotation, spawns independent reviewers, merges after checks and PO acceptance, writes reports, keeps `HANDOFF.md`, escalates | Routine matters: assignment, order inside the Ready set, WIP, merges, when to demo | Accept or reject stories; make product or technical rulings; decide owner items; merge before three reviews and PO accept |
| **Product Owner (PO)** | Knows the whole product; writes stories, gates, backlog, Ready and Done; accepts or rejects each story (the one acceptance); declares a release done; decides "pending owner review" rows; rules on product conflicts | What is built, in what order, product wording that is not legal | Make technical design calls; write legal wording; mark anything "confirmed by owner" |
| **Architect** | Technical design, contracts, data placement, privacy boundaries, switches, ports and adapters catalogue; architecture review of every PR; audits the existing system | How things are built; contract shape (the system of record wins) | Decide what the product does; accept stories; review its own PR |
| **Designer** | Boards, briefs, tokens, components, copy placement; UI design review; owns accessibility and interaction review rules | UI against the board or brief; marks a brief "ready for layout" | Change contracts; accept stories; review a board it drew (a second Designer pass in a fresh session does) |
| **Researcher** | Read-only scout of repo and public sources; proposes ideas | Nothing | Edit the repo; hold more than 2 ideas; research when both ideas are open; decide scope |
| **Developers** | Build one story per branch per PR; request contract changes through the Architect; review each other's PRs | How a story is built within the architecture | Self-review; push to main; change scope, contracts or acceptance; switch a gated feature on; add tests or CI if the project says manual only |
| **Testers** | Verify each acceptance criterion on the running app; record results and severity in the PR | Whether a criterion passes | Accept stories; fix defects; repeat the Designer's board comparison |
| **Reviewers (independent)** | Fresh read-only agents for code, architecture, UI design; verify claims against the code, not the author's summary | Their verdict (approve / changes / N/A with reason) | Fix what they review; review work they wrote or were briefed to defend |
| **Counsel-prep** | Keeps the open-item list and a counsel package current; drafts questions for a real lawyer | Nothing | Give legal advice; invent wording for a legal gate; contact a lawyer |
| **Writer / Integrator** | Applies decided changes to documents; regenerates generated files; merges the main branch into a branch; updates indexes and changelog | Nothing beyond the instruction | Change meaning; mark decisions confirmed; resolve conflicts by hand-merging generated files |

## Decision rights at a glance

| Question | Who decides |
|---|---|
| Pricing, legal position, new principle, rule conflict between owner rules, opening a gate | Owner |
| What the product does, order, product wording, accepting a story or release | PO |
| Contract shape, data placement, privacy boundary, adapters, code-quality disputes | Architect |
| UI against board or brief, accessibility review rules | Designer |
| Assignment, WIP, merge timing, session rotation, report timing | Coordinator |
| Dispute not settled after one exchange | Owner of the area; unresolved goes to the coordinator; owner-level goes to the owner |

## Conflicts between roles

1. Product versus technical: PO decides what, Architect decides how; if impossible, the Architect proposes the closest option and the PO accepts or reduces scope.
2. A review finding the author disputes: one exchange in the PR, then the area owner decides; reason goes in the PR.
3. Two rules conflict: the more specific and later rule wins; a conflict between two owner rules is an owner item and work continues on the provisional reading.
4. A Tester failure the PO calls out of scope: the PO rules in the PR citing the criterion; if the story text is wrong, fix the story, not the test.

## Team size and when to scale

| Rule | Default | Why | Change when |
|---|---|---|---|
| **Owner agreement:** start with **2 Developers + 1 Tester** | Dev A: UI and client state. Dev B: data adapters, switches, API-facing code. They never share files and review each other. One browser Tester | Review and test throughput, not coding, sets the pace; two lanes with no shared files avoid conflicts | The owner changes it |
| **Owner agreement: third Developer rule** | Add a third Developer only when more than 20 Ready stories share no files | Builders need independent work | The owner changes it |
| Always-on (always has the next release in hand; each task is a fresh agent) | PO, Architect, Designer, coordinator | They keep the next release Ready | Pause a role when it has no item of its own |
| **Idle by default** | Researcher (between rounds), counsel-prep (on request only), Writer/Integrator and independent reviewers (spawned per PR), fix-round agents | Idle roles cost tokens for nothing | The role has a Ready item of its own |

**Suggested defaults (not owner agreements):** if the Tester queue stays above its WIP limit, add a Tester before a Developer; do not add builders while the review queue is full.

**Example from WatchYourList:** 2 Developers + 1 Tester chosen by the owner on 2026-10-30. Dev A UI and client state, Dev B adapters and API-facing code. Third Developer only above 20 Ready stories with no shared files.

## Sessions and agents: how roles map

| Role | How it runs | Why |
|---|---|---|
| Coordinator | Its own long-lived session; rotates with `HANDOFF.md` | Owns the loop; must stay light |
| PO, Architect, Designer | Fresh subagent per task (a brief, a topic, a PR), each with its charter in the prompt | Keeps context small; an author cannot be its own reviewer if the review is a new agent |
| Developers, Testers | Separate sessions in the app repo, or subagents with a worktree each | They need the repo checked out and a running app |
| Reviewers | Always a fresh subagent that did not write the work, given the diff and the files it names | Independence; scoped reading limits cost |
| Researcher | Subagent, read-only, spawned per round | Capped; idle otherwise |
| Integrator, fix-round, writer | Subagents spawned per job | Mechanical; cheaper model |

Use a **separate session** (not a subagent) when the role needs its own checkout and running app, runs for hours, or must survive coordinator rotation. Use a **subagent** for bounded, reviewable work. Never let a separate session merge without the gate: tell every session the rules in its first prompt (see `OPERATING-LESSONS.md`).

## Repository and worktree ownership

| Rule | Detail |
|---|---|
| Writable repos are named per session | Everything else is reference-only unless the owner permits |
| The design repo is the source of truth for stories, boards, contracts, strings | Implementation sessions request changes by a note citing story, board and contract |
| Several agents never share one checkout | Each agent: `git worktree add <path outside the repo> origin/main -b <branch>`; remove it when done |
| Identity | Run the account switch before any git or gh call (the login can flip); never push to main |
| Commit and PR attribution | Follow the target repo's own AGENTS.md; where it forbids trailers, add none |
