"""V7 (M3A-6) fixture generator: 30d-91d gap change versus the n-th prior session close (SYNTHETIC)."""
from decimal import Decimal as D
from m3a_oracle3 import CUT, Surf, spec_of, ex, request, r8, fs
from m3a_rowkit3 import make_row, write_dataset, outdir_arg, store_rec
import gen_m3a_g5 as g5

R = ["R-30", "R-33", "R-82", "R-40", "R-84", "R-35", "R-36", "R-92", "R-95"]
rows = []


def E(days, atm, n=2, r="0.03", q="0.01", **kw):
    return ex(days, "1000", r, q, atm=fs(atm), n=n, **kw)


def base(i30="0.22", i91="0.24", **kw):
    return spec_of([E(30, D(i30), **kw), E(91, D(i91), **kw)])


def gap_now(spec):
    sf = Surf(spec)
    return r8(sf.cm(91, "atm_iv") - sf.cm(30, "atm_iv"))


def prior_int(spec, change_pts):
    return g5.int8(gap_now(spec) - D(change_pts) / 100)


def add(spec, store, rid, why, direction=None, thr=None, n=None, dp=4, pending=None, tags=(), extra=(), **kw):
    rq = request(direction=direction, threshold=thr, tenors=[30, 91], **kw)
    if n is not None:
        rq["prior_sessions"] = n
    rows.append(make_row("V7", rid, "V7; R-30 R-33 R-82", R + list(extra), spec, rq, store=store, derivation=why,
                         dp=dp, pending=pending, tags=tags))


sp = base()
for i, (c, w) in enumerate([("3", "fires"), ("-3", "fires (either)"), ("1.8", "no"), ("-1.8", "no"), ("0", "no")]):
    s = base(shift=True) if i == 0 else sp
    add(s, store_rec([prior_int(s, c)]), "V7-A%d" % (i + 1), "gap change %s points vs the prior session close, default direction either, X 2: %s" % (c, w),
        tags=["default-direction"] + (["shift"] if i == 0 else []))
for d, cs in (("up", [("3", "fires"), ("-3", "no fire"), ("1.8", "no fire")]), ("down", [("-3", "fires"), ("3", "no fire"), ("-1.8", "no fire")])):
    for i, (c, w) in enumerate(cs):
        add(sp, store_rec([prior_int(sp, c)]), "V7-B%s%d" % (d[0], i + 1), "direction %s, X 2, change %s: %s" % (d, c, w), direction=d, thr="2")
for i, (c, d) in enumerate([("2", "either"), ("-2", "either"), ("2", "up"), ("-2", "down")]):
    add(sp, store_rec([prior_int(sp, c)]), "V7-C%d" % (i + 1), "change exactly %s points (inclusive, R-35), quotes 8 decimals, near threshold" % c,
        direction=d, thr="2", dp=8, tags=["boundary-exact"])
# n-th prior session: the 3rd (or 2nd) is used; decoys differ so that using the 1st would give the other answer
for i, (n, cs, d, w) in enumerate([(3, ("0", "0", "3"), "either", "3rd prior shows +3: fires; 1st would not"),
                                   (3, ("3", "3", "0"), "either", "3rd prior shows 0: no fire; 1st would fire"),
                                   (3, ("0", "0", "-3"), "down", "3rd prior -3: fires with down"),
                                   (2, ("0", "3", "0"), "either", "2nd prior +3: fires; 1st would not"),
                                   (2, ("3", "0", "3"), "either", "2nd prior 0: no fire; 1st would fire")]):
    vals = [prior_int(sp, c) for c in cs] + [prior_int(sp, "5"), prior_int(sp, "-5")]
    add(sp, store_rec(vals), "V7-D%d" % (i + 1), "prior_sessions=%d, 5 stored priors, priors list carries %d entries: %s" % (n, n, w),
        direction=d, thr="2", n=n, tags=["n-th-prior"])
add(sp, [], "V7-E1", "no stored prior: unavailable no_prior_reading")
add(sp, [], "V7-E2", "no stored prior, n=3: no_prior_reading", n=3)
for i, (n, vals) in enumerate([(3, [20000000, 21000000]), (3, [20000000])]):
    add(sp, store_rec(vals), "V7-F%d" % (i + 1), "fewer stored priors than n=3: unavailable insufficient_history (PO batch 2, D-07)",
        n=n, pending="D-07", tags=["n-th-prior"])
