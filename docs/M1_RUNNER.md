# M1 process-pool runner (opt-in, default single-process)

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12. All numbers are "synthetic workload, relative engineering budget". Developer evidence only; the independent Tester authors and re-runs the determinism, kill and scaling tests and the platform replays.

The runner is opt-in, default single-process. It is a separate optional tool (`tools/m1_runner/`, not shipped in the libraries, no change to the record schema or to any result byte). The libraries stay single-threaded and pure (D4 amended). It is never enabled by default anywhere: `--workers` defaults to 1, which runs in this process and is the reference path. Every other worker count must give identical result bytes.

## What it computes
Units are underlying x session x cutoff (unit key `SYN1/03/045`). One unit, on one size-M chain at one cutoff (2,000 contracts): per-contract IV, ATM IV for every expiry and 30-day IV (`option_features.chainiv`), and OC5 and OC6 for every contract (`imbalance`, `spreadwin`). The driver adds no calculation; `tools/m1_runner/workload.py` only builds the synthetic inputs from `qualification/synthetic/perf/gen_perf_workloads.py` (read only) and calls the pure modules. Units share no state. The whole workload is 5 underlyings x 5 sessions x 78 cutoffs = 1,950 units. Shape `T` (40 contracts) exists for CI tests.

## Usage
```
python tools/m1_runner/cli.py --shape M --workers 24 --out OUTDIR --emit full --log run.jsonl
python tools/m1_runner/cli.py --shape T --underlyings SYN1,SYN2 --sessions 1-2 --cutoffs 0-2     # reference path, 1 worker
```
Options: `--workers N` (default 1), `--batch-size`, `--order natural|reversed|shuffle:K` and `--contract-order` (test levers: results must not depend on them), `--emit digest|full`, `--out DIR`, `--log FILE`, `--b9-peak-bytes`, `--aggregate-hard-bytes`, `--cores`, `--ram-bytes`, `--timeout-s`, `--count-arb`, `--fault`. The API is `m1_runner.Runner(workers=N)` as a context manager and `runner.run(spec, batch_size, order, emit, out_dir)`. The interpreter that starts the run is the interpreter of every worker; it must be the one that has python-flint.

Workers are persistent processes started once (Windows: `spawn`) and fed chunks of one underlying x session and consecutive cutoffs, which amortises IPC and lets a worker keep the quote history it built for its session (derived data, dropped between runs; results never depend on it, tested). Dispatch is dynamic and sticky (an idle worker prefers a chunk it can serve from its cache); this is a scheduling heuristic only.

## Caps
`cap = min(cores, RAM / B9 peak, aggregate hard limit / B9 peak)`, at least 1. B9 peak is a 2 GB placeholder until a B7 run measures the per-process peak (`--b9-peak-bytes`); the aggregate worker RSS hard limit is 8 GB. Requested workers above the cap are clamped and the clamp (requested, used, cap) is reported in the run log; it is not an error. Cores, RAM and the limits are injectable for tests. The aggregate limit is also enforced on measured peak working sets: workers report their peak after each chunk and the run fails with `MemoryLimitError` above the limit.

## Failure semantics: no partial output
A worker crash (`WorkerCrashedError`, names the worker, pid, exit code and the chunk), a chunk timeout (`WorkerTimeoutError`), a missing unit (`MissingUnitError`, names the unit keys), a duplicate or unexpected unit, a worker exception (`WorkerFailedError`), a worker whose interpreter, python-flint version, platform or library path differs from the parent (`InterpreterMismatchError`, checked at start) or the aggregate RSS limit (`MemoryLimitError`) fails the whole run: the pool is terminated, the command exits 2 with the named error on stderr, and NO output file is written, no digest, no temp file. Outputs (`digests.json`, and `results.jsonl` for `--emit full`) are written only after every unit is merged, to temp names and then renamed. `--fault kill_worker:W:N`, `drop_unit:KEY` and `hang_worker:W` exist for tests.

## Determinism rules
- Workers return (unit key, result bytes); the parent orders by unit key (never completion order) and hashes `unit key LF unit sha256 LF` in key order (`result_sha256`). Within a unit contracts are sorted by contract id.
- Worker count, worker ids, timings, counters and the clamp appear only in the run log, never in results or output files.
- Workers are spawned with `PYTHONHASHSEED=0`; no result depends on unsorted set or dict iteration (the Tester shuffles contract, unit and chunk order). Each worker sets its own process-global switches (python-flint threads = 1). Same interpreter and library versions in every worker, verified at start.
- Results at 1, 2, 4 and N workers, across batch sizes and unit orderings, are identical result bytes; the single-process run is the reference.

## Measurements
`tools/m1_runner_bench.py` (heavy, not CI): phases freeze, matrix, scaling, b6, b7, arb. The machine and workload are frozen and written before the first run. Numbers and budgets are in the DECISIONS.md entry of this change and in `docs/m1/M1_RUNNER_BENCH.json`; budgets are printed verbatim from `qualification/synthetic/perf/PERF_ACCEPTANCE.md` (B6 5 s / 15 s, B7 170 / 240 min run once; under 10 minutes on 8 cores is reported, not promised). Exercised from CI time tests: `tests/m1/test_runner.py`.
