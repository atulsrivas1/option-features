# Synthetic fixture sets for M2 (flow completion)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Status: authored, not yet run against any implementation. Independently authored by Testers from docs/m2 (matrix, I/O contract, fixture requirements, gate budgets) and the PO rulings (Q1-Q18, AMB-1..19, interim pending design ratification where the design is silent), reviewed by independent reviewers with their own oracles. PO acceptance is in DECISIONS.md.

- `correctness/`: 570 rows in 14 `m2_cases_*.json` files (F1, F2 incl. F2c/F2d, F4, F7, F10/F20, F17, F18/F19, F12, lane, structural, delayed-feed, session-open, half-day, store), generators, a second implementation (`m2_ref.py`) with `m2_selfcheck.py`, 67 mutants (`m2_mutants.py`), a differential generator (3 x 20,000 cases, generated at run time), AUTHORING_NOTES.md, MANIFEST.sha256 (41 files) and MANIFEST.json (seed, counts, frozen facts). Check: `python m2_selfcheck.py` in that directory.
- `perf/`: M2 performance acceptance (M2-G0, B1-B18, B15r), runner contract v3, resource rows, workload generator and manifest. Full workloads regenerate at run time from the seed; only samples and manifests are committed.

Rules: generators are seeded, deterministic, LF, stdlib only; each dataset carries the SYNTHETIC tag; regenerate and compare hashes before use. Linux is a process check, not claimed.
