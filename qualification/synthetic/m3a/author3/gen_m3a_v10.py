"""V10 (M3A-9) fixture generator: 25-delta skew change in points or sign change versus a prior reading (SYNTHETIC)."""
from decimal import Decimal as D
from m3a_oracle3 import CUT, Surf, spec_of, ex, request, r8, fs
from m3a_rowkit3 import make_row, write_dataset, outdir_arg, store_rec, evaluate, fill
from m3a_skewkit3 import s30, skew_spec, parts, deviant
import gen_m3a_g5 as g5

R = ["R-34", "R-82", "R-40", "R-92", "R-95", "R-84", "R-35", "R-36", "R-27", "R-28"]
rows = []


def now_of(spec):
    p, c, _ = parts(spec)
    if isinstance(p, str) or isinstance(c, str):
        return D(0)
    return r8(p - c)


def add(spec, rid, why, kind="frame", ref=None, refs=None, n=1, cond=None, direction=None, thr=None, dp=4,
        pending=None, tags=(), extra=(), prior_override="unset", store_override="unset", **kw):
    """ref: prior annual skew (frame kind) ; refs: list of annual skews, most recent first (session kind)."""
    now = now_of(spec)
    rq = request(direction=direction, threshold=thr, tenors=[30], prior_kind=kind, **kw)
    if cond is not None:
        rq["condition"] = cond
    rq["prior_sessions"] = n
    if kind == "frame":
        prior = g5.frame_prior(fs(D(ref))) if ref is not None else None
        store = store_rec([g5.int8(now + D("0.05"))])
    else:
        store = store_rec([g5.int8(x) for x in refs]) if refs is not None else []
        prior = g5.frame_prior(fs(now))
    if prior_override != "unset":
        prior = prior_override
    if store_override != "unset":
        store = store_override
    # decoy of the unused source: chosen so that using it would flip the intended outcome
    sf, res = evaluate("V10", spec, fill("V10", rq), prior, store)
    if res["status"] == "available":
        cnd = cond or "change"
        dr = direction or "either"
        if cnd == "change":
            dec = now if res["fired"] else (now + D("0.05") if dr == "down" else now - D("0.05"))
        else:
            dec = now if res["value"]["sign_changed"] else (-now if now != 0 else D("0.03"))
        if kind == "frame":
            store = store_rec([g5.int8(dec)])
        else:
            prior = g5.frame_prior(fs(dec))
        if prior_override != "unset":
            prior = prior_override
        if store_override != "unset":
            store = store_override
    rows.append(make_row("V10", rid, "V10; R-34 R-82 (change in points, sign of rounded-once difference)", R + list(extra), spec, rq,
                         prior=prior, store=store, derivation=why, dp=dp, pending=pending, tags=tags))


def sk(t, **kw):
    return skew_spec(t, **kw)


base = sk("4")
N = now_of(base)


def refc(change):
    return fs(N - D(change) / 100)


for i, (c, w) in enumerate([("3", "fires"), ("-3", "fires"), ("1.8", "no"), ("-1.8", "no")]):
    add(base, "V10-A%d" % (i + 1), "frame prior, change %s points, default direction either, X 2: %s" % (c, w), ref=refc(c),
        tags=["default-direction"])
for d, cs in (("up", [("3", "fires"), ("-3", "no fire"), ("1.8", "no fire")]), ("down", [("-3", "fires"), ("3", "no fire")])):
    for i, (c, w) in enumerate(cs):
        add(base, "V10-B%s%d" % (d[0], i + 1), "frame prior, direction %s, X 2, change %s: %s" % (d, c, w), ref=refc(c),
            direction=d, thr="2")
b8 = sk("4")
for i, (c, d) in enumerate([("2", "up"), ("-2", "down"), ("2", "either"), ("-2", "either")]):
    add(b8, "V10-C%d" % (i + 1), "change exactly %s points (inclusive), quotes 8 decimals, near threshold" % c, ref=refc(c),
        direction=d, thr="2", dp=8, tags=["boundary-exact"])
# sign change condition on the rounded-once skew; 0 is never a flip
sg = [("3", "-0.02", "now +3 points, prior -0.02: changed through zero"), ("-3", "0.02", "now -3, prior +0.02: changed"),
      ("3", "0.02", "same sign positive: not changed"), ("-3", "-0.02", "same sign negative: not changed"),
      ("3", "0", "prior exactly 0: never a flip"), ("-3", "0", "prior exactly 0, now negative: never a flip")]
