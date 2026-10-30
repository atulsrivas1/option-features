"""M3a shared test harness (story S01). Loads the four author fixture sets read-only, checks every MANIFEST.sha256
(LF-normalised), decodes the tagged non-JSON types (R-65, R-125) and exposes rows(set, file, where=...).

It never imports an author's m3a_ref*.py or oracle: expectations come only from the row files.
Also holds the first-owner table of docs/m3a/M3A_BUILD_PLAN.md section 3a (OWNERS, PERF_OWNERS, owner_of).

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12
"""
import hashlib
import json
import re
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "qualification" / "synthetic" / "m3a"
SETS = ("author1", "author2", "author3", "author4")
PERF_FILE = ("author4", "m3a_perf_resource_rows.json")


def set_dir(name):
    return BASE / name


def manifest(name):
    """{file name: sha256 hex} of a set's MANIFEST.sha256 (lines 'hex *name')."""
    out = {}
    for line in (set_dir(name) / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, fname = line.split(None, 1)
            out[fname.strip().lstrip("*")] = digest
    return out


def manifest_mismatches(name):
    """Files of the set whose LF-normalised sha256 differs from the manifest, or that are missing."""
    bad = []
    for fname, digest in manifest(name).items():
        p = set_dir(name) / fname
        if not p.is_file():
            bad.append((fname, "missing"))
            continue
        if hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() != digest:
            bad.append((fname, "sha256"))
    return bad


def decode(o):
    """Decode the tagged objects of the rows (R-65, R-125) recursively: Decimal, Fraction, bytes, non-finite float."""
    if isinstance(o, dict):
        keys = set(o)
        if keys == {"py_type", "text"}:
            t = o["py_type"]
            if t == "Decimal":
                return Decimal(o["text"])
            if t == "Fraction":
                return Fraction(o["text"])
            if t == "float":
                return float(o["text"])          # "nan", "inf", "-inf"
        if keys == {"py_type", "hex"} and o["py_type"] == "bytes":
            return bytes.fromhex(o["hex"])
        return {k: decode(v) for k, v in o.items()}
    if isinstance(o, list):
        return [decode(v) for v in o]
    return o


def _read_rows(path):
    """Two row-file layouts: one JSON document with a "rows" list (author1, author3), or a header line followed by
    one canonical JSON row per line (author2, author4)."""
    text = path.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except ValueError:
        doc = None
    if isinstance(doc, dict) and isinstance(doc.get("rows"), list):
        return doc["rows"]
    lines = [ln for ln in text.split("\n") if ln]
    return [json.loads(ln) for ln in lines[1:]]


_CACHE = {}


def raw_rows(set_name, file_name):
    key = (set_name, file_name)
    if key not in _CACHE:
        _CACHE[key] = _read_rows(set_dir(set_name) / file_name)
    return _CACHE[key]


def rows(set_name, file_name, where=None, decoded=True):
    """Rows of one file (decoded copies; raw rows are never mutated). `where` is a predicate on the raw row."""
    out = []
    for r in raw_rows(set_name, file_name):
        if where is None or where(r):
            out.append(decode(r) if decoded else r)
    return out


def row_files(set_name):
    """Fixture row files of a set (m3a_cases_*.json), sorted."""
    return sorted(p.name for p in set_dir(set_name).glob("m3a_cases_*.json"))


def perf_rows():
    return json.loads((set_dir(PERF_FILE[0]) / PERF_FILE[1]).read_text(encoding="utf-8"))["rows"]


# ---- first-owner table (build plan section 3a); each entry is (story, set, file, predicate on the row id) -------

def _all(_):
    return True


def _cov_s05(i):
    return i.startswith("COV-") and int(i[4:]) <= 34


def _cov_s09(i):
    return i.startswith("COV-") and int(i[4:]) >= 35


def _d25_frame_request(i):
    return re.fullmatch(r"D25-V[1-7]", i) is not None


OWNERS = (
    ("S01", "author2", "m3a_cases_units.json", _all),
    ("S02", "author2", "m3a_cases_history.json", _all),
    ("S05", "author1", "m3a_cases_surface.json", _all),
    ("S05", "author1", "m3a_cases_coverage.json", _cov_s05),
    ("S09", "author1", "m3a_cases_coverage.json", _cov_s09),
    ("S05", "author1", "m3a_cases_american.json", _all),
    ("S05", "author1", "m3a_cases_delta25.json", lambda i: not _d25_frame_request(i)),
    ("S09", "author1", "m3a_cases_delta25.json", _d25_frame_request),
    ("S05", "author1", "m3a_cases_tenors.json", _all),
    ("S06", "author3", "m3a_cases_v5.json", _all),
    ("S06", "author3", "m3a_cases_v6.json", _all),
    ("S06", "author3", "m3a_cases_v8.json", _all),
    ("S06", "author3", "m3a_cases_v11.json", _all),
    ("S06", "author3", "m3a_cases_v21.json", _all),
    ("S07", "author3", "m3a_cases_v4.json", _all),
    ("S07", "author3", "m3a_cases_v7.json", _all),
    ("S07", "author3", "m3a_cases_v10.json", _all),
    ("S08", "author2", "m3a_cases_V1.json", _all),
    ("S08", "author2", "m3a_cases_V3.json", _all),
    ("S08", "author2", "m3a_cases_V9.json", _all),
    ("S09", "author4", "m3a_cases_structural.json", _all),
    ("S09", "author4", "m3a_cases_structural_aux.json", _all),
    ("S09", "author4", "m3a_cases_lane.json", _all),
)

EXPECTED_FIXTURE_COUNTS = {"S01": 21, "S02": 73, "S03": 0, "S04": 0, "S05": 313, "S06": 218, "S07": 188, "S08": 201,
                           "S09": 218, "S10": 0, "S11": 0}
EXPECTED_AUTHOR_COUNTS = {"author1": 323, "author2": 295, "author3": 406, "author4": 208}

PERF_OWNERS = {
    "S02": ("W09", "W10", "R03", "R04", "D10"),
    "S03": ("W03", "W14"),
    "S04": ("W04",),
    "S05": ("W02",),
    "S06": ("W05",),
    "S08": ("W06", "W07"),
    "S10": ("W08",),
    "S11": (("G001", "W01", "W11", "W12", "W13", "W15", "D01", "D02", "D03", "D04", "D05", "D06", "D07", "D08",
             "D09", "D11", "D12") + tuple("E%02d" % n for n in range(1, 13)) + tuple("C%02d" % n for n in range(1, 15))
            + ("R01", "R02", "R05", "R06", "R07", "R08", "S01", "S02", "S03")
            + tuple("K%02d" % n for n in range(1, 7))),
}
EXPECTED_PERF_COUNTS = {"S02": 5, "S03": 2, "S04": 1, "S05": 1, "S06": 1, "S08": 2, "S10": 1, "S11": 58}


def owners_of(set_name, file_name, row_id):
    """All stories whose rule claims the row (exactly one when the table is right)."""
    return [s for s, st, fn, pred in OWNERS if st == set_name and fn == file_name and pred(row_id)]


def owner_of(row_id):
    """First owner story of a fixture row id (searches all files); None when unowned."""
    for set_name in SETS:
        for fn in row_files(set_name):
            for r in raw_rows(set_name, fn):
                if r["id"] == row_id:
                    o = owners_of(set_name, fn, row_id)
                    return o[0] if o else None
    return None
