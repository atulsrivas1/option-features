# Independent runner contract, contract_version 4 (M3a families), rev 1

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Provenance: SYNTHETIC. Written against docs/M1_RUNNER.md (CLI, caps, failure semantics, determinism rules), the M2 perf contract version 3 (qualification/synthetic/m2/perf/M2_PERF_RUNNER_CONTRACT.md) and docs/m3a/M3A_GATE_BUDGETS.md sections 5 and 7; runner and library internals were not read. The runner stays opt-in, default single-process; `--workers 1` is the reference path. The harness drives it as a black box and never imports library code. Version 4 supersedes version 3 for M3a gate names only; version-3 requests stay valid for M2 gate names and version-2 for M1 gate names. The `perf_sut` adapter is deferred (R-80, M1_CLOSE); this note defines the binding the Developer builds.

## A. CLI binding (M1_RUNNER and M2 additions compatible; unchanged options and semantics)
`python tools/m1_runner/cli.py --shape M --workers N --out OUTDIR --emit digest|full --log run.jsonl` with every M1 and M2 option unchanged (`--batch-size`, `--order natural|reversed|shuffle:K`, `--contract-order`, `--b9-peak-bytes`, `--aggregate-hard-bytes`, `--cores`, `--ram-bytes`, `--timeout-s`, `--count-arb`, `--fault kill_worker:W:N | drop_unit:KEY | hang_worker:W | duplicate_unit:KEY | truncate_store:BYTES | corrupt_store:OFFSET`, `--family`, `--history-sessions`, `--series-count`, `--path`, `--cache`, `--workload-manifest`, `--mutation JSON`). Outputs `digests.json` (and `results.jsonl` with `--emit full`), written only after every unit merged (temp name, then rename); failure exits 2 with a named error on stderr and writes NO output file; stderr carries `clamp: requested N used M cap C`; stdout never carries the worker count; cap = min(physical cores, floor(aggregate / B9 2 GB)); `PYTHONHASHSEED=0` in workers; hashing `unit key LF unit sha256 LF` in key order.
M3a additions requested of the tool (additive, defaults unchanged, names are proposals for PO acceptance):
| Option | Values | Meaning |
|---|---|---|
| `--family` (extended) | `surface`, `tenor`, `point`, `rank`, `history`, `store`, `m3a` (all M3a outputs) beside the M2 values | which output family a unit computes; `m3a` = M3A-0 to M3A-11 |
| `--names N` | 103 | batch size for the point and rank gates (names fixed at 103, budgets doc A4) |
| `--history-sessions` (extended) | 252 | prior sessions per series |
| `--grid-units` | `5x5x78` | underlyings x evaluated sessions x cutoffs; unit key `SYN1/03/045` (session field = ordinal 01-05) |
| `--sweep` | 78 | cutoff sweep of one session (M3A-B11) |
| `--path` (extended) | `batched`, `single`, `incremental`, `full_recompute` | batched equals one-surface-at-a-time bytes |
| `--validate` | `full`, `scanned` | structural validation scope; same codes (M2 convention) |
| `--delta-count` | flag | log-only counter of delta evaluations per chain (M3A-B12) |

