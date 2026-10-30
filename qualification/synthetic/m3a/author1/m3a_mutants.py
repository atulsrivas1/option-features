#!/usr/bin/env python3
"""Mutation runner (author 1). Each mutant is the independent engine (m3a_ref.py) with ONE rule made wrong.
A mutant is caught by a row when the mutated engine disagrees with the row expected values (status, reason, counts,
labels exact; IV 1e-4, forward 1e-6). Only gating (vega >= 4) rows count as catching rows; PENDING-RULING rows are
listed separately. Usage: m3a_mutants.py DIR [OUT_FILE]"""
import glob, json, os, sys
import m3a_ref as R

MUTANTS = [
    # group 1 surface
    ("M01", "surface", "forward without carry (F = S)", "fwd_nocarry"),
    ("M02", "surface", "forward ignores dividend yield", "fwd_noq"),
    ("M03", "surface", "forward carry on a 360 day basis", "fwd_basis360"),
    ("M04", "surface", "ATM strike nearest spot (K/S instead of K/F)", "spot_nearest"),
    ("M05", "surface", "ATM tie goes to the higher strike", "tie_high"),
    ("M06", "surface", "ATM IV from the call only", "call_only"),
    ("M07", "surface", "ATM IV from the put only", "put_only"),
    ("M08", "surface", "ATM strike needs only one right eligible", "atm_one_right"),
    ("M09", "delta", "delta from the ATM IV instead of the contract IV", "delta_atm_iv"),
    ("M10", "delta", "forward delta (no e^{-qT})", "fwd_delta"),
    ("M11", "delta", "put delta taken as 1 - call delta", "put_from_call"),
    ("M12", "delta", "each side from the mean of both rights (R-06 violated)", "mean_rights"),
    ("M13", "delta", "scan order reversed (from the outer wing inward)", "scan_inward"),
    ("M14", "delta", "first crossing replaced by the last", "last_crossing"),
    ("M15", "delta", "extrapolation allowed (nearest listed delta used when no bracket)", "extrap"),
    # group 2 interpolation
    ("M16", "interp", "25-delta step interpolated in total variance", "tv_interp"),
    ("M17", "interp", "delta rounded to 2 decimals before interpolation", "round2"),
    ("M18", "interp", "interpolation weight fixed at one half", "midpoint_w"),
    ("M19", "interp", "no interpolation: IV of the listed strike with the closer delta", "nearest_strike"),
    ("M20", "interp", "IV interpolated linear in ln K at the strike found linear in K", "iv_linear_strike"),
    ("M21", "tenor", "tenor interpolated linear in IV instead of total variance", "tenor_linear_iv"),
    ("M22", "tenor", "tenor extrapolation (flat from the nearest expiry)", "tenor_extrap"),
    ("M23", "tenor", "exact expiry ignored, neighbours interpolated", "tenor_exact_ignored"),
    ("M24", "tenor", "expiry without usable ATM skipped when bracketing", "tenor_skip_inelig"),
    # gates
    ("M25", "gate", "stale quotes counted as eligible", "stale_counted"),
    ("M26", "gate", "nonstandard condition counted as eligible", "cond_counted"),
    ("M27", "gate", "crossed quotes counted as eligible", "crossed_counted"),
    ("M28", "gate", "locked quotes counted as eligible", "locked_counted"),
    ("M29", "gate", "american_itm contracts included", "itm_included"),
    ("M30", "gate", "style None treated as European", "unknown_as_euro"),
    ("M31", "gate", "quotes after the cutoff counted (known_at ignored)", "noquote_counted"),
    ("M32", "gate", "contract reason order swapped (stale before excluded_condition)", "reason_swap"),
    ("M33", "gate", "ask used as price instead of the midpoint", "price_ask"),
    # group 3 coverage
    ("M34", "coverage", "3/5 replaced by 1/2", "cov_half"),
    ("M35", "coverage", "coverage boundary exclusive (> instead of >=)", "cov_exclusive"),
    ("M36", "coverage", "min_strikes off by one (needs one more)", "min_plus1"),
    ("M37", "coverage", "min_strikes not applied", "min_off"),
    ("M38", "coverage", "near-the-money rule dropped", "near_off"),
    ("M39", "coverage", "eligible strikes counted as both-rights strikes", "elig_both"),
    ("M40", "coverage", "listed strikes counted as eligible only (ratio always 1)", "listed_eligible_only"),
    ("M41", "coverage", "coverage gate before the ATM gate", "coverage_first"),
    ("M42", "expiry", "expiry_days >= 2 required (off by one)", "min_days_2"),
    ("M43", "expiry", "expiry_days 0 accepted", "allow_zero"),
    ("M47", "solver", "solver-failure contract kept eligible (bounds ignored)", "bounds_ignored"),
    ("M48", "solver", "price_out_of_bounds and upper_asymptote swapped", "bounds_swap"),
    ("M49", "solver", "price exactly at the lower bound treated as a failure", "lower_equal_fails"),
    ("M50", "solver", "price strictly above the upper bound named upper_asymptote", "above_is_asym"),
    ("M51", "gate", "eligible = quote gates only (american_itm, style_unknown, solver failures counted eligible)", "quote_gates_only"),
    ("M52", "delta", "scan from the lowest strike instead of outward from the ATM strike", "lowest_scan"),
    ("M53", "struct", "structural request code evaluated last (upstream reason reported instead)", "struct_last"),
    ("M54", "convention", "delta_convention ignored: always spot", "conv_ignored_spot"),
    ("M55", "convention", "delta_convention ignored: always forward", "conv_ignored_forward"),
    ("M56", "convention", "spot and forward swapped", "conv_swapped"),
    ("M57", "convention", "invalid or non-string delta_convention accepted as spot", "conv_lenient"),
    ("M58", "convention", "omitted delta_convention treated as forward", "conv_default_forward"),
    # labels
    ("M44", "label", "label always exact-model", "label_exact_always"),
    ("M45", "label", "label always approximate", "label_approx_always"),
    ("M46", "label", "delayed label missing", "delayed_missing"),
]


