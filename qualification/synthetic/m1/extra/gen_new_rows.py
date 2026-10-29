"""Tester (M1b review) new IV rows. Expectations are hand-derived from stated sigmas / rules, never from solver output.
Quotes: mid = BS price(sigma) rounded to 4dp, bid = mid - 0.001, ask = mid + 0.001 (spread 0.002) unless overridden."""
import json, math, sys
sys.path.insert(0, ".")
from oracle import price

LIM = 10_000_000_000
EV = -2_000_000_000
rows = []


def fmt(x, n=4):
    return "%.*f" % (n, x)


def mk(spot, r, q, specs, T=None):
    """specs: dict(d, right, K, sig, style='european', mid=None, bid=?, ask=?, event_ns, known_at_ns, condition)"""
    out = []
    for s in specs:
        d, right, K = s["d"], s["right"], s["K"]
        if s.get("mid") is not None:
            mid = s["mid"]
        else:
            mid = round(price(spot, K, r, q, d / 365, s["sig"], right), 4)
        bid = s.get("bid", fmt(mid - 0.001))
        ask = s.get("ask", fmt(mid + 0.001))
        out.append(dict(id="%dd-%s-%s" % (d, right[0].upper(), fmt(K)), expiry_days=d, right=right, strike=fmt(K),
                        style=s.get("style", "european"), bid=bid, ask=ask, event_ns=s.get("event_ns", EV),
                        known_at_ns=s.get("known_at_ns", s.get("event_ns", EV)), condition=s.get("condition", "regular")))
    return out


def pair(d, K, sc, sp, **kw):
    a = dict(d=d, K=K)
    a.update(kw)
    return [dict(a, right="call", sig=sc), dict(a, right="put", sig=sp)]


def row(id, group, case, op, spot, r, q, specs, request_extra, expected, derivation, tags, pre=None):
    contracts = pre if pre is not None else mk(spot, r, q, specs)
    req = {"stale_limit_ns": LIM, "year_basis_days": 365, "time_to_expiry": "calendar days, expiry N*24h after cutoff",
           "price_input": "midpoint of bid and ask", "cutoff_ns": 0}
    req.update(request_extra)
    rows.append(dict(id=id, group=group, case=case, op=op,
                     inputs=dict(T_ns=0, spot=fmt(spot), rate=repr(r), dividend_yield=repr(q), contracts=contracts),
                     request=req, gating=True, expected=expected, derivation=derivation, tags=tags))


def atm_exp(K, F, c, p, label="exact-model"):
    return dict(status="value", reason=None, strike=fmt(K), forward=fmt(F, 8), call_iv=fmt(c), put_iv=fmt(p),
                iv=fmt((c + p) / 2, 6), label=label, tolerance_iv="0.0001", tolerance_forward="0.000001")


def atm_un(reason):
    return dict(status="unavailable", reason=reason, strike=None, forward=None, call_iv=None, put_iv=None, iv=None,
                label=None, tolerance_iv="0.0001", tolerance_forward="0.000001")


def atm_exp_un(reason, K, F):
    return dict(status="unavailable", reason=reason, strike=fmt(K), forward=fmt(F, 8), call_iv=None, put_iv=None, iv=None,
                label=None, tolerance_iv="0.0001", tolerance_forward="0.000001")


def fwd(S, r, q, d):
    return S * math.exp((r - q) * d / 365)


def cexp(**items):
    out = {}
    for k, v in items.items():
        out[k] = v
    return out


def cv(iv, label="exact-model"):
    return dict(status="value", reason=None, iv=fmt(iv), label=label)


def cu(reason):
    return dict(status="unavailable", reason=reason, iv=None, label=None)


S, R, Q = 100.0, 0.03, 0.01
F30 = fwd(S, R, Q, 30)

