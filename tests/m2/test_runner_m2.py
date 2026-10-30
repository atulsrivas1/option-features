"""Developer tests for the M2 binding of the opt-in process-pool runner (tools/m1_runner, family m2 and all).

Developer evidence only: the independent Tester authors and re-runs its own determinism, kill, snapshot-corruption and
scaling tests. Synthetic data only. CI-time workload: 3,000 prints per unit, 40 series, 12 units (heavy gates live in
tools/m2_runner_bench.py). Covers: identical result hashes at 1 (in-process reference), 2, 4 and cap workers x 3, batch sizes,
unit orders, path single = batched, cache off = warm, family all (M1 + M2); the binary snapshot as the worker-start form
(NEW file name per generation, content_hash compared after attach, gc.freeze, memory per worker reported and enforced);
worker kill, hang, dropped and duplicated unit, damaged snapshot (truncated or corrupted) fail the run with a named error and
no output file; the perf_sut JSON binding; doc phrase.
"""
import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools")]
import m1_runner  # noqa: E402
from m1_runner import (DuplicateUnitError, MemoryLimitError, MissingUnitError, Runner, Spec, StoreAttachError,  # noqa: E402
                       WorkerCrashedError, WorkerTimeoutError, worker_cap)

SPEC = Spec(family="m2", underlyings=("SYN1", "SYN2"), sessions=(21, 22), cutoffs=(0, 20, 77), series_count=40, unit_prints=3000)
PERF_SUT = str(ROOT / "tools" / "m1_runner" / "perf_sut.py")


def variant(**kw):
    return Spec(**{**SPEC._asdict(), **kw})


