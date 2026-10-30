"""V8 (M3A-7) fixture generator: 25-delta put-side minus call-side IV at the 30-day tenor (SYNTHETIC)."""
from decimal import Decimal as D
from m3a_oracle3 import spec_of, ex, request, fs, fwd
from m3a_rowkit3 import make_row, write_dataset, outdir_arg
from m3a_skewkit3 import s30, skew_spec

R = ["R-04", "R-06", "R-09", "R-10", "R-16", "R-20", "R-27", "R-28", "R-84", "R-35", "R-36", "R-95"]
rows = []


def add(spec, rid, why, direction=None, thr=None, dp=4, pending=None, tags=(), extra=(), **kw):
    rq = request(direction=direction, threshold=thr, tenors=[30], **kw)
    rows.append(make_row("V8", rid, "V8; R-27 R-28 (25-delta put minus call at 30d)", R + list(extra), spec, rq,
                         derivation=why, dp=dp, pending=pending, tags=tags))


# A default direction up, X 5 omitted
for i, (t, kw, w) in enumerate([("8", {}, "fires"), ("5.3", {"q": "0.10"}, "fires just above X; q 0.10"),
                                ("4.7", {"q": "0.10"}, "no fire just below X; q 0.10"),
                                ("0", {}, "no skew: no fire"), ("-6", {}, "call side above put side: default up, no fire")]):
    add(skew_spec(t, **kw), "V8-A%d" % (i + 1),
        "skew (put25 - call25) = %s points, smile stated, default direction up, X 5: %s" % (t, w),
        tags=["default-direction"] + (["q-high"] if "q" in kw else []))
for i, (t, w) in enumerate([("-8", "fires"), ("-5.3", "fires"), ("-4.7", "no"), ("8", "positive: no fire")]):
    add(skew_spec(t), "V8-B%d" % (i + 1), "direction down, X 5, skew %s points: %s" % (t, w), direction="down", thr="5")
for i, (t, w) in enumerate([("8", "fires"), ("-8", "fires"), ("4.7", "no"), ("-4.7", "no")]):
    add(skew_spec(t, q="0.10") if i < 2 else skew_spec(t), "V8-C%d" % (i + 1),
        "direction either, X 5, skew %s points: %s" % (t, w), direction="either", thr="5")
for i, (t, d) in enumerate([("5", "up"), ("-5", "down"), ("5", "either"), ("-5", "either")]):
    add(skew_spec(t, c="1.5"), "V8-D%d" % (i + 1),
        "skew exactly %s points (inclusive R-35), quotes 8 decimals, near threshold" % t,
        direction=d, thr="5", dp=8, tags=["boundary-exact"])


def lim(ks, **kw):
    e = ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.5", c="1.5", strikes=ks, **kw)
    return spec_of([e])


# each side missing: strikes limited so the 25-delta target is not bracketed (no extrapolation, R-16)
add(lim(["990", "1005", "1020", "1035", "1050", "1065", "1080"]), "V8-E1",
    "put side has one strike below the ATM strike only: no_delta_bracket", tags=["side-missing"])
add(lim(["930", "945", "960", "975", "990", "1005", "1020"]), "V8-E2",
    "call side has one strike above the ATM strike only: no_delta_bracket", tags=["side-missing"])
add(lim(["990", "1005", "1020", "1035"]), "V8-E3", "both sides short of the 25-delta target: no_delta_bracket",
    tags=["side-missing"])
add(lim(["1005", "1020", "1035", "1050", "1065", "1080"]), "V8-E4", "no strike below ATM at all: no_delta_bracket",
    tags=["side-missing"])
add(lim(["990", "1005", "1020"]), "V8-F1", "3 listed strikes: below min_strikes 4: low_surface_coverage (R-20)",
    tags=["coverage"])
add(lim(["975", "1005", "1035"]), "V8-F2", "3 listed strikes (wider): low_surface_coverage", tags=["coverage"])


def bk(b20, b45, a20="0.18", a45="0.24", c20="1.5", c45="1.5"):
    return spec_of([ex(20, "1000", "0.03", "0.01", atm=a20, b=b20, c=c20),
                    ex(45, "1000", "0.03", "0.01", atm=a45, b=b45, c=c45)])


add(bk("-0.9", "-0.5"), "V8-G1",
    "30d from per-side 25-delta IVs of the 20d and 45d expiries by linear total variance, then put minus call",
    tags=["tenor-interp"])
add(bk("-1.4", "-1.0", "0.17", "0.26"), "V8-G2", "as G1, steeper skews, large IV gap between expiries",
    direction="up", thr="5", tags=["tenor-interp"])
add(bk("0.1", "0.3", "0.20", "0.22"), "V8-G3", "as G1, call side above put side, direction down",
    direction="down", thr="3", tags=["tenor-interp"])


