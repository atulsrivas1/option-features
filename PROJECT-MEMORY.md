# Project memory (keep lean; update when scope, contracts or architecture change)

## Shape
- Three repos: option-features (core: contracts and calculations), option-feature-io (adapters and sinks), option-feature-workers (execution and persistence). Dependencies flow inward: I/O and workers use core; core uses neither.
- Options may use qualified equity packages; equity never depends on options. Never copy equity mathematics.
- Contracts between layers are frozen per release; only the coordinator amends them.
- Flow: existing DuckDB or synthetic data -> input adapter -> workers -> feature libraries -> output sink -> separate output DuckDB. Real and synthetic data keep distinct provenance.
- Roadmap, numbered stories and the Project live in equity-features (docs/COORDINATOR_WORKING_AGREEMENT.md there is the working agreement).

## Where things live
- Current work: STATUS.md. Decisions: DECISIONS.md. Resume steps: docs/SESSION_HANDOFF.md. R26 contracts and evidence: docs/r26/. Older detail: docs/ (read only what a task needs).
- Local clones sit beside each other in the owner's workspace folder. The old private workspace (not in any repo) holds R26 fixture source and evidence under work/r26-20261021.

## Open at last check (2026-10-22)
- R25 released as prerelease, unchanged. R26 (44-output native candidate) unreleased: draft PRs option-features #9, option-feature-io #5, option-feature-workers #5; EQ188/EQ189/EQ215 In progress (variant contract rework), EQ191/EQ192 Test, EQ190/EQ193 gated on real EQ153/EQ158 producers.
