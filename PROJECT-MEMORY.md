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

## Run and test commands (read-only inspection; use a clean CPython 3.12 runtime with the packages installed, always `-B`, no bytecode)
- option-features (from repo root): `python -B -m unittest discover -s tests -p "test_*.py" -v` (tests/contracts, tests/features, tests/qualification; the fixture consumer needs R25_INDEPENDENT_WIRE_FIXTURES and R25_INDEPENDENT_WIRE_FIXTURES_SHA256, see docs/R25_LOCAL_QUALIFICATION.md).
- option-feature-io (from repo root): `python -B -m unittest discover -s packages/io/tests -v`
- option-feature-workers (from repo root): `python -B -m unittest discover -s packages/workers/tests -v`; integration: `python -B qualification/run_integration.py --config <config.json> --trusted-manifest-sha256 <digest> --destination <new-dir>` (per qualification/README.md).
- Not executed here. Unverified: whether tests/ discovery works without package markers, and R26 variants1 test entry points (none found).
- Private candidate4 fixtures: see docs/r26-variants/FIXTURE_MANIFEST.md.

## Demo (tools/demo, synthetic only, prerelease)
- `python -I -B tools/demo/export_demo.py OUT.duckdb [--evidence evidence.json] --out demo-export.json`, then open `tools/demo/demo.html` (file://, no network) and pick the JSON. Usage and the badge rules are in the export_demo.py header. The page embeds `tools/demo/sample/demo-export.json` (synthetic fixtures; rebuild with `sample/make_sample.py`). Variants1 sink only; no REAL badge exists; unknown provenance is UNVERIFIED. A gate for a qualified release, not for the prerelease.
