"""M1 OC5/OC6 property tests: batched versus single, and the library versus an independent Fraction reference.

Seeded stdlib random only (no clocks, no files). The reference below is written independently from the library
(plain Fractions, segment-by-segment over the breakpoints, no running sums or caches) and shares no code with it.
Label: synthetic workload, relative engineering budget.
"""
from fractions import Fraction
import random
import unittest

from option_features.imbalance import OC5Params, oc5, oc5_many
from option_features import spreadwin
from option_features.quotehist import OCStructuralError, QuoteSize, QuoteUpdate, as_ticks, validate_history
from option_features.spreadwin import OC6Params, oc6, oc6_many

NS = 10 ** 9
OPEN = -18000 * NS


def dec(t):
    return "%d.%04d" % (t // 10000, t % 10000)


def rand_updates(rng, n, t_end=0, span=400 * NS, with_known=True):
    """n updates with non-decreasing event time, distinct seq, random lag (sometimes negative) and bad quotes."""
    events = sorted(rng.randint(t_end - span, t_end + 20 * NS) for _ in range(n))
    out = []
    for i, e in enumerate(events):
        kind = rng.random()
        mid = rng.choice((9, 10, 10, 11))
        half = rng.choice((1, 2, 5, 10, 50))
        bid, ask = (mid * 10000 - half, mid * 10000 + half)
        if kind < 0.05:
            bid, ask = ask, bid
        elif kind < 0.08:
            ask = bid
        elif kind < 0.10:
            bid = None
        elif kind < 0.12:
            bid = 0
        ka = e + (rng.choice((0, 0, 0, 3 * NS, 90 * NS, -2 * NS)) if with_known else 0)
        out.append(QuoteUpdate(i + 1, e, ka, None if bid is None else dec(bid), dec(ask), rng.random() > 0.1, i))
    return out


def ref_oc6(updates, t, open_ns, p):
    """Independent reference: returns (status/reason/label, ratio, avg_bps) per the ruled definition."""
    def price(x):
        return None if x is None else Fraction(x)
    known = [u for u in updates if u.event_ns <= t and u.known_at_ns <= t]
    if not known:
        return ("no_quote", None)
    key = lambda u: (u.event_ns, u.seq, u.known_at_ns)
    cur = max(known, key=key)
    b, a = price(cur.bid), price(cur.ask)
    if not cur.regular:
        return ("excluded_condition", None)
    for gate, bad in (("invalid_quote", b is None or a is None or b <= 0),
                      ("crossed_market", b is not None and a is not None and b > a),
                      ("locked_market", b == a)):
        if bad:
            return (gate, None)
    if t - cur.event_ns > p["stale"]:
        return ("stale_quote", None)
    start = max(t - p["window"], open_ns)
    count = sum(1 for u in known if u.regular and start <= u.event_ns <= t)
    if count < p["cov"]:
        return ("low_quote_coverage", None)
    pts = sorted({start, t} | {u.known_at_ns for u in known if start < u.known_at_ns < t})
    num = den = Fraction(0)
    for lo, hi in zip(pts, pts[1:]):
        live = [u for u in known if u.known_at_ns <= lo and u.event_ns >= open_ns]
        if not live:
            continue
        q = max(live, key=key)
        qb, qa = price(q.bid), price(q.ask)
        if not q.regular or qb is None or qa is None or not 0 < qb < qa:
            continue
        num += (hi - lo) * (qa - qb) / ((qa + qb) / 2) * 10000
        den += hi - lo
    if den == 0:
        return ("no_window_spread", None)
    avg = num / den
    cur_bps = (a - b) / ((a + b) / 2) * 10000
    ratio = cur_bps / avg
    label = "narrower" if ratio <= Fraction(3, 4) else ("wider" if ratio >= Fraction(3, 2) else None)
    return ("fired" if label else "not_fired", label, ratio, avg)


def ref_oc5(updates, sizes, t, consolidated, stale):
    known = [u for u in updates if u.event_ns <= t and u.known_at_ns <= t]
    if not known:
        return ("no_quote",)
    cur = max(known, key=lambda u: (u.event_ns, u.seq, u.known_at_ns))
    if not cur.regular:
        return ("excluded_condition",)
    if not consolidated:
        return ("not_consolidated",)
    b = None if cur.bid is None else Fraction(cur.bid)
    a = None if cur.ask is None else Fraction(cur.ask)
    if b is None or a is None or b <= 0:
        return ("invalid_quote",)
    if b > a:
        return ("crossed_market",)
    if t - cur.event_ns > stale:
        return ("stale_quote",)
    row = {s.rev: s for s in sizes}.get(cur.rev)
    if row is None or row.bid_size is None or row.ask_size is None:
        return ("missing_size",)
    if row.bid_size + row.ask_size == 0:
        return ("zero_displayed_size",)
    v = Fraction(row.bid_size - row.ask_size, row.bid_size + row.ask_size)
    label = "bid" if v >= Fraction(3, 5) else ("ask" if v <= -Fraction(3, 5) else None)
    return ("fired" if label else "not_fired", label, v)


class OC6Properties(unittest.TestCase):
    def test_against_reference(self):
        rng = random.Random(20261029)
        params = OC6Params()
        pdict = {"stale": 10 * NS, "window": 300 * NS, "cov": 5}
        seen = set()
        for _ in range(3000):
            ups = rand_updates(rng, rng.randint(0, 14), with_known=rng.random() < 0.7)
            t = rng.choice((0, 0, 5 * NS))
            op = rng.choice((OPEN, -150 * NS, -400 * NS))
            want = ref_oc6(ups, t, op, pdict)
            got = oc6(ups, t, op, params)
            if len(want) == 2:
                self.assertEqual((got.status, got.reason), ("unavailable", want[0]), (ups, t, op))
            else:
                self.assertEqual((got.status, got.label, got.value, got.average_spread_bps),
                                 (want[0], want[1], want[2], want[3]), (ups, t, op))
            seen.add(want[0] if len(want) == 2 else want[0] + str(want[1]))
        self.assertGreaterEqual(len(seen), 6, seen)

    def test_batch_equals_single(self):
        rng = random.Random(7)
        items = [(0, rand_updates(rng, rng.randint(0, 12)), OPEN) for _ in range(300)]
        params = OC6Params()
        many = oc6_many(items, params)
        for item, res in zip(items, many):
            single = oc6(item[1], item[0], item[2], params)
            self.assertEqual((res.status, res.reason, res.label, res.value, res.average_spread_bps),
                             (single.status, single.reason, single.label, single.value, single.average_spread_bps))

    def test_input_order_independent_within_ties(self):
        """Shuffling updates that share an event time (seq breaks the tie) does not change the result."""
        rng = random.Random(11)
        base = [QuoteUpdate(i + 1, -(300 - 60 * (i // 2)) * NS, -(300 - 60 * (i // 2)) * NS, "9.9500", "10.0500", True, i)
                for i in range(6)]
        want = oc6(base, 0, OPEN)
        for _ in range(20):
            shuffled = base[:]
            for k in range(0, 6, 2):
                if rng.random() < 0.5:
                    shuffled[k], shuffled[k + 1] = shuffled[k + 1], shuffled[k]
            got = oc6(shuffled, 0, OPEN)
            self.assertEqual((got.status, got.reason, got.value), (want.status, want.reason, want.value))

    def test_float_filter_equals_always_exact(self):
        """The binary64 filter never changes a decision: same label and value as the always-exact path,
        including windows built so the ratio sits within 1e-12 of a threshold."""
        rng = random.Random(13)
        filtered, exact = OC6Params(), OC6Params()
        exact.n_lo = exact.w_lo = float("-inf")
        exact.n_hi = exact.w_hi = float("inf")
        cases = []
        for _ in range(1500):
            cases.append(rand_updates(rng, rng.randint(5, 14), span=300 * NS, with_known=False))
        for k in range(200):  # near-threshold: current spread = 0.75 * constant average (+- tiny), sum of many terms
            base = [QuoteUpdate(i + 1, (-300 + 60 * i) * NS, (-300 + 60 * i) * NS, "9.9500", "10.0500", True, i) for i in range(5)]
            base.append(QuoteUpdate(6, 0, 0, "9.9625", "10.0375", True, 5))
            cases.append(base)
        for ups in cases:
            a, b = oc6(ups, 0, OPEN, filtered), oc6(ups, 0, OPEN, exact)
            self.assertEqual((a.status, a.reason, a.label, a.value), (b.status, b.reason, b.label, b.value))

    def test_preconverted_ticks_equal_strings(self):
        rng = random.Random(17)
        params = OC6Params()
        for _ in range(300):
            ups = rand_updates(rng, rng.randint(0, 12))
            conv = [u._replace(bid=as_ticks(u.bid), ask=as_ticks(u.ask)) for u in ups]
            a, b = oc6(ups, 0, OPEN, params), oc6(conv, 0, OPEN, params)
            self.assertEqual((a.status, a.reason, a.label, a.value), (b.status, b.reason, b.label, b.value))
        mixed = [QuoteUpdate(1, 0, 0, as_ticks("1.0000"), 2, True)]
        with self.assertRaises(OCStructuralError):
            oc6(mixed, 0, OPEN)

    def test_long_window_linear_and_exact(self):
        """5,000 updates with many distinct sums: exact value equals the reference (checks the integer tree)."""
        rng = random.Random(3)
        ups = []
        for i in range(5000):
            e = -300 * NS + i * (300 * NS // 5000)
            half = 5 + rng.randint(0, 40)
            ups.append(QuoteUpdate(i, e, e, dec(100000 - half), dec(100000 + half), True, i))
        got = oc6(ups, 0, OPEN)
        want = ref_oc6(ups, 0, OPEN, {"stale": 10 * NS, "window": 300 * NS, "cov": 5})
        self.assertEqual((got.value, got.average_spread_bps), (want[2], want[3]))


class OC5Properties(unittest.TestCase):
    def test_against_reference(self):
        rng = random.Random(5)
        params = OC5Params()
        seen = set()
        for _ in range(3000):
            ups = rand_updates(rng, rng.randint(0, 6), span=40 * NS)
            sizes = []
            for u in ups:
                if rng.random() < 0.9:
                    pick = lambda: rng.choice((None, 0, 100, 600, 100, 600, 5000))
                    sizes.append(QuoteSize(u.rev, pick(), pick()))
            t = rng.choice((0, 3 * NS))
            cons = rng.random() < 0.85
            want = ref_oc5(ups, sizes, t, cons, 10 * NS)
            got = oc5(ups, sizes, t, params, consolidated=cons)
            if len(want) == 1:
                if want[0] == "invalid_quote" and got.reason == "locked_market":
                    self.fail("locked must evaluate")
                self.assertEqual((got.status, got.reason), ("unavailable", want[0]), (ups, sizes, t))
            else:
                self.assertEqual((got.status, got.label, got.value), (want[0], want[1], want[2]))
            seen.add(want[0] if len(want) == 1 else want[0] + str(want[1]))
        self.assertGreaterEqual(len(seen), 7, seen)

    def test_batch_equals_single(self):
        rng = random.Random(9)
        items = []
        for _ in range(300):
            ups = rand_updates(rng, rng.randint(0, 5), span=30 * NS)
            sizes = [QuoteSize(u.rev, rng.choice((100, 600)), rng.choice((100, 600, 0))) for u in ups]
            items.append((0, ups, sizes, rng.random() < 0.8))
        params = OC5Params()
        for item, res in zip(items, oc5_many(items, params)):
            single = oc5(item[1], item[2], item[0], params, item[3])
            self.assertEqual((res.status, res.reason, res.label, res.value), (single.status, single.reason, single.label, single.value))


def rand_history(rng, n, t_end=0):
    """Long history before and around t_end: events spread over 3000 s, bursty, tie groups, late-known updates."""
    events = []
    t = t_end - 3000 * NS
    while len(events) < n:
        burst = rng.choice((1, 1, 4, 12))
        for _ in range(burst):
            events.append(t)
            t += rng.choice((0, 0, 1, 20_000_000))
        t += rng.randint(1, 120) * NS
    events = sorted(e for e in events if e <= t_end + 10 * NS)
    out = []
    for i, e in enumerate(events):
        half = rng.choice((5, 10, 50, 100))
        mid = 100000 + rng.randint(0, 3000)
        ka = e + rng.choice((0, 0, 0, 5 * NS, 200 * NS))
        out.append(QuoteUpdate(i + 1, e, ka, dec(mid - half), dec(mid + half), rng.random() > 0.05, i))
    return out


class ScannedValidation(unittest.TestCase):
    def test_scanned_equals_full_on_valid_histories(self):
        rng = random.Random(23)
        params5, params6 = OC5Params(), OC6Params()
        for _ in range(600):
            ups = rand_history(rng, rng.randint(0, 120))
            t = rng.choice((0, 0, 7 * NS, -400 * NS))
            op = rng.choice((OPEN, -200 * NS, -1500 * NS))
            a, b = oc6(ups, t, op, params6), oc6(ups, t, op, params6, validate="full")
            self.assertEqual((a.status, a.reason, a.label, a.value, a.regular_update_count),
                             (b.status, b.reason, b.label, b.value, b.regular_update_count), (t, op))
            sizes = {u.rev: QuoteSize(u.rev, rng.choice((0, 100, 600)), rng.choice((0, 100, 600))) for u in ups}
            a5 = oc5(ups, sizes, t, params5)
            b5 = oc5(ups, list(sizes.values()), t, params5, validate="full")
            self.assertEqual(tuple(a5), tuple(b5))

    def test_errors_outside_the_scanned_portion_need_full(self):
        ups = [QuoteUpdate(i + 1, (-2000 + i) * NS, (-2000 + i) * NS, "9.9500", "10.0500", True, i) for i in range(200)]
        ups += [QuoteUpdate(300 + i, (-300 + 60 * i) * NS, (-300 + 60 * i) * NS, "9.9500", "10.0500", True, 300 + i) for i in range(6)]
        sizes = {u.rev: QuoteSize(u.rev, 600, 100) for u in ups}
        bad = list(ups)
        bad[10] = bad[10]._replace(event_ns=ups[10].event_ns + 1000 * NS)  # non-monotone, far outside the window
        bad[20] = bad[20]._replace(bid=1.5)  # float price, far outside
        self.assertEqual(oc6(bad, 0, OPEN).status, oc6(ups, 0, OPEN).status)
        self.assertEqual(oc5(bad, sizes, 0).status, oc5(ups, sizes, 0).status)
        for fn in (lambda: oc6(bad, 0, OPEN, validate="full"), lambda: oc5(bad, sizes, 0, validate="full"), lambda: validate_history(bad)):
            with self.assertRaises(OCStructuralError):
                fn()
        validate_history(ups, sizes)
        with self.assertRaises(ValueError):
            oc6(ups, 0, OPEN, validate="none")

    def test_boundary_order_check_and_tie_group_at_the_carry_in(self):
        win = [QuoteUpdate(10 + i, (-250 + 50 * i) * NS, (-250 + 50 * i) * NS, "9.9500", "10.0500", True, 10 + i) for i in range(6)]
        carry = QuoteUpdate(2, -400 * NS, -400 * NS, "9.9500", "10.0500", True, 2)
        out_of_order = QuoteUpdate(1, -100 * NS, -100 * NS, "9.9500", "10.0500", True, 1)
        with self.assertRaises(OCStructuralError):  # the update just before the carry-in is checked
            oc6([out_of_order, carry] + win, 0, OPEN)
        # a three-update tie group at the carry-in event time: seq 3 (first in the list, wide) is the quote in effect
        a = QuoteUpdate(3, -400 * NS, -400 * NS, "9.9000", "10.1000", True, 3)
        b = QuoteUpdate(4, -400 * NS, -400 * NS, "9.9500", "10.0500", True, 1)
        c = QuoteUpdate(5, -400 * NS, -400 * NS, "9.9500", "10.0500", True, 2)
        ups = [a, b, c] + win
        s, f = oc6(ups, 0, OPEN), oc6(ups, 0, OPEN, validate="full")
        self.assertEqual((s.status, s.label, s.value, s.average_spread_bps), (f.status, f.label, f.value, f.average_spread_bps))
        self.assertGreater(s.average_spread_bps, 100)  # the wide tie-group member carried in at the window start

    def test_boundary_and_window_errors_are_detected(self):
        ups = [QuoteUpdate(i + 1, (-300 + 60 * i) * NS, (-300 + 60 * i) * NS, "9.9500", "10.0500", True, i) for i in range(6)]
        for k in range(6):
            bad = list(ups)
            bad[k] = bad[k]._replace(bid=2.5)
            with self.assertRaises(OCStructuralError, msg=k):
                oc6(bad, 0, OPEN)


class Immutability(unittest.TestCase):
    def test_oc5_results_immutable(self):
        r = oc5([], [], 0)
        self.assertIs(r, oc5([], [], 0))  # shared unavailable result
        for attr in ("status", "reason", "label"):
            with self.assertRaises(AttributeError):
                setattr(r, attr, "x")
        with self.assertRaises(AttributeError):
            r.extra = 1
        self.assertEqual(r.status, "unavailable")
        ok = oc5([QuoteUpdate(1, -NS, -NS, "1.0000", "1.0500", True)], [QuoteSize(1, 600, 100)], 0)
        with self.assertRaises(AttributeError):
            ok.label = "ask"
        self.assertEqual((ok.status, ok.label, ok.value), ("fired", "bid", Fraction(5, 7)))

    def test_as_ticks_rejects_bool_and_float(self):
        for bad in (True, False, 1.0, 0.5):
            with self.assertRaises(OCStructuralError) as cm:
                as_ticks(bad)
            self.assertEqual(cm.exception.code, "malformed_type")
        self.assertEqual(as_ticks("1.0000"), 10 ** 8)


class FloatFilter(unittest.TestCase):
    def test_pinned_constant_covers_proven_bound(self):
        """FILTER_EPS must stay at least 8x the proven relative error bound (m + 8) * 2**-53 for the largest m."""
        self.assertGreaterEqual(spreadwin.FILTER_EPS, 8 * (spreadwin.MAX_FILTER_TERMS + 8) * 2.0 ** -53)

    def test_empirical_float_error_is_far_below_eps(self):
        rng = random.Random(29)
        worst = 0.0
        for n in (50, 500, 3000):
            for _ in range(4):
                ups = [QuoteUpdate(i, -300 * NS + i * (300 * NS // n), -300 * NS + i * (300 * NS // n),
                                   dec(100000 - 5 - rng.randint(0, 3000)), dec(100000 + 5 + rng.randint(0, 3000)), True, i) for i in range(n)]
                res = oc6(ups, 0, OPEN)
                from option_features.spreadwin import float_ratio
                est = float_ratio(res._dc, res._w, res._sc, res._acc)
                exact = res.value
                worst = max(worst, abs(Fraction(est) - exact) / exact)
        self.assertLess(float(worst), spreadwin.FILTER_EPS / 8)

    def test_exact_ties_with_distinct_mids(self):
        """Every interval is 100/3 bps (spread = mid / 300) at a different midpoint and the current spread is 25 bps
        (mid / 400): the ratio is exactly 3/4 (narrower) whatever the binary64 estimate does, and the weights make
        the float sum of the non-representable terms drift; a filter margin of 0 mislabels some of these."""
        rng = random.Random(31)
        mids = (30, 60, 90, 120, 150)
        for _ in range(600):
            ups, t = [], -300 * NS
            for i in range(6):
                m = rng.choice(mids)
                half = Fraction(m, 600)
                ups.append(QuoteUpdate(i + 1, t, t, "%.4f" % (m - half), "%.4f" % (m + half), True, i))
                t += rng.randint(20, 59) * NS + rng.randint(0, 999_999_999)
            m = rng.choice((40, 80, 120, 160))
            half = Fraction(m, 800)
            ups.append(QuoteUpdate(9, 0, 0, "%.4f" % (m - half), "%.4f" % (m + half), True, 9))
            r = oc6(ups, 0, OPEN)
            self.assertEqual((r.status, r.label, r.value), ("fired", "narrower", Fraction(3, 4)), ups)


class Validation(unittest.TestCase):
    def test_params(self):
        for bad in (0, "0", 2, 0.6, "-1"):
            with self.assertRaises(ValueError):
                OC5Params(bad)
        with self.assertRaises(ValueError):
            OC6Params(narrower_max="1.5", wider_min="1.5")
        with self.assertRaises(ValueError):
            OC6Params(window_ns=-1)

    def test_input_is_not_mutated(self):
        ups = [QuoteUpdate(2, -3 * NS, -3 * NS, "1.0000", "1.0500", True, 2), QuoteUpdate(1, -3 * NS, -3 * NS, "1.0000", "1.0500", True, 1)]
        keep = list(ups)
        oc5(ups, [QuoteSize(2, 600, 100), QuoteSize(1, 100, 600)], 0)
        self.assertEqual(ups, keep)

    def test_nonpositive_ask_is_crossed(self):
        """PO ruling on PR 69 item 4: bid > 0 with ask <= 0 is crossed_market; bid <= 0 stays invalid_quote."""
        for bid, ask, reason in (("1.0000", "0.0000", "crossed_market"), ("1.0000", "-0.0500", "crossed_market"),
                                 ("0.0000", "0.0000", "invalid_quote"), ("-0.0500", "1.0500", "invalid_quote")):
            ups = [QuoteUpdate(i + 1, (-9 + i) * NS, (-9 + i) * NS, "1.0000", "1.0500", True) for i in range(5)]
            ups.append(QuoteUpdate(9, -NS, -NS, bid, ask, True))
            r5 = oc5(ups, [QuoteSize(9, 600, 100)], 0)
            r6 = oc6(ups, 0, OPEN)
            self.assertEqual((r5.reason, r6.reason), (reason, reason), (bid, ask))

    def test_structural_codes(self):
        good = QuoteUpdate(1, 0, 0, "1.0000", "1.0500", True)
        cases = (("malformed_type", [good._replace(event_ns=0.0)]), ("malformed_type", [good._replace(regular="yes")]),
                 ("malformed_type", [good._replace(bid=True)]), ("malformed_type", [good._replace(bid="1.000000001")]),
                 ("duplicate_size_revision", None))
        for code, ups in cases:
            with self.subTest(code=code):
                with self.assertRaises(OCStructuralError) as cm:
                    if ups is None:
                        oc5([good], [QuoteSize(1, 1, 1), QuoteSize(1, 2, 2)], 0)
                    else:
                        oc5(ups, [QuoteSize(1, 1, 1)], 0)
                self.assertEqual(cm.exception.code, code)


if __name__ == "__main__":
    unittest.main()
