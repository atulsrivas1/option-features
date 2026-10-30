"""Equivalence of the aligned story B modules (printtape, m2prints, episodes on the shared flowresult and flowgrid)
against the pre-alignment modules kept as an oracle copy (tests/m2/m2b_oracle/old_*.py, taken from main at the
base commit 88cb806, imports renamed): the canonical wire line of every output must be identical on random cases,
including malformed, structural and boundary inputs, for the single, batched and sweep paths.

M2B_EQUIV_N sets the number of random cases (default 20,000 in the suite; the alignment evidence ran 200,000+).
Label: synthetic workload, relative engineering budget (no claim about recorded data). Synthetic fixtures only.
"""
import os
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "m2b_oracle"))

import old_episodes as OE  # noqa: E402
import old_m2prints as OM  # noqa: E402
import old_printtape as OP  # noqa: E402
from option_features import episodes as E, flowresult as FR, m2prints as M, printtape as PT  # noqa: E402
from test_m2b_properties import LANES, NS, OPEN, make_contracts, make_prints  # noqa: E402

N_CASES = int(os.environ.get("M2B_EQUIV_N", "20000"))
WINDOWS = (60, 300, 900, 1800, 3600, 120, 300.0, 0, True)
NS_PARAMS = (3, 1, 2, "3/2", "5/2", ".5", 0.5, "1_0", True, None, "7/4", 15, "1/0")
THRESHOLDS = (1, 100_000, 1_000_000_000, 5_000_000, 1.5, True)
SHARES = ("3/5", "1/2", 0.6, "9/25", "1", "0")
FLTS = ("all", "calls", "puts")


def new_line(r):
    return FR.canonical_line(r)


def old_line(r):
    return OM.canonical_line(r).rstrip("\n")


def corrupt(rng, prints, cons):
    """Inject one structural problem into a print list (or none)."""
    if not prints:
        return prints
    prints = [list(p) for p in prints]
    kind = rng.randrange(15)
    i = rng.randrange(len(prints))
    p = prints[i]
    if kind == 0:
        p[1] = p[1] - rng.choice((10, 10 ** 12)) * NS            # out of order
    elif kind == 1:
        p[3] = -1
    elif kind == 2:
        p[2] = rng.choice(("-1.0000", -5))
    elif kind == 3:
        p[4] = rng.choice((0, -100))
    elif kind == 4:
        p[0] = "NOPE"
    elif kind == 5:
        p[2] = rng.choice(("1.00001", "x", "1e3", " 1", "1_0", 1.5, True, None, ""))
    elif kind == 6:
        p[3] = rng.choice((1.0, "3", None))
    elif kind == 7:
        p[4] = rng.choice((100.0, "100", None))
    elif kind == 8:
        p[5] = rng.choice((2, 3, "x", None, 1.0, 0.0))
    elif kind == 9:
        p[6] = rng.choice((True, 1.5, None, "7"))
    elif kind == 10:
        p[1] = rng.choice((1.5, None, "5"))
    elif kind == 11:
        p[2] = rng.choice(("1.", ".5", "1.50000", "0.0000", "-0", 0))
    elif kind == 12:
        from decimal import Decimal
        from fractions import Fraction
        p[2] = rng.choice((Decimal("1.0000"), Decimal("12.5"), Fraction(3, 2), Fraction(1, 1)))
    return [tuple(q) for q in prints]


DIVERGENT = []
case_id = [0]


def classify(prints, old_error=None, new_error=None):
    """Class of an intended old-versus-new difference ('' when the streams hold none of the changed inputs)."""
    from decimal import Decimal
    from fractions import Fraction
    kinds = set()
    for p in prints:
        if isinstance(p[2], Decimal):
            kinds.add("price is a Decimal (old accepted it, now malformed_type)")
        elif isinstance(p[2], Fraction):
            kinds.add("price is a Fraction (old accepted it, now malformed_type)")
        if type(p[5]) is float:
            kinds.add("condition_excluded is a float 0.0/1.0 (old accepted it, now malformed_type)")
    if old_error == "unordered_prints" and new_error == "malformed_type":
        kinds.add("order violation next to a wrong-typed time or seq (old unordered_prints, now malformed_type; rows M2A-TYP-031 to 034)")
    if old_error is not None and old_error != new_error and not kinds:
        return "UNCLASSIFIED %s -> %s" % (old_error, new_error)
    return "; ".join(sorted(kinds))


