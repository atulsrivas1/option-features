"""Developer tests for the opt-in process-pool runner (tools/m1_runner). Synthetic data only.

Developer evidence only: the independent Tester authors and re-runs its own determinism, kill and scaling tests.
CI-time tests (a tiny chain shape "T", 12 units); the heavy scaling and B6/B7 runs are tools/m1_runner_bench.py.

Rows: cap logic with injected core and RAM values; key-order merge; identical result hashes at 1 (in-process
reference), 2 and 4 workers, 3 repeats, across batch sizes, unit orderings and contract orderings; worker kill,
dropped unit, hang and memory limit fail the run with a named error and no output files; outputs carry no worker
count, ids or timings; doc phrase and forbidden-term grep.
"""
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tools")]
import m1_runner  # noqa: E402
from m1_runner import (MemoryLimitError, MissingUnitError, Runner, RunnerError, Spec, WorkerCrashedError,  # noqa: E402
                       WorkerTimeoutError, merge_units, resolve_workers, result_hash, worker_cap)

GIB = 1 << 30
SPEC = Spec(seed=20261029, shape="T", underlyings=("SYN1", "SYN2"), sessions=(1, 2), cutoffs=(0, 1, 2))
FORBIDDEN = ("real-data", "market data", "production", "validated against vendor", "Databento-qualified",
             "Linux parity", "byte-identical")


