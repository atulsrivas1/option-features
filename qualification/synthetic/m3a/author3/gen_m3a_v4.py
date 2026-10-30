"""V4 (M3A-3) fixture generator: constant 30-day IV change from a prior reading (SYNTHETIC)."""
from decimal import Decimal as D
from m3a_oracle3 import (CUT, Surf, spec_of, ex, request, r8, fs)
from m3a_rowkit3 import make_row, write_dataset, outdir_arg
import gen_m3a_g5 as g5

R = ["R-41", "R-151", "R-152", "R-153", "R-154", "R-84", "R-35", "R-36", "R-49"]
rows = []


def s30(atm, **kw):
    r = kw.pop("r", "0.03"); q = kw.pop("q", "0.01")
    return spec_of([ex(30, "1000", r, q, atm=atm, n=2, **kw)], r=r, q=q)


def now_of(spec):
    v = Surf(spec).cm(30, "atm_iv")
    return D(0) if isinstance(v, str) else r8(v)


def add(spec, pct, rid, why, kind="frame", prior_override="unset", req=None, extra=(), **kw):
    now = now_of(spec)
    pv = g5.prior_for_ratio(fs(now), pct) if prior_override == "unset" else prior_override
    if kind == "frame":
        pr = g5.frame_prior(pv) if pv is not None else None
    else:
        pr = g5.session_prior(pv) if pv is not None else None
    rq = req if req is not None else request(iv_form="30d", tenors=[30])
    rows.append(make_row("V4", rid, "V4; OC 30-day IV (M1 iv_30d)", R + list(extra), spec, rq, prior=pr,
                         derivation=why, **kw))


lv = ["0.22", "0.25", "0.30", "0.18", "0.27", "0.21", "0.35"]
# A: default direction (up) and default threshold (10), omitted from the request
A = [("25", "up fires"), ("12", "up fires"), ("10.4", "just beyond threshold fires"), ("9.6", "just below no fire"),
     ("5", "no fire"), ("-12", "down move, default direction up: no fire"), ("-25", "down move, default up: no fire")]
for i, (p, w) in enumerate(A):
    kw = {"shift": True} if i in (0, 3, 5) else {}
    add(s30(lv[i], **kw), p, "V4-A%02d" % (i + 1),
        "now=ATM IV %s at the strike nearest F; prior=now/(1+%s%%); default direction up, X 10: %s%s" % (lv[i], p, w, "; grid shifted so S and F pick different strikes" if kw else ""),
        tags=["default-direction", "shift"] if kw else ["default-direction"])
# B: down
for i, (p, w) in enumerate([("-25", "fires"), ("-12", "fires"), ("-10.4", "fires"), ("-9.6", "no fire"), ("12", "up move no fire")]):
    add(s30(lv[i + 1]), p, "V4-B%02d" % (i + 1), "direction down, X 10: %s" % w,
        req=request(iv_form="30d", tenors=[30], direction="down", threshold="10"))
# C: either (two on the r=q tie grid: forward exactly between 992.5 and 1007.5, tie to the lower strike)
for i, (p, w, tie) in enumerate([("12", "fires", True), ("-12", "fires", True), ("9.6", "no", False), ("-9.6", "no", False)]):
    kw = dict(r="0.02", q="0.02", base="992.5") if tie else {}
    add(s30(lv[i], **kw), p, "V4-C%02d" % (i + 1), "direction either, X 10: %s%s" % (w, "; tie grid r=q, ATM is the lower strike 992.5" if tie else ""),
        req=request(iv_form="30d", tenors=[30], direction="either", threshold="10"), tags=["tie"] if tie else [])
