# Template: AGENTS.md skeleton and mechanical checks

> Part of the portable playbook. `AGENTS.md` is the one file every agent reads first. Keep it to about 80 lines; point to documents instead of copying them.

```markdown
# {{project}}: guide for agents

{{One paragraph: what this repo is the source of truth for, what it holds and does not hold, which other repos are reference-only.}}

## Read first
0. docs/planning/REQUIREMENTS-DIGEST.md (every agent, before any brief)
1. {{principles file}}
2. {{product map and feature index}}
3. docs/DECISIONS.md (decided and pending); open decisions you must not guess
4. Top entries of CHANGELOG.md (what changed, what was not verified)
5. docs/planning/AUTONOMY-CHARTER.md (how the team runs, the three reviews), DEFINITIONS.md, ORDERED-BACKLOG.md; release documents in docs/releases/<release>/
6. docs/architecture/ (system design, audit, ports and adapters)
7. playbook/: portable team playbook

## Map
| Path | What | Edit how |   (one row per folder; say which files are generated)

## Commands
{{every check and generator, one per line, with what it verifies}}

## Rules that every change keeps
{{the project's non-negotiables, each one line, each checkable}}

## How to make a change
1. Read the spec; check the decision log and open decisions.
2. Make the change.
3. Run every check above. For visual changes, open the result in light and dark at desktop and phone width.
4. Add a CHANGELOG entry at the top: what changed, Verified (what you actually checked and how), Not verified.
5. Any assumption or default is a decision row with reasoning and reversal cost, "decided, pending owner review". Never mark "confirmed by owner".
6. Work on a branch in your own worktree; open a PR with the Review table; never push to main.
```

## Mechanical checks worth having from day one

Scripts beat memory. Each is a small program with exit code non-zero on failure, listed in `AGENTS.md` Commands, run by every author and re-run by every reviewer and the coordinator.

| Check | What it does | Why |
|---|---|---|
| Sync check | Stories, matrices, briefs, board index, strings keys and every count claim in documents agree; hard failures always fail; known gaps live in a baseline file and the check fails only on NEW drift; `--update-baseline` only drops fixed gaps | Counts and indexes drifted when typed by hand |
| Ordered-backlog generator | Reads stories, gates, work packages, roadmap order, epic table; computes rank, status (Ready, Ready (stub), Blocked), size, dependencies; `--check` fails if the output is stale | The pull order is never typed |
| Coverage generator | Regenerates the story-to-board-to-contract index after any change to a story's Board, Contract, Data or Gate line | One index, always current |
| Package builder with `--check` | Builds the artefact the other team consumes (tokens, contracts, copy, mappings, manifest); fails on a missing mapping row | The consumer never sees a half-built package |
| Token sync with `--check` | Rewrites generated colour blocks from the one tokens file; fails if a local colour is declared | One source for colour |
| Contrast check | Verifies colour pairs meet the contrast target in light and dark | Accessibility is computed, not eyeballed |
| Logic and semantic checks | Every board's logic renders; interaction rules hold; paused surfaces stay frozen | Catches broken boards without a human |
| Copy check | Blocked vocabulary in the strings file | Wording rules are enforced |
| Render script | Renders boards to PNG and static HTML so reviewers can see them; stated limits | A way to review visuals at all |
| Decision-id check (suggested) | Ids unique, ranges respected, every cited id exists | Collisions and dangling references |

Rules for checks: all pass on main, so a failure is the author's; never add to a baseline to hide new drift; a check that cannot run says so in "Not verified".
