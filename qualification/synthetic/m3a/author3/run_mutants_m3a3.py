"""Mutation runner: every mutant is a switch in the second implementation (m3a_ref3); a mutant is caught by a
row when the mutated output disagrees with the stored expectation (status, reason, code, labels,
contract_reasons, asserted values within tolerance, fired where asserted). Rows tagged boundary/zero
(8-decimal quotes) are compared strictly (fired and signs asserted) because the reference reproduces the
rounded decimals exactly. SYNTHETIC."""
import sys
import m3a_ref3 as ref
from selfcheck_m3a3 import load, compare, strict_row

MUT = {
    "M01": "wrong forward: no carry (F = S for ATM choice, no drift in delta)",
    "M02": "ATM strike nearest the spot instead of the forward",
    "M03": "delta computed at the ATM IV instead of the contract IV",
    "M04": "forward delta (no exp(-qT) factor)",
    "M05": "strike scan reversed (outermost strike inward)",
    "M06": "ATM tie goes to the higher strike",
    "M07": "last crossing instead of the first",
    "M08": "extrapolation allowed (flat IV of the nearest-delta strike)",
    "M09": "IV linear in log-moneyness instead of delta",
    "M10": "linear total variance in delta instead of linear IV",
    "M11": "IVs rounded to 3 decimals before interpolation",
    "M12": "tenor interpolation linear in IV instead of total variance",
    "M13": "skew sign swapped (call minus put)",
    "M14": "term sign swapped (shorter minus longer; V7 gap iv30-iv91)",
    "M15": "V6 uses nearest and second LISTED expiries (coverage ignored)",
    "M16": "curvature without the half",
    "M17": "V21 inverted (call distance over put distance)",
    "M18": "V21 zero call distance treated as available",
    "M19": "V4 prior 0 divided instead of zero_denominator",
    "M20": "sign change through 0 counted (0 treated as a side)",
    "M21": "prior source swapped (frame instead of session store and back)",
    "M22": "first prior used instead of the n-th prior session",
    "M23": "direction ignored (always either; V21 always up)",
    "M24": "thresholds exclusive instead of inclusive",
    "M25": "hidden in-memory state used as the prior (previous result)",
    "M26": "prior reading time at or after the cutoff accepted",
    "M27": "V4 fires on change_points instead of relative percent",
    "M28": "default direction wrong (V4 either, V7 up, others swapped)",
    "M29": "V5 pair 30-91 uses 91 minus 9",
    "M30": "skew from the listed expiry nearest 30 days instead of per-side constant maturity",
    "M31": "constant maturity of the skew value instead of per-side",
    "M32": "coverage accepts 3 strikes (min_strikes 3 instead of 4)",
    "M33": "condition other than regular treated as eligible",
    "M34": "crossed quotes treated as eligible",
    "M35": "stale quotes treated as eligible",
    "M36": "put delta taken as the call delta (wrong right)",
    "M37": "American label dropped (always exact-model)",
    "M38": "no_delta_bracket reported as no_bracketing_expiry",
    "M39": "tenor extrapolation allowed (flat beyond the last expiry)",
    "M40": "intraday delayed tag accepted for V4",
    "M41": "delayed label dropped",
    "M42": "V4 ATM form uses the nearest LISTED expiry (coverage ignored)",
    "M43": "V4 iv_form default 30d instead of atm",
    "M44": "V4 iv_form selector ignored (always 30d)",
    "M45": "delta convention swapped (spot request computed as forward and back)",
    "M46": "delta convention ignored (always spot)",
    "M47": "convention_mismatch not checked for priors",
    "M48": "coverage.contract_reasons dropped",
    "M49": "empty or all-excluded chain reported as low_surface_coverage instead of no_eligible_contract (R-106)",
    "M50": "delta_convention validated on V4-V7 (bad value gives convention_not_allowed or malformed_type; R-149, R-155, R-174)",
    "M51": "delta_convention echoed in V4-V7 value (R-174)",
    "M52": "ATM-form labels taken from every expiry in the frame, not only the one the output uses (R-180)",
    "M53": "iv_form matched case-insensitively and trimmed (ATM, 30D accepted)",
    "M54": "non-string iv_form reported as iv_form_not_allowed instead of malformed_type",
}


def main():
    sys.stdout.reconfigure(newline=chr(10))   # LF on Windows too
    d = sys.argv[1] if len(sys.argv) > 1 else "."
    rows = load(d)
    ref.STATE["last_now"] = None
    allok = True
    print("%-4s %-7s %-7s %-7s %s" % ("id", "assert", "strict", "gating", "description : first catching rows"))
    for m in sorted(MUT):
        ca, cs, cg, ids = 0, 0, 0, []
        ref.STATE["last_now"] = None
        for row in rows:
            try:
                got = ref.evaluate(row["family"], row["inputs"], frozenset([m]))
            except Exception:
                got = None
            if got is None:
                ca += 1; cs += 1; cg += int(row["gating"]); ids.append(row["id"] + "!")
                continue
            if compare(row, got, strict=False):
                ca += 1
            if compare(row, got, strict=strict_row(row)):
                cs += 1
                cg += int(row["gating"])
                if len(ids) < 4:
                    ids.append(row["id"])
        flag = "" if cs >= 2 else "  <-- NOT CAUGHT BY 2 ROWS"
        if cs < 2:
            allok = False
        print("%-4s %-7d %-7d %-7d %s : %s%s" % (m, ca, cs, cg, MUT[m], ",".join(ids), flag))
    print("mutants %d, all caught by >= 2 rows (strict compare on 8-decimal rows; columns: assert = as an implementation harness asserts, strict = also fired and signs on 8-decimal rows, gating = strict count over non-PENDING rows): %s" % (len(MUT), allok))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