def spike(put=None, call=None):
    over = {}
    if put:
        over[D("945")] = D(put)
    if call:
        over[D("1065")] = D(call)
    return spec_of([ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.5", c="1.5", over=over)])


add(spike(put="0.5"), "V8-H1",
    "put delta at 945 rises to 0.32 again beyond the first crossing (975 to 960): first crossing is used",
    tags=["non-monotone"])
add(spike(call="0.8"), "V8-H2",
    "call delta at 1065 rises to 0.44 beyond the first crossing (1035 to 1050): first crossing is used",
    direction="either", thr="2", tags=["non-monotone"])
add(spike(put="0.5", call="0.8"), "V8-H3", "both sides non-monotone", direction="either", thr="2",
    tags=["non-monotone"])


def moded(mods, over):
    return spec_of([ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.5", c="1.5", mods=mods, over=over)])


add(moded({(D("975"), "put"): "excl"}, {D("975"): D("0.28")}), "V8-I1",
    "put at 975 has condition late_report (excluded_condition): bracket widens to 990/960; the excluded contract carries a deviant IV (0.28) so that using it would show", tags=["excluded"])
add(moded({(D("1035"), "call"): "cross"}, {D("1035"): D("0.26")}), "V8-I2",
    "call at 1035 crossed (crossed_market): bracket widens to 1020/1050; the crossed contract carries a deviant IV", tags=["crossed"])
add(moded({(D("960"), "put"): "stale", (D("1050"), "call"): "excl"}, {D("960"): D("0.30"), D("1050"): D("0.26")}), "V8-I3",
    "put at 960 stale (20 s old), call at 1050 excluded: both sides use wider brackets", tags=["stale", "excluded"])
add(skew_spec("6", style="american"), "V8-J1",
    "American-style chain, OTM contracts and nearest-to-forward legs only: label approximate",
    pending="D-02", extra=["R-11"], tags=["american"])
add(skew_spec("3", style="american"), "V8-J2", "American-style chain, skew 3 points: no fire",
    pending="D-02", extra=["R-11"], tags=["american"])
add(skew_spec("6"), "V8-J3", "delayed tag: computed and labelled delayed", tag="delayed", extra=["R-58"])
add(skew_spec("6", shift=True), "V8-J4", "grid shifted so S and F pick different ATM strikes (scan start differs)",
    tags=["shift"])
add(skew_spec("-6", shift=True, q="0.10"), "V8-J5", "shifted grid, q 0.10, put-side below call-side",
    direction="either", thr="5", tags=["shift", "q-high"])
for i, (a20, a45, b20, b45) in enumerate([("0.15", "0.30", "-1.2", "-0.6"), ("0.30", "0.18", "-0.7", "-1.5"),
                                          ("0.16", "0.28", "-0.4", "-0.4")]):
    add(bk(b20, b45, a20, a45), "V8-K%d" % (i + 1),
        "20d (%s) and 45d (%s): large total-variance gap, per-side interpolation then difference" % (a20, a45),
        direction="either", thr="3", tags=["tenor-interp"])
for i, (r, q, t) in enumerate([("0.0", "0.0", "7"), ("-0.01", "0.03", "6"), ("0.05", "0.10", "-6")]):
    add(skew_spec(t, r=r, q=q), "V8-L%d" % (i + 1), "r=%s q=%s, skew %s points" % (r, q, t),
        direction="either", thr="5", tags=["carry"])
for i, t in enumerate(["9", "-9"]):
    add(skew_spec(t, n=7), "V8-N%d" % (i + 1), "15-strike grid (n=7), skew %s points" % t, direction="either", thr="5")


def putmiss(days, atm, b):
    e = ex(days, "1000", "0.03", "0.01", atm=atm, b=b, c="1.5", n=1)
    F = fwd(D(1000), D("0.03"), D("0.01"), days)
    st = [D(k) for k in sorted(e["strikes"])]
    k0 = min(st, key=lambda k: abs(k - F))
    step = st[1] - st[0]
    ks = [k0 + step * j for j in range(-1, 6)]
    return ex(days, "1000", "0.03", "0.01", atm=atm, b=b, c="1.5", strikes=ks)


add(spec_of([ex(20, "1000", "0.03", "0.01", atm="0.18", b="-0.8", c="1.5"), putmiss(45, "0.24", "-0.5")]), "V8-O1",
    "bracketing 45d expiry has no put-side 25-delta bracket: no_delta_bracket (R-117, R-139)",
    pending="D-08", tags=["bracket-expiry"])
for i, d in enumerate(["up", "either"]):
    add(spec_of([ex(20, "1000", "0.03", "0.01", atm="0.15", b="-1.5", c="1.5"),
                 ex(30, "1000", "0.03", "0.01", atm="0.22", b="-0.7", c="1.5"),
                 ex(45, "1000", "0.03", "0.01", atm="0.30", b="-0.2", c="1.5")]), "V8-P%d" % (i + 1),
        "exact 30-day expiry used as is; 20d and 45d expiries are decoys", direction=d, thr="2", tags=["exact-expiry"])

def _mx(a20, a45, b20="-0.9", b45="-0.5", c="1.5", s20="american", s45="european"):
    return spec_of([ex(20, "1000", "0.03", "0.01", atm=a20, b=b20, c=c, style=s20), ex(45, "1000", "0.03", "0.01", atm=a45, b=b45, c=c, style=s45)])

for i, (s20, s45) in enumerate([("american", "european"), ("european", "american")]):
    add(_mx("0.18", "0.24", s20=s20, s45=s45), "V8-X%d" % (i + 1), "mixed frame: 20d %s and 45d %s both feed the 30d per-side IVs: both labels, sorted" % (s20, s45), direction="either", thr="3", extra=["PO batch 2"], tags=["mixed-style"])
add(spec_of([ex(20, "1000", "0.03", "0.01", atm="0.18", b="-0.8", c="1.5", n=1), ex(45, "1000", "0.03", "0.01", atm="0.24", b="-0.5", c="1.5")]), "V8-N3",
    "bracketing 20d expiry fails coverage (3 strikes): no_bracketing_expiry (PO round 1 D4)", tags=["bracket-coverage"])
FW = dict(delta_convention="forward")
add(skew_spec("8", q="0.10", conv="forward"), "V8-Cv1", "forward delta convention (N(d1), no e^{-qT}), q 0.10, skew 8 points, default direction up: fires; result echoes forward", tags=["forward"], **FW)
add(skew_spec("4.7", q="0.10", conv="forward"), "V8-Cv2", "forward delta, skew 4.7 points: no fire", tags=["forward"], **FW)
add(skew_spec("6", conv="forward"), "V8-Cv3", "forward delta, q 0.01, skew 6, either", direction="either", thr="5", tags=["forward"], **FW)
add(skew_spec("6", q="0.10"), "V8-Cv4", "explicit spot convention, q 0.10, skew 6: echoes spot", tags=["spot"], delta_convention="spot")
_bkf = spec_of([ex(20, "1000", "0.03", "0.10", atm="0.18", b="-0.9", c="1.5"), ex(45, "1000", "0.03", "0.10", atm="0.24", b="-0.5", c="1.5")], q="0.10")
add(_bkf, "V8-Cv5", "forward delta, 30d from 20d and 45d expiries, q 0.10", direction="either", thr="3", tags=["forward", "tenor-interp"], **FW)
add(skew_spec("-6", r="0.05", q="0.10", conv="forward"), "V8-Cv6", "forward delta, r 0.05, q 0.10, put-side below call-side", direction="either", thr="5", tags=["forward"], **FW)
add(skew_spec("8", q="0.10", conv="forward"), "V8-Cv7", "the chain of Cv1 read with the DEFAULT (spot) convention: a different skew value", tags=["spot", "default"])
add(skew_spec("6"), "V8-Cv8", "delta_convention 'Forward': convention_not_allowed (case matters)", tags=["selector"], delta_convention="Forward")
add(skew_spec("6"), "V8-Cv9", "delta_convention 1 (non-string): malformed_type", tags=["selector"], delta_convention=1)
add(skew_spec("6"), "V8-Cv10", "delta_convention null: malformed_type", tags=["selector"], delta_convention=None)
# R-173: two more forward-delta rows: V8-Cv11, Cv12 (forward-delta rows now 12: Cv1-Cv12 less none)
add(skew_spec("-7", q="0.05", r="0.0", conv="forward"), "V8-Cv11", "forward delta, r 0, q 0.05, put-side below call-side, direction down X 5: fires", direction="down", thr="5", tags=["forward"], extra=["R-173"], **FW)
add(skew_spec("6", q="0.10", conv="forward", shift=True, n=7), "V8-Cv12", "forward delta, shifted 15-strike grid, q 0.10, skew 6 points, either X 5: fires", direction="either", thr="5", tags=["forward", "shift"], extra=["R-173"], **FW)
assert len(rows) == 63, len(rows)
if __name__ == "__main__":
    write_dataset("V8", rows, outdir_arg(), "gen_m3a_v8.py",
                  "V8 rows: skew = (put25_30 - call25_30); put25 and call25 from per-expiry 25-delta (spot delta at own IV, linear IV in delta between bracketing eligible strikes, first crossing outward from the ATM strike), per-side constant maturity by linear total variance.")
