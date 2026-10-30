# Continuous integration

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

## What runs

- `.github/workflows/ci.yml`, on every pull request and every push to `main`, one job on `windows-2022`, CPython 3.12 x64. Permissions: `contents: read`. No secrets, no deploys. Every action is pinned by exact tag (`actions/checkout@v4.2.2`, `actions/setup-python@v5.3.0`).
- Dependencies: `.github/requirements-ci.txt`, installed with `--require-hashes --only-binary :all: --no-deps` (python-flint 0.9.0, duckdb 1.5.6; hashes from docs/r26-variants/WINDOWS_PARTIAL_QUALIFICATION_RECORD.md section 2).
- Suites, each as `python -B -m unittest discover -s tests/<dir> -p 'test_*.py'` with `PYTHONPATH=packages/features/src;packages/option-contracts/src;tests/<dir>;tests;.` (script `.github/run_suite.ps1`): contracts, features, p1, qualification, m1, m2.
- qualification needs `R25_INDEPENDENT_WIRE_FIXTURES` (set by the workflow to the repo file) and `R25_INDEPENDENT_WIRE_FIXTURES_SHA256=37f79537...eb23`. A step first checks the file's sha256 and fails on a mismatch. The fixture must keep LF: `.gitattributes` has `qualification/fixtures/*.json text eol=lf` and the job sets `core.autocrlf false` before checkout.
- `M2B_MEMORY` is unset: the 1e6-print memory test is skipped. No benchmarks run in `ci.yml`.
- `tests/m2/test_feature_status.py` is a `unittest.TestCase` (PR 100) and is collected by the m2 unittest run. No pytest dependency.
- `.github/workflows/benchmarks-manual.yml`: `workflow_dispatch` only; one-repeat M chain benchmark on a shared runner, indicative only, never evidence.

## Not claimed

No Linux job: the python-flint manylinux wheel hash is not recorded in the repository. Hosted CI results are Windows evidence on GitHub-hosted runners, not a release gate by themselves.

## Follow-ups (known gaps)

- Pin actions by commit SHA, with the tag in a comment (today: exact tags only).
- pip, setuptools and wheel come from the setup-python image and are not pinned (bootstrap gap; project wheels are hash-checked).
