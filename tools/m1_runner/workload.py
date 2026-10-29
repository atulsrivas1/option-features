"""Unit definition and the pure per-unit computation for the process-pool runner.

Label: synthetic workload, relative engineering budget. Synthetic data only; no claim about recorded data.

A unit is (underlying, session, cutoff). One unit computes, for one size-M style chain at one cutoff:
chain IV outputs (contract IV for every contract, ATM IV for every expiry, 30-day IV: option_features.chainiv)
and OC5 and OC6 for every contract (option_features.imbalance, spreadwin). Units share no state: a unit's result
bytes are a pure function of (spec, unit). A worker may cache the quote history of the session it is working on
(derived data, a deterministic prefix of a stream); a test proves the cache never changes a result byte.

Inputs. Chain layout, quote streams and cutoff grid come from qualification/synthetic/perf/gen_perf_workloads.py
(seed 20261029, read only). Chain IV inputs are coherent Black-Scholes smile mids (as in tools/m1_chain_benchmark.py,
B6) with a per-unit spot and about 7 percent of contracts gated by construction (no quote, crossed, stale, bid 0);
OC5/OC6 inputs are the quote streams of the generator (per contract and session), evaluated at the cutoff.
Shape "T" is a tiny 40-contract chain for CI tests; "S", "M", "L" are the generator sizes.

Result bytes: canonical JSON (sorted keys, no spaces, UTF-8), contracts sorted by contract id. No worker count,
id, timing or completion order is ever part of them.
"""
import hashlib
import json
import math
import sys
from collections import namedtuple
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "qualification" / "synthetic" / "perf")]
import gen_perf_workloads as gen  # noqa: E402
from option_features import chainiv, inverse  # noqa: E402
from option_features.imbalance import OC5Params, oc5  # noqa: E402
from option_features.quotehist import QuoteSize, QuoteUpdate, as_ticks  # noqa: E402
from option_features.spreadwin import OC6Params, oc6  # noqa: E402

NS = 10 ** 9
RATE, DIV = 0.03, 0.01
TINY = {"expiries_days": [7, 28, 35, 63], "strikes": 5}
SHAPES = ("T", "S", "M", "L")
_SpecBase = namedtuple("Spec", "seed shape underlyings sessions cutoffs contract_order gating",
                       defaults=(gen.DEFAULT_SEED, "M", tuple(gen.UNDERLYINGS), tuple(range(1, gen.SESSIONS + 1)),
                                 tuple(range(gen.CUTOFFS_PER_SESSION)), "natural", "mixed"))


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
    prices and a rev -> QuoteSize dict. A deterministic prefix of the generator stream (the generator walks the
    price forward, so stopping early gives the same prefix)."""
    __slots__ = ("key", "horizon_ns", "ups", "sizes", "n_updates")

    def __init__(self, spec, u, s, horizon_ns):
        self.key, self.horizon_ns = (spec.seed, spec.shape, u, s), horizon_ns
        self.ups, self.sizes, total = [], [], 0
        stream_size = "M" if spec.shape == "T" else spec.shape
        for i in range(chain_size(spec.shape)):
            ups, sizes = [], {}
            for rev, q in enumerate(gen.quote_stream_for_contract(spec.seed, stream_size, u, s, i), 1):
                if q["t_rel_ns"] > horizon_ns:
                    break
                ups.append(QuoteUpdate(rev, q["t_rel_ns"], q["t_rel_ns"], as_ticks(q["bid"]), as_ticks(q["ask"]), True, None))
                sizes[rev] = QuoteSize(rev, q["bid_size"], q["ask_size"])
            self.ups.append(ups)
            self.sizes.append(sizes)
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


def compute_unit(spec, key, history=None):
    """Result bytes of one unit. `history` (a SessionHistory covering the cutoff) is an optional cache."""
    u, s, c = parse_key(key)
    rows, spot, cutoff_ns = make_chain_rows(spec, u, s, c)
    if history is None or history.key != (spec.seed, spec.shape, u, s) or history.horizon_ns < cutoff_ns:
        history = SessionHistory(spec, u, s, cutoff_ns)
    order = apply_order(range(len(rows)), spec.contract_order)
    chain = chainiv.IVChain([rows[i] for i in order], spot, "0.0300", "0.0100", cutoff_ns)
    iv = chain.contract_iv()
    atm = chain.atm_iv_all()
    i30 = chain.iv_30d(30)
    out_iv = [[cid, r.status, r.reason, r.iv, r.label] for cid, r in sorted(iv.items())]
    out_atm = [[days] + list(a) for days, a in sorted(atm.items())]
    oc5_rows, oc6_rows = [], []
    for i in order:
        cid = rows[i].contract_id
        r5 = oc5(history.ups[i], history.sizes[i], cutoff_ns, _OC5)
        r6 = oc6(history.ups[i], cutoff_ns, 0, _OC6)
        oc5_rows.append([cid, r5.status, r5.reason, r5.label, r5.numerator, r5.denominator])
        oc6_rows.append([cid, r6.status, r6.reason, r6.label, r6.regular_update_count, _frac(r6.value)])
    oc5_rows.sort()
    oc6_rows.sort()
    doc = {"unit": key, "spot": spot, "iv": out_iv, "atm": out_atm, "iv30": list(i30), "oc5": oc5_rows, "oc6": oc6_rows}
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=_default).encode("utf-8")


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