# D: exact threshold on the rounded decimals (quotes with 8 decimals); fire not asserted for an implementation (near threshold)
for i, (now, pv, d, w) in enumerate([("0.22", "0.2", "up", "+10 percent exactly, inclusive: fires"),
                                     ("0.18", "0.2", "down", "-10 percent exactly, inclusive: fires"),
                                     ("0.22", "0.2", "either", "+10 percent exactly: fires"),
                                     ("0.18", "0.2", "either", "-10 percent exactly: fires")]):
    add(s30(now), None, "V4-D%02d" % (i + 1), w + " (R-35)", prior_override=pv, dp=8,
        req=request(iv_form="30d", tenors=[30], direction=d, threshold="10"), tags=["boundary-exact"])
# E: prior kind session
for i, (p, d, w) in enumerate([("15", "up", "fires"), ("5", "up", "no fire"), ("-15", "down", "fires")]):
    add(s30(lv[i + 2]), p, "V4-E%02d" % (i + 1), "prior kind session (stored close): %s" % w, kind="session",
        req=request(iv_form="30d", tenors=[30], direction=d, threshold="10"))
# F: zero prior
add(s30("0.22"), None, "V4-F01", "prior 0 gives zero_denominator (R-41)", prior_override="0.00000000")
add(s30("0.24"), None, "V4-F02", "session prior 0 gives zero_denominator", kind="session", prior_override="0")
# G: no prior
add(s30("0.22"), None, "V4-G01", "no prior reading: unavailable no_prior_reading", prior_override=None)
add(s30("0.26", shift=True), None, "V4-G02", "no prior reading (shifted grid)", prior_override=None,
    req=request(iv_form="30d", tenors=[30], direction="either", threshold="10"))
# H: prior reading time at or after the cutoff
sp = s30("0.22")
now = now_of(sp)
pv = g5.prior_for_ratio(fs(now), "15")
for rid, pr, w in [("V4-H01", g5.at_cutoff("frame", pv), "frame prior time == cutoff: structural prior_not_before_cutoff (R-92)"),
                   ("V4-H02", g5.after_cutoff("frame", pv), "frame prior time after cutoff: structural"),
                   ("V4-H03", g5.at_cutoff("session", pv), "session prior time == cutoff: structural"),
                   ("V4-H04", dict(g5.frame_prior(pv), time_ns=CUT - 1), "frame prior 1 ns before cutoff: valid, fires")]:
    rows.append(make_row("V4", rid, "V4; R-92", R + ["R-92"], sp, request(iv_form="30d", tenors=[30]), prior=pr, derivation=w))
# I: delayed feed
add(s30("0.22"), "12", "V4-I01", "intraday under a delayed tag: invalid_input delayed_feed_tag (R-58)",
    req=request(iv_form="30d", tenors=[30], tag="delayed"), extra=["R-58"])
add(s30("0.22"), "12", "V4-I02", "close mode delayed: computed and labelled delayed",
    req=request(mode="close", tag="delayed", iv_form="30d", tenors=[30]), extra=["R-58"])
add(s30("0.25"), "5", "V4-I03", "intraday under a delayed tag with a session-kind prior: invalid_input delayed_feed_tag",
    kind="session", req=request(iv_form="30d", tenors=[30], tag="delayed"), extra=["R-58"])
# J: 30 days from bracketing expiries (linear total variance)
for i, (p, w) in enumerate([("14", "fires"), ("6", "no fire")]):
    spec = spec_of([ex(20, "1000", "0.03", "0.01", atm="0.20", n=2), ex(45, "1000", "0.03", "0.01", atm="0.28", n=2)])
    add(spec, p, "V4-J%02d" % (i + 1), "30d from 20d (0.20) and 45d (0.28), linear total variance: %s" % w, tags=["tenor-interp"])
# K: no bracketing expiry
add(spec_of([ex(45, "1000", "0.03", "0.01", atm="0.28", n=2), ex(60, "1000", "0.03", "0.01", atm="0.29", n=2)]),
    "10", "V4-K01", "both listed expiries longer than 30 days: no_bracketing_expiry, no extrapolation (R-16)",
    prior_override="0.2")
