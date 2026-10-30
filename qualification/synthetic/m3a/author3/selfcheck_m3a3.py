"""Self-check: the honest chain-driven reference (m3a_ref3) against every stored expectation (SYNTHETIC)."""
import glob
import json
import os
import sys
from decimal import Decimal as D
import m3a_ref3 as ref

FAM = ["v4", "v5", "v6", "v7", "v8", "v10", "v11", "v21"]


def load(d):
    rows = []
    for f in FAM:
        p = os.path.join(d, "m3a_cases_%s.json" % f)
        with open(p, encoding="ascii") as fh:
            doc = json.load(fh)
        assert doc["header"]["provenance"] == "SYNTHETIC"
        rows += doc["rows"]
    return rows


def strict_row(row):
    return row["oracle"]["quote_dp"] == 8


def get(v, path):
    cur = v
    for k in path.split("."):
        if k == "session_id":
            return [x["session_id"] for x in cur] if cur is not None else None
        cur = cur[k] if not isinstance(cur, list) else cur
    return cur


def num(x):
    return float(D(x)) if not isinstance(x, (int, float)) else float(x)


def tol_for_key(key, tol):
    if key in ("now", "prior", "put25_iv", "call25_iv", "wings_mid", "atm_iv", "longer", "shorter"):
        return float(tol["iv"])
    if key in ("put_distance", "call_distance"):
        return float(tol["points"])
    if key == "change_ratio":
        return float(tol["change_ratio"])
    if key in ("spread_points", "skew_points", "curvature_points", "change_points", "gap_change_points"):
        return float(tol["points"])
    if key == "ratio":
        return float(tol.get("ratio", "0.1"))
    return 0.0


def compare(row, got, strict=False):
    """returns list of mismatch strings (empty = pass)."""
    e = row["expected"]
    bad = []
    for k in ("status", "reason", "code"):
        if got[k] != e[k]:
            bad.append("%s: got %r want %r" % (k, got[k], e[k]))
    if bad:
        return bad
    if e["labels_assert"] and got["labels"] != e["labels"]:
        bad.append("labels: got %r want %r" % (got["labels"], e["labels"]))
    if got["contract_reasons"] != e["coverage"]["contract_reasons"]:
        bad.append("contract_reasons: got %r want %r" % (got["contract_reasons"], e["coverage"]["contract_reasons"]))
    if e["status"] != "available":
        return bad
    if row["family"] in ("V4", "V5", "V6", "V7") and "delta_convention" in got["value"]:
        bad.append("delta_convention echoed on %s (R-174)" % row["family"])
    tol = e["tol"]
    for path in e["assert"]:
        key = path.split(".")[-1]
        if path == "priors.session_id":
            if [x["session_id"] for x in got["value"]["priors"]] != [x["session_id"] for x in e["value"]["priors"]]:
                bad.append("priors ids")
            continue
        if path == "pairs":
            for pn in ("9_30", "30_91"):
                for kk in ("longer", "shorter", "spread_points"):
                    g = num(got["value"]["pairs"][pn][kk])
                    w = num(e["value"]["pairs"][pn][kk])
                    if abs(g - w) > tol_for_key(kk, tol):
                        bad.append("pairs.%s.%s got %s want %s" % (pn, kk, g, w))
            continue
        gv, wv = got["value"][key], e["value"][key]
        if isinstance(wv, (bool, int)) and not isinstance(wv, str) and key in ("tenor", "nearest_days", "second_days", "sign_now", "sign_prior", "sign_changed"):
            if gv != wv:
                bad.append("%s got %r want %r" % (key, gv, wv))
        elif isinstance(wv, str) and key in ("prior_kind", "iv_form", "delta_convention"):
            if gv != wv:
                bad.append("%s got %r want %r" % (key, gv, wv))
        else:
            if abs(num(gv) - num(wv)) > tol_for_key(key, tol):
                bad.append("%s got %s want %s" % (key, num(gv), num(wv)))
    if e["fire_assert"] or strict:
        if got["fired"] != e["fired"]:
            bad.append("fired got %r want %r" % (got["fired"], e["fired"]))
        if strict and row["family"] == "V10":
            for k in ("sign_now", "sign_prior", "sign_changed"):
                if got["value"][k] != e["value"][k]:
                    bad.append("%s got %r want %r" % (k, got["value"][k], e["value"][k]))
    return bad


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "."
    rows = load(d)
    fails = 0
    for row in rows:
        got = ref.evaluate(row["family"], row["inputs"])
        bad = compare(row, got, strict=strict_row(row))
        if bad:
            fails += 1
            print("FAIL", row["id"], bad[:3])
    print("rows %d, failures %d" % (len(rows), fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
