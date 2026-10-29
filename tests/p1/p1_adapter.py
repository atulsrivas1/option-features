"""Test adapter: maps the independently authored P1 rows (p1_cases.json) onto the library API.

Rows are never edited. Each `run_row` returns the library's answer reshaped into the row's
`expected` vocabulary; `compare` reports the first difference. A library reason that has no
mapping is reported as a failure (never silently mapped), so a row cannot pass by accident.

Mapping summary (see docs/FLOW_NAMING_MAP.md for the design-to-repo table):
- spread rows   -> R25 `evaluate` outputs liquidity.spread_bps (phase 1) and
                   liquidity.spread / liquidity.midpoint (phase 2). A quote whose bid and ask
                   are both null is represented as no quote record.
- sign rows     -> option_features.quotes.sign_trade
- aggregate     -> option_features.quotes.sign_aggregate
- window rows   -> option_features.windows.window_premium
- coverage rows -> option_features.windows.quote_count_coverage
- shares rows   -> option_features.shares.single_reference_shares / joint_amounts
- label rows    -> forbidden-word checker over the labels (and the library label constants)
"""
from datetime import date
from decimal import Decimal
from fractions import Fraction
import json
import re
from pathlib import Path

ROWS_PATH = Path(__file__).resolve().parents[2] / "qualification" / "synthetic" / "p1" / "p1_cases.json"
YEAR_NS = 31536000000000000


def load_rows():
    data = json.loads(ROWS_PATH.read_text(encoding="utf-8"))
    return data["rows"]


