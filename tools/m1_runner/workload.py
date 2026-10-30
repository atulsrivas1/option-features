"""Unit definition and the pure per-unit computation for the process-pool runner.

Label: synthetic workload, relative engineering budget. Synthetic data only; no claim about recorded data.

A unit is (underlying, session, cutoff). One unit computes the FULL output set (M2-G0) for one size-M style chain
at one cutoff: chain IV outputs (contract IV for every contract, ATM IV for every expiry, 30-day IV:
option_features.chainiv), OC5 and OC6 for every contract (option_features.imbalance, spreadwin), and the P1
outputs the library ships over the unit's quote and trade streams: spread/locked gate and quote-count coverage
per contract at the cutoff (quotes.spread_reason, quote_spread, windows.QuoteUpdateIndex), touch-policy signing
of every print against the quote stream (quotes.classify_stream), window_end premium windows per contract
(windows.WindowIndex, explicit window end = the cutoff) and single-reference F5/F6 shares for the chain and per
expiry (shares.single_reference_shares). Units share no state: a unit's result
bytes are a pure function of (spec, unit). A worker may cache the quote history of the session it is working on
(derived data, a deterministic prefix of a stream); a test proves the cache never changes a result byte.

Inputs. Chain layout, quote streams and cutoff grid come from qualification/synthetic/perf/gen_perf_workloads.py
(seed 20261029, read only). Chain IV inputs are coherent Black-Scholes smile mids (as in tools/m1_chain_benchmark.py,
B6) with a per-unit spot and about 7 percent of contracts gated by construction (no quote, crossed, stale, bid 0);
OC5/OC6 inputs are the quote streams of the generator (per contract and session), evaluated at the cutoff.
Trade stream (M2-G0, frozen): exactly `prints` prints per contract (default PRINTS_PER_CONTRACT = 20, so 40,000
per size-M unit), times 70 percent within 4 s after a quote update at or before the cutoff and 30 percent uniform in the trailing hour, price chosen from the quote in force
(35 percent at the ask, 35 at the bid, 15 inside, 7 one tick beyond the touch, 8 arbitrary near the mid), size
1..100, 2 percent non-standard multiplier. A pure function of (spec, unit); independent of contract order.
Shape "T" is a tiny 40-contract chain for CI tests; "S", "M", "L" are the generator sizes.

Result bytes: canonical JSON (sorted keys, no spaces, UTF-8), contracts sorted by contract id. No worker count,
id, timing or completion order is ever part of them.
"""
import hashlib
import json
import math
import sys
import time
from bisect import bisect_right
from collections import namedtuple
from fractions import Fraction
from operator import itemgetter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "qualification" / "synthetic" / "perf")]
import gen_perf_workloads as gen  # noqa: E402
from option_features import chainiv, inverse  # noqa: E402
from option_features.imbalance import OC5Params, oc5  # noqa: E402
from option_features.quotehist import QuoteSize, QuoteUpdate, as_ticks  # noqa: E402
from option_features.spreadwin import OC6Params, oc6  # noqa: E402
from option_features import quotes, shares, windows  # noqa: E402

NS = 10 ** 9
RATE, DIV = 0.03, 0.01
PRINTS_PER_CONTRACT = 20          # frozen M2-G0 trade stream: 20 x 2000 contracts = 40,000 prints per size-M unit
PRINT_SPAN_NS = 3600 * NS         # prints fall in the trailing hour up to the cutoff
ANCHORED_PCT = 70                  # share of prints placed shortly after a quote update (the rest uniform in the trailing hour)
ANCHOR_SPREAD_NS = 4 * NS
PRINT_WINDOWS_NS = (300 * NS, 1800 * NS)
SHORT_DTE_MAX_DAYS = 30
CIVIL_DAY_BASE = 739000
TINY = {"expiries_days": [7, 28, 35, 63], "strikes": 5}
SHAPES = ("T", "S", "M", "L")
_SpecBase = namedtuple("Spec", "seed shape underlyings sessions cutoffs contract_order gating prints",
                       defaults=(gen.DEFAULT_SEED, "M", tuple(gen.UNDERLYINGS), tuple(range(1, gen.SESSIONS + 1)),
                                 tuple(range(gen.CUTOFFS_PER_SESSION)), "natural", "mixed", PRINTS_PER_CONTRACT))


