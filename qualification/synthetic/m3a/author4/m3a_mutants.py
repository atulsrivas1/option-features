#!/usr/bin/env python3
"""Mutation run for the structural and lane fixtures (SYNTHETIC, stdlib only). A mutant is a behaviour switch of the
independent reference m3a_ref.py; it is caught by a row when the mutated result differs from `expected`.
Requirement: at least 25 mutants, each caught by at least 2 rows (structural + aux + lane); the count inside the 93
primary rows (structural + lane) is reported too. Usage: python m3a_mutants.py DIR [--out FILE]"""
import sys
import os

import m3a_ref as R
from m3a_common import QUAL, read_rows

MUT = []
for fam, order in (("req", R.REQ_ORDER), ("hist", R.HIST_ORDER), ("snap", R.SNAP_ORDER), ("text", R.TEXT_ORDER),
                   ("view", R.VIEW_ORDER)):
    for i in range(len(order) - 1):
        a, b = order[i], order[i + 1]
        eq = (a, b) in (("h_cal", "h_len"), ("missing", "count"), ("v_cal", "v_minute"), ("minute", "prior"), ("h_dup", "h_ooo"), ("fire", "xrange"), ("ivform", "conv"), ("convmis", "delayed"))
        MUT.append(("pair_swap_%s_%s_%s" % (fam, a, b), {"swap:%s,%s" % (a, b)},
                    "adjacent precedence pair swapped" + (" (EQUIVALENT: the second check cannot run when the first fails, Q03/Q04/Q05, record-major scan)" if eq else "")))
MUT += [
    ("contract_major_scan", {"contract_major"}, "scan contract by contract instead of position by position (R-101)"),
    ("type_check_after_value", {"type_after_value"}, "spot type error reported after every value code (R-67)"),
    ("cutoff_mismatch_skipped", {"skip_mismatch"}, "evaluation_ns versus cutoff_ns never compared (R-100)"),
    ("spot_9_decimals_accepted", {"spot_rep_ok"}, "9-decimal text and non-representable float accepted as spot (R-98)"),
    ("zero_spot_malformed", {"zero_spot_malformed"}, "zero spot reported as malformed_type instead of bad_spot"),
    ("bool_counts_as_int", {"bool_int"}, "True accepted as an int"),
    ("strike_type_at_slot_10", {"strike_type_late"}, "wrong-typed strike reported at the position 10 slot, not 9 (R-67)"),
    ("dividend_before_rate", {"div_before_rate"}, "dividend_yield checked before rate inside position 3"),
    ("dup_id_after_type", {"dup_id_late"}, "duplicate id evaluated after the type slot (R-102a violated)"),
    ("dup_key_before_type", {"move:dupkey,before:type"}, "same expiry/strike/right checked before the type slot (R-102b violated)"),
    ("code_outside_closed_set", {"foreign_code"}, "malformed_type reported as an invented code"),
    ("prior_equal_cutoff_accepted", {"prior_gt"}, "prior at the cutoff accepted (strict instead of at-or-after)"),
    ("minute_equal_grid_accepted", {"minute_le"}, "minute equal to the grid length accepted"),
    ("x_100_rejected", {"x_lt100"}, "x = 100 rejected (upper bound exclusive)"),
    ("minute_last_rejected", {"minute_lt_n1"}, "last minute (389 of 390) rejected"),
    ("price_8_decimals_rejected", {"price_ge8"}, "text price with exactly 8 decimals rejected"),
    ("rate_abs_1_rejected", {"rate_ge1"}, "|rate| = 1 rejected"),
    ("prior_one_ns_before_rejected", {"prior_ge_m1"}, "prior one ns before the cutoff rejected"),
    ("trailing_zeros_trimmed", {"zero_trim"}, "9-decimal text with trailing zeros accepted (value-based, not length-based; R-164)"),
    ("direction_type_unchecked", {"direction_unchecked"}, "non-string direction not checked (R-165)"),
    ("load_scan_position_major", {"load_position_major"}, "history load scanned position-major instead of record-major (R-148)"),
    ("lanes_pooled", {"lane_pool"}, "baseline read ignores the lane (lane isolation lost)"),
]


def main(d, out=None):
    rows = {}
    for k, f in (("structural", "m3a_cases_structural.json"), ("aux", "m3a_cases_structural_aux.json"),
                 ("lane", "m3a_cases_lane.json")):
        rows[k] = read_rows(os.path.join(d, f))[1]
    allr = [(k, r) for k, v in rows.items() for r in v]
    lines, bad, noprim, nequiv = [], 0, 0, 0
    for name, M, desc in MUT:
        caught = [(k, r["id"]) for k, r in allr if not R.agrees(r, R.evaluate(r, frozenset(M)))]
        prim = sum(1 for k, _ in caught if k != "aux")
        equiv = "EQUIVALENT" in desc
        ok = (len(caught) == 0) if equiv else len(caught) >= 2
        nequiv += equiv
        bad += not ok
        noprim += (prim == 0) and not equiv
        lines.append("%-42s caught %3d (primary %3d) %s e.g. %s | %s" % (
            name, len(caught), prim, ("EQV " if equiv else "OK  ") if ok else "FAIL", ",".join(i for _, i in caught[:2]), desc))
    lines.append("mutants %d (%d equivalent by Q04/Q05, %d effective); every effective mutant caught by >= 2 rows: %s; "
                 "effective mutants with no primary-row catch: %d" % (len(MUT), nequiv, len(MUT) - nequiv, bad == 0, noprim))
    text = "\n".join(lines) + "\n"
    print(text)
    if out:
        with open(out, "w", newline="\n") as f:
            f.write("SYNTHETIC. " + QUAL + "\n" + text)
    return 1 if bad else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(a[0] if a else ".", a[a.index("--out") + 1] if "--out" in a else None))