# ---- N01 stale age == limit exactly is NOT stale (contract + ATM), limit+1 ns is stale
spec = pair(30, 100.0, 0.19, 0.21, event_ns=-LIM) + pair(30, 105.0, 0.17, 0.23)
row("N-S01", "contract_iv", "age exactly equal to the stale limit is fresh", "contract_iv", S, R, Q, spec, {},
    {"contracts": {"30d-C-100.0000": cv(0.19), "30d-P-100.0000": cv(0.21), "30d-C-105.0000": cv(0.17), "30d-P-105.0000": cv(0.23)},
     "tolerance_iv": "0.0001"},
    "cutoff - event = 10 s = limit; stale only when strictly greater (D10). All four contracts priced from stated sigma.",
    ["new", "stale_boundary", "kills:X4"])
row("N-S02", "atm_iv", "ATM pair at age == limit stays the ATM strike", "atm_iv", S, R, Q, spec, {"expiry_days": 30},
    atm_exp(100.0, F30, 0.19, 0.21), "F=%.8f; strike 100 nearest; both legs age = limit, fresh, so strike 100 stays eligible; ATM IV = 0.20." % F30,
    ["new", "stale_boundary", "kills:X4"])
spec2 = pair(30, 100.0, 0.19, 0.21, event_ns=-LIM - 1) + pair(30, 105.0, 0.17, 0.23)
row("N-S03", "atm_iv", "ATM call age == limit + 1 ns: strike 100 ineligible, next strike used", "atm_iv", S, R, Q, spec2, {"expiry_days": 30},
    atm_exp(105.0, F30, 0.17, 0.23), "age 10 s + 1 ns > limit -> stale_quote for both 100 legs; only 105 has two eligible legs; ATM IV = (0.17+0.23)/2 = 0.20.",
    ["new", "stale_boundary", "kills:X4"])

# ---- N02 excluded_condition: contract, ATM pool, precedence
spec = (pair(30, 100.0, 0.19, 0.21) + pair(30, 105.0, 0.17, 0.23))
spec[1] = dict(spec[1], condition="auction")           # put 100 excluded
row("N-X01", "atm_iv", "excluded-condition put at the nearest strike: strike 105 used", "atm_iv", S, R, Q, spec, {"expiry_days": 30},
    atm_exp(105.0, F30, 0.17, 0.23), "put 100 has condition auction -> excluded_condition; strike 100 not eligible; 105 both regular; ATM IV 0.20.",
    ["new", "excluded_condition", "kills:X10"])
spec = mk(S, R, Q, pair(30, 100.0, 0.19, 0.21)) + []
tests = [("auction", "0.0000", "0.0000"), ("auction", None, None)]
sp = []
# precedence matrix on put/call contracts at distinct strikes
def gp(K, right, **kw):
    return dict(d=30, K=K, right=right, sig=0.2, **kw)
pre = mk(S, R, Q, [
    gp(100.0, "call", condition="auction"),                                  # excluded, otherwise fine
    gp(101.0, "call", condition="auction", bid="1.5000", ask="1.4000"),      # excluded + crossed -> excluded
    gp(102.0, "call", condition="auction", event_ns=-LIM - 5),               # excluded + stale -> excluded
    gp(103.0, "call", condition="auction", known_at_ns=5),                   # no_quote (future knowledge) + excluded -> no_quote
    gp(104.0, "call", condition="auction", bid=None, ask=None),              # no price at all + excluded -> no_quote
    gp(105.0, "call", bid="1.5000", ask="1.4000", event_ns=-LIM - 5),        # crossed + stale -> crossed
    gp(106.0, "call", bid="1.5000", ask="1.5000", event_ns=-LIM - 5),        # locked + stale -> locked
    gp(107.0, "call", bid="0.0000", ask="0.5000", event_ns=-LIM - 5),        # invalid (bid 0) + stale -> invalid
    gp(108.0, "call", bid=None, ask="0.5000"),                               # ask only -> invalid
    gp(109.0, "call", event_ns=-LIM - 5),                                    # stale only
])
row("N-X02", "contract_iv", "gate precedence on the IV path", "contract_iv", S, R, Q, None, {},
    {"contracts": {"30d-C-100.0000": cu("excluded_condition"), "30d-C-101.0000": cu("excluded_condition"),
                   "30d-C-102.0000": cu("excluded_condition"), "30d-C-103.0000": cu("no_quote"), "30d-C-104.0000": cu("no_quote"),
                   "30d-C-105.0000": cu("crossed_market"), "30d-C-106.0000": cu("locked_market"), "30d-C-107.0000": cu("invalid_quote"),
                   "30d-C-108.0000": cu("invalid_quote"), "30d-C-109.0000": cu("stale_quote")}, "tolerance_iv": "0.0001"},
    "Order (D6/D7 and module rules): no_quote, excluded_condition, invalid, crossed, locked, stale. Each id carries the winning gate.",
    ["new", "gate_precedence", "kills:X10"], pre=pre)
