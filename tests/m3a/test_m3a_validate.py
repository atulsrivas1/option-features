"""S09: structural validation wrappers (`option_features.m3a_validate`).

First owner of author4 M3A-STRUCT-001..157, M3A-STRUCT-AUX-001..045, M3A-LANE-001..006 and author1 COV-35..37 and
D25-V1..V7 (218 rows; build plan section 3a). One test method per row id. Expectations come only from the row files
and, for the Developer unit tests below, from docs/m3a/M3A_IO_CONTRACT.md section 4 and the rulings (R-66 to R-70,
R-100 to R-102, R-107, R-120, R-149, R-152, R-155, R-160, R-164, R-168, R-174, R-185 and the contract-codes decision).

The four lane-read rows (M3A-LANE-003..006) read history through `m3a_history.scalar_baseline`, which story S02 owns:
they are skipped, naming S02, until that module is merged (then wired here in a follow-up).

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12.
"""
import time
import unittest
from fractions import Fraction

import adapt_m3a_validate as A
import m3a_harness as H
from option_features import m3a_validate as V
from option_features.chainiv import ChainContract
from option_features.flowgrid import Calendar
from option_features.m3a_common import CODES

CUTOFF = 1_000_000_000_000


# ---------------------------------------------------------------------------------------------------------------- rows

def _check_row(tc, row):
    e = row["expected"]
    inputs, params = row["inputs"], row.get("params") or {}
    entry = inputs.get("entry", "request")
    want = e.get("code") if e.get("status") == "invalid_input" else None
    if e.get("status") == "invalid_input":
        tc.assertEqual(e.get("first_failing_code", want), want)
    if entry == "request":
        got = A.request(inputs, params)
    elif entry == "view_read":
        got = A.view_read(inputs, params)
    elif entry in ("history_append", "history_load"):
        got, idx = A.history_ops(inputs)
        if want is not None:
            tc.assertEqual(idx, e.get("op_index"), "op_index")
    elif entry == "snapshot_load":
        got = A.snapshot_load(inputs)
    elif entry == "text_load":
        got = A.text_load(inputs)
    else:
        raise AssertionError("unknown entry %r" % entry)
    tc.assertEqual(got, want, row.get("derivation"))


def _make_author4(row):
    def t(self):
        if row["inputs"].get("entry") == "lane_read":
            self.skipTest("%s: lane read runs through m3a_history.scalar_baseline (story S02, not merged); wired "
                          "here once S02 is on main" % row["id"])
        _check_row(self, row)
    return t


def _make_author1(row):
    def t(self):
        e = row["expected"]
        self.assertEqual(e["status"], "invalid_input")
        chain = row["inputs"]["chain"]
        got = A.request(chain, row["params"], output_id=e.get("output_id", "M3A-0"))
        self.assertEqual(got, e["code"], row.get("case"))
    return t


class Author4Rows(unittest.TestCase):
    pass


class Author1FrameRequestRows(unittest.TestCase):
    pass


A4_FILES = ("m3a_cases_structural.json", "m3a_cases_structural_aux.json", "m3a_cases_lane.json")
for _fn in A4_FILES:
    for _row in H.rows("author4", _fn):
        setattr(Author4Rows, "test_" + _row["id"].replace("-", "_"), _make_author4(_row))

A1_ROWS = ([r for r in H.rows("author1", "m3a_cases_coverage.json") if H.owners_of("author1", "m3a_cases_coverage.json",
                                                                                     r["id"]) == ["S09"]]
           + [r for r in H.rows("author1", "m3a_cases_delta25.json")
              if H.owners_of("author1", "m3a_cases_delta25.json", r["id"]) == ["S09"]])
for _row in A1_ROWS:
    setattr(Author1FrameRequestRows, "test_" + _row["id"].replace("-", "_"), _make_author1(_row))


class RowInventory(unittest.TestCase):
    def test_owned_row_count_is_218(self):
        n = sum(len(H.rows("author4", fn)) for fn in A4_FILES) + len(A1_ROWS)
        self.assertEqual(n, 218)
        self.assertEqual(sorted(r["id"] for r in A1_ROWS),
                         sorted(["COV-35", "COV-36", "COV-37"] + ["D25-V%d" % i for i in range(1, 8)]))


# ------------------------------------------------------------------------------------------- Developer unit tests
# Own synthetic request: two contracts (call and put, 30 days, strike 100), every check passing.

