"""Build the SYNTHETIC sample for tools/demo from the frozen replay fixtures (not run in CI).

    python -I -B make_sample.py FIXTURE_DIR NEW_EMPTY_OUT_DIR [REPOS_PARENT]

FIXTURE_DIR holds wire.jsonl, obligations.jsonl and representative.jsonl (read only). REPOS_PARENT
(default: the parent of this repository) holds the sibling checkouts option-feature-io and
option-feature-workers. Writes OUT/sample.duckdb (not committed, several MB) and OUT/evidence.json,
then run export_demo.py on them. Runs: the W3 base batch run and the 3-step W3 chronological replay.
Per run the evidence layers are: direct = evaluate_variants, worker = execute_variants receipt,
replay = an independent single-request replay_variants run of the same request.
All inputs are the synthetic reference fixtures (cohort and sources are placeholders).
"""
import copy
import hashlib
import json
import os
import pathlib
import sys

fix, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
here = pathlib.Path(__file__).resolve()
parent = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else here.parents[4]
assert not out.exists(), "never reuse an output dir"
out.mkdir(parents=True)
repo = here.parents[3]
for p in (repo / "packages" / "option-contracts" / "src", repo / "packages" / "features" / "src",
          parent / "option-feature-io" / "packages" / "io" / "src",
          parent / "option-feature-workers" / "packages" / "workers" / "src"):
    sys.path.insert(0, str(p))
sys.dont_write_bytecode = True
from option_feature_contracts.variants1.canonical import canonical_json, cohort_digest, record_digest  # noqa: E402
from option_features.variants1.evaluate import evaluate_variants  # noqa: E402
from option_feature_workers.variants1 import VariantDuckDBSink, execute_variants, replay_variants  # noqa: E402

rows = {}
for name in ("wire", "obligations", "representative"):
    for line in open(fix / (name + ".jsonl"), encoding="utf8"):
        rec = json.loads(line)
        rows[rec["case_id"]] = rec
base = rows["W3-worker-computed"]
rep = rows["W3-mode-chronological_cut_replay"]


def layer(results):
    raw = canonical_json(results)
    return {"results_sha256": record_digest("variant_Results", results),
            "canonical_sha256": hashlib.sha256(raw).hexdigest(), "canonical_bytes": len(raw)}


def direct(snapshot, request, cohort):
    return evaluate_variants(snapshot, request, cohort_sha256=cohort_digest(cohort))


sink = VariantDuckDBSink(str(out / "sample.duckdb"))
evidence = {}
batch_cfg = copy.deepcopy(base["config"])
batch_cfg["mode"] = "batch"
rk = "REFERENCE-W3-worker-base"
rec = execute_variants(base["snapshot"], base["request"], run_key=rk, config=batch_cfg,
                       verified_cohort=base["cohort"], sink=sink)
again = replay_variants(base["snapshot"], [base["request"]], [rk + "-recheck"],
                        config=dict(batch_cfg, mode="chronological_cut_replay"), verified_cohort=base["cohort"])
evidence[rk] = {"direct": layer(direct(base["snapshot"], base["request"], base["cohort"])),
                "worker": layer(rec["results"]), "replay": layer(again[0]["results"])}

cfg = copy.deepcopy(rep.get("config") or base["config"])
cfg["mode"] = "chronological_cut_replay"
reqs = rep["explicit_replay_requests"]
keys = ["REFERENCE-W3-mode-replay-%d" % n for n in range(len(reqs))]
cohort = rep.get("cohort") or base["cohort"]
recs = replay_variants(rep["snapshot"], reqs, keys, config=cfg, verified_cohort=cohort, sink=sink)
again = replay_variants(rep["snapshot"], reqs, [k + "-recheck" for k in keys], config=cfg, verified_cohort=cohort)
for k, rq, a, b in zip(keys, reqs, recs, again):
    evidence[k] = {"direct": layer(direct(rep["snapshot"], rq, cohort)), "worker": layer(a["results"]),
                   "replay": layer(b["results"])}
sink.close()
with open(out / "evidence.json", "w", encoding="utf-8", newline="\n") as fh:
    json.dump({"schema": "option-flow-demo-evidence1", "runs": evidence}, fh, indent=1, sort_keys=True)
print("wrote", out)
