"""V11 (M3A-10) fixture generator: wings above or below the centre, (put25 + call25)/2 - ATM at 30 days (SYNTHETIC)."""
from decimal import Decimal as D
from m3a_oracle3 import spec_of, ex, request, fs
from m3a_rowkit3 import make_row, write_dataset, outdir_arg
from m3a_skewkit3 import s30, curv_spec, deviant

R = ["R-37", "R-04", "R-09", "R-10", "R-16", "R-20", "R-27", "R-28", "R-84", "R-35", "R-36", "R-95"]
rows = []


def cv(t, **kw):
    if D(t) < 0:
        kw.setdefault("atm", "0.40")
        kw.setdefault("lo", "-30")
        kw.setdefault("hi", "10")
    else:
        kw.setdefault("lo", "-15")
        kw.setdefault("hi", "28")
    kw.setdefault("b", "-0.3")
    return curv_spec(t, **kw)


def add(spec, rid, why, direction=None, thr=None, dp=4, pending=None, tags=(), extra=(), **kw):
    rq = request(direction=direction, threshold=thr, tenors=[30], **kw)
    rows.append(make_row("V11", rid, "V11; R-37 (wings minus centre in points)", R + list(extra), spec, rq,
                         derivation=why, dp=dp, pending=pending, tags=tags))


for i, (t, w, kw) in enumerate([("5", "fires", {}), ("3.3", "fires just above X", {}),
                                ("2.7", "no fire just below X", {"q": "0.10"}),
                                ("0", "flat curvature: no fire", {}), ("-4", "inverted smile: default up, no fire", {})]):
    add(cv(t, **kw), "V11-A%d" % (i + 1), "curvature %s points, default direction up, X 3: %s" % (t, w),
        tags=["default-direction"] + (["q-high"] if kw else []))
for i, (t, w) in enumerate([("-5", "fires"), ("-3.3", "fires"), ("-2.7", "no"), ("5", "positive: no fire")]):
    add(cv(t), "V11-B%d" % (i + 1), "direction down, X 3, curvature %s points: %s" % (t, w), direction="down", thr="3")
for i, (t, w) in enumerate([("5", "fires"), ("-5", "fires"), ("2.7", "no"), ("-2.7", "no")]):
    add(cv(t), "V11-C%d" % (i + 1), "direction either, X 3, curvature %s points: %s" % (t, w), direction="either", thr="3")
for i, (t, d) in enumerate([("3", "up"), ("-3", "down"), ("3", "either"), ("-3", "either")]):
    add(cv(t), "V11-D%d" % (i + 1), "curvature exactly %s points, inclusive (R-35), quotes 8 decimals, near threshold" % t,
        direction=d, thr="3", dp=8, tags=["boundary-exact"])


def lim(ks):
    return spec_of([ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.3", c="12", strikes=ks)])


add(lim(["990", "1005", "1020", "1035", "1050", "1065", "1080"]), "V11-E1", "put side not bracketed: no_delta_bracket",
    tags=["side-missing"])
add(lim(["930", "945", "960", "975", "990", "1005", "1020"]), "V11-E2", "call side not bracketed: no_delta_bracket",
    tags=["side-missing"])
add(lim(["990", "1005", "1020"]), "V11-F1", "3 listed strikes: low_surface_coverage", tags=["coverage"])
bk = spec_of([ex(20, "1000", "0.03", "0.01", atm="0.18", b="-0.3", c="14"),
              ex(45, "1000", "0.03", "0.01", atm="0.26", b="-0.3", c="9")])
add(bk, "V11-G1", "25-delta per side and ATM at 30d from 20d and 45d expiries, linear total variance",
    direction="either", thr="1", tags=["tenor-interp"])
add(cv("5", style="american"), "V11-H1", "American-style chain: label approximate", pending="D-02", extra=["R-11"],
    tags=["american"])
add(cv("5"), "V11-I1", "delayed tag: computed and labelled delayed", tag="delayed", extra=["R-58"])
add(deviant(cv("4", shift=True), "1035", "call", "cross", "0.07"), "V11-J1", "grid shifted so S and F pick different ATM strikes; call at about 1035 crossed with a deviant IV", tags=["shift", "crossed"])
for i, (s20, s45) in enumerate([("american", "european"), ("european", "american")]):
    add(spec_of([ex(20, "1000", "0.03", "0.01", atm="0.18", b="-0.3", c="14", style=s20), ex(45, "1000", "0.03", "0.01", atm="0.26", b="-0.3", c="9", style=s45)]),
        "V11-X%d" % (i + 1), "mixed frame: 20d %s and 45d %s: both labels, sorted" % (s20, s45), direction="either", thr="1", extra=["PO batch 2"], tags=["mixed-style"])
add(spec_of([ex(20, "1000", "0.03", "0.01", atm="0.18", b="-0.3", c="14", n=1), ex(45, "1000", "0.03", "0.01", atm="0.26", b="-0.3", c="9")]), "V11-N1",
    "bracketing 20d expiry fails coverage (3 strikes): no_bracketing_expiry", tags=["bracket-coverage"])
for i, (t, kw, w) in enumerate([("5", dict(q="0.10"), "fires"), ("2.7", dict(q="0.10"), "no fire"), ("-3", {}, "inverted, default up: no fire"), ("3.3", {}, "fires")]):
    add(cv(t, conv="forward", **kw), "V11-Cv%d" % (i + 1), "forward delta convention, curvature %s points: %s" % (t, w), tags=["forward"], delta_convention="forward")
add(cv("5", q="0.10"), "V11-Cv5", "explicit spot, q 0.10: echoes spot", tags=["spot"], delta_convention="spot")
add(cv("5", q="0.10", conv="forward"), "V11-Cv6", "chain tuned under forward read with the default spot convention", tags=["spot", "default"])
add(cv("5"), "V11-Cv7", "delta_convention 'fwd': convention_not_allowed", tags=["selector"], delta_convention="fwd")
add(cv("5"), "V11-Cv8", "delta_convention true: malformed_type", tags=["selector"], delta_convention=True)
assert len(rows) == 35, len(rows)
if __name__ == "__main__":
    write_dataset("V11", rows, outdir_arg(), "gen_m3a_v11.py",
                  "V11 rows: curvature_points = rounded-once ((put25_30 + call25_30)/2 - atm_30) x 100; wings_mid and atm_iv annual decimals.")
