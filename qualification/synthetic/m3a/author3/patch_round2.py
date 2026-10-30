"""patch for owner decision 2 (V4 iv_form selector, ATM form); kept for traceability."""
import re


def sub(f, a, b, cnt=1):
    s = open(f, newline="").read()
    if b in s and a not in s:
        return
    assert a in s, (f, a[:70])
    open(f, "w", newline="\n").write(s.replace(a, b, cnt))


O = "m3a_oracle3.py"
sub(O, '''def ev_v4(sf, req, prior):
    if prior is not None and prior["time_ns"] >= CUT:
        return _inv(sf, "prior_not_before_cutoff", req)
    if req["feed_delay_tag"] == "delayed" and req["mode"] == "intraday":
        return _inv(sf, "delayed_feed_tag", req)
    now = sf.cm(30, "atm_iv")
    if isinstance(now, str):
        return _bad(sf, now, req)
''', '''def ev_v4(sf, req, prior):
    form = req["iv_form"]
    if not isinstance(form, str):
        return _inv(sf, "malformed_type", req)
    if form not in ("atm", "30d"):
        return _inv(sf, "iv_form_not_allowed", req)
    if prior is not None and prior["time_ns"] >= CUT:
        return _inv(sf, "prior_not_before_cutoff", req)
    if req["feed_delay_tag"] == "delayed" and req["mode"] == "intraday":
        return _inv(sf, "delayed_feed_tag", req)
    if form == "30d":
        now = sf.cm(30, "atm_iv")
    else:
        el = [d for d in sf.days if sf.exps[d]["cov_ok"]]
        now = sf.exps[el[0]]["atm_iv"] if el else "low_surface_coverage"
    if isinstance(now, str):
        return _bad(sf, now, req)
''')
sub(O, '''"change_ratio": fs(r8(ratio)), "prior_kind": prior["kind"]}''',
    '''"change_ratio": fs(r8(ratio)), "prior_kind": prior["kind"], "iv_form": form}''')

R = "m3a_ref3.py"
sub(R, '''    if fam == "V4":
        if prior is not None''', '''    if fam == "V4":
        form = req.get("iv_form", "30d" if "M43" in mut else "atm")
        if "M44" in mut and isinstance(form, str):
            form = "30d"
        if not isinstance(form, str):
            return out(ch, req, "invalid_input", code="malformed_type")
        if form not in ("atm", "30d"):
            return out(ch, req, "invalid_input", code="iv_form_not_allowed")
        if prior is not None''')
sub(R, '''        now = cm_value(ch, 30, lambda d: (ch.atm(d) or (None, None))[1], "atm")
        if isinstance(now, str):
            return out(ch, req, "unavailable", now)
        now_r = r8(now)''', '''        if form == "30d":
            now = cm_value(ch, 30, lambda d: (ch.atm(d) or (None, None))[1], "atm")
        else:
            el = sorted(ch.ex) if "M42" in mut else [d for d in sorted(ch.ex) if ch.cov_ok(d)]
            if not el:
                now = "low_surface_coverage"
            else:
                a_ = ch.atm(el[0])
                now = "no_atm_strike" if a_ is None else a_[1]
        if isinstance(now, str):
            return out(ch, req, "unavailable", now)
        now_r = r8(now)''')
sub(R, '''"change_ratio": r8(ratio),
                                   "prior_kind": prior["kind"]}''', '''"change_ratio": r8(ratio),
                                   "prior_kind": prior["kind"], "iv_form": form}''')

K = "m3a_rowkit3.py"
sub(K, '"V4": {"direction": "up", "threshold": "10"},', '"V4": {"direction": "up", "threshold": "10", "iv_form": "atm"},')
sub(K, '"V4": ["now", "prior", "change_points", "change_ratio", "prior_kind"]',
    '"V4": ["now", "prior", "change_points", "change_ratio", "prior_kind", "iv_form"]')
sub(K, '"delta_target", "tenors", "min_strikes"', '"delta_target", "iv_form", "tenors", "min_strikes"')
sub(K, '"inputs": {"series_id": SERIES.get(fam),', '"inputs": {"series_id": ("XYZ/stock/" + ("iv30" if req.get("iv_form") == "30d" else "atm_iv") if fam == "V4" else SERIES.get(fam)),')

C = "selfcheck_m3a3.py"
sub(C, 'elif isinstance(wv, str) and key == "prior_kind":', 'elif isinstance(wv, str) and key in ("prior_kind", "iv_form"):')

R2 = "run_mutants_m3a3.py"
sub(R2, '    "M48":', '''    "M42": "V4 ATM form uses the nearest LISTED expiry (coverage ignored)",
    "M43": "V4 iv_form default 30d instead of atm",
    "M44": "V4 iv_form selector ignored (always 30d)",
    "M48":''')

G = "gen_m3a_v4.py"
s = open(G, newline="").read()
s = s.replace("tenors=[30]", 'iv_form="30d", tenors=[30]')
s = s.replace('assert len(rows) == 46', '''# ------------------------------------------------------------------ ATM form and selector (owner decision 2)
RA = R + ["OD-2", "R-81"]


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
         "V4-A-%02d" % (15 + i), "ATM form, mixed frame: 10d %s and 30d %s: both labels, sorted" % (s10, s30_), tags=["mixed-style"])
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
assert len(rows) == 74''')
open(G, "w", newline="\n").write(s)
