"""Row assembly and dataset writer for author-3 families (SYNTHETIC, stdlib only)."""
import json
import os
import sys
import m3a_tune3
from decimal import Decimal as D
from m3a_oracle3 import (LABEL, CUT, build_chain, smile_record, Surf, fs, quant, request,
                         tol_for, ev_v4, ev_v5, ev_v6, ev_v7, ev_v8, ev_v10, ev_v11, ev_v21)

BAND_PTS = D("0.05")
BAND_PCT = D("0.1")
SEED = 20261030
CLOSED = ["no_atm_strike", "no_bracketing_expiry", "no_eligible_contract", "insufficient_history", "zero_denominator",
          "no_delta_bracket", "low_surface_coverage", "fewer_than_two_expiries",
          "no_prior_reading"]

ASSERT_KEYS = {
    "V4": ["now", "prior", "change_points", "change_ratio", "prior_kind", "iv_form"],
    "V5": ["pairs"],
    "V6": ["nearest_days", "second_days", "spread_points"],
    "V7": ["now", "gap_change_points", "priors.session_id"],
    "V8": ["put25_iv", "call25_iv", "skew_points", "tenor", "delta_convention"],
    "V10": ["now", "change_points", "priors.session_id", "delta_convention"],
    "V11": ["wings_mid", "atm_iv", "curvature_points", "delta_convention"],
    "V21": ["ratio", "put_distance", "call_distance", "delta_convention"],
}
SERIES = {"V4": "XYZ/stock/iv30", "V7": "XYZ/stock/term_30_91", "V10": "XYZ/stock/skew25"}
OUT_ID = {"V4": "M3A-3", "V5": "M3A-4", "V6": "M3A-5", "V7": "M3A-6", "V8": "M3A-7",
          "V10": "M3A-9", "V11": "M3A-10", "V21": "M3A-11"}


def prior_rec(kind, value, time_ns, session_id=None):
    r = {"kind": kind, "value": value, "time_ns": time_ns}
    if session_id is not None:
        r["session_id"] = session_id
    return r


def store_rec(values_int, times=None):
    """most recent first; values in 1e-8 units."""
    out = []
    for i, v in enumerate(values_int):
        out.append({"session_id": "S-%02d" % (i + 1), "time_ns": (times[i] if times else CUT - (i + 1) * 86_400_000_000_000),
                    "value_int": int(v)})
    return out


CONV_FAMS = ("V8", "V10", "V11", "V21")
TUNE_FAMS = ("V5", "V6", "V7", "V8", "V10", "V11", "V21")


def evaluate(fam, spec, req, prior=None, store=None):
    cv = req.get("delta_convention", "spot") if fam in CONV_FAMS else "spot"   # R-149/R-155: V4-V7 ignore the key
    sf = Surf(spec, conv=cv if cv in ("spot", "forward") else "spot")
    if fam == "V4":
        return sf, ev_v4(sf, req, prior)
    if fam == "V5":
        return sf, ev_v5(sf, req)
    if fam == "V6":
        return sf, ev_v6(sf, req)
    if fam == "V7":
        return sf, ev_v7(sf, req, store or [])
    if fam == "V8":
        return sf, ev_v8(sf, req)
    if fam == "V10":
        return sf, ev_v10(sf, req, prior, store or [])
    if fam == "V11":
        return sf, ev_v11(sf, req)
    if fam == "V21":
        return sf, ev_v21(sf, req)
    raise KeyError(fam)


DEFAULTS = {
    "V4": {"direction": "up", "threshold": "10", "iv_form": "atm"},
    "V5": {"direction": "up", "threshold": "3"},
    "V6": {"direction": "up", "threshold": "3"},
    "V7": {"direction": "either", "threshold": "2"},
    "V8": {"direction": "up", "threshold": "5", "delta_convention": "spot"},
    "V10": {"direction": "either", "threshold": "2", "condition": "change", "prior_kind": "frame", "delta_convention": "spot"},
    "V11": {"direction": "up", "threshold": "3", "delta_convention": "spot"},
    "V21": {"direction": "up", "delta_convention": "spot"},
}


def fill(fam, req):
    er = dict(req)
    for k, v in DEFAULTS[fam].items():
        er.setdefault(k, v)
    return er


