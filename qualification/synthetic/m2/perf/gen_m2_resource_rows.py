#!/usr/bin/env python3
"""Generates m2_perf_resource_rows.json (SYNTHETIC, deterministic, LF), rev 2 against the ruled docs
(M2_GATE_BUDGETS section 6, M2_FIXTURE_REQUIREMENTS section 7). Rows are data in this script.
Usage: python gen_m2_resource_rows.py [--out FILE]"""
import argparse
import json

QUAL = "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12"
W = [1, 2, 4, "N"]
ORD = ["natural", "reversed", "shuffle:1", "shuffle:2"]


def row(id_, group, gate, vary, values, workload, expect):
    return {"id": id_, "group": group, "gate": gate, "vary": vary, "values": values,
            "workload": workload, "expect": expect}


ROWS = [
    # G0 first task gate
    row("G001", "g0", "M2-G0", "workers", [1, "N"], "one underlying, size M, all-valid chain, 1 cutoff, every M1+P1 output as ONE timed unit", "gated at 1 worker only (5 s / 15 s p95, 30 repeats); N-worker figures informational; compute-only gated, with-synthesis printed"),
    # D determinism (M2-B14)
    row("D01", "determinism", "M2-B14", "workers", W, "unit SYN1/21/*, 78 cutoffs, all M2 outputs", "per-cutoff and whole-run sha256 identical, 3 repeats"),
    row("D02", "determinism", "M2-B14", "workers", W, "5 underlyings x sessions 21-25 x 78 cutoffs", "identical sha256 (run hash over unit key LF unit sha LF in key order)"),
    row("D03", "determinism", "M2-B14", "batch_size", [1, 7, 64, "all"], "SYN1/21", "identical sha256"),
    row("D04", "determinism", "M2-B14", "order", ORD, "cutoff order", "identical sha256 after canonical keyed ordering"),
    row("D05", "determinism", "M2-B14", "order", ORD, "underlying order", "identical sha256"),
    row("D06", "determinism", "M2-B14", "contract_order", ORD, "contract order within a unit", "identical sha256"),
    row("D07", "determinism", "M2-B14", "series_order", ORD, "series order in the history store and in batched reads", "identical sha256; store content hash identical"),
    row("D08", "determinism", "M2-B14", "tie_order", ["seq", "shuffled arrival of equal-ns prints"], "print stream with same-nanosecond ties (about 1 percent)", "identical sha256 (documented tie rules decide)"),
    row("D09", "determinism", "M2-B14", "workers", W, "history store build and persistence, 250,000 records", "store content hash identical at every worker count"),
    row("D10", "determinism", "M2-B14", "append_order", ["canonical", "shuffled sessions"], "history append", "canonical-only append accepted; out-of-order closed error (no silent reorder); same hash after the canonical rerun"),
    # E batched vs single (zero tolerance)
    row("E01", "equivalence", "M2-B14", "path", ["batched", "single"], "M2-1 F1 and M2-4 F4, 1e5 prints", "bytes equal, status and reason equal"),
    row("E02", "equivalence", "M2-B14", "path", ["batched", "single"], "M2-5 F17 closed trailing window, SYN1/21, 78 cutoffs", "bytes equal; equals window_truth in manifest"),
    row("E03", "equivalence", "M2-B14", "path", ["batched", "single"], "M2-6 F7, 200 concentration cases", "bytes equal; equals the manifest f7 truth; 0.60 boundary classes exact"),
    row("E04", "equivalence", "M2-B14", "path", ["batched", "single"], "M2-2/3/10 percentile rank, N = 500, 2,000, 6,000", "bytes equal; equals rank_truth (N = 500); last batch series not dropped, order kept"),
    row("E05", "equivalence", "M2-B14", "path", ["batched", "single"], "M2-7/8 median and mean ratios, N = 2,000", "bytes equal; zero median gives zero_denominator on that ratio only"),
    row("E06", "equivalence", "M2-B14", "path", ["batched", "single"], "M2-9/10 volume shares and put-call ratio", "bytes equal"),
    row("E07", "equivalence", "M2-B14", "path", ["batched", "single"], "M2-11 F12, gap 1 and 5, 500/2,000/6,000 series and the 1e6-point stream", "bytes equal; counts equal episodes truth in manifest"),
    row("E08", "equivalence", "M2-B14", "path", ["shared_pass", "separate_passes"], "M2-B10 one pass vs six passes, 1e5 and 1e6 prints", "bytes equal; time ratio reported"),
    row("E09", "equivalence", "M2-B14", "path", ["incremental", "full_recompute"], "cutoff sweep, 78 cutoffs", "bytes equal per cutoff"),
    row("E10", "equivalence", "M2-B14", "path", ["library", "tester_reference"], "rank, median and episode outputs", "bytes equal to the independent reference (sorted list, Fraction)"),
    # C cache
    row("C01", "cache", "M2-B14", "cache", ["cold", "warm"], "any M2 output, same request twice", "bytes equal; warm shows hits"),
    row("C02", "cache", "M2-B14", "mutation", ["param:window_s", "param:threshold", "param:N", "param:X", "param:K", "param:multiplier"], "one parameter changed per run", "key changes, recompute, bytes equal the cold result of the changed input"),
    row("C03", "cache", "M2-B14", "mutation", ["contract:right", "contract:strike", "contract:expiry", "session", "lane"], "one input field changed per run", "key changes, recompute, bytes equal cold result of changed input"),
    row("C04", "cache", "M2-B14", "mutation", ["history:content_sha256", "calendar"], "one history record or calendar entry changed", "key changes; only series touched are invalidated"),
    row("C05", "cache", "M2-B14", "scope", ["underlying", "session", "lane"], "same fields in different scope", "no hit crosses underlyings, sessions or lanes"),
    row("C06", "cache", "M2-B14", "event", ["seal_session_26"], "new sealed session", "exactly the series it touches are invalidated, others stay warm"),
    row("C07", "cache", "M2-B14", "cache", ["limited:1048576", "limited:16777216", "off"], "M2-B9 workload", "bytes equal to unbounded; evictions recorded; eviction never changes bytes"),
    row("C08", "cache", "M2-B14", "scope", ["worker"], "per-process caches", "no shared mutable state between workers; cache stats only in the run log, never in results"),
    row("C09", "cache", "M2-B2/B2c", "cache", ["cold", "warm"], "history view read", "cold <= 2 ms, warm <= 50 us p95 (B2c, B2); bytes equal"),
    row("C10", "cache", "M2-B14", "mutation", ["print:price", "print:size", "print:multiplier", "print:condition_excluded", "print:time_ns"], "one print field changed", "key changes, recompute, bytes equal cold"),
    row("C11", "cache", "M2-B14", "history", [19, 20, 21], "history view for one series", "19 sessions: insufficient_history, never a stale 20-session cached value; K+1 appended: oldest evicted"),
    row("C12", "cache", "M2-B14", "param", ["quiet_gap:1", "quiet_gap:5"], "F12 on the same points", "distinct keys, distinct results"),
    # R memory
    row("R01", "memory", "M2-B13", "limit", ["b9_peak_bytes"], "B7-with-M2 and M2-B11 workloads, per process", "peak RSS <= 2 GB budget, 4 GB hard"),
    row("R02", "memory", "M2-B13", "repeats", [30], "every timed gate", "post-GC RSS slope <= 1 MB/repeat; last-10 mean within 5 percent of first-10 mean"),
    row("R03", "memory", "M2-B13", "series", [500, 2000, 6000], "history store resident", "store bytes within 30 percent of series x K x 390 x 8 formula; <= 64 KB per contract series at the median count; <= 512 MB budget, 1 GB hard per worker"),
    row("R04", "memory", "M2-B13", "retention", [20, 25, 26], "append past K", "retention never exceeds K sessions; oldest evicted"),
    row("R05", "memory", "M2-B13", "workers", W, "aggregate worker RSS", "reported; aggregate <= cap rule min(cores, floor(aggregate/2 GB)); MemoryLimitError fails the run"),
    row("R06", "memory", "M2-B13", "size", ["L"], "size L chain, 1 worker", "within the 4 GB hard limit"),
    row("R07", "memory", "M2-B16", "view", ["shared_memory", "mmap", "store_load", "rebuild_one_session"], "view transfer to a worker", "<= 5 s per worker start, <= 512 MB per worker (hard 15 s, 1 GB); a full 25-session rebuild does not qualify"),
    row("R08", "memory", "M2-B16", "accounting", ["view_in_worker_rss"], "worker RSS with the view", "the view counts in that worker RSS; cost never hidden in compute"),
    # S scaling
    row("S01", "scaling", "M2-B9/B11/B12", "workers", W, "5-underlying compute phase", ">= 2.0x at 4 workers p50 wall; efficiency at N reported"),
    row("S02", "scaling", "M2-B5..B8,B10", "workers", W, "trade-stream gates sharded by contract id, merged in canonical order", ">= 1.8x at 4 workers; N/A (reported) under 4 physical cores"),
    row("S03", "scaling", "M2-B1", "workers", W, "history build, parallel across 5 underlyings", "at most 5-way; serial share of wall reported"),
    # K runner
    row("K01", "runner", "M2-B14", "fault", ["kill_worker:1:100"], "any M2 unit set, 4 workers", "exit 2, WorkerCrashedError, no output file, no digest, no temp file"),
    row("K02", "runner", "M2-B14", "fault", ["drop_unit:SYN1/21/003"], "any M2 unit set", "exit 2, MissingUnitError, no partial output"),
    row("K03", "runner", "M2-B14", "fault", ["duplicate_unit:SYN1/21/003"], "any M2 unit set", "exit 2, duplicate or unexpected unit error"),
    row("K04", "runner", "M2-B14", "fault", ["hang_worker:1"], "any M2 unit set with --timeout-s", "exit 2, WorkerTimeoutError"),
    row("K05", "runner", "M2-B14", "interpreter", ["mismatch"], "worker interpreter differs", "InterpreterMismatchError at start"),
    row("K06", "runner", "M2-B14", "hygiene", ["previous_outputs", "own_pids_only"], "rerun in the same --out", "digests.json, results.jsonl and .*.tmp of a previous run removed at start; only own process ids terminated"),
    # transfer, store, sweep
    row("T01", "store", "M2-B17", "round_trip", ["write", "read"], "250,000 records (25 sessions x 2,000 series x 5 metrics)", ">= 25,000 write and >= 50,000 read records/s (hard 5,000 and 10,000); content hash identical after the round trip and at every worker count"),
    row("T02", "store", "M2-B17", "fault", ["truncated_file", "corrupt_line"], "store file damaged", "closed structural error, no silent partial result"),
    row("T03", "sweep", "M2-B15", "cutoffs", [1, 78], "print-pass component, size M", "sweep time / (78 x single) <= 0.25 (hard 0.5); each print processed once per sweep"),
    row("T04", "sweep", "M2-B15r", "reads", [624000], "78 cutoffs x 8,000 series reads, gated apart from the print pass", "<= 32 s (hard 125 s)"),
]

DATA = {
    "label": "synthetic workload, relative engineering budget",
    "provenance": "SYNTHETIC",
    "qualification_label": QUAL,
    "contract_version": 3,
    "rows": ROWS,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="m2_perf_resource_rows.json")
    a = ap.parse_args()
    with open(a.out, "w", newline="\n") as f:
        json.dump(DATA, f, indent=1, sort_keys=True)
        f.write("\n")
    print(a.out, len(ROWS))


if __name__ == "__main__":
    main()