# known_at exactly at cutoff is visible; just after is not
pre = mk(S, R, Q, pair(30, 100.0, 0.19, 0.21, event_ns=EV, known_at_ns=0) + pair(30, 105.0, 0.17, 0.23))
pre[1]["known_at_ns"] = 1       # put 100 known 1 ns after the cutoff
row("N-K01", "atm_iv", "put quote known 1 ns after the cutoff is invisible: strike 105 used", "atm_iv", S, R, Q, None, {"expiry_days": 30},
    atm_exp(105.0, F30, 0.17, 0.23), "put 100 known_at = cutoff + 1 ns -> no_quote; strike 100 loses its put; 105 used; call 100 known_at = cutoff is visible but irrelevant. IV 0.20.",
    ["new", "known_at", "kills:X11"], pre=pre)
pre2 = mk(S, R, Q, pair(30, 100.0, 0.19, 0.21, event_ns=EV, known_at_ns=0))
row("N-K02", "atm_iv", "known_at exactly the cutoff is visible", "atm_iv", S, R, Q, None, {"expiry_days": 30},
    atm_exp(100.0, F30, 0.19, 0.21), "known_at = cutoff is not after the cutoff; both legs usable; ATM IV 0.20.", ["new", "known_at"], pre=pre2)

# ---- N03 mixed style at the ATM strike
spec = [dict(d=30, K=100.0, right="call", sig=0.19, style="european"), dict(d=30, K=100.0, right="put", sig=0.21, style="american"),
        dict(d=30, K=105.0, right="call", sig=0.17), dict(d=30, K=105.0, right="put", sig=0.23)]
row("N-M01", "atm_iv", "mixed style at the ATM strike (call european, put american): approximate", "atm_iv", S, R, Q, spec, {"expiry_days": 30},
    atm_exp(100.0, F30, 0.19, 0.21, "approximate: European model on an American-style contract"),
    "any American leg gives the approximate label (D13); strike 100 nearest F=%.4f; IV 0.20." % F30, ["new", "mixed_style"])
spec = [dict(d=30, K=100.0, right="call", sig=0.19, style="european"), dict(d=30, K=100.0, right="put", sig=0.21, style=None),
        dict(d=30, K=105.0, right="call", sig=0.17), dict(d=30, K=105.0, right="put", sig=0.23)]
row("N-M02", "atm_iv", "unknown-style put at the ATM strike: style_unknown, no fallback to 105", "atm_iv", S, R, Q, spec, {"expiry_days": 30},
    atm_exp_un("style_unknown", 100.0, F30), "PO ruling: unknown-style ATM strike gives style_unknown with no fallback strike, although 105 is fully eligible.",
    ["new", "mixed_style", "ruling"])
row("N-M03", "iv_30d", "unknown-style ATM leg at the exact 30d expiry propagates", "iv_30d", S, R, Q, spec, {"target_days": 30},
    dict(status="unavailable", reason="style_unknown", iv=None, label=None, expiries_used=[], method=None, tolerance_iv="0.0001"),
    "exact-expiry failure reported with its own reason (style_unknown); expiries_used empty.", ["new", "mixed_style", "ruling"])
