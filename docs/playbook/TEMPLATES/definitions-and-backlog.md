# Template: DEFINITIONS and the ordered backlog

> Part of the portable playbook. Start here when the project has neither file. Both are cross-release documents in `docs/planning/`.

## DEFINITIONS.md skeleton

```markdown
# Definitions: Ready, Done and epics

> Working document, not a decision. Written by the PO. Date {{YYYY-MM-DD}}. The pull order is the generated backlog.

## Definition of Ready (a story may be pulled)
{{Copy the table of playbook/LIFECYCLE.md section 4 and trim to what the project has.}}

## Definition of Done (a story may be accepted)
{{Copy the table of playbook/LIFECYCLE.md section 5; item 0 is the three reviews.}}

## How Testers verify
{{Manual browser procedure from TEMPLATES/agent-prompts.md (Tester), or "CI is the gate plus a manual pass for UI changes".}}

## Epics (read by the backlog generator)
| Epic | Family | Name | One line |
|---|---|---|---|
| EP-{{AB}} | {{AB}} | {{name}} | {{one line}} |
```

Each story belongs to exactly one epic, by its id prefix.

## The ordered backlog

Aim: the pull order is computed, never typed. If you have no generator yet, start with a hand-kept table and replace it as soon as there are about 20 stories; until then the coordinator checks it by eye at each merge and says so in the report.

| Column | Source |
|---|---|
| Rank | Build order in the roadmap, then dependencies, then size |
| Story | Story file |
| Release | Gates file |
| Status | Ready (frozen), Ready (stub), Blocked, Done: computed from the Definition of Ready |
| Blockers | Gates file `blocker` field plus stories it needs |
| Size | S, M, L heuristic; an L is split before it is pulled |

Minimal generator contract (any language): inputs the story files, the gates file, the roadmap build order, the epic table and a config file; output one Markdown file with a generated-file banner; flag `--check` exits non-zero if the committed file is stale. It never edits its inputs.