for i, (t, pv, w) in enumerate(sg):
    add(sk(t), "V10-D%d" % (i + 1), "sign condition: %s" % w, ref=pv, cond="sign_change", dp=8 if pv == "0" else 4, tags=["sign"])
for i, pv in enumerate(["0.02", "-0.02"]):
    add(sk("0"), "V10-D%d" % (i + 7), "sign condition: now exactly 0 (rounded once), prior %s: 0 is never a flip" % pv, ref=pv,
        cond="sign_change", dp=8, tags=["sign", "zero-now"])
# session kind (stored closes), n = 1 and 3
s1 = [fs(N - D("0.03")), fs(N)]
add(base, "V10-E1", "session prior n=1, change +3 points: fires", kind="session", refs=[N - D("0.03"), N + D("0.05")], tags=["session"])
add(sk("3"), "V10-E2", "session prior n=1, sign condition: now +3 vs stored -0.02: changed", kind="session", refs=[D("-0.02")], cond="sign_change", tags=["session", "sign"])
add(sk("3"), "V10-E3", "session prior n=1, sign condition: same sign, not changed", kind="session", refs=[D("0.02")], cond="sign_change", tags=["session", "sign"])
add(base, "V10-E4", "session prior n=1, direction down, change -3: fires", kind="session", refs=[N + D("0.03")], direction="down", thr="2", tags=["session"])
add(base, "V10-E5", "n=3: the 3rd stored close is the reference (change +3: fires); 1st would give 0", kind="session", n=3,
    refs=[N, N, N - D("0.03"), D("0.1")], tags=["session", "n-th-prior"])
add(sk("3"), "V10-E6", "n=3 sign condition: 3rd stored close is -0.02: changed; 1st same sign", kind="session", n=3,
    refs=[D("0.02"), D("0.02"), D("-0.02")], cond="sign_change", tags=["session", "n-th-prior", "sign"])
add(base, "V10-E7", "n=3: 3rd stored close equals now: no change, no fire; 1st would fire", kind="session", n=3,
    refs=[N - D("0.05"), N - D("0.05"), N], tags=["session", "n-th-prior"])
# unavailable prior
add(base, "V10-F1", "frame kind, no prior reading (decoy store non-empty): no_prior_reading", kind="frame", ref=None)
add(base, "V10-F2", "session kind, empty store (decoy frame present): no_prior_reading", kind="session", refs=None)
add(base, "V10-F3", "session kind n=3 with 2 stored closes: insufficient_history (PO batch 2, D-07)", kind="session", n=3,
    refs=[N - D("0.03"), N - D("0.03")], pending="D-07", tags=["n-th-prior"])
# prior reading time at or after the cutoff
add(base, "V10-G1", "frame prior time == cutoff: structural prior_not_before_cutoff", kind="frame", ref=refc("3"),
    prior_override=g5.at_cutoff("frame", refc("3")))
add(base, "V10-G2", "frame prior time after the cutoff: structural", kind="frame", ref=refc("3"),
    prior_override=g5.after_cutoff("frame", refc("3")))
add(base, "V10-G3", "session kind: 1st stored close time == cutoff: structural", kind="session", refs=[N - D("0.03")],
    store_override=[dict(store_rec([g5.int8(N - D("0.03"))])[0], time_ns=CUT)])
st3 = store_rec([g5.int8(N), g5.int8(N), g5.int8(N - D("0.03"))])
st3[2] = dict(st3[2], time_ns=CUT)
add(base, "V10-G4", "session kind n=3: 3rd stored close time == cutoff: structural", kind="session", n=3,
    refs=[N, N, N - D("0.03")], store_override=st3, tags=["n-th-prior"])