def fmt(x):
    """Row value format: exact decimal string if terminating, else reduced p/q."""
    x = Fraction(x)
    n, d = x.numerator, x.denominator
    t = d
    for p in (2, 5):
        while t % p == 0:
            t //= p
    if t != 1:
        return "%d/%d" % (n, d)
    k = 0
    while (10 ** k) % d:
        k += 1
    v = abs(n) * (10 ** k // d)
    text = str(v)
    if k:
        text = text.rjust(k + 1, "0")
        text = text[:-k] + "." + text[-k:]
    return ("-" if n < 0 else "") + text


# ---------------------------------------------------------------- spread (R25 evaluate)
LIBRARY_REASON = {
    ("available", "ok"): None,
    ("missing_input", "missing_quote"): "no_quote",
    ("invalid_input", "negative_quote"): "invalid_quote",
    ("invalid_input", "nonpositive_bid"): "invalid_quote",
    ("ineligible_input", "one_sided_quote"): "invalid_quote",
    ("invalid_input", "crossed_quote"): "crossed_market",
    ("invalid_input", "locked_market"): "locked_market",
    ("ineligible_input", "stale_quote"): "stale_quote",
}


def _evaluate_spread(quote, stale_limit_ns, outputs):
    from option_feature_contracts import (
        InputBinding, CivilDateBinding, Definition, Quote, Snapshot, Eligibility,
        SolverConfig, Request, R25_LIMITS,
    )
    from option_features import evaluate
    definition = Definition("c", "u", "call", Decimal("100"), "USD", Decimal("10"), "scalar_underlying", "basis", "european", "certified_vanilla_continuous_carry", "cash", YEAR_NS, YEAR_NS, YEAR_NS, 719528, "UTC", "civil", "1", -1, None, 0, "b")
    quotes = ()
    if quote is not None and not (quote["bid"] is None and quote["ask"] is None):
        quotes = (Quote("c", None,
                        Decimal(quote["bid"]) if quote["bid"] is not None else None,
                        Decimal(quote["ask"]) if quote["ask"] is not None else None,
                        "USD", "per_underlying_payoff_unit", quote["t_rel_ns"], min(quote["t_rel_ns"], 0), 0, "1", "b"),)
    snapshot = Snapshot(
        "option-canonical1", (InputBinding("b", "synthetic-original", "1", "0" * 64, "synthetic", "original synthetic fixtures"),),
        (CivilDateBinding("civil", 0, 719163, "UTC", 0, "b"), CivilDateBinding("civil", YEAR_NS, 719528, "UTC", 0, "b")),
        (definition,), (), (), quotes, (), (), (), (), None,
    )
    request = Request("option-request1", ("c",), tuple(outputs), "computed_only", "exact_only", 0, 0, 719163, "civil", "option-bsm1", "r25-formulas1",
                      Eligibility(stale_limit_ns, YEAR_NS, YEAR_NS), SolverConfig("bisection1", "midpoint", 8.0, 256, 1e-10, 1e-10, 1e-10, 1e-10), R25_LIMITS)
    return evaluate(snapshot, request)


def run_spread(row):
    inputs, params = row["inputs"], row["params"]
    quote, limit = inputs["quote"], params["stale_limit_ns"]
    (bps,) = _evaluate_spread(quote, limit, ["liquidity.spread_bps"])
    key = (bps.status, bps.reason)
    if key not in LIBRARY_REASON:
        return {"error": "unmapped library result %r" % (key,)}
    reason = LIBRARY_REASON[key]
    out = {"status": "available" if reason is None else "unavailable", "reason": reason, "value": None}
    if reason is None:
        out["value"] = {"spread_bps": bps.value}
        try:
            spread, midpoint = _evaluate_spread(quote, limit, ["liquidity.spread", "liquidity.midpoint"])
        except Exception as exc:  # outputs absent in this build
            out["phase2_error"] = "phase 2 (spread, midpoint outputs): %s: %s" % (type(exc).__name__, exc)
        else:
            out["value"]["spread"] = spread.value
            out["value"]["midpoint"] = midpoint.value
    return out


def _compare_spread(row, got):
    exp = row["expected"]
    if (got["status"], got["reason"]) != (exp["status"], exp["reason"]):
        return "status/reason %r != %r" % ((got["status"], got["reason"]), (exp["status"], exp["reason"]))
    if exp["value"] is not None:
        want = float(Fraction(exp["value"]["spread_bps"]))
        if got["value"]["spread_bps"] != want:
            return "spread_bps %r != %r" % (got["value"]["spread_bps"], want)
        if "phase2_error" in got:
            return got["phase2_error"]
        for name in ("spread", "midpoint"):
            want = float(Fraction(exp["value"][name]))
            if got["value"][name] != want:
                return "%s %r != %r" % (name, got["value"][name], want)
    return None


# ---------------------------------------------------------------- sign
def _quote_arg(q):
    if q is None:
        return None
    return (q["bid"], q["ask"], q["t_rel_ns"])


def run_sign(row):
    from option_features import quotes
    inputs, params = row["inputs"], row["params"]
    kwargs = {}
    if "inside_spread" in params:
        kwargs["inside_spread"] = params["inside_spread"]
    if "epsilon" in params:
        kwargs["epsilon"] = params["epsilon"]
    if "max_quote_age_ns" in params:
        kwargs["max_quote_age_ns"] = params["max_quote_age_ns"]
    trade = inputs["trade"]
    r = quotes.sign_trade(trade["price"], _quote_arg(inputs["quote"]), trade["t_rel_ns"], **kwargs)
    return {"status": r.status, "reason": r.reason, "side": r.side, "label": r.label, "value": None}


def _compare_sign(row, got):
    exp = row["expected"]
    if exp["status"] == "not_asserted":
        return None
    for name in ("status", "reason", "side", "label"):
        if got[name] != exp[name]:
            return "%s %r != %r" % (name, got[name], exp[name])
    return None


def run_aggregate(row):
    from option_features import quotes
    params = row["params"]
    trades = [(t["price"], t["size"], t["right"], t["t_rel_ns"], _quote_arg(t["quote"])) for t in row["inputs"]["trades"]]
    a = quotes.sign_aggregate(trades, inside_spread=params["inside_spread"], epsilon=params["epsilon"], max_quote_age_ns=params["max_quote_age_ns"])
    value = {}
    for name in ("ask_premium", "bid_premium", "unclassified_premium", "classified_premium", "call_ask_plus_put_bid_premium",
                 "put_ask_plus_call_bid_premium", "unclassified_share_of_total", "ask_share_of_classified", "bid_share_of_classified"):
        v = getattr(a, name)
        value[name] = None if v is None else fmt(v)
    return {"status": a.status, "reason": a.reason, "value": value, "labels": dict(a.labels)}


def _compare_aggregate(row, got):
    exp = row["expected"]
    for name in ("status", "reason"):
        if got[name] != exp[name]:
            return "%s %r != %r" % (name, got[name], exp[name])
    if got["value"] != exp["value"]:
        return "value %r != %r" % (got["value"], exp["value"])
    if got["labels"] != exp["labels"]:
        return "labels %r != %r" % (got["labels"], exp["labels"])
    return None


# ---------------------------------------------------------------- window, coverage
def run_window(row):
    from option_features import windows
    prints = [(p["t_rel_ns"], p["right"], p["price"], p["size"], p["multiplier"]) for p in row["inputs"]["prints"]]
    params = row["params"]
    w = windows.window_premium(prints, params["window_ns"], params.get("window_end_ns"))
    return {"status": "available", "reason": None, "value": {
        "total_premium": fmt(w.total_premium), "call_premium": fmt(w.call_premium), "put_premium": fmt(w.put_premium),
        "window_start_ns": w.window_start_ns, "window_end_ns": w.window_end_ns,
        "included_count": w.included_count, "excluded_nonstandard_count": w.excluded_nonstandard_count}}


def run_coverage(row):
    from option_features import windows
    params = row["params"]
    updates = [(u["t_rel_ns"], u["cond"] == "regular") for u in row["inputs"]["updates"]]
    c = windows.quote_count_coverage(updates, 0, params["window_ns"], params["min_regular_updates"])
    return {"status": c.status, "reason": c.reason, "value": {"regular_update_count": c.regular_update_count}, "blocks": list(c.blocks)}


def _compare_plain(row, got):
    exp = row["expected"]
    for name in ("status", "reason", "value", "blocks"):
        if name in exp and got.get(name) != exp[name]:
            return "%s %r != %r" % (name, got.get(name), exp[name])
    return None


# ---------------------------------------------------------------- shares
def _day(text):
    return None if text is None else date.fromisoformat(text).toordinal()


def _share_prints(row):
    return [(p["right"], p["strike"], _day(p["expiry"]), p["spot"], p["price"], p["size"]) for p in row["inputs"]["prints"]]


def _measure(m):
    return {"status": m.status, "reason": m.reason,
            "premium": None if m.premium is None else fmt(m.premium),
            "share": None if m.share is None else fmt(m.share),
            "coverage": fmt(m.coverage), "fired": m.fired, "lower_bound": m.lower_bound, "label": m.label}


def run_shares(row):
    from option_features import shares
    params = row["params"]
    r = shares.single_reference_shares(_share_prints(row), _day(row["inputs"]["civil_date"]),
                                       short_dte_max_days=params["short_dte_max_days"],
                                       short_min_share=params.get("short_min_share"),
                                       otm_min_share=params.get("otm_min_share"))
    return {"status": r.status, "reason": r.reason, "value": {
        "total_premium": fmt(r.total_premium), "short_dte": _measure(r.short_dte), "otm": _measure(r.otm),
        "joint_short_dte": _measure(r.joint_short_dte), "joint_otm": _measure(r.joint_otm)}}


def run_joint(row):
    from option_features import shares
    j = shares.joint_amounts(_share_prints(row), _day(row["inputs"]["civil_date"]),
                             short_dte_max_days=row["params"]["short_dte_max_days"])
    return {"status": "available", "reason": None, "value": {
        "joint_short_premium": fmt(j.joint_short_premium), "joint_otm_premium": fmt(j.joint_otm_premium),
        "reference_premium": fmt(j.reference_premium)}}


# ---------------------------------------------------------------- labels
def forbidden_hits(labels, forbidden):
    words = set()
    for label in labels:
        words.update(w.lower() for w in re.findall(r"[A-Za-z]+", label))
    return [w for w in forbidden if w in words]


def run_label(row):
    from option_features import quotes
    params = row["params"]
    labels = row["inputs"]["labels"]
    hits = forbidden_hits(labels, params["forbidden_words"])
    allowed = all(l in params["allowed_labels"] for l in labels)
    if row["id"] == "L01":
        # the live check: the labels the library emits are exactly the allowed set and carry no forbidden word
        emitted = [quotes.ASK_LABEL, quotes.BID_LABEL]
        if sorted(emitted) != sorted(params["allowed_labels"]) or forbidden_hits(emitted, params["forbidden_words"]):
            return {"error": "library labels %r violate the label rule" % (emitted,)}
    return {"status": "available", "reason": None, "value": {"labels_allowed_only": allowed, "forbidden_word_hits": hits}}


DISPATCH = {
    "spread": (run_spread, _compare_spread),
    "sign": (run_sign, _compare_sign),
    "sign_aggregate": (run_aggregate, _compare_aggregate),
    "window_premium": (run_window, _compare_plain),
    "quote_coverage_gate": (run_coverage, _compare_plain),
    "single_ref_shares": (run_shares, _compare_plain),
    "joint_amounts": (run_joint, _compare_plain),
    "label_check": (run_label, _compare_plain),
}


def check_row(row):
    """Returns None when the row passes, else a short failure text."""
    run, compare = DISPATCH[row["inputs"]["op"]]
    try:
        got = run(row)
    except Exception as exc:
        return "%s: %s" % (type(exc).__name__, exc)
    if "error" in got:
        return got["error"]
    return compare(row, got)
