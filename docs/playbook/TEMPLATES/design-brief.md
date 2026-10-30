# Template: design brief (one per board)

> Part of the portable playbook. Written by the PO with the Architect's contract names; read by the Designer. Layout is never blocked by legal wording; only wording is.

```markdown
# Brief B-{{NN}}: {{Board name}}

> Working document, not a decision. Decided by the PO, status "decided, pending owner review" ({{ID}}). Date {{YYYY-MM-DD}}.

## 1. Purpose and user job
{{One paragraph: who uses it, what job it does, where it sits in the journey, release and wave.}}

## 2. Stories placed here
{{Story ids, each with its release. Every story is placed in exactly one brief.}}

## 3. Contract and data
{{Contract files and DTO names the board binds to. Data-capability line per story. Fields that are still open.}}

## 4. States to draw
{{Table: state id, name, when it occurs, what the board shows (word, reason, clock). Available, partial, stale, missing, delayed, empty, loading, error, offline, limit reached, denied.}}

## 5. Layout
{{Regions, order, sizes (phone, tablet, desktop), what is shared with other boards (cite the board number), what is retired.}}

## 6. Copy
{{Keys from the strings file, verbatim. Wording that waits on legal: the key and the tag "counsel pending", no wording drawn as final. Proposed keys marked "proposed key".}}

## 7. Must NOT appear
{{Blocked vocabulary, advice language, scores, ranks, colour-only meaning, any element the owner ruled out.}}

## 8. Interaction
{{Entry points, transitions, what is carried between views, return target.}}

## 9. Keyboard and accessibility
{{Tab order, roles, names, states, focus after a sheet closes, contrast notes.}}

## 10. Open questions
{{Each cites its decision, owner, legal or engineering id. Left open, not guessed.}}

## 11. Ready for layout
{{Checklist below completed? The Designer marks "ready for layout" only when it is.}}

## 12. Checklist (Definition of Done for the board)
- [ ] All states drawn, light and dark, desktop and phone width
- [ ] Every number shows its time and source, or its data-state word (if the project has such a rule)
- [ ] No meaning by colour alone; only design tokens
- [ ] Copy matches the strings file verbatim; legal-pending strings tagged
- [ ] Keyboard path and roles written on the artboard
- [ ] "Must NOT appear" list checked
- [ ] Reused parts cited by board number
- [ ] Index, mapping, changelog and contrast rows done; all checks pass
- [ ] Second Designer pass in a fresh session and PO check recorded in the Review table
```

A board drawn by the Designer is reviewed by a **different** Designer session (second pass), plus the PO check against the brief checklist; both go in the Review table.
