# Lifecycle: Release 0, the story flow, Ready and Done, releases, closure

> Working document, not a decision. Part of the portable playbook (`playbook/README.md`).

## 1. Release 0: the planning release

Release 0 produces no running product. The PO and the Architect:

1. **Design the whole system** (Architect: components, records, flows, ports and adapters, switches, data placement; PO: requirements digest, roadmap, stories, gates, backlog).
2. **Audit the existing system** (what exists today against the stories: reuse, rewrite, retire).
3. **Prepare the first release** so the builders can start and keep working without asking anyone: a Ready set big enough for 2 Developers for the whole release, contracts the stories read, boards or briefs, owner, legal and engineering items named with who closes each.
4. Write the working model: charter (roles, loop, WIP, escalation, safety, cost), release-folder rule, the three-review rule.

**Exit criteria (checklist, copy per project):** system design written and accepted by the PO; audit done; first-release Ready set meets the buffer or the PO states why it starts short; contracts the release reads exist; boards drawn or layout allowed from a brief; owner, legal and engineering items named with closer and needed-by; status of any missing tool or file stated; charter and three-review rule written; release-folder rule applied; all checks pass and the documents were read by someone other than the author; **owner review held once**.

**Owner review of Release 0 (once).** One page (`TEMPLATES/owner-review-guide.md`): what to read in what order (about 45 minutes), the decisions with a recommendation and "if you say nothing", the risks. "Approve" is a complete answer. After it the owner is the facilitator only.

**Do not start builders before Release 0 is exit-complete and the owner has reviewed it.**

**Example from WatchYourList:** `docs/releases/R0/RELEASE-0.md` has 17 exit rows; the owner answered 11 review decisions on 2026-10-30.

### Worked Release 0 kickoff (the first two tasks, filled in)

Inputs: the owner's rules in the requirements digest, the repo as it is, the day-1 decisions settled (`README.md`). Order: the PO writes the roadmap, stories and gates first; the Architect starts the audit and the system design in parallel and writes contract stubs in the order the stories need them; the PO writes readiness last, from the generated backlog. The exit checklist lives in `docs/releases/R0/RELEASE-0.md`; the owner review guide is `docs/releases/R0/REVIEW-GUIDE.md`.

PO task string for `TEMPLATES/agent-prompts.md`:

```text
Write docs/releases/R0/RELEASE-0.md (scope, exit criteria table with closer, status and evidence), the story files for release R1 with Board, Contract and Data lines, docs/planning/story-gates.json, and docs/releases/R1/READINESS.md from the generated backlog. List every owner-level item with the provisional reading in force. Rows for every default you chose.
```

Architect task string:

```text
Audit the existing system against the R1 stories (reuse, rewrite, retire) in docs/architecture/EXISTING-SYSTEM-AUDIT.md. Write docs/architecture/SYSTEM-DESIGN.md: components, records, flows, ports and adapters with a mock adapter per port, switches, data placement, trust boundaries. Write contract stubs in the order the PO's stories need them; list what each stub leaves open. Rows for every assumption.
```

## 2. One release ahead

After Release 0 the PO and the Architect keep working together one release AHEAD of the build: while Developers and Testers build release N, they prepare release N+1 until its stories meet the Definition of Ready (its READINESS, contracts, briefs with the Designer). Builders never wait on design or contracts; the legal and pilot gates are worked ahead.

| Rule | Default | Why |
|---|---|---|
| Ready buffer, current release | at least 10 Ready, unassigned, not-started stories (about two weeks for two Developers), of which at least 4 on a frozen contract | Builders never idle |
| Ready buffer, next release | what it can reach without outside answers, measured when half the current release is Done and at its demo; blockers named with owner and needed-by | Surfaces outside waits early |
| Releases do not overlap in build | A Developer pulls from the next release only when no Ready story of the current one is left that they may build | Keeps demos meaningful |
| Starting short | The PO may start a release short with a stated reason | Honesty over padding |

## 3. The story flow

`backlog -> Ready -> build -> code review -> architecture review -> UI design review -> Tester pass -> PO accept -> merge (coordinator, after checks) -> demo`

1. **Backlog to Ready.** PO and Architect keep stories Ready (section 4). The order is a generated file (section 6).
2. **Pull.** The coordinator assigns the top Ready story of the current release to a free Developer: frozen-contract stories before stub stories; never a story whose layout source is a brief the Designer has not marked "ready for layout". One story = one branch = one PR; nobody pushes to main.
3. **Build** to the board or brief, the contract and the strings file; legal-pending wording as its key tagged "owner pending"; a later-release feature behind its switch, off.
4. **Code review** by the other Developer (independent reviewer for non-app work).
5. **Architecture review** by the Architect.
6. **UI design review** by the Designer.
7. **Tester pass** (manual, browser procedure) with the results table in the PR.
8. **PO accept or reject** against the Definition of Done. A rejection names the criterion and returns the story to build; it is not re-queued as new work.
9. **Merge** by the coordinator once checks pass and the PO has accepted. Never an author; never before the three reviews are recorded.
10. **Demo** at the end of the release.

**WIP limits (defaults):** 1 story in build per Developer; at most 3 PRs waiting for review in total; at most 3 waiting for the Architect (above 3 pauses new pulls); at most 2 waiting for the Tester; Designer 1 in draw and 1 awaiting second-pass review. When a limit is hit, pulls stop and the coordinator moves people to review. The Tester and Architect are the likely bottlenecks; never relax a review to unblock them. A story sized L is split by the PO before it is pulled if it cannot be reviewed in one sitting.

## 4. Definition of Ready (generalised)

