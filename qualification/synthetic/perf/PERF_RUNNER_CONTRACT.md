# Independent runner contract, contract_version 2 (JSON in / JSON out)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Provenance: SYNTHETIC. The implementation team supplies a thin executable `perf_sut` satisfying this contract; the Tester's harness never imports library code. The runner is opt-in, default single-process. Version 2 replaces version 1 (a version-1 request is rejected).

Invocation: `perf_sut --request REQ.json --response RESP.json`. Exit 0 = response written; non-zero = failure (with `errors` filled when a response can be written). Paths relative to the working directory. UTF-8, LF, canonical JSON (sorted keys, no spaces).

## Request
```
{"contract_version": 2, "request_id": "str",
 "gate": "B2|B3a|B3b|B4|B4L|B5|B6|B7|B9|B12|P1-T1|D01..D08|E01..E06|C01..C07|R01..R05|S01..S03|
          SOL-REF|SOL-HOIST|SOL-FILTER|SOL-SEED|SOL-MUT|SOL-KILL|SOL-METRICS",
 "workload": {"manifest": "perf_manifest.json", "seed": 20261029, "chain": "S|M|L|null",
              "underlyings": ["SYN1"], "sessions": [1], "cutoff_indexes": [0,1],
              "oc_window_updates": 50|5000|null, "stream_records": 100000|1000000|null,
              "set": "flat|mixed|null", "order": "natural|reversed|shuffle:<seed>"},
 "workers": 1, "batch_size": 64, "cache": "cold|warm|off|limited:<bytes>",
 "solver_mode": "reference|hoist|filter|filter_newton_seed", "certified_fallback": false,
 "mutation": null | {"kind": "input", "field": "bid", "contract_index": 5, "value": "1.2300"}
                  | {"kind": "bound", "bound_divisor": 10},
 "fault": null | {"kind": "kill_worker", "worker": 1, "after_units": 100} | {"kind": "drop_unit", "unit_key": "str"},
 "params": {"stale_limit_ns": 10000000000, "window_ns": 300000000000, "iv_tolerance": "0.0001"},
 "limits": {"ram_bytes": 0, "b9_peak_bytes": 2147483648, "aggregate_rss_hard_bytes": 8589934592},
 "repeats": 30, "warmup": 1, "emit_results": "digest|full"}
```
Unknown fields or an unknown `kind` are errors. `mutation.kind=input` drives cache rows (C02); `kind=bound` drives SOL-MUT and must report `mutation_applied`.

## Response
```
{"contract_version": 2, "request_id": "str", "provenance": "SYNTHETIC",
 "env": {"cpu": "str", "physical_cores": 0, "logical_cores": 0, "ram_bytes": 0, "os": "str", "python": "str", "affinity": "str|null"},
 "workers_requested": 1, "workers_used": 1,
 "worker_cap": {"cores": 0, "ram_bytes": 0, "b9_peak_bytes": 0, "cap": 0},   // cap = min(cores, ram/b9_peak)
 "timings_ns": [ ... one per timed repeat, call only ... ],
 "wall_ns_by_workers": {"1": [ ... ], "N": [ ... ]} | null,
 "unit_count": 1,
 "result_sha256": "hex|null", "per_cutoff_sha256": {"<index>": "hex"}, "results_digest_inputs": "hex",
 "results": [ ... ] | null,       // per unit: unit_key, status, reason, value; null on failure
 "arb_calls_per_solve": {"p50": 0, "p95": 0, "max": 0, "solves": 0, "total": 0} | null,
 "scaling_efficiency": 0.0 | null,                      // speedup(N)/N from p50 walls, same machine
 "peak_rss_bytes": 0, "peak_rss_per_worker_bytes": [ ... ], "aggregate_peak_rss_bytes": 0, "rss_samples_bytes": [ ... ],
 "cache": {"hits": 0, "misses": 0, "evictions": 0, "bytes": 0},
 "mutation_applied": false, "bound_used": {"default": "str|null", "applied": "str|null"}, "fallback_count": 0,
 "partial_output": false, "errors": []}
```
## Harness rules
1. Harness computes p50/p95/max (nearest rank) from `timings_ns`; the SUT reports none. `len(timings_ns) == repeats` is checked.
2. Result bytes compared across requests for D, E, C, SOL rows; IV within 1e-4 on decimal strings, everything else by bytes.
3. Worker count, ids, timings and completion order never appear in `results` or `result_sha256`; merge is by unit key only. Output is written after all units merge (temp file, then rename).
4. `peak_rss_*` are OS-measured process peaks. Aggregate over workers must be <= `limits.aggregate_rss_hard_bytes` (8 GB).
5. Failure (fault, killed worker, missing unit): exit non-zero, `errors` names the worker or unit, `results` and `result_sha256` are null, `partial_output` false, no output file.
6. Missing response fields fail the row.
