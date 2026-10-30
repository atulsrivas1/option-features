# Template: pull request (copy to `.github/pull_request_template.md`)

> Part of the portable playbook. The file below is the template; fill each section. A PR with an empty Review table is not approved.

```markdown
## What and why

## Checks run (AGENTS.md)

## Verified / Not verified

## Review (nothing is approved until all three are done)

| Review | Reviewer | Verdict (approve / changes / N/A: reason) | Findings fixed |
|---|---|---|---|
| UI design review (Designer) | | | |
| Architecture review (Architect) | | | |
| Code review (independent; not the author) | | | |

## UI evidence (screenshots at 1280 and 375 px, light and dark, one per state the story touches; or "not verified: rendering")

## Tester pass

| Story id | Criterion | Result (pass / fail / not shown) | Evidence |
|---|---|---|---|
| | | | |

PO accept: pending.
```

Rules for filling it:

- **N/A needs a reason a reader can check**, for example "no UI file touched" or "no code or scripts, documents only".
- A verdict "changes" blocks acceptance and merge until the finding is fixed and the reviewer has seen the fix; list the finding under "Findings fixed" when done.
- "not verified: <what>" is allowed when a review cannot be done; the PO decides whether to accept with that limit, and the changelog repeats it.
- Docs-only PR example: UI design N/A (no UI), code N/A (no code or scripts), architecture pending.
- Commit messages and the PR body end with the attribution lines the repo's rules require; where a repo forbids trailers, add none.