## B. JSON binding for gate timing (`perf_sut --request REQ.json --response RESP.json`; exit 0 = response written, non-zero = failure)
UTF-8, LF, canonical JSON (sorted keys, no spaces), paths relative to the working directory.
```
Request: {"contract_version": 4, "request_id": "str",
 "gate": "M3A-G0|M3A-B1|M3A-B2|M3A-B3|M3A-B4|M3A-B5|M3A-B5n|M3A-B6|M3A-B7|M3A-B8|M3A-B9|M3A-B10|M3A-B11|M3A-B12|M3A-B13|
          G001|W01..W15|D01..D12|E01..E12|C01..C14|R01..R08|S01..S03|K01..K06",
 "workload": {"manifest": "m3a_workload_manifest.json", "seed": 20261030,
              "family": "surface|tenor|point|rank|history|store|m3a",
              "underlyings": ["SYN1"], "sessions": [3], "cutoff_indexes": [45],   // unit key SYN1/03/045
              "chain": "S|M|L", "names": 103, "history_sessions": 252, "series": ["iv30_close","skew25","term_30_91","iv30_min"],
              "order": "natural|reversed|shuffle:<seed>", "contract_order": "natural|shuffle:<seed>", "expiry_order": "natural|shuffle:<seed>"},
 "workers": 1, "batch_size": 64, "cache": "cold|warm|off|limited:<bytes>",
 "path": "batched|single|incremental|full_recompute", "validate": "full|scanned",
 "mutation": null
   | {"kind": "chain", "field": "expiry_days|right|strike|bid|ask|event_ns|known_at_ns|style|condition|contract_id", "contract_index": 5, "value": "json"}
   | {"kind": "request", "field": "spot|rate|dividend_yield|cutoff_ns|lane", "value": "json"}
   | {"kind": "param", "name": "tenor|delta_target|threshold|x_percent|direction|min_sessions|max_sessions|minute|prior_sessions", "value": "json"}
   | {"kind": "history", "series_id": "str", "metric": "str", "session_id": 3, "field": "grid|total|complete", "value": "json"}
   | {"kind": "calendar", "session_id": 3, "field": "minutes|drop", "value": "int|null"},
 "fault": null | {"kind": "kill_worker", "worker": 1, "after_units": 100} | {"kind": "drop_unit", "unit_key": "str"}
               | {"kind": "hang_worker", "worker": 1} | {"kind": "duplicate_unit", "unit_key": "str"}
               | {"kind": "truncate_store", "bytes": 1024} | {"kind": "corrupt_store", "offset": 0},
 "params": {"tenors": [9,30,91], "delta_target": "0.25", "x_percent": 5, "min_sessions": 20, "max_sessions": 252,
            "minute": 195, "prior_sessions": 1, "mode": "intraday|close", "lane": "stock|etf_index", "feed_delay_tag": "live|delayed"},
 "limits": {"ram_bytes": 0, "b9_peak_bytes": 2147483648, "aggregate_rss_hard_bytes": 0, "store_bytes_budget": 805306368, "store_bytes_hard": 1073741824},
 "repeats": 30, "warmup": 1, "emit_results": "digest|full"}
```
Unknown fields, unknown gate or unknown `kind` are errors. A mutation kind that does not apply to the gate is an error, never ignored, and the response reports `mutation_applied: true` when it took effect.
```
Response: {"contract_version": 4, "request_id": "str", "provenance": "SYNTHETIC",
 "env": {"cpu": "str", "physical_cores": 0, "logical_cores": 0, "ram_bytes": 0, "os": "str", "python": "str", "affinity": "str|null"},
 "workers_requested": 1, "workers_used": 1, "worker_cap": {"cores": 0, "ram_bytes": 0, "b9_peak_bytes": 0, "cap": 0},
 "timings_ns": [ ... one per timed repeat, call only ... ], "timings_with_synthesis_ns": [ ... ] | null,
 "wall_ns_by_workers": {"1": [ ... ], "N": [ ... ]} | null, "unit_count": 0, "throughput_units": 0,
 "result_sha256": "hex|null", "per_cutoff_sha256": {"<index>": "hex"}, "per_unit_sha256": {"SYN1/03/045": "hex"},
 "store_content_sha256": "hex|null",
 "results": [ ... ] | null,   // canonical IO-contract lines: output_id (M3A-0..M3A-11), series_id, session_id, evaluation_ns, status, reason, code, value, fired, params, coverage, labels, lane, version
 "delta_evaluations": {"per_chain_p50": 0, "per_chain_max": 0, "chains": 0, "total": 0} | null,   // M3A-B12, log only
 "workload_facts": {"chains": {"M": {"contracts": 0, "expiries": 0, "strikes_per_expiry": 0, "quote_count": 0}}, "store": {"names": 0, "sessions": 0, "records": 0}} | null,
 "truth_check": {"chain_truth_ok": true, "rank_truth_ok": true, "point_truth_ok": true, "max_iv_error": "0.00000000"} | null,
 "transfer": {"mode": "shared_memory|mmap|store_load|rebuild_session", "seconds": 0.0, "bytes_per_worker": 0, "private_bytes": 0, "shared_mapped_bytes": 0} | null,
 "store": {"bytes": 0, "bytes_per_series": 0, "records": 0, "write_ns": 0, "read_ns": 0, "round_trip_sha256": "hex", "series_held": 0, "retained_sessions": 0, "error": "str|null"} | null,
 "peak_rss_bytes": 0, "peak_rss_per_worker_bytes": [ ... ], "aggregate_peak_rss_bytes": 0, "rss_samples_bytes": [ ... ],
 "cache": {"hits": 0, "misses": 0, "evictions": 0, "bytes": 0},   // log only, never part of results
 "scaling_efficiency": 0.0 | null, "mutation_applied": false, "partial_output": false, "errors": []}
```
`status` is closed: `available`, `unavailable`, `invalid_input`; `reason` closed: the set of matrix section 5 (no_atm_strike, no_bracketing_expiry, price_out_of_bounds, upper_asymptote, sigma_cap, precision_exhausted, bound_precision, iteration_budget, insufficient_history, session_not_complete, zero_denominator, no_delta_bracket, low_surface_coverage, fewer_than_two_expiries, no_prior_reading, zero_range_history) or null; a reason outside the set (`insufficient_window` is not in it) or a status or reason flip between paths is a failure. Solver-derived values are decimal strings rounded half to even to 8 decimals; quote-derived values are ints or reduced "n/d".