# surface reasons
add(spec_of([ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.5", c="1.5", strikes=["990", "1005", "1020", "1035", "1050", "1065", "1080"])]),
    "V10-H1", "put side not bracketed: no_delta_bracket", ref="0.03", tags=["side-missing"])
add(spec_of([ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.5", c="1.5", strikes=["990", "1005", "1020"])]),
    "V10-H2", "3 listed strikes: low_surface_coverage", ref="0.03", tags=["coverage"])
bk = spec_of([ex(20, "1000", "0.03", "0.01", atm="0.18", b="-1.1", c="1.5"), ex(45, "1000", "0.03", "0.01", atm="0.25", b="-0.6", c="1.5")])
add(bk, "V10-I1", "30d skew from 20d and 45d expiries, per-side total-variance interpolation, change vs prior frame", ref=fs(now_of(bk) - D("0.03")),
    tags=["tenor-interp"])
am = sk("5", style="american")
add(am, "V10-I2", "American-style chain: label approximate", ref=fs(now_of(am) - D("0.03")), pending="D-02", extra=["R-11"], tags=["american"])
add(base, "V10-I3", "delayed tag: computed and labelled delayed", ref=refc("3"), tag="delayed", extra=["R-58"])
# carry, steep and shifted grids
qh = sk("6", q="0.10")
add(qh, "V10-J1", "q 0.10, change +3", ref=fs(now_of(qh) - D("0.03")), tags=["q-high"])
add(qh, "V10-J2", "q 0.10, change -3", ref=fs(now_of(qh) + D("0.03")), tags=["q-high"])
z = sk("4", r="0.0", q="0.0")
add(z, "V10-J3", "r=0 q=0, change +3", ref=fs(now_of(z) - D("0.03")), tags=["carry"])
z2 = sk("-4", r="-0.01", q="0.03")
add(z2, "V10-J4", "r=-0.01 q=0.03, skew -4, change -3", ref=fs(now_of(z2) + D("0.03")), tags=["carry"])


def spike(put=None, call=None):
    over = {}
    if put:
        over[D("945")] = D(put)
    if call:
        over[D("1065")] = D(call)
    return spec_of([ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.5", c="1.5", over=over)])


sp = spike(put="0.5")
add(sp, "V10-J5", "non-monotone put delta (first crossing used), change vs prior +3", ref=fs(now_of(sp) - D("0.03")), tags=["non-monotone"])
sp = spike(call="0.8")
add(sp, "V10-J6", "non-monotone call delta (first crossing used), change vs prior -3", ref=fs(now_of(sp) + D("0.03")), tags=["non-monotone"])
sh = deviant(sk("5", shift=True), "975", "put", "cross", "0.07")
add(sh, "V10-J7", "grid shifted so S and F pick different ATM strikes; put at about 975 crossed with a deviant IV", ref=fs(now_of(sh) - D("0.03")), tags=["shift", "crossed"])
ti = deviant(sk("5", r="0.02", q="0.02", base="992.5"), "1050", "call", "stale", "0.07")
add(ti, "V10-J8", "tie grid r=q: forward exactly between two strikes; call at about 1050 stale with a deviant IV", ref=fs(now_of(ti) - D("0.03")), tags=["tie", "stale"])
add(spec_of([ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.5", c="1.5", strikes=["990", "1005", "1020", "1035", "1050", "1065", "1080"])]),
    "V10-M1", "two conditions: put side not bracketed and no prior reading: upstream reason first (no_delta_bracket), PO batch 2 D-09", kind="frame", ref=None)
for i, (s20, s45) in enumerate([("american", "european"), ("european", "american")]):
    mx = spec_of([ex(20, "1000", "0.03", "0.01", atm="0.18", b="-1.1", c="1.5", style=s20), ex(45, "1000", "0.03", "0.01", atm="0.25", b="-0.6", c="1.5", style=s45)])
    add(mx, "V10-X%d" % (i + 1), "mixed frame: 20d %s and 45d %s: both labels, sorted" % (s20, s45), ref=fs(now_of(mx) - D("0.03")), extra=["PO batch 2"], tags=["mixed-style"])
add(spec_of([ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.5", c="1.5", strikes=["990", "1005", "1020"])]),
    "V10-M2", "two conditions: 3 listed strikes and no prior reading: low_surface_coverage first, D-09", kind="session", refs=None)
add(spec_of([ex(30, "1000", "0.03", "0.01", atm="0.20", b="-0.5", c="1.5", strikes=["990", "1005", "1020", "1035", "1050", "1065", "1080"])]),
    "V10-P01", "two conditions: frame prior time == cutoff and put side not bracketed: structural code first (A2)", kind="frame",
    ref="0.03", prior_override=g5.at_cutoff("frame", "0.03"))


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
assert len(rows) == 61, len(rows)
if __name__ == "__main__":
    write_dataset("V10", rows, outdir_arg(), "gen_m3a_v10.py",
                  "V10 rows: now = rounded-once skew25 annual; reference = prior frame (prior_kind frame) or the n-th stored session close (prior_kind session); condition change or sign_change selects fired (invented fields, defect D-04); the unused source carries a decoy.")
