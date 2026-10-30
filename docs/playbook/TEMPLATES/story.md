# Template: story

> Part of the portable playbook. If the project has no design repo, drop the Board line and keep Contract and Data. One file per family of stories (for example `engineering/stories/<family>-stories.md`). The three lines Board, Contract and Data capability are mandatory; a check script verifies they exist and agree with the indexes. The gate lives in a gates file, not in prose.

```markdown
### {{FAMILY}}-{{N}}: {{Short title, what the user can do}}
- {{Acceptance criterion 1: observable on the running app or in the contract, one fact.}}
- {{Acceptance criterion 2.}}
- {{Acceptance criterion 3: states (empty, partial, stale, missing, error) where relevant.}}
- Decisions: `{{ID}}`. Priority {{tier}}. These are requirements, not executed tests.
- **Board:** {{Drawn board and brief path (state: drawn / concept / review pending), or "none by design: <check that guards it>", or "Not determined" (not Ready)}}.
- **Contract:** {{contract file path and its state (frozen / proposed at version), the stub part it reads; or "Missing: <part> (<work package>)"}}.
- **Data capability:** {{What the story reads, where it is stored, client or server, which source feeds it, how it degrades per source; mark unverified entries.}}
```

Gates file entry (read by the backlog generator):

```json
"{{FAMILY}}-{{N}}": { "gate": "{{release}}", "blocker": "{{item ids}}" }
```

Blocker ids use the prefixes in this project's blocker list (the letters are a convention; choose your own). Only open decisions and unconfirmed engineering items block the build; legal, owner and number items block switch-on.

## Rules of thumb

- Each criterion must be testable by a person on the running app or by reading the contract.
- One story = one branch = one PR; split a story that cannot be reviewed in one sitting.
- Wording that waits on the owner (legal) is named as its strings key, tagged "owner pending"; never invent the wording.
- A story with no screen names the check that guards it.
- After any change to Board, Contract, Data or Gate: regenerate the coverage and backlog files and run the sync check.
