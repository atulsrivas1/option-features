#!/usr/bin/env python3
"""Generates m3a_perf_resource_rows.json (SYNTHETIC, deterministic, LF, ASCII). Rows are data in this script, authored
from docs/m3a/M3A_GATE_BUDGETS.md sections 3, 5, 7 and docs/m3a/M3A_FIXTURE_REQUIREMENTS.md section 7.
Groups: g0 (1), workloads W (15: M3A-G0, M3A-B1..B13, plus M3A-B5n), D determinism (12), E batched vs single (12),
C cache (14), R memory (8), S scaling (3), K runner (6) = 71 rows; plus the infrastructure mutant table.
Usage: python gen_m3a_resource_rows.py [--out FILE]"""
import argparse
import json

from m3a_common import PERF_LABEL, PROVENANCE, QUAL

W = [1, 2, 4, "N"]
ORD = ["natural", "reversed", "shuffle:1", "shuffle:2"]


def row(id_, group, gate, vary, values, workload, expect):
    return {"id": id_, "group": group, "gate": gate, "vary": vary, "values": values, "workload": workload,
            "expect": expect}


ROWS = [
    row("G001", "g0", "M3A-G0", "workers", [1, "N"],
        "one underlying, size M, SYN1/03/045, all-valid-quote chain: M2-G0 set + M2 flow outputs (M2-B9) + M3a surface set "
        "(25-delta put and call IV per expiry, tenors 9, 30, 91, M3A-3..7, M3A-10, M3A-11) as ONE timed unit",
        "gated at ONE worker only, compute-only; 5 s p95 / 15 s hard (nearest rank); at least 30 timed repeats after one "
        "warm-up, unit set rotated; 2, 4, N workers informational with efficiency; with-synthesis printed beside it; "
        "sum check printed (2.66 + 1.2 + 0.1 = 3.96 s) and never gated; machine frozen and written before the first repeat"),
    # workloads, one per gate
    row("W01", "workloads", "M3A-G0", "size", ["M"], "all-valid-quote smile chain, 2,000 contracts, 8 expiries bracketing 9, 30, 91",
        "frozen facts rechecked within +/- 10 percent before the run; output set exactly as G001"),
    row("W02", "workloads", "M3A-B1", "size", ["M"], "surface increment, contract IVs cached, one cutoff, tenors 9, 30, 91, measured per delta convention (spot and forward, R-157)",
        "<= 0.1 s p95, hard 0.5 s; delta evaluations <= 200 (hard 400) counted by the SUT; batch of 103 chains informational"),
    row("W03", "workloads", "M3A-B2", "unit", ["one expiry, one side"], "one 25-delta point on the size-M chain, IVs cached",
        "<= 2 ms p95, hard 10 ms; value within 1e-4 of chain_truth in the manifest on vega >= 4 expiries"),
    row("W04", "workloads", "M3A-B3", "size", ["M"], "tenors 9, 30, 91 from cached ATM IVs",
        "<= 0.1 s p95, hard 0.5 s; tenor IV within 1e-4 of the manifest tenor truth"),
    row("W05", "workloads", "M3A-B4", "names", [1, 103], "point outputs M3A-3..7, 10, 11 from point_inputs (103 names)",
        "<= 1 ms per name and <= 110 ms per batch p95; hard 5 ms and 550 ms; every value equals point_truth (exact rationals)"),
    row("W06", "workloads", "M3A-B5", "series", ["V1", "V9", "V3"], "rank over 252 sessions per series; V3 reads 252 grid entries at minute 195, measured for BOTH forms (atm_iv and iv30 series)",
        "V1, V9 <= 50 us (hard 200 us); V3 <= 150 us (hard 600 us) for each form; equals rank_truth"),
    row("W07", "workloads", "M3A-B5n", "names", [103], "103 names x 3 series at one cutoff, for each iv_form",
        "<= 20 ms (V1, V9), <= 50 ms (V3), each form; hard 80 ms, 200 ms; absolute times, linear in names"),
    row("W08", "workloads", "M3A-B6", "records", [181692], "append 252 sessions x 103 names x 7 series (181,692 records)",
        "records/s >= 25,000 (p5 of the sample), hard 5,000; retention 252 per series"),
    row("W09", "workloads", "M3A-B7", "form", ["canonical LF text", "mmap snapshot"], "round trip of the B6 set",
        "write >= 25,000 and read >= 50,000 records/s (hard 5,000 and 10,000); store content hash identical after the round trip"),
    row("W10", "workloads", "M3A-B8", "limit", ["peak RSS", "store bytes"], "B10 workload per process; store at retention 252",
        "peak RSS <= 2 GB (hard 4 GB); store <= 768 MiB (hard 1 GiB per worker, private bytes); bytes per series reported"),
    row("W11", "workloads", "M3A-B9", "workers", W, "see D and E rows", "result hashes identical, hard"),
    row("W12", "workloads", "M3A-B10", "grid", ["5 x 5 x 78"], "1,950 units, size M, all outputs, run once",
        "<= 170 min, hard 240 min; 60 min at N workers is an informational owner target"),
    row("W13", "workloads", "M3A-B11", "cutoffs", [78], "78 cutoffs of SYN1/03, size M; every cutoff has its own spot (manifest sweep_B11)",
        "sweep wall / (78 x single-cutoff wall) <= 1.1, hard 1.5; no reuse across cutoffs claimed"),
    row("W14", "workloads", "M3A-B12", "size", ["S", "M", "L"], "delta evaluations per chain counted by the SUT",
        "size M <= 200 (hard 400); a count near the contract count (2,000) means the bracketed search degenerated"),
    row("W15", "workloads", "M3A-B13", "workers", [1, 4], "5-underlying compute phase", ">= 2.0x p50 wall ratio at 4 workers; N/A under 4 physical cores"),
    # D determinism (M3A-B9)
    row("D01", "determinism", "M3A-B9", "workers", W, "unit SYN1/03/*, 78 cutoffs, all M3a outputs", "per-cutoff and whole-run sha256 identical, 3 repeats"),
    row("D02", "determinism", "M3A-B9", "workers", W, "5 underlyings x 5 sessions x 78 cutoffs", "identical sha256 (run hash over unit key LF unit sha LF in key order)"),
    row("D03", "determinism", "M3A-B9", "batch_size", [1, 7, 64, "all"], "SYN1/03", "identical sha256"),
    row("D04", "determinism", "M3A-B9", "order", ORD, "cutoff order", "identical sha256 after canonical keyed ordering"),
    row("D05", "determinism", "M3A-B9", "order", ORD, "underlying order", "identical sha256"),
    row("D06", "determinism", "M3A-B9", "contract_order", ORD, "contract order within a chain", "identical sha256"),
    row("D07", "determinism", "M3A-B9", "expiry_order", ORD, "expiry order within a chain", "identical sha256"),
    row("D08", "determinism", "M3A-B9", "name_order", ORD, "name order in the 103-name batches", "identical sha256; results keyed by name, never completion order"),
    row("D09", "determinism", "M3A-B9", "tie_order", ["seq", "shuffled arrival of equal-ns quotes"], "quotes sharing a timestamp (about 1 percent)", "identical sha256 (documented tie rules decide)"),
    row("D10", "determinism", "M3A-B9", "append_order", ["canonical", "shuffled sessions"], "history append of the 103-name store",
        "canonical-only append accepted; out-of-order append is the closed code out_of_order_append (no silent reorder); same hash"),
    row("D11", "determinism", "M3A-B9", "workers", W, "history store build (7 series per name), persistence round trip and mmap attach", "store content hash identical at every worker count and after the round trip"),
    row("D12", "determinism", "M3A-B9", "mutant", ["worker count in a result", "completion order in a result", "float in an output"],
        "infrastructure mutants M-I05, M-I06, M-I07 (table below)", "these rows fail on the mutants (a row that passes a mutant is a defect of the row)"),
    # E batched vs single (zero tolerance)
    row("E01", "equivalence", "M3A-B9", "path", ["batched", "single"], "M3A-0 surface frame, 103 chains", "bytes equal, status and reason equal, zero tolerance"),
    row("E02", "equivalence", "M3A-B9", "path", ["batched", "single"], "25-delta put and call IV for every expiry, sizes S, M, L", "bytes equal; equals the Tester reference on rank positions and interpolation"),
    row("E03", "equivalence", "M3A-B9", "path", ["batched", "single"], "tenors 9, 30, 91", "bytes equal; no extrapolation outside the expiry range"),
    row("E04", "equivalence", "M3A-B9", "path", ["batched", "single"], "M3A-1 and M3A-8 (V1, V9) over 103 names x 252 sessions", "bytes equal; equals rank_truth; last name of the last batch not dropped"),
    row("E05", "equivalence", "M3A-B9", "path", ["batched", "single"], "M3A-2 (V3) same-minute over 103 names", "bytes equal; equals rank_truth minute 195"),
    row("E06", "equivalence", "M3A-B9", "path", ["batched", "single"], "M3A-3 to M3A-6 over 103 names", "bytes equal; equals point_truth"),
    row("E07", "equivalence", "M3A-B9", "path", ["batched", "single"], "M3A-7, M3A-9, M3A-10, M3A-11 over 103 names", "bytes equal; sign_changed equals point_truth; zero never a flip"),
    row("E08", "equivalence", "M3A-B9", "path", ["batched", "single"], "unavailable cases (zero_range_history name 101, insufficient_history, no_delta_bracket) at validate full and scanned", "status and reason equal on every name; no status or reason flip"),
    row("E09", "equivalence", "M3A-B9", "path", ["incremental", "full_recompute"], "cutoff sweep, 78 cutoffs", "bytes equal per cutoff"),
    row("E10", "equivalence", "M3A-B9", "path", ["library", "tester_reference"], "25-delta and tenor interpolation, at least 20,000 randomized cases each", "zero differences"),
    row("E11", "equivalence", "M3A-B9", "path", ["library", "tester_reference"], "rank forms and the sign-change rule, at least 20,000 randomized cases each", "zero differences"),
    row("E12", "equivalence", "M3A-B9", "validate", ["full", "scanned"], "the structural rows and 103-name batches", "same codes at validate=full and scanned on trusted inputs; a code only full detects is reported, never skipped"),
    # C cache
    row("C01", "cache", "M3A-B9", "cache", ["cold", "warm"], "any M3a output, same request twice", "bytes equal; warm shows hits in the log"),
    row("C02", "cache", "M3A-B9", "param", ["tenor", "delta_target", "threshold", "X", "direction", "min_sessions", "max_sessions", "minute", "prior_sessions"], "one parameter changed per run", "key changes, recompute, bytes equal cold run of the changed input"),
    row("C03", "cache", "M3A-B9", "contract_field", ["expiry_days", "right", "strike", "style", "condition", "event_ns", "known_at_ns", "contract_id"], "one contract field changed per run", "key changes, recompute"),
    row("C04", "cache", "M3A-B9", "quote_field", ["bid", "ask"], "one quote changed by one tick", "key changes; IV and delta caches recompute"),
    row("C05", "cache", "M3A-B9", "chain_field", ["spot", "rate", "dividend_yield", "cutoff_ns"], "one request-level field changed", "key changes, recompute"),
    row("C06", "cache", "M3A-B9", "history", ["content_sha256", "calendar", "k"], "one history record, calendar entry or retention changed", "key changes; only the series touched are invalidated"),
    row("C07", "cache", "M3A-B9", "lane", ["stock", "etf_index"], "same fields in different lanes", "no hit crosses lanes"),
    row("C08", "cache", "M3A-B9", "scope", ["chain"], "two chains with equal contracts and different spot or lane", "no hit across chains"),
    row("C09", "cache", "M3A-B9", "scope", ["cutoff"], "same chain at cutoff i and i + 1", "no hit across cutoffs (IV and delta caches are per chain and cutoff)"),
    row("C10", "cache", "M3A-B9", "scope", ["underlying"], "SYN1 and SYN2 with equal fields", "no hit across underlyings"),
    row("C11", "cache", "M3A-B9", "cache", ["limited:1048576", "limited:16777216", "off"], "M3A-G0 and 103-name workloads", "bytes equal to unbounded; evictions recorded; eviction never changes bytes"),
    row("C12", "cache", "M3A-B9", "bound", ["size", "eviction policy"], "cache of the SUT", "bounded size and eviction recorded in the log"),
    row("C13", "cache", "M3A-B9", "scope", ["worker"], "per-process caches", "no shared mutable state between workers"),
    row("C14", "cache", "M3A-B9", "stats", ["log only"], "cache hits, misses, evictions, bytes", "never in results or result_sha256"),
    # R memory
    row("R01", "memory", "M3A-B8", "limit", ["b9_peak_bytes"], "B10-with-M3a and M3A-G0 workloads, per process", "peak RSS <= 2 GB budget, 4 GB hard"),
    row("R02", "memory", "M3A-B8", "repeats", [30], "every timed gate", "post-GC RSS slope <= 1 MB per repeat; last-10 mean within 5 percent of first-10 mean"),
    row("R03", "memory", "M3A-B8", "retention", [252], "store at retention 252, 103 names x 7 series",
        "<= 768 MiB budget (RULED; 805,306,368 B), 1 GiB hard per worker (1,073,741,824 B) (budgets doc B8); bytes per series reported; the 30 percent tolerance against the formula (162 MB raw, 486 MB M2 layout with two minute grids; 485,896,320 B = 463.4 MiB = 60.34 percent of the 768 MiB budget (805,306,368 B), 45.25 percent of the 1 GiB hard limit 1,073,741,824 B) is a PROPOSAL carried from M2 R03, not a budgets-doc number"),
    row("R04", "memory", "M3A-B8", "retention", [60, 252, 253], "append past K (scalar series k = 252, M2 series keep k <= 60)", "retention never exceeds K; the oldest session is evicted; M2 default k = 60 unchanged"),
    row("R05", "memory", "M3A-B8", "workers", W, "aggregate worker RSS", "reported; cap rule min(cores, floor(aggregate / 2 GB)); MemoryLimitError fails the run"),
    row("R06", "memory", "M3A-B8", "size", ["L"], "size L chain, 1 worker", "within the 4 GB hard limit"),
    row("R07", "memory", "M3A-B8", "view", ["mmap snapshot", "store_load", "shared_memory"], "B16-style worker start: 721 series, 181,692 records at retention 252",
        "M2-B16 limits (M2 contract section 9.12): <= 5 s and <= 512 MB per worker start budget, 15 s and 1 GiB hard; 721 series is below 2,000 so the budgets are the gate; content_hash() compared after attach"),
    row("R08", "memory", "M3A-B8", "accounting", ["view_in_worker_rss"], "worker RSS with the view", "the view counts in that worker RSS; private and shared mapped bytes reported separately"),
    # S scaling
    row("S01", "scaling", "M3A-B13", "workers", W, "5-underlying compute phase, size M, all outputs", ">= 2.0x at 4 workers p50 wall; efficiency at N reported; N/A under 4 physical cores"),
    row("S02", "scaling", "M3A-B13", "workers", W, "103-name batch gates sharded by name, merged in canonical order", "informational efficiency; correctness rows pass at every count"),
    row("S03", "scaling", "M3A-B6", "workers", W, "history build parallel across 5 underlyings", "at most 5-way; serial share of wall reported"),
    # K runner
    row("K01", "runner", "M3A-B9", "fault", ["kill_worker:1:100"], "any M3a unit set, 4 workers, M3a outputs in the unit", "exit 2, WorkerCrashedError, no output file, no digest, no temp file"),
    row("K02", "runner", "M3A-B9", "fault", ["drop_unit:SYN1/03/003"], "any M3a unit set", "exit 2, MissingUnitError, no partial output"),
    row("K03", "runner", "M3A-B9", "fault", ["duplicate_unit:SYN1/03/003"], "any M3a unit set", "exit 2, duplicate or unexpected unit error"),
    row("K04", "runner", "M3A-B9", "interpreter", ["mismatch"], "worker interpreter differs", "InterpreterMismatchError at start"),
    row("K05", "runner", "M3A-B9", "output", ["no partial output"], "failure with M3a outputs half merged", "exit 2, results and hashes null, partial_output false, no file"),
    row("K06", "runner", "M3A-B9", "hygiene", ["previous_outputs", "own_pids_only"], "rerun in the same --out", "digests.json, results.jsonl and .*.tmp of a previous run removed at start; only own process ids terminated"),
]

