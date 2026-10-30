"""Generator for the UNITS AND ROUNDING family: round once half to even to 8 decimals (R-48, R-49), integer 10^-8 units,
points keys (x100), rational output form. SYNTHETIC. End-to-end rows go through V1 and V9; kernel rows state a harness op."""
import os

import gen_m3a_g4 as G
import m3a_common as C
import m3a_ref as R


def build():
    rows = []

    def U1(n_id, oid, hist, x_units, **kw):
        rid = "M3A-U-%03d" % n_id
        kw.setdefault("X", 50)
        kw.setdefault("rules", ("R-48", "R-49", "R-45"))
        kw["tags"] = list(kw.get("tags", [])) + ["units", "ties"]
        rows.append(G.pct_row(rid, "units", oid, G.rng_for(rid), ge=0, le=0, n=len(hist), vals_override=hist, now_units=x_units,
                              skew=(oid == "M3A-8"), **kw))

    def hist_around(u, lo_n=6, hi_n=6, eq=6):
        return [u - 1] * lo_n + [u] * eq + [u + 1] * hi_n + [u - 500_000] * 4 + [u + 500_000] * 4

    # V1 float values: exact binary64 ties at 8 decimals are m/512 with m odd
    for k, (num, units, why) in enumerate([(1, 195_312, "down to the even digit 2"), (3, 585_938, "up to the even digit 8"),
                                           (5, 976_562, "down to the even digit 2"), (7, 1_367_188, "up to the even digit 8")], 1):
        f = num / 512
        U1(k, "M3A-1", hist_around(units), units, x_float=f, tags=["round_once", "half_even"],
           derivation="%d/512 = %s is an exact tie at 8 decimals: half to even %s -> %d units" % (num, repr(f), why, units))
    f = 0.1 + 0.2
    U1(5, "M3A-1", hist_around(30_000_000), 30_000_000, x_float=f, tags=["round_once"], derivation="0.1+0.2 = 0.30000000000000004 -> 30,000,000 units")
    U1(6, "M3A-1", [0] * 6 + [1] * 6 + [100_000] * 12, 0, x_float=4e-9, tags=["round_once", "zero"], derivation="4e-9 rounds to 0 units, shown as 0.00000000")
    U1(7, "M3A-1", hist_around(12_345_678), 12_345_678, x_float=0.123456785, tags=["round_once", "near_tie"],
       derivation="0.123456785 as binary64 is not an exact tie; the exact binary value decides (checked in exact Fractions)")
    U1(8, "M3A-1", hist_around(123_456_789), 123_456_789, x_float=1.23456789012, tags=["round_once"], derivation="1.23456789012 -> 123,456,789 units")
    U1(9, "M3A-1", hist_around(500_000_000), 500_000_000, x_float=5.0, tags=["round_once", "large"], derivation="5.0 -> 500,000,000 units, text 5.00000000")
    # V9 derived series: difference of unrounded floats, rounded once
    U1(10, "M3A-8", hist_around(20_000_000), 20_000_000, put_call={"put25_iv": 0.3000000049, "call25_iv": 0.1000000051}, tags=["derived", "round_once"],
       rules=("R-49", "R-95"), derivation="0.3000000049-0.1000000051 = 0.1999999998 -> 20,000,000; rounding parts first gives 19,999,999")
    U1(11, "M3A-8", hist_around(195_312), 195_312, put_call={"put25_iv": 0.25, "call25_iv": 0.248046875}, tags=["derived", "half_even"],
       rules=("R-49", "R-95"), derivation="difference exactly 1/512: tie, half to even 195,312")
    U1(12, "M3A-8", hist_around(-585_938), -585_938, put_call={"put25_iv": 0.248046875, "call25_iv": 0.25390625}, tags=["derived", "half_even", "negative"],
       rules=("R-49", "R-95"), derivation="difference exactly -3/512 = -0.005859375: tie, half to even -585,938 (not -585,937)")
    U1(13, "M3A-8", [0] * 6 + [-1] * 6 + [1] * 6 + [-500_000] * 3 + [500_000] * 3, 0, put_call={"put25_iv": 0.1, "call25_iv": 0.100000004},
       tags=["derived", "negative_zero"], rules=("R-49", "R-95"), derivation="difference -4e-9 rounds to 0 units: text 0.00000000 with no minus sign")
    # kernel rows (points keys and the stored integer)
    for k, (pu, ca, pts, why) in enumerate([(0.31, 0.2, "11.00000000", "0.31-0.2 = 0.11 -> 11,000,000 units -> 11 points"),
                                            (0.2, 0.3, "-10.00000000", "0.2-0.3 = -0.1 -> -10,000,000 units -> -10 points"),
                                            (0.5, 0.498046875, "0.19531250", "R-181: full precision x100 then one rounding: 0.1953125 points, 195,312 units stored (tie)"),
                                            (0.25, 0.25, "0.00000000", "equal sides: 0 points")], 14):
        rid = "M3A-U-%03d" % k
        u = C.r8(pu - ca)
        row = {"id": rid, "family": "units", "output_id": "M3A-7", "design_ref": "IO contract section 3 (points keys, R-60, R-95)", "ruling": ["R-60", "R-95", "R-49"],
               "tags": ["units", "points_key", "kernel"], "derivation": why,
               "inputs": {"kernel": "skew_points", "put25_iv": pu, "call25_iv": ca}, "params": {}}
        e = R.units_eval(row)
        assert e["value"]["skew_points"] == pts, (rid, e)
        row["expected"] = e
        row["pending"] = "RULED"
        if rid == "M3A-U-016":
            row["ruling"] = row["ruling"] + ["R-181"]
            row["tags"] = row["tags"] + ["RULED-R-181"]
        rows.append(row)
    for k, (f, why) in enumerate([(0.3500000049, "0.3500000049 -> 35,000,000 units"), (-0.0100000051, "-0.0100000051 -> -1,000,001 units (rounds away from zero past .5), text -0.01000001")], 18):
        rid = "M3A-U-%03d" % k
        row = {"id": rid, "family": "units", "output_id": "M3A-12", "design_ref": "R-48 stored integers", "ruling": ["R-48", "R-49"],
               "tags": ["units", "stored_integer", "kernel"], "derivation": why, "inputs": {"kernel": "stored_integer", "float": f}, "params": {}}
        row["expected"] = R.units_eval(row)
        row["pending"] = "RULED"
        rows.append(row)
    # rational output form (reduced n/d, integers for integral values)
    rid = "M3A-U-020"
    rows.append(G.pct_row(rid, "units", "M3A-1", G.rng_for(rid), ge=60, le=0, n=60, now_units=1_000_000, X=100, rules=("R-61", "R-45"),
                          tags=["units", "rational_form", "integral"], derivation="x below all: upper_share 1 and lower_share 0 are shown as integers"))
    rid = "M3A-U-021"
    rows.append(G.pct_row(rid, "units", "M3A-1", G.rng_for(rid), ge=25, le=75, n=100, X=25, rules=("R-61", "R-45"),
                          tags=["units", "rational_form", "reduced"], derivation="25/100 and 75/100 are shown reduced: 1/4 and 3/4"))
    return rows


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    rows = build()
    C.write_dataset(os.path.join(here, "m3a_cases_units.json"), G.header("units"), rows)
    return rows


if __name__ == "__main__":
    print(len(main()))