def _contracts(n=2):
    out = []
    for i in range(n):
        right = "call" if i % 2 == 0 else "put"
        strike = str(100 + i // 2)
        out.append(ChainContract("K%d" % i, 30, right, strike, "1.0000", "1.1000", CUTOFF - 5_000_000_000, None,
                                 "european", "regular"))
    return out


def _base(output_id="M3A-0"):
    params = {"mode": "intraday", "lane": "stock", "feed_delay_tag": "live", "evaluation_ns": CUTOFF,
              "tenors": [9, 30, 91], "delta_target": "0.25", "iv_form": "atm", "delta_convention": "spot",
              "direction": "up", "session_minutes": 390}
    return {"output_id": output_id, "contracts": _contracts(), "spot": "100", "rate": "0.05",
            "dividend_yield": "0.01", "cutoff_ns": CUTOFF, "params": params}


def _run(r, validate="scanned"):
    return V.validate_request(r["output_id"], r["contracts"], r["spot"], r["rate"], r["dividend_yield"],
                              r["cutoff_ns"], r["params"], validate=validate)


def _set_contract(r, i, **kw):
    r["contracts"][i] = r["contracts"][i]._replace(**kw)


# one injected defect per code (request list, IO contract section 4); each returns the mutated request
def _d_bad_cutoff(r):
    r["cutoff_ns"] = -1
    r["params"]["evaluation_ns"] = -1


def _d_bad_spot(r):
    r["spot"] = "0"


def _d_bad_rate(r):
    r["rate"] = "1.5"


def _d_invalid_mode(r):
    r["params"]["mode"] = "weekly"


def _d_invalid_lane(r):
    r["params"]["lane"] = "etf"


def _d_bad_expiry(r):
    _set_contract(r, 0, expiry_days=0)


def _d_unknown_right(r):
    _set_contract(r, 1, right="straddle")


def _d_duplicate_id(r):
    _set_contract(r, 1, contract_id="K0")


def _d_bad_strike(r):
    _set_contract(r, 0, strike="0")


def _d_malformed(r):
    _set_contract(r, 1, ask="1.123456789")


def _d_cutoff_mismatch(r):
    r["params"]["evaluation_ns"] = r["cutoff_ns"] + 1


def _d_duplicate_key(r):
    c = r["contracts"][0]
    r["contracts"].append(c._replace(contract_id="K-dup"))


def _d_tenor(r):
    r["params"]["tenors"] = [7]


def _d_delta(r):
    r["params"]["delta_target"] = "0.10"


def _d_iv_form(r):
    r["params"]["iv_form"] = "fast"


def _d_convention(r):
    r["params"]["delta_convention"] = "mid"


def _d_threshold_required(r):
    r["params"]["fire"] = True


def _d_threshold_range(r):
    r["params"]["x"] = 101


def _d_direction(r):
    r["params"]["direction"] = "sideways"


def _d_minute(r):
    r["params"]["minute"] = 390


def _d_prior(r):
    r["params"]["prior"] = {"kind": "frame", "time_ns": r["cutoff_ns"]}


def _d_convention_mismatch(r):
    pr = r["params"].get("prior")
    if pr is None:
        r["params"]["priors"] = [{"kind": "session", "time_ns": r["cutoff_ns"] - 1, "delta_convention": "forward"}]
    else:
        pr["delta_convention"] = "forward"


def _d_delayed(r):
    r["params"]["feed_delay_tag"] = "delayed"


# (code, defect, outputs that use the checked parameter), in request-list order: 23 codes
LIST = (
    ("bad_cutoff", _d_bad_cutoff, None),
    ("bad_spot", _d_bad_spot, None),
    ("bad_rate", _d_bad_rate, None),
    ("invalid_mode", _d_invalid_mode, None),
    ("invalid_lane", _d_invalid_lane, None),
    ("bad_expiry", _d_bad_expiry, None),
    ("unknown_right", _d_unknown_right, None),
    ("duplicate_contract", _d_duplicate_id, None),
    ("bad_strike", _d_bad_strike, None),
    ("malformed_type", _d_malformed, None),
    ("cutoff_mismatch", _d_cutoff_mismatch, None),
    ("duplicate_contract", _d_duplicate_key, None),
    ("tenor_not_allowed", _d_tenor, ("M3A-0", "M3A-3", "M3A-4", "M3A-5", "M3A-6", "M3A-7", "M3A-8", "M3A-9", "M3A-10",
                                     "M3A-11")),
    ("delta_not_allowed", _d_delta, ("M3A-0", "M3A-3", "M3A-4", "M3A-5", "M3A-6", "M3A-7", "M3A-8", "M3A-9",
                                     "M3A-10", "M3A-11")),
    ("iv_form_not_allowed", _d_iv_form, ("M3A-2", "M3A-3")),
    ("convention_not_allowed", _d_convention, ("M3A-0", "M3A-7", "M3A-8", "M3A-9", "M3A-10", "M3A-11")),
    ("threshold_required", _d_threshold_required, ("M3A-1", "M3A-2", "M3A-3", "M3A-4", "M3A-5", "M3A-6", "M3A-7",
                                                   "M3A-8", "M3A-9", "M3A-10", "M3A-11")),
    ("threshold_out_of_range", _d_threshold_range, ("M3A-1", "M3A-2", "M3A-8")),
    ("invalid_direction", _d_direction, ("M3A-3", "M3A-4", "M3A-5", "M3A-6", "M3A-7", "M3A-9", "M3A-10", "M3A-11")),
    ("minute_out_of_range", _d_minute, ("M3A-2",)),
    ("prior_not_before_cutoff", _d_prior, ("M3A-3", "M3A-6", "M3A-9")),
    ("convention_mismatch", _d_convention_mismatch, ("M3A-9",)),
    ("delayed_feed_tag", _d_delayed, ("M3A-1", "M3A-2", "M3A-3", "M3A-8")),
)
ALL_OUTPUTS = tuple("M3A-%d" % i for i in range(12))


def _outputs(uses):
    return ALL_OUTPUTS if uses is None else uses


def _request(output_id, *defects):
    """Nominal valid request for `output_id` (thresholds and minute filled where the output needs them), then the
    defects applied in the order given."""
    r = _base(output_id)
    p = r["params"]
    if output_id in ("M3A-1", "M3A-2", "M3A-8"):
        p["x"] = 5
    if output_id == "M3A-11":
        p["at_least"] = "10"                 # V21 has no default threshold (R-116)
    if output_id == "M3A-2":
        p["minute"] = 10
    for d in defects:
        if d is _d_threshold_required:
            p.pop("x", None)
            p["at_least"] = p["at_most"] = None
        d(r)
    return r


class RequestList(unittest.TestCase):
    def test_list_has_18_positions_23_codes(self):
        self.assertEqual(len(V.REQUEST_LIST), 18)
        flat = [c for pos in V.REQUEST_LIST for c in pos]
        self.assertEqual(len(flat), 23)
        self.assertEqual(flat, [c for c, _, _ in LIST])
        self.assertTrue(set(flat) <= set(CODES))
        self.assertNotIn("invalid_param", flat)
        self.assertEqual(V.REQUEST_LIST[14], ("threshold_out_of_range", "invalid_direction"))
        self.assertEqual(V.VIEW_READ_LIST[2], ("malformed_type", "invalid_session_window"))

    def test_nominal_request_valid_on_every_output(self):
        for oid in ALL_OUTPUTS:
            with self.subTest(oid):
                self.assertIsNone(_run(_request(oid)))
                self.assertIsNone(_run(_request(oid), validate="full"))

    def test_each_code_alone_on_every_output_that_uses_it(self):
        for code, d, uses in LIST:
            for oid in _outputs(uses):
                with self.subTest(code=code, output=oid):
                    self.assertEqual(_run(_request(oid, d)), code)

    def test_parameter_ignored_on_outputs_that_do_not_use_it(self):
        """R-120, R-149, R-168, R-174: a parameter is validated only on outputs that use it."""
        for code, d, uses in LIST:
            if uses is None or d is _d_threshold_required:
                continue
            for oid in ALL_OUTPUTS:
                if oid in uses:
                    continue
                with self.subTest(code=code, output=oid):
                    self.assertIsNone(_run(_request(oid, d)))

    def test_adjacent_pairs_first_listed_code_is_reported(self):
        """Every adjacent pair of the request list (22 pairs): where one output uses both parameters, both errors are
        present and the first is reported; pairs no output can hold are equivalent swaps (R-121, R-130, R-167) and
        are checked as each code alone on its own output (test above)."""
        held = swaps = 0
        for (c1, d1, u1), (c2, d2, u2) in zip(LIST, LIST[1:]):
            both = [o for o in ALL_OUTPUTS if o in _outputs(u1) and o in _outputs(u2)]
            if (c1, c2) == ("threshold_required", "threshold_out_of_range"):
                both = []                         # a request carrying x never lacks a threshold (R-167)
            if not both:
                swaps += 1
                continue
            held += 1
            for oid in both:
                with self.subTest(pair=(c1, c2), output=oid):
                    self.assertEqual(_run(_request(oid, d1, d2)), c1)
                    self.assertEqual(_run(_request(oid, d2, d1)), c1)
        self.assertEqual(held + swaps, 22)
        # 13b-13c, 14-15a, 15a-15b, 15b-16, 16-17a, 17b-18: no output takes both parameters
        self.assertEqual(swaps, 6)

    def test_invalid_direction_value_code_and_type_first(self):
        for oid in ("M3A-3", "M3A-6", "M3A-9", "M3A-11"):
            for bad in ("sideways", "", "UP", "up "):
                r = _request(oid)
                r["params"]["direction"] = bad
                self.assertEqual(_run(r), "invalid_direction", (oid, bad))
            for bad in (5, None, True, ["up"]):
                r = _request(oid)
                r["params"]["direction"] = bad
                self.assertEqual(_run(r), "malformed_type", (oid, bad))
            for ok in ("up", "down", "either"):
                r = _request(oid)
                r["params"]["direction"] = ok
                self.assertIsNone(_run(r))

    def test_direction_after_threshold_required_and_before_prior(self):
        r = _request("M3A-3", _d_threshold_required, _d_direction)
        self.assertEqual(_run(r), "threshold_required")
        r = _request("M3A-3", _d_direction, _d_prior)
        self.assertEqual(_run(r), "invalid_direction")
        r = _request("M3A-9", _d_direction, _d_convention_mismatch)
        self.assertEqual(_run(r), "invalid_direction")
        r = _request("M3A-3", _d_direction)
        r["params"]["direction"] = 5
        _d_prior(r)
        self.assertEqual(_run(r), "malformed_type")       # type-first at position 15, before 17

    def test_scanned_and_full_agree(self):
        for code, d, uses in LIST:
            for oid in _outputs(uses):
                r = _request(oid, d)
                self.assertEqual(_run(r, "scanned"), _run(r, "full"))
        with self.assertRaises(ValueError):
            _run(_request("M3A-0"), validate="fast")


class TypeFirst(unittest.TestCase):
    def test_spot_forms(self):
        ok = ("100", "100.12345678", "1.", ".5", 100, 100.5, 0.25, Fraction(201, 2), Fraction(1, 10 ** 8))
        for s in ok:
            r = _request("M3A-0")
            r["spot"] = s
            self.assertIsNone(_run(r), s)
        for s, code in (("100.123456789", "malformed_type"), (100.1, "malformed_type"),
                        (Fraction(1, 3), "malformed_type"),
                        ("1/2", "malformed_type"), (" 1", "malformed_type"), ("+1", "malformed_type"),
                        ("1_0", "malformed_type"), (True, "malformed_type"), (None, "malformed_type"),
                        (b"100", "malformed_type"), ("0", "bad_spot"), ("-1", "bad_spot"), (0, "bad_spot"),
                        (-0.5, "bad_spot"), (float("nan"), "bad_spot"), (float("inf"), "bad_spot"),
                        (Fraction(-1, 2), "bad_spot"), ("0.00000000", "bad_spot")):
            r = _request("M3A-0")
            r["spot"] = s
            self.assertEqual(_run(r), code, s)

    def test_rate_and_yield_forms(self):
        for v in ("1", "-1", "0.000000000001", 1, -1, 0.5, Fraction(1, 3), "1.0000000000000000000"):
            r = _request("M3A-0")
            r["rate"] = v
            self.assertIsNone(_run(r), v)
        for v, code in (("1.0000000000000000001", "bad_rate"), ("-1.00000000000000000001", "bad_rate"),
                        (float("inf"), "bad_rate"), (2, "bad_rate"), ("1/2", "malformed_type"),
                        (True, "malformed_type"), (None, "malformed_type")):
            r = _request("M3A-0")
            r["rate"] = v
            self.assertEqual(_run(r), code, v)
        for v, code in (("-0.0000000000000000001", "bad_rate"), ("1.00000000000000000001", "bad_rate"),
                        ("0", None), ("1", None), (float("nan"), "bad_rate")):
            r = _request("M3A-0")
            r["dividend_yield"] = v
            self.assertEqual(_run(r), code, v)

    def test_chain_quote_grammar(self):
        for v in ("1.", ".5", "1.00000000", 1, None):
            r = _request("M3A-0")
            _set_contract(r, 0, bid=v)
            self.assertIsNone(_run(r), v)
        for v in ("1.000000000", " 1", "+1", "1_0", "1e5", 1.5, True, Fraction(3, 2), b"1"):
            r = _request("M3A-0")
            _set_contract(r, 0, bid=v)
            self.assertEqual(_run(r), "malformed_type", v)

    def test_strike_type_first_at_position_9(self):
        for v, code in (("100.12345678", None), ("1.00000000", None), (100, None), ("1.000000000", "malformed_type"),
                        (100.5, "malformed_type"), (Fraction(201, 2), "malformed_type"), ("-1", "bad_strike"),
                        ("0.0", "bad_strike"), (0, "bad_strike"), (None, "malformed_type")):
            r = _request("M3A-0")
            _set_contract(r, 0, strike=v)
            self.assertEqual(_run(r), code, v)

    def test_duplicate_key_uses_strike_value(self):
        r = _request("M3A-0")
        r["contracts"].append(r["contracts"][0]._replace(contract_id="K9", strike="100.0"))
        self.assertEqual(_run(r), "duplicate_contract")
        r = _request("M3A-0")
        r["contracts"].append(r["contracts"][0]._replace(contract_id="K9", strike=100))
        self.assertEqual(_run(r), "duplicate_contract")

    def test_position_major_across_contracts(self):
        """R-101: the lowest failing position wins whatever the contract order; ties go to the first contract."""
        r = _request("M3A-0")
        _set_contract(r, 0, ask="1.123456789")          # position 10 on the first contract
        _set_contract(r, 1, expiry_days=-3)             # position 6 on the second contract
        self.assertEqual(_run(r), "bad_expiry")
        r = _request("M3A-0")
        _set_contract(r, 0, strike="-1")
        _set_contract(r, 1, strike="x")
        self.assertEqual(_run(r), "bad_strike")

    def test_delta_target_forms(self):
        for v in ("0.25", "0.250", ".25", 0.25, Fraction(1, 4)):
            r = _request("M3A-7")
            r["params"]["delta_target"] = v
            self.assertIsNone(_run(r), v)
        for v, code in (("0.10", "delta_not_allowed"), (0.5, "delta_not_allowed"), (1, "delta_not_allowed"),
                        ("1/4", "malformed_type"), (True, "malformed_type"), (None, "malformed_type"),
                        ("abc", "malformed_type")):
            r = _request("M3A-0")
            r["params"]["delta_target"] = v
            self.assertEqual(_run(r), code, v)

    def test_x_forms(self):
        for v, code in ((5, None), (0, None), (100, None), (Fraction(5, 2), None), ("5/2", None),
                        (5.0, "malformed_type"), (True, "malformed_type"), (-1, "threshold_out_of_range"),
                        (Fraction(201, 2), "threshold_out_of_range")):
            r = _request("M3A-1")
            r["params"]["x"] = v
            self.assertEqual(_run(r), code, v)

    def test_minute_type_first(self):
        for v, code in ((0, None), (389, None), (-1, "minute_out_of_range"), (True, "malformed_type"),
                        (5.0, "malformed_type")):
            r = _request("M3A-2")
            r["params"]["minute"] = v
            self.assertEqual(_run(r), code, v)

    def test_iv_form_and_convention_selectors(self):
        for v, code in (("atm", None), ("30d", None), ("30D", "iv_form_not_allowed"), (["atm"], "malformed_type")):
            r = _request("M3A-3")
            r["params"]["iv_form"] = v
            self.assertEqual(_run(r), code, v)
        for v, code in (("spot", None), ("forward", None), ("Spot", "convention_not_allowed"),
                        (0.5, "malformed_type"), (True, "malformed_type")):
            r = _request("M3A-0")
            r["params"]["delta_convention"] = v
            self.assertEqual(_run(r), code, v)

    def test_prior_checks_all_priors(self):
        """R-134: every supplied prior is checked; the convention check follows the time check (R-160)."""
        r = _request("M3A-9")
        r["params"]["priors"] = [{"kind": "session", "time_ns": CUTOFF - 10},
                                 {"kind": "session", "time_ns": CUTOFF - 5, "delta_convention": "forward"},
                                 {"kind": "session", "time_ns": CUTOFF + 5}]
        self.assertEqual(_run(r), "prior_not_before_cutoff")
        r["params"]["priors"].pop()
        self.assertEqual(_run(r), "convention_mismatch")
        r["params"]["priors"][1]["delta_convention"] = "spot"
        self.assertIsNone(_run(r))
        r["params"]["priors"][0]["time_ns"] = "5"
        self.assertEqual(_run(r), "malformed_type")

    def test_view_read_list(self):
        cal = Calendar([("2026-01-05", 390), ("2026-01-06", 210)])

        def vr(as_of="2026-01-05", form="scalar_baseline", mn=20, mx=252, x=None, minute=None, sid="S/stock/iv30",
               conv="spot"):
            return V.validate_view_read(cal, as_of, form, mn, mx, x=x, minute=minute, series_id=sid,
                                        delta_convention=conv)
        self.assertIsNone(vr())
        self.assertEqual(vr(as_of="2026-02-01"), "session_not_in_calendar")
        self.assertEqual(vr(form="same_minute_column", minute=390), "minute_out_of_range")
        self.assertEqual(vr(as_of="2026-01-06", form="same_minute_column", minute=210), "minute_out_of_range")
        self.assertIsNone(vr(as_of="2026-01-06", form="same_minute_column", minute=209))
        self.assertEqual(vr(form="same_minute_column", minute=5.0), "malformed_type")
        self.assertEqual(vr(mn="20"), "malformed_type")
        self.assertEqual(vr(mn=0), "malformed_type")
        self.assertEqual(vr(mx=True), "malformed_type")
        self.assertEqual(vr(mn=30, mx=29), "invalid_session_window")
        self.assertIsNone(vr(mn=30, mx=30))
        self.assertEqual(vr(x=101), "threshold_out_of_range")
        self.assertEqual(vr(sid="S/stock/skew25_fwd"), "convention_mismatch")
        self.assertEqual(vr(sid="S/stock/skew25", conv="forward"), "convention_mismatch")
        self.assertIsNone(vr(sid="S/stock/skew25_fwd", conv="forward"))
        self.assertIsNone(vr(sid="S/stock/iv30", conv="forward"))
        # adjacent pairs of the view-read list (5 positions, 6 codes, 5 pairs)
        self.assertEqual(vr(as_of="2026-02-01", form="same_minute_column", minute=999), "session_not_in_calendar")
        self.assertEqual(vr(form="same_minute_column", minute=390, mn="x"), "minute_out_of_range")
        self.assertEqual(vr(mn="x", mx=1), "malformed_type")
        self.assertEqual(vr(mn=30, mx=29, x=101), "invalid_session_window")
        self.assertEqual(vr(x=101, sid="S/stock/skew25_fwd"), "threshold_out_of_range")

    def test_m1_value_error_mapping(self):
        from option_features.chainiv import IVChain
        cases = ((dict(spot="0"), "bad_spot"),
                 (dict(contracts=[ChainContract("a", 0, "call", "1", None, None, 0)]), "bad_expiry"),
                 (dict(contracts=[ChainContract("a", 1, "x", "1", None, None, 0)]), "unknown_right"),
                 (dict(contracts=[ChainContract("a", 1, "call", "1", None, None, 0)] * 2), "duplicate_contract"),
                 (dict(contracts=[ChainContract("a", 1, "call", "0", None, None, 0)]), "bad_strike"),
                 (dict(contracts=[ChainContract("a", 1, "call", "1.000000001", None, None, 0)]), "malformed_type"))
        for kw, code in cases:
            args = dict(contracts=[], spot="100", rate="0", dividend_yield="0", cutoff_ns=0)
            args.update(kw)
            with self.assertRaises(ValueError) as cm:
                IVChain(**args)
            self.assertEqual(V.m1_error_code(cm.exception), code, kw)


class ValidationCost(unittest.TestCase):
    """Developer measurement of the validation cost (printed; the hard bound is loose: validation is O(contracts) and
    must stay a small share of M3A-G0). mock-data qualification only: passed on independently authored synthetic
    fixtures and synthetic workloads, Windows x64, CPython 3.12."""

    def test_cost_per_contract(self):
        r = _base("M3A-9")
        r["contracts"] = _contracts(2000)
        r["params"]["at_least"] = "1"
        r["params"]["priors"] = [{"kind": "session", "time_ns": CUTOFF - 1}]
        for _ in range(3):
            _run(r)
        samples = []
        for _ in range(15):
            t0 = time.perf_counter()
            self.assertIsNone(_run(r))
            samples.append(time.perf_counter() - t0)
        samples.sort()
        per = samples[len(samples) // 2] / 2000
        print("\n[S09 cost] full request validation, 2000 contracts: median %.1f us per call, %.0f ns per contract"
              % (samples[len(samples) // 2] * 1e6, per * 1e9))
        self.assertLess(per, 20e-6)


if __name__ == "__main__":
    unittest.main()
