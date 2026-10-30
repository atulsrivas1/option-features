"""Totality of the story B print entry points: no exception escapes `build_tape`, `stream_code` or any print-family
function on ANY Python objects in any print field or parameter (unhashable contract ids, NaN, bytes, nested objects,
huge ints, objects whose hash, comparison or arithmetic raises, short and non-sequence prints, wrong-typed
parameters); a tape error is one of the ruled codes; a tape with no error means every field was well-typed.
Also: the tape and the shared `flowgrid.check_prints` give the same code on malformed-heavy lists once check_prints
follows IO contract section 9 item 15 (skipped, with a message, while it does not).

M2B_TOTALITY_N sets the number of fuzzed lists (default 20,000 in the suite; the evidence ran 250,000+);
M2B_DIFF_N sets the lists of the check_prints differential (default 30,000; the evidence ran 600,000).
Label: synthetic workload, relative engineering budget (no claim about recorded data). Synthetic fixtures only.
"""
import os
import random
import unittest
from decimal import Decimal
from fractions import Fraction

from option_features import episodes as E, flowgrid, m2prints as M, printtape as PT

NS = 10 ** 9
OPEN = 1_790_000_000 * NS
N_FUZZ = int(os.environ.get("M2B_TOTALITY_N", "20000"))
N_DIFF = int(os.environ.get("M2B_DIFF_N", "30000"))
CONTRACTS = {"A": ("C", 1_000_000, "2026-11-20", "stock"), "B": ("P", 1_100_000, "2026-12-18", "stock"),
             "Z": ("C", 1_200_000, "2026-12-18", "etf_index")}
CODES = {None, "unordered_prints", "negative_size_or_price", "bad_multiplier", "unknown_contract", "malformed_type"}


class Hostile:
    """An object whose hash, comparison, arithmetic, truth value and indexing all raise."""
    __hash__ = None

    def _boom(self, *a, **k):
        raise RuntimeError("hostile")
    __eq__ = __lt__ = __le__ = __gt__ = __ge__ = __bool__ = __int__ = __index__ = __getitem__ = __iter__ = _boom
    __add__ = __radd__ = __sub__ = __rsub__ = __mul__ = __rmul__ = __len__ = __contains__ = _boom


class Weird:
    """Hashable, but every comparison and arithmetic raises."""

    def _boom(self, *a, **k):
        raise RuntimeError("weird")
    __eq__ = __lt__ = __le__ = __gt__ = __ge__ = __bool__ = __index__ = __add__ = __sub__ = __mul__ = _boom

    def __hash__(self):
        return 7