A story may be pulled when all hold:

| # | Item | Generic form |
|---|---|---|
| 1 | **Screen source** | A drawn board exists, or a brief exists and layout-only work is allowed; a story with no screen names its check |
| 2 | **Contract** | The contract file exists, or the Contract line names the Architect's stub. A stub whose "open" list names a shape the story needs does not count: the story says `Missing:` and names the work package. A story on a contract not yet agreed with the system of record is "Ready (stub)": buildable, rework expected, reported apart |
| 3 | **Data line** | States what the story reads and where it is stored (data-capability matrix) |
| 4 | **Gate** | Has a release gate; the gate decides when the feature may be switched on, not whether it may be built |
| 5 | **No open build blocker** | No open decision or engineering item in its blockers; every story it needs is Ready or Done. Legal, owner and number items block switch-on, not the build |
| 6 | **Testable acceptance criteria** | Each can be checked by a person on the running app or by reading the contract (PO checks when the story enters a sprint) |
| 7 | **Legal-pending wording as keys** | Wording that waits on the owner (legal) is a tagged key; numbers the owner owns read a provisional table, else "limit to be set" |

**Example from WatchYourList:** items 1 to 5 and 7 are checked by the backlog generator; item 6 by the PO. See `docs/planning/DEFINITIONS.md`.

## 5. Definition of Done (generalised)

Items 4 to 6 and 8 apply **if the project has a design repo with boards, a strings file and feature switches**; drop them otherwise (`VARIANTS.md`).

| # | Item |
|---|---|
| 0 | **Three reviews recorded in the PR**, none by the author (UI design, architecture, code), with the Review table, UI evidence and the Tester results table |
| 1 | Acceptance criteria pass a manual walkthrough on the running app; results table in the PR |
| 2 | Accessibility: real controls, labels, states; contrast met in light and dark; meaning never by colour alone (UI projects) |
| 3 | Every check in `AGENTS.md` passes |
| 4 | Copy verbatim from the strings file; a Tester read each screen against it (design-repo projects) |
| 5 | No blocked vocabulary (if the project keeps a blocked-word list) |
| 6 | Names the board it implements and its mapping row (or "pending board N") (design-repo projects) |
| 7 | Works on the running app with labelled sample data and is covered by the release demo script; sample and delayed labels shown |
| 8 | A later-release feature is behind its switch and off (if the project uses switches) |
| 9 | Changelog entry with Verified and Not verified |

## 6. Releases, gates, folders, backlog

- **Releases are the planning and demo unit; gates are stop points** (legal, pilot, supply). A story built for a later release stays switched off until its gate opens. Nothing public ships before its gate.
- **Release folders:** `docs/releases/<release>/` holds that release's own documents; cross-release documents stay in `docs/planning/`. Generated cross-release files stay in `docs/planning/`; a release file links to its section instead of copying it. Folders are created one release ahead of need, never empty.

| File in a release folder | What | Written by | When |
|---|---|---|---|
| `SCOPE.md` (R0: `RELEASE-0.md`) | Stories, exit criteria, status, owners | PO | Before the release starts |
| `READINESS.md` | Every story Ready or Blocked, exact missing item, closer, buffer, plan to grow it | PO | One release ahead; refreshed at each merge that changes a story, contract or board |
| `DEMO.md` | Demo script and fixtures | PO, Tester | Before the demo |
| `IMPLEMENTATION-MAP.md` | Story to code area, contract, switch | Architect | One release ahead |
| `REVIEW-GUIDE.md` / `REVIEW-NOTES.md` | R0: owner review guide. Later: demo and review notes (what passed, what failed, what became a story) | PO, coordinator | At the review or demo |

- **Ordered backlog is generated by a script** from the story files, a gates file, the build plan, the roadmap and the epic table. Rank, status, size and dependencies are computed; nothing typed by hand; the script has a `--check` that fails when stale. A change to a story, gate, work package or epic means regenerate.
- **Demos:** one per release from what is Done, on the running app with labelled sample data; an interim demo at most every two weeks if a release runs long. The owner may veto within the demo. A demo changes no status.

## 7. Defect flow

Tester records findings in the PR with severity. Blocking: stop, fix, re-test, PO does not accept meanwhile. Major or minor: PO fixes now or defers with a written reason; deferred findings are listed in the release report and become a story if they recur. After merge: a fix story at the top of the current backlog, written by the PO with the Tester's evidence, pulled before any new story. Design change requests go to the design repo as a note citing story, board and contract.

## 8. Closure and the "nothing left" stop condition

The coordinator stops and returns to the owner when **no Ready story exists and no unblocked work exists** for any role, and everything remaining waits on the owner, legal, engineering or data. In practice:

- no Ready story in the current release and none in the next that a Developer may build;
- PO and Architect have no story, contract or ruling they can write without an outside answer;
- the Designer has no unblocked board or brief;
- no open PR waits only on an idle role (otherwise that role runs).

The report lists what waits and on whom, sorted by the earliest release it blocks. The team does not invent work, does not start a later release's build early to look busy, and does not stop while any one of the above can still move.

**Stop and report at once:** a safety rule would be broken; a surface would become public before its gate; two checks disagree and no role can settle it; cost passes the controls.

**Release closure checklist:** exit criteria met; every story has three reviews and a Tester pass recorded; checks pass; demo held and the owner has seen it or said "go on"; release report sent (shipped, demo script and result, pending-decision list, human-only items, deferred findings, Ready buffer); READINESS for the next release refreshed; `HANDOFF.md` updated. **Suggested default (not an owner agreement; taken from another team's agreement):** write a short retrospective (what went wrong, what to change).
