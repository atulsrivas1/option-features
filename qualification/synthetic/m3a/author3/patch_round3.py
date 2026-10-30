"""patch for owner decision 3 (delta_convention spot or forward); kept for traceability."""


def sub(f, a, b, cnt=1):
    s = open(f, newline="").read()
    if b in s and a not in s:
        return
    assert a in s, (f, a[:70])
    open(f, "w", newline="\n").write(s.replace(a, b, cnt))


O = "m3a_oracle3.py"
sub(O, '''def abs_delta(S, K, T, r, q, sg, right):
    d1 = d1_of(S, K, T, r, q, sg)
    e = (-q * T).exp()''', '''def abs_delta(S, K, T, r, q, sg, right, fwd=False):
    d1 = d1_of(S, K, T, r, q, sg)
    e = D(1) if fwd else (-q * T).exp()''')
sub(O, '''    def __init__(self, spec):
        self.spec = spec
''', '''    def __init__(self, spec, conv=None):
        self.spec = spec
        self.conv = conv or spec.get("conv", "spot")
''')
sub(O, "return abs_delta(S, K, T, r, q, sg[K], right)", 'return abs_delta(S, K, T, r, q, sg[K], right, self.conv == "forward")')
sub(O, '''def skew_now(sf):''', '''def _cv(sf, req):
    c = req["delta_convention"]
    if not isinstance(c, str):
        return _inv(sf, "malformed_type", req)
    if c not in ("spot", "forward"):
        return _inv(sf, "convention_not_allowed", req)
    return None


def skew_now(sf):''')
sub(O, '''def ev_v8(sf, req):
    pc = skew_now(sf)''', '''def ev_v8(sf, req):
    bad = _cv(sf, req)
    if bad:
        return bad
    pc = skew_now(sf)''')
sub(O, '''def ev_v11(sf, req):
    a = sf.cm(30, "atm_iv")''', '''def ev_v11(sf, req):
    bad = _cv(sf, req)
    if bad:
        return bad
    a = sf.cm(30, "atm_iv")''')
sub(O, '''def ev_v21(sf, req):
    if "threshold" not in req:''', '''def ev_v21(sf, req):
    bad = _cv(sf, req)
    if bad:
        return bad
    if "threshold" not in req:''')
sub(O, '''    if (prior is not None and prior["time_ns"] >= CUT) or any(s["time_ns"] >= CUT for s in (store or [])):
        return _inv(sf, "prior_not_before_cutoff", req)
    pc = skew_now(sf)''', '''    bad = _cv(sf, req)
    if bad:
        return bad
    recs = ([prior] if prior is not None else []) + list(store or [])
    if any(x.get("delta_convention", "spot") != req["delta_convention"] for x in recs):
        return _inv(sf, "convention_mismatch", req)
    if (prior is not None and prior["time_ns"] >= CUT) or any(s["time_ns"] >= CUT for s in (store or [])):
        return _inv(sf, "prior_not_before_cutoff", req)
    pc = skew_now(sf)''')

K = "m3a_rowkit3.py"
sub(K, '''def evaluate(fam, spec, req, prior=None, store=None):
    sf = Surf(spec)''', '''CONV_FAMS = ("V8", "V10", "V11", "V21")


def evaluate(fam, spec, req, prior=None, store=None):
    cv = req.get("delta_convention", "spot")
    sf = Surf(spec, conv=cv if cv in ("spot", "forward") else "spot")''')
for fam in ("V8", "V10", "V11", "V21"):
    pass
sub(K, '"V8": {"direction": "up", "threshold": "5"},', '"V8": {"direction": "up", "threshold": "5", "delta_convention": "spot"},')
sub(K, '"V10": {"direction": "either", "threshold": "2", "condition": "change", "prior_kind": "frame"},',
    '"V10": {"direction": "either", "threshold": "2", "condition": "change", "prior_kind": "frame", "delta_convention": "spot"},')