add(spec_of([ex(10, "1000", "0.03", "0.01", atm="0.20", n=2), ex(20, "1000", "0.03", "0.01", atm="0.21", n=2)]),
    "10", "V4-K02", "both listed expiries shorter than 30 days: no_bracketing_expiry", prior_override="0.2")
# L: American chain (labels); PENDING-RULING D-02 coverage definition for American chains
for i, p in enumerate(["15", "5"]):
    add(s30("0.24", style="american"), p, "V4-L%02d" % (i + 1),
        "American-style chain, European model on the nearest-to-forward legs: label approximate (R-11)",
        pending="D-02", extra=["R-11"], tags=["american"])

add(spec_of([ex(45, "1000", "0.03", "0.01", atm="0.28", n=2), ex(60, "1000", "0.03", "0.01", atm="0.29", n=2)]), None, "V4-M01",
    "two conditions: no 30-day bracket and no prior: upstream reason first (no_bracketing_expiry), PO batch 2 D-09", prior_override=None)
add(spec_of([ex(30, "1000", "0.03", "0.01", atm="0.22", n=1)]), None, "V4-M02",
    "two conditions: 3 strikes (low_surface_coverage) and no prior: upstream reason first, PO batch 2 D-09", prior_override=None)
for i, (s20, s45, p) in enumerate([("american", "european", "14"), ("european", "american", "6")]):
    sp_ = spec_of([ex(20, "1000", "0.03", "0.01", atm="0.20", n=2, style=s20), ex(45, "1000", "0.03", "0.01", atm="0.28", n=2, style=s45)])
    add(sp_, p, "V4-X%02d" % (i + 1), "mixed frame: 20d %s and 45d %s both feed the 30d IV: both labels, sorted" % (s20, s45), extra=["PO batch 2"], tags=["mixed-style"])
def _cov_bk():
    return spec_of([ex(20, "1000", "0.03", "0.01", atm="0.20", n=1), ex(45, "1000", "0.03", "0.01", atm="0.28", n=2)])


add(_cov_bk(), "12", "V4-N01", "bracketing 20d expiry fails coverage (3 strikes): the tenor has no usable bracket: no_bracketing_expiry (PO round 1 D4)")
rows.append(make_row("V4", "V4-P01", "V4; R-92", R + ["R-92"], spec_of([ex(45, "1000", "0.03", "0.01", atm="0.28", n=2), ex(60, "1000", "0.03", "0.01", atm="0.29", n=2)]),
                     request(iv_form="30d", tenors=[30]), prior=g5.at_cutoff("frame", "0.2"),
                     derivation="two conditions: prior time == cutoff and no 30-day bracket: the structural code comes first (A2)"))
# ------------------------------------------------------------------ ATM form and selector (owner decision 2)
RA = R + ["OD-2", "R-151", "R-152", "R-153", "R-154"]


def a_now(spec):
    sf = Surf(spec)
    el = [d for d in sf.days if sf.exps[d]["cov_ok"]]
    v = sf.exps[el[0]]["atm_iv"] if el else "x"
    return D(0) if isinstance(v, str) else r8(v)


def addA(spec, pct, rid, why, kind="frame", prior_override="unset", req=None, dp=4, tags=(), omit_form=True):
    now = a_now(spec)
    pv = g5.prior_for_ratio(fs(now), pct) if prior_override == "unset" else prior_override
    if kind == "frame":
        pr = g5.frame_prior(pv) if isinstance(pv, str) else pv
    else:
        pr = g5.session_prior(pv) if isinstance(pv, str) else pv
    rq = req if req is not None else request()
    rows.append(make_row("V4", rid, "V4 ATM form; OD-2 (M1 atm_iv of the nearest eligible expiry)", RA, spec, rq, prior=pr,
                         derivation=why, dp=dp, tags=["atm-form"] + list(tags)))


