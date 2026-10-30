"""V21 (M3A-11) fixture generator: (put25 - ATM)/(call25 - ATM) at 30 days (SYNTHETIC)."""
from decimal import Decimal as D
from m3a_oracle3 import spec_of, ex, request, fs, bisect_param
from m3a_rowkit3 import make_row, write_dataset, outdir_arg
from m3a_skewkit3 import s30, ratio_of, deviant

R = ["R-38", "R-04", "R-09", "R-10", "R-16", "R-20", "R-27", "R-28", "R-84", "R-35", "R-36", "R-95"]
rows = []


def rs(target, b, lo, hi, **kw):
    c = bisect_param(lambda c: ratio_of(s30(b=b, c=fs(c), **kw)), D(lo), D(hi), D(target))
    return s30(b=b, c=fs(c), **kw)


def add(spec, rid, why, direction=None, thr=None, dp=4, pending=None, tags=(), extra=(), **kw):
    rq = request(direction=direction, threshold=thr, tenors=[30], **kw)
    rows.append(make_row("V21", rid, "V21; R-38 (put distance over call distance)", R + list(extra), spec, rq,
                         derivation=why, dp=dp, pending=pending, tags=tags))


POS = dict(b="-0.3", lo="12", hi="30")
NEG = dict(b="-0.5", lo="0.5", hi="8")
for i, (t, w) in enumerate([("3", "fires"), ("2.6", "fires"), ("1.4", "no")]):
    add(rs(t, **POS), "V21-A%d" % (i + 1),
        "ratio %s (both distances positive), default direction up, X 2: %s" % (t, w), thr="2",
        tags=["default-direction"])
for i, (t, w) in enumerate([("1.4", "fires (ratio at most X)"), ("2.6", "no"), ("3", "no")]):
    add(rs(t, **POS), "V21-B%d" % (i + 1), "direction down, X 2, ratio %s: %s" % (t, w), direction="down", thr="2")
for i, (t, d, x, w) in enumerate([("-2", "up", "1", "negative distance: ratio -2 below X 1: no fire"),
                                  ("-2", "down", "-1", "ratio -2 at most -1: fires"),
                                  ("-2", "down", "-3", "ratio -2 above -3: no fire"),
                                  ("-4", "down", "-3", "ratio -4 at most -3: fires")]):
    add(rs(t, **NEG), "V21-C%d" % (i + 1), w + " (call distance negative, shown)", direction=d, thr=x,
        tags=["negative-distance"])
for i, (t, d, x) in enumerate([("2", "up", "2"), ("2", "down", "2"), ("-2", "up", "-2"), ("-2", "down", "-2")]):
    add(rs(t, **(POS if t == "2" else NEG)), "V21-D%d" % (i + 1),
        "ratio exactly %s, inclusive, quotes 8 decimals, near threshold" % t,
        direction=d, thr=x, dp=8, tags=["boundary-exact"])
add(s30(b="0", c="0"), "V21-E1", "flat smile: call distance 0 after rounding: zero_denominator (R-38)", thr="2", dp=8,
    tags=["zero-denominator"])