def make_row(fam, rid, design_ref, rulings, spec, req, prior=None, store=None, derivation="",
             dp=4, tags=(), pending=None, params_extra=None, force_assert=None):
    req_sent = dict(req)
    req = fill(fam, req)
    if "threshold" in req_sent:
        req_sent[{"up": "at_least", "down": "at_most", "either": "x"}[req["direction"]]] = req_sent.pop("threshold")
    if "pair" in req_sent:
        req_sent["pair"] = req_sent["pair"].replace("_", "-")
    sf, res = evaluate(fam, spec, req, prior, store)
    chain = build_chain(spec, dp=dp)
    avail = res["status"] == "available"
    if avail and fam in CONV_FAMS:
        res["value"]["delta_convention"] = req["delta_convention"]
    fire_assert = False
    near = False
    amap = list(ASSERT_KEYS[fam])
    sign_assert = None
    if avail and res["fired"] is not None:
        rule = res["rule"]
        if rule["kind"] == "sign":
            now, ref = D(rule["now"]), D(rule["ref"])
            now_far = abs(now) * 100 >= BAND_PTS
            ref_far = abs(ref) * 100 >= BAND_PTS
            fire_assert = (ref == 0) or (now_far and ref_far)
            sign_assert = {"sign_now": now_far, "sign_prior": ref == 0 or ref_far,
                           "sign_changed": fire_assert}
        elif rule["kind"] == "pct":
            fire_assert = res["margin"] >= BAND_PCT
        elif rule["kind"] == "ratio":
            tol = D(tol_for(res, fam)["ratio"])
            fire_assert = res["margin"] >= 3 * tol
        else:
            fire_assert = res["margin"] >= BAND_PTS
        near = not fire_assert
    if fam == "V10" and avail and sign_assert is None:
        # change condition: sign fields still reported; assert sign only when far from zero
        rr = D(res["value"]["now"])
        now_far = abs(rr) * 100 >= BAND_PTS
        refv = D(prior["value"]) if req["prior_kind"] == "frame" else D(store[int(req["prior_sessions"]) - 1]["value_int"]) / D(10 ** 8)
        ref_far = refv == 0 or abs(refv) * 100 >= BAND_PTS
        sign_assert = {"sign_now": now_far, "sign_prior": ref_far, "sign_changed": (refv == 0) or (now_far and ref_far)}
    if sign_assert:
        for k, v in sign_assert.items():
            if v:
                amap.append(k)
    exp = {"status": res["status"], "reason": res["reason"], "code": res["code"], "value": res["value"],
           "tol": tol_for(res, fam) if avail else None, "assert": amap if avail else [],
           "fired": res["fired"], "fire_assert": bool(fire_assert) if avail else (res["status"] != "available"),
           "labels": res["labels"], "labels_assert": avail,
           "coverage": {"contract_reasons": res["contract_reasons"]},
           "rule": res["rule"], "margin": (fs(quant(res["margin"], 8)) if res["margin"] is not None else None),
           "near_threshold": near}
    if force_assert is not None and avail:
        exp["fire_assert"] = force_assert
    params = {k: req[k] for k in ("direction", "threshold", "prior_sessions", "condition", "prior_kind", "pair",
                                  "delta_target", "delta_convention", "iv_form", "tenors", "min_strikes", "min_coverage", "mode", "feed_delay_tag")
              if k in req and (k != "delta_convention" or fam in CONV_FAMS)}   # R-174: not echoed on V4-V7
    if params_extra:
        params.update(params_extra)
    st = "RULED" if not pending else "RULED (PO batch 2: " + pending + " settled)"
    pending = None
    row = {"id": rid, "family": fam, "output_id": OUT_ID[fam], "design_ref": design_ref,
           "rulings": rulings, "ruling_status": st, "gating": not near,
           "provenance": "SYNTHETIC", "tags": list(tags),
           "inputs": {"series_id": ("XYZ/stock/" + ("iv30" if req.get("iv_form") == "30d" else "atm_iv") if fam == "V4" else ("XYZ/stock/skew25_fwd" if (fam == "V10" and req.get("delta_convention") == "forward") else SERIES.get(fam))), "chain": chain, "prior": prior, "priors_store": store, "request": req_sent},
           "params": params, "oracle": {"smile": smile_record(spec), "quote_dp": dp},
           "expected": exp, "derivation": derivation}
    if ("boundary-exact" in tags and fam in TUNE_FAMS and avail and res["rule"] and res["rule"]["kind"] in ("pts", "ratio")):
        new_in, offs, xraw = m3a_tune3.tune(fam, {"chain": row["inputs"]["chain"], "request": row["inputs"]["request"],
                                                  "prior": prior, "priors_store": store}, res["rule"]["x"])
        if offs:   # R-182: quotes shifted by whole 1e-8 ticks so the value from the quote text lands on the threshold text
            row["inputs"]["chain"] = new_in["chain"]
            exp["boundary"] = {"exact": True, "quote_ticks": offs, "raw_x": format(quant(xraw, 11), "f"),
                               "note": "R-182: value computed from the quote text, full precision, rounds to rule.x under round-once and under round-annual-first"}
            row["tags"] = list(row["tags"]) + ["quote-tuned"]
            row["derivation"] = derivation + "; R-182: quotes shifted by whole 1e-8 ticks (see expected.boundary) so the quote-text value rounds exactly to the boundary"
            row["rulings"] = list(rulings) + ["R-182"]
    return row


def write_dataset(fam, rows, outdir, gen_name, note):
    os.makedirs(outdir, exist_ok=True)
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate ids"
    hdr = {"provenance": "SYNTHETIC", "qualification_label": LABEL, "generator": gen_name, "seed": SEED,
           "schema_version": 1, "family": fam, "row_count": len(rows),
           "note": note,
           "tolerance": {"iv_abs": "0.00003", "diff_annual_abs": "0.00006", "points_abs": "0.005",
                         "fire_band_points": "0.05", "fire_band_percent": "0.1"},
           "model": "BSM European, midpoint, continuous r and q, ACT/365, expiry N x 24 h after cutoff",
           "closed_reasons_used": CLOSED}
    path = os.path.join(outdir, "m3a_cases_%s.json" % fam.lower())
    with open(path, "w", newline="\n", encoding="ascii") as f:
        f.write('{"header":' + json.dumps(hdr, sort_keys=True) + ',\n"rows":[\n')
        f.write(",\n".join(json.dumps(r, sort_keys=True, ensure_ascii=True) for r in rows))
        f.write("\n]}\n")
    return path


def outdir_arg():
    a = sys.argv[1:]
    if "--out" in a:
        return a[a.index("--out") + 1]
    return "."
