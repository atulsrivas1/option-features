"""Export a variants1 stored-output DuckDB to demo-export.json for tools/demo/demo.html.

SYNTHETIC-ONLY PRERELEASE DEMO. It shows stored integration evidence, not a numerical oracle, a
release certificate or real market data. No run is ever badged REAL by this tool.

Usage (CPython 3.12, standard library plus duckdb only; the database is opened read-only):

    python -I -B tools/demo/export_demo.py OUTPUT.duckdb [--evidence evidence.json] [--out demo-export.json]

Then open tools/demo/demo.html in a browser (file://, no server, no network) and choose
demo-export.json with the file picker. The page also embeds the committed sample from
tools/demo/sample/demo-export.json (synthetic, produced from the workers replay fixtures).

Input: the six variants1 tables written by option_feature_workers.variants1.storage
(variant_schema, variant_generations, variant_objects, variant_operations, variant_bindings,
variant_checkpoints). Every stored envelope is re-verified here with the same canonical-JSON and
domain-separated sha256 rules as option_feature_contracts.variants1.canonical (reimplemented,
standard library only); a failed check marks the run integrity=false and badge UNVERIFIED instead
of stopping the export.

Provenance badge (computed here, never typed by hand; weakest claim by default):
  SYNTHETIC   at least one binding and every binding mode is "synthetic"
  MIXED       bindings of both synthetic and other modes (warning)
  UNVERIFIED  everything else: non-synthetic bindings, no bindings, unknown mode, or an integrity
              failure. There is no REAL badge in this prerelease: REAL would need verified
              installed-cohort evidence, which this exporter does not read.

Counts per stored result and per operation receipt:
  dependency_count  number of Evidence.dependencies entries
  evidence_count    len(member_ids) + len(excluded_ids) + len(control_ids)

Replay equality: four layers (direct evaluate, worker receipt, persisted readback, replay).
Only "persisted" is derived from the database (canonical bytes of the stored Results record and
its record digest). The others come from the optional evidence file, written by whoever ran the
library; without it they are "not_run". Evidence file shape:

    {"schema": "option-flow-demo-evidence1",
     "runs": {"<run_key>": {"direct": LAYER, "worker": LAYER, "replay": LAYER}}}
    LAYER = {"results_sha256": hex, "canonical_sha256": hex, "canonical_bytes": int}

results_sha256 is record_digest("variant_Results", results); canonical_sha256 and canonical_bytes
describe the canonical JSON bytes of the Results record. Verdict: equal (two or more layers
present and all identical in all three fields), differs (any mismatch), not_run (fewer than two).
"""
import argparse
import hashlib
import json
import os
import struct
import sys

SCHEMA_JSON = "option-flow-variants-json1"
SCHEMA_GENERATION = "option-flow-variants-generation1"
EXPORT_SCHEMA = "option-flow-demo-export1"
EVIDENCE_SCHEMA = "option-flow-demo-evidence1"
LAYERS = ("direct", "worker", "persisted", "replay")
MAX_VALUE_CHARS = 400


def canonical_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(domain, record_type, payload):
    head = domain + "\n" + ((record_type + "\n") if record_type else "")
    return hashlib.sha256(head.encode("utf-8") + canonical_json(payload)).hexdigest()


def content_digest(record_type, payload):
    return _digest("option-flow-variants-json1", record_type, payload)


def record_digest(record_type, payload):
    return _digest("option-flow-variants-record1", record_type, payload)


def cohort_digest(cohort):
    return _digest("option-flow-variants-cohort1", None, cohort)


def envelope(record_type, record):
    return canonical_json({"content_sha256": content_digest(record_type, record), "payload": record,
                           "record_type": record_type, "schema_version": SCHEMA_JSON}).decode("utf-8")


class Bad(Exception):
    pass


def unwrap(text, record_type):
    try:
        doc = json.loads(text)
    except (TypeError, ValueError):
        raise Bad("undecodable %s" % record_type) from None
    if (not isinstance(doc, dict) or doc.get("record_type") != record_type
            or doc.get("schema_version") != SCHEMA_JSON or "payload" not in doc):
        raise Bad("%s envelope" % record_type)
    if envelope(record_type, doc["payload"]) != text:
        raise Bad("%s canonical bytes or content digest" % record_type)
    return doc["payload"]


def _b64_text(bits):
    try:
        return "0x%s (%r)" % (bits, struct.unpack(">d", bytes.fromhex(bits))[0])
    except (ValueError, struct.error):
        return "0x%s" % bits