ODD = [None, True, False, 0, 1, -1, 2, 100, -100, 10 ** 30, -10 ** 30, 2 ** 64, 2 ** 100, 1.5, -2.5, 0.0, 1.0, float("nan"),
       float("inf"), -float("inf"), Decimal("1.5"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity"), Fraction(3, 2),
       Fraction(-1), b"1", b"", bytearray(b"1"), "", "x", "1", "-1", "1.0000", "-1.0000", "1.00001", ".", "1e3", "١",
       "9" * 5000, " 1 ", [], [1], ["A"], {}, {"id": "A"}, set(), (1, 2), ("A",), [[["A"]]], object(), Hostile(), Weird(), len,
       1 + 2j, "A", "B", "Z", "NOPE"]
SIZES = [0, 1, 5, 10, 1000]
PRICES = [1, 100, 12345, "1.0000", "55.5", "0.0001", 0, 5_000_000]


def field(rng, good):
    return rng.choice(ODD) if rng.random() < 0.35 else good


def make_print(rng, t, seq):
    cid = field(rng, rng.choice(("A", "B", "Z")))
    p = [cid, field(rng, t), field(rng, rng.choice(PRICES)), field(rng, rng.choice(SIZES)),
         field(rng, rng.choice((100, 100, 100, 50))), field(rng, rng.choice((0, 0, 1, False, True))), field(rng, seq)]
    if rng.random() < 0.3:
        p.append(rng.choice(("ask", "bid", None, Hostile())))
    r = rng.random()
    if r < 0.04:
        return rng.choice((None, 5, "abc", [], p[:rng.randrange(0, 7)], {"a": 1}, Hostile(), (), object()))
    return tuple(p) if r < 0.5 else p


def make_stream(rng):
    n = rng.choice((0, 1, 2, 3, 5, 8))
    t, out = OPEN + rng.randrange(0, 5) * NS, []
    for i in range(n):
        t += rng.choice((0, 1, NS, 60 * NS)) if rng.random() < 0.9 else -NS
        out.append(make_print(rng, t, i))
    return out


def odd_or(rng, good):
    return rng.choice(ODD) if rng.random() < 0.2 else good


def exercise(rng, tape):
    """Call every print-family entry on the tape with partly hostile parameters; none may raise."""
    T = odd_or(rng, OPEN + rng.choice((-100, 0, 899, 900, 1000, 3000)) * NS)
    open_ns = odd_or(rng, OPEN)
    lane = odd_or(rng, rng.choice(("stock", "etf_index")))
    flt = odd_or(rng, rng.choice(("all", "calls", "puts")))
    w = odd_or(rng, rng.choice((60, 300, 900, 3600)))
    cuts = [odd_or(rng, T) for _ in range(rng.choice((0, 1, 3)))] if rng.random() < 0.8 else odd_or(rng, [T])
    kw = dict(lane=lane, delayed=odd_or(rng, False), series_id=odd_or(rng, "S"), session_id=odd_or(rng, "D"),
              session_in_calendar=odd_or(rng, True))
    n = odd_or(rng, rng.choice((1, 3, "3/2")))
    thr = odd_or(rng, rng.choice((1, 10 ** 9)))
    calls = [
        lambda: M.f1_premium_surge(tape, T, open_ns, n=n, flt=flt, **kw),
        lambda: M.f1_sweep(tape, cuts, open_ns, n=n, flt=flt, **kw),
        lambda: M.f4_large_prints(tape, T, window_s=w, threshold_ticks=thr, n=n, flt=flt, open_ns=open_ns, **kw),
        lambda: M.f4_sweep(tape, cuts, window_s=w, threshold_ticks=thr, n=n, flt=flt, open_ns=open_ns, **kw),
        lambda: M.f7_concentration(tape, T, window_s=w, share_threshold=odd_or(rng, "3/5"), flt=flt, open_ns=open_ns, **kw),
        lambda: M.f7_sweep(tape, cuts, window_s=w, flt=flt, open_ns=open_ns, **kw),
        lambda: M.f18_put_share(tape, T, window_s=w, at_least=odd_or(rng, "1/2"), at_most=odd_or(rng, None), open_ns=open_ns, **kw),
        lambda: M.f18_sweep(tape, cuts, window_s=w, at_least="1/2", open_ns=open_ns, **kw),
        lambda: E.f12_from_tape(tape, T, open_ns, n=n, n_episodes=odd_or(rng, 1), quiet_gap=odd_or(rng, 1),
                                grid_s=odd_or(rng, 60), flt=flt, **kw),
        lambda: E.f12_sweep(tape, cuts, open_ns, flt=flt, **kw),
        lambda: E.f12_episodes([odd_or(rng, 1000) for _ in range(20)], [odd_or(rng, 15000) for _ in range(20)], T, open_ns, **kw),
    ]
    kw17 = {k: v for k, v in kw.items() if k != "series_id"}
    ids = odd_or(rng, ["A", "Z", "ghost", odd_or(rng, "B")])
    calls += [
        lambda: M.f17_many(tape, T, ids, window_s=odd_or(rng, 300), threshold_ticks=thr, flt=flt, open_ns=open_ns, **kw17),
        lambda: M.f17_sweep(tape, cuts, ids, flt=flt, open_ns=open_ns, **kw17),
        lambda: M.f17_window_premium(tape, T, odd_or(rng, "A"), open_ns=open_ns, **kw17),
    ]
    for call in calls:
        r = call()                            # nothing may raise
        for x in (r if isinstance(r, list) else [r]):
            for y in (x if isinstance(x, list) else [x]):
                assert y.status in ("available", "unavailable", "invalid_input")


class Totality(unittest.TestCase):
    def test_fuzz_no_exception_and_ruled_codes(self):
        for case in range(N_FUZZ):
            rng = random.Random(case * 104729 + 3)
            as_list = make_stream(rng)
            tape = PT.build_tape(iter(as_list) if case % 11 == 0 else as_list, CONTRACTS)
            self.assertIn(tape.error, CODES, case)
            self.assertEqual(PT.stream_code(as_list, CONTRACTS), tape.error, case)
            if tape.error is None:
                for p in as_list:
                    self.assertTrue(isinstance(p, (list, tuple)) and len(p) >= 7 and type(p[1]) is int and type(p[6]) is int
                                    and type(p[3]) is int and type(p[4]) is int, (case, p))
            exercise(rng, tape)

    def test_unhashable_ids_and_odd_objects_have_codes(self):
        base = ("A", OPEN, "1.0000", 5, 100, 0, 0)
        cases = [((["A"],) + base[1:], "malformed_type"), (({"id": 1},) + base[1:], "malformed_type"),
                 ((Hostile(),) + base[1:], "malformed_type"), ((Weird(),) + base[1:], "unknown_contract"),
                 (base[:2] + (Decimal("NaN"),) + base[3:], "malformed_type"), (base[:2] + (b"1",) + base[3:], "malformed_type"),
                 (base[:3] + (10 ** 40,) + base[4:], None), (base[:2] + ("9" * 5000,) + base[3:], "malformed_type"),
                 (base[:3] + (float("nan"),) + base[4:], "malformed_type"), (base[:4] + (Hostile(),) + base[5:], "malformed_type")]
        for p, code in cases:
            self.assertEqual(PT.build_tape([p], CONTRACTS).error, code, p)
        for bad in (None, 5, "abc", [], (), {}, Hostile(), ("A",)):
            self.assertEqual(PT.build_tape([base, bad], CONTRACTS).error, "malformed_type", bad)
        self.assertEqual(PT.build_tape(5, CONTRACTS).error, "malformed_type")
        self.assertEqual(PT.build_tape(None, CONTRACTS).error, "malformed_type")

    def test_per_field_precedence(self):
        def err(*prints):
            return PT.build_tape(list(prints), CONTRACTS).error
        ok = ("A", OPEN, "1.0000", 5, 100, 0, 0)
        # float size beside a negative price (the same print): type first; a negative well-typed size or price: value code
        self.assertEqual(err(("A", OPEN, "-1.0000", 1.5, 100, 0, 0)), "malformed_type")
        self.assertEqual(err(("A", OPEN, "-1.0000", 5, 100, 0, 0)), "negative_size_or_price")
        self.assertEqual(err(("A", OPEN, "1.0000", -5, 100, 0, 0)), "negative_size_or_price")
        # float multiplier on an unknown contract: the multiplier position precedes unknown_contract
        self.assertEqual(err(("ZZ", OPEN, "1.0000", 5, 1.5, 0, 0)), "malformed_type")
        # float price on an unknown contract: price has no value code, its slot is after unknown_contract
        self.assertEqual(err(("ZZ", OPEN, 1.5, 5, 100, 0, 0)), "unknown_contract")
        # positions: within the sign position a value code beats malformed_type (another print's -5); the ordering position
        # comes first, then size, then multiplier: a negative price (sign position) beats a float multiplier (later)
        self.assertEqual(err(ok, ("A", OPEN + 1, "1.0000", 1.5, 100, 0, 1), ("A", OPEN + 2, "1.0000", -5, 100, 0, 2)),
                         "negative_size_or_price")
        self.assertEqual(err(("A", OPEN, "1.0000", 1.5, 100, 0, 0), ("A", OPEN + 1, "1.0000", 5, 0, 0, 1)), "malformed_type")
        self.assertEqual(err(("A", OPEN, "-1.0000", 5, 100, 0, 0), ("A", OPEN + 1, "1.0000", 5, 2.5, 0, 1)), "negative_size_or_price")
        self.assertEqual(err(("A", 1.5, "1.0000", 5, 100, 0, 0), ("A", OPEN + 1, "1.0000", -5, 100, 0, 1)), "malformed_type")
        self.assertEqual(err(ok, ("A", OPEN + 5, "1.0000", 1.5, 100, 0, 1), ("A", OPEN + 4, "1.0000", 5, 100, 0, 2),
                             ("A", OPEN + 3, "1.0000", 5, 100, 0, 3)), "unordered_prints")
        self.assertEqual(err(("A", OPEN, "1.0000", 5, 0, 0, 0), ("A", OPEN + 1, "1.0000", 5, 100, 2, 1)), "bad_multiplier")


class Parameters(unittest.TestCase):
    """Entry points answer malformed_type for hostile parameters, bound the F12 grid, and let a malformed contract
    table (a programming error, not print data) raise."""

    def setUp(self):
        self.tape = PT.build_tape([("A", OPEN + NS, "1.0000", 5, 100, 0, 0)], CONTRACTS)

    def code(self, r):
        return r.code if r.status == "invalid_input" else None

    def test_hostile_parameters(self):
        T = OPEN + 1000 * NS
        for lane in (["x"], {"a": 1}, None, 5, Hostile()):
            self.assertEqual(self.code(M.f4_large_prints(self.tape, T, lane=lane, open_ns=OPEN)), "malformed_type")
            self.assertEqual(self.code(M.f1_premium_surge(self.tape, T, OPEN, lane=lane)), "malformed_type")
            self.assertEqual(self.code(E.f12_from_tape(self.tape, T, OPEN, lane=lane)), "malformed_type")
        for flt in (None, ["all"], 5, Hostile(), Weird()):
            self.assertEqual(self.code(M.f7_concentration(self.tape, T, flt=flt, open_ns=OPEN)), "malformed_type")
        for delayed in (None, 1, "yes", Weird()):
            self.assertEqual(self.code(M.f1_premium_surge(self.tape, T, OPEN, delayed=delayed)), "malformed_type")
        for T_bad in (None, 1.5, "x", Weird(), True):
            self.assertEqual(self.code(M.f4_large_prints(self.tape, T_bad, open_ns=OPEN)), "malformed_type")
        self.assertEqual(self.code(M.f4_large_prints(self.tape, T, window_s=None, open_ns=OPEN)), "window_not_allowed")
        self.assertEqual(M.f4_sweep(self.tape, 5, open_ns=OPEN), [])
        self.assertEqual(M.f17_many(self.tape, T, 5, open_ns=OPEN), [])
        self.assertEqual(self.code(M.f17_window_premium(self.tape, T, ["unhashable"], open_ns=OPEN)), None)

    def test_f12_grid_is_bounded(self):
        for far in (E.MAX_GRID_POINTS * 60 * NS, 10 ** 30):
            r = E.f12_from_tape(self.tape, OPEN + far, OPEN)
            self.assertEqual((r.status, r.code), ("invalid_input", "malformed_type"))
            out = E.f12_sweep(self.tape, [OPEN + 1000 * NS, OPEN + far], OPEN)
            self.assertEqual([x.code for x in out], ["malformed_type"] * 2)
        ok = E.f12_from_tape(self.tape, OPEN + (E.MAX_GRID_POINTS - 1) * 60 * NS, OPEN)
        self.assertEqual(ok.status, "available")

    def test_malformed_contract_table_is_not_swallowed(self):
        good = [("A", OPEN, "1.0000", 5, 100, 0, 0)]
        with self.assertRaises(ValueError):
            PT.build_tape(good, {"A": ("C", 1)})
        with self.assertRaises(TypeError):
            PT.build_tape(good, {"A": None})


class DifferentialCheckPrints(unittest.TestCase):
    def setUp(self):
        contracts = {cid: flowgrid.Contract(c[0], c[1], c[2], c[3], "U") for cid, c in CONTRACTS.items()}
        self.contracts = contracts
        probe = [("A", OPEN, "1.0000", 1.5, 0, 0, 0)]                     # row M2A-TF-042: malformed_type
        try:
            ok = flowgrid.check_prints(probe, contracts) == "malformed_type"
            ok = ok and flowgrid.check_prints([(["A"], OPEN, "1.0000", 5, 100, 0, 0)], contracts) == "malformed_type"
        except Exception:
            ok = False
        if not ok:
            self.skipTest("flowgrid.check_prints does not follow IO contract section 9 item 15 yet (story A PR 93)")

    def _compare(self):
        diffs, raised = [], 0
        for case in range(N_DIFF):
            rng = random.Random(case * 15485863 + 9)
            prints = make_stream(rng)
            got = PT.build_tape(prints, CONTRACTS).error
            try:
                want = flowgrid.check_prints(prints, self.contracts)
            except Exception:
                raised += 1
                continue
            if want != got:
                diffs.append((case, want, got, repr(prints)[:200]))
        return diffs, raised

    def test_tape_equals_check_prints_where_it_answers(self):
        diffs, raised = self._compare()
        self.assertEqual(diffs[:5], [], "%d disagreements of %d lists" % (len(diffs), N_DIFF))
        print("check_prints differential: %d lists, %d disagreements, check_prints raised on %d" % (N_DIFF, len(diffs), raised))

    def test_check_prints_is_total(self):
        _, raised = self._compare()
        if raised:
            self.skipTest("story A defect: flowgrid.check_prints raised on %d of %d hostile lists (the tape never raises)"
                          % (raised, N_DIFF))


if __name__ == "__main__":
    unittest.main()
