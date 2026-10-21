"""Consume independently approved supplemental R26 full-result fixtures.

Run with a qualified installed pure two-distribution or full five-distribution
runtime using python -I -B. The calling controller owns cohort inventory, RECORD,
import-origin and before/after artifact verification. This consumer neither
admits a cohort nor generates expected results. No source paths are inserted.
"""
import argparse
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback


FAMILIES=(
    ("definition","r26-independent-definition-partition-fixtures1",8,78),
    ("clock","r26-independent-selection-clock-fixtures1",12,48),
)
ROOTS=("option_flow_contracts","option_flow_features")
FORBIDDEN=("option_flow_io","option_flow_workers","duckdb","_duckdb")


def require(condition,detail):
    if not condition:raise RuntimeError(detail)


def digest(path):return sha256(path.read_bytes()).hexdigest()


def imported_sources(repository):
    """Record exact actual pure modules without claiming full cohort admission."""
    result={}
    for name,module in tuple(sys.modules.items()):
        require(not any(name==root or name.startswith(root+".") for root in FORBIDDEN),"Storage/worker/native imports are outside this pure consumer")
        if any(name==root or name.startswith(root+".") for root in ROOTS):
            origin=getattr(module,"__file__",None)
            require(type(origin) is str,"Imported pure module lacks a file origin")
            path=Path(origin).resolve(strict=True)
            require(not path.is_relative_to(repository),"Working repository source is not an installed producer")
            require(path.suffix==".py","Expected installed pure Python producer source")
            result[name]={"path":str(path),"sha256":digest(path)}
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for family,_,_,_ in FAMILIES:
        parser.add_argument("--"+family+"-fixture",type=Path,required=True)
        parser.add_argument("--"+family+"-fixture-sha256",required=True)
    parser.add_argument("--report",type=Path,required=True)
    args=parser.parse_args()
    require(sys.flags.isolated==1 and sys.dont_write_bytecode and not os.environ.get("PYTHONPATH"),"Use python -I -B with no PYTHONPATH")
    require(sys.version_info[:2]==(3,12),"The selected R26 runtime requires Python3.12")
    require(not args.report.exists(),"Report must be a new private file")
    script=Path(__file__).resolve();repository=script.parents[2]
    source_before=digest(script)
    pins={}
    for family,_,_,_ in FAMILIES:
        path=getattr(args,family+"_fixture").resolve(strict=True)
        anchor=getattr(args,family+"_fixture_sha256")
        require(re.fullmatch("[0-9a-f]{64}",anchor) is not None,"Externally approved lowercase SHA256 is required")
        require(digest(path)==anchor,"Externally pinned supplemental fixture changed")
        pins[family]={"path":str(path),"sha256":anchor}
    require(args.report.resolve() not in {script,*[Path(pin["path"]) for pin in pins.values()]},"Report collides with a selected input")
    report={"schema":"r26-installed-supplement-conformance1","passed":False,"consumer_sha256_before":source_before,
        "python":sys.version,"platform":sys.platform,"executable":sys.executable,"fixture_pins":pins,"families":[],
        "cohort_admitted_by_consumer":False,"release_accepted":False,
        "limitations":["Caller must verify installed cohort inventory, RECORD, origins and artifact identity before and after this consumer", "Only supplemental pure contracts/features conformance; no IO/workers/native/replay/restore or complete release qualification", "Fixture expectations are externally supplied literals; this consumer does not generate an oracle"]}
    started=time.perf_counter()
    try:
        from option_flow_contracts import (decode_flow_snapshot,decode_flow_request,
            encode_flow_snapshot,encode_flow_request,encode_flow_results,
            flow_canonical_bytes,flow_to_payload,flow_record_digest)
        from option_flow_features import evaluate_flow
        report["imported_sources_before"]=imported_sources(repository)
        require(all(root in report["imported_sources_before"] for root in ROOTS),"Actual pure producer roots missing")
        report["distribution_versions"]={name:importlib.metadata.version(name) for name in ("option-flow-contracts","option-flow-features")}
        for family,schema,expected_cases,expected_rows in FAMILIES:
            pin=pins[family];packet=json.loads(Path(pin["path"]).read_bytes())
            require(packet.get("schema")==schema,"Wrong closed supplemental schema")
            cases=packet["cases"]
            require(type(cases) is list and len(cases)==expected_cases,"Supplemental case census differs")
            require(all(type(case.get("id")) is str and case["id"] for case in cases),"Supplemental cases require literal string identities")
            require(len({case["id"] for case in cases})==expected_cases,"Duplicate supplemental case identity")
            family_report={"family":family,"cases":[],"expected_case_count":expected_cases,"expected_rows":expected_rows,"passed":False}
            report["families"].append(family_report)
            row_count=0
            for case in cases:
                snapshot_wire=case["snapshot_wire"].encode("utf-8");request_wire=case["request_wire"].encode("utf-8")
                snapshot=decode_flow_snapshot(snapshot_wire);request=decode_flow_request(request_wire)
                require(encode_flow_snapshot(snapshot)==snapshot_wire and encode_flow_request(request)==request_wire,"Supplemental input envelope is not canonical")
                require(flow_record_digest("flow_snapshot",snapshot)==case["snapshot_record_sha256"],"Supplemental snapshot identity differs")
                require(flow_record_digest("flow_request",request)==case["request_record_sha256"],"Supplemental request identity differs")
                rows=evaluate_flow(snapshot,request)
                expected=case["expected_results"]
                require(type(expected) is list,"Expected complete results must be a literal list")
                require(flow_to_payload(rows)==expected,"Complete value/status/evidence/identity result payload differs for "+case["id"])
                literal_bytes=json.dumps(expected,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")
                require(flow_canonical_bytes(rows)==literal_bytes,"Complete canonical result bytes differ for "+case["id"])
                require(flow_record_digest("flow_results",rows)==case["expected_results_record_sha256"],"Complete result digest differs for "+case["id"])
                require(encode_flow_results(rows).decode("utf-8")==case["expected_results_wire"],"Complete canonical result envelope differs for "+case["id"])
                entry={"id":case["id"],"rows":len(rows),"snapshot_record_sha256":case["snapshot_record_sha256"],"request_record_sha256":case["request_record_sha256"],"results_record_sha256":case["expected_results_record_sha256"],"passed":True}
                family_report["cases"].append(entry);row_count+=len(rows)
                print(json.dumps({"family":family,**entry}),flush=True)
            require(row_count==expected_rows,"Supplemental complete row census differs")
            family_report.update(passed=True,case_count=len(cases),full_rows=row_count)
        report["imported_sources_after"]=imported_sources(repository)
        for name,entry in report["imported_sources_before"].items():
            require(report["imported_sources_after"].get(name)==entry,"Actual imported producer source identity changed")
        report["consumer_sha256_after"]=digest(script)
        require(report["consumer_sha256_after"]==source_before,"Consumer source changed during qualification")
        for pin in pins.values():require(digest(Path(pin["path"]))==pin["sha256"],"Pinned supplemental fixture changed during qualification")
        report["distribution_versions_after"]={name:importlib.metadata.version(name) for name in ("option-flow-contracts","option-flow-features")}
        require(report["distribution_versions_after"]==report["distribution_versions"],"Actual pure distribution versions changed")
        report.update(passed=True,case_count=20,complete_rows=126)
    except BaseException as error:
        report["failure"]={"class":type(error).__name__,"detail":str(error),"traceback":traceback.format_exc()}
    finally:
        report["elapsed_seconds"]=time.perf_counter()-started
        with args.report.open("x",encoding="utf-8") as stream:json.dump(report,stream,indent=2)
    return 0 if report["passed"] else 1

if __name__=="__main__":raise SystemExit(main())
