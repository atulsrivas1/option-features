# Independent runner contract, contract_version 3 (M2 families), rev 2

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Provenance: SYNTHETIC. Written against docs/M1_RUNNER.md (CLI, caps, failure semantics, determinism rules) and docs/m2/M2_IO_CONTRACT.md; the runner and workload internals were not read. The runner stays opt-in, default single-process; `--workers 1` is the reference path. The Tester's harness drives it as a black box and never imports library code. Version 3 supersedes the version-2 JSON of PERF_RUNNER_CONTRACT.md for M2 gate names; version-2 requests stay valid for M1 gate names only (the contract-v2 perf_sut adapter is "deferred" per M1_CLOSE; this contract defines the binding, the Developer builds it).

## A. CLI binding (M1_RUNNER compatible; unchanged options and semantics)
`python tools/m1_runner/cli.py --shape M --workers N --out OUTDIR --emit digest|full --log run.jsonl` with `--batch-size`, `--order natural|reversed|shuffle:K`, `--contract-order`, `--b9-peak-bytes`, `--aggregate-hard-bytes`, `--cores`, `--ram-bytes`, `--timeout-s`, `--count-arb`, `--fault kill_worker:W:N | drop_unit:KEY | hang_worker:W`. Outputs `digests.json` (and `results.jsonl` with `--emit full`), written only after every unit merged (temp name, then rename); failure exits 2 with a named error on stderr and writes NO output file; stderr carries `clamp: requested N used M cap C`, stdout never carries the worker count; cap = min(physical cores, floor(aggregate / B9 2 GB)); unit key `SYN1/21/045` (underlying/session/cutoff, session 21-25 evaluated); `PYTHONHASHSEED=0` in workers; hashing `unit key LF unit sha256 LF` in key order.
M2 additions requested of the tool (names ACCEPTED by the PO as proposals, conditional on consistency with M1_RUNNER.md; additive, defaults unchanged; deviations from M1_RUNNER.md: one disclosed extension, the unit key session field covers evaluated sessions 21-25 and history sessions 1-25; no change to existing options, exit codes, outputs or stdout/stderr rules; the JSON binding `perf_sut` is new, not an M1 option): `--family prints|window|volume|concentration|grid|baseline|history|episodes|store|all`, `--history-sessions 20|25`, `--series-count 500|2000|6000`, `--stream-size 100000|1000000`, `--path batched|single|incremental|full_recompute|shared_pass|separate_passes`, `--cache cold|warm|off|limited:BYTES`, `--workload-manifest m2_workload_manifest.json`, `--mutation JSON`. Added fault strings: `duplicate_unit:SYN1/21/003`, `truncate_store:BYTES`, `corrupt_store:OFFSET`.