class Spec(_SpecBase):
    __slots__ = ()

    def validate(self):
        return validate_spec(self)


def validate_spec(spec):
    if spec.shape not in SHAPES:
        raise ValueError("unknown shape %r (expected one of %s)" % (spec.shape, ", ".join(SHAPES)))
    for name in ("underlyings", "sessions", "cutoffs"):
        if not getattr(spec, name):
            raise ValueError("spec.%s is empty" % name)
    for u in spec.underlyings:
        if not isinstance(u, str) or "/" in u:
            raise ValueError("bad underlying %r" % (u,))
    for c in spec.cutoffs:
        if type(c) is not int or not 0 <= c < gen.CUTOFFS_PER_SESSION:
            raise ValueError("cutoff index out of range: %r" % (c,))
    for s in spec.sessions:
        if type(s) is not int or s < 1:
            raise ValueError("bad session %r" % (s,))
    parse_order(spec.contract_order)
    if spec.gating not in ("mixed", "valid"):
        raise ValueError("gating must be mixed or valid")
    if type(spec.prints) is not int or not 0 <= spec.prints <= 1000:
        raise ValueError("prints per contract must be an int in 0..1000")
    return spec


def parse_order(order):
    """'natural' | 'reversed' | 'shuffle:<int>' -> (kind, seed)."""
    if order in ("natural", "reversed"):
        return order, None
    if isinstance(order, str) and order.startswith("shuffle:"):
        return "shuffle", int(order[8:])
    raise ValueError("bad order %r" % (order,))


def apply_order(items, order):
    kind, seed = parse_order(order)
    items = list(items)
    if kind == "reversed":
        items.reverse()
    elif kind == "shuffle":
        items.sort(key=lambda x: hashlib.sha256(("%d|%r" % (seed, x)).encode()).digest())
    return items


def unit_key(u, s, c):
    return "%s/%02d/%03d" % (u, s, c)


def parse_key(key):
    u, s, c = key.split("/")
    return u, int(s), int(c)


def all_unit_keys(spec):
    return sorted(unit_key(u, s, c) for u in spec.underlyings for s in spec.sessions for c in spec.cutoffs)


def chain_size(shape):
    return len(TINY["expiries_days"]) * TINY["strikes"] * 2 if shape == "T" else gen.chain_size(shape)


