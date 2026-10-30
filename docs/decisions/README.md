# Decision records

Rule (RULED 2026-10-30, docs/decisions/2026-10-30-process-and-m3-m5-split.md): one decision-record file per PR, in this directory, named `YYYY-MM-DD-<slug>.md`. Records are append-only: a changed decision is a new record that names the one it supersedes; an old record is never edited except to fix a typo.

- DECISIONS.md at the repository root is a frozen log through 2026-10-30 and carries an index of the files here. PRs do NOT edit DECISIONS.md or HANDOFF.md any more.
- HANDOFF.md keeps only the current state (under 60 lines) and is edited only by the PO or the release closer, so that PRs never conflict on it. docs/FEATURE_STATUS.md (updated by every release PR) is the live tracker, including the machine-readable `Merged PRs:` and `Open PRs:` lines; tests/m2/test_feature_status.py checks it and does not depend on HANDOFF edits by other PRs.
- A record states: date, decision, reason, who decided (PO, owner, Developer evidence only, independent reviewer), and the label sentence when it quotes measurements: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12
- Add the new file in the same PR as the change it records; if two PRs would record the same decision, the later one cites the earlier file instead of repeating it.
