"""one-off patch script for the oracle review round 1 (kept for traceability)."""


def sub(f, a, b, cnt=1):
    s = open(f, newline="").read()
    if b in s and a not in s:
        return
    assert a in s, (f, a[:70])
    open(f, "w", newline="\n").write(s.replace(a, b, cnt))


O = "m3a_oracle3.py"
sub(O, 't = {"iv": "0.0001", "diff_annual": "0.0002", "points": "0.02"}',
    't = {"iv": "0.00003", "diff_annual": "0.00006", "points": "0.005"}')
sub(O, 'D("0.0002") / abs(pr)', 'D("0.00006") / abs(pr)')
sub(O, 'D("0.0003") * (1 + abs(D(res["value"]["ratio"])))', 'D("0.00006") * (1 + abs(D(res["value"]["ratio"])))')
sub(O, '''    L = sorted({APPROX if e["style"] == "american" else EXACT for e in sf.spec["expiries"]})
    if req.get("feed_delay_tag") == "delayed":
        L.append("delayed")
    return L''', '''    L = {APPROX if e["style"] == "american" else EXACT for e in sf.spec["expiries"]}
    if req.get("feed_delay_tag") == "delayed":
        L.add("delayed")
    return sorted(L)''')
sub(O, '''        if target in days:
            x = self.exps[target]
            if not x["cov_ok"]:''', '''        if target in days:
            x = self.exps[target]
            if key == "atm_iv" and isinstance(x[key], str):
                return x[key]
            if not x["cov_ok"]:''')
sub(O, '''        if not x1["cov_ok"] or not x2["cov_ok"]:
            return "low_surface_coverage"''', '''        if not x1["cov_ok"] or not x2["cov_ok"]:
            return "no_bracketing_expiry"''')
sub(O, '''    if store and len(store) >= n and store[n - 1]["time_ns"] >= CUT:
        return _inv(sf, "prior_not_before_cutoff", req)
    t30''', '''    if any(s["time_ns"] >= CUT for s in store):
        return _inv(sf, "prior_not_before_cutoff", req)
    t30''')
sub(O, '''    if kind == "frame":
        if prior is not None and prior["time_ns"] >= CUT:
            return _inv(sf, "prior_not_before_cutoff", req)
    else:
        if store and len(store) >= n and store[n - 1]["time_ns"] >= CUT:
            return _inv(sf, "prior_not_before_cutoff", req)
    pc = skew_now(sf)''', '''    if (prior is not None and prior["time_ns"] >= CUT) or any(s["time_ns"] >= CUT for s in (store or [])):
        return _inv(sf, "prior_not_before_cutoff", req)
    pc = skew_now(sf)''')
sub(O, '''def ev_v11(sf, req):
    pc = skew_now(sf)
    if isinstance(pc, str):
        return _bad(sf, pc, req)
    p, c = pc
    a = sf.cm(30, "atm_iv")
    if isinstance(a, str):
        return _bad(sf, a, req)
    cur''', '''def ev_v11(sf, req):
    a = sf.cm(30, "atm_iv")
    if isinstance(a, str):
        return _bad(sf, a, req)
    pc = skew_now(sf)
    if isinstance(pc, str):
        return _bad(sf, pc, req)
    p, c = pc
    cur''')
sub(O, '''def ev_v21(sf, req):
    pc = skew_now(sf)
    if isinstance(pc, str):
        return _bad(sf, pc, req)
    p, c = pc
    a = sf.cm(30, "atm_iv")
    if isinstance(a, str):
        return _bad(sf, a, req)
    if "threshold" not in req:
        return _inv(sf, "threshold_required", req)
''', '''def ev_v21(sf, req):
    if "threshold" not in req:
        return _inv(sf, "threshold_required", req)
    a = sf.cm(30, "atm_iv")
    if isinstance(a, str):
        return _bad(sf, a, req)
    pc = skew_now(sf)
    if isinstance(pc, str):
        return _bad(sf, pc, req)
    p, c = pc
''')

R = "m3a_ref3.py"
sub(R, '''    if target in days:
        if not ch.cov_ok(target):
            return "low_surface_coverage"
        v = getter(target)''', '''    if target in days:
        if kind == "atm" and getter(target) is None:
            return miss_exact
        if not ch.cov_ok(target):
            return "low_surface_coverage"
        v = getter(target)''')
sub(R, '''    if not ch.cov_ok(d1) or not ch.cov_ok(d2):
        return "low_surface_coverage"''', '''    if not ch.cov_ok(d1) or not ch.cov_ok(d2):
        return "no_bracketing_expiry"''')
sub(R, '''    L = [EXACT] if "M37" in ch.mut else sorted({APPROX if s == "american" else EXACT for s in ch.styles})
    if req.get("feed_delay_tag") == "delayed" and "M41" not in ch.mut:
        L.append("delayed")
    return L''', '''    L = {EXACT} if "M37" in ch.mut else {APPROX if s == "american" else EXACT for s in ch.styles}
    if req.get("feed_delay_tag") == "delayed" and "M41" not in ch.mut:
        L.add("delayed")
    return sorted(L)''')
sub(R, '''    thr_text = req.get("threshold", dt)''',
    '''    thr_text = next((req[k] for k in ("at_least", "at_most", "x") if k in req), dt)''')
sub(R, '''    try:
        return _eval(''', '''    try:
        if fam == "V21" and thr is None:
            return out(ch, req, "invalid_input", code="threshold_required")
        return _eval(''')