def run_case(rng):
    cons = make_contracts(rng)
    n = rng.choice((0, 1, 2, 5, 12, 30, 60))
    prints = make_prints(rng, cons, n, rng.choice((600, 2400, 5400)), text_prices=rng.random() < 0.7,
                         ties=rng.random() < 0.7) if n else []
    if rng.random() < 0.35:
        prints = corrupt(rng, prints, cons)
    if rng.random() < 0.15:
        prints = [(p[0], p[1] - 4000 * NS) + tuple(p[2:]) if rng.random() < 0.3 and isinstance(p[1], int) else p for p in prints]
        prints.sort(key=lambda p: (p[1], p[6]) if isinstance(p[1], int) and isinstance(p[6], int) else (0, 0))
    open_ns = rng.choice((OPEN, OPEN, OPEN, OPEN + 100 * NS, OPEN - 300 * NS, None, 1.5))
    ts = [p[1] for p in prints if isinstance(p[1], int)]
    base = rng.choice(ts) if ts else OPEN + 1000 * NS
    T = base + rng.choice((0, 0, 1, -1, 60 * NS, -60 * NS, 300 * NS, 900 * NS, -900 * NS, 3600 * NS, -2000 * NS))
    lane = rng.choice(LANES)
    flt = rng.choice(FLTS) if rng.random() < 0.9 else "bogus"
    delayed = rng.random() < 0.1
    cal = rng.random() < 0.9
    kw = dict(lane=lane, delayed=delayed, series_id="S", session_id="D", session_in_calendar=cal)
    fam = rng.randrange(9)
    # the tape of each side; an unknown filter raises ValueError on both sides
    to, tn = OP.build_tape(prints, cons), PT.build_tape(prints, cons)
    if to.error != tn.error or classify(prints):
        label = classify(prints, to.error, tn.error)
        DIVERGENT.append((label, case_id[0], repr(prints[:4])[:160], to.error, tn.error))
        if to.error != tn.error or label.startswith("price"):
            assert not label.startswith("UNCLASSIFIED"), (to.error, tn.error, prints[:4])
            return 0
    if to.error is None:
        assert (to.n_prints, to.n_eligible) == (tn.n_prints, tn.n_eligible)
    pairs = []
    n_ = rng.choice(NS_PARAMS)
    w = rng.choice(WINDOWS)
    thr = rng.choice(THRESHOLDS)
    cuts = [T + rng.choice((0, 1, -1, 10 * NS, -10 * NS, 300 * NS, -300 * NS, 2000 * NS)) for _ in range(rng.choice((1, 3, 6)))]
    try:
        if fam in (0, 1) and not isinstance(open_ns, int):
            fam = 2
        if fam == 0:
            pairs.append((OM.f1_premium_surge(to, T, open_ns, n=n_, flt=flt, **kw), M.f1_premium_surge(tn, T, open_ns, n=n_, flt=flt, **kw)))
        elif fam == 1:
            pairs += list(zip(OM.f1_sweep(to, cuts, open_ns, n=n_, flt=flt, **kw), M.f1_sweep(tn, cuts, open_ns, n=n_, flt=flt, **kw)))
        elif fam == 2:
            a = dict(window_s=w, threshold_ticks=thr, n=n_, flt=flt, open_ns=open_ns, **kw)
            pairs.append((OM.f4_large_prints(to, T, **a), M.f4_large_prints(tn, T, **a)))
            pairs += list(zip(OM.f4_sweep(to, cuts, **a), M.f4_sweep(tn, cuts, **a)))
        elif fam == 3:
            kw17 = {k: v for k, v in kw.items() if k != "series_id"}
            a = dict(window_s=rng.choice((300, 300, 600, 300.0)), threshold_ticks=thr, flt=flt, open_ns=open_ns, **kw17)
            ids = sorted(cons)[:rng.choice((1, 3, 50))] + ["ghost"]
            pairs += list(zip(OM.f17_many(to, T, ids, **a), M.f17_many(tn, T, ids, **a)))
            for r_o, r_n in zip(OM.f17_sweep(to, cuts, ids, **a), M.f17_sweep(tn, cuts, ids, **a)):
                pairs += list(zip(r_o, r_n))
            if not (OP.build_tape(prints, cons).error) and isinstance(open_ns, int) and isinstance(thr, int) and not isinstance(thr, bool):
                assert OM.f17_columns(to, T, ids, flt=flt, lane=lane, open_ns=open_ns) == M.f17_columns(tn, T, ids, flt=flt, lane=lane, open_ns=open_ns)
                assert OM.f17_sweep_columns(to, cuts, ids, flt=flt, lane=lane, open_ns=open_ns) == M.f17_sweep_columns(tn, cuts, ids, flt=flt, lane=lane, open_ns=open_ns)
                assert (OM.f17_columns(to, T, ids, lane=lane, open_ns=open_ns, sparse=True)
                        == M.f17_columns(tn, T, ids, lane=lane, open_ns=open_ns, sparse=True))
        elif fam == 4:
            a = dict(window_s=w, share_threshold=rng.choice(SHARES), flt=flt, open_ns=open_ns, **kw)
            pairs.append((OM.f7_concentration(to, T, **a), M.f7_concentration(tn, T, **a)))
            pairs += list(zip(OM.f7_sweep(to, cuts, **a), M.f7_sweep(tn, cuts, **a)))
        elif fam == 5:
            al, am = rng.choice((("1/2", None), (None, "1/3"), ("3/5", "1/5"), (None, None), (0.5, None), ("x", None)))
            a = dict(window_s=w, at_least=al, at_most=am, open_ns=open_ns, **kw)
            pairs.append((OM.f18_put_share(to, T, **a), M.f18_put_share(tn, T, **a)))
            pairs += list(zip(OM.f18_sweep(to, cuts, **a), M.f18_sweep(tn, cuts, **a)))
        elif fam == 6:
            a = dict(n=n_, n_episodes=rng.choice((1, 2, 0, 1.5)), quiet_gap=rng.choice((1, 2, 5, 0, True)),
                     grid_s=rng.choice((60, 60, 60, 30, 60.0)), flt=flt, **{k: v for k, v in kw.items()})
            if isinstance(open_ns, int):
                pairs.append((OE.f12_from_tape(to, T, open_ns, **a), E.f12_from_tape(tn, T, open_ns, **a)))
                pairs += list(zip(OE.f12_sweep(to, cuts, open_ns, **a), E.f12_sweep(tn, cuts, open_ns, **a)))
        elif fam == 7:
            m = rng.choice((0, 5, 16, 40))
            p60 = [rng.choice((None, 0, 1000, 3000, 15000)) for _ in range(m)]
            p900 = [rng.choice((None, 0, 15000, 15000, 5000)) for _ in range(m)]
            a = dict(n=n_, n_episodes=rng.choice((1, 2)), quiet_gap=rng.choice((1, 3)), grid_s=rng.choice((60, 60, 30)),
                     **{k: v for k, v in kw.items()})
            op = open_ns if isinstance(open_ns, int) else OPEN
            pairs.append((OE.f12_episodes(p60, p900, T, op, **a), E.f12_episodes(p60, p900, T, op, **a)))
            if isinstance(a["n"], (int, str)) and not isinstance(a["n"], bool):
                f_o, f_n = OM.frac(a["n"]), M.frac(a["n"])
                assert f_o == f_n
        else:
            if isinstance(open_ns, int):
                up = rng.choice((0, 14, 15, 40, 90))
                if not to.error:
                    c_o, c_n = OE.f1_grid_columns(to, open_ns, up, flt, lane), E.f1_grid_columns(tn, open_ns, up, flt, lane)
                    assert c_o == c_n
    except ValueError as exc:
        # the old modules raised ValueError for an unknown filter; the total ones answer malformed_type instead
        assert "filter must be one of" in str(exc), exc
        r_n = (M.f1_premium_surge(tn, T, open_ns, n=n_, flt=flt, **kw) if fam == 0 else
               M.f4_large_prints(tn, T, window_s=w, threshold_ticks=thr, n=n_, flt=flt, open_ns=open_ns, **kw)
               if fam == 2 else None)
        assert r_n is None or (r_n.status, r_n.code) == ("invalid_input", "malformed_type"), (fam, r_n)
        DIVERGENT.append(("unknown filter (old raised ValueError, now malformed_type)", case_id[0], "flt=%r" % (flt,), "ValueError", "malformed_type"))
        return 0
    if flt == "bogus" and fam in (0, 1, 2, 3, 4, 6):
        # an unknown filter: the old modules raised ValueError, or answered another structural code first; the total
        # ones answer malformed_type at its slot (item 5, before the window and threshold codes): a recorded class
        for _o, r_n in pairs:
            assert r_n.status == "invalid_input" and r_n.code in ("malformed_type", "unordered_prints", "negative_size_or_price",
                                                                  "bad_multiplier", "unknown_contract"), r_n
        DIVERGENT.append(("unknown filter (old ValueError or a later code, now malformed_type)", case_id[0], "flt='bogus'", "-", "malformed_type"))
        return 0
    for r_o, r_n in pairs:
        assert old_line(r_o) == new_line(r_n), (fam, old_line(r_o), new_line(r_n))
        assert (r_o["status"], r_o["code"], r_o["reason"]) == (r_n.status, r_n.code, r_n.reason)
    return len(pairs)


