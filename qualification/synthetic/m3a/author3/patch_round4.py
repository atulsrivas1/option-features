"""Round 4 (post-merge consistency pass): applied AFTER the generators, to the stored datasets.
- R-81 (superseded by R-151) -> R-151..R-154 on V4 rows; R-83 (superseded by R-103) -> R-103, R-104 on V6 rows
- V8-O1 derivation text: R-117/R-139 settle no_delta_bracket (was a guess)
- no_eligible_contract (R-106): rows <FAM>-NE1 (empty chain), NE2 (all contracts late_report), NE3 (all stale), per family
- header: row_count, closed_reasons_used (adds no_eligible_contract)
- round 5: citation tags R-178 (V4-M02, V8-F1, V8-F2, V10-H2, V10-M2, V11-F1, V21-F3) and R-179 (V4-A-17, V5-H-1)
Idempotent. Run order: gen_m3a_g5.py, gen_m3a_v4..v21.py (each with --out DIR), then python patch_round4.py DIR"""
import copy
import json
import sys
import os

CONFIRMED = {}
for _i in ("V4-M02", "V8-F1", "V8-F2", "V10-H2", "V10-M2", "V11-F1", "V21-F3"):
    CONFIRMED[_i] = ("R-178", "R-178 confirmed: an exact-tenor expiry failing coverage gives low_surface_coverage, not no_bracketing_expiry")
for _i in ("V4-A-17", "V5-H-1"):
    CONFIRMED[_i] = ("R-179", "R-179 confirmed: a covered selected expiry with no both-right strike gives no_atm_strike, no fallback")
FAM = ["v4", "v5", "v6", "v7", "v8", "v10", "v11", "v21"]
D = sys.argv[1] if len(sys.argv) > 1 else "."
for f in FAM:
    p = os.path.join(D, "m3a_cases_%s.json" % f)
    doc = json.load(open(p, encoding="ascii"))
    hdr, rows = doc["header"], doc["rows"]
    fam = hdr["family"]
    for r in rows:
        if "no_eligible_contract" in r["tags"] and "-NE" not in r["id"]:
            r["id"] = r["id"].replace("-E", "-NE")
        rl = []
        for x in r["rulings"]:
            if x == "R-81":
                rl += ["R-151", "R-152", "R-153", "R-154"]
            elif x == "R-83":
                rl += ["R-103", "R-104"]
            else:
                rl.append(x)
        r["rulings"] = list(dict.fromkeys(rl))
        r["derivation"] = r["derivation"].replace("R-81", "R-151").replace("R-83", "R-103")
        if r["id"] == "V8-O1":
            r["derivation"] = "bracketing 45d expiry has no put-side 25-delta bracket: no_delta_bracket (R-117, R-139)"
            r["ruling_status"] = "RULED (R-117, R-139)"
    if not any(r["id"] == fam + "-NE1" for r in rows):
        base = next(r for r in rows if r["expected"]["status"] == "available" and r["expected"]["code"] is None
                    and not any(t in r["tags"] for t in ("delayed", "american", "mixed")))
        cut = base["inputs"]["chain"]["cutoff_ns"]
        for i, (kind, why) in enumerate([("empty", "empty chain"), ("excl", "every contract has condition late_report"),
                                          ("stale", "every contract is older than stale_limit_ns")], 1):
            r = copy.deepcopy(base)
            r["id"] = "%s-NE%d" % (fam, i)
            cs = r["inputs"]["chain"]["contracts"]
            if kind == "empty":
                cs.clear()
                counts = {}
                r["oracle"]["smile"] = []
            else:
                cs[:] = cs[:6]
                for c in cs:
                    if kind == "excl":
                        c["condition"] = "late_report"
                    else:
                        c["event_ns"] = cut - 20_000_000_000
                        c["known_at_ns"] = None
                counts = {("excluded_condition" if kind == "excl" else "stale_quote"): len(cs)}
                r["oracle"]["smile"] = r["oracle"]["smile"][:1]
            r["derivation"] = "%s: no contract passes the M1 gates, frame unavailable no_eligible_contract, labels [] (R-106, R-105); never structural; request and priors valid so no earlier code applies" % why
            r["tags"] = ["no_eligible_contract", kind]
            r["rulings"] = ["R-106", "R-105", "R-71", "R-118"]
            r["ruling_status"] = "RULED (R-106)"
            r["gating"] = True
            r["expected"] = {"assert": [], "code": None, "coverage": {"contract_reasons": counts}, "fire_assert": True,
                             "fired": None, "labels": [], "labels_assert": True, "margin": None, "near_threshold": False,
                             "reason": "no_eligible_contract", "rule": None, "status": "unavailable", "tol": None, "value": None}
            rows.append(r)
    # round 5 citation tags (R-178, R-179: existing rows confirmed, no change to expectations)
    for r in rows:
        tag = CONFIRMED.get(r["id"])
        if tag and tag[0] not in r["rulings"]:
            r["rulings"] = r["rulings"] + [tag[0]]
            r["derivation"] = r["derivation"] + "; " + tag[1]
    hdr["row_count"] = len(rows)
    if "no_eligible_contract" not in hdr["closed_reasons_used"]:
        hdr["closed_reasons_used"].insert(2, "no_eligible_contract")
    with open(p, "w", newline="\n", encoding="ascii") as fh:
        fh.write('{"header":' + json.dumps(hdr, sort_keys=True) + ',\n"rows":[\n')
        fh.write(",\n".join(json.dumps(r, sort_keys=True, ensure_ascii=True) for r in rows))
        fh.write("\n]}\n")
    print(f, len(rows))
