"""Test adapter: maps the independently authored M1 OC rows (m1_oc_cases.json) onto the library API.

Rows are never edited. `run_row` calls the library (imports are inside the call, so on code without
the OC modules every row fails individually instead of the whole suite failing at import) and
`check_row` reports the first difference against the row's `expected`.

Mapping: OC5 -> option_features.imbalance.oc5 (QuoteUpdate + QuoteSize records);
         OC6 -> option_features.spreadwin.oc6. A structural error is an OCStructuralError with a code.
Quote bid and ask are passed exactly as the row holds them (a JSON float is a malformed type).
Decimals in rows are 4-place roundings of the exact rational (half up); both are checked.
"""
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import json
from pathlib import Path

ROWS_PATH = Path(__file__).resolve().parents[2] / "qualification" / "synthetic" / "m1" / "m1_oc_cases.json"


def load_rows():
    return json.loads(ROWS_PATH.read_text(encoding="utf-8"))["rows"]


def _updates(quote_rows):
    from option_features.quotehist import QuoteUpdate
    return [QuoteUpdate(q["rev"], q["event_ns"], q["known_at_ns"], q["bid"], q["ask"],
                        q["condition"] == "regular", q.get("seq")) for q in quote_rows]


def run_row(row):
    from option_features.quotehist import OCStructuralError, QuoteSize
    inputs, req = row["inputs"], row["request"]
    try:
        if row["op"] == "oc5":
            from option_features.imbalance import OC5Params, oc5
            sizes = [QuoteSize(s["rev"], s["bid_size"], s["ask_size"]) for s in inputs["sizes"]]
            params = OC5Params(req["imbalance_threshold"], req["stale_limit_ns"])
            return oc5(_updates(inputs["quotes"]), sizes, inputs["T_ns"], params,
                       consolidated=inputs["feed_kind"] == "consolidated", standard=inputs["contract_standard"])
        from option_features.spreadwin import OC6Params, oc6
        params = OC6Params(req["window_ns"], req["stale_limit_ns"], req["coverage_min"], req["narrower_max"], req["wider_min"])
        return oc6(_updates(inputs["quotes"]), inputs["T_ns"], req["session_open_ns"], params,
                   consolidated=inputs["feed_kind"] == "consolidated", standard=inputs["contract_standard"])
    except OCStructuralError as exc:
        return exc


def _dec(x):
    text = str((Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
    return "0.0000" if text == "-0.0000" else text


def check_row(row):
    """None if the library result matches the row, else a one-line description of the first difference."""
    from option_features.quotehist import OCStructuralError
    exp = row["expected"]
    got = run_row(row)
    if isinstance(got, OCStructuralError):
        if exp["status"] != "structural_error":
            return "unexpected structural error %s" % got.code
        return None if got.code == exp["code"] else "code %r != %r" % (got.code, exp["code"])
    if exp["status"] == "structural_error":
        return "expected structural error %s, got %s" % (exp["code"], got.status)
    if got.status != exp["status"] or got.reason != exp["reason"]:
        return "status/reason %r != %r" % ((got.status, got.reason), (exp["status"], exp["reason"]))
    if exp["status"] == "unavailable":
        return None if got.value is None else "value on unavailable result"
    if got.label != exp["label"]:
        return "label %r != %r" % (got.label, exp["label"])
    want = Fraction(exp["value"]["exact"])
    if got.value != want:
        return "value %s != %s" % (got.value, want)
    if _dec(got.value) != exp["value"]["decimal"]:
        return "decimal %s != %s" % (_dec(got.value), exp["value"]["decimal"])
    for name, text in (exp.get("aux") or {}).items():
        have = getattr(got, name)
        if have != Fraction(text):
            return "%s %s != %s" % (name, have, text)
    return None