spec = (pair(21, 100.0, 0.20, 0.20) + pair(49, 100.0, 0.30, 0.30))
spec[1] = dict(spec[1], style=None)
row("N-M04", "iv_30d", "unknown-style ATM leg on the lower bracketing expiry propagates style_unknown", "iv_30d", S, R, Q, spec, {"target_days": 30},
    dict(status="unavailable", reason="style_unknown", iv=None, label=None, expiries_used=[21, 49], method=None, tolerance_iv="0.0001"),
    "bracket 21/49 exists; 21d ATM put has unknown style; reason style_unknown (not no_bracketing_expiry); expiries_used shows the bracket.",
    ["new", "mixed_style", "ruling"])
# American contract-level on a mixed chain: unknown style ITM leg stays style_unknown
# ---- N04 American nearest with a tie (S=100.5 r=q): nearest = lower strike 100
pre = mk(100.5, 0.04, 0.04, [dict(d=30, K=100.0, right="call", sig=0.2, style="american"), dict(d=30, K=100.0, right="put", sig=0.2, style="american"),
                             dict(d=30, K=101.0, right="call", sig=0.2, style="american"), dict(d=30, K=101.0, right="put", sig=0.2, style="american")])
row("N-A01", "contract_iv", "American with an exact tie in nearness: lower strike is the exempt strike", "contract_iv", 100.5, 0.04, 0.04, None, {},
    {"contracts": {"30d-C-100.0000": cv(0.2, "approximate: European model on an American-style contract"), "30d-P-100.0000": cv(0.2, "approximate: European model on an American-style contract"),
                   "30d-C-101.0000": cv(0.2, "approximate: European model on an American-style contract"), "30d-P-101.0000": cu("american_itm")},
     "tolerance_iv": "0.0001"},
    "r=q so F=S=100.5, strikes 100 and 101 equidistant -> nearest = 100 (lower). C100 (K<F) ITM but exempt; P100 OTM; C101 OTM; P101 (K>F) ITM and not nearest -> american_itm.",
    ["new", "american", "tie"], pre=pre)

# ---- N05 solver failure on an ATM leg
spec = [dict(d=30, K=100.0, right="call", sig=0.19), dict(d=30, K=100.0, right="put", sig=0.21, mid=150.0, bid="149.9990", ask="150.0010"),
        dict(d=30, K=105.0, right="call", sig=0.17), dict(d=30, K=105.0, right="put", sig=0.23)]
row("N-F01", "atm_iv", "ATM put priced above the no-arbitrage upper bound: solver reason, no fallback", "atm_iv", S, R, Q, spec, {"expiry_days": 30},
    dict(status="unavailable", reason="price_out_of_bounds", strike="100.0000", forward=fmt(F30, 8), call_iv="0.1900", put_iv=None, iv=None, label=None,
         tolerance_iv="0.0001", tolerance_forward="0.000001"),
    "put 100 mid 150 > K*exp(-rT)=99.75 (upper bound of a put) -> no implied vol exists; ATM unavailable with the solver's reason, strike 100 kept (no fallback to 105).",
    ["new", "solver_failure", "ruling"])
row("N-F02", "contract_iv", "solver failure is reported per contract", "contract_iv", S, R, Q, spec, {},
    {"contracts": {"30d-C-100.0000": cv(0.19), "30d-P-100.0000": cu("price_out_of_bounds"), "30d-C-105.0000": cv(0.17), "30d-P-105.0000": cv(0.23)},
     "tolerance_iv": "0.0001"}, "same chain; only the 150 put is impossible.", ["new", "solver_failure"])
row("N-F03", "iv_30d", "solver failure on the exact 30d expiry", "iv_30d", S, R, Q, spec, {"target_days": 30},
    dict(status="unavailable", reason="price_out_of_bounds", iv=None, label=None, expiries_used=[], method=None, tolerance_iv="0.0001"),
    "exact expiry: its own failure reason, expiries_used empty, no fallback.", ["new", "solver_failure", "ruling"])