def sa(a1, a2="0.27", **kw):
    r = kw.pop("r", "0.03"); q = kw.pop("q", "0.01")
    return spec_of([ex(10, "1000", r, q, atm=a1, n=2, **kw), ex(30, "1000", r, q, atm=a2, n=2, **kw)], r=r, q=q)


addA(sa("0.22", shift=True), "25", "V4-A-01", "ATM form (default selector): ATM IV 0.22 of the nearest eligible expiry (10d), +25 percent, default up: fires; grid shifted")
addA(sa("0.25"), "9.6", "V4-A-02", "ATM form default: +9.6 percent: no fire")
addA(sa("0.21"), "-12", "V4-A-03", "ATM form default: -12 percent with default direction up: no fire")
addA(sa("0.24"), "-12", "V4-A-04", "direction down: -12 percent fires", req=request(iv_form="atm", direction="down", threshold="10"))
addA(sa("0.24"), "12", "V4-A-05", "direction down: +12 percent: no fire", req=request(iv_form="atm", direction="down", threshold="10"))
addA(sa("0.23", r="0.02", q="0.02", base="992.5"), "12", "V4-A-06", "tie grid r=q: ATM is the lower strike; either, +12: fires", req=request(iv_form="atm", direction="either", threshold="10"), tags=["tie"])
addA(sa("0.26"), "-9.6", "V4-A-07", "either, -9.6: no fire", req=request(iv_form="atm", direction="either", threshold="10"))
addA(sa("0.22"), None, "V4-A-08", "ATM form, +10 percent exactly (rounded decimals), inclusive: fires; near threshold", prior_override="0.2", dp=8,
     req=request(iv_form="atm", direction="up", threshold="10"), tags=["boundary-exact"])
addA(sa("0.18"), None, "V4-A-09", "ATM form, -10 percent exactly, down: fires; near threshold", prior_override="0.2", dp=8,
     req=request(iv_form="atm", direction="down", threshold="10"), tags=["boundary-exact"])
addA(sa("0.27"), "15", "V4-A-10", "ATM form, session prior, up +15: fires", kind="session", req=request(iv_form="atm", direction="up", threshold="10"))
addA(sa("0.27"), "-15", "V4-A-11", "ATM form, session prior, down -15: fires", kind="session", req=request(iv_form="atm", direction="down", threshold="10"))
addA(sa("0.22"), None, "V4-A-12", "ATM form, prior 0: zero_denominator", prior_override="0.00000000")
addA(sa("0.22"), None, "V4-A-13", "ATM form, no prior reading: no_prior_reading", prior_override=None)
addA(sa("0.22"), None, "V4-A-14", "ATM form, prior time == cutoff: structural prior_not_before_cutoff", prior_override=g5.at_cutoff("frame", "0.2"))
for i, (s10, s30_) in enumerate([("american", "european"), ("european", "american")]):
    addA(spec_of([ex(10, "1000", "0.03", "0.01", atm="0.22", n=2, style=s10), ex(30, "1000", "0.03", "0.01", atm="0.27", n=2, style=s30_)]), "14",
         "V4-A-%02d" % (15 + i), "ATM form, mixed frame: 10d %s and 30d %s: only the nearest eligible expiry (10d) feeds the output, so labels carry its model label only (R-180)" % (s10, s30_), tags=["mixed-style"])
    rows[-1]["rulings"] = rows[-1]["rulings"] + ["R-180"]
_noatm = ex(10, "1000", "0.03", "0.01", atm="0.20", n=3)
_ks = sorted(_noatm["strikes"])
_noatm["mods"] = dict([((K_, "call"), "excl") for K_ in _ks[:4]] + [((K_, "put"), "excl") for K_ in _ks[3:]])
addA(spec_of([_noatm, ex(30, "1000", "0.03", "0.01", atm="0.27", n=2)]), "10", "V4-A-17",
     "nearest eligible expiry (10d) passes coverage but has no strike eligible for both rights: no_atm_strike (no fallback to the next expiry)", prior_override="0.2")