def _display(value):
    """Readable copy of a value: binary64 wire objects become hex plus decoded float."""
    if isinstance(value, dict):
        if set(value) == {"bits", "kind"} and value.get("kind") == "b64" and isinstance(value["bits"], str):
            return _b64_text(value["bits"])
        return {k: _display(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_display(v) for v in value]
    return value


def _find_status(value, depth=0):
    if isinstance(value, dict):
        if isinstance(value.get("status"), str):
            return value["status"], value.get("reason")
        if depth < 4:
            for v in value.values():
                found = _find_status(v, depth + 1)
                if found:
                    return found
    return None


def _counts(ev):
    ev = ev if isinstance(ev, dict) else {}
    deps = ev.get("dependencies") or []
    ev_n = sum(len(ev.get(k) or []) for k in ("member_ids", "excluded_ids", "control_ids"))
    return ev_n, len(deps)


def badge_for(bindings, integrity_ok):
    """Weakest claim by default; never REAL."""
    modes = [b.get("mode") for b in bindings]
    if not integrity_ok:
        return "UNVERIFIED", ["integrity check failed; no claim is made"]
    if not modes:
        return "UNVERIFIED", ["no bindings stored; provenance unknown"]
    synth = [m == "synthetic" for m in modes]
    if all(synth):
        return "SYNTHETIC", ["all %d binding(s) have mode synthetic" % len(modes)]
    if any(synth):
        return "MIXED", ["bindings of both synthetic and other modes; no verification evidence is read"]
    return "UNVERIFIED", ["non-synthetic binding mode(s) %s without verification evidence"
                          % ", ".join(sorted({str(m) for m in modes}))]


def _verify(gen, rows_by_table):
    """Re-verify one generation; returns (publication or None, error list)."""
    errs = []
    (run_key, work, request_h, snapshot_h, cohort_h, input_cp, results_h, output_cp, pub_h,
     object_count, operation_count, canonical, state) = gen
    if state != "committed":
        errs.append("generation state is %r" % state)
    try:
        pub = unwrap(canonical, "variant_Publication")
    except Bad as exc:
        return None, errs + [str(exc)]
    if pub.get("schema_version") != SCHEMA_GENERATION or pub.get("run_key") != run_key:
        errs.append("publication identity")
    try:
        cp = pub["output_checkpoint"]
        results = pub["results"]
        expected = (run_key, pub["work_sha256"], pub["request_sha256"], pub["snapshot_sha256"], pub["cohort_sha256"],
                    pub["input_checkpoint_sha256"], record_digest("variant_Results", results),
                    None if cp is None else record_digest("variant_Checkpoint", cp),
                    record_digest("variant_Publication", pub), len(results["rows"]), len(results["operations"]),
                    canonical, "committed")
    except (KeyError, TypeError):
        return pub, errs + ["publication shape"]
    if tuple(gen) != expected:
        errs.append("generation row does not match recomputed digests")
    if cohort_digest(pub.get("cohort")) != cohort_h:
        errs.append("cohort digest")
    for table, rtype, records in (("variant_objects", "variant_Result", results["rows"]),
                                  ("variant_operations", "variant_OperationReceipt", results["operations"]),
                                  ("variant_bindings", "variant_Binding", pub["bindings"])):
        rows = rows_by_table[table]
        if len(rows) != len(records):
            errs.append("%s row count %d != %d" % (table, len(rows), len(records)))
            continue
        for i, (row, rec) in enumerate(zip(rows, records)):
            if tuple(row) != (run_key, i, record_digest(rtype, rec), envelope(rtype, rec)):
                errs.append("%s row %d" % (table, i))
    return pub, errs


def _layer(results):
    raw = canonical_json(results)
    return {"state": "present", "results_sha256": record_digest("variant_Results", results),
            "canonical_sha256": hashlib.sha256(raw).hexdigest(), "canonical_bytes": len(raw)}


def _evidence_layer(entry):
    try:
        out = {"state": "present", "results_sha256": entry["results_sha256"],
               "canonical_sha256": entry["canonical_sha256"], "canonical_bytes": int(entry["canonical_bytes"])}
        if not all(isinstance(out[k], str) and len(out[k]) == 64 for k in ("results_sha256", "canonical_sha256")):
            raise ValueError
        return out
    except (KeyError, TypeError, ValueError):
        return {"state": "not_run"}


def _equality(persisted, evidence):
    layers = {"persisted": persisted}
    for name in ("direct", "worker", "replay"):
        layers[name] = _evidence_layer(evidence[name]) if isinstance(evidence, dict) and name in evidence \
            else {"state": "not_run"}
    present = [v for v in layers.values() if v["state"] == "present"]
    keys = ("results_sha256", "canonical_sha256", "canonical_bytes")
    if len(present) < 2:
        verdict = "not_run"
    elif all(all(p[k] == present[0][k] for k in keys) for p in present):
        verdict = "equal"
    else:
        verdict = "differs"
    return {"layers": {n: layers[n] for n in LAYERS}, "verdict": verdict}


def export_run(gen, rows_by_table, evidence):
    pub, errs = _verify(gen, rows_by_table)
    run = {"run_key": gen[0], "state": gen[12], "integrity": {"ok": not errs, "errors": errs},
           "shas": dict(zip(("work", "request", "snapshot", "cohort", "input_checkpoint", "results",
                             "output_checkpoint", "publication"), gen[1:9]))}
    if pub is None or "results" not in pub:
        bindings = []
        run.update(counts={"objects": 0, "operations": 0, "bindings": 0}, bindings=[], cohort=None,
                   operations=[], results=[], equality=_equality({"state": "not_run"}, None))
    else:
        bindings = [b for b in pub.get("bindings", []) if isinstance(b, dict)]
        results = pub["results"]
        cohort = pub.get("cohort") or {}
        run["counts"] = {"objects": len(results["rows"]), "operations": len(results["operations"]),
                         "bindings": len(bindings)}
        run["bindings"] = [{k: b.get(k) for k in ("binding_id", "mode", "source_id", "source_revision", "rights",
                                                  "source_content_sha256")} for b in bindings]
        run["cohort"] = {"candidate_id": cohort.get("candidate_id"), "platform_id": cohort.get("platform_id"),
                         "artifacts": [{k: a.get(k) for k in ("distribution", "version", "role", "source_commit",
                                                              "wheel_sha256")} for a in cohort.get("artifacts", [])]}
        run["operations"] = []
        for i, op in enumerate(results["operations"]):
            ev_n, dep_n = _counts(op.get("evidence"))
            run["operations"].append({"ordinal": i, "op_id": op.get("op_id"), "status": op.get("status"),
                                      "reason": op.get("reason"), "object_count": op.get("object_count"),
                                      "evidence_count": ev_n, "dependency_count": dep_n})
        run["results"] = []
        for i, row in enumerate(results["rows"]):
            ev_n, dep_n = _counts(row.get("evidence"))
            payload = row.get("payload") or {}
            st = _find_status(payload.get("value"))
            text = json.dumps(_display(payload.get("value")), sort_keys=True, ensure_ascii=False)
            deps = (row.get("evidence") or {}).get("dependencies") or []
            run["results"].append({
                "ordinal": i, "op_id": row.get("op_id"), "object_id": row.get("object_id"),
                "kind": payload.get("kind"), "scope_id": row.get("scope_id"),
                "status": st[0] if st else None, "reason": st[1] if st else None,
                "value": text[:MAX_VALUE_CHARS] + ("..." if len(text) > MAX_VALUE_CHARS else ""),
                "evidence_count": ev_n, "dependency_count": dep_n,
                "dependency_binding_ids": sorted({d.get("record_id") for d in deps
                                                  if isinstance(d, dict) and d.get("record_type") == "variant_Binding"})})
        run["equality"] = _equality(_layer(results), (evidence or {}).get(gen[0]))
    run["provenance"] = dict(zip(("badge", "reasons"), badge_for(bindings, not errs)))
    return run


def read_db(path):
    import duckdb
    con = duckdb.connect(path, read_only=True)
    try:
        names = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        need = {"variant_schema", "variant_generations", "variant_objects", "variant_operations", "variant_bindings",
                "variant_checkpoints"}
        if not need <= names:
            raise SystemExit("not a variants1 output database; missing tables: %s" % ", ".join(sorted(need - names)))
        version = [r[0] for r in con.execute("SELECT version FROM variant_schema").fetchall()]
        gens = con.execute("SELECT * FROM variant_generations ORDER BY run_key").fetchall()
        out = []
        for gen in gens:
            rows = {t: con.execute("SELECT * FROM %s WHERE run_key = ? ORDER BY ordinal" % t, [gen[0]]).fetchall()
                    for t in ("variant_objects", "variant_operations", "variant_bindings")}
            out.append((gen, rows))
        return version, out
    finally:
        con.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export a variants1 output DuckDB for demo.html (synthetic prerelease demo).")
    ap.add_argument("database")
    ap.add_argument("--evidence", help="optional replay-equality evidence JSON")
    ap.add_argument("--out", default="demo-export.json")
    args = ap.parse_args(argv)
    evidence = None
    if args.evidence:
        with open(args.evidence, encoding="utf-8") as fh:
            doc = json.load(fh)
        if not isinstance(doc, dict) or doc.get("schema") != EVIDENCE_SCHEMA or not isinstance(doc.get("runs"), dict):
            raise SystemExit("evidence file schema must be %s" % EVIDENCE_SCHEMA)
        evidence = doc["runs"]
    version, gens = read_db(args.database)
    runs = [export_run(g, rows, evidence) for g, rows in gens]
    doc = {"schema": EXPORT_SCHEMA, "generated_by": "tools/demo/export_demo.py",
           "source_file": os.path.basename(args.database), "storage_schema": version,
           "note": "Synthetic prerelease demo of stored integration evidence; not real data, not a qualification.",
           "runs": runs}
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    for r in runs:
        print("%s  %s  integrity=%s  equality=%s" % (r["run_key"], r["provenance"]["badge"], r["integrity"]["ok"],
                                                    r["equality"]["verdict"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
