"""V5 (M3A-4) fixture generator: longer tenor minus shorter tenor, pairs 9-30 and 30-91 (SYNTHETIC)."""
from decimal import Decimal as D
from m3a_oracle3 import spec_of, ex, request, fs
from m3a_rowkit3 import make_row, write_dataset, outdir_arg

R = ["R-14", "R-15", "R-16", "R-31", "R-84", "R-35", "R-36", "R-95"]
rows = []


def E(days, atm, n=2, **kw):
    return ex(days, "1000", "0.03", "0.01", atm=fs(atm), n=n, **kw)


def s5(i9, i30, i91, **kw):
    return spec_of([E(9, i9, **kw), E(30, i30, **kw), E(91, i91, **kw)])


def tri(pair, spread, base=D("0.22")):
    sp = D(spread) / 100
    if pair == "9_30":
        return base - sp, base, base + D("0.01")
    return base - D("0.005"), base, base + sp


def add(pair, spread, rid, why, direction=None, thr=None, spec=None, dp=4, pending=None, tags=(), extra=(), **kw):
    if spec is None:
        i9, i30, i91 = tri(pair, spread)
        spec = s5(i9, i30, i91, **kw.pop("grid", {}))
    rq = request(tenors=[9, 30, 91], pair=pair, direction=direction, threshold=thr, **kw)
    rows.append(make_row("V5", rid, "V5; tenor IV (M1 iv_30d(target))", R + list(extra), spec, rq,
                         derivation=why, dp=dp, pending=pending, tags=tags))


n = 0
for pair in ("9_30", "30_91"):
    for i, (sp, w) in enumerate([("4", "fires"), ("3.2", "fires just above X"), ("2.8", "no fire just below X"), ("-4", "negative: default up, no fire")]):
        gr = {"grid": {"shift": True}} if i == 1 else {}
        add(pair, sp, "V5-A-%s-%d" % (pair, i + 1), "pair %s, longer minus shorter = %s points; default direction up, X 3: %s" % (pair, sp, w), tags=["default-direction"], **gr)
for pair in ("9_30", "30_91"):
    for i, (sp, w) in enumerate([("-4", "fires"), ("-3.2", "fires"), ("-2.8", "no fire"), ("4", "positive: no fire")]):
        add(pair, sp, "V5-B-%s-%d" % (pair, i + 1), "pair %s, direction down, X 3: %s" % (pair, w), direction="down", thr="3")
for i, (sp, w) in enumerate([("4", "fires"), ("-4", "fires"), ("2.8", "no"), ("-2.8", "no")]):
    add("9_30", sp, "V5-C-%d" % (i + 1), "pair 9_30, direction either, X 3: %s" % w, direction="either", thr="3")
for i, (pair, sp, d) in enumerate([("9_30", "3", "up"), ("30_91", "-3", "down"), ("9_30", "-3", "either"), ("30_91", "3", "either")]):
    add(pair, sp, "V5-D-%d" % (i + 1), "spread exactly %s points (inclusive, R-35); quotes 8 decimals; near threshold" % sp,
        direction=d, thr="3", dp=8, tags=["boundary-exact"])
# bracketing tenors: expiries 5, 14, 45, 120 (9 from 5/14, 30 from 14/45, 91 from 45/120)
def brk():
    return spec_of([E(5, D("0.18")), E(14, D("0.30")), E(45, D("0.24")), E(120, D("0.40"))])
for i, (pair, d, w) in enumerate([("9_30", "up", "iv30 above iv9 by about 1 point or more"), ("30_91", "up", "iv91 well above iv30"),
                                  ("9_30", "down", "iv30 vs iv9 down rule"), ("30_91", "either", "either")]):
    add(pair, None, "V5-F-%d" % (i + 1), "tenors by linear total variance from 5/14/45/120 day expiries: %s" % w,
        spec=brk(), direction=d, thr="1", tags=["tenor-interp"])
# missing tenors (no extrapolation)
add("9_30", None, "V5-G-1", "expiries 14 and 45: 9 days has no lower bracket: no_bracketing_expiry",
    spec=spec_of([E(14, D("0.22")), E(45, D("0.24"))]))
add("30_91", None, "V5-G-2", "expiries 14 and 45: 91 days has no upper bracket: no_bracketing_expiry",
    spec=spec_of([E(14, D("0.22")), E(45, D("0.24"))]))
add("30_91", None, "V5-G-3", "only 9 and 30 day expiries: 91 days missing", spec=spec_of([E(9, D("0.20")), E(30, D("0.22"))]))
add("9_30", None, "V5-G-4", "only 30 and 91 day expiries: 9 days missing", spec=spec_of([E(30, D("0.22")), E(91, D("0.24"))]))


def noatm(days, atm, **kw):
    # puts excluded at and below the ATM strike area, calls excluded at and above: no strike eligible for both rights
    e = E(days, atm, n=3, **kw)
    ks = sorted(e["strikes"])
    mid = ks[3]
    mods = {}
    for K in ks[:4]:
        mods[(K, "call")] = "excl"
    for K in ks[3:]:
        mods[(K, "put")] = "excl"
    e["mods"] = mods
    return e


add("9_30", None, "V5-H-1", "exact 30-day expiry has no strike eligible for both rights: no_atm_strike (M1 D14)",
    spec=spec_of([E(9, D("0.20")), noatm(30, D("0.22")), E(91, D("0.24"))]), pending="D-02", tags=["no-atm"])
add("9_30", None, "V5-H-2", "bracketing expiry (14) without ATM strike: no_bracketing_expiry (M1 D14)",
    spec=spec_of([E(5, D("0.19")), noatm(14, D("0.20")), E(45, D("0.22")), E(120, D("0.24"))]), pending="D-02", tags=["no-atm"])
add("30_91", "2", "V5-I-1", "American-style chain: label approximate", pending="D-02",
    grid={"style": "american"}, extra=["R-11"], tags=["american"])
add("9_30", "4", "V5-I-2", "delayed tag (any mode): computed and labelled delayed", tag="delayed", extra=["R-58"])
add("9_30", "4", "V5-Cx1", "delta_convention 'forward' supplied to V5: ignored (R-149, R-155, R-174), result as without it, nothing echoed", delta_convention="forward", extra=["R-174", "R-149", "R-155"], tags=["convention-ignored"])
assert len(rows) == 37, len(rows)
if __name__ == "__main__":
    write_dataset("V5", rows, outdir_arg(), "gen_m3a_v5.py",
                  "V5 rows: spread_points = (longer - shorter) x 100 of rounded-once annual difference; `pair` selects the fired pair (invented request field, defect D-05).")