addA(spec_of([ex(7, "1000", "0.03", "0.01", atm="0.30", n=1), ex(21, "1000", "0.03", "0.01", atm="0.22", n=2), ex(50, "1000", "0.03", "0.01", atm="0.27", n=2)]), "14",
     "V4-A-18", "nearest listed expiry (7d, 3 strikes) fails coverage: the nearest ELIGIBLE expiry is the first that passes: 21d", tags=["coverage-skip"])
addA(spec_of([ex(7, "1000", "0.03", "0.01", atm="0.30", n=1), ex(14, "1000", "0.03", "0.01", atm="0.25", n=1), ex(30, "1000", "0.03", "0.01", atm="0.22", n=2)]), "6",
     "V4-A-19", "two nearest expiries fail coverage: the third (30d) is the nearest eligible; +6 percent: no fire", tags=["coverage-skip"])
addA(sa("0.22"), "12", "V4-A-20", "ATM form intraday under a delayed tag: invalid_input delayed_feed_tag", req=request(tag="delayed", iv_form="atm"))
addA(sa("0.22"), "12", "V4-A-21", "ATM form, close mode delayed: computed, labelled delayed", req=request(mode="close", tag="delayed", iv_form="atm"))
# selector validation: the same chain gives different values for atm (10d) and 30d
SEL = sa("0.20", "0.28")
addA(SEL, "20", "V4-S-01", "selector omitted: default atm (ATM IV 0.20 of the 10d expiry), +20 percent: fires; iv_form echoed atm", tags=["selector"])
addA(SEL, "20", "V4-S-02", "iv_form atm explicit", req=request(iv_form="atm"), tags=["selector"])
addA(SEL, "20", "V4-S-03", "iv_form 30d explicit: 30-day IV from the 10d and 30d expiries (here the exact 30d expiry, 0.28); prior from the ATM value 0.20/1.2 is a different series by construction",
     req=request(iv_form="30d", tenors=[30]), tags=["selector"])
for rid, v, w in [("V4-S-04", "ATM", "iv_form_not_allowed (case matters)"), ("V4-S-05", "60d", "iv_form_not_allowed"),
                  ("V4-S-06", 30, "malformed_type (non-string)"), ("V4-S-07", None, "malformed_type (null)")]:
    addA(SEL, "20", rid, "iv_form %r: %s" % (v, w), req=request(iv_form=v), tags=["selector"])
# R-172: selector rows to 3+3 (iv_form_not_allowed: S-04, S-05, S-08; malformed_type: S-06, S-07, S-09)
addA(SEL, "20", "V4-S-08", "iv_form '30D' (upper case): iv_form_not_allowed (case matters)", req=request(iv_form="30D"), tags=["selector"], )
addA(SEL, "20", "V4-S-09", "iv_form ['atm'] (a list, non-string): malformed_type", req=request(iv_form=["atm"]), tags=["selector"])
rows[-2]["rulings"] = rows[-2]["rulings"] + ["R-172"]
rows[-1]["rulings"] = rows[-1]["rulings"] + ["R-172"]
# R-174: V4 takes no delta convention: the key is ignored (not validated, not echoed)
addA(SEL, "20", "V4-Cx1", "delta_convention 'forward' supplied to V4: ignored (R-149, R-155, R-174): same result as V4-S-01, nothing echoed", req=request(iv_form="atm", delta_convention="forward"), tags=["selector", "convention-ignored"])
rows[-1]["rulings"] = rows[-1]["rulings"] + ["R-174", "R-149", "R-155"]
assert len(rows) == 77, len(rows)
if __name__ == "__main__":
    write_dataset("V4", rows, outdir_arg(), "gen_m3a_v4.py",
                  "V4 rows: now = M1-style constant 30-day IV of the stated smile; prior is an input; change_ratio = (now-prior)/prior (fraction), fires on percent.")
