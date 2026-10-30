"""V6 (M3A-5) fixture generator: second eligible expiry ATM IV minus nearest eligible (SYNTHETIC)."""
from decimal import Decimal as D
from m3a_oracle3 import spec_of, ex, request, fs
from m3a_rowkit3 import make_row, write_dataset, outdir_arg

R = ["R-32", "R-20", "R-103", "R-104", "R-91", "R-84", "R-35", "R-36", "R-95"]
rows = []


def E(days, atm, n=2, r="0.03", q="0.01", **kw):
    return ex(days, "1000", r, q, atm=fs(atm), n=n, **kw)


def add(spec, rid, why, direction=None, thr=None, dp=4, pending=None, tags=(), extra=(), **kw):
    rq = request(direction=direction, threshold=thr, **kw)
    rows.append(make_row("V6", rid, "V6; R-32", R + list(extra), spec, rq, derivation=why, dp=dp, pending=pending, tags=tags))


def three(sp, **kw):
    a = D("0.20")
    return spec_of([E(7, a, **kw), E(21, a + D(sp) / 100, **kw), E(50, D("0.27"), **kw)])


for i, (sp, w) in enumerate([("4", "fires"), ("3.2", "fires just above X"), ("2.8", "no fire just below X"), ("-4", "negative, default up: no fire")]):
    add(three(sp, **({"shift": True} if i in (1, 3) else {})), "V6-A%d" % (i + 1), "second (21d) minus nearest (7d) = %s points, default direction up, X 3: %s" % (sp, w),
        tags=["default-direction"] + (["shift"] if i in (1, 3) else []))
for i, (sp, w) in enumerate([("-4", "fires"), ("-3.2", "fires"), ("-2.8", "no fire"), ("4", "positive: no fire")]):
    add(three(sp), "V6-B%d" % (i + 1), "direction down, X 3: %s" % w, direction="down", thr="3")
for i, (sp, w) in enumerate([("4", "fires"), ("-4", "fires"), ("2.8", "no fire"), ("-2.8", "no fire")]):
    add(three(sp), "V6-C%d" % (i + 1), "direction either, X 3: %s" % w, direction="either", thr="3")
for i, (sp, d) in enumerate([("3", "up"), ("-3", "down"), ("-3", "either"), ("3", "either")]):
    add(three(sp), "V6-D%d" % (i + 1), "spread exactly %s points, inclusive (R-35), quotes 8 decimals, near threshold" % sp,
        direction=d, thr="3", dp=8, tags=["boundary-exact"])


def lowcov(days, atm):
    return E(days, atm, n=1)   # 3 strikes only: fewer than min_strikes 4 eligible


for i, (sp, d, w) in enumerate([("4", None, "fires"), ("-4", "down", "fires"), ("2", None, "no fire")]):
    spec = spec_of([lowcov(7, D("0.30")), E(21, D("0.20")), E(50, D("0.20") + D(sp) / 100)])
    add(spec, "V6-E%d" % (i + 1), "nearest listed expiry (7d, 3 strikes) is below min_strikes 4 and skipped: nearest eligible 21d, second 50d: %s" % w,
        direction=d, thr="3", tags=["coverage-skip"])
add(spec_of([E(21, D("0.2"))]), "V6-F1", "one expiry only: fewer_than_two_expiries (R-91)")
add(spec_of([lowcov(7, D("0.3")), E(21, D("0.2"))]), "V6-F2", "two expiries, nearest below min_strikes: one eligible: fewer_than_two_expiries", tags=["coverage-skip"])
add(spec_of([lowcov(7, D("0.3")), lowcov(14, D("0.25")), E(21, D("0.2"))]), "V6-F3", "three expiries, two below min_strikes: one eligible: fewer_than_two_expiries", tags=["coverage-skip"])
spec = spec_of([lowcov(7, D("0.30")), E(14, D("0.20")), lowcov(30, D("0.35")), E(60, D("0.25"))])
add(spec, "V6-G1", "ineligible 7d and 30d skipped: nearest eligible 14d, second 60d, spread 5 points, fires (default 3)", tags=["coverage-skip"])
add(spec, "V6-G2", "same chain, direction down, X 3: no fire", direction="down", thr="3", tags=["coverage-skip"])
# ties on the r=q grid (forward 1000 exactly between 992.5 and 1007.5; ATM is the lower strike)
for i, d in enumerate(["up", "either"]):
    spec = spec_of([E(21, D("0.20"), r="0.02", q="0.02", base="992.5"), E(50, D("0.25"), r="0.02", q="0.02", base="992.5")], r="0.02", q="0.02")
    add(spec, "V6-H%d" % (i + 1), "tie grid r=q: forward exactly between two strikes, ATM is the lower strike; second minus nearest 5 points",
        direction=d, thr="3", tags=["tie"])
for i in range(2):
    spec = spec_of([E(21, D("0.20"), shift=True), E(50, D("0.20") + D("0.045") * (1 if i == 0 else -1), shift=True)])
    add(spec, "V6-H%d" % (i + 3), "grid shifted so S and F pick different strikes; ATM taken at the strike nearest F; spread %s points" % ("4.5" if i == 0 else "-4.5"),
        direction="either", thr="3", tags=["shift"])
add(spec_of([E(21, D("0.22"), style="american"), E(50, D("0.26"), style="american")]), "V6-I1",
    "American-style chain: label approximate", pending="D-02", extra=["R-11"], tags=["american"])
add(three("4"), "V6-I2", "delayed tag: computed and labelled delayed", tag="delayed", extra=["R-58"])
add(three("4"), "V6-Cx1", "delta_convention 'sideways' (not a valid value) supplied to V6: ignored, NOT convention_not_allowed (R-149, R-155, R-174); result as without it",
    delta_convention="sideways", extra=["R-174", "R-149", "R-155"], tags=["convention-ignored", "bad-value"])
assert len(rows) == 31, len(rows)
if __name__ == "__main__":
    write_dataset("V6", rows, outdir_arg(), "gen_m3a_v6.py",
                  "V6 rows: ATM IV at the nearest and second ELIGIBLE expiries (eligible = coverage gate of R-20: at least min_strikes 4 eligible strikes).")