## Harness rules
1. Harness computes p50/p95/max (nearest rank; p5 for rates) from `timings_ns`; the SUT reports none. `len(timings_ns) == repeats` is checked.
2. Quote-derived and rank outputs: bytes, zero tolerance. Solver-derived values: IV within 1e-4 and forward within 1e-6 of the manifest truth on vega >= 4 contracts (R-94); canonical hashes of solver-derived values are Windows-only.
3. Worker count, ids, timings, cache stats and store hashes never appear in `results` or `result_sha256` (run log only); merge by unit key, canonical order.
4. Failure (kill, hang, missing, duplicate unit, interpreter mismatch, memory limit, damaged store): exit 2, `errors` names worker or unit, `results` and hashes null, `partial_output` false, no output file; previous outputs removed at start; only own PIDs terminated, never by name.
5. Missing response fields fail the row. Truth checks and the frozen-fact recheck (+/- 10 percent, `gen_m3a_workloads.py --recheck`) run before timings are accepted.
6. Reports print the label sentence in the header and "synthetic workload, relative engineering budget" beside numbers; no recorded-data claim.

## C. Deviations from docs/M1_RUNNER.md and the M2 contract version 3 (all disclosed; none silent)
- D1: `contract_version` 4 for M3a gate names (M2 says 3 for M2 names); an ask to the PO whether a minor bump (3.1) is preferred.
- D2: the unit key session field is the evaluated-session ordinal 01-05 (M2 used 21-25 and M1 used 01-03); history sessions 1-256 are generated, each evaluated session has 252 prior sessions.
- D3: `--family m3a`, `--names`, `--grid-units`, `--sweep`, `--validate`, `--delta-count` are new options; every existing option, exit code, output file and stdout/stderr rule is unchanged.
- D4: `delta_evaluations` (M3A-B12) is a new response field and a new log-only counter; no such counter exists in the M1 runner text (the SUT must count, the harness cannot).
- D5: mutation kinds `chain`, `request` and `param` replace the M1 compat kinds `input` and `bound` for M3a gate names (M1 kinds stay valid on M1 gate names); `kind=param` field names follow IO contract section 2.
- D6: gate names `M3A-B5n` and `W01..W15` are added (budgets doc has B5n; requirements list B1-B13).
- D7: M3A-G0 combines the M2 workload (runner-built prints and quotes, 40,000 prints per unit) with the G8 chain; the harness cannot check the M2 part against the G8 manifest.
- D8: `validate` is a request field (M2 carried `validate` inside `params`); here it is top-level next to `path` for clarity.
