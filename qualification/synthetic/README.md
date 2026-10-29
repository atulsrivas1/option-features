# Synthetic fixture sets for P1, M1 and performance gates

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Status: authored, not yet run against any implementation. Authored by an independent Tester from the design text and PO rulings without reading implementation; reviewed by independent reviewers; PO acceptance is recorded in DECISIONS.md (2026-10-29 fixtures entry). Expected values come from the rules, never from library output.

- `p1/`: parity-closure rows (spread, locked, window_end, single-reference shares, touch policy, quote age, coverage, legacy defaults) with generator, self-check and mutation table. Rows tagged `pending_design_request` (1, 2, 3, 6, 8) are interim PO rulings; a changed design answer redoes them.
  Run `python selfcheck_p1.py p1_cases.json` in that directory to check every row against the independent reference model and the mutation table.
- `m1/`: OC5, OC6, per-contract IV, chain ATM IV and 30-day IV rows with generators. IV tolerance 1e-4 (forward 1e-6); forward strings compare within tolerance, not bytes.
- `perf/`: performance acceptance spec (gates B2-B7, B9, B12 and the P1 throughput gate), runner contract v2, resource rows, and M1 solver and runner acceptance tests. Governing B7 is 170 min budget / 240 min hard, run once.

Rules: generators are seeded, deterministic, LF, stdlib only; each dataset carries the SYNTHETIC tag; each directory has MANIFEST.sha256. Regenerate and compare hashes before use. Linux is a process check, not claimed.
