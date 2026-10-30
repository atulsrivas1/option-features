# Team playbook: how an owner runs an autonomous AI agent team

> Working document, not a decision. Written by the Product Owner agent, 2026-10-30. Portable: copy the `playbook/` folder into another repository and replace the placeholders. Project names and decision ids appear only in boxes marked **Example from WatchYourList**, in lines labelled as WatchYourList owner agreements, and in `DECISIONS-THIS-PROJECT.md`. On copy, delete or replace every such box, label and that appendix.
>
> **Example from WatchYourList:** the adoption decision is a row in this repo's `docs/DECISIONS.md` (WL390; WL388 and WL389 are reserved on main for the adapter contracts).

## What this is

The record of the system an owner and an agent team used to design and plan a product with the owner as facilitator only. It states each rule, why it exists, the default, the alternatives we considered, and when to change it, plus templates and agent prompts. No secrets, no private data.

**Two kinds of text.** What the owner actually decided is marked **Owner agreement**. Advice added by this playbook is marked **Suggested default (not an owner agreement)**. Unmarked defaults restate the owner's agreement. Keep them apart when you adopt it.

**"The charter".** The document that says who decides what, how a story moves and when work stops. In WatchYourList it was `docs/planning/AUTONOMY-CHARTER.md`. In your project, copy `TEAM.md`, `WORKING-AGREEMENT.md` and `LIFECYCLE.md` into `docs/planning/` (or point prompts at `playbook/` directly); that set is your charter.

## The system on one page

1. **The owner is the facilitator.** The owner sets principles, answers owner-level items (money, legal, new principles), and may veto at a demo. Everything else is decided by the team.
2. **Roles decide inside their lane.** The Product Owner (PO) decides what is built and accepts or rejects. The Architect decides how. The coordinator decides routine matters and merges. The Designer owns UI. Reviewers are never the author.
3. **Release 0 first.** The PO and Architect design the whole system, audit what exists, and prepare the first release. The owner reviews Release 0 once. Then the PO and Architect always work one release ahead of the builders.
4. **One story loop.** Backlog, Ready, build, code review, architecture review, UI design review, Tester pass, PO accept, merge by the coordinator after checks.
5. **Three reviews before anything is approved**, recorded in a Review table in every PR. N/A needs a reason.
6. **Releases are the planning and demo unit; gates are stop points.** Each release has a folder of its own documents and a demo.
7. **Decisions are logged, never silently made.** Every default becomes a row "decided, pending owner review". Only the owner can make a row "confirmed by owner".
8. **Mechanical checks beat memory.** Counts, indexes and backlogs are generated and checked by scripts.
9. **Cost is controlled.** Idle roles do not run; the Researcher is capped; mechanical work uses cheaper models; the coordinator rotates its session with a handoff file.
10. **The team stops only when nothing is left.** "Nothing left" means no Ready story and no unblocked work; the report lists what waits and on whom.

## Bootstrap a new project in one hour

Decisions come first, because the files depend on them. Ask the owner **one question at a time with selectable answers**; settle the five day-1 decisions; take the suggested default for the rest and log each as "decided, pending owner review".

### Step 1 (15 min): the five day-1 decisions

| # | Decision | Suggested default (not an owner agreement) | Why it must come first | See |
|---|---|---|---|---|
| 1 | Repo split and who may write where; how sessions are started and trusted | One writable repo per session; others reference-only | Decides AGENTS.md, worktrees, every prompt | `TEAM.md`, `VARIANTS.md` D, E |
| 2 | Team size at start | WatchYourList (owner agreement): 2 Developers + 1 Tester; solo: `VARIANTS.md` C | Decides lanes and WIP | `TEAM.md` |
| 3 | Tests and CI, or manual Testers only | Decide per repo | Decides the checks in AGENTS.md, the Developer and Tester prompts, the merge precondition | `WORKING-AGREEMENT.md` 15, `VARIANTS.md` A |
| 4 | The owner-level items list | Money, legal, new principles, real rule conflicts, scope across gates | Decides what the team may never decide alone | `WORKING-AGREEMENT.md` 3 |
| 5 | Data and adapter rule | Ports and adapters, a mock adapter for everything external; state where stored data comes from | Decides the architecture and every Data line | `WORKING-AGREEMENT.md` 16, 17 |

The rest (release and gate names, licence, accessibility target and audit timing, cost controls, reporting cadence) take the default and are logged; the owner may change them at the Release 0 review.

### Step 2 (45 min): files, in this order

- [ ] (5) Create the repo; add `.gitattributes` (line endings), `AGENTS.md` (skeleton and the checks to start with: `TEMPLATES/agents-md-and-checks.md`) reflecting decisions 1 to 3.
- [ ] (5) Copy `playbook/` in. Replace `{{project}}`, `{{gh-account}}`, `{{PREFIX}}`.
- [ ] (10) Write `docs/planning/REQUIREMENTS-DIGEST.md`: the owner's rules in the owner's words, each marked owner-stated. Every agent reads it before any brief.
- [ ] (5) Create `docs/DECISIONS.md` (header and table of `DECISIONS-PROCESS.md`); log decisions 1 to 5 and the defaults; reserve id ranges per author.
- [ ] (5) Add `.github/pull_request_template.md` from `TEMPLATES/pull-request-template.md`; if you use CI, set branch protection (`VARIANTS.md` A).
- [ ] (3) Add `CHANGELOG.md` (Verified / Not verified rule) and a short `HANDOFF.md`.
- [ ] (5) Create `docs/planning/DEFINITIONS.md` from `TEMPLATES/definitions-and-backlog.md`.
- [ ] (7) Start Release 0: spawn the PO and the Architect with `TEMPLATES/agent-prompts.md` and the worked kickoff in `LIFECYCLE.md` section 1.

Then add the first check script (a sync or count check) and list it in `AGENTS.md`; run it.

## Folder map

| File | Read it for |
|---|---|
| `README.md` | This page |
| `TEAM.md` | Roles, decision rights, size, sessions versus subagents, worktrees |
| `WORKING-AGREEMENT.md` | Each rule with why, default, alternatives, when to change |
| `LIFECYCLE.md` | Release 0 and kickoff, story flow, Ready and Done, demos, defects, closure |
| `DECISIONS-PROCESS.md` | Decision log format, statuses, numbering, amendments |
| `VARIANTS.md` | Code project with tests and CI, no-UI project, solo team, several repos, session setup |
| `TEMPLATES/` | pull-request-template, decision-row, story, design-brief, release-readiness, owner-review-guide, counsel-open-item, agents-md-and-checks, definitions-and-backlog, agent-prompts |
| `OPERATING-LESSONS.md` | What went wrong or nearly did, and the fix |
| `DECISIONS-THIS-PROJECT.md` | Appendix: what the owner decided for WatchYourList, with a "change for your project?" column. Delete on copy |

## Notation

`{{placeholder}}` is replaced per project. "Example from WatchYourList" boxes show a real instance and can be deleted.