def load_rows(d):
    rows = []
    for p in sorted(glob.glob(os.path.join(d, "m3a_cases_*.json"))):
        doc = json.load(open(p, "rb"))
        for r in doc["rows"]:
            rows.append(r)
    return rows


def run(d):
    rows = load_rows(d)
    base_bad = [r["id"] for r in rows if r["gating"] and R.compare(r, R.run(r))]
    out = []
    for (mid, grp, desc, flag) in MUTANTS:
        M = frozenset([flag])
        caught, caught_pending, nongating = [], [], []
        for r in rows:
            bad = R.compare(r, R.run(r, M))
            if not bad:
                continue
            if not r["gating"]:
                nongating.append(r["id"])
            elif r["ruling_status"] == "RULED":
                caught.append(r["id"])
            else:
                caught_pending.append(r["id"])
        out.append(dict(id=mid, group=grp, desc=desc, flag=flag, caught=caught, caught_pending=caught_pending, nongating=nongating))
    return rows, base_bad, out


def main(argv):
    d = argv[1] if len(argv) > 1 else "."
    rows, base_bad, out = run(d)
    lines = ["M3a author-1 mutation results (SYNTHETIC; Windows x64, CPython 3.12 label applies to the fixtures)",
             "rows=%d  unmutated engine failures on gating rows=%d" % (len(rows), len(base_bad)),
             "mutants=%d" % len(out)]
    worst = 10 ** 9
    uncaught = []
    for m in out:
        n_all = len(m["caught"]) + len(m["caught_pending"])
        worst = min(worst, n_all)
        ok = n_all >= 2
        if not ok:
            uncaught.append(m["id"])
        lines.append("%s [%s] %-62s caught_by_ruled=%3d pending=%2d  %s  e.g. %s" % (
            m["id"], m["group"], m["desc"], len(m["caught"]), len(m["caught_pending"]), ("RULED" if len(m["caught"]) >= 2 else "PENDING-ONLY") if ok else "FEW", ", ".join((m["caught"] + m["caught_pending"])[:4])))
    pend_only = [m["id"] for m in out if len(m["caught"]) < 2 and len(m["caught"]) + len(m["caught_pending"]) >= 2]
    lines.append("mutants caught by fewer than 2 RULED rows (caught by PENDING-RULING rows, tied to open questions): %s" % (",".join(pend_only) or "none"))
    lines.append("RESULT %s: every mutant caught by >= 2 gating rows: %s" % ("PASS" if not uncaught and not base_bad else "FAIL", "yes" if not uncaught else "no, see " + ",".join(uncaught)))
    text = "\n".join(lines) + "\n"
    print(text)
    if len(argv) > 2:
        open(argv[2], "w", newline="\n").write(text)
    return 0 if (not uncaught and not base_bad) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
