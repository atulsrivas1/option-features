# P1 version bump plan: 0.1.0a1 to 0.2.0a1

Author: Product Owner, 2026-10-29. Plan only; nothing is bumped until the Developer starts P1 and the independent fixtures are accepted. Decided by PO.

## Why a bump
P1 changes the R25 result for bid <= 0 (spread unavailable `invalid_quote`) and for locked quotes (spread unavailable `locked_market`), pending design requests 1 and 2 (interim option A). R25 results embed the package version, so any result bytes change at the bump. All other P1 changes are additive (new parameters and outputs whose defaults reproduce the legacy behaviour).

## Files to change (found by text search for the current version string; the Developer re-runs the search)
- `packages/features/pyproject.toml`: version, and the pin on the contracts package.
- `packages/option-contracts/pyproject.toml`: version.
- `packages/features/src/option_features/__init__.py` and `packages/option-contracts/src/option_feature_contracts/__init__.py`: `__version__`.
- `packages/features/src/option_features/evaluator.py`: the version strings embedded in results.
- `docs/r25/COMPATIBILITY.json` is frozen history and is not edited. A new compatibility manifest (0.2.0a1) is added beside it. `docs/r26/COMPATIBILITY.json` likewise stays as history.
- Sibling repositories (option-feature-io, option-feature-workers): pins moved in their own PRs after this repo's P1 is accepted; exact pins, no moving references (docs/VERSIONING.md).
- `docs/VERSIONING.md`: one paragraph recording the bump and its reason.

## Rules
1. Legacy behaviour stays reachable by default parameters; R25/R26 fixtures stay under their tags as legacy and are not edited. Legacy rows are compared on result content; a result that embeds the version string is expected to differ in that string only, and the Developer lists every such row.
2. Bump happens in one PR, after the P1 fixtures exist and fail on the old code (fixtures first, then code).
3. Wheels are rebuilt from the tagged commit; no download is needed. No publication.
4. Performance (owner main goal): the bump PR must carry the P1 throughput gate from the performance acceptance fixtures; no P1 acceptance without it.
5. Labels follow docs/RELEASE_NOTE_TEMPLATE.md.
