"""M3a common (story S01): closed reason and code sets, half-even 8-decimal rounding, 10^-8 integer storage form,
labels sort (R-132), param echo (R-154, R-158, R-184), the M3a result envelope with `frame`, canonical bytes.

First owner of author2 m3a_cases_units.json M3A-U-001..021. The rank rows (M3A-1) belong to the rank kernel (S08) for
their rank part; here each U row is checked at ITEM level: the number-form items S01 owns (x text, stored units,
skew points, lower_share form). One test method per row id so a failing row is named.

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12
"""
import json
import random
import time
import unittest
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction

import m3a_harness as H
from option_features import __version__
from option_features import m3a_common as C

# Closed reason set: docs/m3a/M3A_CAPABILITY_MATRIX.md section 5 (surface reasons), written out independently.
SURFACE = ("no_atm_strike", "no_bracketing_expiry", "price_out_of_bounds", "upper_asymptote", "sigma_cap",
           "precision_exhausted", "bound_precision", "iteration_budget", "insufficient_history", "session_not_complete",
           "zero_denominator", "no_eligible_contract", "no_delta_bracket", "low_surface_coverage",
           "fewer_than_two_expiries", "no_prior_reading", "zero_range_history")
CONTRACT = ("no_quote", "excluded_condition", "invalid_quote", "crossed_market", "locked_market", "stale_quote",
            "american_itm", "style_unknown")
# Structural codes: docs/m3a/M3A_IO_CONTRACT.md section 4 (request 22 distinct codes in 18 positions, history append and
# load, snapshot, text load, view read); `invalid_param` is NOT a code (contract-codes decision).
REQUEST_CODES = ("bad_cutoff", "bad_spot", "bad_rate", "invalid_mode", "invalid_lane", "bad_expiry", "unknown_right",
                 "duplicate_contract", "bad_strike", "malformed_type", "cutoff_mismatch", "tenor_not_allowed",
                 "delta_not_allowed", "iv_form_not_allowed", "convention_not_allowed", "threshold_required",
                 "threshold_out_of_range", "invalid_direction", "minute_out_of_range", "prior_not_before_cutoff",
                 "convention_mismatch", "delayed_feed_tag")
STORE_CODES = ("lane_mismatch", "session_not_in_calendar", "record_length_mismatch", "non_monotone_grid",
               "duplicate_session", "out_of_order_append", "snapshot_bad_magic", "snapshot_length_mismatch",
               "snapshot_hash_mismatch", "trailer_missing", "trailer_count_mismatch", "trailer_hash_mismatch",
               "invalid_session_window")


def _ref_units(x):
    """Independent reference: exact decimal expansion of the binary64, quantised half-even at 8 places."""
    return int(Decimal(x).quantize(Decimal("1e-8"), rounding=ROUND_HALF_EVEN).scaleb(8))