spec = pair(21, 100.0, 0.20, 0.20) + [dict(d=49, K=100.0, right="call", sig=0.3), dict(d=49, K=100.0, right="put", sig=0.3, mid=150.0, bid="149.9990", ask="150.0010")]
row("N-F04", "iv_30d", "solver failure on the upper bracketing expiry propagates", "iv_30d", S, R, Q, spec, {"target_days": 30},
    dict(status="unavailable", reason="price_out_of_bounds", iv=None, label=None, expiries_used=[21, 49], method=None, tolerance_iv="0.0001"),
    "bracket 21/49; 49d ATM put impossible; reason price_out_of_bounds (not no_bracketing_expiry); bracket reported.", ["new", "solver_failure", "ruling"])

# ---- N06 binary64 near-tie (tolerance-scale effects): strikes 100 and 101, S=100.5
def skew_chain(S_, r, q):
    return pair(30, 100.0, 0.19, 0.21) + pair(30, 101.0, 0.24, 0.26)
for tag, r, q, K, c, p, note in [
    ("N-B01", 0.0300000010, 0.03, 101.0, 0.24, 0.26, "r-q = +1e-9 -> F = 100.5*exp(1e-9*30/365) = 100.5 + 8.3e-9 > midpoint 100.5, so 101 is nearer (a float-only tie rule would call a tie and pick 100)"),
    ("N-B02", 0.03, 0.0300000010, 100.0, 0.19, 0.21, "r-q = -1e-9 -> F = 100.5 - 8.3e-9 < midpoint, so 100 is nearer"),
    ("N-B03", 0.0301, 0.03, 101.0, 0.24, 0.26, "r-q = +1e-4 -> F = 100.5 + 8.3e-4 > 100.5, 101 nearer"),
    ("N-B04", 0.0299, 0.03, 100.0, 0.19, 0.21, "r-q = -1e-4 -> F = 100.5 - 8.3e-4, 100 nearer"),
    ("N-B05", 0.05, 0.05, 100.0, 0.19, 0.21, "r = q = 0.05 (not exactly representable but identical binary64) -> F = S = 100.5 exactly, a true tie, lower strike 100")]:
    S_ = 100.5
    row(tag, "atm_iv", "binary64 rate/yield near a nearest-strike tie: " + tag, "atm_iv", S_, r, q, skew_chain(S_, r, q), {"expiry_days": 30},
        atm_exp(K, fwd(S_, r, q, 30), c, p), note + ". Mean IV = (call+put)/2 of the chosen strike.", ["new", "binary64", "tie"])

# ---- N07 parity-consistent chain with r != q, two expiries
spec = []
for d in (21, 49):
    for K in (90.0, 95.0, 100.0, 105.0, 110.0):
        spec += pair(d, K, 0.25, 0.25)
Rp, Qp = 0.05, 0.02
row("N-P01", "iv_30d", "parity-consistent chain r=5% q=2%, flat 25% on both rights, 21d/49d", "iv_30d", S, Rp, Qp, spec, {"target_days": 30},
    dict(status="value", reason=None, iv="0.250000", label="exact-model", expiries_used=[21, 49], method="variance_interpolation", tolerance_iv="0.0001"),
    "C-P = S e^-qT - K e^-rT at every strike by construction (same sigma both rights). Flat total variance 0.0625*T is linear in T so interpolation returns 0.25 exactly.",
    ["new", "parity"])
row("N-P02", "atm_iv", "parity chain: ATM strike by forward with r!=q", "atm_iv", S, Rp, Qp, spec, {"expiry_days": 21},
    atm_exp(100.0, fwd(S, Rp, Qp, 21), 0.25, 0.25), "F=100*exp(0.03*21/365)=%.6f; nearest of 90..110 is 100." % fwd(S, Rp, Qp, 21), ["new", "parity"])