class M2Determinism(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with Runner(workers=1) as r:
            cls.ref = r.run(SPEC, emit="full")
        cls.pools = {}

    @classmethod
    def tearDownClass(cls):
        for p in cls.pools.values():
            p.close()

    def pool(self, n):
        if n not in self.pools:
            self.pools[n] = Runner(workers=n).__enter__()
        return self.pools[n]

    def test_reference_covers_every_output(self):
        self.assertEqual(self.ref.unit_count, 12)
        row = json.loads(dict(self.ref.units)["SYN1/21/077"])
        for key in ("f1", "f4", "f17", "f7", "f18", "f12", "pack", "eod"):
            self.assertIn(key, row, key)
        self.assertEqual(len(row["pack"]), 40)
        self.assertEqual(len(row["pack"][0]), 5)
        self.assertNotIn("eod", json.loads(dict(self.ref.units)["SYN1/21/000"]))
        self.assertEqual(self.ref.log["workers_used"], 1)

    def test_identical_hashes_1_2_4_workers_three_repeats(self):
        for n in (2, 4):
            for _ in range(3):
                res = self.pool(n).run(SPEC, batch_size=2)
                self.assertEqual(res.result_sha256, self.ref.result_sha256, "workers=%d" % n)
                self.assertEqual(res.unit_sha256, self.ref.unit_sha256)

    def test_cap_workers_identical(self):
        cap = min(worker_cap()["cap"], 6)
        for _ in range(3):
            self.assertEqual(self.pool(cap).run(SPEC).result_sha256, self.ref.result_sha256)

    def test_batch_sizes_and_orders(self):
        for batch, order in ((1, "natural"), (1, "shuffle:7"), (2, "reversed"), (3, "shuffle:99"), (1000, "reversed")):
            res = self.pool(2).run(SPEC, batch_size=batch, order=order)
            self.assertEqual(res.result_sha256, self.ref.result_sha256, (batch, order))

    def test_single_equals_batched_and_cache_off_equals_warm(self):
        with Runner(workers=1) as r:
            self.assertEqual(r.run(variant(path="single")).result_sha256, self.ref.result_sha256)
            self.assertEqual(r.run(variant(cache="off")).result_sha256, self.ref.result_sha256)
            self.assertEqual(r.run(variant(cache="cold")).result_sha256, self.ref.result_sha256)

    def test_full_bytes_equal_across_workers(self):
        full = self.pool(2).run(SPEC, emit="full")
        self.assertEqual(full.units, self.ref.units)

    def test_each_family_runs_and_agrees_across_workers(self):
        for fam in ("prints", "window", "volume", "concentration", "grid", "baseline", "history", "episodes", "store"):
            with Runner(workers=1) as r:
                a = r.run(variant(family=fam, cutoffs=(0, 77)))
            b = self.pool(2).run(variant(family=fam, cutoffs=(0, 77)))
            self.assertEqual(a.result_sha256, b.result_sha256, fam)
        with Runner(workers=1) as r:
            self.assertNotEqual(r.run(variant(seed=7)).result_sha256, self.ref.result_sha256)

    def test_family_all_adds_the_m1_unit_and_is_deterministic(self):
        spec = variant(family="all", shape="T", underlyings=("SYN1",), sessions=(21,), cutoffs=(1, 77))
        with Runner(workers=1) as r:
            a = r.run(spec, emit="full")
        with Runner(workers=2) as r:
            b = r.run(spec, emit="full")
        self.assertEqual(a.result_sha256, b.result_sha256)
        row = json.loads(a.units[0][1])
        self.assertIn("m1", row)
        self.assertIn("pack", row)

    def test_store_transfer_log_facts(self):
        res = self.pool(2).run(SPEC)
        st = res.log["store"]
        self.assertEqual(st["content_sha256"], self.ref.log["store"]["content_sha256"])
        self.assertEqual(len(st["attach"]), 2)
        for a in st["attach"]:
            self.assertGreater(a["frozen_objects"], 0)          # gc.freeze() ran after the attach
            self.assertIn("private_bytes", a)
            self.assertGreater(a["shared_mapped_bytes"], 0)
        self.assertEqual(st["over_budget_workers"], [])

    def test_new_snapshot_file_name_per_generation(self):
        with Runner(workers=2) as r:
            d = r._store_dir()
            r.run(SPEC)
            first = sorted(glob.glob(os.path.join(d, "*.m2bin")))
            r.run(variant(series_count=41))   # different content: a new generation, a new file
            second = sorted(glob.glob(os.path.join(d, "*.m2bin")))
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 2)
        self.assertEqual(len({os.path.basename(n) for n in second}), 2)

    def test_store_memory_hard_limit_enforced(self):
        with tempfile.TemporaryDirectory() as out:
            with Runner(workers=2, store_bytes_hard=1000) as r:
                with self.assertRaises(MemoryLimitError) as cm:
                    r.run(SPEC, out_dir=out)
            self.assertIn("store memory", str(cm.exception))
            self.assertEqual(os.listdir(out), [])

    def test_reports_private_and_shared_bytes_separately(self):
        a = self.pool(2).run(SPEC).log["store"]["attach"][0]
        self.assertIn("private_bytes", a)
        self.assertIn("shared_mapped_bytes", a)


class M2Failures(unittest.TestCase):
    def assert_fails(self, exc, fault, workers=2, timeout=300, **kw):
        with tempfile.TemporaryDirectory() as out:
            Path(out, "digests.json").write_text("old")
            with Runner(workers=workers, fault=fault, timeout_s=timeout) as r:
                with self.assertRaises(exc) as cm:
                    r.run(variant(**kw), batch_size=3, out_dir=out)
            self.assertEqual(os.listdir(out), [], "a failed run leaves no output file and removes old ones")
        return str(cm.exception)

    def test_kill(self):
        self.assertIn("worker 1", self.assert_fails(WorkerCrashedError, {"kind": "kill_worker", "worker": 1, "after_units": 2}))

    def test_hang(self):
        self.assertIn("worker 0", self.assert_fails(WorkerTimeoutError, {"kind": "hang_worker", "worker": 0}, timeout=3))

    def test_drop_and_duplicate_unit(self):
        self.assertIn("SYN1/21/020", self.assert_fails(MissingUnitError, {"kind": "drop_unit", "unit_key": "SYN1/21/020"}))
        self.assertIn("SYN2/22/077", self.assert_fails(DuplicateUnitError, {"kind": "duplicate_unit", "unit_key": "SYN2/22/077"}))

    def test_truncated_snapshot_fails_with_named_error(self):
        msg = self.assert_fails(StoreAttachError, {"kind": "truncate_store", "bytes": 1024})
        self.assertIn("snapshot_length_mismatch", msg)

    def test_corrupted_snapshot_fails_with_named_error(self):
        msg = self.assert_fails(StoreAttachError, {"kind": "corrupt_store", "offset": 200})
        self.assertIn("snapshot_hash_mismatch", msg)

    def test_store_faults_need_the_pool(self):
        with self.assertRaises(ValueError):
            Runner(workers=1, fault={"kind": "corrupt_store", "offset": 0})

    def test_bad_m2_specs(self):
        for bad in ({"family": "nope"}, {"sessions": (3,)}, {"series_count": 0}, {"history_sessions": 7}, {"path": "x"},
                    {"mutation": json.dumps({"kind": "bound", "bound_divisor": 10})},
                    {"mutation": json.dumps({"kind": "param", "name": "nonsense", "value": "1"})}):
            with self.assertRaises(ValueError, msg=str(bad)):
                variant(**bad).validate()