ok = store_rec([prior_int(sp, "3")])
bad = [dict(ok[0], time_ns=CUT)]
add(sp, bad, "V7-G1", "n-th (1st) prior session time == cutoff: structural prior_not_before_cutoff (R-92)")
add(sp, [dict(ok[0], time_ns=CUT + 10 ** 9)], "V7-G2", "prior session time after the cutoff: structural")
st3 = store_rec([prior_int(sp, "0"), prior_int(sp, "0"), prior_int(sp, "3")])
st3[2] = dict(st3[2], time_ns=CUT)
add(sp, st3, "V7-G3", "n=3: the 3rd prior time == cutoff: structural prior_not_before_cutoff", n=3, tags=["n-th-prior"])
add(sp, [dict(ok[0], time_ns=CUT - 1)], "V7-G4", "prior time 1 ns before cutoff: valid, fires")
# tenors by bracketing expiries
for i, c in enumerate(["3", "1.5"]):
    s = spec_of([E(20, D("0.19")), E(45, D("0.25")), E(120, D("0.31"))])
    add(s, store_rec([prior_int(s, c)]), "V7-H%d" % (i + 1), "30d from 20d/45d and 91d from 45d/120d by linear total variance, change %s" % c, tags=["tenor-interp"])
add(spec_of([E(30, D("0.22"))]), store_rec([20000000]), "V7-I1", "no 91-day bracket: no_bracketing_expiry")
add(spec_of([E(45, D("0.22")), E(120, D("0.25"))]), store_rec([20000000]), "V7-I2", "no 30-day bracket: no_bracketing_expiry")
s = base(style="american")
add(s, store_rec([prior_int(s, "3")]), "V7-J1", "American-style chain: label approximate", pending="D-02", extra=["R-11"], tags=["american"])
add(sp, store_rec([prior_int(sp, "3")]), "V7-J2", "delayed tag: computed, labelled delayed", tag="delayed", extra=["R-58"])
s = spec_of([E(30, D("0.22"), r="0.02", q="0.02", base="992.5"), E(91, D("0.245"), r="0.02", q="0.02", base="992.5")], r="0.02", q="0.02")
add(s, store_rec([prior_int(s, "3")]), "V7-K1", "tie grid r=q: ATM is the lower strike", tags=["tie"])
s = base("0.21", "0.25", shift=True)
add(s, store_rec([prior_int(s, "-3")]), "V7-K2", "shifted grid: S and F pick different strikes", tags=["shift"])
add(spec_of([E(30, D("0.22"))]), [], "V7-M1", "two conditions: no 91-day bracket and no stored prior: upstream reason first (no_bracketing_expiry), PO batch 2 D-09")
add(spec_of([E(45, D("0.22")), E(120, D("0.25"))]), [], "V7-M2", "two conditions: no 30-day bracket and no stored prior: no_bracketing_expiry first, D-09")
_bad_store = store_rec([prior_int(sp, "3")])
_bad_store[0] = dict(_bad_store[0], time_ns=CUT)
add(spec_of([E(30, D("0.22"))]), _bad_store, "V7-P01", "two conditions: prior time == cutoff and no 91-day bracket: structural code first (A2)")
_st2 = store_rec([prior_int(sp, "3"), prior_int(sp, "0")])
_st2[1] = dict(_st2[1], time_ns=CUT + 10 ** 9)
add(sp, _st2, "V7-P02", "n=1, the SECOND stored prior time after the cutoff (not the n-th): any supplied prior at or after the cutoff is structural (A4)")
add(sp, store_rec([prior_int(sp, "3")]), "V7-Cx1", "delta_convention 5 (non-string, not a valid value) supplied to V7: ignored, NOT malformed_type and NOT convention_not_allowed (R-149, R-155, R-174); result as without it",
    delta_convention=5, extra=["R-174", "R-149", "R-155"], tags=["convention-ignored", "bad-value"])
assert len(rows) == 41, len(rows)
if __name__ == "__main__":
    write_dataset("V7", rows, outdir_arg(), "gen_m3a_v7.py",
                  "V7 rows: gap = rounded-once (iv91 - iv30); priors_store = stored session-close gaps, integers in 1e-8 units, most recent first; no slope key (R-30).")
