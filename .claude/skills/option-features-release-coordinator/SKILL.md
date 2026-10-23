---
name: option-features-release-coordinator
description: Run an Option Features release autonomously. Covers the working agreement, how to avoid re-reading a long chat (handoff file, fresh sessions, delegation), and the autonomy rules with model and token discipline. Use when coordinating any option-feature release.
---

# Option Features release coordinator

Three goals: (1) follow the working agreement, (2) never pay to re-read a long chat, (3) run releases autonomously. Start every session by reading, in order: `HANDOFF.md`, the memory files (option features working rules, equity product model, coordinator autonomy), `STATUS.md`, `DECISIONS.md`. Repos under `C:\Atul\Claude`: `option-features` (core), `option-feature-io`, `option-feature-workers`; the equity-feature repos are reference only. Author is Atul Srivastava. Local build, no CI.

## 1. Working agreement (the pipeline)
Per release, one unit = one contract x one layer:
1. **Contract** (Sonnet author): md + json, hand-derived fixtures (exact fractions + float.hex), per-fixture acceptance rule, shared validators and R17 numeric policy.
2. **Independent contract review** (fresh Sonnet) recomputes every fixture with its own harness. Re-reviews check only changed fixtures.
3. **Freeze**. Give authors complete rulings in one message.
4. **Library** (Sonnet), then **I/O** and **workers** (Haiku first; Sonnet only if Haiku misses after one correction). One agent per layer, own worktree, own scratch subfolder, verify cwd is the right repo.
5. **Independent code review** (fresh read-only reviewer, own harness) for every PR including docs; coordinator also reads the real diff. Tiny docs/status PRs may use a Haiku reviewer plus a recompute script.
6. **Merge** after approval (author merges own PR where permitted). Retire workers after the release; never reuse across releases.
7. **Close**: evidence doc, Windows qualification, browser demo for the owner, retrospective in `docs/knowledge/LESSONS.md`.
8. **Retrospective rule**: at release close write one covering quality (findings per unit), token usage (waste found), worker performance, code performance and other; every retrospective (quality, token usage, worker performance, code performance, other) must end with concrete changes to this skill and the working agreement, applied from the next release's first brief; the next retrospective reports for each change whether it was applied and whether it helped. Distil recurring items into the layer-brief checklist rather than growing a long log.
No unit tests; layers are verified by manual runs. Report outcomes faithfully (failures with output, skipped steps stated).

## 2. Save re-reading the chat
Every turn re-sends the whole chat, so cost grows with length. Therefore:
- **State lives in files, not the chat.** Keep `HANDOFF.md` (under 60 lines: merged/next with PR and branch names, open decisions, owner items, gotchas) current after every merge; decisions go in `DECISIONS.md`.
- **One coordinator session per release.** At release close, or around 150 turns, finish the current step, update `HANDOFF.md`, commit it, then propose a fresh coordinator session with a `start_session` card ("fresh", brief = read `HANDOFF.md` and this skill) and stop.
- **Keep turns few and small:** batch independent tool calls in one message; ask agents for reports under 15 lines; never paste big files or full outputs; read only the needed line ranges.
- **Delegate noisy work** (wide reads, harness runs, fixture recomputes) to agents so only conclusions return.
- Batch review nits and status/decision entries per release; one fix round, not many.

## 3. Autonomy
- Decide and unblock yourself; log each call in `DECISIONS.md` as "decided, pending owner review". Do not ask for routine go-aheads.
- Ask the owner only for owner-only items: cost, destructive git, read-only repos, changing a decision's status, creating tracker issues if unsure, release acceptance, dataset rights. Park these in `HANDOFF.md` owner items and keep working on other units.
- Loop: pick next unit from `HANDOFF.md` -> launch agents (independent layers in parallel; layers sharing files sequentially) -> review -> merge -> update `HANDOFF.md`. If an agent is blocked or rate-limited, retry once, then switch model or unit and note it.
- Models: Haiku for template-driven I/O and workers layers, status/decision/doc-wording PRs, census/hash checks, spot-runs, readable-view tooling. Sonnet for contracts, libraries, fixture recomputation, code review. Never Astra; Opus/Fable only if the owner asks.
- Follow-up work that is a task of its own gets a `start_session` card rather than a sentence.

## 4. When and how to start a fresh coordinator session
Rotate when ANY of these holds: the release closes; the chat has passed about 150 turns or is clearly heavy (long tool results, repeated summaries); a usage limit stopped the session; the owner asks.
Steps:
1. Finish the step in hand. Let running workers report and merge their PRs first (workers are children of this session and cannot report to the next one). If a worker must stay open, record its branch and PR in `HANDOFF.md` and merge it later through the PR itself.
2. Update `HANDOFF.md` (merged, next, owner items, running servers and ports, leftovers, gotchas) and add a last dated line to the release log. Check that anything the next session needs is running and say so in the handoff.
3. Start the new coordinator with `start_session` (fresh, `use_worktree` false, `user_asked` when the owner has asked, otherwise a card) and a brief that says: you are the Option Features release coordinator; read this skill, then `HANDOFF.md`, `STATUS.md`, `DECISIONS.md`; continue the loop; take decisions autonomously; owner items are listed in the handoff; first action is to confirm in one line what you read and what you do next.
4. When the new session has confirmed (read its first report), tell the owner and **archive the old coordinator session** (`archive_session`, after the owner's yes or when the owner has already asked for it). Do not archive before the handover is confirmed.
5. The old session sends no further instructions to workers after the handover.

## Gotchas
- Isolated agents inherit cwd: switch to the target repo first and tell the agent to verify.
- Quote Windows paths.
- Private audit closure material is read-only, never copied; opaque ids only.
- Option stories differ from equity; do not copy equity contracts or fixtures without re-deriving them.

## Layer-brief checklist (put in every worker brief; extend only from retrospectives)
- Verify cwd/repo first; touch only your repo and scratch folder.
- Hash and line-ending check (LF vs CRLF) on every pinned source before comparing hashes.
- No hardcoded ids, instruments or fixture-derived values in code, docs or commit text.
- Haiku gets one correction round, then Sonnet. Coordinator spot-runs the layer before sending it to review.
- Reports under 15 lines; no progress-poll messages (the harness notifies on completion).
- Refusal/error inputs must be in the contract and fixtures before a layer is asked to implement them.