sub(R, '''        pair = req["pair"]''', '''        pair = req["pair"].replace("-", "_")''')
sub(R, '''        if store and len(store) >= n and store[(0 if "M22" in mut else n - 1)]["time_ns"] >= cut and "M26" not in mut:
            return out(ch, req, "invalid_input", code="prior_not_before_cutoff")
        getter''', '''        if any(s["time_ns"] >= cut for s in store) and "M26" not in mut:
            return out(ch, req, "invalid_input", code="prior_not_before_cutoff")
        getter''')
sub(R, '''        if kind == "frame":
            if prior is not None and prior["time_ns"] >= cut and "M26" not in mut:
                return out(ch, req, "invalid_input", code="prior_not_before_cutoff")
        else:
            if store and len(store) >= n and store[(0 if "M22" in mut else n - 1)]["time_ns"] >= cut and "M26" not in mut:
                return out(ch, req, "invalid_input", code="prior_not_before_cutoff")
    pc = skew_parts(ch)''', '''        if ((prior is not None and prior["time_ns"] >= cut) or any(s["time_ns"] >= cut for s in store)) and "M26" not in mut:
            return out(ch, req, "invalid_input", code="prior_not_before_cutoff")
    atm_first = None
    if fam in ("V11", "V21"):
        atm_first = cm_value(ch, 30, lambda d: (ch.atm(d) or (None, None))[1], "atm")
        if isinstance(atm_first, str):
            return out(ch, req, "unavailable", atm_first)
    pc = skew_parts(ch)''')
sub(R, '''    atm = cm_value(ch, 30, lambda d: (ch.atm(d) or (None, None))[1], "atm")
    if isinstance(atm, str):
        return out(ch, req, "unavailable", atm)
    if fam == "V11":''', '''    atm = atm_first
    if fam == "V11":''')

K = "m3a_rowkit3.py"
sub(K, '''    req_sent = req
    req = fill(fam, req)''', '''    req_sent = dict(req)
    req = fill(fam, req)
    if "threshold" in req_sent:
        req_sent[{"up": "at_least", "down": "at_most", "either": "x"}[req["direction"]]] = req_sent.pop("threshold")
    if "pair" in req_sent:
        req_sent["pair"] = req_sent["pair"].replace("_", "-")''')
sub(K, '"gating": True', '"gating": not near')
sub(K, '"tolerance": {"iv_abs": "0.0001", "diff_annual_abs": "0.0002", "points_abs": "0.02",',
    '"tolerance": {"iv_abs": "0.00003", "diff_annual_abs": "0.00006", "points_abs": "0.005",')

# new rows
sub("gen_m3a_v4.py", "assert len(rows) == 44", '''def _cov_bk():
    return spec_of([ex(20, "1000", "0.03", "0.01", atm="0.20", n=1), ex(45, "1000", "0.03", "0.01", atm="0.28", n=2)])


add(_cov_bk(), "12", "V4-N01", "bracketing 20d expiry fails coverage (3 strikes): the tenor has no usable bracket: no_bracketing_expiry (PO round 1 D4)")
rows.append(make_row("V4", "V4-P01", "V4; R-92", R + ["R-92"], spec_of([ex(45, "1000", "0.03", "0.01", atm="0.28", n=2), ex(60, "1000", "0.03", "0.01", atm="0.29", n=2)]),
                     request(tenors=[30]), prior=g5.at_cutoff("frame", "0.2"),
                     derivation="two conditions: prior time == cutoff and no 30-day bracket: the structural code comes first (A2)"))
assert len(rows) == 46''')
sub("gen_m3a_v7.py", "assert len(rows) == 38", '''_bad_store = store_rec([prior_int(sp, "3")])
_bad_store[0] = dict(_bad_store[0], time_ns=CUT)
add(spec_of([E(30, D("0.22"))]), _bad_store, "V7-P01", "two conditions: prior time == cutoff and no 91-day bracket: structural code first (A2)")
_st2 = store_rec([prior_int(sp, "3"), prior_int(sp, "0")])
_st2[1] = dict(_st2[1], time_ns=CUT + 10 ** 9)
add(sp, _st2, "V7-P02", "n=1, the SECOND stored prior time after the cutoff (not the n-th): any supplied prior at or after the cutoff is structural (A4)")
assert len(rows) == 40''')
sub("gen_m3a_v8.py", "assert len(rows) == 50", '''add(spec_of([ex(20, "1000", "0.03", "0.01", atm="0.18", b="-0.8", c="1.5", n=1), ex(45, "1000", "0.03", "0.01", atm="0.24", b="-0.5", c="1.5")]), "V8-N3",
    "bracketing 20d expiry fails coverage (3 strikes): no_bracketing_expiry (PO round 1 D4)", tags=["bracket-coverage"])
assert len(rows) == 51''')
sub("gen_m3a_v11.py", "assert len(rows) == 26", '''add(spec_of([ex(20, "1000", "0.03", "0.01", atm="0.18", b="-0.3", c="14", n=1), ex(45, "1000", "0.03", "0.01", atm="0.26", b="-0.3", c="9")]), "V11-N1",
    "bracketing 20d expiry fails coverage (3 strikes): no_bracketing_expiry", tags=["bracket-coverage"])
assert len(rows) == 27''')
sub("gen_m3a_v10.py", "assert len(rows) == 52", '''add(spec_of([ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.5", c="1.5", strikes=["990", "1005", "1020", "1035", "1050", "1065", "1080"])]),
    "V10-P01", "two conditions: frame prior time == cutoff and put side not bracketed: structural code first (A2)", kind="frame",
    ref="0.03", prior_override=g5.at_cutoff("frame", "0.03"))
assert len(rows) == 53''')