sub(K, '"V11": {"direction": "up", "threshold": "3"},', '"V11": {"direction": "up", "threshold": "3", "delta_convention": "spot"},')
sub(K, '"V21": {"direction": "up"},', '"V21": {"direction": "up", "delta_convention": "spot"},')
sub(K, '"V8": ["put25_iv", "call25_iv", "skew_points", "tenor"],', '"V8": ["put25_iv", "call25_iv", "skew_points", "tenor", "delta_convention"],')
sub(K, '"V11": ["wings_mid", "atm_iv", "curvature_points"],', '"V11": ["wings_mid", "atm_iv", "curvature_points", "delta_convention"],')
sub(K, '"V21": ["ratio", "put_distance", "call_distance"],', '"V21": ["ratio", "put_distance", "call_distance", "delta_convention"],')
sub(K, '"V10": ["now", "change_points", "priors.session_id"],', '"V10": ["now", "change_points", "priors.session_id", "delta_convention"],')
sub(K, '"delta_target", "iv_form",', '"delta_target", "delta_convention", "iv_form",')
sub(K, '''    avail = res["status"] == "available"
''', '''    avail = res["status"] == "available"
    if avail and fam in CONV_FAMS:
        res["value"]["delta_convention"] = req["delta_convention"]
''')
sub(K, 'if fam == "V4" else SERIES.get(fam)),', 'if fam == "V4" else ("XYZ/stock/skew25_fwd" if (fam == "V10" and req.get("delta_convention") == "forward") else SERIES.get(fam))),')

C = "selfcheck_m3a3.py"
sub(C, 'key in ("prior_kind", "iv_form"):', 'key in ("prior_kind", "iv_form", "delta_convention"):')

S = "m3a_skewkit3.py"
sub(S, '''def s30(b="-0.5", c="1.5", q="0.01", r="0.03", atm="0.20", days=30, n=5, extra=(), **kw):''',
    '''def s30(b="-0.5", c="1.5", q="0.01", r="0.03", atm="0.20", days=30, n=5, extra=(), conv="spot", **kw):''')
sub(S, '''    exps = [ex(days, "1000", r, q, atm=atm, b=b, c=c, n=n, **kw)] + list(extra)
    return spec_of(exps, r=r, q=q)''', '''    exps = [ex(days, "1000", r, q, atm=atm, b=b, c=c, n=n, **kw)] + list(extra)
    sp = spec_of(exps, r=r, q=q)
    sp["conv"] = conv
    return sp''')
sub(S, '''    sf = Surf(spec)
    return sf''' if False else '''def parts(spec, target=30):
    sf = Surf(spec)''', '''def parts(spec, target=30):
    sf = Surf(spec, conv=spec.get("conv", "spot"))''')

R = "m3a_ref3.py"
sub(R, '''        self.stale = req.get("stale_limit_ns", 10_000_000_000)''', '''        self.stale = req.get("stale_limit_ns", 10_000_000_000)
        cv = req.get("delta_convention", "spot")
        cv = cv if cv in ("spot", "forward") else "spot"
        if "M46" in mut:
            cv = "spot"
        self.fwd = (cv == "forward") != ("M45" in mut)''')
sub(R, '''        disc = 1.0 if "M04" in self.mut else math.exp(-self.q * T)''', '''        disc = 1.0 if ("M04" in self.mut or self.fwd) else math.exp(-self.q * T)''')
sub(R, '''    try:
        if fam == "V21" and thr is None:''', '''    if fam in ("V8", "V10", "V11", "V21"):
        cvv = req.get("delta_convention", "spot")
        if not isinstance(cvv, str):
            return out(ch, req, "invalid_input", code="malformed_type")
        if cvv not in ("spot", "forward"):
            return out(ch, req, "invalid_input", code="convention_not_allowed")
        if fam == "V10" and "M47" not in mut:
            recs = ([prior] if prior is not None else []) + list(store)
            if any(x.get("delta_convention", "spot") != cvv for x in recs):
                return out(ch, req, "invalid_input", code="convention_mismatch")
    try:
        if fam == "V21" and thr is None:''')
sub(R, '''        return _eval(fam, ch, req, direction, thr, prior, store, n, cut, mut)
    except ZeroDivisionError:''', '''        o = _eval(fam, ch, req, direction, thr, prior, store, n, cut, mut)
        if fam in ("V8", "V10", "V11", "V21") and o["status"] == "available":
            o["value"]["delta_convention"] = req.get("delta_convention", "spot")
        return o
    except ZeroDivisionError:''')

R2 = "run_mutants_m3a3.py"
sub(R2, '    "M48":', '''    "M45": "delta convention swapped (spot request computed as forward and back)",
    "M46": "delta convention ignored (always spot)",
    "M47": "convention_mismatch not checked for priors",
    "M48":''')

# ---------------------------------------------------------------- rows
sub("gen_m3a_v8.py", "assert len(rows) == 51", '''FW = dict(delta_convention="forward")
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
assert len(rows) == 61''')