class Equivalence(unittest.TestCase):
    def test_random_cases_identical_wire_lines(self):
        compared = 0
        for case in range(N_CASES):
            rng = random.Random(case * 7919 + 13)
            case_id[0] = case
            try:
                compared += run_case(rng)
            except AssertionError as exc:
                self.fail("case %d: %s" % (case, str(exc)[:600]))
        self.assertGreater(compared, N_CASES // 2)
        classes = {}
        for label, cid, ex, oe, ne in DIVERGENT:
            classes.setdefault(label, [0, cid, ex, oe, ne])[0] += 1
        self.assertFalse([k for k in classes if k.startswith("UNCLASSIFIED")], classes)
        print("equivalence: %d cases, %d outputs compared, %d changed-input cases" % (N_CASES, compared, len(DIVERGENT)))
        for k, v in sorted(classes.items()):
            print("  class %r: %d cases, e.g. case %d old=%s new=%s %s" % (k, v[0], v[1], v[3], v[4], v[2]))

    def test_price_parser_is_the_shared_one(self):
        from option_features import flowgrid
        self.assertIs(PT.price_ticks, flowgrid.price_ticks)
        for text in ("80.0000", "80", "1.", ".5", "-.5", "1.50000", "1.00001", "1e5", " 1", "", ".", "--1", "1_0", "١"):
            try:
                old = OP.ticks4(text)
            except ValueError:
                old = "error"
            try:
                new = flowgrid.price_ticks(text)
            except ValueError:
                new = "error"
            self.assertEqual(old, new, text)

    def test_tape_error_equals_shared_check_prints(self):
        from option_features import flowgrid
        for case in range(3000):
            rng = random.Random(case + 5)
            cons = make_contracts(rng)
            prints = make_prints(rng, cons, rng.choice((1, 4, 20)), 2400)
            if rng.random() < 0.7:
                prints = corrupt(rng, prints, cons)
            if any(type(p[k]) is not int for p in prints for k in (1, 3, 4, 6)):
                continue        # a wrong-typed time, size, multiplier or seq: rows M2A-TYP-031..034 pin the tape, not check_prints
            contracts = {cid: flowgrid.Contract(c[0], c[1], c[2], c[3], "U") for cid, c in cons.items()}
            self.assertEqual(PT.build_tape(prints, cons).error, flowgrid.check_prints(prints, contracts), prints)

    def test_grid_columns_equal_the_shared_builder(self):
        """The F1 grid (p60 and p900 premium at grid points 15 and later) equals story A's trade-to-grid builder."""
        from option_features import flowgrid
        for seed in range(1, 9):
            rng = random.Random(seed * 31)
            cons = make_contracts(rng)
            prints = make_prints(rng, cons, 250, 3000, text_prices=False)
            contracts = {cid: flowgrid.Contract(c[0], c[1], c[2], c[3], "U") for cid, c in cons.items()}
            minutes = 60
            built = flowgrid.build_session_records(prints, contracts, "2026-06-01", OPEN, OPEN + minutes * 60 * NS, minutes,
                                                   windows=(60, 900), lane="stock", name_series_id="U", contract_series=False)
            recs = {(r.metric, r.window_s): r for r in built.records if r.series_id == "U"}
            tape = PT.build_tape(prints, cons)
            p60, p900 = E.f1_grid_columns(tape, OPEN, minutes - 1, "all", "stock")
            for w, col in ((60, p60), (900, p900)):
                rec = recs[("premium", w)]
                dense = [0] * minutes
                for i, v in zip(rec.idx, rec.vals):
                    dense[i] = v
                self.assertEqual(col[15:], dense[15:minutes], (seed, w))


if __name__ == "__main__":
    unittest.main()