## B. JSON binding for gate timing (`perf_sut --request REQ.json --response RESP.json`; exit 0 = response written, non-zero = failure)
UTF-8, LF, canonical JSON (sorted keys, no spaces), paths relative to the working directory.
```
Request: {"contract_version": 3, "request_id": "str",
 "gate": "M2-G0|M2-B1|M2-B2|M2-B2c|M2-B2n|M2-B3|M2-B3n|M2-B4|M2-B5|M2-B6|M2-B7|M2-B8|M2-B9|M2-B10|M2-B11|M2-B12|
          M2-B13|M2-B14|M2-B15|M2-B15r|M2-B16|M2-B17|M2-B18|P1-T1|B2|B3a|B3b|B4|B5|B6|
          G001|D01..D10|E01..E10|C01..C12|R01..R08|S01..S03|K01..K06|T01..T04",
 "workload": {"manifest": "m2_workload_manifest.json", "seed": 20261029,
              "family": "prints|window|volume|concentration|grid|baseline|history|episodes|store|all",
              "underlyings": ["SYN1"], "sessions": [21], "cutoff_indexes": [0,1],   // index 0 = cutoff i 1 (T = open + 300 s); index 77 = i 78 (close); the unit key cutoff field is this index, as SYN1/21/045
              "unit_prints": 40000, "stream_size": 100000|1000000|null, "history_sessions": 20|25|null,
              "series_count": 500|2000|6000|null, "chain": "S|M|L", "order": "natural|reversed|shuffle:<seed>"},
 "workers": 1, "batch_size": 64, "cache": "cold|warm|off|limited:<bytes>",
 "path": "batched|single|incremental|full_recompute|shared_pass|separate_passes",
 "mutation": null
   | {"kind": "input",   "field": "bid", "contract_index": 5, "value": "1.2300"}          // M1 compat
   | {"kind": "bound",   "bound_divisor": 10}                                            // M1 compat
   | {"kind": "print",   "field": "price|size|multiplier|condition_excluded|time_ns|seq", "index": 0, "value": "int|bool"}
   | {"kind": "contract","field": "right|strike|expiry|lane", "contract_id": 0, "value": "str"}
   | {"kind": "history", "series_id": "S0000", "metric": "premium", "session_id": 3, "field": "grid|total|complete", "value": "json"}
   | {"kind": "calendar","session_id": 3, "field": "minutes|drop", "value": "int|null"}
   | {"kind": "param",   "name": "window_s|premium_threshold|n_large|conc_threshold|baseline_n|k_history|multiplier|quiet_gap|x_percent", "value": "str"},
 "fault": null | {"kind": "kill_worker", "worker": 1, "after_units": 100} | {"kind": "drop_unit", "unit_key": "str"}
               | {"kind": "hang_worker", "worker": 1} | {"kind": "duplicate_unit", "unit_key": "str"}
               | {"kind": "truncate_store", "bytes": 1024} | {"kind": "corrupt_store", "offset": 0},
 "params": {"window_s": 300, "premium_threshold": "100000", "conc_threshold": "3/5", "baseline_n": 20,
            "quiet_gap": 1, "evaluation_ns": 0, "filter": "all|calls|puts", "lane": "stock|etf_index", "validate": "full|scan"},
 "limits": {"ram_bytes": 0, "b9_peak_bytes": 2147483648, "aggregate_rss_hard_bytes": 0, "store_bytes_hard": 1073741824},
 "repeats": 30, "warmup": 1, "emit_results": "digest|full"}
```
Unknown fields, unknown gate or unknown `kind` are errors. A mutation kind that does not apply to the gate is an error, never ignored, and the response reports `mutation_applied: true` when it took effect. `kind=input` and `kind=bound` are the M1 forms, kept for the M1 regression gates.
```
Response: {"contract_version": 3, "request_id": "str", "provenance": "SYNTHETIC",
 "env": {"cpu": "str", "physical_cores": 0, "logical_cores": 0, "ram_bytes": 0, "os": "str", "python": "str", "affinity": "str|null"},
 "workers_requested": 1, "workers_used": 1, "worker_cap": {"cores": 0, "ram_bytes": 0, "b9_peak_bytes": 0, "cap": 0},
 "timings_ns": [ ... one per timed repeat, call only ... ], "timings_with_synthesis_ns": [ ... ] | null,
 "wall_ns_by_workers": {"1": [ ... ], "N": [ ... ]} | null, "unit_count": 0, "throughput_units": 0,
 "result_sha256": "hex|null", "per_cutoff_sha256": {"<index>": "hex"}, "per_unit_sha256": {"SYN1/21/045": "hex"},
 "store_content_sha256": "hex|null",
 "results": [ ... ] | null,      // canonical IO-contract lines: output_id, series_id, session_id, evaluation_ns, status, reason, code, value, fired, params, coverage, label, lane, version
 "truth_check": {"f4_f17_ok": true, "f7_ok": true, "rank_ok": true, "episodes_gap1_total": 0, "episodes_gap5_total": 0, "grid_sha256": "hex"} | null,
 "transfer": {"mode": "shared_memory|mmap|store_load|rebuild_session", "seconds": 0.0, "bytes_per_worker": 0} | null,
 "store": {"bytes": 0, "records": 0, "write_ns": 0, "read_ns": 0, "round_trip_sha256": "hex", "series_held": 0, "retained_sessions": 0, "error": "str|null"} | null,
 "peak_rss_bytes": 0, "peak_rss_per_worker_bytes": [ ... ], "aggregate_peak_rss_bytes": 0, "rss_samples_bytes": [ ... ],
 "cache": {"hits": 0, "misses": 0, "evictions": 0, "bytes": 0},   // log only, never part of results
 "scaling_efficiency": 0.0 | null, "mutation_applied": false, "partial_output": false, "errors": []}
```
`status` is closed: `available`, `unavailable`, `invalid_input`; `reason` closed: `insufficient_history`, `session_not_complete`, `insufficient_window`, `zero_denominator`, or null; gate order invalid_input, insufficient_history, session_not_complete, insufficient_window, zero_denominator. A reason outside the set or a status/reason flip between paths is a failure.

## Harness rules
1. Harness computes p50/p95/max (nearest rank; p5 for rates) from `timings_ns`; the SUT reports none. `len(timings_ns) == repeats` is checked.
2. All M2 outputs are exact (integers, reduced "n/d" strings): comparisons are by bytes, zero tolerance. M1 IV rows keep the M1 tolerance rule.
3. Worker count, ids, timings, cache stats and store hashes never appear in `results` or `result_sha256` (run log only); merge by unit key, canonical order.
4. Failure (kill, hang, missing, duplicate unit, interpreter mismatch, memory limit, damaged store): exit 2, `errors` names worker or unit, `results` and hashes null, `partial_output` false, no output file; previous outputs removed at start; only own PIDs terminated, never by name.
5. Missing response fields fail the row. Truth checks run against m2_workload_manifest.json before timings are accepted.
6. Reports print the label sentence in the header and "synthetic workload, relative engineering budget" beside numbers; no recorded-data claim.