class CapLogic(unittest.TestCase):
    def test_cap_is_min_of_cores_ram_and_aggregate(self):
        c = worker_cap(cores=96, ram_bytes=256 * GIB, b9_peak_bytes=2 * GIB, aggregate_hard_bytes=8 * GIB)
        self.assertEqual((c["cap_by_cores"], c["cap_by_ram"], c["cap_by_aggregate"], c["cap"]), (96, 128, 4, 4))
        c = worker_cap(cores=8, ram_bytes=64 * GIB, b9_peak_bytes=GIB // 4, aggregate_hard_bytes=8 * GIB)
        self.assertEqual((c["cap_by_cores"], c["cap_by_ram"], c["cap_by_aggregate"], c["cap"]), (8, 256, 32, 8))
        c = worker_cap(cores=64, ram_bytes=6 * GIB, b9_peak_bytes=GIB, aggregate_hard_bytes=8 * GIB)
        self.assertEqual(c["cap"], 6)
        for key in ("cores", "ram_bytes", "b9_peak_bytes", "aggregate_hard_bytes"):
            self.assertIn(key, c)

    def test_cap_never_below_one(self):
        self.assertEqual(worker_cap(cores=4, ram_bytes=GIB, b9_peak_bytes=2 * GIB)["cap"], 1)
        self.assertEqual(worker_cap(cores=1, ram_bytes=64 * GIB, b9_peak_bytes=GIB)["cap"], 1)

    def test_clamp_is_reported_not_an_error(self):
        cap = worker_cap(cores=4, ram_bytes=64 * GIB, b9_peak_bytes=GIB // 2)
        used, clamp = resolve_workers(16, cap)
        self.assertEqual(used, 4)
        self.assertEqual(clamp, {"requested": 16, "used": 4, "cap": 4})
        used, clamp = resolve_workers(3, cap)
        self.assertEqual((used, clamp), (3, None))
        with self.assertRaises(ValueError):
            resolve_workers(0, cap)

    def test_bad_cap_inputs(self):
        with self.assertRaises(ValueError):
            worker_cap(cores=0, ram_bytes=GIB, b9_peak_bytes=GIB)
        with self.assertRaises(ValueError):
            worker_cap(cores=2, ram_bytes=GIB, b9_peak_bytes=0)


class KeyOrderMerge(unittest.TestCase):
    PAIRS = [("SYN1/01/%03d" % i, ("row%d" % i).encode()) for i in range(30)]

    def test_merge_orders_by_unit_key_never_completion_order(self):
        keys = [k for k, _ in self.PAIRS]
        expected = sorted(self.PAIRS)
        for seed in range(5):
            shuffled = list(self.PAIRS)
            random.Random(seed).shuffle(shuffled)
            self.assertEqual(merge_units(shuffled, keys), expected)
            self.assertEqual(result_hash(merge_units(shuffled, keys)), result_hash(expected))

    def test_merge_rejects_missing_duplicate_unexpected(self):
        keys = [k for k, _ in self.PAIRS]
        with self.assertRaises(MissingUnitError) as cm:
            merge_units(self.PAIRS[:-1], keys)
        self.assertIn(self.PAIRS[-1][0], str(cm.exception))
        with self.assertRaises(RunnerError):
            merge_units(self.PAIRS + [self.PAIRS[0]], keys)
        with self.assertRaises(RunnerError):
            merge_units(self.PAIRS + [("SYN9/01/000", b"x")], keys)

    def test_hash_depends_on_key_and_bytes(self):
        a = merge_units(self.PAIRS, [k for k, _ in self.PAIRS])
        changed = [(k, b + b"!") if i == 3 else (k, b) for i, (k, b) in enumerate(a)]
        self.assertNotEqual(result_hash(a), result_hash(changed))
        renamed = [("X" + k, b) for k, b in a]
        self.assertNotEqual(result_hash(a), result_hash(renamed))


class Determinism(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with Runner(workers=1) as r:
            cls.ref = r.run(SPEC)
        cls.pools = {}

    @classmethod
    def tearDownClass(cls):
        for p in cls.pools.values():
            p.close()

    def pool(self, n):
        if n not in self.pools:
            self.pools[n] = Runner(workers=n).__enter__()
        return self.pools[n]

    def test_reference_is_in_process_and_nonempty(self):
        self.assertEqual(self.ref.unit_count, 12)
        self.assertEqual(self.ref.log["workers_used"], 1)
        self.assertFalse(self.ref.log["pool"])
        self.assertEqual(len(self.ref.result_sha256), 64)
        self.assertEqual(sorted(self.ref.unit_sha256), list(self.ref.unit_sha256))

    def test_identical_hashes_at_1_2_4_workers_three_repeats(self):
        for n in (1, 2, 4):
            for _ in range(3):
                res = self.pool(n).run(SPEC, batch_size=2)
                self.assertEqual(res.result_sha256, self.ref.result_sha256, "workers=%d" % n)
                self.assertEqual(res.unit_sha256, self.ref.unit_sha256)

    def test_pool_used_for_two_or_more(self):
        res = self.pool(2).run(SPEC)
        self.assertTrue(res.log["pool"])
        self.assertEqual(res.log["workers_used"], 2)

    def test_batch_sizes_and_unit_orders(self):
        for batch, order in ((1, "natural"), (1, "shuffle:7"), (2, "reversed"), (3, "shuffle:99"), (7, "natural"), (1000, "reversed")):
            if True:
                res = self.pool(2).run(SPEC, batch_size=batch, order=order)
                self.assertEqual(res.result_sha256, self.ref.result_sha256, (batch, order))

    def test_uncached_single_unit_equals_chunked_pool_bytes(self):
        full = self.pool(2).run(SPEC, batch_size=3, emit="full")
        for key, data in full.units[::5]:
            self.assertEqual(m1_runner.workload.compute_unit(SPEC, key), data, key)

    def test_contract_order_does_not_change_bytes(self):
        for order in ("reversed", "shuffle:3"):
            spec = Spec(**{**SPEC._asdict(), "contract_order": order})
            with Runner(workers=1) as r:
                self.assertEqual(r.run(spec).result_sha256, self.ref.result_sha256, order)

    def test_workload_changes_change_the_hash(self):
        other = Spec(**{**SPEC._asdict(), "seed": 7})
        with Runner(workers=1) as r:
            self.assertNotEqual(r.run(other).result_sha256, self.ref.result_sha256)

    def test_full_bytes_equal_across_workers(self):
        full1 = self.pool(2).run(SPEC, emit="full")
        with Runner(workers=1) as r:
            full0 = r.run(SPEC, emit="full")
        self.assertEqual(full1.units, full0.units)
        self.assertEqual(len(full0.units), 12)
        for key, data in full0.units:
            row = json.loads(data)
            self.assertEqual(row["unit"], key)
            self.assertTrue(row["iv"] and row["oc5"] and row["oc6"] and row["atm"])

    def test_same_interpreter_and_versions_in_every_worker(self):
        res = self.pool(2).run(SPEC)
        hello = res.log["worker_env"]
        self.assertEqual(len(hello), 2)
        first = hello[0]
        for h in hello:
            for key in ("executable", "version", "flint", "platform", "hashseed"):
                self.assertEqual(h[key], first[key])
        self.assertEqual(first["executable"], sys.executable)
        self.assertEqual(first["hashseed"], "0")

    def test_counters_are_log_only(self):
        with Runner(workers=1, count_arb=True) as r:
            res = r.run(SPEC)
        self.assertEqual(res.result_sha256, self.ref.result_sha256)
        c = res.log["arb_calls_per_solve"]
        self.assertGreater(c["solves"], 0)
        self.assertGreater(c["total"], c["solves"])


class Failures(unittest.TestCase):
    def assert_no_outputs(self, out):
        self.assertEqual(sorted(os.listdir(out)), [], "output directory must stay empty")

    def test_killed_worker_fails_run_with_named_error_and_no_output(self):
        with tempfile.TemporaryDirectory() as out:
            with Runner(workers=2, fault={"kind": "kill_worker", "worker": 1, "after_units": 2}) as r:
                with self.assertRaises(WorkerCrashedError) as cm:
                    r.run(SPEC, batch_size=3, out_dir=out)
            self.assertIn("worker 1", str(cm.exception))
            self.assert_no_outputs(out)

    def test_dropped_unit_fails_run_naming_the_unit(self):
        key = "SYN2/01/001"
        with tempfile.TemporaryDirectory() as out:
            with Runner(workers=2, fault={"kind": "drop_unit", "unit_key": key}) as r:
                with self.assertRaises(MissingUnitError) as cm:
                    r.run(SPEC, out_dir=out)
            self.assertIn(key, str(cm.exception))
            self.assert_no_outputs(out)
        with tempfile.TemporaryDirectory() as out:  # same in the in-process reference path
            with Runner(workers=1, fault={"kind": "drop_unit", "unit_key": key}) as r:
                with self.assertRaises(MissingUnitError):
                    r.run(SPEC, out_dir=out)
            self.assert_no_outputs(out)

    def test_hung_worker_times_out_with_named_error(self):
        with tempfile.TemporaryDirectory() as out:
            with Runner(workers=2, timeout_s=3, fault={"kind": "hang_worker", "worker": 0}) as r:
                with self.assertRaises(WorkerTimeoutError) as cm:
                    r.run(SPEC, out_dir=out)
            self.assertIn("worker 0", str(cm.exception))
            self.assert_no_outputs(out)

    def test_aggregate_rss_limit_fails_run(self):
        with tempfile.TemporaryDirectory() as out:
            with Runner(workers=2, b9_peak_bytes=1 << 10, aggregate_hard_bytes=1 << 20) as r:
                with self.assertRaises(MemoryLimitError):
                    r.run(SPEC, out_dir=out)
            self.assert_no_outputs(out)

    def test_bad_fault_and_bad_spec_are_errors(self):
        with self.assertRaises(ValueError):
            Runner(workers=2, fault={"kind": "nonsense"})
        with self.assertRaises(ValueError):
            Runner(workers=1, fault={"kind": "kill_worker", "worker": 0, "after_units": 1})
        with self.assertRaises(ValueError):
            Spec(**{**SPEC._asdict(), "shape": "Q"}).validate()


class OutputsAndCli(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ)
        return subprocess.run([sys.executable, "-B", str(ROOT / "tools" / "m1_runner" / "cli.py"), *args],
                              capture_output=True, text=True, env=env, timeout=120)

    COMMON = ("--shape", "T", "--underlyings", "SYN1,SYN2", "--sessions", "1,2", "--cutoffs", "0,1,2")

    def test_outputs_identical_across_worker_counts_and_hold_no_run_metadata(self):
        blobs = []
        for workers in ("1", "2", "4"):
            with tempfile.TemporaryDirectory() as out:
                p = self.run_cli(*self.COMMON, "--workers", workers, "--out", out, "--emit", "full",
                                 "--log", os.path.join(out + "-log.jsonl"))
                self.assertEqual(p.returncode, 0, p.stderr)
                names = sorted(os.listdir(out))
                self.assertEqual(names, ["digests.json", "results.jsonl"])
                blobs.append({n: Path(out, n).read_bytes() for n in names})
                logp = Path(out + "-log.jsonl")
                self.assertIn("workers_used", logp.read_text())
                logp.unlink()
        self.assertEqual(blobs[0], blobs[1])
        self.assertEqual(blobs[0], blobs[2])
        text = blobs[0]["digests.json"].decode()
        for word in ("worker", "pid", "timing", "wall", "elapsed"):
            self.assertNotIn(word, text)
        lines = blobs[0]["results.jsonl"].decode().splitlines()
        keys = [json.loads(x)["unit"] for x in lines]
        self.assertEqual(keys, sorted(keys))

    def test_cli_kill_exit_nonzero_named_error_no_files(self):
        with tempfile.TemporaryDirectory() as out:
            p = self.run_cli(*self.COMMON, "--workers", "2", "--out", out, "--fault", "kill_worker:1:2", "--batch-size", "3")
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("WorkerCrashedError", p.stderr)
            self.assertEqual(os.listdir(out), [])

    def test_cli_clamp_is_reported_in_log_not_an_error(self):
        with tempfile.TemporaryDirectory() as out:
            logp = os.path.join(out, "run.log")
            p = self.run_cli(*self.COMMON, "--workers", "64", "--cores", "2", "--log", logp)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn("clamp", Path(logp).read_text())


class Docs(unittest.TestCase):
    DOC = ROOT / "docs" / "M1_RUNNER.md"

    def test_doc_has_exact_phrase(self):
        self.assertIn("opt-in, default single-process", self.DOC.read_text(encoding="utf-8"))

    def test_doc_has_no_forbidden_terms(self):
        low = self.DOC.read_text(encoding="utf-8").lower()
        for term in FORBIDDEN:
            self.assertNotIn(term.lower(), low, term)

    def test_doc_covers_required_topics(self):
        text = self.DOC.read_text(encoding="utf-8")
        for needle in ("--workers", "min(cores", "no partial output", "PYTHONHASHSEED", "unit key", "synthetic workload, relative engineering budget"):
            self.assertIn(needle, text)

    def test_runner_never_enabled_by_default(self):
        self.assertEqual(m1_runner.DEFAULT_WORKERS, 1)


if __name__ == "__main__":
    unittest.main()
