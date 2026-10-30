# 2026-10-30 CI workflow (owner approved, PO directs)

Decision: add GitHub Actions CI (`.github/workflows/ci.yml`) for PRs and pushes to main: Windows x64, CPython 3.12, hash-pinned python-flint and duckdb, unittest suites contracts, features, p1, qualification, m1, m2; the tracker test is collected by the m2 unittest run since PR 100. Benchmarks in a separate manual workflow. Details: docs/CI.md.

Constraints met: no secrets, no deploys, `contents: read`, actions pinned by exact tag, `--require-hashes`, M2B_MEMORY unset.

Findings:
- On Windows with default git settings the LF fixture checks out as CRLF (`text=auto`) and its sha256 changes (3eae4f00... instead of 37f79537...). Fixed with a `.gitattributes` rule and `core.autocrlf false`; the workflow verifies the hash before running.
- YAML: a plain scalar containing `:all: ` is a parse error; install commands use block scalars.
- Local verification with the method-development environment, same commands: contracts 14, features 72, p1 141, qualification 8, m1 251, m2 951 at authoring, 963 on the merged head (2 skipped), all OK. m2 now includes test_feature_status.

Open items:
- No Linux job: manylinux python-flint hash not recorded.
- TODO after the first green run: update the docs/FEATURE_STATUS.md CI status/badge (not done in this PR).