def _ref_text(u):
    s = "-" if u < 0 else ""
    return "%s%d.%08d" % (s, abs(u) // 10 ** 8, abs(u) % 10 ** 8)


class Sets(unittest.TestCase):
    def test_surface_reasons_closed(self):
        self.assertEqual(tuple(C.SURFACE_REASONS), SURFACE)
        self.assertEqual(len(set(C.SURFACE_REASONS)), len(C.SURFACE_REASONS))

    def test_contract_reasons_are_not_surface_reasons(self):
        self.assertEqual(tuple(C.CONTRACT_REASONS), CONTRACT)
        self.assertFalse(set(C.CONTRACT_REASONS) & set(C.SURFACE_REASONS))

    def test_insufficient_window_not_used(self):
        self.assertNotIn("insufficient_window", C.SURFACE_REASONS)

    def test_codes_closed(self):
        self.assertEqual(set(C.CODES), set(REQUEST_CODES) | set(STORE_CODES))
        self.assertEqual(len(set(C.CODES)), len(C.CODES))
        self.assertNotIn("invalid_param", C.CODES)
        self.assertFalse(set(C.CODES) & set(C.SURFACE_REASONS))

    def test_statuses(self):
        self.assertEqual(tuple(C.STATUSES), ("available", "unavailable", "invalid_input"))

    def test_every_code_and_reason_in_the_row_files_is_in_the_sets(self):
        codes, reasons = set(), set()
        for s in H.SETS:
            for fn in H.row_files(s):
                for r in H.raw_rows(s, fn):
                    e = r.get("expected")
                    if isinstance(e, dict):
                        if e.get("code"):
                            codes.add(e["code"])
                        if e.get("reason"):
                            reasons.add(e["reason"])
        self.assertLessEqual(codes, set(C.CODES))
        self.assertLessEqual(reasons, set(C.SURFACE_REASONS))


class Rounding(unittest.TestCase):
    def test_ties_half_even(self):
        # 2^-9 = 0.001953125 is an exact tie at 8 decimals
        self.assertEqual(C.round_units(1 / 512), 195312)
        self.assertEqual(C.round_units(3 / 512), 585938)
        self.assertEqual(C.round_units(5 / 512), 976562)
        self.assertEqual(C.round_units(-1 / 512), -195312)
        self.assertEqual(C.round_units(-3 / 512), -585938)
        self.assertEqual(C.round_units(0.0), 0)

    def test_near_ties_not_ties(self):
        self.assertEqual(C.round_units(0.123456785), _ref_units(0.123456785))
        self.assertEqual(C.round_units(0.30000000000000004), 30000000)

    def test_zero_and_negative_zero(self):
        self.assertEqual(C.round_text(4e-9), "0.00000000")
        self.assertEqual(C.round_text(-4e-9), "0.00000000")
        self.assertEqual(C.round_text(-0.0), "0.00000000")
        self.assertEqual(C.units_text(0), "0.00000000")

    def test_text_forms(self):
        self.assertEqual(C.units_text(-1000001), "-0.01000001")
        self.assertEqual(C.units_text(1234567890123), "12345.67890123")
        self.assertEqual(C.round_text(5.0), "5.00000000")
        self.assertEqual(C.round_text(7), "7.00000000")

    def test_int_input_and_units_constant(self):
        self.assertEqual(C.UNITS, 10 ** 8)
        self.assertEqual(C.round_units(3), 300000000)

    def test_rejects_bool_nonfinite_and_other_types(self):
        for bad in (True, float("nan"), float("inf"), float("-inf"), "0.1", None, Fraction(1, 3)):
            with self.assertRaises((TypeError, ValueError)):
                C.round_units(bad)

    def test_random_against_decimal_reference(self):
        rnd = random.Random(20261030)
        for _ in range(20000):
            m = rnd.choice((0.0, 1e-6, 1e-3, 0.5, 3.0, 100.0))
            x = rnd.uniform(-1, 1) * m
            self.assertEqual(C.round_units(x), _ref_units(x), x)

    def test_random_near_ties_against_decimal_reference(self):
        rnd = random.Random(7)
        for _ in range(20000):
            k = rnd.randrange(-10 ** 9, 10 ** 9)
            x = (k + 0.5) / 10 ** 8                 # decimal tie, but the binary64 is just above or below it
            self.assertEqual(C.round_units(x), _ref_units(x), x)
            y = (rnd.randrange(-2 ** 20, 2 ** 20) * 2 + 1) / 2 ** 10   # binary ties at 2^-10 multiples
            self.assertEqual(C.round_units(y), _ref_units(y), y)

    def test_scaled(self):
        self.assertEqual(C.round_scaled_units(1 / 512, 100), 19531250)        # 0.1953125 exactly, scaled exactly
        self.assertEqual(C.round_scaled_units(0.31 - 0.2, 100), 1100000000)
        self.assertEqual(C.round_scaled_units(-1 / 512, 1), -195312)

    def test_skew_rounded_once_from_unrounded_floats(self):
        # rounding the parts first would give 19999999 (U-010)
        put, call = 0.3000000049, 0.1000000051
        self.assertEqual(C.skew_units(put, call), 20000000)
        self.assertEqual(C.round_units(put) - C.round_units(call), 19999999)

    def test_skew_points_one_rounding(self):
        self.assertEqual(C.skew_points_units(0.31, 0.2), 1100000000)
        self.assertEqual(C.skew_points_units(0.5, 0.498046875), 19531250)       # R-181: 0.1953125 points, one rounding
        self.assertEqual(C.skew_points_units(0.25, 0.25), 0)

    def test_ratio_text(self):
        self.assertEqual(C.ratio_text(0, 60), 0)
        self.assertEqual(C.ratio_text(60, 60), 1)
        self.assertEqual(C.ratio_text(75, 100), "3/4")
        self.assertEqual(C.ratio_text(25, 100), "1/4")
        self.assertEqual(C.ratio_text(16, 26), "8/13")
        self.assertIs(type(C.ratio_text(4, 2)), int)
        with self.assertRaises(ValueError):
            C.ratio_text(1, 0)


class Labels(unittest.TestCase):
    def test_sorted_ascii_with_delayed(self):
        a = "approximate: European model on an American-style contract"
        self.assertEqual(C.sort_labels(["exact-model", a, "delayed"]), [a, "delayed", "exact-model"])

    def test_dedup_and_empty(self):
        self.assertEqual(C.sort_labels(["exact-model", "exact-model"]), ["exact-model"])
        self.assertEqual(C.sort_labels([]), [])
        self.assertEqual(C.sort_labels(()), [])


class Echo(unittest.TestCase):
    def test_defaults_filled_and_only_named(self):
        got = C.params_echo({"mode": "close"}, ("mode", "iv_form", "delta_convention", "min_sessions"))
        self.assertEqual(got, {"mode": "close", "iv_form": "atm", "delta_convention": "spot", "min_sessions": 20})

    def test_given_values_win(self):
        got = C.params_echo({"iv_form": "30d", "delta_convention": "forward"}, ("iv_form", "delta_convention"))
        self.assertEqual(got, {"iv_form": "30d", "delta_convention": "forward"})

    def test_defaults_table(self):
        d = C.DEFAULTS
        self.assertEqual((d["stale_limit_ns"], d["min_sessions"], d["max_sessions"], d["prior_sessions"]),
                         (10 * 10 ** 9, 20, 252, 1))
        self.assertEqual((d["iv_form"], d["delta_convention"], d["mode"], d["lane"]),
                         ("atm", "spot", "intraday", "stock"))

    def test_missing_param_without_default_is_omitted_not_invented(self):
        self.assertEqual(C.params_echo({"x": 5}, ("x", "tail")), {"x": 5})

    def test_key_order_is_sorted(self):
        got = C.params_echo({"x": 5, "tail": "top", "mode": "close"}, ("x", "tail", "mode"))
        self.assertEqual(list(got), sorted(got))


class Envelope(unittest.TestCase):
    def test_key_order(self):
        self.assertEqual(tuple(C.KEY_ORDER), ("output_id", "series_id", "session_id", "evaluation_ns", "status",
                                              "reason", "code", "value", "fired", "params", "coverage", "labels",
                                              "lane", "version"))

    def test_available_line(self):
        r = C.Result.available("M3A-7", "SYN1/stock/skew25", "2024-02-26", 5, {"skew_points": "5.00000000"},
                               fired=True, params={"at_least": 5}, coverage=None, labels=["exact-model"],
                               lane="stock")
        line = C.canonical_line(r)
        self.assertEqual(line, '{"output_id":"M3A-7","series_id":"SYN1/stock/skew25","session_id":"2024-02-26",'
                               '"evaluation_ns":5,"status":"available","reason":null,"code":null,'
                               '"value":{"skew_points":"5.00000000"},"fired":true,"params":{"at_least":5},'
                               '"coverage":null,"labels":["exact-model"],"lane":"stock","version":"%s"}' % __version__)

    def test_unavailable_has_null_value_fired_and_empty_labels(self):
        r = C.Result.unavailable("M3A-0", None, None, 9, "no_eligible_contract")
        w = json.loads(C.canonical_line(r))
        self.assertEqual((w["status"], w["reason"], w["code"], w["value"], w["fired"], w["labels"]),
                         ("unavailable", "no_eligible_contract", None, None, None, []))

    def test_invalid_has_code_and_null_value(self):
        r = C.Result.invalid("M3A-0", "bad_spot", None, None, 9)
        w = json.loads(C.canonical_line(r))
        self.assertEqual((w["status"], w["reason"], w["code"], w["value"], w["fired"], w["labels"]),
                         ("invalid_input", None, "bad_spot", None, None, []))

    def test_unknown_reason_or_code_refused(self):
        with self.assertRaises(ValueError):
            C.Result.unavailable("M3A-0", None, None, 9, "made_up")
        with self.assertRaises(ValueError):
            C.Result.unavailable("M3A-0", None, None, 9, "insufficient_window")
        with self.assertRaises(ValueError):
            C.Result.invalid("M3A-0", "invalid_param", None, None, 9)
        with self.assertRaises(ValueError):
            C.Result.invalid("M3A-0", "no_atm_strike", None, None, 9)

    def test_labels_sorted_on_construction(self):
        r = C.Result.available("M3A-1", "s", "d", 1, {}, labels=["exact-model", "delayed"])
        self.assertEqual(r.labels, ["delayed", "exact-model"])

    def test_frame_follows_value_and_only_when_set(self):
        frame = {"expiries": {"30": {"status": "available"}}}
        r = C.Result.available("M3A-0", None, None, 1, None, frame=frame, labels=["exact-model"])
        w = json.loads(C.canonical_line(r))
        keys = list(w)
        self.assertEqual(keys[keys.index("value") + 1], "frame")
        self.assertEqual(w["frame"], frame)
        r2 = C.Result.available("M3A-7", None, None, 1, {})
        self.assertNotIn("frame", json.loads(C.canonical_line(r2)))

    def test_ascii_and_compact(self):
        line = C.canonical_line(C.Result.available("M3A-1", "sé", "d", 1, {}))
        self.assertTrue(line.isascii())
        self.assertNotIn(" ", line.replace("s\\u00e9", ""))

    def test_canonical_bytes_sorted_lf_not_completion_order(self):
        a = C.Result.available("M3A-7", "b", "2024-01-03", 2, {})
        b = C.Result.available("M3A-1", "z", "2024-01-03", 2, {})
        c = C.Result.available("M3A-1", "a", "2024-01-04", 1, {})
        d = C.Result.available("M3A-1", "a", "2024-01-03", 3, {})
        out = C.canonical_bytes([a, b, c, d])
        lines = out.split(b"\n")
        self.assertEqual(lines[-1], b"")
        order = [(json.loads(x)["output_id"], json.loads(x)["series_id"], json.loads(x)["session_id"])
                 for x in lines[:-1]]
        self.assertEqual(order, [("M3A-1", "a", "2024-01-03"), ("M3A-1", "a", "2024-01-04"),
                                 ("M3A-1", "z", "2024-01-03"), ("M3A-7", "b", "2024-01-03")])
        self.assertEqual(C.canonical_bytes([d, c, b, a]), out)
        self.assertNotIn(b"\r", out)
        self.assertEqual(C.canonical_bytes([]), b"")

    def test_params_default_echo_roundtrip_is_stable(self):
        p = C.params_echo({"x": 5, "tail": "top"}, ("x", "tail", "min_sessions", "max_sessions"))
        r = C.Result.available("M3A-1", "s", "d", 1, {}, params=p)
        self.assertEqual(json.loads(C.canonical_line(r))["params"],
                         {"max_sessions": 252, "min_sessions": 20, "tail": "top", "x": 5})


class Budget(unittest.TestCase):
    """M3A-B4 envelope overhead and M3A-B9 canonical bytes: relative engineering budget on a synthetic workload.
    Developer smoke only (the Tester runs the repeats); min of 5 repeats to ignore scheduler noise."""

    def test_envelope_overhead_and_rounding_speed(self):
        n = 20000
        best_env = best_round = 1e9
        for _ in range(5):
            t = time.perf_counter()
            rs = [C.Result.available("M3A-8", "SYN1/stock/skew25", "2024-02-26", i, {"skew_points": "5.00000000"},
                                     fired=True, params={"at_least": 5}, labels=["exact-model"]) for i in range(n)]
            C.canonical_bytes(rs)
            best_env = min(best_env, (time.perf_counter() - t) / n)
            t = time.perf_counter()
            for i in range(n):
                C.round_units(0.123456789 + i * 1e-7)
            best_round = min(best_round, (time.perf_counter() - t) / n)
        self.assertLess(best_env, 100e-6, "envelope build + canonical line per result (budget 100 us of the 1 ms/name)")
        self.assertLess(best_round, 5e-6, "one rounding (budget 5 us)")


# ---- the 21 unit rows (first owner S01), item level -------------------------------------------------------------

def _units_check(self, row):
    inp, exp = row["inputs"], row["expected"]
    out = row["output_id"]
    if out == "M3A-1":                       # scalar rank rows: x text and lower_share form
        v = exp["value"]
        u = C.round_units(inp["now"]["float"])
        self.assertEqual(v["x"], C.units_text(u))
        self.assertEqual(v["x"], _ref_text(_ref_units(inp["now"]["float"])))
        self.assertEqual(v["lower_share"], C.ratio_text(v["rank_le"], v["n"]))
    elif out == "M3A-8":                     # derived series: difference of the unrounded floats, rounded once
        now = inp["now"]
        u = C.skew_units(now["put25_iv"], now["call25_iv"])
        self.assertEqual(exp["value"]["x"], C.units_text(u))
        self.assertEqual(u, _ref_units(now["put25_iv"] - now["call25_iv"]))
    elif out == "M3A-7":                     # R-181: points = full precision x100, then one rounding
        v = exp["value"]
        self.assertEqual(C.units_text(C.skew_points_units(inp["put25_iv"], inp["call25_iv"])), v["skew_points"])
        self.assertEqual(C.skew_units(inp["put25_iv"], inp["call25_iv"]), v["skew25_units"])
    elif out == "M3A-12":                    # stored integer form
        v = exp["value"]
        u = C.round_units(inp["float"])
        self.assertEqual((C.units_text(u), u), (v["text"], v["units"]))
    else:
        self.fail("unexpected output " + out)
    self.assertEqual(exp["status"], "available")


def _make(row):
    def test(self):
        _units_check(self, row)
    return test


class UnitRows(unittest.TestCase):
    pass


for _row in H.rows("author2", "m3a_cases_units.json"):
    setattr(UnitRows, "test_" + _row["id"].replace("-", "_"), _make(_row))


class UnitRowCount(unittest.TestCase):
    def test_21_rows(self):
        ids = [r["id"] for r in H.rows("author2", "m3a_cases_units.json")]
        self.assertEqual(ids, ["M3A-U-%03d" % n for n in range(1, 22)])


if __name__ == "__main__":
    unittest.main()
