# Decisions process

> Working document, not a decision. Part of the portable playbook (`playbook/README.md`).

## Why a log

Agents make many defaults and assumptions. Each becomes a row so the owner can see, reverse and price it. The log is the only place a decision's status changes.

## Row format

One row per decision in `docs/DECISIONS.md`:

| Column | Content |
|---|---|
| ID | Prefix plus number, unique, never reused (`{{PREFIX}}123`) |
| Date | ISO date decided |
| Decision | What was decided, in plain words; one decision per row |
| Reasoning | Why; the alternative rejected |
| Reversal cost | What changing it later would cost (low: documents only; high: contracts and code) |
| Decided by | Owner, or the role and session (for example "Claude, Architect role"), or "Owner at the Release 0 review, recorded by Claude, PO role" |
| Status | One value from the vocabulary below |

## Status vocabulary

| Status | Meaning | Who may set it |
|---|---|---|
| `proposed` | Written, not decided; for example an Architect proposal waiting for the PO | Author |
| `open` | A question with no answer yet; needs a named closer | Author |
| `decided, pending owner review` | The team decided in the owner's place; in force; passed to the owner in the release list | PO or Architect |
| `confirmed by owner on <date>` | The owner made or confirmed the decision, in chat or at a review | **Only on the owner's actual word**; recorded with the date and where |
| `amended by <ID>` (appended to the old status) | A later row changed it; the old row stays | The author of the amending row |
| `overturned` | Reversed by a later decision, kept for history | The author of the reversing row |

**Never mark "confirmed by owner" unless the owner decided it.** A review, a demo, a Tester pass or a long silence confirms nothing. When the owner answers a question, record the answer as a row (or update the row's status with the date) in the same PR.

## Amendments, not rewrites

History is not erased. To change a decision, add a new row that says what it amends and why; append "amended by NEWID" to the old row's status. Do not edit the old decision text. Typo and link fixes are fine.

## Numbering, prefixes, collisions

- One prefix per repo or topic (for example `{{PREFIX}}` for a design repo). Numbers only go up.
- **Parallel authors reserve ranges.** Before an Architect, a Designer and a PO write at the same time, the coordinator gives each a block (for example Architect 370 to 389, Designer 400 to 419). Each author uses only its own block. Say in the PR which range was used.
- A document may say "ids N to M reserved" when it points at rows not yet written. Treat those as taken.
- Before taking the next number, fetch main and take the next free number **after the highest id and after any reserved range** in any file (grep the whole repo, including contracts).
- A collision found at merge: the later PR renumbers its rows and every reference to them; never renumber the earlier merged one.
- A check script can verify unique ids and that every cited id exists.

**Example from WatchYourList:** while PO and Architect PRs ran in parallel, the Architect reserved WL370 to WL389 and WL388 to WL389 stayed reserved in nine contract files, so the playbook decision used WL390.

## Passing pending decisions to the owner

At each release start (when the PO and the Architect plan the next release) the PO lists every row with status "decided, pending owner review" added since the last list: id, one-line decision, reversal cost. The list goes in the release report as information; work continues; the owner may ask for any change at any time and a requested change is a new row whose reversal cost is what the original stated. Owner-level items (money, legal, new principles, rule conflicts) are never decided by the team and are listed separately with the provisional reading in force.

## Checklist when you write a row

- [ ] The decision fits in one row and states what it changes.
- [ ] Reasoning names the alternative and why not.
- [ ] Reversal cost is stated.
- [ ] Status is not "confirmed by owner" unless the owner said so, with the date.
- [ ] The id is inside your reserved range and unused on main.
- [ ] Anything it amends gets "amended by" and keeps its text.
- [ ] The changelog entry mentions the row.
