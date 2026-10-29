"""P1 batched-versus-single, index-versus-scan and exact-reference property tests.

Seeded stdlib random only (no clocks, no files). Label: synthetic workload, relative engineering budget.
The reference models below are written independently in Fractions; they share no code with the library.
"""
from fractions import Fraction
import random
import unittest

from option_features import quotes, windows, shares

NS = 10 ** 9


def dec(ticks):
    sign = "-" if ticks < 0 else ""
    t = abs(ticks)
    return "%s%d.%04d" % (sign, t // 10000, t % 10000)


def ref_touch(price, bid, ask, qt, t, eps, max_age):
    """Independent Fraction reference of the touch policy with the P1 gate precedence."""
    if bid is None and ask is None or qt > t:
        return "no_quote"
    price = Fraction(price)
    if price <= 0 or bid is None or ask is None or Fraction(bid) <= 0:
        return "invalid_quote"
    bid, ask, eps = Fraction(bid), Fraction(ask), Fraction(eps)
    if bid > ask:
        return "crossed_market"
    if t - qt > max_age:
        return "stale_quote"
    hit_ask, hit_bid = price >= ask - eps, price <= bid + eps
    if hit_ask and hit_bid:
        return "ambiguous_touch"
    return "ask" if hit_ask else ("bid" if hit_bid else "inside_spread")


def outcome(sign):
    return sign.side if sign.status == "available" else sign.reason


class TicksTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(quotes.to_ticks("1.0000"), 10 ** 8)
        self.assertEqual(quotes.to_ticks("-0.0100"), -10 ** 6)
        self.assertEqual(quotes.to_ticks("-.5"), -5 * 10 ** 7)
        self.assertEqual(quotes.to_ticks("12"), 12 * 10 ** 8)
        self.assertEqual(quotes.to_ticks(3), 3 * 10 ** 8)
        self.assertEqual(quotes.to_ticks("0.00000001"), 1)
        self.assertIsNone(quotes.to_ticks(None))
        with self.assertRaises(ValueError):
            quotes.to_ticks("0.000000001")
        with self.assertRaises(ValueError):
            quotes.to_ticks(Fraction(1, 3))

    def test_parameters_validated(self):
        with self.assertRaises(ValueError):
            quotes.sign_trade("1", ("1", "2", 0), 0, inside_spread="midpoint")
        with self.assertRaises(ValueError):
            quotes.sign_trade("1", ("1", "2", 0), 0, epsilon="-0.01")
        with self.assertRaises(ValueError):
            quotes.classify_stream([("q", 1, 5, "1", "2"), ("q", 1, 4, "1", "2")])


class StreamTests(unittest.TestCase):
    def make_stream(self, seed, n):
        rng = random.Random(seed)
        records, t = [], 0
        for _ in range(n):
            t += rng.randrange(0, 2 * NS)
            c = rng.randrange(6)
            if rng.random() < 0.55:
                kind = rng.random()
                bid = rng.randrange(0, 40) * 100
                ask = bid + rng.choice((-100, 0, 100, 200, 500))
                if kind < 0.05:
                    records.append(("q", c, t, None, dec(ask)))
                elif kind < 0.1:
                    records.append(("q", c, t, dec(bid), None))
                elif kind < 0.15:
                    records.append(("q", c, t, None, None))
                else:
                    records.append(("q", c, t, dec(bid), dec(ask)))
            else:
                records.append(("t", c, t, dec(rng.randrange(-100, 4200)), rng.randrange(1, 50)))
        return records

    def test_stream_equals_single_and_exact_reference(self):
        for seed in range(6):
            eps = ("0.0000", "0.0100", "0.0600")[seed % 3]
            max_age = (3 * NS, 10 ** 8, 0)[seed % 3]
            records = self.make_stream(seed, 4000)
            result = quotes.classify_stream(records, epsilon=eps, max_quote_age_ns=max_age)
            last = {}
            ask = bid = unc = 0
            for i, (kind, c, t, x, y) in enumerate(records):
                if kind == "q":
                    last[c] = (x, y, t)
                    reason = quotes.spread_reason(quotes.to_ticks(x), quotes.to_ticks(y), 0, 10 ** 12)
                    self.assertEqual(result.spread_reason(i), reason, i)
                    if reason is None:
                        v = quotes.quote_spread(quotes.to_ticks(x), quotes.to_ticks(y))
                        self.assertEqual(Fraction(result.spread[i], quotes.SCALE), v.spread)
                        self.assertEqual(result.spread_bps(i), v.spread_bps)
                else:
                    single = quotes.sign_trade(x, last.get(c), t, inside_spread="unknown", epsilon=eps, max_quote_age_ns=max_age)
                    batch = result.sign(i)
                    self.assertEqual(batch, single, i)
                    q = last.get(c)
                    want = ref_touch(x, q[0], q[1], q[2], t, eps, max_age) if q else "no_quote"
                    self.assertEqual(outcome(single), want, i)
                    prem = quotes.to_ticks(x) * y * 100
                    if single.side == "ask":
                        ask += prem
                    elif single.side == "bid":
                        bid += prem
                    else:
                        unc += prem
            self.assertEqual((result.ask_premium, result.bid_premium, result.unclassified_premium), (ask, bid, unc))
            self.assertEqual(result.quotes + result.trades, len(records))

    def test_stream_boundaries_equal_single(self):
        # exact touch and age boundaries: price at ask - eps, bid + eps (and one tick either side), age at the limit and +1 ns
        eps, limit = "0.0100", 3 * NS
        records, singles = [], []
        t = 0
        for c, (bid, ask) in enumerate((("10.0000", "10.1000"), ("2.0000", "2.0000"))):
            for price in ("9.9899", "9.9900", "10.0000", "10.0100", "10.0101", "10.0899", "10.0900", "10.1000", "10.1100", "2.0000", "2.0100"):
                for age in (limit - 1, limit, limit + 1):
                    records.append(("q", c, t, bid, ask))
                    records.append(("t", c, t + age, price, 1))
                    singles.append(quotes.sign_trade(price, (bid, ask, t), t + age, inside_spread="unknown", epsilon=eps, max_quote_age_ns=limit))
                    t += limit + 2
        result = quotes.classify_stream(records, epsilon=eps, max_quote_age_ns=limit)
        got = [result.sign(i) for i, r in enumerate(records) if r[0] == "t"]
        self.assertEqual(got, singles)
        self.assertEqual({s.reason for s in singles if s.status != "available"} >= {"stale_quote", "inside_spread", "ambiguous_touch"}, True)

    def test_equal_time_follows_input_order(self):
        quote = ("q", 1, 5, "10.0000", "10.1000")
        trade = ("t", 1, 5, "10.1000", 1)
        after = quotes.classify_stream([quote, trade])
        before = quotes.classify_stream([trade, quote])
        self.assertEqual(after.sign(1).side, "ask")
        self.assertEqual(before.sign(0).reason, "no_quote")

    def test_split_mode_matches_legacy_rule_exactly(self):
        # The default mode must reproduce the shipped variants1 decision, ask-first epsilon then midpoint.
        from option_features.variants1.signing import epsilon_side
        rng = random.Random(7)
        for _ in range(3000):
            b = rng.randrange(1, 4000) * 100
            h = b + rng.randrange(0, 300) * 100
            p = rng.randrange(max(1, b - 200 * 100), h + 200 * 100)
            e = rng.randrange(0, 300) * 100
            got = quotes.sign_trade(dec(p), (dec(b), dec(h), -NS), 0, epsilon=dec(e))
            side, _ = epsilon_side(float(Fraction(dec(p))), float(Fraction(dec(b))), float(Fraction(dec(h))), float(Fraction(dec(e))))
            want = {"buy": "ask", "sell": "bid", "unknown": None}[side]
            self.assertEqual(got.side, want, (p, b, h, e))


class WindowTests(unittest.TestCase):
    def test_index_equals_scan(self):
        rng = random.Random(11)
        for _ in range(60):
            prints = [(rng.randrange(-200, 50) * NS, rng.choice(("call", "put")), dec(rng.randrange(1, 900)),
                       rng.randrange(1, 40), rng.choice((100, 100, 100, 10))) for _ in range(rng.randrange(0, 60))]
            index = windows.WindowIndex(prints)
            for _ in range(8):
                w = rng.randrange(0, 120) * NS
                end = rng.choice((None, 0, rng.randrange(-100, 30) * NS))
                self.assertEqual(index.query(w, end), windows.window_premium(prints, w, end))
            self.assertEqual(index.query_many(60 * NS, [0, -NS]), [windows.window_premium(prints, 60 * NS, e) for e in (0, -NS)])

    def test_legacy_without_standard_print(self):
        r = windows.window_premium([(0, "call", "1", 1, 10)], 5)
        self.assertEqual((r.total_premium, r.window_start_ns, r.window_end_ns, r.excluded_nonstandard_count), (0, None, None, 1))

    def test_coverage_index_equals_scan(self):
        rng = random.Random(13)
        for _ in range(60):
            updates = [(rng.randrange(-400, 20) * NS, rng.random() < 0.7) for _ in range(rng.randrange(0, 30))]
            index = windows.QuoteUpdateIndex(updates)
            for _ in range(8):
                t = rng.randrange(-100, 10) * NS
                self.assertEqual(index.coverage(t, 300 * NS, 5), windows.quote_count_coverage(updates, t, 300 * NS, 5))


class SharesTests(unittest.TestCase):
    def test_joint_amounts_agree_with_single_reference_joint_measures(self):
        rng = random.Random(17)
        for _ in range(100):
            prints = [(rng.choice(("call", "put")), dec(rng.randrange(900, 1100) * 100),
                       rng.choice((None, 100 + rng.randrange(-2, 8))), rng.choice((None, dec(100 * 10000))),
                       dec(rng.randrange(1, 900)), rng.randrange(1, 40)) for _ in range(rng.randrange(1, 25))]
            full = shares.single_reference_shares(prints, 100, short_dte_max_days=2)
            joint = shares.joint_amounts(prints, 100, short_dte_max_days=2)
            for measure, amount in ((full.joint_short_dte, joint.joint_short_premium), (full.joint_otm, joint.joint_otm_premium)):
                if measure.status == "available":
                    self.assertEqual(measure.premium, amount)
            if full.joint_otm.status == "available":
                self.assertEqual(full.joint_otm.coverage * full.total_premium, joint.reference_premium)

    def test_threshold_validated_and_empty_input(self):
        with self.assertRaises(ValueError):
            shares.single_reference_shares([], 1, short_dte_max_days=2, short_min_share="1.5")
        r = shares.single_reference_shares([], 1, short_dte_max_days=2)
        self.assertEqual((r.status, r.reason), ("unavailable", "missing_reference"))


if __name__ == "__main__":
    unittest.main()