sub("gen_m3a_v10.py", "assert len(rows) == 53", '''

def addc(spec, rid, why, conv, label, kind="frame", ref=None, refs=None, **kw):
    """conv: request convention; label: delta_convention carried by the USED prior record (None = field absent)."""
    now = now_of(spec)
    rq = request(tenors=[30], prior_kind=kind, delta_convention=conv, **kw)
    ok = conv if isinstance(conv, str) else "spot"
    def lab(rec, lb):
        if lb is not None:
            rec = dict(rec, delta_convention=lb)
        return rec
    if kind == "frame":
        prior = lab(g5.frame_prior(fs(D(ref))), label)
        store = [dict(x, delta_convention=ok) for x in store_rec([g5.int8(now + D("0.05"))])]
    else:
        store = [lab(x, label) for x in store_rec([g5.int8(x) for x in refs])]
        prior = dict(g5.frame_prior(fs(now)), delta_convention=ok)
    rows.append(make_row("V10", rid, "V10; delta_convention (owner decision 3)", R + ["OD-3"], spec, rq, prior=prior, store=store, derivation=why, tags=["convention"]))


fw = skew_spec("5", q="0.10", conv="forward")
nf = now_of(fw)
addc(fw, "V10-Cv1", "forward convention, frame prior labelled forward, change +3: fires; series skew25_fwd", "forward", "forward", ref=fs(nf - D("0.03")))
addc(fw, "V10-Cv2", "forward convention, session store labelled forward, n=1, change +3", "forward", "forward", kind="session", refs=[nf - D("0.03")])
addc(skew_spec("5", q="0.10"), "V10-Cv3", "explicit spot convention, prior labelled spot", "spot", "spot", ref=fs(now_of(skew_spec("5", q="0.10")) - D("0.03")))
addc(fw, "V10-Cv4", "forward request, frame prior WITHOUT the field (= spot): convention_mismatch", "forward", None, ref=fs(nf - D("0.03")))
addc(fw, "V10-Cv5", "spot request, frame prior labelled forward: convention_mismatch", "spot", "forward", ref=fs(nf - D("0.03")))
addc(fw, "V10-Cv6", "spot request, stored session close labelled forward: convention_mismatch", "spot", "forward", kind="session", refs=[nf - D("0.03")])
addc(fw, "V10-Cv7", "delta_convention 'Spot': convention_not_allowed", "Spot", None, ref=fs(nf - D("0.03")))
addc(fw, "V10-Cv8", "delta_convention 2 (non-string): malformed_type", 2, None, ref=fs(nf - D("0.03")))
assert len(rows) == 61''')

sub("gen_m3a_v11.py", "assert len(rows) == 27", '''for i, (t, kw, w) in enumerate([("5", dict(q="0.10"), "fires"), ("2.7", dict(q="0.10"), "no fire"), ("-4", dict(q="0.10"), "inverted, default up: no fire"), ("3.3", {}, "fires")]):
    add(cv(t, conv="forward", **kw), "V11-Cv%d" % (i + 1), "forward delta convention, curvature %s points: %s" % (t, w), tags=["forward"], delta_convention="forward")
add(cv("5", q="0.10"), "V11-Cv5", "explicit spot, q 0.10: echoes spot", tags=["spot"], delta_convention="spot")
add(cv("5", q="0.10", conv="forward"), "V11-Cv6", "chain tuned under forward read with the default spot convention", tags=["spot", "default"])
add(cv("5"), "V11-Cv7", "delta_convention 'fwd': convention_not_allowed", tags=["selector"], delta_convention="fwd")
add(cv("5"), "V11-Cv8", "delta_convention true: malformed_type", tags=["selector"], delta_convention=True)
assert len(rows) == 35''')

sub("gen_m3a_v21.py", "assert len(rows) == 30", '''for i, (t, thr, w) in enumerate([("3", "2", "fires"), ("2.6", "2", "fires"), ("1.4", "2", "no")]):
    add(rs(t, conv="forward", q="0.10", **POS), "V21-Cv%d" % (i + 1), "forward delta convention, q 0.10, ratio %s vs X %s: %s" % (t, thr, w), thr=thr, tags=["forward"], delta_convention="forward")
add(rs("3", conv="forward", q="0.10", **POS), "V21-Cv4", "chain of Cv1 read with the default spot convention: a different ratio", thr="2", tags=["spot", "default"])
add(rs("3", q="0.10", **POS), "V21-Cv5", "explicit spot, q 0.10", thr="2", tags=["spot"], delta_convention="spot")
add(rs("3", **POS), "V21-Cv6", "delta_convention 'Forward ': convention_not_allowed", thr="2", tags=["selector"], delta_convention="Forward ")
add(rs("3", **POS), "V21-Cv7", "delta_convention 0.5 (non-string): malformed_type", thr="2", tags=["selector"], delta_convention=0.5)
assert len(rows) == 37''')
