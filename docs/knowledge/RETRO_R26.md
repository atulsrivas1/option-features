# Retrospective: R26 variants

## Quality

- Fixtures (N4): two reviews; blocking findings were incoherent Control events and an unflagged inferred pointer.
- Freeze review caught a false claim that no frozen row asserts a gap.
- Static authoring found no runtime defects; they surfaced only in contained runs (attempt 4 passed first run after fixes from earlier attempts).
- Library: inventory gap found by I/O work (744 rows blocked); follow-up reviewed APPROVE.
- I/O review: duplicate-key path order, scan order, bytecode committed in history.
- Workers review: 8 gaps (inferred rules, missing CP0/CP1a/storage); a second review's conditions were applied.
- Roughly 14 independent Sonnet/Haiku reviews; every layer had an independent harness.

## Token usage

Subagent counts are cumulative context, not billed. N4 author 405k, N4 review 182k, attempt4 prep 83k, controller review 179k, auditor author 187k, library worker ~522k + 450k continuation, library PR review 100k, triage 145k, inventory worker 259k, inventory review 133k, I/O worker 165k + 212k, I/O review 149k, workers Haiku 206k, workers review 135k, Sonnet continuation 221k + 229k, re-review 157k.

Waste observed:
- The first library worker hit the session usage limit and had to be resumed.
- The Haiku workers layer needed a Sonnet takeover (second case after equity's E workers).
- Rework because fixtures did not match later clarifications.
- Zero progress-poll notifications this release (a positive).

## Worker performance

- Haiku: I/O layer completed after review fixes; workers layer delivered 33 rows with inferred rules and missing CP0/CP1a/storage, so Sonnet took over.
- Sonnet: fixtures, library continuation, and workers storage on DuckDB all completed.
- Conclusion: Haiku is weak on storage/restore and on contract-faithful rules.

## Code performance

Only observed timing: the contained run took 85 s. No profiling was done.

## Other

- Leftover worktrees remain under .claude/worktrees in the three repos.
- Scratch folders were left behind.
- Bytecode was committed then removed (still in history on the I/O branch).
- PR-diff hygiene: review diffs for stray generated files before opening.

## Changes to the working agreement and skill

Apply from the next release; report on each in the next retro.

1. Regenerate pinned fixtures after every clarification.
2. Triage fixture-vs-contract before changing code.
3. Use Sonnet, not Haiku, for storage/restore work from the start.
4. Add a .gitignore for bytecode before any run.
5. Remove .claude/worktrees at release close (worktree hygiene step).
6. Record usage-limit risk: checkpoint long workers so a resume is cheap.