MUTANTS = [
    ("M-I01", "cache key missing a field (contract style)", ["C03", "C01", "E12"]),
    ("M-I02", "cache key missing the cutoff (hit across cutoffs)", ["C09", "E09"]),
    ("M-I03", "cache key missing spot (hit across chains)", ["C05", "C08"]),
    ("M-I04", "batched path drops the last name of the last batch", ["E04", "E05", "E06", "E07", "D03", "D08"]),
    ("M-I05", "worker count in a result", ["D01", "D02", "D11"]),
    ("M-I06", "completion order in a result", ["D02", "D04", "D08"]),
    ("M-I07", "float used in an output (not a decimal string or exact value)", ["E02", "E10", "E11"]),
    ("M-I08", "scanned validation skips a full-only code", ["E12", "E08"]),
    ("M-I09", "cache shared between lanes", ["C07", "C08"]),
    ("M-I10", "history append reorders sessions silently", ["D10", "R04"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="m3a_perf_resource_rows.json")
    a = ap.parse_args()
    ids = [r["id"] for r in ROWS]
    assert len(ids) == len(set(ids)), "duplicate ids"
    n = {g: sum(1 for r in ROWS if r["group"] == g) for g in dict.fromkeys(r["group"] for r in ROWS)}
    assert n == {"g0": 1, "workloads": 15, "determinism": 12, "equivalence": 12, "cache": 14, "memory": 8, "scaling": 3,
                 "runner": 6}, n
    known = set(ids)
    behav = {r["id"] for r in ROWS if r["group"] in ("determinism", "equivalence", "cache", "memory", "runner")}
    for mid, _, rows in MUTANTS:
        assert len(rows) >= 2 and set(rows) <= behav and "D12" not in rows, mid
    for _, _, rows in MUTANTS:
        assert set(rows) <= known
    doc = {"contract_version": 4, "label": PERF_LABEL, "provenance": PROVENANCE, "qualification_label": QUAL,
           "row_count": len(ROWS), "rows": ROWS,
           "infrastructure_mutants": [{"id": i, "mutant": m, "must_fail_rows": r} for i, m, r in MUTANTS]}
    with open(a.out, "w", encoding="ascii", newline="\n") as f:
        f.write(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
    print(len(ROWS), "rows", n)


if __name__ == "__main__":
    main()