# ---- N08 many-expiry chain around 30 days (integer-day API: 29 and 31)
spec = []
sig = {7: 0.30, 14: 0.28, 29: 0.20, 31: 0.24, 45: 0.26, 60: 0.27, 90: 0.28}
for d, s_ in sig.items():
    spec += pair(d, 100.0, s_, s_)
w = (0.20 ** 2 * 29 + 0.24 ** 2 * 31) / 2 / 365
iv = math.sqrt(w / (30 / 365))
row("N-E01", "iv_30d", "seven expiries, 29d and 31d bracket the target", "iv_30d", S, R, Q, spec, {"target_days": 30},
    dict(status="value", reason=None, iv=fmt(iv, 10), label="exact-model", expiries_used=[29, 31], method="variance_interpolation", tolerance_iv="0.0001"),
    "w29=0.04*29/365, w31=0.0576*31/365; target is the midpoint of 29 and 31 so w30=(w29+w31)/2 = (1.16+1.7856)/2/365; IV=sqrt(w30/(30/365)) = %.8f (linear-in-IV would be 0.22)." % iv,
    ["new", "many_expiry"])
spec2 = [s_ for s_ in spec if not (s_["d"] == 31 and s_["right"] == "put")]
row("N-E02", "iv_30d", "same chain, 31d put missing: no ATM strike on 31d, bracket kept", "iv_30d", S, R, Q, spec2, {"target_days": 30},
    dict(status="unavailable", reason="no_bracketing_expiry", iv=None, label=None, expiries_used=[29, 31], method=None, tolerance_iv="0.0001"),
    "D14: bracketing expiry without an ATM strike -> no_bracketing_expiry; 45d is NOT substituted; bracket reported.", ["new", "many_expiry"])
spec3 = spec + pair(30, 100.0, 0.22, 0.22)
row("N-E03", "iv_30d", "same chain plus an exact 30d expiry: used as is", "iv_30d", S, R, Q, spec3, {"target_days": 30},
    dict(status="value", reason=None, iv="0.220000", label="exact-model", expiries_used=[30], method="as_is", tolerance_iv="0.0001"),
    "exact expiry beats interpolation; ATM IV = 0.22.", ["new", "many_expiry"])
row("N-E04", "iv_30d", "target 14: listed expiry as is, even with neighbours", "iv_30d", S, R, Q, spec, {"target_days": 14},
    dict(status="value", reason=None, iv="0.280000", label="exact-model", expiries_used=[14], method="as_is", tolerance_iv="0.0001"),
    "target_days=14 is listed; ATM IV 0.28.", ["new", "many_expiry"])
row("N-E05", "iv_30d", "target beyond the longest expiry: no extrapolation", "iv_30d", S, R, Q, spec, {"target_days": 120},
    dict(status="unavailable", reason="no_bracketing_expiry", iv=None, label=None, expiries_used=[], method=None, tolerance_iv="0.0001"),
    "no expiry above 120 -> no_bracketing_expiry, expiries_used empty.", ["new", "many_expiry"])

LABEL = "mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12"
doc = dict(provenance="SYNTHETIC", qualification_label=LABEL, generator="gen_new_rows.py", schema_version="m1-iv-extra1",
           note="Extra IV rows for chainiv; same row vocabulary as ../m1_iv_cases.json. Expected values are stated sigmas or rule derivations, never solver output.",
           tolerance={"iv_abs": "0.0001", "forward_abs": "0.000001"},
           closed_reasons=["no_quote", "excluded_condition", "invalid_quote", "crossed_market", "locked_market", "stale_quote",
                           "no_atm_strike", "no_bracketing_expiry", "american_itm", "style_unknown", "price_out_of_bounds"],
           rows=rows)
with open(sys.argv[1], "w", newline="\n") as fh:
    fh.write(json.dumps(doc, indent=1) + "\n")
print(len(rows), "rows")