over = {D(k): D("0.20") for k in ("1020", "1035", "1050", "1065", "1080")}
add(spec_of([ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.5", c="1.5", over=over)]), "V21-E2",
    "call-side IVs equal the ATM IV (call distance 0), put distance positive: zero_denominator", thr="2", dp=8,
    tags=["zero-denominator"])
add(s30(b="0", c="0", q="0.10"), "V21-E3", "flat smile, q 0.10: zero_denominator", thr="2", dp=8,
    tags=["zero-denominator"])


def lim(ks):
    return spec_of([ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.3", c="12", strikes=ks)])


add(lim(["990", "1005", "1020", "1035", "1050", "1065", "1080"]), "V21-F1", "put side not bracketed: no_delta_bracket",
    thr="2", tags=["side-missing"])
add(lim(["930", "945", "960", "975", "990", "1005", "1020"]), "V21-F2", "call side not bracketed: no_delta_bracket",
    thr="2", tags=["side-missing"])
add(lim(["990", "1005", "1020"]), "V21-F3", "3 listed strikes: low_surface_coverage", thr="2", tags=["coverage"])
bk = spec_of([ex(20, "1000", "0.03", "0.01", atm="0.18", b="-0.3", c="14"),
              ex(45, "1000", "0.03", "0.01", atm="0.26", b="-0.3", c="9")])
add(bk, "V21-G1", "30d from 20d and 45d expiries by linear total variance (put25, call25, ATM each)", thr="1",
    tags=["tenor-interp"])
add(rs("2.6", style="american", **POS), "V21-G2", "American-style chain: label approximate",
    thr="2", pending="D-02", extra=["R-11"], tags=["american"])
add(rs("3", **POS), "V21-G3", "delayed tag: computed and labelled delayed", thr="2", tag="delayed", extra=["R-58"])
add(deviant(rs("2.6", shift=True, **POS), "960", "put", "stale", "0.07"), "V21-G4", "grid shifted so S and F pick different ATM strikes; put at about 960 stale (20 s) with a deviant IV", thr="2", tags=["shift", "stale"])
add(rs("3", **POS), "V21-T1", "no threshold in the request: structural threshold_required (R-36 gives V21 no default; PO batch 2 D-06)", thr=None, tags=["threshold-required"])
add(rs("2.6", shift=True, **POS), "V21-T2", "no threshold, direction down: threshold_required", direction="down", thr=None, tags=["threshold-required"])
add(lim(["990", "1005", "1020", "1035", "1050", "1065", "1080"]), "V21-H1", "two conditions: put side not bracketed and no threshold: surface reason first (no_delta_bracket), D-09", thr=None)
add(lim(["990", "1005", "1020"]), "V21-H2", "two conditions: 3 strikes and no threshold: low_surface_coverage first, D-09", thr=None)
for i, (s20, s45) in enumerate([("american", "european"), ("european", "american")]):
    add(spec_of([ex(20, "1000", "0.03", "0.01", atm="0.18", b="-0.3", c="14", style=s20), ex(45, "1000", "0.03", "0.01", atm="0.26", b="-0.3", c="9", style=s45)]),
        "V21-X%d" % (i + 1), "mixed frame: 20d %s and 45d %s: both labels, sorted" % (s20, s45), thr="1", extra=["PO batch 2"], tags=["mixed-style"])
for i, (t, thr, w) in enumerate([("3", "2", "fires"), ("2.6", "2", "fires"), ("1.4", "2", "no")]):
    add(rs(t, conv="forward", q="0.10", **POS), "V21-Cv%d" % (i + 1), "forward delta convention, q 0.10, ratio %s vs X %s: %s" % (t, thr, w), thr=thr, tags=["forward"], delta_convention="forward")
add(rs("3", conv="forward", q="0.10", **POS), "V21-Cv4", "chain of Cv1 read with the default spot convention: a different ratio", thr="2", tags=["spot", "default"])
add(rs("3", q="0.10", **POS), "V21-Cv5", "explicit spot, q 0.10", thr="2", tags=["spot"], delta_convention="spot")
add(rs("3", **POS), "V21-Cv6", "delta_convention 'Forward ': convention_not_allowed", thr="2", tags=["selector"], delta_convention="Forward ")
add(rs("3", **POS), "V21-Cv7", "delta_convention 0.5 (non-string): malformed_type", thr="2", tags=["selector"], delta_convention=0.5)
assert len(rows) == 37, len(rows)
if __name__ == "__main__":
    write_dataset("V21", rows, outdir_arg(), "gen_m3a_v21.py",
                  "V21 rows: ratio = (put25_30 - atm_30)/(call25_30 - atm_30); distances reported as annual decimals (unit pending, D-03); threshold required (no default, D-06); up fires ratio >= X, down fires ratio <= X.")
