# Template: owner review guide (Release 0, one page)

> Part of the portable playbook. Written by the PO. This is the only review the owner holds before the first build release. "Approve" must be a complete answer.

```markdown
# Release 0 owner review guide

> Working document, not a decision. Written by the PO. Date {{YYYY-MM-DD}}. After this review the owner is the facilitator only.

## Read, in this order (about 45 minutes)
1. {{Release 0 scope file, sections 3 and 4}} (10 min): what Release 0 had to produce and where each item stands.
2. {{First release READINESS, sections 1, 3, 5}} (10 min): how many stories are Ready, who closes each blocker.
3. {{Working agreement or charter, sections: roles, reviews, escalation, safety, defects, release acceptance, human-only steps, licence}} (15 min).
4. {{Architect's system design summary and audit}} (10 min).

## Decide (each has a recommendation; "approve" is a complete answer)
| # | Decision | Recommendation | If you say nothing |
|---|---|---|---|
| 1 | Approve the working model, the charter and the three-review rule | Approve | Team starts as written |
| 2 | {{Legal: engage a lawyer now or later}} | {{...}} | {{...}} |
| 3 | {{Each owner-level item with a provisional decision}} | {{...}} | {{...}} |

Items not answered keep their provisional decisions and are listed in the readiness file.

## Risks (in order)
1. {{Lead time of an outside answer and what a late answer would change.}}
2. {{What cannot be verified yet (missing tool, no real screen reader, unreviewed boards).}}
3. {{Throughput: reviews and the single Tester, not coding, set the pace.}}
4. {{Contracts not agreed with the system of record.}}
5. Autonomy drift: the stop condition and reporting points are the control; reverse the model by amending the three decisions.

## After this review
Decisions marked "decided, pending owner review" are passed to you as a list at each next-release planning; work does not wait; you can ask for a change at any time.
```

After the review, add an "The owner's answers" table at the top (decision, answer, recorded as which decision row) and mark the old "Recommendation" and "If you say nothing" columns superseded.
