# Template: decision row

> Part of the portable playbook. See `../DECISIONS-PROCESS.md` for statuses and numbering.

```markdown
| {{PREFIX}}{{N}} | {{YYYY-MM-DD}} | {{What is decided, one decision, plain words. Cite the rule or document it applies.}} | {{Why. The alternative rejected and why.}} | {{Low: documents only. / Medium: contract X and boards Y change. / High: ...}} | {{Claude, <Role> role}} | decided, pending owner review |
```

Variants of the last two cells:

| Situation | Decided by | Status |
|---|---|---|
| Team default | `Claude, PO role` or `Claude, Architect role` | `decided, pending owner review` |
| Waiting for a closer | `Claude, Architect role` | `proposed` or `open` (name the closer in the Decision text) |
| Owner answered | `Owner at the <review name>, recorded by Claude, PO role` | `confirmed by owner on <date>` (name the review in the Decision text) |
| Owner decided outright | `Owner` | `confirmed by owner on <date>` |
| Changed later | the new row says "Amends {{OLDID}}" | old row gets `; amended by {{NEWID}}` appended |

Worked example (project-agnostic):

```markdown
| X201 | 2026-11-02 | Plan limits for the free and first paid tier are provisional numbers (limits only, no prices, no charges), kept in one table in the roadmap. | The build needs numbers; the owner has not set them; limits are reversible. Rejected: leaving "TBD", which blocks the stories. | Low: one table and the strings that cite it. | Claude, PO role | decided, pending owner review |
```