def chain_contract(shape, i):
    if shape != "T":
        return gen.chain_contract(shape, i)
    n = TINY["strikes"]
    e, rem = divmod(i, n * 2)
    k, r = divmod(rem, 2)
    return {"i": i, "expiry_days": TINY["expiries_days"][e],
            "strike": gen.dec(gen.SPOT_TICKS + (k - n // 2) * gen.STRIKE_STEP_TICKS),
            "right": "CP"[r], "style": "european" if e % 3 == 2 else "american"}


def _ncdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _bs(spot, right, K, T, sigma):
    A, B = spot * math.exp(-DIV * T), K * math.exp(-RATE * T)
    d1 = (math.log(spot / K) + (RATE - DIV + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return A * _ncdf(d1) - B * _ncdf(d2) if right == "call" else B * _ncdf(-d2) - A * _ncdf(-d1)


def make_chain_rows(spec, u, s, c):
    """ChainContract rows (coherent smile prices, per-unit spot, deterministic gating), spot string, cutoff ns."""
    g = gen.SM64(gen.sub(spec.seed, "chain", spec.shape, u, s, c))
    spot = "%.4f" % (98.0 + 4.0 * g.uni())
    spot_f = float(spot)
    level = 0.18 + 0.06 * g.uni()
    cutoff_ns = (c + 1) * gen.CUTOFF_STEP_NS
    rows = []
    for i in range(chain_size(spec.shape)):
        m = chain_contract(spec.shape, i)
        K, days, right = float(m["strike"]), m["expiry_days"], "call" if m["right"] == "C" else "put"
        sigma = level + 0.8 * math.log(K / spot_f) ** 2 + 0.02 * math.sqrt(days / 365.0) + (0.004 if right == "put" else 0.0)
        mid = round(_bs(spot_f, right, K, days / 365.0, sigma), 4)
        bid_s, ask_s, age = "%.4f" % max(mid - 0.001, 0.0), "%.4f" % (mid + 0.001), 2 * NS
        r = g.below(100) if spec.gating == "mixed" else 100
        if r < 2:
            bid_s = ask_s = None
        elif r < 4:
            bid_s, ask_s = "%.4f" % (mid + 0.01), "%.4f" % max(mid - 0.01, 0.0)
        elif r < 6:
            age = 20 * NS
        elif r < 7:
            bid_s = "0.0000"
        cid = "%dd-%s-%s" % (days, m["right"], m["strike"])
        rows.append(chainiv.ChainContract(cid, days, right, m["strike"], bid_s, ask_s, cutoff_ns - age, cutoff_ns - age, m["style"]))
    return rows, spot, cutoff_ns


class SessionHistory:
    """Quote history of one (underlying, session) up to a time horizon: per contract a QuoteUpdate list with Ticks
    prices and a rev -> QuoteSize dict, plus the stream form of the same quotes (`recs`: ("q", contract index, t,
    bid text, ask text) for the batch classifier, `times`: update times). A deterministic prefix of the generator
    stream (the generator walks the price forward, so stopping early gives the same prefix)."""
    __slots__ = ("key", "horizon_ns", "ups", "sizes", "recs", "times", "n_updates")

    def __init__(self, spec, u, s, horizon_ns):
        self.key, self.horizon_ns = (spec.seed, spec.shape, u, s), horizon_ns
        self.ups, self.sizes, self.recs, self.times, total = [], [], [], [], 0
        stream_size = "M" if spec.shape == "T" else spec.shape
        for i in range(chain_size(spec.shape)):
            ups, sizes, recs, times = [], {}, [], []
            for rev, q in enumerate(gen.quote_stream_for_contract(spec.seed, stream_size, u, s, i), 1):
                t = q["t_rel_ns"]
                if t > horizon_ns:
                    break
                ups.append(QuoteUpdate(rev, t, t, as_ticks(q["bid"]), as_ticks(q["ask"]), True, None))
                sizes[rev] = QuoteSize(rev, q["bid_size"], q["ask_size"])
                recs.append(("q", i, t, q["bid"], q["ask"]))
                times.append(t)
            self.ups.append(ups)
            self.sizes.append(sizes)
            self.recs.append(recs)
            self.times.append(times)
            total += len(ups)
        self.n_updates = total


_OC5 = OC5Params()
_OC6 = OC6Params()


def _frac(x):
    return None if x is None else "%d/%d" % (x.numerator, x.denominator)


def _default(o):
    if hasattr(o, "numerator") and hasattr(o, "denominator"):
        return "%d/%d" % (o.numerator, o.denominator)
    raise TypeError("not serialisable: %r" % (type(o),))


FAMILIES = ("oc5", "oc6", "iv_build", "iv_contract", "atm", "iv30", "p1_spread", "p1_signing", "p1_sign_agg", "p1_window", "p1_shares", "serialize")
SYNTH = ("synth_history_s", "synth_chain_s", "synth_prints_s", "synth_prep_s")


class UnitInputs:
    """Everything a unit computes from, built before the compute timer starts (input synthesis and the plain
    conversion into the library's input shapes). Holds no result."""
    __slots__ = ("key", "spot", "rows", "cutoff_ns", "order", "hist", "cut", "expiry_days", "prints", "cover_in", "agg_in", "records",
                 "share_prints", "civil_day")


def _print_stream(spec, u, s, c, hist, metas, cutoff_ns):
    """Per contract the frozen trade stream: list of (t, right text, price text, size, multiplier)."""
    out = []
    lo = max(0, cutoff_ns - PRINT_SPAN_NS)
    span = cutoff_ns - lo + 1
    for i, m in enumerate(metas):
        g = gen.SM64(gen.sub(spec.seed, "prints", spec.shape, u, s, c, i))
        times, ups = hist.times[i], hist.ups[i]
        nq = bisect_right(times, cutoff_ns)
        ts = []
        for _ in range(spec.prints):
            if nq and g.below(100) < ANCHORED_PCT:   # shortly after a quote update (mostly fresh for the 3 s signing age)
                ts.append(min(times[g.below(nq)] + g.below(ANCHOR_SPREAD_NS), cutoff_ns))
            else:
                ts.append(lo + g.below(span))
        ts.sort()
        right = "call" if m["right"] == "C" else "put"
        rows = []
        for t in ts:
            k = bisect_right(times, t) - 1
            r = g.below(100)
            if k < 0:
                px = gen.TICK * 5 + g.below(2000)
            else:
                bid, ask = int(ups[k].bid) // 10000, int(ups[k].ask) // 10000
                if r < 35:
                    px = ask
                elif r < 70:
                    px = bid
                elif r < 85:
                    px = (bid + ask) // 2
                elif r < 92:
                    px = ask + 1 if r & 1 else max(bid - 1, 1)
                else:
                    px = max((bid + ask) // 2 + g.below(21) - 10, 1)
            size = 1 + g.below(100)
            mult = 10 if g.below(50) == 0 else 100
            rows.append((t, right, gen.dec(px), size, mult))
        out.append(rows)
    return out


def build_inputs(spec, key, history=None, timing=None):
    """Input synthesis and conversion for one unit (not part of the compute timer). timing (dict) gets the seconds."""
    tm = timing if timing is not None else {}
    clock = time.perf_counter
    u, s, c = parse_key(key)
    inp = UnitInputs()
    inp.key = key
    t0 = clock()
    inp.rows, inp.spot, inp.cutoff_ns = make_chain_rows(spec, u, s, c)
    tm["synth_chain_s"] = tm.get("synth_chain_s", 0.0) + clock() - t0
    cutoff_ns = inp.cutoff_ns
    if history is None or history.key != (spec.seed, spec.shape, u, s) or history.horizon_ns < cutoff_ns:
        t0 = clock()
        history = SessionHistory(spec, u, s, cutoff_ns)
        tm["synth_history_s"] = tm.get("synth_history_s", 0.0) + clock() - t0
    inp.hist = history
    inp.order = apply_order(range(len(inp.rows)), spec.contract_order)
    n = len(inp.rows)
    t0 = clock()
    metas = [chain_contract(spec.shape, i) for i in range(n)]
    inp.prints = _print_stream(spec, u, s, c, history, metas, cutoff_ns)
    tm["synth_prints_s"] = tm.get("synth_prints_s", 0.0) + clock() - t0
    t0 = clock()
    inp.cut = [bisect_right(history.times[i], cutoff_ns) for i in range(n)]
    inp.expiry_days = [m["expiry_days"] for m in metas]
    inp.cover_in = [[(t, True) for t in history.times[i][:inp.cut[i]]] for i in range(n)]
    inp.agg_in = []   # per contract: (price text, size, right, t, quote in force (bid text, ask text, t) or None)
    for i in range(n):
        times, qrecs, rows = history.times[i], history.recs[i], []
        for t, right, price, size, _ in inp.prints[i]:
            k = bisect_right(times, t) - 1
            rows.append((price, size, right, t, None if k < 0 else (qrecs[k][3], qrecs[k][4], qrecs[k][2])))
        inp.agg_in.append(rows)
    recs = []
    for i in range(n):
        recs.extend(history.recs[i][:inp.cut[i]])
    for i in range(n):
        recs.extend(("t", i, p[0], p[2], p[3]) for p in inp.prints[i])
    recs.sort(key=itemgetter(2))  # stable: at equal time quotes precede prints; independent of contract order
    inp.records = recs
    inp.civil_day = CIVIL_DAY_BASE + s
    inp.share_prints = [[(p[1], metas[i]["strike"], inp.civil_day + metas[i]["expiry_days"], inp.spot, p[2], p[3])
                         for p in inp.prints[i]] for i in range(n)]
    tm["synth_prep_s"] = tm.get("synth_prep_s", 0.0) + clock() - t0
    return inp


def compute_from_inputs(spec, inp, timing=None):
    """Result bytes of one unit from prepared inputs. timing (dict, log-only) gets seconds per output family."""
    tm = timing if timing is not None else {}
    clock = time.perf_counter
    hist, rows, cutoff_ns, order = inp.hist, inp.rows, inp.cutoff_ns, inp.order
    cut, expiry_days = inp.cut, inp.expiry_days
    n = len(rows)
    t_all = clock()

    def lap(name, t0):
        tm[name] = tm.get(name, 0.0) + clock() - t0

    t0 = clock()
    chain = chainiv.IVChain([rows[i] for i in order], inp.spot, "0.0300", "0.0100", cutoff_ns)
    lap("iv_build", t0)
    t0 = clock()
    iv = chain.contract_iv()
    lap("iv_contract", t0)
    t0 = clock()
    atm = chain.atm_iv_all()
    lap("atm", t0)
    t0 = clock()
    i30 = chain.iv_30d(30)
    lap("iv30", t0)
    t0 = clock()
    r5s = [oc5(hist.ups[i], hist.sizes[i], cutoff_ns, _OC5) for i in order]
    lap("oc5", t0)
    t0 = clock()
    r6s = [oc6(hist.ups[i], cutoff_ns, 0, _OC6) for i in order]
    lap("oc6", t0)

    # P1 spread / locked / coverage gates at the cutoff, per contract
    t0 = clock()
    p1_spread = []
    stale = quotes.DEFAULT_STALE_LIMIT_NS
    for i in order:
        k = cut[i]
        if k:
            up = hist.ups[i][k - 1]
            bid, ask, age = int(up.bid), int(up.ask), cutoff_ns - up.event_ns
        else:
            bid = ask = None
            age = 0
        reason = quotes.spread_reason(bid, ask, age, stale)
        sv = quotes.quote_spread(bid, ask) if reason is None else None
        cov = windows.QuoteUpdateIndex(inp.cover_in[i]).coverage(cutoff_ns, _OC6.window_ns, _OC6.coverage_min)
        p1_spread.append([rows[i].contract_id, reason] + (list(sv) if sv else [None, None, None]) +
                         [cov.status, cov.reason, cov.regular_update_count])
    lap("p1_spread", t0)

    # touch-policy signing of every print against the quote stream (batched classifier); spread gate of every quote
    t0 = clock()
    sc = quotes.classify_stream(inp.records)
    counts = [[code, sc.codes.count(code)] for code in sorted(set(sc.codes))]
    signing = {"records": len(inp.records), "quotes": sc.quotes, "trades": sc.trades, "code_counts": counts,
               "ask_premium": sc.ask_premium, "bid_premium": sc.bid_premium, "unclassified_premium": sc.unclassified_premium,
               "codes_sha256": hashlib.sha256(bytes(sc.codes) + sc.spread.tobytes() + sc.mid2.tobytes()).hexdigest()}
    lap("p1_signing", t0)

    # per-contract touch-policy aggregate: premium by side, call-ask + put-bid, put-ask + call-bid, shares, status
    t0 = clock()
    p1_agg = []
    for i in order:
        a = quotes.sign_aggregate(inp.agg_in[i])
        p1_agg.append([rows[i].contract_id, a.status, a.reason, a.ask_premium, a.bid_premium, a.unclassified_premium,
                       a.classified_premium, a.call_ask_plus_put_bid_premium, a.put_ask_plus_call_bid_premium,
                       a.unclassified_share_of_total, a.ask_share_of_classified, a.bid_share_of_classified])
    lap("p1_sign_agg", t0)

    # window_end premium windows (explicit end = the cutoff), two window sizes per contract
    t0 = clock()
    p1_window = []
    for i in order:
        idx = windows.WindowIndex(inp.prints[i])
        row = [rows[i].contract_id]
        for w in PRINT_WINDOWS_NS:
            row.append([w] + list(idx.query(w, cutoff_ns)))
        p1_window.append(row)
    lap("p1_window", t0)

    # single-reference F5/F6 shares: whole chain and per expiry
    t0 = clock()
    thr = {"short_dte_max_days": SHORT_DTE_MAX_DAYS, "short_min_share": Fraction(1, 2), "otm_min_share": Fraction(1, 4)}
    allp = [p for i in range(n) for p in inp.share_prints[i]]
    by_exp = {}
    for i in range(n):
        by_exp.setdefault(expiry_days[i], []).extend(inp.share_prints[i])
    p1_shares = {"chain": list(shares.single_reference_shares(allp, inp.civil_day, **thr)),
                 "expiries": [[d] + list(shares.single_reference_shares(by_exp[d], inp.civil_day, **thr)) for d in sorted(by_exp)]}
    lap("p1_shares", t0)

    t0 = clock()
    out_iv = [[cid, r.status, r.reason, r.iv, r.label] for cid, r in sorted(iv.items())]
    out_atm = [[days] + list(a) for days, a in sorted(atm.items())]
    oc5_rows, oc6_rows = [], []
    for i, r5, r6 in zip(order, r5s, r6s):
        cid = rows[i].contract_id
        oc5_rows.append([cid, r5.status, r5.reason, r5.label, r5.numerator, r5.denominator])
        oc6_rows.append([cid, r6.status, r6.reason, r6.label, r6.regular_update_count, _frac(r6.value)])
    oc5_rows.sort()
    oc6_rows.sort()
    p1_spread.sort(key=itemgetter(0))
    p1_window.sort(key=itemgetter(0))
    p1_agg.sort(key=itemgetter(0))
    doc = {"unit": inp.key, "spot": inp.spot, "iv": out_iv, "atm": out_atm, "iv30": list(i30), "oc5": oc5_rows, "oc6": oc6_rows,
           "p1": {"spread": p1_spread, "signing": signing, "sign_aggregate": p1_agg, "window": p1_window, "shares": p1_shares}}
    data = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=_default).encode("utf-8")
    lap("serialize", t0)
    tm["compute_s"] = tm.get("compute_s", 0.0) + clock() - t_all
    return data


def compute_unit(spec, key, history=None, timing=None):
    """Result bytes of one unit. `history` (a SessionHistory covering the cutoff) is an optional cache. `timing`
    (optional dict, log-only, never part of the result) receives input-synthesis and per-family compute seconds."""
    inp = build_inputs(spec, key, history, timing)
    return compute_from_inputs(spec, inp, timing)




class ArbCounter:
    """Counts arb enclosure calls and solves (log-only counters, never part of results)."""

    def __init__(self):
        self.n = {"price_interval": 0, "forward": 0, "bounds": 0, "solves": 0}
        self._real = None

    def __enter__(self):
        self._real = (inverse.price_interval, inverse.forward, inverse.bounds, chainiv.solve)

        def wrap(name, f):
            def g(*a, **k):
                self.n[name] += 1
                return f(*a, **k)
            return g
        inverse.price_interval, inverse.forward, inverse.bounds, chainiv.solve = (
            wrap("price_interval", self._real[0]), wrap("forward", self._real[1]),
            wrap("bounds", self._real[2]), wrap("solves", self._real[3]))
        return self

    def __exit__(self, *exc):
        inverse.price_interval, inverse.forward, inverse.bounds, chainiv.solve = self._real
        return False