class M2Mutations(unittest.TestCase):
    def test_mutations_change_bytes(self):
        with Runner(workers=1) as r:
            ref = r.run(variant(family="m2", cutoffs=(77,))).result_sha256
            for mut in ({"kind": "print", "field": "size", "index": 5, "value": 99999},
                        {"kind": "print", "field": "price", "index": 7, "value": 1},
                        {"kind": "contract", "field": "strike", "contract_id": 0, "value": "123"},
                        {"kind": "param", "name": "window_s", "value": "900"},
                        {"kind": "param", "name": "x_percent", "value": "50"},
                        {"kind": "history", "series_id": "S0003", "metric": "contracts", "session_id": 3, "field": "total", "value": "7"},
                        {"kind": "calendar", "session_id": 3, "field": "minutes", "value": "200"}):
                got = r.run(variant(family="m2", cutoffs=(77,), mutation=json.dumps(mut))).result_sha256
                self.assertNotEqual(got, ref, mut)


class PerfSut(unittest.TestCase):
    def call(self, req, expect_rc=None):
        with tempfile.TemporaryDirectory() as d:
            rq, rp = os.path.join(d, "req.json"), os.path.join(d, "resp.json")
            Path(rq).write_text(json.dumps(req, sort_keys=True, separators=(",", ":")), encoding="utf-8")
            p = subprocess.run([sys.executable, "-B", PERF_SUT, "--request", rq, "--response", rp], capture_output=True, text=True,
                               timeout=600, cwd=d)
            resp = json.loads(Path(rp).read_text(encoding="utf-8")) if os.path.exists(rp) else None
        if expect_rc is not None:
            self.assertEqual(p.returncode, expect_rc, p.stderr[-600:])
        return p, resp

    def req(self, **kw):
        base = {"contract_version": 3, "request_id": "t1", "gate": "D01",
                "workload": {"manifest": "m2_workload_manifest.json", "seed": 20261029, "family": "m2", "underlyings": ["SYN1"],
                             "sessions": [21], "cutoff_indexes": [0, 77], "unit_prints": 3000, "stream_size": None,
                             "history_sessions": 20, "series_count": 40, "chain": "M", "order": "natural"},
                "workers": 1, "batch_size": 64, "cache": "cold", "path": "batched", "mutation": None, "fault": None, "params": {},
                "limits": {"ram_bytes": 0, "b9_peak_bytes": 2147483648, "aggregate_rss_hard_bytes": 0, "store_bytes_hard": 1073741824},
                "repeats": 1, "warmup": 0, "emit_results": "digest"}
        base.update(kw)
        return base

    def wl(self, **kw):
        return dict(self.req()["workload"], **kw)

    def test_determinism_row_returns_hashes_identical_across_workers(self):
        _, a = self.call(self.req(), 0)
        _, b = self.call(self.req(workers=2), 0)
        self.assertEqual(a["result_sha256"], b["result_sha256"])
        self.assertEqual(a["per_unit_sha256"], b["per_unit_sha256"])
        self.assertEqual(a["store_content_sha256"], b["store_content_sha256"])
        self.assertEqual(a["contract_version"], 3)
        self.assertEqual(a["provenance"], "SYNTHETIC")
        self.assertEqual(a["errors"], [])
        self.assertFalse(a["partial_output"])
        self.assertEqual(len(a["timings_ns"]), 1)
        self.assertEqual(b["workers_used"], 2)
        self.assertEqual(set(a["per_unit_sha256"]), {"SYN1/21/000", "SYN1/21/077"})

    def test_kill_fault_fails_with_named_error_and_null_results(self):
        p, r = self.call(self.req(gate="K01", workers=2, batch_size=1, fault={"kind": "kill_worker", "worker": 1, "after_units": 1}), 2)
        self.assertIsNotNone(r)
        self.assertTrue(r["errors"] and "worker 1" in r["errors"][0])
        self.assertIsNone(r["results"])
        self.assertIsNone(r["result_sha256"])
        self.assertFalse(r["partial_output"])

    def test_damaged_store_fault(self):
        _, r = self.call(self.req(gate="K05", workers=2, fault={"kind": "corrupt_store", "offset": 200}), 2)
        self.assertIn("snapshot_hash_mismatch", r["errors"][0])
        self.assertIsNone(r["result_sha256"])

    def test_unknown_field_gate_and_mutation_kind_are_errors(self):
        bad = self.req()
        bad["surprise"] = 1
        self.call(bad, 2)
        self.call(self.req(gate="M2-B99"), 2)
        _, r = self.call(self.req(mutation={"kind": "bound", "bound_divisor": 10}), 2)
        self.assertTrue(r["errors"])
        _, r = self.call(self.req(contract_version=2), 2)
        self.assertTrue(r["errors"])

    def test_mutation_applied_flag(self):
        _, r = self.call(self.req(mutation={"kind": "print", "field": "size", "index": 3, "value": 5000}), 0)
        self.assertTrue(r["mutation_applied"])
        _, base = self.call(self.req(), 0)
        self.assertFalse(base["mutation_applied"])
        self.assertNotEqual(r["result_sha256"], base["result_sha256"])

    def test_store_round_trip_gate(self):
        _, r = self.call(self.req(gate="M2-B17", workload=self.wl(series_count=20, family="store"), repeats=2), 0)
        self.assertEqual(r["store"]["records"], 20 * 25 * 5)
        self.assertEqual(len(r["timings_ns"]), 2)
        self.assertEqual(len(r["store"]["round_trip_sha256"]), 64)
        self.assertGreater(r["store"]["write_ns"], 0)

    def test_transfer_gate_reports_mode_and_bytes(self):
        _, r = self.call(self.req(gate="M2-B16", workers=2, workload=self.wl(series_count=20, family="store"), repeats=2), 0)
        self.assertEqual(r["transfer"]["mode"], "mmap")
        self.assertGreater(r["transfer"]["bytes_per_worker"], 0)
        self.assertEqual(len(r["timings_ns"]), 2)

    def test_trade_to_grid_gate(self):
        _, r = self.call(self.req(gate="M2-B18", workload=self.wl(family="grid", sessions=[21]), repeats=2), 0)
        self.assertEqual(len(r["timings_ns"]), 2)
        self.assertGreater(r["throughput_units"], 0)

    def test_unbound_gate_is_a_named_error_not_a_silent_pass(self):
        _, r = self.call(self.req(gate="M2-B5"), 2)
        self.assertIn("not bound", r["errors"][0])


class Docs(unittest.TestCase):
    def test_runner_doc_phrase_and_m2_section(self):
        text = (ROOT / "docs" / "M1_RUNNER.md").read_text(encoding="utf-8")
        self.assertIn("opt-in, default single-process", text)
        for needle in ("M2BIN", "gc.freeze", "new file name", "perf_sut", "content_hash", "store memory"):
            self.assertIn(needle, text)
        low = text.lower()
        for term in ("real-data", "market data", "production", "byte-identical", "linux parity"):
            self.assertNotIn(term, low, term)

    def test_default_is_single_process(self):
        self.assertEqual(m1_runner.DEFAULT_WORKERS, 1)


if __name__ == "__main__":
    unittest.main()
